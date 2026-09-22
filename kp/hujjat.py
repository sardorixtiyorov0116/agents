"""KP hujjatini yaratish: PDF va Word.

Ko'rinish kompaniyaning haqiqiy KP blankasiga (КП_12951-26) moslashtirilgan:
logotip, o'ng tomonda murojaat, markazda sarlavha, 8 ustunli jadval (har
qatorda QQS va QQSli summa), "Итого" qatori, menejer bloki, shartlar matni,
narx amal qilish muddati va direktor imzosi.

Ikkala format bitta `KP` modelidan chiqadi — summa farq qilmasligi uchun
hisob-kitob modelda, bu yerda faqat formatlash.

Narx topilmagan qator BO'SH ustun bilan chiqadi — taxminiy raqam yozilmaydi.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import sozlama

from .model import KP

MATNLAR = {
    "ru": {
        "bosh": "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ",
        "sana_old": "от",
        "sana_keyin": "г.",
        "murojaat": "Руководителю",
        "n": "№",
        "nomi": "Наименование",
        "birlik": "Ед. изм",
        "miqdor": "Кол-во",
        "narx": "Цена за шт",
        "summa": "Сумма",
        "qqs": "НДС",
        "qqs_bilan": "Сумма с учетом НДС",
        "jami": "Итого:",
        "menejer": "Менеджер продаж",
        "tel": "тел",
        "narx_amal": "*Цены на продукцию действительны от {boshi} по {oxiri}",
        "hurmat": "С уважением,",
        "toldirilsin": "цена требует заполнения",
        "toliq_emas": "(НЕПОЛНАЯ — {soni} позиц. без цены)",
    },
    "uz": {
        "bosh": "TIJORAT TAKLIFI",
        "sana_old": "sana",
        "sana_keyin": "y.",
        "murojaat": "Rahbariga",
        "n": "№",
        "nomi": "Nomi",
        "birlik": "O'lchov",
        "miqdor": "Miqdor",
        "narx": "Birlik narxi",
        "summa": "Summa",
        "qqs": "QQS",
        "qqs_bilan": "QQS bilan summa",
        "jami": "Jami:",
        "menejer": "Savdo menejeri",
        "tel": "tel",
        "narx_amal": "*Mahsulot narxlari {boshi} dan {oxiri} gacha amal qiladi",
        "hurmat": "Hurmat bilan,",
        "toldirilsin": "narx to'ldirilishi kerak",
        "toliq_emas": "(TO'LIQ EMAS — {soni} pozitsiyada narx yo'q)",
    },
}

QIZIL = colors.HexColor("#B03020")
QIZIL_DOCX = RGBColor(0xB0, 0x30, 0x20)

# Blanka o'lchamlari — namunaviy КП_12951-26 dan olingan:
# logotip 193 mm keng, matn chap chekkasi ~9 mm.
CHEKKA_MM = 9.0
BLANKA_KENGLIGI_MM = 192.0
# Rasm o'qilmasa ishlatiladigan zaxira nisbat (192/986 ≈ 0.195).
LOGO_NISBATI = 0.195

# Jadval sarlavhasi va "Итого" qatori foni — brend rangining juda och tusi.
FON = colors.HexColor("#EEF1F7")
FON_DOCX = "EEF1F7"
CHIZIQ = colors.HexColor("#808080")

# Nom ustunidagi tavsif shu belgidan oshmaydi (namunada 1-2 qator).
SPETS_MAKS = 140


def _m(kp: KP, kalit: str) -> str:
    return MATNLAR.get(kp.til, MATNLAR["ru"])[kalit]


def _rekvizit(kp: KP, kalit: str) -> str:
    """Rekvizit qiymati hujjat tilida.

    O'zbekcha KP da "Директор ООО «CLIMAVENT»" turishi noto'g'ri. Har
    rekvizitning `_uz` variantini `rekvizitlar.yaml` ga qo'shish mumkin
    (`nomi_uz`, `direktor_lavozimi_uz`, ...); yo'q bo'lsa asosiysi qoladi —
    shuning uchun fayl to'ldirilmagan bo'lsa ham hujjat buzilmaydi.
    """
    if kp.til == "uz":
        ozbekchasi = kp.rekvizitlar.get(f"{kalit}_uz")
        if ozbekchasi:
            return str(ozbekchasi)
    return str(kp.rekvizitlar.get(kalit, "") or "")


def _kompaniya(kp: KP) -> str:
    return _rekvizit(kp, "nomi")


def _sana(kp: KP) -> str:
    return kp.sana.strftime("%d.%m.%Y")


def _narx_oralig(kp: KP) -> str:
    oxiri = kp.narx_amal_oxiri or (kp.sana + timedelta(days=30))
    return _m(kp, "narx_amal").format(
        boshi=f"{_sana(kp)}{_m(kp, 'sana_keyin')}", oxiri=f"{oxiri.strftime('%d.%m.%Y')}{_m(kp, 'sana_keyin')}"
    )


def _logo_yoli(kp: KP) -> Path | None:
    nomi = kp.rekvizitlar.get("logo")
    if not nomi:
        return None
    yol = sozlama().bilim_papkasi / "sales" / nomi
    return yol if yol.is_file() else None


def _logo_balandligi(logo: Path, kenglik_mm: float) -> float:
    """Blanka balandligi rasm nisbatidan hisoblanadi.

    Qat'iy raqam yozilmaydi: logotip almashtirilsa ham cho'zilib ketmasin.
    Blankada telefon, email va manzil RASM ICHIDA — nisbat buzilsa yoki
    rasm kichraytirilsa, aynan shu kontaktlar o'qilmay qoladi.
    """
    try:
        from PIL import Image as PilImage

        with PilImage.open(logo) as rasm:
            en, boy = rasm.size
        if en > 0 and boy > 0:
            return kenglik_mm * boy / en
    except Exception:
        pass
    return kenglik_mm * LOGO_NISBATI


def _qisqa_spetsifikatsiya(matn: str) -> str:
    """Jadval katagiga sig'adigan qisqa tavsif.

    Namunaviy KP da nom ustuni ikki qatordan oshmaydi. To'liq texnik tavsif
    KP ga emas, alohida spetsifikatsiyaga tegishli — bu yerda uzun matn
    jadvalni buzadi va hujjat ikkinchi sahifaga ketadi.
    Kesish GAP OXIRIDA bo'ladi: yarim jumla qolmasin.
    """
    matn = " ".join((matn or "").split())
    if len(matn) <= SPETS_MAKS:
        return matn
    kesilgan = matn[:SPETS_MAKS]
    for ajratgich in (". ", "; ", ", "):
        joyi = kesilgan.rfind(ajratgich)
        if joyi > SPETS_MAKS // 2:
            return kesilgan[:joyi] + "."
    return kesilgan.rsplit(" ", 1)[0] + "…"


def _jadval_malumoti(kp: KP) -> tuple[list[list[str]], list[int]]:
    """Jadval qatorlari va narxsiz qatorlar indekslari."""
    boshlar = [
        _m(kp, "n"), _m(kp, "nomi"), _m(kp, "birlik"), _m(kp, "miqdor"),
        _m(kp, "narx"), _m(kp, "summa"),
        f"{_m(kp, 'qqs')} {kp.qqs_foizi:g}%", _m(kp, "qqs_bilan"),
    ]
    qatorlar = [boshlar]
    narxsizlar: list[int] = []

    for i, qator in enumerate(kp.qatorlar, 1):
        nomi = qator.nomi
        if qator.spetsifikatsiya:
            nomi = f"{nomi}\n{_qisqa_spetsifikatsiya(qator.spetsifikatsiya)}"
        if qator.narxsizmi:
            narxsizlar.append(i)
            narx_matni = f"[{_m(kp, 'toldirilsin')}]"
        else:
            narx_matni = kp.son(qator.birlik_narx)
        qatorlar.append([
            str(i), nomi, qator.birlik, f"{qator.miqdor:g}",
            narx_matni, kp.son(qator.jami),
            kp.son(qator.qqs), kp.son(qator.qqs_bilan),
        ])

    # "Итого:" birinchi katakda bo'lishi SHART — keyingi kataklar u bilan
    # birlashtiriladi va birlashuvda faqat birinchi katak matni ko'rinadi.
    # QQS katagi namunadagidek BO'SH qoladi: yakunda faqat summa va
    # QQS bilan summa ko'rsatiladi.
    #
    # NARXSIZ QATOR BO'LSA — "Jami" TO'LIQ EMAS.
    #
    # Jonli holat (2026-08-26, KP-2026-12982): to'rt qatordan ikkitasida
    # narx yo'q edi (ventilyator va issiqlik almashtirgich — eng qimmat
    # pozitsiyalar), "Итого" esa 2 419 200 deb turardi. Bu faqat
    # panjaralarning summasi edi, lekin hujjatda buni ko'rsatadigan
    # hech narsa yo'q — o'quvchi butun tizim shu pulga tushadi deb
    # tushunardi.
    jami_yorligi = _m(kp, "jami")
    if narxsizlar:
        jami_yorligi += " " + _m(kp, "toliq_emas").format(soni=len(narxsizlar))
    qatorlar.append([
        jami_yorligi, "", "", "", "",
        kp.son(kp.summa), "", kp.son(kp.jami),
    ])
    return qatorlar, narxsizlar


# --- PDF ---------------------------------------------------------------------

_shrift_tayyor = False


def _shriftlar() -> tuple[str, str]:
    """Unicode shrifti (kirill uchun).

    Birinchi o'rinda Times New Roman: namunaviy КП aynan shu shriftda
    tayyorlangan. Topilmasa — kirillni qo'llab-quvvatlaydigan zaxiralar.
    """
    global _shrift_tayyor
    nomzodlar = [
        (r"C:\Windows\Fonts\times.ttf", r"C:\Windows\Fonts\timesbd.ttf", "Times"),
        ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", "LibSerif"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "DejaVuSerif"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf", "Arial"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu"),
    ]
    for oddiy_yol, qalin_yol, nomi in nomzodlar:
        if not Path(oddiy_yol).is_file():
            continue
        if not _shrift_tayyor:
            pdfmetrics.registerFont(TTFont(nomi, oddiy_yol))
            if Path(qalin_yol).is_file():
                pdfmetrics.registerFont(TTFont(f"{nomi}-Bold", qalin_yol))
                # SHART: busiz `<b>` tegi ishlamaydi — reportlab qalin
                # variantni faqat oila orqali topadi, nom o'xshashligi yetmaydi.
                pdfmetrics.registerFontFamily(
                    nomi, normal=nomi, bold=f"{nomi}-Bold",
                    italic=nomi, boldItalic=f"{nomi}-Bold",
                )
            _shrift_tayyor = True
        return nomi, (f"{nomi}-Bold" if Path(qalin_yol).is_file() else nomi)
    return "Times-Roman", "Times-Bold"


def pdf_yasa(kp: KP, yol: Path) -> Path:
    """KP ni PDF sifatida saqlaydi (namunaviy blanka ko'rinishida)."""
    oddiy, qalin = _shriftlar()
    yol.parent.mkdir(parents=True, exist_ok=True)

    # DIQQAT: `SimpleDocTemplate` freymga har tomondan 6pt ichki bo'shliq
    # qo'shadi va uni sozlash imkoni yo'q. Shu 6pt tufayli abzaslar jadvalga
    # nisbatan ichkariga surilib qolardi ("С уважением," 11.1mm, jadval 9.0mm).
    # Chekkadan o'sha 6pt ni ayiramiz — natijada hamma narsa aniq 9 mm dan
    # boshlanadi va kenglik ham 192 mm bo'lib qoladi.
    freym_ichki = 6
    hujjat = SimpleDocTemplate(
        str(yol), pagesize=A4,
        topMargin=10 * mm - freym_ichki, bottomMargin=12 * mm - freym_ichki,
        leftMargin=CHEKKA_MM * mm - freym_ichki,
        rightMargin=CHEKKA_MM * mm - freym_ichki,
        title=f"{_m(kp, 'bosh')} {kp.raqam}",
    )

    asos = getSampleStyleSheet()
    u = ParagraphStyle("u", parent=asos["Normal"], fontName=oddiy, fontSize=9, leading=11.5)
    u_kichik = ParagraphStyle("uk", parent=u, fontSize=7.8, leading=9.5)
    u_ong = ParagraphStyle("uo", parent=u, alignment=TA_RIGHT)
    u_bosh = ParagraphStyle("ub", parent=u, fontName=qalin, fontSize=11.5,
                            alignment=TA_CENTER, spaceBefore=6, spaceAfter=6)
    # Namunada kirish va shartlar matni MARKAZGA tekislangan.
    u_matn = ParagraphStyle("um", parent=u, alignment=TA_CENTER, fontSize=9, leading=12)
    u_qizil = ParagraphStyle("uq", parent=u_kichik, textColor=QIZIL)

    qismlar = []

    # --- logotip ---
    logo = _logo_yoli(kp)
    if logo:
        # Blanka butun kenglik bo'ylab — kontaktlar rasm ichida, kichraytirsa
        # o'qilmay qoladi.
        rasm = Image(
            str(logo),
            width=BLANKA_KENGLIGI_MM * mm,
            height=_logo_balandligi(logo, BLANKA_KENGLIGI_MM) * mm,
        )
        rasm.hAlign = "LEFT"
        qismlar.append(rasm)
        qismlar.append(Spacer(1, 4 * mm))

    # --- raqam / sana (chap) va murojaat (o'ng) ---
    murojaat = [Paragraph(f"<b>{_m(kp, 'murojaat')}</b>", u_ong)]
    if kp.mijoz.nomi:
        murojaat.append(Paragraph(f"<b>{kp.mijoz.nomi}</b>", u_ong))
    # STIR VA OBYEKT BU YERGA YOZILMAYDI.
    #
    # Murojaat bloki namunaviy blankada faqat «Руководителю» + tashkilot
    # nomidan iborat. STIR shartnoma va hisob-fakturaga tegishli,
    # KP sarlavhasiga emas. Ikkalasi ham `Mijoz` modelida SAQLANADI —
    # menejer mijozdan so'ragani bekorga ketmaydi va shartnoma
    # bosqichida qo'l ostida bo'ladi.
    if kp.mijoz.aloqa:
        murojaat.append(Paragraph(kp.mijoz.aloqa, u_ong))

    bosh_jadval = Table(
        [[
            [Paragraph(f"<b>{_m(kp, 'n')} {kp.raqam}</b>", u),
             Paragraph(
                 f"<b>{_m(kp, 'sana_old')} {_sana(kp)} {_m(kp, 'sana_keyin')}</b>", u
             )],
            murojaat,
        ]],
        colWidths=[100 * mm, 92 * mm],
    )
    bosh_jadval.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    qismlar.append(bosh_jadval)

    qismlar.append(Paragraph(_m(kp, "bosh"), u_bosh))

    if kp.kirish_matni:
        nomi = _kompaniya(kp)
        qismlar.append(Paragraph(f"<b>{nomi}</b> {kp.kirish_matni}", u_matn))
        qismlar.append(Spacer(1, 3 * mm))

    # --- jadval ---
    xom, narxsizlar = _jadval_malumoti(kp)
    # Ustun tekisligi: raqam va o'lchov markazda, pul o'ngda, nom chapda.
    # DIQQAT: `TableStyle("ALIGN")` Paragraph flowable'ga ta'sir qilmaydi —
    # tekislash abzas uslubining o'zida berilishi shart.
    TEKISLIK = {0: TA_CENTER, 1: TA_LEFT, 2: TA_CENTER, 3: TA_CENTER}

    malumot = []
    for i, qator in enumerate(xom):
        oxirgimi = i == len(xom) - 1
        if i == 0:
            malumot.append([
                Paragraph(
                    f"<b>{k}</b>",
                    ParagraphStyle(f"b{j}", parent=u_kichik, alignment=TA_CENTER),
                )
                for j, k in enumerate(qator)
            ])
            continue
        uslub = u_kichik if not oxirgimi else ParagraphStyle("j", parent=u_kichik, fontName=qalin)
        katakar = []
        for j, katak in enumerate(qator):
            if j == 4 and i in narxsizlar:
                katakar.append(Paragraph(katak, u_qizil))
                continue
            # "Итого:" birlashgan katakda chapda turadi (namunadagidek).
            yonalish = TA_LEFT if (oxirgimi and j == 0) else TEKISLIK.get(j, TA_RIGHT)
            tekis = ParagraphStyle(f"r{i}{j}", parent=uslub, alignment=yonalish)
            katakar.append(Paragraph(katak.replace("\n", "<br/>"), tekis))
        malumot.append(katakar)

    jadval = Table(
        malumot,
        colWidths=[7 * mm, 62 * mm, 11 * mm, 14 * mm, 25 * mm, 25 * mm, 23 * mm, 25 * mm],
        repeatRows=1,
    )
    oxirgi = len(malumot) - 1
    jadval.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, CHIZIQ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        # Sarlavha va yakuniy qator ajralib tursin.
        ("BACKGROUND", (0, 0), (-1, 0), FON),
        ("BACKGROUND", (0, oxirgi), (-1, oxirgi), FON),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, CHIZIQ),
        ("LINEABOVE", (0, oxirgi), (-1, oxirgi), 0.8, CHIZIQ),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (3, -1), "CENTER"),
        # "Итого" qatori — chap kataklar birlashtiriladi
        ("SPAN", (0, len(malumot) - 1), (4, len(malumot) - 1)),
        ("ALIGN", (0, len(malumot) - 1), (4, len(malumot) - 1), "LEFT"),
    ]))
    qismlar.append(jadval)
    qismlar.append(Spacer(1, 5 * mm))

    # --- ogohlantirishlar ---
    for ogoh in kp.ogohlantirishlar:
        qismlar.append(Paragraph(f"⚠ {ogoh}", u_qizil))
    if kp.ogohlantirishlar:
        qismlar.append(Spacer(1, 3 * mm))

    # --- shartlar ---
    for matn in kp.shartlar_matni:
        qismlar.append(Paragraph(matn, u_matn))
        qismlar.append(Spacer(1, 1.5 * mm))

    qismlar.append(Spacer(1, 1 * mm))
    qismlar.append(Paragraph(_narx_oralig(kp), u_matn))
    qismlar.append(Spacer(1, 6 * mm))

    # --- imzo (namunadagidek to'liq qalin) ---
    qismlar.append(Paragraph(f"<b>{_m(kp, 'hurmat')}</b>", u))
    lavozim = _rekvizit(kp, "direktor_lavozimi")
    direktor = _rekvizit(kp, "direktor")
    if lavozim or direktor:
        imzo = Table(
            [[Paragraph(f"<b>{lavozim} {_kompaniya(kp)}</b>", u),
              Paragraph(f"<b>{direktor}</b>", u_ong)]],
            colWidths=[116 * mm, 76 * mm],
        )
        imzo.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        qismlar.append(imzo)

    # --- menejer (namunadagidek — imzodan KEYIN, eng pastda) ---
    menejer = kp.rekvizitlar.get("menejer")
    if menejer:
        qismlar.append(Spacer(1, 8 * mm))
        qismlar.append(Paragraph(f"{_m(kp, 'menejer')}: {menejer}", u_kichik))
        telefon = kp.rekvizitlar.get("menejer_telefon")
        if telefon:
            qismlar.append(Paragraph(f"{_m(kp, 'tel')}: {telefon}", u_kichik))

    hujjat.build(qismlar)
    return yol


# --- Word --------------------------------------------------------------------


def _katak_foni(katak, rang: str) -> None:
    """Word katagiga fon rangi beradi (python-docx da tayyor API yo'q)."""
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement

    soya = OxmlElement("w:shd")
    soya.set(qn("w:val"), "clear")
    soya.set(qn("w:fill"), rang)
    katak._tc.get_or_add_tcPr().append(soya)


def docx_yasa(kp: KP, yol: Path) -> Path:
    """KP ni Word hujjati sifatida saqlaydi (PDF bilan bir xil tuzilma)."""
    hujjat = Document()
    bolim = hujjat.sections[0]
    bolim.top_margin = Cm(1.0)
    bolim.bottom_margin = Cm(1.2)
    bolim.left_margin = Cm(CHEKKA_MM / 10)
    bolim.right_margin = Cm(CHEKKA_MM / 10)

    uslub = hujjat.styles["Normal"]
    uslub.font.name = "Times New Roman"
    uslub.font.size = Pt(9)

    logo = _logo_yoli(kp)
    if logo:
        # Blanka butun kenglik bo'ylab: kontaktlar rasm ichida turadi.
        abzas = hujjat.add_paragraph()
        abzas.paragraph_format.space_after = Pt(8)
        abzas.add_run().add_picture(str(logo), width=Cm(BLANKA_KENGLIGI_MM / 10))

    # --- raqam / murojaat ---
    bosh = hujjat.add_table(rows=1, cols=2)
    chap, ong = bosh.rows[0].cells
    chap.width = Cm(10.0)
    ong.width = Cm(9.2)

    p = chap.paragraphs[0]
    p.add_run(f"{_m(kp, 'n')} {kp.raqam}").bold = True
    chap.add_paragraph().add_run(
        f"{_m(kp, 'sana_old')} {_sana(kp)} {_m(kp, 'sana_keyin')}"
    ).bold = True

    p = ong.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run(_m(kp, "murojaat")).bold = True
    if kp.mijoz.nomi:
        q = ong.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        q.add_run(kp.mijoz.nomi).bold = True
    # STIR va obyekt bu yerga yozilmaydi — PDF blokidagi izohga qara.
    if kp.mijoz.aloqa:
        q = ong.add_paragraph(kp.mijoz.aloqa)
        q.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    sarlavha = hujjat.add_paragraph()
    sarlavha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    yugurish = sarlavha.add_run(_m(kp, "bosh"))
    yugurish.bold = True
    yugurish.font.size = Pt(12)

    if kp.kirish_matni:
        kirish = hujjat.add_paragraph()
        kirish.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        kirish.add_run(_kompaniya(kp)).bold = True
        kirish.add_run(f" {kp.kirish_matni}")

    # --- jadval ---
    xom, narxsizlar = _jadval_malumoti(kp)
    kengliklar = [Cm(0.7), Cm(6.2), Cm(1.2), Cm(1.5), Cm(2.5), Cm(2.5), Cm(2.3), Cm(2.3)]
    jadval = hujjat.add_table(rows=0, cols=8)
    jadval.style = "Table Grid"
    jadval.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, qator in enumerate(xom):
        kataklar = jadval.add_row().cells
        oxirgimi = i == len(xom) - 1
        # Sarlavha va "Итого" qatori — PDF dagidek och fon bilan ajratiladi.
        fonli = i == 0 or oxirgimi
        for j, (katak, qiymat, kenglik) in enumerate(zip(kataklar, qator, kengliklar)):
            katak.width = kenglik
            if fonli:
                _katak_foni(katak, FON_DOCX)
            abzas = katak.paragraphs[0]
            if fonli and j == 0:
                pass  # "Итого:" chapda qoladi
            elif j >= 4:
                abzas.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            elif j != 1:
                abzas.alignment = WD_ALIGN_PARAGRAPH.CENTER
            yugurish = abzas.add_run(qiymat)
            yugurish.font.size = Pt(7.8)
            yugurish.bold = fonli
            if j == 4 and i in narxsizlar:
                yugurish.font.color.rgb = QIZIL_DOCX
                yugurish.italic = True

    hujjat.add_paragraph()

    for ogoh in kp.ogohlantirishlar:
        abzas = hujjat.add_paragraph()
        yugurish = abzas.add_run(f"⚠ {ogoh}")
        yugurish.font.color.rgb = QIZIL_DOCX
        yugurish.font.size = Pt(8)
        yugurish.bold = True

    for matn in kp.shartlar_matni:
        abzas = hujjat.add_paragraph(matn)
        abzas.alignment = WD_ALIGN_PARAGRAPH.CENTER
        abzas.runs[0].font.size = Pt(9)

    abzas = hujjat.add_paragraph(_narx_oralig(kp))
    abzas.alignment = WD_ALIGN_PARAGRAPH.CENTER
    abzas.runs[0].font.size = Pt(9)

    hujjat.add_paragraph()
    hujjat.add_paragraph().add_run(_m(kp, "hurmat")).bold = True
    lavozim = _rekvizit(kp, "direktor_lavozimi")
    direktor = _rekvizit(kp, "direktor")
    if lavozim or direktor:
        imzo = hujjat.add_table(rows=1, cols=2)
        chap, ong = imzo.rows[0].cells
        chap.paragraphs[0].add_run(
            f"{lavozim} {_kompaniya(kp)}"
        ).bold = True
        p = ong.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.add_run(direktor).bold = True

    # Menejer bloki — namunadagidek imzodan KEYIN, hujjatning eng pastida.
    menejer = kp.rekvizitlar.get("menejer")
    if menejer:
        hujjat.add_paragraph()
        for matn in (
            f"{_m(kp, 'menejer')}: {menejer}",
            f"{_m(kp, 'tel')}: {kp.rekvizitlar['menejer_telefon']}"
            if kp.rekvizitlar.get("menejer_telefon")
            else "",
        ):
            if not matn:
                continue
            abzas = hujjat.add_paragraph(matn)
            abzas.runs[0].font.size = Pt(8)

    yol.parent.mkdir(parents=True, exist_ok=True)
    hujjat.save(str(yol))
    return yol


def hujjatlarni_yasa(kp: KP, papka: Path) -> dict[str, Path]:
    """Ikkala formatni ham yaratadi: tahrirlash uchun docx, yuborish uchun pdf."""
    asos = kp.raqam.replace("/", "-")
    return {
        "docx": docx_yasa(kp, papka / f"KP_{asos}.docx"),
        "pdf": pdf_yasa(kp, papka / f"KP_{asos}.pdf"),
    }

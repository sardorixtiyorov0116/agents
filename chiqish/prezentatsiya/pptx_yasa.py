"""Prezentatsiyaning PowerPoint (.pptx) ko'rinishini yasaydi.

HTML variantidagi mazmun, rang tizimi va roliklar saqlanadi.

RANG — o'rta ton
----------------
Fon oq emas, qora ham emas: mayin ko'kimtir kul. Kartochkalar oq
bo'lib undan ajralib turadi. Proyektorda ham, ekranda ham o'qiladi.

Ikki aksent MA'NO tashiydi va butun taqdimotda bir xil:
    teal    = mashina, agent, avtomatik
    kahrabo = inson, qaror, tasdiq

ROLIKLAR
--------
To'rtta slaydda haqiqiy PowerPoint animatsiyasi bor (`animatsiya.py`).
Slayd ochilishi bilan o'zi ishlaydi — bosish shart emas.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt


CHIQISH = Path(__file__).parent / "AI-agentlar-prezentatsiya.pptx"

# --- ranglar (HTML bilan bir xil) --------------------------------------------
FON = RGBColor(0xC3, 0xD0, 0xDF)
FON2 = RGBColor(0xB0, 0xC0, 0xD2)
KARTA = RGBColor(0xFC, 0xFD, 0xFE)
KARTA2 = RGBColor(0xED, 0xF2, 0xF8)
CHIZIQ = RGBColor(0x93, 0xA8, 0xC0)
MATN = RGBColor(0x0D, 0x16, 0x20)
XIRA = RGBColor(0x3B, 0x4F, 0x63)
JUDA_XIRA = RGBColor(0x64, 0x79, 0x8F)
HAVO = RGBColor(0x05, 0x63, 0x7D)
HAVO_YUM = RGBColor(0xDA, 0xEA, 0xF1)
INSON = RGBColor(0x94, 0x55, 0x0A)
INSON_YUM = RGBColor(0xF7, 0xE9, 0xCE)
YASHIL = RGBColor(0x0B, 0x64, 0x44)
YASHIL_YUM = RGBColor(0xDC, 0xEF, 0xE6)
QIZIL = RGBColor(0x9E, 0x2F, 0x2C)
QIZIL_YUM = RGBColor(0xF7, 0xE2, 0xE0)

SHRIFT = "Segoe UI"
MONO = "Consolas"

EN = Inches(13.333)
BOY = Inches(7.5)
CHET = Inches(0.85)
ICHKI_EN = EN - CHET * 2


# =============================================================================
# YORDAMCHILAR
# =============================================================================

def yangi_slayd(prs):
    slayd = prs.slides.add_slide(prs.slide_layouts[6])
    fon = slayd.background.fill
    fon.solid()
    fon.fore_color.rgb = FON
    return slayd


def quti(slayd, x, y, w, h, qatorlar, *, oraliq=0):
    shakl = slayd.shapes.add_textbox(x, y, w, h)
    ramka = shakl.text_frame
    ramka.word_wrap = True
    ramka.margin_left = ramka.margin_right = 0
    ramka.margin_top = ramka.margin_bottom = 0
    for i, (matn, olcham, rang, qalin, shrift) in enumerate(qatorlar):
        p = ramka.paragraphs[0] if i == 0 else ramka.add_paragraph()
        if i and oraliq:
            p.space_before = Pt(oraliq)
        yugur = p.add_run()
        yugur.text = matn
        yugur.font.size = Pt(olcham)
        yugur.font.color.rgb = rang
        yugur.font.bold = qalin
        yugur.font.name = shrift
        p.line_spacing = 1.16
    return shakl


def yorliq(slayd, matn, y=Inches(0.6), rang=HAVO):
    chiziqcha = slayd.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, CHET, y + Inches(0.10), Inches(0.26), Pt(2.5)
    )
    chiziqcha.fill.solid()
    chiziqcha.fill.fore_color.rgb = rang
    chiziqcha.line.fill.background()
    chiziqcha.shadow.inherit = False
    quti(slayd, CHET + Inches(0.4), y - Inches(0.02), Inches(9), Inches(0.3),
         [(matn.upper(), 10.5, rang, True, SHRIFT)])


def sarlavha(slayd, matn, y=Inches(1.08), olcham=38, en=None):
    return quti(slayd, CHET, y, en or ICHKI_EN, Inches(1.5),
                [(matn, olcham, MATN, True, SHRIFT)])


def tan(slayd, matn, y, olcham=16, rang=XIRA, en=None):
    return quti(slayd, CHET, y, en or Inches(9.8), Inches(1.4),
                [(matn, olcham, rang, False, SHRIFT)])


def panel(slayd, x, y, w, h, *, fon=KARTA, chek=CHIZIQ, radius=0.04):
    shakl = slayd.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shakl.adjustments[0] = radius
    shakl.fill.solid()
    shakl.fill.fore_color.rgb = fon
    shakl.line.color.rgb = chek
    shakl.line.width = Pt(1)
    shakl.shadow.inherit = False
    return shakl


def kartochka(slayd, x, y, w, h, belgi, bosh, tana, *, urgu=HAVO, chek=CHIZIQ):
    """Kartochka. Natija — guruhlash uchun asosiy shakl."""
    asos = panel(slayd, x, y, w, h, chek=chek)
    ichki = Inches(0.27)
    qatorlar = []
    if belgi:
        qatorlar.append((belgi.upper(), 9.5, urgu, True, MONO))
    qatorlar.append((bosh, 16, MATN, True, SHRIFT))
    qatorlar.append((tana, 12, XIRA, False, SHRIFT))
    quti(slayd, x + ichki, y + ichki, w - ichki * 2, h - ichki * 2,
         qatorlar, oraliq=6)
    return asos


def stat(slayd, x, y, w, h, son, izoh, rang=MATN):
    asos = panel(slayd, x, y, w, h)
    ichki = Inches(0.25)
    quti(slayd, x + ichki, y + ichki, w - ichki * 2, h - ichki * 2,
         [(son, 34, rang, True, MONO), (izoh, 11, XIRA, False, SHRIFT)],
         oraliq=5)
    return asos


def hisoblagich(slayd, n, jami):
    quti(slayd, CHET, BOY - Inches(0.52), Inches(2), Inches(0.3),
         [(f"{n:02d} / {jami:02d}", 10, JUDA_XIRA, False, MONO)])


def puf(slayd, x, y, w, matn, *, fon=FON2, rang=MATN, olcham=12.5,
        h=Inches(0.58), shrift=SHRIFT, chek=None, qalin=False):
    asos = panel(slayd, x, y, w, h, fon=fon, chek=chek or fon, radius=0.14)
    quti(slayd, x + Inches(0.2), y + Inches(0.12), w - Inches(0.4),
         h - Inches(0.24), [(matn, olcham, rang, qalin, shrift)])
    return asos


# =============================================================================
# SLAYDLAR
# =============================================================================

XODIMLAR = [
    ("Temur", "Tijorat menejeri", "Tijorat taklifini tuzadi"),
    ("Rustam", "Loyihachi muhandis", "Havo sarfi va bosimni hisoblaydi"),
    ("Sardor", "Mahsulot mutaxassisi", "Katalogdan mos model tanlaydi"),
    ("Jasur", "Tender kuzatuvchisi", "Xarid e'lonlarini kuzatadi"),
    ("Aziza", "Savdo koordinatori", "Yuborilgan takliflarni kuzatadi"),
    ("Zara", "Narx analitigi", "Bozor narxini kuzatadi"),
    ("Karim", "Raqobat tahlilchisi", "Raqobatchilarni tahlil qiladi"),
    ("Bekzod", "Savdo strategi", "Savdo yondashuvini taklif qiladi"),
    ("Anvar", "Ventilyatsiya maslahatchisi", "Montaj bo'yicha yo'l ko'rsatadi"),
    ("Nodira", "Katalog administratori", "Katalog ma'lumotini tartibga soladi"),
    ("Doston", "Ma'lumot muhandisi", "Bazadan hisobot oladi"),
    ("Malika", "Marketolog", "Kampaniya matnlarini yozadi"),
    ("Nilufar", "Ijtimoiy tarmoq tahlilchisi", "Instagram natijalarini tahlil qiladi"),
    ("Hilola", "HR menejeri", "Vakansiya va hujjat qoralamasi"),
    ("Laziz", "Yurist", "Shartnomadagi xavfni ko'rsatadi"),
]

SAVOL = "«800 m², balandligi 6 m — omborga ventilyatsiya kerak»"
W2 = Inches(5.75)          # ikki ustunli kartochka eni
W3 = Inches(3.76)          # uch ustunli
X2 = CHET + W2 + Inches(0.35)


def qur() -> Presentation:
    prs = Presentation()
    prs.slide_width = EN
    prs.slide_height = BOY
    slaydlar = []

    def yangi():
        s = yangi_slayd(prs)
        slaydlar.append(s)
        return s

    # --- 1 TITUL -----------------------------------------------------------
    s = yangi()
    panel(s, CHET, Inches(1.5), Inches(3.45), Inches(0.42),
          fon=HAVO_YUM, chek=HAVO, radius=0.5)
    quti(s, CHET + Inches(0.28), Inches(1.59), Inches(3.1), Inches(0.3),
         [("● Tizim hozir ishlab turibdi", 11, HAVO, False, MONO)])
    quti(s, CHET, Inches(2.2), Inches(11), Inches(2.3),
         [("Sun'iy intellekt", 58, MATN, True, SHRIFT),
          ("agentlari", 58, MATN, True, SHRIFT)])
    tan(s, "Bu nima, oddiy chatbotdan nimasi bilan farq qiladi va biz "
           "Jihozvent uchun qanday tizim qurdik — 15 ta agent, har biri "
           "o'z ishi bilan.", Inches(4.85), olcham=16.5)

    # --- 2 SIZ AI NI KO'RGANSIZ --------------------------------------------
    s = yangi()
    yorliq(s, "Boshlaymiz eng oddiysidan")
    sarlavha(s, "Siz AI ni allaqachon ko'rgansiz")
    tan(s, "Savol yozasiz — javob oladi. Xuddi juda ko'p o'qigan odam bilan "
           "gaplashgandek.", Inches(2.25), olcham=19, rang=MATN)
    tan(s, "Bu foydali. Lekin bir chegarasi bor va aynan shu chegara bugungi "
           "suhbatning mavzusi.", Inches(3.05))
    chiziq = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, CHET, Inches(4.25),
                                Pt(3), Inches(1.2))
    chiziq.fill.solid()
    chiziq.fill.fore_color.rgb = INSON
    chiziq.line.fill.background()
    chiziq.shadow.inherit = False
    quti(s, CHET + Inches(0.28), Inches(4.3), Inches(7), Inches(1.15),
         [("Chatbot gapiradi.", 28, MATN, True, SHRIFT),
          ("Agent ishlaydi.", 28, MATN, True, SHRIFT)])

    # --- 3 ROLIK 1 ---------------------------------------------------------
    s = yangi()
    yorliq(s, "Rolik 1 — farqni ko'ring")
    sarlavha(s, "Bir xil savol, ikki xil natija", olcham=33)
    y0 = Inches(1.95)
    ust_boy = Inches(4.85)
    panel(s, CHET, y0, W2, ust_boy, fon=KARTA2)
    quti(s, CHET + Inches(0.28), y0 + Inches(0.22), W2 - Inches(0.56),
         Inches(0.3), [("ODDIY CHATBOT", 10.5, JUDA_XIRA, True, SHRIFT)])
    panel(s, X2, y0, W2, ust_boy, fon=KARTA2)
    quti(s, X2 + Inches(0.28), y0 + Inches(0.22), W2 - Inches(0.56),
         Inches(0.3), [("AI AGENT", 10.5, JUDA_XIRA, True, SHRIFT)])

    ich = W2 - Inches(0.56)
    qadamlar = []
    a = puf(s, CHET + Inches(0.28), y0 + Inches(0.65), ich, SAVOL)
    b = puf(s, X2 + Inches(0.28), y0 + Inches(0.65), ich, SAVOL)
    qadamlar += [(a, 300, "chap"), (b, 0, "chap")]

    javob = puf(s, CHET + Inches(0.28), y0 + Inches(1.38), ich,
                "«Ombor uchun havo almashinuvi odatda soatiga 2–3 marta "
                "bo'ladi. Ventilyator quvvatini muhandis hisoblab beradi.»",
                fon=HAVO_YUM, rang=HAVO, h=Inches(0.95), chek=HAVO)
    qadamlar.append((javob, 700, "fade"))
    toxta = puf(s, CHET + Inches(0.28), y0 + Inches(2.55), ich,
                "shu yerda tugadi — keyingi ish sizda",
                fon=QIZIL_YUM, rang=QIZIL, olcham=11.5, shrift=MONO,
                h=Inches(0.42), chek=QIZIL)
    qadamlar.append((toxta, 500, "fade"))

    AMALLAR = [
        "havo sarfini hisoblaydi — 14 400 m³/soat",
        "katalogdan 3 ta mos model topadi",
        "bosim yo'qotishini tekshiradi",
        "tijorat taklifini tayyorlaydi",
        "menejerga tasdiqqa yuboradi",
    ]
    for i, amal in enumerate(AMALLAR):
        v = puf(s, X2 + Inches(0.28), y0 + Inches(1.38) + Inches(0.52) * i,
                ich, ("✓  " if i == 4 else "▸  ") + amal,
                fon=KARTA, rang=MATN, olcham=11.5, shrift=MONO,
                h=Inches(0.44), chek=CHIZIQ)
        qadamlar.append((v, 350 if i else 300, "chap"))
    davom = puf(s, X2 + Inches(0.28), y0 + Inches(4.03), ich,
                "ish bajarildi — sizga faqat tekshirish qoldi",
                fon=YASHIL_YUM, rang=YASHIL, olcham=11.5, shrift=MONO,
                h=Inches(0.44), chek=YASHIL, qalin=True)
    qadamlar.append((davom, 400, "kat"))

    # --- 4 O'XSHATISH ------------------------------------------------------
    s = yangi()
    yorliq(s, "Eng oddiy tushuntirish")
    sarlavha(s, "Ensiklopediya va xodim")
    kartochka(s, CHET, Inches(2.1), W2, Inches(2.45), "Chatbot", "Ensiklopediya",
              "Javobni biladi va aytadi. Lekin javonidan turib hech qayerga "
              "bormaydi, hech kimga qo'ng'iroq qilmaydi, hujjat yozmaydi. "
              "Bilim bor — harakat yo'q.")
    kartochka(s, X2, Inches(2.1), W2, Inches(2.45), "Agent", "Xodim",
              "Vazifani oladi, kerakli joydan ma'lumot topadi, hisoblaydi, "
              "hujjat tayyorlaydi va natijani olib keladi. Bilim plus harakat.",
              urgu=INSON)
    tan(s, "Farqi bitta so'zda: agentda qo'l bor. U nafaqat biladi — "
           "qila oladi.", Inches(5.0), olcham=19, rang=MATN)

    # --- 5 UCHTA NARSA -----------------------------------------------------
    s = yangi()
    yorliq(s, "Agent nimalardan tuziladi")
    sarlavha(s, "Uchta narsa — boshqa hech nima")
    uchta = [
        ("01", "Bilim", "Kompaniyaning o'z hujjatlari: katalog, texnik "
         "ma'lumot, narx, qonun, ish tartibi. Internetdan emas — sizdan.", HAVO),
        ("02", "Asboblar", "Bazaga ulanish, hisob-kitob formulalari, hujjat "
         "yasash, xabar yuborish. Bularsiz agent shunchaki suhbatdosh "
         "bo'lib qoladi.", HAVO),
        ("03", "Chegara", "Nima qila oladi va nimaga qo'l urmaydi. Eng muhimi "
         "shu — chegarasiz agent xavfli.", INSON),
    ]
    for i, (bl, bosh, tn, rang) in enumerate(uchta):
        kartochka(s, CHET + (W3 + Inches(0.28)) * i, Inches(2.1), W3,
                  Inches(2.6), bl, bosh, tn, urgu=rang,
                  chek=INSON if rang is INSON else CHIZIQ)
    tan(s, "Bizning tizimda har agentning chegarasi alohida faylda yozilgan. "
           "O'zi o'zgartira olmaydi.", Inches(5.15))

    # --- 6 MUAMMO ----------------------------------------------------------
    s = yangi()
    yorliq(s, "Endi — bizning ishimiz", rang=INSON)
    sarlavha(s, "Jihozventdagi kundalik holat")
    muammo = [
        ("Katalog juda katta", "1 482 ta model. Menejer mijozga to'g'ri "
         "keladigan modelni qidiradi — bu vaqt oladi va xato bo'lishi mumkin."),
        ("Har taklif qo'lda", "Hisob, model tanlash, narx, hujjat, raqam — "
         "hammasi qo'lda. Bitta tijorat taklifi soatlab vaqt oladi."),
        ("Tenderlar o'tib ketadi", "E'lonlarni kimdir har kuni ochib ko'rishi "
         "kerak. Bir kun unutilsa — imkoniyat yo'qoladi."),
        ("Bilim boshlarda", "Tajribali xodim biladi. U bandmi yoki ishdan "
         "ketdimi — bilim ham u bilan ketadi."),
    ]
    for i, (bosh, tn) in enumerate(muammo):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.1) + Inches(2.05) * (i // 2), W2, Inches(1.8),
                  "", bosh, tn)

    # --- 7 YECHIM + OFIS ---------------------------------------------------
    # Ilgari ikki slayd edi, lekin ikkalasi ham «15 ta alohida agent = ofis»
    # degan bitta fikrni aytardi. Xodim kartochkasiga uchinchi qator —
    # aniq vazifa — qo'shildi; ilgari u alohida jadval slaydida turardi.
    s = yangi()
    yorliq(s, "Yechim", rang=INSON)
    sarlavha(s, "Bitta dastur emas — butun boshli ofis", olcham=32)
    tan(s, "Bitta ulkan «hamma ishni qiladigan» dastur o'rniga biz 15 ta "
           "alohida agent qurdik. Har biri bitta ishni biladi va o'sha ishni "
           "yaxshi bajaradi — xuddi haqiqiy ofisdagidek.",
        Inches(2.0), olcham=16, rang=MATN)
    kw, kh = Inches(2.22), Inches(1.15)
    for i, (ism, lav, ish) in enumerate(XODIMLAR):
        x = CHET + (kw + Inches(0.16)) * (i % 5)
        y = Inches(2.72) + (kh + Inches(0.13)) * (i // 5)
        panel(s, x, y, kw, kh, fon=KARTA2, chek=HAVO)
        quti(s, x + Inches(0.15), y + Inches(0.12), kw - Inches(0.3),
             kh - Inches(0.24),
             [(ism, 12.5, MATN, True, SHRIFT),
              (lav, 8.5, JUDA_XIRA, False, SHRIFT),
              (ish, 8, XIRA, False, SHRIFT)], oraliq=2)
    # Sahifa hisoblagichi 6.98" da turadi — izoh undan yuqorida qolishi kerak.
    quti(s, CHET, Inches(6.55), Inches(11.4), Inches(0.4),
         [("Menejer kimga murojaat qilishni bilishi shart emas — "
           "tizim o'zi tanlaydi.", 13, XIRA, False, SHRIFT)])

    # --- ROUTER: tizim kimni chaqirishni o'zi hal qiladi --------------------
    s = yangi()
    yorliq(s, "Tizim qanday tanlaydi")
    sarlavha(s, "Menejer buyruq emas, oddiy gap yozadi")
    tan(s, "Hech qanday menyu, kod yoki agent nomi kerak emas. Tizim gapni "
           "o'qib, kimni chaqirishni o'zi hal qiladi.",
        Inches(2.05), olcham=17, rang=MATN)
    misollar = [
        ("«Ombor uchun taklif tayyorlang»", "Rustam → Sardor → Temur"),
        ("«Shu shartnomani ko'rib bering»", "Laziz (yurist)"),
        ("«1-tovarga 5 mln qo'ying»", "Temur — tayyor KP tahrirlanadi"),
    ]
    for i, (gap, tanlov) in enumerate(misollar):
        x = CHET + (W3 + Inches(0.28)) * i
        panel(s, x, Inches(2.95), W3, Inches(1.95))
        quti(s, x + Inches(0.25), Inches(3.15), W3 - Inches(0.5), Inches(1.6),
             [("YOZILGAN GAP", 9.5, HAVO, True, MONO),
              (gap, 13, MATN, False, MONO),
              ("Tanlandi: " + tanlov, 12, XIRA, False, SHRIFT)], oraliq=7)
    tan(s, "Bir gapda bir necha ish bo'lsa, agentlar zanjir bo'lib ishlaydi "
           "va natijani bir-biriga uzatadi.", Inches(5.25))

    # --- 9 ROLIK 3: ZANJIR -------------------------------------------------
    s = yangi()
    yorliq(s, "Rolik 3 — bitta so'rov qanday bajariladi")
    sarlavha(s, "Menejer bitta jumla yozadi", olcham=33)
    qadamlar = []
    sav = puf(s, CHET, Inches(1.98), ICHKI_EN,
              "«Tolibjon MChJ uchun 800 m², balandligi 6 m ombor — "
              "ventilyatsiya taklifini tayyorlang»", h=Inches(0.58))
    qadamlar.append((sav, 300, "chap"))

    ZANJIR = [
        ("Rustam", "Loyihachi muhandis", "14 400 m³/soat", False),
        ("Sardor", "Mahsulot mutaxassisi", "ВЦ 14-46 №8", False),
        ("Temur", "Tijorat menejeri", "KP-12951/6", False),
        ("Inson", "Menejer tasdig'i", "✓ tasdiqlandi", True),
        ("Aziza", "Savdo koordinatori", "kuzatuvga olindi", False),
    ]
    bw = Inches(2.22)
    for i, (kim, ish, chiq, odam) in enumerate(ZANJIR):
        x = CHET + (bw + Inches(0.16)) * i
        b = panel(s, x, Inches(3.0), bw, Inches(1.7),
                  fon=INSON_YUM if odam else KARTA2,
                  chek=INSON if odam else CHIZIQ)
        quti(s, x + Inches(0.19), Inches(3.16), bw - Inches(0.38), Inches(1.4),
             [(kim, 13.5, INSON if odam else MATN, True, SHRIFT),
              (ish, 9, JUDA_XIRA, False, SHRIFT),
              (chiq, 11, INSON if odam else HAVO, True, MONO)], oraliq=4)
        qadamlar.append((b, 600 if i == 0 else 500, "kat" if odam else "chap"))
    tayyor = puf(s, CHET, Inches(5.0), ICHKI_EN,
                 "PDF va Word tayyor — mijozga yuborish mumkin",
                 fon=YASHIL_YUM, rang=YASHIL, olcham=12, shrift=MONO,
                 h=Inches(0.48), chek=YASHIL, qalin=True)
    qadamlar.append((tayyor, 500, "kat"))
    tan(s, "Menejer kimni chaqirishni bilishi shart emas — tizim o'zi "
           "kerakli agentlarni tanlaydi va ketma-ket ishlatadi. O'rtadagi "
           "sariq qadam esa hech qachon o'tkazib yuborilmaydi.",
        Inches(5.75), olcham=15)

    # --- BIR NAQSH — BESHTA BO'LIM ----------------------------------------
    s = yangi()
    yorliq(s, "Bu faqat KP emas")
    sarlavha(s, "Bir naqsh — beshta bo'lim")
    tan(s, "Yuqoridagi zanjir — tijorat taklifi misolida. Lekin naqsh bir xil: "
           "so'rov → kerakli agentlar → natija → inson tasdig'i.",
        Inches(2.05))
    # Ismlar bu yerda takrorlanmaydi — ular ofis slaydida bir marta turadi.
    bolimlar = [
        ("SAVDO", "64 ta ish bajarilgan",
         "Taklif tuzish, model tanlash, hisob, yuborilgan KP kuzatuvi.", CHIZIQ),
        ("BOZOR", "15 ta ish bajarilgan",
         "Raqobatchilar tahlili va bozor narxi kuzatuvi.", CHIZIQ),
        ("MA'LUMOT", "21 ta ish bajarilgan",
         "Bazadan hisobot, katalogni tartibga solish.", CHIZIQ),
        ("HUQUQ VA HR", "5 ta ish bajarilgan",
         "Shartnomadagi xavf, vakansiya va hujjat qoralamasi.", CHIZIQ),
        ("XARID VA MARKETING", "7 ta ish bajarilgan",
         "Tender kuzatuvi, savdo yondashuvi, kampaniya matnlari.", CHIZIQ),
        ("HALI ISHLATILMAGAN", "Instagram va montaj",
         "Kod tayyor va sinovdan o'tgan, lekin haqiqiy so'rovda hali "
         "ochilmagan — Instagram hisobiga ulanish ruxsati kerak.", INSON),
    ]
    for i, (bl, bosh, tn, chek) in enumerate(bolimlar):
        kartochka(s, CHET + (W3 + Inches(0.28)) * (i % 3),
                  Inches(2.7) + Inches(1.85) * (i // 3), W3, Inches(1.7),
                  bl, bosh, tn, urgu=INSON if chek is INSON else HAVO, chek=chek)
    quti(s, CHET, Inches(6.42), Inches(11), Inches(0.4),
         [("15 tadan 13 tasi haqiqiy so'rovlarda ishlagan. Qolgan ikkitasini "
           "«ishlaydi» deb aytmayman.", 14, MATN, True, SHRIFT)])

    # --- BILIM BAZASI ------------------------------------------------------
    s = yangi()
    yorliq(s, "Agent qayerdan biladi")
    sarlavha(s, "Internetdan emas — sizning hujjatlaringizdan")
    bilim = [
        ("Kompaniya bilim bazasi", "65 ta hujjat — ichida 5 181 ta qidiriladigan parcha: "
         "mahsulot tavsiflari, ventilyatsiya bo'yicha texnik bilim, montaj "
         "qoidalari, bozor tahlili, savdo tartibi, qonun matnlari."),
        ("Har agent — o'z bo'limi", "Yurist qonunni, muhandis texnik bilimni, "
         "marketolog brend bazasini ko'radi. Kerak bo'lmagan hujjat agentga "
         "berilmaydi — bu aniqlikni ham, xarajatni ham yaxshilaydi."),
        ("Javob manbasini ko'rsatadi", "Har javobda ma'lumot qaysi hujjatdan "
         "olingani yoziladi: baza, katalog, hujjat yoki veb. Tekshirish "
         "mumkin — ishonishga majbur emassiz."),
        ("Yangilash oson", "Hujjat qo'shsangiz yoki narxni o'zgartirsangiz — "
         "tizim uni o'zi o'qiydi. Dasturchi ham, qayta yoqish ham kerak emas."),
    ]
    for i, (bosh, tn) in enumerate(bilim):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.1) + Inches(2.05) * (i // 2), W2, Inches(1.8),
                  "", bosh, tn)

    # --- BILMASA SO'RAYDI --------------------------------------------------
    s = yangi()
    yorliq(s, "Eng muhim odat", rang=INSON)
    sarlavha(s, "Bilmasa — to'qimaydi, so'raydi")
    tan(s, "AI ning eng xavfli tomoni — bilmagan narsani ishonch bilan "
           "aytishi. Tizimda bunga alohida holat qo'yilgan.",
        Inches(2.05), olcham=17, rang=MATN)
    panel(s, CHET, Inches(2.95), W2, Inches(1.9))
    quti(s, CHET + Inches(0.28), Inches(3.18), W2 - Inches(0.56), Inches(1.5),
         [("MENEJER YOZDI", 9.5, HAVO, True, MONO),
          ("«Omborga ventilyatsiya kerak»", 14, MATN, False, MONO)], oraliq=8)
    panel(s, X2, Inches(2.95), W2, Inches(1.9), chek=INSON, fon=INSON_YUM)
    quti(s, X2 + Inches(0.28), Inches(3.18), W2 - Inches(0.56), Inches(1.5),
         [("AGENT JAVOBI", 9.5, INSON, True, MONO),
          ("Hisoblash uchun uchta narsa yetishmayapti:", 12.5, MATN, False, SHRIFT),
          ("—  ombor maydoni (m²)", 12.5, XIRA, False, SHRIFT),
          ("—  shift balandligi", 12.5, XIRA, False, SHRIFT),
          ("—  nima saqlanadi (chang bormi)", 12.5, XIRA, False, SHRIFT)],
         oraliq=5)
    tan(s, "Taxminiy raqam bilan KP tuzilmaydi. Mijozga noto'g'ri quvvat "
           "ketishidan ko'ra bitta savol berish arzonroq.", Inches(5.2))

    # --- 10 ROLIK 4: KOD vs MODEL ------------------------------------------
    s = yangi()
    yorliq(s, "Rolik 4 — eng muhim qoida")
    sarlavha(s, "Raqamni AI o'ylab topmaydi")
    qadamlar = []
    chap = panel(s, CHET, Inches(2.1), W2, Inches(2.65),
                 fon=QIZIL_YUM, chek=QIZIL)
    quti(s, CHET + Inches(0.28), Inches(2.32), W2 - Inches(0.56), Inches(2.2),
         [("AGAR RAQAMNI MODEL AYTSA", 10.5, QIZIL, True, MONO),
          ("«800 m² ombor uchun taxminan…» — model ishonchli ohangda "
           "gapiradi, lekin raqam taxminiy bo'lishi mumkin.", 12, XIRA,
           False, SHRIFT),
          ("≈ 15 000 m³/soat ?", 23, QIZIL, True, MONO),
          ("Tekshirib bo'lmaydi. Mijozga ketsa — javobgarlik.", 11,
           JUDA_XIRA, False, SHRIFT)], oraliq=8)
    qadamlar.append((chap, 300, "fade"))

    ong = panel(s, X2, Inches(2.1), W2, Inches(2.65),
                fon=YASHIL_YUM, chek=YASHIL)
    quti(s, X2 + Inches(0.28), Inches(2.32), W2 - Inches(0.56), Inches(2.2),
         [("BIZDA: RAQAMNI KOD HISOBLAYDI", 10.5, YASHIL, True, MONO),
          ("Model faqat savolni tushunadi. Hisobni esa yozilgan formula "
           "bajaradi — har safar bir xil natija.", 12, XIRA, False, SHRIFT),
          ("800 × 6 × 3 = 14 400 m³/soat", 21, YASHIL, True, MONO),
          ("maydon × balandlik × soatiga havo almashinuvi — har bir raqamni "
           "qo'lda qayta tekshirsa bo'ladi.", 11, JUDA_XIRA, False, SHRIFT)],
         oraliq=8)
    qadamlar.append((ong, 900, "kat"))
    tan(s, "Shuning uchun taklifdagi narx, quvvat va o'lcham — o'ylab "
           "topilgan emas, hisoblangan.", Inches(5.2), olcham=17, rang=MATN)

    # --- 11 INSON TASDIG'I -------------------------------------------------
    s = yangi()
    yorliq(s, "Xavfsizlik", rang=INSON)
    sarlavha(s, "Oxirgi so'z — doim odamda")
    panel(s, CHET, Inches(2.1), W2, Inches(2.55))
    quti(s, CHET + Inches(0.28), Inches(2.32), W2 - Inches(0.56), Inches(2.1),
         [("AGENT QILADI", 9.5, HAVO, True, MONO),
          ("—  Hisoblaydi va model tanlaydi", 13.5, XIRA, False, SHRIFT),
          ("—  Hujjat tayyorlaydi", 13.5, XIRA, False, SHRIFT),
          ("—  Tenderlarni kuzatadi", 13.5, XIRA, False, SHRIFT),
          ("—  Savolga javob beradi", 13.5, XIRA, False, SHRIFT)], oraliq=7)
    panel(s, X2, Inches(2.1), W2, Inches(2.55), chek=INSON)
    quti(s, X2 + Inches(0.28), Inches(2.32), W2 - Inches(0.56), Inches(2.1),
         [("FAQAT ODAM QILADI", 9.5, INSON, True, MONO),
          ("—  Mijozga hujjat yuborish", 13.5, XIRA, False, SHRIFT),
          ("—  Narxni yakuniy tasdiqlash", 13.5, XIRA, False, SHRIFT),
          ("—  Katalogga o'zgartirish kiritish", 13.5, XIRA, False, SHRIFT),
          ("—  Shartnoma bo'yicha qaror", 13.5, XIRA, False, SHRIFT)], oraliq=7)
    chiziq = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, CHET, Inches(5.1),
                                Pt(3), Inches(0.58))
    chiziq.fill.solid()
    chiziq.fill.fore_color.rgb = INSON
    chiziq.line.fill.background()
    chiziq.shadow.inherit = False
    quti(s, CHET + Inches(0.28), Inches(5.15), Inches(11), Inches(0.6),
         [("Tizim taklif qiladi — qarorni odam qabul qiladi.", 23, MATN,
           True, SHRIFT)])

    # --- 12 QAYERDA ISHLAYDI -----------------------------------------------
    s = yangi()
    yorliq(s, "Amalda")
    sarlavha(s, "Yangi dastur o'rganish shart emas")
    joylar = [
        ("Menejerlar uchun", "Telegram", "Oddiy xabar yoziladi, javob keladi. "
         "Har kuni ertalab tender xabari, dushanbada haftalik hisobot — "
         "o'zi keladi."),
        ("Mijozlar uchun", "Alohida bot", "Mijoz savol beradi, javob oladi. "
         "Savol va javob menejerga ham ko'rinadi — nazorat qo'ldan chiqmaydi."),
        ("Rahbariyat uchun", "Veb panel", "Kim nima qilyapti — jonli ko'rinadi. "
         "Ofis 3D ko'rinishida: agentlar ish ustida harakatlanadi."),
    ]
    for i, (bl, bosh, tn) in enumerate(joylar):
        kartochka(s, CHET + (W3 + Inches(0.28)) * i, Inches(2.1), W3,
                  Inches(2.7), bl, bosh, tn)
    tan(s, "Telefondan ham, kompyuterdan ham ochiladi. Panel parol bilan "
           "himoyalangan.", Inches(5.25))

    # --- XAVFSIZLIK --------------------------------------------------------
    s = yangi()
    yorliq(s, "Xavfsizlik")
    sarlavha(s, "To'rt qatlam — aytilgan emas, qulflangan")
    tan(s, "«Modelga o'chirma deb aytdik» — bu himoya emas. Chegaralar kod "
           "darajasida qo'yilgan, ya'ni model nima desa ham bajarilmaydi.",
        Inches(2.05))
    qatlam = [
        ("01", "Baza himoyasi", "Ma'lumot bazasida DELETE va DROP imkonsiz — "
         "taqiq bazaning o'zida qo'yilgan. Model bunday so'rov "
         "yozsa ham baza uni rad etadi."),
        ("02", "Maxfiy maydonlar", "Xodimlarning maoshi va telefoni modelga "
         "umuman berilmaydi — ular so'rovga qo'shilmaydi. Sizib chiqishi "
         "texnik jihatdan mumkin emas."),
        ("03", "Panel qulfi", "Veb panel parolsiz tashqaridan ochilmaydi. "
         "Parol qo'yilmagan bo'lsa — faqat mahalliy kompyuterda ishlaydi."),
        ("04", "Ma'lumot qayerda qoladi", "Baza, hujjatlar va katalog "
         "kompaniyada turadi. Modelga butun baza yuborilmaydi — savolga "
         "kerakli eng ko'pi 5 ta parcha ajratiladi, qolgani umuman chiqmaydi."),
    ]
    # To'rttaga o'tgani uchun 2×2 to'r: uch ustunda to'rtinchisi sig'maydi.
    for i, (bl, bosh, tn) in enumerate(qatlam):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.85) + Inches(2.0) * (i // 2), W2,
                  Inches(1.85), bl, bosh, tn)

    # --- AVTOMATIK ISHLAR --------------------------------------------------
    s = yangi()
    yorliq(s, "Avtomatik ishlar")
    sarlavha(s, "Hech kim eslab turishi shart emas")
    avto = [
        ("HAR KUNI 09:00", "Tender kuzatuvi", "Xarid e'lonlari ko'rib chiqiladi, "
         "Jihozvent mahsulotlariga mosi ajratiladi va Telegramga yuboriladi. "
         "Ko'rilgan e'lon ikkinchi marta kelmaydi.", CHIZIQ),
        ("DUSHANBA 09:00", "Haftalik hisobot", "Tizim bir haftada nima qilgani: "
         "nechta so'rov, nechta KP, nechta tasdiq. Rahbar so'ramasdan oladi.", CHIZIQ),
        ("MUHIM TAFSILOT", "O'tkazib yuborilgani yo'qolmaydi", "Kompyuter 09:00 da "
         "o'chiq bo'lsa, xabar yo'qolmaydi — tizim yoqilishi bilan o'sha "
         "zahoti keladi.", INSON),
        ("", "Takror yo'q", "Bajarilgan ish bazaga yoziladi. Kompyuter kuniga "
         "besh marta yoqilsa ham xabar bir marta keladi.", CHIZIQ),
    ]
    for i, (bl, bosh, tn, chek) in enumerate(avto):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.1) + Inches(2.05) * (i // 2), W2, Inches(1.8),
                  bl, bosh, tn, urgu=INSON if chek is INSON else HAVO, chek=chek)

    # --- TEZLIK VA SIFAT ---------------------------------------------------
    s = yangi()
    yorliq(s, "Muhandislik tomoni")
    sarlavha(s, "Tez, arzon va tekshirilgan")
    muh = [
        ("Oddiy ish — oddiy yo'l", "«Narxni o'zgartiring» degan so'rov butun "
         "tizimni bezovta qilmaydi: tayyor KP to'g'ridan-to'g'ri tahrirlanadi. "
         "Shu bitta yechim javobni 48 soniyadan 0,1 soniyaga tushirdi."),
        ("Har agent — o'z bilimi", "Agentga faqat kerakli hujjatlar beriladi. "
         "Bu javobni ham aniqroq, ham arzonroq qiladi — ortiqcha matn uchun "
         "to'lanmaydi."),
        ("Buzilgan joy darhol bilinadi", "Har o'zgarishdan keyin butun tizim boshdan "
         "tekshiriladi. «Bir joyni tuzatib, boshqa joyni buzish» — shu bilan "
         "to'siladi."),
        ("Xato yashirilmaydi", "Tashqi xizmat ishlamasa, agent buni ochiq "
         "aytadi va taxmin qilmaydi. Ma'lumot namunaviy bo'lsa — ogohlantiradi."),
    ]
    for i, (bosh, tn) in enumerate(muh):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.1) + Inches(2.05) * (i // 2), W2, Inches(1.8),
                  "", bosh, tn)

    # --- 13 RAQAMLAR -------------------------------------------------------
    s = yangi()
    yorliq(s, "Bugungi holat — namoyish emas")
    sarlavha(s, "Tizim allaqachon ishlagan")
    raqamlar = [("127", "bajarilgan so'rov", MATN),
                ("25", "tayyorlangan tijorat taklifi", MATN),
                ("24", "kuzatilgan tender e'loni", MATN),
                ("43", "inson tasdig'idan o'tgan ish", INSON),
                ("1 482", "katalogdagi model", HAVO),
                ("898", "o'tgan avtomatik tekshiruv", HAVO)]
    qadamlar = []
    for i, (son, izoh, rang) in enumerate(raqamlar):
        k = stat(s, CHET + (W3 + Inches(0.28)) * (i % 3),
                 Inches(2.1) + Inches(1.72) * (i // 3), W3, Inches(1.48),
                 son, izoh, rang=rang)
        qadamlar.append((k, 300 if i == 0 else 200, "past"))
    tan(s, "Bu raqamlar taqdimot uchun yozilmagan — hozir ishlab turgan "
           "tizimning bazasidan olindi.", Inches(5.75))

    # --- BU NIMA BERADI ----------------------------------------------------
    s = yangi()
    yorliq(s, "Biznes tomoni", rang=INSON)
    sarlavha(s, "Bu kompaniyaga nima beradi")
    tan(s, "Quyidagilar o'lchangan narsalar. Foiz va daromad va'da qilmayman — "
           "buni bir necha oylik ishlatishdan keyin kompaniyaning o'zi ko'radi.",
        Inches(2.05))
    foyda = [
        ("Mijoz tezroq javob oladi", "Taklif soatlab emas, daqiqalarda tayyor "
         "bo'ladi. Kim birinchi javob bersa, ko'pincha o'sha ishni oladi."),
        ("Tender o'tib ketmaydi", "E'lonlar har kuni avtomatik ko'riladi. "
         "Kompyuter o'chiq bo'lsa ham xabar yo'qolmaydi."),
        ("To'g'ri model taklif qilinadi", "1 482 model ichidan hisob bo'yicha "
         "tanlanadi — «o'xshashi» emas. Xato jihoz qaytib kelmaydi."),
        ("Bilim kompaniyada qoladi", "Tajriba hujjatlarda va kodda saqlanadi. "
         "Xodim ishdan ketsa, bilim u bilan ketmaydi."),
    ]
    for i, (bosh, tn) in enumerate(foyda):
        kartochka(s, CHET + (W2 + Inches(0.35)) * (i % 2),
                  Inches(2.75) + Inches(1.85) * (i // 2), W2, Inches(1.65),
                  "", bosh, tn)
    panel(s, CHET, Inches(6.05), ICHKI_EN, Inches(0.78),
          fon=INSON_YUM, chek=INSON)
    quti(s, CHET + Inches(0.25), Inches(6.22), ICHKI_EN - Inches(0.5), Inches(0.5),
         [("Xarajat haqida rostini aytaman: hozirgi sur'atda taxminan oyiga "
           "$20–70 oralig'ida. Bu jonli hisob-faktura emas — o'lchangan so'rov "
           "hajmidan chiqarilgan taxmin.", 12, INSON, False, SHRIFT)])

    # --- 15 CHEGARALAR -----------------------------------------------------
    s = yangi()
    yorliq(s, "Ochiq gapiramiz", rang=INSON)
    sarlavha(s, "Tizim nimani hali qila olmaydi")
    tan(s, "Yaxshi tizim o'z chegarasini biladi. Bular yashirilmaydi — "
           "rejaga kiritilgan.", Inches(2.1), olcham=16, rang=MATN)
    chegara = [
        ("Narxlar to'liq emas", "1 482 modeldan 25 tasida narx bor. Qolgani "
         "kiritilishi kerak — bu texnik emas, ma'lumot masalasi."),
        ("41 mahsulotda model yo'q", "Katalogda nomi bor, lekin o'lcham "
         "variantlari kiritilmagan. Dasturchilarga ro'yxat topshirildi."),
        ("Kompyuter yoqiq bo'lishi kerak", "Hozir tizim shu kompyuterda "
         "ishlaydi. Doimiy yoqiq kompyuterga ko'chirilsa — uzluksiz ishlaydi."),
    ]
    for i, (bosh, tn) in enumerate(chegara):
        kartochka(s, CHET + (W3 + Inches(0.28)) * i, Inches(2.8), W3,
                  Inches(2.35), "", bosh, tn, urgu=INSON)
    panel(s, CHET, Inches(5.5), ICHKI_EN, Inches(0.8),
          fon=INSON_YUM, chek=INSON)
    quti(s, CHET + Inches(0.28), Inches(5.72), ICHKI_EN - Inches(0.56),
         Inches(0.4),
         [("Uchalasi ham hal qilinadigan — hech biri tizimni qayta qurishni "
           "talab qilmaydi.", 14, INSON, True, SHRIFT)])

    # --- 16 XULOSA ---------------------------------------------------------
    s = yangi()
    yorliq(s, "Xulosa")
    sarlavha(s, "Uch jumlada")
    for i, qator in enumerate([
        "AI agent — bu javob beradigan emas, ish bajaradigan dastur.",
        "Biz Jihozvent uchun 15 ta agentdan iborat ofis qurdik — "
        "hisob, katalog, taklif, tender, hujjat.",
        "Raqamlarni kod hisoblaydi, oxirgi qarorni esa doim odam qabul qiladi.",
    ]):
        y = Inches(2.25) + Inches(0.9) * i
        nuqta = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, CHET, y + Inches(0.15),
                                   Inches(0.16), Pt(2.5))
        nuqta.fill.solid()
        nuqta.fill.fore_color.rgb = HAVO
        nuqta.line.fill.background()
        nuqta.shadow.inherit = False
        quti(s, CHET + Inches(0.33), y, Inches(11), Inches(0.85),
             [(qator, 18, MATN, False, SHRIFT)])
    chiziq = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, CHET, Inches(5.25),
                                Pt(3), Inches(1.05))
    chiziq.fill.solid()
    chiziq.fill.fore_color.rgb = INSON
    chiziq.line.fill.background()
    chiziq.shadow.inherit = False
    quti(s, CHET + Inches(0.28), Inches(5.3), Inches(11), Inches(1.05),
         [("Tizim menejerni almashtirmaydi.", 25, MATN, True, SHRIFT),
          ("Uning qo'lini bo'shatadi.", 25, MATN, True, SHRIFT)])

    for n, slayd in enumerate(slaydlar, start=1):
        hisoblagich(slayd, n, len(slaydlar))
    return prs


if __name__ == "__main__":
    prs = qur()
    prs.save(CHIQISH)
    print(f"Yaratildi: {CHIQISH}")

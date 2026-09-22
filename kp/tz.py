"""Texnik topshiriq (TZ) faylidan xona parametrlarini ajratish.

NEGA KERAK
----------
Mijoz TZ yuborganda menejer uni o'qib, maydon/balandlik/xona turini
qo'lda `/kp` ga ko'chirishi kerak edi. Katta TZ da o'nlab xona bo'ladi —
bu eng sekin va eng xato bo'ladigan joy.

IKKI BOSQICH, IKKI XIL MAS'ULIYAT
---------------------------------
  1. `matn_ol()` — fayldan MATN. Sof kod, LLM yo'q, testlanadi.
  2. `SORASH_PROMPTI` + `TzNatija` — matndan PARAMETR. Buni model
     qiladi, chunki TZ hujjatlari har xil yoziladi.

MODEL HISOBLAMAYDI. Uning sxemasida `havo_sarfi` ham, `diametr` ham
YO'Q — u faqat matnda YOZILGAN raqamni ko'chiradi. Hisob
`hisob/ventilyatsiya.py` da qoladi.

TAXMIN QILINMAYDI: topilmagan qiymat 0 bo'lib qoladi va
`topilmadi` ro'yxatiga tushadi. Menejer har bir qiymatni KO'RADI va
tasdiqlaydi — TZ dan olingan raqam KP ga jimgina tushmaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

# Bundan katta fayl o'qilmaydi — Telegram cheklovi ham shunga yaqin.
MAKS_HAJM = 20 * 1024 * 1024
# Modelga yuboriladigan matn cheklovi. TZ larda ko'p sahifa jadval
# bo'ladi, hammasi kerak emas — parametrlar odatda boshida turadi.
MAKS_MATN = 60_000
# Bir TZ dan shuncha xonadan ko'pi olinmaydi.
MAKS_XONA = 20

QOLLAB_QUVVATLANADI = {".pdf", ".docx", ".xlsx", ".txt"}


class TzXatosi(ValueError):
    """Fayl o'qilmadi — sabab menejerga aytiladi."""


# --- 1-bosqich: fayldan matn (SOF KOD) ---------------------------------------


def _pdf_matni(yol: Path) -> str:
    from pypdf import PdfReader

    betlar = []
    for bet in PdfReader(str(yol)).pages:
        try:
            betlar.append(bet.extract_text() or "")
        except Exception:          # noqa: BLE001 — bitta bet buzuq bo'lsa qolgani olinsin
            continue
    return "\n".join(betlar)


def _docx_matni(yol: Path) -> str:
    from docx import Document

    hujjat = Document(str(yol))
    bolaklar = [p.text for p in hujjat.paragraphs]
    # TZ da parametrlar odatda JADVALDA turadi — ularsiz bo'lmaydi.
    for jadval in hujjat.tables:
        for qator in jadval.rows:
            bolaklar.append(" | ".join(k.text.strip() for k in qator.cells))
    return "\n".join(bolaklar)


def _xlsx_matni(yol: Path) -> str:
    import openpyxl

    kitob = openpyxl.load_workbook(str(yol), data_only=True, read_only=True)
    bolaklar = []
    for varaq in kitob.worksheets:
        bolaklar.append(f"--- {varaq.title} ---")
        for qator in varaq.iter_rows(values_only=True):
            kataklar = [str(k).strip() for k in qator if k is not None]
            if kataklar:
                bolaklar.append(" | ".join(kataklar))
    kitob.close()
    return "\n".join(bolaklar)


def matn_ol(yol: str | Path) -> str:
    """TZ faylidan matn. Formatni KENGAYTMA bo'yicha aniqlaydi.

    Bo'sh matn qaytsa — bu SKAN qilingan PDF bo'lishi mumkin (rasm
    ichida matn). Buni ochiq aytamiz: menejer TZ ni qo'lda kiritishi
    kerakligini bilsin, tizim "tushunmadim" deb jim qolmasin.
    """
    yol = Path(yol)
    if not yol.is_file():
        raise TzXatosi("Fayl topilmadi")
    if yol.stat().st_size > MAKS_HAJM:
        raise TzXatosi(
            f"Fayl juda katta ({yol.stat().st_size / 1024 / 1024:.0f} MB). "
            f"Chegara {MAKS_HAJM // 1024 // 1024} MB"
        )

    kengaytma = yol.suffix.lower()
    if kengaytma not in QOLLAB_QUVVATLANADI:
        raise TzXatosi(
            f"«{kengaytma}» formati o'qilmaydi. "
            f"Mumkin: {', '.join(sorted(QOLLAB_QUVVATLANADI))}"
        )

    try:
        if kengaytma == ".pdf":
            matn = _pdf_matni(yol)
        elif kengaytma == ".docx":
            matn = _docx_matni(yol)
        elif kengaytma == ".xlsx":
            matn = _xlsx_matni(yol)
        else:
            matn = yol.read_text(encoding="utf-8", errors="replace")
    except TzXatosi:
        raise
    except Exception as xato:      # noqa: BLE001
        raise TzXatosi(f"Fayl o'qilmadi: {xato}") from xato

    matn = re.sub(r"[ \t]+", " ", matn)
    matn = re.sub(r"\n{3,}", "\n\n", matn).strip()
    if not matn:
        raise TzXatosi(
            "Faylda matn topilmadi. Skanerlangan PDF bo'lsa (rasm ichida "
            "matn) uni o'qib bo'lmaydi — ma'lumotni qo'lda kiriting"
        )
    return matn[:MAKS_MATN]


# --- 2-bosqich: matndan parametr (MODEL) --------------------------------------


class TzXona(BaseModel):
    """TZ da topilgan bitta xona. HISOB MAYDONLARI YO'Q."""

    nomi: str = ""
    turi: str = ""
    maydon: float = 0
    balandlik: float = 0
    odamlar: int = 0
    # Matnda havo sarfi TAYYOR berilgan bo'lishi mumkin — u holda
    # hisoblash shart emas, TZ dagi raqam ustun turadi.
    havo_sarfi: float = 0
    izoh: str = ""


class TzNatija(BaseModel):
    mijoz: str = ""
    obyekt: str = ""
    inn: str = ""
    xonalar: list[TzXona] = Field(default_factory=list)
    # Matnda ANIQ aytilgan model nomlari (`ВЦ 4-75-6,3-1` kabi).
    mahsulotlar: list[str] = Field(default_factory=list)
    # TZ da yo'q, lekin KP uchun kerak bo'lgan narsalar.
    topilmadi: list[str] = Field(default_factory=list)


TIZIM_PROMPT = """Sen texnik topshiriq (TZ) hujjatidan MA'LUMOT AJRATASAN.

VAZIFANG: matnda YOZILGAN qiymatlarni ko'chirish. Boshqa hech narsa.

QAT'IY QOIDALAR:
1) HISOBLAMAYSAN. Havo sarfini, kanal diametrini, bosimni O'ZING
   hisoblamaysan. `havo_sarfi` ni faqat matnda TAYYOR yozilgan bo'lsa
   ko'chirasan (masalan "L = 3200 м³/ч"). Yo'q bo'lsa 0 qoldirasan.
2) TAXMIN QILMAYSAN. Balandlik yozilmagan bo'lsa 0 qoldirasan va
   `topilmadi` ga "balandlik" deb yozasan. "Odatda 3 metr" — TAQIQLANADI.
3) XONA TURINI faqat berilgan ro'yxatdan tanlaysan. Aniq mosi bo'lmasa
   BO'SH qoldirasan va `izoh` ga matndagi asl nomni yozasan.
4) MODEL NOMINI O'YLAB TOPMAYSAN. `mahsulotlar` ga faqat matnda
   HARFMA-HARF yozilgan model belgilarini kiritasan.
5) STIR/INN — faqat matnda aniq shunday belgilangan bo'lsa. Boshqa
   9 xonali raqamni STIR deb olmaysan.
6) Matn tushunarsiz yoki TZ ga o'xshamasa — bo'sh natija qaytarasan va
   `topilmadi` ga sababini yozasan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi JSON obyekti bilan ber, boshqa matnsiz:
{
  "mijoz": "buyurtmachi tashkilot nomi yoki bo'sh",
  "obyekt": "obyekt nomi va manzili yoki bo'sh",
  "inn": "STIR raqami (9 raqam) yoki bo'sh",
  "xonalar": [
    {"nomi": "xona nomi", "turi": "ro'yxatdagi tur yoki bo'sh",
     "maydon": 0, "balandlik": 0, "odamlar": 0,
     "havo_sarfi": 0, "izoh": "matndagi asl nom yoki izoh"}
  ],
  "mahsulotlar": ["matnda aniq yozilgan model belgisi"],
  "topilmadi": ["TZ da yo'q, lekin KP uchun kerak bo'lgan narsa"]
}"""


def sorov_matni(tz_matni: str, turlar: list[str]) -> str:
    """Modelga yuboriladigan topshiriq."""
    return (
        f"XONA TURLARI (faqat shulardan tanla): {', '.join(turlar)}\n\n"
        f"TEXNIK TOPSHIRIQ MATNI:\n{tz_matni}"
    )


# --- natijani shakl javoblariga aylantirish -----------------------------------


@dataclass
class ShaklTaklifi:
    """TZ dan olingan, MENEJER TASDIG'INI kutayotgan qiymatlar.

    Bu TAYYOR javob emas — taklif. `bot/kp_oqim.py` har bir qiymatni
    menejerga ko'rsatadi va u tasdiqlagandan keyingina shaklga yoziladi.
    """

    javoblar: dict = field(default_factory=dict)
    # Menejerga ko'rsatiladigan "nima topildi" ro'yxati.
    topilganlar: list[str] = field(default_factory=list)
    ogohlantirishlar: list[str] = field(default_factory=list)

    @property
    def bormi(self) -> bool:
        return bool(self.javoblar)


def shaklga_aylantir(natija: TzNatija, turlar: set[str]) -> ShaklTaklifi:
    """`TzNatija` -> shakl javoblari (taklif sifatida).

    ENG KATTA XONA olinadi: `/kp` hozircha bitta xona hisoblaydi, TZ da
    esa o'nlab bo'lishi mumkin. Qaysi biri olinganini menejerga OCHIQ
    aytamiz — u boshqasini tanlashi yoki qo'lda kiritishi mumkin.
    """
    taklif = ShaklTaklifi()

    if natija.mijoz:
        taklif.javoblar["mijoz"] = natija.mijoz
        taklif.topilganlar.append(f"Mijoz: {natija.mijoz}")
    if natija.obyekt:
        taklif.javoblar["obyekt"] = natija.obyekt
        taklif.topilganlar.append(f"Obyekt: {natija.obyekt}")
    if natija.inn and len(re.sub(r"\D", "", natija.inn)) == 9:
        taklif.javoblar["inn"] = re.sub(r"\D", "", natija.inn)
        taklif.topilganlar.append(f"STIR: {taklif.javoblar['inn']}")

    # Model nomi aniq bo'lsa — A yo'li tezroq va aniqroq: loyihachi
    # allaqachon hisoblab, uskunani tanlagan.
    if natija.mahsulotlar:
        taklif.javoblar["yol"] = "model"
        taklif.javoblar["mahsulotlar"] = [
            {"nomi": nom, "miqdor": 1.0, "birlik": "dona"}
            for nom in natija.mahsulotlar[:MAKS_XONA]
        ]
        taklif.topilganlar.append(
            f"Mahsulotlar ({len(natija.mahsulotlar)} ta): "
            + ", ".join(natija.mahsulotlar[:3])
        )
        taklif.ogohlantirishlar.append(
            "TZ dan olingan miqdor har biriga 1 dona deb qo'yildi — "
            "tekshiring"
        )
        # XONALAR JIM TASHLANMAYDI.
        #
        # Loyiha chizmasida ODATDA ikkalasi ham bo'ladi: xonalar
        # ekspliikatsiyasi va tanlangan uskuna. Ilgari mahsulot
        # topilishi bilan xonalar yo'qolardi va menejer 12 ta xona
        # o'qilganini umuman bilmasdi (jonli holat: «Albom №6 —
        # Ustaxona binosi» chizmasi, 2026-08-26).
        yaroqli = [x for x in natija.xonalar if x.maydon > 0]
        if yaroqli:
            taklif.ogohlantirishlar.append(
                f"TZ da {len(yaroqli)} ta xona ham bor "
                f"({', '.join(x.nomi or x.turi for x in yaroqli[:3])}…). "
                "Uskuna nomlari topilgani uchun ULAR ishlatilmadi — "
                "hisobni o'zimiz qilishimiz kerak bo'lsa, /bekor bosib "
                "«Obyektni tasvirlayman» ni tanlang"
            )
        return taklif

    yaroqli = [x for x in natija.xonalar if x.maydon > 0]
    if not yaroqli:
        if natija.xonalar:
            taklif.ogohlantirishlar.append(
                "TZ da xona topildi, lekin MAYDONI yozilmagan — qo'lda kiriting"
            )
        return taklif

    # HAMMA xona olinadi. Ilgari faqat eng kattasi olinardi va TZ dagi
    # qolgan xonalar tashlab yuborilardi — 3 xonali TZ dan bitta xonalik
    # KP chiqardi.
    xonalar: list[dict] = []
    for xona in yaroqli[:MAKS_XONA]:
        if xona.balandlik <= 0:
            taklif.ogohlantirishlar.append(
                f"«{xona.nomi or 'xona'}» balandligi TZ da yozilmagan — "
                "bu xona hisobga OLINMADI"
            )
            continue
        turi = xona.turi if xona.turi in turlar else ""
        if not turi:
            # BO'SH tur ham, NOTO'G'RI tur ham bir xil xavfli.
            #
            # JONLI XATO (2026-08-28): zaxira model «Торговый зал» uchun
            # turni BO'SH qaytardi va tizim jimgina `ofis` qo'ydi.
            # Ogohlantirish faqat NOTO'G'RI tur uchun yozilardi, bo'sh
            # tur esa hech qanday iz qoldirmasdi — menejer «850 m² × 4 m»
            # ni ko'rib, tur o'zi tanlanganini bilmasdi.
            #
            # Tur havo almashinuvi normasini belgilaydi: restoran (8.0
            # karrali) o'rniga ofis (3.0) olinsa sarf 2,7 BAROBAR kam
            # chiqadi va buni hech kim sezmaydi.
            sabab = (f"«{xona.turi}» turi ro'yxatda yo'q"
                     if xona.turi else "TZ dan xona turi aniqlanmadi")
            taklif.ogohlantirishlar.append(
                f"«{xona.nomi or xona.turi or 'xona'}»: {sabab} — "
                "OFIS normasi ishlatildi, TEKSHIRING"
            )
        xonalar.append({
            "nomi": xona.nomi or turi or "xona",
            "turi": turi or "ofis",
            "maydon": xona.maydon,
            "balandlik": xona.balandlik,
            "odamlar": max(xona.odamlar, 0),
        })
        # Tur HAR DOIM ko'rsatiladi — aniqlanmagani ham. Menejer qaysi
        # norma ishlatilganini ko'rmasa, xatoni topa olmaydi.
        taklif.topilganlar.append(
            f"{xona.nomi or turi or 'xona'}: "
            f"{xona.maydon:g} m² × {xona.balandlik:g} m"
            + (f", {xona.odamlar} kishi" if xona.odamlar > 0 else "")
            + (f" ({turi})" if turi else " (turi ANIQLANMADI → ofis)")
        )
        if xona.havo_sarfi > 0:
            # TZ da tayyor sarf berilgan — bu loyihachi hisobi, e'tiborsiz
            # qolmasin. Bizning hisobimiz bilan solishtirilishi kerak.
            taklif.ogohlantirishlar.append(
                f"«{xona.nomi}»: TZ da havo sarfi berilgan "
                f"{xona.havo_sarfi:g} m³/soat — tizim hisobi bilan solishtiring"
            )

    if not xonalar:
        return taklif

    taklif.javoblar["yol"] = "obyekt"
    taklif.javoblar["xonalar"] = xonalar
    # XONA HALQASI YOPIQ: TZ da xonalar ro'yxati TO'LIQ berilgan.
    # Bu qo'yilmasa bot "Yana xona bormi?" deb so'raydi va javob
    # kelganda birinchi xona ro'yxatga IKKINCHI marta qo'shiladi
    # (`Shakl._xonani_yakunla` quyidagi `olcham` ni ko'radi).
    taklif.javoblar["yana_xona"] = "yoq"
    # Eski kalitlar ham to'ldiriladi: shakl shu savollarni "javob
    # berilgan" deb hisoblasin va ularni qayta so'ramasin.
    birinchi = xonalar[0]
    taklif.javoblar["olcham"] = {
        "maydon": birinchi["maydon"], "balandlik": birinchi["balandlik"]
    }
    taklif.javoblar["xona_turi"] = birinchi["turi"]
    if birinchi["odamlar"] > 0:
        taklif.javoblar["odamlar"] = birinchi["odamlar"]

    if len(xonalar) > 1:
        taklif.topilganlar.append(f"Jami {len(xonalar)} ta xona")

    for yetishmaydi in natija.topilmadi[:5]:
        taklif.ogohlantirishlar.append(f"TZ da yo'q: {yetishmaydi}")
    return taklif

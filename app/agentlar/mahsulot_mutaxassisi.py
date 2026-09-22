"""Mahsulot mutaxassisi Sardor — `product-spec`.

Maqsad: mahsulotning texnik xususiyatlarini manbadan topib, tuzilgan
spesifikatsiya shaklida beradi.

Chegaralar (kontraktdan): xususiyatni o'ylab topmaydi (faqat manbadan), narx
bermaydi (bu Zaraning ishi), mahsulotni tavsiya/reklama qilmaydi, sifat
bo'yicha hukm chiqarmaydi.

Diqqat: `narx` maydoni natija sxemasida umuman YO'Q — model uni qaytara
olmaydi, chegara struktura darajasida ta'minlangan.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from integrations import ApiXatosi, mahsulot_qisqa

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig, veb_manbalar
from .asos import Agent

TIZIM_PROMPT = """Sen "Mahsulot mutaxassisi Sardor" — mahsulot spesifikatsiyasi agentisan.

VAZIFAN: so'ralgan mahsulotning texnik xususiyatlarini ishonchli manbalardan
topib, tuzilgan spesifikatsiya shaklida qaytarish.

MANBALAR TARTIBI (juda muhim):
1) ICHKI KATALOG — kompaniyaning o'z tizimi. Agar topshiriqda "ICHKI
   KATALOGDAN TOPILDI" bo'limi bo'lsa, u BIRLAMCHI va eng ishonchli manba.
   Undagi xususiyatni `manba_turi: "ichki_api"` va `ishonch: "yuqori"` bilan
   yozasan, `manba_nomi` — "Climavent ichki katalogi".
2) KOMPANIYA HUJJATI — topshiriqdagi "KOMPANIYA HUJJATLARI" bo'limi. Bu
   bizning bosma katalogimiz va uslubiy hujjatlarimiz: tashqi saytdan
   ishonchliroq, lekin ichki katalogdan farqli o'laroq eskirgan bo'lishi
   mumkin. Bunday xususiyatni `manba_turi: "bilim"` deb belgilaysan va
   `manba_nomi` ga HUJJAT NOMINI o'zgartirmasdan ko'chirasan.
3) TASHQI VEB — faqat yuqoridagi ikkalasida topilmagan narsa uchun. Bunday
   xususiyatni `manba_turi: "tashqi_veb"` deb belgilaysan va havolani
   ko'rsatasan.

Ichki katalogda yoki kompaniya hujjatida mahsulot topilgan bo'lsa, tashqi
qidiruvni faqat YETISHMAGAN xususiyatlar uchun ishlatasan — hammasini
qaytadan qidirmaysan.

DIQQAT: kompaniya hujjatidagi raqamni ichki katalogdagi raqam bilan
ALMASHTIRMAYSAN va aksincha. Ikkisi zid bo'lsa — 3-qoida bo'yicha
ikkalasini ham ko'rsatasan.

QAT'IY QOIDALAR:
1) XUSUSIYATNI O'YLAB TOPMA. Manbadan topmagan xususiyatni YOZMAYSAN —
   uni `topilmagan_maydonlar` ro'yxatiga qo'shasan va qiymatini bo'sh
   qoldirasan. "Odatda shunday bo'ladi" degan taxmin ham to'qish hisoblanadi.
2) Har xususiyat uchun manba nomi va havolani ko'rsat. Manbasiz xususiyat
   yozilmaydi.
3) Manbalar zid bo'lsa — IKKALASINI ham alohida yozuv sifatida ko'rsat va
   `ziddiyatlar` ro'yxatida tushuntir. O'zing tanlab olmaysan.
4) Rasmiy ishlab chiqaruvchi sayti va rasmiy kataloglarga ustunlik ber.

SEN QILMAYDIGAN ISHLAR:
- NARX BERMAYSAN. Narx, chegirma, "qancha turadi" — bularning hammasi Narx
  analitigi Zaraning ishi. Manbada narx ko'rsangiz ham yozmaysan.
- Mahsulotni tavsiya qilmaysan, reklama qilmaysan.
- Sifat bo'yicha hukm chiqarmaysan ("yaxshi", "eng zo'r", "arzimaydi").
  Sen faqat o'lchanadigan xususiyatlarni qaytarasan.
- Raqobatchilarni taqqoslamaysan (bu Raqobat tahlilchisi Karimning ishi).

QIDIRUV: `web_search` vositasidan foydalanib rasmiy spesifikatsiyani top.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "mahsulot": "matn",
  "kategoriya": "matn",
  "xususiyatlar": [
    {
      "nomi": "masalan Maksimal unumdorlik",
      "qiymat": "masalan 1425 m3/soat",
      "manba_turi": "ichki_api | bilim | tashqi_veb",
      "manba_nomi": "matn yoki null",
      "havola": "URL yoki null",
      "ishonch": "yuqori | orta | past"
    }
  ],
  "topilmagan_maydonlar": ["so'ralgan, lekin manbada topilmagan xususiyat"],
  "ziddiyatlar": ["izoh"]
}"""

# Tanlash rejimida qaytariladigan maksimal variant soni.
#
# Kechikish TO'G'RIDAN-TO'G'RI chiqish tokeniga bog'liq (~47 token/sekund).
# Nomzodlar endi KODDA texnik moslik bo'yicha tartiblanadi, ya'ni ro'yxat
# boshidagilari haqiqatan eng mos — modelning hammasini sanab chiqishi
# menejerga foyda bermaydi, faqat kutish vaqtini uzaytiradi.
MAKS_VARIANT = 4

TANLOV_PROMPT = f"""Sen "Mahsulot mutaxassisi Sardor" — mijoz TALABIGA mos
mahsulotni kompaniya katalogidan topib beradigan agentsan.

VAZIFAN: so'rovdagi texnik talablarni ajratib olish va "ICHKI KATALOG"
bo'limidagi mahsulotlar ichidan mos keladiganlarini ko'rsatish.

QAT'IY QOIDALAR:
1) FAQAT KATALOGDAGI mahsulotni taklif qilasan. Katalogda yo'q modelni
   o'ylab topmaysan va boshqa ishlab chiqaruvchini tavsiya qilmaysan.
2) MODEL NOMINI O'ZGARTIRMAYSAN — katalogda qanday yozilgan bo'lsa,
   shundayligicha ko'chirasan.
3) Har variant uchun qaysi talabga JAVOB BERADI va qaysi biriga JAVOB
   BERMAYDI — ikkalasini ham ochiq yozasan. Faqat yaxshi tomonini
   ko'rsatish — mijozni chalg'itish.
4) TO'LIQ mos kelmasa ham ko'rsatasan, lekin `moslik_darajasi` ni
   "qisman" yoki "shartli" deb belgilaysan va nima yetishmasligini aytasan.
5) NARX BERMAYSAN va narx haqida gapirmaysan.
6) "Eng yaxshisi", "tavsiya qilaman" DEMAYSAN. Sen faqat talab bilan
   xususiyatni solishtirasan — qaysi birini olishni menejer hal qiladi.
7) Talab noaniq bo'lsa (masalan havo sarfi aytilmagan) — taxmin qilmaysan,
   `aniqlashtirish` ga savol yozasan.
8) Katalogda umuman mos mahsulot bo'lmasa — `variantlar` bo'sh qoladi va
   `qaror_izohi` da nima uchun ekanini aytasan. Bo'sh javob ham javob.
9) ENG KO'PI BILAN {MAKS_VARIANT} TA VARIANT berasan. Ro'yxat senga
   allaqachon MOSLIGI bo'yicha tartiblangan holda kelgan — boshidagilari
   eng mos. Hammasini sanab chiqma: menejerga solishtirish uchun bir
   nechta aniq variant kerak, uzun ro'yxat emas.
10) QISQA YOZASAN. `javob_beradi` va `javob_bermaydi` dagi har bir yozuv —
   3-6 so'z ("12000 m³/soat qoplaydi", "bosim aniqlanmagan"). Gap
   qurmaysan, izohni takrorlamaysan.

KOMPANIYA HUJJATLARI bo'limi bo'lsa — u TANLASH USLUBIYATI uchun: qaysi
xususiyat nima uchun muhimligini, shovqin va bosim nimaga bog'liqligini
tushuntiradi. Undan `javob_beradi` / `javob_bermaydi` izohlarini
aniqroq yozish uchun foydalanasan.

LEKIN VARIANT FAQAT "ICHKI KATALOG" BO'LIMIDAN OLINADI. Hujjatda model
nomi uchrasa ham, u ichki katalog ro'yxatida bo'lmasa — TAKLIF QILMAYSAN.
Hujjat eskirgan bo'lishi mumkin, katalogda esa hozir sotiladigani turadi.

MOSLIKNI QANDAY ANIQLAYSAN: model nomi yonidagi kvadrat qavsda katalogdan
olingan HAQIQIY raqamlar turadi — havo sarfi va bosim. Solishtirishni
o'shalar bilan qilasan. Qavs bo'lmasa, o'sha model uchun raqam katalogda
yo'q — buni `javob_bermaydi` da ochiq aytasan va TAXMIN QILMAYSAN.
Model nomidagi raqamlar (masalan "ПВН 500-250-2" — 500x250 mm kanal)
o'lcham uchun ishlatiladi, havo sarfi uchun emas.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

TANLOV_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "talablar": [{"nomi": "kanal o'lchami", "qiymat": "500x250 mm"}],
  "variantlar": [
    {
      "mahsulot": "katalogdagi mahsulot nomi",
      "model": "katalogdagi model nomi (aynan)",
      "moslik_darajasi": "to'liq | qisman | shartli",
      "javob_beradi": ["qaysi talabga mos"],
      "javob_bermaydi": ["qaysi talabga mos emas"],
      "izoh": "qisqa izoh yoki bo'sh"
    }
  ],
  "aniqlashtirish": ["menejerdan so'rash kerak bo'lgan narsa"],
  "qaror_izohi": "umumiy izoh (masalan nega mos mahsulot topilmadi)"
}"""

# Promptga sig'ishi uchun ichki katalogdan olinadigan maksimal mahsulot soni.
MAKS_ICHKI_MAHSULOT = 3
# Tanlash rejimida ko'proq nomzod kerak — menejer variantlarni solishtiradi.
MAKS_NOMZOD = 12
MAKS_MODEL = 25

# Saralashda hisobga olinmaydigan so'zlar: ular deyarli har so'rovda bor va
# tasodifiy mahsulotlarni yuqoriga ko'tarib yuboradi.
TOXTATUVCHI = frozenset({
    "uchun", "kerak", "kerakli", "bormi", "bilan", "qanday", "qaysi", "mumkin",
    "tanlab", "tanla", "topib", "ko'rsat", "korsat", "modellarini", "modellar",
    "katalogdan", "katalog", "menga", "iltimos", "hamda", "yoki",
    "нужен", "нужна", "нужно", "который", "какой", "подобрать", "модели",
    "каталога", "каталог", "пожалуйста",
})

# --- rejim aniqlash ----------------------------------------------------------
#
# Sardorning ikki xil ishi bor:
#   1) SPESIFIKATSIYA — mahsulot NOMI aytilgan ("ПВН 500-250-2 xususiyatlari");
#   2) TANLASH — mijoz TALABI aytilgan, nom noma'lum ("500x250 kanal uchun
#      2 qatorli suvli isitgich kerak").
# Menejer ko'pincha model kodini bilmaydi, mijoz esa talabni aytadi — shuning
# uchun ikkinchi rejim kerak. Rejim KODDA aniqlanadi, modelning taxminiga
# tashlab qo'yilmaydi.

# 500x250, 500х250, 500 x 250 — kanal o'lchami.
OLCHAM = re.compile(r"\d{2,4}\s*[x×хX]\s*\d{2,4}")
# Raqam + o'lchov birligi: 1500 m3/soat, 9,7 kVt, 250 Pa.
BIRLIK = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:m3|м3|m³|м³|kvt|квт|kw|вт|vt|pa|па|mm|мм|sm|см|"
    r"kg|кг|db|дб|°c|c°|v\b|в\b)",
    re.IGNORECASE,
)
# "kerak", "mos", "tanla" — tanlashga ishora qiluvchi so'zlar.
TANLOV_SOZI = re.compile(
    r"\b(kerak|kerakli|mos|moslash|tanla|tanlab|qaysi|variant|tavsiya|"
    r"подбер|подобрать|нужен|нужна|нужно|какой|вариант)",
    re.IGNORECASE,
)


# Model suffiksi: "250-2", "500-250-2", "1500" — kamida 3 raqam yoki chiziqcha.
# "2 qatorli" dagi yolg'iz "2" kod hisoblanmaydi.
KOD_RAQAMI = re.compile(r"^(?=.*\d)(?:[\d.,]*-[\d.,\-]*|\d{3,}[\d.,]*)$")


def kod_bormi(matn: str) -> bool:
    """So'rovda aniq model kodi bormi (ВК-250П, ПВН 500-250-2)?

    O'lcham ("500x250") va o'lchov birligi ("1500 m3/soat") kod EMAS — ular
    talab, shuning uchun avval matndan olib tashlanadi. Aks holda har qanday
    texnik talab "model kodi aytilgan" deb tushunilardi.
    """
    tozalangan = BIRLIK.sub(" ", OLCHAM.sub(" ", matn or ""))
    bolaklar = [b.strip(".,;:!?()[]«»\"'") for b in tozalangan.split()]
    bolaklar = [b for b in bolaklar if b]

    for b in bolaklar:
        if any(c.isdigit() for c in b) and any(c.isalpha() for c in b):
            return True
    # Kod ikki bo'lakka bo'linishi mumkin: "ПВН" + "500-250-2".
    for oldingi, keyingi in zip(bolaklar, bolaklar[1:]):
        harfli = any(c.isalpha() for c in oldingi) and not any(
            c.isdigit() for c in oldingi
        )
        if harfli and KOD_RAQAMI.match(keyingi):
            return True
    return False


# So'rovdagi havo sarfi talabi: "12000 m3/soat", "12 000 м³/ч", "8000 m3/h".
SARF_TALABI = re.compile(
    r"(\d[\d\s., ]*?)\s*(?:m3|м3|m³|м³)\s*/?\s*(?:soat|soatda|ч|час|h)\b",
    re.IGNORECASE,
)
# Mingliklar ajratgichi: "12 000", "12.000", "12,000" — kasr emas.
MINGLIK = re.compile(r"[\s., ](?=\d{3}(?:\D|$))")


def talab_sarfi(matn: str) -> float | None:
    """So'rovdagi havo sarfi talabi (m³/soat), topilmasa `None`.

    NEGA KERAK: Sardorga nomzodlar ro'yxati beriladi, lekin ilgari unda
    RAQAM yo'q edi — faqat model nomlari. Ya'ni "qaysi model 12000
    m³/soat beradi?" degan savolga model nomiga qarab taxmin qilinardi.
    Talab raqamini bilsak, mos kelmaydigan modellarni KODDA ajratamiz.
    """
    mos = SARF_TALABI.search(matn or "")
    if not mos:
        return None
    xom = MINGLIK.sub("", mos.group(1).strip()).replace(",", ".")
    try:
        qiymat = float(xom)
    except ValueError:
        return None
    return qiymat if qiymat > 0 else None


def _eng_kop_sarf(parametr: dict[str, Any] | None) -> float | None:
    """Model bera oladigan maksimal havo sarfi (noma'lum bo'lsa `None`)."""
    if not parametr:
        return None
    sarf = parametr.get("havo_sarfi")
    eng_kop = sarf[1] if isinstance(sarf, list) and len(sarf) > 1 else sarf
    if isinstance(eng_kop, list):
        eng_kop = eng_kop[0] if eng_kop else None
    return float(eng_kop) if isinstance(eng_kop, (int, float)) else None


# Promptda model nomiga BIZ qo'shgan texnik izoh: "ВК-250П [1200 m³/soat]".
QAVSLI_IZOH = re.compile(r"\s*\[[^\]]*\]\s*$")


def model_nomini_tozala(nomi: str) -> str:
    """Model nomidan biz qo'shgan qavsli izohni olib tashlaydi.

    NEGA KERAK: nomzodlar promptida endi har model yonida katalogdan
    olingan raqamlar turadi. Model javobni yozganda nomni qavsi bilan
    ko'chirib qo'yishi mumkin. U holda nom katalogdagi nomga to'g'ri
    kelmaydi va variant "katalogda yo'q" deb JIMGINA tashlanardi —
    menejer mos mahsulotni umuman ko'rmay qolardi.

    Qavsni biz qo'shganmiz, demak uni ham biz olib tashlaymiz.
    """
    return QAVSLI_IZOH.sub("", nomi or "").strip()


def _oraliq_matni(qiymat: Any, birlik: str) -> str:
    """`[3040, 12900]` -> "3040–12900 m³/soat". Bo'sh bo'lsa bo'sh satr."""
    if isinstance(qiymat, list):
        raqamlar = [q for q in qiymat if isinstance(q, (int, float))]
        if not raqamlar:
            return ""
        if len(raqamlar) == 1 or raqamlar[0] == raqamlar[-1]:
            return f"{raqamlar[0]:g} {birlik}"
        return f"{raqamlar[0]:g}–{raqamlar[-1]:g} {birlik}"
    if isinstance(qiymat, (int, float)):
        return f"{qiymat:g} {birlik}"
    return ""


def tanlov_rejimimi(matn: str) -> bool:
    """Bu so'rov mahsulot TANLASH so'roVimi (spesifikatsiya emas)?"""
    matn = matn or ""
    talab_bor = bool(OLCHAM.search(matn) or BIRLIK.search(matn))
    if not talab_bor and not TANLOV_SOZI.search(matn):
        return False
    # Aniq model kodi aytilgan bo'lsa — o'sha mahsulot haqida so'ralyapti.
    if kod_bormi(matn):
        return False
    return talab_bor or bool(TANLOV_SOZI.search(matn))


class Xususiyat(BaseModel):
    """Bitta texnik xususiyat va uning manbasi."""

    nomi: str
    qiymat: str = ""
    # Ichki katalog birlamchi, kompaniya hujjati ikkilamchi, tashqi veb
    # uchlamchi — bu farq yashirilmaydi.
    manba_turi: str = "tashqi_veb"
    manba_nomi: str | None = None
    havola: str | None = None
    ishonch: Ishonch = Ishonch.ORTA

    @property
    def ichkimi(self) -> bool:
        return self.manba_turi == "ichki_api"

    @property
    def bilimmi(self) -> bool:
        """Kompaniyaning o'z hujjatidan (bosma katalog, uslubiyat)."""
        return self.manba_turi == "bilim"


class SardorNatija(BaseModel):
    """Sardorning `natija` maydoni. Narx maydoni ataylab yo'q."""

    mahsulot: str = ""
    kategoriya: str = ""
    xususiyatlar: list[Xususiyat] = Field(default_factory=list)
    topilmagan_maydonlar: list[str] = Field(default_factory=list)
    ziddiyatlar: list[str] = Field(default_factory=list)


class Talab(BaseModel):
    """Mijozning bitta talabi (tanlash rejimi)."""

    nomi: str
    qiymat: str = ""


class Variant(BaseModel):
    """Talabga mos nomzod — katalogdagi aniq model."""

    mahsulot: str
    model: str = ""
    # to'liq | qisman | shartli — o'zim baho bermayman, faqat solishtiraman.
    moslik_darajasi: str = ""
    javob_beradi: list[str] = Field(default_factory=list)
    javob_bermaydi: list[str] = Field(default_factory=list)
    izoh: str = ""


class TanlovNatija(BaseModel):
    """Tanlash rejimi natijasi. Narx va tavsiya maydoni ATAYLAB yo'q."""

    talablar: list[Talab] = Field(default_factory=list)
    variantlar: list[Variant] = Field(default_factory=list)
    aniqlashtirish: list[str] = Field(default_factory=list)
    qaror_izohi: str = ""

    def natija_malumoti(self) -> dict[str, Any]:
        """Konvert uchun. `rejim` — presenter qaysi ko'rinishni tanlashi uchun.

        Bo'sh `variantlar` ham tanlov natijasi ("mos mahsulot yo'q"), shuning
        uchun rejimni ro'yxat bo'shligiga qarab aniqlab bo'lmaydi.
        """
        return {"rejim": "tanlov", **self.model_dump(mode="json")}


ISHONCH_TARTIBI = {Ishonch.PAST: 0, Ishonch.ORTA: 1, Ishonch.YUQORI: 2}


class MahsulotMutaxassisi(Agent):
    """Mahsulot mutaxassisi Sardor."""

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._ichki_topildi = False
        self._kontekst: dict[str, Any] = {}

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        self._ichki_topildi = False
        self._kontekst = kontekst or {}

        # Mijoz TALABI aytilgan, mahsulot nomi emas — boshqa ish, boshqa javob.
        if tanlov_rejimimi(vazifa):
            return await self._tanlab_ber(vazifa, kontekst)

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += await self._ichki_katalog(vazifa)
        topilmalar = self.bilimni_qidir(vazifa)
        topshiriq += self._bilim_matni(topilmalar)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=SardorNatija,
                json_skelet=JSON_SKELET,
                # Veb qidiruv FAQAT ichki katalog javob berolmaganda.
                #
                # Kontrakt bo'yicha ichki katalog birlamchi manba: mahsulot
                # o'sha yerda topilsa, internetdan izlashning ma'nosi yo'q —
                # u faqat javobni 20-25 soniyaga cho'zadi. Mijoz kutib
                # turadi, natija esa o'zgarmaydi.
                veb_qidiruv=not self._ichki_topildi,
                # Bu yerda o'ylash emas, KO'CHIRISH ishi: ichki katalogdan
                # kelgan texnik jadvalni tartibli maydonlarga ajratish.
                # Jonli o'lchov: medium 27s / low 21s, natija sifati esa
                # bir xil (xususiyatlar soni 14 va 15).
                effort="low",
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = SardorNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        # Ichki katalogdan olingan xususiyat — birlamchi manba, ishonch yuqori.
        for xususiyat in natija.xususiyatlar:
            if xususiyat.ichkimi:
                xususiyat.ishonch = Ishonch.YUQORI
                xususiyat.manba_nomi = xususiyat.manba_nomi or "Climavent ichki katalogi"

        # Manbasi ko'rsatilmagan xususiyat spesifikatsiyaga tushmaydi.
        manbasiz = [x.nomi for x in natija.xususiyatlar if not (x.manba_nomi or x.havola)]
        if manbasiz:
            natija.xususiyatlar = [
                x for x in natija.xususiyatlar if (x.manba_nomi or x.havola)
            ]
            natija.topilmagan_maydonlar.extend(manbasiz)
            self.ogohlantirish = (
                f"{len(manbasiz)} ta xususiyat manbasiz kelgani uchun olib tashlandi"
            )

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=self._manbalarni_yig(javob, natija),
            ishonch=self._umumiy_ishonch(natija),
            tasdiq_kerak=False,
            izoh=self._izoh(natija),
        )

    # --- tanlash rejimi ------------------------------------------------------

    async def _tanlab_ber(
        self, vazifa: str, kontekst: dict[str, Any] | None
    ) -> Konvert:
        """Talabga mos mahsulotlarni katalogdan tanlaydi.

        Veb qidiruv YO'Q: taklif faqat o'z katalogimizdan bo'lishi kerak,
        aks holda mavjud bo'lmagan mahsulot taklif qilinardi.
        """
        # Talab raqami + katalog raqamlari AVVAL olinadi: nomzodlarni
        # saralashda ham, promptni yozishda ham shular ishlatiladi.
        kerakli_sarf = self._kerakli_sarf(vazifa)
        parametrlar = await self._texnik() if kerakli_sarf else {}

        nomzodlar = await self._nomzodlar(vazifa, parametrlar, kerakli_sarf)
        if nomzodlar is None:
            return xato_konvert(
                self.rol,
                "Ichki katalogga ulanib bo'lmadi — mos mahsulotni tanlash uchun "
                "katalog kerak. Biroz keyin qayta urinib ko'ring.",
            )

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += self._nomzod_matni(nomzodlar, parametrlar, kerakli_sarf)
        # Tanlash rejimida hujjat MAHSULOT ro'yxati uchun emas, TANLASH
        # uslubiyati uchun kerak: "Ventilyator tanlash — ish nuqtasi",
        # "Shovqin", "Havo sarfi" kabi hujjatlar qaysi variant qaysi
        # talabga javob berishini tushuntiradi.
        topshiriq += self._bilim_matni(self.bilimni_qidir(vazifa))

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TANLOV_PROMPT,
                natija_modeli=TanlovNatija,
                json_skelet=TANLOV_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        try:
            natija = TanlovNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        # Model nomni promptdagi qavsli izohi bilan ko'chirgan bo'lishi
        # mumkin — quyidagi tekshiruvdan oldin uni tozalaymiz.
        for variant in natija.variantlar:
            if variant.model:
                variant.model = model_nomini_tozala(variant.model)

        # KATALOGDA YO'Q MODEL — kodda tashlanadi, promptga tayanmaymiz.
        mavjud = self._katalog_nomlari(nomzodlar)
        soxta = [
            v.model or v.mahsulot
            for v in natija.variantlar
            if v.model and v.model.strip().lower() not in mavjud
        ]
        if soxta:
            natija.variantlar = [
                v
                for v in natija.variantlar
                if not v.model or v.model.strip().lower() in mavjud
            ]
            self.ogohlantirish = (
                f"{len(soxta)} ta variant katalogda topilmagani uchun "
                f"olib tashlandi: {', '.join(soxta[:3])}"
            )

        izoh = f"{len(natija.variantlar)} ta mos variant topildi"
        if not natija.variantlar:
            izoh = "Katalogdan talabga mos mahsulot topilmadi"
        if natija.aniqlashtirish:
            izoh += f" | {len(natija.aniqlashtirish)} ta savol bor"

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.natija_malumoti(),
            manba=[
                self.kontrakt_manbasi(),
                Manba(tur="ichki_api", nom="Climavent ichki katalogi"),
            ],
            ishonch=Ishonch.YUQORI if natija.variantlar else Ishonch.ORTA,
            tasdiq_kerak=False,
            izoh=izoh,
        )

    async def _nomzodlar(
        self,
        vazifa: str,
        parametrlar: dict[str, dict[str, Any]] | None = None,
        kerakli_sarf: float | None = None,
    ) -> list[dict[str, Any]] | None:
        """Tanlash uchun nomzod mahsulotlar (API yiqilsa — None).

        Talab so'rovida model kodi bo'lmagani uchun API qidiruvi ko'pincha
        hech narsa topmaydi. Shuning uchun topilmasa butun katalogga
        tushamiz — u keshlangan va tanlash aynan shuni talab qiladi.
        """
        try:
            # HAR DOIM butun katalog. API qidiruvi talab matni bilan ishonchsiz
            # ("kanal ventilyatori" -> 0 natija, ba'zan 1 ta aloqasiz mahsulot),
            # tanlash esa aynan kenglikni talab qiladi. Qidiruv natijasi
            # faqat tartibni kuchaytirish uchun ishlatiladi.
            katalog = await self.api.mahsulotlar()
            try:
                kuchaytir = {m.get("id") for m in await self.api.qidir_keng(vazifa)}
            except ApiXatosi:
                kuchaytir = set()
        except ApiXatosi as xato:
            self.ogohlantirish = f"ichki katalogga ulanib bo'lmadi ({xato})"
            return None
        # Muhandis (Rustam) hisobdan chiqib model tanlagan bo'lsa, o'sha
        # modellar ro'yxat boshida turishi kerak — aks holda ular
        # MAKS_NOMZOD chegarasidan tashqarida qolib ketadi.
        return self._saralab(
            katalog, vazifa + " " + self._muhandis_modellari(), kuchaytir,
            parametrlar, kerakli_sarf,
        )

    def _muhandis_hisobi(self) -> dict[str, Any]:
        """Zanjirda muhandis (Rustam) qaytargan hisob (bo'lmasa — bo'sh)."""
        kontekst = self._kontekst or {}
        zanjir = kontekst.get("zanjir_natijalari") or {}
        hisob = zanjir.get("hvac-calc") if isinstance(zanjir, dict) else None
        if not isinstance(hisob, dict) or not hisob:
            hisob = kontekst.get("oldingi_natija") or {}
        return hisob if isinstance(hisob, dict) else {}

    def _kerakli_sarf(self, vazifa: str) -> float | None:
        """Talab qilingan havo sarfi — avval hisobdan, keyin matndan.

        ZANJIRDA MUHANDIS HISOBI BIRLAMCHI. Rustam `jami_sarf` ni RAQAM
        sifatida qaytaradi — uni matndan qidirishning ma'nosi yo'q va
        xato ehtimoli bor: vazifa matnida "250 m2 restoran" turishi
        mumkin, sarf raqami esa faqat hisobda bo'ladi.
        """
        hisob = self._muhandis_hisobi()
        jami = hisob.get("jami_sarf")
        if isinstance(jami, (int, float)) and jami > 0:
            return float(jami)
        return talab_sarfi(f"{vazifa} {hisob}")

    def _muhandis_modellari(self) -> str:
        """Oldingi qadamda muhandis tanlagan model kodlari (bo'lmasa — bo'sh)."""
        hisob = self._muhandis_hisobi()
        modellar: list[str] = []
        for uskuna in hisob.get("uskunalar") or []:
            if isinstance(uskuna, dict):
                modellar.extend(str(m) for m in (uskuna.get("modellar") or []) if m)
        return " ".join(modellar[:MAKS_MODEL])

    @staticmethod
    def _saralab(
        katalog: list[dict[str, Any]],
        vazifa: str,
        kuchaytir: set[Any] | None = None,
        parametrlar: dict[str, dict[str, Any]] | None = None,
        kerakli_sarf: float | None = None,
    ) -> list[dict[str, Any]]:
        """Katalogni so'rovga mosligi bo'yicha tartiblaydi.

        BIRINCHI MEZON — TEXNIK MOSLIK, so'z o'xshashligi emas.

        Jonli xato (2026-08-17): "12000 m³/soat kerak" so'roviga nomzodlar
        faqat so'z o'xshashligi bo'yicha tanlanardi. Natijada ro'yxatga
        "Kanalli ventilyator VKPP", "Filtr FKG" kabi nomi o'xshash, lekin
        sarfi umuman yetmaydigan mahsulotlar tushardi: 149 ta modeldan
        atigi 18 tasida texnik raqam bor edi. Model esa raqamsiz ro'yxatdan
        "qaysi biri 12000 beradi?" degan savolga TAXMIN bilan javob berardi
        — sekin (30 s), beqaror (bir xil so'rovga har xil javob) va past
        effortda umuman javob topolmasdi.

        Endi sarfi yetadigan modeli BOR mahsulotlar birinchi turadi.
        """
        kuchaytir = kuchaytir or set()
        parametrlar = parametrlar or {}
        sozlar = {
            s
            for s in (
                b.strip(".,;:!?()[]«»\"'").lower() for b in (vazifa or "").split()
            )
            if len(s) > 3 and s not in TOXTATUVCHI
        }

        def texnik_mos(qisqa: dict[str, Any]) -> int:
            """Shu mahsulotda sarfi yetadigan model bormi?"""
            if not kerakli_sarf:
                return 0
            for nomi in qisqa["modellar"] or []:
                eng_kop = _eng_kop_sarf(parametrlar.get(nomi))
                if eng_kop is not None and eng_kop >= kerakli_sarf:
                    return 1
            return 0

        def ball(mahsulot: dict[str, Any]) -> tuple[int, int, int]:
            qisqa = mahsulot_qisqa(mahsulot)
            matn = " ".join(
                str(x).lower()
                for x in (
                    qisqa["nomi"], qisqa["kategoriya"], qisqa["tavsif"],
                    *(qisqa["modellar"] or []),
                )
                if x
            )
            mos = sum(1 for s in sozlar if s in matn)
            return (
                texnik_mos(qisqa),
                mos,
                1 if mahsulot.get("id") in kuchaytir else 0,
            )

        # Hech biri mos kelmasa tartib o'zgarmaydi — "katalogda bunday
        # mahsulot yo'q" javobi ham to'g'ri javob.
        return sorted(katalog, key=ball, reverse=True)

    async def _texnik(self) -> dict[str, dict[str, Any]]:
        """Model bo'yicha texnik parametrlar (yiqilsa — bo'sh lug'at).

        Bu ma'lumot diskda 7 kun keshlanadi, shuning uchun chaqiruv deyarli
        tekin. Yiqilsa ish to'xtamaydi — shunchaki raqamsiz ishlanadi.
        """
        try:
            return await self.api.texnik_parametrlar()
        except Exception as xato:  # kesh/tarmoq — tanlash to'xtamasin
            self.ogohlantirish = "; ".join(filter(None, [
                self.ogohlantirish, f"texnik parametrlar olinmadi ({xato})",
            ]))
            return {}

    @staticmethod
    def _modellarni_tanla(
        modellar: list[str],
        parametrlar: dict[str, dict[str, Any]],
        kerakli_sarf: float | None,
    ) -> tuple[list[str], int]:
        """Modellarni saralaydi va texnik raqamlar bilan yozadi.

        Talab raqami ma'lum bo'lsa, sarfi YETMAYDIGAN modellar kodda
        chiqarib tashlanadi — model ularni ko'rmaydi ham. Ilgari bularning
        hammasi promptga tushardi va model 25 ta nomdan qaysi biri 12000
        m³/soat berishini o'zi taxmin qilishga majbur edi.

        Sarfi noma'lum modellar QOLDIRILADI: ma'lumot yo'qligi "yaramaydi"
        degani emas (Rustamdagi qoida bilan bir xil).

        Qaytaradi: (yozilgan qatorlar, tashlangan modellar soni).
        """
        mos: list[tuple[float, str]] = []
        nomalum: list[str] = []
        tashlandi = 0

        for nomi in modellar:
            p = parametrlar.get(nomi)
            matn = nomi
            bolaklar = [
                _oraliq_matni(p.get("havo_sarfi"), "m³/soat") if p else "",
                _oraliq_matni(p.get("bosim"), "Pa") if p else "",
            ]
            bolaklar = [b for b in bolaklar if b]
            if bolaklar:
                matn = f"{nomi} [{', '.join(bolaklar)}]"

            eng_kop = _eng_kop_sarf(p)
            if kerakli_sarf is None or eng_kop is None:
                nomalum.append(matn)
                continue
            if eng_kop < kerakli_sarf:
                tashlandi += 1
                continue
            # Zaxirasi kichigi oldinda: 12000 kerak bo'lsa 63000 lik
            # markaziy qurilma birinchi bo'lib turmasin.
            mos.append((eng_kop - kerakli_sarf, matn))

        mos.sort(key=lambda x: x[0])
        tanlangan = [m for _, m in mos] + nomalum
        return tanlangan[:MAKS_MODEL], tashlandi

    def _nomzod_matni(
        self,
        nomzodlar: list[dict[str, Any]],
        parametrlar: dict[str, dict[str, Any]] | None = None,
        kerakli_sarf: float | None = None,
    ) -> str:
        """Nomzodlarni model ro'yxati bilan promptga yozadi."""
        if not nomzodlar:
            return "\n\nICHKI KATALOG: bo'sh."

        parametrlar = parametrlar or {}
        qatorlar = [
            f"\n\nICHKI KATALOG ({len(nomzodlar)} ta mahsulot; "
            f"quyida {min(len(nomzodlar), MAKS_NOMZOD)} tasi):"
        ]
        if kerakli_sarf:
            qatorlar.append(
                f"\nTalab: {kerakli_sarf:g} m³/soat. Quyidagi modellarning "
                "sarfi shu talabga YETADI — sarfi yetmaydiganlari ro'yxatdan "
                "allaqachon chiqarilgan. Qavs ichidagi raqamlar katalogdan "
                "olingan, ularni o'zgartirma."
            )
        for mahsulot in nomzodlar[:MAKS_NOMZOD]:
            qisqa = mahsulot_qisqa(mahsulot)
            qatorlar.append(f"\n### {qisqa['nomi']}")
            if qisqa["kategoriya"]:
                qatorlar.append(f"- kategoriya: {qisqa['kategoriya']}")
            if qisqa["tavsif"]:
                qatorlar.append(f"- tavsif: {qisqa['tavsif']}")
            modellar, tashlandi = self._modellarni_tanla(
                [m for m in qisqa["modellar"] if m], parametrlar, kerakli_sarf
            )
            if modellar:
                qatorlar.append(f"- modellar: {', '.join(modellar)}")
            elif tashlandi:
                qatorlar.append(
                    f"- modellar: (hammasi — {tashlandi} ta — sarfi yetmaydi)"
                )
            else:
                qatorlar.append("- modellar: (kiritilmagan)")
            if modellar and tashlandi:
                qatorlar.append(
                    f"- (yana {tashlandi} ta model sarfi yetmagani uchun "
                    "ko'rsatilmadi)"
                )
        if len(nomzodlar) > MAKS_NOMZOD:
            # DIQQAT: bu ro'yxat SO'ROVGA MOSLIGI bo'yicha allaqachon
            # tartiblangan — yuqoridagilar eng mos nomzodlar. Ilgari bu yerda
            # "yana 125 ta mahsulot bor" deyilardi va model "to'liq katalogni
            # bering" deb javob qaytarardi. Foydalanuvchi katalogni bera
            # olmaydi — bu javob foydasiz.
            qatorlar.append(
                f"\n(Katalogda jami {len(nomzodlar)} ta mahsulot bor; yuqoridagi "
                f"{MAKS_NOMZOD} tasi so'rovga MOSLIGI bo'yicha tanlab olingan — "
                "eng mos nomzodlar shular. To'liq katalog SO'RAMA: uni "
                "foydalanuvchi bera olmaydi. Shu ro'yxatdan tanla; biror "
                "TURDAGI uskuna (masalan ventilyator) topilmasa, faqat "
                "o'shani `aniqlashtirish` da ayt va qolganini baribir tanla.)"
            )
        return "\n".join(qatorlar)

    @staticmethod
    def _katalog_nomlari(nomzodlar: list[dict[str, Any]]) -> set[str]:
        """Katalogdagi barcha model va mahsulot nomlari (kichik harfda)."""
        nomlar: set[str] = set()
        for mahsulot in nomzodlar:
            qisqa = mahsulot_qisqa(mahsulot)
            if qisqa["nomi"]:
                nomlar.add(qisqa["nomi"].strip().lower())
            for model in qisqa["modellar"]:
                if model:
                    nomlar.add(str(model).strip().lower())
            for xususiyat in mahsulot.get("characters") or []:
                if isinstance(xususiyat, dict) and xususiyat.get("title"):
                    nomlar.add(str(xususiyat["title"]).strip().lower())
        return nomlar

    # --- ichki katalog (birlamchi manba) -------------------------------------

    async def _ichki_katalog(self, vazifa: str) -> str:
        """Ichki API'dan mahsulotni qidiradi va topshiriqqa qo'shadi.

        API ishlamasa — bu xato emas: ochiq aytamiz va tashqi manbaga o'tamiz
        (to'qib chiqarish yo'q).
        """
        try:
            topilgan = await self.api.qidir_keng(vazifa)
        except ApiXatosi as xato:
            self.ogohlantirish = f"ichki katalogga ulanib bo'lmadi ({xato})"
            return (
                "\n\nICHKI KATALOG: mavjud emas (API'ga ulanib bo'lmadi). "
                "Faqat tashqi manbalardan qidir va buni izohda ayt."
            )

        if not topilgan:
            return (
                "\n\nICHKI KATALOG: bu mahsulot kompaniyaning ichki katalogida "
                "TOPILMADI. Tashqi manbalardan qidirishing mumkin, lekin buni "
                "`manba_turi: \"tashqi_veb\"` deb belgila."
            )

        self._ichki_topildi = True
        mahsulotlar = topilgan[:MAKS_ICHKI_MAHSULOT]

        # Xususiyatlar BIR VAQTDA olinadi. Ketma-ket so'ralganda har
        # mahsulot uchun alohida kutish bo'lardi va mijoz shuncha ko'proq
        # kutardi — natija esa aynan bir xil.
        async def xususiyat_ol(mahsulot: dict[str, Any]) -> list[dict[str, Any]]:
            try:
                return await self.api.mahsulot_xususiyatlari(mahsulot)
            except ApiXatosi:
                return []

        hammasi = await asyncio.gather(*(xususiyat_ol(m) for m in mahsulotlar))

        bolaklar = ["\n\nICHKI KATALOGDAN TOPILDI (birlamchi, ishonchli manba):"]
        for mahsulot, xususiyatlar in zip(mahsulotlar, hammasi):
            qisqa = mahsulot_qisqa(mahsulot)
            bolaklar.append(
                f"\n### {qisqa['nomi']} (id: {qisqa['id']})\n"
                f"- kategoriya: {qisqa['kategoriya']}\n"
                f"- ishlab chiqaruvchi: {qisqa['ishlab_chiqaruvchi']}\n"
                f"- tavsif: {qisqa['tavsif']}\n"
                f"- modellar: {', '.join(m for m in qisqa['modellar'] if m) or '—'}"
            )
            for xususiyat in xususiyatlar:
                if xususiyat["qiymat"]:
                    bolaklar.append(
                        f"- texnik jadval [{xususiyat['nomi']}]:\n{xususiyat['qiymat']}"
                    )

        if len(topilgan) > MAKS_ICHKI_MAHSULOT:
            bolaklar.append(
                f"\n(Ichki katalogda jami {len(topilgan)} ta mos mahsulot bor; "
                f"yuqorida birinchi {MAKS_ICHKI_MAHSULOT} tasi.)"
            )
        return "\n".join(bolaklar)

    def _bilim_matni(self, topilmalar: list[Any]) -> str:
        """Bilim bazasidan topilganini topshiriqqa qo'shadi.

        Bu Climaventning O'Z hujjatlari (bosma katalog, uslubiyat, model
        kodini o'qish qoidalari). Ichki katalog API'da faqat jonli
        mahsulot kartochkasi bor — nima uchun qaysi model tanlanishi,
        kod qanday o'qilishi kabi bilim esa shu hujjatlarda.

        Topilmasa — jim qolmaymiz: modelga ochiq aytamiz, aks holda u
        hujjatga tayangandek javob berib qo'yishi mumkin.
        """
        if not topilmalar:
            return (
                "\n\nKOMPANIYA HUJJATLARI: bu so'rov bo'yicha bazada hujjat "
                "topilmadi. Xususiyatlarni faqat ichki katalog va tashqi "
                "manbalardan olasan."
            )
        return "\n\nKOMPANIYA HUJJATLARI (ikkilamchi manba):\n" + kontekst_matni(
            topilmalar
        )

    def _manbalarni_yig(self, javob: Any, natija: SardorNatija) -> list[Manba]:
        manbalar: list[Manba] = []
        korilgan: set[str] = set()

        for xususiyat in natija.xususiyatlar:
            kalit = xususiyat.havola or xususiyat.manba_nomi or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            # Manba turi javobda ochiq ko'rinadi (o'zgarmas qoida).
            if xususiyat.ichkimi:
                tur = "ichki_api"
            elif xususiyat.bilimmi:
                tur = "bilim"
            else:
                tur = "tashqi_veb"
            manbalar.append(
                Manba(
                    tur=tur,
                    nom=xususiyat.manba_nomi or kalit,
                    havola=xususiyat.havola,
                )
            )

        for veb in veb_manbalar(javob):
            if "xato" in veb:
                manbalar.append(Manba(tur="tashqi_veb", nom=f"qidiruv xatosi: {veb['xato']}"))
                continue
            kalit = veb.get("havola") or veb.get("nom") or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            manbalar.append(
                Manba(
                    tur="tashqi_veb",
                    nom=veb.get("nom") or kalit,
                    havola=veb.get("havola"),
                    sana=veb.get("sana"),
                )
            )

        if self._ichki_topildi and not any(m.tur == "ichki_api" for m in manbalar):
            # Ichki katalogdan olingani aniq bo'lsa, manba ro'yxatida ko'rinsin.
            manbalar.insert(0, Manba(tur="ichki_api", nom="Climavent ichki katalogi"))
        if not manbalar:
            manbalar.append(Manba(tur="tashqi_veb", nom="qidiruv — spesifikatsiya topilmadi"))
        return manbalar

    def _umumiy_ishonch(self, natija: SardorNatija) -> Ishonch:
        if not natija.xususiyatlar:
            return Ishonch.PAST

        # Hammasi ichki katalogdan bo'lsa — ishonch yuqori (birlamchi manba).
        if all(x.ichkimi for x in natija.xususiyatlar) and not natija.ziddiyatlar:
            return Ishonch.YUQORI

        eng_past = min(natija.xususiyatlar, key=lambda x: ISHONCH_TARTIBI[x.ishonch]).ishonch
        if (natija.ziddiyatlar or natija.topilmagan_maydonlar) and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        return eng_past

    def _izoh(self, natija: SardorNatija) -> str:
        ichki = sum(1 for x in natija.xususiyatlar if x.ichkimi)
        bilim = sum(1 for x in natija.xususiyatlar if x.bilimmi)
        tashqi = len(natija.xususiyatlar) - ichki - bilim

        bolaklar = [f"{len(natija.xususiyatlar)} ta xususiyat topildi"]
        if natija.xususiyatlar:
            # Manba taqsimoti ochiq ko'rsatiladi (o'zgarmas qoida).
            bolaklar.append(
                f"ichki katalog: {ichki}, kompaniya hujjati: {bilim}, "
                f"tashqi veb: {tashqi}"
            )
        if natija.topilmagan_maydonlar:
            bolaklar.append("topilmadi (bo'sh qoldirildi): " + ", ".join(natija.topilmagan_maydonlar))
        if natija.ziddiyatlar:
            bolaklar.append(f"{len(natija.ziddiyatlar)} ta manba ziddiyati belgilandi")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)

"""Texnik jadvallardan model parametrlarini ajratish.

NEGA BU KERAK
-------------
Backend katalogida ventilyatorning havo sarfi (m³/soat) va bosimi (Pa)
uchun **maydon yo'q** — `product_models` da faqat nom, narx, SAP kodi va
qoldiq bor. Shuning uchun "8000 m³/soat kerak" degan hisobdan mos
ventilyatorga o'tib bo'lmasdi.

Lekin ma'lumotning O'ZI bor: u `products.characters[].contentJson`
havolasidagi R2 fayl ichida, ProseMirror (TipTap) hujjatidagi **jadval**
ko'rinishida turadi. Jonli o'lchov (2026-08-11, butun katalog):

    137 mahsulotdan 124 tasida texnik hujjat bor
    63 tasida "Производительность, м³/ч" ustuni bor
    bu 63 mahsulotning modellari — 894 / 1482 (60%)

Shu modul o'sha jadvallarni o'qib, model → parametr jadvaliga aylantiradi.

QAT'IY QOIDA
------------
Raqam FAQAT jadvaldan olinadi. Model bu yerga umuman aralashmaydi
(`import anthropic` yo'q va bo'lmaydi — test bilan qo'riqlanadi).
Jadval tushunarsiz bo'lsa parametr **bo'sh qoladi** — taxmin qilinmaydi.

CHEKLOV
-------
Jadvallar qo'lda tuzilgan va har mahsulotda boshqacha: birlashgan
kataklar, ikki qatorli sarlavha, takrorlanuvchi ustun guruhlari, ba'zida
"Рассчитывается индивидуально" degan matn. Shuning uchun qamrov 100%
bo'lmaydi — nimani ishonchli o'qib bo'lsa, o'shani olamiz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

__all__ = [
    "ModelParametri",
    "jadval_gridlari",
    "jadvaldan_parametrlar",
    "hujjatdan_parametrlar",
    "moslashtir",
    "nomlash",
    "son_oraligi",
    "ustun_turi",
]

# --- ustun nomlarini tanish ---------------------------------------------------

# Havo sarfi ustuni. "по теплу" (issiqlik bo'yicha) va "расход воды"
# (suv sarfi) ATAYLAB chiqarib tashlanadi — ular boshqa kattalik.
HAVO_MOS = re.compile(r"производительн|расход\s*возд|подача\s*возд|по\s*воздуху", re.I)
HAVO_MOS_EMAS = re.compile(
    r"по\s*теплу|теплопроизвод|расход\s*воды|воды,|тепл\w*\s*производ|холодопроизвод",
    re.I,
)
BOSIM_MOS = re.compile(r"давлени|напор", re.I)
BOSIM_MOS_EMAS = re.compile(r"греющего\s*пара|рабочее\s*давлени|давлени\w*\s*воды", re.I)
QUVVAT_MOS = re.compile(r"мощность", re.I)
MODEL_MOS = re.compile(r"модель|типоразмер|марка|обозначение|наименование", re.I)

# Birlik ko'paytmasi: "Производительность, тыс. м3/ч" -> 1000
MINGLIK = re.compile(r"тыс\.?|тысяч", re.I)
# Havo sarfi birligi haqiqatan m³/soat ekanini tasdiqlaydi.
HAVO_BIRLIGI = re.compile(r"м\s*[3³]\s*/\s*ч|m\s*[3³]\s*/\s*h|м\s*[3³]\s*/\s*час", re.I)
QUVVAT_KVT = re.compile(r"квт|kw", re.I)

# Real ventilyator chegaralari — bulardan tashqarisi noto'g'ri o'qilgan
# ustun (masalan aylanish tezligi yoki og'irlik) demakdir.
HAVO_ENG_KAM = 20.0
HAVO_ENG_KOP = 500_000.0
BOSIM_ENG_KOP = 20_000.0


def ustun_turi(sarlavha: str) -> str | None:
    """Ustun nomidan kattalik turini aniqlaydi (bilinmasa None)."""
    matn = " ".join((sarlavha or "").split())
    if not matn:
        return None
    if HAVO_MOS.search(matn) and not HAVO_MOS_EMAS.search(matn):
        return "havo"
    if BOSIM_MOS.search(matn) and not BOSIM_MOS_EMAS.search(matn):
        return "bosim"
    if QUVVAT_MOS.search(matn) and QUVVAT_KVT.search(matn):
        return "quvvat"
    return None


def _koeffitsiyent(sarlavha: str) -> float:
    return 1000.0 if MINGLIK.search(sarlavha or "") else 1.0


# --- sonlarni o'qish ----------------------------------------------------------

# "890-1900", "1,60-3,75", "10…20", "1425", "0,98"
SON = re.compile(r"\d+(?:[.,]\d+)?")
ORALIQ_AJRATGICH = re.compile(r"\s*(?:[-–—…]|\.{2,})\s*")


def son_oraligi(qiymat: str) -> tuple[float, float] | None:
    """Katak matnidan (eng kichik, eng katta) juftlikni chiqaradi.

    "890-1900" -> (890, 1900);  "1425" -> (1425, 1425);
    "-" yoki "Рассчитывается индивидуально" -> None.
    """
    matn = (qiymat or "").replace("\xa0", " ").strip()
    if not matn:
        return None
    # Aniq son bo'lmagan matn (masalan "Рассчитывается индивидуально")
    # tasodifan son chiqarib yubormasin.
    if len(SON.findall(matn)) == 0:
        return None
    sonlar = [float(x.replace(",", ".")) for x in SON.findall(matn)]
    if not sonlar:
        return None
    # Faqat oraliq ko'rinishidagi ikki son juftlik hisoblanadi; qolganda
    # birinchi son olinadi (masalan "+65°С" -> 65 bo'lib qolmasligi uchun
    # bu funksiya faqat son ustunlariga qo'llanadi).
    if len(sonlar) == 2 and ORALIQ_AJRATGICH.search(matn):
        return (min(sonlar), max(sonlar))
    return (sonlar[0], sonlar[0])


# --- jadvalni to'rga (grid) aylantirish ---------------------------------------


def _matnlar(tugun: Any) -> list[str]:
    if isinstance(tugun, dict):
        if tugun.get("type") == "text":
            return [str(tugun.get("text") or "")]
        return [x for b in (tugun.get("content") or []) for x in _matnlar(b)]
    if isinstance(tugun, list):
        return [x for b in tugun for x in _matnlar(b)]
    return []


def _butun(qiymat: Any, standart: int = 1) -> int:
    try:
        son = int(qiymat)
    except (TypeError, ValueError):
        return standart
    return son if son > 0 else standart


def jadval_gridlari(hujjat: Any) -> list[list[list[str]]]:
    """Hujjatdagi har jadvalni to'g'ri to'rtburchak to'rga aylantiradi.

    `colspan` va `rowspan` hisobga olinadi: birlashgan katak egallagan
    barcha kataklarga o'sha matn qo'yiladi. Shusiz ustun raqamlari
    siljib ketadi va noto'g'ri qiymat o'qiladi.
    """
    gridlar: list[list[list[str]]] = []

    def jadvalni_yig(jadval: dict[str, Any]) -> None:
        to_r: list[list[str | None]] = []
        # DIQQAT: qator raqami alohida sanaladi. Oldingi qatordagi
        # `rowspan` shu qatorni ALLAQACHON yaratib qo'ygan bo'lishi mumkin
        # — o'shanda yana bittasini qo'shsak, qator siljib ketadi.
        satr = -1
        for qator in jadval.get("content") or []:
            if not isinstance(qator, dict) or qator.get("type") != "tableRow":
                continue
            satr += 1
            while len(to_r) <= satr:
                to_r.append([])
            ustun = 0
            for katak in qator.get("content") or []:
                if not isinstance(katak, dict):
                    continue
                attrs = katak.get("attrs") or {}
                kengligi = _butun(attrs.get("colspan"))
                balandligi = _butun(attrs.get("rowspan"))
                matn = " ".join(_matnlar(katak)).strip()
                # Band bo'lmagan birinchi ustunni topamiz.
                while ustun < len(to_r[satr]) and to_r[satr][ustun] is not None:
                    ustun += 1
                for ds in range(balandligi):
                    while len(to_r) <= satr + ds:
                        to_r.append([])
                    qator_ref = to_r[satr + ds]
                    for du in range(kengligi):
                        joy = ustun + du
                        while len(qator_ref) <= joy:
                            qator_ref.append(None)
                        if qator_ref[joy] is None:
                            qator_ref[joy] = matn
                ustun += kengligi
        if to_r:
            eni = max(len(q) for q in to_r)
            gridlar.append([
                [(q[i] if i < len(q) and q[i] is not None else "") for i in range(eni)]
                for q in to_r
            ])

    def yur(tugun: Any) -> None:
        if isinstance(tugun, dict):
            if tugun.get("type") == "table":
                jadvalni_yig(tugun)
                return
            for bola in tugun.get("content") or []:
                yur(bola)
        elif isinstance(tugun, list):
            for bola in tugun:
                yur(bola)

    yur(hujjat)
    return gridlar


# --- jadvaldan parametr ajratish ----------------------------------------------


@dataclass(frozen=True)
class ModelParametri:
    """Bitta modelning jadvaldan o'qilgan parametrlari."""

    model: str
    havo_min: float | None = None
    havo_maks: float | None = None
    bosim_min: float | None = None
    bosim_maks: float | None = None
    quvvat_kvt: float | None = None
    manba: str = ""

    @property
    def havo_bormi(self) -> bool:
        return self.havo_maks is not None

    def birlashtir(self, boshqa: "ModelParametri") -> "ModelParametri":
        """Bir xil nomli ikki qatorni QAMROVGA birlashtiradi.

        Bitta model nomi jadvalda bir necha marta uchraydi — quvvat va
        aylanish bo'yicha variantlar (`ВКРВ-5` 8 qator). Ular orasidan
        bittasini tanlash oila haqidagi javobni buzadi, shuning uchun
        oila darajasida eng past mindan eng yuqori maksgacha olinadi.

        Aniq artikul so'ralganda esa `moslashtir()` o'z qatorini
        tanlaydi — pastdagi izohga qarang.
        """
        def eng_kichik(a, b):
            sonlar = [x for x in (a, b) if x is not None]
            return min(sonlar) if sonlar else None

        def eng_katta(a, b):
            sonlar = [x for x in (a, b) if x is not None]
            return max(sonlar) if sonlar else None

        return ModelParametri(
            model=self.model,
            havo_min=eng_kichik(self.havo_min, boshqa.havo_min),
            havo_maks=eng_katta(self.havo_maks, boshqa.havo_maks),
            bosim_min=eng_kichik(self.bosim_min, boshqa.bosim_min),
            bosim_maks=eng_katta(self.bosim_maks, boshqa.bosim_maks),
            quvvat_kvt=eng_katta(self.quvvat_kvt, boshqa.quvvat_kvt),
            manba=self.manba or boshqa.manba,
        )

    def yetadimi(self, kerakli_sarf: float) -> bool:
        """Shu model kerakli havo sarfini bera oladimi."""
        return self.havo_maks is not None and self.havo_maks >= kerakli_sarf

    def dict_holida(self) -> dict[str, Any]:
        malumot: dict[str, Any] = {"model": self.model}
        if self.havo_maks is not None:
            malumot["havo_sarfi"] = (
                round(self.havo_maks)
                if self.havo_min == self.havo_maks
                else [round(self.havo_min or 0), round(self.havo_maks)]
            )
        if self.bosim_maks is not None:
            malumot["bosim"] = (
                round(self.bosim_maks)
                if self.bosim_min == self.bosim_maks
                else [round(self.bosim_min or 0), round(self.bosim_maks)]
            )
        if self.quvvat_kvt is not None:
            malumot["quvvat_kvt"] = self.quvvat_kvt
        return malumot


def _model_ustunlari(sarlavha: list[str]) -> list[int]:
    """Sarlavhada "Модель" turidagi ustunlar (takrorlanishi mumkin)."""
    topilgan = [i for i, nom in enumerate(sarlavha) if MODEL_MOS.search(nom or "")]
    # Takroriy birlashgan katak bir nechta ustunga yozilgan bo'lishi mumkin —
    # ketma-ketlaridan faqat birinchisi olinadi.
    natija: list[int] = []
    for i in topilgan:
        if not natija or i - natija[-1] > 1 or sarlavha[i] != sarlavha[i - 1]:
            natija.append(i)
    return natija


# Sof son katagi: "5,5", "1000", "890-1900". Harf bo'lsa — sarlavha.
SOF_SON = re.compile(r"^[\d\s.,\-–—/]+$")


def _sof_sonmi(katak: str) -> bool:
    """Katak faqat sondan iboratmi (birlik yozuvisiz)."""
    matn = (katak or "").replace("\xa0", " ").strip()
    if not matn:
        return False
    return bool(SOF_SON.fullmatch(matn)) and any(ch.isdigit() for ch in matn)


def _sarlavha_qatorlari(grid: list[list[str]]) -> tuple[list[str], int]:
    """Sarlavhani (kerak bo'lsa ikki qatorni birlashtirib) qaytaradi.

    Ba'zi jadvallarda ustun nomi ikki qatorga bo'lingan:
        Модель | Производительность          | Площадь ...
               | по воздуху, м3/час | по теплу, кВт
    Ikkinchi qator birinchisiga qo'shib o'qiladi.
    """
    if not grid:
        return [], 0
    sarlavha = list(grid[0])
    ishlatilgan = 1
    if len(grid) > 1:
        keyingi = grid[1]
        # Ikkinchi qator ham sarlavhami — MA'LUMOT katagi bormi degan
        # savol bilan aniqlanadi.
        #
        # Ilgari shart "hech qanday RAQAM bo'lmasin" edi va u juda
        # qattiq: sarlavhaning o'zida raqam bo'ladi — "м3/ч", "кВт".
        # Natijada ikki qatorli sarlavha deyarli hech qachon
        # birlashmasdi va "Мощность, кВт" ustuni tanilmay qolardi
        # (`ВКРВ-5` jadvalida aynan shunday edi).
        #
        # Endi faqat SOF SON katagi ("5,5", "1000") ma'lumot belgisi
        # hisoblanadi — birlik yozuvi esa sarlavha bo'lib qolaveradi.
        sonli = sum(1 for k in keyingi if _sof_sonmi(k))
        if sonli == 0 and any(k.strip() for k in keyingi):
            sarlavha = [
                f"{bosh} {past}".strip() if past and past != bosh else bosh
                for bosh, past in zip(sarlavha, keyingi)
            ]
            ishlatilgan = 2
    return sarlavha, ishlatilgan


def jadvaldan_parametrlar(
    grid: list[list[str]],
    tanish_modellar: Iterable[str] | None = None,
    manba: str = "",
) -> list[ModelParametri]:
    """Bitta jadvaldan model parametrlarini chiqaradi."""
    if len(grid) < 2:
        return []

    sarlavha, sarlavha_qatori = _sarlavha_qatorlari(grid)
    turlari = [ustun_turi(nom) for nom in sarlavha]
    if "havo" not in turlari and "bosim" not in turlari:
        return []

    model_ustunlari = _model_ustunlari(sarlavha) or [0]
    # Har model ustunidan keyingi model ustunigacha — bitta "blok".
    # (КЦКП jadvalida "Модель | Производительность" juftligi ikki marta
    # takrorlanadi — shu sababli blok tushunchasi kerak.)
    bloklar: list[tuple[int, int]] = []
    for tartib, boshi in enumerate(model_ustunlari):
        oxiri = (
            model_ustunlari[tartib + 1]
            if tartib + 1 < len(model_ustunlari)
            else len(sarlavha)
        )
        bloklar.append((boshi, oxiri))

    tanish = {_kalit(x) for x in (tanish_modellar or ())} or None
    # TAKROR QATOR TASHLANMAYDI.
    #
    # Ilgari bir xil nomli ikkinchi qator e'tiborsiz qolardi. Jadvalda
    # esa bitta model nomi quvvat/aylanish bo'yicha bir necha marta
    # uchraydi (`ВКРВ-5` — 8 qator, 5000-11150 dan 7500-24500 gacha).
    # Natijada BIRINCHI qator butun oilaga tarqalib, kuchli variantlar
    # quvvati kam ko'rsatilardi.
    natija: list[ModelParametri] = []

    for qator in grid[sarlavha_qatori:]:
        for boshi, oxiri in bloklar:
            if boshi >= len(qator):
                continue
            nomi = (qator[boshi] or "").strip()
            if not _model_nomiga_oxshaydimi(nomi):
                continue
            # `tanish_modellar` — IXTIYORIY qo'shimcha filtr. Odatda
            # bo'sh qoldiriladi: jadvaldagi nom katalog nomidan qisqaroq
            # bo'ladi ("ВЦ 14-46-2" ↔ "ВЦ 14-46-2,0-1"), shuning uchun
            # solishtirish `moslashtir()` da, kengroq qoida bilan bo'ladi.
            if tanish is not None and _kalit(nomi) not in tanish:
                continue

            olingan: dict[str, tuple[float, float]] = {}
            for ustun in range(boshi, min(oxiri, len(qator))):
                turi = turlari[ustun] if ustun < len(turlari) else None
                if turi is None or turi in olingan:
                    continue
                oraliq = son_oraligi(qator[ustun])
                if oraliq is None:
                    continue
                koef = _koeffitsiyent(sarlavha[ustun])
                olingan[turi] = (oraliq[0] * koef, oraliq[1] * koef)

            havo = olingan.get("havo")
            bosim = olingan.get("bosim")
            quvvat = olingan.get("quvvat")
            if havo and not (HAVO_ENG_KAM <= havo[1] <= HAVO_ENG_KOP):
                havo = None
            if bosim and not (0 < bosim[1] <= BOSIM_ENG_KOP):
                bosim = None
            if not havo and not bosim:
                continue

            natija.append(
                ModelParametri(
                    model=nomi,
                    havo_min=havo[0] if havo else None,
                    havo_maks=havo[1] if havo else None,
                    bosim_min=bosim[0] if bosim else None,
                    bosim_maks=bosim[1] if bosim else None,
                    quvvat_kvt=quvvat[1] if quvvat else None,
                    manba=manba,
                )
            )
    return natija


def hujjatdan_parametrlar(
    hujjat: Any,
    tanish_modellar: Iterable[str] | None = None,
    manba: str = "",
) -> list[ModelParametri]:
    """R2 hujjatidagi BARCHA jadvallardan parametr yig'adi."""
    natija: list[ModelParametri] = []
    for grid in jadval_gridlari(hujjat):
        natija.extend(jadvaldan_parametrlar(grid, tanish_modellar, manba))
    return natija


# --- jadval nomini katalog nomiga bog'lash ------------------------------------
#
# Jadvalda o'lcham yoziladi ("ВЦ 14-46-2"), katalogda esa to'liq model
# ("ВЦ 14-46-2,0-1", "ВЦ 14-46-2,0-2", ...). Ya'ni bitta jadval qatori
# bir nechta katalog modeliga tegishli — bu to'g'ri: bir o'lchamdagi
# g'ildirakning havo sarfi bir xil.
#
# XAVF: "ВЦ 14-46-2" ni "ВЦ 14-46-2,5-1" ga ham bog'lab yuborish. Bu
# BOSHQA o'lcham. Shuning uchun ",0" olib tashlanadi, qolgan vergul esa
# nuqtaga aylanadi va moslik faqat AJRATGICH chegarasida tan olinadi:
#   "ВЦ14-46-2" + "-"  -> mos      ("ВЦ14-46-2-1")
#   "ВЦ14-46-2" + "."  -> mos emas ("ВЦ14-46-2.5-1")

BOSH_NOL = re.compile(r",0(?![0-9])")
CHEGARA = "-/ "

# Artikul nomidagi QUVVAT: oxirgi ajratgichdan oldingi son.
#
#   ВКРВ-5-1-18,5/1450   -> 18.5 kVt (1450 — aylanish)
#   ВЦ 4-75-2,5-1-0,37/1500 -> 0.37 kVt
#
# Aylanish har doim oxirida va butun son (900..3000), quvvat esa undan
# oldin. Shu tartib butun katalogda barqaror.
QUVVAT_NAQSHI = re.compile(r"(\d+(?:[.,]\d+)?)\s*/\s*\d{3,4}\s*$")


def _nomdan_quvvat(nom: str) -> float | None:
    """Artikul nomidan dvigatel quvvatini (kVt) ajratadi."""
    mos = QUVVAT_NAQSHI.search(str(nom or "").strip())
    if not mos:
        return None
    try:
        return float(mos.group(1).replace(",", "."))
    except ValueError:
        return None


def nomlash(nom: Any) -> str:
    """Model nomini solishtirish uchun bir ko'rinishga keltiradi."""
    matn = str(nom or "").upper().replace("\xa0", " ")
    matn = BOSH_NOL.sub("", matn)
    return matn.replace(",", ".").replace(" ", "")


def moslashtir(
    parametrlar: Iterable[ModelParametri],
    katalog_nomlari: Iterable[str],
) -> dict[str, ModelParametri]:
    """Jadvaldan o'qilgan parametrlarni KATALOG model nomlariga bog'laydi.

    Natija: `{katalog model nomi: ModelParametri}`. Katalogda yo'q nom
    tashlab yuboriladi — o'ylab topilgan model KP ga tushmasligi uchun.
    """
    royxat = list(parametrlar)
    if not royxat:
        return {}

    # Bir model nomiga bir NECHTA qator to'g'ri kelishi mumkin (quvvat va
    # aylanish bo'yicha variantlar). Shuning uchun guruhlab saqlaymiz.
    guruhlar: dict[str, list[ModelParametri]] = {}
    for p in royxat:
        guruhlar.setdefault(_kalit(p.model), []).append(p)

    def qamrov(qatorlar: list[ModelParametri]) -> ModelParametri:
        natija = qatorlar[0]
        for keyingi in qatorlar[1:]:
            natija = natija.birlashtir(keyingi)
        return natija

    # Prefiks moslik — uzunroq nom oldin tekshiriladi, aks holda
    # qisqa nom ("В-2") uzunini o'g'irlab ketadi.
    prefikslar = sorted(
        ((nomlash(kalit_nomi[0].model), kalit) for kalit, kalit_nomi in guruhlar.items()),
        key=lambda juft: -len(juft[0]),
    )

    natija: dict[str, ModelParametri] = {}
    for katalog_nomi in katalog_nomlari:
        nom = str(katalog_nomi or "")
        if not nom.strip():
            continue

        kalit = _kalit(nom) if _kalit(nom) in guruhlar else None
        if kalit is None:
            tayyor = nomlash(nom)
            for prefiks, nomzod in prefikslar:
                if not prefiks or not tayyor.startswith(prefiks):
                    continue
                qolgan = tayyor[len(prefiks):]
                if qolgan == "" or qolgan[0] in CHEGARA:
                    kalit = nomzod
                    break
        if kalit is None:
            continue

        qatorlar = guruhlar[kalit]
        # ARTIKUL o'z qatorini oladi.
        #
        # `ВКРВ-5-1-18,5/1450` — 18,5 kVt. Jadvalda `ВКРВ-5` sakkiz marta
        # uchraydi va 18,5 kVt qatori 7500-17000 beradi, birinchi qator
        # esa 5000-11150. Ilgari har doim birinchisi olinardi va kuchli
        # variant quvvati kam ko'rsatilardi — Rustam uni "yetmaydi" deb
        # rad etishi mumkin edi.
        #
        # Nomida quvvat bo'lmasa yoki mos qator topilmasa — butun oila
        # QAMROVI beriladi (eng pastdan eng yuqorigacha).
        tanlangan = None
        if len(qatorlar) > 1:
            quvvat = _nomdan_quvvat(nom)
            if quvvat is not None:
                mos = [q for q in qatorlar if q.quvvat_kvt is not None
                       and abs(q.quvvat_kvt - quvvat) < 0.05]
                if mos:
                    tanlangan = qamrov(mos)
        natija[nom] = tanlangan or qamrov(qatorlar)
    return natija


# --- yordamchilar -------------------------------------------------------------

# DIQQAT: VERGUL VA NUQTA OLIB TASHLANMAYDI.
#
# Jonli xato (2026-08-11): ilgari `[\s\-/_.,]` ning hammasi o'chirilardi.
# Natijada KASR AJRATGICHI ham yo'qolib, ikki BOSHQA model bir xil kalit
# olardi:
#
#     КЦКП-3,15  ->  "КЦКП315"
#     КЦКП-31,5  ->  "КЦКП315"      <- bir xil!
#
# Shu sababli 3 150 m³/soat lik qurilmaga 31 500 m³/soat biriktirilgan
# edi — o'n barobar xato. Xuddi shunday: 1,6 va 16;  6,3 va 63;
# 12,5 va 125.
#
# Endi vergul nuqtaga aylanadi va SAQLANADI. Shakl ajratgichlari
# (bo'sh joy, "-", "/", "_") esa olib tashlanaveradi — "ПВН 500-300/2"
# va "ПВН 500-300-2" baribir mos tushadi.
AJRATGICH = re.compile(r"[\s\-/_]")


def _kalit(nom: Any) -> str:
    return AJRATGICH.sub("", str(nom or "").replace(",", ".")).upper()


HARF = re.compile(r"[A-Za-zА-Яа-яЁё]")
RAQAM = re.compile(r"\d")


def _model_nomiga_oxshaydimi(nomi: str) -> bool:
    """Katak matni model kodimi yoki oddiy so'zmi.

    Model kodida deyarli har doim harf ham, raqam ham bo'ladi
    ("ВК-250П", "КСК 113-2-01"). "Модель", "Итого", "1" — emas.
    """
    matn = (nomi or "").strip()
    if not (2 <= len(matn) <= 48):
        return False
    if MODEL_MOS.search(matn):
        return False
    return bool(HARF.search(matn) and RAQAM.search(matn))

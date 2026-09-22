"""Menejer qo'lda aytgan narxni so'rov matnidan ajratish.

NEGA KERAK. Katalogda 1482 modeldan 24 tasida narx bor. Menejer narxni
buxgalteriyadan bilib oladi va KP tuzayotganda shunday yozadi:

    "n1 tovarga 5mln, nomer 2 ga 3mln so'm qilib ber"

Ilgari bu ishlamasdi: narx faqat bazadan olinardi, menejerning gapi
e'tiborga olinmasdi va KP narxsiz chiqib ketaverardi.

NEGA MODEL EMAS, KOD. Tizimning asosiy qoidasi kuchda qoladi: model
narx yozmaydi (uning javobidagi narx maydoni e'tiborga olinmaydi).
Bu yerdagi narx MODELDAN emas, FOYDALANUVCHI matnidan regex bilan
ajratiladi — ya'ni raqam o'ylab topilmaydi, u menejer yozgan
raqamning aynan o'zi.

Ikki xil murojaat tushuniladi:
  - TARTIB bo'yicha:  "1-tovar 5 mln", "n2 ga 3mln", "birinchisi 5 mln"
  - NOM bo'yicha:     "ВК-315С 5 mln"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "5mln", "5 mln", "5 млн", "5m"
KATTALIK = {
    "mln": 1_000_000, "млн": 1_000_000, "m": 1_000_000, "million": 1_000_000,
    "ming": 1_000, "тыс": 1_000, "k": 1_000,
}

# So'z bilan aytilgan tartib.
SOZ_TARTIB = {
    "birinchi": 1, "birinchisi": 1, "birinchisiga": 1, "первый": 1, "первому": 1,
    "ikkinchi": 2, "ikkinchisi": 2, "ikkinchisiga": 2, "второй": 2, "второму": 2,
    "uchinchi": 3, "uchinchisi": 3, "uchinchisiga": 3, "третий": 3,
    "to'rtinchi": 4, "tortinchi": 4, "четвертый": 4,
    "beshinchi": 5, "пятый": 5,
}

# Summa: "5 000 000", "5000000", "5mln", "5,5 mln"
SUMMA = re.compile(
    r"(\d[\d\s  ']*(?:[.,]\d+)?)\s*(mln|млн|million|ming|тыс|k|m)?\b",
    re.IGNORECASE,
)

# Tartib raqami. Ikki shakl:
#   BELGILANGAN: "n1", "№2", "nomer 2", "2-tovar" — aniq ko'rsatma
#   so'z bilan:  "birinchisiga", "ikkinchisi"
#
# Belgisiz yolg'iz raqamni tartib deb OLMAYMIZ: "5 metr" ham raqam.
TARTIB = re.compile(
    r"(?:(?:^|[\s,;])(?:n|№|#|nomer|номер|poz|позиция)\s*(\d{1,2}))"
    r"|(?:(?:^|[\s,;])(\d{1,2})\s*(?:[-)\.]\s*)?"
    r"(?:tovar|tovarga|mahsulot|pozitsiya|позиц|товар))",
    re.IGNORECASE,
)

# Narx haqida gap ketayotganini bildiruvchi so'zlar. Busiz
# "balandligi 5 metr" ham narx deb o'qilardi.
NARX_SOZI = re.compile(
    r"narx|so'm|so‘m|som\b|sum\b|сум|mln|млн|ming\b|тыс|pul|цена|стоимост",
    re.IGNORECASE,
)

# Narx sifatida qabul qilinadigan eng kichik qiymat. Undan pastini
# o'lcham yoki miqdor deb hisoblaymiz ("5 metr", "2 dona").
ENG_KICHIK = 1000

BOLAK_AJRATGICH = re.compile(r"[,;\n]|\bva\b|\bи\b", re.IGNORECASE)

# Model kodi: harflar + raqam (ВК-315С, ПВН 500-300-2).
KOD = re.compile(r"\b([A-Za-zЀ-ӿ]{2,}[\s\-]?[\dA-Za-zЀ-ӿ,\-/]{2,})\b")


@dataclass
class QolNarxlari:
    """Menejer aytgan narxlar."""

    tartib_boyicha: dict[int, float] = field(default_factory=dict)
    nom_boyicha: dict[str, float] = field(default_factory=dict)

    @property
    def bormi(self) -> bool:
        return bool(self.tartib_boyicha or self.nom_boyicha)


def _summani_oqi(matn: str) -> float | None:
    mos = SUMMA.search(matn)
    if not mos:
        return None
    xom = re.sub(r"[\s  ']", "", mos.group(1)).replace(",", ".")
    try:
        qiymat = float(xom)
    except ValueError:
        return None
    qiymat *= KATTALIK.get((mos.group(2) or "").lower(), 1)
    return qiymat if qiymat >= ENG_KICHIK else None


def _tartib_raqami(mos: re.Match) -> int:
    return int(mos.group(1) or mos.group(2))


def _soz_tartibi(bolak: str) -> int | None:
    past = bolak.lower()
    for soz, raqam in SOZ_TARTIB.items():
        if soz in past:
            return raqam
    return None


def _nomni_oqi(bolak: str) -> str:
    """Bo'lakdagi mahsulot kodi (topilmasa bo'sh)."""
    tozalangan = SUMMA.sub(" ", bolak)
    for mos in KOD.finditer(tozalangan):
        nomzod = mos.group(1).strip()
        if any(ch.isdigit() for ch in nomzod) and not NARX_SOZI.search(nomzod):
            return nomzod
    return ""


def narx_ajrat(matn: str) -> QolNarxlari:
    """So'rov matnidan menejer aytgan narxlarni ajratadi.

    Narx belgisi (so'm, mln, "narx") bo'lmagan matnni umuman ko'rmaymiz —
    aks holda "balandligi 5 metr" narx bo'lib qolardi.
    """
    natija = QolNarxlari()
    if not matn or not NARX_SOZI.search(matn):
        return natija

    # 1) BELGILANGAN tartib: har ko'rsatkichdan keyingi summani olamiz.
    #    "n1 tovarga 5mln nomer 2 ga 3mln" — vergulsiz ham ishlaydi.
    moslar = list(TARTIB.finditer(matn))
    for i, mos in enumerate(moslar):
        oxiri = moslar[i + 1].start() if i + 1 < len(moslar) else len(matn)
        summa = _summani_oqi(matn[mos.end():oxiri])
        if summa is not None:
            natija.tartib_boyicha[_tartib_raqami(mos)] = summa

    # 2) SO'Z bilan aytilgan tartib va NOM bo'yicha — bo'laklab.
    for bolak in BOLAK_AJRATGICH.split(matn):
        if not NARX_SOZI.search(bolak) or TARTIB.search(bolak):
            continue
        summa = _summani_oqi(bolak)
        if summa is None:
            continue

        tartib = _soz_tartibi(bolak)
        if tartib:
            natija.tartib_boyicha.setdefault(tartib, summa)
            continue

        nom = _nomni_oqi(bolak)
        if nom:
            natija.nom_boyicha[nom] = summa

    return natija

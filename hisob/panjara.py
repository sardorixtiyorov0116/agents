"""Panjara tanlash — nechta va qaysi o'lchamda.

NEGA KODDA: bu raqam mijozga ketadigan KP ga tushadi. Model hisoblasa,
natija chaqiruvdan chaqiruvga o'zgarib turardi.

FORMULA
-------
    F = L / (3600 x v)        kerakli JONLI KESIM yuzasi, m²
    n = ceil(F / f)           panjara soni

`L` — havo sarfi (m³/soat), `v` — panjaradagi tezlik (m/s),
`f` — bitta panjaraning jonli kesim yuzasi (katalog jadvalidan).

JONLI KESIM — panjaraning umumiy o'lchami EMAS. 300x300 panjaraning
gabariti 0,09 m², jonli kesimi esa atigi 0,033 m² (РВН) — jalyuzi
yuzaning uchdan ikkisini yopadi. Gabarit bo'yicha hisoblansa panjara
uch barobar kam chiqadi va tizim shovqin qiladi.

TANLASH QOIDASI: eng katta o'lchamdan boshlab, soni KAMIDA IKKITA
bo'ladigan birinchisi olinadi. Bitta katta panjara havoni xona bo'ylab
taqsimlamaydi — u faqat bir nuqtaga puflaydi.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import sozlama

PANJARA_FAYLI = "panjara.yaml"

# Fayl topilmasa hisob umuman qilinmaydi — TAXMIN QILINMAYDI.
# Jonli kesim yuzasi katalogdan olinadigan qiymat, o'ylab topilmaydi.
_BOSH: dict[str, Any] = {"tezlik": {"standart": 2.0}, "turlar": {}}

# Bittalik panjara havoni taqsimlamaydi — shuning uchun kamida shuncha.
ENG_KAM_SONI = 2
# Bundan ko'p bo'lsa ro'yxat ma'nosiz uzayadi (montaj ham qimmatlashadi).
ENG_KOP_SONI = 40


@dataclass
class PanjaraHisobi:
    """Panjara tanlovi natijasi."""

    turi: str                    # РВН / РВИ
    olcham: str                  # "600х400"
    soni: int
    bitta_yuza: float            # m² — jonli kesim
    kerakli_yuza: float          # m² — jami
    tezlik: float                # m/s — hisobda ishlatilgan
    haqiqiy_tezlik: float        # m/s — tanlangan panjara bilan
    ogohlantirishlar: list[str] = field(default_factory=list)

    @property
    def nomi(self) -> str:
        """Katalogdagi to'liq nom: `РВН 600х400`."""
        return f"{self.turi} {self.olcham}"


@lru_cache
def panjaralar() -> dict[str, Any]:
    """Panjara jadvali. Fayl bo'lmasa BO'SH — taxmin qilinmaydi."""
    yol = Path(sozlama().bilim_papkasi) / "product" / PANJARA_FAYLI
    if not yol.is_file():
        return dict(_BOSH)
    try:
        xom = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return dict(_BOSH)
    return xom if isinstance(xom, dict) and xom.get("turlar") else dict(_BOSH)


def _tezlik() -> float:
    xom = panjaralar().get("tezlik") or {}
    qiymat = xom.get("standart")
    return float(qiymat) if isinstance(qiymat, (int, float)) else 2.0


def _olchamlar(turi: str) -> list[tuple[float, str]]:
    """`[(jonli_kesim_m2, "600х400"), ...]` — kattadan kichikka."""
    yozuv = (panjaralar().get("turlar") or {}).get(turi) or {}
    jadval = yozuv.get("yuza") or {}
    natija: list[tuple[float, str]] = []
    for balandlik, qatorlar in jadval.items():
        if not isinstance(qatorlar, dict):
            continue
        for uzunlik, yuza in qatorlar.items():
            if isinstance(yuza, (int, float)) and yuza > 0:
                # Katalog nomi kirill "х" bilan yoziladi (`РВН 600х400`),
                # lotin "x" bilan emas — backend nomiga aynan mos tushsin.
                natija.append((float(yuza), f"{balandlik}х{uzunlik}"))
    natija.sort(key=lambda x: -x[0])
    return natija


def panjara_tanla(
    sarf: float, turi: str = "РВН", tezlik: float | None = None
) -> PanjaraHisobi | None:
    """Havo sarfiga mos panjara o'lchami va soni.

    Jadval yo'q bo'lsa yoki sarf nol bo'lsa `None` — bu yerda taxmin
    qilinmaydi, chaqiruvchi buni ochiq aytishi kerak.
    """
    if sarf <= 0:
        return None
    olchamlar = _olchamlar(turi)
    if not olchamlar:
        return None

    v = float(tezlik) if tezlik else _tezlik()
    kerakli = sarf / (3600 * v)
    ogohlantirishlar: list[str] = []

    # Kattadan kichikka: soni KAMIDA IKKITA bo'ladigan birinchisi.
    tanlangan: tuple[float, str] | None = None
    soni = 0
    for yuza, olcham in olchamlar:
        n = math.ceil(kerakli / yuza)
        if n >= ENG_KAM_SONI:
            tanlangan, soni = (yuza, olcham), n
            break

    if tanlangan is None:
        # Hatto eng kichigi ham bittada yetadi — kichik xona.
        tanlangan = olchamlar[-1]
        soni = max(1, math.ceil(kerakli / tanlangan[0]))

    if soni > ENG_KOP_SONI:
        ogohlantirishlar.append(
            f"{soni} ta panjara kerak — bu juda ko'p, havo taqsimlash "
            "sxemasini loyihachi ko'rib chiqsin"
        )

    yuza, olcham = tanlangan
    haqiqiy = sarf / (3600 * yuza * soni)
    return PanjaraHisobi(
        turi=turi,
        olcham=olcham,
        soni=soni,
        bitta_yuza=yuza,
        kerakli_yuza=round(kerakli, 4),
        tezlik=v,
        haqiqiy_tezlik=round(haqiqiy, 2),
        ogohlantirishlar=ogohlantirishlar,
    )

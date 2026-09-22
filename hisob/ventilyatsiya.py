"""Ventilyatsiya hisobi — havo sarfi va kanal o'lchami.

NEGA KODDA: bu raqamlar mijozga ketadigan taklifga asos bo'ladi. Model
hisoblasa, natija chaqiruvdan chaqiruvga o'zgarib turardi va tekshirib
bo'lmasdi. Shuning uchun formulalar shu yerda, testlar bilan qoplangan.

MANBA HAQIDA OCHIQ: havo almashinuvi normalari `knowledge/product/
havo_almashinuvi.yaml` da turadi va ular UMUMIY AMALIYOT qiymatlari —
loyiha uchun kompaniyaning o'z normativ bazasi bilan solishtirilishi
kerak. Buni har hisobda foydalanuvchiga aytamiz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import sozlama

# Ishlab chiqariladigan standart dumaloq kanal diametrlari (mm).
KANAL_DIAMETRLARI = (
    100, 125, 160, 200, 250, 315, 355, 400, 450, 500,
    560, 630, 710, 800, 900, 1000,
)

# Tavsiya etiladigan havo tezligi (m/s). Yuqori tezlik — shovqin va
# bosim yo'qotishi; past tezlik — katta va qimmat kanal.
TAVSIYA_TEZLIK = {
    "magistral": (5.0, 8.0),   # asosiy kanal
    "tarmoq": (3.0, 5.0),      # tarmoqlanish
    "panjara": (1.5, 3.0),     # havo taqsimlagich
}

NORMA_FAYLI = "havo_almashinuvi.yaml"

# Fayl topilmasa ishlatiladigan minimal to'plam. Ataylab KICHIK: to'liq
# ro'yxat tahrirlanadigan faylda bo'lishi kerak.
ZAXIRA_NORMALAR: dict[str, dict[str, Any]] = {
    "ofis": {"karrali": 3.0, "odam_boshiga": 60, "izoh": "ofis xonalari"},
    "majlis": {"karrali": 6.0, "odam_boshiga": 60, "izoh": "majlis xonasi"},
    "ombor": {"karrali": 2.0, "izoh": "ombor"},
    "ishlab_chiqarish": {"karrali": 4.0, "izoh": "ishlab chiqarish sexi"},
    "oshxona": {"karrali": 15.0, "izoh": "umumiy ovqatlanish oshxonasi"},
    "sanuzel": {"karrali": 10.0, "izoh": "sanitariya tugunlari"},
    "dokon": {"karrali": 3.0, "odam_boshiga": 60, "izoh": "savdo zali"},
    "avtoturargoh": {"karrali": 6.0, "izoh": "yopiq avtoturargoh"},
}


@lru_cache
def normalar() -> dict[str, dict[str, Any]]:
    """Xona turi -> normalar. Fayl bo'lmasa zaxira ro'yxat."""
    yol = Path(sozlama().bilim_papkasi) / "product" / NORMA_FAYLI
    if not yol.is_file():
        return dict(ZAXIRA_NORMALAR)
    try:
        xom = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return dict(ZAXIRA_NORMALAR)
    turlar = xom.get("turlar") if isinstance(xom, dict) else None
    return turlar if isinstance(turlar, dict) and turlar else dict(ZAXIRA_NORMALAR)


@dataclass
class Xona:
    """Hisob uchun kirish ma'lumoti."""

    turi: str = "ofis"
    maydon: float = 0.0        # m²
    balandlik: float = 3.0     # m
    odamlar: int = 0
    nomi: str = ""

    @property
    def hajm(self) -> float:
        return round(self.maydon * self.balandlik, 2)


@dataclass
class HavoHisobi:
    """Havo sarfi natijasi — qaysi usul qanday natija bergani bilan."""

    xona: Xona
    hajm: float
    karrali_boyicha: float | None      # n × V
    odam_boyicha: float | None         # N × q
    sarf: float                        # yakuniy (eng kattasi)
    tanlangan_usul: str
    norma_izohi: str = ""
    ogohlantirishlar: list[str] = field(default_factory=list)


@dataclass
class KanalHisobi:
    """Kanal o'lchami natijasi."""

    sarf: float                 # m³/soat
    kerakli_yuza: float         # m²
    hisobiy_diametr: float      # mm (yumaloqlanmagan)
    diametr: int                # mm (standart, yuqoriga yumaloqlangan)
    haqiqiy_tezlik: float       # m/s (standart diametr bilan)
    tezlik_oraligi: tuple[float, float]
    turi: str
    ogohlantirishlar: list[str] = field(default_factory=list)


def havo_sarfi(xona: Xona) -> HavoHisobi:
    """Xona uchun kerakli havo sarfi (m³/soat).

    Ikki usul hisoblanadi va ENG KATTASI olinadi — ikkalasi ham
    bajarilishi kerak bo'lgan talab, tanlov emas:
      1) havo almashinuvi karraligi:  L = n × V
      2) odam boshiga norma:          L = N × q
    """
    ogohlantirishlar: list[str] = []
    tur = (xona.turi or "").strip().lower().replace(" ", "_")
    norma = normalar().get(tur)
    if norma is None:
        norma = normalar().get("ofis") or ZAXIRA_NORMALAR["ofis"]
        ogohlantirishlar.append(
            f"'{xona.turi}' turi normalar ro'yxatida yo'q — ofis normasi "
            "ishlatildi, tekshirilsin"
        )

    hajm = xona.hajm
    if hajm <= 0:
        ogohlantirishlar.append("maydon yoki balandlik berilmagan")
        return HavoHisobi(
            xona=xona, hajm=0, karrali_boyicha=None, odam_boyicha=None,
            sarf=0, tanlangan_usul="hisoblanmadi",
            norma_izohi=str(norma.get("izoh") or ""),
            ogohlantirishlar=ogohlantirishlar,
        )

    karrali = norma.get("karrali")
    l_karrali = round(float(karrali) * hajm, 1) if karrali else None

    odam_normasi = norma.get("odam_boshiga")
    l_odam = (
        round(float(odam_normasi) * xona.odamlar, 1)
        if odam_normasi and xona.odamlar > 0
        else None
    )
    if odam_normasi and xona.odamlar <= 0:
        ogohlantirishlar.append(
            "odam soni aytilmagan — faqat karralik bo'yicha hisoblandi"
        )

    nomzodlar = [(l, nom) for l, nom in
                 ((l_karrali, "karralik"), (l_odam, "odam boshiga")) if l]
    if not nomzodlar:
        ogohlantirishlar.append("normada hisob uchun ma'lumot yetarli emas")
        sarf, usul = 0.0, "hisoblanmadi"
    else:
        sarf, usul = max(nomzodlar, key=lambda x: x[0])

    return HavoHisobi(
        xona=xona,
        hajm=hajm,
        karrali_boyicha=l_karrali,
        odam_boyicha=l_odam,
        sarf=sarf,
        tanlangan_usul=usul,
        norma_izohi=str(norma.get("izoh") or ""),
        ogohlantirishlar=ogohlantirishlar,
    )


def kanal_olchami(sarf: float, turi: str = "magistral") -> KanalHisobi:
    """Havo sarfiga mos dumaloq kanal diametri.

    F = L / (3600 × v)  — kesim yuzasi
    D = sqrt(4F / π)    — diametr

    Tezlik oralig'ining O'RTASI olinadi, keyin standart diametrga
    YUQORIGA yumaloqlanadi (kichraytirilsa tezlik oshib, shovqin
    paydo bo'ladi).
    """
    ogohlantirishlar: list[str] = []
    oraliq = TAVSIYA_TEZLIK.get(turi)
    if oraliq is None:
        oraliq = TAVSIYA_TEZLIK["magistral"]
        ogohlantirishlar.append(f"'{turi}' turi noma'lum — magistral olindi")

    if sarf <= 0:
        return KanalHisobi(
            sarf=0, kerakli_yuza=0, hisobiy_diametr=0, diametr=0,
            haqiqiy_tezlik=0, tezlik_oraligi=oraliq, turi=turi,
            ogohlantirishlar=[*ogohlantirishlar, "havo sarfi nol"],
        )

    tezlik = sum(oraliq) / 2
    yuza = sarf / (3600 * tezlik)                 # m²
    diametr_mm = math.sqrt(4 * yuza / math.pi) * 1000

    standart = next(
        (d for d in KANAL_DIAMETRLARI if d >= diametr_mm),
        KANAL_DIAMETRLARI[-1],
    )
    if diametr_mm > KANAL_DIAMETRLARI[-1]:
        ogohlantirishlar.append(
            f"hisobiy diametr {diametr_mm:.0f} mm — standart qatordan katta, "
            "bir necha kanalga bo'lish yoki to'g'ri burchakli kanal kerak"
        )

    haqiqiy_yuza = math.pi * (standart / 1000) ** 2 / 4
    haqiqiy_tezlik = sarf / (3600 * haqiqiy_yuza)
    if haqiqiy_tezlik > oraliq[1]:
        ogohlantirishlar.append(
            f"tezlik {haqiqiy_tezlik:.1f} m/s — tavsiya chegarasidan "
            f"({oraliq[1]} m/s) yuqori, shovqin bo'lishi mumkin"
        )

    return KanalHisobi(
        sarf=sarf,
        kerakli_yuza=round(yuza, 4),
        hisobiy_diametr=round(diametr_mm, 1),
        diametr=standart,
        haqiqiy_tezlik=round(haqiqiy_tezlik, 2),
        tezlik_oraligi=oraliq,
        turi=turi,
        ogohlantirishlar=ogohlantirishlar,
    )

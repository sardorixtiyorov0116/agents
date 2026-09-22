"""Muhandislik hisob-kitoblari.

Bu paket LLM'ga TEGISHLI EMAS: barcha formulalar sof Python'da bajariladi
va testlar bilan qoplangan. Model faqat foydalanuvchi so'rovidan
parametrlarni ajratib beradi (maydon, balandlik, odam soni), hisobni esa
kod qiladi — shuning uchun raqamni "to'qib" bo'lmaydi.
"""

from .bosim import (
    BosimHisobi,
    bosim_yoqotishi,
    tipik_bosim,
    yetadimi,
)
from .markaziy import (
    MarkaziyTanlov,
    markaziy_tanla,
)
from .panjara import (
    PanjaraHisobi,
    panjara_tanla,
    panjaralar,
)
from .shovqin import (
    ShovqinOlchami,
    olchamdan_sigim,
    shovqin_tanla,
)
from .ventilyatsiya import (
    KANAL_DIAMETRLARI,
    TAVSIYA_TEZLIK,
    HavoHisobi,
    KanalHisobi,
    Xona,
    havo_sarfi,
    kanal_olchami,
    normalar,
)

__all__ = [
    "BosimHisobi",
    "bosim_yoqotishi",
    "tipik_bosim",
    "yetadimi",
    "MarkaziyTanlov",
    "markaziy_tanla",
    "PanjaraHisobi",
    "panjara_tanla",
    "panjaralar",
    "ShovqinOlchami",
    "olchamdan_sigim",
    "shovqin_tanla",
    "KANAL_DIAMETRLARI",
    "TAVSIYA_TEZLIK",
    "HavoHisobi",
    "KanalHisobi",
    "Xona",
    "havo_sarfi",
    "kanal_olchami",
    "normalar",
]

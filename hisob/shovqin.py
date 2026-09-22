"""Shovqin pasaytirgich tanlash — KESIM O'LCHAMI bo'yicha.

NEGA ALOHIDA HISOB
------------------
Shovqin pasaytirgichda `havo_sarfi` maydoni YO'Q — katalog u haqda
sarf emas, SHOVQIN PASAYISHINI (dB, chastota bo'yicha) beradi. Shu
sababli u sarf bo'yicha tanlanadigan uskunalar qatoriga tushmasdi va
menejer «tanladim, lekin KP ga chiqmadi» degan holatga tushardi.

Lekin sig'imi MODEL NOMIDA turadi. Bosma katalog 2021, 82-sahifa:

    «КГП 40-20/6, где 40-20 — присоединительные размеры фланца, см;
     6 — длина шумопоглощающего участка, *100 мм»

Ya'ni `КГП 50-30` = 500x300 mm kanalga ulanadi. Kesim ma'lum bo'lsa,
sig'im ham ma'lum: L = F x 3600 x v.

Dumaloq `КГТ 160-6` da esa 160 — DIAMETR (mm).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Kanaldagi tavsiya etilgan tezlik o'rtasi (m/s). Shovqin pasaytirgich
# kanalning O'ZIDA turadi, shuning uchun tezlik ham o'sha —
# `TAVSIYA_TEZLIK["magistral"]` (5-8 m/s) ning o'rtasi.
KANAL_TEZLIGI = 6.5

# `КГП 100-50 (6-10)` -> 100 va 50 (SANTIMETR).
_PLASTINALI = re.compile(r"^\s*КГП\s+(\d+)\s*[-x×хX]\s*(\d+)", re.I)
# `КГТ 160-6` -> 160 (MILLIMETR, dumaloq kanal diametri).
_DUMALOQ = re.compile(r"^\s*КГТ\s+(\d+)\s*[-/]", re.I)


@dataclass(frozen=True)
class ShovqinOlchami:
    nomi: str
    yuza: float          # m² — ulanish kesimi
    sigim: float         # m³/soat — shu kesimdan o'tadigan havo


def olchamdan_sigim(nom: str) -> ShovqinOlchami | None:
    """Model NOMIDAN kesim yuzasi va sig'imini hisoblaydi.

    Nom tanish shaklda bo'lmasa `None` — TAXMIN QILINMAYDI.
    """
    plastinali = _PLASTINALI.match(nom or "")
    if plastinali:
        # Santimetrdan metrga: 100 sm -> 1,0 m.
        en = int(plastinali.group(1)) / 100
        boy = int(plastinali.group(2)) / 100
        yuza = en * boy
    else:
        dumaloq = _DUMALOQ.match(nom or "")
        if not dumaloq:
            return None
        # Millimetrdan metrga.
        diametr = int(dumaloq.group(1)) / 1000
        yuza = math.pi * diametr ** 2 / 4

    if yuza <= 0:
        return None
    return ShovqinOlchami(
        nomi=nom,
        yuza=round(yuza, 4),
        sigim=round(yuza * 3600 * KANAL_TEZLIGI, 1),
    )


def shovqin_tanla(
    nomlar: list[str], sarf: float
) -> tuple[ShovqinOlchami, int] | None:
    """Sarfga yetadigan shovqin pasaytirgich va NECHTA kerakligi.

    Bittasi yetsa — `(o'lcham, 1)`. Kattasi olinsa kanal kengaytirilishi
    kerak bo'ladi va ortiqcha pul ketadi; kichigi olinsa tezlik oshib,
    shovqinning O'ZI ko'payadi — ya'ni uskuna o'z vazifasiga qarshi
    ishlaydi.

    BITTASI YETMASA — eng kattasidan PARALLEL. 18 000 m³/soat ga eng
    katta `КГП 100-50` (11 700) bo'lsa, 2 dona qo'yiladi. Katta tizim
    baribir bir necha tarmoqqa bo'linadi.
    """
    if sarf <= 0:
        return None
    olchamlar = [o for o in (olchamdan_sigim(n) for n in nomlar) if o]
    if not olchamlar:
        return None

    yetadigan = [o for o in olchamlar if o.sigim >= sarf]
    if yetadigan:
        return min(yetadigan, key=lambda o: o.sigim), 1

    eng_katta = max(olchamlar, key=lambda o: o.sigim)
    return eng_katta, math.ceil(sarf / eng_katta.sigim)

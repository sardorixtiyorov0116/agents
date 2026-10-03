"""Konditsioner so'rovnoma varaqasi (ОЛ, «Опросный лист на подбор блоков
системы кондиционирования») — PDF dan VRF bloklari.

NEGA KERAK
----------
Yirik loyihada zayavka faqat «К5. Система VRF кондиционирования — 1 к-т»
deydi; qaysi bloklar kerakligi esa ilovadagi ОЛ da: har xona uchun blok
turi va sovutish quvvati, har qavat uchun tashqi blok quvvati (5-juft,
2026-10-03). Menejer shu jadvaldan JVI/JVO bloklarini tanlaydi.

Bu modul ОЛ ni TZ qatorlariga (`TzQator`) aylantiradi: bir qavatdagi bir
xil blok (turi + kVt) bitta qatorga yig'iladi — menejer KP sida ham shunday
(«JVI-071C × 5»). Nom keyin `kp/tz_qoralama.py` da JVI kodiga aylanadi.

Qavat — `bolim` («1 этаж»). Qaysi qavat qaysi tizim (К5, К6) ekani
ОЛ da yozilmagan, shuning uchun tizim belgisi qo'yilmaydi.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

from .tz_jadval import TzQator

_QAVAT = re.compile(r"^\s*(\d+)\s*этаж", re.I | re.M)
_TASHQI = re.compile(r"Наружный\s+блок\s+([^\n\d]*?)\s*([\d]+(?:[.,]\d+)?)\s+R\d", re.I)
# «5 пом.108 Настенный - 3,6 R410A» — tur ikki qatorga bo'linishi mumkin
# («Кассетный \nоднопоточный \n- 5,6»).
_ICHKI = re.compile(
    r"^\s*\d+\s+пом\.?\s*[\d,\s]+?\s+([А-Яа-яЁё\-\s]+?)\s+-\s+(\d+(?:[.,]\d+)?)\s+R\d",
    re.M)


def ol_oqi(yol: str | Path) -> list[TzQator] | None:
    """ОЛ PDF -> TZ qatorlari. ОЛ bo'lmasa `None`."""
    from pypdf import PdfReader

    matn = "\n".join(b.extract_text() or "" for b in PdfReader(str(yol)).pages)
    if not re.search(r"Опросный\s+лист", matn, re.I) or "Холодопр" not in matn:
        return None

    # Qavatlar bo'yicha bo'laklar.
    chegaralar = [(m.start(), f"{m.group(1)} этаж") for m in _QAVAT.finditer(matn)]
    if not chegaralar:
        chegaralar = [(0, "")]
    natija: list[TzQator] = []
    for i, (bosh, qavat) in enumerate(chegaralar):
        oxir = chegaralar[i + 1][0] if i + 1 < len(chegaralar) else len(matn)
        bolak = matn[bosh:oxir]
        yigilgan: OrderedDict[tuple[str, str], int] = OrderedDict()
        for m in _TASHQI.finditer(bolak):
            tur = re.sub(r"\s+", " ", m.group(1)).strip()
            nomi = f"Наружный блок {tur} {m.group(2)} кВт".replace("  ", " ")
            yigilgan[(nomi, "")] = yigilgan.get((nomi, ""), 0) + 1
        for m in _ICHKI.finditer(bolak):
            tur = re.sub(r"\s+", " ", m.group(1)).strip()
            nomi = f"Внутренний блок, {tur} {m.group(2)} кВт"
            yigilgan[(nomi, "")] = yigilgan.get((nomi, ""), 0) + 1
        for (nomi, _), soni in yigilgan.items():
            natija.append(TzQator(
                nomi=nomi, miqdor=float(soni), birlik="шт", bolim=qavat,
                guruh=qavat, matn=nomi, varaq=Path(yol).name))
    return natija or None

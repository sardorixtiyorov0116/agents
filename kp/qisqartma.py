"""Loyiha qisqartmalarini katalog nomiga aylantiradi.

NEGA KERAK
----------
Loyihachi KP so'raganda o'z qisqartmalarini yozadi:

    Решетка АДН:
    Решетка 300х150 — 57 dona
    Решетка 200х150 — 31 dona

Katalogda esa bu «Решетка вентиляционная регулируемая РВР-2 300х150мм
без КРВ». Tarjimani hozirgacha menejer boshida qilardi.

JONLI XATO (2026-08-28): shunday ro'yxat botga berilganda KP ga
«Клап 1000х400» deb tushdi — bunday nom katalogda yo'q, 44 qatorning
hammasi narxsiz chiqdi. Menejer esa o'sha ro'yxatdan to'liq narxlangan
KP-13357 ni tuzgan edi.

Moslik jadvali `knowledge/product/loyiha_qisqartmalari.yaml` da —
yangi qisqartma uchrasa kodga tegilmaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import sozlama

# «300x150», «300х150», «Д125» — o'lchamni ajratib olish.
_OLCHAM = re.compile(r"(\d+)\s*[xх×*]\s*(\d+)(?:\s*[xх×*]\s*(\d+))?", re.I)
_DIAMETR = re.compile(r"[ДдDd]\s*(\d{2,4})")

# Katalogda KIRILLCHA «х» ishlatiladi — lotincha «x» bilan qidirsak
# hech nima topilmaydi.
AJRATGICH = "х"


@dataclass(frozen=True)
class Qisqartma:
    belgilar: tuple[str, ...]
    nomi: str
    qolip: str
    izoh: str = ""
    ogohlantirish: str = ""
    eng_kichik: str = ""
    diametr: bool = False


@lru_cache
def qisqartmalar() -> tuple[Qisqartma, ...]:
    yol = Path(sozlama().bilim_yoli) / "product" / "loyiha_qisqartmalari.yaml"
    if not yol.exists():
        return ()
    xom = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    natija = []
    for q in xom.get("qisqartmalar") or []:
        natija.append(Qisqartma(
            belgilar=tuple(str(b).lower() for b in q.get("belgilar") or []),
            nomi=str(q.get("nomi") or ""),
            qolip=str(q.get("qolip") or ""),
            izoh=str(q.get("izoh") or ""),
            ogohlantirish=str(q.get("ogohlantirish") or ""),
            eng_kichik=str(q.get("eng_kichik") or ""),
            diametr=bool(q.get("diametr")),
        ))
    return tuple(natija)


def topilsin(sarlavha: str) -> Qisqartma | None:
    """Sarlavha matnidan qisqartmani topadi.

    ENG UZUN mos kelgani tanlanadi: «решетка апн» ham, «апн» ham
    ro'yxatda bor va qisqasi birinchi tushib qolmasligi kerak.
    """
    past = (sarlavha or "").lower().strip(" :—–-")
    nomzod: tuple[int, Qisqartma] | None = None
    for q in qisqartmalar():
        for belgi in q.belgilar:
            if belgi in past and (nomzod is None or len(belgi) > nomzod[0]):
                nomzod = (len(belgi), q)
    return nomzod[1] if nomzod else None


def olcham_ajrat(matn: str, diametr: bool = False) -> str:
    """Qatordan o'lchamni ajratadi. Topilmasa bo'sh satr."""
    if diametr:
        mos = _DIAMETR.search(matn or "")
        return mos.group(1) if mos else ""
    mos = _OLCHAM.search(matn or "")
    if not mos:
        return ""
    bolaklar = [b for b in mos.groups() if b]
    return AJRATGICH.join(bolaklar)


def _kichikmi(olcham: str, eng_kichik: str) -> bool:
    """O'lcham eng kichigidan kichikmi? Ikkala tomon ham AxB."""
    def sonlar(s: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", s)]

    a, b = sonlar(olcham), sonlar(eng_kichik)
    if len(a) < 2 or len(b) < 2:
        return False
    return a[0] < b[0] or a[1] < b[1]


@dataclass
class Natija:
    nomi: str
    ogohlantirishlar: list[str] = field(default_factory=list)


def qollash(sarlavha: str, qator: str) -> Natija | None:
    """Sarlavha + qatordan katalog nomini yasaydi.

    Sarlavha tanilmasa yoki o'lcham topilmasa `None` — qator
    O'ZGARISHSIZ qoladi. Taxminiy nom yasashdan ko'ra asl matnni
    qoldirgan yaxshi: menejer nimani tuzatish kerakligini ko'radi.
    """
    q = topilsin(sarlavha)
    if q is None or not q.qolip:
        return None
    olcham = olcham_ajrat(qator, q.diametr)
    if not olcham:
        return None

    ogohlantirishlar: list[str] = []
    if q.eng_kichik and _kichikmi(olcham, q.eng_kichik):
        # JIMGINA almashtirmaymiz: loyihada 150х150 tuynuk bo'lsa,
        # 300х300 panjara u yerga sig'maydi.
        ogohlantirishlar.append(
            f"«{q.nomi}» {olcham} so'ralgan, lekin eng kichik o'lcham "
            f"{q.eng_kichik} — {q.eng_kichik} ga o'zgartirildi, "
            "loyihadagi tuynuk o'lchamini tekshiring")
        olcham = q.eng_kichik
    if q.ogohlantirish:
        ogohlantirishlar.append(q.ogohlantirish)

    return Natija(nomi=q.qolip.format(olcham=olcham),
                  ogohlantirishlar=ogohlantirishlar)

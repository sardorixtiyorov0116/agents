"""КЦКП (markaziy konditsioner) — KP qoralamasi uchun o'lcham va tavsif.

NEGA KERAK
----------
Ilgari TZ dagi КЦКП qatori («Кондиционеры компактные панельные»,
VENTAS «AHU-01») KP ga TZ nomi bilan tushardi va menejer o'lchamni
qo'lda tanlardi. O'lcham esa faqat SARFDAN chiqadi: menejer KP larida
qoida bitta (tests/etalon_tz, 2026-10-05 o'lchovi):

  1100 -> 1,6   2600 -> 3,15   3000 -> 3,15   4500 -> 5   6000 -> 6,3
  8000 -> 8     9000 -> 10     10250 -> 10    17500 -> 20  22500 -> 25
  28000 -> 31,5   31750 -> 31,5   33000 -> 31,5

ya'ni nominal sarfdan 5% gacha oshsa ham o'sha o'lcham olinadi.
O'lchamlar qatori va foiz — `tz_analoglar.yaml` (`kckp`) da.

SEKSIYALAR TARKIBI (batareya modeli, ventilyator, avtomatika) bu yerda
YASALMAYDI: u zavod tanlov dasturidan keladi. Tavsifga faqat TZ da
RAQAM bilan berilgani yoziladi — sarf, bosim, quvvat, filtr klassi.
"""

from __future__ import annotations

from typing import Any

from .ventas import Qurilma


def _son(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def olcham_tanla(sarf: float, qoida: dict[str, Any]) -> str | None:
    """Sarf (m³/soat) -> «3,15». Eng kattasidan ham oshsa `None` (tanlov)."""
    if not sarf or sarf <= 0:
        return None
    ortiq = 1 + float(qoida.get("ortiq_foizi") or 0) / 100
    for olcham in sorted(float(o) for o in qoida.get("olchamlar") or []):
        if sarf <= olcham * 1000 * ortiq:
            return _son(olcham)
    return None


def nomi(olcham: str, qoida: dict[str, Any]) -> str:
    return str(qoida.get("qolip") or "Кондиционер КЦКП-{olcham}").format(olcham=olcham)


def sarf_matni(sarf: float, bosim: float | None = None) -> str:
    """«L=3000м3/ч, Р=500Па» — menejer KP laridagi yozuv."""
    return f"L={_son(sarf)}м3/ч" + (f", Р={_son(bosim)}Па" if bosim else "")


_REKUPERATOR = {"PHE": "Рекуператор пластинчатый", "RAC": "Рекуператор гликолевый"}
_FILTR_NOMI = {"elektrostatik": "электростатический", "ko'mir": "угольный"}


def ventas_tavsifi(q: Qurilma) -> str:
    """VENTAS tanlovidan qisqa tavsif — har band alohida qatorda."""
    if q.qaytish_sarf:
        qatorlar = [f"Приток {sarf_matni(q.sarf, q.bosim)}",
                    f"Вытяжка {sarf_matni(q.qaytish_sarf, q.qaytish_bosim)}"]
    else:
        qatorlar = [sarf_matni(q.sarf, q.bosim)]
    qatorlar += [v for k, v in _REKUPERATOR.items() if k in q.kodlar]
    if {"DCM", "TCM"} & set(q.kodlar):
        qatorlar.append("Камера смешения")
    if q.isitish and "HWC" in q.kodlar:
        qatorlar.append(f"Нагрев Qт={_son(q.isitish)}кВт")
    if q.sovutish and "CWC" in q.kodlar:
        qatorlar.append(f"Охлаждение Qх={_son(q.sovutish)}кВт")
    if q.filtrlar:
        filtrlar = dict.fromkeys(_FILTR_NOMI.get(f, f) for f in q.filtrlar)
        qatorlar.append("Фильтры: " + ", ".join(filtrlar))
    return "\n".join(qatorlar)

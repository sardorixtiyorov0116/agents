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

import re
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


_REKUPERATOR = {"PHE": "пластинчатый", "RAC": "гликолевый"}
_FILTR_NOMI = {"elektrostatik": "электростатический", "ko'mir": "угольный"}
_FILTR_KLASSI = re.compile(r"\b([GFMEH])\s?(\d{1,2})\b")

# Menejer KP sidagi tartib (KP 13603, 13574): sarf/bosim, tizim turi,
# seksiyalar, oxirida loyihadagi belgisi. Faqat TZ dagi RAQAM yoziladi —
# «Сторона обслуживания», ventilyator modeli, avtomatika TZ da yo'q,
# ularni menejer zavod tanlovidan qo'shadi.


def _tizim_turi(belgi: str, qaytish: bool) -> str:
    if qaytish:
        return "приточно-вытяжная"
    if re.match(r"\s*(П|ПВ|AHU)", belgi or "", re.I):
        return "приточная"
    if re.match(r"\s*В", belgi or ""):
        return "вытяжная"
    return ""


def tz_tavsifi(sarf_q: float, parametrlar: dict[str, float],
               guruh_matni: dict[str, str], belgi: str) -> str:
    """Excel TZ («Характеристика систем») qatoridan КЦКП tavsifi."""
    qatorlar = [sarf_matni(sarf_q, parametrlar.get("P"))]
    turi = _tizim_turi(belgi, False)
    if turi:
        qatorlar.append(f"Тип системы: {turi}")
    filtr = _FILTR_KLASSI.findall(guruh_matni.get("filtr", ""))
    if filtr:
        qatorlar.append("Секция фильтров: " + ", ".join(dict.fromkeys(a + b for a, b in filtr)))
    isitgich = guruh_matni.get("isitgich", "")
    if isitgich or "Qt" in parametrlar:
        turi = ("электрический" if re.search(r"электр|эл\.", isitgich, re.I)
                else "водяной" if re.search(r"вод", isitgich, re.I) else "")
        bolaklar = [turi] if turi else []
        if "tn" in parametrlar and "tk" in parametrlar:
            bolaklar.append(f"tвн={_son(parametrlar['tn'])}°С, "
                            f"tвк={'+' if parametrlar['tk'] > 0 else ''}{_son(parametrlar['tk'])}°С")
        if "Qt" in parametrlar:
            bolaklar.append(f"Qт={_son(parametrlar['Qt'])}кВт")
        qatorlar.append("Секция нагрева: " + ", ".join(bolaklar))
    if belgi:
        qatorlar.append(f"Система в проекте: {belgi}")
    return "\n".join(qatorlar)


def ventas_tavsifi(q: Qurilma) -> str:
    """VENTAS tanlovidan tavsif — har band alohida qatorda."""
    if q.qaytish_sarf:
        qatorlar = [f"Приток {sarf_matni(q.sarf, q.bosim)}",
                    f"Вытяжка {sarf_matni(q.qaytish_sarf, q.qaytish_bosim)}"]
    else:
        qatorlar = [sarf_matni(q.sarf, q.bosim)]
    qatorlar.append(f"Тип системы: {_tizim_turi(q.nomi, bool(q.qaytish_sarf))}")
    qatorlar += [f"Секция рекуператора: {v}" for k, v in _REKUPERATOR.items() if k in q.kodlar]
    if {"DCM", "TCM"} & set(q.kodlar):
        qatorlar.append("Камера смешения")
    if q.filtrlar:
        filtrlar = dict.fromkeys(_FILTR_NOMI.get(f, f) for f in q.filtrlar)
        qatorlar.append("Секция фильтров: " + ", ".join(filtrlar))
    if q.isitish and "HWC" in q.kodlar:
        qatorlar.append(f"Секция нагрева: водяной, Qт={_son(q.isitish)}кВт")
    if q.sovutish and "CWC" in q.kodlar:
        qatorlar.append(f"Секция охлаждения: водяной, Qх={_son(q.sovutish)}кВт")
    qatorlar.append(f"Система в проекте: {q.nomi}")
    return "\n".join(qatorlar)

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
_FILTR_KLASSI = re.compile(r"\b([GFMEHU])\s?(\d{1,2})\b")
_FILTR_TARTIBI = {"G": 1, "M": 2, "F": 3, "E": 4, "H": 5, "U": 6}

# Havo: zichlik 1,2 kg/m³, issiqlik sig'imi 1,005 kJ/(kg·K) — loyihachilar
# odatda shu bilan hisoblaydi. Isitgich TZ dagidan 5% dan ko'p kam chiqsa —
# menejerga aytiladi.
ZICHLIK, SIGIM = 1.2, 1.005

# Menejer KP sidagi tartib (KP 13603, 13574): sarf/bosim, tizim turi,
# seksiyalar, oxirida loyihadagi belgisi. Yoziladigani — TZ raqamlari va
# katalogdagi STANDART (filtr bloki, bitta ventilyatorli o'lchamlar).
# «Сторона обслуживания», avtomatika TZ da ham, katalogda ham yo'q —
# ularni menejer qo'shadi.


def _tizim_turi(belgi: str, qaytish: bool) -> str:
    if qaytish:
        return "приточно-вытяжная"
    if re.match(r"\s*RC", belgi or "", re.I):      # VENTAS RC — retsirkulyatsiya sovutgichi
        return "рециркуляционная"
    if re.match(r"\s*(П|ПВ|AHU)", belgi or "", re.I):
        return "приточная"
    if re.match(r"\s*В", belgi or ""):
        return "вытяжная"
    return ""


def _filtr_ball(klass: str) -> tuple[int, int]:
    m = re.match(r"([A-Z])(\d+)", klass)
    return (_FILTR_TARTIBI.get(m.group(1), 0), int(m.group(2))) if m else (0, 0)


def filtr_seksiyasi(klasslar: list[str], qoida: dict[str, Any], belgi: str,
                    majburiy: bool) -> tuple[str, list[str]]:
    """TZ filtr klasslari -> («ФяГ G4, ФяК F7», menejerga eslatmalar).

    Katalog: КЦКП filtr bloki — ФЯГ G4 (hamma o'lchamda), cho'ntakli ФЯК
    F5–F9; F9 dan yuqori КЦКП ichida bo'lmaydi. TZ da G3 bo'lsa ham G4
    (yaxshiroq, standart). Kirish havosi bor tizimda filtr TZ da yozilmagan
    bo'lsa ham standart qo'yiladi (`majburiy`): ko'chadan filtrlanmagan havo
    batareyani ifloslantiradi.
    """
    standart = str(qoida.get("filtr_standart") or "ФяГ G4")
    kotarma = str(qoida.get("filtr_kotarma") or "ФяК")
    maks = _filtr_ball(str(qoida.get("filtr_maks") or "F9"))
    bolaklar: list[str] = []
    eslatmalar: list[str] = []
    for k in sorted(dict.fromkeys(klasslar), key=_filtr_ball):
        ball = _filtr_ball(k)
        if ball <= _filtr_ball("G4"):
            if standart not in bolaklar:
                bolaklar.append(standart)
            if k != standart.split()[-1]:
                eslatmalar.append(f"{belgi}: TZ da filtr {k} — КЦКП standarti {standart} qo'yildi "
                                  "(katalogda КЦКП filtr bloki G4)")
        elif ball <= maks:
            bolaklar.append(f"{kotarma} {k}")
        else:
            eslatmalar.append(
                f"{belgi}: TZ da {k} (HEPA) — КЦКП ichida F9 gacha (katalog). Alohida HEPA "
                "blokini taklif qiling, aks holda mijoz talabi bajarilmaydi")
    if not bolaklar and majburiy:
        bolaklar.append(standart)
    return ", ".join(bolaklar), eslatmalar


def isitish_tekshir(sarf_q: float, tn: float, tk: float, qt: float,
                    belgi: str) -> str | None:
    """TZ dagi isitgich quvvati shu sarfni tn -> tk isitishga yetadimi."""
    kerak = sarf_q / 3600 * ZICHLIK * SIGIM * (tk - tn)
    if kerak <= 0 or qt >= 0.95 * kerak:
        return None
    haqiqiy = tn + qt / (sarf_q / 3600 * ZICHLIK * SIGIM)
    return (f"{belgi}: {sarf_q:g} m³/soat ni {tn:g} dan {tk:+g} °C gacha isitishga "
            f"≈{_son(round(kerak, 1))} kVt kerak, TZ da {_son(qt)} kVt — havo faqat "
            f"≈{haqiqiy:+.0f} °C "
            "gacha isiydi. Mijoz bilan aniqlang (TZ dagi quvvat KP ga yozildi)")


def ventilyator_seksiyasi(olcham: str, bosim: float | None, qoida: dict[str, Any]) -> str:
    """Katalogda bitta ebmpapst modeli bo'lgan o'lcham va bosim EC ventilyatorga mos bo'lsa."""
    model = (qoida.get("ventilyator") or {}).get(olcham)
    chegara = float(qoida.get("ec_maks_bosim") or 0)
    if not model or (bosim and chegara and bosim > chegara):
        return ""
    return f"Секция вентилятора: ebmpapst {model}"


def tz_tavsifi(sarf_q: float, parametrlar: dict[str, float], guruh_matni: dict[str, str],
               belgi: str, olcham: str, qoida: dict[str, Any]) -> tuple[str, list[str]]:
    """Excel TZ («Характеристика систем») qatoridan КЦКП tavsifi va eslatmalar."""
    eslatmalar: list[str] = []
    qatorlar = [sarf_matni(sarf_q, parametrlar.get("P"))]
    turi = _tizim_turi(belgi, False)
    if turi:
        qatorlar.append(f"Тип системы: {turi}")
    klasslar = [a + b for a, b in _FILTR_KLASSI.findall(guruh_matni.get("filtr", ""))]
    filtr, e = filtr_seksiyasi(klasslar, qoida, belgi or "КЦКП", turi.startswith("приточ"))
    eslatmalar += e
    if filtr:
        qatorlar.append(f"Секция фильтров: {filtr}")
    isitgich = guruh_matni.get("isitgich", "")
    if isitgich or "Qt" in parametrlar:
        tur = ("электрический" if re.search(r"электр|эл\.", isitgich, re.I)
               else "водяной" if re.search(r"вод", isitgich, re.I) else "")
        bolaklar = [tur] if tur else []
        if "tn" in parametrlar and "tk" in parametrlar:
            bolaklar.append(f"tвн={_son(parametrlar['tn'])}°С, "
                            f"tвк={'+' if parametrlar['tk'] > 0 else ''}{_son(parametrlar['tk'])}°С")
        if "Qt" in parametrlar:
            bolaklar.append(f"Qт={_son(parametrlar['Qt'])}кВт")
            if "tn" in parametrlar and "tk" in parametrlar:
                e = isitish_tekshir(sarf_q, parametrlar["tn"], parametrlar["tk"],
                                    parametrlar["Qt"], belgi or "КЦКП")
                if e:
                    eslatmalar.append(e)
        qatorlar.append("Секция нагрева: " + ", ".join(bolaklar))
    ventilyator = ventilyator_seksiyasi(olcham, parametrlar.get("P"), qoida)
    if ventilyator:
        qatorlar.append(ventilyator)
    if belgi:
        qatorlar.append(f"Система в проекте: {belgi}")
    return "\n".join(qatorlar), eslatmalar


def ventas_tavsifi(q: Qurilma, olcham: str, qoida: dict[str, Any]) -> tuple[str, list[str]]:
    """VENTAS tanlovidan tavsif — har band alohida qatorda — va eslatmalar."""
    eslatmalar: list[str] = []
    if q.qaytish_sarf:
        qatorlar = [f"Приток {sarf_matni(q.sarf, q.bosim)}",
                    f"Вытяжка {sarf_matni(q.qaytish_sarf, q.qaytish_bosim)}"]
    else:
        qatorlar = [sarf_matni(q.sarf, q.bosim)]
    qatorlar.append(f"Тип системы: {_tizim_turi(q.nomi, bool(q.qaytish_sarf))}")
    qatorlar += [f"Секция рекуператора: {v}" for k, v in _REKUPERATOR.items() if k in q.kodlar]
    if {"DCM", "TCM"} & set(q.kodlar):
        qatorlar.append("Камера смешения")
    klasslar = [f for f in q.filtrlar if _FILTR_KLASSI.fullmatch(f)]
    filtr, e = filtr_seksiyasi(klasslar, qoida, q.nomi, bool(q.filtrlar))
    eslatmalar += e
    boshqa = [_FILTR_NOMI.get(f, f) for f in q.filtrlar if f not in klasslar]
    filtr = ", ".join(x for x in [filtr] + list(dict.fromkeys(boshqa)) if x)
    if filtr:
        qatorlar.append(f"Секция фильтров: {filtr}")
    if q.isitish and "HWC" in q.kodlar:
        qatorlar.append(f"Секция нагрева: водяной, Qт={_son(q.isitish)}кВт")
    if q.sovutish and "CWC" in q.kodlar:
        qatorlar.append(f"Секция охлаждения: водяной, Qх={_son(q.sovutish)}кВт")
    # Kirish + chiqish — ikkita ventilyator, ularni zavod tanlaydi.
    ventilyator = "" if q.qaytish_sarf else ventilyator_seksiyasi(olcham, q.bosim, qoida)
    if ventilyator:
        qatorlar.append(ventilyator)
    qatorlar.append(f"Система в проекте: {q.nomi}")
    return "\n".join(qatorlar), eslatmalar

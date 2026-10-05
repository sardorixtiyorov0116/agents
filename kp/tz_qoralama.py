"""Excel TZ -> KP qoralamasi (mahsulotlar ro'yxati).

NEGA KERAK
----------
`/kp` ga Excel TZ tashlansa, ilgari u MATNGA aylantirilib modelga berilardi
(`kp/tz.py`): model faqat 20 ta nom olardi, hammasiga miqdor 1 qo'yardi va
raqib nomini (КЛОП-1, 4АПР, KV315M) Climavent nomiga aylantirmasdi.

Endi Excel modelsiz o'qiladi (`kp/tz_jadval.py` — miqdori bilan), har
qator esa Climavent nomiga aylantiriladi:

  1. bo'lim sarlavhasi tanilsa — `kp/qisqartma.py` («Решетка АДН» ostidagi
     «Решетка 300x150» -> «РВР-2 300х150мм без КРВ»);
  2. qator nomi tanilsa — `knowledge/product/tz_analoglar.yaml` qolipi
     («КЛОП-1 … FD 125x100» -> «КПУ-НО-Н-EI60-125х100-…»);
  3. КЦКП — o'lchami sarfdan (`kp/kckp.py`: 3000 -> КЦКП-3,15);
  4. muhandis TANLOVI kerak bo'lsa (VRF, radial ventilyator, sarfsiz
     КЦКП) — qator TZ nomi bilan qoladi va parametrlari bilan belgilanadi;
  5. tanilmasa — TZ nomi bilan qoladi va belgilanadi.

KP DA NOM QISQA: menejer KP larida qatorda faqat Climavent nomi turadi,
qurilmada esa loyihadagi pozitsiyasi — «Вентилятор канальный ВК-315С
(В1)». TZ dagi asl nom hujjatga YOZILMAYDI (`asl_nomi` — faqat menejer
uchun). Pozitsiya faqat qurilmalarga qo'yiladi: panjara va klapanlarda
«В1» tizim nomi, menejer uni yozmaydi.

HECH NARSA JIMGINA QO'YILMAYDI: TZ da EI yozilmagan bo'lsa standart
olinadi va bu aytiladi; o'lcham kattalashtirilsa — aytiladi. Qoralama —
menejer uchun, mijoz uchun emas.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .solishtir import diametr, kvt, olcham, sarf, tz_oilasi
from .tz_jadval import TzQator

# Qator turlari — menejerga hisobot uchun.
QISQARTMA = "qisqartma"
ANALOG = "analog"
TANLOV = "tanlov"
TANILMADI = "tanilmadi"

# Nomga loyiha pozitsiyasi («(В1)», «(П1)») qo'shiladigan oilalar —
# o'z belgisi bor QURILMALAR. Panjara/klapandagi «В1» — tizim nomi.
# КЦКП ga qo'yilmaydi: menejer «Кондиционер КЦКП-3,15» deb yozadi, belgisi
# tavsif oxirida («Система в проекте: П1»).
POZITSIYALI = {"vent_kanal", "vent_sanoat", "vent_maishiy", "rekuperator"}

# «EI60», «EI 90», tutun klapanida «E90» / kirillcha «Е90».
_EI = re.compile(r"\b[EЕ][IІ]?\s?-?(\d{2,3})\b", re.I)
_UCH_OLCHAM = re.compile(r"(\d{2,4})\s*[xхХ×*]\s*(\d{2,4})\s*[xхХ×*]\s*(\d{3,4})")
_MODEL_RAQAMI = re.compile(r"(?:KV|ВК|ПРО|MF)[\s-]*(\d{3})", re.I)
# Sanoat ventilyatori nomeri: «ВРАН6 080» -> 8, «ОСА 201 080» -> 8 (080 = №8,0).
_NOMER = re.compile(r"(?:ВРАН\d*|ОСА\s*\d+)\s+(\d{3})\b", re.I)
_DU = re.compile(r"ДУ\s*-?\s*(\d{3})\b")


def _jadval_yoli() -> Path:
    try:
        from app.config import sozlama

        return Path(sozlama().bilim_yoli) / "product" / "tz_analoglar.yaml"
    except Exception:   # noqa: BLE001 — sozlamasiz (skript) ishlaganda ham
        return Path(__file__).resolve().parent.parent / "knowledge" / "product" / "tz_analoglar.yaml"


@lru_cache
def jadval() -> dict[str, Any]:
    return yaml.safe_load(_jadval_yoli().read_text(encoding="utf-8")) or {}


@dataclass
class Qoralama:
    mahsulotlar: list[dict[str, Any]] = field(default_factory=list)
    turlar: Counter = field(default_factory=Counter)
    # Butun qoralama uchun bitta marta aytiladigan gaplar («74 ta klapanda
    # EI yo'q») — har qatorda takrorlansa menejer o'qimay qo'yadi.
    umumiy: list[str] = field(default_factory=list)

    @property
    def tayyor_foizi(self) -> float:
        jami = sum(self.turlar.values())
        return 100.0 * (self.turlar[QISQARTMA] + self.turlar[ANALOG]) / jami if jami else 0.0


def _kichikmi(a: str, b: str) -> bool:
    x = [int(s) for s in re.findall(r"\d+", a)]
    y = [int(s) for s in re.findall(r"\d+", b)]
    return len(x) >= 2 and len(y) >= 2 and (x[0] < y[0] or x[1] < y[1])


def _parametrlar_matni(q: TzQator) -> str:
    nomlar = {"L": "m³/soat", "P": "Pa", "N": "kVt"}
    qismlar = [f"{q.parametrlar[k]:g} {nomlar[k]}" for k in ("L", "P", "N") if k in q.parametrlar]
    return ", ".join(qismlar)


def _standart(qiymat: float, olchamlar: list[float]) -> float | None:
    """Eng kichik standart o'lcham, TZ quvvatidan 5% gacha kam bo'lishi mumkin."""
    mos = [o for o in sorted(olchamlar) if o >= 0.95 * qiymat]
    return mos[0] if mos else None


def _konditsioner(q: TzQator, oila_kod: str, qoida: dict[str, Any],
                  yozuv: dict[str, Any]) -> list[dict[str, Any]] | None:
    """VRF ichki blok / split: quvvatdan model. Bo'lmasa `None` (tanlov)."""
    matn = f"{q.nomi} {q.matn}"
    quvvat = kvt(matn)
    if not quvvat:
        return None
    standart = _standart(quvvat, qoida.get("olchamlar") or [])
    if standart is None and oila_kod == "split":
        return _katta_split(q, quvvat, qoida, yozuv)
    if standart is None:
        return None
    if oila_kod == "split":
        nomi = qoida["qolip"].format(kvt=f"{standart:g}".replace(".", ","))
        yozuv["nomi"] = nomi
        return [yozuv]
    tur = next((t for t in qoida.get("turlar") or [] if re.search(t["agar"], matn, re.I)), None)
    if tur is None:
        return None
    yozuv["nomi"] = tur["qolip"].format(kod=f"{round(standart * 10):03d}")
    if abs(standart - quvvat) > 0.01:
        yozuv["ogohlantirishlar"].append(
            f"«{q.nomi[:50]}»: TZ da {quvvat:g} kVt — standart {standart:g} kVt olindi")
    qatorlar = [yozuv]
    if tur.get("panel") and qoida.get("panel"):
        qatorlar.append({
            "nomi": qoida["panel"], "miqdor": q.miqdor, "birlik": "шт",
            "bolim": yozuv["bolim"], "asl_nomi": "",
            "ogohlantirishlar": [],
        })
    return qatorlar


def _katta_split(q: TzQator, quvvat: float, qoida: dict[str, Any],
                 yozuv: dict[str, Any]) -> list[dict[str, Any]] | None:
    """7 kVt dan katta split -> mini-VRF to'plami (fankoyl + tashqi + panel + pult)."""
    toplam = _katta_toplam(quvvat, qoida)
    if toplam is None:
        return None
    qatorlar = [{**yozuv, "nomi": nomi, "ogohlantirishlar": []} for nomi in toplam["qatorlar"]]
    qatorlar[0]["ogohlantirishlar"] = [
        f"«{q.nomi[:50]}»: {quvvat:g} kVt split — mini-VRF to'plami "
        f"({toplam['kvt']:g} kVt), tasdiqlang"]
    return qatorlar


def _katta_toplam(quvvat: float, qoida: dict[str, Any]) -> dict[str, Any] | None:
    return next((t for t in sorted(qoida.get("katta") or [], key=lambda t: t["kvt"])
                 if t["kvt"] >= 0.95 * quvvat), None)


def ulanish_boyicha(ichki: float, modullar: list[dict[str, Any]],
                    foiz: tuple[float, float] = (100, 130)) -> str | None:
    """Ichki bloklar yig'indisidan BITTA tashqi modul (ichki/tashqi foiz oralig'ida).

    Bir nechta mos kelsa — nisbati 100% ga eng yaqini (eng katta modul).
    """
    mos = [m for m in modullar if foiz[0] <= 100 * ichki / m["kvt"] <= foiz[1]]
    return max(mos, key=lambda m: m["kvt"])["kod"] if mos else None


def tashqi_kombinatsiyalar(quvvat: float, modullar: list[dict[str, Any]],
                           maks_modul: int = 4, farq_foizi: float = 1.5) -> list[list[str]]:
    """Yig'indisi `quvvat` ga AYNAN teng HAMMA kombinatsiyalar (kam modullisi oldin).

    BITTASINI O'ZIMIZ TANLAMAYMIZ. 128,5 kVt ni 725T + 560T ham, 615T + 335T
    × 2 ham beradi — menejer KP 13173 da ikkinchisini olgan. Qaysi biri
    to'g'riligi (modullar mosligi, zaxira) — muhandis qarori. Shuning uchun
    bitta variant bo'lsa — qo'yiladi, bir nechta bo'lsa — ro'yxat ko'rsatiladi.
    Taxminiy (katta yoki kichik) kombinatsiya qaytarilmaydi.
    """
    from itertools import combinations_with_replacement

    chegara = quvvat * farq_foizi / 100
    natija: list[list[str]] = []
    for soni in range(1, maks_modul + 1):
        for k in combinations_with_replacement(sorted(modullar, key=lambda m: -m["kvt"]), soni):
            if abs(sum(m["kvt"] for m in k) - quvvat) <= chegara:
                natija.append([m["kod"] for m in k])
    return natija


def _kombinatsiya_matni(kodlar: list[str]) -> str:
    return " + ".join(f"{kod} × {kodlar.count(kod)}" if kodlar.count(kod) > 1 else kod
                      for kod in dict.fromkeys(kodlar))


def _kckp(q: TzQator, qoida: dict[str, Any], yozuv: dict[str, Any],
          kckp_olindi: list[str]) -> bool:
    """КЦКП: o'lcham sarfdan, tavsif TZ raqamlaridan. Sarf yo'q — `False`."""
    from .kckp import nomi, olcham_tanla, tz_tavsifi

    sarf_q = q.parametrlar.get("L") or sarf(f"{q.nomi} {q.matn}")
    olcham_q = olcham_tanla(sarf_q or 0, qoida)
    if olcham_q is None:
        return False
    yozuv["nomi"] = nomi(olcham_q, qoida)
    yozuv["tavsif"], eslatmalar = tz_tavsifi(sarf_q, q.parametrlar, q.guruh_matni,
                                            q.tizim, olcham_q, qoida)
    yozuv["ogohlantirishlar"] += eslatmalar
    yozuv["birlik"] = "комп."
    kckp_olindi.append(f"{q.tizim or q.nomi[:20]} {sarf_q:g} -> КЦКП-{olcham_q}")
    return True


def _qator(q: TzQator, ei_yoq: list[str],
           kckp_olindi: list[str] | None = None,
           ichki_yigindi: dict[str, float] | None = None) -> tuple[list[dict[str, Any]], str]:
    from .qisqartma import qollash

    bolim = " · ".join(x for x in (q.tizim, q.guruh.rstrip(":")) if x)
    yozuv: dict[str, Any] = {
        "nomi": q.nomi, "miqdor": q.miqdor, "birlik": q.birlik or "шт",
        "bolim": bolim, "asl_nomi": q.nomi, "ogohlantirishlar": [],
    }

    # 1) Bo'lim sarlavhasi orqali (ro'yxat TZ).
    if q.guruh:
        tarjima = qollash(q.guruh, q.nomi)
        if tarjima is not None:
            yozuv["nomi"] = tarjima.nomi
            yozuv["ogohlantirishlar"] = list(tarjima.ogohlantirishlar)
            return [yozuv], QISQARTMA

    oila = tz_oilasi(q.nomi, q.guruh)
    if oila is None:
        yozuv["ogohlantirishlar"] = [f"«{q.nomi[:60]}» tanilmadi — TZ nomi bilan qoldi"]
        return [yozuv], TANILMADI

    qoida = (jadval().get("analoglar") or {}).get(oila.kod) or {}
    matn = f"{q.nomi} {q.matn}"
    if q.tizim and oila.kod in POZITSIYALI:
        yozuv["pozitsiya"] = q.tizim

    if oila.kod == "kckp" and _kckp(q, qoida, yozuv,
                                    kckp_olindi if kckp_olindi is not None else []):
        return [yozuv], ANALOG

    # 2) Konditsioner: quvvatdan model (VRF ichki blok, split).
    if oila.kod in ("vrf_ichki", "split") and not qoida.get("tanlov"):
        qatorlar = _konditsioner(q, oila.kod, qoida, yozuv)
        if qatorlar is not None:
            return qatorlar, ANALOG

    # 3) VRF tashqi blok: modullar kombinatsiyasi — faqat YAGONA aniq bo'lsa.
    if oila.kod == "vrf_tashqi" and qoida.get("modullar"):
        quvvat = kvt(matn)
        variantlar = tashqi_kombinatsiyalar(
            quvvat, qoida["modullar"], qoida.get("maks_modul", 4),
            qoida.get("farq_foizi", 1.5)) if quvvat else []
        if len(variantlar) == 1:
            kodlar = variantlar[0]
            qatorlar = []
            for kod in dict.fromkeys(kodlar):
                qatorlar.append({
                    **yozuv, "ogohlantirishlar": [],
                    "nomi": qoida["qolip"].format(kod=kod),
                    "miqdor": q.miqdor * kodlar.count(kod),
                })
            qatorlar[0]["ogohlantirishlar"] = [
                f"«{q.nomi[:50]}»: {quvvat:g} kVt = {_kombinatsiya_matni(kodlar)} — "
                "yagona aniq kombinatsiya, tasdiqlang"]
            return qatorlar, ANALOG
        if len(variantlar) > 1:
            yozuv["ogohlantirishlar"] = [
                f"«{q.nomi[:50]}»{' (' + q.tizim + ')' if q.tizim else ''}: {quvvat:g} kVt — "
                f"{len(variantlar)} ta aniq kombinatsiya bor, tanlang: "
                + "; ".join(_kombinatsiya_matni(v) for v in variantlar[:4])]
            return [yozuv], TANLOV
        # Aniq kombinatsiya yo'q — shu tizim ichki bloklari yig'indisidan.
        ichki = (ichki_yigindi or {}).get(q.tizim, 0) / (q.miqdor or 1)
        kod = ulanish_boyicha(ichki, qoida["modullar"],
                              tuple(qoida.get("ulanish_foizi") or (100, 130))) if ichki else None
        if kod:
            modul = next(m for m in qoida["modullar"] if m["kod"] == kod)
            return [{**yozuv, "nomi": qoida["qolip"].format(kod=kod), "ogohlantirishlar": [
                f"«{q.nomi[:50]}»{' (' + q.tizim + ')' if q.tizim else ''}: "
                f"TZ {quvvat or 0:g} kVt — aniq modul yo'q; ichki bloklar {ichki:g} kVt "
                f"-> {kod} ({modul['kvt']:g} kVt, ulanish {100 * ichki / modul['kvt']:.0f}%), "
                "tasdiqlang"]}], ANALOG

    mos_qolip = next(
        (k for k in qoida.get("qoliplar") or []
         if not k.get("agar") or re.search(k["agar"], matn, re.I)), None)
    if (qoida.get("tanlov") or not qoida.get("qoliplar")
            or (mos_qolip is None and qoida.get("faqat_mos"))):
        parametr = _parametrlar_matni(q)
        izoh = qoida.get("izoh") or f"{oila.nomi} — parametr bo'yicha tanlanadi"
        yozuv["ogohlantirishlar"] = [
            f"«{q.nomi[:60]}»{' (' + q.tizim + ')' if q.tizim else ''}: {izoh}"
            + (f" — TZ: {parametr}" if parametr else "")]
        return [yozuv], TANLOV

    qolip_yozuvi = mos_qolip or qoida["qoliplar"][-1]

    # O'rinlarni to'ldirish.
    kv = olcham(q.nomi) or olcham(q.matn)
    d = diametr(q.nomi) or diametr(q.matn)
    d_son = d.lstrip("Ø") if d else ""
    if not d_son:
        m = _MODEL_RAQAMI.search(matn)
        d_son = m.group(1) if m else ""
    qolip = qolip_yozuvi["qolip"]
    if "{olcham}" in qolip and not kv and d_son:
        kv = f"Ф{d_son}"
    m = _NOMER.search(q.nomi)
    nomer = f"{int(m.group(1)) / 10:g}".replace(".", ",") if m else ""
    m = _DU.search(q.nomi)
    du = f"-ДУ-{m.group(1)}" if m else ""
    # `ajrat` — qolipning o'z regexi: TZ dagi nomerni oladi («ВЦ4-75 №2.5» -> 2,5).
    m = re.search(qolip_yozuvi["ajrat"], q.nomi, re.I) if qolip_yozuvi.get("ajrat") else None
    x = m.group(1).replace(".", ",") if m else ""
    if (("{olcham}" in qolip and not kv) or ("{d}" in qolip and not d_son)
            or ("{nomer}" in qolip and not nomer) or ("{x}" in qolip and not x)):
        yozuv["ogohlantirishlar"] = [f"«{q.nomi[:60]}»: o'lcham topilmadi — TZ nomi bilan qoldi"]
        return [yozuv], TANILMADI

    if kv and qoida.get("eng_kichik") and "х" in kv and _kichikmi(kv, qoida["eng_kichik"]):
        yozuv["ogohlantirishlar"].append(
            f"«{q.nomi[:60]}»: {kv} so'ralgan, eng kichik {qoida['eng_kichik']} — "
            "kattalashtirildi, loyihadagi tuynukni tekshiring")
        kv = qoida["eng_kichik"]

    ei = ""
    if "{ei}" in qolip:
        m = _EI.search(matn)
        ei = m.group(1) if m else str(jadval().get("ei_standart") or "60")
        if not m:
            ei_yoq.append(oila.nomi)
        # Katalogdagi bajarilishlar: so'ralganidan kichik bo'lmagan eng yaqini.
        # Katalogda yo'q darajani (КПД EI120) YOZMAYMIZ — eng kattasi va
        # menejerga ogohlantirish: ishlab chiqarilmaydigan klapan KP ga tushmasin.
        qatori = sorted(int(x) for x in qoida.get("ei_qatori") or [])
        if qatori:
            mos = [x for x in qatori if x >= int(ei)]
            if not mos:
                yozuv["ogohlantirishlar"].append(
                    f"«{q.nomi[:50]}»: TZ da {ei} daqiqa so'ralgan, katalogda {oila.nomi} "
                    f"{qatori[-1]} gacha — {qatori[-1]} yozildi, zavoddan so'rang")
            ei = str(mos[0] if mos else qatori[-1])
    uzunlik = ""
    if "{uzunlik}" in qolip:
        m = _UCH_OLCHAM.search(matn)
        uzunlik = m.group(3) if m else str(jadval().get("uzunlik_standart") or "1000")

    yozuv["nomi"] = qolip.format(olcham=kv, d=d_son, ei=ei, uzunlik=uzunlik,
                                 nomer=nomer, du=du, x=x)
    if qolip_yozuvi.get("ogohlantirish"):
        yozuv["ogohlantirishlar"].append(f"«{q.nomi[:50]}»: {qolip_yozuvi['ogohlantirish']}")
    return [yozuv], ANALOG


def qoralama(tz: list[TzQator]) -> Qoralama:
    """TZ qatorlari -> `/kp` «model» yo'li uchun mahsulotlar ro'yxati."""
    natija = Qoralama()
    ei_yoq: list[str] = []
    kckp_olindi: list[str] = []

    # Ventilyatsiyaga aloqasi yo'q varaq (bir faylda eski armatura, quvur
    # zayavkalari ham turadi — 5-juft) qoralamaga tushmaydi.
    tanilgan: Counter = Counter()
    jami: Counter = Counter()
    for q in tz:
        jami[q.varaq] += 1
        if tz_oilasi(q.nomi, q.guruh) is not None:
            tanilgan[q.varaq] += 1
    for varaq in jami:
        if tanilgan[varaq] == 0:
            natija.umumiy.append(
                f"«{varaq}» varag'i ({jami[varaq]} qator) ventilyatsiyaga aloqasiz — olinmadi")

    analoglar = jadval().get("analoglar") or {}
    ichki_yigindi, split_ichki = _vrf_kontekst(tz, analoglar)
    kirmadi: Counter = Counter()
    oxirgi_bolim = ""
    for q in tz:
        if tanilgan[q.varaq] == 0:
            continue
        # Climavent ishlab chiqarmaydigan narsa (maishiy «Compact 20») KP ga
        # tushmaydi — menejer 13603 da shunday: 50 emas, 41 mahsulot.
        oila = tz_oilasi(q.nomi, q.guruh)
        if oila is not None and (analoglar.get(oila.kod) or {}).get("kpga_kirmaydi"):
            kirmadi[q.nomi[:40]] += q.miqdor
            continue
        if id(q) in split_ichki:
            natija.umumiy.append(
                f"«{q.nomi[:50]}» ({q.tizim}) — katta splitning ichki bloki, "
                "mini-VRF to'plamiga kirdi")
            continue
        # SEKSIYA SARLAVHASI qator bo'lib turadi («- 9 СЕКЦИЯ»), menejer KP
        # sidagidek — bir xil ro'yxat 3 seksiyada takrorlanganda qaysi qator
        # qaysi seksiyaniki ekani shundan bilinadi.
        if q.bolim and q.bolim != oxirgi_bolim:
            natija.mahsulotlar.append({
                "nomi": f"- {q.bolim}", "miqdor": 1, "birlik": "шт",
                "sarlavha": True, "ogohlantirishlar": [],
            })
            oxirgi_bolim = q.bolim
        qatorlar, turi = _qator(q, ei_yoq, kckp_olindi, ichki_yigindi)
        natija.mahsulotlar += qatorlar
        natija.turlar[turi] += 1
    if kirmadi:
        natija.umumiy.append(
            "KP ga KIRITILMADI (Climavent ishlab chiqarmaydi): "
            + ", ".join(f"{nom} — {soni:g} dona" for nom, soni in kirmadi.items()))
    if ei_yoq:
        standart = jadval().get("ei_standart") or "60"
        sanoq = Counter(ei_yoq)
        natija.umumiy.append(
            f"Olovbardoshlik (EI) TZ da yozilmagan: "
            + ", ".join(f"{nom} — {soni} qator" for nom, soni in sanoq.items())
            + f". EI{standart} qo'yildi — loyiha talabini tekshiring")
    if kckp_olindi:
        natija.umumiy.append(_kckp_eslatma(kckp_olindi))
    return natija


def _vrf_kontekst(tz: list[TzQator], analoglar: dict[str, Any]
                 ) -> tuple[dict[str, float], set[int]]:
    """Tizim bo'yicha VRF ichki bloklar yig'indisi (kVt) va katta splitning
    ichki qismi bo'lgan qatorlar (KP 13321 K6: «Сплит 14,07» + «Вн.блок 14,07»
    — bitta qurilma, menejer bir marta yozgan)."""
    katta: dict[str, list[float]] = {}
    split_q = analoglar.get("split") or {}
    eng_katta = max(split_q.get("olchamlar") or [0])
    for q in tz:
        oila = tz_oilasi(q.nomi, q.guruh)
        if oila is not None and oila.kod == "split":
            quvvat = kvt(f"{q.nomi} {q.matn}")
            if quvvat and quvvat > eng_katta and _katta_toplam(quvvat, split_q):
                katta.setdefault(q.tizim, []).append(quvvat)
    yigindi: dict[str, float] = {}
    split_ichki: set[int] = set()
    for q in tz:
        oila = tz_oilasi(q.nomi, q.guruh)
        if oila is None or oila.kod != "vrf_ichki":
            continue
        quvvat = kvt(f"{q.nomi} {q.matn}") or 0
        if q.tizim and any(abs(quvvat - k) <= 0.05 * k for k in katta.get(q.tizim, [])):
            split_ichki.add(id(q))
            continue
        yigindi[q.tizim] = yigindi.get(q.tizim, 0) + quvvat * q.miqdor
    return yigindi, split_ichki


def _kckp_eslatma(olindi: list[str]) -> str:
    return (f"КЦКП o'lchami sarfdan olindi ({len(olindi)}): " + "; ".join(olindi[:6])
            + (" …" if len(olindi) > 6 else "")
            + ". Tavsifda faqat TZ dagi raqamlar (sarf, bosim, isitgich, filtr) — "
              "Seksiyalar tarkibi: ventilyator modeli, xizmat tomoni, avtomatika "
              "KP da YO'Q, tanlov dasturidan qo'shing")


def kp_bilan_qamrov(mahsulotlar: list[dict[str, Any]], kp) -> tuple[float, float]:
    """Qoralama haqiqiy KP ni qanchalik takrorlaydi — ETALON o'lchovi.

    (miqdor qamrovi %, aniq nom %):
      * miqdor qamrovi — KP dagi har (oila, o'lcham/quvvat) miqdorining
        qanchasi qoralamada ham bor (`min(qoralama, KP)` yig'indisi);
      * aniq nom — KP mahsulot qatorlarining qanchasi qoralamada harfma-harf
        bor (bo'shliq va katta-kichik harf farqsiz).
    Narx hisobga olinmaydi — u katalogdan keladi, qoralamadan emas.
    """
    from .solishtir import _kalit, kp_oilasi

    def guruhla(nomlar_miqdor):
        natija: Counter = Counter()
        for nomi, miqdor in nomlar_miqdor:
            oila = kp_oilasi(nomi)
            kalit = (oila.kod, _kalit(oila, nomi)) if oila else ("?", nomi.lower())
            natija[kalit] += miqdor
        return natija

    haqiqiy = guruhla((q.toza_nomi, q.miqdor) for q in kp.mahsulotlar)
    # TZ nomi bilan QOLGAN qator (tanlov, tanilmadi) hech narsani qoplamaydi —
    # aks holda «ventilyator» oilasi bir xil bo'lgani uchun mos sanalardi.
    bizniki = guruhla((m["nomi"], float(m["miqdor"])) for m in mahsulotlar
                      if m["nomi"] != m.get("asl_nomi"))
    jami = sum(haqiqiy.values())
    qamrov = sum(min(v, bizniki.get(k, 0)) for k, v in haqiqiy.items())

    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s).lower()

    bizning_nomlar = {norm(m["nomi"]) for m in mahsulotlar}
    aniq = sum(1 for q in kp.mahsulotlar if norm(q.toza_nomi) in bizning_nomlar)
    return (100.0 * qamrov / jami if jami else 0.0,
            100.0 * aniq / len(kp.mahsulotlar) if kp.mahsulotlar else 0.0)


def fayldan_taklif(yol: str | Path):
    """TZ fayli -> `ShaklTaklifi` (yol=model). Tanilmasa `None`.

    Excel jadval (`kp/tz_jadval.py`), VENTAS КЦКП tanlovi PDF
    (`kp/ventas.py`) yoki konditsioner so'rovnoma varaqasi PDF
    (`kp/ol_pdf.py`). `None` qaytsa `/kp` eski yo'ldan ketadi (matn ->
    model): fayl jadval emas, xonalar tavsifi bo'lishi mumkin.
    """
    yol = Path(yol)
    kengaytma = yol.suffix.lower()
    from .tz_jadval import JADVAL_KENGAYTMALARI

    if kengaytma in JADVAL_KENGAYTMALARI:
        return jadvaldan_taklif(yol)
    if kengaytma == ".pdf":
        from .ol_pdf import ol_oqi
        from .ventas import ventas_oqi

        qurilma = ventas_oqi(yol)
        if qurilma is not None:
            return ventasdan_taklif(qurilma)

        qatorlar = ol_oqi(yol)
        return qatorlardan_taklif(qatorlar, [], "So'rovnoma varaqasi (ОЛ)") if qatorlar else None
    return None


def ventas_mahsuloti(q) -> tuple[dict[str, Any], str]:
    """VENTAS qurilmasi (`kp/ventas.py`) -> qoralama qatori va turi.

    AHU / RC — КЦКП, o'lchami kirish sarfidan. Boshqasi (HEF — oshxona
    so'rish filtri) КЦКП emas: TZ nomi bilan qoladi, menejer tanlaydi.
    """
    from .kckp import nomi, olcham_tanla, ventas_tavsifi

    asl = f"{q.nomi} {q.model}".strip()
    yozuv: dict[str, Any] = {
        "nomi": asl, "miqdor": q.soni or 1, "birlik": "комп.", "bolim": "",
        "asl_nomi": asl, "ogohlantirishlar": [],
    }
    qoida = (jadval().get("analoglar") or {}).get("kckp") or {}
    olcham_q = (olcham_tanla(q.sarf, qoida)
                if re.match(r"(AHU|RC)\b", q.nomi, re.I) else None)
    if olcham_q is None:
        return yozuv, TANLOV
    yozuv["nomi"] = nomi(olcham_q, qoida)
    yozuv["tavsif"], yozuv["ogohlantirishlar"] = ventas_tavsifi(q, olcham_q, qoida)
    return yozuv, ANALOG


def ventasdan_taklif(q):
    """Bitta VENTAS tanlov PDF -> `ShaklTaklifi`. Bir nechta PDF tashlansa
    bot ularni bitta ro'yxatga QO'SHADI (`bot/kp_oqim.py::_taklifni_qolla`)."""
    from .tz import ShaklTaklifi

    yozuv, turi = ventas_mahsuloti(q)
    taklif = ShaklTaklifi()
    taklif.javoblar["yol"] = "model"
    taklif.javoblar["mahsulotlar"] = [yozuv]
    taklif.topilganlar.append(
        f"VENTAS tanlovi: {q.nomi}, {q.sarf:g} m³/soat"
        + (f" -> {yozuv['nomi']}" if turi == ANALOG else ""))
    if turi == ANALOG:
        taklif.ogohlantirishlar.append(_markdownsiz(_kckp_eslatma(
            [f"{q.nomi} {q.sarf:g} -> {yozuv['nomi'].split()[-1]}"])))
    else:
        taklif.ogohlantirishlar.append(_markdownsiz(
            f"{q.nomi} ({q.model}) — КЦКП emas, TZ nomi bilan qoldi: menejer tanlaydi"))
    return taklif


def jadvaldan_taklif(yol: str | Path):
    """Excel TZ -> `ShaklTaklifi` (yol=model). Jadval bo'lmasa `None`."""
    from .tz_jadval import jadval_oqi

    j = jadval_oqi(yol)
    if not j.qatorlar:
        return None
    return qatorlardan_taklif(j.qatorlar, j.ogohlantirishlar, "Jadval")


def qatorlardan_taklif(qatorlar: list[TzQator], fayl_ogohlari: list[str], manba: str):
    from .tz import ShaklTaklifi

    q = qoralama(qatorlar)
    if q.turlar[QISQARTMA] + q.turlar[ANALOG] + q.turlar[TANLOV] == 0:
        return None     # hech bir qator ventilyatsiya mahsulotiga o'xshamadi

    taklif = ShaklTaklifi()
    if q.turlar[QISQARTMA] + q.turlar[ANALOG] == 0:
        # BIRORTA qator Climavent nomiga aylanmadi — bu KP emas, TZ nusxasi.
        # JONLI HOLAT (2026-10-05, KP-2026-13008): Enter ALM zayavkasi (xarid
        # so'rovi: «Приточная установка П1», «Вытяжной вентилятор В1…В25»,
        # «К1. Система VRF…», «Чиллер») 37 qatorlik bo'sh KP bo'lib chiqdi.
        # Menejer o'sha so'rovga opros listdan (ОЛ, kVt bilan) faqat VRF
        # qismini hisoblagan (KP 13173). Zayavkada parametr yo'q — model
        # tanlab bo'lmaydi; nima kerakligini aytamiz, KP yasamaymiz.
        guruhlar = Counter(
            (tz_oilasi(t.nomi, t.guruh).nomi if tz_oilasi(t.nomi, t.guruh) else "boshqa")
            for t in qatorlar if t.varaq in {x.varaq for x in qatorlar
                                             if tz_oilasi(x.nomi, x.guruh)})
        taklif.ogohlantirishlar.append(_markdownsiz(
            f"{manba}: {sum(guruhlar.values())} qator, lekin BIRORTASI Climavent modeliga "
            "aylanmadi — faqat nomlar, parametr (sarf, bosim, kVt) yo'q. KP YASALMADI: u "
            "TZ nusxasi bo'lib qolardi. Tarkibi: "
            + ", ".join(f"{nom} — {soni}" for nom, soni in guruhlar.most_common())))
        taklif.ogohlantirishlar.append(
            "KP uchun kerak: VRF/konditsioner — opros list (ОЛ, har blok kVt); КЦКП va "
            "ventilyatorlar — sarf (m³/soat) va bosim (Pa) yozilgan spetsifikatsiya. "
            "Shularni tashlang — shu /kp ga qo'shiladi.")
        taklif.ogohlantirishlar += [_markdownsiz(o) for o in fayl_ogohlari + q.umumiy]
        return taklif

    taklif.javoblar["yol"] = "model"
    taklif.javoblar["mahsulotlar"] = q.mahsulotlar
    jami = len(q.mahsulotlar)
    taklif.topilganlar.append(
        f"{manba}: {jami} qator, miqdorlari bilan")
    taklif.topilganlar.append(
        f"Climavent nomiga aylandi: {q.turlar[QISQARTMA] + q.turlar[ANALOG]} "
        f"({q.tayyor_foizi:.0f}%)")
    if q.turlar[TANLOV]:
        taklif.topilganlar.append(
            f"Parametr bo'yicha TANLASH kerak: {q.turlar[TANLOV]} (КЦКП, ventilyator, VRF …)")
    if q.turlar[TANILMADI]:
        taklif.topilganlar.append(f"Tanilmadi (TZ nomi bilan qoldi): {q.turlar[TANILMADI]}")
    # Bot bu matnni Markdown bilan yuboradi: TZ dan kelgan «_», «*» (varaq
    # nomida, mahsulot nomida) xabarni BUZADI — Telegram uni rad etadi.
    taklif.ogohlantirishlar += [_markdownsiz(o) for o in fayl_ogohlari + q.umumiy]
    return taklif


def _markdownsiz(matn: str) -> str:
    return re.sub(r"[_*`\[\]]", " ", matn)

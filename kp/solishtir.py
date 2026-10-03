"""TZ ni tayyor KP bilan solishtirish — tekshiruvchi.

NEGA KERAK
----------
KP ni menejer qo'lda tuzadi. 7 juft haqiqiy TZ va KP ni solishtirganda
(2026-10-03, tests/etalon_tz/) deyarli har bir juftda farq chiqdi:

  * TZ dagi qurilma KP ga KIRMAGAN (HEF-01, `Compact 20` ventilyatorlari);
  * o'lcham almashgan (4РВП 150х150 -> 300х300; ДКСп 250х150 o'rniga
    250х100 — jami bir xil, taqsimot boshqa);
  * kuchlanish, filtr klassi, rekuperator turi almashgan (24В -> 220В,
    H14 HEPA tushib qolgan, glikolli -> plastinchatiy);
  * KP ichida bitta tavsif ikki qatorga nusxa qilingan, narxi esa
    3 barobar farq qiladi.

Bularning bir qismi menejerning ongli qarori bo'lishi mumkin (mijoz bilan
og'zaki kelishilgan). Shuning uchun tekshiruvchi HECH NARSANI
TUZATMAYDI va «xato» demaydi — u farqni KO'RSATADI, qarorni odam qiladi.

QANDAY SOLISHTIRADI
-------------------
Qatorma-qator emas: menejer qatorlarni birlashtiradi yoki bo'ladi
(22 ta AHU -> 25 qator). Shuning uchun ikki tomon (oila, kalit)
bo'yicha YIG'ILADI va miqdorlar solishtiriladi:

    (devor panjarasi, 300х150)  TZ 57 = KP 57   -> mos
    (shift panjarasi, 150х150)  TZ 16, KP 0     -> kam 16
    (shift panjarasi, 300х300)  TZ 0,  KP 16    -> ortiq 16
                                                -> «o'lcham almashgan»

Bir oilada KAM va aynan shuncha ORTIQ bo'lsa — bu ikki alohida xato
emas, bitta almashinuv; menejerga shunday ko'rsatiladi.

Oila — `knowledge/product/tz_oilalari.yaml` dan, kodda emas.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .kp_pdf import KpHujjat, KpQator
from .tz_jadval import TzQator
from .ventas import Qurilma

# --- farq turlari --------------------------------------------------------------

YOQ_KPDA = "yoq_kpda"            # TZ da bor, KP da yo'q
ORTIQCHA = "ortiqcha_kpda"       # KP da bor, TZ da yo'q
MIQDOR = "miqdor"
OLCHAM = "olcham"                # o'lcham (yoki quvvat) almashgan
PARAMETR = "parametr"            # kuchlanish, filtr, bosim, kVt …
NOM_TOLIQ_EMAS = "nom_toliq_emas"
NUSXA = "nusxa"
TANILMADI = "tanilmadi"          # TZ qatori hech qaysi oilaga tushmadi
ALOQASIZ = "aloqasiz"            # TZ varag'i HVAC ga aloqasiz

# Daraja: menejer nimaga birinchi qarashi kerak.
JIDDIY = "jiddiy"
TEKSHIRING = "tekshiring"
MALUMOT = "malumot"

_DARAJA_TARTIBI = {JIDDIY: 0, TEKSHIRING: 1, MALUMOT: 2}


@dataclass
class Farq:
    turi: str
    daraja: str
    matn: str
    oila: str = ""
    kalit: str = ""


@dataclass
class Natija:
    farqlar: list[Farq] = field(default_factory=list)
    tz_guruhlar: int = 0          # TZ dagi (oila, kalit) juftlari
    mos_guruhlar: int = 0         # miqdori bilan to'liq mos kelganlari
    tz_qatorlar: int = 0
    kp_qatorlar: int = 0

    @property
    def moslik_foizi(self) -> float:
        return 100.0 * self.mos_guruhlar / self.tz_guruhlar if self.tz_guruhlar else 0.0

    def turlar(self, turi: str) -> list[Farq]:
        return [f for f in self.farqlar if f.turi == turi]

    def saralangan(self) -> list[Farq]:
        return sorted(self.farqlar, key=lambda f: _DARAJA_TARTIBI.get(f.daraja, 9))


# --- oilalar -------------------------------------------------------------------


@dataclass(frozen=True)
class Oila:
    kod: str
    nomi: str
    tz: tuple[re.Pattern, ...]
    tz_umumiy: tuple[re.Pattern, ...]
    kp: tuple[re.Pattern, ...]
    kalit: str
    olcham_shart: bool = False
    aksessuar: bool = False


def _oilalar_yoli() -> Path:
    try:
        from app.config import sozlama

        return Path(sozlama().bilim_yoli) / "product" / "tz_oilalari.yaml"
    except Exception:   # noqa: BLE001 — sozlamasiz (skript) ishlaganda ham
        return Path(__file__).resolve().parent.parent / "knowledge" / "product" / "tz_oilalari.yaml"


@lru_cache
def oilalar() -> tuple[Oila, ...]:
    xom = yaml.safe_load(_oilalar_yoli().read_text(encoding="utf-8")) or {}

    def qolip(royxat) -> tuple[re.Pattern, ...]:
        return tuple(re.compile(p, re.I) for p in royxat or [])

    return tuple(
        Oila(kod=o["kod"], nomi=o.get("nomi", o["kod"]), tz=qolip(o.get("tz")),
             tz_umumiy=qolip(o.get("tz_umumiy")), kp=qolip(o.get("kp")),
             kalit=o.get("kalit", "olcham"), olcham_shart=bool(o.get("olcham_shart")),
             aksessuar=bool(o.get("aksessuar")))
        for o in xom.get("oilalar") or [])


def _birinchi(matn: str, qolip_nomi: str) -> Oila | None:
    for o in oilalar():
        if any(q.search(matn) for q in getattr(o, qolip_nomi)):
            return o
    return None


def tz_oilasi(nomi: str, guruh: str = "") -> Oila | None:
    """TZ qatorining oilasi: nom (kuchli) -> guruh (kuchli) -> nom (kuchsiz)."""
    return (_birinchi(nomi, "tz") or (_birinchi(guruh, "tz") if guruh else None)
            or _birinchi(nomi, "tz_umumiy"))


def kp_oilasi(nomi: str) -> Oila | None:
    """KP qatori oilasi — avval nom BOSHIDAN.

    КЦКП tavsifi ichida «наружная», «секция шумоглушения», «рекуператор»
    so'zlari uchraydi; to'liq matndan qidirsak konditsioner «tashqi
    panjara» bo'lib qolardi (KP 13574 dagi 10 ta qator).
    """
    return _birinchi(nomi[:40], "kp") or _birinchi(nomi, "kp")


# --- kalitlar -------------------------------------------------------------------

_OLCHAM = re.compile(r"(\d{2,4})\s*[xхХ×*]\s*(\d{2,4})")
# «∅100», «Ø100», «ДФА 100», «DVS 125», «Д125», «…-Ф200» (dumaloq klapan).
_DIAMETR = re.compile(r"(?:∅|Ø|ДФА|DVS|\bД|-Ф)\s*-?\s*(\d{2,4})\b", re.I)
_KVT = re.compile(r"(\d+(?:[.,]\d+)?)\s*к[Вв]т", re.I)
_VRF_KOD = re.compile(r"\bJ[VU][IO]-(\d{3})", re.I)
_BTU = re.compile(r"(\d+)\s*(?:000)?\s*БТУ", re.I)
_SARF = re.compile(r"L\s*=\s*([\d\s]+?)\s*м", re.I)
_BELGI = re.compile(r"\(((?:ПВ|ПД|ДУ|П|В|K|К)\d+[рp]?)\)")
# Nom BOSHIDAGI tizim belgisi: «К1. Система VRF кондиционирования».
_BOSH_BELGI = re.compile(r"^\s*((?:ПВ|ПД|ДУ|П|В|K|К)\s*\d+[рp]?)[.\s]")
# KP bo'lim sarlavhasidagi belgilar: «- K1.K4», «- (Система К5)».
_SARLAVHA_BELGI = re.compile(r"[KК]\s*\d+[рРpP]?")
_LOTIN = str.maketrans("KPBEHOCX", "КРВЕНОСХ")


def _belgi_normal(belgi: str) -> str:
    return re.sub(r"\s+", "", belgi.upper().translate(_LOTIN))


def tizimlar_normal(matn: str) -> str:
    """«К1, К4» / «K1.K4» / «К6,К6р» -> «К1,К4» — ikki tomonni tenglash uchun."""
    return ",".join(sorted({_belgi_normal(b) for b in _SARLAVHA_BELGI.findall(matn or "")}))


def olcham(matn: str) -> str:
    m = _OLCHAM.search(matn or "")
    return f"{int(m.group(1))}х{int(m.group(2))}" if m else ""


def diametr(matn: str) -> str:
    m = _DIAMETR.search(matn or "")
    return f"Ø{int(m.group(1))}" if m else ""


def kvt(matn: str) -> float | None:
    m = _VRF_KOD.search(matn or "")
    if m:
        return int(m.group(1)) / 10
    m = _KVT.search(matn or "")
    if m:
        return float(m.group(1).replace(",", "."))
    m = _BTU.search(matn or "")
    if m:
        # «12 БТУ» = 12 000 BTU/soat ≈ 3,5 kVt
        return round(int(m.group(1)) * 1000 * 0.000293, 1)
    return None


def sarf(matn: str) -> float | None:
    m = _SARF.search(matn or "")
    if not m:
        return None
    raqam = re.sub(r"\s", "", m.group(1))
    return float(raqam) if raqam.isdigit() else None


def _kalit(oila: Oila, matn: str, belgi: str = "", sarf_qiymati: float | None = None) -> str:
    if oila.kalit == "olcham":
        # Dumaloq klapan: «КПД-НЗ-…-Ф200», «FD Ø200».
        return olcham(matn) or diametr(matn)
    if oila.kalit == "diametr":
        return diametr(matn) or olcham(matn)
    if oila.kalit == "kvt":
        k = kvt(matn)
        return f"{k:g} kVt" if k else ""
    if oila.kalit == "sarf":
        s = sarf_qiymati or sarf(matn)
        return f"{s:g} m³/soat" if s else ""
    if oila.kalit == "belgi":
        return _belgi_normal(belgi) if belgi else ""
    return ""


# --- yig'ish -------------------------------------------------------------------


@dataclass
class _Guruh:
    miqdor: float = 0
    qatorlar: list[Any] = field(default_factory=list)


Kalit = tuple[str, str, str]   # (oila, tizim, kalit)


def _tz_yig(tz: list[TzQator], natija: Natija) -> dict[Kalit, _Guruh]:
    guruhlar: dict[Kalit, _Guruh] = defaultdict(_Guruh)
    varaq_soni: dict[str, int] = defaultdict(int)
    varaq_tanilgan: dict[str, int] = defaultdict(int)
    tanilmagan: list[TzQator] = []
    for q in tz:
        varaq_soni[q.varaq] += 1
        oila = tz_oilasi(q.nomi, q.guruh)
        if oila is None:
            tanilmagan.append(q)
            continue
        varaq_tanilgan[q.varaq] += 1
        tizim = q.tizim
        if not tizim:
            m = _BOSH_BELGI.match(q.nomi)
            tizim = m.group(1) if m else ""
        belgilar = [b.strip() for b in re.split(r"[,.]", tizim) if b.strip()] or [""]
        if oila.kalit == "belgi":
            # «К1, К4 — 2 dona»: har belgiga bittadan.
            for b in belgilar:
                g = guruhlar[(oila.kod, "", _belgi_normal(b))]
                g.miqdor += q.miqdor / len(belgilar)
                g.qatorlar.append(q)
            continue
        kalit = _kalit(oila, q.nomi + " " + q.matn, "", q.parametrlar.get("L"))
        # VRF va split bloklari TIZIM ichida solishtiriladi (К7 dagi 18 kVt
        # tashqi blok К8 dagisiga tenglashtirilmasin).
        tizim_kaliti = tizimlar_normal(tizim) if oila.kalit == "kvt" else ""
        g = guruhlar[(oila.kod, tizim_kaliti, kalit)]
        g.miqdor += q.miqdor
        g.qatorlar.append(q)

    for varaq, soni in varaq_soni.items():
        if varaq_tanilgan[varaq] == 0:
            natija.farqlar.append(Farq(
                ALOQASIZ, MALUMOT,
                f"«{varaq}» varag'ida ventilyatsiya/konditsioner mahsuloti yo'q "
                f"({soni} qator) — solishtirilmadi"))
    for q in tanilmagan:
        if varaq_tanilgan[q.varaq] == 0:
            continue
        natija.farqlar.append(Farq(
            TANILMADI, MALUMOT,
            f"TZ qatori tanilmadi: «{q.nomi[:90]}» — {q.miqdor:g} {q.birlik}".strip()))
    return guruhlar


def _kp_yig(kp: KpHujjat, natija: Natija) -> tuple[dict[Kalit, _Guruh], dict[str, list[KpQator]]]:
    """KP guruhlari va bo'lim sarlavhasi bo'yicha qatorlar («К5» -> […])."""
    guruhlar: dict[Kalit, _Guruh] = defaultdict(_Guruh)
    bolimlar: dict[str, list[KpQator]] = defaultdict(list)
    tizim = ""
    for q in kp.qatorlar:
        if q.sarlavhami:
            tizim = tizimlar_normal(q.toza_nomi)
            bolimlar.setdefault(tizim, [])
            continue
        if tizim:
            bolimlar[tizim].append(q)
        oila = kp_oilasi(q.toza_nomi)
        if oila is None:
            natija.farqlar.append(Farq(
                ORTIQCHA, MALUMOT,
                f"KP {q.raqam}-qator oilasi aniqlanmadi: «{q.toza_nomi[:80]}» — "
                f"{q.miqdor:g} {q.birlik}"))
            continue
        belgi = _BELGI.search(q.toza_nomi)
        if oila.kalit == "belgi":
            kalit_ = (oila.kod, "", _kalit(oila, q.toza_nomi, belgi.group(1) if belgi else ""))
        else:
            kalit = _kalit(oila, q.toza_nomi)
            if oila.olcham_shart and not kalit:
                natija.farqlar.append(Farq(
                    NOM_TOLIQ_EMAS, TEKSHIRING,
                    f"KP {q.raqam}-qator nomida o'lcham yo'q: «{q.toza_nomi[:80]}» — "
                    f"{q.miqdor:g} {q.birlik}", oila=oila.kod))
            kalit_ = (oila.kod, tizim if oila.kalit == "kvt" else "", kalit)
        g = guruhlar[kalit_]
        g.miqdor += q.miqdor
        g.qatorlar.append(q)
    return guruhlar, bolimlar


def _yaqin_kvt(a: str, b: str) -> bool:
    try:
        x, y = float(a.split()[0]), float(b.split()[0])
    except (ValueError, IndexError):
        return False
    return abs(x - y) <= 0.2 * max(x, y)


def _raqamlar(qatorlar: list[Any]) -> str:
    r = [str(q.raqam) for q in qatorlar if hasattr(q, "raqam")]
    return ", ".join(r[:6]) + ("…" if len(r) > 6 else "")


def _nom(oila: Oila, tizim: str, kalit: str) -> str:
    return " ".join(x for x in (oila.nomi, f"[{tizim}]" if tizim else "", kalit) if x)


def _oilaga_yig(guruhlar: dict[Kalit, _Guruh], oila_kod: str) -> None:
    """Oilaning hamma kalitlarini bitta (kalitsiz) guruhga birlashtiradi."""
    kalitlar = [k for k in guruhlar if k[0] == oila_kod]
    if not kalitlar or (len(kalitlar) == 1 and kalitlar[0][1:] == ("", "")):
        return
    umumiy = _Guruh()
    for k in kalitlar:
        g = guruhlar.pop(k)
        umumiy.miqdor += g.miqdor
        umumiy.qatorlar += g.qatorlar
    guruhlar[(oila_kod, "", "")] = umumiy


# --- asosiy solishtirish ---------------------------------------------------------


@dataclass
class _Qoldiq:
    """Juftlanmagan farq: manfiy — KP da KAM, musbat — KP da ORTIQ."""
    kalit: Kalit
    farq: float
    tz: _Guruh | None
    kp: _Guruh | None


def solishtir(tz: list[TzQator], kp: KpHujjat) -> Natija:
    """TZ qatorlari va KP ni solishtiradi. Hech narsa o'zgartirilmaydi."""
    natija = Natija(tz_qatorlar=len(tz), kp_qatorlar=len(kp.mahsulotlar))
    tzg = _tz_yig(tz, natija)
    kpg, bolimlar = _kp_yig(kp, natija)
    nomlar = {o.kod: o for o in oilalar()}

    # VRF tizimi TZ da bitta qator («К5. Система VRF») — KP da u bo'lim
    # sarlavhasi («- (Система К5)»). Bo'lim bor bo'lsa — tizim KP da bor,
    # uning ostidagi bloklar esa «ortiqcha» emas.
    qoplangan: set[int] = set()
    for kalit in [k for k in tzg if k[0] == "vrf_tizim"]:
        g = tzg.pop(kalit)
        natija.tz_guruhlar += 1
        bolim = next((b for b in bolimlar if kalit[2] and kalit[2] in b.split(",")), None)
        if bolim is not None:
            natija.mos_guruhlar += 1
            qoplangan |= {id(q) for q in bolimlar[bolim]}
        else:
            natija.farqlar.append(Farq(
                YOQ_KPDA, TEKSHIRING,
                f"TZ: VRF tizimi {kalit[2] or '(belgisiz)'} — KP da bunday tizim bo'limi yo'q",
                oila="vrf_tizim", kalit=kalit[2]))
    # TZ da bloklar ALOHIDA ham berilgan bo'lsa (zayavka + so'rovnoma varaqasi),
    # KP bloklari ular bilan solishtiriladi — tizim qatori ularni «yutmasin».
    # Faqat TZ da alohida BERILMAGAN oila qatorlari qoplangan sanaladi
    # (5-juft: К1–К4 splitlari ОЛ da yo'q, zayavkada tizim sifatida bor).
    tz_oilalari = {k[0] for k in tzg}
    if qoplangan:
        for k in list(kpg):
            if k[0] in tz_oilalari:
                continue
            g = kpg[k]
            g.qatorlar = [q for q in g.qatorlar if id(q) not in qoplangan]
            g.miqdor = sum(q.miqdor for q in g.qatorlar)
            if not g.qatorlar:
                del kpg[k]

    # Quvvat bo'yicha oilalar (VRF, split): TZ da tizim belgisi umuman yo'q
    # bo'lsa (so'rovnoma varaqasida faqat qavat) — KP ham tizimsiz yig'iladi.
    for oila_kod in {k[0] for k in tzg if nomlar[k[0]].kalit == "kvt"}:
        if all(k[1] == "" for k in tzg if k[0] == oila_kod):
            for k in [k for k in kpg if k[0] == oila_kod and k[1]]:
                g = kpg.pop(k)
                umumiy = kpg[(oila_kod, "", k[2])]
                umumiy.miqdor += g.miqdor
                umumiy.qatorlar += g.qatorlar

    # VRF tashqi bloklari: TZ da tizim quvvati («128,5 kVt»), KP da modullar
    # (615T + 335T × 2). Bir-biriga bittalab mos kelmaydi — JAMI quvvat
    # solishtiriladi (tizim bo'yicha, tizim yo'q bo'lsa hammasi).
    for tizim in {k[1] for k in tzg if k[0] == "vrf_tashqi"}:
        tz_k = [k for k in tzg if k[0] == "vrf_tashqi" and k[1] == tizim and k[2]]
        kp_k = [k for k in kpg if k[0] == "vrf_tashqi" and k[1] == tizim and k[2]]
        if not tz_k or not kp_k:
            continue

        def jami(guruhlar, kalitlar):
            return sum(float(k[2].split()[0]) * guruhlar[k].miqdor for k in kalitlar)

        tz_jami, kp_jami = jami(tzg, tz_k), jami(kpg, kp_k)
        if abs(tz_jami - kp_jami) <= 0.02 * tz_jami:
            kp_qatorlar = [q for k in kp_k for q in kpg[k].qatorlar]
            for k in tz_k:
                del tzg[k]
            for k in kp_k:
                del kpg[k]
            natija.tz_guruhlar += 1
            natija.mos_guruhlar += 1
            natija.farqlar.append(Farq(
                PARAMETR, MALUMOT,
                f"VRF tashqi bloklar{' [' + tizim + ']' if tizim else ''}: jami quvvat "
                f"TZ {tz_jami:g} kVt = KP {kp_jami:g} kVt (KP qatorlari: {_raqamlar(kp_qatorlar)})",
                oila="vrf_tashqi"))

    # Belgili oilalar (ventilyatorlar): belgisi yo'q tomon bo'lsa — oila
    # darajasida (jami dona) solishtiriladi.
    for oila_kod in {k[0] for k in tzg} | {k[0] for k in kpg}:
        if nomlar[oila_kod].kalit != "belgi":
            continue
        tz_k = {k[2] for k in tzg if k[0] == oila_kod}
        kp_k = {k[2] for k in kpg if k[0] == oila_kod}
        if "" in tz_k or "" in kp_k or not (tz_k & kp_k):
            _oilaga_yig(tzg, oila_kod)
            _oilaga_yig(kpg, oila_kod)

    # 1) Kalit bo'yicha juftlash (kVt — 20% gacha farq bilan).
    qoldiqlar: list[_Qoldiq] = []
    qolgan_kp = dict(kpg)
    for kalit, g in tzg.items():
        natija.tz_guruhlar += 1
        oila = nomlar[kalit[0]]
        juft = kalit if kalit in qolgan_kp else None
        if juft is None and oila.kalit == "kvt" and kalit[2]:
            nomzodlar = [k for k in qolgan_kp if k[:2] == kalit[:2] and _yaqin_kvt(kalit[2], k[2])]
            juft = min(nomzodlar, key=lambda k: abs(float(k[2].split()[0]) - float(kalit[2].split()[0])),
                       default=None)
        if juft is None:
            qoldiqlar.append(_Qoldiq(kalit, -g.miqdor, g, None))
            continue
        kg = qolgan_kp.pop(juft)
        _parametrlar(natija, oila, kalit[2], g, kg)
        if abs(g.miqdor - kg.miqdor) < 1e-6:
            natija.mos_guruhlar += 1
            if juft[2] != kalit[2] and oila.kalit == "kvt":
                natija.farqlar.append(Farq(
                    PARAMETR, MALUMOT,
                    f"{_nom(oila, kalit[1], kalit[2])}: KP da {juft[2]} "
                    f"(KP qatorlari: {_raqamlar(kg.qatorlar)})", oila=oila.kod, kalit=kalit[2]))
        else:
            qoldiqlar.append(_Qoldiq(kalit, kg.miqdor - g.miqdor, g, kg))
    for kalit, kg in qolgan_kp.items():
        qoldiqlar.append(_Qoldiq(kalit, kg.miqdor, None, kg))

    # 2) Bir oilada (VRF da — bir tizimda) KAM va aynan shuncha ORTIQ —
    #    bitta almashinuv. Split <-> VRF tashqi blok ham shunday: TZ dagi
    #    «Сплит-система» KP da mini-VRF tashqi bloki bo'lib chiqishi mumkin.
    #    Yong'in klapanlari ham: TZ dagi Н/О klapan KP da КПД-НЗ bo'lishi mumkin.
    #    Avval O'LCHAMI BIR XIL juft qidiriladi (oila almashgan), keyin
    #    oilasi bir xil (o'lcham almashgan).
    qoshni = ({"split", "vrf_tashqi"}, {"kpu", "kpd"})

    def mos_oila(a: str, b: str) -> bool:
        return a == b or {a, b} in qoshni

    kamlar = [q for q in qoldiqlar if q.farq < 0]
    ortiqlar = [q for q in qoldiqlar if q.farq > 0]

    def juft_top(kam: _Qoldiq) -> _Qoldiq | None:
        mos = [o for o in ortiqlar
               if mos_oila(o.kalit[0], kam.kalit[0]) and o.kalit[1] == kam.kalit[1]
               and abs(o.farq + kam.farq) < 1e-6]
        bir_xil = [o for o in mos if o.kalit[2] == kam.kalit[2]]
        bir_oila = [o for o in mos if o.kalit[0] == kam.kalit[0]]
        return (bir_xil or bir_oila or mos or [None])[0]

    for kam in sorted(kamlar, key=lambda k: not any(
            o.kalit[2] == k.kalit[2] and o.kalit[0] != k.kalit[0] for o in ortiqlar)):
        oila = nomlar[kam.kalit[0]]
        juft = juft_top(kam)
        if juft is None:
            continue
        ortiqlar.remove(juft)
        kam.farq = 0
        soni = abs(juft.farq)
        kp_raqam = _raqamlar(juft.kp.qatorlar) if juft.kp else ""
        if juft.kalit[0] != kam.kalit[0]:
            # Yong'in klapani turi almashsa — bu xavfsizlik masalasi.
            daraja = TEKSHIRING if {juft.kalit[0], kam.kalit[0]} == {"kpu", "kpd"} else MALUMOT
            natija.farqlar.append(Farq(
                OLCHAM, daraja,
                f"{_nom(oila, kam.kalit[1], kam.kalit[2])} × {soni:g} -> KP da "
                f"{nomlar[juft.kalit[0]].nomi} {juft.kalit[2]} (KP qatorlari: {kp_raqam})",
                oila=oila.kod, kalit=kam.kalit[2]))
        elif not juft.kalit[2] and oila.olcham_shart:
            natija.farqlar.append(Farq(
                NOM_TOLIQ_EMAS, TEKSHIRING,
                f"{oila.nomi}: TZ da {kam.kalit[2]} × {soni:g}; KP {kp_raqam}-qatorda "
                f"xuddi shu miqdor, lekin nomida o'lcham YO'Q — ehtimol {kam.kalit[2]}",
                oila=oila.kod, kalit=kam.kalit[2]))
        else:
            natija.farqlar.append(Farq(
                OLCHAM, TEKSHIRING,
                f"{_nom(oila, kam.kalit[1], '')}: {soni:g} dona TZ da {kam.kalit[2]}, "
                f"KP da {juft.kalit[2]} (KP qatorlari: {kp_raqam}) — almashgan bo'lishi mumkin",
                oila=oila.kod, kalit=kam.kalit[2]))

    # 3) Qolganlari.
    for q in kamlar:
        if q.farq == 0:
            continue
        oila = nomlar[q.kalit[0]]
        nom = _nom(oila, q.kalit[1], q.kalit[2])
        if q.kp is None:
            misol = q.tz.qatorlar[0].nomi[:70] if q.tz and q.tz.qatorlar else ""
            natija.farqlar.append(Farq(
                YOQ_KPDA, TEKSHIRING,
                f"TZ da bor, KP da yo'q: {nom} — {abs(q.farq):g} dona"
                + (f" («{misol}»)" if misol else ""), oila=oila.kod, kalit=q.kalit[2]))
        else:
            natija.farqlar.append(Farq(
                MIQDOR, TEKSHIRING,
                f"{nom}: TZ {q.tz.miqdor:g}, KP {q.kp.miqdor:g} — KP da {abs(q.farq):g} kam "
                f"(KP qatorlari: {_raqamlar(q.kp.qatorlar)})", oila=oila.kod, kalit=q.kalit[2]))
    for q in ortiqlar:
        oila = nomlar[q.kalit[0]]
        if oila.aksessuar:
            continue
        nom = _nom(oila, q.kalit[1], q.kalit[2])
        if q.tz is None:
            natija.farqlar.append(Farq(
                ORTIQCHA, MALUMOT,
                f"KP da bor, TZ da yo'q: {nom} — {q.farq:g} dona "
                f"(KP qatorlari: {_raqamlar(q.kp.qatorlar)})", oila=oila.kod, kalit=q.kalit[2]))
        else:
            natija.farqlar.append(Farq(
                MIQDOR, TEKSHIRING,
                f"{nom}: TZ {q.tz.miqdor:g}, KP {q.kp.miqdor:g} — KP da {q.farq:g} ortiq "
                f"(KP qatorlari: {_raqamlar(q.kp.qatorlar)})", oila=oila.kod, kalit=q.kalit[2]))

    natija.farqlar += kp_ichki_tekshiruv(kp)
    return natija


# --- parametrlar -----------------------------------------------------------------

_KUCHLANISH_24 = re.compile(r"\b24\s*[ВV]\b")
_CAV = re.compile(r"\bCAV\b|\bСAV\b|постоянн\w*\s+объем", re.I)
_FILTR = re.compile(r"\b([GFHE])\s?(\d{1,2})\b")
_DVIGATEL_KP = re.compile(r"-(\d+(?:,\d+)?)/\d{3,4}")
_FILTR_TARTIB = {"G": 1, "F": 3, "E": 4, "H": 5}


def _filtr_ball(f: str) -> tuple[int, int]:
    return (_FILTR_TARTIB.get(f[0], 0), int(f[1:]))


def _parametrlar(natija: Natija, oila: Oila, kalit: str, tz: _Guruh, kp: _Guruh) -> None:
    tz_matn = " ".join(q.matn or q.nomi for q in tz.qatorlar)
    kp_matn = " ".join(q.toza_nomi for q in kp.qatorlar)
    nom = f"{oila.nomi} {kalit}".strip()

    if _KUCHLANISH_24.search(tz_matn) and "220" in kp_matn:
        natija.farqlar.append(Farq(
            PARAMETR, TEKSHIRING,
            f"{nom}: TZ da yuritma 24 V, KP da 220 V", oila=oila.kod, kalit=kalit))

    if _CAV.search(tz_matn) and not _CAV.search(kp_matn):
        natija.farqlar.append(Farq(
            PARAMETR, TEKSHIRING,
            f"{nom}: TZ da doimiy sarf (CAV) rostlagichi so'ralgan, KP da oddiy ДКСп",
            oila=oila.kod, kalit=kalit))

    tz_filtr = {"".join(m) for m in _FILTR.findall(tz_matn)}
    kp_filtr = {"".join(m) for m in _FILTR.findall(kp_matn)}
    if tz_filtr and kp_filtr and oila.kod == "kckp":
        tz_max, kp_max = max(tz_filtr, key=_filtr_ball), max(kp_filtr, key=_filtr_ball)
        if _filtr_ball(kp_max) < _filtr_ball(tz_max):
            natija.farqlar.append(Farq(
                PARAMETR, JIDDIY,
                f"{nom}: TZ da filtr {tz_max}, KP da eng yuqorisi {kp_max}",
                oila=oila.kod, kalit=kalit))
        elif tz_max not in kp_filtr:
            natija.farqlar.append(Farq(
                PARAMETR, MALUMOT,
                f"{nom}: filtr TZ da {tz_max}, KP da {kp_max} (yuqoriroq)",
                oila=oila.kod, kalit=kalit))

    if oila.kod.startswith("vent"):
        tz_n = {q.parametrlar.get("N") for q in tz.qatorlar if q.parametrlar.get("N")}
        kp_n = {float(m.replace(",", ".")) for m in _DVIGATEL_KP.findall(kp_matn)}
        if tz_n and kp_n and not tz_n & kp_n:
            natija.farqlar.append(Farq(
                PARAMETR, TEKSHIRING,
                f"{nom}: dvigatel TZ da {', '.join(f'{x:g}' for x in sorted(tz_n))} kVt, "
                f"KP model belgisida {', '.join(f'{x:g}' for x in sorted(kp_n))}",
                oila=oila.kod, kalit=kalit))


# --- KP ning o'zi ------------------------------------------------------------------


def kp_ichki_tekshiruv(kp: KpHujjat) -> list[Farq]:
    """TZ siz ham ko'rinadigan farqlar: bir xil tavsif, har xil narx."""
    farqlar: list[Farq] = []
    tavsiflar: dict[str, list[KpQator]] = defaultdict(list)
    for q in kp.mahsulotlar:
        if len(q.toza_nomi) >= 120:
            tavsiflar[q.toza_nomi].append(q)
    for qatorlar in tavsiflar.values():
        narxlar = [q.narx for q in qatorlar if q.narx]
        if len(qatorlar) > 1 and narxlar and max(narxlar) > 1.2 * min(narxlar):
            farqlar.append(Farq(
                NUSXA, JIDDIY,
                f"KP {_raqamlar(qatorlar)}-qatorlar tavsifi harfma-harf bir xil, "
                f"narxi esa {_pul(min(narxlar))} va {_pul(max(narxlar))} — "
                "tavsif nusxa qilingan bo'lishi mumkin"))
    return farqlar


def _pul(qiymat: float) -> str:
    """235200000 -> «235 200 000»."""
    return f"{qiymat:,.0f}".replace(",", " ")


# --- VENTAS (tayyor tanlov) bilan solishtirish -------------------------------------


@dataclass
class _KpKckp:
    qator: KpQator
    sarf: float | None
    bosim: float | None
    isitish: float | None
    sovutish: float | None
    filtrlar: set[str]


def _kckp_oqi(q: KpQator) -> _KpKckp:
    matn = q.toza_nomi
    bosim = re.search(r"[РP]\s*=\s*(\d+)\s*Па", matn)
    qt = re.search(r"Qт\s*=\s*([\d.,]+)", matn)
    qx = re.search(r"Qх\s*=\s*([\d.,]+)", matn)

    def son(m):
        return float(m.group(1).rstrip(".,").replace(",", ".")) if m else None

    return _KpKckp(q, sarf(matn), son(bosim), son(qt), son(qx),
                   {"".join(m) for m in _FILTR.findall(matn)})


def ventas_solishtir(qurilmalar: list[Qurilma], kp: KpHujjat) -> Natija:
    """Har VENTAS qurilmasini KP dagi КЦКП qatori bilan solishtiradi."""
    natija = Natija(tz_qatorlar=len(qurilmalar), kp_qatorlar=len(kp.mahsulotlar))
    kp_qatorlar = []
    for q in kp.mahsulotlar:
        oila = kp_oilasi(q.toza_nomi)
        if oila is not None and oila.kod == "kckp":
            kp_qatorlar.append(_kckp_oqi(q))
    ishlatilgan: set[int] = set()
    oxirgi = -1

    def topish(sarf_qiymati: float) -> int | None:
        nomzodlar = [i for i, k in enumerate(kp_qatorlar)
                     if i not in ishlatilgan and k.sarf and abs(k.sarf - sarf_qiymati) < 1]
        # TZ tartibi KP tartibiga mos: oxirgi topilgandan KEYINGISI afzal.
        keyingi = [i for i in nomzodlar if i > oxirgi]
        return (keyingi or nomzodlar or [None])[0]

    topilmagan: list[Qurilma] = []
    for q in qurilmalar:
        natija.tz_guruhlar += 1
        i = topish(q.sarf)
        if i is None:
            topilmagan.append(q)
            # Topilmagan qurilma ham KP da o'z NAVBATINI egallagan bo'lishi
            # mumkin (sarfi boshqacha yozilgan). Navbatni o'tkazib yubormasak,
            # keyingi qurilma uning qatoriga ulanadi (AHU-05/06 almashgan edi).
            oxirgi += 1
            continue
        ishlatilgan.add(i)
        oxirgi = i
        # Uch damperli aralashtirishda menejer so'rgichni alohida qator qiladi.
        if "TCM" in q.kodlar:
            j = topish(q.sarf)
            if j is not None and j == i + 1:
                ishlatilgan.add(j)
                oxirgi = j
        farqlar_oldin = len(natija.farqlar)
        _qurilma_parametrlari(natija, q, kp_qatorlar[i])
        if len(natija.farqlar) == farqlar_oldin:
            natija.mos_guruhlar += 1

    qolgan = [k for i, k in enumerate(kp_qatorlar) if i not in ishlatilgan]
    for q in topilmagan:
        yaqin = next((k for k in qolgan if k.sarf and abs(k.sarf - q.sarf) <= 0.15 * q.sarf), None)
        if yaqin is not None:
            qolgan.remove(yaqin)
            natija.farqlar.append(Farq(
                PARAMETR, TEKSHIRING,
                f"{q.nomi}: TZ da sarf {q.sarf:g} m³/soat, eng yaqin KP qatori "
                f"{yaqin.qator.raqam} da {yaqin.sarf:g}", kalit=q.nomi))
            _qurilma_parametrlari(natija, q, yaqin)
        else:
            natija.farqlar.append(Farq(
                YOQ_KPDA, JIDDIY,
                f"{q.nomi} ({q.sarf:g} m³/soat, filtr: {', '.join(q.filtrlar) or '—'}) "
                "KP da yo'q", kalit=q.nomi))
    for k in qolgan:
        natija.farqlar.append(Farq(
            ORTIQCHA, MALUMOT,
            f"KP {k.qator.raqam}-qator (L={k.sarf or '?'}) TZ dagi qurilmaga bog'lanmadi"))

    natija.farqlar += kp_ichki_tekshiruv(kp)
    return natija


def _qurilma_parametrlari(natija: Natija, q: Qurilma, k: _KpKckp) -> None:
    r = k.qator.raqam
    if q.bosim and k.bosim and k.bosim < 0.9 * q.bosim:
        natija.farqlar.append(Farq(
            PARAMETR, TEKSHIRING,
            f"{q.nomi}: tashqi bosim TZ da {q.bosim:g} Pa, KP {r}-qatorda {k.bosim:g} Pa",
            kalit=q.nomi))
    # 10% dan kichik farq — tanlov dasturlari orasidagi odatiy tafovut.
    if q.isitish and k.isitish and k.isitish < 0.9 * q.isitish:
        # Rekuperatorli qurilmada TZ dagi «jami isitish» ichida rekuperator
        # hissasi bo'lishi mumkin, KP da esa faqat batareya — to'g'ridan-
        # to'g'ri solishtirib bo'lmaydi, faqat ma'lumot.
        rekuperatorli = bool({"PHE", "RAC"} & set(q.kodlar))
        natija.farqlar.append(Farq(
            PARAMETR, MALUMOT if rekuperatorli else TEKSHIRING,
            f"{q.nomi}: isitish TZ da {q.isitish:g} kVt, KP {r}-qatorda {k.isitish:g} kVt"
            + (" (rekuperatorli — TZ dagi jami quvvatga rekuperator kirganmi, tekshiring)"
               if rekuperatorli else ""),
            kalit=q.nomi))
    if q.sovutish and k.sovutish and k.sovutish < 0.9 * q.sovutish:
        natija.farqlar.append(Farq(
            PARAMETR, TEKSHIRING,
            f"{q.nomi}: sovutish TZ da {q.sovutish:g} kVt, KP {r}-qatorda {k.sovutish:g} kVt",
            kalit=q.nomi))
    tz_max = q.eng_yuqori_filtr
    if re.fullmatch(r"[GFHE]\d{1,2}", tz_max or ""):
        kp_max = max(k.filtrlar, key=_filtr_ball) if k.filtrlar else ""
        if not kp_max or _filtr_ball(kp_max) < _filtr_ball(tz_max):
            natija.farqlar.append(Farq(
                PARAMETR, JIDDIY,
                f"{q.nomi}: TZ da filtr {tz_max}"
                + (" (HEPA)" if tz_max.startswith("H") else "")
                + f", KP {r}-qatorda eng yuqorisi {kp_max or 'ko‘rsatilmagan'}",
                kalit=q.nomi))
    if "RAC" in q.kodlar and re.search(r"пластинчат", k.qator.toza_nomi, re.I):
        natija.farqlar.append(Farq(
            PARAMETR, JIDDIY,
            f"{q.nomi}: TZ da glikolli (ikki batareyali) rekuperator, KP {r}-qatorda "
            "plastinchatiy — havo oqimlari ajratilganmi, tekshiring",
            kalit=q.nomi))


# --- fayllardan --------------------------------------------------------------------


def fayllarni_tekshir(kp_yoli: str | Path,
                      tz_yollari: list[str | Path],
                      qoshimcha_qatorlar: list[TzQator] | None = None,
                      ) -> tuple[Natija | None, list[str]]:
    """KP PDF + TZ fayllari -> (natija, ogohlantirishlar).

    Natija `None` — solishtiradigan TZ topilmadi (sababi ogohlantirishda).
    Skript (`skriptlar/tz_tekshir.py`) ham, bot (`bot/tekshir_oqim.py`) ham
    shu funksiyani chaqiradi — qoidalar bitta joyda.

    `qoshimcha_qatorlar` — fayldan emas, oldindan o'qilgan TZ qatorlari
    (rasm/skan: model bilan o'qiladi, bu funksiya esa sinxron).
    DWG chizma — faqat TUR darajasida: chizmada bor, KP da butunlay yo'q.
    """
    from .kp_pdf import kp_oqi
    from .tz_jadval import jadval_oqi
    from .ventas import ventas_oqi

    kp = kp_oqi(kp_yoli)
    ogoh: list[str] = []
    if not kp.qatorlar:
        ogoh.append("KP da jadval qatorlari topilmadi — bu Climavent KP PDF imi?")
    elif not kp.yigindi_mosmi():
        ogoh.append("KP qatorlari yig'indisi «Итого» bilan mos emas — PDF to'liq "
                    "o'qilmagan bo'lishi mumkin")

    jadval_qatorlari: list[TzQator] = list(qoshimcha_qatorlar or [])
    qurilmalar: list[Qurilma] = []
    chizma_farqlari: list[Farq] = []
    for yol in map(Path, tz_yollari):
        if yol.resolve() == Path(kp_yoli).resolve():
            continue    # TZ papkasida KP ning o'zi ham turgan bo'lishi mumkin
        kengaytma = yol.suffix.lower()
        if kengaytma == ".xlsx":
            j = jadval_oqi(yol)
            jadval_qatorlari += j.qatorlar
            ogoh += [f"{yol.name}: {o}" for o in j.ogohlantirishlar]
        elif kengaytma == ".pdf":
            from .ol_pdf import ol_oqi

            q = ventas_oqi(yol)
            ol = ol_oqi(yol) if q is None else None
            if q is not None:
                qurilmalar.append(q)
            elif ol:
                jadval_qatorlari += ol
            else:
                ogoh.append(f"{yol.name}: tanlov ma'lumotnomasi emas (skan chizma yoki "
                            "boshqa PDF) — hozircha o'qilmaydi")
        elif kengaytma == ".dwg":
            from .dwg import DwgXatosi, dwg_yozuvlari, kp_bilan_farqlar, xulosa

            try:
                chizma_farqlari += kp_bilan_farqlar(xulosa(dwg_yozuvlari(yol)), kp)
            except DwgXatosi as xato:
                ogoh.append(f"{yol.name}: {xato}")
        else:
            ogoh.append(f"{yol.name}: «{kengaytma}» hozircha o'qilmaydi")

    if jadval_qatorlari:
        if qurilmalar:
            ogoh.append("TZ da ham Excel, ham tanlov PDF bor — faqat Excel solishtirildi")
        natija = solishtir(jadval_qatorlari, kp)
    elif qurilmalar:
        natija = ventas_solishtir(qurilmalar, kp)
    elif chizma_farqlari or any(Path(y).suffix.lower() == ".dwg" for y in tz_yollari):
        # Faqat chizma berilgan — jadval solishtiruvi yo'q, faqat tur darajasi.
        natija = Natija(kp_qatorlar=len(kp.mahsulotlar), farqlar=kp_ichki_tekshiruv(kp))
    else:
        return None, ogoh
    natija.farqlar += chizma_farqlari
    return natija, ogoh


# --- hisobot ------------------------------------------------------------------------

_SARLAVHA = {
    JIDDIY: "Jiddiy",
    TEKSHIRING: "Tekshiring",
    MALUMOT: "Ma'lumot uchun",
}


def hisobot(natija: Natija, sarlavha: str = "") -> str:
    """Menejer uchun matnli hisobot (Telegram / konsol)."""
    satrlar = []
    if sarlavha:
        satrlar.append(sarlavha)
    if natija.tz_guruhlar:
        satrlar.append(
            f"TZ: {natija.tz_qatorlar} qator, KP: {natija.kp_qatorlar} mahsulot qatori. "
            f"Mos guruhlar: {natija.mos_guruhlar}/{natija.tz_guruhlar} "
            f"({natija.moslik_foizi:.0f}%).")
    else:
        satrlar.append(
            f"KP: {natija.kp_qatorlar} mahsulot qatori. TZ jadvali yo'q — faqat chizmadagi "
            "uskuna TURLARI va KP ning o'zi tekshirildi.")
    for daraja in (JIDDIY, TEKSHIRING, MALUMOT):
        farqlar = [f for f in natija.farqlar if f.daraja == daraja]
        if not farqlar:
            continue
        satrlar.append("")
        satrlar.append(f"{_SARLAVHA[daraja]} ({len(farqlar)}):")
        satrlar += [f"  • {f.matn}" for f in farqlar]
    if not natija.farqlar:
        satrlar.append("Farq topilmadi.")
    return "\n".join(satrlar)

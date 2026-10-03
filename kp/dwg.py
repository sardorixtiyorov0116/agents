"""DWG chizma -> uskuna belgilari (qaysi turdan nechta YOZUV).

NEGA KERAK VA NIMA QILMAYDI
---------------------------
TZ bilan ko'pincha loyiha chizmasi (DWG) keladi: 1-juftda 3 ta seksiya,
5-juftda konditsionerlash, 7-juftda AHU P&ID (2026-10-03). Ularda
spetsifikatsiya jadvalidan tashqari ko'p narsa bor: 7-juft P&ID da
34 ta so'rish ventilyatori (EF-…, HEF-…) bor edi, KP da esa ventilyator
umuman yo'q edi.

Chizmadagi YOZUVLAR SONI — DONA SONI EMAS: bitta panjara reja va sxemada
ikki marta yoziladi, «1–8 qavat» bitta yozuv bilan beriladi. Shuning
uchun bu modul KP QORALAMASINI YASAMAYDI. U faqat:

  * `/kp` da — «chizmada qanday uskuna bor» ro'yxati (menejer uchun);
  * `/tekshir` da — chizmada bor, lekin KP da BUTUNLAY yo'q uskuna TURI.

O'QISH: DWG yopiq format. LibreDWG (`dwg2dxf`, GNU, bepul) DXF ga o'giradi,
DXF esa oddiy matn. Ruscha yozuvlar ko'pincha buzilib chiqadi («РђРњРќ») —
UTF-8 baytlari cp1251 deb o'qilgan; qaytarib tiklanadi.

Dastur: `DWG2DXF` muhit o'zgaruvchisi -> `asboblar/libredwg/dwg2dxf(.exe)`
-> tizim yo'li (`apt install libredwg-tools` kabi). Topilmasa — ochiq aytiladi.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

MUDDAT_SONIYA = 240
MAKS_YOZUV_UZUNLIGI = 160

# Chizmaga xos belgilar: oilalar jadvalida (`tz_oilalari.yaml`) ular yo'q,
# chunki TZ jadvallarida bunday yozilmaydi.
_CHIZMA_BELGILARI: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(AHU|RC)-\d+", re.I), "kckp"),
    (re.compile(r"^\s*(HEF|EF|SF)-\d+(\.\d+)?\s*$", re.I), "vent_sanoat"),
    (re.compile(r"^\s*KT(VA|YA|HA|GA)\d+", re.I), "vrf_ichki"),
    (re.compile(r"^\s*KTRV\d+", re.I), "vrf_tashqi"),
    (re.compile(r"^\s*DJR\w+", re.I), "refnet"),
]
# Oila nomlari (oilalar jadvalida bo'lmaganlari).
_QOSHIMCHA_NOMLAR = {"refnet": "VRF tarmoqlagich (refnet)"}


class DwgXatosi(RuntimeError):
    """DWG o'qilmadi — sababi menejerga aytiladi."""


@dataclass
class DwgXulosa:
    # oila kodi -> yozuvlar soni / misollar
    yozuvlar: Counter = field(default_factory=Counter)
    misollar: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    jami_yozuv: int = 0

    def oila_nomi(self, kod: str) -> str:
        from .solishtir import oilalar

        nomlar = {o.kod: o.nomi for o in oilalar()}
        return nomlar.get(kod) or _QOSHIMCHA_NOMLAR.get(kod, kod)

    def satrlar(self, eng_kam: int = 1) -> list[str]:
        return [
            f"{self.oila_nomi(kod)}: {soni} yozuv ({', '.join(self.misollar[kod][:3])})"
            for kod, soni in self.yozuvlar.most_common() if soni >= eng_kam
        ]


def dastur_yoli() -> str | None:
    if os.environ.get("DWG2DXF") and Path(os.environ["DWG2DXF"]).is_file():
        return os.environ["DWG2DXF"]
    ildiz = Path(__file__).resolve().parent.parent / "asboblar" / "libredwg"
    for nom in ("dwg2dxf.exe", "dwg2dxf"):
        if (ildiz / nom).is_file():
            return str(ildiz / nom)
    return shutil.which("dwg2dxf")


def _tikla(matn: str) -> str:
    """«РђРњРќ150С…100» -> «АМН150х100»: UTF-8 baytlari cp1251 deb o'qilgan."""
    try:
        return matn.encode("cp1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return matn


def _tozala(matn: str) -> str:
    bs = re.escape(chr(92))
    matn = re.sub(bs + r"U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), matn)
    matn = re.sub(bs + r"[ACHQTWcfFpL][^;]*;", "", matn)
    matn = re.sub(bs + r"[PN]", " ", matn)
    matn = matn.replace("{", "").replace("}", "").replace("LEADER_LINE", "")
    matn = matn.replace("%%c", "∅").replace("%%C", "∅")
    return re.sub(r"\s+", " ", matn).strip()


def dxf_yozuvlari(dxf: str | Path) -> list[str]:
    """DXF dagi TEXT / MTEXT / ATTRIB yozuvlari (model maydoni va bloklar)."""
    yozuvlar: list[str] = []
    joriy: list[str] | None = None
    with open(dxf, "rb") as f:
        qatorlar = (q.decode("utf-8", errors="replace").rstrip("\r\n") for q in f)
        for kod in qatorlar:
            qiymat = next(qatorlar, "")
            kod = kod.strip()
            if kod == "0":
                if joriy:
                    yozuvlar.append("".join(joriy))
                joriy = [] if qiymat.strip() in ("TEXT", "MTEXT", "ATTRIB") else None
            elif joriy is not None and kod in ("1", "3"):
                joriy.append(qiymat)
    if joriy:
        yozuvlar.append("".join(joriy))
    return [t for t in (_tozala(_tikla(y)) for y in yozuvlar) if t]


def dwg_yozuvlari(dwg: str | Path) -> list[str]:
    dastur = dastur_yoli()
    if dastur is None:
        raise DwgXatosi(
            "DWG o'qish dasturi (LibreDWG) o'rnatilmagan — chizmani PDF qilib yuboring")
    with tempfile.TemporaryDirectory() as papka:
        dxf = Path(papka) / "chizma.dxf"
        try:
            subprocess.run([dastur, "-y", "-o", str(dxf), str(dwg)], capture_output=True,
                           timeout=MUDDAT_SONIYA, check=False)
        except subprocess.TimeoutExpired as xato:
            raise DwgXatosi("Chizma juda katta — o'girish vaqti tugadi") from xato
        if not dxf.is_file() or dxf.stat().st_size == 0:
            raise DwgXatosi("DWG o'qilmadi (fayl buzuq yoki versiyasi qo'llanmaydi)")
        return dxf_yozuvlari(dxf)


def kp_bilan_farqlar(x: DwgXulosa, kp, eng_kam: int = 3) -> list:
    """Chizmada bor, KP da BUTUNLAY yo'q uskuna TURLARI.

    Faqat tur darajasida: «chizmada 41 ta ventilyator yozuvi, KP da birorta
    ventilyator qatori yo'q». Dona solishtirilmaydi — yozuv soni dona emas.
    `eng_kam` dan kam yozuvli tur e'tiborsiz (tasodifiy so'z mos kelishi).
    """
    from .solishtir import TEKSHIRING, YOQ_KPDA, Farq, kp_oilasi

    kp_turlari = {o.kod for o in (kp_oilasi(q.toza_nomi) for q in kp.mahsulotlar) if o}
    # Turlar o'zaro yaqin: KP da VRF ichki blok bo'lsa, refnet ham shu tizimniki.
    if {"vrf_ichki", "vrf_tashqi"} & kp_turlari:
        kp_turlari |= {"vrf_ichki", "vrf_tashqi"}
    if {"vent_sanoat", "vent_kanal"} & kp_turlari:
        kp_turlari |= {"vent_sanoat", "vent_kanal"}
    farqlar = []
    for kod, soni in x.yozuvlar.most_common():
        if soni < eng_kam or kod in kp_turlari:
            continue
        farqlar.append(Farq(
            YOQ_KPDA, TEKSHIRING,
            f"Chizmada (DWG) {x.oila_nomi(kod)}: {soni} yozuv "
            f"({', '.join(x.misollar[kod][:3])}) — KP da bu turdagi qator YO'Q "
            "(yozuv soni dona emas)", oila=kod))
    return farqlar


def xulosa(yozuvlar: list[str]) -> DwgXulosa:
    """Yozuvlarni oilalar bo'yicha sanaydi (yozuv soni — dona emas)."""
    from .solishtir import tz_oilasi

    natija = DwgXulosa(jami_yozuv=len(yozuvlar))
    for y in yozuvlar:
        if len(y) > MAKS_YOZUV_UZUNLIGI:
            continue
        kod = next((k for q, k in _CHIZMA_BELGILARI if q.search(y)), None)
        if kod is None:
            oila = tz_oilasi(y)
            kod = oila.kod if oila else None
        if kod is None:
            continue
        natija.yozuvlar[kod] += 1
        if y not in natija.misollar[kod] and len(natija.misollar[kod]) < 5:
            natija.misollar[kod].append(y[:40])
    return natija

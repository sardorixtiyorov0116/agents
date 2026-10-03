"""Tayyor tanlov ma'lumotnomasi (VENTAS HVACCALC, turkcha PDF) — o'qish.

NEGA KERAK
----------
Yirik loyihalarda TZ — bu tayyor qurilma tanlovlari: loyihachi har bir
markaziy konditsionerni (AHU) ishlab chiqaruvchi dasturida hisoblab,
6–14 betlik ma'lumotnoma beradi. Unda hamma narsa RAQAM: havo sarfi,
tashqi bosim, isitish/sovutish kVt, filtr klasslari, seksiyalar.

Menejer bundan КЦКП tanlaydi. Tekshiruvchi (`kp/solishtir.py`) esa
KP dagi КЦКП TZ talabini qondiradimi — shuni solishtiradi. Jonli holat
(2026-10-03, KP 13574): HEPA H14 tushib qolgan, glikolli rekuperator
plastinchatiga almashgan, 8 ta qurilmada bosim 2–3 barobar past.

MODEL KODI — seksiyalar ro'yxati: «Unique 10 X 12 [1825 RAC CWC HWC]».
  PHE — plastinchatiy rekuperator     RAC — glikolli (ikki batareyali)
  CWC — sovutish batareyasi           HWC — isitish batareyasi
  DCM — ikki damperli aralashtirish   TCM — uch damperli aralashtirish

DIQQAT: 1-betdagi «F9 T2 TB1» — FILTR EMAS, korpus germetikligi klassi
(EN 1886 FBL). Filtrlar faqat «Filtre Tipi» qatorlaridan olinadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SEKSIYA_KODLARI = {
    "PHE": "plastinchatiy rekuperator",
    "RAC": "glikolli rekuperator (ikki batareyali)",
    "CWC": "sovutish batareyasi",
    "HWC": "isitish batareyasi",
    "DCM": "ikki damperli aralashtirish",
    "TCM": "uch damperli aralashtirish",
}


@dataclass
class Qurilma:
    nomi: str                       # AHU-11, HEF-01, RC-01
    soni: int = 1
    model: str = ""
    kodlar: list[str] = field(default_factory=list)   # PHE, RAC, CWC …
    sarf: float = 0                 # kirish havosi, m³/soat
    qaytish_sarf: float = 0
    bosim: float = 0                # tashqi statik bosim (kirish), Pa
    qaytish_bosim: float = 0
    isitish: float = 0              # kVt
    sovutish: float = 0             # kVt
    filtrlar: list[str] = field(default_factory=list)  # G4, F7, F9, H14 …
    sorgich_bor: bool = False       # ASPİRATÖR — so'rish ventilyatori
    yol: str = ""

    @property
    def eng_yuqori_filtr(self) -> str:
        tartib = {"G": 1, "M": 2, "F": 3, "E": 4, "H": 5, "U": 6}

        def ball(f: str) -> tuple[int, int]:
            m = re.match(r"([A-Z])(\d+)", f)
            return (tartib.get(m.group(1), 0), int(m.group(2))) if m else (0, 0)

        return max(self.filtrlar, key=ball) if self.filtrlar else ""


def _son(matn: str) -> float:
    """«18.250» (turkcha minglik nuqta), «158,7» (o'nlik vergul)."""
    matn = matn.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", matn):
        return float(matn.replace(".", ""))
    return float(matn.replace(".", "").replace(",", "."))


def ventas_oqi(yol: str | Path) -> Qurilma | None:
    """Bitta ma'lumotnoma -> `Qurilma`. VENTAS hujjati bo'lmasa `None`."""
    from pypdf import PdfReader

    matn = "\n".join(b.extract_text() or "" for b in PdfReader(str(yol)).pages)
    if "Santral Adı" not in matn:
        return None

    q = Qurilma(nomi="", yol=str(yol))
    m = re.search(r"Santral Adı\s+(.+?)\s+-\s+\((\d+)\s*AD\.?\)", matn)
    if m:
        q.nomi = re.sub(r"\s+", " ", m.group(1)).strip()
        q.soni = int(m.group(2))
    m = re.search(r"Santral Modeli\s+([^\n]+)", matn)
    if m:
        q.model = m.group(1).strip()
        kv = re.search(r"\[([^\]]+)\]", q.model)
        if kv:
            q.kodlar = [k for k in kv.group(1).split() if k in SEKSIYA_KODLARI]

    m = re.search(r"Hava Debisi[^\n]*\n(?:[^\n]*\n)?\s*([\d.]+) m³/h(?:\s+([\d.]+) m³/h)?", matn)
    if m:
        q.sarf = _son(m.group(1))
        if m.group(2):
            q.qaytish_sarf = _son(m.group(2))

    m = re.search(r"Toplam Isıtma Kapasitesi[^\n]*\n\s*([\d.,]+) kW\s+([\d.,]+) kW", matn)
    if m:
        q.isitish, q.sovutish = _son(m.group(1)), _son(m.group(2))

    m = re.search(r"Cihaz Dışı Statik Basınç[^\n]*\n([^\n]+)", matn)
    if m:
        bosimlar = [_son(x) for x in re.findall(r"([\d.,]+) Pa", m.group(1))]
        if bosimlar:
            q.bosim = bosimlar[0]
        if len(bosimlar) > 1:
            q.qaytish_bosim = bosimlar[1]

    for f in re.findall(r"Filtre Tipi\s*\n?\s*([A-Za-z]+-?\s?\d{1,2})", matn):
        kod = re.sub(r"[-\s]", "", f).upper()
        if re.fullmatch(r"[GMFEHU]\d{1,2}", kod):
            q.filtrlar.append(kod)
    if re.search(r"Elektrostatik", matn, re.I):
        q.filtrlar.append("elektrostatik")
    if re.search(r"Aktif Karbon", matn, re.I):
        q.filtrlar.append("ko'mir")

    q.sorgich_bor = "ASPİRATÖR" in matn
    return q


def papka_oqi(papka: str | Path) -> list[Qurilma]:
    """Papkadagi hamma VENTAS ma'lumotnomalari, nomi bo'yicha tartibda."""
    natija = []
    for yol in sorted(Path(papka).glob("*.pdf")):
        q = ventas_oqi(yol)
        if q is not None:
            natija.append(q)
    return natija

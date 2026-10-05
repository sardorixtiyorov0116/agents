"""Rasm yoki skan qilingan TZ -> jadval qatorlari (model faqat KO'CHIRADI).

NEGA KERAK
----------
TZ ko'pincha skrinshot bo'lib keladi (KP-13357 «Нирвана» ro'yxati — Excel
dan olingan surat) yoki skan PDF bo'lib (2-juft — loyiha chizmalari).
Ularda matn yo'q: `pypdf` ham, `openpyxl` ham hech narsa o'qimaydi.

MODEL FAQAT KO'CHIRADI
----------------------
Rasm tanish modeli (Gemini) jadvalni QATORMA-QATOR ko'chiradi: guruh
sarlavhasi, nom, birlik, miqdor. U Climavent nomiga AYLANTIRMAYDI va
hech narsa TANLAMAYDI — bu ish keyin kodda, Excel bilan bir xil yo'lda
(`kp/tz_qoralama.py`). Shunda model xatosi faqat «noto'g'ri o'qilgan
raqam» bo'lishi mumkin, «o'ylab topilgan model» emas.

Har qator miqdori menejerga ko'rsatiladi va «rasmdan o'qildi —
tekshiring» deb belgilanadi: o'qishdagi xato (8 va 3, 1 va 7) KP ga
jimgina tushmasin.

Faqat GEMINI modellari ishlatiladi: zanjirdagi boshqa modellar (Groq)
rasm qabul qilmaydi, Anthropic kaliti esa hozir yaroqsiz.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .tz_jadval import TzQator

RASM_KENGAYTMALARI = {".png": "image/png", ".jpg": "image/jpeg",
                      ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAKS_SAHIFA = 4                 # shundan ko'p sahifa bo'lsa — avval jadval sahifalari tanlanadi
MAKS_PDF_SAHIFA = 40            # skan PDF dan ko'riladigan sahifalar
MAKS_JADVAL_SAHIFA = 12         # tanlangandan keyin ko'chiriladigan sahifalar (kvota)
RENDER_PIKSEL = 2200            # render qilingan varaqning uzun tomoni
MAKS_HAJM = 8 * 1024 * 1024     # bitta rasm
MIN_HAJM = 20 * 1024            # bundan kichigi — muhr/belgi, varaq emas


class RasmXatosi(ValueError):
    """Rasm o'qilmadi — sababi menejerga aytiladi."""


class RasmQator(BaseModel):
    guruh: str = ""
    nomi: str = ""
    birlik: str = ""
    miqdor: float = 0


class RasmNatija(BaseModel):
    qatorlar: list[RasmQator] = Field(default_factory=list)
    izoh: str = ""


TIZIM_PROMPT = """Sen rasmdagi JADVALNI KO'CHIRASAN. Boshqa hech narsa.

VAZIFA: texnik topshiriq (spetsifikatsiya, ro'yxat) rasmidagi har bir
mahsulot qatorini ko'chirish: nomi, o'lchov birligi, miqdori.

QAT'IY QOIDALAR:
1) HARFMA-HARF ko'chirasan. Tarjima qilmaysan, tuzatmaysan, qisqartmani
   ochmaysan: «Клпн 1000x400» qanday bo'lsa shunday.
2) Miqdorni FAQAT rasmda yozilgan raqamdan olasan. O'qib bo'lmasa 0 qo'yasan.
3) Miqdorsiz sarlavha qatori («Решетка АДН», «Клпн ДКС») — mahsulot EMAS.
   U keyingi qatorlarning `guruh` maydoniga yoziladi.
4) Tartib raqami ustunini (№) ko'chirmaysan.
5) Jadval yo'q yoki o'qib bo'lmasa — bo'sh ro'yxat va `izoh` ga sababi.
6) Hech qanday mahsulot, model yoki raqam O'YLAB TOPMAYSAN.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi JSON obyekti bilan ber, boshqa matnsiz:
{
  "qatorlar": [
    {"guruh": "miqdorsiz sarlavha yoki bo'sh", "nomi": "rasmdagi nom",
     "birlik": "шт", "miqdor": 57}
  ],
  "izoh": "o'qilmagan joylar yoki bo'sh"
}"""


def rasmlar(yol: str | Path) -> list[tuple[bytes, str]]:
    """Fayldan rasmlar: (baytlar, mime). Rasm fayli yoki skan PDF sahifalari.

    Matnli PDF uchun BO'SH ro'yxat: uni rasm qilib modelga berish shart
    emas — matni boshqa yo'l bilan o'qiladi.
    """
    yol = Path(yol)
    kengaytma = yol.suffix.lower()
    if kengaytma in RASM_KENGAYTMALARI:
        if yol.stat().st_size > MAKS_HAJM:
            raise RasmXatosi(f"Rasm juda katta ({yol.stat().st_size // 1024 // 1024} MB)")
        return [(yol.read_bytes(), RASM_KENGAYTMALARI[kengaytma])]
    if kengaytma != ".pdf":
        return []

    from pypdf import PdfReader

    sahifalar = PdfReader(str(yol)).pages[:MAKS_PDF_SAHIFA]
    for sahifa in sahifalar[:MAKS_SAHIFA]:
        if (sahifa.extract_text() or "").strip():
            return []           # matnli PDF — skan emas
    # Sahifa RENDER qilinadi. Skanerlar varaqni qatlamlab siqadi (MRC: fon
    # + matn niqobi alohida rasmlar) — «eng katta rasm» ko'pincha matnsiz
    # fon bo'lib chiqardi (2-juft loyihasi: jadval ramkasi bor, yozuv yo'q).
    try:
        return _render(yol, len(sahifalar))
    except ImportError:
        pass
    natija: list[tuple[bytes, str]] = []
    for sahifa in sahifalar:
        # Sahifada bir nechta rasm bo'lishi mumkin (muhr, belgi — 200 bayt,
        # 2 KB). Skan varag'i — ENG KATTASI.
        sahifa_rasmlari = [r for r in sahifa.images if MIN_HAJM <= len(r.data) <= MAKS_HAJM]
        if sahifa_rasmlari:
            rasm = max(sahifa_rasmlari, key=lambda r: len(r.data))
            mime = "image/png" if rasm.name.lower().endswith(".png") else "image/jpeg"
            natija.append((rasm.data, mime))
    return natija


def _render(yol: Path, soni: int) -> list[tuple[bytes, str]]:
    import io

    import pypdfium2 as pdfium

    hujjat = pdfium.PdfDocument(str(yol))
    natija: list[tuple[bytes, str]] = []
    try:
        for i in range(min(soni, len(hujjat))):
            sahifa = hujjat[i]
            en, boy = sahifa.get_size()
            rasm = sahifa.render(scale=RENDER_PIKSEL / max(en, boy)).to_pil().convert("L")
            bufer = io.BytesIO()
            rasm.save(bufer, "JPEG", quality=80)
            natija.append((bufer.getvalue(), "image/jpeg"))
    finally:
        hujjat.close()
    return natija


TANLASH_PROMPT = """Senga loyiha varaqlari kichraytirilgan holda beriladi (1 dan boshlab raqamlangan).
Qaysi varaqlarda USKUNA/MAHSULOT SPETSIFIKATSIYASI JADVALI bor — nomi, birligi,
miqdori ustunlari bilan («Спецификация», «Наименование и техническая
характеристика», «Ведомость оборудования»)? Chizma, sxema, muqova, umumiy
ma'lumot varaqlarini OLMA. Javob FAQAT JSON: {"varaqlar": [3, 4, 5]}"""


class Tanlov(BaseModel):
    varaqlar: list[int] = Field(default_factory=list)


async def jadval_varaqlari(bolaklar: list[tuple[bytes, str]], llm: Any) -> list[int]:
    """Ko'p varaqli skan loyihadan spetsifikatsiya varaqlari (0 dan indeks)."""
    import io

    from PIL import Image

    from app.llm import json_ajrat, matn_yig

    kontent: list[dict[str, Any]] = []
    for i, (baytlar, _) in enumerate(bolaklar, 1):
        rasm = Image.open(io.BytesIO(baytlar))
        rasm.thumbnail((900, 900))
        bufer = io.BytesIO()
        rasm.convert("L").save(bufer, "JPEG", quality=70)
        kontent += [{"type": "text", "text": f"{i}-varaq:"},
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": base64.b64encode(bufer.getvalue()).decode("ascii")}}]
    kontent.append({"type": "text", "text": "Spetsifikatsiya varaqlari raqamlari?"})
    javob = await llm.javob(system=TANLASH_PROMPT, messages=[{"role": "user", "content": kontent}])
    tanlov = Tanlov.model_validate(json_ajrat(matn_yig(javob)))
    return sorted({v - 1 for v in tanlov.varaqlar if 1 <= v <= len(bolaklar)})


def rasm_modellari(modellar: list[str]) -> list[str]:
    """Zanjirdan faqat rasm qabul qiladigan modellar (Gemini)."""
    from app.llm import provayder

    return [m for m in modellar if provayder(m) == "gemini"]


async def rasmdan_qatorlar(yol: str | Path, llm: Any) -> tuple[list[TzQator], list[str]]:
    """Rasm/skan -> (TZ qatorlari, ogohlantirishlar). `llm` — Gemini (zanjir)."""
    from app.llm import json_ajrat, matn_yig

    bolaklar = rasmlar(yol)
    if not bolaklar:
        raise RasmXatosi("Faylda rasm topilmadi")

    qatorlar: list[TzQator] = []
    ogohlar: list[str] = []
    raqamlar = list(range(len(bolaklar)))
    if len(bolaklar) > MAKS_SAHIFA:
        # Loyiha to'plami (muqova, chizmalar, spetsifikatsiya) — avval
        # jadval varaqlari tanlanadi, faqat ular ko'chiriladi (kvota).
        raqamlar = await jadval_varaqlari(bolaklar, llm)
        if not raqamlar:
            raise RasmXatosi(f"{len(bolaklar)} varaqda spetsifikatsiya jadvali topilmadi")
        if len(raqamlar) > MAKS_JADVAL_SAHIFA:
            ogohlar.append(f"{len(raqamlar)} ta jadval varag'idan birinchi "
                           f"{MAKS_JADVAL_SAHIFA} tasi o'qildi")
            raqamlar = raqamlar[:MAKS_JADVAL_SAHIFA]
        ogohlar.append(f"{len(bolaklar)} varaqdan spetsifikatsiya: "
                       + ", ".join(str(r + 1) for r in raqamlar) + "-varaqlar")
    for i in (r + 1 for r in raqamlar):
        baytlar, mime = bolaklar[i - 1]
        javob = await llm.javob(
            system=TIZIM_PROMPT,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": mime,
                    "data": base64.b64encode(baytlar).decode("ascii")}},
                {"type": "text", "text": JSON_SKELET},
            ]}],
        )
        natija = RasmNatija.model_validate(json_ajrat(matn_yig(javob)))
        if natija.izoh:
            ogohlar.append(f"{i}-rasm: {natija.izoh}")
        for r in natija.qatorlar:
            nomi = re.sub(r"\s+", " ", r.nomi).strip()
            if not nomi:
                continue
            if r.miqdor <= 0:
                ogohlar.append(f"«{nomi[:50]}»: miqdori o'qilmadi — qator olinmadi")
                continue
            qatorlar.append(TzQator(
                nomi=nomi, miqdor=float(r.miqdor), birlik=r.birlik.strip(),
                guruh=r.guruh.strip(), matn=nomi, varaq=f"rasm {i}"))
    if qatorlar:
        ogohlar.insert(0, f"{len(qatorlar)} qator RASMDAN o'qildi — nom va miqdorlarni "
                          "asl rasm bilan solishtiring")
    return qatorlar, ogohlar

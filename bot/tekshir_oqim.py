"""`/tekshir` — tayyor KP ni TZ bilan solishtirish (ichki bot).

NEGA KERAK
----------
Menejer KP ni qo'lda tuzadi va mijozga yuboradi. Haqiqiy 7 juftda
(2026-10-03) deyarli har birida TZ bilan farq chiqdi: KP ga kirmagan
qurilma, almashgan o'lcham, tushib qolgan HEPA filtr, nusxa qilingan
tavsif. `/tekshir` shuni KP mijozga ketishidan OLDIN ko'rsatadi.

OQIM
----
  1. `/tekshir` — seans ochiladi.
  2. Menejer fayllarni tashlaydi: KP (PDF) va TZ (Excel yoki VENTAS PDF,
     bir nechta bo'lishi mumkin). Har fayl tanilib, nima ekani aytiladi.
  3. «Tekshirish» tugmasi (yoki yana `/tekshir`) — farqlar ro'yxati.

HECH NARSA TUZATILMAYDI va hech narsa mijozga yuborilmaydi — bu faqat
menejer uchun ro'yxat. Farqning bir qismi ongli qaror bo'lishi mumkin.

Seans XOTIRADA turadi (bot qayta ishga tushsa yo'qoladi — fayllarni
qaytadan tashlash kifoya) va 30 daqiqadan keyin eskiradi. Fayllar
tekshiruvdan keyin O'CHIRILADI: ular mijoz hujjatlari, saqlashga sabab yo'q.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import sozlama

log = logging.getLogger(__name__)

MUDDAT_SONIYA = 30 * 60
MAKS_FAYL = 40                    # VENTAS papkasida 23 ta PDF bo'ladi
MAKS_HAJM = 20 * 1024 * 1024      # Telegram bot API chegarasi
TELEGRAM_CHEGARA = 3800           # bitta xabar (4096) — zaxira bilan

TUGMA_TEKSHIR = "tekshir:boshla"
TUGMA_BEKOR = "tekshir:bekor"


@dataclass
class Seans:
    papka: Path
    kp: Path | None = None
    kp_tavsif: str = ""
    tz: list[Path] = field(default_factory=list)
    tz_tavsif: list[str] = field(default_factory=list)
    # Rasm / skan TZ — tekshiruv paytida model bilan o'qiladi.
    rasmlar: list[Path] = field(default_factory=list)
    boshlangan: float = field(default_factory=time.monotonic)

    @property
    def tz_soni(self) -> int:
        return len(self.tz) + len(self.rasmlar)

    @property
    def eskirganmi(self) -> bool:
        return time.monotonic() - self.boshlangan > MUDDAT_SONIYA


_seanslar: dict[int, Seans] = {}


def _tugmalar() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tekshirish", callback_data=TUGMA_TEKSHIR),
        InlineKeyboardButton("❌ Bekor", callback_data=TUGMA_BEKOR),
    ]])


def _yop(tg_id: int) -> None:
    seans = _seanslar.pop(tg_id, None)
    if seans is not None:
        shutil.rmtree(seans.papka, ignore_errors=True)


def faolmi(tg_id: int) -> bool:
    seans = _seanslar.get(tg_id)
    if seans is not None and seans.eskirganmi:
        _yop(tg_id)
        return False
    return seans is not None


async def boshla(xabar, tg_id: int) -> None:
    """`/tekshir`. Seans ochiq va fayl bor bo'lsa — darhol tekshiradi."""
    if faolmi(tg_id) and _seanslar[tg_id].kp is not None and _seanslar[tg_id].tz_soni:
        await ishga_tushir(xabar, tg_id)
        return
    _yop(tg_id)
    papka = Path(sozlama().kp_papkasi) / "tekshir" / f"{tg_id}_{int(time.time())}"
    papka.mkdir(parents=True, exist_ok=True)
    _seanslar[tg_id] = Seans(papka=papka)
    await xabar.reply_text(
        "🔎 KP ni TZ bilan solishtiraman.\n\n"
        "Fayllarni tashlang:\n"
        "• KP — Climavent KP PDF (bitta)\n"
        "• TZ — Excel (spetsifikatsiya, ro'yxat, zayavka) yoki VENTAS tanlov PDF "
        "(bir nechta bo'lishi mumkin)\n\n"
        "Rasm va skan PDF ham bo'ladi (jadval o'qiladi). DWG chizma — faqat uskuna "
        "TURLARI solishtiriladi. Arxiv (zip/rar) — ochib yuboring.\n"
        "Tashlab bo'lgach «Tekshirish» ni bosing.\n\n"
        "Hech narsa tuzatilmaydi va mijozga yuborilmaydi — faqat farqlar ro'yxati.",
        reply_markup=_tugmalar(),
    )


def _tani(yol: Path) -> tuple[str, str]:
    """Fayl turi: ("kp" | "tz" | "rasm" | "", tavsif). Sinxron — thread da chaqiriladi."""
    from kp.kp_pdf import kp_oqi
    from kp.ol_pdf import ol_oqi
    from kp.tz_jadval import jadval_oqi
    from kp.tz_rasm import RASM_KENGAYTMALARI, rasmlar
    from kp.ventas import ventas_oqi

    kengaytma = yol.suffix.lower()
    if kengaytma == ".dwg":
        from kp.dwg import dastur_yoli

        if dastur_yoli() is None:
            return "", "DWG o'qish dasturi (LibreDWG) o'rnatilmagan — PDF qilib yuboring"
        return "tz", "chizma (DWG) — uskuna TURLARI solishtiriladi"
    if kengaytma in RASM_KENGAYTMALARI:
        return "rasm", "rasm — jadval tekshiruvda o'qiladi"
    from kp.tz_jadval import JADVAL_KENGAYTMALARI

    if kengaytma in JADVAL_KENGAYTMALARI:
        j = jadval_oqi(yol)
        if not j.qatorlar:
            return "", "; ".join(j.ogohlantirishlar) or "jadval topilmadi"
        tur = "Excel" if kengaytma.startswith(".xls") else "Word"
        return "tz", f"TZ ({tur}): {len(j.qatorlar)} qator"
    if kengaytma == ".pdf":
        q = ventas_oqi(yol)
        if q is not None:
            return "tz", f"TZ (tanlov): {q.nomi}, {q.sarf:g} m³/soat"
        try:
            kp = kp_oqi(yol)
        except Exception:      # noqa: BLE001 — buzuq PDF: shunchaki tanilmadi
            kp = None
        if kp is not None and kp.raqam and kp.qatorlar:
            mijoz = f", {kp.mijoz}" if kp.mijoz else ""
            return "kp", f"KP №{kp.raqam}{mijoz} — {len(kp.mahsulotlar)} mahsulot qatori"
        ol = ol_oqi(yol)
        if ol:
            return "tz", f"TZ (so'rovnoma varaqasi): {len(ol)} qator"
        if rasmlar(yol):
            return "rasm", "skan PDF — jadval tekshiruvda o'qiladi"
        return "", "na KP, na TZ jadvali"
    return "", f"«{kengaytma}» o'qilmaydi (arxivni ochib, ichidagi fayllarni yuboring)"


async def hujjat(xabar, tg_id: int, fayl, fayl_nomi: str, hajm: int = 0) -> bool:
    """Seans ochiq bo'lsa faylni oladi. `True` — fayl shu oqimga tegishli."""
    if not faolmi(tg_id):
        return False
    seans = _seanslar[tg_id]
    if seans.tz_soni + (1 if seans.kp else 0) >= MAKS_FAYL:
        await xabar.reply_text(f"⚠️ {MAKS_FAYL} tadan ko'p fayl olinmaydi — «Tekshirish» ni bosing.")
        return True
    if hajm and hajm > MAKS_HAJM:
        await xabar.reply_text(f"⚠️ {fayl_nomi}: fayl {MAKS_HAJM // 1024 // 1024} MB dan katta.")
        return True

    # Telegram rasmlari hammasi «rasm.jpg» bo'lib keladi — tartib raqami
    # nomlar to'qnashmasligi uchun.
    yol = seans.papka / f"{sum(1 for _ in seans.papka.iterdir()) + 1:02d}_{Path(fayl_nomi).name}"
    try:
        await fayl.download_to_drive(str(yol))
    except Exception as xato:                       # noqa: BLE001
        log.exception("tekshir: fayl yuklab olinmadi")
        await xabar.reply_text(f"⚠️ {fayl_nomi}: faylni olib bo'lmadi: {xato}")
        return True

    try:
        turi, tavsif = await asyncio.to_thread(_tani, yol)
    except Exception as xato:                       # noqa: BLE001
        log.exception("tekshir: fayl o'qilmadi")
        turi, tavsif = "", f"o'qib bo'lmadi: {xato}"

    if turi == "kp":
        if seans.kp is not None:
            tavsif += " (oldingi KP o'rniga)"
        seans.kp, seans.kp_tavsif = yol, tavsif
    elif turi == "tz":
        seans.tz.append(yol)
        seans.tz_tavsif.append(tavsif)
    elif turi == "rasm":
        seans.rasmlar.append(yol)
        seans.tz_tavsif.append(tavsif)
    else:
        await xabar.reply_text(f"⚠️ {fayl_nomi}: {tavsif}")
        return True

    holat = [f"✓ {fayl_nomi}: {tavsif}", ""]
    holat.append(f"KP: {seans.kp_tavsif or '— hali yo‘q'}")
    holat.append(f"TZ fayllari: {seans.tz_soni}")
    await xabar.reply_text("\n".join(holat), reply_markup=_tugmalar())
    return True


def _bolaklar(matn: str) -> list[str]:
    """Telegram chegarasidan oshmasin — qatorlar bo'yicha bo'linadi."""
    natija, joriy = [], ""
    for satr in matn.split("\n"):
        if len(joriy) + len(satr) + 1 > TELEGRAM_CHEGARA and joriy:
            natija.append(joriy)
            joriy = ""
        joriy += satr + "\n"
    if joriy.strip():
        natija.append(joriy)
    return natija


async def ishga_tushir(xabar, tg_id: int) -> None:
    from kp.solishtir import fayllarni_tekshir, hisobot

    if not faolmi(tg_id):
        await xabar.reply_text("Seans yo'q yoki eskirgan — /tekshir dan boshlang.")
        return
    seans = _seanslar[tg_id]
    if seans.kp is None or not seans.tz_soni:
        yetishmaydi = "KP (PDF)" if seans.kp is None else "TZ fayli"
        await xabar.reply_text(f"⚠️ Hali {yetishmaydi} yo'q — faylni tashlang.",
                               reply_markup=_tugmalar())
        return

    await xabar.reply_text("⏳ Solishtirilmoqda…")
    # Rasm / skan TZ — model faqat jadvalni ko'chiradi (`kp/tz_rasm.py`);
    # `/kp` dagi bilan bir xil funksiya (faqat Gemini).
    rasm_qatorlari: list = []
    rasm_ogohlari: list[str] = []
    for rasm in seans.rasmlar:
        from bot import kp_oqim

        try:
            qatorlar, ogohlar = await kp_oqim._rasm_ajrat(rasm)
            rasm_qatorlari += qatorlar
            rasm_ogohlari += ogohlar
        except Exception as xato:                   # noqa: BLE001
            log.warning("tekshir: rasm o'qilmadi", exc_info=True)
            rasm_ogohlari.append(f"rasm o'qilmadi: {xato}")
    try:
        natija, ogoh = await asyncio.to_thread(
            fayllarni_tekshir, seans.kp, seans.tz, rasm_qatorlari)
        ogoh = rasm_ogohlari + ogoh
    except Exception as xato:                       # noqa: BLE001
        log.exception("tekshir: solishtirishda xato")
        await xabar.reply_text(f"⚠️ Solishtirib bo'lmadi: {xato}")
        return
    finally:
        kp_tavsif = seans.kp_tavsif
        _yop(tg_id)

    satrlar = [f"! {o}" for o in ogoh]
    if natija is None:
        satrlar.append("Solishtiradigan TZ topilmadi.")
    else:
        satrlar.append(hisobot(natija, f"🔎 {kp_tavsif}"))
    for bolak in _bolaklar("\n".join(satrlar)):
        await xabar.reply_text(bolak)


async def tugma(soro, tg_id: int) -> None:
    if soro.data == TUGMA_BEKOR:
        _yop(tg_id)
        await soro.edit_message_text("Tekshiruv bekor qilindi.")
        return
    if soro.data == TUGMA_TEKSHIR:
        await ishga_tushir(soro.message, tg_id)


async def bekor(xabar, tg_id: int) -> bool:
    """`/bekor` — seans ochiq bo'lsa yopadi. `True` — yopildi."""
    if not faolmi(tg_id):
        return False
    _yop(tg_id)
    await xabar.reply_text("Tekshiruv bekor qilindi.")
    return True

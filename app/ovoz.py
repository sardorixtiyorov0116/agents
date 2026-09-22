"""Ovozli xabar bilan ishlash: eshitish va gapirish.

NEGA GEMINI, ALOHIDA XIZMAT EMAS
--------------------------------
Ovozni matnga o'girish uchun odatda alohida xizmat qo'yiladi (Whisper,
Yandex SpeechKit). Bizga kerak emas: Gemini allaqachon ulangan va
o'zbekchani to'g'ri tushunadi.

O'LCHANDI (2026-09-05): 10 soniyalik o'zbekcha ovozli xabar aynan
o'girildi va «ikki yuz» -> «200», «yuz ellik» -> «150» qilib raqamga
aylantirildi — bu hisob moduliga kerak bo'lgan shakl. Narxi 331 token.

CHEGARALAR
----------
Uzun ovozli xabar qimmat va odatda ichida bir nechta savol bo'ladi —
model ularni chalkashtiradi. Shuning uchun `MAKS_SONIYA` dan uzunini
qabul qilmaymiz va buni foydalanuvchiga OCHIQ aytamiz.

JIM QOLMASLIK
-------------
Ovoz o'girilmasa yoki kvota tugasa — foydalanuvchi sababini biladi.
Eng yomon holat: mijoz ovoz yubordi, bot jim qoldi. Avval shunday edi
(botda ovoz ishlovchisi umuman yo'q edi).
"""

from __future__ import annotations

import base64
import logging
import re
import struct
from dataclasses import dataclass
from typing import Any

import httpx

from .config import sozlama
from .sarf import qayd_bilan

log = logging.getLogger("ovoz")

ASOS = "https://generativelanguage.googleapis.com/v1beta/models"

# Eshitish uchun oddiy suhbat modeli yetadi — alohida STT modeli shart emas.
ESHITISH_MODELI = "gemini-3.5-flash"
# Gapirish uchun alohida TTS modeli kerak.
GAPIRISH_MODELI = "gemini-3.1-flash-tts-preview"
OVOZ_NOMI = "Kore"

MAKS_SONIYA = 120          # undan uzun ovozli xabar qabul qilinmaydi
MAKS_BAYT = 8 * 1024 * 1024
KUTISH = 90.0

# TTS xom PCM qaytaradi — WAV sarlavhasi qo'lda yoziladi.
PCM_CHASTOTA = 24000

KORSATMA = (
    "Bu ovozli xabarni AYNAN eshitilganidek matnga aylantir. "
    "Til — o'zbekcha (ruscha so'zlar aralashishi mumkin). "
    "Sonlarni RAQAM bilan yoz. Izoh qo'shma, faqat matnni ber."
)


class OvozXatosi(RuntimeError):
    """Ovozni o'girib yoki yasab bo'lmadi."""


@dataclass
class _Sarf:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _Javob:
    """`sarf.qayd_bilan` token sanashi uchun minimal shakl."""

    usage: _Sarf


def _tokenlar(xom: dict[str, Any]) -> _Sarf:
    olcham = xom.get("usageMetadata") or {}
    return _Sarf(
        input_tokens=int(olcham.get("promptTokenCount") or 0),
        output_tokens=int(olcham.get("candidatesTokenCount") or 0),
    )


def _matn_ajrat(xom: dict[str, Any]) -> str:
    for nomzod in xom.get("candidates") or []:
        for qism in (nomzod.get("content") or {}).get("parts") or []:
            if qism.get("text"):
                return str(qism["text"]).strip()
    return ""


def _audio_ajrat(xom: dict[str, Any]) -> bytes:
    for nomzod in xom.get("candidates") or []:
        for qism in (nomzod.get("content") or {}).get("parts") or []:
            ichki = qism.get("inlineData") or qism.get("inline_data") or {}
            if ichki.get("data"):
                return base64.b64decode(ichki["data"])
    return b""


async def _sorov(model: str, tana: dict[str, Any]) -> dict[str, Any]:
    kalit = (sozlama().gemini_api_key or "").strip()
    if not kalit:
        raise OvozXatosi("Gemini kaliti qo'yilmagan — ovoz ishlamaydi")

    xom: dict[str, Any] = {}

    async def chaqir() -> _Javob:
        nonlocal xom
        async with httpx.AsyncClient(timeout=KUTISH) as mijoz:
            javob = await mijoz.post(
                f"{ASOS}/{model}:generateContent",
                params={"key": kalit}, json=tana,
            )
        if javob.status_code >= 400:
            raise OvozXatosi(
                f"{model}: HTTP {javob.status_code} {javob.text[:160]}")
        xom = javob.json()
        return _Javob(usage=_tokenlar(xom))

    await qayd_bilan("gemini", model, chaqir)
    return xom


async def matnga(audio: bytes, mime: str = "audio/ogg") -> str:
    """Ovozli xabarni matnga o'giradi.

    Bo'sh natija ham XATO deb qaraladi: mijozga «tushunmadim» deyish
    kerak, jim qolish emas.
    """
    if not audio:
        raise OvozXatosi("ovoz fayli bo'sh")
    if len(audio) > MAKS_BAYT:
        raise OvozXatosi("ovoz fayli juda katta")

    tana = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": KORSATMA},
                {"inline_data": {"mime_type": mime,
                                 "data": base64.b64encode(audio).decode()}},
            ],
        }]
    }
    matn = _matn_ajrat(await _sorov(ESHITISH_MODELI, tana))
    if not matn:
        raise OvozXatosi("ovozdan matn chiqmadi")
    return matn


# Ovozga o'giriladigan matn uzunligi.
#
# Uzun javobni o'qib berish foydasizdan ham yomon: mijoz uni to'xtata
# olmaydi, orqaga qaytara olmaydi va jadval-ro'yxatni quloq bilan
# tushunmaydi. To'liq matn baribir xabar sifatida turadi — ovoz esa
# uning boshi. O'lchandi: bir gap ~5 soniya sintez qilinadi.
GAPIRISH_CHEGARASI = 600

# «Batafsil: https://…» — yorliq havola bilan BIRGA olib tashlanadi.
# Aks holda ovozda osilib qolgan «Batafsil:» eshitiladi.
_YORLIQLI_HAVOLA = re.compile(r"[^\s.!?]+:\s*https?://\S+")

# Ovozda o'qilmasligi kerak bo'lgan bezaklar.
_BEZAK = re.compile(r"[*_`#>\[\]]|—\s*—\s*—|https?://\S+")
_KOP_BOSHLIQ = re.compile(r"\s+")
_TINISH_OLDI = re.compile(r"\s+([.,!?;:])")


def gapirish_uchun(matn: str) -> str:
    """Javob matnini ovoz uchun tozalaydi va qisqartiradi.

    Markdown belgilari, havolalar va ajratgich chiziqlar olib tashlanadi —
    ular ovozda ma'nosiz shovqin bo'lib eshitiladi.
    """
    xom = _YORLIQLI_HAVOLA.sub(" ", matn or "")
    toza = _KOP_BOSHLIQ.sub(" ", _BEZAK.sub(" ", xom)).strip()
    # Bezak olib tashlangach «12 mln .» kabi bo'shliq qoladi — ovozda
    # bu joyda g'alati pauza eshitiladi.
    toza = _TINISH_OLDI.sub(r"\1", toza).strip(" :–-")
    if len(toza) <= GAPIRISH_CHEGARASI:
        return toza
    # Gap oxirida kesamiz — yarim gap ovozda juda bilinadi.
    kesik = toza[:GAPIRISH_CHEGARASI]
    for belgi in (". ", "! ", "? "):
        joy = kesik.rfind(belgi)
        if joy > GAPIRISH_CHEGARASI // 2:
            return kesik[:joy + 1].strip()
    return kesik.rsplit(" ", 1)[0].strip()


def _wav(pcm: bytes, chastota: int = PCM_CHASTOTA) -> bytes:
    """Xom PCM ga WAV sarlavhasi qo'shadi (16 bit, mono)."""
    return (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, chastota, chastota * 2, 2, 16)
        + b"data" + struct.pack("<I", len(pcm)) + pcm
    )


async def ovozga(matn: str) -> bytes:
    """Matndan ovoz yasaydi. WAV qaytaradi (Telegram o'zi o'giradi)."""
    matn = (matn or "").strip()
    if not matn:
        raise OvozXatosi("bo'sh matndan ovoz yasab bo'lmaydi")

    tana = {
        "contents": [{"parts": [{"text": matn}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": OVOZ_NOMI}}
            },
        },
    }
    pcm = _audio_ajrat(await _sorov(GAPIRISH_MODELI, tana))
    if not pcm:
        raise OvozXatosi("model ovoz qaytarmadi")
    return _wav(pcm)

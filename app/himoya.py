"""Panel himoyasi — serverga chiqarishdan oldin qo'shildi.

MUAMMO
------
Panel (`/`, `/panel`, `/ofis`, `/izlar`, `/sorov`) hech qanday parolsiz
ochiq edi. Mahalliy kompyuterda bu muammo emas — unga faqat o'zingiz
kirasiz. Serverda esa manzilni bilgan HAR KIM ko'radi:

  - `/izlar` — barcha so'rovlar va javoblar (mijoz nomi, KP mazmuni);
  - `/sorov` — agentlarni ISHGA TUSHIRADI, ya'ni begona odam sizning
    Anthropic hisobingizdan pul sarflaydi;
  - `/tasdiq/{id}` — inson tasdig'ini bosib yuborishi mumkin.

QOIDA (fail-closed)
-------------------
`PANEL_PAROLI` qo'yilgan bo'lsa — HTTP Basic parol so'raladi.
Qo'yilmagan bo'lsa — faqat MAHALLIY ulanishga (127.0.0.1) ruxsat,
tashqaridan kelgan so'rov 403 oladi va sababini aytadi.

Ya'ni parolni qo'yishni unutsangiz ham ma'lumot ochilib qolmaydi.

`/salomat` ochiq qoladi: konteyner sog'ligini tekshiruvchi (Docker,
Railway) parol bilan kira olmaydi. U yerda maxfiy ma'lumot yo'q —
model nomi va "ulangan/ulanmagan" holati.
"""

from __future__ import annotations

import base64
import hmac
import ipaddress
import logging

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import sozlama

log = logging.getLogger("himoya")

# Parolsiz ochiq qoladigan yo'llar.
OCHIQ = ("/salomat",)

# Foydalanuvchi nomi — parol bilan solishtiriladi, o'zi sir emas.
FOYDALANUVCHI = "jihozvent"

MAHALLIY_XABAR = (
    "Panel tashqaridan yopiq. Ochish uchun serverda PANEL_PAROLI "
    "muhit o'zgaruvchisini qo'ying."
)


def _mahalliymi(mijoz: str | None) -> bool:
    if not mijoz:
        return False
    try:
        manzil = ipaddress.ip_address(mijoz)
    except ValueError:
        return False
    return manzil.is_loopback


def _parol_togrimi(sarlavha: str | None, parol: str) -> bool:
    """HTTP Basic sarlavhasini tekshiradi (vaqt bo'yicha xavfsiz)."""
    if not sarlavha or not sarlavha.lower().startswith("basic "):
        return False
    try:
        ochilgan = base64.b64decode(sarlavha[6:].strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    nomi, _, berilgan = ochilgan.partition(":")
    # `compare_digest` — parolni belgima-belgi solishtirish vaqti bo'yicha
    # aniqlab olishning oldini oladi.
    return hmac.compare_digest(nomi, FOYDALANUVCHI) and hmac.compare_digest(
        berilgan, parol
    )


class PanelHimoyasi(BaseHTTPMiddleware):
    """Parol yoki mahalliy ulanish — boshqasiga ruxsat yo'q."""

    async def dispatch(self, request: Request, keyingi):  # type: ignore[override]
        yol = request.url.path
        if yol.startswith(OCHIQ):
            return await keyingi(request)

        parol = (sozlama().panel_paroli or "").strip()
        if not parol:
            if _mahalliymi(request.client.host if request.client else None):
                return await keyingi(request)
            log.warning("parolsiz panelga tashqaridan urinish: %s", yol)
            return JSONResponse({"xato": MAHALLIY_XABAR}, status_code=403)

        if _parol_togrimi(request.headers.get("authorization"), parol):
            return await keyingi(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Jihozvent agentlar"'},
        )

"""Botning xato ishlovchisi.

MUAMMO (2026-08-11, jonli log): O'zbekistondan Telegram'ga ulanish
vaqti-vaqti bilan uziladi. `python-telegram-bot` o'zi qayta urinadi va
tiklanadi — ya'ni bu XATO EMAS, oddiy tarmoq shovqini. Lekin xato
ishlovchisi ro'yxatdan o'tmagani uchun har uzilishda **30 qatorli
traceback** yozilardi:

    ERROR telegram.ext.Application - No error handlers are registered...
    Traceback (most recent call last):
      ... 25 qator ...
    telegram.error.NetworkError: httpx.ReadError:

Kuniga bir necha marta takrorlansa log shu tracebacklar bilan to'lib
ketadi va HAQIQIY xato ko'rinmay qoladi.

Endi:
  - tarmoq/timeout xatolari — BITTA qator ogohlantirish;
  - boshqasi — to'liq traceback (u chindan tekshirilishi kerak).

Foydalanuvchiga xabar YUBORILMAYDI: tarmoq uzilganda xabar baribir
yetib bormaydi, yetib borsa ham "tarmoq sekin" degan xabar foydasiz.
"""

from __future__ import annotations

import logging

from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, ContextTypes

log = logging.getLogger("bot.xato")

# DIQQAT: `isinstance(..., NetworkError)` ISHLATIB BO'LMAYDI.
#
# `python-telegram-bot` da xatolar ierarxiyasi shunday:
#     TelegramError
#       └── NetworkError
#             ├── BadRequest   <- HAQIQIY xato ("chat topilmadi")
#             └── TimedOut     <- tarmoq
#
# Ya'ni `isinstance(xato, NetworkError)` `BadRequest` ni ham tutadi va
# haqiqiy xato bir qatorlik "tarmoq uzildi" ogohlantirishi ostida
# ko'milib ketadi. Shuning uchun TURI AYNAN solishtiriladi.
TIKLANADIGAN_TURLAR = (NetworkError, TimedOut)


def tiklanadimi(xato: BaseException | None) -> bool:
    """Xato o'z-o'zidan tiklanadimi (tarmoq shovqinimi)."""
    return type(xato) in TIKLANADIGAN_TURLAR


async def xatoni_yoz(_update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    xato = ctx.error
    if tiklanadimi(xato):
        log.warning("tarmoq uzildi (%s: %s) — qayta urinilmoqda",
                    type(xato).__name__, xato)
        return
    log.error("kutilmagan xato", exc_info=xato)


def ulash(ilova: Application) -> Application:
    """Xato ishlovchisini botga ulaydi."""
    ilova.add_error_handler(xatoni_yoz)
    return ilova

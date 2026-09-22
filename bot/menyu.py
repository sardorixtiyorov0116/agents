"""Telegramda "/" bosilganda chiqadigan buyruqlar menyusi.

MUAMMO
------
Buyruqlar `CommandHandler` bilan ulangan edi, lekin Telegramga
"menda shu buyruqlar bor" deb AYTILMAGAN. Natijada "/" bosilganda
pastdan hech narsa chiqmasdi va menejer buyruqlarni yod bilishi
kerak edi.

YECHIM
------
`set_my_commands` — bot ishga tushganda bir marta yuboriladi.
Telegram ro'yxatni o'zida saqlaydi.

KIM NIMANI KO'RADI
------------------
Ichki bot faqat xodimlar uchun. Begona odam botni topib "/" bossa,
ichki buyruqlar ro'yxatini ko'rmasligi kerak — shuning uchun:

    umumiy ko'rinish (hamma)      -> bo'sh
    har bir ruxsat etilgan xodim  -> to'liq ro'yxat

Mijozlar boti ochiq, unda umumiy ro'yxat qo'yiladi.

DIQQAT: ro'yxat bot ishga tushganda yuboriladi. `.env` dagi ruxsat
ro'yxatiga yangi xodim qo'shilsa, tizim qayta ishga tushishi kerak —
`.env` ham baribir qayta o'qilmaydi.
"""

from __future__ import annotations

import logging

from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

log = logging.getLogger("bot.menyu")

# Ichki bot — menejerlar uchun. Tartib menyuda ko'rinadigan tartib:
# eng ko'p ishlatiladigani tepada.
ICHKI: list[tuple[str, str]] = [
    ("start", "Boshlash — yangi mavzu"),
    ("kp", "KP tuzish — savol-javob bilan"),
    ("hisobot", "Hisobot — tizim qancha ish qildi"),
    ("tasdiq", "Tasdiq kutayotgan ishlar"),
    ("tender", "Tenderlarni hozir tekshirish"),
    ("murojaatlar", "Mijozlar botidagi savollar"),
    ("sorovnomalar", "To'ldirilgan oprosniy listlar"),
    ("menejer", "KP da chiqadigan ism va telefon"),
    ("sarf", "LLM sarfi — limitga qancha qolgan"),
    ("agentlar", "Agentlar ro'yxati va vazifasi"),
    ("bekor", "Joriy ishni bekor qilish"),
]

# Mijozlar boti — ochiq. Faqat ikkita buyruq bor.
MIJOZ: list[tuple[str, str]] = [
    ("start", "Boshlash — yangi savol"),
    ("bolimlar", "Uskunalar ro'yxati"),
    ("savat", "So'rovim — to'plangan uskunalar"),
    ("aloqa", "Telefon raqamimni qoldirish"),
    ("help", "Yordam"),
]


def _buyruqlar(royxat: list[tuple[str, str]]) -> list[BotCommand]:
    return [BotCommand(nom, izoh) for nom, izoh in royxat]


async def ichkini_qoy(bot, ruxsat_etilgan) -> int:
    """Ichki bot menyusi — faqat ruxsat etilgan xodimlarga.

    Natija: nechta xodimga qo'yilgani.
    """
    buyruqlar = _buyruqlar(ICHKI)

    # Begona odam "/" bossa bo'sh ko'rsin.
    try:
        await bot.set_my_commands([], scope=BotCommandScopeDefault())
    except Exception as xato:
        log.warning("umumiy menyuni tozalab bo'lmadi: %s", xato)

    qoyildi = 0
    for tg_id in ruxsat_etilgan:
        try:
            await bot.set_my_commands(
                buyruqlar, scope=BotCommandScopeChat(chat_id=tg_id)
            )
            qoyildi += 1
        except Exception as xato:
            # Odatiy sabab: xodim botni hali ochmagan ("chat not found").
            # Bu xato emas — u /start bosgach menyu o'zi paydo bo'ladi
            # (keyingi ishga tushishda qo'yiladi). Bot to'xtamasin.
            log.info("menyu qo'yilmadi (id=%s): %s", tg_id, xato)

    log.info("ichki menyu: %d/%d xodimga qo'yildi", qoyildi, len(ruxsat_etilgan))
    return qoyildi


async def mijozniki_qoy(bot) -> None:
    """Mijozlar boti menyusi — hammaga ko'rinadi."""
    try:
        await bot.set_my_commands(
            _buyruqlar(MIJOZ), scope=BotCommandScopeDefault()
        )
        log.info("mijoz menyusi qo'yildi: %d buyruq", len(MIJOZ))
    except Exception as xato:
        log.warning("mijoz menyusi qo'yilmadi: %s", xato)

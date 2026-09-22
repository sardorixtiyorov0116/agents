"""Bot xato ishlovchisi.

JONLI LOG (2026-08-11): O'zbekistondan Telegram'ga ulanish uzilganda
har safar 30 qatorli traceback yozilardi, chunki xato ishlovchisi
ro'yxatdan o'tmagan edi. `python-telegram-bot` bunday xatodan o'zi
tiklanadi — ya'ni traceback keraksiz, u faqat logni ko'madi.
"""

from __future__ import annotations

import logging

import pytest
from telegram.error import BadRequest, NetworkError, TimedOut

from bot import xatolar


class SoxtaKontekst:
    def __init__(self, xato):
        self.error = xato


@pytest.mark.asyncio
@pytest.mark.parametrize("xato", [
    NetworkError("httpx.ReadError: "),
    TimedOut(),
])
async def test_tarmoq_xatosi_bitta_qator(caplog, xato):
    with caplog.at_level(logging.WARNING, logger="bot.xato"):
        await xatolar.xatoni_yoz(None, SoxtaKontekst(xato))

    yozuvlar = [q for q in caplog.records if q.name == "bot.xato"]
    assert len(yozuvlar) == 1
    assert yozuvlar[0].levelno == logging.WARNING
    assert yozuvlar[0].exc_info is None, "traceback yozilib qoldi"
    assert "qayta urinilmoqda" in yozuvlar[0].getMessage()


@pytest.mark.asyncio
async def test_boshqa_xato_toliq_yoziladi(caplog):
    """Haqiqiy xato yashirilmasin — u tekshirilishi kerak."""
    with caplog.at_level(logging.ERROR, logger="bot.xato"):
        await xatolar.xatoni_yoz(None, SoxtaKontekst(BadRequest("chat topilmadi")))

    yozuvlar = [q for q in caplog.records if q.name == "bot.xato"]
    assert len(yozuvlar) == 1
    assert yozuvlar[0].levelno == logging.ERROR
    assert yozuvlar[0].exc_info is not None, "traceback yo'q"


def test_ikkala_bot_ham_ishlovchini_ulaydi():
    """Ulash unutilmasin — jonli xato aynan shundan chiqqan edi."""
    import inspect

    import bot.asosiy
    import bot.mijoz

    for modul in (bot.asosiy, bot.mijoz):
        manba = inspect.getsource(modul.yasa)
        assert "xatolar.ulash" in manba, f"{modul.__name__}: ishlovchi ulanmagan"


def test_badrequest_networkerror_avlodi():
    """Filtr `isinstance` bilan yozilsa haqiqiy xato yashirinib qoladi.

    Bu test kutubxona ierarxiyasini QOTIRIB qo'yadi: agar kelajakda
    o'zgarsa, filtrni qayta ko'rib chiqish kerakligini eslatadi.
    """
    assert issubclass(BadRequest, NetworkError), (
        "ierarxiya o'zgardi — `bot/xatolar.py` dagi filtrni qayta ko'ring"
    )
    assert issubclass(TimedOut, NetworkError)


@pytest.mark.parametrize("xato,kutilgan", [
    (NetworkError("uzildi"), True),
    (TimedOut(), True),
    # HAQIQIY xatolar — yashirilmasin.
    (BadRequest("chat topilmadi"), False),
])
def test_qaysi_xato_tiklanadi(xato, kutilgan):
    assert xatolar.tiklanadimi(xato) is kutilgan


@pytest.mark.asyncio
async def test_ikki_bot_bir_vaqtda_ishlasa_koriladi(caplog):
    """`Conflict` — ikkita nusxa bir vaqtda polling qilyapti.

    Bu jimgina o'tib ketmasligi kerak: javob bir kelib, bir kelmaydi.
    """
    from telegram.error import Conflict

    with caplog.at_level(logging.ERROR, logger="bot.xato"):
        await xatolar.xatoni_yoz(None, SoxtaKontekst(Conflict("terminated by other")))

    yozuvlar = [q for q in caplog.records if q.name == "bot.xato"]
    assert len(yozuvlar) == 1
    assert yozuvlar[0].levelno == logging.ERROR

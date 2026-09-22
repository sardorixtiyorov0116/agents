"""Telegram "/" menyusi.

Buyruqlar `CommandHandler` bilan ulangan edi, lekin Telegramga
aytilmagan — shuning uchun "/" bosilganda hech narsa chiqmasdi.
"""

from __future__ import annotations

import inspect
import re

import pytest

from bot import menyu


class SoxtaTelegram:
    """`set_my_commands` chaqiruvlarini yozib boradi."""

    def __init__(self, yiqiladigan: set[int] | None = None):
        self.chaqiruvlar: list[tuple[list, object]] = []
        self.yiqiladigan = yiqiladigan or set()

    async def set_my_commands(self, buyruqlar, scope=None):
        chat_id = getattr(scope, "chat_id", None)
        if chat_id in self.yiqiladigan:
            raise RuntimeError("Chat not found")
        self.chaqiruvlar.append((list(buyruqlar), scope))


# --- ichki bot ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_har_xodimga_qoyiladi():
    tg = SoxtaTelegram()

    qoyildi = await menyu.ichkini_qoy(tg, {111, 222})

    assert qoyildi == 2
    chatlar = {getattr(s, "chat_id", None) for _, s in tg.chaqiruvlar}
    assert chatlar == {None, 111, 222}


@pytest.mark.asyncio
async def test_begona_odam_bosh_royxat_koradi():
    """Ichki buyruqlar hammaga ko'rinib turmasin."""
    tg = SoxtaTelegram()

    await menyu.ichkini_qoy(tg, {111})

    umumiy = [b for b, s in tg.chaqiruvlar if getattr(s, "chat_id", None) is None]
    assert umumiy == [[]], "umumiy ko'rinishda buyruq qolmasligi kerak"


@pytest.mark.asyncio
async def test_botni_ochmagan_xodim_yiqitmaydi():
    """"Chat not found" — bu xato emas, bot to'xtamasin."""
    tg = SoxtaTelegram(yiqiladigan={222})

    qoyildi = await menyu.ichkini_qoy(tg, {111, 222})

    assert qoyildi == 1


@pytest.mark.asyncio
async def test_ruxsat_bosh_bolsa_yiqilmaydi():
    tg = SoxtaTelegram()
    assert await menyu.ichkini_qoy(tg, set()) == 0


@pytest.mark.asyncio
async def test_umumiy_royxat_yiqilsa_ham_davom_etadi():
    """Umumiy ko'rinish qo'yilmasa ham xodimlarga qo'yilsin."""

    class Yarim(SoxtaTelegram):
        async def set_my_commands(self, buyruqlar, scope=None):
            if getattr(scope, "chat_id", None) is None:
                raise RuntimeError("tarmoq")
            await super().set_my_commands(buyruqlar, scope)

    assert await menyu.ichkini_qoy(Yarim(), {111}) == 1


# --- mijozlar boti ------------------------------------------------------------


@pytest.mark.asyncio
async def test_mijoz_menyusi_hammaga_koinadi():
    tg = SoxtaTelegram()

    await menyu.mijozniki_qoy(tg)

    assert len(tg.chaqiruvlar) == 1
    buyruqlar, scope = tg.chaqiruvlar[0]
    assert getattr(scope, "chat_id", None) is None
    assert [b.command for b in buyruqlar] == [
        "start", "bolimlar", "savat", "aloqa", "help"]


# --- ro'yxat haqiqatga mos keladimi -------------------------------------------


def _ulangan_buyruqlar(manba: str) -> set[str]:
    """`CommandHandler([...])` va `CommandHandler("...")` dan nomlarni yig'adi."""
    nomlar: set[str] = set()
    for xom in re.findall(r"CommandHandler\(\s*(\[[^\]]*\]|\"[^\"]+\")", manba):
        nomlar.update(re.findall(r'"([^"]+)"', xom))
    return nomlar


def test_ichki_menyudagi_buyruqlar_ulangan():
    """MUHIM: menyuda bor, lekin ishlamaydigan buyruq bo'lmasin.

    Bunday buyruq bosilsa bot jim qoladi va menejer buzuq deb o'ylaydi.
    """
    import bot.asosiy as modul

    ulangan = _ulangan_buyruqlar(inspect.getsource(modul.yasa))
    assert ulangan, "CommandHandler topilmadi — test eskirgan"

    for nom, _ in menyu.ICHKI:
        assert nom in ulangan, f"/{nom} menyuda bor, lekin ulanmagan"


def test_mijoz_menyudagi_buyruqlar_ulangan():
    import bot.mijoz as modul

    ulangan = _ulangan_buyruqlar(inspect.getsource(modul.yasa))
    for nom, _ in menyu.MIJOZ:
        assert nom in ulangan, f"/{nom} menyuda bor, lekin ulanmagan"


def test_izohlar_telegram_chegarasiga_sigadi():
    """Telegram: nom 1-32 belgi, izoh 1-256 belgi, nom kichik harf."""
    for royxat in (menyu.ICHKI, menyu.MIJOZ):
        for nom, izoh in royxat:
            assert re.fullmatch(r"[a-z0-9_]{1,32}", nom), f"noto'g'ri nom: {nom}"
            assert 1 <= len(izoh) <= 256, f"izoh uzunligi: {nom}"


def test_takrorlanmas_nomlar():
    for royxat in (menyu.ICHKI, menyu.MIJOZ):
        nomlar = [n for n, _ in royxat]
        assert len(nomlar) == len(set(nomlar))


def test_botlarga_ulangan():
    """Menyu chaqiruvi `post_init` da turibdimi — ulash unutilmasin."""
    import bot.asosiy
    import bot.mijoz

    assert "menyu.ichkini_qoy" in inspect.getsource(bot.asosiy.yasa)
    assert "menyu.mijozniki_qoy" in inspect.getsource(bot.mijoz.yasa)

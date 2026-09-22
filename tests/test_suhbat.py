"""Suhbat konteksti — bot savol berganda javob kontekstsiz qolmasin.

Jonli sinovda topilgan nuqson:

    mijoz: "Ofis uchun ventilyatsiya kerak, 120 kv metr"
    bot:   "Balandligi qancha? Necha kishi?"
    mijoz: "3 metr, 15 kishi"
    bot:   "Xona maydoni qancha?"        <- 120 m² unutilgan

Bu mijoz uchun cheksiz halqa edi va tizimning eng qimmatli agentini
(Rustam) real suhbatda ishlatib bo'lmasdi.
"""

from __future__ import annotations

import pytest

from app.baza import SUHBAT_MAKS_QADAM, Baza
from app.konvert import Holat, Ishonch, Konvert, Manba
from app.orkestr import Natija
from bot import suhbat


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "suhbat.db")
    await b.tayyorla()
    return b


def natija_yasa(holat: Holat, savollar: list[str] | None = None) -> Natija:
    return Natija(
        sorov="sinov",
        davomiylik_ms=0,
        yakuniy=Konvert(
            kim="hvac-calc",
            holat=holat,
            ishonch=Ishonch.YUQORI,
            natija={"savollar": savollar or []},
            # `TUGADI` uchun manba majburiy (konvert qoidasi).
            manba=[Manba(tur="kontrakt", nom="hvac-calc kontrakti")],
        ),
    )


# --- birlashtirish ------------------------------------------------------------


def test_ikki_qism_belgilanadi():
    """Router qaysi qism yangi ekanini ko'rishi kerak."""
    matn = suhbat.birlashtir("Ofis 120 m²", "3 metr balandlik")

    assert suhbat.OLDINGI in matn
    assert suhbat.YANGI in matn
    assert matn.index(suhbat.OLDINGI) < matn.index(suhbat.YANGI)


@pytest.mark.asyncio
async def test_kontekst_yoq_bolsa_xabar_ozgarmaydi(baza):
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Ombor 500 m²")

    assert davom.sorov == "Ombor 500 m²"
    assert davom.davomimi is False
    assert davom.qadam == 1


@pytest.mark.asyncio
async def test_savol_berilgach_keyingi_xabar_birlashadi(baza):
    """Asosiy holat — busiz mijoz bir xil savolni qayta eshitadi."""
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Ofis, 120 kv metr")
    await suhbat.yakunla(
        baza, suhbat.MIJOZ, 1, davom,
        natija_yasa(Holat.ANIQLIK_KERAK, ["Balandligi qancha?"]),
    )

    keyingi = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "3 metr, 15 kishi")

    assert keyingi.davomimi is True
    assert "120 kv metr" in keyingi.sorov
    assert "3 metr, 15 kishi" in keyingi.sorov
    assert keyingi.qadam == 2


@pytest.mark.asyncio
async def test_javob_berilgach_ham_kontekst_qoladi(baza):
    """Mijoz javobdan keyin aniqlashtiradi: "balandligini 4 metr qilsak?"

    Kontekst tozalansa, bu gap ma'nosini yo'qotadi.
    """
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Oshxona 80 m², 3.5 m")
    await suhbat.yakunla(baza, suhbat.MIJOZ, 1, davom, natija_yasa(Holat.TUGADI))

    keyingi = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "balandligini 4 metr qilsak")

    assert keyingi.davomimi is True
    assert "80 m²" in keyingi.sorov


# --- kontekst QACHON tozalanadi -----------------------------------------------


@pytest.mark.parametrize("holat", [Holat.XATO, Holat.MOS_AGENT_YOQ, Holat.ULANMAGAN])
@pytest.mark.asyncio
async def test_muvaffaqiyatsiz_natija_kontekstni_tozalaydi(baza, holat):
    """Javob berilmagan bo'lsa, keyingi savol eskisiga yopishmasin."""
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Narxi qancha?")
    await suhbat.yakunla(baza, suhbat.MIJOZ, 1, davom, natija_yasa(holat))

    keyingi = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Ombor 500 m²")

    assert keyingi.davomimi is False


@pytest.mark.asyncio
async def test_tozala_yangi_mavzu_boshlaydi(baza):
    """`/start` va salomlashish — eski zanjir uzilsin."""
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Ofis 120 m²")
    await suhbat.yakunla(baza, suhbat.MIJOZ, 1, davom, natija_yasa(Holat.TUGADI))

    await suhbat.tozala(baza, suhbat.MIJOZ, 1)

    assert (await suhbat.boshla(baza, suhbat.MIJOZ, 1, "salom")).davomimi is False


# --- chegaralar ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_suhbat_cheksiz_uzaymaydi(baza):
    """Chegarasiz so'rov matni o'sib, har chaqiruvda ko'proq token yeydi."""
    for qadam in range(SUHBAT_MAKS_QADAM + 2):
        davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, f"xabar {qadam}")
        await suhbat.yakunla(
            baza, suhbat.MIJOZ, 1, davom, natija_yasa(Holat.ANIQLIK_KERAK, ["?"])
        )
        assert davom.qadam <= SUHBAT_MAKS_QADAM


@pytest.mark.asyncio
async def test_juda_uzun_suhbat_qaytadan_boshlanadi(baza):
    uzun = "a" * (suhbat.MAKS_UZUNLIK - 10)
    await baza.suhbat_yoz(suhbat.MIJOZ, 1, uzun, "", 1)

    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "yangi xabar")

    assert davom.davomimi is False
    assert davom.sorov == "yangi xabar"


@pytest.mark.asyncio
async def test_eskirgan_kontekst_ishlatilmaydi(baza):
    """Ertaga yozilgan xabar kechagi so'rovga yopishib qolmasligi kerak."""
    import sqlite3

    await baza.suhbat_yoz(suhbat.MIJOZ, 1, "Ofis 120 m²", "", 1)
    with sqlite3.connect(baza.yol) as u:
        u.execute(
            "UPDATE suhbat_konteksti SET yangilandi = ?",
            ("2020-01-01T00:00:00+00:00",),
        )

    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 1, "Ombor 500 m²")

    assert davom.davomimi is False


@pytest.mark.asyncio
async def test_ikki_bot_suhbati_aralashmaydi(baza):
    """Bir odam ikkala botga yozishi mumkin."""
    davom = await suhbat.boshla(baza, suhbat.MIJOZ, 5, "Ofis 120 m²")
    await suhbat.yakunla(baza, suhbat.MIJOZ, 5, davom, natija_yasa(Holat.TUGADI))

    ichki = await suhbat.boshla(baza, suhbat.ICHKI, 5, "Raqiblarni ko'r")

    assert ichki.davomimi is False
    assert (await suhbat.boshla(baza, suhbat.MIJOZ, 5, "…")).davomimi is True


# --- router qoidasi -----------------------------------------------------------


def test_routerda_suhbat_qoidasi_bor():
    """Belgilar qo'yilgani yetarli emas — router ularni tushunishi kerak."""
    from app.router import TIZIM_PROMPT

    tekis = " ".join(TIZIM_PROMPT.split())
    assert "SUHBAT DAVOMI" in tekis
    assert suhbat.OLDINGI in tekis
    assert suhbat.YANGI in tekis
    # Mavzu o'zgarishi qoidasi
    assert "TASHLAB YUBOR" in tekis

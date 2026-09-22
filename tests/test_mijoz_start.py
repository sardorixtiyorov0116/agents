"""Support bot: birinchi kirish -> raqam -> bo'limlar.

NEGA BU TESTLAR BOR
-------------------
JONLI E'TIROZ (2026-08-28): ilgari `/start` bosilganda salom, raqam
tugmasi va bo'limlar ro'yxati BIR VAQTDA chiqardi. Mijoz uchta narsani
birdan ko'rib, qaysi biridan boshlashni bilmasdi. Pastdagi «telefon
raqamimni yuborish» tugmasi esa raqam berilgandan KEYIN ham osilib
turaverardi — ya'ni bot allaqachon bilgan narsani qayta so'rayotgandek
ko'rinardi.

Endi bir vaqtda BITTA ish bo'ladi va raqam BIR MARTA so'raladi.
"""

from __future__ import annotations

import pytest
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.baza import Baza
from bot.mijoz import (
    ALOQA_RAHMAT,
    KEYINROQ_JAVOBI,
    TUGMA_KEYINROQ,
    TUGMA_TELEFON,
    MijozBot,
)

TG = 9090


@pytest.fixture
async def baza(tmp_path):
    b = Baza(yol=tmp_path / "sinov.db")
    await b.tayyorla()
    return b


class Foydalanuvchi:
    id = TG
    full_name = "Yangi Mijoz"
    username = "yangi_mijoz"


class Kontakt:
    phone_number = "+998901234567"


class Chat:
    id = TG

    async def send_action(self, *a, **k):
        pass


class Xabar:
    def __init__(self, kontakt=None, text=""):
        self.contact = kontakt
        self.text = text
        self.chat = Chat()
        self.javoblar: list[tuple[str, object]] = []

    async def reply_text(self, matn, reply_markup=None, **k):
        self.javoblar.append((matn, reply_markup))
        return self

    async def edit_text(self, matn, **k):
        self.javoblar.append((matn, None))
        return self


class Update:
    def __init__(self, xabar, foydalanuvchi=None):
        self.effective_message = xabar
        self.effective_user = foydalanuvchi or Foydalanuvchi()


def _bot(baza):
    bot = MijozBot.__new__(MijozBot)
    bot.baza = baza
    bot._ichki_bot = None
    bot.telefon = "+998 78 150 00 07"
    bot.kompaniya_nomi = "Climavent"
    bot.tezlik = type("T", (), {"ruxsatmi": lambda self, i: True})()

    class S:
        mijoz_menejer_idlar: set[int] = set()
        bot_maks_belgi = 3000

    bot.s = S()
    return bot


def _klaviaturalar(xabar):
    return [m for _, m in xabar.javoblar]


def _tugma_matnlari(markup):
    if not isinstance(markup, ReplyKeyboardMarkup):
        return []
    return [t.text for qator in markup.keyboard for t in qator]


# --- Birinchi kirish ----------------------------------------------------------


@pytest.mark.asyncio
async def test_birinchi_startda_RAQAM_soraladi(baza):
    bot = _bot(baza)
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    matn, markup = xabar.javoblar[0]
    assert "telefon raqamingizni qoldiring" in matn
    assert TUGMA_TELEFON in _tugma_matnlari(markup)


@pytest.mark.asyncio
async def test_birinchi_startda_bolimlar_HALI_korsatilmaydi(baza):
    """Bir vaqtda bitta ish: avval raqam, keyin uskuna."""
    bot = _bot(baza)
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    assert len(xabar.javoblar) == 1
    assert "Qaysi uskuna kerak" not in xabar.javoblar[0][0]


@pytest.mark.asyncio
async def test_raqamsiz_davom_etish_TAKLIF_qilinadi(baza):
    """Majburiy qilsak, raqam bermoqchi bo'lmagan mijoz butunlay ketardi."""
    bot = _bot(baza)
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    assert TUGMA_KEYINROQ in _tugma_matnlari(xabar.javoblar[0][1])


# --- Raqam berilgach ----------------------------------------------------------


@pytest.mark.asyncio
async def test_raqam_kelgach_klaviatura_OLIB_TASHLANADI(baza):
    bot = _bot(baza)
    xabar = Xabar(kontakt=Kontakt())

    await bot.kontakt(Update(xabar), None)

    _, markup = xabar.javoblar[0]
    assert isinstance(markup, ReplyKeyboardRemove)


@pytest.mark.asyncio
async def test_raqam_kelgach_bolimlar_KORSATILADI(baza):
    bot = _bot(baza)
    xabar = Xabar(kontakt=Kontakt())

    await bot.kontakt(Update(xabar), None)

    assert ALOQA_RAHMAT in xabar.javoblar[0][0]
    assert "Qaysi uskuna kerak" in xabar.javoblar[1][0]


@pytest.mark.asyncio
async def test_raqam_BAZAGA_saqlanadi(baza):
    bot = _bot(baza)

    await bot.kontakt(Update(Xabar(kontakt=Kontakt())), None)

    yozuv = await baza.aloqa(TG)
    assert yozuv["telefon"] == "+998901234567"


# --- Ikkinchi kirish ----------------------------------------------------------


@pytest.mark.asyncio
async def test_ikkinchi_startda_raqam_QAYTA_SORALMAYDI(baza):
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Yangi Mijoz")
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    matnlar = " ".join(m for m, _ in xabar.javoblar)
    assert "raqamingizni qoldiring" not in matnlar
    assert TUGMA_TELEFON not in matnlar


@pytest.mark.asyncio
async def test_ikkinchi_startda_saqlangan_raqam_KORSATILADI(baza):
    """Mijoz bizda qaysi raqam turganini bilsin."""
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Yangi Mijoz")
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    assert "+998901234567" in xabar.javoblar[0][0]


@pytest.mark.asyncio
async def test_ikkinchi_startda_DARHOL_bolimlar(baza):
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Yangi Mijoz")
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    assert "Qaysi uskuna kerak" in xabar.javoblar[1][0]


@pytest.mark.asyncio
async def test_ikkinchi_startda_eski_klaviatura_OLIB_TASHLANADI(baza):
    """Tugma oldingi seansdan osilib qolgan bo'lishi mumkin."""
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Yangi Mijoz")
    xabar = Xabar()

    await bot.boshla(Update(xabar), None)

    assert isinstance(xabar.javoblar[0][1], ReplyKeyboardRemove)


# --- «Keyinroq» ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyinroq_bosilsa_bolimlar_ochiladi(baza):
    bot = _bot(baza)
    xabar = Xabar(text=TUGMA_KEYINROQ)

    await bot.sorov(Update(xabar), None)

    assert KEYINROQ_JAVOBI in xabar.javoblar[0][0]
    assert "Qaysi uskuna kerak" in xabar.javoblar[1][0]


@pytest.mark.asyncio
async def test_keyinroq_klaviaturani_OLIB_TASHLAYDI(baza):
    bot = _bot(baza)
    xabar = Xabar(text=TUGMA_KEYINROQ)

    await bot.sorov(Update(xabar), None)

    assert isinstance(xabar.javoblar[0][1], ReplyKeyboardRemove)


@pytest.mark.asyncio
async def test_keyinroq_SOROVNOMA_javobiga_tushmaydi(baza):
    """Ochiq so'rovnoma bo'lsa ham tugma matni javob bo'lib yozilmasin."""
    from sorovnoma import oqim as sn

    bot = _bot(baza)
    await sn.boshla(baza, TG, "panjara")
    xabar = Xabar(text=TUGMA_KEYINROQ)

    await bot.sorov(Update(xabar), None)

    shakl = await sn.joriy_shakl(baza, TG)
    assert shakl.javoblar == {}


@pytest.mark.asyncio
async def test_keyinroqdan_keyin_aloqa_buyrugi_ISHLAYDI(baza):
    """Mijoz fikrini o'zgartirsa yo'l ochiq qolsin."""
    bot = _bot(baza)
    xabar = Xabar()

    await bot.aloqa_buyrugi(Update(xabar), None)

    assert TUGMA_TELEFON in _tugma_matnlari(xabar.javoblar[0][1])


@pytest.mark.asyncio
async def test_aloqa_buyrugi_hozirgi_raqamni_korsatadi(baza):
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Yangi Mijoz")
    xabar = Xabar()

    await bot.aloqa_buyrugi(Update(xabar), None)

    assert "+998901234567" in xabar.javoblar[0][0]


# --- Har mijoz alohida --------------------------------------------------------


@pytest.mark.asyncio
async def test_boshqa_mijozdan_raqam_QAYTA_soraladi(baza):
    """Bir mijozning raqami boshqasiga tegishli emas."""
    bot = _bot(baza)
    await baza.aloqa_yoz(TG, "+998901234567", "Birinchi")

    class Boshqa:
        id = 9091
        full_name = "Ikkinchi"
        username = None

    xabar = Xabar()
    await bot.boshla(Update(xabar, Boshqa()), None)

    assert TUGMA_TELEFON in _tugma_matnlari(xabar.javoblar[0][1])


# --- Tezlik chegaralari -------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-28): mijoz «Biroz sekinroq yozing» degan javob
# olardi. Ikkita alohida xato bor edi:
#
# 1. Chegara SO'ROVNOMADAN OLDIN tekshirilardi. So'rovnoma LLM umuman
#    ishlatmaydi — u sof shakl to'ldirish. 7 savolli so'rovnomani bir
#    daqiqada to'ldirish MUMKIN EMAS bo'lib qolgandi, va savat ham
#    ko'rinmasdi, chunki oqim o'rtada to'xtardi.
#
# 2. Chegara 5 edi. Uskuna qidirayotgan odam bir daqiqada 6-7 savol
#    berishi normal.


@pytest.mark.asyncio
async def test_SOROVNOMA_javoblari_tezlik_chegarasiga_KIRMAYDI(baza):
    """So'rovnoma LLM ishlatmaydi — chegara unga tegmasin."""
    from sorovnoma import oqim as sn

    bot = _bot(baza)
    # Chegarani ATAYLAB bittaga tushiramiz.
    from bot.mijoz_ruxsat import Tezlik

    bot.tezlik = Tezlik(1)
    await sn.boshla(baza, TG, "panjara")

    javoblar = []
    for javob in ("500x300", "9016", "14"):
        shakl = await sn.joriy_shakl(baza, TG)
        if shakl is None or shakl.tugadimi():
            break
        if shakl.joriy().tanlovlar:
            await sn.javobni_qabul_qil(baza, TG, shakl, "РВН")
            continue
        xabar = Xabar(text=javob)
        await bot.sorov(Update(xabar), None)
        javoblar += [m for m, _ in xabar.javoblar]

    assert not any("sekinroq" in m for m in javoblar)


@pytest.mark.asyncio
async def test_erkin_matn_chegaraga_KIRADI(baza):
    """Chegara LLM xarajatini himoya qiladi — u yo'qolmasin."""
    from bot.mijoz_ruxsat import Tezlik

    bot = _bot(baza)
    bot.tezlik = Tezlik(1)

    await bot.sorov(Update(Xabar(text="kanal ventilyatori bormi")), None)
    ikkinchi = Xabar(text="narxi qancha")
    await bot.sorov(Update(ikkinchi), None)

    assert any("sekinroq" in m for m, _ in ikkinchi.javoblar)


def test_daqiqalik_chegara_ODAM_uriladigan_darajada_EMAS():
    """6-7 savol bir daqiqada — normal xatti-harakat."""
    from app.config import sozlama

    assert sozlama().mijoz_bot_limit >= 10


def test_KUNLIK_chegara_bor():
    """Gemini bepul tarifida kuniga jami 20 ta so'rov — bitta odam
    butun kvotani yeb qo'ymasin."""
    from app.config import sozlama

    assert 0 < sozlama().mijoz_kunlik_limit < 20


def test_kunlik_chegara_ISHLAYDI():
    from bot.mijoz_ruxsat import Tezlik

    t = Tezlik(100, kunlik=3)

    assert [t.kunlik_ruxsatmi(1) for _ in range(5)] == [True, True, True, False, False]


def test_kunlik_chegara_har_mijozga_ALOHIDA():
    from bot.mijoz_ruxsat import Tezlik

    t = Tezlik(100, kunlik=2)
    t.kunlik_ruxsatmi(1)
    t.kunlik_ruxsatmi(1)

    assert t.kunlik_ruxsatmi(1) is False
    assert t.kunlik_ruxsatmi(2) is True


def test_kunlik_NOL_bolsa_chegara_yoq():
    from bot.mijoz_ruxsat import Tezlik

    t = Tezlik(100, kunlik=0)

    assert all(t.kunlik_ruxsatmi(1) for _ in range(50))


@pytest.mark.asyncio
async def test_kunlik_chegarada_mijoz_QURUQ_qaytarilmaydi(baza):
    """Savol menejerga yuboriladi — mijoz javobsiz qolmasin."""
    from bot.mijoz_ruxsat import Tezlik

    bot = _bot(baza)
    bot.tezlik = Tezlik(100, kunlik=1)

    await bot.sorov(Update(Xabar(text="birinchi savol")), None)
    ikkinchi = Xabar(text="ikkinchi savol")
    await bot.sorov(Update(ikkinchi), None)

    matnlar = " ".join(m for m, _ in ikkinchi.javoblar)
    assert "menejerimizga yubordim" in matnlar
    assert "/bolimlar" in matnlar

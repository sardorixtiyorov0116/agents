"""Dollar kursi — manba, solishtiruv va zaxira yo'li.

Nega bu testlar muhim: kurs butun katalog narxini ko'paytiruvchi YAGONA
raqam. U bazada dollarda saqlangan narxni so'mga aylantiradi, ya'ni xato
kurs KP ni ham, tender bahosini ham, saytdagi narxni ham bir vaqtda
siljitadi. Va bunday xato KO'RINMAYDI — hamma joyda raqam "chiroyli"
chiqaveradi.

Shu sabab uchta chegara tekshiriladi:
  - manba SAYT, sozlama emas (bot va sayt bir xil raqamdan ishlasin);
  - sayt javob bermasa — zaxiraga tushadi, lekin buni yashirmaydi;
  - Markaziy bank bilan farq o'lchanadi va sezilarlisi ajratiladi.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app import kurs as kurs_moduli
from app.config import sozlama
from integrations.climavent_client import ClimaventKlient
from integrations.valyuta import (
    KursXatosi,
    MbKursi,
    markaziy_bank_kursi,
    matn,
    solishtir,
)

MB_JAVOBI = [
    {
        "id": 1, "Code": "840", "Ccy": "USD",
        "CcyNm_UZ": "AQSH dollari", "Nominal": "1",
        "Rate": "11813.21", "Diff": "23.88", "Date": "09.09.2026",
    }
]


@pytest.fixture(autouse=True)
def kursni_tozala():
    """Modul darajasidagi holat testlar orasida oqib ketmasin."""
    kurs_moduli.tozala()
    yield
    kurs_moduli.tozala()


class SoxtaJavob:
    def __init__(self, holat: int, tana):
        self.status_code = holat
        self._tana = tana
        self.text = json.dumps(tana)

    def json(self):
        if isinstance(self._tana, str):
            raise ValueError("buzuq JSON")
        return self._tana

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("xato", request=None, response=None)


class SoxtaMijoz:
    """`httpx.AsyncClient` o'rniga — tarmoqqa chiqmaydi."""

    def __init__(self, javob=None, xato: Exception | None = None):
        self.javob = javob
        self.xato = xato
        self.sorovlar: list[str] = []

    async def get(self, manzil, timeout=None):
        self.sorovlar.append(manzil)
        if self.xato:
            raise self.xato
        return self.javob

    async def request(self, metod, manzil, json=None, headers=None, timeout=None):
        self.sorovlar.append(f"{metod} {manzil}")
        if self.xato:
            raise self.xato
        return self.javob


# --- Markaziy bank -----------------------------------------------------------


async def test_markaziy_bank_kursi_oqiladi():
    mijoz = SoxtaMijoz(SoxtaJavob(200, MB_JAVOBI))

    natija = await markaziy_bank_kursi(mijoz=mijoz, keshdan=False)

    assert natija.qiymat == 11813.21
    assert natija.sana == "09.09.2026"
    assert natija.ozgarish == 23.88


async def test_markaziy_bank_javobi_bosh_bolsa_xato():
    mijoz = SoxtaMijoz(SoxtaJavob(200, []))

    with pytest.raises(KursXatosi, match="bo'sh ro'yxat"):
        await markaziy_bank_kursi(mijoz=mijoz, keshdan=False)


async def test_markaziy_bank_nol_kurs_qabul_qilinmaydi():
    """Nol kurs hamma narxni nolga aylantirardi — jimgina o'tmasin."""
    mijoz = SoxtaMijoz(SoxtaJavob(200, [{**MB_JAVOBI[0], "Rate": "0"}]))

    with pytest.raises(KursXatosi, match="noto'g'ri kurs"):
        await markaziy_bank_kursi(mijoz=mijoz, keshdan=False)


async def test_markaziy_bank_tarmoq_xatosi_yutilmaydi():
    mijoz = SoxtaMijoz(xato=httpx.ConnectError("ulanmadi"))

    with pytest.raises(KursXatosi, match="olinmadi"):
        await markaziy_bank_kursi(mijoz=mijoz, keshdan=False)


# --- solishtiruv -------------------------------------------------------------


def test_farq_foizda_olchanadi():
    s = solishtir(MbKursi(11813.21, "09.09.2026", 23.88), backend=12000.0)

    # (12000 - 11813.21) / 11813.21 — farq NISHONGA nisbatan o'lchanadi.
    assert s.farq_foiz == pytest.approx(1.5812, abs=0.001)
    assert s.sezilarlimi(1.0) is True
    assert s.sezilarlimi(2.0) is False


def test_ustama_nishonni_kotaradi():
    """MB kursini ko'r-ko'rona qo'yish katalogni arzonlashtirib yuboradi."""
    s = solishtir(MbKursi(11813.21, "09.09.2026", 0.0), backend=12000.0, ustama_foiz=2.0)

    assert s.nishon == pytest.approx(12049.47, abs=0.01)
    # Ustama bilan sayt kursi endi PAST bo'lib qoladi.
    assert s.farq_foiz < 0


def test_backend_oqilmasa_farq_hisoblanmaydi():
    s = solishtir(MbKursi(11813.21, "09.09.2026", 0.0), backend=None)

    assert s.farq_foiz is None
    assert s.sezilarlimi(0.1) is False
    assert "o'qilmadi" in matn(s)


def test_hisobot_farqni_ochiq_yozadi():
    s = solishtir(MbKursi(11813.21, "09.09.2026", 23.88), backend=12000.0)

    chiqish = matn(s)

    assert "11 813.21" in chiqish
    assert "12 000.00" in chiqish
    assert "+1.58%" in chiqish


# --- joriy kurs --------------------------------------------------------------


def test_standart_holatda_zaxira_ishlatiladi():
    assert kurs_moduli.joriy() == float(sozlama().usd_kursi)
    assert kurs_moduli.manba() == "zaxira"


def test_saytdan_olingan_kurs_zaxirani_almashtiradi():
    kurs_moduli.qoy(11813.21)

    assert kurs_moduli.joriy() == 11813.21
    assert kurs_moduli.manba() == "sayt"


def test_notogri_qiymat_joriy_kursni_buzmaydi():
    """Nol yoki manfiy kurs o'tib ketsa butun narx zanjiri yiqilardi."""
    kurs_moduli.qoy(11813.21)

    kurs_moduli.qoy(0)
    kurs_moduli.qoy(-5)

    assert kurs_moduli.joriy() == 11813.21


class SoxtaKlient:
    def __init__(self, qiymat):
        self.qiymat = qiymat

    async def kurs(self):
        return self.qiymat


async def test_yangila_saytdagi_qiymatni_oladi():
    natija = await kurs_moduli.yangila(SoxtaKlient(11813.21))

    assert natija == 11813.21
    assert kurs_moduli.manba() == "sayt"


async def test_sayt_javob_bermasa_zaxirada_qoladi():
    natija = await kurs_moduli.yangila(SoxtaKlient(None))

    assert natija == float(sozlama().usd_kursi)
    assert kurs_moduli.manba() == "zaxira"


# --- klient tomoni -----------------------------------------------------------


@pytest.mark.oz_transporti
async def test_klient_saytdagi_kursni_oqiydi():
    mijoz = SoxtaMijoz(SoxtaJavob(200, {"rate": 11813.21, "updatedAt": "..."}))
    klient = ClimaventKlient(asos="https://sinov.local", mijoz=mijoz, kesh_ttl=0.01)

    assert await klient.kurs() == 11813.21
    assert "/api/settings/usd-rate" in mijoz.sorovlar[0]


@pytest.mark.oz_transporti
@pytest.mark.parametrize("tana", [{"rate": "yo'q"}, {"rate": 0}, {}, [1, 2]])
async def test_klient_buzuq_javobda_None_qaytaradi(tana):
    """Chala javob zaxira yo'liga o'tsin, taxminiy raqam bermasin."""
    mijoz = SoxtaMijoz(SoxtaJavob(200, tana))
    klient = ClimaventKlient(asos="https://sinov.local", mijoz=mijoz, kesh_ttl=0.01)

    assert await klient.kurs() is None


@pytest.mark.oz_transporti
async def test_klient_api_xatosida_None_qaytaradi():
    mijoz = SoxtaMijoz(SoxtaJavob(500, {"xato": "ichki"}))
    klient = ClimaventKlient(asos="https://sinov.local", mijoz=mijoz, kesh_ttl=0.01)

    assert await klient.kurs() is None


# --- kunlik tekshiruv (bot ishi) ---------------------------------------------
#
# Ish LLM chaqirmaydi va kursni O'ZGARTIRMAYDI — faqat farqni o'lchab
# xabar beradi. Qaysi kurs to'g'ri ekani biznes qarori.


class SoxtaBot:
    """`Bot.kurs_tekshiruvi` ni sinash uchun eng kichik qobiq."""

    def __init__(self, mb, saytdagi, chegara=1.0, ustama=0.0, oluvchilar=(1,)):
        from types import SimpleNamespace

        self._mb = mb
        self._saytdagi = saytdagi
        self.s = SimpleNamespace(
            tender_idlar=set(oluvchilar),
            usd_farq_chegarasi=chegara,
            usd_ustama_foiz=ustama,
        )
        self.baza = None
        self.yuborilgan: list[str] = []

    async def _tenderga_yubor(self, ctx, oluvchilar, xabar):
        self.yuborilgan.append(xabar)


@pytest.fixture
def kurs_ishi(monkeypatch):
    """`Bot.kurs_tekshiruvi` ni soxta muhitda chaqiradigan yordamchi."""
    import bot.asosiy as modul

    async def ishlat(bot):
        async def soxta_mb():
            return bot._mb

        class SoxtaKlientKlassi:
            def __init__(self, *a, **kw):
                pass

            async def kurs(self):
                return bot._saytdagi

        async def belgila(*a, **kw):
            return None

        monkeypatch.setattr(modul, "markaziy_bank_kursi", soxta_mb)
        monkeypatch.setattr(modul, "ClimaventKlient", SoxtaKlientKlassi)
        monkeypatch.setattr(modul.otkazilgan, "belgila", belgila)
        await modul.Bot.kurs_tekshiruvi(bot, ctx=None)

    return ishlat


async def test_sezilarli_farqda_xabar_keladi(kurs_ishi):
    bot = SoxtaBot(MbKursi(11813.21, "09.09.2026", 23.88), saytdagi=12000.0)

    await kurs_ishi(bot)

    assert len(bot.yuborilgan) == 1
    xabar = bot.yuborilgan[0]
    assert "+1.58%" in xabar
    assert "11 813.21" in xabar


async def test_kichik_farqda_xabar_kelmaydi(kurs_ishi):
    """Kunlik tebranish shovqinga aylanmasin."""
    bot = SoxtaBot(MbKursi(11950.0, "09.09.2026", 5.0), saytdagi=12000.0)

    await kurs_ishi(bot)

    assert bot.yuborilgan == []


async def test_tekshiruv_kursni_ozgartirmaydi(kurs_ishi):
    """Ish faqat XABAR beradi — narx siyosatini o'zi hal qilmaydi."""
    bot = SoxtaBot(MbKursi(11813.21, "09.09.2026", 0.0), saytdagi=12000.0)

    await kurs_ishi(bot)

    # Saytdagi qiymat joriy kursga o'rnatiladi (bot va sayt bir xil
    # raqamdan hisoblasin), lekin MB kursiga O'TKAZILMAYDI.
    assert kurs_moduli.joriy() == 12000.0
    assert kurs_moduli.manba() == "sayt"


async def test_oluvchi_bolmasa_tarmoqqa_chiqilmaydi(kurs_ishi):
    bot = SoxtaBot(MbKursi(11813.21, "09.09.2026", 0.0), saytdagi=12000.0,
                   oluvchilar=())

    await kurs_ishi(bot)

    assert bot.yuborilgan == []
    assert kurs_moduli.manba() == "zaxira"

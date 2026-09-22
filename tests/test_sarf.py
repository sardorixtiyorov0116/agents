"""LLM sarfini hisoblash.

NEGA BU TESTLAR BOR
-------------------
2026-08-27 da butun tizim bepul tarifdagi Gemini'ga o'tkazildi
(`TEZ_ROLLAR_ROYXATI=*`). Shu paytdan boshlab kunlik limit real xavfga
aylandi — lekin kodda sarf HISOBI UMUMAN YO'Q edi. Limitga
yaqinlashganimizni faqat urilganda bilardik: menejer KP so'ragan payt,
mijoz kutib turganda.

Eng nozik ikki joy shu yerda qo'riqlanadi:

1. KVOTA KUNI. Google limiti Tinch okeani yarim tunida yangilanadi,
   Toshkent yarim tunida emas. Farq 12-13 soat: Toshkentda ertalab
   soat 11 bo'lganda Google uchun hali KECHAGI kun. Mahalliy sana
   bilan hisoblansak, bir kvota kunining sarfi ikkiga bo'linib ketardi
   va ko'rsatkichimiz Google ko'rsatkichi bilan hech qachon mos
   kelmasdi.

2. XATO O'ZGARMASLIGI. `app/agentlar/asos.py` structured-output rad
   etilganini AYNAN `BadRequestError` turidan biladi. O'lchov qatlami
   xatoni yutib yuborsa yoki boshqa turga o'rasa — o'sha zaxira yo'l
   jimgina ishlamay qolardi.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import sarf


@pytest.fixture(autouse=True)
def _yozuvchini_tozala():
    """Har test o'z yozuvchisi bilan ishlasin."""
    sarf.yozuvchini_ol(None)
    yield
    sarf.yozuvchini_ol(None)


# --- Kvota kuni --------------------------------------------------------------


def test_gemini_kuni_tinch_okeani_boyicha():
    """Toshkentda 27-avgust ertalab — Google uchun hali 26-avgust."""
    # 2026-08-27 06:00 UTC = Toshkentda 11:00, Los-Anjelesda 23:00 (26-avgust)
    payt = datetime(2026, 8, 27, 6, 0, tzinfo=timezone.utc)

    assert sarf.kvota_kuni("gemini", payt) == "2026-08-26"


def test_anthropic_kuni_utc_boyicha():
    payt = datetime(2026, 8, 27, 6, 0, tzinfo=timezone.utc)

    assert sarf.kvota_kuni("anthropic", payt) == "2026-08-27"


def test_gemini_kuni_tinch_okeani_yarim_tunidan_KEYIN_almashadi():
    oldin = datetime(2026, 8, 27, 6, 59, tzinfo=timezone.utc)   # 23:59 PDT
    keyin = datetime(2026, 8, 27, 7, 1, tzinfo=timezone.utc)    # 00:01 PDT

    assert sarf.kvota_kuni("gemini", oldin) == "2026-08-26"
    assert sarf.kvota_kuni("gemini", keyin) == "2026-08-27"


def test_notanish_provayder_UTC_ga_tushadi():
    payt = datetime(2026, 8, 27, 6, 0, tzinfo=timezone.utc)

    assert sarf.kvota_kuni("groq", payt) == "2026-08-27"


# --- Yozib borish ------------------------------------------------------------


class _Sarf:
    def __init__(self, kirish, chiqish):
        self.input_tokens = kirish
        self.output_tokens = chiqish


class _Javob:
    def __init__(self, kirish=100, chiqish=20):
        self.usage = _Sarf(kirish, chiqish)


def _yigib_oluvchi(qayerga: list):
    async def yoz(yozuv):
        qayerga.append(yozuv)
    return yoz


@pytest.mark.asyncio
async def test_muvaffaqiyatli_chaqiruv_yoziladi():
    yozuvlar: list = []
    sarf.yozuvchini_ol(_yigib_oluvchi(yozuvlar))

    async def chaqiruv():
        return _Javob(kirish=1234, chiqish=56)

    javob = await sarf.qayd_bilan("gemini", "gemini-3.5-flash", chaqiruv)

    assert isinstance(javob, _Javob)
    assert len(yozuvlar) == 1
    y = yozuvlar[0]
    assert y["provayder"] == "gemini"
    assert y["model"] == "gemini-3.5-flash"
    assert y["kirish"] == 1234
    assert y["chiqish"] == 56
    assert y["xato"] is None
    assert y["ms"] >= 0


@pytest.mark.asyncio
async def test_xato_YOZILADI_lekin_TURI_OZGARMAYDI():
    """`asos.py` xato TURIga qarab zaxira yo'lga o'tadi — o'ramaymiz."""
    yozuvlar: list = []
    sarf.yozuvchini_ol(_yigib_oluvchi(yozuvlar))

    class MendagiXato(ValueError):
        pass

    async def chaqiruv():
        raise MendagiXato("400 schema rad etildi")

    with pytest.raises(MendagiXato):
        await sarf.qayd_bilan("gemini", "m", chaqiruv)

    assert len(yozuvlar) == 1
    assert "MendagiXato" in yozuvlar[0]["xato"]
    assert yozuvlar[0]["kirish"] == 0


@pytest.mark.asyncio
async def test_yozuv_XATO_bersa_asosiy_chaqiruv_buzilmaydi():
    """Hisob yuritish asosiy ishni to'xtatishi mumkin emas."""
    async def buzuq_yozuvchi(yozuv):
        raise RuntimeError("baza qulflangan")

    sarf.yozuvchini_ol(buzuq_yozuvchi)

    async def chaqiruv():
        return _Javob()

    javob = await sarf.qayd_bilan("gemini", "m", chaqiruv)

    assert isinstance(javob, _Javob)


@pytest.mark.asyncio
async def test_yozuvchi_ulanmagan_bolsa_ham_ishlaydi():
    """Testlarda va alohida skriptlarda baza yo'q."""
    async def chaqiruv():
        return _Javob()

    assert isinstance(await sarf.qayd_bilan("anthropic", "m", chaqiruv), _Javob)


@pytest.mark.asyncio
async def test_usage_maydoni_yoq_javob_nolga_tushadi():
    """Soxta LLM lar `usage` qaytarmaydi — yiqilmasligi kerak."""
    yozuvlar: list = []
    sarf.yozuvchini_ol(_yigib_oluvchi(yozuvlar))

    async def chaqiruv():
        return object()

    await sarf.qayd_bilan("anthropic", "m", chaqiruv)

    assert yozuvlar[0]["kirish"] == 0 and yozuvlar[0]["chiqish"] == 0


# --- Rol nomi ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_rol_yozuvga_tushadi():
    yozuvlar: list = []
    sarf.yozuvchini_ol(_yigib_oluvchi(yozuvlar))

    async def chaqiruv():
        return _Javob()

    with sarf.rol_bilan("hvac-calc"):
        await sarf.qayd_bilan("gemini", "m", chaqiruv)

    assert yozuvlar[0]["rol"] == "hvac-calc"


@pytest.mark.asyncio
async def test_rol_blokdan_chiqqach_tiklanadi():
    with sarf.rol_bilan("router"):
        assert sarf.joriy_rol() == "router"
    assert sarf.joriy_rol() == sarf.NOMA_LUM_ROL


@pytest.mark.asyncio
async def test_rol_ichma_ich_ishlaydi():
    with sarf.rol_bilan("tashqi"):
        with sarf.rol_bilan("ichki"):
            assert sarf.joriy_rol() == "ichki"
        assert sarf.joriy_rol() == "tashqi"


@pytest.mark.asyncio
async def test_rol_asyncio_vazifasiga_kochadi():
    """Agent ichida `create_task` bo'lsa ham rol yo'qolmasin."""
    import asyncio

    natija: list = []

    async def ichkarida():
        natija.append(sarf.joriy_rol())

    with sarf.rol_bilan("temur"):
        await asyncio.create_task(ichkarida())

    assert natija == ["temur"]


# --- Limit xatosini ajratish -------------------------------------------------


@pytest.mark.parametrize("matn", [
    "APIStatusError: Gemini: RESOURCE_EXHAUSTED",
    "quota exceeded for model",
    "HTTP 429 Too Many Requests",
    "rate_limit_error",
])
def test_limit_xatolari_tanilardi(matn):
    assert sarf.limit_xatosimi(matn) is True


@pytest.mark.parametrize("matn", [
    None,
    "",
    "APIConnectionError: internet yo'q",
    "400 schema rad etildi",
])
def test_boshqa_xatolar_limit_deb_belgilanmaydi(matn):
    """3 ta tarmoq uzilishi bilan 3 ta kvota xatosi butunlay boshqa ma'no."""
    assert sarf.limit_xatosimi(matn) is False

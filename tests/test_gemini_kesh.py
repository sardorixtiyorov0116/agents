"""Gemini prompt keshi.

NEGA BU TESTLAR BOR
-------------------
O'lchandi (2026-08-28): bitta erkin matnli so'rov 8 465 kirish tokeni
yeydi, shundan 4 412 tasi — kontraktlar ro'yxati. U har so'rovda bir
xil, lekin Gemini adapterida har safar to'liq to'lanardi:
`app/router.py` qo'ygan `cache_control` belgisi jimgina tashlanardi.

BEPUL TARIFDA KESH YO'Q — bu ham o'lchangan (`cachedContents` -> 429,
limit=0; avtomatik kesh -> `cachedContentTokenCount` doim 0). Ya'ni bu
kod bugun ishlamaydi va billing yoqilganda ishga tushadi.

Aynan shuning uchun testlar SOXTA TRANSPORT ustida: mantiqni Google'siz
tekshirish kerak, aks holda billing yoqilgan kuni sinalmagan kod ishga
tushardi — eng yomon variant.
"""

from __future__ import annotations

import pytest

from app.gemini_kesh import ENG_KAM_TOKEN, GeminiKesh, KeshYopiq

UZUN = "x" * (ENG_KAM_TOKEN * 4)          # keshga arziydi
QISQA = "x" * 100                         # arzimaydi


class SoxtaJavob:
    def __init__(self, kod=200, tana=None, xato=""):
        self.status_code = kod
        self._tana = tana or {}
        self.text = xato

    def json(self):
        return self._tana


def _sorovchi(javoblar):
    """Ketma-ket javob qaytaradigan soxta transport."""
    navbat = list(javoblar)
    chaqiriqlar = []

    async def sorov(usul, yol, tana):
        chaqiriqlar.append((usul, yol, tana))
        return navbat.pop(0) if navbat else SoxtaJavob(200, {"name": "c/x"})

    sorov.chaqiriqlar = chaqiriqlar
    return sorov


# --- Arziydimi ----------------------------------------------------------------


def test_katta_blok_keshga_arziydi():
    assert GeminiKesh.arziydimi(UZUN) is True


def test_kichik_blok_ARZIMAYDI():
    """Saqlash haqi tejamdan oshib ketardi."""
    assert GeminiKesh.arziydimi(QISQA) is False
    assert GeminiKesh.arziydimi("") is False


@pytest.mark.asyncio
async def test_kichik_blok_uchun_sorov_YUBORILMAYDI():
    sorov = _sorovchi([])
    kesh = GeminiKesh(sorov)

    assert await kesh.nomi("gemini-3.5-flash", QISQA) is None
    assert sorov.chaqiriqlar == []


# --- Yaratish -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_kesh_yaratiladi_va_nomi_qaytadi():
    sorov = _sorovchi([SoxtaJavob(200, {"name": "cachedContents/abc"})])
    kesh = GeminiKesh(sorov)

    assert await kesh.nomi("gemini-3.5-flash", UZUN) == "cachedContents/abc"


@pytest.mark.asyncio
async def test_model_nomiga_prefiks_qoshiladi():
    """Gemini `models/` prefiksini talab qiladi."""
    sorov = _sorovchi([SoxtaJavob(200, {"name": "c/a"})])
    kesh = GeminiKesh(sorov)

    await kesh.nomi("gemini-3.5-flash", UZUN)

    assert sorov.chaqiriqlar[0][2]["model"] == "models/gemini-3.5-flash"


@pytest.mark.asyncio
async def test_ikkinchi_sorovda_QAYTA_yaratilmaydi():
    sorov = _sorovchi([SoxtaJavob(200, {"name": "c/a"})])
    kesh = GeminiKesh(sorov)

    await kesh.nomi("gemini-3.5-flash", UZUN)
    await kesh.nomi("gemini-3.5-flash", UZUN)

    assert len(sorov.chaqiriqlar) == 1


@pytest.mark.asyncio
async def test_BOSHQA_matn_uchun_alohida_kesh():
    sorov = _sorovchi([SoxtaJavob(200, {"name": "c/a"}),
                       SoxtaJavob(200, {"name": "c/b"})])
    kesh = GeminiKesh(sorov)

    a = await kesh.nomi("gemini-3.5-flash", UZUN)
    b = await kesh.nomi("gemini-3.5-flash", UZUN + "boshqa")

    assert a != b


@pytest.mark.asyncio
async def test_BOSHQA_model_uchun_alohida_kesh():
    sorov = _sorovchi([SoxtaJavob(200, {"name": "c/a"}),
                       SoxtaJavob(200, {"name": "c/b"})])
    kesh = GeminiKesh(sorov)

    await kesh.nomi("gemini-3.5-flash", UZUN)
    await kesh.nomi("gemini-3.6-flash", UZUN)

    assert len(sorov.chaqiriqlar) == 2


# --- Bepul tarif --------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_da_kesh_OCHIRILADI():
    """Bepul tarifda limit nol — har so'rovda 429 olish kvotani yeydi."""
    sorov = _sorovchi([SoxtaJavob(
        429, {"error": {"message": "TotalCachedContentStorageTokens... limit=0"}})])
    kesh = GeminiKesh(sorov)

    assert await kesh.nomi("gemini-3.5-flash", UZUN) is None
    assert kesh.yopiqmi is True


@pytest.mark.asyncio
async def test_ochirilgach_QAYTA_urinilmaydi():
    sorov = _sorovchi([SoxtaJavob(429, {"error": {"message": "limit=0"}})])
    kesh = GeminiKesh(sorov)

    for _ in range(5):
        await kesh.nomi("gemini-3.5-flash", UZUN)

    assert len(sorov.chaqiriqlar) == 1


# --- Nosozlik asosiy ishni to'xtatmaydi ---------------------------------------


@pytest.mark.asyncio
async def test_boshqa_xatoda_None_qaytadi_lekin_OCHIRILMAYDI():
    """Vaqtinchalik nosozlik keshni butunlay yopmasin."""
    sorov = _sorovchi([SoxtaJavob(500, {"error": {"message": "server xatosi"}}),
                       SoxtaJavob(200, {"name": "c/a"})])
    kesh = GeminiKesh(sorov)

    assert await kesh.nomi("gemini-3.5-flash", UZUN) is None
    assert kesh.yopiqmi is False
    assert await kesh.nomi("gemini-3.5-flash", UZUN) == "c/a"


@pytest.mark.asyncio
async def test_transport_YIQILSA_ham_xato_chiqmaydi():
    """Kesh — tejamkorlik, majburiyat emas."""
    async def buzuq(usul, yol, tana):
        raise ConnectionError("tarmoq yo'q")

    kesh = GeminiKesh(buzuq)

    assert await kesh.nomi("gemini-3.5-flash", UZUN) is None


@pytest.mark.asyncio
async def test_javobda_nom_yoq_bolsa_None():
    sorov = _sorovchi([SoxtaJavob(200, {})])
    kesh = GeminiKesh(sorov)

    assert await kesh.nomi("gemini-3.5-flash", UZUN) is None


# --- So'rov tanasi ------------------------------------------------------------


def test_keshlanadigan_blok_TOPILADI():
    from app.gemini import keshlanadigan_blok

    soro = {"system": [
        {"type": "text", "text": "ko'rsatma"},
        {"type": "text", "text": "kontraktlar",
         "cache_control": {"type": "ephemeral"}},
    ]}

    assert keshlanadigan_blok(soro) == "kontraktlar"


def test_belgisiz_sorovda_blok_YOQ():
    from app.gemini import keshlanadigan_blok

    assert keshlanadigan_blok({"system": [{"type": "text", "text": "x"}]}) == ""
    assert keshlanadigan_blok({"system": "oddiy satr"}) == ""
    assert keshlanadigan_blok({}) == ""


def test_keshlangan_matn_systemInstruction_dan_OLIB_TASHLANADI():
    """Ikki marta yuborilsa kesh hech narsa tejamasdi."""
    from app.gemini import sorovni_ogir

    soro = {"system": [
        {"type": "text", "text": "ko'rsatma"},
        {"type": "text", "text": "KONTRAKTLAR",
         "cache_control": {"type": "ephemeral"}},
    ], "messages": [{"role": "user", "content": "salom"}]}

    tana = sorovni_ogir(soro, keshsiz="KONTRAKTLAR")

    tizim = tana["systemInstruction"]["parts"][0]["text"]
    assert "KONTRAKTLAR" not in tizim
    assert "ko'rsatma" in tizim


def test_keshsiz_berilmasa_matn_JOYIDA_qoladi():
    from app.gemini import sorovni_ogir

    soro = {"system": [{"type": "text", "text": "KONTRAKTLAR",
                        "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": "salom"}]}

    tana = sorovni_ogir(soro)

    assert "KONTRAKTLAR" in tana["systemInstruction"]["parts"][0]["text"]


# --- Javobdagi kesh tokenlari -------------------------------------------------


def test_keshdan_oqilgan_tokenlar_javobdan_OLINADI():
    from app.gemini import javobni_ogir

    javob = javobni_ogir({
        "candidates": [{"content": {"parts": [{"text": "ok"}]},
                        "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 5000,
                          "candidatesTokenCount": 100,
                          "cachedContentTokenCount": 4400},
    }, "gemini-3.5-flash")

    assert javob.usage.cache_read_input_tokens == 4400


def test_kesh_maydoni_YOQ_bolsa_nol():
    """Bepul tarifda Gemini bu maydonni umuman qaytarmaydi."""
    from app.gemini import javobni_ogir

    javob = javobni_ogir({
        "candidates": [{"content": {"parts": [{"text": "ok"}]},
                        "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 5000, "candidatesTokenCount": 100},
    }, "gemini-3.5-flash")

    assert javob.usage.cache_read_input_tokens == 0

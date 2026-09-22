"""Zaxira zanjiri — bir model yiqilsa keyingisi.

NEGA BU TESTLAR BOR
-------------------
JONLI HOLAT (2026-08-27): Gemini bepul tarifi "This model is currently
experiencing high demand" bilan rad etdi va TZ o'qish butunlay ishlamay
qoldi. Bitta provayderga bog'lanish bepul tarifda kutiladigan nosozlik.

ENG NOZIK QOIDA — 400 DA O'TILMAYDI
-----------------------------------
`app/agentlar/asos.py` structured-output rad etilganini AYNAN
`BadRequestError` turidan biladi va matn rejimiga o'zi o'tadi. Zanjir
400 ni ushlab boshqa modelga o'tsa, o'sha zaxira yo'l jimgina ishlamay
qolardi — va natijada sxemani tushunmaydigan model o'rniga sxemani
tushunmaydigan BOSHQA modelga borib, baribir yiqilardik.
"""

from __future__ import annotations

import httpx
import pytest

from app.zanjir import DAM_MUDDATI, QISQA_DAM, ZanjirLlm, otish_kerakmi, zanjir_yasa


def _javob(kod: int) -> httpx.Response:
    return httpx.Response(kod, request=httpx.Request("POST", "https://x"))


def _api_xato(kod: int, matn: str = "xato"):
    import anthropic

    if kod == 400:
        return anthropic.BadRequestError(matn, response=_javob(400), body=None)
    return anthropic.APIStatusError(matn, response=_javob(kod), body=None)


class SoxtaLlm:
    """Berilgan xatoni tashlaydi yoki javob qaytaradi."""

    def __init__(self, nom: str, xato: BaseException | None = None):
        self.nom = nom
        self.xato = xato
        self.chaqiriqlar = 0

    async def javob(self, **soro):
        self.chaqiriqlar += 1
        if self.xato is not None:
            raise self.xato
        return {"model": self.nom, "soro": soro}


def _zanjir(*llmlar: SoxtaLlm) -> ZanjirLlm:
    jadval = {l.nom: l for l in llmlar}
    return ZanjirLlm([l.nom for l in llmlar], lambda nom: jadval[nom])


# --- Qaysi xatoda o'tiladi ---------------------------------------------------


@pytest.mark.parametrize("kod", [401, 403, 404, 429, 500, 503, 529])
def test_provayder_xatolarida_OTILADI(kod):
    assert otish_kerakmi(_api_xato(kod)) is True


def test_400_da_OTILMAYDI():
    """`asos.py` uni o'zi ushlaydi — structured output zaxirasi."""
    assert otish_kerakmi(_api_xato(400)) is False


def test_oz_kodimizdagi_xatoda_OTILMAYDI():
    """Boshqa modelda ham aynan takrorlanardi."""
    assert otish_kerakmi(TypeError("noto'g'ri argument")) is False
    assert otish_kerakmi(ValueError("x")) is False


def test_ulanish_xatosida_OTILADI():
    import anthropic

    xato = anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))

    assert otish_kerakmi(xato) is True


# --- Zanjir ishlashi ---------------------------------------------------------


@pytest.mark.asyncio
async def test_birinchi_ishlasa_ikkinchisi_CHAQIRILMAYDI():
    a = SoxtaLlm("a")
    b = SoxtaLlm("b")

    natija = await _zanjir(a, b).javob(messages=[])

    assert natija["model"] == "a"
    assert b.chaqiriqlar == 0


@pytest.mark.asyncio
async def test_birinchi_yiqilsa_ikkinchisi_urinadi():
    a = SoxtaLlm("a", _api_xato(429, "RESOURCE_EXHAUSTED"))
    b = SoxtaLlm("b")

    natija = await _zanjir(a, b).javob(messages=[])

    assert natija["model"] == "b"
    assert a.chaqiriqlar == 1 and b.chaqiriqlar == 1


@pytest.mark.asyncio
async def test_model_nomi_ALMASHTIRILADI():
    """Zanjirdagi har model o'z nomi bilan chaqirilsin."""
    a = SoxtaLlm("a", _api_xato(503))
    b = SoxtaLlm("b")

    natija = await _zanjir(a, b).javob(messages=[], model="eskisi")

    assert natija["soro"]["model"] == "b"


@pytest.mark.asyncio
async def test_400_zanjirni_TOXTATADI():
    a = SoxtaLlm("a", _api_xato(400, "schema rad etildi"))
    b = SoxtaLlm("b")

    import anthropic

    with pytest.raises(anthropic.BadRequestError):
        await _zanjir(a, b).javob(messages=[])

    assert b.chaqiriqlar == 0


@pytest.mark.asyncio
async def test_hammasi_yiqilsa_ASOSIY_model_xatosi_chiqadi():
    """Menejer ko'radigan xabar shu xatodan yasaladi — ASL sabab kerak.

    Zanjir `gemini,claude-haiku` bo'lib Gemini kvotasi tugasa va
    Anthropic'da mablag' bo'lmasa, oxirgi xato "hisobda mablag' yo'q"
    bo'lardi. Bu asl sabab emas va menejerni noto'g'ri tomonga
    yuborardi.
    """
    asosiy = _api_xato(429, "RESOURCE_EXHAUSTED")
    a = SoxtaLlm("a", asosiy)
    b = SoxtaLlm("b", _api_xato(529, "credit balance too low"))

    with pytest.raises(Exception) as tutildi:
        await _zanjir(a, b).javob(messages=[])

    assert tutildi.value is asosiy


@pytest.mark.asyncio
async def test_xato_TURI_ozgarmaydi():
    """`asos.py` turga qarab qaror qiladi — o'ramaymiz."""
    import anthropic

    a = SoxtaLlm("a", _api_xato(429))
    b = SoxtaLlm("b", _api_xato(503))

    with pytest.raises(anthropic.APIStatusError):
        await _zanjir(a, b).javob(messages=[])


@pytest.mark.asyncio
async def test_uchta_modeldan_uchinchisi_ishlaydi():
    a = SoxtaLlm("a", _api_xato(429))
    b = SoxtaLlm("b", _api_xato(503))
    c = SoxtaLlm("c")

    assert (await _zanjir(a, b, c).javob(messages=[]))["model"] == "c"


# --- Dam olish (cooldown) ----------------------------------------------------


@pytest.mark.asyncio
async def test_yiqilgan_model_KEYINGI_sorovda_chetga_suriladi():
    """Kvota tugagan model har safar qayta sinalsa, har so'rov sekinlashardi."""
    a = SoxtaLlm("a", _api_xato(429, "RESOURCE_EXHAUSTED"))
    b = SoxtaLlm("b")
    zanjir = _zanjir(a, b)

    await zanjir.javob(messages=[])
    await zanjir.javob(messages=[])
    await zanjir.javob(messages=[])

    assert a.chaqiriqlar == 1        # faqat birinchi safar
    assert b.chaqiriqlar == 3


@pytest.mark.asyncio
async def test_limit_xatosi_UZOQROQ_dam_beradi():
    limitli = _zanjir(SoxtaLlm("a", _api_xato(429, "RESOURCE_EXHAUSTED")), SoxtaLlm("b"))
    vaqtinchalik = _zanjir(SoxtaLlm("c", _api_xato(503, "band")), SoxtaLlm("d"))

    await limitli.javob(messages=[])
    await vaqtinchalik.javob(messages=[])

    import time
    hozir = time.monotonic()
    assert limitli._dam["a"] - hozir > QISQA_DAM
    assert vaqtinchalik._dam["c"] - hozir <= QISQA_DAM + 1


@pytest.mark.asyncio
async def test_dam_olayotgan_model_OCHIRILMAYDI_faqat_suriladi():
    """Dam muddati noto'g'ri hisoblansa ham tizim to'xtab qolmasin."""
    a = SoxtaLlm("a", _api_xato(429))
    b = SoxtaLlm("b", _api_xato(429))
    zanjir = _zanjir(a, b)

    with pytest.raises(Exception):
        await zanjir.javob(messages=[])

    # Ikkalasi ham dam olyapti — lekin navbat baribir ikkalasini beradi.
    assert set(zanjir._navbat()) == {"a", "b"}


# --- zanjir_yasa -------------------------------------------------------------


def test_bitta_model_ORALMAYDI():
    """Eski o'rnatmalarda xatti-harakat aynan avvalgidek qolsin."""
    yagona = SoxtaLlm("a")

    assert zanjir_yasa(["a"], lambda nom: yagona) is yagona


def test_ikkita_model_ORALADI():
    natija = zanjir_yasa(["a", "b"], lambda nom: SoxtaLlm(nom))

    assert isinstance(natija, ZanjirLlm)


def test_bosh_royxat_RAD_ETILADI():
    with pytest.raises(ValueError):
        zanjir_yasa([], lambda nom: None)


# --- Sozlama ------------------------------------------------------------------


def test_vergulli_TEZ_MODEL_royxatga_aylanadi():
    from app.config import Sozlama

    s = Sozlama(tez_model="gemini-3.5-flash, claude-haiku-4-5")

    assert s.tez_modellar == ["gemini-3.5-flash", "claude-haiku-4-5"]


def test_takrorlangan_model_bir_marta():
    from app.config import Sozlama

    s = Sozlama(tez_model="a,b,a")

    assert s.tez_modellar == ["a", "b"]


def test_TEZ_MODEL_bosh_bolsa_hech_kim_tez_modelga_otmaydi():
    from app.config import Sozlama

    s = Sozlama(tez_model="", tez_rollar_royxati="*")

    assert s.tez_modellar == []
    assert s.tez_rollar == set()
    assert s.hamma_rol_tezmi is False

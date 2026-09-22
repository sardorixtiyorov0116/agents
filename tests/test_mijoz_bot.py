"""Mijozlar boti — OCHIQ bot, shuning uchun himoya boshqacha.

Ichki botda "kim kirishi mumkin" tekshiriladi. Bu yerda foydalanuvchi
notanish, shuning uchun asosiy savol: QAYSI AGENT mijozga chiqadi.
Eng muhim test — yangi agent qo'shilganda u avtomatik ochilib
qolmasligi.
"""

from __future__ import annotations

import pytest

from app.baza import Baza
from app.router import Reja, RejaQadam
from bot.mijoz_ruxsat import OCHIQ_AGENTLAR, Tezlik, rejani_tekshir


def reja(*rollar: str) -> Reja:
    return Reja(
        niyat="sinov",
        qadamlar=[RejaQadam(agent=r, vazifa="…") for r in rollar],
    )


# --- qaysi agent mijozga ochiq ------------------------------------------------


def test_ochiq_agentlar_royxati_qisqa():
    """Ro'yxat OQ (allowlist): faqat ataylab qo'shilgani ochiq."""
    # Bu ro'yxat ATAYLAB qat'iy yozilgan: yangi agent qo'shilganda
    # test yiqiladi va uni mijozga ochish ONGLI qaror bo'ladi.
    # Har qo'shilganda: agent mijozga nima ayta oladi va nima
    # ayta olmasligi kodda ushlanganmi?
    assert OCHIQ_AGENTLAR == {"product-spec", "hvac-calc", "montaj-guide"}


def test_yangi_agent_avtomatik_ochilmaydi():
    """Eng muhim himoya.

    Tizimga agent qo'shilganda u mijozlarga O'ZIDAN ochilib qolmasligi
    kerak — ro'yxatga qo'lda qo'shilmaguncha yopiq.
    """
    from app.agentlar import AGENT_KLASSLARI

    for rol in AGENT_KLASSLARI:
        if rol in OCHIQ_AGENTLAR:
            continue
        assert not rejani_tekshir(reja(rol)).ruxsat, f"{rol} mijozga ochiq qolgan"


@pytest.mark.parametrize("rol", sorted(OCHIQ_AGENTLAR))
def test_ochiq_agent_otadi(rol):
    assert rejani_tekshir(reja(rol)).ruxsat


@pytest.mark.parametrize("rol", [
    "data-query",        # ichki bazaga SQL
    "catalog-admin",     # katalogni o'zgartiradi
    "hr-assist",         # xodimlar ma'lumoti
    "proposal-builder",  # narx
    "kp-tracker",        # savdo hisoboti
    "competitor-watch",  # raqobatchilar
])
def test_xavfli_agentlar_yopiq(rol):
    qaror = rejani_tekshir(reja(rol))
    assert not qaror.ruxsat
    assert rol in qaror.sabab


def test_zanjirda_bitta_yopiq_bolsa_hammasi_rad_etiladi():
    """Yarim javob mijozni chalg'itadi — butun reja to'xtaydi."""
    qaror = rejani_tekshir(reja("hvac-calc", "proposal-builder"))

    assert not qaror.ruxsat
    assert "proposal-builder" in qaror.sabab


def test_bosh_reja_rad_etiladi():
    assert not rejani_tekshir(reja()).ruxsat


# --- flood himoyasi -----------------------------------------------------------


def test_limitdan_oshsa_toxtatadi():
    """Bot ochiq — bitta odam LLM hisobini sarflab yubormasin."""
    t = Tezlik(limit=3)

    assert [t.ruxsatmi(111) for _ in range(3)] == [True, True, True]
    assert t.ruxsatmi(111) is False
    # Boshqa odamga ta'sir qilmaydi
    assert t.ruxsatmi(222) is True


def test_oyna_otgach_qayta_ruxsat():
    t = Tezlik(limit=1, oyna=0.01)
    assert t.ruxsatmi(111) is True
    assert t.ruxsatmi(111) is False

    import time
    time.sleep(0.02)
    assert t.ruxsatmi(111) is True


# --- lidlar bazasi ------------------------------------------------------------


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "mijoz.db")
    await b.tayyorla()
    return b


@pytest.mark.asyncio
async def test_murojaat_yoziladi_va_ochiladi(baza):
    """Javobsiz murojaat botda qolib ketmasligi kerak."""
    await baza.murojaat_yoz({
        "tg_id": 555, "ism": "Aziz", "aloqa": "+998901234567",
        "savol": "Narxi qancha?", "sabab": "mijozga yopiq: proposal-builder",
    })

    yangi = await baza.murojaatlar(holat="yangi")
    assert len(yangi) == 1
    assert yangi[0]["aloqa"] == "+998901234567"
    assert yangi[0]["holat"] == "yangi"


@pytest.mark.asyncio
async def test_korildi_deb_belgilanadi(baza):
    murojaat_id = await baza.murojaat_yoz({
        "tg_id": 555, "savol": "salom", "sabab": "test",
    })

    assert await baza.murojaat_korildi(murojaat_id) is True
    assert await baza.murojaatlar(holat="yangi") == []
    assert len(await baza.murojaatlar(holat="korildi")) == 1


@pytest.mark.asyncio
async def test_yoq_murojaat_belgilanmaydi(baza):
    assert await baza.murojaat_korildi(99999) is False


# --- telefon raqamini tanish --------------------------------------------------


@pytest.mark.parametrize("matn", [
    "+998 90 099 12 60",
    "998901234567",
    "90 123 45 67",
    "Mening raqamim 93-456-78-90",
])
def test_telefon_taniladi(matn):
    from bot.mijoz import TELEFON

    assert TELEFON.search(matn), matn


@pytest.mark.parametrize("matn", [
    "800 kv metr ombor uchun hisob kerak",
    "Kanal ventilyatori 250 mm",
])
def test_oddiy_savol_telefon_deb_qabul_qilinmaydi(matn):
    from bot.mijoz import TELEFON

    assert not TELEFON.search(matn), matn


# --- token aralashmasligi -----------------------------------------------------


def test_ichki_token_bilan_bir_xil_bolsa_ishga_tushmaydi(monkeypatch):
    """Aks holda ichki buyruqlar mijozlarga ochiq qolardi."""
    from app.config import sozlama
    from bot.mijoz import yasa

    s = sozlama()
    monkeypatch.setattr(s, "mijoz_bot_token", "bir-xil-token", raising=False)
    monkeypatch.setattr(s, "bot_token", "bir-xil-token", raising=False)

    with pytest.raises(RuntimeError, match="alohida bo'lishi shart"):
        yasa()


def test_token_yoq_bolsa_aniq_xato(monkeypatch):
    from app.config import sozlama
    from bot.mijoz import yasa

    s = sozlama()
    monkeypatch.setattr(s, "mijoz_bot_token", "", raising=False)

    with pytest.raises(RuntimeError, match="MIJOZ_BOT_TOKEN"):
        yasa()


# --- menejerga xabar ----------------------------------------------------------
#
# Jonli sinovda chiqqan xato: xabar MIJOZ boti orqali yuborilgan edi.
# Menejer u bilan hech qachon suhbat boshlamagan, Telegram esa notanish
# chatga yozishga ruxsat bermaydi — xabar hech qachon yetib bormadi.


class SoxtaFoydalanuvchi:
    def __init__(self, tg_id=555, ism="Aziz", username="aziz"):
        self.id = tg_id
        self.full_name = ism
        self.username = username


class SoxtaUpdate:
    def __init__(self, foydalanuvchi):
        self.effective_user = foydalanuvchi

    def get_bot(self):
        raise AssertionError("menejerga xabar MIJOZ boti orqali ketmasligi kerak")


class SoxtaIchkiBot:
    def __init__(self):
        self.yuborilgan: list[tuple[int, str]] = []
        self.hujjatlar: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **_):
        self.yuborilgan.append((chat_id, text))

    async def send_document(self, chat_id, fayl, filename=None, **_):
        self.hujjatlar.append((chat_id, filename))


def soxta_bot(baza, ichki, menejerlar={7001, 7002}):
    from bot.mijoz import MijozBot

    bot = object.__new__(MijozBot)
    bot.baza = baza
    bot._ichki_bot = ichki

    class S:
        mijoz_menejer_idlar = menejerlar
        # Telegram xabari 4096 belgi — `_menejerga` uni qirqadi.
        bot_maks_belgi = 4000

    bot.s = S()
    return bot


@pytest.mark.asyncio
async def test_menejerga_xabar_ichki_bot_orqali(baza):
    ichki = SoxtaIchkiBot()
    bot = soxta_bot(baza, ichki)

    await bot._lid(SoxtaUpdate(SoxtaFoydalanuvchi()), "Narxi qancha?",
                   sabab="mijozga yopiq: proposal-builder")

    assert {kim for kim, _ in ichki.yuborilgan} == {7001, 7002}
    assert "Narxi qancha?" in ichki.yuborilgan[0][1]


@pytest.mark.asyncio
async def test_yangi_mijoz_alohida_belgilanadi(baza):
    ichki = SoxtaIchkiBot()
    bot = soxta_bot(baza, ichki)

    await bot._lid(SoxtaUpdate(SoxtaFoydalanuvchi()), "800 m² ombor",
                   javob="Hisob: …", sabab="")

    assert len(ichki.yuborilgan) == 2
    assert "Yangi mijoz" in ichki.yuborilgan[0][1]


@pytest.mark.asyncio
async def test_javob_berilgan_savol_ham_menejerga_korinadi(baza):
    """Bot "menejerimiz bog'lanadi" deydi — menejer suhbatni bilsin.

    Avval takroriy savol jim o'tardi va menejer nima gaplashilganini
    umuman ko'rmasdi.
    """
    ichki = SoxtaIchkiBot()
    bot = soxta_bot(baza, ichki)
    update = SoxtaUpdate(SoxtaFoydalanuvchi())

    await bot._lid(update, "birinchi savol", javob="…", sabab="")
    ichki.yuborilgan.clear()
    await bot._lid(update, "ikkinchi savol", javob="Havo sarfi 9600", sabab="")

    matn = ichki.yuborilgan[0][1]
    assert "ikkinchi savol" in matn
    assert "Havo sarfi 9600" in matn          # javob ham ko'rinadi
    assert "Yangi mijoz" not in matn          # endi u yangi emas
    assert len(await baza.murojaatlar(holat="yangi")) == 2


@pytest.mark.asyncio
async def test_uzun_javob_qisqartiriladi(baza):
    """Telegram xabari cheksiz emas — javob kesiladi, to'lig'i bazada."""
    from bot.mijoz import MENEJER_JAVOB

    ichki = SoxtaIchkiBot()
    bot = soxta_bot(baza, ichki)
    uzun = "\n".join(f"qator {i}" for i in range(400))

    await bot._lid(SoxtaUpdate(SoxtaFoydalanuvchi()), "savol", javob=uzun)

    assert len(ichki.yuborilgan[0][1]) < MENEJER_JAVOB + 600
    assert (await baza.murojaatlar(holat="yangi"))[0]["javob"] == uzun


@pytest.mark.asyncio
async def test_ichki_token_yoq_bolsa_yiqilmaydi(baza):
    """BOT_TOKEN qo'yilmagan bo'lsa ham mijozga javob berish to'xtamaydi."""
    bot = soxta_bot(baza, None)

    await bot._lid(SoxtaUpdate(SoxtaFoydalanuvchi()), "savol", sabab="xato")

    assert len(await baza.murojaatlar(holat="yangi")) == 1


# --- telefon tugmasi ----------------------------------------------------------


def test_start_klaviaturasida_telefon_tugmasi():
    """Mijoz raqamni qo'lda yozmasin — bitta bosishda yuborsin."""
    from bot.mijoz import TUGMA_TELEFON, MijozBot

    klaviatura = MijozBot._klaviatura()
    tugma = klaviatura.keyboard[0][0]

    assert tugma.text == TUGMA_TELEFON
    assert tugma.request_contact is True


class SoxtaKontakt:
    def __init__(self, raqam):
        self.phone_number = raqam


class SoxtaXabar:
    def __init__(self, kontakt):
        self.contact = kontakt
        self.javoblar: list[str] = []

    async def reply_text(self, matn, **_):
        self.javoblar.append(matn)


class SoxtaKontaktUpdate(SoxtaUpdate):
    def __init__(self, foydalanuvchi, raqam):
        super().__init__(foydalanuvchi)
        self.effective_message = SoxtaXabar(SoxtaKontakt(raqam))


@pytest.mark.asyncio
async def test_tugma_orqali_kelgan_raqam_lid_boladi(baza):
    ichki = SoxtaIchkiBot()
    bot = soxta_bot(baza, ichki)
    update = SoxtaKontaktUpdate(SoxtaFoydalanuvchi(), "+998901234567")

    await bot.kontakt(update, None)

    yozuv = (await baza.murojaatlar(holat="yangi"))[0]
    assert yozuv["aloqa"] == "+998901234567"
    assert "raqamini yubordi" in yozuv["sabab"]
    assert ichki.yuborilgan, "menejerga xabar ketishi kerak"
    assert update.effective_message.javoblar, "mijozga tasdiq javobi kerak"


# --- token tejash -------------------------------------------------------------


def test_router_faqat_ochiq_kontraktlarni_koradi():
    """Yopiq 12 agentning matni router promptiga umuman qo'shilmaydi.

    Bu xavfsizlik emas (u `rejani_tekshir` da), bu TEJASH: to'liq reyestr
    har savolga ~9 300 token qo'shadi.
    """
    from app.kontraktlar import reyestr
    from bot.mijoz_ruxsat import ochiq_kontraktlar

    ochiq = ochiq_kontraktlar()

    assert set(ochiq) == OCHIQ_AGENTLAR
    assert len(ochiq) < len(reyestr())


def test_rustam_prompti_qisqa():
    """Prompt har savolda qaytadan yuboriladi — u kichik bo'lishi kerak."""
    from app.agentlar.loyihachi import TIZIM_PROMPT

    assert len(TIZIM_PROMPT) < 1200, "prompt o'sib ketdi — token sarfi oshadi"


def test_rustam_past_effortda_ishlaydi():
    """Rustam o'ylamaydi — matndan maydon ajratadi."""
    from app.agentlar.loyihachi import Loyihachi

    assert Loyihachi.EFFORT == "low"


# --- mijoz ichki bezaklarni KO'RMAYDI -----------------------------------------
#
# Jonli sinovda mijozga shu chiqqan edi:
#   "⏸ Loyihachi muhandis Rustam — tasdiq kutilmoqda"
#   "Manba: hvac-calc kontrakti, hisob"
# Mijoz uchun bu ikkalasi ham zarar: birinchisi javob chala qolgandek
# ko'rsatadi, ikkinchisi ichki tuzilmani oshkor qiladi.


def natija_yasa(holat, kim="hvac-calc"):
    from app.konvert import Ishonch, Konvert, Manba
    from app.orkestr import Natija

    k = Konvert(
        kim=kim, holat=holat, ishonch=Ishonch.YUQORI,
        natija={"obyekt": "Ombor", "xonalar": [], "eslatmalar": []},
        manba=[Manba(tur="kontrakt", nom="hvac-calc kontrakti")],
        tasdiq_kerak=True,
    )
    return Natija(sorov="ombor", davomiylik_ms=0, yakuniy=k)


@pytest.mark.parametrize("holat_nomi", ["TUGADI", "TASDIQ_KUTILMOQDA"])
def test_mijozga_agent_ismi_va_tasdiq_korinmaydi(holat_nomi):
    from app.konvert import Holat
    from presenter import mijoz_matni

    matn = mijoz_matni(natija_yasa(getattr(Holat, holat_nomi)))

    assert "tasdiq" not in matn.lower()
    assert "Rustam" not in matn
    assert "Loyihachi" not in matn
    assert "Manba:" not in matn
    assert "⏸" not in matn


def test_ichki_botda_esa_bularning_hammasi_qoladi():
    """Xodim kim ishlaganini va tasdiq kutilayotganini BILISHI kerak."""
    from app.konvert import Holat
    from presenter import javob_matni

    matn = javob_matni(
        natija_yasa(Holat.TASDIQ_KUTILMOQDA),
        {"hvac-calc": "Loyihachi muhandis Rustam"},
    )

    assert "Loyihachi muhandis Rustam" in matn
    assert "tasdiq kutilmoqda" in matn


# --- salomlashish LLM ga bormaydi ---------------------------------------------


@pytest.mark.parametrize("matn", [
    "Salom", "assalomu alaykum", "Assalomu alaykum!", "Привет",
    "hello", "Rahmat", "rahmat.", "spasibo",
])
def test_salomga_llm_chaqirilmaydi(matn):
    """Har salom uchun router + agent chaqirilsa — pul va menejerga shovqin."""
    from bot.mijoz import _oddiy_javob

    assert _oddiy_javob(matn) is not None


@pytest.mark.parametrize("matn", [
    "800 kv metr ombor",
    "salom, ombor uchun hisob kerak",     # salom + savol — bu SAVOL
    "ВК-250С narxi",
])
def test_haqiqiy_savol_otkazib_yuborilmaydi(matn):
    from bot.mijoz import _oddiy_javob

    assert _oddiy_javob(matn) is None


# --- ovozli xabar -------------------------------------------------------------
#
# ENG MUHIM QOIDA: mijoz ovoz yuborsa, bot HAR QANDAY holatda javob
# beradi. Ilgari ovoz ishlovchisi umuman yo'q edi — ovozli xabar
# javobsiz qolardi va mijoz bot ishlamayapti deb o'ylardi.


class SoxtaOvoz:
    def __init__(self, davomiylik=8, baytlar=b"ogg-baytlari"):
        self.duration = davomiylik
        self.mime_type = "audio/ogg"
        self._baytlar = baytlar

    async def get_file(self):
        baytlar = self._baytlar

        class Fayl:
            async def download_as_bytearray(self):
                return bytearray(baytlar)

        return Fayl()


class SoxtaOvozXabar:
    def __init__(self, ovoz):
        self.voice = ovoz
        self.audio = None
        self.text = None
        self.chat = object()
        self.javoblar: list[str] = []

    async def reply_text(self, matn, **_):
        self.javoblar.append(matn)


class SoxtaOvozUpdate(SoxtaUpdate):
    def __init__(self, foydalanuvchi, ovoz):
        super().__init__(foydalanuvchi)
        self.effective_message = SoxtaOvozXabar(ovoz)


def ovoz_boti(baza, monkeypatch, matnga=None, xato=None):
    """Ovoz ishlovchisi uchun minimal bot."""
    from app import ovoz as ovoz_moduli
    from bot import mijoz as mijoz_moduli

    bot = soxta_bot(baza, SoxtaIchkiBot())
    chaqirilgan = {}

    async def soxta_matnga(xom, mime="audio/ogg"):
        if xato:
            raise xato
        return matnga

    monkeypatch.setattr(mijoz_moduli.ovoz_moduli, "matnga", soxta_matnga)

    async def soxta_yozmoqda(chat):
        return None

    bot._yozmoqda = soxta_yozmoqda

    async def soxta_sorov(update, kontekst, matn=None):
        chaqirilgan["matn"] = matn

    bot.sorov = soxta_sorov
    return bot, chaqirilgan


@pytest.mark.asyncio
async def test_ovoz_matnga_ogirilib_sorovga_uzatiladi(baza, monkeypatch):
    bot, chaqirilgan = ovoz_boti(
        baza, monkeypatch, matnga="200 metr kvadrat ofis uchun ventilyatsiya")
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())

    await bot.ovoz(update, None)

    assert chaqirilgan["matn"] == "200 metr kvadrat ofis uchun ventilyatsiya"


@pytest.mark.asyncio
async def test_mijozga_nima_eshitilgani_KORSATILADI(baza, monkeypatch):
    """Model xato eshitsa, mijoz buni ko'rib darrov tuzatib yozadi."""
    bot, _ = ovoz_boti(baza, monkeypatch, matnga="ventilyatsiya kerak")
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())

    await bot.ovoz(update, None)

    assert any("ventilyatsiya kerak" in j for j in update.effective_message.javoblar)


@pytest.mark.asyncio
async def test_ogirib_bolmasa_ham_JAVOB_beriladi(baza, monkeypatch):
    from app.ovoz import OvozXatosi

    bot, chaqirilgan = ovoz_boti(baza, monkeypatch, xato=OvozXatosi("kvota"))
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())

    await bot.ovoz(update, None)

    assert update.effective_message.javoblar, "bot JIM QOLDI"
    assert "matn" in update.effective_message.javoblar[0].lower()
    assert "matn" not in chaqirilgan, "xato bo'lsa so'rov yuborilmasligi kerak"


@pytest.mark.asyncio
async def test_tarmoq_yiqilsa_ham_JAVOB_beriladi(baza, monkeypatch):
    bot, _ = ovoz_boti(baza, monkeypatch, xato=RuntimeError("tarmoq uzildi"))
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())

    await bot.ovoz(update, None)

    assert update.effective_message.javoblar, "bot JIM QOLDI"


@pytest.mark.asyncio
async def test_uzun_ovoz_rad_etiladi_va_sabab_aytiladi(baza, monkeypatch):
    from app import ovoz as ovoz_moduli

    bot, chaqirilgan = ovoz_boti(baza, monkeypatch, matnga="uzun")
    uzun = SoxtaOvoz(davomiylik=ovoz_moduli.MAKS_SONIYA + 1)
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), uzun)

    await bot.ovoz(update, None)

    javob = update.effective_message.javoblar[0]
    assert str(ovoz_moduli.MAKS_SONIYA) in javob
    assert "matn" not in chaqirilgan


def test_ovoz_ishlovchisi_ROYXATDAN_OTGAN():
    """Ishlovchi ulanmasa, modul ishlagani bilan bot jim qolaveradi."""
    import inspect
    from bot import mijoz

    manba = inspect.getsource(mijoz.yasa)
    assert "filters.VOICE" in manba
    assert "bot.ovoz" in manba


def test_mijoz_boti_SARFNI_YOZADI():
    """Mijozlar boti alohida jarayon — unda ham yozuvchi qo'yilishi shart.

    Qo'yilmasa, mijozlar bilan bo'lgan butun suhbat xarajati hisobga
    tushmaydi va `/sarf` haqiqiydan kam ko'rsatadi.
    """
    import inspect
    from bot import mijoz

    assert "yozuvchini_ol" in inspect.getsource(mijoz.yasa)


# --- ovozli javob -------------------------------------------------------------


def ovozli_javob_boti(baza, monkeypatch, javob="Narxi 12 million so'm",
                      ovoz_xatosi=None):
    from bot import mijoz as mijoz_moduli

    bot, _ = ovoz_boti(baza, monkeypatch, matnga="narxi qancha")
    yasalgan = {}

    async def soxta_ovozga(matn):
        if ovoz_xatosi:
            raise ovoz_xatosi
        yasalgan["matn"] = matn
        return b"RIFF" + b"\x00" * 40

    monkeypatch.setattr(mijoz_moduli.ovoz_moduli, "ovozga", soxta_ovozga)

    async def soxta_sorov(update, kontekst, matn=None):
        return javob

    bot.sorov = soxta_sorov
    return bot, yasalgan


@pytest.mark.asyncio
async def test_ovozga_ovoz_bilan_javob_qaytadi(baza, monkeypatch):
    bot, yasalgan = ovozli_javob_boti(baza, monkeypatch)
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())
    yuborilgan = []
    update.effective_message.reply_voice = (
        lambda w, **_: yuborilgan.append(w) or _bajarildi())

    await bot.ovoz(update, None)

    assert yuborilgan, "ovozli javob yuborilmadi"
    assert "12 million" in yasalgan["matn"]


def _bajarildi():
    import asyncio
    fut = asyncio.get_event_loop().create_future()
    fut.set_result(None)
    return fut


@pytest.mark.asyncio
async def test_ovoz_yasalmasa_MATN_baribir_qoladi(baza, monkeypatch):
    """Ovoz — qo'shimcha. U chiqmasa ham mijoz javobsiz qolmaydi."""
    bot, _ = ovozli_javob_boti(baza, monkeypatch,
                               ovoz_xatosi=RuntimeError("TTS yiqildi"))
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())
    update.effective_message.reply_voice = lambda w, **_: _bajarildi()

    await bot.ovoz(update, None)   # xato tashqariga chiqmasligi kerak

    assert update.effective_message.javoblar, "matn javobi ham yo'qoldi"


@pytest.mark.asyncio
async def test_javob_bosh_bolsa_ovoz_yasalmaydi(baza, monkeypatch):
    bot, yasalgan = ovozli_javob_boti(baza, monkeypatch, javob="")
    update = SoxtaOvozUpdate(SoxtaFoydalanuvchi(), SoxtaOvoz())
    update.effective_message.reply_voice = lambda w, **_: _bajarildi()

    await bot.ovoz(update, None)

    assert "matn" not in yasalgan, "bo'sh javobdan ovoz yasaldi"


def test_matnli_sorovga_ovoz_QOSHILMAYDI():
    """Matn bilan yozgan mijozga ovoz yuborilmaydi — u so'ramagan."""
    import inspect
    from bot import mijoz

    manba = inspect.getsource(mijoz.MijozBot.sorov)
    assert "_ovozli_javob" not in manba

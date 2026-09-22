"""Tender kuzatuvchisi Jasur — e'lon to'qimaslik, takrorlanmaslik, chegaralar."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.agentlar.tender_kuzatuvchi import TIZIM_PROMPT, TenderKuzatuvchi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch
from integrations.tender_manba import (
    Elon,
    LotHujjati,
    TenderXatosi,
    UzexManba,
    elonlarni_yig,
)
from presenter.agentlar import agent_matni

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim

KATALOG = [
    {"id": 1, "name_uz": "Kanal ventilyatori ВК-П",
     "category": {"name_uz": "Yumaloq kanallar uchun"}, "models": [], "characters": []},
    {"id": 2, "name_uz": "Kanalli isitgich ПВН",
     "category": {"name_uz": "To'rtburchak kanallar uchun"}, "models": [], "characters": []},
]

ELONLAR = [
    Elon(sarlavha="Ventilyatsiya tizimi uchun ventilyatorlar sotib olinadi",
         havola="https://uzex.uz/Announces/ventilyator", sana="21 07/2026",
         manba="uzex.uz e'lonlari"),
    Elon(sarlavha="Ofis mebellari yetkazib berish",
         havola="https://uzex.uz/Announces/mebel", sana="20 07/2026",
         manba="uzex.uz e'lonlari"),
]


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["tender-watch"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "jasur.db")
    await b.tayyorla()
    return b


class SoxtaManba:
    def __init__(self, elonlar=None, xato=None):
        self.nomi = "sinov manbasi"
        self._elonlar = elonlar if elonlar is not None else list(ELONLAR)
        self._xato = xato
        self.chaqirildi = 0

    async def elonlar(self, chek: int = 40):
        self.chaqirildi += 1
        if self._xato:
            raise TenderXatosi(self._xato)
        return self._elonlar[:chek]


def jasur_javobi(**ustama):
    malumot = {
        "mos_elonlar": [
            {"raqam": 1, "nimaga_kerak": "Kanal ventilyatorlari",
             "buyurtmachi": "O'zRTXB AJ", "muddat": "5 kun",
             "ishonch": "yuqori", "izoh": ""}
        ],
        "mos_emas_soni": 1,
        "xulosa": "Bitta ventilyatsiya e'loni topildi.",
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


def jasur_yasa(kontrakt, baza, llm, manba=None):
    return TenderKuzatuvchi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(mahsulotlar=KATALOG),
        qidiruv_manbasi=soxta_bilim(),
        manbalar=[manba or SoxtaManba()],
    )


# --- eng muhim: e'lon to'qib bo'lmaydi ---------------------------------------


@pytest.mark.asyncio
async def test_havola_manbadan_olinadi(kontrakt, baza):
    """O'ZGARMAS QOIDA: model havola yoza olmaydi, u manbadan qo'yiladi."""
    k = await jasur_yasa(kontrakt, baza, jasur_javobi()).ishla("Yangi tenderlar bormi?")

    assert k.holat is Holat.TUGADI
    mos = k.natija["mos_elonlar"]
    assert len(mos) == 1
    assert mos[0]["havola"] == "https://uzex.uz/Announces/ventilyator"
    assert mos[0]["sarlavha"] == ELONLAR[0].sarlavha


def test_model_havola_qaytara_olmaydi():
    """Chegara struktura darajasida: sxemada `havola` maydoni yo'q."""
    from app.agentlar.tender_kuzatuvchi import MosElon

    maydonlar = set(MosElon.model_fields)
    assert "havola" not in maydonlar
    assert "sarlavha" not in maydonlar
    assert "raqam" in maydonlar


@pytest.mark.asyncio
async def test_notogri_raqam_tashlanadi(kontrakt, baza):
    """Model ro'yxatda yo'q raqamni ko'rsatsa — e'lon o'ylab topilgan."""
    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 99, "nimaga_kerak": "x", "buyurtmachi": "", "muddat": "",
         "ishonch": "yuqori", "izoh": ""},
        {"raqam": 1, "nimaga_kerak": "Ventilyator", "buyurtmachi": "", "muddat": "",
         "ishonch": "yuqori", "izoh": ""},
    ])
    k = await jasur_yasa(kontrakt, baza, llm).ishla("tenderlar")

    assert len(k.natija["mos_elonlar"]) == 1
    assert k.natija["mos_elonlar"][0]["havola"].endswith("ventilyator")


# --- takrorlanmaslik ---------------------------------------------------------


@pytest.mark.asyncio
async def test_korilgan_elon_qayta_chiqmaydi(kontrakt, baza):
    """Har kuni ishlaydi — kecha ko'rsatilgani bugun qayta kelmasin."""
    manba = SoxtaManba()
    await jasur_yasa(kontrakt, baza, jasur_javobi(), manba).ishla("tenderlar")

    # Ikkinchi marta: LLM umuman chaqirilmasligi kerak (yangi e'lon yo'q)
    ikkinchi = jasur_yasa(kontrakt, baza, SoxtaLlm([]), manba)
    k = await ikkinchi.ishla("tenderlar")

    assert k.holat is Holat.TUGADI
    assert k.natija["mos_elonlar"] == []
    assert k.natija["yangi_korildi"] == 0
    assert "ilgari ko'rilgan" in k.natija["xulosa"]


@pytest.mark.asyncio
async def test_yangi_elon_qoshilsa_korsatiladi(kontrakt, baza):
    manba = SoxtaManba()
    await jasur_yasa(kontrakt, baza, jasur_javobi(), manba).ishla("tenderlar")

    yangi = Elon(sarlavha="Havo isitgichlari xaridi",
                 havola="https://uzex.uz/Announces/isitgich", manba="sinov manbasi")
    manba._elonlar = [*ELONLAR, yangi]

    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 1, "nimaga_kerak": "Havo isitgichi", "buyurtmachi": "",
         "muddat": "", "ishonch": "yuqori", "izoh": ""}
    ])
    k = await jasur_yasa(kontrakt, baza, llm, manba).ishla("tenderlar")

    assert k.natija["yangi_korildi"] == 1
    assert k.natija["mos_elonlar"][0]["havola"].endswith("isitgich")


# --- manba nosozliklari ------------------------------------------------------


@pytest.mark.asyncio
async def test_manba_yiqilsa_ochiq_aytiladi(kontrakt, baza):
    manba = SoxtaManba(xato="uzex.uz: ulanib bo'lmadi")
    k = await jasur_yasa(kontrakt, baza, SoxtaLlm([]), manba).ishla("tenderlar")

    assert k.holat is Holat.XATO
    assert "ulanib bo'lmadi" in k.izoh
    assert k.natija["qamrov_izohi"]


@pytest.mark.asyncio
async def test_bitta_manba_yiqilsa_qolgani_ishlaydi():
    """Nosozlik yutilmaydi, lekin butun kuzatuvni to'xtatmaydi."""
    ishlaydi = SoxtaManba()
    yiqilgan = SoxtaManba(xato="ikkinchi manba yiqildi")

    elonlar, nosozliklar = await elonlarni_yig([yiqilgan, ishlaydi])

    assert len(elonlar) == 2
    assert nosozliklar == ["ikkinchi manba yiqildi"]


@pytest.mark.asyncio
async def test_mos_elon_yoq_bolsa_ochiq_aytadi(kontrakt, baza):
    llm = jasur_javobi(mos_elonlar=[], xulosa="Ventilyatsiyaga aloqador e'lon yo'q.")
    k = await jasur_yasa(kontrakt, baza, llm).ishla("tenderlar")

    assert k.holat is Holat.TUGADI
    assert k.natija["mos_elonlar"] == []
    assert "Yangi mos e'lon yo'q" in k.izoh
    assert k.ishonch is Ishonch.ORTA


# --- chegaralar --------------------------------------------------------------


def test_promptda_chegaralar():
    assert "E'LON O'YLAB TOPMAYSAN" in TIZIM_PROMPT
    assert "ariza topshirmaysan" in TIZIM_PROMPT
    assert "BASHORAT QILMAYSAN" in TIZIM_PROMPT
    assert "Temur" in TIZIM_PROMPT  # KP boshqa agentning ishi


def test_kontraktda_ariza_taqiqlangan():
    kontrakt = kontraktlarni_yukla()["tender-watch"]
    chegaralar = " ".join(kontrakt.chegaralar).upper()

    assert "ARIZA TOPSHIRMAYDI" in chegaralar
    assert "PAROL" in chegaralar  # yopiq portalga kirmaydi
    assert kontrakt.xavf.value == "past"


@pytest.mark.asyncio
async def test_qamrov_cheklovi_har_javobda(kontrakt, baza):
    """Foydalanuvchi qamrov cheklanganini bilib tursin.

    Aniq so'zlar emas, MAZMUNI tekshiriladi: qaysi manba ko'rilgani va
    nima ko'rinmay qolishi mumkinligi aytilgan bo'lsin. (Avval bu test
    «xarid.uzex.uz» degan aniq matnni qidirardi va manba almashganda
    yiqildi — holbuki qoida buzilmagandi.)
    """
    k = await jasur_yasa(kontrakt, baza, jasur_javobi()).ishla("tenderlar")

    izoh = k.natija["qamrov_izohi"]
    assert "etender.uzex.uz" in izoh          # qaysi manba ko'rilgan
    assert "bo'lishi mumkin" in izoh          # nima ko'rinmasligi mumkin
    # O'CHIRILGAN manbalar ham aytilsin: menejer "hammasi ko'rildi" deb
    # o'ylab qolmasin.
    assert "O'CHIRILGAN" in izoh
    matn = agent_matni("tender-watch", k.natija)
    assert "Qamrov" in matn


# --- ko'rinish ---------------------------------------------------------------


def test_tender_korinishi():
    matn = agent_matni("tender-watch", {
        "mos_elonlar": [{
            "sarlavha": "Ventilyatorlar xaridi", "havola": "https://uzex.uz/x",
            "sana": "21 07/2026", "buyurtmachi": "AGMK",
            "nimaga_kerak": "Kanal ventilyatorlari", "muddat": "5 kun", "izoh": "",
        }],
        "yangi_korildi": 3, "mos_emas_soni": 2,
        "xulosa": "Bitta mos e'lon.",
        "qamrov_izohi": "Qamrov cheklangan: ...",
    })

    assert "Ventilyatorlar xaridi" in matn
    assert "AGMK" in matn
    assert "https://uzex.uz/x" in matn
    assert "5 kun" in matn
    assert "3 ta yangi e'lon ko'rildi" in matn


# --- manba qatlami (HTML tahlili) --------------------------------------------


SAHIFA = """
<div class="blog__date">21 07/2026</div>
<a class="blog__title" href="/Announces/ventilyator-xaridi">Ventilyator&#x2018;lar xaridi </a>
<div class="blog__date">20 07/2026</div>
<a class="blog__title" href="/Announces/mebel-xaridi">Ofis mebellari</a>
"""


@pytest.mark.asyncio
async def test_uzex_sahifasi_tahlil_qilinadi():
    import httpx

    def ishlov(soro: httpx.Request) -> httpx.Response:
        # Ikkinchi sahifa bo'sh — to'xtash sharti tekshiriladi
        sahifa = soro.url.params.get("page")
        return httpx.Response(200, text=SAHIFA if sahifa == "1" else "<html></html>")

    mijoz = httpx.AsyncClient(transport=httpx.MockTransport(ishlov))
    elonlar = await UzexManba(mijoz=mijoz).elonlar()

    assert len(elonlar) == 2
    assert elonlar[0].sarlavha == "Ventilyator‘lar xaridi"
    assert elonlar[0].havola == "https://uzex.uz/Announces/ventilyator-xaridi"
    assert elonlar[0].sana == "21 07/2026"
    # Kalit havoladan olinadi — barqaror
    assert elonlar[0].kalit == "https://uzex.uz/announces/ventilyator-xaridi"


@pytest.mark.asyncio
async def test_sayt_ochilmasa_xato_beriladi():
    import httpx

    def ishlov(soro: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("tarmoq yo'q")

    mijoz = httpx.AsyncClient(transport=httpx.MockTransport(ishlov))
    with pytest.raises(TenderXatosi, match="ulanib bo'lmadi"):
        await UzexManba(mijoz=mijoz).elonlar()


# --- avtomatik kunlik kuzatuv ------------------------------------------------


def test_kuzatuv_vaqti_oqiladi():
    from app.config import Sozlama

    def vaqt(xom):
        return Sozlama(anthropic_api_key="x", tender_kuzatuv_vaqti=xom).tender_vaqti

    assert vaqt("09:00") == (9, 0)
    assert vaqt("9:30") == (9, 30)
    assert vaqt("23:59") == (23, 59)
    # Bo'sh yoki buzuq qiymat — kuzatuv o'chiriladi, yiqilmaydi
    assert vaqt("") is None
    assert vaqt("25:00") is None
    assert vaqt("salom") is None


def test_oluvchilar_royxati():
    """Alohida ro'yxat bo'lmasa — umumiy whitelist."""
    from app.config import Sozlama

    s = Sozlama(anthropic_api_key="x", bot_ruxsat_etilgan_id="111,222")
    assert s.tender_idlar == {111, 222}

    s = Sozlama(
        anthropic_api_key="x", bot_ruxsat_etilgan_id="111,222",
        tender_kuzatuv_id="222",
    )
    assert s.tender_idlar == {222}


@pytest.mark.asyncio
async def test_mos_elon_bolsa_xabar_yuboriladi(baza, monkeypatch):
    from app.konvert import Ishonch, Konvert, Manba
    from bot.asosiy import Bot

    yuborilgan: list[tuple[int, str]] = []

    class SoxtaBot:
        async def send_message(self, tg_id, matn, **kw):
            yuborilgan.append((tg_id, matn))

    class SoxtaKontekst:
        bot = SoxtaBot()

    konvert = Konvert(
        kim="tender-watch", holat=Holat.TUGADI,
        natija={"mos_elonlar": [{
            "sarlavha": "Ventilyatorlar xaridi", "havola": "https://uzex.uz/x",
            "sana": "", "buyurtmachi": "AGMK", "nimaga_kerak": "Kanal ventilyatori",
            "muddat": "", "izoh": "",
        }], "yangi_korildi": 1, "mos_emas_soni": 0, "xulosa": ""},
        manba=[Manba(tur="veb", nom="uzex", havola="https://uzex.uz/x")],
        ishonch=Ishonch.YUQORI,
    )

    class SoxtaOrkestr:
        async def agentni_chaqir(self, rol, vazifa, kontekst=None):
            assert rol == "tender-watch"
            return konvert

    bot = Bot.__new__(Bot)
    bot.s = type("S", (), {"tender_idlar": {111, 222}, "bot_maks_belgi": 3000})()
    bot.korinishlar = {"tender-watch": "Tender kuzatuvchisi Jasur"}
    bot.baza = baza
    monkeypatch.setattr(bot, "orkestr", lambda: SoxtaOrkestr(), raising=False)

    await Bot.tender_tekshiruvi(bot, SoxtaKontekst())

    assert sorted(t[0] for t in yuborilgan) == [111, 222]
    assert "Ventilyatorlar xaridi" in yuborilgan[0][1]
    assert "🔔" in yuborilgan[0][1]
    # Bajarilgan kun yozilsin — busiz o'tkazib yuborilganini bilib bo'lmaydi.
    assert await baza.rejali_ish_kuni("tender-kuzatuvi") == date.today().isoformat()


def _soxta_bot(monkeypatch, konvert, baza=None):
    """Tender tekshiruvi uchun eng kichik Bot nusxasi + yozib boruvchi kontekst."""
    from bot.asosiy import Bot

    yuborilgan: list[tuple[int, str]] = []

    class SoxtaBot:
        async def send_message(self, tg_id, matn, **kw):
            yuborilgan.append((tg_id, matn))

    class SoxtaKontekst:
        bot = SoxtaBot()

    class SoxtaOrkestr:
        async def agentni_chaqir(self, rol, vazifa, kontekst=None):
            if isinstance(konvert, Exception):
                raise konvert
            return konvert

    bot = Bot.__new__(Bot)
    bot.s = type("S", (), {"tender_idlar": {111}, "bot_maks_belgi": 3000})()
    bot.korinishlar = {"tender-watch": "Tender kuzatuvchisi Jasur"}
    if baza is not None:
        bot.baza = baza
    monkeypatch.setattr(bot, "orkestr", lambda: SoxtaOrkestr(), raising=False)
    return bot, SoxtaKontekst(), yuborilgan


@pytest.mark.asyncio
async def test_mos_elon_yoq_bolsa_ham_xabar_keladi(baza, monkeypatch):
    """Jimlik ikki ma'noli edi: "tekshirdim, yo'q" va "tekshirmadim".

    Foydalanuvchi talabi: topsa ham, topmasa ham xabar bo'lsin. Lekin
    quruq "hech narsa yo'q" emas — ichida nima ko'rilgani turishi kerak,
    aks holda xabar bir haftada o'qilmay qoladi.
    """
    from app.konvert import Ishonch, Konvert, Manba

    konvert = Konvert(
        kim="tender-watch", holat=Holat.TUGADI,
        natija={
            "mos_elonlar": [], "yangi_korildi": 7, "jami_korildi": 19,
            "manbalar": ["uzex.uz"],
            "xulosa": "E'lonlar asosan qurilish materiallariga tegishli.",
            "qamrov_izohi": "Qamrov cheklangan: davlat portallari yopiq.",
        },
        manba=[Manba(tur="kontrakt", nom="tender-watch")],
        ishonch=Ishonch.ORTA,
    )
    bot, ctx, yuborilgan = _soxta_bot(monkeypatch, konvert, baza)

    await type(bot).tender_tekshiruvi(bot, ctx)

    assert len(yuborilgan) == 1
    matn = yuborilgan[0][1]
    assert "mos e'lon topilmadi" in matn
    # Xabar MAZMUNLI bo'lishi kerak — quruq inkor emas.
    # Nechta OCHIQ e'lon ko'rilgani aytiladi. "Manbada jami" va
    # "ilgari ko'rilgan" farqi olib tashlandi — har tekshiruv endi
    # hozir ochiq lotlarni beradi, ya'ni ikkalasi bir xil narsa.
    assert "7 ta" in matn
    assert "uzex.uz" in matn              # qayerdan qaralgan
    assert "qurilish materiallari" in matn  # nega mos emas
    assert "Qamrov cheklangan" in matn    # nimani ko'ra olmaymiz


@pytest.mark.asyncio
async def test_yangi_elon_bolmasa_ham_tushuntiriladi(baza, monkeypatch):
    """Hammasi ilgari ko'rilgan bo'lsa — buni ochiq aytish kerak."""
    from app.konvert import Ishonch, Konvert, Manba

    konvert = Konvert(
        kim="tender-watch", holat=Holat.TUGADI,
        natija={"mos_elonlar": [], "yangi_korildi": 0, "jami_korildi": 19},
        manba=[Manba(tur="kontrakt", nom="tender-watch")],
        ishonch=Ishonch.ORTA,
    )
    bot, ctx, yuborilgan = _soxta_bot(monkeypatch, konvert, baza)

    await type(bot).tender_tekshiruvi(bot, ctx)

    matn = yuborilgan[0][1]
    # "ILGARI KO'RILGAN" DEGAN GAP OLIB TASHLANDI (2026-09-09).
    #
    # U eski mantiqdan qolgan edi: tekshiruv faqat YANGI lotni
    # qidirardi. Endi har tekshiruv HOZIR OCHIQ lotlarni beradi —
    # menejer uchun lot ilgari ko'rilganmi yoki yo'qmi ahamiyatsiz,
    # muhimi u hali ochiqmi.
    assert "ilgari ko'rilgan" not in matn
    assert "Yangisi chiqmagan" not in matn
    # O'rniga: nechta ochiq e'lon ko'rilgani aytiladi.
    assert "ochiq e'lon ko'rildi" in matn


@pytest.mark.asyncio
async def test_kuzatuv_yiqilsa_nosozlik_aytiladi(monkeypatch):
    """Nosozlikda jim qolish eng yomoni: tizim ishlayapti deb o'ylanadi."""
    bot, ctx, yuborilgan = _soxta_bot(monkeypatch, RuntimeError("tarmoq yo'q"))

    await type(bot).tender_tekshiruvi(bot, ctx)  # xato ko'tarilmasligi kerak

    assert len(yuborilgan) == 1
    matn = yuborilgan[0][1]
    assert "Tekshiruv bajarilmadi" in matn
    assert "tarmoq yo'q" in matn
    assert "/tender" in matn


@pytest.mark.asyncio
async def test_agentni_chaqir_routersiz_ishlaydi(baza):
    """Rejali ish uchun router chaqirilmaydi — ortiqcha xarajat va noaniqlik."""
    from app.kontraktlar import kontraktlarni_yukla
    from app.orkestr import Orkestr

    llm = SoxtaLlm([])  # router chaqirilsa test yiqiladi
    orkestr = Orkestr(llm, baza, kontraktlarni_yukla())

    k = await orkestr.agentni_chaqir("nomalum-agent", "x")
    assert k.holat is Holat.XATO
    assert "Noma'lum agent" in k.izoh


# --- manba bergan ma'lumot model taxminidan ustun -----------------------------


@pytest.mark.asyncio
async def test_manba_buyurtmachisi_model_taxminini_yengadi(kontrakt, baza):
    """DXMAP buyurtmachini STIR bilan beradi — model uni "tuzatmasin".

    Havoladagi tamoyilning davomi: tekshirib bo'ladigan ma'lumot
    modelning taxminidan ustun turadi.
    """
    elon = Elon(
        sarlavha="Metall ventilyatsiya shaxtasi",
        havola="https://xarid.icppa.uz/contracts/organ/200236998/262110088570255/BUDGET",
        manba="DXMAP (xarid.icppa.uz)",
        lot_raqami="262110088570255",
        buyurtmachi='"ANDIJON VILOYAT KO`P TARMOQLI TIBBIYOT MARKAZI" DM',
        buyurtmachi_stir="200236998",
        summa=12_500_000,
    )
    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 1, "nimaga_kerak": "Ventilyatsiya kanallari",
         "buyurtmachi": "Andijon shifoxonasi",   # modelning qisqartmasi
         "muddat": "", "ishonch": "yuqori", "izoh": ""},
    ])
    k = await jasur_yasa(kontrakt, baza, llm, manba=SoxtaManba([elon])).ishla("tenderlar")

    mos = k.natija["mos_elonlar"][0]
    assert mos["buyurtmachi"] == elon.buyurtmachi
    assert mos["lot_raqami"] == "262110088570255"
    assert mos["summa"] == 12_500_000


@pytest.mark.asyncio
async def test_manba_jim_bolsa_model_toldiradi(kontrakt, baza):
    """Erkin matnli manbada buyurtmachi yo'q — o'shanda model yordam beradi."""
    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 1, "nimaga_kerak": "Ventilyator", "buyurtmachi": "O'zRTXB AJ",
         "muddat": "", "ishonch": "yuqori", "izoh": ""},
    ])
    k = await jasur_yasa(kontrakt, baza, llm).ishla("tenderlar")

    assert k.natija["mos_elonlar"][0]["buyurtmachi"] == "O'zRTXB AJ"


@pytest.mark.asyncio
async def test_qidiruv_qamrovi_javobda_korinadi(kontrakt, baza):
    """Kalit so'z bo'yicha qidirilgani menejerdan yashirilmaydi."""
    from integrations.tender_manba import DxmapManba

    k = await jasur_yasa(
        kontrakt, baza, jasur_javobi(),
        manba=DxmapManba(kalit_sozlar=("ventilyatsiya",)),
    ).ishla("tenderlar")
    # DxmapManba tarmoqqa chiqadi — bu yerda faqat qamrov matni tekshiriladi.
    assert any("ventilyatsiya" in q for q in k.natija.get("qidiruv_qamrovi", []))


@pytest.mark.asyncio
async def test_lot_raqami_va_summa_menejerga_korinadi(kontrakt, baza):
    """Menejer portalda lot raqami bilan qidiradi — u xabarda bo'lishi shart."""
    elon = Elon(
        sarlavha="Rekuperator",
        havola="https://xarid.icppa.uz/contracts/organ/200555349/262110088479707/BUDGET",
        manba="DXMAP (xarid.icppa.uz)",
        lot_raqami="262110088479707",
        buyurtmachi="BOSH PROKURATURA",
        buyurtmachi_stir="200555349",
        summa=12_500_000,
        hudud="Toshkent shahar",
        maydoncha="xarid.uzex.uz",
    )
    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 1, "nimaga_kerak": "Issiqlik almashtirgich", "buyurtmachi": "",
         "muddat": "", "ishonch": "yuqori", "izoh": ""},
    ])
    k = await jasur_yasa(kontrakt, baza, llm, manba=SoxtaManba([elon])).ishla("tenderlar")

    matn = agent_matni("tender-watch", k.natija)
    assert "262110088479707" in matn
    assert "12 500 000 so'm" in matn
    assert "200555349" in matn, "buyurtmachi STIRi ko'rinmadi"
    assert "Toshkent shahar" in matn
    # Havola ham bo'lishi shart — menejer lot kartochkasini shundan ochadi.
    assert elon.havola in matn
    # BUYURTMACHI NOMI YOZILMAYDI: uzun, tirnoqlar bilan buzilgan holda
    # keladi va STIR ustiga hech narsa qo'shmaydi.
    assert "BOSH PROKURATURA" not in matn


def test_sana_muddat_deb_korsatilmaydi():
    """E'lon sanasi tugash muddati EMAS — prompt buni ochiq aytadi."""
    from app.agentlar.tender_kuzatuvchi import TIZIM_PROMPT, TenderKuzatuvchi

    matn = TenderKuzatuvchi._elon_matni([
        Elon(sarlavha="Rekuperator", havola="https://x/1", sana="2026-09-04")
    ])
    assert "e'lon sanasi" in matn
    assert "MUDDATNI O'YLAB TOPMAYSAN" in TIZIM_PROMPT


# --- xizmat lotlari (2026-09-08 da o'lchangan kamchilik) ---------------------


def test_promptda_XIZMAT_lotlari_ham_bor():
    """O'LCHANDI: xizmat lotlari jimgina rad etilardi.

    Jasur 11 ta haqiqiy tenderdan 6 tasini o'tkazib yuborardi —
    hammasi "texnik xizmat", "montaj", "ta'mirlash" lotlari. Model
    to'g'ri o'ylardi ("biz uskuna sotamiz"), lekin kompaniya montaj,
    puskonaladka va servis ham qilishini unga hech kim aytmagandi.

    Tuzatilgach: 5/11 -> 11/11, aniqlik 0.846 -> 0.974.
    """
    tekis = " ".join(TIZIM_PROMPT.split()).lower()

    assert "montaj" in tekis, "montaj xizmati promptda yo'q"
    assert "servis" in tekis, "servis xizmati promptda yo'q"
    assert "ta'mirlash" in tekis
    # Eng muhimi — rad etmaslik ko'rsatmasi.
    assert "rad etmaysan" in tekis


def test_promptda_MAISHIY_split_chegarasi_bor():
    """Doira kengaytirilgach, teskari xato paydo bo'ldi.

    Xizmatlar qo'shilgach model maishiy split YETKAZIB BERISH lotini
    ham mos deb belgiladi. Kompaniya splitni ishlab chiqarmaydi
    (katalogda КЦКП va IXCHAM — sanoat/markaziy), lekin
    konditsionerlash tizimiga SERVIS qiladi. Chegara aynan shu yerda.
    """
    tekis = " ".join(TIZIM_PROMPT.split())

    assert "MAISHIY" in tekis
    assert "КЦКП" in tekis, "sanoat konditsioneri misoli yo'q"
    # 2026-09-09 da kengaytirildi: pretsizion konditsioner va aniq
    # chet el modeli ham bizniki emas. Jonli holat: pretsizion
    # konditsioner lotlari "yuqori" ishonch bilan kelardi.
    assert "PRETSIZION" in tekis
    assert "CHET EL" in tekis
    # Xizmat tomoni ochiq qolishi kerak — mavzu butunlay taqiqlanmasin.
    assert "MONTAJ va SERVIS bizning" in tekis
    # Va ular RAD ETILMAYDI, past ishonch bilan pastga tushadi.
    assert 'ishonch: "past"' in tekis


def test_JASUR_profilda_xizmatlarni_koradi():
    """Prompt yetarli emas: profil ham xizmatlarni bermasa, model
    kompaniya nima qilishini bilmaydi."""
    from app.profil import AGENT_BOLIMLARI

    assert "xizmatlar" in AGENT_BOLIMLARI.get("tender-watch", ())


def test_kontraktda_xizmat_ham_qamralgan():
    kontrakt = kontraktlarni_yukla()["tender-watch"]
    matn = (kontrakt.maqsad + " " + " ".join(kontrakt.output)).lower()

    assert "xizmat" in matn
    assert "montaj" in matn or "servis" in matn


# --- xabar ko'rinishi va bo'linishi (2026-09-09) -----------------------------


def test_uzun_xabar_KESILMAYDI_bolinadi():
    """JIM YO'QOTISH EDI.

    Jonli holat: 12 ta mos e'lon topilgan, menejerga 5 tasi yetgan.
    Qolgan 7 tasi `matn[:maks]` bilan kesilib, hech qayerda
    ko'rinmasdan yo'qolgan.
    """
    from presenter.matn import xabarni_bol

    bitta = ("=" * 28) + "\n1. Lot nomi\n\nLot:     123\nSTIR:    456\n\n"
    matn = bitta * 12

    bolaklar = xabarni_bol(matn, 400)

    assert len(bolaklar) > 1, "bo'linmadi"
    # HAMMA e'lon saqlanishi kerak — bittasi ham tushib qolmasin.
    assert sum(b.count("=" * 28) for b in bolaklar) == 12
    assert all(len(b) <= 400 for b in bolaklar)


def test_bolish_ELON_ortasidan_kesmaydi():
    """Bo'lish joyi ajratgich bo'yicha tanlanadi."""
    from presenter.matn import xabarni_bol

    bitta = ("=" * 28) + "\n1. Nomi\n\nLot:     123\nHudud:   Toshkent\n\n"
    bolaklar = xabarni_bol(bitta * 6, 300)

    for b in bolaklar[1:]:
        assert b.startswith("=" * 28), f"e'lon o'rtasidan kesildi: {b[:40]!r}"


def test_qisqa_xabar_bolinmaydi():
    from presenter.matn import xabarni_bol

    assert xabarni_bol("qisqa matn", 4000) == ["qisqa matn"]
    assert xabarni_bol("", 4000) == []


def test_TAKROR_izoh_yozilmaydi():
    """Model sarlavhani qayta yozib beradi — bu shovqin.

    Jonli namuna:
      sarlavha     "Ventilyatsiya tizimiga texnik xizmat ko'rsatish"
      nimaga_kerak "Ventilyatsiya tizimlariga texnik xizmat ko'rsatish xizmati"
    """
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [{
        "sarlavha": "Ventilyatsiya tizimiga texnik xizmat ko'rsatish",
        "nimaga_kerak": "Ventilyatsiya tizimlariga texnik xizmat ko'rsatish xizmati",
        "izoh": "Ventilyatsiya tizimiga texnik xizmat ko'rsatish bo'yicha lot.",
        "lot_raqami": "1",
    }]})

    assert "Izoh:" not in matn, matn


def test_YANGI_malumot_beruvchi_izoh_QOLADI():
    """Miqdor va model kodi sarlavhada yo'q — u foydali."""
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [{
        "sarlavha": "Metall ventilyatsiya shaxtasi",
        "nimaga_kerak": "Kanal ventilyatori ВКП 40x20, 12 dona kerak",
        "lot_raqami": "1",
    }]})

    assert "12 dona" in matn


def test_har_elon_AJRATGICH_bilan_ajratiladi():
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [
        {"sarlavha": "Birinchi", "lot_raqami": "1"},
        {"sarlavha": "Ikkinchi", "lot_raqami": "2"},
    ]})

    assert matn.count("=" * 28) >= 2


def test_mos_elon_bolsa_QADAM_izohi_qoshiladi():
    """Menejer nima qilishini bilishi kerak."""
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [{"sarlavha": "Rekuperator",
                                       "lot_raqami": "1",
                                       "maydoncha": "xarid.uzex.uz"}]})

    assert "NIMA QILISH KERAK" in matn
    assert "lot raqami bo'yicha qidirasiz" in matn


def test_QADAM_izohida_toqilgan_tartib_YOQ():
    """Ro'yxatdan o'tish tartibi, to'lov, kafolat puli TEKSHIRILMAGAN.

    Ular portal qoidasi va o'zgaradi — xotiradan yozilsa menejer
    noto'g'ri yo'lga tushardi. Shuning uchun izoh ularni ATAYLAB
    aytmaydi, faqat "kartochkadagi shartlarni o'qing" deydi.
    """
    from presenter.agentlar import QADAM_IZOHI

    past = QADAM_IZOHI.lower()
    # Konkret summa yoki foiz aytilmasin.
    assert "%" not in QADAM_IZOHI
    assert "so'm" not in past
    assert "shartlarni o'qing" in past


def test_MANBA_muddati_model_taxminidan_USTUN():
    """`etender.uzex.uz` haqiqiy tugash sanasini beradi.

    Ilgari kodda `"muddat": baho.muddat` turardi — modelning qiymati
    manbadagi ANIQ sanani ustidan yozib yuborardi. Muddati o'tgan
    lotga ariza berilmaydi, ya'ni bu maydon xato bo'lsa menejer
    behuda ish qiladi.
    """
    import inspect

    from app.agentlar import tender_kuzatuvchi

    manba = inspect.getsource(tender_kuzatuvchi.TenderKuzatuvchi._javob)
    assert 'if not elon.muddat and baho.muddat:' in manba
    assert '"muddat": baho.muddat,' not in manba


# --- tartib: etender birinchi, kattadan kichikka (2026-09-09) ----------------


def _elon(nomi, maydoncha, summa):
    return Elon(sarlavha=nomi, havola=f"https://x/{nomi}",
                maydoncha=maydoncha, summa=summa)


def test_ETENDER_lotlari_birinchi_turadi():
    """O'LCHANDI: 8 ta etender loti 134 ta DXMAP lotidan 4 barobar
    ko'p pul olib keladi (16,84 mlrd va 4,31 mlrd), mediana esa 12
    barobar katta (130 mln va 11 mln)."""
    from app.agentlar.tender_kuzatuvchi import _tartibla

    tartib = _tartibla([
        _elon("dxmap katta", "xt-xarid.uz", 7_000_000_000),
        _elon("etender kichik", "etender.uzex.uz", 50_000_000),
    ])

    assert [e.sarlavha for e in tartib] == ["etender kichik", "dxmap katta"]


def test_har_guruh_ichida_KATTADAN_kichikka():
    from app.agentlar.tender_kuzatuvchi import _tartibla

    tartib = _tartibla([
        _elon("e-kichik", "etender.uzex.uz", 50_000_000),
        _elon("d-kichik", "xarid.uzex.uz", 1_000_000),
        _elon("e-katta", "etender.uzex.uz", 9_000_000_000),
        _elon("d-katta", "xarid.uzex.uz", 700_000_000),
    ])

    assert [e.sarlavha for e in tartib] == [
        "e-katta", "e-kichik", "d-katta", "d-kichik",
    ]


def test_summasiz_elon_OXIRIDA_qoladi():
    """Summasi yo'q e'lon haqida hech narsa deya olmaymiz."""
    from app.agentlar.tender_kuzatuvchi import _tartibla

    tartib = _tartibla([
        _elon("summasiz", "xarid.uzex.uz", None),
        _elon("arzon", "xarid.uzex.uz", 1_000),
    ])

    assert [e.sarlavha for e in tartib] == ["arzon", "summasiz"]


@pytest.mark.asyncio
async def test_UMUMIY_chek_manbani_yoq_qilmaydi():
    """JIM YO'QOTISH EDI.

    `elonlarni_yig` da `[:chek]` turardi. DXMAP yolg'iz 156 e'lon
    berardi, chek esa 150 — `etender` lotlari ro'yxatga UMUMAN
    kirmasdi. Aynan o'sha lotlar eng qimmatlisi edi.
    """
    kop = SoxtaManba([
        Elon(sarlavha=f"dxmap {i}", havola=f"https://d/{i}",
             maydoncha="xarid.uzex.uz", summa=1000)
        for i in range(160)
    ])
    kam = SoxtaManba([
        Elon(sarlavha="etender katta", havola="https://e/1",
             maydoncha="etender.uzex.uz", summa=9_000_000_000)
    ])

    elonlar, _ = await elonlarni_yig([kop, kam], 150)

    havolalar = {e.havola for e in elonlar}
    assert "https://e/1" in havolalar, "ikkinchi manba butunlay yo'qoldi"


@pytest.mark.asyncio
async def test_ODAM_sorasa_KORILGANLAR_ham_korsatiladi(kontrakt, baza):
    """`/tender` — "hozir nima bor", "yangi nima bor" EMAS.

    JONLI HOLAT: 13 ta lot jurnalda "ko'rilgan" deb turgan (o'tkazib
    yuborilgan ish jimgina bajargan), menejer esa ularni ko'rmagan.
    `/tender` yozganda javob "hammasi ilgari ko'rilgan" bo'lib chiqdi —
    ya'ni tizimda lot bor, lekin menejer uni ko'ra olmaydi.
    """
    manba = SoxtaManba()
    # Birinchi yurish — hammasi jurnalga tushadi.
    await jasur_yasa(kontrakt, baza, jasur_javobi(), manba).ishla("tenderlar")

    # Kunlik ish: yangisi yo'q.
    kunlik = await jasur_yasa(kontrakt, baza, SoxtaLlm([]), manba).ishla("tenderlar")
    assert kunlik.natija["mos_elonlar"] == []
    assert kunlik.natija["yangi_korildi"] == 0

    # Odam so'radi: ro'yxat BARIBIR ko'rsatiladi.
    qolda = await jasur_yasa(kontrakt, baza, jasur_javobi(), manba).ishla(
        "tenderlar", {"hammasini_korsat": True}
    )
    assert qolda.natija["yangi_korildi"] == len(ELONLAR)
    assert qolda.natija["mos_elonlar"], "qo'lda so'rovda ham bo'sh qaytdi"


def test_TENDER_buyrugi_hammasini_soraydi():
    """Buyruq va agent orasidagi bog'lanish uzilib qolmasin."""
    import inspect

    from bot.asosiy import Bot

    manba = inspect.getsource(Bot.tender)
    assert "hammasini_korsat=True" in manba

    tekshiruv = inspect.getsource(Bot.tender_tekshiruvi)
    assert "hammasini_korsat" in tekshiruv


# --- muddati o'tgan lot ko'rsatilmaydi (2026-09-09) --------------------------


def test_muddati_OTGAN_lot_tashlanadi():
    """Muddati o'tgan lotga taklif berib bo'lmaydi — u foydasiz."""
    from app.agentlar.tender_kuzatuvchi import _muddati_otmaganlar

    qolgan, tashlangan = _muddati_otmaganlar([
        Elon(sarlavha="eski", havola="https://x/1", muddat="2020-01-01"),
        Elon(sarlavha="yangi", havola="https://x/2", muddat="2099-12-31"),
    ])

    assert [e.sarlavha for e in qolgan] == ["yangi"]
    assert tashlangan == 1


def test_BUGUN_tugaydigan_lot_QOLADI():
    """Muddat 23:59 da tugaydi — kun bo'yi taklif berish mumkin."""
    from datetime import datetime

    from app.agentlar.tender_kuzatuvchi import MINTAQA, _muddati_otmaganlar

    bugun = datetime.now(MINTAQA).date().isoformat()
    qolgan, tashlangan = _muddati_otmaganlar([
        Elon(sarlavha="bugun", havola="https://x/1", muddat=bugun),
    ])

    assert len(qolgan) == 1 and tashlangan == 0


def test_muddati_NOMALUM_lot_ham_qoladi():
    """Manba muddat bermasa, biz uni o'tgan deb qaror qila olmaymiz.

    DXMAP shunday: 156 lotdan nolida muddat bor. Jimgina tashlash —
    bor imkoniyatni yo'qotish.
    """
    from app.agentlar.tender_kuzatuvchi import _muddati_otmaganlar

    qolgan, tashlangan = _muddati_otmaganlar([
        Elon(sarlavha="muddatsiz", havola="https://x/1"),
    ])

    assert len(qolgan) == 1 and tashlangan == 0


@pytest.mark.asyncio
async def test_muddati_otganlar_soni_OCHIQ_aytiladi(kontrakt, baza):
    """Jimgina tashlansa, menejer manba ishlamayapti deb o'ylardi."""
    manba = SoxtaManba([
        Elon(sarlavha="eski lot", havola="https://x/1", muddat="2020-01-01"),
        Elon(sarlavha="Ventilyatsiya tizimi", havola="https://x/2",
             muddat="2099-12-31"),
    ])
    llm = jasur_javobi(mos_elonlar=[
        {"raqam": 1, "nimaga_kerak": "Ventilyatsiya", "buyurtmachi": "",
         "muddat": "", "ishonch": "yuqori", "izoh": ""},
    ])
    k = await jasur_yasa(kontrakt, baza, llm, manba).ishla("tenderlar")

    assert k.natija["muddati_otgan"] == 1
    # Ko'rsatilganlar ichida eskisi YO'Q.
    assert all("/1" not in m["havola"] for m in k.natija["mos_elonlar"])
    assert "muddati o'tgani uchun" in agent_matni("tender-watch", k.natija)


@pytest.mark.asyncio
async def test_hammasi_muddati_otgan_bolsa_OCHIQ_aytadi(kontrakt, baza):
    """«Mos e'lon yo'q» va «hammasi eskirgan» — boshqa ma'no."""
    manba = SoxtaManba([
        Elon(sarlavha="eski", havola="https://x/1", muddat="2020-01-01"),
    ])
    k = await jasur_yasa(kontrakt, baza, SoxtaLlm([]), manba).ishla("tenderlar")

    assert k.natija["mos_elonlar"] == []
    assert "muddati o'tgan" in k.natija["xulosa"]


# --- ikki marta tekshirish va kesh (2026-09-09) ------------------------------


@pytest.mark.parametrize("xom,kutilgan", [
    ("09:00,15:00", [(9, 0), (15, 0)]),
    ("09:00", [(9, 0)]),
    ("", []),
    # Noto'g'ri vaqt JIMGINA tashlanadi, qolganlari ishlaydi —
    # bitta xato butun kuzatuvni to'xtatmasin.
    ("09:00, 25:00, 15:30", [(9, 0), (15, 30)]),
    # Takror bir marta.
    ("09:00,09:00", [(9, 0)]),
])
def test_bir_nechta_kuzatuv_vaqti(xom, kutilgan):
    from app.config import Sozlama

    assert Sozlama(tender_kuzatuv_vaqti=xom).tender_vaqtlari == kutilgan


def test_eski_tender_vaqti_BIRINCHISINI_qaytaradi():
    """Eski kod `tender_vaqti` ni kutadi — u buzilmasin."""
    from app.config import Sozlama

    s = Sozlama(tender_kuzatuv_vaqti="09:00,15:00")
    assert s.tender_vaqti == (9, 0)


def test_IKKINCHI_tekshiruv_jim_turadi():
    """Kuniga ikki xil bir xil ro'yxat kelsa, menejer o'qishni to'xtatadi.

    Shuning uchun keyingi tekshiruvlar faqat YANGI lot chiqqanda
    xabar beradi.
    """
    import inspect

    from bot.asosiy import Bot, _kuzatuvni_rejala

    reja = inspect.getsource(_kuzatuvni_rejala)
    assert "jim=not birinchimi" in reja

    tekshiruv = inspect.getsource(Bot.tender_tekshiruvi)
    # Ro'yxat O'ZGARMAGAN bo'lsa jim turadi ("yangi lot yo'q" emas —
    # ikkalasi ham hozir OCHIQ lotlarni ko'rsatadi).
    assert "faqat_yangilik and matn.strip() == eski_matn.strip()" in tekshiruv


def test_kesh_yozib_oqiladi(tmp_path, monkeypatch):
    """`/tender` shu keshdan darhol javob beradi."""
    from bot import tender_keshi

    monkeypatch.setattr(tender_keshi, "FAYL", tmp_path / "kesh.json")

    assert tender_keshi.oqi() is None
    tender_keshi.yoz("Mos e'lonlar (2 ta)")
    saqlangan = tender_keshi.oqi()

    assert saqlangan is not None
    matn, vaqt = saqlangan
    assert matn == "Mos e'lonlar (2 ta)"
    assert tender_keshi.yoshi_daqiqa(vaqt) == 0


def test_buzuq_kesh_YIQITMAYDI(tmp_path, monkeypatch):
    """Fayl buzilsa `/tender` ishlashda davom etsin."""
    from bot import tender_keshi

    fayl = tmp_path / "kesh.json"
    fayl.write_text("{buzuq", encoding="utf-8")
    monkeypatch.setattr(tender_keshi, "FAYL", fayl)

    assert tender_keshi.oqi() is None


def test_TENDER_buyrugi_keshdan_javob_beradi():
    """"Tekshiryapman…" deb 20 soniya kuttirmasin."""
    import inspect

    from bot.asosiy import Bot

    manba = inspect.getsource(Bot.tender)
    assert "tender_keshi.oqi()" in manba
    # Kesh bo'lmasagina kutish xabari chiqadi.
    assert manba.index("saqlangan is None") < manba.index("Tekshiryapman")


def test_BIZNIKI_EMAS_uskuna_pastga_tushadi():
    """Pretsizion konditsioner, chet el brendi — uskunasi bizniki emas.

    JONLI HOLAT (2026-09-09): pretsizion konditsioner lotlari "yuqori"
    ishonch bilan kelardi va ro'yxat boshida turardi. Menejer ularni
    "to'liq bizniki" deb o'ylab tayyorgarlik ko'rishi mumkin edi.
    """
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [
        {"sarlavha": "Pretsizion konditsioner", "lot_raqami": "1",
         "summa": 9e9, "ishonch": "past"},
        {"sarlavha": "Ventilyatsiya tizimi", "lot_raqami": "2",
         "summa": 1e8, "ishonch": "yuqori"},
    ]})

    assert "BIZGA MOS (1 ta)" in matn
    assert "BIZGA TEGISHLI BO'LISHI MUMKIN (1 ta)" in matn
    # Kattaroq summa bo'lsa ham pastda.
    assert matn.index("Ventilyatsiya tizimi") < matn.index("Pretsizion")


def test_hammasi_ANIQ_bolsa_ikkinchi_bolim_yoq():
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [
        {"sarlavha": "Ventilyatsiya", "lot_raqami": "1", "ishonch": "yuqori"},
    ]})

    assert "TEGISHLI BO'LISHI MUMKIN" not in matn


# --- muddat eslatmasi va ogohlantirish (2026-09-09) --------------------------


def test_muddat_ogohi_kunga_qarab():
    """Sana o'zi yetarli emas — menejer ro'yxatni tez o'qiydi."""
    from datetime import timedelta

    from presenter.agentlar import _bugun, _muddat_ogohi

    bugun = _bugun()
    assert "BUGUN TUGAYDI" in _muddat_ogohi(bugun.isoformat())
    assert "1 kun qoldi" in _muddat_ogohi((bugun + timedelta(days=1)).isoformat())
    assert "2 kun qoldi" in _muddat_ogohi((bugun + timedelta(days=2)).isoformat())
    # Uzoq muddat — ogohlantirish shart emas, shovqin bo'lardi.
    assert _muddat_ogohi((bugun + timedelta(days=10)).isoformat()) == ""
    # Noto'g'ri sana yiqitmasin.
    assert _muddat_ogohi("nomalum") == ""


def test_shoshilinch_eslatma_keshdan_oqiladi():
    """LLM chaqirilmaydi — ro'yxat oxirgi tekshiruv matnidan olinadi."""
    from datetime import timedelta

    from bot.tender_keshi import shoshilinchlar
    from presenter.agentlar import _bugun

    bugun = _bugun()
    matn = (
        "=" * 28 + "\n1. Yaqin lot\n\nLot:     1\n"
        f"Muddat:  {bugun.isoformat()}\n\n"
        + "=" * 28 + "\n2. Uzoq lot\n\nLot:     2\n"
        f"Muddat:  {(bugun + timedelta(days=30)).isoformat()}\n"
    )

    xabar = shoshilinchlar(matn, 2)

    assert "Yaqin lot" in xabar
    assert "BUGUN tugaydi" in xabar
    assert "Uzoq lot" not in xabar


def test_eslatadigan_narsa_yoq_bolsa_JIM():
    """Bo'sh eslatma yubormaymiz — u faqat e'tiborni yeydi."""
    from datetime import timedelta

    from bot.tender_keshi import shoshilinchlar
    from presenter.agentlar import _bugun

    uzoq = (_bugun() + timedelta(days=30)).isoformat()
    matn = "=" * 28 + f"\n1. Uzoq\n\nLot:     1\nMuddat:  {uzoq}\n"

    assert shoshilinchlar(matn, 2) == ""


def test_RAD_ETILGAN_sozlar_kalit_royxatida_YOQ():
    """O'lchandi: bu so'zlar shovqin keltiradi, qayta qo'shilmasin.

    `kanal` +12 lot berardi va hammasi SUG'ORISH kanali edi.
    """
    from integrations.tender_manba import DXMAP_KALIT_SOZLAR, RAD_ETILGAN_SOZLAR

    for soz in RAD_ETILGAN_SOZLAR:
        assert soz not in DXMAP_KALIT_SOZLAR, f"«{soz}» qayta qo'shilgan"


def test_yangi_kalit_sozlar_qoshilgan():
    """O'lchov bilan tanlangan: `chiller` +2 lot, `isitish` +1."""
    from integrations.tender_manba import DXMAP_KALIT_SOZLAR

    for soz in ("chiller", "чиллер", "isitish", "отоплен"):
        assert soz in DXMAP_KALIT_SOZLAR


# --- katalog NOMLARI promptga tushadi (2026-09-09) ---------------------------


@pytest.mark.asyncio
async def test_katalogda_MAHSULOT_NOMLARI_beriladi(kontrakt, baza):
    """Faqat kategoriya nomi yetarli emas — model adashadi.

    JONLI HOLAT: modelga "Issiqlik almashish uskunalari: 14" berilardi
    va u neftni qayta ishlash uchun QOBIQ-TRUBALI apparatni ham shu
    kategoriyaga qo'shdi. Bizniki esa HAVO uchun mis-alyuminiy (VNV,
    VOV). Xuddi shunday "Ventilyatsiya panjaralari: 11" ni ko'rib
    RULONLI panjarani (to'siq jalyuzi) mos dedi.
    """
    katalog = [
        {"id": 1, "name_uz": "Mis-alyuminiy issiqlik almashtirgich VNV",
         "category": {"name_uz": "Issiqlik almashish uskunalari"},
         "models": [], "characters": []},
        {"id": 2, "name_uz": "Shamollatish panjarasi РВ-1",
         "category": {"name_uz": "Ventilyatsiya panjaralari"},
         "models": [], "characters": []},
    ]
    llm = jasur_javobi()
    jasur = TenderKuzatuvchi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(mahsulotlar=katalog),
        qidiruv_manbasi=soxta_bilim(),
        manbalar=[SoxtaManba()],
    )
    await jasur.ishla("tenderlar")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "Mis-alyuminiy issiqlik almashtirgich VNV" in xabar
    assert "Shamollatish panjarasi РВ-1" in xabar
    # Kategoriya nomiga o'xshaganlik yetarli emasligi ochiq aytilsin.
    assert "YETARLI EMAS" in xabar


def test_promptda_ADASHTIRGAN_misollar_bor():
    """Model aynan shularda adashgan — misol bilan yozib qo'yilgan."""
    tekis = " ".join(TIZIM_PROMPT.split())

    assert "RULONLI panjara" in tekis
    assert "QOBIQ-TRUBALI" in tekis
    assert "muzlatgich" in tekis
    # Aralash lot ham past ishonch oladi.
    assert "ARALASH LOT" in tekis


# --- kesh FAQAT lotli natijani saqlaydi (2026-09-09) -------------------------


def test_botsh_natija_KESHNI_buzmaydi(tmp_path, monkeypatch):
    """JONLI HOLAT: kesh "mos e'lon topilmadi" xabarini saqlab qoldi.

    `/tender` uni darhol qaytaraverdi va menejer lot bor-yo'qligini
    bila olmadi. Endi bo'sh natija eskisini o'chirmaydi.
    """
    from bot import tender_keshi

    monkeypatch.setattr(tender_keshi, "FAYL", tmp_path / "kesh.json")

    lotli = "=" * 28 + "\n1. Ventilyatsiya\n\nMuddat:  2026-09-20"
    tender_keshi.yoz(lotli)

    assert tender_keshi.lotlimi(lotli) is True
    assert tender_keshi.lotlimi("Bizga mos e'lon topilmadi.") is False


def test_KESHGA_faqat_lotli_natija_yoziladi():
    """Kod darajasida: bo'sh natija keshni almashtirmaydi."""
    import inspect

    from bot.asosiy import Bot

    manba = inspect.getsource(Bot.tender_tekshiruvi)
    assert "if mos:\n            tender_keshi.yoz(matn)" in manba


def test_TENDER_lotsiz_keshda_qayta_tekshiradi():
    """Lotsiz keshni ko'rsatishning ma'nosi yo'q."""
    import inspect

    from bot.asosiy import Bot

    assert "tender_keshi.lotlimi" in inspect.getsource(Bot.tender)


def test_ILGARI_KORILGAN_gapi_kodda_YOQ():
    """Menejer uchun lot ko'rilganmi emas, OCHIQmi degani muhim."""
    import inspect

    from bot.asosiy import Bot

    manba = inspect.getsource(Bot._tender_xabari)
    assert "hammasi ilgari ko'rilgan" not in manba
    assert "Yangisi chiqmagan" not in manba


def test_kesh_ishlab_turgan_faylga_yozmaydi():
    """JONLI MUAMMO (2026-09-09): test soxta loti `/tender` da chiqib qoldi.

    `Bot.tender_tekshiruvi` natijani `chiqish/tender_keshi.json` ga
    yozadi. Test uni to'g'ridan-to'g'ri chaqirgani uchun HAQIQIY faylga
    tushib, menejer `/tender` bosganda "AGMK — Ventilyatorlar xaridi"
    degan soxta lot ko'rsatilardi.

    Tarmoq va katalogga yozish bloklangan edi, diskdagi kesh esa ochiq
    qolgan. `conftest.chiqish_yopiq` uni yopadi — shu blok yo'qolmasin.
    """
    from pathlib import Path

    from bot import tender_keshi

    assert tender_keshi.FAYL != Path("chiqish/tender_keshi.json"), (
        "kesh ishlab turgan faylga yo'naltirilgan — test uni buzadi"
    )
    # Ishlab turgan fayl BOR bo'lishi mumkin — uni haqiqiy bot yozadi.
    # Tekshiriladigan narsa: test uni YARATMASIN va O'ZGARTIRMASIN.
    ishlab_turgan = Path("chiqish/tender_keshi.json")
    oldin = ishlab_turgan.read_bytes() if ishlab_turgan.exists() else None

    tender_keshi.yoz("sinov matni")

    assert tender_keshi.FAYL.exists(), "vaqtinchalik faylga yozilmadi"
    keyin = ishlab_turgan.read_bytes() if ishlab_turgan.exists() else None
    assert keyin == oldin, "test ishlab turgan keshni yaratdi yoki o'zgartirdi"


# --- summa o'z valyutasida (2026-09-14) ----------------------------------------
#
# etender da 866 lotdan 54 tasi DOLLARDA, 10 tasi YEVRODA. Ilgari hammasi
# "so'm" deb ko'rsatilardi: 81 205,70 dollarlik lot "81 206 so'm" edi.


def test_dollar_lot_DOLLAR_deb_korinadi():
    from presenter.agentlar import tenderlar

    matn = tenderlar({"mos_elonlar": [{
        "sarlavha": "Press", "lot_raqami": "1", "summa": 81205.7,
        "valyuta": "USD", "maydoncha": "etender.uzex.uz",
    }]})

    assert "Narx:    81 205,70 dollar" in matn
    assert "81 206 so'm" not in matn


def test_saralashda_valyuta_somga_keltiriladi():
    """100 000 dollar (~1,18 mlrd so'm) 500 mln so'mdan TEPADA turishi kerak."""
    from app.agentlar.tender_kuzatuvchi import _tartibla

    dollar = Elon(sarlavha="dollar", havola="https://e/1", maydoncha="etender.uzex.uz",
                  summa=100_000, valyuta="USD")
    som = Elon(sarlavha="som", havola="https://e/2", maydoncha="etender.uzex.uz",
               summa=500_000_000)

    tartib = _tartibla([som, dollar], {"UZS": 1.0, "USD": 11765.76})

    assert [e.sarlavha for e in tartib] == ["dollar", "som"]


def test_kurs_nomalum_bolsa_taxmin_qilinmaydi():
    """Kurs yo'q — xorijiy lot summasiz lot kabi pastga tushadi."""
    from app.agentlar.tender_kuzatuvchi import _tartibla

    dollar = Elon(sarlavha="dollar", havola="https://e/1", maydoncha="etender.uzex.uz",
                  summa=100_000, valyuta="USD")
    som = Elon(sarlavha="som", havola="https://e/2", maydoncha="etender.uzex.uz",
               summa=1_000)

    assert [e.sarlavha for e in _tartibla([dollar, som])] == ["som", "dollar"]


# --- begona brend (2026-09-14) ------------------------------------------------
#
# 510351-lot "VRF tashqi bloklariga ta'mir" "bizga mos" deb chiqdi, TZ da
# esa AUX ARV6-H610 turardi. Sarlavhada brend yo'q edi.


def _etender_elon():
    return Elon(
        sarlavha="Konditsionerlash VRF tizimlarining tashqi bloklariga joriy ta'mirlash",
        havola="https://etender.uzex.uz/lot/510351",
        maydoncha="etender.uzex.uz",
        lot_raqami="26110012510351",
        summa=50_000_000,
    )


def hujjat_bahosi(*baholar):
    """Ikkinchi so'rov — hujjat bahosi — javobi."""
    return javob([matn_bloki(json.dumps({"baholar": list(baholar)}, ensure_ascii=False))])


def ikki_bosqich(*baholar, **ustama):
    llm = jasur_javobi(**ustama)
    llm.javoblar.append(hujjat_bahosi(*baholar))
    return llm


def hujjat_qoy(monkeypatch, hujjat, chaqiruvlar=None, funksiya="etender_lot_hujjatlari"):
    import integrations.tender_manba as tender_manba

    async def yukla(lot_id, mijoz=None):
        if chaqiruvlar is not None:
            chaqiruvlar.append(lot_id)
        return hujjat

    monkeypatch.setattr(tender_manba, funksiya, yukla)


@pytest.mark.asyncio
async def test_begona_brend_TZ_dan_topiladi_va_pastga_tushadi(kontrakt, baza, monkeypatch):
    chaqiruvlar: list[str] = []
    hujjat_qoy(
        monkeypatch,
        LotHujjati(fayllar=[("tz.pdf", "- Марка/модель: ARV6-H610/SR1MV")]),
        chaqiruvlar,
    )
    # Hujjat bahosi ham "yuqori" deydi — brend baribir USTUN.
    llm = ikki_bosqich({"raqam": 1, "mos": True, "ishonch": "yuqori"})

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert chaqiruvlar == ["510351"]
    mos = k.natija["mos_elonlar"][0]
    assert mos["begona_brend"] == ["AUX (ARV6-H610/SR1MV)"]
    assert mos["ishonch"] == "past"
    assert k.natija["brend_tekshirilmadi"] == 0

    matn = agent_matni("tender-watch", k.natija)
    assert "⚠ Brend:  AUX (ARV6-H610/SR1MV) — bizniki emas" in matn
    assert matn.index("BIZGA TEGISHLI BO'LISHI MUMKIN") < matn.index("⚠ Brend:")


@pytest.mark.asyncio
async def test_TZ_oqilmasa_tekshirilmadi_deb_ochiq_aytiladi(kontrakt, baza, monkeypatch):
    """O'qilmagan TZ "brend yo'q" deb jimgina hisoblanmasin."""
    import integrations.tender_manba as tender_manba

    async def yiqilgan(lot_id, mijoz=None):
        raise tender_manba.TenderXatosi("lot 510351: tafsilot 404 qaytardi")

    monkeypatch.setattr(tender_manba, "etender_lot_hujjatlari", yiqilgan)

    k = await jasur_yasa(
        kontrakt, baza, jasur_javobi(), manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    mos = k.natija["mos_elonlar"][0]
    assert "begona_brend" not in mos
    assert mos["ishonch"] == "yuqori"
    assert k.natija["brend_tekshirilmadi"] == 1
    assert "1 ta lotning texnik topshirig'i o'qilmadi" in agent_matni("tender-watch", k.natija)


@pytest.mark.asyncio
async def test_hech_fayli_oqilmagan_lot_ham_tekshirilmagan(kontrakt, baza, monkeypatch):
    """Kartochka ochildi, lekin TZ fayli o'qilmadi — "brend yo'q" EMAS."""
    hujjat_qoy(monkeypatch, LotHujjati(oqilmagan=["tz.doc: eski Word formati"]))

    k = await jasur_yasa(
        kontrakt, baza, jasur_javobi(), manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert k.natija["brend_tekshirilmadi"] == 1
    assert "O'qilmadi: tz.doc: eski Word formati" in agent_matni("tender-watch", k.natija)


@pytest.mark.asyncio
async def test_boshqa_maydon_lot_hujjati_yuklanmaydi(kontrakt, baza, monkeypatch):
    chaqiruvlar: list[str] = []
    hujjat_qoy(monkeypatch, LotHujjati(), chaqiruvlar)
    hujjat_qoy(monkeypatch, LotHujjati(), chaqiruvlar, funksiya="mcuz_lot_hujjatlari")

    await jasur_yasa(kontrakt, baza, jasur_javobi()).ishla("tenderlar")

    assert chaqiruvlar == []


# --- hujjat bahosi (2026-09-14) -----------------------------------------------
#
# Uchala "mos" lotning xavfi faqat HUJJATDA edi: 287840 — ta'mir emas,
# loyiha-smeta; 511606 — ehtiyot qismlar ijrochi hisobidan; 511261 —
# tajriba hujjatisiz chetlashtiriladi. Sarlavhada birortasi yo'q.


@pytest.mark.asyncio
async def test_hujjat_bahosi_aslida_va_shartlar_korsatiladi(kontrakt, baza, monkeypatch):
    hujjat_qoy(monkeypatch, LotHujjati(
        karta="Lot kartochkasi",
        shartlar=["Baholash: Eng past narx usuli"],
        fayllar=[("TZ.pdf",
                  "Ehtiyot qismlar Ijrochi hisobidan. Tel: +998 93 524 10 60, "
                  "bosh muhandis X.Akromov, tender@misol.uz")],
    ))
    llm = ikki_bosqich({
        "raqam": 1, "mos": True, "ishonch": "past",
        "aslida": "Faqat loyiha-smeta hujjatlarini tuzish, ta'mirning o'zi emas",
        "talablar": ["Ehtiyot qismlar ijrochi hisobidan", " "],
    })

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    mos = k.natija["mos_elonlar"][0]
    assert mos["ishonch"] == "past"
    assert mos["tz_aslida"].startswith("Faqat loyiha-smeta")
    assert mos["tz_talablar"] == ["Ehtiyot qismlar ijrochi hisobidan"]   # bo'sh tashlandi
    assert mos["shartlar"] == ["Baholash: Eng past narx usuli"]
    assert k.natija["hujjat_baholanmadi"] == ""
    # Sarlavha bo'yicha xulosa "yuqori" degan edi — eskirgani aytiladi.
    assert k.natija["xulosa"].startswith("Sarlavha bo'yicha dastlabki xulosa:")
    assert "Hujjatlar o'qilgach 1 ta lotning bahosi o'zgardi" in k.natija["xulosa"]

    # Hujjat modelga BORDI, shaxsiy ma'lumot esa YO'Q.
    sorov = json.dumps(llm.chaqiruvlar[1], ensure_ascii=False, default=str)
    assert "Ehtiyot qismlar Ijrochi hisobidan" in sorov
    for sir in ("524 10 60", "Akromov", "tender@misol.uz"):
        assert sir not in sorov

    matn = agent_matni("tender-watch", k.natija)
    assert "Aslida:  Faqat loyiha-smeta hujjatlarini tuzish" in matn
    assert "  · Baholash: Eng past narx usuli" in matn
    assert "  ⚠ Ehtiyot qismlar ijrochi hisobidan" in matn
    # Sarlavha bo'yicha izoh hujjatga zid bo'lishi mumkin — ko'rsatilmaydi.
    assert "Izoh:" not in matn


@pytest.mark.asyncio
async def test_hamma_lot_hujjati_BITTA_sorovda(kontrakt, baza, monkeypatch):
    """Gemini bepul tarifida kuniga 20 so'rov — har lotga alohida bo'lmaydi."""
    hujjat_qoy(monkeypatch, LotHujjati(fayllar=[("tz.pdf", "Texnik topshiriq")]))
    ikkinchi = Elon(
        sarlavha="Sanoat chilleri", havola="https://etender.uzex.uz/lot/511261",
        maydoncha="etender.uzex.uz", summa=8700, valyuta="USD",
    )
    llm = ikki_bosqich(
        {"raqam": 1, "aslida": "Birinchi lot aslida"},
        {"raqam": 2, "aslida": "Ikkinchi lot aslida"},
        mos_elonlar=[
            {"raqam": 1, "ishonch": "yuqori"},
            {"raqam": 2, "ishonch": "yuqori"},
        ],
    )

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon(), ikkinchi])
    ).ishla("tenderlar")

    assert len(llm.chaqiruvlar) == 2
    assert {m["tz_aslida"] for m in k.natija["mos_elonlar"]} == {
        "Birinchi lot aslida", "Ikkinchi lot aslida",
    }
    # Model bermagan ishonch sarlavha bahosini ALMASHTIRMAYDI.
    assert {m["ishonch"] for m in k.natija["mos_elonlar"]} == {"yuqori"}
    # Baho o'zgarmagan — xulosa ham o'zgarmaydi.
    assert k.natija["xulosa"] == "Bitta ventilyatsiya e'loni topildi."


@pytest.mark.asyncio
async def test_hujjat_mos_emas_desa_sababi_bilan_chiqariladi(kontrakt, baza, monkeypatch):
    hujjat_qoy(monkeypatch, LotHujjati(fayllar=[("tz.pdf", "Yo'l qurilishi")]))
    llm = ikki_bosqich(
        {"raqam": 1, "mos": False, "aslida": "Avtomobil yo'li qurilishi"}
    )

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert k.natija["mos_elonlar"] == []
    assert k.natija["mos_emas_soni"] == 1
    assert k.natija["hujjat_chiqargan"] == [{
        "sarlavha": _etender_elon().sarlavha,
        "havola": "https://etender.uzex.uz/lot/510351",
        "sabab": "Avtomobil yo'li qurilishi",
    }]
    matn = agent_matni("tender-watch", k.natija)
    assert "Hujjati o'qilgach 1 ta lot chiqarildi:" in matn
    assert "— Avtomobil yo'li qurilishi" in matn


@pytest.mark.asyncio
async def test_sababsiz_mos_emas_etiborsiz_qoladi(kontrakt, baza, monkeypatch):
    hujjat_qoy(monkeypatch, LotHujjati(fayllar=[("tz.pdf", "TZ")]))
    llm = ikki_bosqich({"raqam": 1, "mos": False, "aslida": ""})

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert len(k.natija["mos_elonlar"]) == 1
    assert k.natija["hujjat_chiqargan"] == []


@pytest.mark.asyncio
async def test_hujjat_bahosi_yiqilsa_sarlavha_bahosi_qoladi(kontrakt, baza, monkeypatch):
    hujjat_qoy(monkeypatch, LotHujjati(
        shartlar=["Avans: 15%"], fayllar=[("tz.pdf", "TZ")],
    ))
    llm = jasur_javobi()
    llm.javoblar.append(javob([matn_bloki("kechirasiz, JSON bera olmayman")]))

    k = await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert k.holat is Holat.TUGADI
    mos = k.natija["mos_elonlar"][0]
    assert mos["ishonch"] == "yuqori"
    assert "tz_aslida" not in mos
    assert k.natija["hujjat_baholanmadi"]
    matn = agent_matni("tender-watch", k.natija)
    # Kodda olingan shart model yiqilsa ham ko'rinadi.
    assert "  · Avans: 15%" in matn
    assert "⚠ Hujjatlar o'qildi, lekin model baholay olmadi" in matn


@pytest.mark.asyncio
async def test_hujjati_bosh_lot_uchun_model_chaqirilmaydi(kontrakt, baza):
    llm = jasur_javobi()

    await jasur_yasa(
        kontrakt, baza, llm, manba=SoxtaManba([_etender_elon()])
    ).ishla("tenderlar")

    assert len(llm.chaqiruvlar) == 1


@pytest.mark.asyncio
async def test_mcuz_lot_hujjati_ham_oqiladi(kontrakt, baza, monkeypatch):
    chaqiruvlar: list[str] = []
    hujjat_qoy(
        monkeypatch,
        LotHujjati(shartlar=["Obyekt turi: Проектно-изыскательный"]),
        chaqiruvlar,
        funksiya="mcuz_lot_hujjatlari",
    )
    elon = Elon(
        sarlavha="Oshxona ventilyatsiyasini joriy ta'mirlash",
        havola="https://tender.mc.uz/tender-list/tender/287840/view",
        maydoncha="tender.mc.uz", summa=1_452_080,
    )
    llm = ikki_bosqich({
        "raqam": 1, "ishonch": "past",
        "aslida": "Loyiha-smeta hujjatlarini ishlab chiqish",
    })

    k = await jasur_yasa(kontrakt, baza, llm, manba=SoxtaManba([elon])).ishla("tenderlar")

    assert chaqiruvlar == ["287840"]
    mos = k.natija["mos_elonlar"][0]
    assert mos["shartlar"] == ["Obyekt turi: Проектно-изыскательный"]
    assert mos["tz_aslida"] == "Loyiha-smeta hujjatlarini ishlab chiqish"


def test_parcha_TZ_ga_andozadan_kop_joy_beradi():
    from app.agentlar.tender_kuzatuvchi import _hujjat_parchasi

    hujjat = LotHujjati(fayllar=[
        ("Xarid hujjati.pdf", "andoza " * 5000),
        ("Chiller TZ.pdf", "parametr\n\n\n " * 400),   # bo'shliqlar siqiladi
        ("Baholash tartibi.pdf", "mezon " * 50),
    ])

    parcha = _hujjat_parchasi(hujjat, 6000)

    assert len(parcha) < 6400
    # Kalta fayl TO'LIQ kiradi, ortgan joy qolganlarga o'tadi.
    assert parcha.count("mezon") == 50
    assert parcha.count("parametr") == 400
    assert "--- Xarid hujjati.pdf ---" in parcha
    assert "…[qisqartirildi]" in parcha

"""Loyihachi muhandis Rustam — `hvac-calc`.

Asosiy xavf: model raqamni "to'qib" chiqarishi. Shuning uchun bu yerda
eng muhim tekshiruv — modelning javob sxemasida hisob natijasi UMUMAN
yo'qligi va raqamlar faqat koddan kelishi.
"""

from __future__ import annotations

import json

import pytest

from app.agentlar.loyihachi import Loyihachi, RustamNatija, XonaKirishi
from app.baza import Baza
from app.konvert import Holat
from app.kontraktlar import kontraktlarni_yukla

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim

KATALOG = [
    {
        "id": 25, "name_uz": "ВК-С ventilyatori", "name_ru": "Вентилятор ВК-С",
        "models": [
            {"name": "ВК-200С"}, {"name": "ВК-250С"}, {"name": "ВК-315С"},
        ],
    },
    {
        "id": 31, "name_uz": "Kanal isitgichi", "name_ru": "ПВН",
        "models": [{"name": "ПВН 500-250-2"}],
    },
]


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["hvac-calc"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "rustam.db")
    await b.tayyorla()
    return b


def rustam_javobi(**maydonlar):
    tana = {
        "obyekt": "Ombor binosi",
        "xonalar": [
            {"nomi": "Asosiy ombor", "turi": "ombor", "maydon": 800,
             "balandlik": 6, "odamlar": 0, "izoh": ""}
        ],
        "kanal_turi": "magistral",
        "sorash_kerak": [],
        "eslatmalar": [],
    }
    tana.update(maydonlar)
    return SoxtaLlm([javob([matn_bloki(json.dumps(tana, ensure_ascii=False))])])


def rustam_yasa(kontrakt, baza, llm, katalog=KATALOG):
    return Loyihachi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(mahsulotlar=katalog), qidiruv_manbasi=soxta_bilim(),
    )


# --- model hisoblay OLMAYDI ---------------------------------------------------


def test_model_sxemasida_hisob_maydoni_yoq():
    """Eng muhim himoya: model raqam qaytara olmasligi KERAK.

    Agar sxemaga `havo_sarfi` qo'shilsa, model uni to'ldiradi va
    natija chaqiruvdan chaqiruvga o'zgarib turadi.
    """
    maydonlar = set(RustamNatija.model_fields)
    taqiqlangan = {
        "havo_sarfi", "sarf", "diametr", "kanal_diametri", "tezlik",
        "hajm", "bosim",
    }
    assert not (maydonlar & taqiqlangan)

    xona_maydonlari = set(XonaKirishi.model_fields)
    assert not (xona_maydonlari & taqiqlangan)
    # Faqat kirish parametrlari
    assert {"maydon", "balandlik", "odamlar", "turi"} <= xona_maydonlari


@pytest.mark.asyncio
async def test_raqamlar_koddan_keladi(kontrakt, baza):
    """Model 800 m² × 6 m dedi — qolganini kod hisoblaydi."""
    k = await rustam_yasa(kontrakt, baza, rustam_javobi()).ishla("ombor uchun hisob")

    assert k.holat is Holat.TUGADI
    xona = k.natija["xonalar"][0]
    assert xona["hajm"] == 4800            # 800 × 6
    assert xona["havo_sarfi"] == 9600      # 2 karra × 4800
    assert xona["diametr"] == 800
    assert 5.0 <= xona["tezlik"] <= 8.0


# --- o'lcham yetishmasa TAXMIN QILINMAYDI ------------------------------------


@pytest.mark.asyncio
async def test_olcham_yetishmasa_soraydi(kontrakt, baza):
    """"Odatda 3 metr bo'ladi" — bu taxmin, taqiqlanadi."""
    llm = rustam_javobi(xonalar=[
        {"nomi": "Zal", "turi": "ofis", "maydon": 200, "balandlik": 0,
         "odamlar": 0, "izoh": ""}
    ], sorash_kerak=["Balandligi qancha?"])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("200 m² zal uchun hisob")

    assert k.holat is Holat.ANIQLIK_KERAK
    assert any("balandlig" in s.lower() for s in k.natija["savollar"])


@pytest.mark.asyncio
async def test_xona_umuman_aytilmasa_soraydi(kontrakt, baza):
    llm = rustam_javobi(xonalar=[], sorash_kerak=["Qaysi xona?"])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("hisoblab bering")

    assert k.holat is Holat.ANIQLIK_KERAK


# --- ikki usul: kattasi olinadi ----------------------------------------------


@pytest.mark.asyncio
async def test_odam_normasi_kattaroq_bolsa_yutadi(kontrakt, baza):
    """Kichik majlis xonasi, ko'p odam — odam normasi ustun."""
    llm = rustam_javobi(xonalar=[
        {"nomi": "Majlis", "turi": "majlis", "maydon": 20, "balandlik": 3,
         "odamlar": 30, "izoh": ""}
    ])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("majlis xonasi")

    xona = k.natija["xonalar"][0]
    assert xona["karrali_boyicha"] == 360
    assert xona["odam_boyicha"] == 1800
    assert xona["havo_sarfi"] == 1800
    assert xona["usul"] == "odam boshiga"


# --- bir nechta xona ----------------------------------------------------------


@pytest.mark.asyncio
async def test_bir_nechta_xona_va_umumiy_magistral(kontrakt, baza):
    llm = rustam_javobi(xonalar=[
        {"nomi": "Ofis 1", "turi": "ofis", "maydon": 100, "balandlik": 3,
         "odamlar": 0, "izoh": ""},
        {"nomi": "Ofis 2", "turi": "ofis", "maydon": 100, "balandlik": 3,
         "odamlar": 0, "izoh": ""},
    ])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("ikki ofis")

    assert len(k.natija["xonalar"]) == 2
    assert k.natija["jami_sarf"] == 1800       # 900 + 900
    assert k.natija["umumiy_diametr"] >= k.natija["xonalar"][0]["diametr"]


# --- katalog moslashuvi -------------------------------------------------------


@pytest.mark.asyncio
async def test_katalogdan_diametr_boyicha_topiladi(kontrakt, baza):
    """Katalogda quvvat yo'q — moslik model NOMIDAGI diametr bo'yicha."""
    llm = rustam_javobi(xonalar=[
        {"nomi": "Xona", "turi": "ofis", "maydon": 100, "balandlik": 3,
         "odamlar": 0, "izoh": ""}
    ])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("ofis")

    xona = k.natija["xonalar"][0]
    uskunalar = {u["diametr"]: u["modellar"] for u in k.natija["uskunalar"]}
    assert xona["diametr"] in uskunalar
    if xona["diametr"] == 250:
        assert "ВК-250С" in uskunalar[250]


@pytest.mark.asyncio
async def test_katalog_ishlamasa_hisob_toxtamaydi(kontrakt, baza):
    from integrations import ApiXatosi

    class YiqiluvchiApi:
        async def mahsulotlar(self):
            raise ApiXatosi("API yiqildi")

    agent = Loyihachi(
        kontrakt=kontrakt, llm=rustam_javobi(), baza=baza,
        api=YiqiluvchiApi(), qidiruv_manbasi=soxta_bilim(),
    )
    k = await agent.ishla("ombor")

    assert k.holat is Holat.TUGADI
    assert k.natija["xonalar"][0]["havo_sarfi"] == 9600   # hisob bor
    assert k.natija["uskunalar"] == []                    # tavsiya yo'q
    assert "katalogga ulanib bo'lmadi" in agent.ogohlantirish


# --- manba va tasdiq ----------------------------------------------------------


@pytest.mark.asyncio
async def test_norma_manbasi_ochiq_aytiladi(kontrakt, baza):
    """Normativ hujjat deb ko'rsatib bo'lmaydi — bu umumiy amaliyot."""
    k = await rustam_yasa(kontrakt, baza, rustam_javobi()).ishla("ombor")

    eslatmalar = " ".join(k.natija["eslatmalar"])
    assert "rasmiy normativ hujjat ko'chirmasi emas" in eslatmalar
    assert "solishtirilishi shart" in eslatmalar


@pytest.mark.asyncio
async def test_hisob_tasdiqdan_otadi(kontrakt, baza):
    """Hisob loyihaga ketadi — muhandis ko'rib chiqsin."""
    k = await rustam_yasa(kontrakt, baza, rustam_javobi()).ishla("ombor")

    assert k.tasdiq_kerak is True


@pytest.mark.asyncio
async def test_notanish_xona_turi_ogohlantiriladi(kontrakt, baza):
    llm = rustam_javobi(xonalar=[
        {"nomi": "Kosmodrom", "turi": "kosmodrom", "maydon": 100,
         "balandlik": 3, "odamlar": 0, "izoh": ""}
    ])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("kosmodrom")

    assert any("kosmodrom" in o for o in k.natija["ogohlantirishlar"])


# --- chegaralar ---------------------------------------------------------------


def test_promptda_chegaralar():
    from app.agentlar.loyihachi import TIZIM_PROMPT

    tekis = " ".join(TIZIM_PROMPT.split())
    assert "HISOBLAMAYSAN" in tekis
    assert "TAXMIN QILMAYSAN" in tekis
    assert "NORMATIV HUJJATGA HAVOLA QILMAYSAN" in tekis


def test_promptda_xona_turlari_beriladi(kontrakt, baza):
    """Model turni o'zi o'ylab topmasin — ro'yxatdan tanlasin."""
    from app.agentlar.loyihachi import Loyihachi as L

    matn = L._normalar_matni(object.__new__(L))
    assert "ofis" in matn and "ombor" in matn
    assert "faqat shu ro'yxatdan tanla" in matn.lower()


def test_kontraktda_chegaralar():
    matn = kontraktlarni_yukla()["hvac-calc"].matn()
    assert "RAQAMNI O'ZI HISOBLAMAYDI" in matn
    assert "NORMATIV HUJJATGA HAVOLA QILMAYDI" in matn
    assert "LOYIHA HUJJATINI RASMIYLASHTIRMAYDI" in matn


# --- eslatmalar: ichki qoida foydalanuvchiga chiqmaydi -----------------------


@pytest.mark.asyncio
async def test_tizim_haqidagi_eslatma_filtrlanadi(kontrakt, baza):
    """Model ba'zan ichki qoidani eslatma qilib yozadi.

    Jonli sinovda shunday chiqqan edi: "Havo sarfi va kanal diametri
    tizim tomonidan hisoblanadi — bu javobda ular ko'rsatilmagan."
    Mijoz uchun bu ma'nosiz: raqamlar aynan javobda turibdi.
    """
    llm = rustam_javobi(eslatmalar=[
        "Havo sarfi va kanal diametri tizim tomonidan hisoblanadi — "
        "bu javobda ular ko'rsatilmagan.",
        "Omborda zararli modda bo'lsa, alohida hisob kerak.",
    ])

    k = await rustam_yasa(kontrakt, baza, llm).ishla("ombor")

    eslatmalar = k.natija["eslatmalar"]
    assert not any("tizim tomonidan" in e for e in eslatmalar)
    # Obyekt haqidagi foydali eslatma QOLADI
    assert any("zararli modda" in e for e in eslatmalar)


def test_promptda_eslatma_qoidasi_bor():
    from app.agentlar.loyihachi import TIZIM_PROMPT

    tekis = " ".join(TIZIM_PROMPT.split())
    assert "TIZIMNING O'ZI haqida yozmaysan" in tekis

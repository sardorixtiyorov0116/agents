"""Montaj maslahatchisi Anvar.

NEGA CHEGARALAR QATTIQ: noto'g'ri hisob uskunani sust ishlatadi,
noto'g'ri MONTAJ maslahati esa tushib ketgan uskuna yoki yopiq
yong'in yo'liga aylanishi mumkin. Shuning uchun xavfli mavzular
MODELGA UMUMAN YETIB BORMAYDI — kodda ushlanadi.
"""

from __future__ import annotations

import json

import pytest

from app.agentlar.montaj_maslahatchi import (
    MontajMaslahatchi,
    bandlarni_olib_tashla,
    xavfli_mavzu,
)
from app.konvert import Holat
from app.kontraktlar import reyestr

from .soxta import SoxtaLlm, javob, matn_bloki


# --- xavfli mavzular ----------------------------------------------------------


@pytest.mark.parametrize("savol,kutilgan", [
    ("Tom bu ventilyatorni ko'tara oladimi?", "konstruksiya"),
    ("Ko'taruvchi konstruksiya yetarlimi?", "konstruksiya"),
    ("Несущая способность перекрытия?", "konstruksiya"),
    ("Dud chiqarish tizimini qanday qilamiz?", "yongin"),
    ("Yong'in klapanini qayerga qo'yamiz?", "yongin"),
    ("Противопожарный клапан", "yongin"),
    ("Kabel kesimi qancha bo'lsin?", "elektr"),
    ("Сечение кабеля для вентилятора", "elektr"),
])
def test_xavfli_mavzu_aniqlanadi(savol, kutilgan):
    assert xavfli_mavzu(savol) == kutilgan


@pytest.mark.parametrize("savol", [
    "Ventilyatorni qayerga o'rnatamiz?",
    "Kanal qanday tortiladi?",
    "Filtr tez to'lyapti, sababi nima?",
    "Ombor uchun montaj tartibi",
])
def test_oddiy_savol_toxtatilmaydi(savol):
    assert xavfli_mavzu(savol) is None


@pytest.mark.asyncio
async def test_xavfli_savolga_model_chaqirilmaydi():
    """Model umuman ishlamasin — javob kodda tayyor."""
    class Yiqiladigan:
        async def sorov(self, *a, **kw):
            raise AssertionError("xavfli savolda model chaqirilmasligi kerak")

    agent = MontajMaslahatchi(
        kontrakt=reyestr()["montaj-guide"], llm=Yiqiladigan(), baza=None,
    )
    konvert = await agent.ishla("Tom shu ventilyatorni ko'tara oladimi?")

    assert konvert.holat is Holat.TUGADI
    assert "KONSTRUKTOR" in konvert.natija["chegaradan_tashqari"]
    assert konvert.natija["qadamlar"] == []


# --- normativ band raqami -----------------------------------------------------


@pytest.mark.parametrize("xom", [
    "ShNQ 2.04.05 bo'yicha qilinadi",
    "ШНК 2.04.05-97 ning 4.7-bandi talab qiladi",
    "СНиП 41-01-2003 bo'yicha",
    "GOST 12.4.021 talabi",
])
def test_band_raqami_olib_tashlanadi(xom):
    """Model bandni tekshira olmaydi — yozsa yolg'on ishonch beradi."""
    natija = bandlarni_olib_tashla(xom)

    for taqiq in ("2.04.05", "41-01", "12.4.021", "4.7-band"):
        assert taqiq not in natija
    assert "amaldagi normativ hujjat" in natija


def test_oddiy_matn_ozgarmaydi():
    matn = "Moslashuvchan ulagich qo'yilishi shart, aks holda bino gudullaydi."

    assert bandlarni_olib_tashla(matn) == matn


# --- javob tuzilishi ----------------------------------------------------------


def anvar_javobi(**ustama) -> str:
    malumot = {
        "vaziyat": "800 m² ombor uchun ventilyator montaji",
        "qadamlar": [
            {"nima": "Ventilyatorni texnik xonaga joylashtiring",
             "nega": "shovqin ish joyidan uzoqda qoladi"},
            {"nima": "Moslashuvchan ulagich qo'ying",
             "nega": "tebranish kanalga o'tmasin"},
        ],
        "tekshiruv": ["Aylanish yo'nalishi", "Kanal ichi toza"],
        "sabablar": [],
        "joyida_aniqlanadi": ["Mahkamlash nuqtasi"],
        "sorash_kerak": [],
        "bazada_yoq": [],
    }
    malumot.update(ustama)
    return javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])


def agent_yasa(javoblar, topilmalar=None):
    agent = MontajMaslahatchi(
        kontrakt=reyestr()["montaj-guide"], llm=SoxtaLlm(javoblar), baza=None,
    )
    agent.bilimni_qidir = lambda *a, **kw: topilmalar or []
    return agent


@pytest.mark.asyncio
async def test_montaj_maslahati_beriladi():
    konvert = await agent_yasa([anvar_javobi()]).ishla(
        "800 m² ombor uchun ventilyatorni qayerga o'rnatamiz?"
    )

    assert konvert.holat is Holat.TUGADI
    assert len(konvert.natija["qadamlar"]) == 2
    assert "Moslashuvchan" in konvert.natija["qadamlar"][1]["nima"]
    assert konvert.natija["joyida_aniqlanadi"]


@pytest.mark.asyncio
async def test_javobdagi_band_raqami_ham_tozalanadi():
    """Model qoidani buzib band yozsa — kod uni olib tashlaydi."""
    buzuq = anvar_javobi(qadamlar=[
        {"nima": "ShNQ 2.04.05 ning 4.7-bandi bo'yicha o'rnating",
         "nega": "СНиП 41-01-2003 talabi"},
    ])

    konvert = await agent_yasa([buzuq]).ishla("Ventilyatorni qanday o'rnatamiz?")

    matn = json.dumps(konvert.natija, ensure_ascii=False)
    assert "2.04.05" not in matn
    assert "41-01" not in matn


@pytest.mark.asyncio
async def test_bazada_yoq_bolsa_ishonch_pasayadi():
    """Kompaniya hujjatiga emas, umumiy amaliyotga tayangan javob."""
    from app.konvert import Ishonch

    konvert = await agent_yasa([anvar_javobi()]).ishla("Noma'lum uskuna montaji")

    assert konvert.ishonch is Ishonch.ORTA
    assert "bazada hujjat topilmadi" in konvert.izoh


@pytest.mark.asyncio
async def test_malumot_yetishmasa_soraladi():
    bosh = anvar_javobi(
        qadamlar=[], sabablar=[],
        sorash_kerak=["Xona balandligi qancha?", "Osma shift bormi?"],
    )

    konvert = await agent_yasa([bosh]).ishla("Montaj qilib bering")

    assert konvert.holat is Holat.ANIQLIK_KERAK
    assert len(konvert.natija["savollar"]) == 2


@pytest.mark.asyncio
async def test_bosh_savol_soraladi():
    konvert = await agent_yasa([]).ishla("   ")

    assert konvert.holat is Holat.ANIQLIK_KERAK


@pytest.mark.asyncio
async def test_nosozlik_sabablari_tartib_bilan():
    """Muammo so'ralganda — tekshirish osonligi bo'yicha tartib."""
    nosozlik = anvar_javobi(qadamlar=[], sabablar=[
        {"sabab": "Dvigatel teskari aylanyapti",
         "qanday_tekshirish": "g'ildirak yo'nalishini ko'ring — 1 daqiqa"},
        {"sabab": "Kanalda chiqindi qolgan",
         "qanday_tekshirish": "lyukdan qarang"},
    ])

    konvert = await agent_yasa([nosozlik]).ishla(
        "Ventilyator ishlayapti lekin havo yo'q"
    )

    sabablar = konvert.natija["sabablar"]
    assert len(sabablar) == 2
    assert "teskari" in sabablar[0]["sabab"]


# --- kontrakt -----------------------------------------------------------------


def test_kontrakt_chegaralari_yozilgan():
    kontrakt = reyestr()["montaj-guide"]
    matn = " ".join(kontrakt.chegaralar).lower()

    for kerak in ("konstruksiya", "yong'in", "normativ", "elektr"):
        assert kerak in matn, f"chegaralarda yo'q: {kerak}"


def test_montaj_bilim_bolimi_ulangan():
    from bilim.qidiruv import AGENT_PAPKALARI

    assert "montaj" in AGENT_PAPKALARI["montaj-guide"]
    # Rustamga ham ochiq: hisobdan keyin "qayerga qo'yamiz" savoli keladi.
    assert "montaj" in AGENT_PAPKALARI["hvac-calc"]


# --- mijozlar botiga ulanish --------------------------------------------------


def test_anvar_mijozga_ochiq():
    """Mijoz "qayerga o'rnataman" deb ko'p so'raydi — javob berilsin."""
    from bot.mijoz_ruxsat import OCHIQ_AGENTLAR, ochiq_kontraktlar

    assert "montaj-guide" in OCHIQ_AGENTLAR
    assert "montaj-guide" in ochiq_kontraktlar()


def test_mijozga_yopiq_agentlar_yopiq_qoladi():
    """Anvar qo'shilgani boshqasini ochib yubormasin."""
    from bot.mijoz_ruxsat import OCHIQ_AGENTLAR

    for yopiq in ("data-query", "catalog-admin", "hr-assist",
                  "proposal-builder", "kp-tracker", "legal-review"):
        assert yopiq not in OCHIQ_AGENTLAR


def test_mijoz_rejasida_anvar_otadi():
    from app.router import Reja, RejaQadam
    from bot.mijoz_ruxsat import rejani_tekshir

    reja = Reja(qadamlar=[RejaQadam(agent="montaj-guide", vazifa="montaj savoli")])

    assert rejani_tekshir(reja).ruxsat is True


def test_mijoz_rejasida_yopiq_agent_rad_etiladi():
    from app.router import Reja, RejaQadam
    from bot.mijoz_ruxsat import rejani_tekshir

    reja = Reja(qadamlar=[
        RejaQadam(agent="montaj-guide", vazifa="montaj"),
        RejaQadam(agent="proposal-builder", vazifa="KP"),
    ])

    qaror = rejani_tekshir(reja)
    assert qaror.ruxsat is False
    assert "proposal-builder" in qaror.sabab


@pytest.mark.asyncio
async def test_mijozga_ham_xavfli_mavzu_yopiq():
    """Mijoz so'rasa ham konstruksiya savoliga javob berilmaydi."""
    class Yiqiladigan:
        async def javob(self, *a, **kw):
            raise AssertionError("model chaqirilmasligi kerak")

    agent = MontajMaslahatchi(
        kontrakt=reyestr()["montaj-guide"], llm=Yiqiladigan(), baza=None,
    )
    konvert = await agent.ishla("Tomim shu ventilyatorni ko'tara oladimi?")

    assert "KONSTRUKTOR" in konvert.natija["chegaradan_tashqari"]

"""Savdo strategi Bekzod — raqam to'qimaslik, narx belgilamaslik, KP tasdig'i."""

from __future__ import annotations

import json

import pytest

from app.agentlar.savdo_strategi import SavdoStrategi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch
from presenter.agentlar import agent_matni

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["sales-strategy"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "bekzod.db")
    await b.tayyorla()
    return b


def bekzod_javobi(**ustama):
    malumot = {
        "vazifa_turi": "savdo_rejasi",
        "mahsulot": "Jetfun ventilyatori",
        "davr": "2026 4-chorak",
        "maqsadlar": [{"nomi": "Yangi dilerlar", "olchov": "5 ta", "izoh": ""}],
        "bosqichlar": ["Diler bazasini kengaytirish", "Tender hujjatlarini tayyorlash"],
        "kanallar": [
            {"nomi": "diler", "ulush": "50%", "yondashuv": "hududiy dilerlar", "izoh": ""},
            {"nomi": "tender", "ulush": "30%", "yondashuv": "davlat obyektlari", "izoh": ""},
        ],
        "segmentlar": [{"nomi": "Qurilish tashkilotlari", "yondashuv": "to'g'ridan-to'g'ri"}],
        "kpi": [{"nomi": "Yangi diler soni", "olchov": "chorakda 5 ta"}],
        "xavflar": ["Raqiblar narx bilan bosim o'tkazishi mumkin"],
        "narx_taklifi": "",
        "kp_qoralamasi": "",
        "malumot_yoq": [],
        "kimga_havola": [],
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


def bekzod_yasa(kontrakt, baza, llm, bilim=True, katalog=True):
    return SavdoStrategi(
        kontrakt=kontrakt,
        llm=llm,
        baza=baza,
        api=soxta_api(qidir_keng=[{"id": 1, "name_uz": "Jetfun", "category": {}, "quantity": 5}])
        if katalog
        else soxta_api(),
        qidiruv_manbasi=soxta_bilim(("Savdo rejasi 2025", "O'tgan yil rejasi …"))
        if bilim
        else None,
    )


# --- normal holat ------------------------------------------------------------


@pytest.mark.asyncio
async def test_savdo_rejasi_tayyorlanadi(kontrakt, baza):
    llm = bekzod_javobi()
    k = await bekzod_yasa(kontrakt, baza, llm).ishla("Jetfun uchun savdo rejasi")

    assert k.kim == "sales-strategy"
    assert k.holat is Holat.TUGADI
    # Ichki reja qoralamasi — tasdiqsiz mumkin (kontrakt)
    assert k.tasdiq_kerak is False
    assert len(k.natija["kanallar"]) == 2


@pytest.mark.asyncio
async def test_bilim_bazasi_va_katalog_promptga_tushadi(kontrakt, baza):
    llm = bekzod_javobi()
    await bekzod_yasa(kontrakt, baza, llm).ishla("Jetfun uchun savdo rejasi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "BILIM BAZASIDAN TOPILDI" in xabar
    assert "ICHKI KATALOG" in xabar
    # Katalogda narx yo'qligi aytilgan
    assert "narx raqamini yozma" in xabar


# --- chegaralar --------------------------------------------------------------


@pytest.mark.asyncio
async def test_kp_soralganda_tasdiq_kerak(kontrakt, baza):
    """KP mijozga ketadi — tasdiqsiz chiqmaydi."""
    llm = bekzod_javobi(
        vazifa_turi="kp", kp_qoralamasi="Hurmatli hamkor, sizga quyidagini taklif qilamiz…"
    )
    k = await bekzod_yasa(kontrakt, baza, llm).ishla("Jetfun uchun KP tayyorla")

    assert k.tasdiq_kerak is True
    assert "inson tasdig'i kerak" in k.izoh


@pytest.mark.asyncio
async def test_narx_taklifida_tasdiq_kerak(kontrakt, baza):
    llm = bekzod_javobi(narx_taklifi="Diler narxi ro'yxat narxidan 15% past bo'lishi mumkin")
    k = await bekzod_yasa(kontrakt, baza, llm).ishla("Narx siyosati taklifi")

    assert k.tasdiq_kerak is True
    assert "qaror rahbariyatniki" in k.izoh


@pytest.mark.asyncio
async def test_malumot_yoq_bolsa_taxmin_qilinmaydi(kontrakt, baza):
    llm = bekzod_javobi(
        maqsadlar=[],
        malumot_yoq=["o'tgan yilgi savdo hajmi", "joriy diler soni"],
        kimga_havola=["Bozor ma'lumoti uchun — Raqobat tahlilchisi Karim"],
    )
    k = await bekzod_yasa(kontrakt, baza, llm, bilim=False).ishla("Savdo rejasi")

    assert k.ishonch is Ishonch.PAST
    assert "taxmin qilinmadi" in k.izoh
    assert "havola" in k.izoh


@pytest.mark.asyncio
async def test_promptda_chegaralar_bor():
    from app.agentlar.savdo_strategi import TIZIM_PROMPT

    assert "RAQAMNI O'YLAB TOPMA" in TIZIM_PROMPT
    assert "NARX BELGILAMAYSAN" in TIZIM_PROMPT
    assert "YUBORMAYSAN" in TIZIM_PROMPT
    # Malika bilan chegara promptda ham aniq
    assert "Malikaning" in TIZIM_PROMPT


@pytest.mark.asyncio
async def test_katalog_yoq_bolsa_ochiq_aytadi(kontrakt, baza):
    llm = bekzod_javobi()
    await bekzod_yasa(kontrakt, baza, llm, katalog=False).ishla("Noma'lum mahsulot rejasi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "mavjud emas" in xabar or "topilmadi" in xabar


# --- ko'rinish ---------------------------------------------------------------


def test_savdo_rejasi_odamcha_korinadi():
    natija = {
        "vazifa_turi": "savdo_rejasi",
        "mahsulot": "Jetfun",
        "davr": "2026 4-chorak",
        "maqsadlar": [{"nomi": "Yangi dilerlar", "olchov": "5 ta", "izoh": ""}],
        "bosqichlar": ["Diler bazasi"],
        "kanallar": [{"nomi": "diler", "ulush": "50%", "yondashuv": "hududiy", "izoh": ""}],
        "segmentlar": [],
        "kpi": [{"nomi": "Diler soni", "olchov": "5 ta"}],
        "xavflar": ["Narx bosimi"],
        "narx_taklifi": "",
        "kp_qoralamasi": "",
        "malumot_yoq": ["o'tgan yil hajmi"],
        "kimga_havola": [],
    }
    matn = agent_matni("sales-strategy", natija)

    assert matn.startswith("Savdo rejasi — Jetfun (2026 4-chorak)")
    assert "Yangi dilerlar — 5 ta" in matn
    assert "diler (50%)" in matn
    assert "Ma'lumot yetishmadi (taxmin qilinmadi): o'tgan yil hajmi" in matn
    # JSON belgilari yo'q
    for belgi in ("{", "}", '"nomi"'):
        assert belgi not in matn


def test_bekzod_past_effortda_ishlaydi():
    """Jonli o'lchov: medium 71s / low 58s, natija tuzilishi bir xil."""
    from app.agentlar.savdo_strategi import SavdoStrategi

    assert SavdoStrategi.EFFORT == "low"

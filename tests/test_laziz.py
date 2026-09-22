"""Yurist Laziz — xavf darajalari, taxmin qilmaslik, doimiy tasdiq."""

from __future__ import annotations

import json

import pytest

from app.agentlar.yurist import Yurist
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_bilim


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["legal-review"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "laziz.db")
    await b.tayyorla()
    return b


def laziz_javobi(**ustama):
    malumot = {
        "hujjat_turi": "yetkazib berish shartnomasi",
        "yurisdiksiya": "O'zbekiston",
        "qaydlar": [
            {
                "band": "4.2",
                "xavf": "yuqori",
                "izoh": "Jarima chegarasi ko'rsatilmagan — cheksiz javobgarlik xavfi",
                "tuzatish_taklifi": "Jarimaning yuqori chegarasini shartnoma summasi bilan cheklang",
                "manba_nomi": "FK 333-modda",
                "havola": "https://lex.uz/docs/111",
            },
            {
                "band": "7.1",
                "xavf": "past",
                "izoh": "Tahririy noaniqlik",
                "tuzatish_taklifi": "So'zlashuvni aniqlashtiring",
                "manba_nomi": None,
                "havola": None,
            },
        ],
        "xulosa": "Shartnomada bitta jiddiy band bor, tuzatish tavsiya etiladi.",
        "aniqlik_kerak": [],
        "yetishmagan_qismlar": [],
    }
    malumot.update(ustama)
    return malumot


def soxta(malumot):
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


@pytest.mark.asyncio
async def test_xavf_darajalari_ajratiladi(kontrakt, baza):
    llm = soxta(laziz_javobi())
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await laziz.ishla("Bu yetkazib berish shartnomasini tekshiring")

    assert k.kim == "legal-review"
    assert k.holat is Holat.TUGADI
    assert len(k.natija["qaydlar"]) == 2
    assert k.natija["qaydlar"][0]["xavf"] == "yuqori"
    # Xavf sanog'i izohda ko'rinadi
    assert "yuqori: 1" in k.izoh and "past: 1" in k.izoh
    assert "DIQQAT: 1 ta yuqori xavfli band" in k.izoh


@pytest.mark.asyncio
async def test_har_doim_tasdiq_kerak(kontrakt, baza):
    """Kontrakt: HAR DOIM — hech qanday holatda tasdiqsiz chiqmaydi."""
    llm = soxta(laziz_javobi(qaydlar=[], xulosa="Muammo topilmadi"))
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await laziz.ishla("Shartnomani ko'ring")

    assert k.tasdiq_kerak is True
    assert "HUQUQIY KAFOLAT EMAS" in k.izoh


@pytest.mark.asyncio
async def test_noaniq_bandda_taxmin_qilmaydi(kontrakt, baza):
    llm = soxta(
        laziz_javobi(
            aniqlik_kerak=["5.3-band: 'oqilona muddat' nima ekani aniqlanmagan"],
        )
    )
    # Bilim bazasida manba bor — shunda ishonch faqat noaniqlik uchun pasayadi.
    laziz = Yurist(
        kontrakt=kontrakt,
        llm=llm,
        baza=baza,
        qidiruv_manbasi=soxta_bilim(("Fuqarolik kodeksi, 242-modda", "Shartnoma muddati…")),
    )
    k = await laziz.ishla("Shartnomani tekshiring")

    assert k.ishonch is Ishonch.ORTA
    assert "noaniq band — taxmin qilinmadi" in k.izoh
    assert k.natija["aniqlik_kerak"]


@pytest.mark.asyncio
async def test_hujjat_toliq_bolmasa_soraydi(kontrakt, baza):
    llm = soxta(
        laziz_javobi(
            qaydlar=[],
            yetishmagan_qismlar=["Ilova 1 (narx jadvali)", "Tomonlar rekvizitlari"],
        )
    )
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await laziz.ishla("Shartnoma qismini tekshiring")

    assert k.ishonch is Ishonch.PAST
    assert "hujjat to'liq emas" in k.izoh
    assert "Ilova 1" in k.izoh


@pytest.mark.asyncio
async def test_chegaralar_promptda(kontrakt):
    from app.agentlar.yurist import TIZIM_PROMPT

    assert "IMZOLAMAYSAN" in TIZIM_PROMPT
    assert "YUBORMAYSAN" in TIZIM_PROMPT
    assert "KAFOLAT" in TIZIM_PROMPT
    assert "TAXMIN QILMAYSAN" in TIZIM_PROMPT


@pytest.mark.asyncio
async def test_manbali_qayd_manbaga_aylanadi(kontrakt, baza):
    llm = soxta(laziz_javobi())
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await laziz.ishla("Shartnomani tekshiring")

    assert "https://lex.uz/docs/111" in {m.havola for m in k.manba}


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("shartnoma yaxshi ko'rinadi")])])
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await laziz.ishla("Shartnoma")
    assert k.holat is Holat.XATO


def test_laziz_past_effortda_ishlaydi():
    """Xavfli bandni TOPISH — naqsh tanish ishi, uzoq o'ylash emas.

    Jonli o'lchov: medium 50s / low 28s, topilgan qayd ikkalasida bir xil.
    """
    from app.agentlar.yurist import Yurist

    assert Yurist.EFFORT == "low"

"""Narx analitigi Zara — konvert, tarix, keskin o'zgarish, xato holatlari."""

from __future__ import annotations

import pytest

from app.agentlar.narx_kuzatuvchi import NarxKuzatuvchi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki, qidiruv_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["price-monitor"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "test.db")
    await b.tayyorla()
    return b


def zara_javobi(**ustama):
    malumot = {
        "bozor": "Toshkent, O'zbekiston",
        "valyuta": "UZS",
        "yozuvlar": [
            {
                "mahsulot": "iPhone 15 128GB",
                "narx": 12500000.0,
                "valyuta": "UZS",
                "sana": "2026-07-20",
                "manba_nomi": "Olcha.uz",
                "havola": "https://olcha.uz/product/iphone-15",
                "ishonch": "yuqori",
                "manba_ishonchsiz": False,
                "izoh": "",
            }
        ],
        "topilmaganlar": [],
        "ziddiyatlar": [],
        "diqqat": [],
    }
    malumot.update(ustama)
    return malumot


@pytest.mark.asyncio
async def test_konvert_togri_qaytadi(kontrakt, baza):
    llm = SoxtaLlm(
        [
            javob(
                [
                    qidiruv_bloki([{"title": "Olcha.uz", "url": "https://olcha.uz/x"}]),
                    matn_bloki(__import__("json").dumps(zara_javobi(), ensure_ascii=False)),
                ]
            )
        ]
    )
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await zara.ishla("iPhone 15 narxini Toshkentda top")

    assert k.kim == "price-monitor"
    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.YUQORI
    assert k.tasdiq_kerak is False
    assert k.natija["yozuvlar"][0]["narx"] == 12500000.0
    # Manba majburiy: mahsulot havolasi + qidiruv natijasi
    havolalar = {m.havola for m in k.manba}
    assert "https://olcha.uz/product/iphone-15" in havolalar

    # web_search vositasi ulangan va structured output so'ralgan
    soro = llm.chaqiruvlar[0]
    assert soro["tools"][0]["type"] == "web_search_20260209"
    assert soro["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_narx_tarixi_yoziladi_va_keskin_ozgarish_belgilanadi(kontrakt, baza):
    import json

    # 1-so'rov: 10 mln
    birinchi = zara_javobi(
        yozuvlar=[
            {
                "mahsulot": "Televizor X",
                "narx": 10_000_000.0,
                "valyuta": "UZS",
                "sana": "2026-07-01",
                "manba_nomi": "Texnomart",
                "havola": "https://texnomart.uz/x",
                "ishonch": "yuqori",
                "manba_ishonchsiz": False,
                "izoh": "",
            }
        ]
    )
    # 2-so'rov: 13 mln (+30% -> keskin)
    ikkinchi = zara_javobi(
        yozuvlar=[
            {
                "mahsulot": "Televizor X",
                "narx": 13_000_000.0,
                "valyuta": "UZS",
                "sana": "2026-07-27",
                "manba_nomi": "Texnomart",
                "havola": "https://texnomart.uz/x",
                "ishonch": "yuqori",
                "manba_ishonchsiz": False,
                "izoh": "",
            }
        ]
    )
    llm = SoxtaLlm(
        [
            javob([matn_bloki(json.dumps(birinchi, ensure_ascii=False))]),
            javob([matn_bloki(json.dumps(ikkinchi, ensure_ascii=False))]),
        ]
    )
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)

    k1 = await zara.ishla("Televizor X narxi")
    assert k1.natija["diqqat"] == []

    k2 = await zara.ishla("Televizor X narxi")
    assert k2.natija["diqqat"], "keskin o'zgarish belgilanishi kerak"
    assert "+30%" in k2.natija["diqqat"][0]
    assert "keskin o'zgarish" in k2.izoh

    oxirgi = await baza.oxirgi_narx("Televizor X", "UZS")
    assert oxirgi["narx"] == 13_000_000.0


@pytest.mark.asyncio
async def test_topilmasa_toqib_chiqarmaydi(kontrakt, baza):
    import json

    malumot = zara_javobi(yozuvlar=[], topilmaganlar=["Noma'lum mahsulot Z"])
    llm = SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await zara.ishla("Noma'lum mahsulot Z narxi")
    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.PAST
    assert k.natija["topilmaganlar"] == ["Noma'lum mahsulot Z"]
    assert k.manba, "manba har doim ko'rsatiladi"
    assert "topilmadi" in k.izoh


@pytest.mark.asyncio
async def test_ishonchsiz_manba_ishonchni_pasaytiradi(kontrakt, baza):
    import json

    malumot = zara_javobi(
        yozuvlar=[
            {
                "mahsulot": "Noutbuk Y",
                "narx": 7_000_000.0,
                "valyuta": "UZS",
                "sana": None,
                "manba_nomi": "e'lonlar forumi",
                "havola": "https://forum.example/e1",
                "ishonch": "yuqori",
                "manba_ishonchsiz": True,
                "izoh": "sanasi yo'q e'lon",
            }
        ]
    )
    llm = SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await zara.ishla("Noutbuk Y narxi")
    assert k.ishonch is Ishonch.ORTA
    assert "ishonchsiz" in k.izoh


@pytest.mark.asyncio
async def test_pause_turn_davom_ettiriladi(kontrakt, baza):
    import json

    llm = SoxtaLlm(
        [
            javob([matn_bloki("")], stop_reason="pause_turn"),
            javob([matn_bloki(json.dumps(zara_javobi(), ensure_ascii=False))]),
        ]
    )
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await zara.ishla("iPhone 15 narxi")

    assert k.holat is Holat.TUGADI
    assert len(llm.chaqiruvlar) == 2
    # Ikkinchi chaqiruvda assistant javobi tarixga qo'shilgan
    assert llm.chaqiruvlar[1]["messages"][-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_structured_output_rad_etilsa_zaxira_yol(kontrakt, baza):
    """API `format`ni rad etsa, matn rejimida JSON so'raladi."""
    import json

    import anthropic
    import httpx

    class RadEtuvchiLlm:
        def __init__(self):
            self.chaqiruvlar = []

        async def javob(self, **soro):
            self.chaqiruvlar.append(soro)
            if "format" in soro.get("output_config", {}):
                raise anthropic.BadRequestError(
                    message="output_config.format is not supported here",
                    response=httpx.Response(400, request=httpx.Request("POST", "https://x")),
                    body=None,
                )
            return javob([matn_bloki(json.dumps(zara_javobi(), ensure_ascii=False))])

    llm = RadEtuvchiLlm()
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await zara.ishla("iPhone 15 narxi")

    assert k.holat is Holat.TUGADI
    assert len(llm.chaqiruvlar) == 2
    assert "format" not in llm.chaqiruvlar[1]["output_config"]
    assert "JSON" in llm.chaqiruvlar[1]["messages"][0]["content"]
    assert "matn rejimida" in k.izoh


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("narx taxminan 12 mln bo'lsa kerak")])])
    zara = NarxKuzatuvchi(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await zara.ishla("iPhone 15 narxi")
    assert k.holat is Holat.XATO
    assert k.ishonch is Ishonch.PAST


def test_zara_chuqur_effortda_qoladi():
    """Zara — YAGONA agent, past effort SIFATNI pasaytiradi.

    Jonli o'lchov: medium 99s da 3 ta narx topdi, low 52s da atigi 1 ta.
    Narx qidirish chindan qidiruv ishi — tezlik uchun aniqlikni bermaymiz.
    """
    from app.agentlar.narx_kuzatuvchi import NarxKuzatuvchi

    assert NarxKuzatuvchi.EFFORT is None

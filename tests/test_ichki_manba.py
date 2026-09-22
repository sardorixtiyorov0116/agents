"""Ichki API birlamchi manba ekanini tekshiradi (Sardor, Zara, Doston).

O'zgarmas qoidalar:
  - ichki API birlamchi, tashqi veb ikkilamchi;
  - manba turi har doim ko'rsatiladi (`ichki_api` / `tashqi_veb`);
  - narxlar tizimda yo'q — tashqi narx o'z narximiz sifatida ko'rsatilmaydi;
  - API ishlamasa — "manba mavjud emas" deyiladi, to'qib chiqarilmaydi.
"""

from __future__ import annotations

import json

import pytest

from app.agentlar.mahsulot_mutaxassisi import MahsulotMutaxassisi
from app.agentlar.malumot_muhandisi import MalumotMuhandisi
from app.agentlar.narx_kuzatuvchi import NarxKuzatuvchi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api

MAHSULOT = {
    "id": 26,
    "name_uz": "VK-250 kanal ventilyatori",
    "description_short_uz": "Doira kanallari uchun ventilyator.",
    "price": 0,
    "quantity": 62,
    "producer": "JIHOZVENT",
    "category": {"name_uz": "Yumaloq kanallar uchun"},
    "models": [{"name": "VK-250P"}],
    "characters": [{"title": "VK-250P", "content": "Quvvat 210 Vt"}],
}


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "ichki.db")
    await b.tayyorla()
    return b


def sardor_javobi(xususiyatlar):
    return javob(
        [
            matn_bloki(
                json.dumps(
                    {
                        "mahsulot": "VK-250",
                        "kategoriya": "Kanal ventilyatori",
                        "xususiyatlar": xususiyatlar,
                        "topilmagan_maydonlar": [],
                        "ziddiyatlar": [],
                    },
                    ensure_ascii=False,
                )
            )
        ]
    )


# --- Sardor ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sardor_avval_ichki_katalogdan_qidiradi(kontraktlar, baza):
    api = soxta_api(qidir_keng=[MAHSULOT], mahsulot_xususiyatlari=[
        {"nomi": "VK-250P", "qiymat": "Model | Quvvat\nVK-250P | 210 Vt"}
    ])
    llm = SoxtaLlm(
        [
            sardor_javobi(
                [
                    {
                        "nomi": "Quvvat",
                        "qiymat": "210 Vt",
                        "manba_turi": "ichki_api",
                        "manba_nomi": "Climavent ichki katalogi",
                        "havola": None,
                        "ishonch": "yuqori",
                    }
                ]
            )
        ]
    )
    sardor = MahsulotMutaxassisi(
        kontrakt=kontraktlar["product-spec"], llm=llm, baza=baza, api=api
    )
    k = await sardor.ishla("VK-250 spesifikatsiyasi")

    # Ichki katalog topshiriqqa qo'shilgan va birlamchi deb belgilangan
    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ICHKI KATALOGDAN TOPILDI" in xabar
    assert "VK-250 kanal ventilyatori" in xabar
    assert "210 Vt" in xabar

    assert k.holat is Holat.TUGADI
    # Ichki manbadan olingan ma'lumot ishonchi — yuqori
    assert k.ishonch is Ishonch.YUQORI
    assert k.natija["xususiyatlar"][0]["manba_turi"] == "ichki_api"
    assert [m.tur for m in k.manba] == ["ichki_api"]
    assert "ichki katalog: 1" in k.izoh


@pytest.mark.asyncio
async def test_sardor_ichki_topilmasa_tashqiga_otadi(kontraktlar, baza):
    api = soxta_api(qidir_keng=[])
    llm = SoxtaLlm(
        [
            sardor_javobi(
                [
                    {
                        "nomi": "Quvvat",
                        "qiymat": "180 Vt",
                        "manba_turi": "tashqi_veb",
                        "manba_nomi": "example.com",
                        "havola": "https://example.com/spec",
                        "ishonch": "orta",
                    }
                ]
            )
        ]
    )
    sardor = MahsulotMutaxassisi(
        kontrakt=kontraktlar["product-spec"], llm=llm, baza=baza, api=api
    )
    k = await sardor.ishla("Noma'lum model spesifikatsiyasi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ichki katalogida" in xabar and "TOPILMADI" in xabar
    assert [m.tur for m in k.manba] == ["tashqi_veb"]
    assert "tashqi veb: 1" in k.izoh


@pytest.mark.asyncio
async def test_sardor_api_yiqilsa_ochiq_aytadi(kontraktlar, baza):
    """API ishlamasa — to'qib chiqarmaydi, ochiq aytadi."""
    api = soxta_api()  # hech narsa sozlanmagan -> ApiXatosi
    llm = SoxtaLlm([sardor_javobi([])])
    sardor = MahsulotMutaxassisi(
        kontrakt=kontraktlar["product-spec"], llm=llm, baza=baza, api=api
    )
    k = await sardor.ishla("VK-250 spesifikatsiyasi")

    assert "ICHKI KATALOG: mavjud emas" in llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ichki katalogga ulanib bo'lmadi" in k.izoh


# --- Zara --------------------------------------------------------------------


def zara_javobi(**ustama):
    malumot = {
        "bozor": "Toshkent",
        "valyuta": "UZS",
        "yozuvlar": [],
        "topilmaganlar": [],
        "ziddiyatlar": [],
        "diqqat": [],
        "ichki_narx_holati": "",
    }
    malumot.update(ustama)
    return javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])


@pytest.mark.asyncio
async def test_zara_ichki_narx_yoqligini_aytadi(kontraktlar, baza):
    """Narxlar tizimda yo'q — bu ochiq holat."""
    api = soxta_api(qidir_keng=[MAHSULOT])  # price = 0
    llm = SoxtaLlm(
        [
            zara_javobi(
                ichki_narx_holati="Ichki tizimda bu mahsulot narxi to'ldirilmagan"
            )
        ]
    )
    zara = NarxKuzatuvchi(kontrakt=kontraktlar["price-monitor"], llm=llm, baza=baza, api=api)
    k = await zara.ishla("VK-250 narxi qancha?")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "NARXI TO'LDIRILMAGAN" in xabar
    assert "o'z narximiz sifatida KO'RSATMA" in xabar
    assert "ichki narx" in k.izoh


@pytest.mark.asyncio
async def test_zara_tashqi_narxni_oz_narx_deb_korsatmaydi(kontraktlar, baza):
    api = soxta_api(qidir_keng=[MAHSULOT])
    llm = SoxtaLlm(
        [
            zara_javobi(
                yozuvlar=[
                    {
                        "mahsulot": "VK-250",
                        "narx": 1_500_000.0,
                        "valyuta": "UZS",
                        "sana": "2026-07-20",
                        "manba_nomi": "raqib sayti",
                        "havola": "https://raqib.uz/x",
                        "ishonch": "orta",
                        "manba_ishonchsiz": False,
                        "tashqi_bozor": True,
                        "izoh": "raqib narxi",
                    }
                ],
                ichki_narx_holati="ichki narx mavjud emas",
            )
        ]
    )
    zara = NarxKuzatuvchi(kontrakt=kontraktlar["price-monitor"], llm=llm, baza=baza, api=api)
    k = await zara.ishla("VK-250 narxi")

    assert k.natija["yozuvlar"][0]["tashqi_bozor"] is True
    assert "TASHQI bozordan" in k.izoh
    assert "kompaniyaning o'z narxi emas" in k.izoh


# --- Doston ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_doston_katalog_savoliga_sqlsiz_javob_beradi(kontraktlar, baza):
    api = soxta_api(
        katalog_xulosasi={
            "mahsulotlar_soni": 137,
            "kategoriyalar_soni": 35,
            "kategoriya_boyicha": {"Ventilyatorlar": 40, "Klapanlar": 12},
            "ombordagi_jami": 5000,
            "narxi_toldirilgan": 1,
            "narxi_bosh": 136,
        }
    )
    llm = SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "sql": "",
                                "izoh": "Katalogda 137 ta mahsulot, 35 ta kategoriya bor.",
                                "yozish_kerakmi": False,
                                "yozish_sababi": "",
                                "katalogdan_javob": True,
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
            )
        ]
    )
    doston = MalumotMuhandisi(
        kontrakt=kontraktlar["data-query"], llm=llm, baza=baza, api=api
    )
    k = await doston.ishla("Katalogda nechta mahsulot bor?")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ICHKI KATALOG (Climavent API" in xabar
    assert "mahsulotlar soni: 137" in xabar

    assert k.holat is Holat.TUGADI
    assert k.natija["manba_turi"] == "ichki_api"
    assert k.natija["sql"] is None
    assert [m.tur for m in k.manba] == ["ichki_api"]
    assert k.ishonch is Ishonch.YUQORI


@pytest.mark.asyncio
async def test_doston_sql_yoli_ozgarmagan(kontraktlar, baza):
    """Katalog qo'shilgani SQL yo'liga xalaqit bermaydi."""
    api = soxta_api(katalog_xulosasi={
        "mahsulotlar_soni": 137, "kategoriyalar_soni": 35,
        "kategoriya_boyicha": {}, "ombordagi_jami": 0,
        "narxi_toldirilgan": 1, "narxi_bosh": 136,
    })
    llm = SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "sql": "SELECT count(*) AS n FROM mijozlar",
                                "izoh": "mijozlar soni",
                                "yozish_kerakmi": False,
                                "yozish_sababi": "",
                                "katalogdan_javob": False,
                            }
                        )
                    )
                ]
            )
        ]
    )
    doston = MalumotMuhandisi(
        kontrakt=kontraktlar["data-query"], llm=llm, baza=baza, api=api
    )
    k = await doston.ishla("Nechta mijoz bor?")

    assert k.holat is Holat.TUGADI
    assert k.natija["qatorlar"] == [{"n": 5}]
    assert k.natija["sql"].startswith("SELECT")

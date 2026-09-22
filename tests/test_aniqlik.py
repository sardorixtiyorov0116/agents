"""Router aniqlashtirish holati — yetishmagan ma'lumotda savol beriladi.

Asosiy talab: profildan yoki API'dan olinadigan ma'lumot uchun SAVOL
BERILMAYDI; chindan yetishmayotgan narsa bo'lsa — agentlar chaqirilmaydi.
"""

from __future__ import annotations

import pytest

from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat
from app.orkestr import Orkestr
from app.router import Router

from .soxta import SoxtaLlm, json_javob


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "aniqlik.db")
    await b.tayyorla()
    return b


def router_javobi(**ustama):
    malumot = {
        "niyat": "test",
        "vazifa_soni": 0,
        "qadamlar": [],
        "mos_agent_yoq": False,
        "aniqlik_kerak": False,
        "savollar": [],
        "izoh": "",
    }
    malumot.update(ustama)
    return json_javob(malumot)


# --- router darajasida -------------------------------------------------------


@pytest.mark.asyncio
async def test_aniqlik_kerak_bolsa_qadamlar_tozalanadi(kontraktlar):
    """Savol berilsa, agentlar rejada qolmaydi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                aniqlik_kerak=True,
                savollar=["Qaysi hujjatni tekshiray?"],
                qadamlar=[
                    {
                        "agent": "legal-review",
                        "vazifa": "tekshir",
                        "tasdiq_kerak": True,
                        "tasdiq_sababi": "",
                    }
                ],
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Shartnomani tekshiring")

    assert reja.aniqlik_kerak is True
    assert reja.qadamlar == []
    assert reja.savollar == ["Qaysi hujjatni tekshiray?"]


@pytest.mark.asyncio
async def test_savolsiz_aniqlik_kerak_eiborga_olinmaydi(kontraktlar):
    """"Aniqlik kerak" deyilsa-yu savol berilmasa — foydasiz, reja davom etadi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                aniqlik_kerak=True,
                savollar=["", "   "],
                qadamlar=[
                    {
                        "agent": "price-monitor",
                        "vazifa": "narx",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ],
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Narx top")

    assert reja.aniqlik_kerak is False
    assert [q.agent for q in reja.qadamlar] == ["price-monitor"]


@pytest.mark.asyncio
async def test_promptda_savol_bermaslik_qoidalari_bor(kontraktlar):
    llm = SoxtaLlm([router_javobi()])
    await Router(llm, kontraktlar).reja_tuz("nimadir")

    tizim = "\n".join(b["text"] for b in llm.chaqiruvlar[0]["system"])
    assert "ANIQLASHTIRISH QOIDALARI" in tizim
    # Profil va API'dan olinadigan narsa uchun savol berilmaydi
    assert "SAVOL BERMA" in tizim
    assert "ICHKI API" in tizim


# --- orkestr darajasida ------------------------------------------------------


@pytest.mark.asyncio
async def test_aniqlik_kerakda_agentlar_chaqirilmaydi(kontraktlar, baza):
    """Eng muhim: bo'sh natija o'rniga aniq savol qaytadi."""
    # Bitta javob: agent chaqirilsa test yiqiladi.
    llm = SoxtaLlm(
        [
            router_javobi(
                niyat="hujjatni tekshirish",
                aniqlik_kerak=True,
                savollar=[
                    "Qaysi hujjatni tekshirishim kerak — matnini yuboring",
                    "Yurisdiksiya O'zbekistonmi?",
                ],
                izoh="Hujjat matni berilmagan",
            )
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Shartnomani tekshirib bering")

    assert natija.qadamlar == []
    assert natija.yakuniy.holat is Holat.ANIQLIK_KERAK
    assert natija.yakuniy.kim == "router"
    assert len(natija.yakuniy.natija["savollar"]) == 2
    assert "Hujjat matni berilmagan" in natija.yakuniy.izoh
    # Bu xato emas — logda xato deb yozilmaydi
    iz = await baza.iz(natija.iz_id)
    assert iz["xato"] is None


@pytest.mark.asyncio
async def test_aniqlik_kerak_xato_emas():
    from app.konvert import aniqlik_kerak_konvert

    k = aniqlik_kerak_konvert(["Qaysi davr uchun?"])

    assert k.holat is Holat.ANIQLIK_KERAK
    assert k.holat is not Holat.XATO
    assert k.tasdiq_kerak is False
    assert "Qaysi davr uchun?" in k.izoh


@pytest.mark.asyncio
async def test_javob_kelgach_zanjir_ishga_tushadi(kontraktlar, baza):
    """Foydalanuvchi javob bergach, oddiy so'rov sifatida davom etadi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                niyat="narx",
                vazifa_soni=1,
                qadamlar=[
                    {
                        "agent": "price-monitor",
                        "vazifa": "VK-250 narxini top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ],
            ),
            json_javob(
                {
                    "bozor": "Toshkent",
                    "valyuta": "UZS",
                    "yozuvlar": [],
                    "topilmaganlar": ["VK-250"],
                    "ziddiyatlar": [],
                    "diqqat": [],
                    "ichki_narx_holati": "ichki narx mavjud emas",
                }
            ),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "VK-250 narxi — oldingi savolga javob: VK-250 modeli"
    )

    assert [q.agent for q in natija.qadamlar] == ["price-monitor"]
    assert natija.yakuniy.holat is Holat.TUGADI


def test_olti_holat_ajratilgan():
    assert {h.value for h in Holat} == {
        "tugadi",
        "tasdiq_kutilmoqda",
        "aniqlik_kerak",
        "mos_agent_yoq",
        "ulanmagan",
        "xato",
    }

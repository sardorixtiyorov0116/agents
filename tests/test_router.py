"""Router qarorlari (soxta LLM bilan, API'ga chiqmaydi)."""

from __future__ import annotations

import pytest

from app.kontraktlar import kontraktlarni_yukla
from app.router import Router, RouterXatosi

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.mark.asyncio
async def test_bitta_vazifa_bitta_agent(kontraktlar):
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "iPhone 15 narxini topish",
                    "vazifa_soni": 1,
                    "qadamlar": [
                        {
                            "agent": "price-monitor",
                            "vazifa": "iPhone 15 narxini Toshkent bozorida top",
                            "tasdiq_kerak": False,
                            "tasdiq_sababi": "",
                        }
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "narx so'rovi -> Zara",
                }
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("iPhone 15 narxini top")

    assert len(reja.qadamlar) == 1
    assert reja.qadamlar[0].agent == "price-monitor"
    assert reja.qadamlar[0].tasdiq_kerak is False

    # Kontraktlar prompt ichida keshlanib yuborilgan bo'lishi kerak
    soro = llm.chaqiruvlar[0]
    keshlangan = [b for b in soro["system"] if b.get("cache_control")]
    assert len(keshlangan) == 1, "aynan bitta kesh nuqtasi bo'lishi kerak"
    assert keshlangan[0]["cache_control"] == {"type": "ephemeral"}

    hammasi = "\n".join(b["text"] for b in soro["system"])
    assert "AGENT KONTRAKTLARI" in hammasi
    # Kompaniya profili ham routerga beriladi
    assert "KOMPANIYA" in hammasi
    assert soro["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_yuqori_xavfli_agentga_tasdiq_majburan_qoyiladi(kontraktlar):
    # LLM tasdiqni belgilashni "unutdi" — router o'zi majburan qo'yadi.
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "shartnomani tekshirish",
                    "vazifa_soni": 1,
                    "qadamlar": [
                        {
                            "agent": "legal-review",
                            "vazifa": "shartnomani tekshir",
                            "tasdiq_kerak": False,
                            "tasdiq_sababi": "",
                        }
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "",
                }
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Bu shartnomani tekshirib bering")

    assert reja.qadamlar[0].tasdiq_kerak is True
    assert "Yurist Laziz" in reja.qadamlar[0].tasdiq_sababi


@pytest.mark.asyncio
async def test_zanjir_tartibi_saqlanadi(kontraktlar):
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "raqib tahlili + kampaniya",
                    "vazifa_soni": 2,
                    "qadamlar": [
                        {
                            "agent": "competitor-watch",
                            "vazifa": "raqiblarning aksiyalarini yig'",
                            "tasdiq_kerak": False,
                            "tasdiq_sababi": "",
                        },
                        {
                            "agent": "marketing",
                            "vazifa": "topilmalar asosida kampaniya qoralamasi",
                            "tasdiq_kerak": True,
                            "tasdiq_sababi": "nashr etiladigan kontent",
                        },
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "",
                }
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Raqiblarni ko'rib, kampaniya taklif qil")

    assert [q.agent for q in reja.qadamlar] == ["competitor-watch", "marketing"]
    assert reja.qadamlar[1].tasdiq_kerak is True


@pytest.mark.asyncio
async def test_mos_agent_yoq_ochiq_aytiladi(kontraktlar):
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "ofisga pizza buyurtma qilish",
                    "vazifa_soni": 1,
                    "qadamlar": [],
                    "mos_agent_yoq": True,
                    "izoh": "Buyurtma berish birorta agent kontraktiga kirmaydi",
                }
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Ofisga pizza buyurtma qil")

    assert reja.mos_agent_yoq is True
    assert reja.qadamlar == []


@pytest.mark.asyncio
async def test_notogri_javobda_router_xatosi(kontraktlar):
    llm = SoxtaLlm([javob([matn_bloki("bu JSON emas")])])
    with pytest.raises(RouterXatosi):
        await Router(llm, kontraktlar).reja_tuz("nimadir")


@pytest.mark.asyncio
async def test_bosh_tortishda_mos_agent_yoq(kontraktlar):
    llm = SoxtaLlm([javob([], stop_reason="refusal")])
    reja = await Router(llm, kontraktlar).reja_tuz("nimadir")
    assert reja.mos_agent_yoq is True


# --- KP zanjiridagi ortiqcha qadamlar --------------------------------------
#
# 135 ta haqiqiy izdan o'lchandi: ayni bir so'rov turlicha zanjir olgan va
# ortiqcha qadam KP ni 80 s dan 230 s ga cho'zgan. Model barqaror emas,
# shuning uchun qoida KODDA turadi.


def _kp_zanjiri(*qoshimcha: str) -> dict:
    qadamlar = [{"agent": "hvac-calc", "vazifa": "havo sarfi", "tasdiq_kerak": False},
                {"agent": "product-spec", "vazifa": "uskuna tanla", "tasdiq_kerak": False}]
    qadamlar += [{"agent": a, "vazifa": "qo'shimcha", "tasdiq_kerak": False}
                 for a in qoshimcha]
    qadamlar.append({"agent": "proposal-builder", "vazifa": "KP tuz",
                     "tasdiq_kerak": False})
    return {"niyat": "KP", "vazifa_soni": 1, "qadamlar": qadamlar,
            "mos_agent_yoq": False, "izoh": ""}


@pytest.mark.asyncio
@pytest.mark.parametrize("ortiqcha", ["price-monitor", "sales-strategy"])
async def test_kp_zanjiridan_soralmagan_qadam_olib_tashlanadi(kontraktlar, ortiqcha):
    llm = SoxtaLlm([json_javob(_kp_zanjiri(ortiqcha))])

    reja = await Router(llm, kontraktlar).reja_tuz(
        "Toshkentdagi 250 m2 restoran uchun KP tayyorla, balandligi 3.2 m"
    )

    nomlar = [q.agent for q in reja.qadamlar]
    assert ortiqcha not in nomlar, nomlar
    assert nomlar == ["hvac-calc", "product-spec", "proposal-builder"]


@pytest.mark.asyncio
async def test_bozor_narxi_SORALSA_price_monitor_qoladi(kontraktlar):
    """Foydalanuvchi atayin so'rasa — olib tashlash xato bo'lardi."""
    llm = SoxtaLlm([json_javob(_kp_zanjiri("price-monitor"))])

    reja = await Router(llm, kontraktlar).reja_tuz(
        "KP tayyorla va raqiblarda bozor narxi qancha ekanini ham ko'r"
    )

    assert "price-monitor" in [q.agent for q in reja.qadamlar]


@pytest.mark.asyncio
async def test_strategiya_SORALSA_sales_strategy_qoladi(kontraktlar):
    llm = SoxtaLlm([json_javob(_kp_zanjiri("sales-strategy"))])

    reja = await Router(llm, kontraktlar).reja_tuz(
        "KP tayyorla va savdo strategiyasini ham ayt"
    )

    assert "sales-strategy" in [q.agent for q in reja.qadamlar]


@pytest.mark.asyncio
async def test_KP_SIZ_zanjirga_tegilmaydi(kontraktlar):
    """Qoida faqat KP zanjiriga tegishli — boshqa zanjirlar o'zgarmaydi."""
    llm = SoxtaLlm([json_javob({
        "niyat": "narx", "vazifa_soni": 1,
        "qadamlar": [{"agent": "price-monitor", "vazifa": "narx", "tasdiq_kerak": False}],
        "mos_agent_yoq": False, "izoh": "",
    })])

    reja = await Router(llm, kontraktlar).reja_tuz("ВК-250П narxi qancha")

    assert [q.agent for q in reja.qadamlar] == ["price-monitor"]


def test_HAMMA_rol_yulduzcha_bilan_tez_modelga_otadi():
    """`TEZ_ROLLAR_ROYXATI=*` — rollarni bittalab sanash mo'rt.

    Yangi agent qo'shilganda uni ro'yxatga qo'shish unutiladi va u
    jimgina eski (qimmat yoki ishlamaydigan) modelda qolib ketardi.
    """
    from app.config import HAMMA_ROL, Sozlama

    s = Sozlama(tez_model="gemini-3.5-flash", tez_rollar_royxati=HAMMA_ROL)

    assert s.hamma_rol_tezmi is True


def test_royxat_aniq_bolsa_yulduzcha_YOQ():
    from app.config import Sozlama

    s = Sozlama(tez_model="gemini-3.5-flash", tez_rollar_royxati="router")

    assert s.hamma_rol_tezmi is False
    assert s.tez_rollar == {"router"}


def test_tez_model_bosh_bolsa_yulduzcha_ISHLAMAYDI():
    """Model nomi yo'q bo'lsa hech kim noma'lum modelga yuborilmaydi."""
    from app.config import Sozlama

    s = Sozlama(tez_model="", tez_rollar_royxati="*")

    assert s.hamma_rol_tezmi is False


# --- Qimmat modelda qoladigan rollar ------------------------------------------
#
# `TEZ_ROLLAR_ROYXATI` da hamma ARZON rolni sanash mo'rt edi: yangi
# agent qo'shilganda uni ro'yxatga qo'shish unutiladi va u jimgina
# QIMMAT modelga tushib qolardi. Teskari ro'yxat xavfsizroq: standart
# holat arzon, chetga chiqish ATAYLAB yoziladi.


def test_sekin_royxati_YULDUZCHADAN_ustun():
    from app.config import Sozlama

    s = Sozlama(tez_model="gemini-3.5-flash", tez_rollar_royxati="*",
                sekin_rollar_royxati="legal-review")

    assert s.hamma_rol_tezmi is True
    assert "legal-review" in s.sekin_rollar


def test_sekin_royxati_bosh_bolsa_hech_kim_chetda_qolmaydi():
    from app.config import Sozlama

    s = Sozlama(tez_model="gemini-3.5-flash", tez_rollar_royxati="*")

    assert s.sekin_rollar == set()


def test_sekin_rollar_kichik_harfga_keltiriladi():
    from app.config import Sozlama

    s = Sozlama(sekin_rollar_royxati="Legal-Review, SALES-STRATEGY")

    assert s.sekin_rollar == {"legal-review", "sales-strategy"}


def test_orkestr_sekin_rolni_ASOSIY_modelda_qoldiradi():
    """`*` bo'lsa ham bu rol arzon modelga o'tmaydi."""
    from unittest.mock import patch

    from app.config import Sozlama
    from app.llm import AnthropicLlm
    from app.orkestr import Orkestr

    s = Sozlama(tez_model="gemini-3.5-flash", tez_rollar_royxati="*",
                sekin_rollar_royxati="legal-review",
                anthropic_api_key="sinov")

    with patch("app.orkestr.sozlama", lambda: s):
        o = Orkestr(llm=AnthropicLlm(), baza=None)
        sekin = o._llm_uchun("legal-review")
        tez = o._llm_uchun("hvac-calc")

    assert isinstance(sekin, AnthropicLlm)
    assert not isinstance(tez, AnthropicLlm)

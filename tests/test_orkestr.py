"""Orkestr — reja bajarilishi, zanjir to'xtashi, log yozilishi."""

from __future__ import annotations

import json

import pytest

from app.baza import Baza
from app.kontraktlar import Kontrakt, kontraktlarni_yukla
from app.konvert import Holat, Xavf
from app.orkestr import Orkestr

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
def ulanmagan_bilan(kontraktlar):
    """Haqiqiy kontraktlar + ataylab ulanmagan sinov agenti.

    Barcha 7 agent ulangandan keyin ham "ulanmagan" yo'lini tekshirib turish
    uchun kerak — aks holda bu shox umuman sinalmay qoladi.
    """
    sinov = Kontrakt(
        rol="sinov-agent",
        lavozim="Sinov agenti",
        ism="Sinov",
        xavf=Xavf.PAST,
        amalga_oshirilgan=False,
        maqsad="Faqat testda ishlatiladi — kodda hech qachon ulanmaydi",
        input=["-"],
        output=["-"],
        chegaralar=["-"],
        ruxsatlar=["-"],
        tasdiq_qachon=["-"],
        xato_holati=["-"],
    )
    return kontraktlar | {"sinov-agent": sinov}


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "orkestr.db")
    await b.tayyorla()
    return b


def router_javobi(qadamlar, **ustama):
    malumot = {
        "niyat": "test",
        "vazifa_soni": len(qadamlar),
        "qadamlar": qadamlar,
        "mos_agent_yoq": False,
        "izoh": "",
    }
    malumot.update(ustama)
    return json_javob(malumot)


ZARA_NATIJA = {
    "bozor": "Toshkent",
    "valyuta": "UZS",
    "yozuvlar": [
        {
            "mahsulot": "iPhone 15",
            "narx": 12_000_000.0,
            "valyuta": "UZS",
            "sana": "2026-07-25",
            "manba_nomi": "Olcha.uz",
            "havola": "https://olcha.uz/x",
            "ishonch": "yuqori",
            "manba_ishonchsiz": False,
            "izoh": "",
        }
    ],
    "topilmaganlar": [],
    "ziddiyatlar": [],
    "diqqat": [],
}


@pytest.mark.asyncio
async def test_vertikal_kesim_zara(kontraktlar, baza):
    """Muvaffaqiyat mezoni: so'rov -> router Zarani tanlaydi -> konvert -> log."""
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "price-monitor",
                        "vazifa": "iPhone 15 narxini top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ]
            ),
            javob([matn_bloki(json.dumps(ZARA_NATIJA, ensure_ascii=False))]),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("iPhone 15 narxini topib bering")

    assert natija.yakuniy.kim == "price-monitor"
    assert natija.yakuniy.holat is Holat.TUGADI
    assert len(natija.qadamlar) == 1
    assert natija.qadamlar[0].korinish == "Narx analitigi Zara"
    assert natija.iz_id is not None

    # Har qadam logda ko'rinadi
    iz = await baza.iz(natija.iz_id)
    assert iz["qadamlar"][0]["agent"] == "price-monitor"
    assert iz["qadamlar"][0]["konvert"]["holat"] == "tugadi"
    assert iz["reja"]["qadamlar"][0]["agent"] == "price-monitor"


@pytest.mark.asyncio
async def test_ulanmagan_agent_ochiq_aytiladi(ulanmagan_bilan, baza):
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "sinov-agent",
                        "vazifa": "nimadir qil",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ]
            )
        ]
    )
    natija = await Orkestr(llm, baza, ulanmagan_bilan).bajar("Sinov vazifasi")

    # Ulanmagan agent — xato emas, alohida holat (panel ko'k rangda ko'rsatadi)
    assert natija.yakuniy.holat is Holat.ULANMAGAN
    assert "ulanmagan" in natija.yakuniy.izoh


@pytest.mark.asyncio
async def test_api_xatosi_500_bermaydi(kontraktlar, baza):
    """Model topilmasa / API yiqilsa — konvert qaytadi, istisno chiqmaydi."""
    import anthropic
    import httpx

    class YiqiluvchiLlm:
        async def javob(self, **soro):
            raise anthropic.NotFoundError(
                message="model: xato-model was not found",
                response=httpx.Response(404, request=httpx.Request("POST", "https://x")),
                body=None,
            )

    natija = await Orkestr(YiqiluvchiLlm(), baza, kontraktlar).bajar("iPhone narxi")

    assert natija.yakuniy.kim == "router"
    assert natija.yakuniy.holat is Holat.XATO
    # Izoh menejer o'qiy oladigan bo'lsin: sabab + nima qilish kerakligi.
    # Xom `Error code: 404 - {...}` hech kimga yordam bermaydi.
    assert "LLM_MODEL" in natija.yakuniy.izoh
    assert "Error code" not in natija.yakuniy.izoh
    assert natija.iz_id is not None, "xato ham logga tushishi kerak"


@pytest.mark.asyncio
async def test_mos_agent_yoq(kontraktlar, baza):
    llm = SoxtaLlm(
        [
            router_javobi([], mos_agent_yoq=True, izoh="Bunday vazifa kontraktlarda yo'q"),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Ofisga pizza buyurtma qil")

    assert natija.yakuniy.kim == "router"
    # Mos agent yo'qligi — normal javob, xato emas (panel kulrang ko'rsatadi)
    assert natija.yakuniy.holat is Holat.MOS_AGENT_YOQ
    assert "kontraktlarda yo'q" in natija.yakuniy.izoh


@pytest.mark.asyncio
async def test_zanjir_ulanmagan_qadamda_toxtaydi(ulanmagan_bilan, baza):
    """1-qadam ulanmagan agent -> 2-qadam bajarilmaydi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "sinov-agent",
                        "vazifa": "birinchi qadam",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                    {
                        "agent": "price-monitor",
                        "vazifa": "narxni top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                ]
            )
        ]
    )
    natija = await Orkestr(llm, baza, ulanmagan_bilan).bajar("Ikki qadamli vazifa")

    assert len(natija.qadamlar) == 1
    assert natija.yakuniy.holat is Holat.ULANMAGAN


@pytest.mark.asyncio
async def test_zanjir_xatoda_toxtaydi(kontraktlar, baza):
    """1-qadam agent xatosi -> 2-qadam bajarilmaydi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "competitor-watch",
                        "vazifa": "raqiblar",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                    {
                        "agent": "price-monitor",
                        "vazifa": "narxni top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                ]
            ),
            javob([matn_bloki("bu JSON emas")]),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Raqiblarni ko'rib narxni top")

    assert len(natija.qadamlar) == 1
    assert natija.yakuniy.holat is Holat.XATO


KARIM_NATIJA = {
    "hudud": "Toshkent",
    "davr": "oxirgi 1 oy",
    "topilmalar": [
        {
            "raqib": "Texnomart",
            "mavzu": "aksiya",
            "tafsilot": "Maishiy texnikaga 15% chegirma",
            "sana": "2026-07-15",
            "manba_nomi": "texnomart.uz",
            "havola": "https://texnomart.uz/aksiya",
            "ishonch": "yuqori",
            "manba_ishonchsiz": False,
        }
    ],
    "trendlar": ["Yozgi chegirma mavsumi"],
    "xulosa": "Raqib narx bo'yicha agressiv siyosatga o'tdi.",
    "topilmaganlar": [],
}

MALIKA_NATIJA = {
    "kampaniya_nomi": "Yozgi salqinlik",
    "auditoriya": "Toshkentdagi oilalar",
    "goya": "Chegirmaga xizmat sifati bilan javob",
    "asos": ["Karim: Texnomart 15% chegirma (2026-07-15)"],
    "variantlar": [
        {"kanal": "Telegram", "ohang": "sokin", "matn": "Chegirma o'tadi — xizmat qoladi."}
    ],
    "tavsiya_kanal": "Telegram",
    "tavsiya_vaqt": "Iyul oxiri",
    "sorash_kerak": [],
    "asossiz_dovolar": [],
}


@pytest.mark.asyncio
async def test_toliq_zanjir_karim_malika(kontraktlar, baza):
    """2-bosqichning asosiy tekshiruv nuqtasi: competitor-watch -> marketing.

    Karim ishlaydi, konverti Malikaga o'tadi, Malika qoralama beradi va
    natija tasdiqsiz chiqmaydi.
    """
    llm = SoxtaLlm(
        [
            router_javobi(
                [
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
                ]
            ),
            javob([matn_bloki(json.dumps(KARIM_NATIJA, ensure_ascii=False))]),
            javob([matn_bloki(json.dumps(MALIKA_NATIJA, ensure_ascii=False))]),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "Raqiblarni ko'rib chiqing va kampaniya taklif qiling"
    )

    assert [q.agent for q in natija.qadamlar] == ["competitor-watch", "marketing"]
    assert [q.korinish for q in natija.qadamlar] == [
        "Raqobat tahlilchisi Karim",
        "Marketolog Malika",
    ]

    # Karim tugadi, konverti Malikaga kirish bo'lib o'tdi
    assert natija.qadamlar[0].konvert.holat is Holat.TUGADI
    malika_kirishi = natija.qadamlar[1].kirish_kontekst
    assert malika_kirishi["oldingi_agent"] == "competitor-watch"
    assert malika_kirishi["oldingi_natija"]["topilmalar"][0]["raqib"] == "Texnomart"

    # Malika qoralama berdi, lekin tasdiqsiz chiqmadi
    assert natija.yakuniy.kim == "marketing"
    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA
    assert natija.yakuniy.tasdiq_kerak is True
    assert "nashr etiladigan kontent" in natija.yakuniy.izoh
    assert natija.yakuniy.natija["variantlar"][0]["kanal"] == "Telegram"

    # To'liq iz logda saqlandi
    iz = await baza.iz(natija.iz_id)
    assert [q["agent"] for q in iz["qadamlar"]] == ["competitor-watch", "marketing"]


@pytest.mark.asyncio
async def test_tasdiq_kerak_bolsa_holat_ozgaradi(kontraktlar, baza):
    """Tasdiq talab qilingan qadam natijasi tasdiqsiz 'tugadi' bo'lib chiqmaydi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "price-monitor",
                        "vazifa": "narxni top va rasmiy hisobotga yoz",
                        "tasdiq_kerak": True,
                        "tasdiq_sababi": "rasmiy hisobotga o'tadi",
                    }
                ]
            ),
            javob([matn_bloki(json.dumps(ZARA_NATIJA, ensure_ascii=False))]),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Narxni top va hisobotga yoz")

    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA
    assert natija.yakuniy.tasdiq_kerak is True
    assert "TASDIQ KERAK" in natija.yakuniy.izoh


@pytest.mark.asyncio
async def test_kuzatuvchi_har_qadamda_chaqiriladi(kontraktlar, baza):
    """Bot "Rustam ishlayapti…" xabarini shu kuzatuvchi orqali yangilaydi.

    Zanjir 60-80 soniya olishi mumkin; kuzatuvchi bo'lmasa menejer shuncha
    vaqt bo'sh ekranga qaraydi. Shuning uchun u har qadamda IKKI marta
    chaqilishi shart: boshida (konvert=None) va oxirida (konvert bilan).
    """
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "price-monitor",
                        "vazifa": "iPhone 15 narxini top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ]
            ),
            javob([matn_bloki(json.dumps(ZARA_NATIJA, ensure_ascii=False))]),
        ]
    )
    chaqiruvlar: list[tuple[str, bool]] = []

    async def kuzatuvchi(agent, konvert):
        chaqiruvlar.append((agent, konvert is None))

    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "iPhone 15 narxini topib bering", kuzatuvchi=kuzatuvchi
    )

    assert natija.yakuniy.holat is Holat.TUGADI
    assert chaqiruvlar == [("price-monitor", True), ("price-monitor", False)]


@pytest.mark.asyncio
async def test_kuzatuvchi_xatosi_zanjirni_toxtatmaydi(kontraktlar, baza):
    """Telegram xabarni tahrirlay olmasa ham KP baribir tayyor bo'lishi kerak.

    Kuzatuvchi — bu faqat ko'rsatkich. Uning xatosi ishning o'zini
    yo'qotmasligi shart.
    """
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "price-monitor",
                        "vazifa": "iPhone 15 narxini top",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ]
            ),
            javob([matn_bloki(json.dumps(ZARA_NATIJA, ensure_ascii=False))]),
        ]
    )

    async def buzuq_kuzatuvchi(agent, konvert):
        raise RuntimeError("Telegram javob bermadi")

    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "iPhone 15 narxini topib bering", kuzatuvchi=buzuq_kuzatuvchi
    )

    assert natija.yakuniy.holat is Holat.TUGADI
    assert natija.yakuniy.kim == "price-monitor"

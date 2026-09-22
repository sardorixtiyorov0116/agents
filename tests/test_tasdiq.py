"""Tasdiq oqimi — to'xtash, saqlash, davom ettirish, rad etish.

Asosiy talab: tasdiq holati BAZADA saqlanadi, xotirada emas — server qayta
ishga tushsa ham yo'qolmaydi.
"""

from __future__ import annotations

import json

import pytest

from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat
from app.orkestr import Orkestr, TasdiqXatosi

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "tasdiq.db")
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


def doston_taklifi(sql: str):
    return javob(
        [
            matn_bloki(
                json.dumps(
                    {
                        "sql": sql,
                        "izoh": "buyurtma holatini yangilash",
                        "yozish_kerakmi": True,
                        "yozish_sababi": "yozish so'ralgan",
                    },
                    ensure_ascii=False,
                )
            )
        ]
    )


YOZISH_QADAMI = [
    {
        "agent": "data-query",
        "vazifa": "7-buyurtmani yakunlandi deb belgila",
        "tasdiq_kerak": False,
        "tasdiq_sababi": "",
    }
]

YANGILASH_SQL = "UPDATE buyurtmalar SET holat = 'yakunlandi' WHERE id = 7"


async def yozish_sorovi(llm_javoblar, baza, kontraktlar):
    llm = SoxtaLlm(llm_javoblar)
    return await Orkestr(llm, baza, kontraktlar).bajar("7-buyurtmani yakunla")


# --- to'xtash va saqlash -----------------------------------------------------


@pytest.mark.asyncio
async def test_tasdiq_kutilganda_bazaga_yoziladi(kontraktlar, baza):
    natija = await yozish_sorovi(
        [router_javobi(YOZISH_QADAMI), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )

    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA

    kutilayotgan = await baza.kutilayotgan_tasdiqlar()
    assert len(kutilayotgan) == 1
    assert kutilayotgan[0]["iz_id"] == natija.iz_id
    assert kutilayotgan[0]["agent"] == "data-query"
    assert kutilayotgan[0]["korinish"] == "Ma'lumot muhandisi Doston"
    assert kutilayotgan[0]["holat"] == "kutilmoqda"

    # Harakat hali BAJARILMAGAN
    qator = await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7")
    assert qator[0]["holat"] == "yangi"


# --- tasdiqlash --------------------------------------------------------------


@pytest.mark.asyncio
async def test_tasdiqlangach_harakat_bajariladi(kontraktlar, baza):
    natija = await yozish_sorovi(
        [router_javobi(YOZISH_QADAMI), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )

    # Yangi Orkestr nusxasi = server qayta ishga tushgandek. Holat bazadan
    # o'qiladi, xotirada hech narsa saqlanmagan.
    yangi = Orkestr(SoxtaLlm([]), baza, kontraktlar)
    davomi = await yangi.davom_ettir(natija.iz_id, tasdiqlaymi=True, izoh="ko'rib chiqdim")

    assert davomi.yakuniy.holat is Holat.TUGADI
    assert davomi.iz_id == natija.iz_id

    # Endi harakat haqiqatan bajarildi
    qator = await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7")
    assert qator[0]["holat"] == "yakunlandi"

    # Tasdiq yopildi va ro'yxatdan chiqdi
    assert await baza.kutilayotgan_tasdiqlar() == []
    tasdiq = await baza.tasdiq(natija.iz_id)
    assert tasdiq["holat"] == "tasdiqlandi"
    assert tasdiq["qaror_izohi"] == "ko'rib chiqdim"

    # Iz yangilandi — yakuniy natija almashdi
    iz = await baza.iz(natija.iz_id)
    assert iz["yakuniy"]["holat"] == "tugadi"


@pytest.mark.asyncio
async def test_tasdiqdan_keyin_zanjir_davom_etadi(kontraktlar, baza):
    """Tasdiq kutgan qadamdan keyingi qadamlar ham bajariladi."""
    zanjir = [
        {
            "agent": "data-query",
            "vazifa": "7-buyurtmani yakunla",
            "tasdiq_kerak": False,
            "tasdiq_sababi": "",
        },
        {
            "agent": "marketing",
            "vazifa": "natija asosida xabar qoralamasi",
            "tasdiq_kerak": False,
            "tasdiq_sababi": "",
        },
    ]
    natija = await yozish_sorovi(
        [router_javobi(zanjir), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )
    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA
    assert len(natija.qadamlar) == 1, "Malika hali ishlamasligi kerak"

    malika = javob(
        [
            matn_bloki(
                json.dumps(
                    {
                        "kampaniya_nomi": "Buyurtma yakunlandi xabari",
                        "auditoriya": "mijoz",
                        "goya": "xabar berish",
                        "asos": ["Doston: 1 qator yangilandi"],
                        "variantlar": [{"kanal": "SMS", "ohang": "rasmiy", "matn": "Tayyor"}],
                        "tavsiya_kanal": "SMS",
                        "tavsiya_vaqt": "darhol",
                        "sorash_kerak": [],
                        "asossiz_dovolar": [],
                    },
                    ensure_ascii=False,
                )
            )
        ]
    )
    davomi = await Orkestr(SoxtaLlm([malika]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=True
    )

    assert [q.agent for q in davomi.qadamlar] == ["data-query", "marketing"]
    assert davomi.yakuniy.kim == "marketing"
    assert davomi.yakuniy.holat is Holat.TUGADI
    # Malika Dostonning natijasini kirish sifatida oldi
    assert davomi.qadamlar[1].kirish_kontekst["oldingi_agent"] == "data-query"


# --- rad etish ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_rad_etilsa_harakat_bajarilmaydi(kontraktlar, baza):
    natija = await yozish_sorovi(
        [router_javobi(YOZISH_QADAMI), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )

    davomi = await Orkestr(SoxtaLlm([]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=False, izoh="noto'g'ri buyurtma raqami"
    )

    assert davomi.yakuniy.holat is Holat.XATO
    assert "Inson rad etdi" in davomi.yakuniy.izoh
    assert "noto'g'ri buyurtma raqami" in davomi.yakuniy.izoh

    # Baza tegilmagan
    qator = await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7")
    assert qator[0]["holat"] == "yangi"

    tasdiq = await baza.tasdiq(natija.iz_id)
    assert tasdiq["holat"] == "rad_etildi"
    assert tasdiq["qaror_izohi"] == "noto'g'ri buyurtma raqami"


@pytest.mark.asyncio
async def test_rad_etilgan_zanjir_davom_etmaydi(kontraktlar, baza):
    zanjir = YOZISH_QADAMI + [
        {
            "agent": "marketing",
            "vazifa": "xabar",
            "tasdiq_kerak": False,
            "tasdiq_sababi": "",
        }
    ]
    natija = await yozish_sorovi(
        [router_javobi(zanjir), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )

    # Bo'sh LLM: Malika chaqirilsa test yiqiladi
    davomi = await Orkestr(SoxtaLlm([]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=False, izoh="kerak emas"
    )

    assert len(davomi.qadamlar) == 1
    assert davomi.yakuniy.holat is Holat.XATO


# --- xato holatlari ----------------------------------------------------------


@pytest.mark.asyncio
async def test_ikki_marta_tasdiqlab_bolmaydi(kontraktlar, baza):
    natija = await yozish_sorovi(
        [router_javobi(YOZISH_QADAMI), doston_taklifi(YANGILASH_SQL)], baza, kontraktlar
    )
    orkestr = Orkestr(SoxtaLlm([]), baza, kontraktlar)
    await orkestr.davom_ettir(natija.iz_id, tasdiqlaymi=True)

    with pytest.raises(TasdiqXatosi, match="allaqachon hal qilingan"):
        await orkestr.davom_ettir(natija.iz_id, tasdiqlaymi=True)


@pytest.mark.asyncio
async def test_tasdiq_sorlmagan_izni_davom_ettirib_bolmaydi(kontraktlar, baza):
    orkestr = Orkestr(SoxtaLlm([]), baza, kontraktlar)
    with pytest.raises(TasdiqXatosi, match="tasdiq so'ralmagan"):
        await orkestr.davom_ettir(999, tasdiqlaymi=True)


# --- katalogga yozish (Nodira) -----------------------------------------------


@pytest.fixture
def soxta_yozuvchi(monkeypatch):
    """Nodiraning yozish klientini soxtasiga almashtiradi.

    Orkestr agentni o'zi yasaydi, shuning uchun klass darajasida almashtiramiz.
    """
    import app.agentlar.katalog_admin as modul

    class SoxtaYozuvchi:
        def __init__(self, *a, **kw):
            self.bajarilgan: list = []

        def sozlanganmi(self):
            return True

        async def bajar(self, amal):
            self.bajarilgan.append(amal.model_dump())
            return {"amal": amal.tur, "yol": "/sinov", "metod": "PATCH",
                    "yuborilgan": amal.tozalangan(), "javob": {"ok": True}}

    nusxa = SoxtaYozuvchi()
    monkeypatch.setattr(modul, "ClimaventYozuvchi", lambda *a, **kw: nusxa)
    return nusxa


NODIRA_QADAMI = [
    {
        "agent": "catalog-admin",
        "vazifa": "ВК-315П narxini 2 400 000 qil",
        "tasdiq_kerak": False,
        "tasdiq_sababi": "",
    }
]


def nodira_taklifi():
    return javob(
        [
            matn_bloki(
                json.dumps(
                    {
                        "niyat": "narx belgilash",
                        "amallar": [
                            {"tur": "xususiyat_yangila", "nishon_id": 91,
                             "maydonlar": [{"nomi": "price", "qiymati": "2400000"}],
                             "izoh": "yangi narx"}
                        ],
                        "topilmadi": [],
                        "sorash_kerak": [],
                        "xavf": "",
                    },
                    ensure_ascii=False,
                )
            )
        ]
    )


@pytest.mark.asyncio
async def test_katalog_yozuvi_tasdiqsiz_bajarilmaydi(
    kontraktlar, baza, soxta_yozuvchi, monkeypatch
):
    """Eng muhim: router yuborsa ham, tasdiqsiz katalog o'zgarmaydi."""
    import app.agentlar.katalog_admin as modul

    async def katalog(self, vazifa):
        return "\n\nKATALOGDAN TOPILDI:\n- model id=91 | ВК-315П | narx: 0"

    monkeypatch.setattr(modul.KatalogAdmin, "_katalog_matni", katalog)

    llm = SoxtaLlm([router_javobi(NODIRA_QADAMI), nodira_taklifi()])
    natija = await Orkestr(llm, baza, kontraktlar).bajar("ВК-315П narxini belgila")

    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA
    assert soxta_yozuvchi.bajarilgan == [], "tasdiqsiz yozilmasligi kerak"

    kutilayotgan = await baza.kutilayotgan_tasdiqlar()
    assert kutilayotgan[0]["agent"] == "catalog-admin"


@pytest.mark.asyncio
async def test_katalog_yozuvi_tasdiqdan_keyin_bajariladi(
    kontraktlar, baza, soxta_yozuvchi, monkeypatch
):
    import app.agentlar.katalog_admin as modul

    async def katalog(self, vazifa):
        return "\n\nKATALOGDAN TOPILDI:\n- model id=91 | ВК-315П | narx: 0"

    monkeypatch.setattr(modul.KatalogAdmin, "_katalog_matni", katalog)

    llm = SoxtaLlm([router_javobi(NODIRA_QADAMI), nodira_taklifi()])
    natija = await Orkestr(llm, baza, kontraktlar).bajar("ВК-315П narxini belgila")

    # Yangi Orkestr = server qayta ishga tushgandek.
    davomi = await Orkestr(SoxtaLlm([]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=True, izoh="narx to'g'ri"
    )

    assert davomi.yakuniy.holat is Holat.TUGADI
    assert len(soxta_yozuvchi.bajarilgan) == 1
    assert soxta_yozuvchi.bajarilgan[0]["nishon_id"] == 91
    assert soxta_yozuvchi.bajarilgan[0]["maydonlar"] == {"price": "2400000"}
    assert davomi.yakuniy.natija["bajarilgan_soni"] == 1


@pytest.mark.asyncio
async def test_katalog_yozuvi_rad_etilsa_bajarilmaydi(
    kontraktlar, baza, soxta_yozuvchi, monkeypatch
):
    import app.agentlar.katalog_admin as modul

    async def katalog(self, vazifa):
        return "\n\nKATALOGDAN TOPILDI:\n- model id=91 | ВК-315П | narx: 0"

    monkeypatch.setattr(modul.KatalogAdmin, "_katalog_matni", katalog)

    llm = SoxtaLlm([router_javobi(NODIRA_QADAMI), nodira_taklifi()])
    natija = await Orkestr(llm, baza, kontraktlar).bajar("ВК-315П narxini belgila")

    davomi = await Orkestr(SoxtaLlm([]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=False, izoh="narx noto'g'ri"
    )

    assert davomi.yakuniy.holat is Holat.XATO
    assert soxta_yozuvchi.bajarilgan == []


# --- natijani ochadigan (harakatsiz) agent -----------------------------------


@pytest.mark.asyncio
async def test_qoralama_tasdiqlansa_natija_ochiladi(kontraktlar, baza):
    """Malika kabi agentlarda tasdiq natijani ochadi, qayta ishlatmaydi."""
    malika_natija = {
        "kampaniya_nomi": "Yozgi",
        "auditoriya": "hamma",
        "goya": "g'oya",
        "asos": [],
        "variantlar": [{"kanal": "Telegram", "ohang": "sokin", "matn": "Salom"}],
        "tavsiya_kanal": "Telegram",
        "tavsiya_vaqt": "iyul",
        "sorash_kerak": [],
        "asossiz_dovolar": [],
    }
    llm = SoxtaLlm(
        [
            router_javobi(
                [
                    {
                        "agent": "marketing",
                        "vazifa": "kampaniya qoralamasi",
                        "tasdiq_kerak": True,
                        "tasdiq_sababi": "nashr etiladigan kontent",
                    }
                ]
            ),
            javob([matn_bloki(json.dumps(malika_natija, ensure_ascii=False))]),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Kampaniya taklif qil")
    assert natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA

    # Bo'sh LLM: agent qayta chaqirilmasligi kerak
    davomi = await Orkestr(SoxtaLlm([]), baza, kontraktlar).davom_ettir(
        natija.iz_id, tasdiqlaymi=True, izoh="nashrga ruxsat"
    )

    assert davomi.yakuniy.holat is Holat.TUGADI
    assert davomi.yakuniy.tasdiq_kerak is False
    assert "INSON TASDIQLADI: nashrga ruxsat" in davomi.yakuniy.izoh
    # Qoralama saqlanib qoldi
    assert davomi.yakuniy.natija["variantlar"][0]["kanal"] == "Telegram"

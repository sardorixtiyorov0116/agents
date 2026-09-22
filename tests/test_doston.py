"""Ma'lumot muhandisi Doston — SELECT, tasdiq, va o'chirishning imkonsizligi.

Eng muhim testlar: model nima taklif qilsa ham, baza o'zgarmasligi.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.agentlar.malumot_muhandisi import MalumotMuhandisi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat

from .soxta import SoxtaLlm, javob, matn_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["data-query"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "doston.db")
    await b.tayyorla()
    return b


def taklif(sql: str, yozish: bool = False, izoh: str = "test", sabab: str = ""):
    return SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "sql": sql,
                                "izoh": izoh,
                                "yozish_kerakmi": yozish,
                                "yozish_sababi": sabab,
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
            )
        ]
    )


async def qatorlar_soni(baza, jadval: str) -> int:
    natija = await baza.sorov_bajar(f"SELECT count(*) AS n FROM {jadval}")
    return natija[0]["n"]


# --- normal holat ------------------------------------------------------------


@pytest.mark.asyncio
async def test_oddiy_select_ishlaydi(kontrakt, baza):
    llm = taklif("SELECT shahar, count(*) AS soni FROM mijozlar GROUP BY shahar")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("Mijozlar qaysi shaharlarda?")

    assert k.holat is Holat.TUGADI
    assert k.natija["qatorlar_soni"] == 3
    # Shaffoflik: ishlatilgan so'rov javobda ko'rinadi
    assert k.natija["sql"].startswith("SELECT shahar")
    assert "so'rov: SELECT shahar" in k.izoh
    assert k.manba[0].tur == "baza"


@pytest.mark.asyncio
async def test_sxema_promptga_beriladi(kontrakt, baza):
    llm = taklif("SELECT 1 AS a FROM mijozlar LIMIT 1")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await doston.ishla("nechta mijoz bor")

    matn = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "mijozlar(" in matn and "buyurtmalar(" in matn
    # Tizim jadvallari Dostonga ko'rsatilmaydi
    assert "izlar(" not in matn and "narxlar(" not in matn


@pytest.mark.asyncio
async def test_natija_bosh_bolsa_toqimaydi(kontrakt, baza):
    llm = taklif("SELECT * FROM mijozlar WHERE shahar = 'Yo''q shahar'")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("Yo'q shahardagi mijozlar")

    assert k.holat is Holat.TUGADI
    assert k.natija["qatorlar"] == []
    assert "topilmadi" in k.izoh


# --- chegara buzilishiga urinish ---------------------------------------------


@pytest.mark.asyncio
async def test_delete_taklifi_rad_etiladi_va_baza_ozgarmaydi(kontrakt, baza):
    """Eng muhim test: model DELETE taklif qilsa ham ma'lumot o'chmaydi."""
    oldin = await qatorlar_soni(baza, "mijozlar")

    llm = taklif("DELETE FROM mijozlar WHERE segment = 'jismoniy'", yozish=True)
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("Jismoniy mijozlarni o'chirib tashla")

    assert k.holat is Holat.XATO
    assert "rad etildi" in k.izoh
    assert await qatorlar_soni(baza, "mijozlar") == oldin


@pytest.mark.asyncio
async def test_drop_table_bajarilmaydi(kontrakt, baza):
    llm = taklif("DROP TABLE buyurtmalar")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("buyurtmalar jadvalini o'chir")

    assert k.holat is Holat.XATO
    assert await qatorlar_soni(baza, "buyurtmalar") == 8


@pytest.mark.asyncio
async def test_baza_darajasida_ham_ochirib_bolmaydi(baza):
    """Agent qatlamini butunlay chetlab o'tsak ham — SQLite rad etadi.

    Bu himoya promptda emas, ulanish darajasida ekanini isbotlaydi.
    """
    for sql in (
        "DELETE FROM mijozlar",
        "DROP TABLE mijozlar",
        "UPDATE mijozlar SET ism = 'x'",
        "SELECT * FROM izlar",
        "PRAGMA table_info(mijozlar)",
        "ATTACH DATABASE 'boshqa.db' AS b",
    ):
        with pytest.raises(sqlite3.Error):
            await baza.sorov_bajar(sql)

    # Yozish ulanishida ham o'chirish yopiq
    for sql in ("DELETE FROM mijozlar", "DROP TABLE mijozlar", "UPDATE izlar SET sorov = 'x'"):
        with pytest.raises(sqlite3.Error):
            await baza.sorov_bajar(sql, yozish=True)

    assert await qatorlar_soni(baza, "mijozlar") == 5


@pytest.mark.asyncio
async def test_maxfiy_jadvalga_yashirin_yollar_yopiq(baza):
    """Ichki so'rov, CTE, UNION orqali ham ruxsat etilmagan jadval ochilmaydi."""
    for sql in (
        "WITH x AS (SELECT sorov FROM izlar) SELECT * FROM x",
        "SELECT (SELECT sorov FROM izlar LIMIT 1) AS o FROM mijozlar",
        "SELECT ism FROM mijozlar UNION SELECT sorov FROM izlar",
        "SELECT name FROM sqlite_master",
        "CREATE VIEW v AS SELECT * FROM izlar",
        "CREATE TRIGGER t AFTER INSERT ON mijozlar BEGIN DELETE FROM mijozlar; END",
    ):
        with pytest.raises(sqlite3.Error):
            await baza.sorov_bajar(sql)

    # Yozish rejimida ham maxfiy jadvaldan o'qib ko'chirib bo'lmaydi
    for sql in (
        "INSERT INTO mijozlar SELECT * FROM izlar",
        "UPDATE mijozlar SET ism = (SELECT sorov FROM izlar LIMIT 1)",
    ):
        with pytest.raises(sqlite3.Error):
            await baza.sorov_bajar(sql, yozish=True)


@pytest.mark.asyncio
async def test_ogir_sorov_vaqt_chegarasida_toxtaydi(baza, monkeypatch):
    """Cheksiz/og'ir so'rov tizimni osib qo'ymaydi."""
    import app.baza as baza_moduli

    monkeypatch.setattr(baza_moduli, "SOROV_MUDDATI", 0.3)
    kesishma = ", ".join(f"mijozlar t{i}" for i in range(16))

    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        await baza.sorov_bajar(f"SELECT count(*) AS n FROM {kesishma}")


@pytest.mark.asyncio
async def test_ruxsat_etilmagan_jadval_rad_etiladi(kontrakt, baza):
    llm = taklif("SELECT sorov FROM izlar")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("Log yozuvlarini ko'rsat")

    assert k.holat is Holat.XATO
    assert "baza rad etdi" in k.izoh


@pytest.mark.asyncio
async def test_ikkinchi_buyruq_qoshib_bolmaydi(kontrakt, baza):
    """`;` orqali ikkinchi buyruq — `execute` bitta statement bilan cheklangan."""
    llm = taklif("SELECT 1 AS a; DELETE FROM mijozlar")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("nimadir")

    assert k.holat is Holat.XATO
    assert await qatorlar_soni(baza, "mijozlar") == 5


# --- yozish: tasdiq harakatdan OLDIN -----------------------------------------


@pytest.mark.asyncio
async def test_yozish_tasdiqsiz_bajarilmaydi(kontrakt, baza):
    oldin = await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7")

    llm = taklif(
        "UPDATE buyurtmalar SET holat = 'yakunlandi' WHERE id = 7",
        yozish=True,
        sabab="buyurtma holatini yangilash",
    )
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("7-buyurtmani yakunlandi deb belgila")

    assert k.holat is Holat.TASDIQ_KUTILMOQDA
    assert k.tasdiq_kerak is True
    assert "BAJARILMADI" in k.izoh
    assert k.natija["taklif_sql"].startswith("UPDATE")
    # Baza tegilmagan
    assert await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7") == oldin


@pytest.mark.asyncio
async def test_tasdiqdan_keyin_yozish_bajariladi(kontrakt, baza):
    """Tasdiq oqimi shu yo'ldan foydalanadi (5-bosqich)."""
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=SoxtaLlm([]), baza=baza)
    k = await doston.ishla(
        "7-buyurtmani yakunla",
        {
            "tasdiqlandi": True,
            "tasdiqlangan_sql": "UPDATE buyurtmalar SET holat = 'yakunlandi' WHERE id = 7",
        },
    )

    assert k.holat is Holat.TUGADI
    assert "tasdiqlangan yozish bajarildi" in k.izoh
    qator = await baza.sorov_bajar("SELECT holat FROM buyurtmalar WHERE id = 7")
    assert qator[0]["holat"] == "yakunlandi"


@pytest.mark.asyncio
async def test_tasdiqlangan_yozish_ham_ochira_olmaydi(kontrakt, baza):
    """Tasdiq berilgan bo'lsa ham DELETE ishlamaydi — huquq umuman yo'q."""
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=SoxtaLlm([]), baza=baza)
    k = await doston.ishla(
        "hammasini o'chir",
        {"tasdiqlandi": True, "tasdiqlangan_sql": "DELETE FROM mijozlar"},
    )

    assert k.holat is Holat.XATO
    assert await qatorlar_soni(baza, "mijozlar") == 5


# --- noaniq so'rov -----------------------------------------------------------


@pytest.mark.asyncio
async def test_noaniq_sorovda_aniqlashtirish_soraydi(kontrakt, baza):
    llm = taklif("", izoh="Qaysi davr uchun kerakligini aniqlashtiring")
    doston = MalumotMuhandisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await doston.ishla("Hisobot ber")

    assert k.holat is Holat.XATO
    assert "aniqlashtiring" in k.izoh


# --- namunaviy ma'lumot ochiq aytiladi ----------------------------------------
#
# `mijozlar` va `buyurtmalar` jadvallari hozir NAMUNAVIY qatorlar bilan
# to'ldirilgan. Javob ishonchli ohangda chiqadi va menejer uni haqiqat deb
# qabul qilishi mumkin — bu funksiya kamchiligi emas, ISHONCH buzilishi.


@pytest.mark.asyncio
async def test_namunaviy_bazada_ogohlantirish_chiqadi(kontrakt, baza, monkeypatch):
    from app.config import sozlama

    monkeypatch.setattr(sozlama(), "ish_bazasi_haqiqiy", False, raising=False)
    doston = MalumotMuhandisi(
        kontrakt=kontrakt, llm=taklif("SELECT shahar FROM mijozlar"), baza=baza
    )

    k = await doston.ishla("Qaysi shaharda mijoz ko'p?")

    assert k.natija.get("demo_ogohi"), "namunaviy ma'lumot ogohlantirishsiz chiqdi"
    assert "NAMUNAVIY" in k.natija["demo_ogohi"]


@pytest.mark.asyncio
async def test_real_baza_ulangach_ogohlantirish_yoqoladi(kontrakt, baza, monkeypatch):
    from app.config import sozlama

    monkeypatch.setattr(sozlama(), "ish_bazasi_haqiqiy", True, raising=False)
    doston = MalumotMuhandisi(
        kontrakt=kontrakt, llm=taklif("SELECT shahar FROM mijozlar"), baza=baza
    )

    k = await doston.ishla("Qaysi shaharda mijoz ko'p?")

    assert "demo_ogohi" not in k.natija


def test_ogohlantirish_javob_tepasida_turadi():
    """Pastda qolsa, uzun javobda ko'rinmay ketadi."""
    from presenter.agentlar import malumot

    matn = malumot({
        "demo_ogohi": "⚠️ NAMUNAVIY",
        "qatorlar": [{"shahar": "Toshkent"}],
        "qatorlar_soni": 1,
    })

    assert matn.startswith("⚠️ NAMUNAVIY")

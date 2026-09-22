"""HTTP darajasidagi uchidan-uchiga sinov: so'rov -> tasdiq -> davom."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import sozlama
from app.kontraktlar import reyestr
from app.main import app

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki


@pytest.fixture
def mijoz(tmp_path, monkeypatch):
    """Ilova + vaqtinchalik baza + soxta LLM (API'ga chiqmaydi).

    `BAZA_YOLI` ni almashtiramiz va sozlama keshini tozalaymiz — ilova
    lifespan'i bazani o'zi shu yo'lda yaratadi.
    """
    monkeypatch.setenv("BAZA_YOLI", str(tmp_path / "api.db"))
    # Panel paroli bo'sh: bu testlar mahalliy ulanish orqali kiradi.
    # Ishlab chiquvchining `.env` ida parol bo'lsa, hamma so'rov 401
    # olardi — testlar mahalliy sozlamaga bog'lanib qolmasin.
    monkeypatch.setenv("PANEL_PAROLI", "")
    sozlama.cache_clear()
    try:
        # `client=` MAHALLIY manzil beradi. Standart holda TestClient
        # o'zini "testclient" deb tanishtiradi va panel himoyasi (parol
        # qo'yilmagan holatda faqat 127.0.0.1 ga ruxsat beradi) uni
        # to'g'ri rad etadi — bu himoya ishlayotganining belgisi.
        with TestClient(app, client=("127.0.0.1", 50000)) as c:
            yield c
    finally:
        sozlama.cache_clear()


def llm_qoy(mijoz, javoblar):
    mijoz.app.state.llm = SoxtaLlm(javoblar)
    mijoz.app.state.llm_xatosi = None


DOSTON_TAKLIFI = javob(
    [
        matn_bloki(
            json.dumps(
                {
                    "sql": "UPDATE buyurtmalar SET holat = 'yakunlandi' WHERE id = 7",
                    "izoh": "holatni yangilash",
                    "yozish_kerakmi": True,
                    "yozish_sababi": "yozish so'ralgan",
                },
                ensure_ascii=False,
            )
        )
    ]
)

ROUTER_JAVOBI = json_javob(
    {
        "niyat": "buyurtma holatini yangilash",
        "vazifa_soni": 1,
        "qadamlar": [
            {
                "agent": "data-query",
                "vazifa": "7-buyurtmani yakunlandi deb belgila",
                "tasdiq_kerak": False,
                "tasdiq_sababi": "",
            }
        ],
        "mos_agent_yoq": False,
        "izoh": "",
    }
)


def test_agentlar_royxati(mijoz):
    javob_ = mijoz.get("/agentlar")
    assert javob_.status_code == 200
    agentlar = javob_.json()
    assert len(agentlar) == len(reyestr())
    ulangan = [a["rol"] for a in agentlar if a["amalga_oshirilgan"]]
    assert "data-query" in ulangan and "marketing" in ulangan


def test_tasdiq_oqimi_http_orqali(mijoz):
    llm_qoy(mijoz, [ROUTER_JAVOBI, DOSTON_TAKLIFI])

    # 1) So'rov -> tasdiq kutilmoqda
    javob_ = mijoz.post("/sorov", json={"matn": "7-buyurtmani yakunla"})
    assert javob_.status_code == 200
    natija = javob_.json()
    iz_id = natija["iz_id"]
    assert natija["yakuniy"]["holat"] == "tasdiq_kutilmoqda"

    # 2) Kutilayotgan tasdiqlar ro'yxatida ko'rinadi
    kutilayotgan = mijoz.get("/tasdiq").json()
    assert [t["iz_id"] for t in kutilayotgan] == [iz_id]
    assert kutilayotgan[0]["korinish"] == "Ma'lumot muhandisi Doston"

    # 3) Tasdiqlash -> zanjir yakunlanadi
    llm_qoy(mijoz, [])
    javob_ = mijoz.post(f"/tasdiq/{iz_id}", json={"tasdiqlaymi": True, "izoh": "roziman"})
    assert javob_.status_code == 200
    assert javob_.json()["yakuniy"]["holat"] == "tugadi"

    # 4) Ro'yxat bo'shadi
    assert mijoz.get("/tasdiq").json() == []

    # 5) Ikkinchi marta tasdiqlab bo'lmaydi
    javob_ = mijoz.post(f"/tasdiq/{iz_id}", json={"tasdiqlaymi": True})
    assert javob_.status_code == 409


def test_rad_etish_http_orqali(mijoz):
    llm_qoy(mijoz, [ROUTER_JAVOBI, DOSTON_TAKLIFI])
    iz_id = mijoz.post("/sorov", json={"matn": "7-buyurtmani yakunla"}).json()["iz_id"]

    llm_qoy(mijoz, [])
    javob_ = mijoz.post(f"/tasdiq/{iz_id}", json={"tasdiqlaymi": False, "izoh": "kerak emas"})

    assert javob_.status_code == 200
    yakuniy = javob_.json()["yakuniy"]
    assert yakuniy["holat"] == "xato"
    assert "Inson rad etdi" in yakuniy["izoh"]


def test_log_korinishi_ochiladi(mijoz):
    javob_ = mijoz.get("/")
    assert javob_.status_code == 200
    assert "Agentlar tizimi" in javob_.text


# --- panel -------------------------------------------------------------------


def test_panel_va_statik_fayllar_ochiladi(mijoz):
    assert mijoz.get("/panel").status_code == 200
    assert "panel.js" in mijoz.get("/panel").text
    assert mijoz.get("/statik/panel.css").status_code == 200
    assert mijoz.get("/statik/panel.js").status_code == 200


def test_statistika(mijoz):
    s = mijoz.get("/statistika").json()
    assert s["agentlar_soni"] == len(reyestr())
    assert s["ulangan_agentlar_soni"] == len(reyestr())
    assert s["tasdiq_kutilmoqda"] == 0

    llm_qoy(mijoz, [ROUTER_JAVOBI, DOSTON_TAKLIFI])
    mijoz.post("/sorov", json={"matn": "7-buyurtmani yakunla"})

    s = mijoz.get("/statistika").json()
    assert s["tasdiq_kutilmoqda"] == 1
    assert s["bugun_sorovlar"] == 1
    assert "data-query" in s["bugun_ishlagan_agentlar"]


def test_agent_faoliyati_oxirgi_holatni_beradi(mijoz):
    llm_qoy(mijoz, [ROUTER_JAVOBI, DOSTON_TAKLIFI])
    mijoz.post("/sorov", json={"matn": "7-buyurtmani yakunla"})

    faoliyat = {a["rol"]: a for a in mijoz.get("/agent-faoliyati").json()}
    assert len(faoliyat) == len(reyestr())
    assert faoliyat["data-query"]["oxirgi"]["holat"] == "tasdiq_kutilmoqda"
    assert faoliyat["data-query"]["korinish"] == "Ma'lumot muhandisi Doston"
    # Hali ishlamagan agentda oxirgi holat yo'q
    assert faoliyat["price-monitor"]["oxirgi"] is None


def test_ozgarish_belgisi_qadam_qoshilganda_ozgaradi(mijoz):
    """SSE shu belgiga tayanadi — zanjir jonli ko'rinishi uchun."""
    import asyncio

    baza = mijoz.app.state.baza
    oldin = asyncio.run(baza.ozgarish_belgisi())

    llm_qoy(mijoz, [ROUTER_JAVOBI, DOSTON_TAKLIFI])
    mijoz.post("/sorov", json={"matn": "7-buyurtmani yakunla"})

    assert asyncio.run(baza.ozgarish_belgisi()) != oldin


def test_ishlayotgan_sorov_izda_korinadi(mijoz):
    """So'rov boshida iz ochiladi: `yakuniy` bo'sh = hali ishlayapti."""
    import asyncio

    baza = mijoz.app.state.baza
    iz_id = asyncio.run(baza.iz_boshla("sinov so'rovi", {"qadamlar": []}))

    izlar = mijoz.get("/izlar?chek=5").json()
    ishlayotgan = [iz for iz in izlar if iz["id"] == iz_id]
    assert ishlayotgan and ishlayotgan[0]["yakuniy"] is None

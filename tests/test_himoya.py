"""Panel himoyasi.

Serverga chiqarishdan oldin panel butunlay ochiq edi: manzilni bilgan
har kim `/izlar` dan barcha KP mazmunini o'qib, `/sorov` bilan
agentlarni ishga tushirib (ya'ni bizning hisobimizdan pul sarflab)
qo'ya olardi.

Bu testlar HIMOYA FAIL-CLOSED ekanini qoplaydi: parol qo'yishni
unutsak ham ma'lumot tashqariga chiqmaydi.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import sozlama
from app.main import app


@pytest.fixture
def tayyorla(tmp_path, monkeypatch):
    monkeypatch.setenv("BAZA_YOLI", str(tmp_path / "himoya.db"))

    def yasa(parol: str | None, manzil: str):
        # `delenv` yetarli emas: `sozlama()` qiymatni `.env` FAYLIDAN ham
        # o'qiydi. Ishlab chiquvchining `.env` ida parol bo'lsa,
        # "parolsiz holat" testlari o'sha parolni olib, yiqilardi.
        # Bo'sh muhit o'zgaruvchisi `.env` dan ustun turadi.
        monkeypatch.setenv("PANEL_PAROLI", "" if parol is None else parol)
        sozlama.cache_clear()
        return TestClient(app, client=(manzil, 50000))

    yield yasa
    sozlama.cache_clear()


def basic(parol: str, nomi: str = "jihozvent") -> dict[str, str]:
    kalit = base64.b64encode(f"{nomi}:{parol}".encode()).decode()
    return {"Authorization": f"Basic {kalit}"}


# --- parolsiz holat -----------------------------------------------------------


@pytest.mark.parametrize("yol", ["/", "/panel", "/ofis", "/izlar", "/agentlar"])
def test_parolsiz_tashqaridan_yopiq(tayyorla, yol):
    """Parol qo'yilmagan bo'lsa — begona IP hech narsa ko'rmaydi."""
    with tayyorla(None, "203.0.113.7") as m:
        javob = m.get(yol)

    assert javob.status_code == 403
    assert "PANEL_PAROLI" in javob.json()["xato"]


def test_parolsiz_sorov_yuborib_bolmaydi(tayyorla):
    """ENG MUHIMI: begona odam agentlarni ishga tushira olmaydi."""
    with tayyorla(None, "203.0.113.7") as m:
        javob = m.post("/sorov", json={"sorov": "pul sarfla"})

    assert javob.status_code == 403


def test_parolsiz_mahalliy_ulanish_ishlaydi(tayyorla):
    """Mahalliy kompyuterda ishlash buzilmasin."""
    with tayyorla(None, "127.0.0.1") as m:
        assert m.get("/panel").status_code == 200


# --- parol qo'yilgan holat ----------------------------------------------------


def test_parol_bilan_kiriladi(tayyorla):
    with tayyorla("maxfiy123", "203.0.113.7") as m:
        assert m.get("/panel", headers=basic("maxfiy123")).status_code == 200


def test_notogri_parol_rad_etiladi(tayyorla):
    with tayyorla("maxfiy123", "203.0.113.7") as m:
        javob = m.get("/panel", headers=basic("boshqa"))

    assert javob.status_code == 401
    assert "Basic" in javob.headers.get("WWW-Authenticate", "")


def test_notogri_foydalanuvchi_rad_etiladi(tayyorla):
    with tayyorla("maxfiy123", "203.0.113.7") as m:
        assert m.get("/panel", headers=basic("maxfiy123", "admin")).status_code == 401


def test_parolsiz_sorovga_401_qaytadi(tayyorla):
    with tayyorla("maxfiy123", "203.0.113.7") as m:
        assert m.get("/panel").status_code == 401


@pytest.mark.parametrize("sarlavha", [
    {"Authorization": "Bearer maxfiy123"},        # boshqa sxema
    {"Authorization": "Basic ???"},               # buzuq base64
    {"Authorization": "Basic " + base64.b64encode(b"parolsiz").decode()},
])
def test_buzuq_sarlavha_yiqitmaydi(tayyorla, sarlavha):
    with tayyorla("maxfiy123", "203.0.113.7") as m:
        assert m.get("/panel", headers=sarlavha).status_code == 401


# --- salomat har doim ochiq ---------------------------------------------------


def test_salomat_parolsiz_ham_ochiq(tayyorla):
    """Docker/Railway sog'liq tekshiruvi parol bilan kira olmaydi."""
    with tayyorla(None, "203.0.113.7") as m:
        javob = m.get("/salomat")

    assert javob.status_code == 200
    assert javob.json()["holat"] == "ishlayapti"


def test_salomatda_kalit_korinmaydi(tayyorla):
    """Ochiq endpoint maxfiy narsani chiqarmasligi kerak."""
    with tayyorla(None, "203.0.113.7") as m:
        matn = m.get("/salomat").text

    assert "sk-ant" not in matn
    assert "PANEL_PAROLI" not in matn

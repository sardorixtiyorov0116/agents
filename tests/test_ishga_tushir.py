"""Jarayon boshqaruvchisi (serverda uchala jarayonni ushlab turadi).

Serverda hech kim qarab turmaydi: bot tarmoq uzilishidan yiqilsa, uni
qayta ko'taradigan odam yo'q. Shuning uchun boshqaruvchi:
  - yiqilgan jarayonni qayta ko'taradi;
  - ketma-ket yiqilaverса kutishni oshiradi (log to'lib ketmasin);
  - tokeni yo'q botni umuman ishga tushirmaydi (aks holda u cheksiz
    yiqilib, cheksiz qayta ko'tarilardi).
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

import ishga_tushir


@pytest.fixture(autouse=True)
def log_ajratilgan(tmp_path, monkeypatch):
    """Boshqaruvchi logi ISHLAB TURGAN faylga tushmasin.

    JONLI MUAMMO (2026-09-14): pytest chiqishni ushlaydi, shuning uchun
    `sys.stdout.isatty()` yolg'on bo'lib, `log()` faylga yozadi. Yo'l
    berilmagani uchun esa `chiqish/ishga_tushir.log` tanlanardi — o'sha
    fayl serverdagi haqiqiy boshqaruvchining logi. Har test yurganda unga
    o'nlab "sinov: to'xtadi (kod=1)" qatori qo'shilib, haqiqiy
    yiqilishni qidirganda chalg'itardi.
    """
    monkeypatch.setenv("BOSHQARUVCHI_LOG", str(tmp_path / "boshqaruvchi.log"))
    monkeypatch.setattr(ishga_tushir, "_log_fayli", None)
    yield
    oqim = ishga_tushir._log_fayli
    if oqim is not None:
        oqim.close()
    ishga_tushir._log_fayli = None


@pytest.fixture(autouse=True)
def tez(monkeypatch):
    """Testlar sekund emas, millisekund kutsin."""
    monkeypatch.setattr(ishga_tushir, "ENG_KAM_KUTISH", 0.02)
    monkeypatch.setattr(ishga_tushir, "ENG_KOP_KUTISH", 0.08)
    monkeypatch.setattr(ishga_tushir, "BARQAROR", 5.0)
    ishga_tushir.toxtatilyapti.clear()
    yield
    ishga_tushir.toxtatilyapti.set()


def yurgiz(jarayon: ishga_tushir.Jarayon, muddat: float = 0.8) -> None:
    oqim = threading.Thread(target=jarayon.kuzat, daemon=True)
    oqim.start()
    time.sleep(muddat)
    ishga_tushir.toxtatilyapti.set()
    jarayon.toxtat()
    oqim.join(timeout=5)


# --- qaysi jarayonlar ishga tushadi -------------------------------------------


def tokenlar(monkeypatch, ichki: str, mijoz: str) -> None:
    """Tokenlarni `sozlama()` darajasida qo'yadi.

    JONLI XATO: ilgari `os.environ` tekshirilardi. Mahalliy kompyuterda
    tokenlar `.env` faylida turadi — natijada ikkala bot ham ishga
    tushmasdi va faqat panel ko'tarilardi.
    """
    monkeypatch.setattr(
        ishga_tushir, "_token",
        lambda maydon: ichki if maydon == "bot_token" else mijoz,
    )


def test_tokensiz_bot_ishga_tushmaydi(monkeypatch):
    """Token yo'q bo'lsa bot cheksiz yiqilib turmasin."""
    tokenlar(monkeypatch, "", "")

    assert [j.nomi for j in ishga_tushir.jarayonlar()] == ["panel"]


def test_token_bor_bolsa_uchalasi_tushadi(monkeypatch):
    tokenlar(monkeypatch, "1:aaa", "2:bbb")

    assert [j.nomi for j in ishga_tushir.jarayonlar()] == [
        "panel", "ichki-bot", "mijoz-bot",
    ]


def test_token_env_faylidan_oqiladi(monkeypatch, tmp_path):
    """`.env` dagi token muhit o'zgaruvchisisiz ham topilishi kerak."""
    from app.config import sozlama

    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setattr(
        "app.config.sozlama",
        lambda: type("S", (), {"bot_token": "9:zzz", "mijoz_bot_token": ""})(),
    )

    assert ishga_tushir._token("bot_token") == "9:zzz"
    assert ishga_tushir._token("mijoz_bot_token") == ""


def test_bosh_token_hisobga_olinmaydi(monkeypatch):
    """"   " — token emas."""
    tokenlar(monkeypatch, "   ", "")

    assert [j.nomi for j in ishga_tushir.jarayonlar()] == ["panel"]


def test_port_muhitdan_olinadi(monkeypatch):
    """Bulut xizmatlari portni PORT orqali beradi."""
    monkeypatch.setenv("PORT", "3000")
    tokenlar(monkeypatch, "", "")

    assert "3000" in ishga_tushir.jarayonlar()[0].buyruq


# --- qayta ko'tarish ----------------------------------------------------------


def test_yiqilgan_jarayon_qayta_kotariladi():
    jarayon = ishga_tushir.Jarayon(
        "sinov", [sys.executable, "-c", "import sys; sys.exit(3)"]
    )

    yurgiz(jarayon)

    assert jarayon.yiqilish >= 2, "faqat bir marta ishga tushdi"


def test_ketma_ket_yiqilsa_kutish_oshadi():
    jarayon = ishga_tushir.Jarayon(
        "sinov", [sys.executable, "-c", "import sys; sys.exit(1)"]
    )

    yurgiz(jarayon)

    assert jarayon.kutish > ishga_tushir.ENG_KAM_KUTISH
    assert jarayon.kutish <= ishga_tushir.ENG_KOP_KUTISH, "chegara oshib ketdi"


def test_toxtatilganda_qayta_kotarilmaydi():
    jarayon = ishga_tushir.Jarayon(
        "sinov", [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    oqim = threading.Thread(target=jarayon.kuzat, daemon=True)
    oqim.start()
    time.sleep(0.3)

    ishga_tushir.toxtatilyapti.set()
    jarayon.toxtat()
    oqim.join(timeout=5)

    assert not oqim.is_alive(), "to'xtatilgandan keyin ham aylanyapti"
    assert jarayon.yiqilish == 0, "to'xtatish yiqilish deb sanaldi"


def test_toxtat_ishlamayotgan_jarayonda_yiqilmaydi():
    """Hali ishga tushmagan jarayonni to'xtatish xato bermasin."""
    ishga_tushir.Jarayon("sinov", [sys.executable, "-c", "pass"]).toxtat()


# --- log fayli (konsolsiz ishga tushirilganda) --------------------------------


def test_konsolsiz_ishlaganda_log_faylga_yoziladi(tmp_path, monkeypatch):
    """Vazifa rejalashtiruvchisi konsolsiz ishga tushiradi.

    Log faylga yozilmasa, nima bo'lgani UMUMAN ko'rinmaydi — muammoni
    aniqlashning iloji qolmaydi.
    """
    yol = tmp_path / "boshqaruvchi.log"
    monkeypatch.setenv("BOSHQARUVCHI_LOG", str(yol))
    monkeypatch.setattr(ishga_tushir, "_log_fayli", None)

    class Konsolsiz:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(ishga_tushir.sys, "stdout", Konsolsiz())
    try:
        ishga_tushir.log("sinov xabari")
    finally:
        oqim = ishga_tushir._log_fayli
        if oqim is not None:
            oqim.close()
        monkeypatch.setattr(ishga_tushir, "_log_fayli", None)

    assert "sinov xabari" in yol.read_text(encoding="utf-8")
    assert "boshqaruvchi" in yol.read_text(encoding="utf-8")


def test_konsol_bolsa_faylga_yozilmaydi(tmp_path, monkeypatch):
    """Mahalliy ishlatishda chiqish konsolda qolsin."""
    yol = tmp_path / "yozilmasin.log"
    monkeypatch.setenv("BOSHQARUVCHI_LOG", str(yol))
    monkeypatch.setattr(ishga_tushir, "_log_fayli", None)

    class Konsolli:
        yozilgan: list[str] = []

        @staticmethod
        def isatty() -> bool:
            return True

        @classmethod
        def write(cls, matn: str) -> int:
            cls.yozilgan.append(matn)
            return len(matn)

        @staticmethod
        def flush() -> None:
            pass

    monkeypatch.setattr(ishga_tushir.sys, "stdout", Konsolli())
    ishga_tushir.log("konsolga")

    assert any("konsolga" in x for x in Konsolli.yozilgan)

    assert not yol.exists()

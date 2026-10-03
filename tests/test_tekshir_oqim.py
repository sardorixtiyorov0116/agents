"""`/tekshir` bot oqimi — `bot/tekshir_oqim.py`.

Telegram yo'q: xabar va fayl soxta. Fayl «yuklab olinganda» tayyor
fayldan nusxa qilinadi. Qoidalar:

  * seans ochiq bo'lmasa fayl bu oqimga TEGISHLI EMAS (`/kp` ga o'tadi);
  * har fayl tanilib, nima ekani aytiladi; tanilmagani ochiq aytiladi;
  * KP va TZ bo'lmasa tekshiruv boshlanmaydi;
  * tekshiruvdan keyin seans yopiladi va fayllar O'CHIRILADI.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bot import tekshir_oqim

ETALON = Path(__file__).parent / "etalon_tz"
TG = 777


class SoxtaXabar:
    def __init__(self) -> None:
        self.matnlar: list[str] = []
        self.tugmalar: list[Any] = []

    async def reply_text(self, matn: str, reply_markup=None, **_: Any) -> None:
        self.matnlar.append(matn)
        self.tugmalar.append(reply_markup)

    @property
    def hammasi(self) -> str:
        return "\n".join(self.matnlar)


class SoxtaFayl:
    def __init__(self, manba: Path) -> None:
        self.manba = manba

    async def download_to_drive(self, yol: str) -> None:
        shutil.copy(self.manba, yol)


class SoxtaSoro:
    def __init__(self, data: str, xabar: SoxtaXabar) -> None:
        self.data = data
        self.message = xabar
        self.tahrirlar: list[str] = []

    async def edit_message_text(self, matn: str, **_: Any) -> None:
        self.tahrirlar.append(matn)


@pytest.fixture(autouse=True)
def papka(tmp_path, monkeypatch):
    monkeypatch.setattr(tekshir_oqim, "sozlama", lambda: SimpleNamespace(kp_papkasi=tmp_path))
    tekshir_oqim._seanslar.clear()
    yield tmp_path
    tekshir_oqim._seanslar.clear()


def _tz_xlsx(tmp_path: Path) -> Path:
    import openpyxl

    kitob = openpyxl.Workbook()
    v = kitob.active
    v.append(["№", "Наименование материалов", "Ед-изм", "Кол-во"])
    v.append([None, "Клпн ДКС", None, None])
    v.append([1, "Клпн 300x200", "шт", 59])
    yol = tmp_path / "manba_tz.xlsx"
    kitob.save(yol)
    return yol


async def test_seanssiz_fayl_bu_oqimga_tegishli_emas(tmp_path):
    xabar = SoxtaXabar()
    assert await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(_tz_xlsx(tmp_path)), "tz.xlsx") is False
    assert xabar.matnlar == []


async def test_boshlash_yoriqnoma_va_tugmalar():
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    assert tekshir_oqim.faolmi(TG)
    assert "KP" in xabar.matnlar[0] and "TZ" in xabar.matnlar[0]
    assert xabar.tugmalar[0] is not None


async def test_KP_siz_tekshiruv_boshlanmaydi(tmp_path):
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    assert await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(_tz_xlsx(tmp_path)), "tz.xlsx")
    assert "TZ (Excel): 1 qator" in xabar.matnlar[-1]
    await tekshir_oqim.ishga_tushir(xabar, TG)
    assert "KP (PDF)" in xabar.matnlar[-1]
    assert tekshir_oqim.faolmi(TG)          # seans yopilmadi — fayl kutilmoqda


async def test_tanilmagan_fayl_ochiq_aytiladi(tmp_path):
    rasm = tmp_path / "skrinshot.png"
    rasm.write_bytes(b"\x89PNG")
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(rasm), "skrinshot.png")
    assert "o'qilmaydi" in xabar.matnlar[-1]
    assert tekshir_oqim._seanslar[TG].tz == []


async def test_katta_fayl_yuklab_olinmaydi():
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    await tekshir_oqim.hujjat(xabar, TG, None, "katta.pdf", tekshir_oqim.MAKS_HAJM + 1)
    assert "MB" in xabar.matnlar[-1]


async def test_bekor_tugmasi_va_buyrugi(papka):
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    seans_papkasi = tekshir_oqim._seanslar[TG].papka
    soro = SoxtaSoro(tekshir_oqim.TUGMA_BEKOR, xabar)
    await tekshir_oqim.tugma(soro, TG)
    assert not tekshir_oqim.faolmi(TG)
    assert not seans_papkasi.exists()
    assert await tekshir_oqim.bekor(xabar, TG) is False   # yopiq seans — boshqasiga


async def test_eskirgan_seans_yopiladi(monkeypatch):
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    tekshir_oqim._seanslar[TG].boshlangan -= tekshir_oqim.MUDDAT_SONIYA + 1
    assert not tekshir_oqim.faolmi(TG)


def test_uzun_hisobot_bolinadi():
    matn = "\n".join(f"  • farq {i} " + "x" * 80 for i in range(200))
    bolaklar = tekshir_oqim._bolaklar(matn)
    assert len(bolaklar) > 1
    assert all(len(b) <= tekshir_oqim.TELEGRAM_CHEGARA + 100 for b in bolaklar)
    assert "".join(bolaklar).count("farq") == 200


@pytest.mark.skipif(not ETALON.is_dir(), reason="tests/etalon_tz/ yo'q")
async def test_etalon_nirvana_tolik_oqim():
    """Haqiqiy KP + TZ: tanish, tekshirish, natija, fayllar o'chirilgan."""
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    seans_papkasi = tekshir_oqim._seanslar[TG].papka
    await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(ETALON / "6-nirvana" / "kp.pdf"), "kp.pdf")
    assert "KP №13357/8" in xabar.matnlar[-1]
    await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(ETALON / "6-nirvana" / "tz_qolda.xlsx"), "tz.xlsx")
    assert "TZ fayllari: 1" in xabar.matnlar[-1]

    await tekshir_oqim.tugma(SoxtaSoro(tekshir_oqim.TUGMA_TEKSHIR, xabar), TG)
    assert "150х150" in xabar.hammasi and "300х300" in xabar.hammasi
    assert not tekshir_oqim.faolmi(TG)
    assert not seans_papkasi.exists()


@pytest.mark.skipif(not ETALON.is_dir(), reason="tests/etalon_tz/ yo'q")
async def test_etalon_ventas_papkasi():
    xabar = SoxtaXabar()
    await tekshir_oqim.boshla(xabar, TG)
    papka = ETALON / "7-provik-ventas"
    await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(papka / "kp.pdf"), "kp.pdf")
    for pdf in sorted((papka / "tz").glob("*.pdf")):
        await tekshir_oqim.hujjat(xabar, TG, SoxtaFayl(pdf), pdf.name)
    assert "TZ fayllari: 23" in xabar.matnlar[-1]
    # Yana /tekshir — fayllar bor, darhol tekshiradi.
    await tekshir_oqim.boshla(xabar, TG)
    assert "HEF-01" in xabar.hammasi and "H14" in xabar.hammasi

"""Rasm / skan TZ — `kp/tz_rasm.py` va `/kp` dagi rasm yo'li.

Model SOXTA (tarmoqqa chiqilmaydi). Qoidalar:
  * model faqat jadvalni KO'CHIRADI — nomga aylantirish kodda;
  * miqdori o'qilmagan qator olinmaydi va bu aytiladi;
  * «rasmdan o'qildi — tekshiring» har doim aytiladi;
  * rasm faqat Gemini ga yuboriladi (Groq rasm qabul qilmaydi);
  * matnli PDF rasm deb hisoblanmaydi.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kp.tz_qoralama import qatorlardan_taklif
from kp.tz_rasm import RasmXatosi, rasm_modellari, rasmdan_qatorlar, rasmlar
from tests.soxta import SoxtaLlm, json_javob

ETALON = Path(__file__).parent / "etalon_tz"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture
def rasm(tmp_path) -> Path:
    yol = tmp_path / "tz.png"
    yol.write_bytes(PNG)
    return yol


def _nirvana_javobi():
    return json_javob({"qatorlar": [
        {"guruh": "Клпн огназадернивиший", "nomi": "Клпн 1000x400", "birlik": "шт", "miqdor": 2},
        {"guruh": "Решетка АДН", "nomi": "Решетка 300x150", "birlik": "шт", "miqdor": 57},
        {"guruh": "Решетка АДН", "nomi": "Решетка 200x150", "birlik": "шт", "miqdor": 0},
    ], "izoh": ""})


async def test_model_jadvalni_kochiradi_kod_aylantiradi(rasm):
    llm = SoxtaLlm([_nirvana_javobi()])
    qatorlar, ogoh = await rasmdan_qatorlar(rasm, llm)

    # Rasm modelga BORDI (base64 blok).
    blok = llm.chaqiruvlar[0]["messages"][0]["content"][0]
    assert blok["type"] == "image" and blok["source"]["media_type"] == "image/png"
    # Miqdori o'qilmagan qator olinmadi va aytildi.
    assert [(q.nomi, q.miqdor) for q in qatorlar] == [("Клпн 1000x400", 2), ("Решетка 300x150", 57)]
    assert any("miqdori o'qilmadi" in o for o in ogoh)
    assert "RASMDAN" in ogoh[0]

    taklif = qatorlardan_taklif(qatorlar, ogoh, "Rasm")
    nomlar = [m["nomi"] for m in taklif.javoblar["mahsulotlar"]]
    assert nomlar[0].startswith("Клапан противопожарный КПУ-НО-Н-EI90-1000х400")
    assert "РВР-2 300х150" in nomlar[1]


def test_faqat_gemini_rasm_oladi():
    assert rasm_modellari(["gemini-3.5-flash", "groq/gpt-oss-120b", "gemini-flash-lite"]) == [
        "gemini-3.5-flash", "gemini-flash-lite"]


def test_matnli_PDF_rasm_emas(tmp_path):
    from reportlab.pdfgen import canvas

    yol = tmp_path / "matn.pdf"
    c = canvas.Canvas(str(yol))
    c.drawString(100, 750, "Kol-vo 5")
    c.save()
    assert rasmlar(yol) == []


def test_boshqa_format_rasm_emas(tmp_path):
    yol = tmp_path / "tz.docx"
    yol.write_bytes(b"x")
    assert rasmlar(yol) == []


async def test_rasm_yoq_bolsa_xato(tmp_path):
    yol = tmp_path / "bosh.txt"
    yol.write_text("x")
    with pytest.raises(RasmXatosi):
        await rasmdan_qatorlar(yol, SoxtaLlm([]))


@pytest.mark.skipif(not ETALON.is_dir(), reason="tests/etalon_tz/ yo'q")
def test_etalon_skrinshot_rasm_sifatida_olinadi():
    assert len(rasmlar(ETALON / "6-nirvana" / "tz_skrinshot.png")) == 1


# --- /kp oqimi -----------------------------------------------------------------


class _Xabar:
    def __init__(self):
        self.matnlar: list[str] = []

    async def reply_text(self, matn, reply_markup=None, **_):
        self.matnlar.append(matn)


class _Fayl:
    def __init__(self, baytlar: bytes):
        self.baytlar = baytlar

    async def download_to_drive(self, yol):
        Path(yol).write_bytes(self.baytlar)


async def test_kp_oqimi_rasm_TZ(tmp_path, monkeypatch):
    from app.baza import Baza
    from bot import kp_oqim

    async def soxta(yol):
        return await rasmdan_qatorlar(yol, SoxtaLlm([_nirvana_javobi()]))

    monkeypatch.setattr(kp_oqim, "_rasm_ajrat", soxta)
    baza = Baza(tmp_path / "b.db")
    await baza.tayyorla()
    xabar = _Xabar()
    await kp_oqim.boshla(baza, xabar, 5151)
    assert await kp_oqim.hujjat(baza, xabar, 5151, _Fayl(PNG), "rasm.jpg")

    javoblar = (await baza.kp_shakli(5151))["javoblar"]
    assert javoblar["yol"] == "model"
    assert [m["miqdor"] for m in javoblar["mahsulotlar"]] == [2, 57]
    assert any("Rasm: 2 qator" in m for m in xabar.matnlar)


async def test_kp_oqimi_Gemini_yoq_bolsa_ochiq_aytadi(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.baza import Baza
    from bot import kp_oqim

    monkeypatch.setattr(kp_oqim, "sozlama", lambda: SimpleNamespace(
        tez_modellar=["groq/gpt-oss-120b"], kp_papkasi=tmp_path))
    baza = Baza(tmp_path / "b.db")
    await baza.tayyorla()
    xabar = _Xabar()
    await kp_oqim.boshla(baza, xabar, 5252)
    await kp_oqim.hujjat(baza, xabar, 5252, _Fayl(PNG), "rasm.png")
    assert any("Gemini" in m for m in xabar.matnlar)

"""DWG chizma — `kp/dwg.py`.

Qoidalar:
  * buzilgan kirill («РђРњРќ») tiklanadi, to'g'ri matnga tegilmaydi;
  * uskuna turi bo'yicha YOZUVLAR soni (dona emas) sanaladi, shovqin
    («по адресу», «ЗАПРОЕКТИРОВАННОГО», «Конструкции металлические») turga
    tushmaydi;
  * KP bilan faqat TUR darajasida: chizmada bor, KP da butunlay yo'q;
  * dastur yo'q bo'lsa — ochiq xato.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kp.dwg import (
    DwgXatosi,
    _tikla,
    _tozala,
    dastur_yoli,
    dwg_yozuvlari,
    dxf_yozuvlari,
    kp_bilan_farqlar,
    xulosa,
)
from kp.kp_pdf import KpHujjat, KpQator

ETALON = Path(__file__).parent / "etalon_tz"


def test_buzilgan_kirill_tiklanadi():
    buzuq = "АМН150х100".encode("utf-8").decode("cp1251")
    assert buzuq != "АМН150х100"
    assert _tikla(buzuq) == "АМН150х100"
    assert _tikla("КЦКП-3,15") == "КЦКП-3,15"          # to'g'ri matn o'zgarmaydi
    assert _tikla("EF-08.01") == "EF-08.01"


def test_mtext_formatlash_belgilari_tozalanadi():
    bs = chr(92)
    assert _tozala(f"Мульти сплит {bs}c0;AM3-H27 {bs}PнаружныйLEADER_LINE") == \
        "Мульти сплит AM3-H27 наружный"


def test_dxf_yozuvlari(tmp_path):
    dxf = tmp_path / "c.dxf"
    dxf.write_text("\n".join([
        "0", "SECTION", "2", "ENTITIES",
        "0", "TEXT", "8", "0", "1", "EF-08.01",
        "0", "MTEXT", "8", "0", "3", "КПД-4-01-", "1", "600х500",
        "0", "LINE", "8", "0",
        "0", "ENDSEC", "0", "EOF",
    ]), encoding="utf-8")
    assert dxf_yozuvlari(dxf) == ["EF-08.01", "КПД-4-01-600х500"]


def test_xulosa_turlar_va_shovqin():
    x = xulosa([
        "EF-08.01", "HEF-01", "AHU-05 Cooling Coil", "KTVA72HQAN1", "KTRV615HZAN3-B",
        "DJR103E", "КПД-4-01-600х500-2*ф",
        # shovqin — hech qaysi turga tushmasligi kerak:
        "3-я и 4-я очередь, расположенное по адресу", "ЗАПРОЕКТИРОВАННОГО ЗДАНИЯ",
        "Конструкции металлические. Каркас здания", "A1088 COMPACTOR",
    ])
    assert dict(x.yozuvlar) == {"vent_sanoat": 2, "kckp": 1, "vrf_ichki": 1,
                                "vrf_tashqi": 1, "refnet": 1, "kpd": 1}


def _kp(*nomlar: str) -> KpHujjat:
    h = KpHujjat(yol="x")
    for i, n in enumerate(nomlar, 1):
        h.qatorlar.append(KpQator(raqam=i, nomi=n, miqdor=1, narx=1, summa=1))
    return h


def test_KP_da_yoq_turlar():
    x = xulosa(["EF-08.01"] * 5 + ["AHU-01"] * 5 + ["DJR101E"] * 4)
    farqlar = kp_bilan_farqlar(x, _kp("Кондиционер КЦКП-31,5 L=31750м3/ч"))
    matnlar = " | ".join(f.matn for f in farqlar)
    assert "ventilyatori: 5 yozuv" in matnlar           # KP da ventilyator yo'q
    assert "refnet" in matnlar
    assert "КЦКП" not in matnlar and "Markaziy" not in matnlar   # KP da bor


def test_VRF_bloki_bor_KP_da_refnet_shu_tizimniki():
    x = xulosa(["KTVA72HQAN1"] * 5)
    assert kp_bilan_farqlar(x, _kp("Внутренний блок кассетного типа VRF JVI-071C")) == []


def test_dastur_yoq_bolsa_ochiq_xato(tmp_path, monkeypatch):
    import kp.dwg as modul

    monkeypatch.setattr(modul, "dastur_yoli", lambda: None)
    with pytest.raises(DwgXatosi, match="LibreDWG"):
        dwg_yozuvlari(tmp_path / "x.dwg")


@pytest.mark.skipif(not (ETALON / "7-provik-ventas" / "chizma_pid.dwg").is_file()
                    or dastur_yoli() is None, reason="etalon chizma yoki LibreDWG yo'q")
async def test_kp_oqimi_DWG_royxat_beradi_qoralama_yasamaydi(tmp_path):
    from app.baza import Baza
    from bot import kp_oqim

    class Xabar:
        def __init__(self):
            self.matnlar = []

        async def reply_text(self, matn, reply_markup=None, **_):
            self.matnlar.append(matn)

    class Fayl:
        async def download_to_drive(self, yol):
            Path(yol).write_bytes((ETALON / "7-provik-ventas" / "chizma_pid.dwg").read_bytes())

    baza = Baza(tmp_path / "b.db")
    await baza.tayyorla()
    xabar = Xabar()
    await kp_oqim.boshla(baza, xabar, 6161)
    oldin = dict((await baza.kp_shakli(6161))["javoblar"])
    assert await kp_oqim.hujjat(baza, xabar, 6161, Fayl(), "pid.dwg")
    assert any("YOZUVLAR SONI" in m and "HEF-01" in m for m in xabar.matnlar)
    assert (await baza.kp_shakli(6161))["javoblar"] == oldin     # shaklga tegilmadi


@pytest.mark.skipif(not (ETALON / "7-provik-ventas" / "chizma_pid.dwg").is_file()
                    or dastur_yoli() is None, reason="etalon chizma yoki LibreDWG yo'q")
def test_etalon_PID_chizmasi_ventilyatorlar_KP_da_yoq():
    """7-juft: P&ID da 34 ta EF/HEF ventilyator, KP-13574 da ventilyator yo'q."""
    from kp.solishtir import fayllarni_tekshir

    papka = ETALON / "7-provik-ventas"
    natija, _ = fayllarni_tekshir(papka / "kp.pdf", [papka / "chizma_pid.dwg"])
    matnlar = [f.matn for f in natija.farqlar]
    assert any("ventilyatori" in m and "HEF-01" in m for m in matnlar)

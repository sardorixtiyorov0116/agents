"""Katalog salomatligi — Nodiraning avtonom ko'zi.

Bu SANOQ, tahlil emas: LLM chaqirilmaydi va katalog o'zgartirilmaydi.
Shuning uchun testlar aynan sanoqni tekshiradi — noto'g'ri son
menejerni noto'g'ri joyga yuboradi.

Tarmoqqa CHIQILMAYDI.
"""

from __future__ import annotations

from app.katalog_salomatligi import bosma_katalogdan_yoq, hisobla, matn


def _mahsulot(nomi, variantlar):
    return {"name_uz": nomi, "characters": variantlar}


def test_narxsiz_variantlar_sanaladi():
    """O'LCHANGAN muammo: 342 variantdan 21 tasida narx bor."""
    olchov = hisobla([
        _mahsulot("A", [{"price": 100}, {"price": 0}]),
        _mahsulot("B", [{"price": 0}, {"price": None}]),
    ])

    assert olchov["variant"] == 4
    assert olchov["narxli"] == 1
    assert olchov["narxsiz"] == 3


def test_BUTUNLAY_narxsiz_mahsulot_alohida_korsatiladi():
    """Bitta varianti narxli bo'lsa — mahsulot "narxsiz" emas.

    Menejerga qaysi MAHSULOTNI ochish kerakligi aytiladi, qaysi
    variantni emas: u katalogda mahsulot bo'yicha ishlaydi.
    """
    olchov = hisobla([
        _mahsulot("Yarim", [{"price": 100}, {"price": 0}]),
        _mahsulot("Butunlay", [{"price": 0}, {"price": 0}]),
    ])

    assert olchov["butunlay_narxsiz_mahsulotlar"] == ["Butunlay"]


def test_texnik_korsatkichsiz_variantlar_sanaladi():
    """Rustam ventilyatorni HAVO SARFIGA qarab tanlaydi.

    Bu maydonsiz hisob natijasi uskunaga bog'lanmaydi.
    """
    olchov = hisobla([
        _mahsulot("A", [
            {"price": 1, "airflow_m3h": 1200},
            {"price": 1, "pressure_pa": 300},
            {"price": 1},
        ]),
    ])

    assert olchov["texnikasiz"] == 1


def test_variantsiz_mahsulot_sanoqni_buzmaydi():
    olchov = hisobla([
        {"name_uz": "Bo'sh", "characters": []},
        {"name_uz": "Maydonsiz"},
    ])

    assert olchov["variant"] == 0
    assert olchov["butunlay_narxsiz_mahsulotlar"] == []


def test_bosh_katalogda_ochiq_aytiladi():
    """Nol variant "hammasi joyida" degani EMAS."""
    xabar = matn(hisobla([]), [])
    assert "API bo'sh qaytardi" in xabar


def test_xabarda_narx_foizi_va_yol_korsatiladi():
    xabar = matn(hisobla([_mahsulot("A", [{"price": 100}, {"price": 0}])]), [])

    assert "50%" in xabar
    assert "/katalog" in xabar


def test_bosma_katalog_royxati_yoq_bolsa_YIQILMAYDI(monkeypatch, tmp_path):
    """Fayl bo'lmasa hisobot baribir chiqsin — faqat shu bo'lim tushsin."""
    import app.katalog_salomatligi as modul

    monkeypatch.setattr(modul, "OILALAR_FAYLI", tmp_path / "yoq.json")

    assert bosma_katalogdan_yoq([{"name_uz": "A"}]) == []

"""Bosma katalogni Obsidianga ko'chirish.

Eng muhim talab: MATN O'ZGARTIRILMAYDI. Katalogdagi raqam — mijozga
ketadigan raqam; uni qayta yozish yoki "tozalash" xato KP demakdir.
Shuning uchun bu yerda faqat KESIB TASHLASH tekshiriladi (takrorlanuvchi
navigatsiya va sahifa raqami), qolgani o'zgarishsiz o'tishi shart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bilim.katalog_pdf import (
    MUNDARIJA,
    SILJISH,
    nav_tozala,
    yozuvlar_yasa,
)

# Haqiqiy sahifa boshi (96-sahifa, ВЦ 4-75). Navigatsiya ICHIDA bo'sh
# qator bor — aynan shu bitta bo'shliq oldingi versiyani chalg'itgan edi.
XOM_SAHIFA = """Кондиционер Холодильное
оборудование
Отопительное
оборудование оборудование
Теплообменное Канальное
оборудование Вентиляторы Аспирационное
оборудование Клапаны Решетки
вентиляционные Шумоглушители Вентиляционные
изделия Фильтры

Комплектующие
Вентилятор центробежный ВЦ 4-75
94
Назначение
   Вентилятор ВЦ 4-75 радиальный, низкого давления."""


def test_navigatsiya_toliq_olib_tashlanadi():
    """Navigatsiya 260 marta takrorlanadi — indeksga sof shovqin."""
    natija = nav_tozala(XOM_SAHIFA, 94)

    assert natija.startswith("Вентилятор центробежный ВЦ 4-75")
    for soz in ("Кондиционер", "Комплектующие", "Шумоглушители"):
        assert soz not in natija


def test_sahifa_raqami_sarlavhadan_keyin_ham_topiladi():
    """PDF da raqam sarlavhadan KEYIN turadi — oddiy tekshiruv o'tkazib yuborardi."""
    assert "\n94\n" not in nav_tozala(XOM_SAHIFA, 94)


def test_mazmun_ozgarmaydi():
    natija = nav_tozala(XOM_SAHIFA, 94)

    assert "Вентилятор ВЦ 4-75 радиальный, низкого давления." in natija


def test_navigatsiya_sarlavhadan_keyin_ham_topiladi():
    """ВР 12-26 sahifasida navigatsiya matn O'RTASIDA turadi.

    Faqat sahifa boshini tekshirsak, u indeksga tushib qolardi va
    qidiruvda "Шумоглушители" so'zi ventilyator yozuvidan chiqardi.
    """
    matn = (
        "Вентилятор ВР 12-26\n"
        "Кондиционер оборудование Холодильное\n"
        "Отопительное Теплообменное\n"
        "Канальное Вентиляторы Аспирационное\n"
        "оборудование Клапаны Шумоглушители\n"
        "Назначение\n"
        "   Вентилятор высокого давления."
    )

    natija = nav_tozala(matn, 116)

    assert natija.startswith("Вентилятор ВР 12-26")
    assert "Шумоглушители" not in natija
    assert "Вентилятор высокого давления." in natija


def test_bitta_qatorga_sigib_ketgan_navigatsiya_ham_olinadi():
    """СИОТ sahifasida butun navigatsiya bitta qatorda chiqqan."""
    matn = (
        "СИОТ 5.907-2\n"
        "Кондиционер Холодильное оборудование Отопительное оборудование "
        "Теплообменное Канальное Вентиляторы Клапаны\n"
        "Назначение\n"
        "   Пылеуловитель СИОТ."
    )

    natija = nav_tozala(matn, 201)

    assert "Холодильное" not in natija
    assert "Пылеуловитель СИОТ." in natija


def test_yopishib_qolgan_sozlar_ham_tanilади():
    """PDF eksporti so'zlarni yopishtirib yuboradi: "ШумоглушителиВентиляционные"."""
    matn = (
        "ВКПП\n"
        "Клапаны вентиляционные\n"
        "Решетки ШумоглушителиВентиляционные\n"
        "изделия Фильтры Комплектующие\n"
        "Назначение\n"
        "   Канальный вентилятор."
    )

    natija = nav_tozala(matn, 62)

    assert "Шумоглушители" not in natija
    assert "Канальный вентилятор." in natija


def test_bolim_nomini_ozida_saqlagan_soz_ochirilmaydi():
    """"Переоборудование" ichida "оборудование" bor, lekin bu nav emas."""
    matn = "Переоборудование цеха\nМодель ВЦ 4-75"

    assert nav_tozala(matn, 94) == matn


def test_yolgiz_bolim_nomi_ochirilmaydi():
    """Bitta "Вентиляторы" — bo'lim sarlavhasi bo'lishi mumkin."""
    matn = "Вентиляторы\nМодель ВЦ 4-75\nМасса 120 кг"

    assert nav_tozala(matn, 94) == matn


def test_navigatsiyasiz_sahifa_buzilmaydi():
    """Ba'zi sahifalarda navigatsiya yo'q — matn butun qolishi kerak."""
    matn = "Содержание\nКондиционеры\nКЦКП\n15"

    assert nav_tozala(matn, 3) == matn


def test_raqamga_oxshash_jadval_qiymati_saqlanadi():
    """Chuqurroqdagi yolg'iz raqam — jadval qiymati, sahifa raqami emas."""
    matn = "Модель\nВЦ 4-75-8\nМасса, кг\n94\n120"

    assert nav_tozala(matn, 94).endswith("94\n120")


# --- mundarija butunligi ------------------------------------------------------


def test_mundarija_sahifalari_osib_boradi():
    """Tartib buzilsa, oila boshqa oilaning sahifalarini o'zlashtirib oladi."""
    raqamlar = [o.bosma for b in MUNDARIJA for o in b.oilalar]

    assert raqamlar == sorted(raqamlar), "mundarija sahifa tartibi buzilgan"


def test_model_kodlari_takrorlanmaydi():
    """Bir xil kod — bir xil fayl nomi — biri ikkinchisini o'chirib yuboradi."""
    kodlar = [o.kod for b in MUNDARIJA for o in b.oilalar]

    assert len(kodlar) == len(set(kodlar))


# --- yozuv yasash -------------------------------------------------------------


@pytest.fixture
def sahifalar() -> list[str]:
    """260 ta soxta sahifa: har birida o'z raqami yozilgan."""
    return [f"Кондиционер\n{i - SILJISH}\nMazmun {i}" for i in range(1, 261)]


def test_har_oila_uchun_fayl_yoziladi(sahifalar, tmp_path: Path):
    yozilgan = yozuvlar_yasa(sahifalar, tmp_path)

    oilalar = sum(len(b.oilalar) for b in MUNDARIJA)
    assert len(yozilgan) == oilalar + 1     # + indeks
    assert (tmp_path / "Katalog 2021 — indeks.md").is_file()


def test_yozuvda_manba_korsatiladi(sahifalar, tmp_path: Path):
    """Menejer raqamni asl katalog bilan solishtira olishi kerak."""
    yozuvlar_yasa(sahifalar, tmp_path)
    matn = (tmp_path / "ВЦ 4-75 — markazdan qochma ventilyator.md").read_text(
        encoding="utf-8"
    )

    assert "JIHOZVENT katalogi 2021" in matn
    assert "Bosma sahifa 94" in matn
    assert "model_kodi: ВЦ 4-75" in matn


def test_oilalar_sahifalarni_bolishib_oladi(sahifalar, tmp_path: Path):
    """ВЦ 4-75 (94) keyingi oila (95) sahifasini o'zlashtirmasligi kerak."""
    yozuvlar_yasa(sahifalar, tmp_path)
    matn = (tmp_path / "ВЦ 4-75 — markazdan qochma ventilyator.md").read_text(
        encoding="utf-8"
    )

    assert "Bosma sahifa 94" in matn
    assert "Bosma sahifa 95" not in matn


def test_indeks_hamma_oilaga_havola_beradi(sahifalar, tmp_path: Path):
    yozuvlar_yasa(sahifalar, tmp_path)
    indeks = (tmp_path / "Katalog 2021 — indeks.md").read_text(encoding="utf-8")

    for bolim in MUNDARIJA:
        assert f"## {bolim.nomi}" in indeks
        for oila in bolim.oilalar:
            assert f"|{oila.kod}]]" in indeks


def test_bosh_sahifalar_yozuvga_tushmaydi(tmp_path: Path):
    """Matnsiz sahifa "### Bosma sahifa N" degan bo'sh sarlavha qoldirmasin."""
    sahifalar = ["" for _ in range(260)]

    yozilgan = yozuvlar_yasa(sahifalar, tmp_path)

    assert len(yozilgan) == 1               # faqat indeks

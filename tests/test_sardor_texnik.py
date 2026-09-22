"""Sardor mahsulotni RAQAM bo'yicha tanlaydi, nom o'xshashligi bo'yicha emas.

Jonli xato (2026-08-17): "12000 m³/soat kerak" so'roviga nomzodlar faqat
so'z o'xshashligi bilan tanlanardi. Promptga tushgan 149 ta modeldan atigi
18 tasida texnik raqam bor edi — qolganini model NOMIGA qarab taxmin
qilardi. Oqibati uch xil:

  1. sekin  — 30 s (model taxmin qilishga urinadi);
  2. beqaror — bir xil so'rov, ikki xil mahsulot ro'yxati;
  3. past effortda umuman javob topolmasdi (0 variant).

Endi sarfi yetadigan modeli bor mahsulotlar birinchi turadi va raqamlar
promptga yoziladi.
"""

from __future__ import annotations

import pytest

from app.agentlar.mahsulot_mutaxassisi import (
    MAKS_VARIANT,
    MahsulotMutaxassisi,
    _eng_kop_sarf,
    _oraliq_matni,
    talab_sarfi,
)

# --- talab raqamini o'qish ----------------------------------------------------


@pytest.mark.parametrize("matn,kutilgan", [
    ("12000 m3/soat havo sarfi kerak", 12000.0),
    ("12 000 м³/ч kerak", 12000.0),
    ("8000 m3/h", 8000.0),
    ("1 500 m³/soat", 1500.0),
    ("4050 m³/soatda", 4050.0),
    # Mingliklar ajratgichi — kasr emas.
    ("12.000 m3/soat", 12000.0),
    ("12,000 m3/soat", 12000.0),
])
def test_talab_sarfi_oqiladi(matn, kutilgan):
    assert talab_sarfi(matn) == kutilgan


@pytest.mark.parametrize("matn", [
    "shift balandligi 3 m",
    "250 m2 restoran",
    "kanal diametri 900 mm",
    "",
])
def test_sarf_talabi_yoq_bolsa_none(matn):
    """Boshqa o'lchov sarf deb o'qilmasligi kerak — aks holda filtr yolg'on."""
    assert talab_sarfi(matn) is None


# --- katalog raqamlarini o'qish ----------------------------------------------


@pytest.mark.parametrize("parametr,kutilgan", [
    ({"havo_sarfi": [3040, 12900]}, 12900.0),
    ({"havo_sarfi": 5000.0}, 5000.0),
    ({"havo_sarfi": None}, None),
    ({}, None),
    (None, None),
])
def test_eng_kop_sarf(parametr, kutilgan):
    assert _eng_kop_sarf(parametr) == kutilgan


@pytest.mark.parametrize("qiymat,kutilgan", [
    ([3040, 12900], "3040–12900 m³/soat"),
    ([5000, 5000], "5000 m³/soat"),
    (1600.0, "1600 m³/soat"),
    (None, ""),
    ([], ""),
])
def test_oraliq_matni(qiymat, kutilgan):
    assert _oraliq_matni(qiymat, "m³/soat") == kutilgan


# --- modellarni saralash ------------------------------------------------------


PARAMETRLAR = {
    "KATTA": {"havo_sarfi": [8000, 15300], "bosim": [430, 550]},
    "ORTA": {"havo_sarfi": [5000, 13000]},
    "KICHIK": {"havo_sarfi": [500, 1200]},
    # Raqami yo'q model — katalogda ma'lumot kiritilmagan.
}


def test_sarfi_yetmaydigan_model_promptga_tushmaydi():
    """Model uni ko'rmasa, uni taklif qila olmaydi ham."""
    modellar, tashlandi = MahsulotMutaxassisi._modellarni_tanla(
        ["KATTA", "KICHIK", "ORTA"], PARAMETRLAR, kerakli_sarf=12000,
    )

    assert tashlandi == 1
    assert not any(m.startswith("KICHIK") for m in modellar)


def test_zaxirasi_kichigi_oldinda_turadi():
    """12000 kerak bo'lsa, 63000 lik qurilma birinchi turmasligi kerak."""
    modellar, _ = MahsulotMutaxassisi._modellarni_tanla(
        ["KATTA", "ORTA"], PARAMETRLAR, kerakli_sarf=12000,
    )

    assert modellar[0].startswith("ORTA")   # 13000 — zaxira 1000
    assert modellar[1].startswith("KATTA")  # 15300 — zaxira 3300


def test_raqami_yoq_model_tashlanmaydi():
    """Ma'lumot yo'qligi "yaramaydi" degani emas (Rustamdagi qoida)."""
    modellar, tashlandi = MahsulotMutaxassisi._modellarni_tanla(
        ["KATTA", "NOMALUM"], PARAMETRLAR, kerakli_sarf=12000,
    )

    assert tashlandi == 0
    assert any(m == "NOMALUM" for m in modellar)


def test_raqamlar_model_nomi_yoniga_yoziladi():
    """Model taxmin qilmasligi uchun raqam ko'rinib turishi kerak."""
    modellar, _ = MahsulotMutaxassisi._modellarni_tanla(
        ["KATTA"], PARAMETRLAR, kerakli_sarf=12000,
    )

    assert modellar[0] == "KATTA [8000–15300 m³/soat, 430–550 Pa]"


def test_talab_yoq_bolsa_hech_narsa_tashlanmaydi():
    modellar, tashlandi = MahsulotMutaxassisi._modellarni_tanla(
        ["KATTA", "KICHIK"], PARAMETRLAR, kerakli_sarf=None,
    )

    assert tashlandi == 0
    assert len(modellar) == 2


# --- nomzodlarni saralash -----------------------------------------------------


def _mahsulot(id_, nomi, modellar):
    return {"id": id_, "name": nomi, "models": [{"name": m} for m in modellar]}


def test_texnik_moslik_soz_oxshashligidan_ustun():
    """Nomi mos, lekin sarfi yetmaydigan mahsulot birinchi turmasligi kerak.

    Aynan shu xato edi: "Kanalli ventilyator VKPP" nomi so'rovga o'xshagani
    uchun ro'yxat boshida turardi, sarfi esa 10 barobar kam edi.
    """
    katalog = [
        # Nomi so'rovga to'liq mos, lekin sarfi yetmaydi.
        _mahsulot(1, "Kanalli ventilyator", ["KICHIK"]),
        # Nomi mos emas, lekin sarfi yetadi.
        _mahsulot(2, "Markaziy qurilma", ["KATTA"]),
    ]

    saralangan = MahsulotMutaxassisi._saralab(
        katalog, "kanalli ventilyator kerak", set(), PARAMETRLAR, 12000,
    )

    assert saralangan[0]["id"] == 2, "sarfi yetadigan mahsulot boshida turmadi"


def test_talab_yoq_bolsa_eski_tartib_saqlanadi():
    """Sarf aytilmagan so'rovda saralash o'zgarmasligi kerak."""
    katalog = [
        _mahsulot(1, "Kanalli ventilyator", ["KICHIK"]),
        _mahsulot(2, "Markaziy qurilma", ["KATTA"]),
    ]

    saralangan = MahsulotMutaxassisi._saralab(
        katalog, "kanalli ventilyator kerak", set(), PARAMETRLAR, None,
    )

    assert saralangan[0]["id"] == 1


# --- prompt matni -------------------------------------------------------------


def test_promptda_talab_va_qoida_bor():
    sardor = MahsulotMutaxassisi.__new__(MahsulotMutaxassisi)
    katalog = [_mahsulot(1, "Ventilyator", ["KATTA", "KICHIK"])]

    matn = sardor._nomzod_matni(katalog, PARAMETRLAR, 12000)

    assert "Talab: 12000 m³/soat" in matn
    assert "8000–15300 m³/soat" in matn        # raqam ko'rinadi
    assert "KICHIK" not in matn                # yetmaydigani yo'q
    assert "1 ta model sarfi yetmagani" in matn  # nechtasi tashlangani aytiladi


def test_hamma_model_yetmasa_ochiq_aytiladi():
    """"modellar: (kiritilmagan)" degan yolg'on chiqmasligi kerak."""
    sardor = MahsulotMutaxassisi.__new__(MahsulotMutaxassisi)
    katalog = [_mahsulot(1, "Kichik ventilyator", ["KICHIK"])]

    matn = sardor._nomzod_matni(katalog, PARAMETRLAR, 12000)

    assert "sarfi yetmaydi" in matn
    assert "kiritilmagan" not in matn


# --- zanjirdagi hisobdan sarfni olish ----------------------------------------


def _sardor(kontekst):
    sardor = MahsulotMutaxassisi.__new__(MahsulotMutaxassisi)
    sardor._kontekst = kontekst
    return sardor


def test_sarf_muhandis_hisobidan_olinadi():
    """Zanjirda raqam RUSTAMDAN keladi, vazifa matnidan emas.

    Vazifa matnida "250 m² restoran" turadi — unda sarf raqami yo'q.
    Sarf faqat hisobda bo'ladi va uni matndan qidirish xato.
    """
    sardor = _sardor({
        "zanjir_natijalari": {"hvac-calc": {"jami_sarf": 12000.0}},
    })

    assert sardor._kerakli_sarf("250 m2 restoran uchun jihoz tanlab ber") == 12000.0


def test_eski_kalit_ham_ishlaydi():
    """`oldingi_natija` — bitta agent chaqirilganda ishlatiladigan kalit."""
    sardor = _sardor({"oldingi_natija": {"jami_sarf": 4050.0}})

    assert sardor._kerakli_sarf("kafe uchun") == 4050.0


def test_hisob_yoq_bolsa_matndan_oqiladi():
    """Sardor yolg'iz chaqirilsa raqam faqat so'rov matnida bo'ladi."""
    sardor = _sardor({})

    assert sardor._kerakli_sarf("8000 m3/soat kerak") == 8000.0


def test_hech_qayerda_raqam_yoq_bolsa_none():
    sardor = _sardor({})

    assert sardor._kerakli_sarf("kanal klapanini tanlab ber") is None


# --- qavsli izoh nomni buzmasligi kerak --------------------------------------


@pytest.mark.parametrize("xom,kutilgan", [
    ("ВК-250П [1200 m³/soat, 425 Pa]", "ВК-250П"),
    ("ВЦ 4-75-8-1 [8200–15300 m³/soat]", "ВЦ 4-75-8-1"),
    ("КЦКП-12,5", "КЦКП-12,5"),
    # Nom ICHIDAGI qavsga tegilmaydi — faqat oxiridagisi olinadi.
    ("ВЦ 4-75 (isp.1)", "ВЦ 4-75 (isp.1)"),
    ("", ""),
])
def test_qavsli_izoh_tozalanadi(xom, kutilgan):
    """Qavsni biz qo'shganmiz — nom u bilan qaytsa ham tanilishi kerak.

    Aks holda variant "katalogda yo'q" deb JIMGINA tashlanardi va
    menejer mos mahsulotni umuman ko'rmasdi.
    """
    from app.agentlar.mahsulot_mutaxassisi import model_nomini_tozala

    assert model_nomini_tozala(xom) == kutilgan


def test_variant_soni_promptda_cheklangan():
    """Kechikish chiqish tokeniga bog'liq — variant soni cheklanishi kerak."""
    from app.agentlar.mahsulot_mutaxassisi import TANLOV_PROMPT

    assert f"{MAKS_VARIANT} TA VARIANT" in TANLOV_PROMPT

"""Tashqi modelga ketadigan tender hujjatidan shaxsiy ma'lumot yashiriladi.

Jasur Gemini bepul tarifida ishlaydi — so'rovlar model o'qitishga
ketishi mumkin. Lekin summa va texnik raqamlar SAQLANISHI shart: baho
ular bilan qilinadi.
"""

from __future__ import annotations

import pytest

from integrations.maxfiy import yashir


@pytest.mark.parametrize("sir", [
    "+998 93 524 10 60",
    "(55) 510-12-17",
    "93 524 10 60",
    "tender_tash@bk.ru",
    "2021 4000 9047 3792 7001",
    "20210000805200277003",
])
def test_kontakt_va_hisob_raqam_yashiriladi(sir):
    assert sir not in yashir(f"Ma'lumot uchun: {sir}.")


@pytest.mark.parametrize("matn,sir", [
    ("INN: 206978481", "206978481"),
    ("STIR 200936561", "200936561"),
    ("MFO: 00224", "00224"),
    ("тел. 935241060", "935241060"),
])
def test_yorliqli_raqam_yashiriladi(matn, sir):
    natija = yashir(matn)
    assert sir not in natija
    assert "[yashirildi]" in natija


@pytest.mark.parametrize("ism,familiya", [
    ("M.M. Parpiyev", "Parpiyev"),
    ("Х.Мамарасулов", "Мамарасулов"),
    ("Z.G.Radjapov", "Radjapov"),
    ("Radjapov Z.G.", "Radjapov"),
    ("Abdurahmonov Baxtiyor Karabayevich", "Abdurahmonov"),
    ("Бектошев Худайназар Жуманазарович", "Бектошев"),
    ("Aliyev Vali Karim o'g'li", "Aliyev"),
])
def test_ism_yashiriladi(ism, familiya):
    natija = yashir(f"Bosh direktor: {ism}")
    assert familiya not in natija
    assert "[shaxs]" in natija


def test_summa_va_texnik_raqamlar_SAQLANADI():
    matn = (
        "Taxminiy baho 145 208 000 сум. Chiller 30–80 kW, ±1°C, "
        "380V / 50Hz / 3 faza, 72 kVA. Lot 26120012511261, muddat 2026-09-18. "
        "Model ARV6-H610/SR1MV. I. Malakaviy baholash mezonlari. "
        "205 dona | 420 000,00 | 86 100 000,00. Avans 15%, 30 ish kuni."
    )

    assert yashir(matn) == matn

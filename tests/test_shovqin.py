"""Shovqin pasaytirgich tanlash — `hisob/shovqin.py`.

NEGA BU HISOB BOR
-----------------
Katalogda shovqin pasaytirgich uchun `havo_sarfi` maydoni YO'Q — u
yerda SHOVQIN PASAYISHI (dB, chastota bo'yicha) jadvali turadi. Shu
sababli tizim uni sarf bo'yicha tanlay olmasdi va menejer «tanladim,
lekin KP ga chiqmadi» degan holatga tushardi.

Sig'imi esa model NOMIDA. Bosma katalog 2021, 82-sahifa:
«КГП 40-20/6, где 40-20 — присоединительные размеры фланца, см».
"""

from __future__ import annotations

import math

import pytest

from hisob.shovqin import KANAL_TEZLIGI, olchamdan_sigim, shovqin_tanla


def test_plastinali_olchami_SANTIMETRDA():
    """`КГП 50-30` = 500x300 mm = 0,15 m²."""
    natija = olchamdan_sigim("КГП 50-30 (6-10)")

    assert natija.yuza == pytest.approx(0.15)
    assert natija.sigim == pytest.approx(0.15 * 3600 * KANAL_TEZLIGI)


def test_dumaloq_olchami_MILLIMETRDA():
    """`КГТ 160-6` = Ø160 mm."""
    natija = olchamdan_sigim("КГТ 160-6")

    assert natija.yuza == pytest.approx(math.pi * 0.16 ** 2 / 4, abs=0.0001)


def test_eng_katta_plastinali():
    """`КГП 100-50` = 1000x500 mm — katalogdagi eng kattasi."""
    assert olchamdan_sigim("КГП 100-50 (6-10)").yuza == pytest.approx(0.5)


def test_notanish_nom_TAXMIN_QILINMAYDI():
    assert olchamdan_sigim("ВЦ 4-75-6,3-1") is None
    assert olchamdan_sigim("") is None


# --- tanlash ------------------------------------------------------------------

_NOMLAR = ["КГП 30-15 (6-10)", "КГП 50-25 (6-10)", "КГП 50-30 (6-10)",
           "КГП 80-50 (6-10)", "КГП 100-50 (6-10)"]


def test_sarfga_YETADIGAN_eng_kichigi():
    """Kattasi olinsa kanal kengaytiriladi va ortiqcha pul ketadi."""
    olcham, soni = shovqin_tanla(_NOMLAR, 2000)

    assert olcham.nomi == "КГП 50-25 (6-10)"      # 2925 m³/soat
    assert soni == 1


def test_kichigi_OLINMAYDI():
    """Kichigi olinsa tezlik oshib, shovqinning O'ZI ko'payadi.

    Ya'ni uskuna o'z vazifasiga qarshi ishlaydi.
    """
    olcham, soni = shovqin_tanla(_NOMLAR, 2000)

    assert olcham.sigim * soni >= 2000


def test_bittasi_yetmasa_PARALLEL_qoyiladi():
    """18 000 m³/soat ga eng katta (11 700) dan 2 dona.

    Katta tizim baribir bir necha tarmoqqa bo'linadi — bitta uskuna
    yetmasa, «yo'q» deb qator tashlab ketish menejerni qo'lda
    to'ldirishga majbur qilardi.
    """
    olcham, soni = shovqin_tanla(_NOMLAR, 18_000)

    assert olcham.nomi == "КГП 100-50 (6-10)"     # eng kattasi, 11 700
    assert soni == 2
    assert olcham.sigim * soni >= 18_000


def test_parallel_soni_YUQORIGA_yumaloqlanadi():
    """Ortiqcha yuk bilan ishlatmaymiz."""
    olcham, soni = shovqin_tanla(_NOMLAR, 12_000)

    assert soni == 2      # 11 700 bitta yetmaydi


def test_sarf_nol_bolsa_None():
    assert shovqin_tanla(_NOMLAR, 0) is None

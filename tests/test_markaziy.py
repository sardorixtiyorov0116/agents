"""Markaziy havo tayyorlash qurilmasi (КЦКП) — `hisob/markaziy.py`.

NEGA BU BOR
-----------
18 000 m³/soat lik binoga tizim 15 ta kanal isitgichi + 6 ta sovutgich
taklif qilardi. Arifmetik to'g'ri, amaliy jihatdan noto'g'ri: bunday
masshtabda muhandis BITTA markaziy qurilma qo'yadi (КЦКП-20), uning
ichida ventilyator ham, isitgich ham, sovutgich ham, filtr ham bor.
"""

from __future__ import annotations

import pytest

from hisob.markaziy import ENG_KAM_SARF, markaziy_tanla

_PARAM = {
    "КЦКП-1,6": {"havo_sarfi": 1600.0},
    "КЦКП-5": {"havo_sarfi": 5000.0},
    "КЦКП-16": {"havo_sarfi": 16000.0},
    "КЦКП-20": {"havo_sarfi": 20000.0},
    "КЦКП-100": {"havo_sarfi": 100000.0},
    # Ventilyator — markaziy qurilma emas, tanlovga tushmasin.
    "ВЦ 4-75-8-1": {"havo_sarfi": 18000.0},
}


def test_sarfga_YETADIGAN_eng_kichigi():
    """18 000 -> КЦКП-20, КЦКП-100 emas (ortiqcha pul va joy)."""
    natija = markaziy_tanla(_PARAM, 18_000)

    assert natija.nomi == "КЦКП-20"
    assert natija.zaxira == pytest.approx(0.111, abs=0.001)


def test_VENTILYATOR_markaziy_deb_olinmaydi():
    """Nomi `КЦКП` bilan boshlanmagani tanlovga tushmasligi kerak."""
    natija = markaziy_tanla(_PARAM, 18_000)

    assert not natija.nomi.startswith("ВЦ")


def test_KICHIK_obyektga_taklif_QILINMAYDI():
    """Kichik obyektga markaziy qurilma ortiqcha qimmat va joy egallaydi."""
    assert markaziy_tanla(_PARAM, ENG_KAM_SARF - 1) is None


def test_yetadigani_yoq_bolsa_None():
    """PARALLEL qo'yilmaydi — ikkita markaziy qurilma alohida qaror."""
    assert markaziy_tanla(_PARAM, 500_000) is None


def test_katalogda_yoq_bolsa_None():
    assert markaziy_tanla({}, 18_000) is None

"""Telegram ID ro'yxatini o'qish.

NEGA ALOHIDA TEST: bu ro'yxat QO'LDA to'ldiriladi va xato qilish oson.
Bo'sh ro'yxat esa botni HECH KIMGA javob bermaydigan qilib qo'yadi —
ya'ni bitta noto'g'ri ajratgich butun tizimni jimgina o'chiradi.
"""

from __future__ import annotations

import logging

import pytest

from app.config import Sozlama


@pytest.mark.parametrize("xom,kutilgan", [
    # Asosiy shakl — VERGUL.
    ("8149535541", {8149535541}),
    ("111,222", {111, 222}),
    ("111, 222, 333", {111, 222, 333}),
    (" 111 , 222 ", {111, 222}),
    ("111,,222,", {111, 222}),
    # Boshqa ajratgichlar ham qabul qilinadi. Ilgari bular BO'SH
    # to'plam berardi — ya'ni bot hech kimga javob bermay qo'yardi.
    ("111;222", {111, 222}),
    ("111 222", {111, 222}),
    ("111\n222", {111, 222}),
    ("111,\n222;  333", {111, 222, 333}),
    # Bo'sh — bu to'g'ri holat (bot ataylab o'chirilgan).
    ("", set()),
    ("   ", set()),
])
def test_idlar_oqiladi(xom, kutilgan):
    assert Sozlama._idlar(xom) == kutilgan


@pytest.mark.parametrize("xom", ["@aziz", "ism familiya", "aziz, 222"])
def test_raqam_bolmagan_yozuv_ogohlantiradi(xom, caplog):
    """Xato jimgina o'tib ketmasin — logda sabab ko'rinsin."""
    with caplog.at_level(logging.WARNING, logger="sozlama"):
        Sozlama._idlar(xom)

    assert any("tushunarsiz yozuv" in q.getMessage() for q in caplog.records)


def test_togri_royxat_ogohlantirmaydi(caplog):
    with caplog.at_level(logging.WARNING, logger="sozlama"):
        Sozlama._idlar("111, 222, 333")

    assert not [q for q in caplog.records if q.name == "sozlama"]


def test_bosh_royxat_ogohlantirmaydi(caplog):
    """Bo'sh ro'yxat — ataylab qilingan sozlama, xato emas."""
    with caplog.at_level(logging.WARNING, logger="sozlama"):
        Sozlama._idlar("")

    assert not [q for q in caplog.records if q.name == "sozlama"]


@pytest.mark.parametrize("maydon,xususiyat", [
    ("bot_ruxsat_etilgan_id", "ruxsat_etilgan_idlar"),
    ("bot_hr_ruxsat_id", "hr_idlar"),
    ("bot_katalog_ruxsat_id", "katalog_idlar"),
    ("tender_kuzatuv_id", "tender_idlar"),
    ("mijoz_bot_menejer_id", "mijoz_menejer_idlar"),
])
def test_barcha_royxatlar_vergulni_tushunadi(maydon, xususiyat):
    """Beshala ro'yxat ham bir xil qoida bilan o'qilsin."""
    s = Sozlama(**{maydon: "111, 222, 333"})

    assert getattr(s, xususiyat) == {111, 222, 333}


@pytest.mark.parametrize("maydon,xususiyat", [
    ("tender_kuzatuv_id", "tender_idlar"),
    ("mijoz_bot_menejer_id", "mijoz_menejer_idlar"),
])
def test_bosh_qoldirilsa_umumiy_royxat_ishlatiladi(maydon, xususiyat):
    """Tender va lid xabari — aytilmagan bo'lsa hammaga boradi."""
    s = Sozlama(bot_ruxsat_etilgan_id="777, 888", **{maydon: ""})

    assert getattr(s, xususiyat) == {777, 888}

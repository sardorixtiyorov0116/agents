"""QQS hisobi — katalog narxi QQS BILAN saqlanadi.

NEGA BU TESTLAR BOR
-------------------
JONLI XATO (2026-08-21 da topildi): har bir KP 12% QIMMAT chiqardi.

Buxgalteriya prays faylida narx ustuni «Цена USD с НДС» — ya'ni QQS
narx ICHIDA. Backendga aynan shu raqam yozilgan. KP esa uni QQSsiz
deb hisoblab, ustiga yana 12% qo'shardi.

Tekshirilgan: `PRICE JIHOZVENT_v5.1`, `ВЦ 4-75` varag'i, 9-qator
12-ustun = «Цена USD с НДС», qiymati 156.76 — backenddagi narx.

500 m² restoran KP sida farq 4,3 mln so'm edi. Sayt esa o'sha narxni
QQSsiz ko'rsatadi — mijoz saytda bir narx, KP da boshqa narx ko'rardi.
"""

from __future__ import annotations

import pytest

from datetime import date

from kp.model import KP, Mijoz, Qator, Shartlar
from kp.shakldan import katalog_narxi_xavfsiz, qqssiz

KATALOG = [{
    "name_uz": "Ventilyator",
    "characters": [{"title": "ВЦ 4-75-2,5", "insides": [
        {"in_model_name": "ВЦ 4-75-2,5-1-0,12/1500", "price": 156.76},
    ]}],
}]


# --- qqssiz() -----------------------------------------------------------------


def test_qqs_ajratiladi():
    """1 881 120 (QQS bilan) -> 1 679 571 (QQSsiz)."""
    assert qqssiz(1_881_120, 12) == pytest.approx(1_679_571.43, abs=0.5)


def test_ajratilgandan_keyin_QQS_qoshilsa_ASLIGA_qaytadi():
    """Bu testning butun mazmuni: ikki marta hisoblanmasin."""
    asl = 1_881_120.0

    qqssiz_summa = qqssiz(asl, 12)
    qaytgan = qqssiz_summa * 1.12

    assert qaytgan == pytest.approx(asl)


def test_qqs_nol_bolsa_narx_OZGARMAYDI():
    assert qqssiz(1000, 0) == 1000


def test_narx_yoq_bolsa_None_qaytadi():
    assert qqssiz(None, 12) is None


# --- katalogdan o'qish --------------------------------------------------------


def test_katalog_narxi_QQSSIZ_qaytadi():
    """156.76 $ x 12 000 = 1 881 120 (QQS bilan) -> QQSsiz 1 679 571."""
    natija = katalog_narxi_xavfsiz(KATALOG, "ВЦ 4-75-2,5-1-0,12/1500", 12000.0, 12.0)

    assert natija[0] == pytest.approx(1_679_571.43, abs=0.5)


def test_qqs_berilmasa_narx_OZGARMAYDI():
    """Eski chaqiruvlar buzilmasin — standart qiymat 0."""
    natija = katalog_narxi_xavfsiz(KATALOG, "ВЦ 4-75-2,5-1-0,12/1500", 12000.0)

    assert natija[0] == pytest.approx(1_881_120, abs=1)


# --- KP jadvali ---------------------------------------------------------------


def _kp(qatorlar: list[Qator]) -> KP:
    return KP(
        raqam="T", sana=date.today(), mijoz=Mijoz(nomi="Sinov"),
        qatorlar=qatorlar, shartlar=Shartlar(), rekvizitlar={},
        qqs_foizi=12.0,
    )


def test_KP_jamisi_KATALOG_narxiga_TENG():
    """Eng muhim tekshiruv: KP dagi JAMI = bazadagi narx.

    Mijoz saytda 1 881 120 ko'rsa, KP da ham shuncha ko'rishi kerak.
    """
    narx = katalog_narxi_xavfsiz(KATALOG, "ВЦ 4-75-2,5-1-0,12/1500", 12000.0, 12.0)
    kp = _kp([Qator(nomi="ВЦ 4-75-2,5-1-0,12/1500", miqdor=1,
                    birlik_narx=narx[0], qqs_foizi=12.0)])

    assert kp.jami == pytest.approx(1_881_120, abs=1)


def test_miqdor_kop_bolganda_ham_TOGRI():
    narx = katalog_narxi_xavfsiz(KATALOG, "ВЦ 4-75-2,5-1-0,12/1500", 12000.0, 12.0)
    kp = _kp([Qator(nomi="x", miqdor=7,
                    birlik_narx=narx[0], qqs_foizi=12.0)])

    assert kp.jami == pytest.approx(1_881_120 * 7, abs=7)

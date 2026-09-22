"""Ventilyatsiya hisobi — sof matematika.

Bu raqamlar mijozga ketadigan taklifga asos bo'ladi, shuning uchun ular
LLM'da emas, kodda hisoblanadi va shu yerda qo'lda tekshiriladi.
"""

from __future__ import annotations

import math

import pytest

from hisob import (
    KANAL_DIAMETRLARI,
    TAVSIYA_TEZLIK,
    Xona,
    havo_sarfi,
    kanal_olchami,
    normalar,
)


# --- havo sarfi --------------------------------------------------------------


def test_karralik_boyicha_hisob():
    """L = n × V. Ofis: 3 karra, 100 m² × 3 m = 300 m³ -> 900 m³/soat."""
    h = havo_sarfi(Xona(turi="ofis", maydon=100, balandlik=3))

    assert h.hajm == 300
    assert h.karrali_boyicha == 900
    assert h.sarf == 900
    assert h.tanlangan_usul == "karralik"


def test_odam_boyicha_hisob_kattaroq_bolsa_yutadi():
    """Ikkalasi ham TALAB — kattasi olinadi, tanlov emas.

    Kichkina majlis xonasi, ko'p odam: 20 m² × 3 m = 60 m³ × 6 = 360,
    lekin 30 odam × 60 = 1800. Odam normasi yutadi.
    """
    h = havo_sarfi(Xona(turi="majlis", maydon=20, balandlik=3, odamlar=30))

    assert h.karrali_boyicha == 360
    assert h.odam_boyicha == 1800
    assert h.sarf == 1800
    assert h.tanlangan_usul == "odam boshiga"


def test_odam_soni_aytilmasa_ogohlantiradi():
    h = havo_sarfi(Xona(turi="ofis", maydon=100, balandlik=3))

    assert h.odam_boyicha is None
    assert any("odam soni" in o for o in h.ogohlantirishlar)


def test_notanish_xona_turi_ochiq_aytiladi():
    """Jimgina ofis normasini qo'llash — yashirin xato."""
    h = havo_sarfi(Xona(turi="kosmodrom", maydon=100, balandlik=3))

    assert h.sarf == 900          # ofis normasi
    assert any("kosmodrom" in o for o in h.ogohlantirishlar)
    assert any("tekshirilsin" in o for o in h.ogohlantirishlar)


def test_olcham_berilmasa_nol_qaytadi():
    """Taxmin qilinmaydi — nol va ochiq sabab."""
    h = havo_sarfi(Xona(turi="ofis", maydon=0))

    assert h.sarf == 0
    assert h.tanlangan_usul == "hisoblanmadi"
    assert any("berilmagan" in o for o in h.ogohlantirishlar)


# --- kanal o'lchami ----------------------------------------------------------


def test_kanal_diametri_formula_boyicha():
    """F = L/(3600·v), D = sqrt(4F/π). 900 m³/soat, v = 6.5 m/s."""
    k = kanal_olchami(900, "magistral")

    kutilgan_yuza = 900 / (3600 * 6.5)
    kutilgan_d = math.sqrt(4 * kutilgan_yuza / math.pi) * 1000

    assert k.kerakli_yuza == pytest.approx(kutilgan_yuza, rel=1e-3)
    assert k.hisobiy_diametr == pytest.approx(kutilgan_d, rel=1e-3)


def test_standart_diametrga_YUQORIGA_yumaloqlanadi():
    """Kichraytirilsa tezlik oshadi va shovqin paydo bo'ladi."""
    k = kanal_olchami(900)

    assert k.diametr in KANAL_DIAMETRLARI
    assert k.diametr >= k.hisobiy_diametr
    # Bir pog'ona pastdagi diametr yetarli bo'lmasligi kerak
    pastdagi = [d for d in KANAL_DIAMETRLARI if d < k.diametr]
    if pastdagi:
        assert pastdagi[-1] < k.hisobiy_diametr


def test_haqiqiy_tezlik_standart_diametr_boyicha():
    """Diametr kattalashgach tezlik pasayadi — shuni ko'rsatamiz."""
    k = kanal_olchami(900)

    yuza = math.pi * (k.diametr / 1000) ** 2 / 4
    assert k.haqiqiy_tezlik == pytest.approx(900 / (3600 * yuza), rel=1e-2)
    assert k.haqiqiy_tezlik <= TAVSIYA_TEZLIK["magistral"][1]


def test_juda_katta_sarfda_ogohlantirish():
    """Standart qatordan oshsa — bir necha kanal kerakligi aytiladi."""
    k = kanal_olchami(200_000)

    assert k.diametr == KANAL_DIAMETRLARI[-1]
    assert any("standart qatordan katta" in o for o in k.ogohlantirishlar)


def test_tarmoq_uchun_tezlik_pastroq():
    """Tarmoqda 3-5 m/s — magistraldan past, kanal kattaroq chiqadi."""
    magistral = kanal_olchami(2000, "magistral")
    tarmoq = kanal_olchami(2000, "tarmoq")

    assert tarmoq.hisobiy_diametr > magistral.hisobiy_diametr
    assert tarmoq.tezlik_oraligi == TAVSIYA_TEZLIK["tarmoq"]


def test_nol_sarfda_hisob_yoq():
    k = kanal_olchami(0)

    assert k.diametr == 0
    assert any("nol" in o for o in k.ogohlantirishlar)


# --- normalar fayli ----------------------------------------------------------


def test_normalar_fayldan_oqiladi():
    n = normalar()

    assert "ofis" in n and "ombor" in n
    assert n["ofis"]["karrali"] == 3.0
    # Fayl kengaytirilgan bo'lsin — zaxira ro'yxatdan ko'p
    assert len(n) >= 10


def test_har_normada_izoh_bor():
    """Menejer qaysi norma ishlatilganini ko'rishi kerak."""
    for tur, norma in normalar().items():
        assert norma.get("izoh"), f"{tur}: izoh yo'q"
        assert norma.get("karrali") or norma.get("odam_boshiga")


# --- oxirigacha ---------------------------------------------------------------


def test_ombor_misoli():
    """800 m², 6 m balandlik: 4800 m³ × 2 = 9600 m³/soat -> Ø800."""
    h = havo_sarfi(Xona(turi="ombor", maydon=800, balandlik=6))
    k = kanal_olchami(h.sarf)

    assert h.sarf == 9600
    assert k.diametr == 800
    assert 5.0 <= k.haqiqiy_tezlik <= 8.0

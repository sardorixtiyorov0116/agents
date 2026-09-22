"""Panjara tanlash — `hisob/panjara.py`.

NEGA BU TESTLAR BOR
-------------------
Panjara soni KP ga miqdor bo'lib tushadi va mijoz shuncha dona sotib
oladi. Xato bo'lsa: kam bo'lsa tizim shovqin qiladi, ko'p bo'lsa mijoz
ortiqcha pul to'laydi.

Eng nozik joyi — JONLI KESIM. Panjaraning gabariti 300x300 = 0,09 m²,
lekin jonli kesimi atigi 0,033 m² (РВН). Gabarit bo'yicha hisoblansa
panjara UCH BAROBAR kam chiqadi.
"""

from __future__ import annotations

import math

import pytest

from hisob.panjara import ENG_KAM_SONI, panjara_tanla, panjaralar

# --- jadval manbadan o'qiladi -------------------------------------------------


def test_jadval_yuklanadi():
    xom = panjaralar()

    assert "РВН" in xom["turlar"]
    assert "РВИ" in xom["turlar"]


def test_jadval_SIMMETRIK():
    """300x400 va 400x300 — bir xil panjara, yuzasi ham bir xil.

    Bosma katalogdan ko'chirishda raqam tushib qolsa, shu yerda
    bilinadi. Aynan shunday xato bo'lgan: РВН jadvalining 500x400
    katagida "0,87" turadi (nol tushib qolgan, to'g'risi 0,087).
    """
    for turi, yozuv in panjaralar()["turlar"].items():
        jadval = yozuv["yuza"]
        for a, qatorlar in jadval.items():
            for b, yuza in qatorlar.items():
                assert jadval[b][a] == pytest.approx(yuza), f"{turi} {a}x{b}"


def test_RVI_yuzasi_RVN_dan_KATTA():
    """РВН tashqi panjara — jalyuzisi qalin, jonli kesimi kichikroq."""
    rvn = panjaralar()["turlar"]["РВН"]["yuza"]
    rvi = panjaralar()["turlar"]["РВИ"]["yuza"]

    for a in rvn:
        for b in rvn[a]:
            assert rvi[a][b] > rvn[a][b], f"{a}x{b}"


# --- hisob --------------------------------------------------------------------


def test_soni_formula_boyicha():
    """n = ceil(L / (3600 x v x f)) — qo'lda tekshiriladigan misol."""
    natija = panjara_tanla(14000, "РВН", tezlik=2.0)

    kerakli = 14000 / (3600 * 2.0)
    assert natija.kerakli_yuza == pytest.approx(kerakli, abs=0.001)
    assert natija.soni == math.ceil(kerakli / natija.bitta_yuza)


def test_kamida_IKKITA_panjara():
    """Bitta panjara havoni xona bo'ylab taqsimlamaydi — bir nuqtaga puflaydi."""
    natija = panjara_tanla(14000)

    assert natija.soni >= ENG_KAM_SONI


def test_sarf_oshsa_soni_ham_OSHADI():
    kichik = panjara_tanla(1000)
    katta = panjara_tanla(40000)

    assert katta.soni > kichik.soni


def test_haqiqiy_tezlik_chegaradan_OSHMAYDI():
    """Tezlik 3 m/s dan oshsa shovqin bo'ladi (vault: «shamol shikoyati»).

    Soni yuqoriga yumaloqlanadi, shuning uchun haqiqiy tezlik har doim
    hisobiy tezlikdan PAST bo'lishi kerak.
    """
    for sarf in (300, 1000, 8400, 14000, 40000, 100000):
        natija = panjara_tanla(sarf)
        assert natija.haqiqiy_tezlik <= natija.tezlik + 0.01, sarf


def test_nomi_katalog_shaklida():
    """`РВН 600х400` — kirill «х» bilan, backend nomiga aynan mos."""
    natija = panjara_tanla(14000, "РВН")

    assert natija.nomi.startswith("РВН ")
    assert "х" in natija.nomi          # kirill x, lotin emas
    assert "x" not in natija.nomi


def test_sarf_nol_bolsa_TAXMIN_QILINMAYDI():
    assert panjara_tanla(0) is None
    assert panjara_tanla(-5) is None


def test_notogri_tur_uchun_None():
    """Jadvalda yo'q turga panjara «o'ylab topilmaydi»."""
    assert panjara_tanla(1000, "YOQ-BUNDAY-TUR") is None


def test_juda_katta_sarfda_OGOHLANTIRADI():
    """Panjara soni haddan oshsa, loyihachi ko'rib chiqsin."""
    natija = panjara_tanla(1_000_000)

    assert natija.ogohlantirishlar


def test_jonli_kesim_GABARIT_emas():
    """300x300 gabariti 0,09 m², jonli kesimi 0,033 m².

    Gabarit ishlatilsa panjara uch barobar kam chiqadi va tizim
    shovqin qiladi — shuning uchun bu farq testda qayd etilgan.
    """
    yuza = panjaralar()["turlar"]["РВН"]["yuza"][300][300]

    assert yuza == 0.033
    assert yuza < 0.3 * 0.3

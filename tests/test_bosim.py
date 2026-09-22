"""Bosim yo'qotishi va ventilyator tanlash.

NEGA BU MODUL BOR: ventilyator o'z tavsifi tizim tavsifi bilan
kesishgan ish nuqtasida ishlaydi. Sarfi yetadigan, lekin bosimi
yetmaydigan ventilyator "ishlaydi, lekin havo bermaydi" holatini
beradi.

Jonli misol (2026-08-11, 800 m² ombor, 8000 m³/soat):
    ВО 12-300-6,3   6150–10000 m³/soat,   50–95 Pa   <- YARAMAYDI
    ВЦ 14-46-5      5000–8400 m³/soat,  860–1070 Pa  <- to'g'ri
Ikkalasining sarfi ham yetadi. Farq faqat bosimda.
"""

from __future__ import annotations

import pytest

from hisob import bosim_yoqotishi, tipik_bosim, yetadimi
from hisob.bosim import USKUNA, ZAXIRA, dinamik_bosim


# --- bosim yo'qotishi ---------------------------------------------------------


def test_kanal_uzunligi_hisobga_olinadi():
    qisqa = bosim_yoqotishi(tezlik=6.0, kanal_uzunligi=10)
    uzun = bosim_yoqotishi(tezlik=6.0, kanal_uzunligi=100)

    assert uzun.ishqalanish > qisqa.ishqalanish
    assert uzun.jami > qisqa.jami


def test_burilish_bosimni_oshiradi():
    """Keskin burilish yumshog'idan ancha qimmat."""
    yumshoq = bosim_yoqotishi(tezlik=6.0, qarshiliklar={"burilish_yumshoq": 4})
    keskin = bosim_yoqotishi(tezlik=6.0, qarshiliklar={"burilish_keskin": 4})

    assert keskin.mahalliy > yumshoq.mahalliy * 3


def test_tezlik_kvadrat_boyicha_tasir_qiladi():
    """Tezlik 2 barobar oshsa, mahalliy yo'qotish ~4 barobar."""
    sekin = bosim_yoqotishi(tezlik=4.0, qarshiliklar={"panjara": 1})
    tez = bosim_yoqotishi(tezlik=8.0, qarshiliklar={"panjara": 1})

    assert tez.mahalliy == pytest.approx(sekin.mahalliy * 4, rel=0.01)


def test_uskunalar_qoshiladi():
    bosh = bosim_yoqotishi(tezlik=6.0, kanal_uzunligi=20)
    filtrli = bosim_yoqotishi(
        tezlik=6.0, kanal_uzunligi=20, uskunalar=["filtr_g4", "isitgich_suvli"],
    )

    kutilgan = USKUNA["filtr_g4"] + USKUNA["isitgich_suvli"]
    assert filtrli.uskunalar == kutilgan
    assert filtrli.jami > bosh.jami


def test_filtr_iflos_holatida_hisoblanadi():
    """Toza filtr bo'yicha hisoblansa, tizim faqat birinchi oyda ishlaydi."""
    assert USKUNA["filtr_g4"] >= 150, "toza filtr qiymati olingan ko'rinadi"


def test_zaxira_qoshiladi():
    natija = bosim_yoqotishi(tezlik=6.0, kanal_uzunligi=50)

    asosiy = natija.ishqalanish + natija.mahalliy + natija.uskunalar
    assert natija.zaxira == pytest.approx(asosiy * ZAXIRA, rel=0.01)
    assert natija.jami == pytest.approx(asosiy + natija.zaxira, rel=0.01)


def test_malumot_bolmasa_ochiq_aytiladi():
    natija = bosim_yoqotishi(tezlik=6.0)

    assert natija.jami == 0
    assert any("baholanmadi" in x for x in natija.ogohlantirishlar)


def test_juda_yuqori_bosim_ogohlantiradi():
    natija = bosim_yoqotishi(
        tezlik=15.0, kanal_uzunligi=500,
        qarshiliklar={"burilish_keskin": 20},
        uskunalar=["filtr_f7", "rekuperator", "sovutgich"],
    )

    assert any("juda yuqori" in x for x in natija.ogohlantirishlar)


def test_notogri_nom_yiqitmaydi():
    natija = bosim_yoqotishi(
        tezlik=6.0, qarshiliklar={"yoq_bunday": 3}, uskunalar=["yoq_uskuna"],
    )

    assert natija.mahalliy == 0
    assert len(natija.ogohlantirishlar) >= 2


def test_dinamik_bosim():
    """ρ·v²/2 — 6 m/s da ≈ 21,6 Pa."""
    assert dinamik_bosim(6.0) == pytest.approx(21.6, rel=0.01)
    assert dinamik_bosim(0) == 0


# --- ventilyator bosimi yetadimi ----------------------------------------------


@pytest.mark.parametrize("bosim,kerakli,kutilgan", [
    # Jonli misol: kanalli tizim ~250 Pa talab qiladi.
    ([50, 95], 250, False),          # ВО 12-300-6,3 — yaramaydi
    ([860, 1070], 250, True),        # ВЦ 14-46-5 — yaraydi
    (500, 250, True),
    (200, 250, False),
    (250, 250, True),                # aynan tengi yetadi
    # Katalogda bosim yo'q — "yaramaydi" DEB HISOBLANMAYDI.
    (None, 250, None),
    ([], 250, None),
    ("", 250, None),
])
def test_bosim_yetadimi(bosim, kerakli, kutilgan):
    assert yetadimi(bosim, kerakli) is kutilgan


def test_oraliqdan_maksimal_olinadi():
    """Ventilyator eng katta bosimni eng kichik sarfda beradi."""
    assert yetadimi([100, 900], 800) is True
    assert yetadimi([100, 900], 1000) is False


def test_kerakli_bosim_nol_bolsa_baholanmaydi():
    assert yetadimi([500], 0) is None


# --- tipik tarmoq -------------------------------------------------------------


@pytest.mark.parametrize("tarmoq", ["oddiy", "kanalli", "filtrli", "toliq"])
def test_tipik_bosim_oraliq_beradi(tarmoq):
    oraliq = tipik_bosim(tarmoq)

    assert oraliq is not None
    assert oraliq[0] < oraliq[1]


def test_tipik_bosim_ortib_boradi():
    """Tarmoq murakkablashgani sari bosim oshadi."""
    oddiy = tipik_bosim("oddiy")
    kanalli = tipik_bosim("kanalli")
    filtrli = tipik_bosim("filtrli")
    toliq = tipik_bosim("toliq")

    assert oddiy[1] <= kanalli[1] <= filtrli[1] <= toliq[1]


def test_nomalum_tarmoq():
    assert tipik_bosim("yoq bunday") is None


# --- aspiratsiya boshqa usul bilan hisoblanadi --------------------------------


@pytest.mark.parametrize("savol", [
    "Yog'och sexida aspiratsiya tizimi kerak",
    "Chang so'rish tizimi qanday qilinadi",
    "Siklon tanlab bering",
    "Аспирация цеха",
    "опилки удаление",
    "Chang ventilyatori kerak",
])
def test_aspiratsiya_aniqlanadi(savol):
    from app.agentlar.loyihachi import ASPIRATSIYA

    assert ASPIRATSIYA.search(savol) is not None


@pytest.mark.parametrize("savol", [
    "800 kv metr ombor uchun ventilyatsiya hisobi",
    "Ofis uchun havo sarfini hisoblang",
    "Majlis xonasi, 20 kishi",
])
def test_oddiy_hisob_toxtatilmaydi(savol):
    from app.agentlar.loyihachi import ASPIRATSIYA

    assert ASPIRATSIYA.search(savol) is None


@pytest.mark.asyncio
async def test_aspiratsiyada_xona_olchami_soralmaydi():
    """JONLI XATO: "yog'och sexida aspiratsiya" -> "sex maydoni qancha?"

    Aspiratsiyada havo sarfi xona hajmidan emas, HAR DASTGOH
    bo'yicha hisoblanadi. Xona o'lchamini so'rash — noto'g'ri savol
    va mijozni chalg'itadi.
    """
    from app.agentlar.loyihachi import Loyihachi
    from app.konvert import Holat
    from app.kontraktlar import reyestr

    class Yiqiladigan:
        async def javob(self, *a, **kw):
            raise AssertionError("aspiratsiyada model chaqirilmasligi kerak")

    agent = Loyihachi(
        kontrakt=reyestr()["hvac-calc"], llm=Yiqiladigan(), baza=None,
    )
    konvert = await agent.ishla("Yog'och sexida aspiratsiya tizimi kerak")

    assert konvert.holat is Holat.ANIQLIK_KERAK
    savollar = " ".join(konvert.natija["savollar"]).lower()
    # To'g'ri savollar: material, manba soni, portlash xavfi.
    assert "material" in savollar or "yog'och" in savollar
    assert "dastgoh" in savollar
    assert "portlash" in savollar
    # NOTO'G'RI savol bo'lmasin.
    assert "maydon" not in savollar
    assert "balandlik" not in savollar

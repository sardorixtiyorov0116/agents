"""Loyiha qisqartmalarini katalog nomiga aylantirish.

NEGA BU TESTLAR BOR
-------------------
JONLI XATO (2026-08-28). Menejer botga haqiqiy loyiha
spetsifikatsiyasini berdi:

    Решетка АДН:
    Решетка 300х150 — 57 dona

Bot KP ga «Решетка 300х150» deb yozdi — katalogda bunday nom yo'q,
narx topilmadi. 44 qatorning hammasi bo'sh chiqdi. Ustiga har bo'lim
sarlavhasi («Клп ДКС:») ham MAHSULOT bo'lib tushdi.

Menejer esa o'sha ro'yxatdan to'liq narxlangan KP-13357 ni tuzgan
edi: «Решетка вентиляционная регулируемая РВР-2 300х150мм без КРВ».

Quyidagi kutilgan qiymatlar AYNAN o'sha KP dan olingan — o'ylab
topilmagan.
"""

from __future__ import annotations

import pytest

from kp.qisqartma import olcham_ajrat, qollash, topilsin
from kp.shakl import mahsulot_royxati, sarlavhami


# --- Sarlavha va mahsulotni ajratish ------------------------------------------


@pytest.mark.parametrize("qator", [
    "Клп ДКС:",
    "Решетка АДН:",
    "Клп огназадернивиший:",
    "Клп ПОЖАРНИЙ:",
])
def test_bolim_sarlavhasi_TANILADI(qator):
    assert sarlavhami(qator) is True


@pytest.mark.parametrize("qator", [
    "Клап 1000х400 — 2 dona",
    "Решетка 300х150 — 57 dona",
    "ВКП 40х20 — 4 dona",
])
def test_mahsulot_qatori_sarlavha_EMAS(qator):
    assert sarlavhami(qator) is False


def test_sarlavha_MAHSULOT_bolib_qolmaydi():
    """Ro'yxatda 9 ta sarlavha bor edi — KP ga 9 ta ortiqcha qator tushgan."""
    royxat = mahsulot_royxati(
        "Клп ДКС:\nКлап 900х400 — 1 dona\nРешетка АДН:\nРешетка 300х150 — 57 dona")

    assert len(royxat) == 2
    assert all("ДКС:" not in y["nomi"] for y in royxat)


def test_sarlavha_KEYINGI_qatorlarga_biriktiriladi():
    royxat = mahsulot_royxati("Решетка АДН:\nРешетка 300х150 — 57 dona")

    assert royxat[0]["bolim"] == "Решетка АДН"


def test_sarlavhasiz_royxat_AVVALGIDEK_ishlaydi():
    royxat = mahsulot_royxati("ВКП 40х20-4E20 — 4 dona\nВЦ 4-75-6,3 — 1 dona")

    assert len(royxat) == 2
    assert royxat[0]["nomi"] == "ВКП 40х20-4E20"
    assert "bolim" not in royxat[0]


# --- O'lcham ajratish ---------------------------------------------------------


@pytest.mark.parametrize("matn,kutilgan", [
    ("Решетка 300х150", "300х150"),
    ("Клап 1000x400", "1000х400"),          # lotincha x
    ("Клапан дымавой сеч. 500х300 с эл.приводом", "500х300"),
    ("Дроссель 700х400х250", "700х400х250"),
])
def test_olcham_ajratiladi(matn, kutilgan):
    assert olcham_ajrat(matn) == kutilgan


def test_diametr_alohida_ajratiladi():
    """«Решетка Д125» -> DVS 125."""
    assert olcham_ajrat("Решетка Д125", diametr=True) == "125"


def test_olchamsiz_qator_bosh_qaytaradi():
    assert olcham_ajrat("Решетка kattaroq") == ""


# --- Qisqartmani topish -------------------------------------------------------


@pytest.mark.parametrize("sarlavha", [
    "Решетка АДН", "решетка адн", "Решетка АДН:", "АДН",
])
def test_qisqartma_har_xil_yozilishda_topiladi(sarlavha):
    q = topilsin(sarlavha)

    assert q is not None and "без КРВ" in q.qolip


def test_ENG_UZUN_mos_kelgani_tanlanadi():
    """«решетка апн» ham, «апн» ham ro'yxatda — qisqasi tushib qolmasin."""
    q = topilsin("Решетка АПН")

    assert q is not None and "4РВП" in q.qolip and "без КРВ" in q.qolip


def test_notanish_sarlavha_None():
    assert topilsin("Nimadir boshqa") is None


# --- Tarjima — KP-13357 dan olingan kutilgan qiymatlar -------------------------


@pytest.mark.parametrize("sarlavha,qator,kutilgan", [
    ("Клп огназадернивиший", "Клап 1000х400",
     "Клапан противопожарный КПУ-НО-Н-EI90-1000х400-КН-НУП-ЭМ-220"),
    ("Клп ДКС", "Клап 900х400",
     "Дроссель клапан ДКСп 900х400"),
    ("Решетка АДН", "Решетка 300х150",
     "Решетка вентиляционная регулируемая РВР-2 300х150мм без КРВ"),
    ("Решетка АДР", "Решетка 500х300",
     "Решетка вентиляционная регулируемая РВР-2 500х300мм с КРВ"),
    ("Решетка АПР", "Решетка 600х600",
     "Решетка вентиляционная потолочная 4РВП 600х600мм с КРВ"),
    ("Решетка АПН", "Решетка 600х600",
     "Решетка вентиляционная потолочная 4РВП 600х600мм без КРВ"),
    ("Решетка ДПУ", "Решетка Д125",
     "Потолочный диффузор DVS 125"),
    ("Решетка пожарный", "Решетка пожарный 500х200",
     "Решетка металлическая РМ-Д-ОЦ-500х200-НС-У1-СТ"),
    ("Клп ПОЖАРНИЙ", "Клапан дымавой сеч. 500х300",
     "Клапан противопожарный КПД-НЗ-Н-EI90-500х300-КН-НУП-ЭР-220v"),
])
def test_KP_13357_dagi_nomlar_AYNAN_chiqadi(sarlavha, qator, kutilgan):
    natija = qollash(sarlavha, qator)

    assert natija is not None
    assert natija.nomi == kutilgan


def test_notanish_bolim_TARJIMA_QILINMAYDI():
    """Taxminiy nom yasashdan ko'ra asl matn qolgani yaxshi."""
    assert qollash("Nimadir", "Narsa 300х150") is None


def test_olchamsiz_qator_tarjima_QILINMAYDI():
    assert qollash("Решетка АДН", "Решетка kattaroq") is None


# --- Eng kichik o'lcham qoidasi -----------------------------------------------
#
# KP-13357 da mijoz «Решетка 150х150 — 7 dona» so'ragan (АПР bo'limida),
# menejer esa «4РВП 300х300мм с КРВ — 7» yozgan — o'lchamni O'ZI
# kattalashtirgan, chunki 4РВП 300х300 dan kichik ishlab chiqarilmaydi.


def test_kichik_olcham_KATTALASHTIRILADI():
    natija = qollash("Решетка АПР", "Решетка 150х150")

    assert natija is not None
    assert "300х300" in natija.nomi


def test_kattalashtirish_JIMGINA_bolmaydi():
    """Loyihada 150х150 tuynuk bo'lsa, 300х300 panjara sig'maydi."""
    natija = qollash("Решетка АПР", "Решетка 150х150")

    assert natija.ogohlantirishlar
    assert any("tuynuk" in o for o in natija.ogohlantirishlar)


def test_yetarli_olcham_OZGARMAYDI():
    natija = qollash("Решетка АПР", "Решетка 600х600")

    assert "600х600" in natija.nomi
    assert not any("o'zgartirildi" in o for o in natija.ogohlantirishlar)


def test_DKS_da_chuqurlik_soraladi():
    """Katalogda «700х400х250» — uchinchi o'lchamni O'YLAB TOPMAYMIZ."""
    natija = qollash("Клп ДКС", "Клап 700х400")

    assert any("chuqurlik" in o for o in natija.ogohlantirishlar)


# --- To'liq oqim --------------------------------------------------------------


def test_royxat_tarjima_bilan_oqiladi():
    royxat = mahsulot_royxati(
        "Решетка АДН:\n"
        "Решетка 300х150 — 57 dona\n"
        "Клп ПОЖАРНИЙ:\n"
        "Клапан дымавой сеч. 500х400 — 62 dona")

    assert royxat[0]["nomi"].startswith("Решетка вентиляционная регулируемая")
    assert royxat[0]["miqdor"] == 57
    assert royxat[1]["nomi"].startswith("Клапан противопожарный КПД")
    assert royxat[1]["miqdor"] == 62


def test_ASL_nom_saqlanadi():
    """Menejer mijoz nima so'raganini ko'rishi kerak."""
    royxat = mahsulot_royxati("Решетка АДН:\nРешетка 300х150 — 57 dona")

    assert royxat[0]["asl_nomi"] == "Решетка 300х150"


# --- AI bilan moslashtirish ---------------------------------------------------
#
# JONLI E'TIROZ (2026-08-28): «mahsulot bilaman» yo'lida AI umuman
# yo'q edi — faqat aniq moslik qidirilardi. Nom bir oz boshqacha
# yozilsa jimgina bo'sh natija chiqardi va tashqaridan "qotib qolgan"
# bo'lib ko'rinardi.
#
# QOTIB QOLGAN JADVAL BU MUAMMONI HAL QILMAYDI — u faqat oldindan
# yozilgan holatlarni biladi. Shuning uchun: kod toraytiradi, AI
# tanlaydi, kod narxlaydi.


def test_bitta_nomzodda_AI_chaqirilmaydi():
    """Kvota tejaladi: bepul tarifda kuniga 20 ta so'rov."""
    from kp.royxat_ai import hal_qilinishi_kerakmi

    assert hal_qilinishi_kerakmi(["ВЦ 4-75-6,3-1"], "ВЦ 4-75") is False


def test_AYNAN_mos_kelganda_AI_chaqirilmaydi():
    from kp.royxat_ai import hal_qilinishi_kerakmi

    nomzodlar = ["ВЦ 4-75-6,3-1", "ВЦ 4-75-6,3-2"]

    assert hal_qilinishi_kerakmi(nomzodlar, "ВЦ 4-75-6,3-1") is False


def test_kop_nomzodda_AI_kerak():
    from kp.royxat_ai import hal_qilinishi_kerakmi

    assert hal_qilinishi_kerakmi(["ВЦ 4-75-6,3-1", "ВЦ 4-75-6,3-2"], "ВЦ 4-75") is True


def test_AI_katalogda_YOQ_nomni_kirita_olmaydi():
    """Chegaradan tashqari raqam RAD ETILADI."""
    from kp.royxat_ai import javobni_oqi

    qatorlar = [(0, "ВЦ 4-75", ["ВЦ 4-75-6,3-1", "ВЦ 4-75-8-1"])]

    natija = javobni_oqi({"tanlovlar": [{"qator": 0, "nomzod": 99}]}, qatorlar)

    assert natija == {}


def test_manfiy_javob_TOPILMADI_deb_qabul_qilinadi():
    from kp.royxat_ai import javobni_oqi

    qatorlar = [(0, "Nimadir", ["ВЦ 4-75-6,3-1"])]

    assert javobni_oqi({"tanlovlar": [{"qator": 0, "nomzod": -1}]}, qatorlar) == {}


def test_togri_tanlov_qabul_qilinadi():
    from kp.royxat_ai import javobni_oqi

    qatorlar = [(5, "ВЦ 4-75", ["ВЦ 4-75-6,3-1", "ВЦ 4-75-8-1"])]

    natija = javobni_oqi({"tanlovlar": [{"qator": 0, "nomzod": 1}]}, qatorlar)

    assert natija == {5: "ВЦ 4-75-8-1"}


def test_buzuq_javob_YIQITMAYDI():
    from kp.royxat_ai import javobni_oqi

    qatorlar = [(0, "x", ["a"])]

    assert javobni_oqi({}, qatorlar) == {}
    assert javobni_oqi({"tanlovlar": ["buzuq"]}, qatorlar) == {}
    assert javobni_oqi({"tanlovlar": [{"qator": "x", "nomzod": "y"}]}, qatorlar) == {}


def test_ASL_nom_saqlanadi_qollashda():
    from kp.royxat_ai import qollash

    mahsulotlar = [{"nomi": "ВЦ 4-75", "miqdor": 2.0}]

    natija = qollash(mahsulotlar, {0: "ВЦ 4-75-6,3-1"})

    assert natija[0]["nomi"] == "ВЦ 4-75-6,3-1"
    assert natija[0]["asl_nomi"] == "ВЦ 4-75"


def test_tanlovsiz_royxat_OZGARMAYDI():
    from kp.royxat_ai import qollash

    mahsulotlar = [{"nomi": "ВЦ 4-75", "miqdor": 2.0}]

    assert qollash(mahsulotlar, {}) == mahsulotlar


@pytest.mark.asyncio
async def test_AI_YIQILSA_royxat_avvalgidek_ishlanadi():
    """Moslashtirishsiz KP — umuman KP yo'qligidan yaxshi."""
    from kp.royxat_ai import moslashtir

    class Buzuq:
        async def javob(self, **k):
            raise RuntimeError("kvota tugadi")

    katalog = [{"characters": [{"title": "ВЦ", "insides": [
        {"in_model_name": "ВЦ 4-75-6,3-1", "price": 1.0},
        {"in_model_name": "ВЦ 4-75-6,3-2", "price": 2.0}]}]}]

    tanlovlar, ogoh = await moslashtir(
        [{"nomi": "ВЦ 4-75"}], katalog, Buzuq())

    assert tanlovlar == {}
    assert any("tekshirsin" in o for o in ogoh)

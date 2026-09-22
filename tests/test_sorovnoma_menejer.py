"""So'rovnomadan KP loyihasi va menejer tugmalari.

NEGA LOYIHA, TAYYOR KP EMAS
---------------------------
KP tijorat majburiyati: blankada kompaniya nomi, direktor imzosi va
narx amal qilish muddati turadi. Botga yozgan istalgan odamga uni
avtomat yuborish narx E'LON QILISH degani, va xato narxni qaytarib
bo'lmaydi. Shuning uchun oxirgi qadamda odam turadi.

RAQAM ALOHIDA. Tasdiqlanmagan hujjat rasmiy KP raqamini BAND
QILMASLIGI kerak: mijoz "KP-2026-0042 qani" deb so'rasa, u raqam
boshqa taklifga berilgan bo'lardi.
"""

from __future__ import annotations

import pytest

from sorovnoma.kp_loyiha import _olcham_normal, loyiha_yasa, model_nomi
from sorovnoma.menejer import (
    LOYIHA_OLDI,
    OZIM,
    YUBOR,
    loyiha_raqami,
    mijoz_havolasi,
    ozim_matni,
    tugmalar,
    xabar_matni,
)

SAVAT = [
    {"bolim": "panjara", "javoblar": {
        "model": "РВН", "olcham": "500x300", "krv": "ha",
        "rang": "9016", "soni": 14}},
    {"bolim": "filtr", "javoblar": {
        "turi": "ФЯГ", "klass": "G4", "olcham": "592x592",
        "ramka": 48.0, "iqlim": "У", "soni": 6}},
]


# --- Model nomini yig'ish -----------------------------------------------------


@pytest.mark.parametrize("kiritilgan,kutilgan", [
    ("500x300", "500х300"),
    ("500 x 300", "500х300"),
    ("500х300", "500х300"),
    ("500*300", "500х300"),
    ("500×300", "500х300"),
    ("500 на 300", "500х300"),
])
def test_olcham_KIRILCHA_belgiga_keltiriladi(kiritilgan, kutilgan):
    """Katalogda kirilcha «х» ishlatilgan — lotincha «x» bilan topilmasdi."""
    assert _olcham_normal(kiritilgan) == kutilgan


def test_olchamsiz_matn_bosh_qaytaradi():
    assert _olcham_normal("kattaroq") == ""
    assert _olcham_normal("") == ""


def test_panjara_nomi_model_va_olchamdan():
    nom = model_nomi("panjara", {"model": "РВН", "olcham": "500x300"})

    assert nom == "РВН 500х300"


def test_filtr_nomi_tur_va_olchamdan():
    nom = model_nomi("filtr", {"turi": "ФЯГ", "olcham": "592x592"})

    assert nom == "ФЯГ 592х592"


def test_olcham_YOQ_bolsa_faqat_model():
    assert model_nomi("panjara", {"model": "РВН", "olcham": ""}) == "РВН"


def test_ventilyator_nomi_javoblardan_YIGILMAYDI():
    """Mijoz model nomini bilmaydi — u sarf va bosim beradi."""
    assert model_nomi("ventilyator", {"sarf": 8000, "bosim": 450}) == ""


# --- Loyiha raqami ------------------------------------------------------------


def test_loyiha_raqami_HAQIQIY_KP_raqamidan_farq_qiladi():
    raqam = loyiha_raqami(42)

    assert raqam.startswith(LOYIHA_OLDI)
    assert "0042" in raqam


# --- Mijoz havolasi -----------------------------------------------------------


def test_username_bosiladigan_havolaga_aylanadi():
    havola = mijoz_havolasi("@jasur_k", 111)

    assert "https://t.me/jasur_k" in havola


def test_telefon_oz_holicha_qoladi():
    assert mijoz_havolasi("+998901234567", 111) == "+998901234567"


def test_aloqa_yoq_bolsa_YOLGON_havola_berilmaydi():
    """Ishlamaydigan havola bergandan ko'ra hech nima bermagan yaxshi."""
    assert mijoz_havolasi("", 111) == ""


# --- Menejer xabari -----------------------------------------------------------


def test_xabarda_hamma_pozitsiya_va_aloqa_bor():
    matn = xabar_matni(SAVAT, "Jasur", "@jasur_k", 111)

    assert "2 ta pozitsiya" in matn
    assert "Ventilyatsiya panjaralari" in matn
    assert "Filtrlar" in matn
    assert "t.me/jasur_k" in matn


def test_aloqasiz_mijoz_OGOHLANTIRISH_bilan():
    matn = xabar_matni(SAVAT, "Jasur", "", 111)

    assert "Aloqa yo'q" in matn


def test_KP_bolmasa_summa_qatori_YOQ():
    """Loyiha yasalmasa so'rov baribir ketadi — hujjatsiz."""
    matn = xabar_matni(SAVAT, "Jasur", "@jasur_k", 111, kp=None)

    assert "KP loyihasi" not in matn


def test_narxsiz_pozitsiyalar_soni_aytiladi():
    class SoxtaKP:
        jami = 1_000_000.0

    matn = xabar_matni(SAVAT, "Jasur", "@jasur_k", 111,
                       kp=SoxtaKP(), narxsiz_soni=2)

    assert "2 pozitsiyada narx yo'q" in matn


def test_summa_TOLIQ_EMAS_deb_belgilanadi():
    class SoxtaKP:
        jami = None

    matn = xabar_matni(SAVAT, "Jasur", "@jasur_k", 111, kp=SoxtaKP())

    assert "summa to'liq emas" in matn


def test_xabarda_TEKSHIRING_ogohlantirishi_bor():
    """Menejer tugmani o'ylamasdan bosmasin."""
    class SoxtaKP:
        jami = 1_000_000.0

    matn = xabar_matni(SAVAT, "Jasur", "@jasur_k", 111, kp=SoxtaKP())

    assert "TEKSHIRING" in matn


# --- Tugmalar -----------------------------------------------------------------


def test_ikkala_yol_ham_tugmada_bor():
    qatorlar = tugmalar(7, 111).inline_keyboard
    hamma = [t.callback_data for q in qatorlar for t in q]

    assert any(d.endswith(f":{YUBOR}") for d in hamma)
    assert any(d.endswith(f":{OZIM}") for d in hamma)


def test_callback_data_sorovnoma_va_mijoz_idsini_saqlaydi():
    hamma = [t.callback_data
             for q in tugmalar(7, 111).inline_keyboard for t in q]

    assert all("7:111" in d for d in hamma)


def test_callback_data_TELEGRAM_chegarasiga_sigadi():
    hamma = [t.callback_data
             for q in tugmalar(999999, 9999999999).inline_keyboard for t in q]

    assert all(len(d.encode("utf-8")) <= 64 for d in hamma)


def test_ozim_matnida_mijoz_kontakti_bor():
    matn = ozim_matni("@jasur_k", 111)

    assert "t.me/jasur_k" in matn


def test_kontaktsiz_mijozda_BOT_orqali_yuborish_taklif_qilinadi():
    """Username ham, telefon ham yo'q — yagona yo'l bot."""
    matn = ozim_matni("", 111)

    assert "bot orqali" in matn


# --- Loyiha hujjati -----------------------------------------------------------


class SoxtaRoyxat:
    valyuta = "UZS"
    qqs_foizi = 12.0
    shartlar = {"tolov": "100% oldindan", "yetkazish": "14 kun",
                "kafolat": "12 oy", "amal_qilish_muddati": "30 kun"}

    def kirish_matni(self, til):
        return "Taklif"

    def shartlar_matni(self, til):
        return ["Shart"]


KATALOG = [{
    "name_uz": "Panjara",
    "characters": [{"title": "РВН 500х300", "insides": [
        {"in_model_name": "РВН 500х300", "price": 16.0}]}],
}]


def test_loyihada_narx_va_miqdor_toldiriladi():
    kp = loyiha_yasa(SAVAT[:1], "LOYIHA-1", "Jasur", "@jasur_k",
                     KATALOG, {}, 12000.0, SoxtaRoyxat(), {}, til="uz")

    assert len(kp.qatorlar) == 1
    assert kp.qatorlar[0].nomi == "РВН 500х300"
    assert kp.qatorlar[0].miqdor == 14
    assert kp.qatorlar[0].birlik_narx is not None


def test_narxi_YOQ_pozitsiya_ham_qatorda_qoladi():
    """Mijoz buni so'ragan — qator tushib qolmasin, narx bo'sh qolsin."""
    kp = loyiha_yasa(SAVAT[1:], "LOYIHA-1", "Jasur", "@jasur_k",
                     KATALOG, {}, 12000.0, SoxtaRoyxat(), {}, til="uz")

    assert len(kp.qatorlar) == 1
    assert kp.qatorlar[0].birlik_narx is None


def test_loyiha_hujjatda_DASTLABKI_deb_belgilanadi():
    """Tekshirilmasdan yuborilsa, buni mijoz ham sezsin."""
    kp = loyiha_yasa(SAVAT[:1], "LOYIHA-1", "Jasur", "@jasur_k",
                     KATALOG, {}, 12000.0, SoxtaRoyxat(), {}, til="uz")

    assert any("dastlabki" in o.lower() for o in kp.ogohlantirishlar)


def test_miqdor_kamida_bitta():
    savat = [{"bolim": "panjara",
              "javoblar": {"model": "РВН", "olcham": "500x300", "soni": 0}}]

    kp = loyiha_yasa(savat, "LOYIHA-1", "Jasur", "", KATALOG, {},
                     12000.0, SoxtaRoyxat(), {}, til="uz")

    assert kp.qatorlar[0].miqdor == 1


def test_mijoz_nomi_va_aloqasi_KP_ga_tushadi():
    kp = loyiha_yasa(SAVAT[:1], "LOYIHA-1", "Jasur Karimov", "+998901112233",
                     KATALOG, {}, 12000.0, SoxtaRoyxat(), {}, til="uz")

    assert kp.mijoz.nomi == "Jasur Karimov"
    assert kp.mijoz.aloqa == "+998901112233"


# --- Umumiy nom bilan narx QIDIRILMAYDI ---------------------------------------
#
# JONLI XATO (2026-08-28): chiller bo'limi qatori «Chiller» deb
# nomlandi va katalogdan «Sovitish mashinasi JV (chiller) / JV-65» ga
# tushib, KP ga 11 063 so'm narx yozildi. Mijoz esa 120 kVt so'ragan
# edi — JV-65 butunlay boshqa o'lcham.
#
# Bo'sh narxli qator menejerga tushunarli: u to'ldiradi. NOTO'G'RI
# narxli qator esa tekshirilmasdan mijozga ketishi mumkin.


@pytest.mark.parametrize("kalit", ["panjara", "filtr", "klapan", "siklon", "kckp"])
def test_javobga_bogliq_nomda_narx_QIDIRILADI(kalit):
    from sorovnoma.kp_loyiha import _narx_qidirilsinmi

    assert _narx_qidirilsinmi(kalit, "X") is True


@pytest.mark.parametrize("kalit", ["chiller", "gradirnya"])
def test_UMUMIY_nomda_narx_qidirilmaydi(kalit):
    """Qolip faqat harfli matn — nom mijoz javoblaridan hech narsa olmaydi."""
    from sorovnoma.kp_loyiha import _narx_qidirilsinmi

    assert _narx_qidirilsinmi(kalit, "X") is False


def test_chiller_qatori_NARXSIZ_chiqadi():
    from sorovnoma.kp_loyiha import loyiha_yasa

    # Katalogda «chiller» so'zi bor mahsulot BOR va narxi ham bor.
    katalog = [{
        "name_uz": "Sovitish mashinasi JV (chiller)",
        "characters": [{"title": "JV-65", "insides": [
            {"in_model_name": "JV-65", "price": 1.03}]}],
    }]
    savat = [{"bolim": "chiller",
              "javoblar": {"turi": "faqat sovutish", "sovuq_quvvat": 120.0,
                           "soni": 1}}]

    kp = loyiha_yasa(savat, "L-1", "Sinov", "", katalog, {}, 12000.0,
                     SoxtaRoyxat(), {}, til="uz")

    assert kp.qatorlar[0].birlik_narx is None


def test_harfli_qolip_ham_NOM_beradi():
    """«model aniqlanmadi» dan ko'ra oila nomi foydaliroq."""
    from sorovnoma.kp_loyiha import model_nomi

    assert model_nomi("gradirnya", {"uskuna": "kompressor"}) == "ВГ"
    assert model_nomi("chiller", {"turi": "faqat sovutish"}) == "Chiller"


def test_bosh_javob_nomni_QISQARTIRADI_lekin_yoqotmaydi():
    """«РВН» ham «РВН 500х300» kabi qidiriladi — oila narxi topilishi mumkin."""
    from sorovnoma.kp_loyiha import model_nomi

    assert model_nomi("panjara", {"model": "РВН", "olcham": ""}) == "РВН"

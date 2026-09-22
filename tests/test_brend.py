"""Texnik topshiriqdan begona brendni aniqlash.

JONLI HOLAT (2026-09-14): 510351-lot "VRF tashqi bloklariga ta'mir"
"bizga mos" deb ko'rsatildi. Texnik topshiriqda esa AUX ARV6-H610 —
bizning brend emas. Sarlavhada brend yo'q edi: 867 ta etender
sarlavhasida lug'at birorta ham moslik bermadi.

Ikki xil xato bir xil zararli:
  - brend o'tkazib yuborilsa — menejer begona uskunaga tayyorgarlik
    ko'radi;
  - noto'g'ri ogohlantirish chiqsa — menejer ogohlantirishlarga
    ishonmay qo'yadi.
"""

from __future__ import annotations

from integrations.brend import BrendTopilma, begona_brendlar


def test_haqiqiy_tz_qatori_AUX_modeli_bilan():
    """510351-lot TZ sidagi qatorning o'zi."""
    topilgan = begona_brendlar("2. Ускуналар таркиби\n- Марка/модель: ARV6-H610/SR1MV\n")

    assert topilgan == [BrendTopilma(brend="AUX", model="ARV6-H610/SR1MV")]
    assert topilgan[0].korinish == "AUX (ARV6-H610/SR1MV)"


def test_datasheet_yozilishi_ham_AUX():
    assert begona_brendlar("ARV-H610/SR1MV 22HP")[0].brend == "AUX"


def test_elektr_sxemadagi_AUX_brend_EMAS():
    """Elektr sxemada "AUX" — qo'shimcha kontakt. Kontekstsiz brend emas."""
    assert begona_brendlar("Подключить контакт AUX щита автоматики") == []


def test_kontekstdagi_AUX_brend():
    assert begona_brendlar("Кондиционер AUX, настенная сплит-система")[0].brend == "AUX"


def test_kirillcha_nom():
    assert begona_brendlar("Поставка оборудования Дайкин")[0].brend == "Daikin"


def test_Nyu_York_brend_EMAS():
    assert begona_brendlar("Офис компании в Нью-Йорке") == []


def test_umumiy_atamalar_brend_EMAS():
    matn = (
        "Приточно-вытяжная установка, VRF система, инверторный компрессор, "
        "фреон R410A, электронный расширительный клапан"
    )
    assert begona_brendlar(matn) == []


def test_takrorlanmaydi_va_model_kodi_saqlanadi():
    matn = "Daikin VRV. Оборудование DAIKIN. Наружный блок RXYQ10U."
    topilgan = begona_brendlar(matn)

    assert [t.brend for t in topilgan] == ["Daikin"]
    assert topilgan[0].model == "RXYQ10U"


def test_LG_modeli():
    assert begona_brendlar("Наружный блок ARUN080LSS0")[0].korinish == "LG (ARUN080LSS0)"


def test_biz_sotadigan_brend_begona_EMAS():
    assert begona_brendlar("Daikin VRV", istisno={"Daikin"}) == []


def test_bosh_matn():
    assert begona_brendlar("") == []

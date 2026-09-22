"""Ism transliteratsiyasi — ruscha KP da kirill, o'zbekchada lotin.

Ruscha blankada lotincha ism begona ko'rinadi:
    Менеджер: Aziz Karimov     <- xato
    Менеджер: Азиз Каримов     <- to'g'ri
"""

from __future__ import annotations

import pytest

from kp.harf import kirilga, lotinga, moslash, yozuvi

# Aylanma sinov uchun: lotin -> kiril -> lotin asliga qaytishi kerak.
ISMLAR = [
    ("Aziz Karimov", "Азиз Каримов"),
    ("Shuhrat Yo'ldoshev", "Шуҳрат Йўлдошев"),
    ("G'ulom Rahimov", "Ғулом Раҳимов"),
    ("Erkin Nurmatov", "Эркин Нурматов"),
    ("O'tkir Xoshimov", "Ўткир Хошимов"),
    ("Feruza Qodirova", "Феруза Қодирова"),
    ("Jasur Tursunov", "Жасур Турсунов"),
    ("Nilufar Yusupova", "Нилуфар Юсупова"),
    ("Sardor Ne'matov", "Сардор Неъматов"),
    ("Malika Choriyeva", "Малика Чориева"),
]


@pytest.mark.parametrize("lotin,kiril", ISMLAR)
def test_lotindan_kirilga(lotin, kiril):
    assert kirilga(lotin) == kiril


@pytest.mark.parametrize("lotin,kiril", ISMLAR)
def test_kirildan_lotinga(lotin, kiril):
    assert lotinga(kiril) == lotin


@pytest.mark.parametrize("lotin,_", ISMLAR)
def test_aylanma_asliga_qaytadi(lotin, _):
    """O'girib-qaytarganda ism buzilmasin."""
    assert lotinga(kirilga(lotin)) == lotin


def test_yo_apostrof_alohida_qoida():
    """"yo'" birikmasi: "Ёъ" emas, "Йў" bo'lishi kerak.

    "yo" digrafi "o'" dan oldin ushlanib qolsa, familiya buziladi.
    """
    assert kirilga("Yo'ldoshev") == "Йўлдошев"
    assert kirilga("yo'l") == "йўл"


def test_soz_boshidagi_e():
    """Erkin -> Эркин (э), lekin Ergashev ichidagi "e" -> е."""
    assert kirilga("Erkin") == "Эркин"
    assert kirilga("Dilshod Ergashev") == "Дилшод Эргашев"


def test_unlidan_keyingi_e_ye_boladi():
    """Чориева -> Choriyeva, Чориeва emas."""
    assert lotinga("Чориева") == "Choriyeva"
    assert lotinga("Елена") == "Yelena"
    # Undoshdan keyin oddiy "e".
    assert lotinga("Эргашев") == "Ergashev"


def test_turli_tutuq_belgilari():
    """Word, klaviatura va nusxa-ko'chirish har xil apostrof qoldiradi."""
    for tutuq in "'‘’ʻʼ`":
        assert kirilga(f"O{tutuq}tkir") == "Ўткир"


def test_allaqachon_togri_alifboda_bolsa_tegilmaydi():
    assert kirilga("Азиз Каримов") == "Азиз Каримов"
    assert lotinga("Aziz Karimov") == "Aziz Karimov"


def test_bosh_harf_saqlanadi():
    assert kirilga("aziz karimov") == "азиз каримов"
    assert kirilga("Aziz Karimov") == "Азиз Каримов"


def test_bosh_matn_va_none():
    assert kirilga("") == ""
    assert lotinga("") == ""
    assert moslash("", "ru") == ""
    assert moslash(None, "ru") == ""


def test_yozuvi_aniqlaydi():
    assert yozuvi("Aziz") == "lotin"
    assert yozuvi("Азиз") == "kiril"
    assert yozuvi("12345") == "nomalum"


# --- KP tiliga moslash --------------------------------------------------------


def test_ruscha_kp_kirill_oladi():
    assert moslash("Aziz Karimov", "ru") == "Азиз Каримов"


def test_ozbekcha_kp_lotin_oladi():
    assert moslash("Азиз Каримов", "uz") == "Aziz Karimov"


def test_togri_alifbo_kelsa_ozgarmaydi():
    assert moslash("Азиз Каримов", "ru") == "Азиз Каримов"
    assert moslash("Aziz Karimov", "uz") == "Aziz Karimov"


def test_qolda_yozilgani_ustun():
    """ENG MUHIM: pasportdagi yozuvni avtomatika bosib ketmasin.

    "Шухрат" ni "Shuhrat" ham, "Shukhrat" ham deb yozish mumkin —
    qaysi biri to'g'riligini faqat egasi biladi.
    """
    xodim = {"ism": "Shukhrat Yuldashev", "ism_kiril": "Шухрат Юлдашев"}
    assert moslash(xodim["ism"], "ru", xodim) == "Шухрат Юлдашев"

    xodim2 = {"ism": "Шухрат Юлдашев", "ism_lotin": "Shukhrat Yuldashev"}
    assert moslash(xodim2["ism"], "uz", xodim2) == "Shukhrat Yuldashev"


def test_qolda_yozilgani_bosh_bolsa_avtomatik_ishlaydi():
    xodim = {"ism": "Aziz Karimov", "ism_kiril": "   "}
    assert moslash(xodim["ism"], "ru", xodim) == "Азиз Каримов"


def test_notogri_tilda_lotin_beriladi():
    """Kutilmagan til qiymati kelsa — o'zbekcha (lotin) standart."""
    assert moslash("Азиз Каримов", "en") == "Aziz Karimov"
    assert moslash("Азиз Каримов", "") == "Aziz Karimov"


# --- rekvizitlar.yaml qatlami -------------------------------------------------


def test_menejerlar_qoshimcha_maydonni_saqlaydi(tmp_path, monkeypatch):
    """`ism_kiril` yuklashda tushib qolmasin."""
    import kp.narx as narx

    fayl = tmp_path / "rekvizitlar.yaml"
    fayl.write_text(
        "nomi: Test\n"
        "menejerlar:\n"
        '  "111":\n'
        '    ism: "Aziz Karimov"\n'
        '    telefon: "+998901234567"\n'
        '    ism_kiril: "Азиз Каримов-Юсупов"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(narx, "REKVIZIT_FAYLI", fayl)
    narx.keshni_tozala()

    xodim = narx.menejerlar()["111"]
    assert xodim["ism_kiril"] == "Азиз Каримов-Юсупов"
    assert moslash(xodim["ism"], "ru", xodim) == "Азиз Каримов-Юсупов"

    narx.keshni_tozala()


def test_fayl_tahrirlansa_qayta_oqiladi(tmp_path, monkeypatch):
    """Administrator YAML ga menejer qo'shsa, tizim qayta yoqilmasin.

    Ilgari `lru_cache` bir marta o'qib qo'yardi va yangi menejer faqat
    tizim qayta ishga tushgach ko'rinardi.
    """
    import time

    import kp.narx as narx

    fayl = tmp_path / "rekvizitlar.yaml"
    fayl.write_text(
        'nomi: Test\nmenejerlar:\n  "111":\n    ism: "Birinchi Xodim"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        narx, "_ozgarish_belgisi", lambda f: fayl.stat().st_mtime
    )
    monkeypatch.setattr(narx, "_yukla", lambda f: __import__("yaml").safe_load(
        fayl.read_text(encoding="utf-8")
    ))
    narx.keshni_tozala()

    assert set(narx.menejerlar()) == {"111"}

    time.sleep(0.05)
    fayl.write_text(
        'nomi: Test\nmenejerlar:\n'
        '  "111":\n    ism: "Birinchi Xodim"\n'
        '  "222":\n    ism: "Ikkinchi Xodim"\n',
        encoding="utf-8",
    )

    assert set(narx.menejerlar()) == {"111", "222"}
    narx.keshni_tozala()

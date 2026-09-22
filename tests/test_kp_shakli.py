"""KP savol-javob shakli — mantiq, Telegramsiz.

Bu yerdagi testlar shaklning UCH xususiyatini qo'riqlaydi:

  1. Javob TAXMIN qilinmaydi — tushunarsiz javobda savol kuchda qoladi.
  2. Yo'l tanlanishi savollar ro'yxatini o'zgartiradi (model / obyekt).
  3. Tanlovlar normalar faylidan olinadi — ro'yxat ikki joyda turmasin.
"""

from __future__ import annotations

import pytest

from kp.shakl import (
    YO_L_MODEL,
    YO_L_OBYEKT,
    Shakl,
    ShaklXatosi,
    mahsulot_royxati,
    olcham_balandlik,
    savollar,
)

# --- javob tekshiruvi ---------------------------------------------------------


@pytest.mark.parametrize("matn,maydon,balandlik", [
    ("250 kv, 3 metr", 250.0, 3.0),
    ("250 3", 250.0, 3.0),
    ("1000 kv.m 5 m", 1000.0, 5.0),
    ("250,5 kv 3,2 metr", 250.5, 3.2),
])
def test_olcham_har_xil_yozilishda_oqiladi(matn, maydon, balandlik):
    """Menejer shoshib yozadi — format qat'iy bo'lmasligi kerak."""
    assert olcham_balandlik(matn) == {"maydon": maydon, "balandlik": balandlik}


def test_bitta_raqam_berilsa_SORALADI():
    """Taxmin qilmaymiz: balandlik 3 m deb o'ylab qo'yish xato bo'lardi."""
    with pytest.raises(ShaklXatosi, match="Ikkita raqam"):
        olcham_balandlik("250 kv")


def test_balandlik_maydondan_katta_bolsa_OGOHLANTIRADI():
    """«3 metr, 250 kv» — tartib almashib ketgan, jim qabul qilmaymiz."""
    with pytest.raises(ShaklXatosi, match="juda katta"):
        olcham_balandlik("3 250")


def test_mahsulot_royxati_miqdor_bilan():
    natija = mahsulot_royxati("ВКП 40х20-4E20 — 4 dona\nРВН 300х300 - 12 dona")

    assert natija == [
        {"nomi": "ВКП 40х20-4E20", "miqdor": 4.0, "birlik": "dona"},
        {"nomi": "РВН 300х300", "miqdor": 12.0, "birlik": "dona"},
    ]


def test_miqdorsiz_qator_bitta_deb_olinadi():
    """Menejer KP da miqdorni ko'radi va tuzata oladi — bu xavfsiz standart."""
    assert mahsulot_royxati("ВК-250П")[0]["miqdor"] == 1.0


def test_bosh_royxat_qabul_qilinmaydi():
    with pytest.raises(ShaklXatosi):
        mahsulot_royxati("   \n  ")


# --- shakl oqimi --------------------------------------------------------------


def _tolgan_obyekt() -> Shakl:
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "250 kv, 3 metr", "ofis", "20",
                  "yoq", "kirish", "yoq", "40", "__tayyor__"):
        shakl.javob_ber(javob)
    shakl.otkaz()          # yetkazish
    shakl.otkaz()          # maxsus shartlar
    return shakl


def test_obyekt_yoli_toliq_toladi():
    shakl = _tolgan_obyekt()

    assert shakl.tugadimi()
    assert shakl.javoblar["olcham"] == {"maydon": 250.0, "balandlik": 3.0}
    assert shakl.javoblar["xona_turi"] == "ofis"
    assert shakl.javoblar["uskunalar"] == []
    assert shakl.javoblar["yonalish"] == "kirish"


def test_yonalish_MAJBURIY():
    """Yo'nalish nechta ventilyator kerakligini belgilaydi — taxmin qilinmaydi.

    Kirish + chiqish tizimida ikkita ventilyator kerak. Bu savol
    qo'shilgunga qadar KP ga har doim BITTA ventilyator tushardi.
    """
    savol = next(s for s in savollar() if s.kalit == "yonalish")

    assert not savol.otkazsa_boladi
    assert {t.qiymat for t in savol.tanlovlar} == {"kirish", "chiqish", "ikkalasi"}


def test_yonalish_faqat_OBYEKT_yolida_soraladi():
    """Model nomi aytilgan bo'lsa, miqdorni menejer o'zi yozadi."""
    savol = next(s for s in savollar() if s.kalit == "yonalish")

    assert savol.shart is not None
    assert savol.shart({"yol": YO_L_OBYEKT}) is True
    assert savol.shart({"yol": YO_L_MODEL}) is False


def test_model_yolida_obyekt_savollari_BERILMAYDI():
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber(YO_L_MODEL)

    berilgan = []
    while not shakl.tugadimi():
        savol = shakl.joriy()
        berilgan.append(savol.kalit)
        if savol.kalit == "mahsulotlar":
            shakl.javob_ber("ВК-250П — 5 dona")
        else:
            shakl.otkaz()

    assert "mahsulotlar" in berilgan
    assert "olcham" not in berilgan
    assert "xona_turi" not in berilgan


def test_notogri_javobda_savol_KUCHDA_QOLADI():
    """Eng muhim qoida: xato javob bilan davom etmaymiz."""
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber(YO_L_OBYEKT)

    with pytest.raises(ShaklXatosi):
        shakl.javob_ber("bilmayman")

    assert shakl.joriy().kalit == "olcham"      # o'sha savol turibdi


def test_tanlovni_raqam_bilan_ham_tanlash_mumkin():
    """Telegramda tugma bosiladi, lekin qo'lda «2» deb yozish ham ishlasin."""
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber("2")

    assert shakl.javoblar["yol"] == YO_L_OBYEKT


def test_majburiy_savolni_otkazib_bolmaydi():
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")

    with pytest.raises(ShaklXatosi, match="o'tkazib bo'lmaydi"):
        shakl.otkaz()       # "Nima kerak?" — o'tkazib bo'lmaydi


def test_qadam_hisobi_ortga_ketmaydi():
    """«1/4» dan «3/8» ga sakrash menejerni chalkashtirardi."""
    shakl = Shakl()
    jamilar = []
    for javob in ("Sinov MChJ", YO_L_MODEL):
        jamilar.append(shakl.qadam()[1])
        shakl.javob_ber(javob)
    jamilar.append(shakl.qadam()[1])

    assert jamilar[0] == jamilar[1]              # yo'l tanlanmaguncha o'zgarmaydi
    assert jamilar[2] <= jamilar[1]              # faqat KAMAYADI


# --- tanlovlar manbasi --------------------------------------------------------


def test_xona_turlari_normalar_faylidan_olinadi():
    """Ro'yxat ikki joyda turmasin — yamlga qo'shilgan tur shaklda ham chiqsin."""
    from hisob import normalar

    savol = next(s for s in savollar() if s.kalit == "xona_turi")
    qiymatlar = {t.qiymat for t in savol.tanlovlar}

    assert qiymatlar == set(normalar())
    assert "restoran" in qiymatlar               # 2026-08-19 da qo'shilgan


def test_uskuna_tanlovida_BOSIM_KORINADI():
    """Menejer qaysi qism qancha bosim qo'shishini ko'rsin.

    Ilgari bu yerda TO'RTTA tayyor to'plam bor edi va ular bir-birini
    istisno qilardi — «filtr + sovutgich, rekuperatorsiz» mumkin emasdi.
    """
    savol = next(s for s in savollar() if s.kalit == "uskuna")
    qismlar = [t for t in savol.tanlovlar if t.qiymat.startswith("__") is False]

    assert len(qismlar) >= 5
    assert all("Pa" in t.izoh for t in qismlar)


def test_model_nomidagi_raqam_miqdor_deb_oqilmaydi():
    """Haqiqiy xato edi: `ВК-250П` da «250» miqdor deb olinardi.

    Natijasi: KP ga 1 dona o'rniga 250 dona tushardi. Model nomlarida
    tire va raqam ko'p, shuning uchun ajratgich bo'shliq bilan o'ralgan
    bo'lishi yoki miqdordan keyin birlik turishi SHART.
    """
    for nom in ("ВК-250П", "ВЦ 4-75-2,5-1-0,75/3000", "ВКП 40х20-4E20"):
        natija = mahsulot_royxati(nom)
        assert natija[0]["nomi"] == nom
        assert natija[0]["miqdor"] == 1.0, nom


@pytest.mark.parametrize("qator,nomi,miqdor", [
    ("ВК-250П — 5 dona", "ВК-250П", 5.0),
    ("ВК-250П 5 dona", "ВК-250П", 5.0),
    ("РВН 300х300: 12 шт", "РВН 300х300", 12.0),
    ("ВЦ 4-75-2,5-1-0,75/3000 2 dona", "ВЦ 4-75-2,5-1-0,75/3000", 2.0),
])
def test_miqdor_har_xil_yozilishda_oqiladi(qator, nomi, miqdor):
    natija = mahsulot_royxati(qator)[0]

    assert natija["nomi"] == nomi
    assert natija["miqdor"] == miqdor


# --- holat diskda saqlanadi ---------------------------------------------------
#
# Menejer 5-savolda turganda bot qayta ishga tushsa, shakl yo'qolmasligi
# kerak — aks holda u boshidan boshlashi kerak bo'ladi.


@pytest.mark.asyncio
async def test_shakl_bot_qayta_ishga_tushsa_ham_saqlanadi(tmp_path):
    from app.baza import Baza

    baza = Baza(tmp_path / "shakl.db")
    await baza.tayyorla()

    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber(YO_L_OBYEKT)
    shakl.javob_ber("250 kv, 3 metr")
    await baza.kp_shakli_yoz(111, shakl.javoblar)

    # "bot qayta ishga tushdi" — butunlay yangi nusxa
    yangi_baza = Baza(tmp_path / "shakl.db")
    saqlangan = await yangi_baza.kp_shakli(111)
    tiklangan = Shakl(javoblar=saqlangan["javoblar"])

    assert tiklangan.javoblar["olcham"] == {"maydon": 250.0, "balandlik": 3.0}
    assert tiklangan.joriy().kalit == "xona_turi"     # o'sha yerdan davom etadi


@pytest.mark.asyncio
async def test_shakl_ochirilsa_yoq(tmp_path):
    from app.baza import Baza

    baza = Baza(tmp_path / "shakl.db")
    await baza.tayyorla()
    await baza.kp_shakli_yoz(222, {"mijoz": "X"})

    await baza.kp_shakli_ochir(222)

    assert await baza.kp_shakli(222) is None


@pytest.mark.asyncio
async def test_har_menejerning_shakli_ALOHIDA(tmp_path):
    from app.baza import Baza

    baza = Baza(tmp_path / "shakl.db")
    await baza.tayyorla()
    await baza.kp_shakli_yoz(111, {"mijoz": "Birinchi"})
    await baza.kp_shakli_yoz(222, {"mijoz": "Ikkinchi"})

    assert (await baza.kp_shakli(111))["javoblar"]["mijoz"] == "Birinchi"
    assert (await baza.kp_shakli(222))["javoblar"]["mijoz"] == "Ikkinchi"


def test_STIR_va_obyekt_MODELDA_saqlanadi():
    """Shaklda so'ralmaydi, lekin TZ faylidan bepul olinadi."""
    from kp.model import Mijoz

    mijoz = Mijoz(nomi="TOY MCHJ", inn="123456789", obyekt="Chilonzor SM")

    assert mijoz.inn == "123456789"
    assert mijoz.obyekt == "Chilonzor SM"


# --- xona halqasi -------------------------------------------------------------
#
# Hisob qismi ko'p xonani ko'taradi, lekin menejerda unga YO'L yo'q edi:
# ko'p xonali obyekt faqat TZ fayli orqali kelardi. Endi shaklning
# o'zida "yana xona" tugmasi bor.


def _kop_xonali() -> Shakl:
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT,
                  "1200 kv, 4.5 m", "dokon", "300", "ha",
                  "450 kv, 6 m", "ombor", "5", "yoq",
                  "ikkalasi", "yoq", "40", "__tayyor__"):
        shakl.javob_ber(javob)
    return shakl


def test_yana_xona_SAVOLLARNI_QAYTARADI():
    """«Ha» bosilsa o'lcham va tur yangi xona uchun qaytadan so'raladi."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "1200 kv, 4.5 m", "dokon", "300"):
        shakl.javob_ber(javob)

    shakl.javob_ber("ha")

    assert shakl.joriy().kalit == "olcham", "o'lcham qayta so'ralmadi"


def test_xonalar_ROYXATGA_yigiladi():
    shakl = _kop_xonali()

    xonalar = shakl.javoblar["xonalar"]
    assert len(xonalar) == 2
    assert xonalar[0]["maydon"] == 1200 and xonalar[0]["turi"] == "dokon"
    assert xonalar[1]["maydon"] == 450 and xonalar[1]["turi"] == "ombor"


def test_yoq_bosilsa_OXIRGI_xona_ham_qoshiladi():
    """«Yo'q» — halqa tugadi, lekin joriy xona yo'qolmasligi kerak."""
    shakl = _kop_xonali()

    assert shakl.javoblar["xonalar"][-1]["turi"] == "ombor"


def test_bitta_xona_ham_ROYXATGA_tushadi():
    """Bitta xonada ham hisob bir xil yo'ldan ketsin."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "250 kv, 3 m", "ofis", "20", "yoq"):
        shakl.javob_ber(javob)

    assert len(shakl.javoblar["xonalar"]) == 1


def test_xona_belgisi_SAKRASHNI_tushuntiradi():
    """Halqada qadam ORQAGA ketadi (6/12 -> 3/12).

    Xona raqamisiz bu «ish orqaga ketdi» bo'lib ko'rinardi.
    """
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "1200 kv, 4.5 m", "dokon", "300"):
        shakl.javob_ber(javob)
    shakl.javob_ber("ha")

    assert shakl.belgi().startswith("2-xona ·")


def test_birinchi_xonada_belgi_ODDIY():
    """Bitta xonali oddiy KP da «1-xona» yozuvi ortiqcha shovqin."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT):
        shakl.javob_ber(javob)

    assert "xona ·" not in shakl.belgi()


def test_yana_xona_faqat_OBYEKT_yolida():
    savol = next(s for s in savollar() if s.kalit == "yana_xona")

    assert savol.shart({"yol": YO_L_OBYEKT}) is True
    assert savol.shart({"yol": YO_L_MODEL}) is False


def test_xona_soni_CHEKLANGAN():
    """Cheksiz halqa bo'lmasin — 15 tadan ko'pi alohida loyiha."""
    from kp.shakl import MAKS_XONA

    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber(YO_L_OBYEKT)
    for _ in range(MAKS_XONA + 3):
        if shakl.joriy() is None or shakl.joriy().kalit != "olcham":
            break
        shakl.javob_ber("100 kv, 3 m")
        shakl.javob_ber("ofis")
        shakl.javob_ber("10")
        shakl.javob_ber("ha")

    assert len(shakl.javoblar["xonalar"]) <= MAKS_XONA


# --- ORQAGA tugmasi -----------------------------------------------------------
#
# Shakl 12 qadamdan iborat. Menejer o'rtada xato tugma bosib qo'ysa,
# ilgari butun KP ni `/bekor` qilib boshidan boshlashi kerak edi.


def test_orqaga_oxirgi_javobni_BEKOR_qiladi():
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")
    shakl.javob_ber(YO_L_OBYEKT)

    assert shakl.orqaga() is True
    assert shakl.joriy().kalit == "yol"
    assert "yol" not in shakl.javoblar


def test_boshida_orqaga_qaytadigan_joy_YOQ():
    assert Shakl().orqaga() is False


def test_orqaga_USKUNA_tanlovini_bittalab_oladi():
    """Uskuna halqasida javob ro'yxatda — oxirgi TANLOV olib tashlanadi."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "250 kv, 3 m", "ofis", "20",
                  "yoq", "kirish", "yoq", "40", "filtr", "sovutgich"):
        shakl.javob_ber(javob)

    shakl.orqaga()

    assert shakl.javoblar["uskunalar"] == ["filtr"]
    assert shakl.joriy().kalit == "uskuna"       # o'sha savolda qolamiz


def test_orqaga_XONANI_shaklga_qaytaradi():
    """«Ha» bosib yangi xona boshlangan — oldingisi tiklanishi kerak."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "1200 kv, 4.5 m", "dokon",
                  "300", "ha"):
        shakl.javob_ber(javob)

    shakl.orqaga()

    assert shakl.javoblar["olcham"]["maydon"] == 1200
    assert shakl.javoblar["xona_turi"] == "dokon"
    assert not shakl.javoblar.get("xonalar")


def test_orqaga_YOL_ozgarsa_eski_javoblar_tozalanadi():
    """Model yo'liga o'tilsa, obyekt javoblari qolib ketmasin."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "250 kv, 3 m", "ofis", "20", "yoq"):
        shakl.javob_ber(javob)

    while shakl.joriy() is None or shakl.joriy().kalit != "yol":
        if not shakl.orqaga():
            break

    assert "olcham" not in shakl.javoblar
    assert "xonalar" not in shakl.javoblar
    assert "xona_turi" not in shakl.javoblar


def test_orqaga_keyin_boshqa_javob_berish_mumkin():
    """Eng muhimi: orqaga qaytib, TUZATIB davom etish."""
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "250 kv, 3 m", "ofis"):
        shakl.javob_ber(javob)

    shakl.orqaga()                    # "ofis" bekor qilindi
    shakl.javob_ber("ombor")          # to'g'risi yozildi

    assert shakl.javoblar["xona_turi"] == "ombor"


def test_STIR_va_obyekt_HUJJATGA_yozilmaydi():
    """Murojaat bloki namunaviy blankada faqat «Rahbariga» + tashkilot.

    STIR shartnoma va hisob-fakturaga tegishli, KP sarlavhasiga emas.
    Ma'lumot SAQLANADI — menejer so'ragani bekorga ketmaydi.
    """
    from datetime import date
    from kp.hujjat import _jadval_malumoti
    from kp.model import KP, Mijoz, Qator, Shartlar

    kp = KP(
        raqam="T", sana=date.today(),
        mijoz=Mijoz(nomi="TOY MCHJ", inn="123456789", obyekt="Chilonzor SM"),
        qatorlar=[Qator(nomi="x", miqdor=1, birlik_narx=100.0, qqs_foizi=12)],
        shartlar=Shartlar(), rekvizitlar={}, qqs_foizi=12.0, til="uz",
    )
    jadval, _ = _jadval_malumoti(kp)

    matn = " ".join(k for q in jadval for k in q)
    assert "123456789" not in matn
    # Ma'lumot modelda TURADI — shartnoma bosqichida kerak bo'ladi.
    assert kp.mijoz.inn == "123456789"
    assert kp.mijoz.obyekt == "Chilonzor SM"


# --- gapirib berilgan javob (ovozli xabar) ------------------------------------
#
# JONLI XATO (2026-09-05): menejer ovozli xabar yubordi —
# «Obyekt tasvirlayman, obyekt 250 metr kvadrat, balandligi 3 metr» —
# va «Variantlardan birini tanlang» degan javob oldi. Javob AYTILGAN
# edi, lekin tanlov faqat AYNAN teng matnni qabul qilardi.


def yol_savoli():
    from kp.shakl import YO_L_MODEL, YO_L_OBYEKT, Savol, Tanlov

    return Savol(kalit="yol", matn="Nima kerak?", tanlovlar=(
        Tanlov(YO_L_MODEL, "Model nomini bilaman", ""),
        Tanlov(YO_L_OBYEKT, "Obyektni tasvirlayman", ""),
    ))


def test_gap_ichidagi_javob_tushuniladi():
    from kp.shakl import YO_L_OBYEKT, _tanlovni_top

    tanlov = _tanlovni_top(
        yol_savoli(),
        "Obyekt tasvirlayman, obyekt 250 metr kvadrat, balandligi 3 metr.")
    assert tanlov is not None and tanlov.qiymat == YO_L_OBYEKT


def test_qoshimchasiz_shakl_ham_tushuniladi():
    """«Obyekt tasvirlayman» va «Obyektni tasvirlayman» — bir xil."""
    from kp.shakl import YO_L_OBYEKT, _tanlovni_top

    tanlov = _tanlovni_top(yol_savoli(), "obyekt tasvirlayman")
    assert tanlov is not None and tanlov.qiymat == YO_L_OBYEKT


def test_INKOR_teskari_tanlanmaydi():
    """«Model nomini BILMAYMAN» — bu «bilaman» EMAS.

    Eng muhim himoya: inkorni tasdiq deb tushunish, savolni qayta
    berishdan ancha yomon.
    """
    from kp.shakl import _tanlovni_top

    assert _tanlovni_top(yol_savoli(), "model nomini bilmayman") is None


def test_IKKALASI_uchrasa_taxmin_qilinmaydi():
    """Noaniqlik — savol qayta beriladi, tanlov o'ylab topilmaydi."""
    from kp.shakl import _tanlovni_top

    assert _tanlovni_top(
        yol_savoli(), "modelni bilaman va obyektni ham tasvirlayman") is None


def test_aloqasiz_matn_tanlov_qilmaydi():
    from kp.shakl import _tanlovni_top

    assert _tanlovni_top(yol_savoli(), "bilmadim") is None
    assert _tanlovni_top(yol_savoli(), "salom") is None


def test_aniq_teng_va_raqam_ISHLAYVERADI():
    """Eski yo'llar buzilmagan."""
    from kp.shakl import YO_L_MODEL, YO_L_OBYEKT, _tanlovni_top

    savol = yol_savoli()
    assert _tanlovni_top(savol, "obyekt").qiymat == YO_L_OBYEKT
    assert _tanlovni_top(savol, "Model nomini bilaman").qiymat == YO_L_MODEL
    assert _tanlovni_top(savol, "1").qiymat == YO_L_MODEL
    assert _tanlovni_top(savol, "2").qiymat == YO_L_OBYEKT


# --- bir nafasda aytilgan javob -----------------------------------------------
#
# Ovozli xabarda odam hammasini birdan aytadi. Yo'l tanlangach, o'sha
# xabardagi o'lchamni QAYTA so'rash ortiqcha — u allaqachon aytilgan.


def yolgacha():
    """Shaklni «yol» savoligacha olib boradi."""
    from kp.shakl import Shakl

    s = Shakl()
    while s.joriy() and s.joriy().kalit != "yol":
        s.otkaz()
    return s


def test_olcham_ayni_xabardan_olinadi():
    s = yolgacha()
    s.javob_ber("Obyekt tasvirlayman, obyekt 250 metr kvadrat, "
                "balandligi 3 metr. Shunga ventilyatsiya kerak.")

    assert s.javoblar["olcham"] == {"maydon": 250.0, "balandlik": 3.0}
    assert s.joriy().kalit == "xona_turi", "o'lcham qayta so'ralyapti"


def test_model_royxati_ayni_xabardan_olinadi():
    s = yolgacha()
    s.javob_ber("Model nomini bilaman, ВКП 40х20-4E20 — 4 dona")

    mahsulotlar = s.javoblar["mahsulotlar"]
    assert len(mahsulotlar) == 1
    # Tanlov so'zlari nomga TUSHMASLIGI kerak — aks holda KP ga
    # «Model nomini bilaman, ВКП…» bo'lib chiqardi.
    assert mahsulotlar[0]["nomi"] == "ВКП 40х20-4E20"
    assert mahsulotlar[0]["miqdor"] == 4.0


def test_raqamsiz_javobda_savol_ODATDAGIDEK_beriladi():
    for javob in ("Obyektni tasvirlayman", "obyekt", "2"):
        s = yolgacha()
        s.javob_ber(javob)
        assert s.javoblar.get("olcham") is None, javob
        assert s.joriy().kalit == "olcham", javob


def test_RAQAMLAR_keyingi_savolga_OQIB_KETMAYDI():
    """«250 kv, 3 metr» dagi 250 «necha kishi?» ga tushmasligi kerak.

    Faqat BITTA qadam oldinga to'ldiriladi — aks holda bitta raqam
    bir necha savolga tarqab ketardi.
    """
    s = yolgacha()
    s.javob_ber("obyekt tasvirlayman, 250 kv, 3 metr")
    s.javob_ber("ofis")                      # xona_turi

    assert s.joriy().kalit == "odamlar"
    assert s.javoblar.get("odamlar") is None


def test_tanlov_sozlari_qoldiqdan_olib_tashlanadi():
    from kp.shakl import YO_L_MODEL, Tanlov, _tanlovsiz

    tanlov = Tanlov(YO_L_MODEL, "Model nomini bilaman", "")
    assert _tanlovsiz(tanlov, "Model nomini bilaman, ВКП 40х20 — 4 dona") == (
        "ВКП 40х20 — 4 dona")


def test_tugma_bosilganda_qoldiq_yoq():
    """Tugma bosilsa qo'shimcha matn bo'lmaydi — hech narsa buzilmasin."""
    s = yolgacha()
    s.javob_ber("obyekt")
    assert s.javoblar["yol"] == "obyekt"
    assert s.javoblar.get("olcham") is None

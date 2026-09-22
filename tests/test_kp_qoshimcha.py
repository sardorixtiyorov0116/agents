"""Tarmoq turiga bog'liq qo'shimcha uskunalar — `kp/shakldan.py`.

NEGA BU TESTLAR BOR
-------------------
Jonli holat (2026-08-21): 500 m² restoranga `/kp` BITTA ventilyator
chiqardi. Menejer "kanalli tizim, panjaralar bilan" ni tanlagan edi,
lekin KP da panjara ham, isitgich ham yo'q edi — tanlov nomi bilan
hujjat mazmuni bir-biriga ZID bo'lib qoldi.

Bu yerda qo'riqlanadigan to'rt qoida:

  1. Tanlangan tarmoq turi talab qiladigan uskuna KP ga QO'SHILADI.
  2. Katalog qamrovi yetmasa — eng kattasi "mayli, shu bo'la qolsin"
     deb OLINMAYDI, ochiq aytiladi.
  3. Panjara soni HISOBLANADI (jonli kesim yuzasi bo'yicha).
  4. Bu hisobga kirmaydigan qismlar JIM qoldirilmaydi.
"""

from __future__ import annotations

import pytest

from kp.shakldan import (
    TARMOQ_USKUNASI,
    USKUNA_TOIFALARI,
    _qoshimcha_qatorlar,
    _qoshimcha_tanla,
    _uskuna_tanla,
    _ventilyatormi,
)

# Haqiqiy katalogdagi qamrovga o'xshatilgan: isitgich KICHIK obyektlargacha
# (600-1200), issiqlik almashtirgich esa kattasiga ham yetadi (2000-25000).
# Aynan shu farq tufayli katta obyektda isitgich topilmaydi.
_PARAMETRLAR = {
    "ПВН 500-250-2": {"turi": "Suv bilan ishlaydigan kanalli isitgich ПВН",
                      "havo_sarfi": 600.0},
    "ПВН 600-350-2": {"turi": "Suv bilan ishlaydigan kanalli isitgich ПВН",
                      "havo_sarfi": 1200.0},
    "КСК 113-2-01": {"turi": "Issiqlik almashtirgich KSK", "havo_sarfi": 2000.0},
    "КСК 113-2-11": {"turi": "Issiqlik almashtirgich KSK", "havo_sarfi": 10000.0},
    "ПВФ 40-20-1": {"turi": "Kanalli freonli sovutgich PVF", "havo_sarfi": 400},
    # Ventilyator — qo'shimcha uskuna ro'yxatiga TUSHMASLIGI kerak.
    "ВЦ 4-75-6,3-1": {"turi": "Ventilyator ВЦ 4-75 (isp.1)",
                      "havo_sarfi": [5200, 10500]},
}


def _yig(tarmoq: str, sarf: float):
    """Qo'shimcha qatorlarni yig'adi va ogohlantirishlarni qaytaradi.

    Panjara qatorlari ALOHIDA qaytariladi: ular sarf bo'yicha emas,
    jonli kesim bo'yicha tanlanadi va uskuna testlarini chalkashtiradi.
    """
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": tarmoq}, _PARAMETRLAR, [], sarf, 12000.0, 12.0,
        narxsiz, ogohlantirishlar,
    )
    uskuna = [q for q in qatorlar if not q.nomi.startswith(("РВН", "РВИ"))]
    panjara = [q for q in qatorlar if q.nomi.startswith(("РВН", "РВИ"))]
    return uskuna, ogohlantirishlar, panjara


# --- 1. tanlangan tur talab qilgan uskuna qo'shiladi --------------------------


def test_filtrli_tanlansa_isitgich_QOSHILADI():
    """«filtr va isitgich bilan» deyilgan bo'lsa, isitgich KP da bo'lsin."""
    qatorlar, _, _ = _yig("filtrli", 1000)

    assert [q.nomi for q in qatorlar] == ["ПВН 600-350-2"]


def test_sarf_YETADIGAN_eng_kichigi_olinadi():
    """600 lik isitgich 1000 m³/soat ga yetmaydi — 1200 lik olinishi kerak."""
    qatorlar, _, _ = _yig("filtrli", 1000)

    assert qatorlar[0].nomi == "ПВН 600-350-2"


def test_toliq_tanlansa_sovutgich_va_almashtirgich_QOSHILADI():
    qatorlar, _, _ = _yig("toliq", 400)

    assert {q.nomi for q in qatorlar} == {"ПВФ 40-20-1", "КСК 113-2-01"}


def test_oddiy_tarmoqda_qoshimcha_uskuna_YOQ():
    """Qisqa, uskunasiz kanalga isitgich tiqishtirilmaydi."""
    qatorlar, ogohlantirishlar, _ = _yig("oddiy", 1000)

    assert qatorlar == []
    assert ogohlantirishlar == []


# --- 2. katalog qamrovi yetmasa — taxmin qilinmaydi ---------------------------


def test_bittasi_yetmasa_PARALLEL_qoyiladi():
    """JONLI SAVOL (2026-08-26): «1200 likdan 15 ta qilsa bo'lmaydimi?»

    Bo'ladi va bu to'g'ri: katta tizim baribir bir necha tarmoqqa
    bo'linadi. Ilgari bu holatda qator umuman qo'yilmasdi va menejer
    KP ni qo'lda to'ldirardi.
    """
    qatorlar, ogohlantirishlar, _ = _yig("filtrli", 8400)

    isitgich = [q for q in qatorlar if q.nomi.startswith("ПВН")]
    assert len(isitgich) == 1
    assert isitgich[0].miqdor == 7          # 8400 / 1200
    assert any("PARALLEL" in o for o in ogohlantirishlar)


def test_parallel_qoyilganda_SABABI_aytiladi():
    """Menejer «nega 7 dona?» deb hayron bo'lmasin."""
    _, ogohlantirishlar, _ = _yig("filtrli", 8400)

    assert any("1200" in o and "8400" in o for o in ogohlantirishlar)
    assert any("tarmoqqa bo'linishi" in o for o in ogohlantirishlar)


def test_toifa_umuman_yoq_bolsa_ham_aytiladi():
    """Katalogda bunday toifa bo'lmasa, KP jim qolmasin."""
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "filtrli"}, {"КСК 113-2-01": _PARAMETRLAR["КСК 113-2-01"]},
        [], 1000, 12000.0, 12.0, narxsiz, ogohlantirishlar,
    )

    uskuna = [q for q in qatorlar if not q.nomi.startswith(("РВН", "РВИ"))]
    assert uskuna == []
    assert any("topilmadi" in o for o in ogohlantirishlar)


# --- 3. katalogda yo'q qismlar ochiq aytiladi ---------------------------------


def test_kanalli_tanlansa_PANJARA_QOSHILADI():
    """«panjaralar bilan» deyilgan — panjara KP da qator bo'lib chiqsin.

    XATO TUZATILDI: ilgari bu yerda "panjara katalogda yo'q" deb
    ogohlantirish chiqardi. Tekshirilganda РВН/РВИ oilalari NARXI
    BILAN backendda turgani aniqlandi (har biri 64 o'lcham). Ular
    `havo_sarfi` maydoniga ega emas, shuning uchun `_uskuna_tanla`
    ularni ko'rmagan va "yo'q" degan noto'g'ri xulosa chiqqan edi.
    """
    _, _, panjara = _yig("kanalli", 1000)

    assert len(panjara) == 1
    assert panjara[0].nomi.startswith("РВН")
    assert panjara[0].miqdor >= 2       # bitta panjara havoni taqsimlamaydi


def test_oddiy_tarmoqda_panjara_YOQ():
    """Qisqa, devordan devorga kanalga panjara tarmog'i qo'yilmaydi."""
    _, _, panjara = _yig("oddiy", 1000)

    assert panjara == []


def test_kirish_chiqishda_IKKI_XIL_panjara():
    """Kirishga РВН, chiqishga РВИ — ular bir-birining o'rnini bosmaydi.

    РВИ teskari klapanli: jalyuzi havo oqimi bilan ochiladi. Kirish
    tarmog'iga qo'yilsa umuman ochilmaydi (katalog 2021, 228-sahifa).
    """
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "ikkalasi"}, _PARAMETRLAR, [],
        14000, 12000.0, 12.0, narxsiz, ogohlantirishlar,
    )

    nomlar = [q.nomi.split()[0] for q in qatorlar]
    assert "РВН" in nomlar and "РВИ" in nomlar


def test_chiqish_tizimiga_RVI_qoyiladi():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "chiqish"}, _PARAMETRLAR, [],
        14000, 12000.0, 12.0, narxsiz, [],
    )

    assert all(q.nomi.startswith("РВИ") for q in qatorlar)


def test_yonalish_aytilmasa_KIRISH_deb_olinadi():
    """Eski saqlangan shakllarda bu maydon yo'q — yiqilmasin."""
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli"}, _PARAMETRLAR, [],
        14000, 12000.0, 12.0, narxsiz, [],
    )

    assert all(q.nomi.startswith("РВН") for q in qatorlar)


def test_panjara_soni_sarf_oshsa_KOPAYADI():
    """Panjara soni jonli kesim yuzasidan hisoblanadi, doimiy emas."""
    _, _, kichik = _yig("kanalli", 1000)
    _, _, katta = _yig("kanalli", 40000)

    assert katta[0].miqdor > kichik[0].miqdor


def test_toliq_tanlansa_filtr_va_rekuperator_YOQLIGI_aytiladi():
    _, ogohlantirishlar, _ = _yig("toliq", 400)

    matn = " ".join(ogohlantirishlar)
    assert "filtr" in matn and "rekuperator" in matn


# --- 4. qidiruv DIAMETR bo'yicha emas ----------------------------------------


def test_ventilyator_qoshimcha_uskuna_bolib_TUSHMAYDI():
    """Jonli xato: Ø710 uchun `ДР710` (deflektor) asosiy uskuna bo'lib qolgan.

    Diametr raqamini model nomidan qidirish sinab ko'rilgan va axlat
    bergan (Ø800 ga `ЦН-11-800` — siklon, ya'ni chang tutgich chiqadi).
    Shuning uchun qidiruv TOIFA bo'yicha ketadi va ventilyator hech
    qachon qo'shimcha uskuna ro'yxatiga tushmaydi.
    """
    for tarmoq in TARMOQ_USKUNASI:
        qatorlar, _, _ = _yig(tarmoq, 8000)
        assert all("Ventilyator" not in q.spetsifikatsiya for q in qatorlar)
        assert all(q.nomi != "ВЦ 4-75-6,3-1" for q in qatorlar)


def test_toifa_belgisi_haqiqiy_katalog_nomlariga_MOS():
    """Belgilar `turi` maydonidagi matnga mos kelmasa, hech narsa topilmaydi.

    Bu jimgina buziladi: KP ga uskuna qo'shilmaydi va sababi ko'rinmaydi.
    """
    for belgi, _nomi in USKUNA_TOIFALARI.values():
        assert any(belgi in (y.get("turi") or "") for y in _PARAMETRLAR.values()), belgi


def test_har_tarmoq_turi_royxatda_BOR():
    """`hisob/bosim.py` ga yangi tur qo'shilsa, bu yerda ham hisobga olinsin."""
    from hisob.bosim import TIPIK_TARMOQ

    assert set(TARMOQ_USKUNASI) == set(TIPIK_TARMOQ)


def test_sarf_yetmasa_ENG_KATTASIDAN_parallel():
    model, soni, eng_katta = _qoshimcha_tanla(_PARAMETRLAR, "ПВН", 8400)

    assert model == "ПВН 600-350-2"     # eng kattasi
    assert soni == 7                     # ceil(8400 / 1200)
    assert eng_katta == 1200.0


# --- 5. ASOSIY uskuna faqat ventilyator bo'ladi -------------------------------


def test_isitgich_ASOSIY_uskuna_bolib_qolmaydi():
    """Jonli xato: 600 m³/soat ga asosiy uskuna `ПВН 500-250-2` tanlangan.

    Isitgichda `havo_sarfi` bor, `bosim` esa `None` — shuning uchun u
    sarf filtridan ham, bosim filtridan ham o'tib ketardi va narxi
    arzonroq bo'lgani uchun ventilyatordan OLDIN turardi. Mijozga
    ventilyator o'rniga isitgich sotilardi.
    """
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "ПВН 500-250-2", "price": 10.0},
        {"in_model_name": "КСК 113-2-01", "price": 20.0},
    ]}]}]

    natija = _uskuna_tanla(_PARAMETRLAR, katalog, 600, 12000.0, (500, 900))

    assert natija == []


def test_ventilyator_toifalari_TANILADI():
    """Katalogdagi barcha ventilyator nomlanishi qamrab olinsin."""
    for turi in (
        "Ventilyator ВЦ 4-75 (isp.1)",
        "ВК-П ventilyatori",
        "Devorga o‘rnatiladigan ventilyatorlar ВНР-ДУ",
        "Maxsus ventilyator",
        "Radial ventilyator BP",
        "Tortish va puflash mashinalari ДН va ВДН",
    ):
        assert _ventilyatormi({"turi": turi}), turi


def test_ventilyator_BOLMAGAN_toifalar_chetlatiladi():
    for turi in (
        "Suv bilan ishlaydigan kanalli isitgich ПВН",
        "Kanalli freonli sovutgich PVF",
        "Issiqlik almashtirgich KSK",
        "Plastinali shovqin pasaytiruvchi KGP",
        "Teplobmennik КП",
    ):
        assert not _ventilyatormi({"turi": turi}), turi


def test_toifasi_YOQ_yozuv_chetlatilmaydi():
    """Eski yozuvda `turi` bo'lmasligi mumkin — uni yo'qotib qo'ymaymiz.

    Sarf va bosim baribir tekshiriladi, shuning uchun bu xavfsiz.
    """
    assert _ventilyatormi({"havo_sarfi": [1000, 2000]})


# --- 6. faqat so'rishga quriladigan xonalar -----------------------------------


def test_sanuzelga_KIRISH_tarmogi_qoyilmaydi():
    """Sanuzelga havo alohida quvur bilan berilmaydi.

    U yonidagi xonalardan o'zi kiradi — maqsad shu: xonada bosim PAST
    bo'lsin, shunda hid tashqariga chiqmaydi. Kirish tarmog'i qo'yilsa
    bosim ko'tariladi va hid koridorga tarqaladi.

    Normalar faylida `faqat_sorish: true` bilan belgilangan. Menejer
    "kirish + chiqish" ni tanlasa ham, hisob so'rish bo'yicha qilinadi.
    """
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "ikkalasi", "xona_turi": "sanuzel"},
        _PARAMETRLAR, [], 14000, 12000.0, 12.0, narxsiz, ogohlantirishlar,
    )

    assert all(q.nomi.startswith("РВИ") for q in qatorlar), "kirish panjarasi qo'yildi"
    assert any("SO'RISH" in o for o in ogohlantirishlar), "sabab aytilmadi"


def test_oddiy_xonada_kirish_chiqish_OZGARMAYDI():
    """Faqat `faqat_sorish` belgilangan turlarga tegiladi."""
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "ikkalasi", "xona_turi": "ofis"},
        _PARAMETRLAR, [], 14000, 12000.0, 12.0, narxsiz, [],
    )

    nomlar = {q.nomi.split()[0] for q in qatorlar}
    assert nomlar == {"РВН", "РВИ"}


def test_normalar_faylida_sanuzel_belgilangan():
    """Qoida KODDA emas, normalar faylida turishi kerak."""
    from hisob import normalar

    assert normalar()["sanuzel"].get("faqat_sorish") is True
    assert not normalar()["ofis"].get("faqat_sorish")


# --- 7. ko'p xonali obyekt ----------------------------------------------------


def test_kop_xona_sarfi_QOSHILADI():
    """Magistral kanal UMUMIY sarfga qarab o'lchanadi, bitta xonanikiga emas."""
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({"tarmoq": "kanalli", "xonalar": [
        {"nomi": "A", "turi": "ofis", "maydon": 200, "balandlik": 3},
        {"nomi": "B", "turi": "ofis", "maydon": 300, "balandlik": 3},
    ]})

    assert h["kirish_sarfi"] == 1800 + 2700
    assert len(h["xonalar"]) == 2


def test_sanuzel_ALOHIDA_tizim():
    """Sanuzel havosi boshqa xonalar bilan bitta kanalga qo'shilmaydi.

    Aks holda hid butun binoga tarqaladi.
    """
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({"tarmoq": "kanalli", "xonalar": [
        {"nomi": "Ofis", "turi": "ofis", "maydon": 200, "balandlik": 3},
        {"nomi": "Sanuzel", "turi": "sanuzel", "maydon": 30, "balandlik": 3},
    ]})

    assert h["kirish_sarfi"] == 1800          # sanuzel QO'SHILMAGAN
    assert h["sorish_sarfi"] == 900
    assert any("ALOHIDA" in o for o in h["ogohlantirishlar"])


def test_eski_bitta_xonali_shakl_BUZILMAYDI():
    """Saqlangan javoblarda `xonalar` yo'q — ular ham ishlashi kerak."""
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({
        "tarmoq": "kanalli", "olcham": {"maydon": 250, "balandlik": 3},
        "xona_turi": "ofis", "odamlar": 20,
    })

    assert h["sarf"] == 2250
    assert len(h["xonalar"]) == 1


def test_panjara_HAR_XONA_uchun_alohida():
    """KP dan nechta panjara qaysi xonaga ketishi ko'rinib tursin."""
    narxsiz: list[str] = []
    xonalar = [
        {"nomi": "Ofis", "turi": "ofis", "sarf": 1800, "sorish": False},
        {"nomi": "Sanuzel", "turi": "sanuzel", "sarf": 900, "sorish": True},
    ]
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "kirish"}, _PARAMETRLAR, [],
        2700, 12000.0, 12.0, narxsiz, [], xonalar=xonalar,
    )

    matn = " | ".join(q.spetsifikatsiya for q in qatorlar)
    assert "Ofis" in matn and "Sanuzel" in matn


def test_sanuzelga_kirish_panjarasi_QOYILMAYDI():
    """Menejer «kirish» tanlasa ham, sanuzelga so'rish panjarasi qo'yiladi."""
    narxsiz: list[str] = []
    xonalar = [{"nomi": "Sanuzel", "turi": "sanuzel", "sarf": 900, "sorish": True}]
    qatorlar = _qoshimcha_qatorlar(
        {"tarmoq": "kanalli", "yonalish": "kirish"}, _PARAMETRLAR, [],
        900, 12000.0, 12.0, narxsiz, [], xonalar=xonalar,
    )

    assert all(q.nomi.startswith("РВИ") for q in qatorlar)


def test_ARALASH_obyektda_sanuzel_butun_tizimni_ozgartirmaydi():
    """XATO TUZATILDI: sex + sanuzel obyektida sex ham so'rishga o'tardi.

    Sabab: yo'nalish `javoblar["xona_turi"]` ga qarab aniqlanardi.
    Xona halqasi qo'shilgach u OXIRGI kiritilgan xonani saqlaydigan
    bo'ldi — sanuzel oxirida kiritilsa, butun bino so'rish tizimiga
    aylanardi va KP ga ikkita o'rniga bitta ventilyator tushardi.
    """
    narxsiz: list[str] = []
    javoblar = {
        "tarmoq": "kanalli", "yonalish": "ikkalasi",
        "xonalar": [
            {"nomi": "Sex", "turi": "ishlab_chiqarish", "maydon": 350,
             "balandlik": 6, "odamlar": 20},
            {"nomi": "Sanuzel", "turi": "sanuzel", "maydon": 30,
             "balandlik": 3, "odamlar": 1},
        ],
    }
    xonalar = [
        {"nomi": "Sex", "turi": "ishlab_chiqarish", "sarf": 8400, "sorish": False},
        {"nomi": "Sanuzel", "turi": "sanuzel", "sarf": 900, "sorish": True},
    ]
    qatorlar = _qoshimcha_qatorlar(
        javoblar, _PARAMETRLAR, [], 8400, 12000.0, 12.0, narxsiz, [],
        xonalar=xonalar,
    )

    sex = [q for q in qatorlar if "Sex" in q.spetsifikatsiya]
    sanuzel = [q for q in qatorlar if "Sanuzel" in q.spetsifikatsiya]
    # Sexga IKKALA panjara ham (kirish + chiqish), sanuzelga faqat so'rish.
    assert {q.nomi.split()[0] for q in sex} == {"РВН", "РВИ"}
    assert {q.nomi.split()[0] for q in sanuzel} == {"РВИ"}


def test_HAMMA_xona_sorish_bolsa_tizim_sorishga_otadi():
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    javoblar = {"tarmoq": "kanalli", "yonalish": "ikkalasi", "xonalar": [
        {"nomi": "S1", "turi": "sanuzel", "maydon": 30, "balandlik": 3},
    ]}
    qatorlar = _qoshimcha_qatorlar(
        javoblar, _PARAMETRLAR, [], 900, 12000.0, 12.0, narxsiz,
        ogohlantirishlar,
        xonalar=[{"nomi": "S1", "turi": "sanuzel", "sarf": 900, "sorish": True}],
    )

    assert all(q.nomi.startswith("РВИ") for q in qatorlar)
    assert any("SO'RISH" in o for o in ogohlantirishlar)


# --- 8. qismlarni erkin tanlash -----------------------------------------------
#
# Ilgari to'rtta TAYYOR to'plam bor edi va ular bir-birini istisno
# qilardi: «filtr + sovutgich, lekin rekuperatorsiz» mumkin emasdi.


def test_bosim_tanlangan_qismlardan_YIGILADI():
    from kp.shakldan import tanlangan_bosim

    assert tanlangan_bosim({"uskunalar": []}) == (250, 450)
    # filtr 200 + isitgich 120 = 320 qo'shiladi
    assert tanlangan_bosim({"uskunalar": ["filtr", "isitgich"]}) == (570, 770)


def test_ISTALGAN_birikma_mumkin():
    """Eski to'plamlarda bunday variant YO'Q edi."""
    from kp.shakldan import tanlangan_bosim

    faqat_sovutgich = tanlangan_bosim({"uskunalar": ["filtr", "sovutgich"]})
    rekuperator_bilan = tanlangan_bosim(
        {"uskunalar": ["filtr", "sovutgich", "rekuperator"]})

    assert faqat_sovutgich != rekuperator_bilan
    assert rekuperator_bilan[0] - faqat_sovutgich[0] == 250   # rekuperator


def test_qisqa_kanalda_bosim_PAST():
    from kp.shakldan import tanlangan_bosim

    assert tanlangan_bosim({"qisqa_kanal": True, "uskunalar": []}) == (100, 250)


def test_ESKI_shakl_tarmoq_bilan_ishlaydi():
    """Saqlangan javoblarda `tarmoq` turadi — ular buzilmasin."""
    from kp.shakldan import tanlangan_bosim

    assert tanlangan_bosim({"tarmoq": "filtrli"}) == (500, 900)
    assert tanlangan_bosim({"tarmoq": "oddiy"}) == (100, 250)


def test_tanlangan_isitgich_KP_ga_tushadi():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": ["filtr", "isitgich"], "yonalish": "kirish"},
        _PARAMETRLAR, [], 1000, 12000.0, 12.0, narxsiz, [],
    )

    uskuna = [q for q in qatorlar if not q.nomi.startswith(("РВН", "РВИ"))]
    assert [q.nomi for q in uskuna] == ["ПВН 600-350-2"]


def test_rekuperator_tanlansa_HISOBGA_KIRMAGANI_aytiladi():
    """Rekuperator bosimga ta'sir qiladi, lekin KP ga qator bo'lib tushmaydi."""
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    _qoshimcha_qatorlar(
        {"uskunalar": ["rekuperator"], "yonalish": "kirish"},
        _PARAMETRLAR, [], 1000, 12000.0, 12.0, narxsiz, ogohlantirishlar,
    )

    assert any("rekuperator" in o for o in ogohlantirishlar)


def test_qisqa_kanalda_PANJARA_YOQ():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"qisqa_kanal": True, "uskunalar": [], "yonalish": "kirish"},
        _PARAMETRLAR, [], 1000, 12000.0, 12.0, narxsiz, [],
    )

    assert qatorlar == []


# --- 9. hujjat tili -----------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-26): ruscha KP da o'lchov birligi «dona» bo'lib
# chiqardi — jadval sarlavhasi «Ед. изм», ichida o'zbekcha so'z.


def test_ruscha_KP_da_birlik_SHT():
    from kp.shakldan import _birlik

    assert _birlik("ru") == "шт"
    assert _birlik("ru", "dona") == "шт"      # o'zbekchasi tarjima qilinadi


def test_ozbekcha_KP_da_birlik_DONA():
    from kp.shakldan import _birlik

    assert _birlik("uz") == "dona"
    assert _birlik("uz", "шт") == "dona"


def test_maxsus_birlik_OZGARMAYDI():
    """Menejer «kg» yoki «m» yozsa — u tarjima qilinmaydi."""
    from kp.shakldan import _birlik

    assert _birlik("ru", "kg") == "kg"
    assert _birlik("uz", "m") == "m"


def test_ruscha_KP_da_spetsifikatsiya_ham_RUSCHA():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": [], "yonalish": "kirish"}, _PARAMETRLAR, [],
        1000, 12000.0, 12.0, narxsiz, [], til="ru",
    )

    matn = " ".join(q.spetsifikatsiya for q in qatorlar)
    assert "решётка" in matn
    assert "panjara" not in matn, "o'zbekcha matn ruscha hujjatga tushdi"
    assert all(q.birlik == "шт" for q in qatorlar)


def test_ozbekcha_KP_da_spetsifikatsiya_OZBEKCHA():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": [], "yonalish": "kirish"}, _PARAMETRLAR, [],
        1000, 12000.0, 12.0, narxsiz, [], til="uz",
    )

    matn = " ".join(q.spetsifikatsiya for q in qatorlar)
    assert "panjara" in matn
    assert "решётка" not in matn


def test_ikkala_tilda_ham_HAMMA_kalit_bor():
    """Bir tilda qo'shilib, ikkinchisida unutilgan matn bo'lmasin."""
    from kp.shakldan import MATN

    assert set(MATN["uz"]) == set(MATN["ru"])


# --- 10. «ko'proq tanladim — kamroq chiqdi» ------------------------------------


def test_bosim_sababi_AYTILADI():
    """JONLI E'TIROZ (2026-08-26): hamma qismni tanlaganda mahsulot kamayardi.

    Sabab: har qism bosimni oshiradi (hammasi = ~1270 Pa), katalogdagi
    narxli ventilyatorlar esa 600 Pa gacha. Natijada hech narsa mos
    kelmaydi. Sababi aytilmasa menejer buni tushunolmaydi.
    """
    from kp.shakldan import _bosim_sababi

    parametrlar = {
        "ВЦ 4-75-6,3-1": {"turi": "Ventilyator ВЦ 4-75",
                          "havo_sarfi": [5200, 10500], "bosim": [310, 600]},
    }
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "ВЦ 4-75-6,3-1", "price": 500.0},
    ]}]}]
    hisob = {"sarf": 8400, "bosim": (1070, 1270)}

    sabab = _bosim_sababi(parametrlar, katalog, hisob, 12000.0, 12.0)

    assert "BOSIM" in sabab
    assert "1270" in sabab and "600" in sabab
    assert "kamaytirsangiz" in sabab


def test_sarf_aybdor_bolsa_BOSIM_ayblanmaydi():
    """Bosim shartsiz ham hech narsa topilmasa — muammo bosimda emas."""
    from kp.shakldan import _bosim_sababi

    hisob = {"sarf": 999_999, "bosim": (250, 450)}

    assert _bosim_sababi({}, [], hisob, 12000.0, 12.0) == ""


def test_sabab_ISHLATSA_BOLADIGAN_ventilyatorlardan_hisoblanadi():
    """Bosim shifti — KP ga tusha OLADIGAN modellar bo'yicha.

    Narx endi filtr emas, shuning uchun narxsiz model ham hisobga
    kiradi: u ham KP ga tusha oladi (narxi bo'sh qator bilan).
    """
    from kp.shakldan import _bosim_sababi

    parametrlar = {
        "NARXLI": {"turi": "Ventilyator", "havo_sarfi": [5200, 10500],
                   "bosim": [310, 600]},
        "NARXSIZ": {"turi": "Ventilyator", "havo_sarfi": [5000, 12000],
                    "bosim": [700, 900]},
    }
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "NARXLI", "price": 500.0},
    ]}]}]
    hisob = {"sarf": 8400, "bosim": (1070, 1270)}

    sabab = _bosim_sababi(parametrlar, katalog, hisob, 12000.0, 12.0)

    # Eng yuqori shift — 900 Pa (narxsiz model), 600 emas.
    assert "900" in sabab
    assert "1270" in sabab


# --- 11. tanlov NARXGA emas, XARAKTERISTIKAGA qarab ---------------------------


_TANLOV_KATALOG = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
    {"in_model_name": "NARXLI-MOS", "price": 100.0},
    {"in_model_name": "NARXLI-KATTA", "price": 50.0},
]}]}]
_TANLOV_PARAM = {
    # Zaxirasi 25% — MAQBUL oraliqda, narxi bor.
    "NARXLI-MOS": {"turi": "Ventilyator", "havo_sarfi": [800, 1250],
                   "bosim": [300, 500]},
    # Zaxirasi 400% — juda katta, lekin ARZON.
    "NARXLI-KATTA": {"turi": "Ventilyator", "havo_sarfi": [900, 5000],
                     "bosim": [300, 500]},
    # Zaxirasi 10% — eng mosi, lekin NARXI YO'Q.
    "NARXSIZ-ANIQ": {"turi": "Ventilyator", "havo_sarfi": [900, 1100],
                     "bosim": [300, 500]},
}


def test_NARXSIZ_model_ham_tanlanadi():
    """Narx FILTR EMAS: narxsiz model ham KP ga tusha oladi.

    Ilgari narxsizi butunlay chetlatilardi va KP asosiy uskunasiz
    qolardi. To'g'ri uskunali narxsiz KP — uskunasiz KP dan foydaliroq.
    """
    param = {"NARXSIZ-ANIQ": _TANLOV_PARAM["NARXSIZ-ANIQ"]}

    natija = _uskuna_tanla(param, [], 1000, 12000.0, (300, 500), 12.0)

    assert [n["nomi"] for n in natija] == ["NARXSIZ-ANIQ"]
    assert natija[0]["narx_som"] is None


def test_ORTIQCHA_ZAXIRA_kam_bolgani_afzal():
    """Katta ventilyator kichik tizimga — ortiqcha pul, shovqin, elektr.

    `NARXLI-KATTA` ikki barobar ARZON, lekin zaxirasi 400% —
    olinmasligi kerak.
    """
    natija = _uskuna_tanla(_TANLOV_PARAM, _TANLOV_KATALOG, 1000, 12000.0,
                           (300, 500), 12.0)

    assert natija[0]["nomi"] != "NARXLI-KATTA"


def test_MAQBUL_zaxirada_narxi_bori_afzal():
    """0-30% zaxira — texnik jihatdan teng, KP darrov to'liq chiqsin."""
    natija = _uskuna_tanla(_TANLOV_PARAM, _TANLOV_KATALOG, 1000, 12000.0,
                           (300, 500), 12.0)

    # NARXSIZ-ANIQ zaxirasi kamroq (10% va 25%), lekin ikkalasi ham
    # maqbul oraliqda — narxi bori tanlanadi.
    assert natija[0]["nomi"] == "NARXLI-MOS"


def test_zaxira_foizi_hisoblanadi():
    from kp.shakldan import _zaxira_foizi

    assert _zaxira_foizi([800, 1250], 1000) == pytest.approx(0.25)
    assert _zaxira_foizi([900, 1000], 1000) == 0.0


# --- 12. shovqin pasaytirgich KP ga tushadi -----------------------------------


_SHOVQIN_PARAM = {
    "КГП 50-25 (6-10)": {"turi": "Plastinali shovqin pasaytiruvchi KGP",
                         "bosim": 14},
    "КГП 80-50 (6-10)": {"turi": "Plastinali shovqin pasaytiruvchi KGP",
                         "bosim": 11},
}


def test_shovqin_tanlansa_KP_ga_tushadi():
    """JONLI E'TIROZ: «shovqin pasaytirgich tanladim, KP da yo'q».

    Sabab: katalogda `havo_sarfi` maydoni yo'q (dB jadvali bor),
    shuning uchun `_uskuna_tanla` uni ko'rmasdi. Sig'imi model NOMIDA
    turadi — `КГП 50-30` = 500x300 mm.
    """
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": ["shovqin"], "yonalish": "kirish"},
        _SHOVQIN_PARAM, [], 2000, 12000.0, 12.0, narxsiz, [],
    )

    shovqin = [q for q in qatorlar if q.nomi.startswith("КГП")]
    assert len(shovqin) == 1
    assert shovqin[0].nomi == "КГП 50-25 (6-10)"


def test_shovqin_YETMASA_parallel_va_SABABI():
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": ["shovqin"], "yonalish": "kirish"},
        _SHOVQIN_PARAM, [], 18_000, 12000.0, 12.0, narxsiz, ogohlantirishlar,
    )

    shovqin = [q for q in qatorlar if q.nomi.startswith("КГП")]
    assert shovqin[0].miqdor > 1
    assert any("PARALLEL" in o for o in ogohlantirishlar)


def test_shovqin_tanlanmasa_QATOR_YOQ():
    narxsiz: list[str] = []
    qatorlar = _qoshimcha_qatorlar(
        {"uskunalar": ["filtr"], "yonalish": "kirish"},
        _SHOVQIN_PARAM, [], 2000, 12000.0, 12.0, narxsiz, [],
    )

    assert not any(q.nomi.startswith("КГП") for q in qatorlar)


# --- 13. markaziy qurilma -----------------------------------------------------


def test_markaziy_tanlansa_ALOHIDA_uskuna_qoyilmaydi():
    """Isitgich va sovutgich КЦКП ICHIDA — alohida qator qo'yilsa,
    mijoz ikki marta to'lardi.
    """
    from kp.shakldan import _kerakli_toifalar

    javoblar = {"markaziy": "ha", "uskunalar": ["isitgich", "sovutgich"]}

    assert _kerakli_toifalar(javoblar) == ()


def test_markaziysiz_uskunalar_ODATDAGIDEK():
    from kp.shakldan import _kerakli_toifalar

    javoblar = {"markaziy": "yoq", "uskunalar": ["isitgich", "sovutgich"]}

    assert set(_kerakli_toifalar(javoblar)) == {"isitgich", "sovutgich"}


def test_SORISH_tizimi_OZ_bosimida_hisoblanadi():
    """XATO TUZATILDI (2026-08-26): sanuzelning so'rish ventilyatori
    kirish tizimining bosimi bilan qidirilardi.

    Kirishga filtr + isitgich tanlansa talab 770 Pa ga chiqib ketardi
    va sanuzel ventilyatori TOPILMAY qolardi — KP da panjaralar
    turardi-yu, ularni tortadigan ventilyator yo'q edi.

    Sanuzel so'rishida filtr ham, isitgich ham YO'Q.
    """
    from kp.shakldan import _sorish_ventilyatori

    parametrlar = {
        # Faqat TARMOQ bosimiga (250-450) yetadi, 770 ga emas.
        "ВЦ 14-46-2,5-1": {"turi": "Ventilyator", "havo_sarfi": [890, 1200],
                           "bosim": [410, 470]},
    }
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "ВЦ 14-46-2,5-1", "price": 200.0},
    ]}]}]
    hisob = {
        "sorish_sarfi": 1200, "sorish_diametri": 315,
        # Kirish tizimida filtr+isitgich bor — bosim yuqori.
        "bosim": (570, 770),
        "xonalar": [{"nomi": "Sanuzel", "sorish": True}],
    }
    narxsiz: list[str] = []

    qatorlar = _sorish_ventilyatori(
        hisob, parametrlar, katalog, 12000.0, 12.0, narxsiz, [], "uz")

    assert len(qatorlar) == 1
    assert qatorlar[0].nomi == "ВЦ 14-46-2,5-1"


# --- 14. kanal uzunligi: taxmin -> HAQIQIY hisob ------------------------------
#
# JONLI HOLAT (2026-08-26): sanuzelning qisqa so'rish kanaliga 450 Pa
# talab qilindi (tayyor oraliqning YUQORI chegarasi), holbuki haqiqiy
# hisob 65 Pa berardi. Natijada mos ventilyator umuman topilmadi.


def test_uzunlik_aytilmasa_TAXMINIY_oraliq():
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({"uskunalar": [], "xonalar": [
        {"nomi": "S", "turi": "sanuzel", "maydon": 55, "balandlik": 3}]})

    assert h["bosim"] == (250, 450)
    assert h["bosim_aniq"] is False


def test_uzunlik_aytilsa_ANIQ_hisoblanadi():
    """Qisqa kanal — past bosim. Taxmin 450 edi, haqiqiy 100 dan kam."""
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({"uskunalar": [], "kanal_uzunligi": 10, "xonalar": [
        {"nomi": "S", "turi": "sanuzel", "maydon": 55, "balandlik": 3}]})

    assert h["bosim_aniq"] is True
    assert h["bosim"][1] < 150, "qisqa kanalga 150 Pa dan ko'p chiqdi"


def test_uzun_kanalda_bosim_YUQORI():
    """Qisqartirish emas — HISOB. Uzun tarmoqda talab oshadi."""
    from kp.shakldan import hisobni_bajar

    xona = [{"nomi": "S", "turi": "sanuzel", "maydon": 55, "balandlik": 3}]
    qisqa = hisobni_bajar({"uskunalar": [], "kanal_uzunligi": 10, "xonalar": xona})
    uzun = hisobni_bajar({"uskunalar": [], "kanal_uzunligi": 100, "xonalar": xona})

    assert uzun["bosim"][1] > qisqa["bosim"][1]


def test_uskunalar_ANIQ_hisobga_ham_qoshiladi():
    from kp.shakldan import hisobni_bajar

    xona = [{"nomi": "Z", "turi": "ofis", "maydon": 400, "balandlik": 3}]
    sof = hisobni_bajar({"uskunalar": [], "kanal_uzunligi": 40, "xonalar": xona})
    filtrli = hisobni_bajar(
        {"uskunalar": ["filtr", "isitgich"], "kanal_uzunligi": 40, "xonalar": xona})

    # filtr 200 + isitgich 120 = 320, ustiga 12% zaxira
    assert filtrli["bosim"][1] - sof["bosim"][1] == pytest.approx(358, abs=3)


def test_aniq_hisob_MENEJERGA_aytiladi():
    """Burilishlar soni taxmin qilingani yashirilmaydi."""
    from kp.shakldan import hisobni_bajar

    h = hisobni_bajar({"uskunalar": [], "kanal_uzunligi": 40, "xonalar": [
        {"nomi": "Z", "turi": "ofis", "maydon": 400, "balandlik": 3}]})

    assert any("kanal uzunligi" in o and "Burilishlar" in o
               for o in h["ogohlantirishlar"])


def test_SORISH_tizimi_ham_aniq_hisoblanadi():
    """Sanuzel ventilyatori topilishi uchun ayni shu kerak edi."""
    from kp.shakldan import _sorish_ventilyatori

    parametrlar = {
        # 405 Pa — tayyor oraliqning 450 talabiga YETMAYDI,
        # lekin qisqa kanalning haqiqiy bosimiga yetib ortadi.
        "ВКРВ-3,15": {"turi": "Ventilyator", "havo_sarfi": [1180, 2610],
                      "bosim": [320, 405]},
    }
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "ВКРВ-3,15", "price": 300.0}]}]}]
    hisob = {
        "sorish_sarfi": 1650, "sorish_diametri": 315, "sorish_tezligi": 5.88,
        "sorish_xonalari": 1, "bosim": (570, 770),
        "xonalar": [{"nomi": "Sanuzel", "sorish": True}],
    }
    narxsiz: list[str] = []

    qatorlar = _sorish_ventilyatori(
        hisob, parametrlar, katalog, 12000.0, 12.0, narxsiz, [], "uz",
        {"kanal_uzunligi": 20},
    )

    assert len(qatorlar) == 1
    assert qatorlar[0].nomi == "ВКРВ-3,15"


def test_MARKAZIY_qurilmada_ham_sanuzel_ventilyatori_boladi():
    """JONLI HOLAT (2026-08-26): markaziy variantda sanuzel panjaralari
    turardi-yu, ularni tortadigan ventilyator yo'q edi.

    КЦКП kirish tomonini qoplaydi, lekin `faqat_sorish` xonalari
    ALOHIDA tizim — ularning havosi boshqa xonalarga aralashtirilmaydi.
    """
    from kp.narx import narxlar, rekvizitlar
    from kp.shakldan import _markaziy_kp

    parametrlar = {
        "КЦКП-25": {"turi": "KЦKП", "havo_sarfi": 25000.0},
        "ВКРВ-3,15": {"turi": "Ventilyator", "havo_sarfi": [1180, 2610],
                      "bosim": [320, 405]},
    }
    katalog = [{"name_uz": "x", "characters": [{"title": "x", "insides": [
        {"in_model_name": "КЦКП-25", "price": 5000.0},
        {"in_model_name": "ВКРВ-3,15", "price": 300.0},
    ]}]}]
    hisob = {
        "sarf": 23601, "diametr": 1000, "bosim": (1203, 1203),
        "sorish_sarfi": 1440, "sorish_diametri": 315, "sorish_tezligi": 5.1,
        "sorish_xonalari": 1,
        "xonalar": [
            {"nomi": "Sex", "turi": "ishlab_chiqarish", "sarf": 23601,
             "sorish": False},
            {"nomi": "Sanuzel", "turi": "sanuzel", "sarf": 1440, "sorish": True},
        ],
    }
    javoblar = {"yol": "obyekt", "markaziy": "ha", "yonalish": "ikkalasi",
                "uskunalar": ["filtr"], "kanal_uzunligi": 20}

    natija = _markaziy_kp(
        javoblar, hisob, parametrlar, katalog, "T", 12000.0,
        narxlar(), dict(rekvizitlar()), "uz", [],
    )

    nomlar = [q.nomi for q in natija.kp.qatorlar]
    assert "КЦКП-25" in nomlar
    assert "ВКРВ-3,15" in nomlar, "sanuzel ventilyatori qo'yilmadi"


# --- Bosim ish oralig'i -------------------------------------------------------
#
# JONLI XATO (2026-08-27): 8000 m³/soat, 450 Pa so'ralganda
# `ВР 12-26-5,5-1-45,0-2940` tanlandi. Uning ish oralig'i 6800-8000 Pa —
# so'ralgandan 15 BAROBAR yuqori. `_bosimga_mosmi` faqat «bosimi
# YETADIMI» ni tekshirardi, «ORTIQCHA EMASMI» ni emas.
#
# Oqibati: 45 kVt dvigatel 5,5 kVt o'rniga (narx bir necha barobar) va
# ventilyator o'z egri chizig'idan tashqarida ishlaydi.


def test_ish_oraligidagi_bosim_TANILADI():
    from kp.shakldan import _bosim_oraligidami

    ventilyator = {"bosim": [310, 600]}

    assert _bosim_oraligidami(ventilyator, (450, 450)) is True


def test_ORTIQCHA_bosimli_ventilyator_oraliqdan_TASHQARIDA():
    from kp.shakldan import _bosim_oraligidami

    yuqori_bosimli = {"bosim": [6800, 8000]}

    assert _bosim_oraligidami(yuqori_bosimli, (450, 450)) is False


def test_YETARSIZ_bosimli_ham_oraliqdan_tashqarida():
    from kp.shakldan import _bosim_oraligidami

    past_bosimli = {"bosim": [50, 95]}

    assert _bosim_oraligidami(past_bosimli, (450, 450)) is False


def test_bosim_NOMALUM_bolsa_jazolanmaydi():
    """Oraliq ma'lumoti to'liq emas — noma'lumlik chetlatish sababi emas."""
    from kp.shakldan import _bosim_oraligidami

    assert _bosim_oraligidami({}, (450, 450)) is True
    assert _bosim_oraligidami({"bosim": None}, (450, 450)) is True
    assert _bosim_oraligidami({"bosim": [310]}, (450, 450)) is True


def test_bosim_talab_qilinmasa_hammasi_mos():
    from kp.shakldan import _bosim_oraligidami

    assert _bosim_oraligidami({"bosim": [6800, 8000]}, None) is True


def test_ish_oraligidagi_ventilyator_TARTIBDA_TEPADA():
    """Sarf bo'yicha ideal bo'lsa ham, oraliqdan tashqaridagi pastga tushadi."""
    from kp.shakldan import _uskuna_tanla

    parametrlar = {
        # Sarf bo'yicha ANIQROQ mos (zaxira kam), lekin bosimi 15x yuqori.
        "ВР 12-26-5,5-1-45,0-2940": {
            "turi": "Ventilyator ВР 12-26",
            "havo_sarfi": [5000, 9400], "bosim": [6800, 8000]},
        # Zaxirasi kattaroq, lekin bosimi TO'G'RI.
        "ВЦ 4-75-6,3-1": {
            "turi": "Ventilyator ВЦ 4-75",
            "havo_sarfi": [5200, 10500], "bosim": [310, 600]},
    }

    nomzodlar = _uskuna_tanla(parametrlar, [], 8000.0, 12000.0, (450, 450))

    assert nomzodlar[0]["nomi"] == "ВЦ 4-75-6,3-1"
    assert nomzodlar[0]["bosim_mos"] is True
    assert nomzodlar[1]["bosim_mos"] is False


def test_YUQORI_bosim_soralsa_yuqori_bosimli_tanlanadi():
    """Tuzatish teskari tomonga buzmasin."""
    from kp.shakldan import _uskuna_tanla

    parametrlar = {
        "ВР 12-26-5,5-1-45,0-2940": {
            "turi": "Ventilyator ВР 12-26",
            "havo_sarfi": [5000, 9400], "bosim": [6800, 8000]},
        "ВЦ 4-75-6,3-1": {
            "turi": "Ventilyator ВЦ 4-75",
            "havo_sarfi": [5200, 10500], "bosim": [310, 600]},
    }

    nomzodlar = _uskuna_tanla(parametrlar, [], 8000.0, 12000.0, (7000, 7000))

    assert nomzodlar[0]["nomi"] == "ВР 12-26-5,5-1-45,0-2940"

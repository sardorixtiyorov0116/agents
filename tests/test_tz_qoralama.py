"""Excel TZ -> KP qoralamasi: `kp/tz_qoralama.py` va `/kp` dagi Excel yo'li.

Qoidalar:
  * miqdor TZ dagidek qoladi (ilgari model hammasiga 1 qo'yardi);
  * raqib nomi Climavent nomiga aylanadi, qolip `tz_analoglar.yaml` dan;
  * muhandis TANLOVI kerak bo'lsa (КЦКП, VRF tashqi blok) — TZ nomi qoladi
    va parametrlari bilan belgilanadi, o'ylab topilgan model yozilmaydi;
  * TZ da yo'q parametr (EI) jimgina qo'yilmaydi — aytiladi;
  * ETALON: qoralama menejerning haqiqiy KP sini kamida shuncha takrorlashi
    shart (2026-10-03 da o'lchangan qiymat — pasaysa test yiqiladi).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kp.tz_jadval import TzQator
from kp.tz_qoralama import (
    ANALOG,
    QISQARTMA,
    TANILMADI,
    TANLOV,
    jadvaldan_taklif,
    kp_bilan_qamrov,
    qoralama,
)

ETALON = Path(__file__).parent / "etalon_tz"


def _tz(nomi: str, miqdor: float = 1, guruh: str = "", tizim: str = "",
        varaq: str = "Лист1", bolim: str = "", **param) -> TzQator:
    return TzQator(nomi=nomi, miqdor=miqdor, guruh=guruh, tizim=tizim, bolim=bolim,
                   parametrlar=param, matn=nomi, varaq=varaq)


def _bitta(q: TzQator) -> dict:
    natija = qoralama([q])
    assert len(natija.mahsulotlar) >= 1
    return natija.mahsulotlar[0]


# --- qoliplar ----------------------------------------------------------------


@pytest.mark.parametrize("tz, kp", [
    ("Огнезадерживающий клапан КЛОП-1 (Н/О) с реверсивным приводом 24В FD 125x100",
     "Клапан противопожарный КПУ-НО-Н-EI60-125х100-КН-НУП-ЭМ-220"),
    ("Клапан-(НЗ) 500х500, огнезащитный",
     "Клапан противопожарный КПД-НЗ-Н-EI60-500х500-КН-НУП-ЭР-220v"),
    ("Альюминевые решетка 4АПР-450х450мм.",
     "Решетка вентиляционная потолочная 4РВП 450х450мм без КРВ"),
    ("Решетка щелевая АРС 1700х150.",
     "Решетка вентиляционная регулируемая РВР-2 1700х150мм без КРВ"),
    ("Диффузоры ДПУ-М ∅100", "Диффузор веерный ДФА 100"),
    ("РВН-Решетка наружная 400x350", "Решетка вентиляционная наружная РВН 400х350мм"),
    ("Декоративная решетка РКДМ-700х700", "Решетка металлическая декоративный 700х700"),
    ("Шумоглушитель трубчатый 250*150*1000 ГТП1-3",
     "Шумоглушитель трубчатый прямоугольный ГТП 250х150-1000"),
    ("Канальный вентилятор KV315M", "Вентилятор канальный ВК-315С"),
    ("Дроссель-клапан ДКСп 250x200мм Серия 1.494-39", "Дроссель клапан ДКСп 250х200"),
    ("Обратный клапан 100х100.", "Клапан обратный КОП 100х100"),
])
def test_analog_qoliplari(tz, kp):
    assert _bitta(_tz(tz))["nomi"] == kp


def test_miqdor_TZ_dagidek_qoladi():
    assert _bitta(_tz("Альюминевые решетка 4АПР-600х600мм.", 124))["miqdor"] == 124


def test_EI_TZ_da_bolsa_ishlatiladi_bolmasa_aytiladi():
    bor = qoralama([_tz("Клапан КЛОП-1 EI90 FD 125x100")])
    assert "EI90" in bor.mahsulotlar[0]["nomi"]
    assert bor.umumiy == []

    yoq = qoralama([_tz("Клапан КЛОП-1 FD 125x100")])
    assert "EI60" in yoq.mahsulotlar[0]["nomi"]
    assert any("EI" in u and "tekshiring" in u for u in yoq.umumiy)


def test_eng_kichik_olcham_kattalashtiriladi_va_aytiladi():
    m = _bitta(_tz("Альюминевые решетка 4АПР-150х150мм."))
    assert "300х300" in m["nomi"]
    assert any("kattalashtirildi" in o for o in m["ogohlantirishlar"])


def test_CAV_aytiladi():
    m = _bitta(_tz("Дроссель-клапан ДКСп Постоянный объем воздуха (СAV) 125x100"))
    assert any("CAV" in o for o in m["ogohlantirishlar"])


def test_dumaloq_klapan():
    assert "Ф200" in _bitta(_tz("Огнезадерживающий клапан КЛОП-1 (Н/О) FD Ø200"))["nomi"]


def test_bolim_sarlavhasi_qisqartmasi_birinchi():
    natija = qoralama([_tz("Решетка 300x150", 57, guruh="Решетка АДН")])
    assert natija.turlar[QISQARTMA] == 1
    assert natija.mahsulotlar[0]["nomi"].startswith("Решетка вентиляционная регулируемая РВР-2 300х150")


# --- tanlov va VRF ------------------------------------------------------------


@pytest.mark.parametrize("sarf_q, olcham_q", [
    # Menejer KP lari (13603, 13574): nominaldan 5% gacha oshsa ham o'sha o'lcham.
    (1100, "1,6"), (2600, "3,15"), (3000, "3,15"), (4500, "5"), (9000, "10"),
    (10250, "10"), (17500, "20"), (22500, "25"), (28000, "31,5"), (33000, "31,5"),
])
def test_KCKP_olchami_sarfdan(sarf_q, olcham_q):
    natija = qoralama([_tz("Кондиционеры компактные панельные", tizim="П1", L=sarf_q, P=500)])
    m = natija.mahsulotlar[0]
    assert natija.turlar[ANALOG] == 1
    assert m["nomi"] == f"Кондиционер КЦКП-{olcham_q}"
    assert "pozitsiya" not in m             # menejer «КЦКП-3,15 (П1)» deb yozmaydi
    assert m["tavsif"] == (f"L={sarf_q}м3/ч, Р=500Па\nТип системы: приточная\n"
                           "Система в проекте: П1")
    assert any("Seksiyalar" in u for u in natija.umumiy)    # tarkibi yasalmaydi — aytiladi


def test_KCKP_sarfsiz_tanlov_TZ_nomi_bilan():
    natija = qoralama([_tz("Кондиционеры компактные панельные", tizim="П1", P=500)])
    assert natija.turlar[TANLOV] == 1
    assert natija.mahsulotlar[0]["nomi"] == "Кондиционеры компактные панельные"
    assert qoralama([_tz("Приточная установка", L=120000)]).turlar[TANLOV] == 1


def test_pozitsiya_faqat_qurilmaga():
    """«(В1)» ventilyatorga qo'yiladi, panjara/klapanga — yo'q (menejer KP lari)."""
    natija = qoralama([
        _tz("Канальный вентилятор KV315M", tizim="В1"),
        _tz("Альюминевые решетка 4АПР-450х450мм.", tizim="В1"),
    ])
    assert natija.mahsulotlar[0]["pozitsiya"] == "В1"
    assert "pozitsiya" not in natija.mahsulotlar[1]


def test_KP_da_nom_qisqa_asl_nom_hujjatga_yozilmaydi():
    """Ilgari ostiga «В1 · от · Канальный вентилятор KV315M» yozilardi."""
    from kp.shakldan import _qatorlar_modeldan

    natija = qoralama([
        _tz("Канальный вентилятор KV315M", tizim="В1", guruh="от"),
        _tz("Кондиционеры компактные панельные", tizim="П1", L=3000, P=500),
        _tz("Огнезадерживающий клапан КЛОП-1 FD 125x100", 4, tizim="В1"),
    ])
    qatorlar, _, aniqlik, _ = _qatorlar_modeldan(natija.mahsulotlar, [], 12000, 12)
    assert aniqlik is None
    assert [q.nomi for q in qatorlar] == [
        "Вентилятор канальный ВК-315С (В1)",
        "Кондиционер КЦКП-3,15",
        "Клапан противопожарный КПУ-НО-Н-EI60-125х100-КН-НУП-ЭМ-220",
    ]
    assert qatorlar[1].spetsifikatsiya.startswith("L=3000м3/ч, Р=500Па\n")
    assert qatorlar[0].spetsifikatsiya == qatorlar[2].spetsifikatsiya == ""
    assert "KV315M" in qatorlar[0].izoh                       # menejer uchun saqlanadi
    assert qatorlar[1].birlik == "комп."


def test_maishiy_ventilyator_KP_ga_kirmaydi_va_aytiladi():
    """Menejer 13603: «Compact 20» (9 dona) KP da yo'q — Climavent qilmaydi."""
    natija = qoralama([_tz("вентилятор с решеткой Compact 20", tizim="В3", L=100),
                       _tz("Канальный вентилятор KV315M", tizim="В1")])
    assert [m["nomi"] for m in natija.mahsulotlar] == ["Вентилятор канальный ВК-315С"]
    assert any("KIRITILMADI" in u and "Compact 20" in u for u in natija.umumiy)


@pytest.mark.parametrize("tz, kp", [
    ("Канальный вентилятор ВЕНТС ТТ ПРО 250", "Вентилятор канальный MF-250P"),
    ("Вентилятор ВРАН6 080 ДУ400", "Вентилятор ВЦ 4-75-8-ДУ-400"),
    ("Вентилятор ОСА 201 080 Н", "Вентилятор ВО 30-160-8"),
])
def test_ventilyator_analoglari_13603(tz, kp):
    assert _bitta(_tz(tz))["nomi"] == kp


def test_nomersiz_sanoat_ventilyatori_tanlov():
    natija = qoralama([_tz("Вентилятор радиальный дымоудаления", L=20000)])
    assert natija.turlar[TANLOV] == 1


def test_seksiya_sarlavhasi_qator_bolib_turadi():
    natija = qoralama([
        _tz("Канальный вентилятор KV315M", tizim="В1", bolim="9 СЕКЦИЯ"),
        _tz("Канальный вентилятор KV200M", tizim="В2", bolim="9 СЕКЦИЯ"),
        _tz("Канальный вентилятор KV200M", tizim="В2", bolim="10 СЕКЦИЯ"),
    ])
    nomlar = [m["nomi"] for m in natija.mahsulotlar]
    assert nomlar[0] == "- 9 СЕКЦИЯ" and nomlar[3] == "- 10 СЕКЦИЯ" and len(nomlar) == 5
    from kp.shakldan import _qatorlar_modeldan

    qatorlar, narxsiz, _, _ = _qatorlar_modeldan(natija.mahsulotlar, [], 12000, 12)
    assert qatorlar[0].birlik_narx == 0 and "- 9 СЕКЦИЯ" not in narxsiz


def test_qatorli_tavsif_hujjatda_qatorlari_bilan_qoladi():
    from kp.hujjat import _qisqa_spetsifikatsiya

    tavsif = "L=31750м3/ч, Р=750Па\nНагрев Qт=138,9кВт\nФильтры: G4, F7, F9"
    assert _qisqa_spetsifikatsiya(tavsif) == tavsif
    assert _qisqa_spetsifikatsiya("bir  qator,   tavsif") == "bir qator, tavsif"


def test_VRF_kasseta_kodi_va_paneli():
    natija = qoralama([_tz("Внутренний блок, кассетный Производительность 16 кВт", 8)])
    nomlar = [m["nomi"] for m in natija.mahsulotlar]
    assert nomlar[0] == "Внутренний блок кассетного типа VRF JVI-160C"
    assert nomlar[1].startswith("Состав панели JHPEE-G-NK")
    assert [m["miqdor"] for m in natija.mahsulotlar] == [8, 8]


def test_VRF_devoriy_panelsiz_va_standart_olcham():
    natija = qoralama([_tz("Внутренний блок, настенный Производительность 4,5 кВт", 2)])
    assert [m["nomi"] for m in natija.mahsulotlar] == ["Внутренний блок настенные типа VRF JVI-045W"]


def test_VRF_tashqi_blok_yagona_kombinatsiya_qoyiladi():
    natija = qoralama([_tz("Наружный блок кондиционирования, напольная 56 кВт", 2)])
    assert [(m["nomi"], m["miqdor"]) for m in natija.mahsulotlar] == [
        ("Наружный блок VRF модель JVO-560T", 2)]
    assert "tasdiqlang" in natija.mahsulotlar[0]["ogohlantirishlar"][0]


def test_VRF_tashqi_blok_bir_nechta_kombinatsiya_TANLOV():
    """128,5 kVt: 725T+560T ham, 615T+335T×2 ham (menejer tanlagani) — o'zimiz tanlamaymiz."""
    natija = qoralama([_tz("Наружный блок инверторный 128,5 кВт")])
    assert natija.turlar[TANLOV] == 1
    ogoh = natija.mahsulotlar[0]["ogohlantirishlar"][0]
    assert "JVO-615T + JVO-335T × 2" in ogoh and "JVO-725T + JVO-560T" in ogoh


def test_VRF_tashqi_blok_aniq_kombinatsiya_yoq():
    natija = qoralama([_tz("Наружный блок кондиционирования 18 кВт")])
    assert natija.turlar[TANLOV] == 1


def test_katalog_uchinchi_olchami_nomga_qoyiladi():
    from kp.shakldan import katalog_olchami

    assert katalog_olchami("Дроссель клапан ДКСп 250х200",
                           "ДКСп 250х200х250 (13 $ x 12600)") == "Дроссель клапан ДКСп 250х200х250"
    # Narx boshqa o'lchamdan topilgan — nom O'ZGARMAYDI.
    assert katalog_olchami("Дроссель клапан ДКСп 250х200",
                           "ДКСп 300х200х250 (13 $)") == "Дроссель клапан ДКСп 250х200"
    assert katalog_olchami("Решетка 4РВП 450х450мм", "4РВП 450х450 (16 $)") == "Решетка 4РВП 450х450мм"


async def test_kp_oqimi_ikkinchi_TZ_fayli_royxatga_QOSHILADI(tmp_path, monkeypatch):
    """Zayavka + so'rovnoma varaqasi — ikkinchi fayl tashlab yuborilmaydi."""
    from app.baza import Baza
    from bot import kp_oqim
    from kp.tz import ShaklTaklifi

    class Xabar:
        def __init__(self):
            self.matnlar = []

        async def reply_text(self, matn, reply_markup=None, **_):
            self.matnlar.append(matn)

    baza = Baza(tmp_path / "b.db")
    await baza.tayyorla()
    xabar = Xabar()
    await kp_oqim.boshla(baza, xabar, 4343)
    for nom, miqdor in (("A", 1), ("B", 2)):
        t = ShaklTaklifi()
        t.javoblar = {"yol": "model", "mahsulotlar": [{"nomi": nom, "miqdor": miqdor}]}
        t.topilganlar = ["x"]
        await kp_oqim._taklifni_qolla(baza, xabar, 4343, t)
    javoblar = (await baza.kp_shakli(4343))["javoblar"]
    assert [m["nomi"] for m in javoblar["mahsulotlar"]] == ["A", "B"]
    assert any("QO'SHILDI" in m for m in xabar.matnlar)


def test_split_standart_quvvat():
    m = _bitta(_tz("Сплит-система кондиционирования, настенная Производительность 2,64 кВт", 2))
    assert m["nomi"] == "Сплит кондиционер 2,7 квт"


def test_aloqasiz_varaq_olinmaydi():
    natija = qoralama([_tz("Арматура ф10 А400", 5, varaq="Заявка №2011"),
                       _tz("Альюминевые решетка 4АПР-450х450мм.", 8, varaq="6901")])
    assert len(natija.mahsulotlar) == 1
    assert any("aloqasiz" in u for u in natija.umumiy)


def test_tanilmagan_qator_TZ_nomi_bilan_qoladi():
    natija = qoralama([_tz("Чиллер охлаждения воды"), _tz("Альюминевые решетка 4АПР-450х450мм.")])
    assert natija.turlar[TANILMADI] == 1
    assert natija.mahsulotlar[0]["nomi"] == "Чиллер охлаждения воды"


# --- /kp ga Excel ---------------------------------------------------------------


def _xlsx(tmp_path, qatorlar) -> Path:
    import openpyxl

    kitob = openpyxl.Workbook()
    v = kitob.active
    v.title = "Лист_1"          # pastki chiziq — Markdown ni buzmasligi kerak
    for q in qatorlar:
        v.append(q)
    yol = tmp_path / "tz_1.xlsx"
    kitob.save(yol)
    return yol


def test_jadvaldan_taklif_model_yoli(tmp_path):
    yol = _xlsx(tmp_path, [
        ["Позиция", "Наименование", "Ед. изм", "Кол-во"],
        ["ПВ1", "Система ПВ1:", None, None],
        [None, "Альюминевые решетка 4АПР-450х450мм.", "шт", 8],
        [None, "Огнезадерживающий клапан КЛОП-1 FD 125x100", "шт", 74],
    ])
    taklif = jadvaldan_taklif(yol)
    assert taklif.javoblar["yol"] == "model"
    assert [m["miqdor"] for m in taklif.javoblar["mahsulotlar"]] == [8, 74]
    assert all("_" not in o for o in taklif.ogohlantirishlar + taklif.topilganlar)


def test_jadvaldan_taklif_jadval_bolmasa_None(tmp_path):
    yol = _xlsx(tmp_path, [["Ombor 800 m2, balandligi 6 m"]])
    assert jadvaldan_taklif(yol) is None


async def test_kp_oqimi_Excel_TZ_ni_modelsiz_oladi(tmp_path, monkeypatch):
    """`/kp` ochiq — Excel tashlanadi — shakl «model» yo'liga to'ladi.

    Model CHAQIRILMAYDI: `_tz_ajrat` chaqirilsa test yiqiladi.
    """
    from app.baza import Baza
    from bot import kp_oqim

    async def chaqirilmasin(*_a, **_k):
        raise AssertionError("Excel jadvali modelga yuborilmasligi kerak")

    monkeypatch.setattr(kp_oqim, "_tz_ajrat", chaqirilmasin)

    class Xabar:
        def __init__(self):
            self.matnlar = []

        async def reply_text(self, matn, reply_markup=None, **_):
            self.matnlar.append(matn)

    class Fayl:
        def __init__(self, manba):
            self.manba = manba

        async def download_to_drive(self, yol):
            Path(yol).write_bytes(self.manba.read_bytes())

    baza = Baza(tmp_path / "b.db")
    await baza.tayyorla()
    xabar = Xabar()
    await kp_oqim.boshla(baza, xabar, 4242)
    manba = _xlsx(tmp_path, [
        ["№", "Наименование материалов", "Ед-изм", "Кол-во"],
        [None, "Решетка АДН", None, None],
        [1, "Решетка 300x150", "шт", 57],
        [2, "Решетка 200x150", "шт", 31],
    ])
    assert await kp_oqim.hujjat(baza, xabar, 4242, Fayl(manba), "tz_1.xlsx")
    javoblar = (await baza.kp_shakli(4242))["javoblar"]
    assert javoblar["yol"] == "model"
    assert [m["miqdor"] for m in javoblar["mahsulotlar"]] == [57, 31]
    assert "РВР-2 300х150" in javoblar["mahsulotlar"][0]["nomi"]
    assert any("Climavent nomiga aylandi: 2" in m for m in xabar.matnlar)


def test_uzun_KP_xulosasi_bolinadi():
    from bot import kp_oqim

    qatorlar = [f"• Решетка вентиляционная потолочная 4РВП {i}х{i}мм · 8 шт · 196 000"
                for i in range(300)]
    bolaklar = kp_oqim._bolaklar(qatorlar)
    assert len(bolaklar) > 1
    assert all(len(b) <= kp_oqim.XABAR_CHEGARASI for b in bolaklar)
    assert sum(b.count("•") for b in bolaklar) == 300


# --- ETALON -------------------------------------------------------------------------

etalon = pytest.mark.skipif(not ETALON.is_dir(), reason="tests/etalon_tz/ yo'q (git ga kirmaydi)")


@etalon
@pytest.mark.parametrize("papka, nomga, qamrov", [
    # 2026-10-03 o'lchovi (nomga aylangan %, haqiqiy KP miqdor qamrovi %).
    # Chegaralar o'lchovdan bir oz past — pasayish xato sifatida ushlanadi.
    ("1-murod", 45, 85),            # КЦКП, radial ventilyator — tanlov
    ("3-provik-zarafshon", 98, 95),
    ("4-enter-k1-k12", 60, 75),     # VRF tashqi blok — tanlov
    ("6-nirvana", 100, 100),
])
def test_etalon_qoralama_haqiqiy_KP_ni_takrorlaydi(papka, nomga, qamrov):
    from kp.kp_pdf import kp_oqi
    from kp.tz_jadval import jadval_oqi

    tz = []
    for yol in sorted((ETALON / papka).glob("tz*.xlsx")):
        tz += jadval_oqi(yol).qatorlar
    natija = qoralama(tz)
    olchov, _ = kp_bilan_qamrov(natija.mahsulotlar, kp_oqi(ETALON / papka / "kp.pdf"))
    assert natija.tayyor_foizi >= nomga
    assert olchov >= qamrov


@etalon
def test_etalon_OL_dan_VRF_bloklari():
    """5-juft ОЛ: menejer KP-13173 dagi ichki bloklar birma-bir chiqadi."""
    from kp.kp_pdf import kp_oqi
    from kp.ol_pdf import ol_oqi
    from kp.tz_qoralama import fayldan_taklif

    qatorlar = ol_oqi(ETALON / "5-enter-alm" / "tz_ol.pdf")
    assert sum(q.miqdor for q in qatorlar if "Внутр" in q.nomi) == 30
    natija = qoralama(qatorlar)
    nomlar = {m["nomi"]: m["miqdor"] for m in natija.mahsulotlar if natija.mahsulotlar}
    assert nomlar["Внутренний блок настенные типа VRF JVI-056W"] == 6
    olchov, _ = kp_bilan_qamrov(natija.mahsulotlar, kp_oqi(ETALON / "5-enter-alm" / "kp.pdf"))
    assert olchov >= 80
    taklif = fayldan_taklif(ETALON / "5-enter-alm" / "tz_ol.pdf")
    assert taklif.javoblar["yol"] == "model"
    assert fayldan_taklif(ETALON / "5-enter-alm" / "kp.pdf") is None    # KP — ОЛ emas


@etalon
def test_etalon_VENTAS_dan_KCKP_menejer_tanloviga_mos():
    """7-juft: AHU + RC — o'lcham menejer KP-13574 dagidek.

    Bitta istisno — AHU-19 (13250 m³/soat): menejer КЦКП-12,5 olgan (6%
    ortiq), AHU-13 da esa 26500 uchun 6% da ham 25 emas, 31,5. Bitta foiz
    ikkalasini qoplamaydi — 5% qoldi, AHU-19 da 16 chiqadi.
    """
    import re

    from kp.kp_pdf import kp_oqi
    from kp.solishtir import sarf
    from kp.tz_qoralama import ventas_mahsuloti
    from kp.ventas import papka_oqi

    menejer = {}
    for q in kp_oqi(ETALON / "7-provik-ventas" / "kp.pdf").mahsulotlar:
        m = re.search(r"КЦКП-([\d,]+)", q.toza_nomi)
        if m:
            menejer.setdefault(sarf(q.toza_nomi), m.group(1))
    mos, jami = 0, 0
    for q in papka_oqi(ETALON / "7-provik-ventas" / "tz"):
        yozuv, turi = ventas_mahsuloti(q)
        if not q.nomi.startswith(("AHU", "RC")):
            assert turi == TANLOV                     # HEF — КЦКП emas
            continue
        assert yozuv["nomi"].startswith("Кондиционер КЦКП-")
        assert yozuv["tavsif"].startswith(("L=", "Приток L="))
        if q.sarf in menejer:
            jami += 1
            mos += yozuv["nomi"].endswith(f"-{menejer[q.sarf]}")
    assert jami >= 15 and mos >= jami - 1


@etalon
def test_etalon_murod_menejer_KP_13603_dagidek():
    """TZ -> 44 qator, menejer KP 13603 dagidek: 3 seksiya sarlavhasi + 41 mahsulot.

    Ilgari bot 50 qator chiqardi (seksiyasiz, 9 ta «Compact 20» bilan) va
    КЦКП tavsifi faqat «L=…, Р=…» edi — isitgich TZ da bo'lsa ham.
    """
    from kp.tz_qoralama import jadvaldan_taklif

    m = jadvaldan_taklif(ETALON / "1-murod" / "tz.xlsx").javoblar["mahsulotlar"]
    nomlar = [x["nomi"] for x in m]
    assert len(m) == 44
    assert [n for n in nomlar if n.startswith("- ")] == [
        "- 9 СЕКЦИЯ", "- 10 СЕКЦИЯ", "- 11 СЕКЦИЯ"]
    assert not any("Compact" in n or "ВРАН" in n or "ОСА" in n for n in nomlar)
    kckp = m[1]
    assert kckp["nomi"] == "Кондиционер КЦКП-3,15"
    assert "Секция нагрева: электрический, tвн=-14°С, tвк=+12°С, Qт=30кВт" in kckp["tavsif"]
    assert "Секция фильтров: G3" in kckp["tavsif"]


@etalon
def test_etalon_VENTAS_kp_ga_fayl_bilan():
    from kp.tz_qoralama import fayldan_taklif

    taklif = fayldan_taklif(ETALON / "7-provik-ventas" / "tz" / "AHU-11.pdf")
    m = taklif.javoblar["mahsulotlar"][0]
    assert m["nomi"] == "Кондиционер КЦКП-20"
    assert "Секция рекуператора: гликолевый" in m["tavsif"] and "H14" in m["tavsif"]
    assert m["tavsif"].endswith("Система в проекте: AHU-11")


@etalon
def test_etalon_alm_tekshiruvchi_OL_bilan():
    """Zayavka + ОЛ: tashqi bloklar jami quvvat bo'yicha mos, 10 -> 11,2 kVt topiladi."""
    from kp.solishtir import fayllarni_tekshir

    papka = ETALON / "5-enter-alm"
    natija, _ = fayllarni_tekshir(papka / "kp.pdf", [papka / "tz_zayavka.xlsx", papka / "tz_ol.pdf"])
    matnlar = " | ".join(f.matn for f in natija.farqlar)
    assert "285 kVt = KP 285 kVt" in matnlar
    assert "10 kVt" in matnlar and "11.2 kVt" in matnlar
    assert "Split" not in matnlar           # К1–К4 zayavkadagi tizim qatori bilan qoplangan


@etalon
def test_etalon_alm_aloqasiz_varaqlar_olinmaydi():
    from kp.tz_jadval import jadval_oqi

    natija = qoralama(jadval_oqi(ETALON / "5-enter-alm" / "tz_zayavka.xlsx").qatorlar)
    assert sum("aloqasiz" in u for u in natija.umumiy) == 3
    assert not any("Арматура" in m["nomi"] for m in natija.mahsulotlar)

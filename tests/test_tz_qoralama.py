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
        varaq: str = "Лист1", **param) -> TzQator:
    return TzQator(nomi=nomi, miqdor=miqdor, guruh=guruh, tizim=tizim,
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


def test_KCKP_tanlov_TZ_nomi_va_parametrlari_bilan():
    natija = qoralama([_tz("Кондиционеры компактные панельные", tizim="П1", L=3000, P=500)])
    m = natija.mahsulotlar[0]
    assert natija.turlar[TANLOV] == 1
    assert m["nomi"] == "Кондиционеры компактные панельные"     # o'ylab topilmaydi
    assert "3000 m³/soat" in m["ogohlantirishlar"][0]


def test_VRF_kasseta_kodi_va_paneli():
    natija = qoralama([_tz("Внутренний блок, кассетный Производительность 16 кВт", 8)])
    nomlar = [m["nomi"] for m in natija.mahsulotlar]
    assert nomlar[0] == "Внутренний блок кассетного типа VRF JVI-160C"
    assert nomlar[1].startswith("Состав панели JHPEE-G-NK")
    assert [m["miqdor"] for m in natija.mahsulotlar] == [8, 8]


def test_VRF_devoriy_panelsiz_va_standart_olcham():
    natija = qoralama([_tz("Внутренний блок, настенный Производительность 4,5 кВт", 2)])
    assert [m["nomi"] for m in natija.mahsulotlar] == ["Внутренний блок настенные типа VRF JVI-045W"]


def test_VRF_tashqi_blok_tanlov():
    natija = qoralama([_tz("Наружный блок кондиционирования, напольная 56 кВт", 2)])
    assert natija.turlar[TANLOV] == 1


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
def test_etalon_alm_aloqasiz_varaqlar_olinmaydi():
    from kp.tz_jadval import jadval_oqi

    natija = qoralama(jadval_oqi(ETALON / "5-enter-alm" / "tz_zayavka.xlsx").qatorlar)
    assert sum("aloqasiz" in u for u in natija.umumiy) == 3
    assert not any("Арматура" in m["nomi"] for m in natija.mahsulotlar)

"""TZ ↔ KP tekshiruvchisi: `kp/kp_pdf.py`, `kp/tz_jadval.py`, `kp/ventas.py`,
`kp/solishtir.py`.

Ikki qism:

  1. SUN'IY ma'lumot — har qoida alohida, mijoz hujjatisiz. Doim ishlaydi.
  2. ETALON — 7 juft HAQIQIY TZ va menejer KP si (`tests/etalon_tz/`).
     Bu papka git ga kirmaydi (mijoz hujjatlari), shuning uchun u
     yo'q bo'lsa testlar o'tkazib yuboriladi. Har bir assert — 2026-10-03
     da qo'lda tekshirilgan farq: tekshiruvchi uni topishi SHART.

Tekshiruvchi hech narsani tuzatmaydi — u farqni ko'rsatadi. Shuning uchun
testlar «xato bor» emas, «farq topildi» ni tekshiradi.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kp.kp_pdf import KpHujjat, KpQator, _pul_tortligi
from kp.solishtir import (
    JIDDIY,
    MALUMOT,
    NOM_TOLIQ_EMAS,
    NUSXA,
    OLCHAM,
    PARAMETR,
    TEKSHIRING,
    YOQ_KPDA,
    diametr,
    kp_oilasi,
    kvt,
    olcham,
    solishtir,
    tz_oilasi,
    ventas_solishtir,
)
from kp.tz_jadval import TzQator, jadval_oqi
from kp.ventas import Qurilma, _son

ETALON = Path(__file__).parent / "etalon_tz"


def _kp(*qatorlar: tuple) -> KpHujjat:
    """(nomi, miqdor[, narx]) -> KpHujjat. Narxsiz «- …» — bo'lim sarlavhasi."""
    h = KpHujjat(yol="soxta.pdf")
    for i, q in enumerate(qatorlar, 1):
        nomi, miqdor = q[0], q[1]
        narx = q[2] if len(q) > 2 else (0.0 if nomi.startswith("-") else 1000.0)
        h.qatorlar.append(KpQator(raqam=i, nomi=nomi, birlik="шт", miqdor=miqdor,
                                  narx=narx, summa=narx * miqdor))
    return h


def _tz(nomi: str, miqdor: float, guruh: str = "", tizim: str = "", **param) -> TzQator:
    return TzQator(nomi=nomi, miqdor=miqdor, guruh=guruh, tizim=tizim,
                   parametrlar=param, matn=nomi, varaq="Лист1")


# --- 1. sun'iy: KP o'qish yordamchilari ---------------------------------------


def test_pul_ustunlari_tartibga_emas_HISOBGA_qarab_aniqlanadi():
    """QQS bo'lagi PDF da alohida yoziladi — x tartibi aralashadi."""
    # 2 dona × 3 324 000 = 6 648 000; QQS 797 760; jami 7 445 760
    natija = _pul_tortligi([3324000.0, 6648000.0, 7445760.0, 797760.0], 2)
    assert natija == (3324000.0, 6648000.0, 797760.0, 7445760.0)


def test_sarlavha_qatori_mahsulot_emas():
    h = _kp(("- 9-секция", 1), ("Вентилятор канальный ВК-315С (В1)", 1))
    assert [q.raqam for q in h.mahsulotlar] == [2]


# --- 1. sun'iy: oila va kalit -------------------------------------------------


@pytest.mark.parametrize("nomi, guruh, oila", [
    ("Клпн 1000x400", "Клпн огназадернивиший", "kpu"),
    ("Клпн 300x200", "Клпн ДКС", "dks"),
    ("Решетка 150x150", "Решетка АПН", "panjara_shift"),
    ("Решетка 300x150", "Решетка АДН", "panjara_devor"),
    ("Решетка Д125", "Решетка ДПУ", "diffuzor"),
    ("Клапан дымавой сеч. 500x300 «Belimo»", "Клпн ПОЖАРНИЙ", "kpd"),
    # Guruh sarlavhasi «диффузоры» bo'lsa ham oddiy panjara diffuzor emas.
    ("Альюминевые решетка АДР-150х150мм.", "Решётки и диффузоры:", "panjara_devor"),
    # «дымоудаления» — panjara, klapan emas.
    ("Декоративная решетка для дымоудаления РКДМ-700х700", "", "panjara_metall"),
    ("Вентилятор дымоудаления ДВ1", "", "vent_sanoat"),
    ("Огнезадерживающий клапан КЛОП-1 (Н/О) 24В FD 125x100", "", "kpu"),
    ("Клапан-(НЗ) 500х500, огнезащитный", "", "kpd"),
])
def test_tz_oilasi(nomi, guruh, oila):
    assert tz_oilasi(nomi, guruh).kod == oila


def test_kp_oilasi_KCKP_tavsifidagi_sozlarga_aldanmaydi():
    """Tavsifda «наружная», «шумоглушения» bor — lekin bu konditsioner."""
    nomi = ("Кондиционер КЦКП-8 L=8000м3/ч, Р=450Па Исполнение: моноблок, "
            "наружная; секция шумоглушения; рекуператор пластинчатый")
    assert kp_oilasi(nomi).kod == "kckp"


def test_kalitlar():
    assert olcham("Дроссель клапан ДКСп 700х400х250") == "700х400"
    assert olcham("Шумоглушитель трубчатый 250*150*1000") == "250х150"
    assert diametr("Потолочный диффузор DVS 125") == "Ø125"
    assert diametr("КПД-НЗ-Н-EI60-Ф200-КН") == "Ø200"
    assert kvt("Внутренний блок кассетного типа JVI-071C") == pytest.approx(7.1)
    assert kvt("Производительность 2,64 кВт") == pytest.approx(2.64)


# --- 1. sun'iy: solishtirish ---------------------------------------------------


def test_aniq_moslik_farqsiz():
    tz = [_tz("Клпн 300x200", 59, "Клпн ДКС"), _tz("Решетка 300x150", 57, "Решетка АДН")]
    kp = _kp(("Дроссель клапан ДКСп 300х200х250", 59),
             ("Решетка вентиляционная регулируемая РВР-2 300х150мм без КРВ", 57))
    natija = solishtir(tz, kp)
    assert natija.farqlar == []
    assert natija.moslik_foizi == 100


def test_olcham_almashgani_bitta_farq_bolib_chiqadi():
    """KAM va aynan shuncha ORTIQ — ikki xato emas, bitta almashinuv."""
    tz = [_tz("Решетка 150x150", 7, "Решетка АПР")]
    kp = _kp(("Решетка вентиляционная потолочная 4РВП 300х300мм с КРВ", 7))
    natija = solishtir(tz, kp)
    assert [f.turi for f in natija.farqlar] == [OLCHAM]
    assert "150х150" in natija.farqlar[0].matn and "300х300" in natija.farqlar[0].matn


def test_taqsimot_almashgani_ham_topiladi():
    """Jami teng (25), lekin 8 dona 250х150 o'rniga 250х100 yozilgan."""
    tz = [_tz("ДКСп 250x100", 8, "Регулирующее клапана"),
          _tz("ДКСп 250х150", 17, "Регулирующее клапана")]
    kp = _kp(("Дроссель клапан ДКСп 250х100х200", 16), ("Дроссель клапан ДКСп 250х150х200", 9))
    natija = solishtir(tz, kp)
    assert [f.turi for f in natija.farqlar] == [OLCHAM]


def test_TZ_dagi_qurilma_KP_da_yoq():
    tz = [_tz("вентилятор с решеткой Compact 20", 1, tizim="В3"),
          _tz("Канальный вентилятор KV315M", 1, tizim="В1")]
    kp = _kp(("Вентилятор канальный ВК-315С (В1)", 1))
    natija = solishtir(tz, kp)
    assert [f.turi for f in natija.farqlar] == [YOQ_KPDA]
    assert "Compact" in natija.farqlar[0].matn


def test_kuchlanish_24V_220V():
    tz = [_tz("Огнезадерживающий клапан КЛОП-1 (Н/О) с приводом 24В FD 125x100", 74)]
    kp = _kp(("Клапан противопожарный КПУ-НО-Н-EI60-125х100-КН-НУП-ЭМ-М1-220", 74))
    natija = solishtir(tz, kp)
    assert [f.turi for f in natija.farqlar] == [PARAMETR]
    assert "24 V" in natija.farqlar[0].matn


def test_yongin_klapani_turi_almashgani_TEKSHIRING():
    """TZ da normal ochiq (КЛОП Н/О), KP da normal yopiq (КПД-НЗ)."""
    tz = [_tz("Огнезадерживающий клапан КЛОП-1 (Н/О) FD Ø200", 1)]
    kp = _kp(("Клапан противопожарный КПД-НЗ-Н-EI60-Ф200-КН-НУП-ЭМ", 1))
    natija = solishtir(tz, kp)
    assert [(f.turi, f.daraja) for f in natija.farqlar] == [(OLCHAM, TEKSHIRING)]


def test_KP_nomida_olcham_yoq():
    tz = [_tz("Решетка 200x150", 31, "Решетка АДН")]
    kp = _kp(("Решетка вентиляционная регулируемая", 31))
    turlar = {f.turi for f in solishtir(tz, kp).farqlar}
    assert NOM_TOLIQ_EMAS in turlar


def test_nusxa_tavsif_har_xil_narx():
    tavsif = "Кондиционер КЦКП-12,5-Г2 L=12500м3/ч, Р=400Па " + "секция " * 20
    kp = _kp((tavsif, 1, 235_200_000.0), (tavsif, 1, 775_665_000.0))
    natija = solishtir([], kp)
    assert [(f.turi, f.daraja) for f in natija.farqlar if f.turi == NUSXA] == [(NUSXA, JIDDIY)]


def test_VRF_tizim_ichida_solishtiriladi():
    """К7 dagi 18 kVt tashqi blok К8 dagi blok bilan tenglashtirilmaydi."""
    tz = [_tz("Наружный блок кондиционирования 18 кВт", 1, tizim="К7"),
          _tz("Наружный блок кондиционирования 56 кВт", 2, tizim="К8, К9")]
    kp = _kp(("- K7", 1), ("Наружный блок VRF модель JVO-155S", 1),
             ("- K8.K9", 1), ("Наружный блок VRF модель JVO-560T", 2))
    natija = solishtir(tz, kp)
    assert all(f.daraja == MALUMOT for f in natija.farqlar)
    assert natija.mos_guruhlar == 2


def test_VRF_tizimi_bitta_qator_KP_bolimi_bilan_qoplanadi():
    tz = [_tz("К5. Система VRF кондиционирования", 1)]
    kp = _kp(("- (Система К5)", 1), ("Наружный блок VRF модель JVO-335T", 2))
    natija = solishtir(tz, kp)
    assert natija.farqlar == []
    assert natija.mos_guruhlar == 1


# --- 1. sun'iy: Excel TZ ----------------------------------------------------------


def _kitob(tmp_path, varaqlar: dict[str, list[list]]) -> Path:
    import openpyxl

    kitob = openpyxl.Workbook()
    kitob.remove(kitob.active)
    for nom, qatorlar in varaqlar.items():
        v = kitob.create_sheet(nom)
        for q in qatorlar:
            v.append(q)
    yol = tmp_path / "tz.xlsx"
    kitob.save(yol)
    return yol


def test_royxat_bolim_sarlavhasi_guruhga_tushadi(tmp_path):
    yol = _kitob(tmp_path, {"Нирвана": [
        ["№", "Наименование материалов", "Ед-изм", "Кол-во"],
        [None, "Решетка АДН", None, None],
        [1, "Решетка 300x150", "шт", 57],
    ]})
    q = jadval_oqi(yol).qatorlar
    assert [(x.nomi, x.miqdor, x.guruh) for x in q] == [("Решетка 300x150", 57, "Решетка АДН")]


def test_bir_xil_varaq_ikki_marta_sanalmaydi(tmp_path):
    jadval = [["Позиция", "Наименование", "Ед. изм", "Кол-во"],
              ["ПВ1", "Система ПВ1:", None, None],
              [None, "Дроссель-клапан ДКСп 250x200мм", "шт", 4]]
    j = jadval_oqi(_kitob(tmp_path, {"Лист1": jadval, "ЗакСпец": jadval}))
    assert len(j.qatorlar) == 1
    assert j.qatorlar[0].tizim == "ПВ1"
    assert "bir xil" in j.ogohlantirishlar[0]


def test_kop_qatorli_sarlavhaning_ichki_Kol_vo_si_asosiy_emas(tmp_path):
    """Zayavkada 2-sarlavha qatorida ham «Кол-во» bor (filtr soni)."""
    yol = _kitob(tmp_path, {"9 СЕК": [
        ["9 СЕКЦИЯ"],
        ["Обозначение", "Наименование", "Тип", "Ед. изм", "Кол-во", "Вентилятор", None, None],
        [None, None, None, None, None, "L м3/ч", "Р, Па", "Кол-во"],
        ["В1", "Канальный вентилятор", "KV315M", "шт", 1, 1240, 300, None],
    ]})
    q = jadval_oqi(yol).qatorlar
    assert len(q) == 1
    assert q[0].tizim == "В1" and q[0].bolim == "9 СЕКЦИЯ"
    assert q[0].parametrlar == {"L": 1240, "P": 300}


def test_belgi_ustuni_nomsiz_va_davom_qatori(tmp_path):
    yol = _kitob(tmp_path, {"Лист1": [
        [None, None, None, None, "Кол-во"],
        [None, "К6, К6р", "Сплит-система, подвесная", "14,07 кВт", 2],
        [None, None, "Вн.блок кассетного типа", "14,07 кВт", 2],
    ]})
    q = jadval_oqi(yol).qatorlar
    assert [x.tizim for x in q] == ["К6, К6р", "К6, К6р"]


# --- 1. sun'iy: VENTAS ------------------------------------------------------------


def test_turkcha_sonlar():
    assert _son("18.250") == 18250
    assert _son("158,7") == pytest.approx(158.7)
    assert _son("1.045") == 1045


def test_ventas_HEPA_va_glikolli_rekuperator():
    q = Qurilma(nomi="AHU-11", kodlar=["RAC", "CWC", "HWC"], sarf=18250, bosim=1045,
                filtrlar=["G4", "F7", "F9", "H14"])
    kp = _kp(("Кондиционер КЦКП-20-Г2 L=18250м3/час; Р=750Па; ФяГ G4; ФЯК F7; "
              "Пластинчатий рекуператор", 1))
    matnlar = [f.matn for f in ventas_solishtir([q], kp).farqlar]
    assert any("H14" in m for m in matnlar)
    assert any("glikolli" in m for m in matnlar)
    assert any("1045 Pa" in m for m in matnlar)


def test_ventas_qurilma_KP_da_yoq():
    q = Qurilma(nomi="HEF-01", sarf=8000, filtrlar=["elektrostatik"])
    natija = ventas_solishtir([q], _kp(("Кондиционер КЦКП-5 L=4500м3/ч", 1)))
    assert any(f.turi == YOQ_KPDA and "HEF-01" in f.matn for f in natija.farqlar)


# --- 2. ETALON: haqiqiy 7 juft -----------------------------------------------------

etalon = pytest.mark.skipif(not ETALON.is_dir(), reason="tests/etalon_tz/ yo'q (git ga kirmaydi)")


def _juft(papka: str):
    from kp.kp_pdf import kp_oqi

    tz = []
    for yol in sorted((ETALON / papka).glob("tz*.xlsx")):
        tz += jadval_oqi(yol).qatorlar
    return tz, kp_oqi(ETALON / papka / "kp.pdf")


@etalon
@pytest.mark.parametrize("papka, qatorlar, raqam", [
    ("1-murod", 44, "13603/9"),
    ("2-provik-skan", 19, "13508/9"),
    ("3-provik-zarafshon", 203, "12748/5"),
    ("4-enter-k1-k12", 27, "13321/8"),
    ("5-enter-alm", 33, "13173/7"),
    ("6-nirvana", 44, "13357/8"),
    ("7-provik-ventas", 25, "13574/9"),
])
def test_etalon_KP_toliq_oqiladi(papka, qatorlar, raqam):
    """Qatorlar yig'indisi «Итого» ga teng — hech bir qator tushib qolmagan."""
    from kp.kp_pdf import kp_oqi

    h = kp_oqi(ETALON / papka / "kp.pdf")
    assert len(h.qatorlar) == qatorlar
    assert h.raqam == raqam
    assert h.yigindi_mosmi()


@etalon
def test_etalon_sahifadan_otgan_nom_ulanadi():
    """Nirvana 21-qator nomi keyingi sahifada tugaydi — o'lcham o'sha yerda."""
    _, kp = _juft("6-nirvana")
    assert "200х150" in kp.qatorlar[20].nomi


@etalon
def test_etalon_1_murod():
    natija = solishtir(*_juft("1-murod"))
    matnlar = [f.matn for f in natija.farqlar]
    assert any("Compact" in m and f.turi == YOQ_KPDA for f, m in zip(natija.farqlar, matnlar))
    assert any("ДУ1" in m and "15" in m and "18.5" in m for m in matnlar)


@etalon
def test_etalon_3_zarafshon():
    natija = solishtir(*_juft("3-provik-zarafshon"))
    matnlar = " | ".join(f.matn for f in natija.farqlar)
    assert "24 V" in matnlar
    assert "CAV" in matnlar
    assert "250х150" in matnlar and "250х100" in matnlar
    assert natija.moslik_foizi >= 85


@etalon
def test_etalon_4_enter_faqat_malumot():
    """Hamma VRF/split tizim ichida topiladi — tekshiriladigan farq yo'q."""
    natija = solishtir(*_juft("4-enter-k1-k12"))
    assert all(f.daraja == MALUMOT for f in natija.farqlar)


@etalon
def test_etalon_5_alm_tizimlar_va_aloqasiz_varaqlar():
    natija = solishtir(*_juft("5-enter-alm"))
    assert natija.mos_guruhlar >= 6         # К1–К6 KP bo'limlarida bor
    assert len([f for f in natija.farqlar if f.turi == "aloqasiz"]) == 3


@etalon
def test_etalon_6_nirvana_faqat_150_300():
    natija = solishtir(*_juft("6-nirvana"))
    jiddiylar = [f for f in natija.farqlar if f.daraja != MALUMOT]
    assert len(jiddiylar) == 1
    assert "150х150" in jiddiylar[0].matn and "300х300" in jiddiylar[0].matn
    assert natija.moslik_foizi >= 95


@etalon
def test_etalon_6_nirvana_mavjud_generator_hamma_qatorni_katalog_nomiga_aylantiradi():
    """`kp/shakl.mahsulot_royxati` + qisqartmalar — botdagi ro'yxat yo'li.

    2026-10-03 gacha «Клпн огназадернивиший» va «Клпн ПОЖАРНИЙ» bo'limlari
    (88 klapan — KP ning eng qimmat qatorlari) tanilmasdi: jadvalda faqat
    «клп» bor edi. Endi 44/44. ДКСп uzunligi (3-o'lcham) ataylab menejerga
    qoldiriladi — haqiqiy KP larda u bir xil emas (300 balandlik bir KP da
    250, boshqasida 350).
    """
    from kp.shakl import mahsulot_royxati

    tz, kp = _juft("6-nirvana")
    satrlar, oldingi = [], None
    for q in tz:
        if q.guruh != oldingi:
            satrlar.append(q.guruh + ":")
            oldingi = q.guruh
        satrlar.append(f"{q.nomi} — {q.miqdor:g} шт")
    yasalgan = mahsulot_royxati("\n".join(satrlar))
    assert sum("asl_nomi" in y for y in yasalgan) == 44
    assert [y["miqdor"] for y in yasalgan] == [q.miqdor for q in kp.mahsulotlar]


@etalon
def test_etalon_7_ventas():
    from kp.kp_pdf import kp_oqi
    from kp.ventas import papka_oqi

    natija = ventas_solishtir(papka_oqi(ETALON / "7-provik-ventas" / "tz"),
                              kp_oqi(ETALON / "7-provik-ventas" / "kp.pdf"))
    matnlar = [f.matn for f in natija.farqlar]
    assert any("HEF-01" in m and "KP da yo'q" in m for m in matnlar)
    assert sum("H14" in m for m in matnlar) == 2            # AHU-11, AHU-13
    assert sum("glikolli" in m for m in matnlar) == 2
    assert any(f.turi == NUSXA and "5, 21" in f.matn for f in natija.farqlar)
    assert any("AHU-14" in m and "1710 Pa" in m for m in matnlar)
    assert any("AHU-01" in m and "F9" in m for m in matnlar)

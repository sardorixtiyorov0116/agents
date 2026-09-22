"""«Katalogda ko'rdim — narxi qancha?» savoliga javob.

NEGA BU TESTLAR BOR
-------------------
Bu mijozning ENG KO'P beradigan savoli. Ilgari u routerga, undan
agentga borardi: 10-30 soniya kutish, bir so'rov puli, natija esa
baribir "menejerimiz bog'lanadi".

HALOL CHEGARA. Katalogda 1482 modeldan atigi 24 tasida narx bor.
Shuning uchun uchta yo'l ATAYLAB ajratilgan va uchalasi ham
tekshiriladi: narx bor / model bor-narx yo'q / model umuman yo'q.
"Taxminan shuncha" degan to'rtinchi yo'l YO'Q — mijoz uni eslab qoladi
va haqiqiy narx chiqqanda nizo bo'ladi.
"""

from __future__ import annotations

import pytest

from sorovnoma.narx_sorov import (
    javob_matni,
    model_ajrat,
    narx_soralyaptimi,
    narxni_top,
)

KATALOG = [
    {
        "name_uz": "Radial ventilyator",
        "characters": [
            {
                "title": "ВЦ 4-75-2,5",
                "insides": [
                    {"in_model_name": "ВЦ 4-75-2,5-1-0,12/1500", "price": 156.76},
                    {"in_model_name": "ВЦ 4-75-2,5-1-0,25/3000", "price": 210.00},
                ],
            },
            {
                "title": "ВЦ 4-75-6,3",
                "insides": [{"in_model_name": "ВЦ 4-75-6,3-1-4/1000"}],
            },
        ],
    },
    {
        "name_uz": "Markaziy qurilma",
        "characters": [{"title": "КЦКП-40", "insides": [{"in_model_name": "КЦКП-40"}]}],
    },
]


# --- Savolni tanish -----------------------------------------------------------


@pytest.mark.parametrize("matn", [
    "ВЦ 4-75 narxi qancha",
    "сколько стоит КЦКП",
    "цена на фильтр",
    "qancha turadi",
    "price?",
])
def test_narx_savoli_tanilardi(matn):
    assert narx_soralyaptimi(matn) is True


@pytest.mark.parametrize("matn", [
    "salom",
    "800 kv metr ombor uchun nima kerak",
    "yetkazib berasizmi",
])
def test_boshqa_savollar_narx_deb_belgilanmaydi(matn):
    assert narx_soralyaptimi(matn) is False


# --- Model ajratish -----------------------------------------------------------


@pytest.mark.parametrize("matn,kutilgan", [
    ("ВЦ 4-75-6,3 narxi qancha", "ВЦ 4-75-6,3"),
    ("сколько стоит КЦКП-40", "КЦКП-40"),
    ("Цена на ВКР-5", "ВКР-5"),
])
def test_RAQAMLI_model_katalogsiz_ajratiladi(matn, kutilgan):
    """Raqamli model nomi namunadan taniladi — katalog kerak emas."""
    assert model_ajrat(matn) == kutilgan


def test_RAQAMSIZ_oila_uchun_katalog_KERAK():
    """Oilalar ro'yxati endi kodda emas, katalogdan olinadi.

    Ilgari u qo'lda sanalgan edi va «РКВ» unutilgandi — mijoz
    javob ololmasdi. Katalogdan olish shu xatoni takrorlanmas qiladi.
    """
    katalog = [{"characters": [{"title": "ФЯК", "insides": [
        {"in_model_name": "ФЯК 592х592", "price": 46.0}]}]}]

    assert model_ajrat("ФЯК filtr narxi") is None
    assert model_ajrat("ФЯК filtr narxi", katalog) == "ФЯК"


def test_ENG_UZUN_moslik_olinadi():
    """«ВЦ 4» bilan qidirsak noto'g'ri model chiqardi."""
    assert model_ajrat("ВЦ 4-75-6,3 kerak") == "ВЦ 4-75-6,3"


def test_modelsiz_matndan_None():
    assert model_ajrat("salom qandaysiz") is None


def test_modelsiz_sorovda_narxni_top_None_qaytaradi():
    """Matnda model yo'q — so'rov ODATDAGI yo'l bilan ketsin."""
    assert narxni_top(KATALOG, "narxlaringiz qanday", kurs=12000.0) is None


# --- Uch yo'l -----------------------------------------------------------------


def test_narx_BOR_bolsa_aytiladi():
    j = narxni_top(KATALOG, "ВЦ 4-75-2,5 narxi", kurs=12000.0)

    assert j.holat == "narx"
    assert j.narx == pytest.approx(156.76 * 12000)


def test_narxi_yoq_model_KATALOGDA_borligi_aytiladi():
    j = narxni_top(KATALOG, "КЦКП-40 narxi", kurs=12000.0)

    assert j.holat == "narxsiz"
    assert j.model == "КЦКП-40"


def test_notanish_model_TOPILMADI():
    j = narxni_top(KATALOG, "ХХХ 999-88 narxi", kurs=12000.0)

    assert j.holat == "topilmadi"


def test_topilmaganda_YAQIN_nomlar_taklif_qilinadi():
    """«Topilmadi» deb to'xtash mijozni ketkazadi."""
    j = narxni_top(KATALOG, "ВЦ 999-77 narxi", kurs=12000.0)

    assert j.holat == "topilmadi"
    assert j.takliflar
    assert all(t.startswith("ВЦ") for t in j.takliflar)


# --- Javob matni --------------------------------------------------------------


def test_narx_javobida_son_va_manba_bor():
    j = narxni_top(KATALOG, "ВЦ 4-75-2,5 narxi", kurs=12000.0)

    matn = javob_matni(j, "+998 78 150 00 07")

    assert "1 881 120" in matn
    assert "QQS bilan" in matn
    assert "+998 78 150 00 07" in matn


def test_narxsiz_javobida_TAXMINIY_son_YOQ():
    """«Taxminan $500-800» keyin nizoga sabab bo'ladi."""
    j = narxni_top(KATALOG, "КЦКП-40 narxi", kurs=12000.0)

    matn = javob_matni(j)

    assert "taxmin" not in matn.lower()
    assert "so'm" not in matn
    assert "menejerimiz" in matn.lower()


def test_topilmagan_javobida_takliflar_korinadi():
    j = narxni_top(KATALOG, "ВЦ 999-77 narxi", kurs=12000.0)

    matn = javob_matni(j)

    assert "Balki bulardan biri?" in matn


def test_javob_matni_TELEGRAM_uchun_qisqa():
    """Telegram xabari 4096 belgi."""
    for sorov in ("ВЦ 4-75-2,5 narxi", "КЦКП-40 narxi", "ВЦ 999-77 narxi"):
        j = narxni_top(KATALOG, sorov, kurs=12000.0)
        assert len(javob_matni(j, "+998 78 150 00 07")) < 4096


# --- Oila nomlari KATALOGDAN olinadi ------------------------------------------
#
# JONLI XATO (2026-08-28): raqamsiz oila nomlari kodda QO'LDA sanalgan
# edi (РВН, РВИ, ФЯК…) va ro'yxatda «РКВ» yo'q edi. Mijoz «РКВ narxi
# qancha» deb so'raganda model ajratilmadi, savol LLM yo'liga tushdi —
# 10-30 soniya kutish va oxirida «topilmadi», holbuki katalogda
# РКВ-150 bor va narxi ham bor.

KATALOG_RKV = [{
    "name_uz": "Kanal isitgichi",
    "characters": [{"title": "РКВ", "price": 0, "insides": [
        {"in_model_name": "РКВ-150", "price": 1154.0},
        {"in_model_name": "РКВ1-260", "price": 1607.0},
    ]}],
}]


def test_raqamsiz_oila_KATALOGDAN_taniladi():
    from sorovnoma.narx_sorov import model_ajrat

    assert model_ajrat("РКВ narxi qancha", KATALOG_RKV) == "РКВ"


def test_katalogsiz_raqamsiz_oila_TANILMAYDI():
    """Katalog berilmasa eski xatti-harakat — bu kutilgan."""
    from sorovnoma.narx_sorov import model_ajrat

    assert model_ajrat("РКВ narxi qancha") is None


def test_raqamli_model_katalogsiz_ham_taniladi():
    from sorovnoma.narx_sorov import model_ajrat

    assert model_ajrat("ВЦ 4-75-6,3 narxi") == "ВЦ 4-75-6,3"


# --- Lotincha yozilish --------------------------------------------------------
#
# Mijoz klaviaturasiga qarab yozadi, katalogga qarab emas.


@pytest.mark.parametrize("yozilgan", ["RKV narxi", "rkv narxi", "PKB narxi"])
def test_LOTINCHA_yozilgan_oila_taniladi(yozilgan):
    from sorovnoma.narx_sorov import model_ajrat

    assert model_ajrat(yozilgan, KATALOG_RKV) == "РКВ"


def test_transliteratsiya_va_KORINISH_ikkalasi_ham():
    """В -> V (talaffuz) va В -> B (harf shakli)."""
    from sorovnoma.narx_sorov import lotincha_shakllar

    shakllar = lotincha_shakllar("РКВ")

    assert "RKV" in shakllar
    assert "PKB" in shakllar


def test_oddiy_soz_model_deb_QABUL_QILINMAYDI():
    from sorovnoma.narx_sorov import model_ajrat

    assert model_ajrat("salom qalaysiz", KATALOG_RKV) is None


def test_qidiruv_TEZ_ishlaydi():
    """Mijoz kutmasligi kerak — bu yo'l LLM ishlatmaydi."""
    import time

    from sorovnoma.narx_sorov import narxni_top

    boshlandi = time.perf_counter()
    natija = narxni_top(KATALOG_RKV, "RKV narxi qancha", kurs=12000.0)
    ketgan = time.perf_counter() - boshlandi

    assert natija is not None and natija.holat == "narx"
    assert ketgan < 0.5


# --- Valyuta ------------------------------------------------------------------
#
# JONLI XATO (2026-08-28): chiller narxi 12 391 so'm bo'lib chiqardi,
# haqiqiysi 148 692 000 so'm — 12 000 BAROBAR kam. Sabab:
# `characters[].price` SO'M deb o'qilardi, aslida u DOLLARDA.
#
# `models` maydoni katalogda umuman yo'q (0/137 mahsulot), ya'ni eski
# so'mli yo'l o'lik edi.


def test_characters_narxi_DOLLARDA_deb_oqiladi():
    from integrations.climavent_client import katalog_narxi

    katalog = [{
        "name_uz": "Sovitish mashinasi JV (chiller)",
        "characters": [{"title": "JV-65", "price": 12391}],
    }]

    narx, _ = katalog_narxi(katalog, "JV-65", kurs=12000.0)

    assert narx == 12391 * 12000


def test_insides_narxi_ham_DOLLARDA():
    from integrations.climavent_client import katalog_narxi

    narx, _ = katalog_narxi(KATALOG_RKV, "РКВ-150", kurs=12000.0)

    assert narx == 1154.0 * 12000


# --- Narx savolini tanish: MODEL nomi ham yetarli ------------------------------
#
# JONLI XATO (2026-08-28): mijoz «ПВН nechpul» deb yozdi. «nechpul»
# (probelsiz) qo'lda yozilgan so'zlar ro'yxatida yo'q edi — savol LLM
# yo'liga tushdi va «menejerimiz aniqroq javob beradi» degan quruq
# javob qaytdi. Holbuki ПВН katalogda bor va narxi ham bor.
#
# Bunday ro'yxat HECH QACHON to'liq bo'lmaydi: «pochom», «skolko»,
# imlo xatolari, aralash til. Shuning uchun ikkinchi yo'l qo'shildi:
# katalogdagi model nomi + qisqa jumla = shu mahsulot haqida savol.

KATALOG_PVN = [{
    "name_uz": "Panjara",
    "characters": [{"title": "ПВН 400-200/2", "insides": [
        {"in_model_name": "ПВН 400-200/2", "price": 106.0}]}],
}]


@pytest.mark.parametrize("matn", [
    "ПВН nechpul",
    "ПВН",
    "ПВН bormi",
    "ПВН 400-200 kerak edi",
])
def test_MODEL_nomi_narx_savoli_deb_qabul_qilinadi(matn):
    from sorovnoma.narx_sorov import narx_soralyaptimi

    assert narx_soralyaptimi(matn, KATALOG_PVN) is True


def test_ANIQ_soz_katalogsiz_ham_ishlaydi():
    from sorovnoma.narx_sorov import narx_soralyaptimi

    assert narx_soralyaptimi("narxi qancha") is True
    assert narx_soralyaptimi("сколько стоит") is True


@pytest.mark.parametrize("matn", [
    "ПВН ni qanday o'rnatiladi va qanaqa sxema kerak bo'ladi",
    "salom qalaysiz",
    "800 kv metr ombor uchun ventilyatsiya kerak",
])
def test_UZUN_yoki_modelsiz_savol_agentga_ketadi(matn):
    """Narx yo'liga tushib qolsa mijoz noto'g'ri javob olardi."""
    from sorovnoma.narx_sorov import narx_soralyaptimi

    assert narx_soralyaptimi(matn, KATALOG_PVN) is False


def test_nechpul_va_boshqa_yozilishlar():
    from sorovnoma.narx_sorov import narx_soralyaptimi

    for matn in ("nechpul", "necha pul", "necha so'm", "pochom", "сколько"):
        assert narx_soralyaptimi(matn) is True, matn

"""Texnik jadvaldan havo sarfi va bosimni o'qish.

MUAMMO (2026-08-11 da o'lchangan): backendda ventilyatorning havo sarfi
uchun maydon yo'q — `product_models` da faqat nom, narx, SAP kodi. Shu
sababli 800 m² omborga 8000 m³/soat kerak deb HISOBLANGANDAN keyin ham
mos ventilyator topilmasdi va KP ga deflektor (aksessuar) tushib qolardi.

Ma'lumotning o'zi bor — `characters[].contentJson` dagi R2 hujjatida,
jadval ko'rinishida. Shu testlar o'sha jadvalni o'qishni qoplaydi.

Jadval namunalari JONLI katalogdan olingan (mahsulot id lari izohda).
"""

from __future__ import annotations

import pytest

from integrations.texnik import (
    ModelParametri,
    hujjatdan_parametrlar,
    jadval_gridlari,
    jadvaldan_parametrlar,
    moslashtir,
    nomlash,
    son_oraligi,
    ustun_turi,
)


# --- ustun nomini tanish ------------------------------------------------------


@pytest.mark.parametrize("sarlavha,kutilgan", [
    ("Производительность, м3/ч", "havo"),
    ("Максимальная производительность, м3/ч", "havo"),
    ("Производительность по воздуху, м3/час", "havo"),
    ("Расход воздуха", "havo"),
    ("Полное давление, Па", "bosim"),
    ("Максимальное давление, Па", "bosim"),
    ("Мощность, кВт", "quvvat"),
    ("Модель", None),
    ("Масса, кг не более", None),
    ("Частота вращения, об/мин", None),
])
def test_ustun_turi(sarlavha, kutilgan):
    assert ustun_turi(sarlavha) == kutilgan


@pytest.mark.parametrize("sarlavha", [
    # Bular ham "производительность"/"давление" so'zini o'z ichiga oladi,
    # lekin BOSHQA kattalik — havo sarfi deb olinsa KP buziladi.
    "Производительность по теплу, кВт",
    "Номинальная теплопроизводительность",
    "Номинальный расход воды, т/ч",
    "Холодопроизводительность, кВт",
])
def test_havo_bilan_adashtirmaydi(sarlavha):
    assert ustun_turi(sarlavha) != "havo"


def test_bug_bosimi_bosim_emas():
    """"Давление греющего пара" — bu ventilyator bosimi emas."""
    assert ustun_turi("Давление греющего пара, кгс/см2") != "bosim"


# --- sonlarni o'qish ----------------------------------------------------------


@pytest.mark.parametrize("matn,kutilgan", [
    ("1425", (1425.0, 1425.0)),
    ("570-800", (570.0, 800.0)),
    ("4200-13100", (4200.0, 13100.0)),
    ("1,60-3,75", (1.6, 3.75)),
    ("10…20", (10.0, 20.0)),
    ("0,98", (0.98, 0.98)),
])
def test_son_oraligi(matn, kutilgan):
    assert son_oraligi(matn) == kutilgan


@pytest.mark.parametrize("matn", ["", "-", "Рассчитывается индивидуально", "подбор"])
def test_son_yoq(matn):
    assert son_oraligi(matn) is None


# --- jadvalni to'rga aylantirish ---------------------------------------------


def hujjat_yasa(qatorlar: list[list[dict]]) -> dict:
    """ProseMirror jadvalini soddalashtirib yasaydi."""
    def katak(matn: str, colspan: int = 1, rowspan: int = 1) -> dict:
        return {
            "type": "tableCell",
            "attrs": {"colspan": colspan, "rowspan": rowspan},
            "content": [{"type": "paragraph",
                         "content": [{"type": "text", "text": matn}]}],
        }

    return {
        "type": "doc",
        "content": [{
            "type": "table",
            "content": [
                {"type": "tableRow", "content": [katak(**k) for k in qator]}
                for qator in qatorlar
            ],
        }],
    }


def test_colspan_ustunlarni_surmaydi():
    """`colspan` hisobga olinmasa ustun raqami siljib, xato qiymat o'qiladi."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Электродвигатель", "colspan": 2},
         {"matn": "Производительность, м3/ч"}],
        [{"matn": "ВЦ 14-46-2"}, {"matn": "0,18"}, {"matn": "1500"},
         {"matn": "570-800"}],
    ])

    grid = jadval_gridlari(hujjat)[0]

    assert grid[0] == ["Модель", "Электродвигатель", "Электродвигатель",
                       "Производительность, м3/ч"]
    assert grid[1][3] == "570-800"


def test_rowspan_keyingi_qatorga_tushadi():
    hujjat = hujjat_yasa([
        [{"matn": "Модель", "rowspan": 2}, {"matn": "Производительность", "colspan": 2}],
        [{"matn": "по воздуху, м3/час"}, {"matn": "по теплу, кВт"}],
        [{"matn": "КСК 113-2-01"}, {"matn": "2000"}, {"matn": "29"}],
    ])

    grid = jadval_gridlari(hujjat)[0]

    assert grid[0][0] == "Модель"
    assert grid[1][0] == "Модель", "rowspan ikkinchi qatorga tushmadi"
    assert grid[1][1] == "по воздуху, м3/час"


# --- jadvaldan parametr ajratish ----------------------------------------------


def test_ikki_qatorli_sarlavha_oqiladi():
    """Mahsulot 15 (Теплообменник КСК) shakli."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель", "rowspan": 2}, {"matn": "Производительность", "colspan": 2}],
        [{"matn": "по воздуху, м3/час"}, {"matn": "по теплу, кВт"}],
        [{"matn": "КСК 113-2-01"}, {"matn": "2000"}, {"matn": "29"}],
    ])

    natija = hujjatdan_parametrlar(hujjat)

    assert len(natija) == 1
    assert natija[0].model == "КСК 113-2-01"
    assert natija[0].havo_maks == 2000
    # "по теплу, кВт" — havo emas, u olinmasligi kerak.
    assert natija[0].havo_min == 2000


def test_oraliqli_qiymat_va_bosim():
    """Mahsulot 51 (Вентилятор ВЦ 14-46) shakli."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Мощность, кВт"},
         {"matn": "Производительность, м3/ч"}, {"matn": "Полное давление, Па"},
         {"matn": "Масса, кг не более"}],
        [{"matn": "ВЦ 14-46-2"}, {"matn": "0,18"}, {"matn": "570-800"},
         {"matn": "270-310"}, {"matn": "21"}],
    ])

    natija = hujjatdan_parametrlar(hujjat)[0]

    assert (natija.havo_min, natija.havo_maks) == (570, 800)
    assert (natija.bosim_min, natija.bosim_maks) == (270, 310)
    assert natija.quvvat_kvt == 0.18


def test_minglik_birlik_kopaytiriladi():
    """"тыс. м³/ч" — ming marta ko'p. Bu e'tibordan qolsa 1000 marta xato."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Производительность, тыс. м3/ч"}],
        [{"matn": "ВНР-4-0,18"}, {"matn": "1,60-3,75"}],
    ])

    natija = hujjatdan_parametrlar(hujjat)[0]

    assert (natija.havo_min, natija.havo_maks) == (1600, 3750)


def test_takrorlanuvchi_ustun_guruhi():
    """Mahsulot 5 (КЦКП): "Модель | Производительность" juftligi ikki marta."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель кондиционера"}, {"matn": "Номинальная производительность, м3/ч"},
         {"matn": "Модель кондиционера"}, {"matn": "Номинальная производительность, м3/ч"}],
        [{"matn": "КЦКП-1,6"}, {"matn": "1600"},
         {"matn": "КЦКП-31,5"}, {"matn": "31500"}],
    ])

    natija = {p.model: p.havo_maks for p in hujjatdan_parametrlar(hujjat)}

    assert natija == {"КЦКП-1,6": 1600, "КЦКП-31,5": 31500}


def test_hisoblanadi_deb_yozilgan_qator_tashlanadi():
    """Mahsulot 13 (ВНВ): qiymat o'rniga "Рассчитывается индивидуально"."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Производительность по воздуху, м3/час"}],
        [{"matn": "ВНВ 243.1-116"}, {"matn": "Рассчитывается индивидуально"}],
    ])

    assert hujjatdan_parametrlar(hujjat) == []


def test_havo_ustuni_yoq_jadval_tashlanadi():
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Масса, кг"}],
        [{"matn": "ДР710"}, {"matn": "12"}],
    ])

    assert hujjatdan_parametrlar(hujjat) == []


def test_ishonchsiz_katta_son_olinmaydi():
    """Ustun noto'g'ri o'qilsa (masalan og'irlik) — qiymat rad etiladi."""
    hujjat = hujjat_yasa([
        [{"matn": "Модель"}, {"matn": "Производительность, м3/ч"}],
        [{"matn": "ВЦ 14-46-2"}, {"matn": "9000000"}],
    ])

    assert hujjatdan_parametrlar(hujjat) == []


# --- jadval nomini katalog nomiga bog'lash ------------------------------------


def test_prefiks_boyicha_boglanadi():
    """Jadvalda "ВЦ 14-46-2", katalogda "ВЦ 14-46-2,0-1" — bir xil o'lcham."""
    parametr = ModelParametri(model="ВЦ 14-46-2", havo_min=570, havo_maks=800)

    natija = moslashtir([parametr], ["ВЦ 14-46-2,0-1", "ВЦ 14-46-2,0-4"])

    assert set(natija) == {"ВЦ 14-46-2,0-1", "ВЦ 14-46-2,0-4"}
    assert natija["ВЦ 14-46-2,0-1"].havo_maks == 800


def test_boshqa_olcham_boglanmaydi():
    """ENG XAVFLI XATO: "ВЦ 14-46-2" ni "ВЦ 14-46-2,5" ga bog'lash.

    Bular boshqa g'ildirak — havo sarfi ham boshqacha.
    """
    parametr = ModelParametri(model="ВЦ 14-46-2", havo_min=570, havo_maks=800)

    natija = moslashtir([parametr], ["ВЦ 14-46-2,5-1"])

    assert natija == {}


def test_ajratgich_farqi_halaqit_bermaydi():
    """Jadvalda "ПВН 500-300/2", katalogda "ПВН 500-300-2"."""
    parametr = ModelParametri(model="ПВН 500-300/2", havo_min=800, havo_maks=800)

    natija = moslashtir([parametr], ["ПВН 500-300-2"])

    assert natija["ПВН 500-300-2"].havo_maks == 800


def test_katalogda_yoq_model_tushmaydi():
    """O'ylab topilgan model KP ga tushmasligi kerak."""
    parametr = ModelParametri(model="ВОД 112", havo_maks=31140)

    assert moslashtir([parametr], ["ВОД-040-ДУ-0,18-1350"]) == {}


def test_uzunroq_nom_ustun_turadi():
    """"В-2" qisqa nomi "В-25-1" ni o'g'irlab ketmasin."""
    qisqa = ModelParametri(model="В-2", havo_maks=1000)
    uzun = ModelParametri(model="В-25", havo_maks=5000)

    natija = moslashtir([qisqa, uzun], ["В-25-1"])

    assert natija["В-25-1"].havo_maks == 5000


@pytest.mark.parametrize("xom,kutilgan", [
    ("ВЦ 14-46-2,0-1", "ВЦ14-46-2-1"),
    ("ВЦ 14-46-2,5-1", "ВЦ14-46-2.5-1"),
    ("вк-250п", "ВК-250П"),
])
def test_nomlash(xom, kutilgan):
    assert nomlash(xom) == kutilgan


# --- asosiy qoida -------------------------------------------------------------


def test_raqam_modeldan_kelmaydi():
    """Havo sarfi FAQAT jadvaldan olinadi — LLM bu yerga aralashmaydi."""
    import ast
    import inspect

    import integrations.texnik as modul

    daraxt = ast.parse(inspect.getsource(modul))
    importlar: set[str] = set()
    for tugun in ast.walk(daraxt):
        if isinstance(tugun, ast.Import):
            importlar.update(a.name.split(".")[0] for a in tugun.names)
        elif isinstance(tugun, ast.ImportFrom) and tugun.module:
            importlar.add(tugun.module.split(".")[0])

    for taqiq in ("anthropic", "openai", "app"):
        assert taqiq not in importlar, f"parametr ajratishga model kirib qolgan: {taqiq}"


def test_bosh_jadval_yiqilmaydi():
    assert jadvaldan_parametrlar([]) == []
    assert jadvaldan_parametrlar([["Модель"]]) == []
    assert hujjatdan_parametrlar({}) == []
    assert hujjatdan_parametrlar(None) == []


# --- Rustam ventilyatorni havo sarfi bo'yicha tanlaydi ------------------------


class SoxtaApi:
    def __init__(self, parametrlar):
        self._parametrlar = parametrlar

    async def texnik_parametrlar(self):
        return self._parametrlar


def rustam_yasa(parametrlar):
    from app.agentlar.loyihachi import Loyihachi

    agent = Loyihachi.__new__(Loyihachi)
    agent.api = SoxtaApi(parametrlar)
    return agent


KATALOG = {
    "ВК-315П": {"havo_sarfi": 2110, "bosim": 550, "turi": "ВК-П ventilyatori"},
    "ВЦ 14-46-5-1": {"havo_sarfi": [5000, 8400], "bosim": [860, 1070],
                     "turi": "Ventilyator VC 14-46"},
    "ВЦ 14-46-8-1": {"havo_sarfi": [14000, 31000], "bosim": [900, 1200],
                     "turi": "Ventilyator VC 14-46"},
    # Ventilyator EMAS — havo sarfi bo'lsa ham tanlanmasligi kerak.
    "КЦКП-31,5": {"havo_sarfi": 31500, "turi": "Markaziy konditsioner KЦKП"},
    "КСК 113-2-01": {"havo_sarfi": 2000, "turi": "Issiqlik almashtirgich KSK"},
}


@pytest.mark.asyncio
async def test_eng_kichik_yetadigan_ventilyator_birinchi():
    """8000 m³/soat ga 31000 lik emas, 8400 lik mos keladi."""
    natija = await rustam_yasa(KATALOG)._ventilyatorlar(8000)

    assert [x["model"] for x in natija] == ["ВЦ 14-46-5-1", "ВЦ 14-46-8-1"]
    assert natija[0]["zaxira_foiz"] == 5
    assert natija[0]["bosim"] == [860, 1070]


@pytest.mark.asyncio
async def test_ventilyator_bolmagan_uskuna_tanlanmaydi():
    """Markaziy konditsioner va issiqlik almashgich — ventilyator emas."""
    natija = await rustam_yasa(KATALOG)._ventilyatorlar(2000)

    turlari = {x["turi"] for x in natija}
    assert not any("onditsioner" in t or "almashtirgich" in t for t in turlari)


@pytest.mark.asyncio
async def test_yetmaydigan_ventilyator_tushmaydi():
    natija = await rustam_yasa(KATALOG)._ventilyatorlar(50_000)

    assert natija == []


@pytest.mark.asyncio
async def test_sarf_nol_bolsa_soralmaydi():
    """Hisob chiqmagan bo'lsa katalogga umuman bormaymiz."""
    class Yiqiladigan:
        async def texnik_parametrlar(self):
            raise AssertionError("sarf 0 bo'lganda API chaqirilmasligi kerak")

    agent = rustam_yasa(KATALOG)
    agent.api = Yiqiladigan()

    assert await agent._ventilyatorlar(0) == []


@pytest.mark.asyncio
async def test_api_yiqilsa_hisob_toxtamaydi():
    """Kesh/tarmoq xatosi — ventilyator ro'yxati bo'sh, lekin hisob chiqadi."""
    class Yiqiladigan:
        async def texnik_parametrlar(self):
            raise RuntimeError("tarmoq yo'q")

    agent = rustam_yasa(KATALOG)
    agent.api = Yiqiladigan()

    assert await agent._ventilyatorlar(8000) == []


@pytest.mark.asyncio
async def test_bir_xil_sarfli_variantlar_takrorlanmaydi():
    """ВЦ 14-46-5-1 … -5-5 — bir xil g'ildirak, bir xil sarf.

    Menejerga bir xil qatorni besh marta ko'rsatish foydasiz.
    """
    katalog = {
        f"ВЦ 14-46-5-{i}": {"havo_sarfi": [5000, 8400], "bosim": [860, 1070],
                            "turi": "Ventilyator VC 14-46"}
        for i in range(1, 6)
    }
    katalog["ВЦ 14-46-8-1"] = {"havo_sarfi": [14000, 31000], "bosim": [900, 1200],
                               "turi": "Ventilyator VC 14-46"}

    natija = await rustam_yasa(katalog)._ventilyatorlar(8000)

    assert [x["model"] for x in natija] == ["ВЦ 14-46-5-1", "ВЦ 14-46-8-1"]


# --- kasr ajratgichi -----------------------------------------------------------


def test_kasr_vergul_modelni_adashtirmaydi():
    """ENG XAVFLI XATO: КЦКП-3,15 va КЦКП-31,5 — BOSHQA qurilmalar.

    Jonli tekshiruv (2026-08-11): vergul olib tashlanganda ikkalasi ham
    "КЦКП315" kalitini olardi va 3 150 m³/soat lik qurilmaga
    31 500 m³/soat biriktirilardi — o'n barobar xato.
    """
    kichik = ModelParametri(model="КЦКП-3,15", havo_min=3150, havo_maks=3150)
    katta = ModelParametri(model="КЦКП-31,5", havo_min=31500, havo_maks=31500)

    natija = moslashtir([kichik, katta], ["КЦКП-3,15", "КЦКП-31,5"])

    assert natija["КЦКП-3,15"].havo_maks == 3150
    assert natija["КЦКП-31,5"].havo_maks == 31500


@pytest.mark.parametrize("kichik,katta,kichik_qiymat,katta_qiymat", [
    ("КЦКП-1,6", "КЦКП-16", 1600, 16000),
    ("КЦКП-6,3", "КЦКП-63", 6300, 63000),
    ("КЦКП-12,5", "КЦКП-125", 12500, 125000),
])
def test_kasrli_juftliklar_ajratiladi(kichik, katta, kichik_qiymat, katta_qiymat):
    """Jonli katalogda aynan shu to'rt juftlik chalkashgan edi."""
    natija = moslashtir(
        [
            ModelParametri(model=kichik, havo_min=kichik_qiymat, havo_maks=kichik_qiymat),
            ModelParametri(model=katta, havo_min=katta_qiymat, havo_maks=katta_qiymat),
        ],
        [kichik, katta],
    )

    assert natija[kichik].havo_maks == kichik_qiymat
    assert natija[katta].havo_maks == katta_qiymat


def test_shakl_ajratgichi_hamon_ahamiyatsiz():
    """Vergul saqlanadi, lekin "-" va "/" farqi baribir halaqit bermasin."""
    parametr = ModelParametri(model="ПВН 500-300/2", havo_min=800, havo_maks=800)

    natija = moslashtir([parametr], ["ПВН 500-300-2"])

    assert natija["ПВН 500-300-2"].havo_maks == 800


# --- ventilyator tanlashda BOSIM ----------------------------------------------


BOSIMLI_KATALOG = {
    # Sarfi katta, lekin bosimi past — kanalli tizimga YARAMAYDI.
    "ВО 12-300-6,3": {"havo_sarfi": [6150, 10000], "bosim": [50, 95],
                      "turi": "Ventilyator VO 12-300"},
    # Sarfi kamroq, bosimi yuqori — to'g'ri tanlov.
    "ВЦ 14-46-5-1": {"havo_sarfi": [5000, 8400], "bosim": [860, 1070],
                     "turi": "Ventilyator VC 14-46"},
    # Bosimi katalogda yo'q — tashlab yuborilmaydi, lekin oxirroqda.
    "ВР 6-28-9": {"havo_sarfi": [8500, 16200], "bosim": None,
                  "turi": "Ventilyator VR 6-28"},
}


@pytest.mark.asyncio
async def test_bosimi_yetmagan_ventilyator_pastga_tushadi():
    """JONLI XATO: ВО 12-300 sarfi bo'yicha birinchi chiqardi.

    Sarfi 10 000 m³/soat — eng katta, zaxirasi eng kichik. Lekin
    bosimi 95 Pa, kanalli tizim esa ~250 Pa talab qiladi. Ya'ni
    o'rnatilsa havo bermaydi.
    """
    natija = await rustam_yasa(BOSIMLI_KATALOG)._ventilyatorlar(8000, "kanalli")

    modellar = [x["model"] for x in natija]
    assert modellar[0] == "ВЦ 14-46-5-1", "bosimi yetadigan birinchi turmadi"
    assert modellar[-1] == "ВО 12-300-6,3", "bosimi yetmagani pastga tushmadi"


@pytest.mark.asyncio
async def test_bosim_holati_belgilanadi():
    natija = await rustam_yasa(BOSIMLI_KATALOG)._ventilyatorlar(8000, "kanalli")
    holat = {x["model"]: x["bosim_yetadi"] for x in natija}

    assert holat["ВЦ 14-46-5-1"] is True
    assert holat["ВО 12-300-6,3"] is False
    # Katalogda bosim yo'q — "yaramaydi" deb belgilanmaydi.
    assert holat["ВР 6-28-9"] is None


@pytest.mark.asyncio
async def test_bosimsiz_model_tashlanmaydi():
    """Ma'lumot yo'qligi modelning yomonligini bildirmaydi."""
    natija = await rustam_yasa(BOSIMLI_KATALOG)._ventilyatorlar(8000, "kanalli")

    assert "ВР 6-28-9" in [x["model"] for x in natija]


@pytest.mark.asyncio
async def test_oddiy_tarmoqda_oqli_ventilyator_yaraydi():
    """Qisqa kanal, qarshiliksiz — o'qli ventilyator to'g'ri tanlov."""
    natija = await rustam_yasa(BOSIMLI_KATALOG)._ventilyatorlar(8000, "oddiy")
    holat = {x["model"]: x["bosim_yetadi"] for x in natija}

    # `oddiy` tarmoq 100 Pa dan boshlanadi — 95 Pa hali ham yetmaydi,
    # lekin farq sezilarli kamayadi.
    assert holat["ВЦ 14-46-5-1"] is True


# --- manba `characters[]` ga ko'chgandan keyin ---------------------------------
#
# Backend `product_models` jadvalini butunlay olib tashladi (2026-09-09).
# Model nomlari, R2 hujjatlari VA `airflow_m3h`/`pressure_pa` ustunlari
# endi `characters[]` ichida. Quyidagilar shu ko'chishni qo'riqlaydi.


@pytest.mark.parametrize("qiymat,kutilgan", [
    (1425, 1425.0),
    ("2110", 2110.0),
    (None, None),
    (0, None),        # "to'ldirilmagan" degani, "sarfi nol" emas
    (-5, None),
    ("", None),
    ("abc", None),
])
def test_musbat_qiymat(qiymat, kutilgan):
    from integrations.climavent_client import _musbat

    assert _musbat(qiymat) == kutilgan


@pytest.mark.parametrize("backend,jadval,zidmi", [
    # Aylanish tezligi havo sarfi o'rniga tushgan — jonli misollar.
    (1500, [1800, 2700], True),      # ВО 12-300-3,15
    (1000, [1250, 2950], True),      # ВКР-4
    (22, [20050, 40100], True),      # ВНР-10-22-1000 (nomdagi son)
    (750, [7060, 28400], True),      # ВКОП-10
    # Mos keladiganlar.
    (1425, [1425, 1425], False),
    (8000, [5000, 8400], False),
    (5200, [5000, 8400], False),
    (8800, [5000, 8400], False),     # 10% bo'shashtirish ichida
    # O'lchab bo'lmaydigan holatlar — zid deb belgilanmaydi.
    (None, [1000, 2000], False),
    (1500, None, False),
])
def test_zid_aniqlash(backend, jadval, zidmi):
    from integrations.climavent_client import _zid_keladimi

    assert _zid_keladimi(backend, jadval) is zidmi


def _texnik_klient(monkeypatch, mahsulotlar, artikullar=(), hujjatlar=None):
    """Tarmoqqa chiqmaydigan klient (kesh o'qish/yozish ham o'chirilgan)."""
    from integrations.climavent_client import ClimaventKlient

    klient = ClimaventKlient.__new__(ClimaventKlient)
    klient.ogohlantirish = ""
    monkeypatch.setattr(
        "integrations.climavent_client._texnik_keshdan_oqi", lambda *a, **kw: None)
    monkeypatch.setattr(
        "integrations.climavent_client._texnik_keshga_yoz", lambda x: None)

    async def _mahsulotlar():
        return list(mahsulotlar)

    async def _artikullar():
        return list(artikullar)

    async def _hujjat(havola):
        return (hujjatlar or {}).get(havola)

    klient.mahsulotlar = _mahsulotlar
    klient.artikullar = _artikullar
    klient._hujjat_json = _hujjat
    return klient


@pytest.mark.asyncio
async def test_havo_sarfi_xususiyatdan_olinadi(monkeypatch):
    """`airflow_m3h` endi `characters[]` da — ilgari alohida jadvalda edi."""
    klient = _texnik_klient(monkeypatch, [{
        "id": 1, "name_uz": "Kanal ventilyatori",
        "characters": [
            {"id": 10, "title": "ВК-200С", "airflow_m3h": 1200, "pressure_pa": 425},
        ],
    }])

    natija = await klient.texnik_parametrlar(yangila=True)

    assert natija["ВК-200С"]["havo_sarfi"] == 1200
    assert natija["ВК-200С"]["bosim"] == 425
    assert natija["ВК-200С"]["manba"] == "backend"


@pytest.mark.asyncio
async def test_artikul_nomlari_ham_nomzod_boladi(monkeypatch):
    """Jadvalda to'liq artikul nomi turadi, xususiyat sarlavhasi qisqa.

    Faqat sarlavha bilan cheklansak qamrov keskin tushardi — o'lchandi:
    342 nomzodda 73 model, artikul nomlari qo'shilgach 267 ta.
    """
    klient = _texnik_klient(
        monkeypatch,
        mahsulotlar=[{
            "id": 1, "name_uz": "Ventilyator",
            "characters": [{"id": 10, "title": "ВЦ 4-75-2,5",
                            "contentJson": "https://r2/jadval"}],
        }],
        artikullar=[{"product_model_id": 10,
                     "in_model_name": "ВЦ 4-75-2,5-1-0,37/1500",
                     "sap_name": "ВЦ 4-75-2,5-О-1-0,37/1500"}],
        hujjatlar={"https://r2/jadval": {"soxta": True}},
    )

    yozilgan: dict = {}

    def soxta_moslashtir(xom, nomzodlar):
        yozilgan["nomzodlar"] = list(nomzodlar)
        return {}

    monkeypatch.setattr(
        "integrations.climavent_client.moslashtir", soxta_moslashtir)
    monkeypatch.setattr(
        "integrations.climavent_client.hujjatdan_parametrlar",
        lambda hujjat, manba: [])

    await klient.texnik_parametrlar(yangila=True)

    assert "ВЦ 4-75-2,5" in yozilgan["nomzodlar"]
    assert "ВЦ 4-75-2,5-1-0,37/1500" in yozilgan["nomzodlar"]


@pytest.mark.asyncio
async def test_bosh_natija_keshni_buzmaydi(monkeypatch):
    """Muvaffaqiyatsiz yig'ish ishlaydigan keshni o'chirib yubormasin."""
    from integrations.climavent_client import ClimaventKlient

    klient = ClimaventKlient.__new__(ClimaventKlient)
    klient.ogohlantirish = ""
    yozildi: list = []
    monkeypatch.setattr(
        "integrations.climavent_client._texnik_keshdan_oqi", lambda *a, **kw: None)
    monkeypatch.setattr(
        "integrations.climavent_client._texnik_keshga_yoz", yozildi.append)

    async def bosh():
        return []

    klient.mahsulotlar = bosh
    klient.artikullar = bosh

    assert await klient.texnik_parametrlar(yangila=True) == {}
    assert yozildi == [], "bo'sh natija keshga yozildi"


# --- bir nomli KO'P QATOR (quvvat/aylanish variantlari) -----------------------
#
# JONLI HOLAT: `ВКРВ-5` jadvalda sakkiz marta uchraydi — 5,5 kVt dan
# 30 kVt gacha, havo sarfi 5000-11150 dan 7500-24500 gacha. Ilgari
# BIRINCHI qator olinib, qolgani tashlanardi va butun oilaga o'sha
# tarqalardi: 18,5 kVt li ventilyator 11150 m³/soat deb yozilardi,
# haqiqiysi esa 17000. Rustam uni "yetmaydi" deb rad etishi mumkin edi.

VKRV_JADVALI = [
    ["Модель", "Электродвигатель", "Электродвигатель",
     "Производительность, м3/ч", "Полное давление, Па"],
    ["Модель", "Мощность, кВт", "Частота вращения, об/мин",
     "Производительность, м3/ч", "Полное давление, Па"],
    ["ВКРВ-5", "5,5", "1000", "5000-11150", "860-1150"],
    ["ВКРВ-5", "18,5", "1500", "7500-17000", "1980-2540"],
    ["ВКРВ-5", "30,0", "1500", "7500-24500", "1980-2500"],
]


def test_ikki_qatorli_sarlavha_birlashadi():
    """Birlik yozuvidagi raqam ("м3/ч", "кВт") sarlavhani buzmasin.

    Ilgari shart "ikkinchi qatorda raqam bo'lmasin" edi va shu sababli
    ikki qatorli sarlavha deyarli hech qachon birlashmasdi — quvvat
    ustuni umuman tanilmasdi.
    """
    from integrations.texnik import _sarlavha_qatorlari, ustun_turi

    sarlavha, qatori = _sarlavha_qatorlari(VKRV_JADVALI)

    assert qatori == 2, "ikkinchi sarlavha qatori ma'lumot deb o'qildi"
    assert "quvvat" in [ustun_turi(s) for s in sarlavha]


def test_takror_qatorlar_saqlanadi():
    from integrations.texnik import jadvaldan_parametrlar

    qatorlar = [p for p in jadvaldan_parametrlar(VKRV_JADVALI)
                if p.model == "ВКРВ-5"]

    assert len(qatorlar) == 3, "bir nomli qatorlar tashlab yuborildi"
    assert sorted(p.quvvat_kvt for p in qatorlar) == [5.5, 18.5, 30.0]


def test_artikul_oz_quvvat_qatorini_oladi():
    """`-18,5/1450` — 18,5 kVt qatori olinishi kerak, birinchisi emas."""
    from integrations.texnik import jadvaldan_parametrlar, moslashtir

    natija = moslashtir(
        jadvaldan_parametrlar(VKRV_JADVALI),
        ["ВКРВ-5-1-18,5/1450", "ВКРВ-5-1-5,5/1000"],
    )

    assert natija["ВКРВ-5-1-18,5/1450"].havo_maks == 17000
    assert natija["ВКРВ-5-1-5,5/1000"].havo_maks == 11150


def test_oila_nomi_butun_qamrovni_oladi():
    """Aniq artikul aytilmasa — oilaning eng past/eng yuqorisi."""
    from integrations.texnik import jadvaldan_parametrlar, moslashtir

    par = moslashtir(jadvaldan_parametrlar(VKRV_JADVALI), ["ВКРВ-5"])["ВКРВ-5"]

    assert par.havo_min == 5000
    assert par.havo_maks == 24500


def test_nomida_quvvat_yoq_bolsa_qamrov_beriladi():
    """Noma'lum variantga bittasini tanlab berish xato bo'lardi."""
    from integrations.texnik import jadvaldan_parametrlar, moslashtir

    # 4,0 kVt jadvalda umuman yo'q.
    par = moslashtir(
        jadvaldan_parametrlar(VKRV_JADVALI), ["ВКРВ-5-1-4,0/960"]
    )["ВКРВ-5-1-4,0/960"]

    assert (par.havo_min, par.havo_maks) == (5000, 24500)


@pytest.mark.parametrize("nom,kutilgan", [
    ("ВКРВ-5-1-18,5/1450", 18.5),
    ("ВЦ 4-75-2,5-1-0,37/1500", 0.37),
    ("ВКРВ-5", None),
    ("ПВН 500-250/2", None),      # oxiridagi "2" aylanish emas
])
def test_nomdan_quvvat_ajratiladi(nom, kutilgan):
    from integrations.texnik import _nomdan_quvvat

    assert _nomdan_quvvat(nom) == kutilgan

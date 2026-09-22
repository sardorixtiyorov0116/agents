"""Katalog administratori Nodira — yozish faqat tasdiqdan keyin.

Eng muhim testlar:
  - tasdiqsiz backendga BITTA HAM so'rov ketmasligi;
  - ixtiyoriy endpointga so'rov yuborib bo'lmasligi (amal jadvali);
  - begona maydonlar tashlanishi;
  - o'chirish ochiq ogohlantirish bilan ko'rsatilishi.
"""

from __future__ import annotations

import json

import pytest

from app.agentlar.katalog_admin import MAKS_AMAL, TIZIM_PROMPT, KatalogAdmin
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat
from integrations import AMALLAR, Amal, ClimaventYozuvchi, YozishXatosi
from presenter.agentlar import agent_matni

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim

# Bu faylning testlari yozish klientini O'Z soxta transporti bilan quradi —
# haqiqiy tarmoqqa chiqmaydi, lekin `_sorov` mantiqini haqiqiy holda sinaydi.
pytestmark = pytest.mark.oz_transporti

KATALOG = [
    {
        "id": 26,
        "name_uz": "Kanal ventilyatori ВК-П",
        "category": {"id": 3, "name_uz": "Kanal"},
        "models": [
            {"id": 91, "name": "ВК-315П", "price": "0"},
            {"id": 92, "name": "ВК-250П", "price": "0"},
        ],
        "characters": [{"id": 7, "title": "ВК-315П", "price": 0}],
        "quantity": 10,
    }
]


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["catalog-admin"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "nodira.db")
    await b.tayyorla()
    return b


class SoxtaHttp:
    """Yozish klientining tarmoq qatlami o'rniga — nima yuborilganini yozadi."""

    def __init__(self, holat: int = 201, javob_tanasi=None):
        self.sorovlar: list[dict] = []
        self.holat = holat
        self.javob_tanasi = javob_tanasi if javob_tanasi is not None else {"id": 1}

    class _Javob:
        def __init__(self, holat, tana):
            self.status_code = holat
            self._tana = tana
            self.text = json.dumps(tana)

        def json(self):
            return self._tana

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    async def request(self, metod, manzil, json=None, headers=None, timeout=None):
        self.sorovlar.append(
            {"metod": metod, "manzil": manzil, "tana": json, "sarlavha": headers}
        )
        return self._Javob(self.holat, self.javob_tanasi)

    async def get(self, manzil, timeout=None):
        self.sorovlar.append({"metod": "GET", "manzil": manzil, "tana": None})
        return self._Javob(200, {"id": 26, "name_uz": "Kanal ventilyatori ВК-П",
                                 "name_ru": "Вентилятор", "name_en": "Fan",
                                 "description_short_uz": "a", "description_short_ru": "b",
                                 "description_short_en": "c", "quantity": 10,
                                 "producer": "Climavent", "category_id": 3})


def yozuvchi_yasa(
    http: SoxtaHttp | None = None,
    token: str = "",
    xizmat_kaliti: str = "sinov-kalit",
):
    return ClimaventYozuvchi(
        asos="https://sinov.local", token=token,
        xizmat_kaliti=xizmat_kaliti, mijoz=http or SoxtaHttp(),
    )


def nodira_javobi(**ustama):
    malumot = {
        "niyat": "ВК-315П narxini belgilash",
        "amallar": [
            {"tur": "xususiyat_yangila", "nishon_id": 91,
             "maydonlar": [{"nomi": "price", "qiymati": "2400000"}],
             "izoh": "yangi narx"}
        ],
        "topilmadi": [],
        "sorash_kerak": [],
        "xavf": "",
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


def nodira_yasa(kontrakt, baza, llm, http=None, katalog=True, kalit="sinov-kalit"):
    return KatalogAdmin(
        kontrakt=kontrakt,
        llm=llm,
        baza=baza,
        api=soxta_api(qidir_keng=KATALOG if katalog else [], keshni_tozala=None),
        qidiruv_manbasi=soxta_bilim(),
        yozuvchi=yozuvchi_yasa(http, xizmat_kaliti=kalit),
    )


# --- eng muhim: tasdiqsiz yozilmaydi -----------------------------------------


@pytest.mark.asyncio
async def test_tasdiqsiz_backendga_hech_narsa_yubormaydi(kontrakt, baza):
    """O'ZGARMAS QOIDA: reja tuzilganda backend UMUMAN chaqirilmaydi."""
    http = SoxtaHttp()
    k = await nodira_yasa(kontrakt, baza, nodira_javobi(), http).ishla(
        "ВК-315П narxini 2 400 000 qil"
    )

    assert k.holat is Holat.TASDIQ_KUTILMOQDA
    assert k.tasdiq_kerak is True
    assert http.sorovlar == [], "tasdiqdan oldin backendga so'rov ketmasligi kerak"
    assert k.natija["bajarildi"] is False
    assert k.natija["taklif_amal"][0]["nishon_id"] == 91
    assert "HECH NARSA HALI YOZILMADI" in k.izoh


@pytest.mark.asyncio
async def test_tasdiqdan_keyin_yoziladi(kontrakt, baza):
    http = SoxtaHttp()
    nodira = nodira_yasa(kontrakt, baza, SoxtaLlm([]), http)

    k = await nodira.ishla(
        "narxni yangila",
        {"tasdiqlandi": True,
         "tasdiqlangan_amal": [
             {"tur": "xususiyat_yangila", "nishon_id": 91,
              "maydonlar": {"price": "2400000"}, "izoh": ""}
         ]},
    )

    assert k.holat is Holat.TUGADI
    assert k.tasdiq_kerak is False
    assert len(http.sorovlar) == 1
    yuborilgan = http.sorovlar[0]
    assert yuborilgan["metod"] == "PATCH"
    assert yuborilgan["manzil"].endswith("/api/characteristics/update/91")
    # Narx SON bo'lib ketadi: xususiyat narxi Swagger'da `number`.
    assert yuborilgan["tana"] == {"price": 2400000}
    assert yuborilgan["sarlavha"]["X-API-Key"] == "sinov-kalit"


@pytest.mark.asyncio
async def test_zanjir_tasdiq_bilan_toliq_ishlaydi(kontrakt, baza):
    """Reja -> tasdiq -> bajarish: orkestrsiz ham to'liq oqim."""
    http = SoxtaHttp()
    nodira = nodira_yasa(kontrakt, baza, nodira_javobi(), http)

    reja = await nodira.ishla("ВК-315П narxini 2 400 000 qil")
    assert http.sorovlar == []

    yakun = await nodira.ishla(
        "ВК-315П narxini 2 400 000 qil",
        {"tasdiqlandi": True, "tasdiqlangan_amal": reja.natija["taklif_amal"]},
    )
    assert yakun.holat is Holat.TUGADI
    assert yakun.natija["bajarilgan_soni"] == 1


# --- kod darajasidagi chegaralar ---------------------------------------------


def test_notogri_amal_rad_etiladi():
    """Model o'zi endpoint o'ylab topa olmaydi."""
    with pytest.raises(YozishXatosi, match="Noma'lum amal"):
        Amal(tur="foydalanuvchi_ochir", nishon_id=1).turi()


def test_begona_maydon_tashlanadi():
    amal = Amal(
        tur="xususiyat_yangila",
        nishon_id=91,
        maydonlar={"price": "100", "is_admin": True, "role": "root"},
    )
    assert amal.tozalangan() == {"price": 100}
    assert any("e'tiborga olinmaydi" in m for m in amal.tekshir())


def test_narx_turi_api_kutganicha_keltiriladi():
    """Narx HAR DOIM son — bo'sh joyli matn ham to'g'ri keltiriladi.

    Ilgari `model_*` amallarida narx MATN sifatida yuborilardi
    (`product_models.price` shunday edi). O'sha jadval API'da yo'q va
    amallar olib tashlandi; qolgan ikkala narx maydoni ham Swagger
    bo'yicha `number`.
    """
    xususiyat = Amal(tur="xususiyat_yangila", nishon_id=1, maydonlar={"price": "3 200 000"})
    assert xususiyat.tozalangan() == {"price": 3200000}

    ichki = Amal(tur="ichki_yangila", nishon_id=1, maydonlar={"price": "3 200 000"})
    assert ichki.tozalangan() == {"price": 3200000}


def test_raqamli_maydonlar_songa_keltiriladi():
    amal = Amal(
        tur="mahsulot_yangila",
        nishon_id=26,
        maydonlar={"quantity": "55", "category_id": "3", "producer": "Climavent"},
    )
    assert amal.tozalangan() == {"quantity": 55, "category_id": 3, "producer": "Climavent"}


def test_maydonlar_sxemada_ifodalanadi():
    """Erkin `dict` structured output'da BO'SH qoladi — juftliklar ishlaydi.

    Bu haqiqiy xato edi: model narxni yozardi, sxema uni tashlab yuborardi.
    """
    from app.agentlar.katalog_admin import NodiraNatija
    from app.sxema import json_format

    maydonlar = json_format(NodiraNatija)["schema"]["$defs"]["NodiraAmal"]["properties"][
        "maydonlar"
    ]
    assert maydonlar["type"] == "array", "maydonlar ro'yxat bo'lishi kerak"
    assert "$ref" in maydonlar["items"]


def test_id_siz_yangilash_rad_etiladi():
    muammolar = Amal(tur="xususiyat_yangila", maydonlar={"price": "1"}).tekshir()
    assert any("id" in m for m in muammolar)


def test_majburiy_maydon_yetishmasa_rad_etiladi():
    muammolar = Amal(tur="xususiyat_yarat", maydonlar={"title": "X"}).tekshir()
    assert any("price" in m and "product_id" in m for m in muammolar)


@pytest.mark.asyncio
async def test_guvohnomasiz_yozib_bolmaydi():
    yozuvchi = ClimaventYozuvchi(
        asos="https://sinov.local", token="", xizmat_kaliti="", mijoz=SoxtaHttp()
    )
    assert yozuvchi.sozlanganmi() is False
    with pytest.raises(YozishXatosi, match="SERVICE_API_KEY"):
        await yozuvchi.bajar(
            Amal(tur="xususiyat_yangila", nishon_id=1, maydonlar={"price": "1"})
        )


@pytest.mark.asyncio
async def test_guvohnomasiz_agent_ochiq_aytadi(kontrakt, baza):
    k = await nodira_yasa(kontrakt, baza, SoxtaLlm([]), kalit="").ishla("narx qo'sh")

    assert k.holat is Holat.XATO
    assert "SERVICE_API_KEY" in k.izoh


@pytest.mark.asyncio
async def test_yangilashda_mavjud_yozuv_birlashtiriladi():
    """PATCH to'liq DTO talab qiladi — maydonlar o'chib ketmasligi kerak."""
    http = SoxtaHttp()
    yozuvchi = yozuvchi_yasa(http)

    await yozuvchi.bajar(
        Amal(tur="mahsulot_yangila", nishon_id=26, maydonlar={"quantity": 55})
    )

    # Avval mavjud yozuv o'qildi, keyin birlashtirilgan tana yuborildi.
    assert http.sorovlar[0]["metod"] == "GET"
    tana = http.sorovlar[1]["tana"]
    assert tana["quantity"] == 55
    assert tana["name_uz"] == "Kanal ventilyatori ВК-П", "eski maydon saqlanishi kerak"
    assert tana["producer"] == "Climavent"


@pytest.mark.asyncio
async def test_ochirishda_tana_yuborilmaydi():
    http = SoxtaHttp(holat=200)
    await yozuvchi_yasa(http).bajar(Amal(tur="xususiyat_ochir", nishon_id=91))

    assert http.sorovlar[0]["metod"] == "DELETE"
    assert http.sorovlar[0]["tana"] is None


@pytest.mark.asyncio
async def test_401_aniq_xabar_beradi():
    with pytest.raises(YozishXatosi, match="SERVICE_API_KEY"):
        await yozuvchi_yasa(SoxtaHttp(holat=401)).bajar(
            Amal(tur="xususiyat_yangila", nishon_id=1, maydonlar={"price": "1"})
        )


# --- ish oqimi ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_ochirish_ochiq_ogohlantiriladi(kontrakt, baza):
    llm = nodira_javobi(
        niyat="eskirgan modelni o'chirish",
        amallar=[{"tur": "xususiyat_ochir", "nishon_id": 91, "maydonlar": [], "izoh": "eskirgan"}],
        xavf="ВК-315П modeli va uning narxi yo'qoladi",
    )
    k = await nodira_yasa(kontrakt, baza, llm).ishla("ВК-315П modelini o'chir")

    assert k.holat is Holat.TASDIQ_KUTILMOQDA
    assert k.natija["ochirish_soni"] == 1
    assert "O'CHIRISH" in k.izoh
    matn = agent_matni("catalog-admin", k.natija)
    assert "O'CHIRILADI" in matn
    assert "qaytarib bo'lmaydi" in matn


@pytest.mark.asyncio
async def test_amal_yoq_bolsa_aniqlik_soraydi(kontrakt, baza):
    llm = nodira_javobi(
        amallar=[], topilmadi=["Гибкая вставка"],
        sorash_kerak=["Qaysi model uchun narx kerak?"],
    )
    k = await nodira_yasa(kontrakt, baza, llm, katalog=False).ishla("narx qo'sh")

    assert k.holat is Holat.ANIQLIK_KERAK
    assert k.natija["savollar"] == ["Qaysi model uchun narx kerak?"]


@pytest.mark.asyncio
async def test_ommaviy_ozgartirish_kodda_cheklangan(kontrakt, baza):
    """Chegara promptda emas, KODDA: model 30 ta so'rasa ham 20 ta bajariladi."""
    llm = nodira_javobi(
        amallar=[
            {"tur": "xususiyat_yangila", "nishon_id": 91,
             "maydonlar": [{"nomi": "price", "qiymati": str(i)}], "izoh": ""}
            for i in range(1, 31)
        ]
    )
    k = await nodira_yasa(kontrakt, baza, llm).ishla("hamma narxni yangila")

    assert len(k.natija["taklif_amal"]) == MAKS_AMAL
    assert any("qayta so'rov" in o for o in k.natija["ogohlantirishlar"])


@pytest.mark.asyncio
async def test_katalog_idlari_promptga_beriladi(kontrakt, baza):
    """Model id ni taxmin qilmasligi uchun haqiqiy id'lar ko'rsatiladi."""
    llm = nodira_javobi()
    await nodira_yasa(kontrakt, baza, llm).ishla("ВК-315П narxi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "model id=91" in xabar
    assert "mahsulot id=26" in xabar


@pytest.mark.asyncio
async def test_katalog_ochilmasa_id_taxmin_qilinmaydi(kontrakt, baza):
    llm = nodira_javobi()
    nodira = KatalogAdmin(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(),  # qidir_keng sozlanmagan -> ApiXatosi
        qidiruv_manbasi=soxta_bilim(),
        yozuvchi=yozuvchi_yasa(),
    )
    await nodira.ishla("narx yangila")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "id noma'lum" in xabar


# --- kontrakt chegaralari ----------------------------------------------------


def test_promptda_chegaralar():
    assert "NARXNI O'ZING O'YLAB TOPMAYSAN" in TIZIM_PROMPT
    assert "ID NI TAXMIN QILMAYSAN" in TIZIM_PROMPT
    assert "BAJARMAYSAN" in TIZIM_PROMPT
    # Faqat jadvaldagi amallar promptda; boshqa endpoint nomi yo'q.
    for nom in AMALLAR:
        assert nom in TIZIM_PROMPT


def test_faqat_katalog_endpointlari():
    """Foydalanuvchi, buyurtma, to'lov yo'llari umuman mavjud emas."""
    yollar = " ".join(t.yol for t in AMALLAR.values())
    for taqiqlangan in ("users", "orders", "cart", "reviews", "likes"):
        assert taqiqlangan not in yollar


def test_ikkala_guvohnoma_ham_yuboriladi():
    """Backend qaysi birini tekshirishini bilmaymiz — ikkalasi ham ketadi."""
    yozuvchi = ClimaventYozuvchi(
        asos="https://sinov.local", token="jwt-token", xizmat_kaliti="hex-kalit",
        mijoz=SoxtaHttp(),
    )
    sarlavhalar = yozuvchi._sarlavhalar()

    assert sarlavhalar["X-API-Key"] == "hex-kalit"
    assert sarlavhalar["Authorization"] == "Bearer jwt-token"


def test_faqat_xizmat_kaliti_bilan_ham_ishlaydi():
    yozuvchi = ClimaventYozuvchi(
        asos="https://sinov.local", token="", xizmat_kaliti="hex-kalit",
        mijoz=SoxtaHttp(),
    )
    assert yozuvchi.sozlanganmi() is True
    assert "Authorization" not in yozuvchi._sarlavhalar()


def test_haqiqiy_sozlamada_kalit_bor():
    """`.env` da SERVICE_API_KEY bo'lmasa Nodira umuman ishlamaydi."""
    from app.config import sozlama

    s = sozlama()
    assert s.service_api_key or s.climavent_token, (
        "SERVICE_API_KEY yoki CLIMAVENT_TOKEN .env da bo'lishi kerak"
    )


# --- product_model_inside: quvvat variantining narxi (USD) -------------------
#
# Bu jadval katalogdagi eng nozik joyi: bitta o'lcham (ВЦ 4-75 №2,5) ostida
# bir nechta quvvat varianti bor va HAR BIRINING narxi boshqa. Narx aynan
# shu yerga yoziladi — `product_models` da quvvat ko'rsatilmagan.


def test_ichki_amallar_amal_jadvalida_bor():
    for nom in ("ichki_yarat", "ichki_yangila", "ichki_ochir"):
        assert nom in AMALLAR, f"{nom} amal jadvalida yo'q"


def test_ichki_yangilash_narxni_SON_qilib_yuboradi():
    """`product_model_inside.price` — SON, va u kasrli bo'lishi mumkin.

    Narx dollarda saqlanadi, shuning uchun butun songa yaxlitlanmasligi
    kerak: "174,51" -> 174.51.
    """
    amal = Amal(tur="ichki_yangila", nishon_id=3, maydonlar={"price": "174,51"})

    tozalangan = amal.tozalangan()

    assert tozalangan == {"price": 174.51}
    assert isinstance(tozalangan["price"], float)


def test_hech_qaysi_amalda_narx_MATN_bolib_ketmaydi():
    """Narx matn bo'lib qolsa backend 400 qaytaradi — chegara yo'qolmasin."""
    narxli = [nom for nom, a in AMALLAR.items() if "price" in a.maydonlar]
    assert narxli, "narx maydoni bor amal qolmadi — test ma'nosini yo'qotdi"

    for nom in narxli:
        tozalangan = Amal(
            tur=nom, nishon_id=3, maydonlar={"price": "1 650 000"}
        ).tozalangan()
        assert tozalangan["price"] == 1650000, nom
        assert not isinstance(tozalangan["price"], str), nom


def test_ichki_yaratishda_xarakteristika_id_soni_kerak():
    amal = Amal(tur="ichki_yarat", maydonlar={
        "sap_name": "ВЦ 4-75-2,5-О-1-0,37/1500",
        "in_model_name": "ВЦ 4-75-2,5-1-0,37/1500",
        "product_model_id": "96",
        "price": 174.51,
    })

    tozalangan = amal.tozalangan()

    assert tozalangan["product_model_id"] == 96      # matn emas, son
    assert amal.tekshir() == []


def test_ichki_yaratishda_yetishmagan_maydon_aytiladi():
    amal = Amal(tur="ichki_yarat", maydonlar={"price": 174.51})

    muammolar = " ".join(amal.tekshir())

    assert "sap_name" in muammolar and "in_model_name" in muammolar


def test_ichki_begona_maydon_tashlanadi():
    """Masalan `currency` — bu jadvalda bunday ustun YO'Q."""
    amal = Amal(tur="ichki_yangila", nishon_id=3,
                maydonlar={"price": 174.51, "currency": "USD"})

    assert "currency" not in amal.tozalangan()
    assert any("currency" in m for m in amal.tekshir())


@pytest.mark.anyio
async def test_ichki_yangilash_togri_yolga_boradi():
    soxta = SoxtaHttp()
    yozuvchi = ClimaventYozuvchi(
        asos="https://sinov.local", token="", xizmat_kaliti="hex-kalit",
        mijoz=soxta,
    )

    await yozuvchi.bajar(
        Amal(tur="ichki_yangila", nishon_id=3, maydonlar={"price": 174.51})
    )

    sorov = soxta.sorovlar[-1]
    assert sorov["metod"] == "PATCH"
    assert sorov["manzil"] == "https://sinov.local/api/product-model-inside/3"
    assert sorov["tana"] == {"price": 174.51}


def test_usd_kursi_sozlamada_bor():
    """So'm narxi bazada saqlanmaydi — shu kursdan hisoblanadi."""
    from app.config import sozlama

    assert sozlama().usd_kursi > 0


# --- ikki bosqichli yaratish -------------------------------------------------
#
# `CreateProductDto` da atigi 10 maydon bor. Ilgari yaratishga to'liq
# ro'yxat yuborilardi va `sizes`, `opisaniya`, `naznacheniya`,
# `markirovka` jimgina yo'qolardi — mahsulot yarim ma'lumot bilan
# katalogga tushardi.


@pytest.mark.asyncio
async def test_yaratish_avval_POST_keyin_PATCH_qiladi():
    http = SoxtaHttp(javob_tanasi={"id": 77})

    natija = await yozuvchi_yasa(http).bajar(Amal(tur="mahsulot_yarat", maydonlar={
        "name_uz": "Kanal ventilyatori", "name_ru": "Вентилятор", "name_en": "Fan",
        "description_short_uz": "a", "description_short_ru": "b",
        "description_short_en": "c",
        "quantity": 10, "producer": "Climavent", "category_id": 3,
        # Quyidagilar yaratish DTO'sida YO'Q — ular PATCH bilan qo'yiladi.
        "sizes": "315 mm", "opisaniya": "kanal tipidagi",
    }))

    metodlar = [s["metod"] for s in http.sorovlar]
    assert metodlar == ["POST", "GET", "PATCH"], metodlar

    yaratish = http.sorovlar[0]
    assert yaratish["manzil"].endswith("/api/products/create")
    assert "sizes" not in yaratish["tana"]
    assert "opisaniya" not in yaratish["tana"]
    assert yaratish["tana"]["name_uz"] == "Kanal ventilyatori"

    toldirish = http.sorovlar[2]
    assert toldirish["manzil"].endswith("/api/products/update/77")
    assert toldirish["tana"]["sizes"] == "315 mm"
    assert toldirish["tana"]["opisaniya"] == "kanal tipidagi"

    assert natija["nishon_id"] == 77
    assert "toldirish" in natija


@pytest.mark.asyncio
async def test_yaratishda_qoshimcha_maydon_bolmasa_PATCH_qilinmaydi():
    http = SoxtaHttp(javob_tanasi={"id": 77})

    await yozuvchi_yasa(http).bajar(Amal(tur="mahsulot_yarat", maydonlar={
        "name_uz": "A", "name_ru": "B", "name_en": "C",
        "description_short_uz": "a", "description_short_ru": "b",
        "description_short_en": "c",
        "quantity": 1, "producer": "Climavent", "category_id": 3,
    }))

    assert [s["metod"] for s in http.sorovlar] == ["POST"]


@pytest.mark.asyncio
async def test_yaratish_javobida_id_bolmasa_OCHIQ_ogohlantiradi():
    """Yarim bajarilgan o'zgarish yashirin qolmasligi kerak."""
    http = SoxtaHttp(javob_tanasi={"holat": "ok"})    # `id` yo'q

    natija = await yozuvchi_yasa(http).bajar(Amal(tur="mahsulot_yarat", maydonlar={
        "name_uz": "A", "name_ru": "B", "name_en": "C",
        "description_short_uz": "a", "description_short_ru": "b",
        "description_short_en": "c",
        "quantity": 1, "producer": "Climavent", "category_id": 3,
        "sizes": "315 mm",
    }))

    assert [s["metod"] for s in http.sorovlar] == ["POST"]
    assert "sizes" in natija["ogohlantirish"]
    assert "mahsulot_yangila" in natija["ogohlantirish"]


def test_mavjud_bolmagan_endpointga_amal_qolmadi():
    """`model_*` amallari olib tashlandi — backendda bunday yo'l yo'q."""
    assert not [nom for nom in AMALLAR if nom.startswith("model_")]
    assert not [a for a in AMALLAR.values() if "product-models" in a.yol]

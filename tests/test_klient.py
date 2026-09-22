"""Climavent API klienti — kesh, xato holatlari, faqat o'qish, matn ajratish.

Tarmoqqa chiqmaydi: httpx transport soxta javob bilan almashtiriladi.
"""

from __future__ import annotations

import httpx
import pytest

from integrations import ApiXatosi, ClimaventKlient, mahsulot_qisqa, matn, narx_bormi
from integrations.climavent_client import hujjat_matni, xususiyatlar_qisqa

# Bu modul klientni o'z soxta transporti bilan quradi — tarmoqqa chiqmaydi.
pytestmark = pytest.mark.oz_transporti

MAHSULOT = {
    "id": 26,
    "name_uz": "VK-250 ventilyatori",
    "name_ru": "Вентилятор ВК-250",
    "name_en": "Fan VK-250",
    "description_short_uz": "Doira kanallari uchun ventilyator.",
    "price": 0,
    "quantity": 62,
    "producer": "JIHOZVENT",
    "category": {"id": 10, "name_uz": "Yumaloq kanallar uchun"},
    "models": [{"id": 1, "name": "VK-250P"}, {"id": 2, "name": "VK-200P"}],
    "characters": [{"id": 1, "title": "VK-250P", "content": "230 V, 210 Vt"}],
}


class Xato:
    """Test uchun: shu yo'l HTTP xatosi qaytarsin."""

    def __init__(self, kod: int):
        self.kod = kod


def soxta_klient(javoblar: dict[str, object], kuzatuv: list | None = None):
    """Berilgan yo'llarga soxta javob qaytaradigan klient."""

    def ishlov(soro: httpx.Request) -> httpx.Response:
        if kuzatuv is not None:
            kuzatuv.append(f"{soro.method} {soro.url.path}")
        javob = javoblar.get(soro.url.path)
        if javob is None:
            return httpx.Response(404, json={"message": "topilmadi"})
        if isinstance(javob, Xato):
            return httpx.Response(javob.kod, json={"message": "xato"})
        return httpx.Response(200, json=javob)

    mijoz = httpx.AsyncClient(transport=httpx.MockTransport(ishlov))
    return ClimaventKlient(mijoz=mijoz, kesh_ttl=60)


# Narxi bor mahsulot — haqiqiy katalogdagi ПВН guruhi ko'rinishida.
NARXLI = {
    "id": 31,
    "name_uz": "Suv bilan ishlaydigan kanalli isitgich ПВН",
    "name_ru": "Канальный нагреватель ПВН",
    "category": {"id": 5, "name_uz": "To'rtburchaklar kanallar uchun"},
    "quantity": 4,
    "models": [
        {"id": 28, "name": "ПВН 500-250-2", "price": "1700000", "product_id": 31},
        {"id": 29, "name": "ПВН 500-250-3", "price": "2200000", "product_id": 31},
        {"id": 44, "name": "ПВН 400-200-2", "price": "0", "product_id": 31},
    ],
    "characters": [],
}

# Qidiruv endpointi `models` ni QAYTARMAYDI — haqiqiy backend shunday ishlaydi.
NARXLI_QIDIRUVDAN = {
    "id": 31,
    "name_uz": "Suv bilan ishlaydigan kanalli isitgich ПВН",
    "category": {"id": 5, "name_uz": "To'rtburchaklar kanallar uchun"},
    "quantity": 4,
}


# --- narx qidirish -----------------------------------------------------------


@pytest.mark.asyncio
async def test_narx_toliq_katalogdan_olinadi():
    """Narx `/all` da bor, `/search` da yo'q — shuning uchun `/all` ishlatiladi."""
    kuzatuv: list[str] = []
    k = soxta_klient(
        {
            "/api/products/all": [NARXLI],
            "/api/products/search": [NARXLI_QIDIRUVDAN],
        },
        kuzatuv,
    )

    topilgan = await k.model_narxi("ПВН 500-250-2")
    assert topilgan is not None
    narx, yozuv = topilgan
    assert narx == 1_700_000
    assert yozuv == "ПВН 500-250-2"
    # Aynan to'liq katalogga murojaat qilindi
    assert "GET /api/products/all" in kuzatuv


@pytest.mark.asyncio
async def test_nol_narx_topilmagan_hisoblanadi():
    k = soxta_klient({"/api/products/all": [NARXLI]})
    assert await k.model_narxi("ПВН 400-200-2") is None


@pytest.mark.asyncio
async def test_ikki_bolakli_model_kodi_topiladi():
    """"ПВН 500-250-2" — harfli va raqamli bo'lak alohida; ilgari topilmasdi."""
    k = soxta_klient(
        {"/api/products/all": [NARXLI], "/api/products/search": []}
    )

    topilgan = await k.qidir_keng("5 dona ПВН 500-250-2 uchun KP kerak")
    assert [m["id"] for m in topilgan] == [31]
    # Topilgan yozuvda narx ham bor (qidiruv natijasida bo'lmasdi)
    assert topilgan[0]["models"][0]["price"] == "1700000"


# --- normal ishlash ----------------------------------------------------------


@pytest.mark.asyncio
async def test_mahsulotlar_va_soni():
    k = soxta_klient(
        {"/api/products/all": [MAHSULOT], "/api/products/allcount": 137}
    )

    assert len(await k.mahsulotlar()) == 1
    assert await k.mahsulotlar_soni() == 137


@pytest.mark.asyncio
async def test_javob_orami_ochiladi():
    """API ba'zan `{rows: [...]}` ko'rinishida qaytaradi."""
    k = soxta_klient({"/api/products/all": {"rows": [MAHSULOT, MAHSULOT]}})
    assert len(await k.mahsulotlar()) == 2


@pytest.mark.asyncio
async def test_kesh_ikkinchi_sorov_yubormaydi():
    kuzatuv: list[str] = []
    k = soxta_klient({"/api/products/all": [MAHSULOT]}, kuzatuv)

    await k.mahsulotlar()
    await k.mahsulotlar()

    assert kuzatuv == ["GET /api/products/all"], "ikkinchi marta keshdan olinishi kerak"

    await k.keshni_tozala()
    await k.mahsulotlar()
    assert len(kuzatuv) == 2


def test_kalitla_kirill_lotin_moslashuvi():
    """Katalog kirillcha (ВК-250П), foydalanuvchi lotincha (VK-250) yozadi."""
    from integrations.climavent_client import _mos_keladimi

    assert _mos_keladimi("VK-250", "ВК-250П")
    assert _mos_keladimi("ВК-250П", "VK-250")
    assert _mos_keladimi("vk250", "ВК-250С")
    assert not _mos_keladimi("VK-250", "ВЦ 4-75")
    assert not _mos_keladimi("", "ВК-250П")


@pytest.mark.asyncio
async def test_model_kodi_boyicha_qidiriladi():
    """Model kodlari mahsulot nomida emas — `models`/`characters` ichida."""
    katalog = [
        {
            "id": 1,
            "name_uz": "ВК-П ventilyatori",
            "models": [{"name": "ВК-250П"}, {"name": "ВК-315П"}],
            "characters": [{"title": "ВК-250П"}],
        },
        {"id": 2, "name_uz": "Klapan DKSP", "models": [], "characters": []},
    ]
    k = soxta_klient({"/api/products/all": katalog})

    topilgan = await k.model_boyicha_qidir("VK-250")
    assert [m["id"] for m in topilgan] == [1]

    # Mos kelmasa — bo'sh
    assert await k.model_boyicha_qidir("XYZ-999") == []


@pytest.mark.asyncio
async def test_qidir_keng_avval_model_kodini_sinaydi():
    """Model kodi bor bo'lsa, u API qidiruvidan oldin tekshiriladi."""
    katalog = [
        {"id": 1, "name_uz": "ВК-П ventilyatori", "models": [{"name": "ВК-250П"}], "characters": []}
    ]
    yollar: list[str] = []
    k = soxta_klient({"/api/products/all": katalog}, yollar)

    topilgan = await k.qidir_keng("VK-250 ventilyatorining xususiyatlari")

    assert [m["id"] for m in topilgan] == [1]
    # Katalog o'qildi, API qidiruvi umuman chaqirilmadi
    assert "POST /api/products/search" not in yollar


@pytest.mark.asyncio
async def test_qidir_keng_qisqartirib_qaytadan_uriniadi():
    """To'liq ibora topilmasa, so'zma-so'z qidiradi."""
    chaqiruvlar: list[str] = []

    def ishlov(soro: httpx.Request) -> httpx.Response:
        import json as _json

        tana = _json.loads(soro.content or b"{}")
        chaqiruvlar.append(tana.get("text", ""))
        # Faqat bitta so'zli so'rov natija beradi
        if tana.get("text") == "ventilyatori":
            return httpx.Response(200, json=[MAHSULOT])
        return httpx.Response(200, json=[])

    k = ClimaventKlient(mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)))
    topilgan = await k.qidir_keng("kanal ventilyatori")

    assert len(topilgan) == 1
    assert chaqiruvlar[0] == "kanal ventilyatori", "avval to'liq so'rov sinaladi"
    assert "ventilyatori" in chaqiruvlar


# --- xato holatlari ----------------------------------------------------------


@pytest.mark.asyncio
async def test_api_yiqilsa_xato_kotariladi():
    """Xato yutilmaydi — agent 'manba mavjud emas' deb ochiq aytadi."""
    k = soxta_klient({"/api/products/all": Xato(500)})

    with pytest.raises(ApiXatosi, match="HTTP 500"):
        await k.mahsulotlar()


@pytest.mark.asyncio
async def test_tarmoq_uzilsa_xato_kotariladi():
    def ishlov(soro: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ulanib bo'lmadi")

    k = ClimaventKlient(mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)))

    with pytest.raises(ApiXatosi, match="ulanib bo'lmadi"):
        await k.mahsulotlar()


@pytest.mark.asyncio
async def test_topilmagan_mahsulot():
    k = soxta_klient({})
    with pytest.raises(ApiXatosi):
        await k.mahsulot(999)


# --- faqat o'qish ------------------------------------------------------------


def test_klientda_yozish_metodlari_yoq():
    """Doston yozish endpointiga murojaat qila olmaydi — kodda imkonsiz."""
    ochiq = {a for a in dir(ClimaventKlient) if not a.startswith("_")}
    taqiqlangan = {"yarat", "ochir", "yangila", "create", "delete", "update", "post_yoz"}

    assert not (ochiq & taqiqlangan)
    # Barcha ochiq metodlar o'qish uchun
    assert ochiq == {
        # Buyurtma qilinadigan artikullar (`product-model-inside`) —
        # SAP kodlari va texnik nomlar shundan olinadi.
        "artikullar",
        "katalog_xulosasi",
        "kategoriya_mahsulotlari",
        "kategoriyalar",
        "keshni_tozala",
        # Saytdagi dollar kursini O'QIYDI (`settings.usd-rate`). Narx
        # bazada dollarda saqlangani uchun bot va sayt bir xil kursdan
        # hisoblashi kerak. Yozish esa Nodiraning yozuvchi klientida.
        "kurs",
        "mahsulot",
        "mahsulot_xususiyatlari",
        "sap_kodi",
        "sap_kodlari",
        "mahsulotlar",
        "mahsulotlar_soni",
        "model_boyicha_qidir",
        "model_narxi",
        "qidir",
        "qidir_keng",
        # Texnik jadvallarni O'QIYDI (havo sarfi, bosim) — R2 fayllaridan.
        "texnik_parametrlar",
        "xususiyat_matni",
    }


# --- yordamchilar ------------------------------------------------------------


def test_kop_tilli_matn_tanlanadi():
    assert matn(MAHSULOT, "name", "uz") == "VK-250 ventilyatori"
    assert matn(MAHSULOT, "name", "ru") == "Вентилятор ВК-250"
    # uz bo'sh bo'lsa ru ga tushadi
    assert matn({"name_uz": "", "name_ru": "Тест"}, "name", "uz") == "Тест"
    assert matn({}, "name") == ""


def test_narx_nol_bolsa_narx_yoq_hisoblanadi():
    """0 — 'narx yo'q' degani, 'bepul' emas."""
    assert narx_bormi(MAHSULOT) is False
    assert narx_bormi({"price": 0}) is False
    assert narx_bormi({"price": None}) is False
    assert narx_bormi({"price": 20000}) is True


def test_mahsulot_qisqa_korinishi():
    q = mahsulot_qisqa(MAHSULOT)

    assert q["nomi"] == "VK-250 ventilyatori"
    assert q["kategoriya"] == "Yumaloq kanallar uchun"
    assert q["ishlab_chiqaruvchi"] == "JIHOZVENT"
    assert q["modellar"] == ["VK-250P", "VK-200P"]
    # Narx qisqa ko'rinishga umuman tushmaydi
    assert "narx" not in q and "price" not in q


def test_xususiyatlar_qisqa():
    xs = xususiyatlar_qisqa(MAHSULOT)
    assert xs == [{"nomi": "VK-250P", "qiymat": "230 V, 210 Vt"}]


def test_hujjat_matni_jadvalni_ochadi():
    """R2 dagi boy matn hujjati o'qiladigan jadvalga aylanadi."""
    hujjat = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Texnik xususiyatlar"}],
            },
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "Model"}]}
                                ],
                            },
                            {
                                "type": "tableHeader",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "Quvvat"}]}
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "VK-250"}]}
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "210 Vt"}]}
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }
    natija = hujjat_matni(hujjat)

    assert "Texnik xususiyatlar" in natija
    assert "Model | Quvvat" in natija
    assert "VK-250 | 210 Vt" in natija


@pytest.mark.asyncio
async def test_xususiyat_fayli_ochilmasa_bosh_qaytadi():
    """R2 fayli ochilmasa — xato emas, shunchaki bo'sh (to'qilmaydi)."""

    def ishlov(soro: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    k = ClimaventKlient(mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)))
    assert await k.xususiyat_matni("https://r2.example/x") == ""
    assert await k.xususiyat_matni("") == ""


# --- SAP kodlari -------------------------------------------------------------

# Jonli backenddagi shakl: katalogda `ПВН 500-250-2`, SAP jadvalida
# `ПВН 500-250/2` — farq faqat ajratuvchi belgida.
SAP_YOZUVLARI = [
    {"id": 1, "sap_name": "ПВН 500-250/2", "in_model_name": "ПВН 500-250/2",
     "product_model_id": 96},
    {"id": 2, "sap_name": "ВР 6-28-4-О-1-0,37/1500",
     "in_model_name": "ВР 6-28-4-1-0,37/1500", "product_model_id": 96},
    # Bir kalitga ikki xil kod — ishlatilmasligi kerak
    {"id": 3, "sap_name": "ДКСп 500х300", "in_model_name": "ДКСП 500Х300",
     "product_model_id": 5},
    {"id": 4, "sap_name": "ДКСп 600х300", "in_model_name": "ДКСП-500-Х300",
     "product_model_id": 5},
]


def _sap_klient(javob=SAP_YOZUVLARI, kod: int = 200):
    async def ishlov(soro: httpx.Request) -> httpx.Response:
        # `/api/product-models/all` BOSHQA yo'q — backend uni olib
        # tashlagan (2026-09-09). SAP kodlari yagona manbadan keladi.
        assert soro.url.path == "/api/product-model-inside"
        return httpx.Response(kod, json=javob)

    return ClimaventKlient(
        asos="https://test",
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )


@pytest.mark.asyncio
async def test_sap_kodi_ajratuvchi_belgidan_qatiy_nazar_topiladi():
    """Katalogda `-2`, SAP da `/2` — bir xil model, kod topilishi shart."""
    k = _sap_klient()
    assert await k.sap_kodi("ПВН 500-250-2") == "ПВН 500-250/2"
    assert await k.sap_kodi("ПВН 500-250/2") == "ПВН 500-250/2"


@pytest.mark.asyncio
async def test_sap_kodi_in_model_name_boyicha_boglanadi():
    """`sap_name` da qo'shimcha `-О-` bo'lsa ham, katalog nomi mos keladi."""
    assert await _sap_klient().sap_kodi("ВР 6-28-4-1-0,37-1500") == (
        "ВР 6-28-4-О-1-0,37/1500"
    )


@pytest.mark.asyncio
async def test_ikki_xil_kod_tushsa_ishlatilmaydi():
    """Noto'g'ri kod mijozga ketgandan ko'ra, kodsiz chiqqani yaxshi."""
    assert await _sap_klient().sap_kodi("ДКСП 500х300") == ""


@pytest.mark.asyncio
async def test_topilmasa_bosh_qaytadi():
    assert await _sap_klient().sap_kodi("Jetfun-9000") == ""
    assert await _sap_klient().sap_kodi("") == ""


@pytest.mark.asyncio
async def test_manba_yiqilsa_bosh_karta_qaytadi():
    """Yagona manba yiqilsa — jimgina noto'g'ri kod bermaydi, bo'sh qoladi."""
    karta = await _sap_klient(javob={"xato": "server"}, kod=500).sap_kodlari()

    assert karta == {}


@pytest.mark.asyncio
async def test_ikkala_manba_yiqilsa_ham_kp_toxtamaydi():
    """API butunlay yiqilsa ham KP tuziladi — shunchaki kod bo'lmaydi."""
    async def ishlov(soro: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"xato": "server"})

    k = ClimaventKlient(
        asos="https://test",
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )
    assert await k.sap_kodlari() == {}
    assert await k.sap_kodi("ПВН 500-250-2") == ""


@pytest.mark.asyncio
async def test_sap_kodi_ichki_jadvaldan_olinadi():
    """Yagona manba — `product_model_inside` (`in_model_name` -> `sap_name`).

    Ilgari birinchi navbatda `product_models.sap_name` o'qilardi. Backend
    o'sha jadvalni olib tashlagach chaqiruv 404 qaytarib, natija jimgina
    shu manbaga tushardi — endi u ochiq va yagona.
    """
    k = _sap_klient()

    assert await k.sap_kodi("ВР 6-28-4-1-0,37/1500") == "ВР 6-28-4-О-1-0,37/1500"


# --- katalog TO'LIQ olinishi --------------------------------------------------
#
# JONLI REGRESSIYA (2026-08-10): backend `/api/products/all` ga standart
# chegara (20) qo'ydi — buni biz so'ragan edik. Klient parametrsiz
# chaqirar edi va 137 mahsulot o'rniga 20 tasini olib qoldi.
#
# Xatolik hech qayerda ko'rinmadi: API 200 qaytardi, shunchaki ma'lumot
# kam edi. Natijasi esa og'ir bo'ldi — Rustam Ø315 uchun bironta uskuna
# topa olmadi, Temur esa omborga SHAXTA ventilyatorini tanladi.


def _sahifali_klient(jami: int, sahifa_hajmi: int):
    """Backend kabi sahifalab qaytaradigan soxta server."""
    mahsulotlar = [
        {"id": i, "name_uz": f"Mahsulot {i}", "models": [{"name": f"M-{i}"}]}
        for i in range(1, jami + 1)
    ]
    chaqiruvlar: list[str] = []

    async def ishlov(soro: httpx.Request) -> httpx.Response:
        chaqiruvlar.append(str(soro.url))
        sahifa = int(soro.url.params.get("page", 1))
        chek = int(soro.url.params.get("limit", 20))
        boshi = (sahifa - 1) * chek
        return httpx.Response(200, json=mahsulotlar[boshi : boshi + chek])

    k = ClimaventKlient(
        asos="https://test",
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )
    return k, chaqiruvlar


@pytest.mark.asyncio
async def test_katalog_toliq_olinadi():
    """20 emas, 137 ta — sahifalar oxirigacha o'qilishi kerak."""
    k, chaqiruvlar = _sahifali_klient(jami=137, sahifa_hajmi=100)

    mahsulotlar = await k.mahsulotlar()

    assert len(mahsulotlar) == 137, "katalog chala olindi"
    assert len(chaqiruvlar) >= 2, "sahifalash umuman ishlatilmadi"
    # Har chaqiruvda chegara ko'rsatilishi kerak — parametrsiz chaqiruv
    # backendning standart 20 tasini beradi.
    assert all("limit=" in u and "page=" in u for u in chaqiruvlar)


@pytest.mark.asyncio
async def test_bitta_sahifaga_sigsa_ortiqcha_sorov_yoq():
    k, chaqiruvlar = _sahifali_klient(jami=10, sahifa_hajmi=100)

    assert len(await k.mahsulotlar()) == 10
    assert len(chaqiruvlar) == 1


@pytest.mark.asyncio
async def test_katalog_juda_uzun_bolsa_ogohlantiradi():
    """Chegaraga urilsak — jimgina chala ma'lumot bermaymiz."""
    from integrations import climavent_client as modul

    k, _ = _sahifali_klient(jami=100000, sahifa_hajmi=100)
    asl = modul.MAKS_SAHIFA
    modul.MAKS_SAHIFA = 3
    try:
        await k.mahsulotlar()
    finally:
        modul.MAKS_SAHIFA = asl

    assert "hammasi o'qilmadi" in k.ogohlantirish


# --- variant narxi (product_model_inside, DOLLARDA) -------------------------
#
# 2026-iyundan narx `characters[].insides[].price` da va DOLLARDA turadi.
# Eski `models[].price` esa SO'MDA. Ikkalasini adashtirsak natija 12 000
# barobar noto'g'ri chiqadi — shuning uchun chegara aniq tekshiriladi.

from integrations.climavent_client import katalog_narxi  # noqa: E402

KATALOG_ICHKI = [
    {
        "name_uz": "Ventilyator ВЦ 4-75",
        "models": [{"name": "ВЦ 4-75-2,5-1", "price": None}],
        "characters": [
            {
                "title": "ВЦ 4-75-2,5",
                "price": 0,
                "insides": [
                    {"in_model_name": "ВЦ 4-75-2,5-1-0,12/1500", "price": 156.76},
                    {"in_model_name": "ВЦ 4-75-2,5-1-0,75/3000", "price": 199.33},
                    {"in_model_name": "ВЦ 4-75-2,5-1-0,25/1500", "price": None},
                ],
            }
        ],
    },
    {
        "name_uz": "Kanal ventilyatori ВК",
        "models": [{"name": "ВК-100П", "price": "999000"}],   # ESKI: SO'MDA
        "characters": [],
    },
]


def test_variant_narxi_dollardan_somga_ogiriladi():
    natija = katalog_narxi(KATALOG_ICHKI, "ВЦ 4-75-2,5-1-0,75/3000", kurs=12000)

    assert natija is not None
    assert natija[0] == 199.33 * 12000
    assert "199.33 $" in natija[1]


def test_quvvat_aytilmasa_eng_arzoni_va_OCHIQ_aytiladi():
    """Jim tanlash xato bo'lardi — mijoz boshqa quvvat so'ragan bo'lishi mumkin."""
    natija = katalog_narxi(KATALOG_ICHKI, "ВЦ 4-75-2,5", kurs=12000)

    assert natija[0] == 156.76 * 12000          # eng arzoni
    assert "2 variantdan eng arzoni" in natija[1]


def test_narxsiz_variant_hisobga_olinmaydi():
    """`price=None` — "narx kiritilmagan", "bepul" emas."""
    natija = katalog_narxi(KATALOG_ICHKI, "ВЦ 4-75-2,5", kurs=12000)

    assert "0,25/1500" not in natija[1]


def test_eski_somdagi_narxga_KURS_QOLLANILMAYDI():
    """Eng xavfli chegara: `models[].price` SO'MDA, ko'paytirilmasligi shart."""
    natija = katalog_narxi(KATALOG_ICHKI, "ВК-100П", kurs=12000)

    assert natija[0] == 999_000        # 999 000, 11 988 000 000 emas
    assert "$" not in natija[1]


def test_topilmasa_none():
    assert katalog_narxi(KATALOG_ICHKI, "bunday model yo'q", kurs=12000) is None


# --- texnik kesh: eskirsa ham darrov beriladi -------------------------------
#
# O'lchandi (2026-08-19): keshni noldan yig'ish 256 SEKUND turadi.
# Ilgari muddat (7 kun) o'tgan zahoti keyingi so'rov shuncha kutardi.

import json as _json  # noqa: E402
import time as _vaqt  # noqa: E402


def _bosh_mijoz() -> httpx.AsyncClient:
    """Tarmoqqa chiqilsa test yiqilsin — kesh ishlatilishi SHART."""
    def ishlov(_):
        raise AssertionError("kesh o'rniga tarmoqqa chiqildi")
    return httpx.AsyncClient(transport=httpx.MockTransport(ishlov))


def _kesh_yoz(yol, yosh_kun: float) -> None:
    yol.write_text(_json.dumps({
        "yozilgan": _vaqt.time() - yosh_kun * 86400,
        "parametrlar": {"ВК-250П": {"model": "ВК-250П", "havo_sarfi": 1200}},
    }), encoding="utf-8")


@pytest.mark.asyncio
async def test_yangi_kesh_ishlatiladi(tmp_path, monkeypatch):
    from app.config import sozlama
    fayl = tmp_path / "texnik.json"
    _kesh_yoz(fayl, yosh_kun=1)
    monkeypatch.setattr(sozlama(), "texnik_kesh_yoli", str(fayl), raising=False)

    k = ClimaventKlient(mijoz=_bosh_mijoz(), kesh_ttl=60)
    natija = await k.texnik_parametrlar()

    assert "ВК-250П" in natija


@pytest.mark.asyncio
async def test_eskirgan_kesh_HAM_darrov_qaytariladi(tmp_path, monkeypatch):
    """Menejer 4 daqiqa kutmasin — eski ma'lumot yo'qdan yaxshi."""
    from app.config import sozlama
    fayl = tmp_path / "texnik.json"
    _kesh_yoz(fayl, yosh_kun=99)               # muddati ancha o'tgan
    monkeypatch.setattr(sozlama(), "texnik_kesh_yoli", str(fayl), raising=False)

    k = ClimaventKlient(mijoz=_bosh_mijoz(), kesh_ttl=60)
    boshi = _vaqt.perf_counter()
    natija = await k.texnik_parametrlar()
    ketgan = _vaqt.perf_counter() - boshi

    assert "ВК-250П" in natija          # eski ma'lumot qaytdi
    assert ketgan < 1.0                 # kutish yo'q

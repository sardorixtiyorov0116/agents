"""Mahsulot mutaxassisi Sardor — spesifikatsiya, to'qimaslik, narx bermaslik."""

from __future__ import annotations

import json

import pytest

from app.agentlar.mahsulot_mutaxassisi import MahsulotMutaxassisi, SardorNatija
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, matn_bloki, qidiruv_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["product-spec"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "sardor.db")
    await b.tayyorla()
    return b


def sardor_javobi(**ustama):
    malumot = {
        "mahsulot": "iPhone 15 128GB",
        "kategoriya": "smartfon",
        "xususiyatlar": [
            {
                "nomi": "Ekran o'lchami",
                "qiymat": "6.1 dyuym",
                "manba_nomi": "apple.com",
                "havola": "https://apple.com/iphone-15/specs",
                "ishonch": "yuqori",
            },
            {
                "nomi": "Xotira",
                "qiymat": "128 GB",
                "manba_nomi": "apple.com",
                "havola": "https://apple.com/iphone-15/specs",
                "ishonch": "yuqori",
            },
        ],
        "topilmagan_maydonlar": [],
        "ziddiyatlar": [],
    }
    malumot.update(ustama)
    return malumot


def soxta(malumot, qidiruv=None):
    bloklar = []
    if qidiruv:
        bloklar.append(qidiruv_bloki(qidiruv))
    bloklar.append(matn_bloki(json.dumps(malumot, ensure_ascii=False)))
    return SoxtaLlm([javob(bloklar)])


@pytest.mark.asyncio
async def test_spesifikatsiya_qaytadi(kontrakt, baza):
    llm = soxta(sardor_javobi(), [{"title": "apple.com", "url": "https://apple.com/x"}])
    sardor = MahsulotMutaxassisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await sardor.ishla("iPhone 15 128GB spesifikatsiyasi")

    assert k.kim == "product-spec"
    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.YUQORI
    assert len(k.natija["xususiyatlar"]) == 2
    assert "https://apple.com/iphone-15/specs" in {m.havola for m in k.manba}


@pytest.mark.asyncio
async def test_narx_maydoni_sxemada_yoq(kontrakt):
    """Chegara struktura darajasida: model narx qaytara olmaydi."""
    maydonlar = set(SardorNatija.model_fields)
    assert "narx" not in maydonlar
    assert not any("narx" in m for m in maydonlar)

    from app.agentlar.mahsulot_mutaxassisi import TIZIM_PROMPT

    assert "NARX BERMAYSAN" in TIZIM_PROMPT
    assert "Zara" in TIZIM_PROMPT


@pytest.mark.asyncio
async def test_topilmagan_maydon_bosh_qoladi(kontrakt, baza):
    llm = soxta(
        sardor_javobi(
            xususiyatlar=[],
            topilmagan_maydonlar=["Batareya sig'imi", "Suv o'tkazmaslik darajasi"],
        )
    )
    sardor = MahsulotMutaxassisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await sardor.ishla("Noma'lum model X to'liq spesifikatsiyasi")

    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.PAST
    assert k.natija["xususiyatlar"] == []
    assert "Batareya sig'imi" in k.natija["topilmagan_maydonlar"]
    assert "bo'sh qoldirildi" in k.izoh


@pytest.mark.asyncio
async def test_manbasiz_xususiyat_olib_tashlanadi(kontrakt, baza):
    """To'qib chiqarishning eng ehtimolli shakli — manbasiz qiymat."""
    llm = soxta(
        sardor_javobi(
            xususiyatlar=[
                {
                    "nomi": "Protsessor",
                    "qiymat": "A16 Bionic",
                    "manba_nomi": None,
                    "havola": None,
                    "ishonch": "yuqori",
                }
            ]
        )
    )
    sardor = MahsulotMutaxassisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await sardor.ishla("iPhone 15 protsessori")

    assert k.natija["xususiyatlar"] == []
    assert "Protsessor" in k.natija["topilmagan_maydonlar"]
    assert "manbasiz" in k.izoh


@pytest.mark.asyncio
async def test_zid_manbalar_ikkalasi_ham_korsatiladi(kontrakt, baza):
    llm = soxta(
        sardor_javobi(
            xususiyatlar=[
                {
                    "nomi": "Batareya",
                    "qiymat": "3349 mAh",
                    "manba_nomi": "apple.com",
                    "havola": "https://apple.com/s",
                    "ishonch": "yuqori",
                },
                {
                    "nomi": "Batareya",
                    "qiymat": "3877 mAh",
                    "manba_nomi": "gsmarena",
                    "havola": "https://gsmarena.com/s",
                    "ishonch": "orta",
                },
            ],
            ziddiyatlar=["Batareya sig'imi bo'yicha manbalar zid: 3349 va 3877 mAh"],
        )
    )
    sardor = MahsulotMutaxassisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await sardor.ishla("iPhone 15 batareyasi")

    assert len(k.natija["xususiyatlar"]) == 2
    assert k.ishonch is Ishonch.ORTA
    assert "ziddiyati" in k.izoh
    assert len(k.manba) >= 2


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("yaxshi telefon, tavsiya qilaman")])])
    sardor = MahsulotMutaxassisi(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await sardor.ishla("iPhone 15")
    assert k.holat is Holat.XATO


# --- tanlash rejimi (mijoz talabi bo'yicha) ----------------------------------

from .soxta import soxta_api, soxta_bilim  # noqa: E402

TANLOV_KATALOG = [
    {
        "id": 31,
        "name_uz": "Suv bilan ishlaydigan kanalli isitgich ПВН",
        "category": {"name_uz": "To'rtburchak kanallar uchun"},
        "description_short_uz": "To'rtburchak kanallar uchun suvli isitgich.",
        "models": [
            {"id": 28, "name": "ПВН 500-250-2", "price": "1700000"},
            {"id": 29, "name": "ПВН 500-250-3", "price": "2200000"},
            {"id": 32, "name": "ПВН 600-300-2", "price": "2220000"},
        ],
        "characters": [],
        "quantity": 4,
    },
    {
        "id": 26,
        "name_uz": "Kanal ventilyatori ВК-П",
        "category": {"name_uz": "Yumaloq kanallar uchun"},
        "models": [{"id": 91, "name": "ВК-315П", "price": "0"}],
        "characters": [],
        "quantity": 10,
    },
]


def tanlov_javobi(**ustama):
    malumot = {
        "talablar": [
            {"nomi": "kanal o'lchami", "qiymat": "500x250 mm"},
            {"nomi": "qatorlar soni", "qiymat": "2"},
        ],
        "variantlar": [
            {
                "mahsulot": "Suv bilan ishlaydigan kanalli isitgich ПВН",
                "model": "ПВН 500-250-2",
                "moslik_darajasi": "to'liq",
                "javob_beradi": ["500x250 mm kanal", "2 qatorli"],
                "javob_bermaydi": [],
                "izoh": "",
            }
        ],
        "aniqlashtirish": ["Havo sarfi qancha?"],
        "qaror_izohi": "",
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


def tanlov_sardor(kontrakt, baza, llm, katalog=TANLOV_KATALOG):
    return MahsulotMutaxassisi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(qidir_keng=katalog, mahsulotlar=katalog),
        qidiruv_manbasi=soxta_bilim(),
    )


def test_rejim_aniqlash():
    """Talab aytilganda tanlash, model kodi aytilganda spesifikatsiya."""
    from app.agentlar.mahsulot_mutaxassisi import tanlov_rejimimi

    # Talab — tanlash rejimi
    assert tanlov_rejimimi("500x250 kanal uchun 2 qatorli isitgich kerak")
    assert tanlov_rejimimi("1500 m3/soat ga mos ventilyator tanlab ber")
    assert tanlov_rejimimi("250 Pa bosimga qaysi ventilyator mos keladi?")
    assert tanlov_rejimimi("подобрать вентилятор на 2000 м3/ч")

    # Model kodi — spesifikatsiya rejimi
    assert not tanlov_rejimimi("ПВН 500-250-2 xususiyatlarini ber")
    assert not tanlov_rejimimi("ВК-250П spesifikatsiyasi")
    assert not tanlov_rejimimi("ПВН 500-250-2 mos keladimi?")
    # Umuman boshqa ish
    assert not tanlov_rejimimi("Olmaliq AGMK uchun KP tayyorla")


def test_olcham_va_birlik_kod_deb_sanalmaydi():
    """"500x250" va "1500 m3/soat" — talab, model kodi emas."""
    from app.agentlar.mahsulot_mutaxassisi import kod_bormi

    assert not kod_bormi("500x250 kanal kerak")
    assert not kod_bormi("1500 m3/soat")
    assert not kod_bormi("2 qatorli isitgich")
    assert kod_bormi("ВК-250П")
    assert kod_bormi("ПВН 500-250-2")


@pytest.mark.asyncio
async def test_talabga_mos_variantlar(kontrakt, baza):
    k = await tanlov_sardor(kontrakt, baza, tanlov_javobi()).ishla(
        "500x250 kanal uchun 2 qatorli suvli isitgich kerak"
    )

    assert k.holat is Holat.TUGADI
    assert k.natija["variantlar"][0]["model"] == "ПВН 500-250-2"
    assert k.natija["talablar"][0]["qiymat"] == "500x250 mm"
    # Manba — ichki katalog
    assert any(m.tur == "ichki_api" for m in k.manba)


@pytest.mark.asyncio
async def test_katalogda_yoq_model_tashlanadi(kontrakt, baza):
    """O'ZGARMAS QOIDA: mavjud bo'lmagan mahsulot taklif qilinmaydi."""
    llm = tanlov_javobi(variantlar=[
        {"mahsulot": "Boshqa brend", "model": "XYZ-9000",
         "moslik_darajasi": "to'liq", "javob_beradi": [], "javob_bermaydi": [],
         "izoh": ""},
        {"mahsulot": "Suv bilan ishlaydigan kanalli isitgich ПВН",
         "model": "ПВН 500-250-2", "moslik_darajasi": "to'liq",
         "javob_beradi": [], "javob_bermaydi": [], "izoh": ""},
    ])
    k = await tanlov_sardor(kontrakt, baza, llm).ishla("500x250 uchun isitgich kerak")

    modellar = [v["model"] for v in k.natija["variantlar"]]
    assert modellar == ["ПВН 500-250-2"], "katalogda yo'q model o'tib ketdi"


@pytest.mark.asyncio
async def test_mos_mahsulot_yoq_bolsa_ochiq_aytadi(kontrakt, baza):
    llm = tanlov_javobi(
        variantlar=[], qaror_izohi="Katalogda 800x400 kanal uchun isitgich yo'q."
    )
    k = await tanlov_sardor(kontrakt, baza, llm).ishla("800x400 kanal uchun isitgich kerak")

    assert k.holat is Holat.TUGADI
    assert k.natija["variantlar"] == []
    assert "topilmadi" in k.izoh
    assert k.ishonch is Ishonch.ORTA


@pytest.mark.asyncio
async def test_katalog_yiqilsa_taxmin_qilmaydi(kontrakt, baza):
    """Katalogsiz tanlash mumkin emas — to'qib chiqarilmaydi."""
    sardor = MahsulotMutaxassisi(
        kontrakt=kontrakt, llm=SoxtaLlm([]), baza=baza,
        api=soxta_api(),  # sozlanmagan -> ApiXatosi
        qidiruv_manbasi=soxta_bilim(),
    )
    k = await sardor.ishla("500x250 kanal uchun isitgich kerak")

    assert k.holat is Holat.XATO
    assert "katalog" in k.izoh.lower()


@pytest.mark.asyncio
async def test_modellar_promptga_beriladi(kontrakt, baza):
    """Model nomlarida o'lcham kodlangan — model ularni ko'rishi shart."""
    llm = tanlov_javobi()
    await tanlov_sardor(kontrakt, baza, llm).ishla("500x250 uchun isitgich kerak")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ПВН 500-250-2" in xabar
    assert "ПВН 600-300-2" in xabar
    assert "ICHKI KATALOG" in xabar


@pytest.mark.asyncio
async def test_tanlashda_veb_qidiruv_ishlatilmaydi(kontrakt, baza):
    """Taklif faqat O'Z katalogimizdan bo'lishi kerak."""
    llm = tanlov_javobi()
    await tanlov_sardor(kontrakt, baza, llm).ishla("500x250 uchun isitgich kerak")

    assert "tools" not in llm.chaqiruvlar[0]


def test_tanlov_natijasida_narx_maydoni_yoq():
    """Chegara struktura darajasida: narx qaytarib bo'lmaydi."""
    from app.agentlar.mahsulot_mutaxassisi import TanlovNatija, Variant

    assert not any("narx" in m for m in Variant.model_fields)
    assert not any("narx" in m for m in TanlovNatija.model_fields)


def test_tanlov_promptida_chegaralar():
    from app.agentlar.mahsulot_mutaxassisi import TANLOV_PROMPT

    assert "FAQAT KATALOGDAGI" in TANLOV_PROMPT
    assert "NARX BERMAYSAN" in TANLOV_PROMPT
    assert "tavsiya qilaman" in TANLOV_PROMPT
    # Har variantda ijobiy ham, salbiy ham ko'rsatilishi shart
    assert "JAVOB BERADI" in TANLOV_PROMPT
    assert "BERMAYDI" in TANLOV_PROMPT


def test_tanlov_korinishi():
    """Presenter variantlarni odamcha ko'rsatadi."""
    from presenter.agentlar import agent_matni

    matn = agent_matni("product-spec", {
        "rejim": "tanlov",
        "talablar": [{"nomi": "kanal", "qiymat": "500x250"}],
        "variantlar": [{
            "mahsulot": "ПВН", "model": "ПВН 500-250-2",
            "moslik_darajasi": "to'liq",
            "javob_beradi": ["500x250 kanal"], "javob_bermaydi": ["3 qator"],
        }],
        "aniqlashtirish": ["Havo sarfi qancha?"],
    })

    assert "ПВН 500-250-2" in matn or "ПВН" in matn
    assert "Javob beradi" in matn
    assert "Javob bermaydi" in matn
    assert "Havo sarfi" in matn


@pytest.mark.asyncio
async def test_bosh_variant_ham_tanlov_korinishida(kontrakt, baza):
    """"Mos mahsulot yo'q" javobi spesifikatsiya ko'rinishida chiqmasin."""
    from presenter.agentlar import agent_matni

    llm = tanlov_javobi(variantlar=[], qaror_izohi="800x400 uchun isitgich yo'q.")
    k = await tanlov_sardor(kontrakt, baza, llm).ishla("800x400 kanal uchun isitgich kerak")

    assert k.natija["rejim"] == "tanlov"
    matn = agent_matni("product-spec", k.natija)
    assert "Talabga mos mahsulotlar" in matn
    assert "Xususiyat topilmadi" not in matn
    assert "800x400" in matn


def test_katalog_moslik_boyicha_saralanadi():
    """Kerakli mahsulot 40-o'rinda bo'lsa ham ro'yxatga tushishi kerak."""
    from app.agentlar.mahsulot_mutaxassisi import MahsulotMutaxassisi

    katalog = [
        {"id": i, "name_uz": f"Boshqa mahsulot {i}", "category": {"name_uz": "x"},
         "models": [], "characters": []}
        for i in range(40)
    ] + [
        {"id": 99, "name_uz": "Suv bilan ishlaydigan kanalli isitgich ПВН",
         "category": {"name_uz": "To'rtburchak kanallar uchun"},
         "models": [{"name": "ПВН 500-250-2"}], "characters": []},
    ]
    saralangan = MahsulotMutaxassisi._saralab(katalog, "kanalli isitgich kerak 500x250")

    assert saralangan[0]["id"] == 99, "mos mahsulot birinchi bo'lishi kerak"


@pytest.mark.asyncio
async def test_toliq_katalogdan_mos_mahsulot_topiladi(kontrakt, baza):
    """API qidiruvi bo'sh qaytarsa ham, katalogdan saralab topiladi."""
    kop_katalog = [
        {"id": i, "name_uz": f"Aloqasiz mahsulot {i}", "category": {"name_uz": "x"},
         "models": [], "characters": []}
        for i in range(30)
    ] + TANLOV_KATALOG

    llm = tanlov_javobi()
    sardor = MahsulotMutaxassisi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(qidir_keng=[], mahsulotlar=kop_katalog),
        qidiruv_manbasi=soxta_bilim(),
    )
    await sardor.ishla("kanalli isitgich kerak, 500x250 kanal")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ПВН 500-250-2" in xabar, "mos mahsulot promptga tushmadi"


# --- bilim bazasi (RAG) --------------------------------------------------

SARDOR_BILIMI = (
    ("Model kodini o'qish, Kanal ventilyatorlari",
     "ВКР-4 — tom ventilyatori, tomga o'rnatiladigan turdagi."),
    ("Shovqin — sabablari va kamaytirish, Asosiy sabablar",
     "Shovqin ish nuqtasi FIDdan uzoqlashganda keskin oshadi."),
)


def bilimli_sardor(kontrakt, baza, llm, parchalar=SARDOR_BILIMI):
    return MahsulotMutaxassisi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(qidir_keng=[], mahsulotlar=[]),
        qidiruv_manbasi=soxta_bilim(*parchalar),
    )


@pytest.mark.asyncio
async def test_kompaniya_hujjati_promptga_tushadi(kontrakt, baza):
    """Sardorga `product` papkasi biriktirilgan, lekin u o'qilmasdi.

    Bosma katalog va uslubiy hujjatlar ichki API'da yo'q — model kodi
    qanday o'qilishi, shovqin nimaga bog'liqligi faqat shu hujjatlarda.
    """
    llm = soxta(sardor_javobi())
    await bilimli_sardor(kontrakt, baza, llm).ishla("ВКР-4 spesifikatsiyasi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "KOMPANIYA HUJJATLARI" in xabar
    assert "tomga o'rnatiladigan" in xabar


@pytest.mark.asyncio
async def test_hujjat_topilmasa_MODELGA_ochiq_aytiladi(kontrakt, baza):
    """Jim qolish xavfli: model hujjatga tayangandek javob berib qo'yadi."""
    llm = soxta(sardor_javobi())
    await bilimli_sardor(kontrakt, baza, llm, parchalar=()).ishla("ВКР-4 spesifikatsiyasi")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "hujjat topilmadi" in xabar


@pytest.mark.asyncio
async def test_tanlashda_ham_hujjat_oqiladi(kontrakt, baza):
    """Tanlash uslubiyati (ish nuqtasi, shovqin) hujjatlarda."""
    llm = tanlov_javobi()
    sardor = MahsulotMutaxassisi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(qidir_keng=TANLOV_KATALOG, mahsulotlar=TANLOV_KATALOG),
        qidiruv_manbasi=soxta_bilim(*SARDOR_BILIMI),
    )
    await sardor.ishla("500x250 uchun isitgich kerak")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "KOMPANIYA HUJJATLARI" in xabar
    assert "ish nuqtasi FIDdan" in xabar


@pytest.mark.asyncio
async def test_hujjat_manbasi_ALOHIDA_turda_korinadi(kontrakt, baza):
    """Menejer qayerdan olinganini ajrata olishi kerak.

    Kompaniya hujjati tashqi vebdan ishonchliroq, ichki katalogdan esa
    eskiroq — uchalasi bir xil ko'rinsa bu farq yo'qoladi.
    """
    llm = soxta(sardor_javobi(xususiyatlar=[
        {"nomi": "Kanal o'lchami", "qiymat": "400x200 mm",
         "manba_turi": "bilim", "manba_nomi": "Model kodini o'qish",
         "ishonch": "yuqori"},
        {"nomi": "Og'irligi", "qiymat": "12 kg",
         "manba_turi": "tashqi_veb", "manba_nomi": "vents.uz",
         "havola": "https://vents.uz/vkp", "ishonch": "orta"},
    ]))
    k = await bilimli_sardor(kontrakt, baza, llm).ishla("ВКР-4 spesifikatsiyasi")

    turlar = {m.tur for m in k.manba}
    assert "bilim" in turlar, f"hujjat manbasi ko'rinmadi: {turlar}"
    assert "tashqi_veb" in turlar
    # Taqsimot izohda ham to'g'ri bo'lsin — hujjat vebga qo'shilib ketmasin.
    assert "kompaniya hujjati: 1" in k.izoh
    assert "tashqi veb: 1" in k.izoh


def test_tanlov_promptida_katalogdan_TASHQARI_model_taqiqlangan():
    """Hujjatda eskirgan model nomlari bor — ular taklif bo'lib ketmasin."""
    from app.agentlar.mahsulot_mutaxassisi import TANLOV_PROMPT

    assert "ICHKI KATALOG" in TANLOV_PROMPT
    assert "TAKLIF QILMAYSAN" in TANLOV_PROMPT

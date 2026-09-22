"""SMM tahlilchisi Nilufar — raqam to'qimaslik, post o'ylab topmaslik."""

from __future__ import annotations

import json

import httpx
import pytest

from app.agentlar.smm_tahlilchi import TIZIM_PROMPT, SmmTahlilchi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch
from integrations import InstagramKlient, InstagramXatosi, foydalanuvchi_nomi
from presenter.agentlar import agent_matni

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim

pytestmark = pytest.mark.oz_transporti


def media(i: int, korish: int, sarlavha: str, kommentlar=()):
    return {
        "id": f"m{i}",
        "media_type": "VIDEO",
        "media_product_type": "REELS",
        "caption": sarlavha,
        "permalink": f"https://instagram.com/reel/{i}",
        "timestamp": f"2026-07-{10 + i:02d}T10:00:00+0000",
        "like_count": korish // 20,
        "comments_count": len(kommentlar),
        "view_count": korish,
        "comments": {"data": [{"text": k, "like_count": 0} for k in kommentlar]},
    }


GRAPH_JAVOBI = {
    "business_discovery": {
        "followers_count": 12400,
        "media_count": 210,
        "media": {"data": [
            media(1, 180_000, "Ventilyator qanday tanlanadi?\nTo'liq qo'llanma",
                  ["Narxi qancha?", "Narxini ayting", "Yetkazib berasizmi?"]),
            media(2, 9_000, "Yangi mahsulot", ["Narxi qancha?"]),
            media(3, 45_000, "3 xato: kanal o'lchamini noto'g'ri tanlash",
                  ["Zo'r", "Narxi qancha?"]),
        ]},
    }
}


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["smm-analyst"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "nilufar.db")
    await b.tayyorla()
    return b


def soxta_instagram(javob_tanasi=None, holat=200):
    kuzatuv: list[httpx.Request] = []

    def ishlov(soro: httpx.Request) -> httpx.Response:
        kuzatuv.append(soro)
        return httpx.Response(
            holat, json=javob_tanasi if javob_tanasi is not None else GRAPH_JAVOBI
        )

    klient = InstagramKlient(
        token="sinov-token", ig_user_id="17841400000000000",
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )
    klient.kuzatuv = kuzatuv  # type: ignore[attr-defined]
    return klient


def nilufar_javobi(**ustama):
    malumot = {
        "umumiy_baho": "Profil ta'lim beruvchi kontentga tayanadi.",
        "kontent_turlari": ["qo'llanma", "xato tahlili"],
        "ishlagan_postlar": [{"raqam": 1, "nega_ishladi": "Savol bilan boshlangan"}],
        "hook_naqshlari": [
            {"naqsh": "savol bilan boshlash", "misol": "Ventilyator qanday tanlanadi?",
             "izoh": "eng ko'p ko'rilgan postda"}
        ],
        "komment_muammolari": [
            {"mavzu": "Narx so'ralgan, javob yo'q", "necha_marta": 4,
             "izoh": "Narxni sarlavhaga qo'ying"}
        ],
        "tavsiyalar": ["Savol shaklidagi hooklarni ko'paytiring"],
        "cheklovlar": [],
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


def nilufar_yasa(kontrakt, baza, llm, instagram=None):
    return SmmTahlilchi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(), qidiruv_manbasi=soxta_bilim(),
        instagram=instagram or soxta_instagram(),
    )


# --- havoladan profil ajratish -----------------------------------------------


def test_havoladan_profil_ajratiladi():
    for xom in (
        "https://www.instagram.com/climaventuz/",
        "instagram.com/climaventuz",
        "@climaventuz",
        "climaventuz",
        "https://instagram.com/climaventuz/?hl=ru",
    ):
        assert foydalanuvchi_nomi(xom) == "climaventuz"


@pytest.mark.asyncio
async def test_sorovdagi_havola_topiladi(kontrakt, baza):
    ig = soxta_instagram()
    await nilufar_yasa(kontrakt, baza, nilufar_javobi(), ig).ishla(
        "https://instagram.com/climaventuz profilini tahlil qil"
    )

    assert ig.kuzatuv, "Instagram API chaqirilmadi"
    # Birinchi so'rov — "bu bizning akkauntmi?" tekshiruvi; profil so'rovi
    # keyingilarida bo'ladi.
    assert any("climaventuz" in str(s.url) for s in ig.kuzatuv)


@pytest.mark.asyncio
async def test_profil_korsatilmasa_soraydi(kontrakt, baza):
    k = await nilufar_yasa(kontrakt, baza, SoxtaLlm([])).ishla("SMM tahlil qilib ber")

    assert k.holat is Holat.XATO
    assert "havolasini" in k.izoh


# --- eng muhim: raqam va post to'qib bo'lmaydi --------------------------------


@pytest.mark.asyncio
async def test_raqamlar_apidan_olinadi(kontrakt, baza):
    """O'ZGARMAS QOIDA: ko'rish va layk soni model javobidan olinmaydi."""
    k = await nilufar_yasa(kontrakt, baza, nilufar_javobi()).ishla(
        "@climaventuz tahlil qil"
    )

    assert k.holat is Holat.TUGADI
    assert k.natija["obunachilar"] == 12400
    assert k.natija["eng_kop_korilgan"]["korishlar"] == 180_000
    assert k.natija["ishlagan_postlar"][0]["korishlar"] == 180_000
    assert k.natija["ishlagan_postlar"][0]["havola"] == "https://instagram.com/reel/1"


def test_model_korsatkich_qaytara_olmaydi():
    """Chegara struktura darajasida."""
    from app.agentlar.smm_tahlilchi import IshlaganPost, NilufarNatija

    for model in (NilufarNatija, IshlaganPost):
        maydonlar = " ".join(model.model_fields)
        for taqiq in ("korish", "layk", "obunachi", "view", "like"):
            assert taqiq not in maydonlar.lower(), f"{model.__name__}: {taqiq}"


@pytest.mark.asyncio
async def test_notogri_raqamli_post_tashlanadi(kontrakt, baza):
    llm = nilufar_javobi(ishlagan_postlar=[
        {"raqam": 99, "nega_ishladi": "mavjud bo'lmagan post"},
        {"raqam": 1, "nega_ishladi": "haqiqiy post"},
    ])
    k = await nilufar_yasa(kontrakt, baza, llm).ishla("@climaventuz")

    assert len(k.natija["ishlagan_postlar"]) == 1
    assert k.natija["ishlagan_postlar"][0]["nega_ishladi"] == "haqiqiy post"


@pytest.mark.asyncio
async def test_postlar_korishlar_boyicha_tartiblanadi(kontrakt, baza):
    """Model 1-raqam deb eng ko'p ko'rilganini tushunishi kerak."""
    llm = nilufar_javobi()
    await nilufar_yasa(kontrakt, baza, llm).ishla("@climaventuz")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    # Hook matni bo'yicha tekshiramiz: raqamlar boshqa ustunlarda ham uchraydi
    # (180000 ko'rishli postning layki aynan 9000).
    birinchi = xabar.index("Ventilyator qanday tanlanadi?")
    ikkinchi = xabar.index("3 xato: kanal")
    uchinchi = xabar.index("Yangi mahsulot")
    assert birinchi < ikkinchi < uchinchi


# --- video cheklovi ochiq aytiladi -------------------------------------------


@pytest.mark.asyncio
async def test_video_cheklovi_promptda_va_javobda(kontrakt, baza):
    """API videoni bermaydi — buni model ham, foydalanuvchi ham bilsin."""
    llm = nilufar_javobi()
    k = await nilufar_yasa(kontrakt, baza, llm).ishla("@climaventuz")

    # Xabar endi bloklardan iborat (rasm + matn) — matnini yig'amiz.
    xom = llm.chaqiruvlar[0]["messages"][0]["content"]
    xabar = xom if isinstance(xom, str) else " ".join(
        b.get("text", "") for b in xom if b.get("type") == "text"
    )
    assert "videoning" in xabar.lower() or "videoni" in xabar.lower()
    assert any("video" in c.lower() for c in k.natija["cheklovlar"])
    # Promptda nimani KO'RMASLIGI aniq aytilgan bo'lishi shart: muqova
    # biriktirilsa ham ovoz va montaj ko'rinmaydi.
    tekis = " ".join(TIZIM_PROMPT.split())
    assert "OVOZ, MONTAJ va KEYINGI KADRLAR" in tekis
    assert "sen uni ko'rmading" in tekis


def test_promptda_chegaralar():
    assert "RAQAM YOZMAYSAN" in TIZIM_PROMPT
    assert "BASHORAT QILMAYSAN" in TIZIM_PROMPT
    assert "nashr qilmaysan" in TIZIM_PROMPT
    assert "Malika" in TIZIM_PROMPT


def test_kontraktda_chegaralar():
    kontrakt = kontraktlarni_yukla()["smm-analyst"]
    chegaralar = " ".join(kontrakt.chegaralar).lower()

    assert "nashr qilmaydi" in chegaralar
    assert "scraping" in chegaralar
    assert "bashorat" in chegaralar


# --- xato holatlari ----------------------------------------------------------


@pytest.mark.asyncio
async def test_tokensiz_ochiq_aytadi(kontrakt, baza):
    bosh = InstagramKlient(token="", ig_user_id="", mijoz=None)
    k = await nilufar_yasa(kontrakt, baza, SoxtaLlm([]), bosh).ishla("@climaventuz")

    assert k.holat is Holat.XATO
    assert "INSTAGRAM_TOKEN" in k.izoh


@pytest.mark.asyncio
async def test_biznes_akkaunt_emasligini_tushuntiradi(kontrakt, baza):
    """Eng ko'p uchraydigan sabab — profil shaxsiy akkaunt."""
    ig = soxta_instagram(javob_tanasi={})  # business_discovery yo'q
    k = await nilufar_yasa(kontrakt, baza, SoxtaLlm([]), ig).ishla("@shaxsiy")

    assert k.holat is Holat.XATO
    assert "Business" in k.izoh


@pytest.mark.asyncio
async def test_api_xatosi_ochiq_aytiladi(kontrakt, baza):
    ig = soxta_instagram(javob_tanasi={
        "error": {"code": 190, "message": "Invalid OAuth access token"}
    })
    k = await nilufar_yasa(kontrakt, baza, SoxtaLlm([]), ig).ishla("@climaventuz")

    assert k.holat is Holat.XATO
    assert "190" in k.izoh


@pytest.mark.asyncio
async def test_kam_post_bolsa_ishonch_pasayadi(kontrakt, baza):
    ig = soxta_instagram(javob_tanasi={
        "business_discovery": {
            "followers_count": 100, "media_count": 2,
            "media": {"data": [media(1, 500, "Salom")]},
        }
    })
    k = await nilufar_yasa(kontrakt, baza, nilufar_javobi(), ig).ishla("@yangi")

    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.ORTA
    assert any("taxminiy" in c for c in k.natija["cheklovlar"])


@pytest.mark.asyncio
async def test_postsiz_profil(kontrakt, baza):
    ig = soxta_instagram(javob_tanasi={
        "business_discovery": {"followers_count": 5, "media_count": 0,
                               "media": {"data": []}}
    })
    k = await nilufar_yasa(kontrakt, baza, SoxtaLlm([]), ig).ishla("@bosh")

    assert k.holat is Holat.XATO
    assert "post yo'q" in k.izoh


# --- ko'rinish ---------------------------------------------------------------


def test_smm_korinishi():
    matn = agent_matni("smm-analyst", {
        "profil": "climaventuz", "obunachilar": 12400, "postlar_soni": 210,
        "korilgan_postlar": 3, "video_soni": 3, "korishlar_medianasi": 45000,
        "umumiy_baho": "Ta'lim beruvchi kontent ustun.",
        "kontent_turlari": ["qo'llanma"],
        "ishlagan_postlar": [{
            "korishlar": 180000, "layklar": 9000, "sana": "2026-07-11",
            "hook": "Ventilyator qanday tanlanadi?",
            "nega_ishladi": "Savol bilan boshlangan",
            "havola": "https://instagram.com/reel/1",
        }],
        "hook_naqshlari": [{"naqsh": "savol bilan boshlash", "misol": "…", "izoh": "…"}],
        "komment_muammolari": [{"mavzu": "Narx so'ralgan", "necha_marta": 4,
                                "izoh": "Narxni ko'rsating"}],
        "tavsiyalar": ["Savol hooklarini ko'paytiring"],
        "cheklovlar": ["Video ko'rinmaydi"],
    })

    assert "@climaventuz" in matn
    assert "12 400" in matn
    assert "180 000 ko'rish" in matn
    assert "Ventilyator qanday tanlanadi?" in matn
    assert "Narx so'ralgan" in matn
    assert "4 marta" in matn


# --- video muqovasi (birinchi kadr) ------------------------------------------

# 1x1 PNG — eng kichik haqiqiy rasm.
KICHIK_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)


def _muqovali_javob():
    """Graph javobi + har postda `thumbnail_url`."""
    import copy

    javob = copy.deepcopy(GRAPH_JAVOBI)
    for i, element in enumerate(javob["business_discovery"]["media"]["data"], 1):
        element["thumbnail_url"] = f"https://cdn.test/muqova{i}.jpg"
    return javob


def soxta_instagram_muqovali(rasm_holati: int = 200, tur: str = "image/jpeg"):
    """Graph so'roviga JSON, muqova so'roviga rasm qaytaradi."""

    def ishlov(soro: httpx.Request) -> httpx.Response:
        if "cdn.test" in str(soro.url):
            return httpx.Response(
                rasm_holati, content=KICHIK_PNG, headers={"content-type": tur}
            )
        return httpx.Response(200, json=_muqovali_javob())

    return InstagramKlient(
        token="sinov-token", ig_user_id="17841400000000000",
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )


@pytest.mark.asyncio
async def test_muqovalar_modelga_rasm_sifatida_yuboriladi():
    """Hook tahlili uchun model birinchi kadrni O'ZI ko'rishi kerak."""
    klient = soxta_instagram_muqovali()
    profil = await klient.profil("climaventuz")
    assert all(p.muqova for p in profil.postlar)

    yuklangan = await klient.muqova_yukla(profil.postlar[0])
    assert yuklangan is not None
    tur, baytlar = yuklangan
    assert tur == "image/jpeg"
    assert baytlar == KICHIK_PNG


@pytest.mark.asyncio
async def test_muqova_sorovda_rasm_bloki_boladi(kontrakt, baza):
    llm = nilufar_javobi()
    await nilufar_yasa(kontrakt, baza, llm, soxta_instagram_muqovali()).ishla(
        "@climaventuz"
    )

    tana = llm.chaqiruvlar[0]["messages"][0]["content"]
    rasmlar = [b for b in tana if b.get("type") == "image"]
    assert len(rasmlar) == 3
    assert rasmlar[0]["source"]["media_type"] == "image/jpeg"
    # Matn oxirida — model avval rasmlarni ko'radi
    assert tana[-1]["type"] == "text"
    assert "BIRIKTIRILGAN MUQOVALAR" in tana[-1]["text"]


@pytest.mark.asyncio
async def test_muqova_olinmasa_tahlil_toxtamaydi(kontrakt, baza):
    """CDN javob bermasa ham profil tahlili chiqadi — faqat matnga tayanadi."""
    llm = nilufar_javobi()
    agent = nilufar_yasa(kontrakt, baza, llm, soxta_instagram_muqovali(rasm_holati=404))
    k = await agent.ishla("@climaventuz")

    assert k.holat is Holat.TUGADI
    # Rasm yo'q — xabar oddiy matn bo'lib qoladi
    tana = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert isinstance(tana, str)
    assert "muqova" in agent.ogohlantirish.lower()


@pytest.mark.asyncio
async def test_rasm_bolmagan_javob_qabul_qilinmaydi():
    """CDN HTML xato sahifasi qaytarsa, uni modelga yubormaymiz."""
    klient = soxta_instagram_muqovali(tur="text/html")
    profil = await klient.profil("climaventuz")
    assert await klient.muqova_yukla(profil.postlar[0]) is None


# --- o'z akkauntimiz: Insights -----------------------------------------------

OZ_ID = "17841400000000000"

INSIGHTS_JAVOBI = {
    "data": [
        {"name": "reach", "values": [{"value": 52000}]},
        {"name": "saved", "values": [{"value": 1840}]},
        {"name": "shares", "values": [{"value": 620}]},
        {"name": "profile_visits", "values": [{"value": 410}]},
        {"name": "follows", "values": [{"value": 95}]},
    ]
}

DEMOGRAFIYA = {
    "data": [{
        "name": "follower_demographics",
        "total_value": {"breakdowns": [{"results": [
            {"dimension_values": ["Tashkent"], "value": 8200},
            {"dimension_values": ["Samarkand"], "value": 1100},
        ]}]},
    }]
}


def soxta_oz_akkaunt(insights=None, insights_holati: int = 200):
    """`/media` postlarni, `/insights` ko'rsatkichlarni qaytaradi."""
    kuzatuv: list[httpx.Request] = []

    def ishlov(soro: httpx.Request) -> httpx.Response:
        kuzatuv.append(soro)
        yol = soro.url.path
        if yol.endswith("/insights"):
            if "follower_demographics" in str(soro.url):
                return httpx.Response(200, json=DEMOGRAFIYA)
            return httpx.Response(
                insights_holati,
                json=insights if insights is not None else INSIGHTS_JAVOBI,
            )
        if yol.endswith("/media"):
            return httpx.Response(
                200, json={"data": GRAPH_JAVOBI["business_discovery"]["media"]["data"]}
            )
        # Profil tugunining o'zi
        return httpx.Response(200, json={
            "username": "climaventuz", "followers_count": 12400, "media_count": 210,
        })

    klient = InstagramKlient(
        token="sinov-token", ig_user_id=OZ_ID,
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(ishlov)),
    )
    klient.kuzatuv = kuzatuv  # type: ignore[attr-defined]
    return klient


@pytest.mark.asyncio
async def test_oz_akkaunt_insights_bilan_olinadi():
    """Qamrov, saqlash, ulashish — faqat o'z akkauntda bo'ladi."""
    profil = await soxta_oz_akkaunt().tahlil("climaventuz")

    assert profil.ozimizniki
    post = profil.postlar[0]
    assert post.qamrov == 52000
    assert post.saqlash == 1840
    assert post.ulashish == 620
    assert post.obuna_boldi == 95
    assert post.insightsmi


@pytest.mark.asyncio
async def test_boshqa_profilda_insights_yoq():
    """Meta boshqa akkauntning qamrovini bermaydi — nol deb ko'rsatmaymiz."""
    profil = await soxta_instagram().profil("raqib")

    assert not profil.ozimizniki
    post = profil.postlar[0]
    assert post.qamrov == -1        # "yo'q", 0 emas
    assert not post.insightsmi
    assert "qamrov" not in post.qisqa()


@pytest.mark.asyncio
async def test_auditoriya_olinadi():
    profil = await soxta_oz_akkaunt().tahlil("climaventuz")
    assert profil.auditoriya.bormi
    assert profil.auditoriya.shaharlar["Tashkent"] == 8200


@pytest.mark.asyncio
async def test_insights_rad_etilsa_tahlil_toxtamaydi():
    """Ruxsat yetmasa ham post ro'yxati va sarlavhalar keladi."""
    xato = {"error": {"code": 100, "message": "(#100) metric[0] noto'g'ri"}}
    profil = await soxta_oz_akkaunt(insights=xato, insights_holati=400).tahlil(
        "climaventuz"
    )

    assert profil.postlar          # postlar baribir bor
    assert profil.insights_izohi   # sabab ochiq yozilgan
    assert not profil.postlar[0].insightsmi


@pytest.mark.asyncio
async def test_promptda_oz_akkaunt_ajratiladi(kontrakt, baza):
    llm = nilufar_javobi()
    await nilufar_yasa(kontrakt, baza, llm, soxta_oz_akkaunt()).ishla("@climaventuz")

    xom = llm.chaqiruvlar[0]["messages"][0]["content"]
    xabar = xom if isinstance(xom, str) else " ".join(
        b.get("text", "") for b in xom if b.get("type") == "text"
    )
    assert "BIZNING AKKAUNTIMIZ" in xabar
    assert "INSIGHTS:" in xabar
    assert "AUDITORIYA" in xabar


@pytest.mark.asyncio
async def test_promptda_begona_profil_ogohlantiriladi(kontrakt, baza):
    """Model "qamrov past" kabi asossiz xulosa chiqarmasligi uchun."""
    llm = nilufar_javobi()
    await nilufar_yasa(kontrakt, baza, llm, soxta_instagram()).ishla("@raqib")

    xom = llm.chaqiruvlar[0]["messages"][0]["content"]
    xabar = xom if isinstance(xom, str) else " ".join(
        b.get("text", "") for b in xom if b.get("type") == "text"
    )
    assert "BOSHQA PROFIL" in xabar
    assert "YO'Q" in xabar


# --- kommentlar: takroriy mavzular kodda sanaladi -----------------------------


@pytest.mark.asyncio
async def test_takroriy_savollar_kodda_sanaladi(kontrakt, baza):
    """"Narx 3 marta so'ralgan" — bu qaror qildiradigan raqam.

    Modelga sanashni qoldirsak, raqam taxminiy bo'ladi. Namunaviy
    ma'lumotda "Narxi qancha?" uch marta, "Narxini ayting" bir marta —
    jami 4 ta narx savoli.
    """
    llm = nilufar_javobi()
    await nilufar_yasa(kontrakt, baza, llm).ishla("@climaventuz")

    xom = llm.chaqiruvlar[0]["messages"][0]["content"]
    xabar = xom if isinstance(xom, str) else " ".join(
        b.get("text", "") for b in xom if b.get("type") == "text"
    )
    assert "KOMMENTLARDA TAKRORLANGAN MAVZULAR" in xabar
    assert "narx: 4 marta" in xabar
    assert "yetkazib berish: 1 marta" in xabar
    # Model o'zi sanamasin
    assert "o'zingdan sanama" in xabar


def test_komment_sanogi_ikki_tilni_tushunadi():
    from app.agentlar.smm_tahlilchi import SmmTahlilchi
    from integrations.instagram_klient import Komment, Post, Profil

    profil = Profil(nomi="test", postlar=[Post(id="1", kommentlar=[
        Komment(matn="Narxi qancha?"),
        Komment(matn="Сколько стоит?"),
        Komment(matn="Цена какая"),
        Komment(matn="Zo'r video"),
    ])])
    sanoq = dict((m, s) for m, s, _ in SmmTahlilchi._komment_sanogi(profil))
    assert sanoq["narx"] == 3          # o'zbekcha + ruscha
    assert "shikoyat" not in sanoq

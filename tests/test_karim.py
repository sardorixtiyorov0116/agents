"""Raqobat tahlilchisi Karim — konvert, tarix, ishonch, chegaralar."""

from __future__ import annotations

import json

import pytest

from app.agentlar.raqobat_tahlilchisi import RaqobatTahlilchisi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, matn_bloki, qidiruv_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["competitor-watch"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "karim.db")
    await b.tayyorla()
    return b


def karim_javobi(**ustama):
    malumot = {
        "hudud": "Toshkent",
        "davr": "oxirgi 1 oy",
        "topilmalar": [
            {
                "raqib": "Texnomart",
                "mavzu": "aksiya",
                "tafsilot": "Maishiy texnikaga 15% chegirma e'lon qilindi",
                "sana": "2026-07-15",
                "manba_nomi": "texnomart.uz",
                "havola": "https://texnomart.uz/aksiya",
                "ishonch": "yuqori",
                "manba_ishonchsiz": False,
            }
        ],
        "trendlar": ["Yozgi chegirma mavsumi boshlandi"],
        "xulosa": "Raqib narx bo'yicha agressiv siyosatga o'tdi.",
        "topilmaganlar": [],
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
async def test_normal_holat(kontrakt, baza):
    llm = soxta(karim_javobi(), [{"title": "texnomart.uz", "url": "https://texnomart.uz/a"}])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await karim.ishla("Texnomart aksiyalarini oxirgi oyda kuzat")

    assert k.kim == "competitor-watch"
    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.YUQORI
    assert k.tasdiq_kerak is False
    assert k.natija["topilmalar"][0]["raqib"] == "Texnomart"
    # Kontrakt talabi: tahliliy xulosa bo'ladi
    assert k.natija["xulosa"]
    # Manba majburiy: topilma havolasi + qidiruv natijasi
    assert "https://texnomart.uz/aksiya" in {m.havola for m in k.manba}

    soro = llm.chaqiruvlar[0]
    assert soro["tools"][0]["type"] == "web_search_20260209"
    assert soro["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_topilmasa_toqib_chiqarmaydi(kontrakt, baza):
    llm = soxta(
        karim_javobi(
            topilmalar=[],
            trendlar=[],
            xulosa="",
            topilmaganlar=["Noma'lum raqib Z"],
        )
    )
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await karim.ishla("Noma'lum raqib Z ni kuzat")

    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.PAST
    assert k.natija["topilmaganlar"] == ["Noma'lum raqib Z"]
    assert k.natija["topilmalar"] == []
    assert k.manba, "manba har doim ko'rsatiladi"
    assert "topilmadi" in k.izoh


@pytest.mark.asyncio
async def test_ishonchsiz_va_sanasiz_manba_ishonchni_pasaytiradi(kontrakt, baza):
    llm = soxta(
        karim_javobi(
            topilmalar=[
                {
                    "raqib": "Raqib A",
                    "mavzu": "yangilik",
                    "tafsilot": "Yangi filial ochilgani haqida mish-mish",
                    "sana": None,
                    "manba_nomi": "forum",
                    "havola": "https://forum.example/1",
                    "ishonch": "yuqori",
                    "manba_ishonchsiz": True,
                }
            ]
        )
    )
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await karim.ishla("Raqib A yangiliklari")

    assert k.ishonch is Ishonch.ORTA
    assert "ishonchsiz" in k.izoh


@pytest.mark.asyncio
async def test_topilmalar_tarixga_yoziladi(kontrakt, baza):
    llm = soxta(karim_javobi())
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await karim.ishla("Texnomart aksiyalari")

    import sqlite3

    with sqlite3.connect(baza.yol) as u:
        qatorlar = u.execute("SELECT raqib, mavzu FROM raqib_topilmalari").fetchall()
    assert qatorlar == [("Texnomart", "aksiya")]


@pytest.mark.asyncio
async def test_chegara_marketing_rejasi_promptda_taqiqlangan(kontrakt):
    """Kontrakt chegarasi promptga chiqishi kerak — Karim kampaniya tuzmaydi."""
    from app.agentlar.raqobat_tahlilchisi import TIZIM_PROMPT

    assert "Marketolog Malika" in TIZIM_PROMPT
    assert "Maxfiy ma'lumot" in TIZIM_PROMPT or "maxfiy ma'lumot" in TIZIM_PROMPT


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("raqiblar hozircha tinch")])])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await karim.ishla("Raqiblarni kuzat")
    assert k.holat is Holat.XATO
    assert k.ishonch is Ishonch.PAST


# --- tarix: takrorlamaslik va o'zgarishni ko'rish -----------------------------


@pytest.mark.asyncio
async def test_oldingi_topilmalar_promptga_qoshiladi(kontrakt, baza):
    """Tarixsiz Karim o'tgan oydagi gapni yana aytadi.

    Eng qimmatli xulosa O'ZGARISHDA: "narxni ko'targan", "yangi model".
    Buni ko'rish uchun eskisi promptda bo'lishi shart.
    """
    await baza.topilma_yoz({
        "raqib": "Vento", "mavzu": "narx",
        "tafsilot": "VK-250 narxi 1 200 000 so'm",
        "manba": "vento.uz", "havola": "https://vento.uz",
    })

    llm = soxta(karim_javobi())
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await karim.ishla("Vento narxlarini ko'r")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "OLDINGI TOPILMALAR" in xabar
    assert "VK-250 narxi 1 200 000" in xabar
    # Model tarixdan yangi fakt to'qimasligi aniq aytilgan bo'lsin
    assert "YANGI FAKT to'qima" in xabar


@pytest.mark.asyncio
async def test_tarix_bosh_bolsa_prompt_ifloslanmaydi(kontrakt, baza):
    llm = soxta(karim_javobi())
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await karim.ishla("raqiblarni ko'r")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "OLDINGI TOPILMALAR" not in xabar


# --- javob uzunligi chegarasi -------------------------------------------------


def test_topilmalar_soni_cheklangan():
    """Vaqtning deyarli hammasi JAVOB YOZISHGA ketadi (5 000+ token).

    Chegarasiz Karim 25 ta topilma yozadi, ularning ko'pi mayda-chuyda.
    Menejer baribir yuqoridagilarini o'qiydi.
    """
    from app.agentlar.raqobat_tahlilchisi import MAKS_TOPILMA, KarimNatija

    chegara = KarimNatija.model_fields["topilmalar"].metadata
    assert MAKS_TOPILMA == 10
    assert any(getattr(m, "max_length", None) == MAKS_TOPILMA for m in chegara), (
        "topilmalar ro'yxatiga max_length qo'yilmagan"
    )


def test_promptda_ham_chegara_bor():
    """Sxema chegarasi kifoya emas: model baribir uzun yozib, keyin kesiladi.

    Tejash uchun chegara PROMPTDA bo'lishi kerak — model kamroq yozsin.
    """
    from app.agentlar.raqobat_tahlilchisi import TIZIM_PROMPT

    tekis = " ".join(TIZIM_PROMPT.split())
    assert "ENG KO'PI 10 TA TOPILMA" in tekis


def test_veb_qidiruv_byudjeti_cheklangan():
    """Vaqt manba soniga chiziqli bog'liq — byudjet o'sib ketmasin.

    O'lchov (9 ta yurish izi): har manba ~1.2 s. 20 ta qidiruv 154 tagacha
    manba bergan va 265 s turgan, javob esa 10 ta topilma bilan cheklangan.
    """
    from app.agentlar.raqobat_tahlilchisi import MAKS_TOPILMA, VEB_MAKS

    assert VEB_MAKS <= 10, "veb qidiruv byudjeti o'sib ketdi — vaqtni tekshiring"
    assert MAKS_TOPILMA <= 10


# --- veb qidiruv yo'qligi JIMGINA o'tmasin (2026-09-08) ----------------------


class VebsizLlm(SoxtaLlm):
    """Veb qidiruvni qo'llamaydigan provayder (Gemini, lokal model)."""

    VEB_QIDIRUV = False


@pytest.mark.asyncio
async def test_vebsiz_provayderda_TOOLS_yuborilmaydi(kontrakt, baza):
    """Tashlanadigan narsani yuborishning ma'nosi yo'q.

    Gemini `tools` ni jimgina tashlaydi (`app/gemini.py`). Uni yuborish
    hech nima bermaydi, lekin agent qidirdim deb o'ylaydi.
    """
    llm = VebsizLlm([javob([matn_bloki(json.dumps(karim_javobi()))])])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await karim.ishla("Texnomart aksiyalari")

    assert "tools" not in llm.chaqiruvlar[0]


@pytest.mark.asyncio
async def test_vebsiz_provayderda_MENEJER_ogohlantiriladi(kontrakt, baza):
    """JIM XATO EDI: javob to'liq ko'rinardi, lekin tashqi manba yo'q.

    Karim ishining asosi tashqi ma'lumot. Veb qidiruv o'chganda javob
    faqat profildagi ro'yxatga tayanadi — menejer buni bilmasa,
    to'liq tahlil deb qabul qiladi.
    """
    llm = VebsizLlm([javob([matn_bloki(json.dumps(karim_javobi()))])])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await karim.ishla("Texnomart aksiyalari")

    assert "veb qidiruv ishlamadi" in k.izoh.lower(), k.izoh


@pytest.mark.asyncio
async def test_vebsiz_provayderda_MODELGA_ham_aytiladi(kontrakt, baza):
    """Model izlab topgandek yozib qo'ymasin."""
    llm = VebsizLlm([javob([matn_bloki(json.dumps(karim_javobi()))])])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    await karim.ishla("Texnomart aksiyalari")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "VEB QIDIRUV HOZIR ISHLAMAYDI" in xabar


@pytest.mark.asyncio
async def test_vebli_provayderda_ogohlantirish_YO_Q(kontrakt, baza):
    """Anthropic'da qidiruv ishlaydi — ortiqcha ogohlantirish bermaymiz."""
    llm = soxta(karim_javobi(), [{"title": "t", "url": "https://t.uz"}])
    karim = RaqobatTahlilchisi(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await karim.ishla("Texnomart aksiyalari")

    assert "veb qidiruv ishlamadi" not in k.izoh.lower()
    assert "tools" in llm.chaqiruvlar[0]


def test_zanjir_veb_qidiruv_imkoniyatini_biladi():
    """Zanjir butunlay vebsiz bo'lsa — agent buni oldindan bilsin."""
    from app.zanjir import ZanjirLlm

    faqat_bulut = ZanjirLlm(["gemini-3.5-flash", "ollama:qwen3:8b"], lambda m: None)
    aralash = ZanjirLlm(["gemini-3.5-flash", "claude-haiku-4-5"], lambda m: None)

    assert faqat_bulut.VEB_QIDIRUV is False
    assert aralash.VEB_QIDIRUV is True


# --- ichki tahlil hujjatlari (market RAG, 2026-09-08) ------------------------


@pytest.mark.asyncio
async def test_ichki_tahlil_hujjatlari_promptga_tushadi(kontrakt, baza):
    """`market` papkasi biriktirilgan edi, lekin hech qachon so'ralmasdi.

    Profil faqat 8 ta NOM beradi. `market` da esa har raqobatchi
    bo'yicha dosye, bozor hajmi va segment tahlili bor — 74 bo'lak.
    Veb qidiruv Gemini'da ishlamagani uchun Karim amalda 8 ta nom
    bilan qolib ketardi.
    """
    from .soxta import soxta_bilim

    llm = soxta(karim_javobi())
    karim = RaqobatTahlilchisi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        qidiruv_manbasi=soxta_bilim(
            ("Ventsystems, Ma'lumot",
             "Jihozventning sobiq sotuv va konstruktor xodimlari tuzgan."),
        ),
    )
    await karim.ishla("Ventsystems kim")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "ICHKI TAHLIL HUJJATLARI" in xabar
    assert "sobiq sotuv va konstruktor" in xabar


@pytest.mark.asyncio
async def test_hujjat_topilmasa_MODELGA_aytiladi(kontrakt, baza):
    """Jim qolish xavfli: model hujjatga tayangandek yozib qo'yadi."""
    from .soxta import soxta_bilim

    llm = soxta(karim_javobi())
    karim = RaqobatTahlilchisi(
        kontrakt=kontrakt, llm=llm, baza=baza, qidiruv_manbasi=soxta_bilim(),
    )
    await karim.ishla("Ventsystems kim")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "hujjat topilmadi" in xabar


def test_promptda_ICHKI_hujjat_manbasi_tavsiflangan():
    """Model qaysi manbadan olganini belgilashi kerak."""
    from app.agentlar.raqobat_tahlilchisi import TIZIM_PROMPT

    assert "ICHKI TAHLIL HUJJATLARI" in TIZIM_PROMPT
    assert "ichki_manba" in TIZIM_PROMPT
    # Eskirish xavfi ochiq aytilsin — hujjatdagi raqam bugungi emas.
    assert "ESKI" in TIZIM_PROMPT

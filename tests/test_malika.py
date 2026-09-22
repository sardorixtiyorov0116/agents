"""Marketolog Malika — qoralama, chegaralar, yetishmagan ma'lumot."""

from __future__ import annotations

import json

import pytest

from app.agentlar.marketolog import Marketolog
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch

from .soxta import SoxtaLlm, javob, matn_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["marketing"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "malika.db")
    await b.tayyorla()
    return b


def malika_javobi(**ustama):
    malumot = {
        "kampaniya_nomi": "Yozgi salqinlik",
        "auditoriya": "Toshkentdagi 25-45 yoshli oila boshliqlari",
        "goya": "Raqib chegirmasiga xizmat sifati bilan javob berish",
        "asos": ["Karim: Texnomart 15% chegirma e'lon qildi (2026-07-15)"],
        "variantlar": [
            {
                "kanal": "Telegram",
                "ohang": "ishonchli, sokin",
                "matn": "Chegirma o'tadi — xizmat qoladi. Bepul o'rnatish.",
            }
        ],
        "tavsiya_kanal": "Telegram",
        "tavsiya_vaqt": "Iyul oxiri",
        "sorash_kerak": [],
        "asossiz_dovolar": [],
    }
    malumot.update(ustama)
    return malumot


def soxta(malumot):
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


@pytest.mark.asyncio
async def test_qoralama_tayyorlanadi(kontrakt, baza):
    llm = soxta(malika_javobi())
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await malika.ishla("Yozgi kampaniya taklif qil")

    assert k.kim == "marketing"
    assert k.holat is Holat.TUGADI
    assert k.natija["variantlar"][0]["kanal"] == "Telegram"
    assert k.manba, "manba majburiy"
    # Nashr qilinmagani ochiq aytiladi
    assert "QORALAMA" in k.izoh


@pytest.mark.asyncio
async def test_veb_qidiruv_ishlatmaydi(kontrakt, baza):
    """Kontrakt: raqib ma'lumotini o'zi yig'maydi — demak veb vositasi yo'q."""
    llm = soxta(malika_javobi())
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    await malika.ishla("Kampaniya taklif qil")

    assert "tools" not in llm.chaqiruvlar[0]


@pytest.mark.asyncio
async def test_malumot_yetishmasa_soraydi(kontrakt, baza):
    llm = soxta(
        malika_javobi(
            asos=[],
            variantlar=[],
            sorash_kerak=["mahsulot xususiyatlari", "byudjet doirasi"],
        )
    )
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await malika.ishla("Yangi mahsulotga reklama yoz")

    assert k.holat is Holat.TUGADI
    assert k.ishonch is Ishonch.PAST
    assert "ma'lumot yetishmaydi" in k.izoh
    assert k.natija["sorash_kerak"] == ["mahsulot xususiyatlari", "byudjet doirasi"]


@pytest.mark.asyncio
async def test_asossiz_dovo_yozilmaydi(kontrakt, baza):
    llm = soxta(
        malika_javobi(
            asossiz_dovolar=["'eng arzon' — narx taqqoslash ma'lumoti yo'q"],
        )
    )
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await malika.ishla("'Eng arzon' deb reklama yoz")

    assert k.natija["asossiz_dovolar"]
    assert "asossiz da'vo yozilmadi" in k.izoh


@pytest.mark.asyncio
async def test_zanjirdan_kelgan_kontekst_manba_boladi(kontrakt, baza):
    llm = soxta(malika_javobi())
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await malika.ishla(
        "Karim topilmalari asosida kampaniya tuz",
        {"oldingi_agent": "competitor-watch", "oldingi_natija": {"topilmalar": [{"raqib": "X"}]}},
    )

    assert k.manba[0].nom == "competitor-watch konverti"
    assert k.ishonch is Ishonch.YUQORI
    # Kontekst promptga tushgan bo'lishi kerak
    assert "competitor-watch" in llm.chaqiruvlar[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("kampaniya g'oyasi: yaxshi bo'ladi")])])
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await malika.ishla("Kampaniya")
    assert k.holat is Holat.XATO


# --- raqib konteksti: yakka chaqirilganda ham bozorni ko'radi ------------------


@pytest.mark.asyncio
async def test_yakka_chaqirilganda_raqib_tarixi_beriladi(kontrakt, baza):
    """Malika yolg'iz ishlaganda bozor konteksti umuman yo'q edi."""
    await baza.topilma_yoz({
        "raqib": "Vento", "mavzu": "aksiya",
        "tafsilot": "Kanal ventilyatorlariga 15% chegirma e'lon qilgan",
        "manba": "vento.uz", "havola": "https://vento.uz",
    })

    llm = soxta(malika_javobi())
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    await malika.ishla("Kanal ventilyatorlari uchun kampaniya taklif qil")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "RAQOBATCHILAR HAQIDA MA'LUM" in xabar
    assert "15% chegirma" in xabar
    # Kontrakt chegarasi promptda ham takrorlanadi
    assert "NOMLAB QORALAMAYSAN" in xabar


@pytest.mark.asyncio
async def test_zanjirda_tarix_takrorlanmaydi(kontrakt, baza):
    """Karim zanjirda oldin ishlagan bo'lsa, uning natijasi allaqachon bor."""
    await baza.topilma_yoz({
        "raqib": "Vento", "mavzu": "aksiya", "tafsilot": "chegirma",
    })

    llm = soxta(malika_javobi())
    malika = Marketolog(kontrakt=kontrakt, llm=llm, baza=baza)
    await malika.ishla("kampaniya", {"oldingi_natija": {"topilmalar": []}})

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "RAQOBATCHILAR HAQIDA MA'LUM" not in xabar


# --- brend hujjatlari (marketing RAG, 2026-09-08) ---------------------------


@pytest.mark.asyncio
async def test_brend_hujjatlari_promptga_tushadi(kontrakt, baza):
    """`marketing` papkasi biriktirilgan edi, lekin so'ralmasdi.

    Malikaning 1-qoidasi — "faktsiz da'vo yozma". Pozitsiyalash (STP),
    brend-arxetip va kommunikatsiya strategiyasi hujjatlarisiz unda
    tasdiq manbasi yo'q edi va matn umumiy chiqardi.
    """
    from .soxta import soxta_bilim

    llm = soxta(malika_javobi())
    malika = Marketolog(
        kontrakt=kontrakt, llm=llm, baza=baza,
        qidiruv_manbasi=soxta_bilim(
            ("Pozitsiyalash va STP, Asosiy segment",
             "Asosiy segment — sanoat obyektlari, ohang: ishonchli muhandis."),
        ),
    )
    await malika.ishla("Yangi rekuperator uchun kampaniya")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "BREND VA POZITSIYALASH HUJJATLARI" in xabar
    assert "ishonchli muhandis" in xabar


@pytest.mark.asyncio
async def test_brend_hujjati_MANBADA_korinadi(kontrakt, baza):
    """Qaysi hujjatga tayangani javobda ko'rinishi kerak."""
    from .soxta import soxta_bilim

    llm = soxta(malika_javobi())
    malika = Marketolog(
        kontrakt=kontrakt, llm=llm, baza=baza,
        qidiruv_manbasi=soxta_bilim(
            ("Pozitsiyalash va STP, Asosiy segment", "Sanoat obyektlari."),
        ),
    )
    k = await malika.ishla("Yangi rekuperator uchun kampaniya")

    nomlar = " ".join(m.nom for m in k.manba)
    assert "Pozitsiyalash va STP" in nomlar, nomlar
    assert any(m.tur == "bilim" for m in k.manba)


@pytest.mark.asyncio
async def test_hujjat_yoq_bolsa_OHANG_oylab_topilmaydi(kontrakt, baza):
    """Jim qolish xavfli: model brend ohangini o'zi to'qib qo'yadi."""
    from .soxta import soxta_bilim

    llm = soxta(malika_javobi())
    malika = Marketolog(
        kontrakt=kontrakt, llm=llm, baza=baza, qidiruv_manbasi=soxta_bilim(),
    )
    await malika.ishla("Yangi rekuperator uchun kampaniya")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "hujjat topilmadi" in xabar
    assert "o'zingdan o'ylab topma" in xabar

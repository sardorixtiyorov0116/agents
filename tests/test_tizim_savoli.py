"""Tizim haqidagi savollar va konstruktiv rad etish.

Ikki bo'shliq yopiladi:
  - "Malika nima qiladi?" — router o'zi javob beradi, agent chaqirilmaydi;
  - "savdo rejasi tuzib ber" — quruq "agent yo'q" emas, konstruktiv taklif.
"""

from __future__ import annotations

import pytest

from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat
from app.orkestr import Orkestr
from app.router import Router
from presenter import javob_matni, konvert_matni

from .soxta import SoxtaLlm, json_javob


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "meta.db")
    await b.tayyorla()
    return b


def router_javobi(**ustama):
    malumot = {
        "niyat": "test",
        "vazifa_soni": 0,
        "qadamlar": [],
        "mos_agent_yoq": False,
        "aniqlik_kerak": False,
        "savollar": [],
        "tizim_savoli": False,
        "javob": "",
        "taklif": "",
        "izoh": "",
    }
    malumot.update(ustama)
    return json_javob(malumot)


TIZIM_JAVOBI = (
    "Marketolog Malika kommunikatsiya va kontent bilan shug'ullanadi.\n"
    "Qila oladi: kampaniya g'oyasi, reklama matni, kanal tavsiyasi.\n"
    "Qilmaydi: nashr etmaydi, byudjet sarflamaydi, savdo rejasi tuzmaydi.\n"
    "Masalan shunday so'rov berishingiz mumkin: «Yangi ventilyator uchun "
    "Telegram posti tayyorla»."
)


# --- tizim savoli ------------------------------------------------------------


# Tizim savolida router IKKI marta chaqiriladi: birinchisi qisqa
# kontraktlar bilan (arzon, faqat "bu tizim savolimi?" ni aniqlaydi),
# ikkinchisi to'liq kontraktlar bilan (javobning o'zi shundan yoziladi).
def tizim_javoblari():
    return [
        router_javobi(tizim_savoli=True, javob="qisqa"),
        router_javobi(tizim_savoli=True, javob=TIZIM_JAVOBI),
    ]


@pytest.mark.asyncio
async def test_tizim_savolida_agent_chaqirilmaydi(kontraktlar, baza):
    """Agent chaqirilsa test yiqiladi (soxta LLM javoblari tugaydi)."""
    llm = SoxtaLlm(tizim_javoblari())
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Malika nima qiladi?")

    assert natija.qadamlar == []
    assert natija.yakuniy.holat is Holat.TUGADI
    assert natija.yakuniy.kim == "router"
    assert natija.yakuniy.natija["javob"] == TIZIM_JAVOBI
    # Manba — kontraktlar (o'ylab topilmagan)
    assert natija.yakuniy.manba[0].tur == "kontrakt"


@pytest.mark.asyncio
async def test_tizim_javobi_toza_matn_bolib_chiqadi(kontraktlar, baza):
    llm = SoxtaLlm(tizim_javoblari())
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Malika nima qiladi?")

    matn = javob_matni(natija, {"router": "Router"})
    assert matn == TIZIM_JAVOBI
    # Texnik bezaklar yo'q
    assert "Manba:" not in matn
    assert "✅" not in matn


@pytest.mark.asyncio
async def test_javobsiz_tizim_savoli_eiborga_olinmaydi(kontraktlar):
    """"Tizim savoli" deyilsa-yu javob berilmasa — oddiy yo'l davom etadi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                tizim_savoli=True,
                javob="   ",
                qadamlar=[
                    {
                        "agent": "price-monitor",
                        "vazifa": "narx",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    }
                ],
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("narx top")

    assert reja.tizim_savoli is False
    assert [q.agent for q in reja.qadamlar] == ["price-monitor"]


@pytest.mark.asyncio
async def test_promptda_tizim_savoli_qoidalari(kontraktlar):
    llm = SoxtaLlm([router_javobi()])
    await Router(llm, kontraktlar).reja_tuz("nimadir")

    tizim = "\n".join(b["text"] for b in llm.chaqiruvlar[0]["system"])
    assert "TIZIM SAVOLI" in tizim
    assert "KONSTRUKTIV RAD ETISH" in tizim
    assert "PARCHALASH" in tizim
    # Quruq ro'yxat taqiqlangan
    assert "Quruq ro'yxat berma" in tizim


# --- konstruktiv rad etish ---------------------------------------------------

TAKLIF = (
    "To'liq savdo rejasi uchun alohida agent yo'q, lekin quyidagilarni "
    "tayyorlay olaman: bozor tahlili (Karim), o'tgan savdo raqamlari (Doston), "
    "kampaniya rejasi (Malika). Masalan: «Raqiblarning kanal strategiyasini "
    "ko'rib chiq» deb so'rasangiz bo'ladi."
)


@pytest.mark.asyncio
async def test_rad_etishda_taklif_asosiy_javob_boladi(kontraktlar, baza):
    llm = SoxtaLlm(
        [
            router_javobi(
                mos_agent_yoq=True,
                izoh="Bunday agent yo'q",
                taklif=TAKLIF,
            )
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Ofis uchun mebel tanla")

    assert natija.yakuniy.holat is Holat.MOS_AGENT_YOQ
    assert natija.yakuniy.natija["taklif"] == TAKLIF

    matn = konvert_matni(natija.yakuniy)
    # Taklif ko'rsatiladi, quruq "agent yo'q" emas
    assert matn == TAKLIF
    assert "Bunday agent yo'q" not in matn


@pytest.mark.asyncio
async def test_taklifsiz_rad_etishda_ham_sabab_aytiladi(kontraktlar, baza):
    llm = SoxtaLlm([router_javobi(mos_agent_yoq=True, izoh="Pizza buyurtma qilib bo'lmaydi")])
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Pizza buyurtma qil")

    matn = konvert_matni(natija.yakuniy)
    assert "Pizza buyurtma qilib bo'lmaydi" in matn
    # Foydalanuvchi nima qilish mumkinligini biladi
    assert "agent yo'q" in matn


@pytest.mark.asyncio
async def test_parchalangan_zanjir_rad_etilmaydi(kontraktlar, baza):
    """Router zanjir tuza olsa, mos_agent_yoq qaytarmaydi."""
    llm = SoxtaLlm(
        [
            router_javobi(
                niyat="savdo rejasi",
                vazifa_soni=3,
                qadamlar=[
                    {
                        "agent": "competitor-watch",
                        "vazifa": "bozor tahlili",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                    {
                        "agent": "data-query",
                        "vazifa": "o'tgan savdo",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                    {
                        "agent": "sales-strategy",
                        "vazifa": "savdo rejasi",
                        "tasdiq_kerak": False,
                        "tasdiq_sababi": "",
                    },
                ],
            )
        ]
    )
    reja = await Router(llm, kontraktlar).reja_tuz("Savdo rejasi tuzib ber")

    assert reja.mos_agent_yoq is False
    assert [q.agent for q in reja.qadamlar] == [
        "competitor-watch",
        "data-query",
        "sales-strategy",
    ]


# --- Bekzod kontrakti --------------------------------------------------------


def test_bekzod_kontrakti_va_chegaralari(kontraktlar):
    bekzod = kontraktlar["sales-strategy"]

    assert bekzod.korinish == "Savdo strategi Bekzod"
    assert bekzod.xavf.value == "orta"
    assert bekzod.amalga_oshirilgan

    chegaralar = " ".join(bekzod.chegaralar).lower()
    assert "narx belgilamaydi" in chegaralar
    assert "chegirma" in chegaralar
    assert "yubormaydi" in chegaralar
    assert "reklama matni" in chegaralar  # Malika bilan chegara


def test_malika_bekzod_chegarasi_aniq(kontraktlar):
    """Chegara chalkashmaslik uchun — ikkalasi bir-birini ko'rsatadi."""
    malika = " ".join(kontraktlar["marketing"].chegaralar).lower()
    assert "savdo rejasi" in malika and "bekzod" in malika

    bekzod = " ".join(kontraktlar["sales-strategy"].chegaralar).lower()
    assert "malika" in bekzod

    # Malikaning maqsadi endi aniq: kommunikatsiya va kontent
    assert "kommunikatsiya" in kontraktlar["marketing"].maqsad.lower()


# --- token tejash: router qisqa kontraktlarni ko'radi -------------------------


@pytest.mark.asyncio
async def test_oddiy_sorovda_qisqa_kontraktlar_yuboriladi(kontraktlar):
    """Router uchun agent tanlashga maqsad + chegaralar yetarli.

    `input`, `output`, `ruxsatlar`, `xato_holati` — agentning O'Z ishini
    tavsiflaydi, tanlashga ta'sir qilmaydi. Ular har so'rovda ~4 200
    ortiqcha token edi.
    """
    llm = SoxtaLlm([router_javobi()])
    await Router(llm, kontraktlar).reja_tuz("narx top")

    assert len(llm.chaqiruvlar) == 1, "oddiy so'rovda bitta chaqiruv bo'lsin"
    tizim = "\n".join(b["text"] for b in llm.chaqiruvlar[0]["system"])

    # Tanlash uchun keraklisi bor
    assert "QILMAYDI (chegaralar)" in tizim
    assert "Inson tasdig'i qachon" in tizim
    # Ortiqchasi yo'q
    assert "Ruxsatlar:" not in tizim
    assert "Xato holati:" not in tizim
    assert "Input:" not in tizim


@pytest.mark.asyncio
async def test_tizim_savolida_toliq_kontrakt_yuboriladi(kontraktlar):
    """Tizim savoliga javob aynan kontrakt tafsilotidan yoziladi."""
    llm = SoxtaLlm(tizim_javoblari())
    reja = await Router(llm, kontraktlar).reja_tuz("Malika nima qiladi?")

    assert len(llm.chaqiruvlar) == 2
    ikkinchi = "\n".join(b["text"] for b in llm.chaqiruvlar[1]["system"])
    assert "Ruxsatlar:" in ikkinchi
    assert "Xato holati:" in ikkinchi
    # Yakuniy javob ikkinchi chaqiruvdan
    assert reja.javob == TIZIM_JAVOBI


@pytest.mark.asyncio
async def test_javobsiz_tizim_savolida_ikkinchi_chaqiruv_bolmaydi(kontraktlar):
    """Bekor qilinadigan javob uchun pul sarflamaymiz."""
    llm = SoxtaLlm([
        router_javobi(
            tizim_savoli=True, javob="   ",
            qadamlar=[{"agent": "price-monitor", "vazifa": "narx",
                       "tasdiq_kerak": False, "tasdiq_sababi": ""}],
        )
    ])
    await Router(llm, kontraktlar).reja_tuz("narx top")

    assert len(llm.chaqiruvlar) == 1


def test_qisqa_matnda_muhim_qismlar_yoqolmaydi(kontraktlar):
    """Har kontraktning ajratuvchi qismi qisqa shaklda ham qolsin."""
    for rol, k in kontraktlar.items():
        qisqa = k.qisqa_matn()
        assert rol in qisqa
        assert k.maqsad.strip()[:40] in qisqa
        for chegara in k.chegaralar:
            assert chegara in qisqa, f"{rol}: chegara yo'qoldi"
        for tasdiq in k.tasdiq_qachon:
            assert tasdiq in qisqa, f"{rol}: tasdiq sharti yo'qoldi"


def test_qisqa_matn_toliqdan_kichik(kontraktlar):
    from app.kontraktlar import kontraktlar_matni

    toliq = len(kontraktlar_matni(kontraktlar))
    qisqa = len(kontraktlar_matni(kontraktlar, qisqa=True))

    assert qisqa < toliq * 0.65, f"tejash kutilganidan kam: {qisqa}/{toliq}"

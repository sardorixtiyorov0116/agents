"""Savdo koordinatori Aziza — `kp-tracker`.

Asosiy xavf: agent KP holatini o'zboshimchalik bilan o'zgartirib qo'yishi.
Shuning uchun bu yerda ikkita narsa qat'iy tekshiriladi:
  - holat FAQAT tasdiqdan keyin yoziladi;
  - mavjud bo'lmagan KP raqami rad etiladi.
"""

from __future__ import annotations

import json

import pytest

from app.agentlar.kp_kuzatuvchi import KUTISH_KUNI, KpKuzatuvchi
from app.baza import Baza
from app.konvert import Holat
from app.kontraktlar import kontraktlarni_yukla

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_api, soxta_bilim


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["kp-tracker"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "aziza.db")
    await b.tayyorla()
    return b


def aziza_javobi(**maydonlar):
    tana = {
        "xulosa": "Uchta KP javobsiz.",
        "etibor_kerak": [],
        "tavsiyalar": [],
        "yangi_holat": "",
        "nishon_raqam": "",
        "holat_izohi": "",
    }
    tana.update(maydonlar)
    return SoxtaLlm([javob([matn_bloki(json.dumps(tana, ensure_ascii=False))])])


def aziza_yasa(kontrakt, baza, llm):
    return KpKuzatuvchi(
        kontrakt=kontrakt, llm=llm, baza=baza,
        api=soxta_api(), qidiruv_manbasi=soxta_bilim(),
    )


async def _kp_qoy(baza, raqam="12969/8", mijoz="Tolibjon MCHJ", summa=5_000_000):
    await baza.kp_kuzatuv_yoz(raqam, mijoz, summa)


# --- bo'sh holat -------------------------------------------------------------


@pytest.mark.asyncio
async def test_kp_bolmasa_ochiq_aytadi(kontrakt, baza):
    """Bo'sh ro'yxatni "hammasi yaxshi" deb ko'rsatib bo'lmaydi."""
    k = await aziza_yasa(kontrakt, baza, aziza_javobi()).ishla("KP lar qalay?")

    assert k.holat is Holat.TUGADI
    assert k.natija["jami"] == 0
    assert "kuzatuvga tushmagan" in k.izoh.lower()


# --- ko'rsatish --------------------------------------------------------------


@pytest.mark.asyncio
async def test_royxat_va_konversiya_bazadan_olinadi(kontrakt, baza):
    """Raqamlar model javobidan EMAS, bazadan chiqadi."""
    await _kp_qoy(baza, "1/1", "A", 1_000_000)
    await _kp_qoy(baza, "2/2", "B", 3_000_000)
    await baza.kp_holat_yoz("2/2", "shartnoma", "imzolandi")

    k = await aziza_yasa(kontrakt, baza, aziza_javobi()).ishla("xulosa ber")

    assert k.natija["jami"] == 2
    assert k.natija["konversiya"] == 50.0
    assert k.natija["shartnoma_summasi"] == 3_000_000
    assert k.natija["holatlar"]["shartnoma"] == 1


@pytest.mark.asyncio
async def test_javobsiz_kp_ajratiladi(kontrakt, baza):
    """Kunlar KODDA sanaladi — model taxmin qilmaydi."""
    import sqlite3
    from datetime import UTC, datetime, timedelta

    await _kp_qoy(baza, "3/3", "Eski mijoz")
    eski = (datetime.now(UTC) - timedelta(days=KUTISH_KUNI + 4)).isoformat()
    with sqlite3.connect(baza.yol) as u:
        u.execute("UPDATE kp_kuzatuv SET yaratildi = ? WHERE raqam = '3/3'", (eski,))

    llm = aziza_javobi(etibor_kerak=[{"raqam": "3/3", "nega": "javob yo'q"}])
    k = await aziza_yasa(kontrakt, baza, llm).ishla("javobsizlarni ko'rsat")

    assert k.natija["javobsiz_soni"] == 1
    assert k.natija["etibor_kerak"][0]["raqam"] == "3/3"
    assert k.natija["etibor_kerak"][0]["kun"] >= KUTISH_KUNI


@pytest.mark.asyncio
async def test_oylab_topilgan_kp_otkazilmaydi(kontrakt, baza):
    """Model mavjud bo'lmagan raqam yozsa, u javobga tushmaydi."""
    await _kp_qoy(baza, "4/4")
    llm = aziza_javobi(etibor_kerak=[
        {"raqam": "4/4", "nega": "haqiqiy"},
        {"raqam": "999/9", "nega": "o'ylab topilgan"},
    ])

    k = await aziza_yasa(kontrakt, baza, llm).ishla("ko'rsat")

    raqamlar = [e["raqam"] for e in k.natija["etibor_kerak"]]
    assert raqamlar == ["4/4"]


# --- holat o'zgartirish: TASDIQSIZ YOZILMAYDI --------------------------------


@pytest.mark.asyncio
async def test_holat_tasdiqsiz_ozgarmaydi(kontrakt, baza):
    """Eng muhim test: agent o'zi yozib qo'ymasin."""
    await _kp_qoy(baza, "5/5", "AGMK")
    llm = aziza_javobi(yangi_holat="shartnoma", nishon_raqam="5/5",
                       holat_izohi="imzolandi")

    k = await aziza_yasa(kontrakt, baza, llm).ishla("AGMK shartnoma tuzdi")

    assert k.holat is Holat.TASDIQ_KUTILMOQDA
    assert k.natija["taklif_holat"]["raqam"] == "5/5"
    # Baza O'ZGARMAGAN bo'lishi shart
    yozuv = (await baza.kp_kuzatuv())[0]
    assert yozuv["holat"] == "yuborildi"


@pytest.mark.asyncio
async def test_tasdiqdan_keyin_yoziladi(kontrakt, baza):
    await _kp_qoy(baza, "6/6", "AGMK", 9_000_000)
    agent = aziza_yasa(kontrakt, baza, aziza_javobi())

    k = await agent.ishla("", {
        "tasdiqlandi": True,
        "tasdiqlangan_holat": {
            "raqam": "6/6", "holat": "shartnoma", "izoh": "imzolandi",
        },
    })

    assert k.holat is Holat.TUGADI
    yozuv = (await baza.kp_kuzatuv())[0]
    assert yozuv["holat"] == "shartnoma"
    assert yozuv["izoh"] == "imzolandi"
    assert k.natija["shartnoma_summasi"] == 9_000_000


@pytest.mark.asyncio
async def test_notogri_raqam_rad_etiladi(kontrakt, baza):
    await _kp_qoy(baza, "7/7")
    llm = aziza_javobi(yangi_holat="shartnoma", nishon_raqam="yoq-raqam")

    k = await aziza_yasa(kontrakt, baza, llm).ishla("holatni o'zgartir")

    assert k.holat is Holat.XATO
    assert "topilmadi" in k.izoh
    assert "7/7" in k.izoh          # mavjudlaridan namuna ko'rsatiladi


@pytest.mark.asyncio
async def test_notanish_holat_rad_etiladi(kontrakt, baza):
    """Statistika buzilmasligi uchun faqat to'rtta qiymat."""
    await _kp_qoy(baza, "8/8")
    llm = aziza_javobi(yangi_holat="kutilmoqda", nishon_raqam="8/8")

    k = await aziza_yasa(kontrakt, baza, llm).ishla("holatni o'zgartir")

    assert k.holat is Holat.XATO
    assert "shartnoma" in k.izoh    # ruxsat etilganlari sanab beriladi


@pytest.mark.asyncio
async def test_baza_notanish_holatni_qabul_qilmaydi(baza):
    """Kod darajasidagi himoya — promptga tayanmaydi."""
    await _kp_qoy(baza, "9/9")
    with pytest.raises(ValueError):
        await baza.kp_holat_yoz("9/9", "allaqanday", "")


# --- chegaralar --------------------------------------------------------------


def test_promptda_chegaralar():
    from app.agentlar.kp_kuzatuvchi import TIZIM_PROMPT

    tekis = " ".join(TIZIM_PROMPT.split())
    assert "RAQAM YOZMAYSAN" in tekis
    assert "BASHORAT QILMAYSAN" in tekis
    assert "Mijozga xat yoki xabar yubormaysan" in tekis


def test_kontraktda_chegaralar():
    matn = kontraktlarni_yukla()["kp-tracker"].matn()
    assert "MIJOZGA HECH NARSA YUBORMAYDI" in matn
    assert "KP TUZMAYDI" in matn


# --- KUNLIK ESLATMA (avtonom, 2026-09-08) -----------------------------------
#
# O'LCHANDI: 25 ta taklif "yuborildi" holatida 40 kundan beri turgan,
# 26 tadan faqat 1 tasi shartnomaga aylangan. Tizim KP tayyorlab, keyin
# unutardi. Aziza shu ish uchun yozilgan, lekin uni HECH KIM so'ramasdi.


@pytest.mark.asyncio
async def test_javobsiz_kplar_bazadan_topiladi(tmp_path):
    """Ro'yxat SOF SO'ROV bilan olinadi — modelga berilmaydi."""
    from app.baza import Baza

    from datetime import date, timedelta

    b = Baza(tmp_path / "eslatma.db")
    await b.tayyorla()
    # Sanalar BUGUNDAN hisoblanadi. Ilgari "yangi" KP sanasi qotirib
    # yozilgan edi (2026-09-08) va 6 kun o'tib u o'zi "eski" bo'lib
    # qoldi — test hech narsa o'zgarmasa ham yiqildi.
    bugun = date.today()
    await b.kp_kuzatuv_yoz("ESKI-1", "Alfa MChJ", 1000.0,
                           (bugun - timedelta(days=40)).isoformat())
    await b.kp_kuzatuv_yoz("YANGI-1", "Beta MChJ", 2000.0,
                           (bugun - timedelta(days=1)).isoformat())

    javobsiz = await b.javobsiz_kplar(kun=5)

    raqamlar = [x["raqam"] for x in javobsiz]
    assert "ESKI-1" in raqamlar
    assert "YANGI-1" not in raqamlar, "yangi KP eslatmaga tushmasligi kerak"


@pytest.mark.asyncio
async def test_javob_kelgan_KP_eslatilmaydi(tmp_path):
    """Holat o'zgargan bo'lsa — ish tugagan, eslatish keraksiz."""
    from app.baza import Baza

    b = Baza(tmp_path / "eslatma2.db")
    await b.tayyorla()
    await b.kp_kuzatuv_yoz("A-1", "Alfa", 100.0, "2026-08-01")
    await b.kp_kuzatuv_yoz("A-2", "Beta", 100.0, "2026-08-01")
    await b.kp_holat_yoz("A-2", "shartnoma")

    raqamlar = [x["raqam"] for x in await b.javobsiz_kplar(kun=5)]

    assert raqamlar == ["A-1"]


def test_eslatma_MIJOZ_boyicha_guruhlanadi():
    """Qo'ng'iroq mijozga qilinadi, taklifga emas.

    Jonli ma'lumotda bitta korxonaga 9 ta taklif chiqdi — 20 qatorli
    ro'yxat menejerga tushunarsiz edi.
    """
    from app.baza import Baza
    from app.config import sozlama
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.s = sozlama()
    bot.baza = Baza.__new__(Baza)

    matn = bot._kp_eslatma_xabari([
        {"raqam": "1", "mijoz": "Alfa MChJ", "summa": 100.0, "yaratildi": "2026-08-01"},
        {"raqam": "2", "mijoz": "Alfa MChJ", "summa": 200.0, "yaratildi": "2026-08-02"},
        {"raqam": "3", "mijoz": "Beta", "summa": None, "yaratildi": "2026-08-03"},
    ])

    assert "2 ta mijoz" in matn
    assert "Alfa MChJ — 2 ta" in matn
    assert "1, 2" in matn


def test_eslatmada_KIRILL_va_LOTIN_nomi_birlashadi():
    """Bitta korxona ikki xil yozilgan bo'lsa ikki mijoz ko'rinmasin.

    Jonli ma'lumot: "Олмалиқ АГМК" va "Olmaliq AGMK" — bir korxona.
    """
    from app.baza import Baza
    from app.config import sozlama
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.s = sozlama()
    bot.baza = Baza.__new__(Baza)

    matn = bot._kp_eslatma_xabari([
        {"raqam": "1", "mijoz": "Олмалиқ АГМК", "summa": None,
         "yaratildi": "2026-08-01"},
        {"raqam": "2", "mijoz": "Olmaliq AGMK", "summa": None,
         "yaratildi": "2026-08-02"},
    ])

    assert "1 ta mijoz" in matn, matn


def test_OXSHASH_nomlar_birlashtirilmaydi():
    """Bir harf farq boshqa korxona bo'lishi mumkin — taxmin qilmaymiz."""
    from app.baza import Baza
    from app.config import sozlama
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.s = sozlama()
    bot.baza = Baza.__new__(Baza)

    matn = bot._kp_eslatma_xabari([
        {"raqam": "1", "mijoz": "Hoshimjon MCHJ", "summa": None,
         "yaratildi": "2026-08-01"},
        {"raqam": "2", "mijoz": "Hoshimkon MChJ", "summa": None,
         "yaratildi": "2026-08-02"},
    ])

    assert "2 ta mijoz" in matn, matn


def test_javobsiz_KP_yoq_bolsa_HAM_xabar_keladi():
    """Jimlik ikki xil ma'no berardi: "joyida" va "umuman ishlamadi"."""
    from app.baza import Baza
    from app.config import sozlama
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.s = sozlama()
    bot.baza = Baza.__new__(Baza)

    matn = bot._kp_eslatma_xabari([])

    assert "javobsiz turgan taklif yo'q" in matn

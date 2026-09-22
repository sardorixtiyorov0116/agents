"""HR menejeri Hilola — maxfiy maydonlar, kamsituvchi mezon, yakuniy qaror yo'q."""

from __future__ import annotations

import json

import pytest

from app.agentlar.hr_menejeri import HrMenejeri
from app.baza import HR_RUXSAT_ETILGAN_MAYDONLAR, Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat

from .soxta import SoxtaLlm, javob, matn_bloki


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["hr-assist"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "hilola.db")
    await b.tayyorla()
    return b


def hilola_javobi(**ustama):
    malumot = {
        "vazifa_turi": "e'lon",
        "qoralama": "Sotuv menejeri lavozimiga ish e'loni matni...",
        "mezonlar": [{"nomi": "Sotuvda 2 yil tajriba", "izoh": "lavozim talabi"}],
        "solishtirma": [],
        "rad_etilgan_mezonlar": [],
        "sorash_kerak": [],
        "tavsiya": "E'lonni HR mas'uli ko'rib chiqsin",
    }
    malumot.update(ustama)
    return malumot


def soxta(malumot):
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


# --- normal holat ------------------------------------------------------------


@pytest.mark.asyncio
async def test_elon_qoralamasi_tayyorlanadi(kontrakt, baza):
    llm = soxta(hilola_javobi())
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await hilola.ishla("Sotuv menejeri uchun ish e'loni tayyorla")

    assert k.kim == "hr-assist"
    assert k.holat is Holat.TUGADI
    # Yuqori xavfli agent — natija tasdiqsiz chiqmaydi
    assert k.tasdiq_kerak is True
    assert "YAKUNIY QAROR EMAS" in k.izoh
    assert k.manba


# --- maxfiy maydonlar (eng muhim test) ---------------------------------------


@pytest.mark.asyncio
async def test_maosh_va_telefon_hech_qachon_chiqmaydi(baza):
    """Cheklov kodda: `xodimlar()` maxfiy ustunlarni umuman o'qimaydi."""
    xodimlar = await baza.xodimlar()

    assert len(xodimlar) == 6
    for xodim in xodimlar:
        assert set(xodim) == set(HR_RUXSAT_ETILGAN_MAYDONLAR)
        assert "maosh" not in xodim
        assert "telefon" not in xodim

    # Bo'lim bo'yicha filtrda ham xuddi shunday
    it = await baza.xodimlar("IT")
    assert [x["ism"] for x in it] == ["Jamshid Ergashev", "Otabek Rasulov"]
    assert all("maosh" not in x for x in it)


@pytest.mark.asyncio
async def test_maxfiy_malumot_promptga_tushmaydi(kontrakt, baza):
    """Maosh bazada bor, lekin modelga yuborilgan matnda bo'lmasligi kerak."""
    llm = soxta(hilola_javobi(vazifa_turi="saralash"))
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)
    await hilola.ishla("IT bo'limi xodimlarini ko'rib chiq", {"xodimlar_kerak": True, "bolim": "IT"})

    # Ma'lumot foydalanuvchi xabarida yuboriladi — aynan shuni tekshiramiz.
    # (Tizim promptida "maosh" so'zi bor, lekin u yerda TAQIQ sifatida.)
    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "Jamshid Ergashev" in xabar, "ruxsat etilgan maydon yuborilishi kerak"
    assert "maosh" not in xabar.lower()
    assert "telefon" not in xabar.lower()

    # Maxfiy QIYMATLAR butun so'rovning hech bir joyida yo'q
    hammasi = json.dumps(llm.chaqiruvlar[0], ensure_ascii=False, default=str)
    for maxfiy in ("18000000", "18000000.0", "15500000", "+998901234502", "+998901234506"):
        assert maxfiy not in hammasi


# --- kamsituvchi mezon -------------------------------------------------------


@pytest.mark.asyncio
async def test_kamsituvchi_mezon_aniqlanadi_va_ogohlantiriladi(kontrakt, baza):
    llm = soxta(
        hilola_javobi(
            rad_etilgan_mezonlar=["'30 yoshgacha' — yosh mezon bo'la olmaydi"],
            mezonlar=[{"nomi": "3 yil tajriba", "izoh": "yosh o'rniga tajriba"}],
        )
    )
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await hilola.ishla("30 yoshgacha bo'lgan erkak nomzodlarni sarala")

    # Kod darajasida aniqlandi
    assert "kamsituvchi mezon aniqlandi" in k.izoh
    assert "yosh" in k.izoh and "jins" in k.izoh
    # Modelga ogohlantirish yuborildi
    assert "ISHLATMA" in llm.chaqiruvlar[0]["messages"][0]["content"]
    assert k.natija["rad_etilgan_mezonlar"]


@pytest.mark.asyncio
async def test_oddiy_sorovda_ogohlantirish_yoq(kontrakt, baza):
    llm = soxta(hilola_javobi())
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await hilola.ishla("Python dasturchisi uchun e'lon tayyorla")

    assert "kamsituvchi" not in k.izoh
    assert "ISHLATMA" not in llm.chaqiruvlar[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_chegaralar_promptda(kontrakt):
    from app.agentlar.hr_menejeri import TIZIM_PROMPT

    assert "YAKUNIY QAROR CHIQARMAYSAN" in TIZIM_PROMPT
    assert "YUBORMAYSAN" in TIZIM_PROMPT
    assert "KAMSITUVCHI MEZON ISHLATMAYSAN" in TIZIM_PROMPT


# --- ma'lumot yetishmasa -----------------------------------------------------


@pytest.mark.asyncio
async def test_malumot_yetishmasa_soraydi(kontrakt, baza):
    llm = soxta(
        hilola_javobi(
            qoralama="",
            sorash_kerak=["lavozim talablari", "ish haqi doirasi kim tomonidan belgilanadi"],
        )
    )
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await hilola.ishla("Yangi lavozimga e'lon tayyorla")

    assert "ma'lumot yetishmaydi" in k.izoh
    assert k.natija["sorash_kerak"]


@pytest.mark.asyncio
async def test_buzuq_javobda_xato_konverti(kontrakt, baza):
    llm = SoxtaLlm([javob([matn_bloki("bu nomzodni ishga oling")])])
    hilola = HrMenejeri(kontrakt=kontrakt, llm=llm, baza=baza)

    k = await hilola.ishla("Nomzodni baholang")
    assert k.holat is Holat.XATO


# --- namunaviy xodimlar jadvali ochiq aytiladi --------------------------------


def test_xodim_ishlatilmasa_ogohlantirish_yoq():
    """Vakansiya e'loni xodimlar jadvaliga tegmaydi — ogohlantirish keraksiz."""
    from presenter.agentlar import hr

    matn = hr({"vazifa_turi": "e'lon", "qoralama": "matn"})

    assert "NAMUNAVIY" not in matn


def test_ogohlantirish_javob_tepasida_turadi():
    from presenter.agentlar import hr

    matn = hr({
        "demo_ogohi": "⚠️ NAMUNAVIY MA'LUMOT",
        "vazifa_turi": "saralash",
        "qoralama": "matn",
    })

    assert matn.startswith("⚠️ NAMUNAVIY")


def test_sozlama_standart_qiymati_ehtiyotkor():
    """Standart `False` bo'lishi SHART.

    `True` bo'lsa, real baza ulanmagan holatda ham ogohlantirish
    chiqmaydi va soxta raqam haqiqat bo'lib ko'rinadi.
    """
    from app.config import Sozlama

    assert Sozlama.model_fields["ish_bazasi_haqiqiy"].default is False

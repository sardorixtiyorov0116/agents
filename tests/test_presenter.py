"""Javob formatlash qatlami — texnik maydonlar yashiriladi, matn odamcha bo'ladi.

O'zgarmas qoida: texnik JSON maydonlari foydalanuvchiga KO'RSATILMAYDI.
"""

from __future__ import annotations

import pytest

from app.konvert import Holat, Ishonch, Konvert, Manba, aniqlik_kerak_konvert
from presenter import javob_matni, konvert_matni
from presenter.agentlar import agent_matni
from presenter.matn import TEXNIK_MAYDONLAR, manba_qatori, qisqartir

# Topshiriqdagi misol — Sardorning xom natijasi.
SARDOR_NATIJA = {
    "mahsulot": "Глиномешалка МГ 2-4Х",
    "kategoriya": "Aralashtirgich",
    "xususiyatlar": [
        {
            "nomi": "Unumdorlik",
            "qiymat": "30 ± 0,5 м³/ч",
            "manba_turi": "ichki_api",
            "manba_nomi": "Climavent ichki katalogi",
            "havola": None,
            "ishonch": "yuqori",
        },
        {
            "nomi": "Elektrodvigatel",
            "qiymat": "18,5 kVt, 750 ob/min",
            "manba_turi": "ichki_api",
            "manba_nomi": "Climavent ichki katalogi",
            "havola": None,
            "ishonch": "yuqori",
        },
    ],
    "topilmagan_maydonlar": [
        "kuchlanish", "IP darajasi", "sertifikatlar", "og'irlik", "kafolat",
        "ishlab chiqarilgan yil", "rang", "qadoq",
    ],
    "ziddiyatlar": [],
}


def konvert_yasa(kim: str, natija: dict, **kw) -> Konvert:
    asos = {
        "kim": kim,
        "holat": Holat.TUGADI,
        "natija": natija,
        "manba": [Manba(tur="ichki_api", nom="Climavent ichki katalogi")],
        "ishonch": Ishonch.YUQORI,
    }
    asos.update(kw)
    return Konvert(**asos)


# --- texnik maydonlar --------------------------------------------------------


def test_texnik_maydonlar_korsatilmaydi():
    matn = agent_matni("product-spec", SARDOR_NATIJA)

    for texnik in ("manba_turi", "ichki_api", "havola", "null", "None"):
        assert texnik not in matn, f"texnik maydon chiqib qoldi: {texnik}"


def test_bosh_maydonlar_chiqmaydi():
    natija = {
        "mahsulot": "Test",
        "kategoriya": "",
        "xususiyatlar": [],
        "topilmagan_maydonlar": [],
        "ziddiyatlar": [],
    }
    matn = agent_matni("product-spec", natija)

    assert "kategoriya" not in matn.lower()
    assert "ziddiyat" not in matn.lower()


def test_texnik_maydonlar_royxati_toliq():
    """Ro'yxat kengaytirilsa ham asosiylari joyida qolsin."""
    for kalit in ("manba_turi", "havola", "sql", "ichki_manba", "taklif_sql"):
        assert kalit in TEXNIK_MAYDONLAR


# --- o'qish qulayligi --------------------------------------------------------


def test_spetsifikatsiya_odamcha_korinadi():
    matn = agent_matni("product-spec", SARDOR_NATIJA)

    assert matn.startswith("Глиномешалка МГ 2-4Х — texnik xususiyatlari")
    assert "Unumdorlik: 30 ± 0,5 м³/ч" in matn
    assert "Elektrodvigatel: 18,5 kVt, 750 ob/min" in matn
    # JSON belgilari yo'q
    for belgi in ("{", "}", "[", "]", '"nomi"'):
        assert belgi not in matn


def test_uzun_royxat_qisqartiriladi():
    matn = agent_matni("product-spec", SARDOR_NATIJA)

    assert "Topilmadi:" in matn
    assert "yana 2 ta" in matn, "8 ta topilmagandan 6 tasi ko'rsatilib, qolgani sanaladi"


def test_qisqartir_yordamchisi():
    assert qisqartir(["a", "b"]) == "a, b"
    assert qisqartir([]) == ""
    assert qisqartir(["", "  "]) == ""
    uzun = qisqartir([str(i) for i in range(10)], maks=3)
    assert uzun == "0, 1, 2 (yana 7 ta)"


# --- manba qatori ------------------------------------------------------------


def test_manba_bitta_qatorda():
    manbalar = [
        Manba(tur="ichki_api", nom="Climavent ichki katalogi"),
        Manba(tur="ichki_api", nom="yana bir"),
        Manba(tur="tashqi_veb", nom="example.com", havola="https://example.com"),
    ]
    qator = manba_qatori(manbalar)

    assert qator == "Manba: Climavent ichki katalogi, tashqi manbalar"
    # Havolalar ro'yxat bo'lib chiqmaydi
    assert "https://" not in qator


def test_manba_yoq_bolsa_qator_yoq():
    assert manba_qatori([]) == ""


def test_bilim_bazasi_manbasi_hujjat_nomi_bilan():
    qator = manba_qatori([Manba(tur="bilim", nom="Mehnat kodeksi, 173-modda")])
    assert qator == "Manba: Mehnat kodeksi, 173-modda"


# --- ishonch ogohlantirishi --------------------------------------------------


def test_past_ishonchda_ogohlantirish():
    konvert = konvert_yasa("product-spec", SARDOR_NATIJA, ishonch=Ishonch.PAST)
    matn = konvert_matni(konvert)

    assert "Ishonch past" in matn


def test_yuqori_ishonchda_ogohlantirish_yoq():
    matn = konvert_matni(konvert_yasa("product-spec", SARDOR_NATIJA))
    assert "Ishonch past" not in matn


# --- holat xabarlari (jim qolmaslik) -----------------------------------------


def test_mos_agent_yoq_tushunarli_xabar():
    konvert = Konvert(
        kim="router",
        holat=Holat.MOS_AGENT_YOQ,
        ishonch=Ishonch.ORTA,
        izoh="Pizza buyurtma qilish kontraktlarda yo'q",
    )
    matn = konvert_matni(konvert)

    assert "agent yo'q" in matn
    assert "Pizza" in matn
    # Foydalanuvchi nima qila olishini biladi
    assert "narx" in matn and "marketing" in matn


def test_xato_holatida_sabab_aytiladi():
    konvert = Konvert(
        kim="data-query",
        holat=Holat.XATO,
        ishonch=Ishonch.PAST,
        izoh="Baza rad etdi: ruxsat etilmagan jadval",
    )
    matn = konvert_matni(konvert)

    assert "bajarilmadi" in matn
    assert "ruxsat etilmagan jadval" in matn


def test_aniqlik_kerak_savollar_bilan():
    konvert = aniqlik_kerak_konvert(["Qaysi hujjat?", "Qaysi davr?"])
    matn = konvert_matni(konvert)

    assert "1. Qaysi hujjat?" in matn
    assert "2. Qaysi davr?" in matn
    assert "Javobingizni yozing" in matn


def test_hech_qachon_bosh_javob_qaytmaydi():
    """Tizim jim qolmaydi — hatto natija bo'sh bo'lsa ham."""
    from app.orkestr import Natija

    natija = Natija(
        sorov="test",
        davomiylik_ms=0,
        yakuniy=Konvert(kim="x", holat=Holat.TUGADI, ishonch=Ishonch.ORTA, manba=[
            Manba(tur="veb", nom="x")
        ]),
    )
    matn = javob_matni(natija)
    assert matn.strip()


# --- huquqiy javob -----------------------------------------------------------


def test_huquqiy_javobda_modda_havolasi_korinadi():
    natija = {
        "hujjat_turi": "Yetkazib berish shartnomasi",
        "yurisdiksiya": "O'zbekiston",
        "qaydlar": [
            {
                "band": "4.2",
                "xavf": "past",
                "izoh": "Tahririy",
                "tuzatish_taklifi": "Aniqlashtiring",
                "manba_nomi": "FK 333-modda",
                "havola": "https://lex.uz/x",
            },
            {
                "band": "1.1",
                "xavf": "yuqori",
                "izoh": "Muddat aniq emas",
                "tuzatish_taklifi": "Aniq sana yozing",
                "manba_nomi": "FK 242-modda",
                "havola": None,
            },
        ],
        "xulosa": "Bitta jiddiy band bor.",
        "aniqlik_kerak": [],
        "yetishmagan_qismlar": [],
    }
    matn = agent_matni("legal-review", natija)

    # Yuqori xavf birinchi ko'rsatiladi
    assert matn.index("1.1") < matn.index("4.2")
    assert "🔴" in matn and "🟢" in matn
    # Har xulosa modda havolasi bilan
    assert "Asos: FK 242-modda" in matn
    assert "huquqiy kafolat emas" in matn
    assert "havola" not in matn


# --- zanjir to'xtashi --------------------------------------------------------


@pytest.mark.asyncio
async def test_zanjir_toxtasa_qayerda_toxtagani_aytiladi():
    from app.orkestr import Natija, QadamIzi
    from app.router import Reja, RejaQadam

    natija = Natija(
        sorov="test",
        davomiylik_ms=0,
        reja=Reja(
            niyat="test",
            qadamlar=[
                RejaQadam(agent="competitor-watch", vazifa="raqiblar"),
                RejaQadam(agent="marketing", vazifa="kampaniya"),
            ],
        ),
        qadamlar=[
            QadamIzi(
                tartib=1,
                agent="competitor-watch",
                korinish="Raqobat tahlilchisi Karim",
                vazifa="raqiblar",
                konvert=Konvert(
                    kim="competitor-watch",
                    holat=Holat.XATO,
                    ishonch=Ishonch.PAST,
                    izoh="API yiqildi",
                ),
                davomiylik_ms=10,
            )
        ],
        yakuniy=Konvert(
            kim="competitor-watch", holat=Holat.XATO, ishonch=Ishonch.PAST, izoh="API yiqildi"
        ),
    )
    matn = javob_matni(natija, {"marketing": "Marketolog Malika"})

    assert "1-qadamda to'xtadi" in matn
    assert "Marketolog Malika boshlanmadi" in matn


def test_smm_oz_akkauntda_insights_korsatiladi():
    """Qamrov va saqlash ko'rishlar sonidan muhimroq — ular ko'rinsin."""
    from presenter.agentlar import smm

    matn = smm({
        "profil": "climaventuz", "obunachilar": 12400, "postlar_soni": 210,
        "korilgan_postlar": 25, "video_soni": 20,
        "oz_akkaunt": True,
        "jami_qamrov": 52000, "jami_saqlash": 1840,
        "jami_ulashish": 620, "jami_obuna": 95,
        "auditoriya": {"shaharlar": {"Tashkent": 8200, "Samarqand": 1100}},
    })
    assert "Qamrov" in matn and "52" in matn
    assert "Saqlash" in matn
    assert "Yangi obuna" in matn
    assert "Tashkent" in matn


def test_smm_begona_profilda_insights_korsatilmaydi():
    """Boshqa akkauntda bu raqamlar yo'q — nol deb ko'rsatmaymiz."""
    from presenter.agentlar import smm

    matn = smm({
        "profil": "raqib", "obunachilar": 5000, "postlar_soni": 80,
        "korilgan_postlar": 25, "video_soni": 20,
    })
    assert "Qamrov" not in matn
    assert "Saqlash" not in matn

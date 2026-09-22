"""Bot — ruxsat qatlami va formatlash (Telegram'ga ulanmaydi)."""

from __future__ import annotations

import json

import pytest

from app.baza import Baza
from app.config import Sozlama
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat
from app.orkestr import Orkestr
from app.router import Reja, RejaQadam
from bot.formatlash import javob_matni, reja_matni
from bot.ruxsat import Ruxsat

from .soxta import SoxtaLlm, javob, json_javob, matn_bloki


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
def korinishlar(kontraktlar):
    return {rol: k.korinish for rol, k in kontraktlar.items()}


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "bot.db")
    await b.tayyorla()
    return b


def sozlama_yasa(**kw):
    # Har maydon ATAYLAB ko'rsatilgan: aks holda pydantic ularni haqiqiy
    # `.env` dan o'qiydi va test ishlab chiquvchining muhitiga bog'lanib qoladi.
    asos = {
        "bot_ruxsat_etilgan_id": "111,222",
        "bot_hr_ruxsat_id": "222",
        "bot_katalog_ruxsat_id": "",
        "anthropic_api_key": "sinov",
    }
    asos.update(kw)
    return Sozlama(**asos)


# --- ruxsat ------------------------------------------------------------------


def test_royxatda_yoq_foydalanuvchi_rad_etiladi():
    ruxsat = Ruxsat(sozlama_yasa())

    assert ruxsat.foydalanuvchi(111).ruxsat is True
    rad = ruxsat.foydalanuvchi(999)
    assert rad.ruxsat is False
    # O'z ID'sini ko'rsatamiz — administrator qo'shishi oson bo'lsin
    assert "999" in rad.sabab


def test_bosh_royxatda_bot_hech_kimga_javob_bermaydi():
    """Xavfsiz standart: sozlanmagan bot ochiq qolmaydi."""
    ruxsat = Ruxsat(sozlama_yasa(bot_ruxsat_etilgan_id=""))

    assert ruxsat.sozlanganmi() is False
    assert ruxsat.foydalanuvchi(111).ruxsat is False
    assert ruxsat.foydalanuvchi(None).ruxsat is False


def test_hr_agentiga_alohida_ruxsat_kerak():
    ruxsat = Ruxsat(sozlama_yasa())
    hr_reja = Reja(niyat="nomzodlar", qadamlar=[RejaQadam(agent="hr-assist", vazifa="sarala")])

    # 111 — umumiy ruxsat bor, HR ruxsati yo'q
    qaror = ruxsat.reja(111, hr_reja)
    assert qaror.ruxsat is False
    assert "HR ruxsati yo'q" in qaror.sabab

    # 222 — HR ruxsati bor
    assert ruxsat.reja(222, hr_reja).ruxsat is True


def test_katalog_ruxsati_alohida_cheklanadi():
    """Katalogni hamma emas, faqat belgilangan ID o'zgartira oladi."""
    ruxsat = Ruxsat(sozlama_yasa(bot_katalog_ruxsat_id="222"))
    katalog_reja = Reja(
        niyat="narx",
        qadamlar=[RejaQadam(agent="catalog-admin", vazifa="narx qo'sh")],
    )

    qaror = ruxsat.reja(111, katalog_reja)
    assert qaror.ruxsat is False
    assert "katalog ruxsati yo'q" in qaror.sabab

    assert ruxsat.reja(222, katalog_reja).ruxsat is True


def test_katalog_royxati_bosh_bolsa_umumiy_royxat_ishlaydi():
    """Yangi sozlama qo'shilgani agentni o'chirib qo'ymasligi kerak."""
    ruxsat = Ruxsat(sozlama_yasa())  # bot_katalog_ruxsat_id berilmagan
    reja = Reja(
        niyat="narx", qadamlar=[RejaQadam(agent="catalog-admin", vazifa="narx")]
    )

    assert ruxsat.reja(111, reja).ruxsat is True
    assert ruxsat.reja(999, reja).ruxsat is False


def test_boshqa_agentlar_hammaga_ochiq():
    ruxsat = Ruxsat(sozlama_yasa())
    reja = Reja(
        niyat="narx va kampaniya",
        qadamlar=[
            RejaQadam(agent="price-monitor", vazifa="narx"),
            RejaQadam(agent="marketing", vazifa="kampaniya"),
        ],
    )
    assert ruxsat.reja(111, reja).ruxsat is True


def test_zanjirdagi_hr_qadami_ham_tekshiriladi():
    """HR zanjirning ikkinchi qadami bo'lsa ham ruxsat talab qilinadi."""
    ruxsat = Ruxsat(sozlama_yasa())
    reja = Reja(
        niyat="ma'lumot + HR",
        qadamlar=[
            RejaQadam(agent="data-query", vazifa="xodimlar soni"),
            RejaQadam(agent="hr-assist", vazifa="e'lon tayyorla"),
        ],
    )
    assert ruxsat.reja(111, reja).ruxsat is False


# --- ruxsat orkestr bilan birga ----------------------------------------------


@pytest.mark.asyncio
async def test_ruxsatsiz_reja_bajarilmaydi(kontraktlar, baza):
    """Ilgak rad etsa — birorta agent ishga tushmaydi."""
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "nomzodlarni sarala",
                    "vazifa_soni": 1,
                    "qadamlar": [
                        {
                            "agent": "hr-assist",
                            "vazifa": "nomzodlarni sarala",
                            "tasdiq_kerak": True,
                            "tasdiq_sababi": "yuqori xavf",
                        }
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "",
                }
            )
            # Ikkinchi javob yo'q: agent chaqirilsa test yiqiladi.
        ]
    )
    ruxsat = Ruxsat(sozlama_yasa())

    async def tekshir(reja):
        qaror = ruxsat.reja(111, reja)
        return None if qaror.ruxsat else qaror.sabab

    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "Nomzodlarni saralab bering", reja_tekshiruvi=tekshir
    )

    assert natija.qadamlar == []
    assert natija.yakuniy.holat is Holat.XATO
    assert "HR ruxsati yo'q" in natija.yakuniy.izoh


@pytest.mark.asyncio
async def test_ruxsat_berilsa_reja_bajariladi(kontraktlar, baza):
    korilgan = []

    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "narx",
                    "vazifa_soni": 1,
                    "qadamlar": [
                        {
                            "agent": "data-query",
                            "vazifa": "mijozlar soni",
                            "tasdiq_kerak": False,
                            "tasdiq_sababi": "",
                        }
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "",
                }
            ),
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "sql": "SELECT count(*) AS n FROM mijozlar",
                                "izoh": "mijozlar soni",
                                "yozish_kerakmi": False,
                                "yozish_sababi": "",
                            }
                        )
                    )
                ]
            ),
        ]
    )

    async def tekshir(reja):
        korilgan.append([q.agent for q in reja.qadamlar])
        return None

    natija = await Orkestr(llm, baza, kontraktlar).bajar(
        "Nechta mijoz bor?", reja_tekshiruvi=tekshir
    )

    # Ilgak rejani bajarishdan OLDIN ko'rdi
    assert korilgan == [["data-query"]]
    assert natija.yakuniy.holat is Holat.TUGADI


# --- formatlash --------------------------------------------------------------


# --- tayyor hujjatlarni yuborish ---------------------------------------------


@pytest.mark.asyncio
async def test_kp_fayllari_biriktiriladi(tmp_path):
    """Agent hujjat yaratsa, bot uni foydalanuvchiga YETKAZISHI shart."""
    from app.konvert import Holat, Ishonch, Konvert, Manba
    from app.orkestr import Natija
    from bot.asosiy import Bot

    pdf = tmp_path / "KP_12951-7.pdf"
    docx = tmp_path / "KP_12951-7.docx"
    pdf.write_bytes(b"%PDF-1.4 sinov")
    docx.write_bytes(b"PK sinov")

    natija = Natija(
        sorov="KP tayyorla",
        davomiylik_ms=0,
        yakuniy=Konvert(
            kim="proposal-builder",
            holat=Holat.TUGADI,
            natija={"raqam": "12951/7", "fayllar": {"pdf": str(pdf), "docx": str(docx)}},
            manba=[Manba(tur="bilim", nom="narxlar.yaml")],
            ishonch=Ishonch.ORTA,
        ),
    )

    yuborilgan: list[str] = []

    class SoxtaXabar:
        async def reply_document(self, fayl, filename=None):
            yuborilgan.append(filename)

    bot = Bot.__new__(Bot)  # __init__ LLM/baza talab qiladi — kerak emas
    await Bot._tayyor_fayllar(bot, SoxtaXabar(), natija)

    # PDF birinchi (yuborish uchun), keyin DOCX (tahrirlash uchun)
    assert yuborilgan == ["KP_12951-7.pdf", "KP_12951-7.docx"]


@pytest.mark.asyncio
async def test_fayl_yoq_bolsa_bot_yiqilmaydi(tmp_path):
    from app.konvert import Holat, Ishonch, Konvert, Manba
    from app.orkestr import Natija
    from bot.asosiy import Bot

    natija = Natija(
        sorov="x",
        davomiylik_ms=0,
        yakuniy=Konvert(
            kim="proposal-builder",
            holat=Holat.TUGADI,
            natija={"fayllar": {"pdf": str(tmp_path / "yoq.pdf")}},
            manba=[Manba(tur="bilim", nom="x")],
            ishonch=Ishonch.ORTA,
        ),
    )

    class SoxtaXabar:
        async def reply_document(self, fayl, filename=None):
            raise AssertionError("mavjud bo'lmagan fayl yuborilmasligi kerak")

    await Bot._tayyor_fayllar(Bot.__new__(Bot), SoxtaXabar(), natija)


@pytest.mark.asyncio
async def test_fayl_yoq_agentlarda_hech_narsa_yuborilmaydi():
    """Boshqa agentlar hujjat yaratmaydi — bo'sh o'tishi kerak."""
    from app.konvert import Holat, Ishonch, Konvert, Manba
    from app.orkestr import Natija
    from bot.asosiy import Bot

    natija = Natija(
        sorov="narx",
        davomiylik_ms=0,
        yakuniy=Konvert(
            kim="price-monitor",
            holat=Holat.TUGADI,
            natija={"yozuvlar": []},
            manba=[Manba(tur="veb", nom="x")],
            ishonch=Ishonch.ORTA,
        ),
    )

    class SoxtaXabar:
        async def reply_document(self, *a, **kw):
            raise AssertionError("hujjat yo'q — yuborilmasligi kerak")

    await Bot._tayyor_fayllar(Bot.__new__(Bot), SoxtaXabar(), natija)


# --- menejer savoli: so'ralganda javob ASL so'rovni davom ettiradi ----------


@pytest.mark.asyncio
async def test_menejer_javobi_asl_sorovni_qaytaradi(baza):
    """Javob ("Aziz +998...") alohida so'rov emas — oldingi KP ning davomi."""
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.baza = baza
    await baza.savol_yoz(111, "menejer", "Olmaliq AGMK uchun KP tayyorla")

    asl, tasdiq = await Bot._kutilgan_javob(bot, 111, "Aziz Karimov +998 90 111 11 11")

    assert asl == "Olmaliq AGMK uchun KP tayyorla"
    assert "Aziz Karimov" in tasdiq
    saqlangan = await baza.menejer(111)
    assert saqlangan == {"ism": "Aziz Karimov", "telefon": "+998 90 111 11 11"}
    # Savol yopildi — keyingi xabar oddiy so'rov sifatida ketadi
    assert await baza.savol(111) is None


@pytest.mark.asyncio
async def test_tushunarsiz_javobda_savol_kuchda_qoladi(baza):
    """Telefonsiz javob qabul qilinmaydi, aks holda KP da raqam bo'sh qolardi."""
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.baza = baza
    await baza.savol_yoz(111, "menejer", "KP tayyorla")

    assert await Bot._kutilgan_javob(bot, 111, "Aziz Karimov") is None
    assert await baza.menejer(111) is None
    assert (await baza.savol(111))["tur"] == "menejer"


@pytest.mark.asyncio
async def test_savol_kutilmayotganda_xabar_oddiy_sorov(baza):
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.baza = baza

    assert await Bot._kutilgan_javob(bot, 111, "Aziz Karimov +998901112233") is None


@pytest.mark.asyncio
async def test_menejer_xodimlar_orasida_aralashmaydi(baza):
    await baza.menejer_yoz(111, "Aziz Karimov", "+998 90 111 11 11")
    await baza.menejer_yoz(222, "Bekzod Aliyev", "+998 90 222 22 22")

    assert (await baza.menejer(111))["ism"] == "Aziz Karimov"
    assert (await baza.menejer(222))["ism"] == "Bekzod Aliyev"
    assert await baza.menejer(333) is None


@pytest.mark.asyncio
async def test_menejer_qayta_yozilsa_almashadi(baza):
    await baza.menejer_yoz(111, "Aziz Karimov", "+998 90 111 11 11")
    await baza.menejer_yoz(111, "Aziz Karimov", "+998 90 999 99 99")

    assert (await baza.menejer(111))["telefon"] == "+998 90 999 99 99"


def test_reja_matni_kim_ishlashini_aytadi(korinishlar):
    reja = Reja(
        niyat="raqib + kampaniya",
        qadamlar=[
            RejaQadam(agent="competitor-watch", vazifa="raqiblar"),
            RejaQadam(agent="marketing", vazifa="kampaniya", tasdiq_kerak=True),
        ],
    )
    matn = reja_matni(reja, korinishlar)

    assert "Karim → Malika ishlaydi" in matn
    assert "Raqobat tahlilchisi Karim" in matn
    assert "(tasdiq kerak)" in matn


def test_mos_agent_yoq_matni(korinishlar):
    reja = Reja(niyat="pizza", mos_agent_yoq=True, izoh="Buyurtma kontraktlarda yo'q")
    matn = reja_matni(reja, korinishlar)

    assert "Mos agent topilmadi" in matn
    assert "kontraktlarda yo'q" in matn


@pytest.mark.asyncio
async def test_javob_matnida_manba_va_ishonch_bor(kontraktlar, baza, korinishlar):
    llm = SoxtaLlm(
        [
            json_javob(
                {
                    "niyat": "mijozlar",
                    "vazifa_soni": 1,
                    "qadamlar": [
                        {
                            "agent": "data-query",
                            "vazifa": "mijozlar soni",
                            "tasdiq_kerak": False,
                            "tasdiq_sababi": "",
                        }
                    ],
                    "mos_agent_yoq": False,
                    "izoh": "",
                }
            ),
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "sql": "SELECT count(*) AS n FROM mijozlar",
                                "izoh": "mijozlar soni",
                                "yozish_kerakmi": False,
                                "yozish_sababi": "",
                            }
                        )
                    )
                ]
            ),
        ]
    )
    natija = await Orkestr(llm, baza, kontraktlar).bajar("Nechta mijoz bor?")
    matn = javob_matni(natija, korinishlar)

    assert "Ma'lumot muhandisi Doston" in matn
    # Manba har doim ko'rsatiladi (o'zgarmas qoida)
    assert "Manba: ichki baza" in matn
    assert "✅" in matn
    # Texnik maydonlar foydalanuvchiga chiqmaydi
    for texnik in ("manba_turi", "havola", "sql", '"qatorlar"', "kesildi"):
        assert texnik not in matn


@pytest.mark.asyncio
async def test_til_javobi_asl_sorovga_qoshiladi(baza):
    """"o'zbekcha" javobi alohida so'rov emas — KP so'rovining davomi."""
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.baza = baza
    await baza.savol_yoz(111, "til", "5 dona ВК-250П uchun KP")

    asl, tasdiq = await Bot._kutilgan_javob(bot, 111, "o'zbekcha")

    # Til ASL so'rovga qo'shiladi — Temur uni o'sha yerdan o'qiydi
    assert asl == "5 dona ВК-250П uchun KP (o'zbekcha)"
    assert "o'zbek tilida" in tasdiq
    assert await baza.savol(111) is None


@pytest.mark.asyncio
async def test_til_javobi_tushunarsiz_bolsa_savol_qoladi(baza):
    from bot.asosiy import Bot

    bot = Bot.__new__(Bot)
    bot.baza = baza
    await baza.savol_yoz(111, "til", "KP tayyorla")

    assert await Bot._kutilgan_javob(bot, 111, "bilmadim") is None
    assert await baza.savol(111) is not None


# --- /murojaatlar -------------------------------------------------------------
#
# Menejer mijoz bilan NIMA gaplashilganini ko'rishi kerak: bot unga
# "menejerimiz bog'lanadi" deb va'da beradi.


def test_murojaat_matnida_savol_ham_javob_ham_bor():
    from bot.asosiy import _murojaat_matni

    matn = _murojaat_matni({
        "id": 7, "vaqt": "2026-08-06T12:30:00", "ism": "Aziz",
        "aloqa": "+998901234567", "savol": "800 m² ombor",
        "javob": "Havo sarfi: 9 600 m³/soat", "sabab": None,
    })

    assert "800 m² ombor" in matn
    assert "9 600 m³/soat" in matn
    assert "+998901234567" in matn
    assert "2026-08-06 12:30" in matn


def test_javobsiz_murojaat_ochiq_korsatiladi():
    """Javob yo'qligi ko'rinib tursin — menejer o'zi javob berishi kerak."""
    from bot.asosiy import _murojaat_matni

    matn = _murojaat_matni({
        "id": 8, "vaqt": "2026-08-06T12:30:00", "ism": "Aziz",
        "aloqa": "", "savol": "Narxi qancha?", "javob": None,
        "sabab": "mijozga yopiq: proposal-builder",
    })

    assert "Bot javob bermadi" in matn
    assert "proposal-builder" in matn


def test_murojaatlar_buyrugi_royxatda():
    """Buyruq ulanmasa, /murojaatlar javobsiz qoladi."""
    import inspect

    from bot import asosiy

    manba = inspect.getsource(asosiy.yasa)
    assert '"murojaatlar"' in manba
    assert "/murojaatlar" in asosiy.SALOM


# --- uzoq kutish: xodim bot qotib qolgan deb o'ylamasin -----------------------


def test_sekin_agent_uchun_muddat_aytiladi():
    """Karim veb qidiruvni 18 martagacha bajaradi — bu 2-3 daqiqa.

    Muddat aytilmasa, xodim javob kelmayapti deb so'rovni qayta yuboradi
    va ikki barobar ko'p pul ketadi.
    """
    from app.router import Reja, RejaQadam
    from bot.asosiy import _kutish_izohi

    reja = Reja(niyat="raqiblar", qadamlar=[
        RejaQadam(agent="competitor-watch", vazifa="raqiblarni ko'r"),
    ])

    izoh = _kutish_izohi(reja)
    assert "2-3 daqiqa" in izoh
    assert "kutib turing" in izoh


def test_tez_agent_uchun_ortiqcha_gap_yozilmaydi():
    from app.router import Reja, RejaQadam
    from bot.asosiy import _kutish_izohi

    reja = Reja(niyat="hisob", qadamlar=[
        RejaQadam(agent="hvac-calc", vazifa="ombor hisobi"),
    ])

    assert _kutish_izohi(reja) == ""


def test_yozmoqda_belgisi_takrorlanadi():
    """Telegram belgisi ~5 soniyada o'chadi — oraliq undan qisqa bo'lsin."""
    from bot.asosiy import YOZMOQDA_ORALIQ

    assert 0 < YOZMOQDA_ORALIQ < 5


@pytest.mark.asyncio
async def test_yozmoqda_bekor_qilinsa_yiqilmaydi():
    import asyncio

    from bot.asosiy import Bot

    class Chat:
        soni = 0

        async def send_action(self, *_):
            Chat.soni += 1

    vazifa = asyncio.create_task(Bot._yozmoqda(Chat()))
    await asyncio.sleep(0.05)
    vazifa.cancel()
    await vazifa                      # CancelledError chiqmasligi kerak

    assert Chat.soni >= 1


# --- `sorov()` chindan ishlaydimi ---------------------------------------------
#
# JONLI SINOVDA TOPILGAN: `sorov()` mavjud bo'lmagan `_menejer_javobi`
# metodini chaqirardi (asl nomi `_kutilgan_javob`). Ya'ni ichki bot HAR
# matnli xabarda `AttributeError` bilan yiqilardi.
#
# Buyruqlar (`/menejer`, `/tasdiq`) ishlagani uchun sezilmagan — ular
# boshqa metodlarga boradi. Testlar ham yordamchi metodlarni ALOHIDA
# tekshirardi, `sorov()` ning o'zini emas.
#
# Shuning uchun bu yerda butun oqim chaqiriladi.


class SoxtaChat:
    async def send_action(self, *_):
        return None


class SoxtaXabar:
    def __init__(self, matn: str):
        self.text = matn
        self.chat = SoxtaChat()
        self.chiqish: list[str] = []

    async def reply_text(self, matn, **_):
        self.chiqish.append(matn)
        return self

    async def reply_document(self, *_, **__):
        return None


class SoxtaKim:
    id = 901
    full_name = "Sinov"
    username = "sinov"


class SoxtaYangilanish:
    def __init__(self, xabar):
        self.effective_user = SoxtaKim()
        self.effective_message = xabar


@pytest.mark.asyncio
async def test_sorov_oqimi_yiqilmaydi(tmp_path, monkeypatch):
    """Matnli xabar uchun butun `sorov()` oqimi chaqiriladi."""
    from app.baza import Baza
    from app.konvert import Holat, Ishonch, Konvert, Manba
    from app.orkestr import Natija
    from bot.asosiy import Bot

    bot = object.__new__(Bot)
    bot.s = Sozlama()
    bot.baza = Baza(tmp_path / "bot.db")
    await bot.baza.tayyorla()
    bot.korinishlar = {"hvac-calc": "Loyihachi muhandis Rustam"}

    from bot.ruxsat import RuxsatQarori

    class OchiqRuxsat:
        hammasi = {901}

        def foydalanuvchi(self, tg_id):
            return RuxsatQarori(True, "")

        def reja(self, tg_id, reja):
            return RuxsatQarori(True, "")

    bot.ruxsat = OchiqRuxsat()

    yakuniy = Konvert(
        kim="hvac-calc", holat=Holat.TUGADI, ishonch=Ishonch.YUQORI,
        natija={"obyekt": "Ombor"},
        manba=[Manba(tur="kontrakt", nom="hvac-calc kontrakti")],
    )

    class SoxtaOrkestr:
        async def bajar(self, sorov, kontekst=None, reja_tekshiruvi=None, **kw):
            return Natija(sorov=sorov, davomiylik_ms=1, yakuniy=yakuniy, iz_id=1)

    monkeypatch.setattr(bot, "orkestr", lambda: SoxtaOrkestr(), raising=False)

    xabar = SoxtaXabar("Ombor uchun ventilyatsiya hisobi")
    await bot.sorov(SoxtaYangilanish(xabar), None)

    assert xabar.chiqish, "bot javob bermadi"
    assert any("Ombor" in j for j in xabar.chiqish)


@pytest.mark.asyncio
async def test_sorov_suhbat_kontekstini_saqlaydi(tmp_path, monkeypatch):
    """Ikkinchi xabar birinchisi bilan birlashishi kerak."""
    from app.baza import Baza
    from app.konvert import Holat, Ishonch, Konvert
    from app.orkestr import Natija
    from bot import suhbat
    from bot.asosiy import Bot
    from bot.ruxsat import RuxsatQarori

    bot = object.__new__(Bot)
    bot.s = Sozlama()
    bot.baza = Baza(tmp_path / "bot.db")
    await bot.baza.tayyorla()
    bot.korinishlar = {}

    class OchiqRuxsat:
        hammasi = {901}

        def foydalanuvchi(self, tg_id):
            return RuxsatQarori(True, "")

        def reja(self, tg_id, reja):
            return RuxsatQarori(True, "")

    bot.ruxsat = OchiqRuxsat()

    korilgan: list[str] = []

    class SoxtaOrkestr:
        async def bajar(self, sorov, kontekst=None, reja_tekshiruvi=None, **kw):
            korilgan.append(sorov)
            return Natija(
                sorov=sorov, davomiylik_ms=1, iz_id=1,
                yakuniy=Konvert(
                    kim="hvac-calc", holat=Holat.ANIQLIK_KERAK,
                    ishonch=Ishonch.PAST,
                    natija={"savollar": ["Balandligi qancha?"]},
                ),
            )

    monkeypatch.setattr(bot, "orkestr", lambda: SoxtaOrkestr(), raising=False)

    await bot.sorov(SoxtaYangilanish(SoxtaXabar("Ombor 500 kv metr")), None)
    await bot.sorov(SoxtaYangilanish(SoxtaXabar("5 metr balandlik")), None)

    assert len(korilgan) == 2
    assert suhbat.OLDINGI in korilgan[1], "ikkinchi xabar birlashmadi"
    assert "500 kv metr" in korilgan[1]


# --- "bekor qil" --------------------------------------------------------------
#
# FOYDALANUVCHI XABARI: "bekor qil" dedim — ishlamadi. U oddiy so'rov
# sifatida modelga ketardi: pul sarflanardi, tasdiq esa osilib qolardi.


@pytest.mark.parametrize("matn", [
    "bekor qil", "Bekor qil", "bekor", "rad et", "kerakmas",
    "to'xtat", "отмена", "cancel", "bekor qil.",
])
def test_bekor_sozlari_taniladi(matn):
    from bot.asosiy import BEKOR_SOZLARI

    assert matn.lower().strip(" .!?") in BEKOR_SOZLARI


@pytest.mark.parametrize("matn", [
    "Ombor uchun KP tayyorla",
    "bekor qilingan buyurtmalarni ko'rsat",   # bu SO'ROV, buyruq emas
])
def test_oddiy_sorov_bekor_deb_qabul_qilinmaydi(matn):
    from bot.asosiy import BEKOR_SOZLARI

    assert matn.lower().strip(" .!?") not in BEKOR_SOZLARI


# --- ovozli xabar (ichki bot) -------------------------------------------------


class SoxtaIchkiOvoz:
    def __init__(self, davomiylik=8):
        self.duration = davomiylik
        self.mime_type = "audio/ogg"

    async def get_file(self):
        class Fayl:
            async def download_as_bytearray(self):
                return bytearray(b"ogg")

        return Fayl()


class SoxtaOvozXabar(SoxtaXabar):
    def __init__(self, ovoz):
        super().__init__("")
        self.text = None
        self.voice = ovoz
        self.audio = None
        self.ovozlar: list[bytes] = []

    async def reply_voice(self, wav, **_):
        self.ovozlar.append(wav)
        return self


def ichki_ovoz_boti(monkeypatch, ruxsat_id=901, matnga="ПВН narxi qancha",
                    javob="Narxi 1 340 900 so'm"):
    from bot import asosiy as asosiy_moduli
    from bot.asosiy import Bot

    bot = object.__new__(Bot)
    ogirilgan = {"marta": 0}

    async def soxta_ruxsatmi(update):
        return ruxsat_id

    async def soxta_matnga(xom, mime="audio/ogg"):
        ogirilgan["marta"] += 1
        return matnga

    async def soxta_ovozga(matn):
        ogirilgan["gapirildi"] = matn
        return b"RIFF" + b"\x00" * 40

    async def soxta_sorov(update, kontekst, matn=None):
        ogirilgan["sorov"] = matn
        return javob

    bot._ruxsatmi = soxta_ruxsatmi
    bot.sorov = soxta_sorov
    monkeypatch.setattr(asosiy_moduli.ovoz_moduli, "matnga", soxta_matnga)
    monkeypatch.setattr(asosiy_moduli.ovoz_moduli, "ovozga", soxta_ovozga)
    return bot, ogirilgan


@pytest.mark.asyncio
async def test_ichki_ovoz_matnga_ogiriladi(monkeypatch):
    bot, ogirilgan = ichki_ovoz_boti(monkeypatch)
    xabar = SoxtaOvozXabar(SoxtaIchkiOvoz())

    await bot.ovoz(SoxtaYangilanish(xabar), None)

    assert ogirilgan["sorov"] == "ПВН narxi qancha"
    assert any("Eshitdim" in j for j in xabar.chiqish)


@pytest.mark.asyncio
async def test_RUXSATSIZ_odamga_token_sarflanmaydi(monkeypatch):
    """Ichki bot oq ro'yxatli. O'girish PULLIK chaqiruv — ruxsat oldin.

    Aks holda notanish odam ovoz yuboraverib kvotani yeb qo'yardi.
    """
    bot, ogirilgan = ichki_ovoz_boti(monkeypatch, ruxsat_id=None)
    xabar = SoxtaOvozXabar(SoxtaIchkiOvoz())

    await bot.ovoz(SoxtaYangilanish(xabar), None)

    assert ogirilgan["marta"] == 0, "ruxsatsiz odam uchun o'girish chaqirildi"
    assert "sorov" not in ogirilgan


@pytest.mark.asyncio
async def test_ichki_botda_ovozli_javob_YOQ(monkeypatch):
    """Ichki botda javob FAQAT MATNDA.

    Menejerga keladigan javob ko'pincha jadval: tender ro'yxati lot
    raqamlari bilan, KP pozitsiyalari, narx jadvali. Ularni ovozda
    tinglash ko'z bilan o'qishdan sekinroq va foydasiz.
    """
    bot, ogirilgan = ichki_ovoz_boti(monkeypatch)
    xabar = SoxtaOvozXabar(SoxtaIchkiOvoz())

    await bot.ovoz(SoxtaYangilanish(xabar), None)

    assert ogirilgan["sorov"], "ovoz o'girilmadi"
    assert not xabar.ovozlar, "ichki botda ovozli javob yuborildi"
    assert "gapirildi" not in ogirilgan, "TTS chaqirildi — pul behuda ketdi"


def test_ichki_botda_TTS_umuman_chaqirilmaydi():
    """Kod darajasida: ichki botda ovoz yasash chaqiruvi bo'lmasin."""
    import inspect
    from bot import asosiy

    manba = inspect.getsource(asosiy.Bot.ovoz)
    assert "ovozga" not in manba
    assert "reply_voice" not in manba


@pytest.mark.asyncio
async def test_ichki_uzun_ovoz_rad_etiladi(monkeypatch):
    from app import ovoz as ovoz_moduli

    bot, ogirilgan = ichki_ovoz_boti(monkeypatch)
    xabar = SoxtaOvozXabar(SoxtaIchkiOvoz(davomiylik=ovoz_moduli.MAKS_SONIYA + 1))

    await bot.ovoz(SoxtaYangilanish(xabar), None)

    assert ogirilgan["marta"] == 0
    assert str(ovoz_moduli.MAKS_SONIYA) in xabar.chiqish[0]


def test_ichki_ovoz_ishlovchisi_ROYXATDAN_OTGAN():
    import inspect
    from bot import asosiy

    manba = inspect.getsource(asosiy.yasa)
    assert "filters.VOICE" in manba
    assert "bot.ovoz" in manba

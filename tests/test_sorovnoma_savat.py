"""Savat va telefon xotirasi.

NEGA BU TESTLAR BOR
-------------------
JONLI E'TIROZ (2026-08-27): birinchi variantda har so'rovnoma alohida
yuborilardi va oxirida telefon QAYTA so'ralardi. Ikkalasi ham noto'g'ri
edi:

1. Mijoz bitta uskuna bilan cheklanmaydi. Bitta obyektga ventilyator
   ham, panjara ham, filtr ham kerak — hatto bitta bo'limdan BIR NECHA
   xil o'lchamda (zalga 500x300, koridorga 200x200). Har biri alohida
   yuborilsa menejer bitta obyektning bo'laklarini bog'lay olmasdi.

2. Bir mijoz uchta pozitsiya so'rasa, bir xil raqamni uch marta
   yozardi. Bu bezovta qiladi va ba'zilari umuman tashlab ketardi.
"""

from __future__ import annotations

import pytest

from app.baza import Baza
from sorovnoma import SorovnomaShakli
from sorovnoma import oqim as sn

TG = 4242


@pytest.fixture
async def baza(tmp_path):
    b = Baza(yol=tmp_path / "sinov.db")
    await b.tayyorla()
    return b


def _toldirilgan(kalit: str, javoblar: list[str]) -> SorovnomaShakli:
    s = SorovnomaShakli(kalit)
    for javob in javoblar:
        s.javob_ber(javob)
    assert s.tugadimi(), f"{kalit}: savollar tugamadi"
    return s


VENTILYATOR = ["ichkarida", "radial", "8000", "450", "toza", "2"]
PANJARA_ZAL = ["РВН", "500x300", "krv-bilan", "9016", "14"]
PANJARA_KORIDOR = ["РВИ", "200x200", "krv-siz", "9016", "6"]


# --- Savat --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bosh_savat(baza):
    assert await sn.savatni_ol(baza, TG) == []


@pytest.mark.asyncio
async def test_pozitsiya_savatga_tushadi(baza):
    await sn.boshla(baza, TG, "ventilyator")
    shakl = _toldirilgan("ventilyator", VENTILYATOR)

    savat = await sn.savatga_qosh(baza, TG, shakl)

    assert len(savat) == 1
    assert savat[0]["bolim"] == "ventilyator"


@pytest.mark.asyncio
async def test_YANGI_bolim_boshlanganda_savat_SAQLANADI(baza):
    """Eng muhim xossa: ikkinchi uskuna birinchisini o'chirmasin."""
    await sn.boshla(baza, TG, "ventilyator")
    await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    await sn.boshla(baza, TG, "panjara")

    assert len(await sn.savatni_ol(baza, TG)) == 1


@pytest.mark.asyncio
async def test_javob_yozilganda_savat_TEGILMAYDI(baza):
    """Har javobda savat qayta yozilsa, pozitsiyalar yo'qolib ketardi."""
    await sn.boshla(baza, TG, "ventilyator")
    await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    await sn.boshla(baza, TG, "panjara")
    shakl = await sn.joriy_shakl(baza, TG)
    await sn.javobni_qabul_qil(baza, TG, shakl, "РВН")

    assert len(await sn.savatni_ol(baza, TG)) == 1


@pytest.mark.asyncio
async def test_BITTA_bolimdan_bir_necha_pozitsiya(baza):
    """Zalga 500x300, koridorga 200x200 — bir xil bo'lim, har xil o'lcham."""
    await sn.boshla(baza, TG, "panjara")
    await sn.savatga_qosh(baza, TG, _toldirilgan("panjara", PANJARA_ZAL))
    await sn.boshla(baza, TG, "panjara")
    savat = await sn.savatga_qosh(baza, TG, _toldirilgan("panjara", PANJARA_KORIDOR))

    assert len(savat) == 2
    assert savat[0]["javoblar"]["olcham"] == "500x300"
    assert savat[1]["javoblar"]["olcham"] == "200x200"


@pytest.mark.asyncio
async def test_uch_xil_uskuna(baza):
    for kalit, javoblar in (("ventilyator", VENTILYATOR),
                            ("panjara", PANJARA_ZAL),
                            ("panjara", PANJARA_KORIDOR)):
        await sn.boshla(baza, TG, kalit)
        savat = await sn.savatga_qosh(baza, TG, _toldirilgan(kalit, javoblar))

    assert [p["bolim"] for p in savat] == ["ventilyator", "panjara", "panjara"]


@pytest.mark.asyncio
async def test_pozitsiya_soni_CHEKLANGAN(baza):
    """Xato bosish tufayli yuzlab pozitsiya to'planib qolmasin."""
    for _ in range(sn.MAKS_POZITSIYA + 5):
        await sn.boshla(baza, TG, "panjara")
        savat = await sn.savatga_qosh(baza, TG, _toldirilgan("panjara", PANJARA_ZAL))

    assert len(savat) == sn.MAKS_POZITSIYA


@pytest.mark.asyncio
async def test_yakunlash_HAMMA_pozitsiyani_yozadi(baza):
    for kalit, javoblar in (("ventilyator", VENTILYATOR), ("panjara", PANJARA_ZAL)):
        await sn.boshla(baza, TG, kalit)
        savat = await sn.savatga_qosh(baza, TG, _toldirilgan(kalit, javoblar))

    idlar = await sn.yakunla(baza, TG, savat, ism="Jasur", aloqa="+998901112233")

    assert len(idlar) == 2
    yozuvlar = await baza.sorovnomalar(holat="yangi", chek=10)
    assert len(yozuvlar) == 2
    assert all(y["aloqa"] == "+998901112233" for y in yozuvlar)


@pytest.mark.asyncio
async def test_yakunlashdan_keyin_holat_TOZALANADI(baza):
    await sn.boshla(baza, TG, "ventilyator")
    savat = await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    await sn.yakunla(baza, TG, savat)

    assert await baza.sorovnoma_holati(TG) is None
    assert await sn.savatni_ol(baza, TG) == []


# --- Menejer xabari -----------------------------------------------------------


def test_menejer_xabarida_HAMMA_pozitsiya_bor():
    savat = [
        {"bolim": "ventilyator",
         "javoblar": dict(zip(
             ("joy", "turi", "sarf", "bosim", "havo", "soni"),
             ("ichkarida", "radial", 8000.0, 450.0, "toza", 2)))},
        {"bolim": "panjara",
         "javoblar": dict(zip(
             ("model", "olcham", "krv", "rang", "soni"),
             ("РВН", "500x300", "krv-bilan", "9016", 14)))},
    ]

    matn = sn.savat_menejer_matni(savat, ism="Jasur",
                                  aloqa="+998901112233", tg_id=TG)

    assert "2 ta pozitsiya" in matn
    assert "Ventilyator" in matn
    assert "Ventilyatsiya panjaralari" in matn
    assert "500x300" in matn
    assert "+998901112233" in matn


def test_savat_matnida_pozitsiyalar_RAQAMLANADI():
    savat = [{"bolim": "panjara", "javoblar": {"model": "РВН", "soni": 14}},
             {"bolim": "panjara", "javoblar": {"model": "РВИ", "soni": 6}}]

    matn = sn.savat_matni(savat)

    assert "1." in matn and "2." in matn
    assert "2 ta pozitsiya" in matn


def test_bosh_savatda_YUBORISH_tugmasi_YOQ():
    """Bo'sh so'rovni yuborib bo'lmaydi."""
    tugmalar = sn.savat_tugmalari([]).inline_keyboard
    hamma = [t.callback_data for qator in tugmalar for t in qator]

    assert any(sn.SAVAT_QOSH in d for d in hamma)
    assert not any(sn.SAVAT_YUBOR in d for d in hamma)


def test_toldirilgan_savatda_YUBORISH_tugmasi_BOR():
    tugmalar = sn.savat_tugmalari(
        [{"bolim": "panjara", "javoblar": {}}]).inline_keyboard
    hamma = [t.callback_data for qator in tugmalar for t in qator]

    assert any(sn.SAVAT_YUBOR in d for d in hamma)


# --- Telefon xotirasi ---------------------------------------------------------


@pytest.mark.asyncio
async def test_aloqa_boshida_YOQ(baza):
    assert await baza.aloqa(TG) is None


@pytest.mark.asyncio
async def test_aloqa_saqlanadi_va_qaytariladi(baza):
    await baza.aloqa_yoz(TG, "+998901234567", "Jasur Karimov")

    yozuv = await baza.aloqa(TG)

    assert yozuv["telefon"] == "+998901234567"
    assert yozuv["ism"] == "Jasur Karimov"


@pytest.mark.asyncio
async def test_raqam_yangilanadi(baza):
    await baza.aloqa_yoz(TG, "+998901234567", "Jasur")
    await baza.aloqa_yoz(TG, "+998907654321", "Jasur")

    assert (await baza.aloqa(TG))["telefon"] == "+998907654321"


@pytest.mark.asyncio
async def test_bosh_ism_eskisini_OCHIRMAYDI(baza):
    """Telegram profilida ism bo'lmasligi mumkin — ilgari yozilgani qolsin."""
    await baza.aloqa_yoz(TG, "+998901234567", "Jasur Karimov")
    await baza.aloqa_yoz(TG, "+998901234567", "")

    assert (await baza.aloqa(TG))["ism"] == "Jasur Karimov"


@pytest.mark.asyncio
async def test_har_mijozning_aloqasi_ALOHIDA(baza):
    await baza.aloqa_yoz(1, "+998901111111", "Bir")
    await baza.aloqa_yoz(2, "+998902222222", "Ikki")

    assert (await baza.aloqa(1))["telefon"] == "+998901111111"
    assert (await baza.aloqa(2))["telefon"] == "+998902222222"


# --- Migratsiya ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_ESKI_bazaga_savat_ustuni_qoshiladi(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` mavjud jadvalga ustun qo'shmaydi."""
    import sqlite3

    yol = tmp_path / "eski.db"
    u = sqlite3.connect(yol)
    u.execute("""CREATE TABLE sorovnoma_holati (
        tg_id TEXT PRIMARY KEY, bolim TEXT NOT NULL, javoblar TEXT NOT NULL,
        yaratildi TEXT NOT NULL, yangilandi TEXT NOT NULL)""")
    u.commit()
    u.close()

    await Baza(yol=yol).tayyorla()

    u = sqlite3.connect(yol)
    ustunlar = {q[1] for q in u.execute("PRAGMA table_info(sorovnoma_holati)")}
    u.close()

    assert "savat" in ustunlar


@pytest.mark.asyncio
async def test_migratsiya_IKKI_MARTA_ishlasa_ham_buzilmaydi(baza):
    await baza.tayyorla()
    await baza.tayyorla()

    assert await sn.savatni_ol(baza, TG) == []


# --- Savatga qo'shilgach shakl YOPILADI ----------------------------------------
#
# JONLI XATO (2026-08-28, 12 bo'limni sinaganda topildi): pozitsiya
# savatga qo'shilgandan keyin o'sha bo'lim shakli OCHIQ qolardi. Mijoz
# tugma o'rniga biror narsa yozsa (masalan "rahmat"), u o'sha bo'limning
# YANGI nusxasiga birinchi javob bo'lib tushardi va jimgina takroriy
# pozitsiya boshlanardi. Sinovda shu tarzda chegaragacha (20 ta)
# pozitsiya to'planib qoldi.


@pytest.mark.asyncio
async def test_savatga_qoshgach_ochiq_shakl_QOLMAYDI(baza):
    await sn.boshla(baza, TG, "ventilyator")
    await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    assert await sn.joriy_shakl(baza, TG) is None


@pytest.mark.asyncio
async def test_shakl_yopilgach_SAVAT_saqlanadi(baza):
    """Shakl yo'q — lekin savat bor. Ikkalasi alohida."""
    await sn.boshla(baza, TG, "ventilyator")
    await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    assert await sn.joriy_shakl(baza, TG) is None
    assert len(await sn.savatni_ol(baza, TG)) == 1


@pytest.mark.asyncio
async def test_yangi_bolim_shaklni_QAYTA_ochadi(baza):
    await sn.boshla(baza, TG, "ventilyator")
    await sn.savatga_qosh(baza, TG, _toldirilgan("ventilyator", VENTILYATOR))

    await sn.boshla(baza, TG, "panjara")

    shakl = await sn.joriy_shakl(baza, TG)
    assert shakl is not None
    assert shakl.bolim_kaliti == "panjara"


@pytest.mark.asyncio
async def test_notanish_bolim_holatni_TOZALAYDI(baza):
    """Bo'lim YAML dan olib tashlangan — eski shakl ishlamaydi."""
    await baza.sorovnoma_holati_yoz(TG, "yoq_bunday", {"a": 1}, [])

    assert await sn.joriy_shakl(baza, TG) is None
    assert await baza.sorovnoma_holati(TG) is None


# --- Uzun xabarni bo'lish -----------------------------------------------------
#
# JONLI XATO (2026-08-28): 12 pozitsiyali savat menejerga yuborilganda
# xabar 3000 belgida QIRQILDI — oxirgi ikki pozitsiya umuman ko'rinmadi
# va menejer buni bilmasdi ham.


def test_qisqa_xabar_BOLINMAYDI():
    assert sn.bolaklarga_boling("qisqa matn", 3000) == ["qisqa matn"]


def test_uzun_xabar_POZITSIYA_chegarasidan_bolinadi():
    pozitsiyalar = "\n".join(
        f"━━ {i}. Bo'lim ━━\n" + "x" * 400 for i in range(1, 11))

    bolaklar = sn.bolaklarga_boling(pozitsiyalar, 1000)

    assert len(bolaklar) > 1
    # Har bo'lak butun pozitsiyalardan iborat — o'rtasidan uzilmagan.
    for b in bolaklar[1:]:
        assert b.lstrip().startswith("━━")


def test_bolishda_hech_narsa_YOQOLMAYDI():
    matn = "\n".join(f"━━ {i}. Bo'lim ━━\nqator {i}" for i in range(1, 13))

    bolaklar = sn.bolaklarga_boling(matn, 200)

    for i in range(1, 13):
        assert f"━━ {i}. Bo'lim ━━" in "\n".join(bolaklar), f"{i} yo'qoldi"


def test_juda_uzun_bitta_pozitsiya_qirqilsa_AYTILADI():
    matn = "━━ 1. Bo'lim ━━\n" + "x" * 5000

    bolaklar = sn.bolaklarga_boling(matn, 500)

    assert len(bolaklar) > 1
    assert any("davomi hujjatda" in b for b in bolaklar)


def test_bolaklar_chekdan_OSHMAYDI():
    matn = "\n".join(f"━━ {i}. Bo'lim ━━\n" + "y" * 300 for i in range(1, 21))

    for b in sn.bolaklarga_boling(matn, 900):
        assert len(b) <= 900


# --- Savatni KO'RISH ----------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-28): savat FAQAT pozitsiya tugagan zahoti bir
# marta ko'rinardi. Mijoz «yana qo'shish» bosib yo'lda adashsa yoki
# xabar yuqoriga surilib ketsa — savatga qaytishning YO'LI YO'Q edi.
# Menyuda ham yo'q edi. To'plangan pozitsiyalar ko'rinmas holda qolib,
# hech qachon yuborilmasdi.


def test_savat_MENYUDA_bor():
    from bot import menyu

    assert "savat" in [nom for nom, _ in menyu.MIJOZ]


def test_savat_buyrugi_ULANGAN():
    import inspect

    from bot import mijoz

    manba = inspect.getsource(mijoz.yasa)
    assert "bot.savat" in manba


@pytest.mark.asyncio
async def test_bosh_savatda_TUSHUNARLI_xabar(baza):
    from bot.mijoz import MijozBot

    bot = MijozBot.__new__(MijozBot)
    bot.baza = baza
    javoblar = []

    class X:
        async def reply_text(self, matn, **k):
            javoblar.append(matn)
            return self

    class U:
        effective_message = X()
        effective_user = type("F", (), {"id": TG})()

    await bot.savat(U(), None)

    assert "bo'sh" in javoblar[0]
    assert "/bolimlar" in javoblar[0]


def test_bolimlar_royxatida_savat_ESLATILADI():
    """Mijoz «yana qo'shish» bosib bu ro'yxatga qaytadi."""
    matn = sn.bolimlar_matni(savat_soni=3)

    assert "3 ta pozitsiya" in matn
    assert "/savat" in matn


def test_bosh_savatda_ROYXAT_toza_qoladi():
    matn = sn.bolimlar_matni(savat_soni=0)

    assert "pozitsiya" not in matn


def test_savat_matnida_QAYTISH_yoli_aytiladi():
    savat = [{"bolim": "panjara", "javoblar": {"model": "РВН", "soni": 14}}]

    assert "/savat" in sn.savat_matni(savat)

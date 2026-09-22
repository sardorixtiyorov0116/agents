"""O'tkazib yuborilgan rejali ishni ushlab qolish.

JONLI MUAMMO: tender tekshiruvi har kuni 09:00 da ishlashi kerak edi,
lekin 7 kunda atigi 2 marta ishladi — qolgan kunlari kompyuter o'chiq
edi. `run_daily` faqat tizim yoqiq bo'lganda ishlaydi va o'tkazib
yuborilgan kun butunlay yo'qoladi.

Endi: soat 11:00 da kompyuter yoqilsa, 09:00 dagi xabar shu zahoti
keladi.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timezone

import pytest

from bot.otkazilgan import bajarilishi_kerakmi, belgila, ushlab_qol

TONG = dt_time(9, 0)


def vaqt(kun: str, soat: int, daqiqa: int = 0) -> datetime:
    y, o, k = (int(x) for x in kun.split("-"))
    return datetime(y, o, k, soat, daqiqa)


# --- kunlik ish (tender) ------------------------------------------------------


def test_kompyuter_kech_yoqilsa_ushlab_qolinadi():
    """ASOSIY HOLAT: 09:00 o'tib ketgan, kompyuter 11:00 da yoqildi."""
    assert bajarilishi_kerakmi(None, TONG, vaqt("2026-08-14", 11)) is True


def test_bugun_bajarilgan_bolsa_takrorlanmaydi():
    """Bir kunda ikki marta xabar kelmasin."""
    assert bajarilishi_kerakmi("2026-08-14", TONG, vaqt("2026-08-14", 11)) is False


def test_vaqti_hali_kelmagan_bolsa_kutadi():
    """Soat 07:00 — 09:00 hali kelmagan, kechagisi bajarilgan."""
    assert bajarilishi_kerakmi("2026-08-13", TONG, vaqt("2026-08-14", 7)) is False


def test_kecha_otkazilgan_bolsa_ushlanadi():
    """Kecha o'chiq edi, bugun ertalab 07:00 da yoqildi."""
    assert bajarilishi_kerakmi("2026-08-12", TONG, vaqt("2026-08-14", 7)) is True


def test_uzoq_tanaffusdan_keyin_bitta_xabar():
    """Kompyuter 2 hafta o'chiq turgan bo'lsa ham 14 ta xabar kelmaydi.

    Faqat ENG OXIRGI belgilangan vaqt ushlanadi — bugungi 09:00.
    """
    assert bajarilishi_kerakmi("2026-08-01", TONG, vaqt("2026-08-14", 11)) is True
    # Va shu zahoti belgilanadi, ya'ni ikkinchi marta ishlamaydi.
    assert bajarilishi_kerakmi("2026-08-14", TONG, vaqt("2026-08-14", 11)) is False


def test_buzuq_sana_yiqitmaydi():
    """Bazada noto'g'ri qiymat bo'lsa ham ish to'xtamasin."""
    assert bajarilishi_kerakmi("axlat", TONG, vaqt("2026-08-14", 11)) is True


# --- haftalik ish (hisobot) ---------------------------------------------------


def test_dushanba_otkazilsa_seshanba_ushlanadi():
    """Dushanba kompyuter o'chiq edi, seshanba yoqildi."""
    # 2026-08-10 — dushanba, 2026-08-11 — seshanba.
    assert bajarilishi_kerakmi(
        None, TONG, vaqt("2026-08-11", 10), hafta_kuni=0,
    ) is True


def test_shu_hafta_yuborilgan_bolsa_takrorlanmaydi():
    assert bajarilishi_kerakmi(
        "2026-08-10", TONG, vaqt("2026-08-11", 10), hafta_kuni=0,
    ) is False


def test_hafta_orasida_hisobot_kutilmaydi():
    """Payshanba — o'tgan dushanbaniki yuborilgan, yangisi kerak emas."""
    assert bajarilishi_kerakmi(
        "2026-08-10", TONG, vaqt("2026-08-13", 15), hafta_kuni=0,
    ) is False


def test_dushanba_ertalab_vaqtidan_oldin():
    """Dushanba 07:00 — hali 09:00 emas, o'tgan haftaniki bajarilgan."""
    assert bajarilishi_kerakmi(
        "2026-08-03", TONG, vaqt("2026-08-10", 7), hafta_kuni=0,
    ) is False


# --- to'liq oqim --------------------------------------------------------------


class SoxtaBaza:
    def __init__(self, oxirgi=None):
        self._oxirgi = oxirgi
        self.yozilgan: list[tuple[str, str]] = []

    async def rejali_ish_kuni(self, nomi):
        return self._oxirgi

    async def rejali_ish_yoz(self, nomi, kun):
        self.yozilgan.append((nomi, kun))


@pytest.mark.asyncio
async def test_otkazilgan_ish_bajariladi_va_belgilanadi():
    baza = SoxtaBaza(oxirgi=None)
    chaqirildi = []

    async def ish(ctx):
        chaqirildi.append(ctx)

    bajarildi = await ushlab_qol(
        baza, "tender-kuzatuvi", ish, "ctx", dt_time(0, 1), kechikish=0,
    )

    assert bajarildi is True
    assert chaqirildi == ["ctx"]
    assert baza.yozilgan and baza.yozilgan[0][0] == "tender-kuzatuvi"


@pytest.mark.asyncio
async def test_bugun_bajarilgan_bolsa_qayta_chaqirilmaydi():
    baza = SoxtaBaza(oxirgi=date.today().isoformat())

    async def ish(ctx):
        raise AssertionError("qayta chaqirilmasligi kerak")

    assert await ushlab_qol(
        baza, "tender-kuzatuvi", ish, "ctx", dt_time(0, 1), kechikish=0,
    ) is False


@pytest.mark.asyncio
async def test_ish_yiqilsa_belgilanmaydi():
    """Xato bo'lsa "bajarildi" deb yozilmasin — keyingi safar qayta urinsin."""
    baza = SoxtaBaza(oxirgi=None)

    async def ish(ctx):
        raise RuntimeError("tarmoq yo'q")

    bajarildi = await ushlab_qol(
        baza, "tender-kuzatuvi", ish, "ctx", dt_time(0, 1), kechikish=0,
    )

    assert bajarildi is False
    assert baza.yozilgan == []


@pytest.mark.asyncio
async def test_baza_yiqilsa_bot_toxtamaydi():
    class Yiqiladigan:
        async def rejali_ish_kuni(self, nomi):
            raise RuntimeError("baza yopiq")

    async def ish(ctx):
        raise AssertionError("chaqirilmasligi kerak")

    assert await ushlab_qol(
        Yiqiladigan(), "tender", ish, "ctx", dt_time(0, 1), kechikish=0,
    ) is False


@pytest.mark.asyncio
async def test_belgila_bazaga_yozadi():
    baza = SoxtaBaza()

    await belgila(baza, "tender-kuzatuvi", date(2026, 8, 14))

    assert baza.yozilgan == [("tender-kuzatuvi", "2026-08-14")]


# --- botga ulanganmi ----------------------------------------------------------


def test_ikkala_ish_ham_ulangan():
    """Ulash unutilmasin — jonli muammo aynan shundan chiqqan edi."""
    import inspect

    import bot.asosiy as modul

    for nomi in ("_kuzatuvni_rejala", "_hisobotni_rejala",
                 "_kurs_tekshiruvini_rejala"):
        manba = inspect.getsource(getattr(modul, nomi))
        assert "otkazilgan.ushlab_qol" in manba, f"{nomi}: ushlab qolish yo'q"

    # Bajarilgan ish belgilanadimi — busiz xabar har ishga tushishda
    # qaytadan kelaveradi.
    for nomi in ("tender_tekshiruvi", "haftalik_hisobot", "kurs_tekshiruvi"):
        manba = inspect.getsource(getattr(modul.Bot, nomi))
        assert "otkazilgan.belgila" in manba, f"{nomi}: belgilanmayapti"


# --- jadval vaqti Toshkent bo'yicha (2026-09-14) -------------------------------
#
# PTB mintaqasiz vaqtni UTC deb oladi: "09:00" tender tekshiruvi 14:00 da,
# "15:00" dagisi 20:00 da ishlardi. Endi vaqt Toshkent mintaqasi bilan
# beriladi — ushlab qolish mantiqi bunda yiqilmasligi SHART (Python
# mintaqali va mintaqasiz vaqtni solishtirmaydi).

from zoneinfo import ZoneInfo  # noqa: E402

TOSHKENT = ZoneInfo("Asia/Tashkent")


def test_mintaqali_vaqt_bilan_solishtirish_yiqilmaydi():
    tong = dt_time(9, 0, tzinfo=TOSHKENT)
    hozir = datetime(2026, 9, 14, 11, 0, tzinfo=TOSHKENT)

    assert bajarilishi_kerakmi(None, tong, hozir) is True
    assert bajarilishi_kerakmi("2026-09-14", tong, hozir) is False


def test_UTC_dagi_hozir_Toshkentga_otkaziladi():
    """04:30 UTC = 09:30 Toshkent — 09:00 lik ish o'tgan hisoblanadi."""
    tong = dt_time(9, 0, tzinfo=TOSHKENT)
    hozir = datetime(2026, 9, 14, 4, 30, tzinfo=timezone.utc)

    assert bajarilishi_kerakmi("2026-09-13", tong, hozir) is True


def test_UTC_da_vaqt_kelmagan_bolsa_kechagi_hisoblanadi():
    """03:30 UTC = 08:30 Toshkent — 09:00 lik ish hali kelmagan."""
    tong = dt_time(9, 0, tzinfo=TOSHKENT)
    hozir = datetime(2026, 9, 14, 3, 30, tzinfo=timezone.utc)

    assert bajarilishi_kerakmi("2026-09-13", tong, hozir) is False


def test_bot_jadval_vaqtlari_TOSHKENT_mintaqasida():
    """Oltita `run_daily` ning hammasi mintaqali vaqt olsin."""
    import inspect

    import bot.asosiy as modul

    vaqt = modul._jadval_vaqti(9, 0)
    assert vaqt.tzinfo is not None
    assert str(vaqt.tzinfo) == "Asia/Tashkent"

    manba = inspect.getsource(modul)
    assert "dt_time(hour=soat, minute=daqiqa)" not in manba, (
        "mintaqasiz jadval vaqti qolib ketgan — u UTC da ishlaydi"
    )

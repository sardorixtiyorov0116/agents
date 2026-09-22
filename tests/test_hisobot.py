"""Davriy hisobot.

Eng muhim talab: RAQAMLAR KODDAN. Hisobot model bilan tuzilsa, bir xil
davr har safar boshqacha chiqadi va unga ishonib bo'lmaydi.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from bot.asosiy import _davrni_oqi
from hisobot import Davr, Hisobot, hisobot_matni, hisobot_yig


def _vaqt(kun_oldin: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=kun_oldin)).isoformat()


@pytest.fixture
async def baza(tmp_path):
    from app.baza import Baza

    b = Baza(tmp_path / "hisobot.db")
    await b.tayyorla()

    with sqlite3.connect(b.yol) as u:
        # Mijoz murojaatlari: 2 tasi shu hafta, 1 tasi eski
        u.executemany(
            "INSERT INTO mijoz_murojaatlari"
            " (vaqt, tg_id, ism, aloqa, savol, javob, sabab, holat)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'yangi')",
            [
                (_vaqt(1), "1", "A", "", "Ombor ventilyatsiyasi hisobi", "javob", None),
                (_vaqt(2), "2", "B", "+998901234567", "+998901234567", None,
                 "mijoz aloqa qoldirdi"),
                (_vaqt(3), "3", "C", "", "Narxi qancha?", None,
                 "mijozga yopiq: proposal-builder"),
                (_vaqt(40), "4", "D", "", "Eski savol", "javob", None),
            ],
        )
        u.executemany(
            "INSERT INTO izlar (vaqt, sorov, reja, qadamlar, yakuniy,"
            " davomiylik_ms, xato) VALUES (?, ?, '{}', '[]', '{}', ?, ?)",
            [
                (_vaqt(1), "so'rov 1", 10000, None),
                (_vaqt(2), "so'rov 2", 20000, "xato bo'ldi"),
                (_vaqt(40), "eski so'rov", 5000, None),
            ],
        )
        u.executemany(
            "INSERT INTO kp_kuzatuv (raqam, mijoz, summa, holat, izoh,"
            " yaratildi, yangilandi) VALUES (?, ?, 0, ?, '', ?, ?)",
            [
                ("KP-1", "A", "yuborildi", _vaqt(2), _vaqt(2)),
                ("KP-2", "B", "shartnoma", _vaqt(3), _vaqt(1)),
                ("KP-3", "C", "yuborildi", _vaqt(40), _vaqt(40)),
            ],
        )
        u.executemany(
            "INSERT INTO tenderlar (kalit, sarlavha, havola, manba, sana,"
            " mosmi, korildi) VALUES (?, ?, '', '', '', ?, ?)",
            [
                ("t1", "Konditsioner xaridi", 1, _vaqt(2)),
                ("t2", "Boshqa narsa", 0, _vaqt(2)),
                ("t3", "Eski", 1, _vaqt(40)),
            ],
        )
    return b


# --- davr chegarasi -----------------------------------------------------------


@pytest.mark.asyncio
async def test_faqat_davr_ichidagi_malumot_olinadi(baza):
    """40 kun oldingi yozuvlar haftalik hisobotga tushmasligi kerak."""
    h = hisobot_yig(baza.yol, Davr.kunlar(7))

    assert h.mijoz_savollari == 3      # 4 tadan biri eski
    assert h.ichki_sorovlar == 2
    assert h.kp_yaratildi == 2
    assert h.tender_korildi == 2


@pytest.mark.asyncio
async def test_uzunroq_davr_kopoq_qamraydi(baza):
    """"2 haftalik hisobot ber" — davr o'zgarsa natija ham o'zgaradi."""
    hafta = hisobot_yig(baza.yol, Davr.kunlar(7))
    oy = hisobot_yig(baza.yol, Davr.kunlar(60))

    assert oy.mijoz_savollari > hafta.mijoz_savollari
    assert oy.ichki_sorovlar > hafta.ichki_sorovlar


# --- hisoblash to'g'rimi ------------------------------------------------------


@pytest.mark.asyncio
async def test_lid_va_javobsiz_ajratiladi(baza):
    """Aloqa qoldirgan — LID; javob berolmagan — muammo. Ikki xil narsa."""
    h = hisobot_yig(baza.yol, Davr.kunlar(7))

    assert h.lidlar == 1
    assert h.javobsiz == 1
    assert h.javob_berildi == 1


@pytest.mark.asyncio
async def test_javobsiz_savollar_royxati(baza):
    """Eng qimmatli bo'lim — bilim bazasiga nima qo'shish kerakligi."""
    h = hisobot_yig(baza.yol, Davr.kunlar(7))

    assert any("Narxi qancha" in s for s in h.javobsiz_savollar)
    # Javob berilgan savol bu ro'yxatga tushmaydi
    assert not any("Ombor" in s for s in h.javobsiz_savollar)


@pytest.mark.asyncio
async def test_mavzular_sanaladi(baza):
    h = hisobot_yig(baza.yol, Davr.kunlar(7))
    mavzular = dict(h.mavzular)

    assert mavzular.get("ventilyatsiya hisobi") == 1
    assert mavzular.get("narx") == 1


@pytest.mark.asyncio
async def test_xato_va_ortacha_vaqt(baza):
    h = hisobot_yig(baza.yol, Davr.kunlar(7))

    assert h.xatolar == 1
    assert h.ortacha_soniya == 15.0     # (10000 + 20000) / 2 / 1000


@pytest.mark.asyncio
async def test_bosh_davrda_yiqilmaydi(baza):
    """Hech narsa bo'lmagan hafta ham hisobot berishi kerak."""
    davr = Davr(
        boshi=datetime.now(timezone.utc) - timedelta(days=400),
        oxiri=datetime.now(timezone.utc) - timedelta(days=390),
        nomi="bo'sh davr",
    )
    h = hisobot_yig(baza.yol, davr)

    assert h.mijoz_savollari == 0
    assert h.javob_foizi == 0.0
    assert "murojaat bo'lmadi" in hisobot_matni(h)


# --- matn ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_matnda_asosiy_raqamlar_bor(baza):
    matn = hisobot_matni(hisobot_yig(baza.yol, Davr.kunlar(7)))

    assert "MIJOZLAR BOTI" in matn
    assert "JAVOB BEROLMAGAN SAVOLLAR" in matn
    assert "TIJORAT TAKLIFI" in matn


# --- matn TUSHUNARLI bo'lishi -------------------------------------------------
#
# Foydalanuvchi aytgan kamchilik: hisobot faqat raqamlar ro'yxati edi.
# "Mos keldi: 0" ni ko'rgan odam bu yomonmi yoki normalmi bilmasdi.


def _hisobot(**maydonlar) -> Hisobot:
    return Hisobot(davr=Davr.kunlar(7), **maydonlar)


def test_har_bolim_nima_ekanini_aytadi():
    """Sarlavha yetarli emas — bo'lim nimani o'lchashini yozish kerak."""
    matn = hisobot_matni(_hisobot())

    assert "mijoz yozadi, tizim javob beradi" in matn
    assert "Mijozga yuborilgan narx takliflari" in matn
    assert "Ochiq xarid e'lonlari avtomatik kuzatiladi" in matn


def test_nol_tender_normal_ekani_aytiladi():
    """"Mos keldi: 0" o'z-o'zidan yomon xabarga o'xshaydi — izoh kerak."""
    matn = hisobot_matni(_hisobot(tender_korildi=4, tender_mos=0))

    assert "odatiy holat" in matn


def test_nol_murojaat_bot_buzilgani_emas():
    matn = hisobot_matni(_hisobot())

    assert "murojaat bo'lmadi" in matn
    assert "Bot ishlayapti" in matn


def test_javobsiz_kp_jami_ekani_aytiladi():
    """25 ta — shu hafta emas, JAMI. Aks holda dahshatli ko'rinadi."""
    matn = hisobot_matni(_hisobot(kp_yaratildi=1, kp_ochiq=25))

    assert "JAMI son" in matn


def test_nima_qilish_royxati_tuziladi():
    """Hisobotning maqsadi — raqam emas, qaror."""
    matn = hisobot_matni(_hisobot(
        tasdiq_kutilmoqda=1, kp_ochiq=25, lidlar=2, mijoz_savollari=3,
    ))

    assert "E'TIBOR BERING" in matn
    assert "/tasdiq" in matn
    assert "qo'ng'iroq qiling" in matn
    assert "mijozlarga eslating" in matn


def test_ish_yoq_bolsa_ochiq_aytiladi():
    """Bo'sh ro'yxat o'rniga aniq jumla — o'quvchi ikkilanmasin."""
    matn = hisobot_matni(_hisobot())

    assert "Shoshilinch ish yo'q" in matn
    assert "E'TIBOR BERING" not in matn


def test_telegram_chegarasidan_oshmaydi():
    """Bot uzun xabarni kesib yuboradi — eng to'la hisobot ham sig'sin."""
    from app.config import sozlama

    matn = hisobot_matni(_hisobot(
        mijoz_savollari=14, javob_berildi=11, lidlar=3, javobsiz=2,
        javobsiz_savollar=[f"Savol {i}" * 5 for i in range(8)],
        mavzular=[("narx", 6), ("montaj", 4), ("kafolat", 3),
                  ("muddat", 2), ("montaj", 1)],
        kp_yaratildi=5, kp_javob_keldi=2, kp_shartnoma=1, kp_ochiq=25,
        tender_korildi=12, tender_mos=2,
        ichki_sorovlar=41, ortacha_soniya=28.9,
        rad_etilgan=2, bajarilmadi=1, tasdiq_kutilmoqda=3,
        xatolar=2, xato_turlari=[("API kaliti yaroqsiz", 2), ("HTTP 500", 1)],
    ))

    assert len(matn) < sozlama().bot_maks_belgi


# --- `/hisobot` argumentlari --------------------------------------------------


@pytest.mark.parametrize(
    "arglar,kutilgan_kun",
    [
        ([], 7),
        (["14"], 14),
        (["30"], 30),
        (["hafta"], 7),
        (["oy"], 30),
        (["kvartal"], 90),
        (["10", "kun"], 10),
        (["chalkash"], 7),        # tushunarsiz — standart
        (["99999"], 365),         # juda uzoq — cheklanadi
        # "14 nima?" degan savol tug'ilmasligi uchun tabiiy shakl ham
        # tushunilishi kerak — bu foydalanuvchi aytgan kamchilik edi.
        (["2", "hafta"], 14),
        (["3", "oy"], 90),
        (["kvartal"], 90),
        (["2", "haftalik"], 14),
    ],
)
def test_davr_argumenti_oqiladi(arglar, kutilgan_kun):
    """"2 haftalik hisobot ber" ham ishlashi kerak edi."""
    davr = _davrni_oqi(arglar)
    kunlar = (davr.oxiri - davr.boshi).days

    assert kunlar == kutilgan_kun


def test_hisobot_modelsiz_ishlaydi():
    """Raqamlar SQL dan keladi — hisobot tekin va takrorlanadigan.

    Model ishlatilsa, bir xil davr har safar boshqacha chiqardi.
    """
    import ast
    import inspect

    import hisobot.yigish as modul

    # Matn qidirish emas, IMPORTLARNI tekshiramiz: modulda "anthropic"
    # so'zi xato matnini tanish uchun ham uchraydi (`ANTHROPIC_API_KEY`),
    # lekin bu model chaqiruvi emas.
    daraxt = ast.parse(inspect.getsource(modul))
    importlar: set[str] = set()
    for tugun in ast.walk(daraxt):
        if isinstance(tugun, ast.Import):
            importlar.update(a.name.split(".")[0] for a in tugun.names)
        elif isinstance(tugun, ast.ImportFrom) and tugun.module:
            importlar.add(tugun.module.split(".")[0])

    for taqiq in ("anthropic", "openai", "app"):
        assert taqiq not in importlar, f"hisobotga model qatlami kirib qolgan: {taqiq}"


# --- xatolarni to'g'ri tasniflash ---------------------------------------------
#
# `izlar.xato` HAR QANDAY muvaffaqiyatsiz yakunni yozadi. Ularning
# hammasini "xato" deb sanash rahbarni chalg'itadi: haqiqiy bazada 19
# ta yozuvdan faqat 7 tasi nosozlik, qolgani tizimning NORMAL ishlashi
# (menejer tasdiqni bermadi, xavfsizlik qoidasi to'sdi).


@pytest.mark.parametrize("matn,guruh", [
    ("Inson rad etdi: sabab ko'rsatilmadi", "rad"),
    ("Bu so'rov rad etildi. Ma'lumotlarni o'chirish qat'iyan taqiqlangan.", "rad"),
    ("Karim kontrakti mavjud, lekin agent hali kodda ulanmagan", "bajarilmadi"),
    ("Buyurtma berish birorta agent kontraktiga kirmaydi", "bajarilmadi"),
    ("KP uchun mahsulot aniqlanmadi.", "bajarilmadi"),
    ("ANTHROPIC_API_KEY yaroqsiz yoki bekor qilingan.", "xato"),
    ("Backend rad etdi (/api/products/update/2): HTTP 500", "xato"),
    ("API xatosi: Error code: 400", "xato"),
])
def test_xato_turi_ajratiladi(matn, guruh):
    from hisobot.yigish import _xato_turi

    assert _xato_turi(matn).guruh == guruh


@pytest.mark.asyncio
async def test_rad_etish_nosozlik_deb_sanalmaydi(baza):
    """Menejer tasdiqni bermasa — bu tizim ishlagani, buzilgani emas."""
    with sqlite3.connect(baza.yol) as u:
        u.executemany(
            "INSERT INTO izlar (vaqt, sorov, reja, qadamlar, yakuniy,"
            " davomiylik_ms, xato) VALUES (?, ?, '{}', '[]', '{}', 100, ?)",
            [
                (_vaqt(1), "KP tayyorla", "Inson rad etdi: sabab ko'rsatilmadi"),
                (_vaqt(1), "hammasini o'chir",
                 "Bu so'rov rad etildi. O'chirish qat'iyan taqiqlangan."),
                (_vaqt(1), "narx", "API xatosi: Error code: 401 API key is invalid"),
            ],
        )

    h = hisobot_yig(baza.yol, Davr.kunlar(7))

    assert h.rad_etilgan == 2
    assert h.xatolar == 2          # oldingi fikstyuradagi 1 ta + yangi 1 ta
    assert any("API kaliti" in nom for nom, _ in h.xato_turlari)


@pytest.mark.asyncio
async def test_nosozlik_turlari_guruhlanadi(baza):
    """"19 ta xato" emas — QAYSI xato ekani ko'rinishi kerak."""
    with sqlite3.connect(baza.yol) as u:
        u.executemany(
            "INSERT INTO izlar (vaqt, sorov, reja, qadamlar, yakuniy,"
            " davomiylik_ms, xato) VALUES (?, 's', '{}', '[]', '{}', 100, ?)",
            [
                (_vaqt(1), "ANTHROPIC_API_KEY yaroqsiz"),
                (_vaqt(1), "ANTHROPIC_API_KEY yaroqsiz"),
                (_vaqt(1), "Backend rad etdi: HTTP 500"),
            ],
        )

    h = hisobot_yig(baza.yol, Davr.kunlar(7))
    turlar = dict(h.xato_turlari)

    assert turlar["API kaliti yaroqsiz"] == 2
    assert turlar["backend 500 qaytardi"] == 1

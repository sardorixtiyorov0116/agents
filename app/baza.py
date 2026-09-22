"""SQLite baza — log (izlar) va narx tarixi.

Boshlanish uchun SQLite; keyinchalik PostgreSQL'ga o'tish mumkin (sxema oddiy).
Barcha yozish/o'qish `asyncio.to_thread` orqali, event loop bloklanmaydi.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import sozlama

log = logging.getLogger("baza")

SXEMA = """
CREATE TABLE IF NOT EXISTS izlar (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt           TEXT NOT NULL,
    sorov          TEXT NOT NULL,
    reja           TEXT,
    qadamlar       TEXT,
    yakuniy        TEXT,
    davomiylik_ms  INTEGER,
    xato           TEXT
);

CREATE TABLE IF NOT EXISTS narxlar (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt      TEXT NOT NULL,
    mahsulot  TEXT NOT NULL,
    bozor     TEXT,
    narx      REAL NOT NULL,
    valyuta   TEXT NOT NULL,
    sana      TEXT,
    manba     TEXT,
    havola    TEXT
);

CREATE INDEX IF NOT EXISTS narxlar_mahsulot ON narxlar (mahsulot, valyuta, id);

CREATE TABLE IF NOT EXISTS raqib_topilmalari (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt      TEXT NOT NULL,
    raqib     TEXT NOT NULL,
    mavzu     TEXT,
    tafsilot  TEXT,
    sana      TEXT,
    manba     TEXT,
    havola    TEXT
);

CREATE INDEX IF NOT EXISTS raqib_topilmalari_raqib ON raqib_topilmalari (raqib, id);

-- Ma'lumot muhandisi Doston so'rov yozadigan ish jadvallari (namunaviy).
CREATE TABLE IF NOT EXISTS mijozlar (
    id       INTEGER PRIMARY KEY,
    ism      TEXT NOT NULL,
    telefon  TEXT,
    shahar   TEXT,
    segment  TEXT
);

CREATE TABLE IF NOT EXISTS buyurtmalar (
    id        INTEGER PRIMARY KEY,
    mijoz_id  INTEGER NOT NULL,
    mahsulot  TEXT NOT NULL,
    miqdor    INTEGER NOT NULL,
    summa     REAL NOT NULL,
    valyuta   TEXT NOT NULL,
    sana      TEXT,
    holat     TEXT
);

CREATE INDEX IF NOT EXISTS buyurtmalar_mijoz ON buyurtmalar (mijoz_id);

-- Tijorat takliflari (KP). Raqam TAKRORLANMASLIGI kafolatlanadi:
-- (yil, tartib) juftligi ustida UNIQUE indeks bor, shuning uchun ikkita
-- bir vaqtdagi so'rov ham bir xil raqam ololmaydi.
CREATE TABLE IF NOT EXISTS kp_raqamlari (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    yil      INTEGER NOT NULL,
    tartib   INTEGER NOT NULL,
    raqam    TEXT NOT NULL UNIQUE,
    vaqt     TEXT NOT NULL,
    iz_id    INTEGER,
    mijoz    TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS kp_yil_tartib ON kp_raqamlari (yil, tartib);

-- KP kuzatuvi: taklif yuborilgandan keyin nima bo'ldi.
-- Tuzilgan KP ning taqdiri kuzatilmasa, ish yarim qoladi — shuning
-- uchun har KP shu yerda holat bilan turadi.
CREATE TABLE IF NOT EXISTS kp_kuzatuv (
    raqam       TEXT PRIMARY KEY,
    mijoz       TEXT,
    summa       REAL,
    holat       TEXT NOT NULL,   -- yuborildi|javob_keldi|shartnoma|rad_etildi
    izoh        TEXT,
    yaratildi   TEXT NOT NULL,
    yangilandi  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS kp_kuzatuv_holat ON kp_kuzatuv (holat);

-- Mijozlar botidan kelgan murojaatlar (lidlar).
-- Bot javob berolmagan yoki mijoz aloqa qoldirgan har savol shu yerda —
-- aks holda murojaat botda qolib ketadi va hech kim ko'rmaydi.
CREATE TABLE IF NOT EXISTS mijoz_murojaatlari (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt      TEXT NOT NULL,
    tg_id     TEXT NOT NULL,
    ism       TEXT,
    aloqa     TEXT,          -- telefon yoki @username
    savol     TEXT NOT NULL,
    javob     TEXT,          -- bot bergan javob (bo'lsa)
    sabab     TEXT,          -- nega menejerga o'tkazildi
    holat     TEXT NOT NULL  -- yangi | korildi
);

CREATE INDEX IF NOT EXISTS mijoz_murojaat_holat
    ON mijoz_murojaatlari (holat, id);

-- LLM sarfi: har bir model chaqiruvi. Bepul tarifdagi kunlik limit real
-- xavf bo'lgani uchun kerak — limitga qancha qolganini OLDINDAN ko'rish.
--
-- `kun` MAHALLIY sana emas: u provayder kvotasi yangilanadigan mintaqa
-- bo'yicha hisoblanadi (`app/sarf.py: kvota_kuni`). Toshkent kuni bilan
-- hisoblansa Google ko'rsatkichi bilan mos kelmasdi.
--
-- `xato` NULL bo'lsa — chaqiruv muvaffaqiyatli.
CREATE TABLE IF NOT EXISTS llm_sarfi (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt       TEXT NOT NULL,
    kun        TEXT NOT NULL,
    provayder  TEXT NOT NULL,
    model      TEXT NOT NULL,
    rol        TEXT,
    kirish     INTEGER NOT NULL DEFAULT 0,
    chiqish    INTEGER NOT NULL DEFAULT 0,
    -- Keshdan o'qilgan tokenlar. ALOHIDA, chunki ular arzon (to'liq
    -- narxning ~10%i) va kirish bilan qo'shilsa xarajat ko'p ko'rinardi.
    keshdan    INTEGER NOT NULL DEFAULT 0,
    ms         INTEGER,
    xato       TEXT
);

CREATE INDEX IF NOT EXISTS llm_sarfi_kun ON llm_sarfi (provayder, kun, id);
CREATE INDEX IF NOT EXISTS llm_sarfi_vaqt ON llm_sarfi (vaqt);

-- HR menejeri Hilola uchun (namunaviy). `maosh` va `telefon` maxfiy:
-- kod ularni hech qachon o'qimaydi, LLM promptiga tushmaydi.
CREATE TABLE IF NOT EXISTS xodimlar (
    id                  INTEGER PRIMARY KEY,
    ism                 TEXT NOT NULL,
    lavozim             TEXT,
    bolim               TEXT,
    ish_boshlagan_sana  TEXT,
    holat               TEXT,
    maosh               REAL,
    telefon             TEXT
);

-- Tasdiq oqimi. Holat XOTIRADA emas, shu yerda saqlanadi — server qayta
-- ishga tushsa ham kutilayotgan tasdiq yo'qolmaydi.
CREATE TABLE IF NOT EXISTS tasdiqlar (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    iz_id         INTEGER NOT NULL,
    qadam_tartib  INTEGER NOT NULL,
    agent         TEXT NOT NULL,
    korinish      TEXT NOT NULL,
    holat         TEXT NOT NULL,          -- kutilmoqda | tasdiqlandi | rad_etildi
    sorov         TEXT,
    izoh          TEXT,
    yaratildi     TEXT NOT NULL,
    hal_qilindi   TEXT,
    qaror_izohi   TEXT
);

CREATE INDEX IF NOT EXISTS tasdiqlar_holat ON tasdiqlar (holat, id);
CREATE UNIQUE INDEX IF NOT EXISTS tasdiqlar_iz ON tasdiqlar (iz_id);

-- KP pastida ko'rsatiladigan savdo menejeri. Bot bir necha xodimda ishlaydi,
-- shuning uchun har kimdan BIR MARTA so'raladi va shu yerda saqlanadi.
CREATE TABLE IF NOT EXISTS menejerlar (
    tg_id       TEXT PRIMARY KEY,
    ism         TEXT NOT NULL,
    telefon     TEXT NOT NULL,
    yangilandi  TEXT NOT NULL
);

-- Ko'rilgan tender e'lonlari. Kuzatuvchi har kuni ishlaydi, shuning uchun
-- bir marta ko'rsatilgan e'lon qayta chiqmasligi kerak.
CREATE TABLE IF NOT EXISTS tenderlar (
    kalit      TEXT PRIMARY KEY,       -- e'lon havolasi (barqaror)
    sarlavha   TEXT NOT NULL,
    havola     TEXT NOT NULL,
    manba      TEXT,
    sana       TEXT,
    mosmi      INTEGER NOT NULL DEFAULT 0,   -- katalogimizga mos kelganmi
    korildi    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS tenderlar_korildi ON tenderlar (korildi);

-- Javob kutayotgan savol. Foydalanuvchi javob yozgach, ASL so'rov shu
-- yerdan olinib davom ettiriladi — aks holda javob kontekstsiz qolardi.
CREATE TABLE IF NOT EXISTS kutilayotgan_savol (
    tg_id      TEXT PRIMARY KEY,
    tur        TEXT NOT NULL,          -- hozircha: menejer
    sorov      TEXT NOT NULL,          -- asl so'rov, javobdan keyin qayta ishlanadi
    yaratildi  TEXT NOT NULL
);

-- KP savol-javob shakli (`/kp`) — yarim to'ldirilgan holat.
--
-- NEGA BAZADA: menejer 5-savolda turganda bot qayta ishga tushsa,
-- xotiradagi holat yo'qolardi va u boshidan boshlashi kerak bo'lardi.
-- Diskda saqlansa — qayerda to'xtagan bo'lsa, o'sha yerdan davom etadi.
--
-- Bir menejerda bir vaqtda BITTA shakl bo'ladi (tg_id — birlamchi kalit).
CREATE TABLE IF NOT EXISTS kp_shakli (
    tg_id      TEXT PRIMARY KEY,
    javoblar   TEXT NOT NULL,          -- JSON: {kalit: qiymat}
    yaratildi  TEXT NOT NULL,
    yangilandi TEXT NOT NULL
);

-- So'rovnoma (oprosniy list) — MIJOZLAR botida to'ldirilayotgani.
--
-- `kp_shakli` dan alohida: u ichki bot menejeriniki, bu esa mijozniki.
-- Bitta jadvalda bo'lsa, menejer KP tuzayotganda mijoz so'rovnomasi
-- ustidan yozib yuborardi (ikkalasi ham `tg_id` bo'yicha).
CREATE TABLE IF NOT EXISTS sorovnoma_holati (
    tg_id      TEXT PRIMARY KEY,
    bolim      TEXT NOT NULL,
    javoblar   TEXT NOT NULL,          -- JSON: {kalit: qiymat}
    -- SAVAT: tugatilgan pozitsiyalar (JSON ro'yxat).
    --
    -- Mijoz bitta uskuna bilan cheklanmaydi: ventilyator ham, panjara
    -- ham, filtr ham kerak bo'lishi mumkin — hatto bitta bo'limdan
    -- BIR NECHA xil o'lchamda. Har biri alohida yuborilsa menejer
    -- bitta obyektning bo'laklarini bog'lay olmasdi.
    savat      TEXT NOT NULL DEFAULT '[]',
    yaratildi  TEXT NOT NULL,
    yangilandi TEXT NOT NULL
);

-- Mijoz aloqasi — BIR MARTA so'raladi va eslab qolinadi.
--
-- Ilgari har so'rovnoma oxirida telefon so'ralardi. Bir mijoz kuniga
-- bir necha pozitsiya so'rasa, u bir xil raqamni qayta-qayta yozardi —
-- bu bezovta qiladi va ba'zilari umuman tashlab ketardi.
CREATE TABLE IF NOT EXISTS mijoz_aloqasi (
    tg_id      TEXT PRIMARY KEY,
    ism        TEXT,
    telefon    TEXT,
    yaratildi  TEXT NOT NULL,
    yangilandi TEXT NOT NULL
);

-- To'ldirilib TUGATILGAN so'rovnomalar.
--
-- Menejerga xabar ketadi, lekin xabar yo'qolishi mumkin (telefon
-- o'chgan, chat tozalangan). Yozuv bazada qoladi va panelda ko'rinadi.
CREATE TABLE IF NOT EXISTS sorovnomalar (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    vaqt     TEXT NOT NULL,
    tg_id    TEXT NOT NULL,
    ism      TEXT,
    aloqa    TEXT,                     -- telefon yoki @username
    bolim    TEXT NOT NULL,
    javoblar TEXT NOT NULL,            -- JSON
    holat    TEXT NOT NULL             -- yangi | korildi
);

CREATE INDEX IF NOT EXISTS sorovnomalar_holat ON sorovnomalar (holat, id);

-- Foydalanuvchi sozlamasi — BIR MARTA so'raladi, keyin eslab qolinadi.
--
-- Ilgari KP tili har safar so'ralardi. Menejer kuniga bir necha KP
-- tuzadi va har safar "ruscha" deb yozishi kerak edi — bu tizimni
-- bezovta qiluvchi qiladi.
-- Rejali ish OXIRGI MARTA qachon bajarilgani.
--
-- NEGA KERAK: tender tekshiruvi har kuni 09:00 da, hisobot dushanba
-- 09:00 da ishga tushadi. Lekin jadval faqat tizim YOQIQ bo'lganda
-- ishlaydi — kompyuter o'chiq bo'lsa o'sha kunlik xabar butunlay
-- yo'qoladi. Jonli o'lchov: tender kuzatuvi 7 kunda atigi 2 marta
-- ishlagan.
--
-- Shu jadval yordamida tizim ishga tushganda "bugungisi bajarildimi?"
-- deb tekshiradi va bajarilmagan bo'lsa DARHOL bajaradi.
CREATE TABLE IF NOT EXISTS rejali_ish (
    nomi       TEXT PRIMARY KEY,
    oxirgi_kun TEXT NOT NULL,      -- YYYY-MM-DD (mahalliy vaqt)
    vaqt       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS foydalanuvchi_sozlamasi (
    tg_id      TEXT PRIMARY KEY,
    kp_tili    TEXT,
    yangilandi TEXT NOT NULL
);

-- Oxirgi tuzilgan KP — TAHRIRLASH uchun.
--
-- Menejer KP ni ko'rgach ko'pincha "1-tovarga 5 mln, 2-tovarga 3 mln"
-- deb yozadi. Busiz tizim YANGI KP tuzardi: yangi raqam, boshqa
-- mahsulotlar, "Mahsulot №2 (nomi ko'rsatilmagan)" kabi qatorlar.
-- Endi o'sha KP ning qatorlari shu yerdan olinadi.
CREATE TABLE IF NOT EXISTS oxirgi_kp (
    tg_id      TEXT PRIMARY KEY,
    raqam      TEXT NOT NULL,
    malumot    TEXT NOT NULL,          -- KP JSON (qatorlar, mijoz, til…)
    yaratildi  TEXT NOT NULL
);

-- SUHBAT KONTEKSTI — agent aniqlashtirish so'raganda saqlanadi.
--
-- Busiz shunday bo'lardi:
--   mijoz: "Ofis uchun ventilyatsiya, 120 kv metr"
--   bot:   "Balandligi qancha? Necha kishi?"
--   mijoz: "3 metr, 15 kishi"
--   bot:   "Xona maydoni qancha?"      <- 120 m² unutilgan, cheksiz halqa
--
-- Endi asl so'rov shu yerda turadi va javob kelganda ular birlashtiriladi.
-- `kanal` kerak: bir odam ikkala botga yozishi mumkin, suhbatlar
-- aralashib ketmasligi kerak.
CREATE TABLE IF NOT EXISTS suhbat_konteksti (
    kanal      TEXT NOT NULL,          -- mijoz | ichki
    tg_id      TEXT NOT NULL,
    sorov      TEXT NOT NULL,          -- to'plangan so'rov
    savollar   TEXT,                   -- agent so'ragan savollar
    qadam      INTEGER NOT NULL DEFAULT 1,
    yangilandi TEXT NOT NULL,
    PRIMARY KEY (kanal, tg_id)
);
"""

# Suhbat konteksti shundan keyin eskiradi (soniya).
#
# 8 soat — bitta ish kuni. Menejer ertalab KP so'rab, tushdan keyin
# narxni aytishi mumkin va tizim uni eslashi kerak. Ertaga yozilgan
# xabar esa kechagi so'rovga yopishib qolmaydi.
SUHBAT_MUDDATI = 8 * 60 * 60

# Suhbat necha marta uzaytiriladi. Chegarasiz qo'yilsa, so'rov matni
# cheksiz o'sib, har chaqiruvda ko'proq token yeydi. Uzunlik chegarasi
# (`suhbat.MAKS_UZUNLIK`) ham himoya bo'lib turadi.
SUHBAT_MAKS_QADAM = 12

# Bitta agent so'rovining maksimal ijro vaqti (sekund).
SOROV_MUDDATI = 5.0

# Doston faqat shu jadvallarni ko'radi. Ro'yxatdan tashqarisi — `izlar`,
# `narxlar` kabi tizim jadvallari ham — avtorizator darajasida rad etiladi.
RUXSAT_ETILGAN_JADVALLAR = frozenset({"mijozlar", "buyurtmalar"})

# So'rovda ishlatilishi mumkin bo'lgan funksiyalar. Ro'yxat ataylab qisqa:
# `load_extension` kabi narsalar hech qachon ochilmaydi.
XAVFSIZ_FUNKSIYALAR = frozenset(
    {
        "abs", "avg", "coalesce", "count", "date", "datetime", "group_concat",
        "ifnull", "instr", "julianday", "length", "lower", "ltrim", "max", "min",
        "nullif", "printf", "quote", "random", "replace", "round", "rtrim",
        "strftime", "substr", "sum", "time", "total", "trim", "typeof", "upper",
    }
)

NAMUNAVIY_MIJOZLAR = [
    (1, "Alisher Karimov", "+998901112233", "Toshkent", "korporativ"),
    (2, "Nodira Yusupova", "+998931234567", "Toshkent", "jismoniy"),
    (3, "Bekzod Rahimov", "+998977778899", "Samarqand", "jismoniy"),
    (4, '"Oqtepa Lavash" MChJ', "+998712001020", "Toshkent", "korporativ"),
    (5, "Dilnoza Sobirova", "+998909998877", "Buxoro", "jismoniy"),
]

# Hilola FAQAT shu maydonlarni ko'radi. `maosh` va `telefon` ataylab yo'q —
# cheklov promptda emas, shu ro'yxatda (kontrakt: "cheklangan o'qish").
HR_RUXSAT_ETILGAN_MAYDONLAR = ("id", "ism", "lavozim", "bolim", "ish_boshlagan_sana", "holat")

NAMUNAVIY_XODIMLAR = [
    (1, "Aziza Tosheva", "Sotuv menejeri", "Sotuv", "2023-03-15", "faol", 9_500_000.0, "+998901234501"),
    (2, "Jamshid Ergashev", "Dasturchi", "IT", "2022-09-01", "faol", 18_000_000.0, "+998901234502"),
    (3, "Malika Norova", "Buxgalter", "Moliya", "2021-01-20", "faol", 11_000_000.0, "+998901234503"),
    (4, "Sanjar Qodirov", "Omborchi", "Logistika", "2024-06-10", "faol", 6_800_000.0, "+998901234504"),
    (5, "Nigora Ismoilova", "Sotuv menejeri", "Sotuv", "2024-11-05", "ta'tilda", 8_900_000.0, "+998901234505"),
    (6, "Otabek Rasulov", "Dasturchi", "IT", "2025-02-17", "faol", 15_500_000.0, "+998901234506"),
]

NAMUNAVIY_BUYURTMALAR = [
    (1, 1, "Konditsioner Artel 12", 4, 18_000_000.0, "UZS", "2026-06-14", "yakunlandi"),
    (2, 2, "Muzlatgich Samsung RB37", 1, 9_500_000.0, "UZS", "2026-06-21", "yakunlandi"),
    (3, 3, "Smartfon Redmi Note 13", 2, 4_800_000.0, "UZS", "2026-07-02", "yakunlandi"),
    (4, 1, "Kir yuvish mashinasi LG", 2, 11_200_000.0, "UZS", "2026-07-09", "yo'lda"),
    (5, 4, "Konditsioner Artel 09", 6, 24_600_000.0, "UZS", "2026-07-15", "yo'lda"),
    (6, 5, "Changyutgich Philips", 1, 2_300_000.0, "UZS", "2026-07-18", "bekor qilindi"),
    (7, 2, "Televizor Artel 55", 1, 7_400_000.0, "UZS", "2026-07-22", "yangi"),
    (8, 4, "Muzlatgich Artel HD", 3, 21_000_000.0, "UZS", "2026-07-25", "yangi"),
]


def _hozir() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Doston uchun avtorizator -----------------------------------------------
#
# Bu SQLite'ning o'z darajasidagi himoyasi: har bir amal bajarilishidan OLDIN
# shu funksiya chaqiriladi va rad etilgan amal umuman ishga tushmaydi. SQL
# matnini o'qib tekshirishga (regex, kalit so'z qidirish) tayanmaydi — shuning
# uchun uni prompt bilan ham, chalkash SQL bilan ham aylanib o'tib bo'lmaydi.


def _oqishga_ruxsat(amal: int, arg1: str | None, arg2: str | None) -> int:
    """O'qish amallari: faqat ruxsat etilgan jadvallardan SELECT."""
    if amal == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if amal == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 in RUXSAT_ETILGAN_JADVALLAR else sqlite3.SQLITE_DENY
    if amal == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK if (arg2 or "").lower() in XAVFSIZ_FUNKSIYALAR else sqlite3.SQLITE_DENY
    # Qolgan hamma narsa — DELETE, DROP, ALTER, ATTACH, PRAGMA va h.k. — yo'q.
    return sqlite3.SQLITE_DENY


def faqat_oqish_avtorizatori(
    amal: int, arg1: str | None, arg2: str | None, dbnomi: str | None, tetik: str | None
) -> int:
    return _oqishga_ruxsat(amal, arg1, arg2)


def yozish_avtorizatori(
    amal: int, arg1: str | None, arg2: str | None, dbnomi: str | None, tetik: str | None
) -> int:
    """Yozish amallari: faqat INSERT/UPDATE, faqat ruxsat etilgan jadvallarga.

    DELETE / DROP / TRUNCATE / ALTER bu yerda ham ochilmaydi — tasdiqlangan
    yozish so'rovi ham ma'lumotni o'chira olmaydi.
    """
    if amal in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE):
        return sqlite3.SQLITE_OK if arg1 in RUXSAT_ETILGAN_JADVALLAR else sqlite3.SQLITE_DENY
    if amal == sqlite3.SQLITE_TRANSACTION:
        # Python sqlite3 yozishdan oldin BEGIN/COMMIT yuboradi.
        return sqlite3.SQLITE_OK
    return _oqishga_ruxsat(amal, arg1, arg2)


class Baza:
    """Juda yupqa SQLite qatlami."""

    def __init__(self, yol: Path | None = None):
        self.yol = yol or sozlama().baza_fayli

    def _ulanish(self) -> sqlite3.Connection:
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        ulanish = sqlite3.connect(self.yol, timeout=10)
        ulanish.row_factory = sqlite3.Row
        return ulanish

    # --- sinxron ichki metodlar ---------------------------------------------

    def _agent_ulanishi(self, yozish: bool) -> sqlite3.Connection:
        """Doston uchun cheklangan ulanish.

        Ikki qatlamli himoya: o'qish rejimida baza SQLite darajasida `mode=ro`
        bilan ochiladi (yozish jismonan imkonsiz), ustiga avtorizator qo'yiladi.
        """
        if yozish:
            ulanish = sqlite3.connect(self.yol, timeout=10)
            ulanish.set_authorizer(yozish_avtorizatori)
        else:
            ulanish = sqlite3.connect(f"file:{self.yol.as_posix()}?mode=ro", uri=True, timeout=10)
            ulanish.set_authorizer(faqat_oqish_avtorizatori)

        # Og'ir so'rov (masalan katta dekart ko'paytmasi) tizimni osib
        # qo'ymasligi uchun qat'iy vaqt chegarasi.
        muddat = time.monotonic() + SOROV_MUDDATI
        ulanish.set_progress_handler(lambda: int(time.monotonic() > muddat), 10_000)

        ulanish.row_factory = sqlite3.Row
        return ulanish

    # Keyin qo'shilgan ustunlar: (jadval, ustun, ta'rif).
    #
    # `CREATE TABLE IF NOT EXISTS` mavjud jadvalga ustun QO'SHMAYDI —
    # jadval bor bo'lsa u butunlay o'tkazib yuboriladi. Shuning uchun
    # yangi ustun shu ro'yxatga yoziladi va har ishga tushganda
    # tekshiriladi.
    YANGI_USTUNLAR: tuple[tuple[str, str, str], ...] = (
        ("sorovnoma_holati", "savat", "TEXT NOT NULL DEFAULT '[]'"),
        ("llm_sarfi", "keshdan", "INTEGER NOT NULL DEFAULT 0"),
    )

    def _tayyorla(self) -> None:
        with self._ulanish() as u:
            u.executescript(SXEMA)
            self._ustunlarni_moslash(u)
            self._urugla(u)

    @classmethod
    def _ustunlarni_moslash(cls, u: sqlite3.Connection) -> None:
        """Eski bazaga yangi ustunlarni qo'shadi."""
        for jadval, ustun, tarif in cls.YANGI_USTUNLAR:
            mavjud = {q["name"] for q in
                      u.execute(f"PRAGMA table_info({jadval})").fetchall()}
            if not mavjud:                      # jadval umuman yo'q
                continue
            if ustun in mavjud:
                continue
            u.execute(f"ALTER TABLE {jadval} ADD COLUMN {ustun} {tarif}")
            log.info("baza: %s.%s ustuni qo'shildi", jadval, ustun)

    @staticmethod
    def _urugla(u: sqlite3.Connection) -> None:
        """Namunaviy ish ma'lumoti — faqat jadval bo'sh bo'lsa."""
        if not u.execute("SELECT 1 FROM mijozlar LIMIT 1").fetchone():
            u.executemany("INSERT INTO mijozlar VALUES (?, ?, ?, ?, ?)", NAMUNAVIY_MIJOZLAR)
        if not u.execute("SELECT 1 FROM buyurtmalar LIMIT 1").fetchone():
            u.executemany(
                "INSERT INTO buyurtmalar VALUES (?, ?, ?, ?, ?, ?, ?, ?)", NAMUNAVIY_BUYURTMALAR
            )
        if not u.execute("SELECT 1 FROM xodimlar LIMIT 1").fetchone():
            u.executemany("INSERT INTO xodimlar VALUES (?, ?, ?, ?, ?, ?, ?, ?)", NAMUNAVIY_XODIMLAR)

    def _xodimlar(self, bolim: str | None) -> list[dict[str, Any]]:
        """Hilola uchun xodimlar ro'yxati — FAQAT ruxsat etilgan maydonlar.

        Ustunlar ro'yxati kodda qat'iy belgilangan: `maosh` va `telefon` bu
        yerdan chiqmaydi, demak LLM promptiga ham hech qachon tushmaydi.
        """
        ustunlar = ", ".join(HR_RUXSAT_ETILGAN_MAYDONLAR)
        sql = f"SELECT {ustunlar} FROM xodimlar"
        parametrlar: tuple[Any, ...] = ()
        if bolim:
            sql += " WHERE bolim = ?"
            parametrlar = (bolim,)
        sql += " ORDER BY id"

        with self._ulanish() as u:
            qatorlar = u.execute(sql, parametrlar).fetchall()
        return [dict(q) for q in qatorlar]

    def _jadval_sxemasi(self) -> str:
        """Ruxsat etilgan jadvallar tuzilmasi — Dostonning promptiga beriladi.

        Bazadan o'qiladi, qo'lda yozilmaydi: sxema o'zgarsa prompt ham o'zgaradi.
        """
        qatorlar: list[str] = []
        with self._ulanish() as u:
            for jadval in sorted(RUXSAT_ETILGAN_JADVALLAR):
                ustunlar = u.execute(f"PRAGMA table_info({jadval})").fetchall()
                tavsif = ", ".join(f"{q['name']} {q['type']}" for q in ustunlar)
                qatorlar.append(f"{jadval}({tavsif})")
        return "\n".join(qatorlar)

    def _sorov_bajar(self, sql: str, yozish: bool) -> list[dict[str, Any]]:
        """Bitta SQL so'rovini cheklangan ulanishda bajaradi.

        `execute` bitta statement bilan cheklangan — nuqta-vergul bilan
        ikkinchi buyruq qo'shib yuborib bo'lmaydi.
        """
        ulanish = self._agent_ulanishi(yozish)
        try:
            with ulanish:
                qatorlar = ulanish.execute(sql).fetchall()
            return [dict(q) for q in qatorlar]
        finally:
            ulanish.close()

    def _iz_yoz(self, yozuv: dict[str, Any]) -> int:
        with self._ulanish() as u:
            kursor = u.execute(
                "INSERT INTO izlar (vaqt, sorov, reja, qadamlar, yakuniy, davomiylik_ms, xato)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _hozir(),
                    yozuv["sorov"],
                    json.dumps(yozuv.get("reja"), ensure_ascii=False),
                    json.dumps(yozuv.get("qadamlar"), ensure_ascii=False),
                    json.dumps(yozuv.get("yakuniy"), ensure_ascii=False),
                    yozuv.get("davomiylik_ms"),
                    yozuv.get("xato"),
                ),
            )
            return int(kursor.lastrowid or 0)

    def _izlar(self, chek: int) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT * FROM izlar ORDER BY id DESC LIMIT ?", (chek,)
            ).fetchall()
        return [self._iz_ochir(q) for q in qatorlar]

    def _iz(self, iz_id: int) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute("SELECT * FROM izlar WHERE id = ?", (iz_id,)).fetchone()
        return self._iz_ochir(qator) if qator else None

    @staticmethod
    def _iz_ochir(qator: sqlite3.Row) -> dict[str, Any]:
        yozuv = dict(qator)
        for kalit in ("reja", "qadamlar", "yakuniy"):
            xom = yozuv.get(kalit)
            try:
                yozuv[kalit] = json.loads(xom) if xom else None
            except (TypeError, json.JSONDecodeError):
                yozuv[kalit] = None
        return yozuv

    def _iz_boshla(self, sorov: str, reja: Any) -> int:
        """So'rov boshida iz ochadi: `yakuniy` bo'sh = hali ishlayapti.

        Panel shu yozuvni ko'rib zanjirni jonli ko'rsatadi.
        """
        with self._ulanish() as u:
            kursor = u.execute(
                "INSERT INTO izlar (vaqt, sorov, reja, qadamlar, yakuniy) VALUES (?, ?, ?, '[]', NULL)",
                (_hozir(), sorov, json.dumps(reja, ensure_ascii=False)),
            )
            return int(kursor.lastrowid or 0)

    def _iz_qadamlarni_yangila(self, iz_id: int, qadamlar: list[Any]) -> None:
        """Har qadamdan keyin chaqiriladi — jonli ko'rinish uchun."""
        with self._ulanish() as u:
            u.execute(
                "UPDATE izlar SET qadamlar = ? WHERE id = ?",
                (json.dumps(qadamlar, ensure_ascii=False), iz_id),
            )

    def _iz_yangila(self, iz_id: int, yozuv: dict[str, Any]) -> None:
        """Tasdiqdan keyin davom etgan so'rovning izini yangilaydi."""
        with self._ulanish() as u:
            u.execute(
                "UPDATE izlar SET qadamlar = ?, yakuniy = ?, davomiylik_ms = ?, xato = ?"
                " WHERE id = ?",
                (
                    json.dumps(yozuv.get("qadamlar"), ensure_ascii=False),
                    json.dumps(yozuv.get("yakuniy"), ensure_ascii=False),
                    yozuv.get("davomiylik_ms"),
                    yozuv.get("xato"),
                    iz_id,
                ),
            )

    # --- KP raqamlari -------------------------------------------------------

    def _kp_raqam_ol(
        self,
        mijoz: str | None,
        iz_id: int | None,
        shakl: str = "KP-{yil}-{tartib:04d}",
        boshlanish: int = 0,
    ) -> str:
        """Yangi KP raqamini ajratadi.

        `shakl` — rekvizitlardan keladi (namunaviy KP da `12951/6`).
        `boshlanish` — mavjud qog'oz raqamlari bilan davom etish uchun.

        Takrorlanmaslik UNIQUE indeks bilan kafolatlangan: bir vaqtda ikkita
        so'rov kelsa, biri xato oladi va keyingi tartibni sinaydi.
        """
        hozir = datetime.now(timezone.utc)
        yil = hozir.year
        with self._ulanish() as u:
            for _ in range(50):
                qator = u.execute(
                    "SELECT coalesce(max(tartib), 0) AS oxirgi FROM kp_raqamlari WHERE yil = ?",
                    (yil,),
                ).fetchone()
                tartib = max(int(qator["oxirgi"]), boshlanish - 1) + 1
                try:
                    raqam = shakl.format(
                        tartib=tartib, yil=yil, qisqa_yil=yil % 100, oy=hozir.month
                    )
                except (KeyError, IndexError, ValueError):
                    raqam = f"KP-{yil}-{tartib:04d}"
                try:
                    u.execute(
                        "INSERT INTO kp_raqamlari (yil, tartib, raqam, vaqt, iz_id, mijoz)"
                        " VALUES (?, ?, ?, ?, ?, ?)",
                        (yil, tartib, raqam, _hozir(), iz_id, mijoz),
                    )
                    return raqam
                except sqlite3.IntegrityError:
                    continue  # boshqa so'rov shu raqamni oldi — keyingisini sinaymiz
        raise RuntimeError("KP raqamini ajratib bo'lmadi")

    def _kp_royxati(self, chek: int) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT * FROM kp_raqamlari ORDER BY id DESC LIMIT ?", (chek,)
            ).fetchall()
        return [dict(q) for q in qatorlar]

    # --- KP kuzatuvi ----------------------------------------------------------

    # Ruxsat etilgan holatlar. Boshqa qiymat yozilmaydi — statistika
    # buzilmasligi uchun.
    KP_HOLATLARI = ("yuborildi", "javob_keldi", "shartnoma", "rad_etildi")

    def _kp_kuzatuv_yoz(
        self,
        raqam: str,
        mijoz: str | None,
        summa: float | None,
        yaratildi: str | None,
    ) -> None:
        """Yangi KP ni kuzatuvga qo'yadi (mavjud bo'lsa tegmaydi).

        `yaratildi` — KP ning HAQIQIY sanasi. Eski KP larni ko'chirganda
        bugungi sana qo'yilsa, "necha kun javob yo'q" hisobi buziladi.
        """
        hozir = datetime.now(timezone.utc).isoformat(timespec="seconds")
        boshlangan = yaratildi or hozir
        with self._ulanish() as u:
            u.execute(
                """INSERT INTO kp_kuzatuv
                       (raqam, mijoz, summa, holat, izoh, yaratildi, yangilandi)
                   VALUES (?, ?, ?, 'yuborildi', '', ?, ?)
                   ON CONFLICT(raqam) DO NOTHING""",
                (raqam, mijoz, summa, boshlangan, hozir),
            )

    def _kp_holat_yoz(self, raqam: str, holat: str, izoh: str) -> bool:
        """Holatni yangilaydi. KP topilmasa `False`."""
        if holat not in self.KP_HOLATLARI:
            raise ValueError(f"noma'lum holat: {holat}")
        hozir = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._ulanish() as u:
            natija = u.execute(
                """UPDATE kp_kuzatuv
                      SET holat = ?, izoh = ?, yangilandi = ?
                    WHERE raqam = ?""",
                (holat, izoh, hozir, raqam),
            )
            return natija.rowcount > 0

    def _kp_kuzatuv(self, holat: str | None, chek: int) -> list[dict[str, Any]]:
        shart = "WHERE holat = ?" if holat else ""
        parametrlar: tuple[Any, ...] = (holat, chek) if holat else (chek,)
        with self._ulanish() as u:
            qatorlar = u.execute(
                f"""SELECT * FROM kp_kuzatuv {shart}
                    ORDER BY yaratildi DESC LIMIT ?""",
                parametrlar,
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _javobsiz_kplar(self, kun: int, chek: int) -> list[dict[str, Any]]:
        """Yuborilgan, lekin `kun` kundan beri javobsiz KP lar.

        SOF KOD — modelga berilmaydi. Bu ro'yxat eslatma uchun ishlatiladi
        va unda XATO BO'LMASLIGI kerak: yo'q KP eslatilsa menejer ishonchni
        yo'qotadi, bor KP tushib qolsa — savdo yo'qoladi.

        Sana solishtiruvi MATN darajasida: `yaratildi` ISO formatda
        saqlanadi (`2026-08-15`), shuning uchun leksik taqqoslash
        xronologik taqqoslash bilan bir xil natija beradi.
        """
        chegara = (
            datetime.now(timezone.utc).date() - timedelta(days=max(kun, 0))
        ).isoformat()
        with self._ulanish() as u:
            qatorlar = u.execute(
                """SELECT * FROM kp_kuzatuv
                   WHERE holat = 'yuborildi' AND substr(yaratildi, 1, 10) <= ?
                   ORDER BY yaratildi ASC LIMIT ?""",
                (chegara, chek),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _kp_xulosasi(self) -> dict[str, Any]:
        """Konversiya: nechta yuborildi, nechta shartnomaga aylandi."""
        with self._ulanish() as u:
            sanoq = {
                q["holat"]: q["soni"]
                for q in u.execute(
                    "SELECT holat, COUNT(*) AS soni FROM kp_kuzatuv GROUP BY holat"
                ).fetchall()
            }
            summa = u.execute(
                "SELECT COALESCE(SUM(summa), 0) AS s FROM kp_kuzatuv "
                "WHERE holat = 'shartnoma'"
            ).fetchone()["s"]
        jami = sum(sanoq.values())
        shartnoma = sanoq.get("shartnoma", 0)
        return {
            "jami": jami,
            "holatlar": sanoq,
            "shartnoma_summasi": float(summa or 0),
            # Konversiya — javobsizlar ham maxrajda: ular ham yuborilgan.
            "konversiya": round(shartnoma / jami * 100, 1) if jami else 0.0,
        }

    # --- mijoz murojaatlari ---------------------------------------------------

    def _murojaat_yoz(self, yozuv: dict[str, Any]) -> int:
        with self._ulanish() as u:
            kursor = u.execute(
                """INSERT INTO mijoz_murojaatlari
                       (vaqt, tg_id, ism, aloqa, savol, javob, sabab, holat)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'yangi')""",
                (
                    _hozir(),
                    str(yozuv.get("tg_id") or ""),
                    yozuv.get("ism"),
                    yozuv.get("aloqa"),
                    yozuv.get("savol") or "",
                    yozuv.get("javob"),
                    yozuv.get("sabab"),
                ),
            )
            return int(kursor.lastrowid or 0)

    def _murojaatlar(self, holat: str | None, chek: int) -> list[dict[str, Any]]:
        shart = "WHERE holat = ?" if holat else ""
        parametrlar: tuple[Any, ...] = (holat, chek) if holat else (chek,)
        with self._ulanish() as u:
            qatorlar = u.execute(
                f"SELECT * FROM mijoz_murojaatlari {shart} "
                f"ORDER BY id DESC LIMIT ?",
                parametrlar,
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _murojaat_bormi(self, tg_id: Any) -> bool:
        """Bu odam ilgari yozganmi (yangi mijozni ajratish uchun)."""
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT 1 FROM mijoz_murojaatlari WHERE tg_id = ? LIMIT 1",
                (str(tg_id),),
            ).fetchone()
        return qator is not None

    def _murojaat_korildi(self, murojaat_id: int) -> bool:
        with self._ulanish() as u:
            natija = u.execute(
                "UPDATE mijoz_murojaatlari SET holat = 'korildi' WHERE id = ?",
                (murojaat_id,),
            )
            return natija.rowcount > 0

    # --- menejerlar va javob kutayotgan savollar ------------------------------

    def _menejer(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT ism, telefon FROM menejerlar WHERE tg_id = ?", (str(tg_id),)
            ).fetchone()
        return dict(qator) if qator else None

    def _menejer_yoz(self, tg_id: Any, ism: str, telefon: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO menejerlar (tg_id, ism, telefon, yangilandi)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " ism = excluded.ism, telefon = excluded.telefon,"
                " yangilandi = excluded.yangilandi",
                (str(tg_id), ism, telefon, _hozir()),
            )

    def _menejer_ochir(self, tg_id: Any) -> None:
        with self._ulanish() as u:
            u.execute("DELETE FROM menejerlar WHERE tg_id = ?", (str(tg_id),))

    # --- suhbat konteksti ----------------------------------------------------

    # --- foydalanuvchi sozlamasi --------------------------------------------

    def _sozlama_yoz(self, tg_id: Any, kp_tili: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO foydalanuvchi_sozlamasi (tg_id, kp_tili, yangilandi)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " kp_tili = excluded.kp_tili, yangilandi = excluded.yangilandi",
                (str(tg_id), kp_tili, _hozir()),
            )

    def _foydalanuvchi_sozlamasi(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT kp_tili FROM foydalanuvchi_sozlamasi WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        return dict(qator) if qator else None

    # --- oxirgi KP (tahrirlash uchun) ---------------------------------------

    def _oxirgi_kp_yoz(self, tg_id: Any, raqam: str, malumot: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO oxirgi_kp (tg_id, raqam, malumot, yaratildi)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " raqam = excluded.raqam, malumot = excluded.malumot,"
                " yaratildi = excluded.yaratildi",
                (str(tg_id), raqam, malumot, _hozir()),
            )

    def _oxirgi_kp(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT raqam, malumot, yaratildi FROM oxirgi_kp WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        return dict(qator) if qator else None

    def _suhbat_yoz(
        self, kanal: str, tg_id: Any, sorov: str, savollar: str, qadam: int
    ) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO suhbat_konteksti"
                " (kanal, tg_id, sorov, savollar, qadam, yangilandi)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(kanal, tg_id) DO UPDATE SET"
                " sorov = excluded.sorov, savollar = excluded.savollar,"
                " qadam = excluded.qadam, yangilandi = excluded.yangilandi",
                (kanal, str(tg_id), sorov, savollar, qadam, _hozir()),
            )

    def _suhbat(self, kanal: str, tg_id: Any) -> dict[str, Any] | None:
        """Eskirgan kontekst QAYTARILMAYDI va darhol o'chiriladi.

        Aks holda ertaga yozilgan xabar kechagi so'rovga yopishib qolardi.
        """
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT sorov, savollar, qadam, yangilandi FROM suhbat_konteksti"
                " WHERE kanal = ? AND tg_id = ?",
                (kanal, str(tg_id)),
            ).fetchone()
        if qator is None:
            return None

        try:
            vaqt = datetime.fromisoformat(qator["yangilandi"])
        except ValueError:
            vaqt = None
        eskirgan = (
            vaqt is None
            or (datetime.now(timezone.utc) - vaqt).total_seconds() > SUHBAT_MUDDATI
            or qator["qadam"] >= SUHBAT_MAKS_QADAM
        )
        if eskirgan:
            self._suhbat_ochir(kanal, tg_id)
            return None
        return dict(qator)

    def _suhbat_ochir(self, kanal: str, tg_id: Any) -> None:
        with self._ulanish() as u:
            u.execute(
                "DELETE FROM suhbat_konteksti WHERE kanal = ? AND tg_id = ?",
                (kanal, str(tg_id)),
            )

    def _savol_yoz(self, tg_id: Any, tur: str, sorov: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO kutilayotgan_savol (tg_id, tur, sorov, yaratildi)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " tur = excluded.tur, sorov = excluded.sorov,"
                " yaratildi = excluded.yaratildi",
                (str(tg_id), tur, sorov, _hozir()),
            )

    def _savol(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT tur, sorov, yaratildi FROM kutilayotgan_savol WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        return dict(qator) if qator else None

    def _savol_ochir(self, tg_id: Any) -> None:
        with self._ulanish() as u:
            u.execute("DELETE FROM kutilayotgan_savol WHERE tg_id = ?", (str(tg_id),))

    # --- KP shakli (/kp) ------------------------------------------------------

    def _kp_shakli_yoz(self, tg_id: Any, javoblar: dict[str, Any]) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO kp_shakli (tg_id, javoblar, yaratildi, yangilandi)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " javoblar = excluded.javoblar, yangilandi = excluded.yangilandi",
                (str(tg_id), json.dumps(javoblar, ensure_ascii=False),
                 _hozir(), _hozir()),
            )

    def _kp_shakli(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT javoblar, yaratildi FROM kp_shakli WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        if not qator:
            return None
        try:
            javoblar = json.loads(qator["javoblar"])
        except ValueError:
            # Buzuq JSON — shaklni yo'qotgandan ko'ra qaytadan boshlagan afzal.
            log.warning("kp_shakli buzuq JSON: id=%s", tg_id)
            return None
        return {"javoblar": javoblar, "yaratildi": qator["yaratildi"]}

    def _kp_shakli_ochir(self, tg_id: Any) -> None:
        with self._ulanish() as u:
            u.execute("DELETE FROM kp_shakli WHERE tg_id = ?", (str(tg_id),))

    # --- tenderlar ------------------------------------------------------------

    def _korilgan_tenderlar(self, kalitlar: list[str]) -> set[str]:
        if not kalitlar:
            return set()
        oyna = ",".join("?" * len(kalitlar))
        with self._ulanish() as u:
            qatorlar = u.execute(
                f"SELECT kalit FROM tenderlar WHERE kalit IN ({oyna})", kalitlar
            ).fetchall()
        return {q["kalit"] for q in qatorlar}

    def _tender_yoz(self, yozuvlar: list[dict[str, Any]]) -> int:
        if not yozuvlar:
            return 0
        hozir = _hozir()
        with self._ulanish() as u:
            kursor = u.executemany(
                "INSERT OR IGNORE INTO tenderlar"
                " (kalit, sarlavha, havola, manba, sana, mosmi, korildi)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        y["kalit"], y["sarlavha"], y["havola"],
                        y.get("manba"), y.get("sana"),
                        1 if y.get("mosmi") else 0, hozir,
                    )
                    for y in yozuvlar
                ],
            )
            return int(kursor.rowcount or 0)

    def _tender_tarixi(self, chek: int = 20) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT * FROM tenderlar WHERE mosmi = 1"
                " ORDER BY korildi DESC LIMIT ?",
                (chek,),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    # --- tasdiqlar ----------------------------------------------------------

    def _tasdiq_yoz(self, yozuv: dict[str, Any]) -> int:
        with self._ulanish() as u:
            kursor = u.execute(
                "INSERT OR REPLACE INTO tasdiqlar"
                " (iz_id, qadam_tartib, agent, korinish, holat, sorov, izoh, yaratildi)"
                " VALUES (?, ?, ?, ?, 'kutilmoqda', ?, ?, ?)",
                (
                    yozuv["iz_id"],
                    yozuv["qadam_tartib"],
                    yozuv["agent"],
                    yozuv["korinish"],
                    yozuv.get("sorov"),
                    yozuv.get("izoh"),
                    _hozir(),
                ),
            )
            return int(kursor.lastrowid or 0)

    def _tasdiq(self, iz_id: int) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute("SELECT * FROM tasdiqlar WHERE iz_id = ?", (iz_id,)).fetchone()
        return dict(qator) if qator else None

    def _kutilayotgan_tasdiqlar(self) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT * FROM tasdiqlar WHERE holat = 'kutilmoqda' ORDER BY id DESC"
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _tasdiq_hal_qil(self, iz_id: int, tasdiqlandi: bool, izoh: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "UPDATE tasdiqlar SET holat = ?, hal_qilindi = ?, qaror_izohi = ?"
                " WHERE iz_id = ? AND holat = 'kutilmoqda'",
                (
                    "tasdiqlandi" if tasdiqlandi else "rad_etildi",
                    _hozir(),
                    izoh,
                    iz_id,
                ),
            )

    # --- panel uchun ---------------------------------------------------------

    def _statistika(self) -> dict[str, Any]:
        """Panel uchun yig'ma ko'rsatkichlar (bazadan hisoblanadi)."""
        bugun = datetime.now(timezone.utc).date().isoformat()
        with self._ulanish() as u:
            jami = u.execute("SELECT count(*) AS n FROM izlar").fetchone()["n"]
            bugungi = u.execute(
                "SELECT count(*) AS n FROM izlar WHERE substr(vaqt, 1, 10) = ?", (bugun,)
            ).fetchone()["n"]
            kutilmoqda = u.execute(
                "SELECT count(*) AS n FROM tasdiqlar WHERE holat = 'kutilmoqda'"
            ).fetchone()["n"]
            holatlar = u.execute(
                "SELECT json_extract(yakuniy, '$.holat') AS holat, count(*) AS n"
                " FROM izlar WHERE substr(vaqt, 1, 10) = ? GROUP BY holat",
                (bugun,),
            ).fetchall()
            oxirgi_agentlar = u.execute(
                "SELECT DISTINCT json_extract(value, '$.agent') AS agent"
                " FROM izlar, json_each(izlar.qadamlar)"
                " WHERE substr(izlar.vaqt, 1, 10) = ?",
                (bugun,),
            ).fetchall()

        return {
            "jami_sorovlar": jami,
            "bugun_sorovlar": bugungi,
            "tasdiq_kutilmoqda": kutilmoqda,
            "bugun_holatlar": {q["holat"]: q["n"] for q in holatlar if q["holat"]},
            "bugun_ishlagan_agentlar": [q["agent"] for q in oxirgi_agentlar if q["agent"]],
        }

    def _ozgarish_belgisi(self) -> str:
        """Bazada nimadir o'zgarganini bildiradigan yengil belgi (SSE uchun)."""
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT (SELECT count(*) FROM izlar) AS izlar,"
                " (SELECT coalesce(max(id), 0) FROM izlar) AS oxirgi_iz,"
                # Qadam qo'shilganda ham o'zgaradi — zanjir jonli ko'rinadi.
                " (SELECT coalesce(sum(length(qadamlar) + length(coalesce(yakuniy, ''))), 0)"
                "  FROM izlar) AS hajm,"
                " (SELECT coalesce(max(coalesce(hal_qilindi, yaratildi)), '') FROM tasdiqlar)"
                "   AS tasdiq_vaqti,"
                " (SELECT count(*) FROM tasdiqlar WHERE holat = 'kutilmoqda') AS kutilmoqda"
            ).fetchone()
        return "|".join(str(q) for q in tuple(qator))

    def _agent_faoliyati(self) -> dict[str, dict[str, Any]]:
        """Har agentning oxirgi holati — panel va ofis ko'rinishi uchun."""
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT json_extract(q.value, '$.agent') AS agent,"
                "       json_extract(q.value, '$.konvert.holat') AS holat,"
                "       izlar.vaqt AS vaqt, izlar.id AS iz_id,"
                "       json_extract(q.value, '$.vazifa') AS vazifa"
                " FROM izlar, json_each(izlar.qadamlar) AS q"
                " ORDER BY izlar.id DESC"
            ).fetchall()

        # Haqiqatan kutilayotgan tasdiqlar (eskirgan iz emas).
        with self._ulanish() as u:
            kutayotgan_izlar = {
                q["iz_id"]
                for q in u.execute(
                    "SELECT iz_id FROM tasdiqlar WHERE holat = 'kutilmoqda'"
                ).fetchall()
            }

        oxirgi: dict[str, dict[str, Any]] = {}
        for qator in qatorlar:
            agent = qator["agent"]
            if not agent or agent in oxirgi:
                continue

            holat = qator["holat"]
            # Eski izda "tasdiq_kutilmoqda" qolib ketgan bo'lishi mumkin —
            # agar tasdiq navbatida bunday yozuv bo'lmasa, bu HOZIRGI holat
            # emas, shunchaki tarix. Aks holda agent abadiy kutib turadi.
            kutilmoqda = qator["iz_id"] in kutayotgan_izlar
            if holat == "tasdiq_kutilmoqda" and not kutilmoqda:
                holat = "yakunlanmagan"

            oxirgi[agent] = {
                "holat": holat,
                "kutilmoqda": kutilmoqda,
                "vaqt": qator["vaqt"],
                "iz_id": qator["iz_id"],
                "vazifa": qator["vazifa"],
            }
        return oxirgi

    def _narx_yoz(self, yozuv: dict[str, Any]) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO narxlar (vaqt, mahsulot, bozor, narx, valyuta, sana, manba, havola)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _hozir(),
                    yozuv["mahsulot"],
                    yozuv.get("bozor"),
                    float(yozuv["narx"]),
                    yozuv["valyuta"],
                    yozuv.get("sana"),
                    yozuv.get("manba"),
                    yozuv.get("havola"),
                ),
            )

    def _oxirgi_narx(self, mahsulot: str, valyuta: str) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT narx, valyuta, vaqt, manba FROM narxlar"
                " WHERE mahsulot = ? AND valyuta = ? ORDER BY id DESC LIMIT 1",
                (mahsulot, valyuta),
            ).fetchone()
        return dict(qator) if qator else None

    def _topilma_yoz(self, yozuv: dict[str, Any]) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO raqib_topilmalari (vaqt, raqib, mavzu, tafsilot, sana, manba, havola)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _hozir(),
                    yozuv["raqib"],
                    yozuv.get("mavzu"),
                    yozuv.get("tafsilot"),
                    yozuv.get("sana"),
                    yozuv.get("manba"),
                    yozuv.get("havola"),
                ),
            )

    def _topilmalar(self, chek: int) -> list[dict[str, Any]]:
        """Oldingi topilmalar — yangisidan eskisiga.

        Karim har safar noldan qidirsa, "bu yangimi yoki o'tgan oyda ham
        shunday edimi?" degan savolga javob bo'lmaydi. Tarix aynan shuning
        uchun saqlanadi.
        """
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT * FROM raqib_topilmalari ORDER BY id DESC LIMIT ?",
                (chek,),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    # --- So'rovnoma ---------------------------------------------------------

    def _sorovnoma_holati_yoz(self, tg_id: Any, bolim: str,
                              javoblar: dict[str, Any],
                              savat: list[Any] | None = None) -> None:
        with self._ulanish() as u:
            if savat is None:
                # Savat berilmasa — TEGILMAYDI. Har javob yozilganda
                # savat ham qayta yozilsa, allaqachon qo'shilgan
                # pozitsiyalar yo'qolib ketardi.
                u.execute(
                    "INSERT INTO sorovnoma_holati (tg_id, bolim, javoblar,"
                    " savat, yaratildi, yangilandi) VALUES (?, ?, ?, '[]', ?, ?)"
                    " ON CONFLICT(tg_id) DO UPDATE SET"
                    " bolim = excluded.bolim, javoblar = excluded.javoblar,"
                    " yangilandi = excluded.yangilandi",
                    (str(tg_id), bolim, json.dumps(javoblar, ensure_ascii=False),
                     _hozir(), _hozir()),
                )
                return
            u.execute(
                "INSERT INTO sorovnoma_holati (tg_id, bolim, javoblar,"
                " savat, yaratildi, yangilandi) VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " bolim = excluded.bolim, javoblar = excluded.javoblar,"
                " savat = excluded.savat, yangilandi = excluded.yangilandi",
                (str(tg_id), bolim, json.dumps(javoblar, ensure_ascii=False),
                 json.dumps(savat, ensure_ascii=False), _hozir(), _hozir()),
            )

    def _sorovnoma_holati(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT bolim, javoblar, savat FROM sorovnoma_holati"
                " WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        if qator is None:
            return None
        try:
            javoblar = json.loads(qator["javoblar"])
        except (TypeError, ValueError):
            log.warning("sorovnoma_holati buzuq JSON: id=%s", tg_id)
            return None
        try:
            savat = json.loads(qator["savat"] or "[]")
        except (TypeError, ValueError):
            # Savat buzuq bo'lsa BUTUN holat tashlanmaydi: joriy
            # so'rovnoma baribir to'ldirilaveradi.
            log.warning("sorovnoma savati buzuq JSON: id=%s", tg_id)
            savat = []
        return {"bolim": qator["bolim"], "javoblar": javoblar,
                "savat": savat if isinstance(savat, list) else []}

    def _sorovnoma_holati_ochir(self, tg_id: Any) -> None:
        with self._ulanish() as u:
            u.execute("DELETE FROM sorovnoma_holati WHERE tg_id = ?", (str(tg_id),))

    def _sorovnoma_yoz(self, yozuv: dict[str, Any]) -> int:
        with self._ulanish() as u:
            kursor = u.execute(
                "INSERT INTO sorovnomalar (vaqt, tg_id, ism, aloqa, bolim,"
                " javoblar, holat) VALUES (?, ?, ?, ?, ?, ?, 'yangi')",
                (_hozir(), str(yozuv["tg_id"]), yozuv.get("ism"),
                 yozuv.get("aloqa"), yozuv["bolim"],
                 json.dumps(yozuv["javoblar"], ensure_ascii=False)),
            )
            return int(kursor.lastrowid)

    def _sorovnomalar(self, holat: str | None = "yangi",
                      chek: int = 20) -> list[dict[str, Any]]:
        shart = "WHERE holat = ?" if holat else ""
        parametrlar = ((holat, chek) if holat else (chek,))
        with self._ulanish() as u:
            qatorlar = u.execute(
                f"SELECT * FROM sorovnomalar {shart} ORDER BY id DESC LIMIT ?",
                parametrlar,
            ).fetchall()
        natija = []
        for q in qatorlar:
            y = dict(q)
            try:
                y["javoblar"] = json.loads(y["javoblar"])
            except (TypeError, ValueError):
                y["javoblar"] = {}
            natija.append(y)
        return natija

    def _sorovnoma_korildi(self, sorovnoma_id: int) -> None:
        with self._ulanish() as u:
            u.execute("UPDATE sorovnomalar SET holat = 'korildi' WHERE id = ?",
                      (sorovnoma_id,))

    # --- Mijoz aloqasi ------------------------------------------------------

    def _aloqa_yoz(self, tg_id: Any, telefon: str, ism: str = "") -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO mijoz_aloqasi (tg_id, ism, telefon, yaratildi,"
                " yangilandi) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(tg_id) DO UPDATE SET"
                " telefon = excluded.telefon,"
                # Ism BO'SH bo'lsa eskisi qoladi: Telegram profilida ism
                # bo'lmasligi mumkin, lekin mijoz uni ilgari yozgan
                # bo'lishi mumkin.
                " ism = CASE WHEN excluded.ism <> '' THEN excluded.ism"
                "            ELSE mijoz_aloqasi.ism END,"
                " yangilandi = excluded.yangilandi",
                (str(tg_id), ism, telefon, _hozir(), _hozir()),
            )

    def _aloqa(self, tg_id: Any) -> dict[str, Any] | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT ism, telefon, yangilandi FROM mijoz_aloqasi"
                " WHERE tg_id = ?",
                (str(tg_id),),
            ).fetchone()
        return dict(qator) if qator else None

    # --- LLM sarfi ----------------------------------------------------------

    def _sarf_yoz(self, yozuv: dict[str, Any]) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO llm_sarfi"
                " (vaqt, kun, provayder, model, rol, kirish, chiqish,"
                "  keshdan, ms, xato)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    yozuv["vaqt"],
                    yozuv["kun"],
                    yozuv["provayder"],
                    yozuv.get("model") or "",
                    yozuv.get("rol"),
                    int(yozuv.get("kirish") or 0),
                    int(yozuv.get("chiqish") or 0),
                    int(yozuv.get("keshdan") or 0),
                    yozuv.get("ms"),
                    yozuv.get("xato"),
                ),
            )

    def _sarf_kunlik(self, provayder: str, kun: str) -> dict[str, Any]:
        """Bitta provayderning bitta kvota kunidagi yig'indisi."""
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT COUNT(*) AS soni,"
                "       SUM(CASE WHEN xato IS NULL THEN 1 ELSE 0 END) AS muvaffaq,"
                "       SUM(CASE WHEN xato IS NOT NULL THEN 1 ELSE 0 END) AS xatolar,"
                "       COALESCE(SUM(kirish), 0)  AS kirish,"
                "       COALESCE(SUM(chiqish), 0) AS chiqish,"
                "       COALESCE(SUM(keshdan), 0) AS keshdan"
                " FROM llm_sarfi WHERE provayder = ? AND kun = ?",
                (provayder, kun),
            ).fetchone()
        return dict(qator) if qator else {}

    def _sarf_rollar(self, provayder: str, kun: str, chek: int = 12) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT rol, COUNT(*) AS soni,"
                "       COALESCE(SUM(kirish + chiqish), 0) AS tokenlar"
                " FROM llm_sarfi WHERE provayder = ? AND kun = ?"
                " GROUP BY rol ORDER BY soni DESC LIMIT ?",
                (provayder, kun, chek),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _sarf_modellar(self, provayder: str, kun: str) -> list[dict[str, Any]]:
        """Model bo'yicha ajratma — zanjir qanday ishlaganini ko'rsatadi."""
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT model, COUNT(*) AS soni,"
                "       SUM(CASE WHEN xato IS NOT NULL THEN 1 ELSE 0 END) AS xatolar,"
                "       COALESCE(SUM(kirish), 0)  AS kirish,"
                "       COALESCE(SUM(chiqish), 0) AS chiqish,"
                "       COALESCE(SUM(keshdan), 0) AS keshdan"
                " FROM llm_sarfi WHERE provayder = ? AND kun = ?"
                " GROUP BY model ORDER BY soni DESC",
                (provayder, kun),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _sarf_kunlar(self, provayder: str, chek: int = 7) -> list[dict[str, Any]]:
        """Oxirgi kunlar — bugungi son ko'p yoki kammi, taqqoslash uchun."""
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT kun, COUNT(*) AS soni,"
                "       SUM(CASE WHEN xato IS NOT NULL THEN 1 ELSE 0 END) AS xatolar"
                " FROM llm_sarfi WHERE provayder = ?"
                " GROUP BY kun ORDER BY kun DESC LIMIT ?",
                (provayder, chek),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def _sarf_provayderlar(self, kun: str) -> list[str]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT DISTINCT provayder FROM llm_sarfi WHERE kun >= ?"
                " ORDER BY provayder",
                (kun,),
            ).fetchall()
        return [q["provayder"] for q in qatorlar]

    def _sarf_oxirgi_daqiqa(self, provayder: str, chegara: str) -> int:
        """`chegara` (ISO vaqt) dan keyingi so'rovlar soni — RPM bosimi."""
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT COUNT(*) AS soni FROM llm_sarfi"
                " WHERE provayder = ? AND vaqt >= ?",
                (provayder, chegara),
            ).fetchone()
        return int(qator["soni"]) if qator else 0

    def _sarf_xatolari(self, provayder: str, kun: str, chek: int = 5) -> list[dict[str, Any]]:
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT vaqt, rol, xato FROM llm_sarfi"
                " WHERE provayder = ? AND kun = ? AND xato IS NOT NULL"
                " ORDER BY id DESC LIMIT ?",
                (provayder, kun, chek),
            ).fetchall()
        return [dict(q) for q in qatorlar]

    # --- async yuzasi -------------------------------------------------------

    async def tayyorla(self) -> None:
        await asyncio.to_thread(self._tayyorla)

    async def iz_yoz(self, yozuv: dict[str, Any]) -> int:
        return await asyncio.to_thread(self._iz_yoz, yozuv)

    async def izlar(self, chek: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._izlar, chek)

    async def iz(self, iz_id: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._iz, iz_id)

    async def iz_boshla(self, sorov: str, reja: Any) -> int:
        return await asyncio.to_thread(self._iz_boshla, sorov, reja)

    async def iz_qadamlarni_yangila(self, iz_id: int, qadamlar: list[Any]) -> None:
        await asyncio.to_thread(self._iz_qadamlarni_yangila, iz_id, qadamlar)

    async def iz_yangila(self, iz_id: int, yozuv: dict[str, Any]) -> None:
        await asyncio.to_thread(self._iz_yangila, iz_id, yozuv)

    async def kp_raqam_ol(
        self,
        mijoz: str | None = None,
        iz_id: int | None = None,
        shakl: str = "KP-{yil}-{tartib:04d}",
        boshlanish: int = 0,
    ) -> str:
        """Yangi, takrorlanmas KP raqami."""
        return await asyncio.to_thread(
            self._kp_raqam_ol, mijoz, iz_id, shakl, boshlanish
        )

    async def kp_royxati(self, chek: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._kp_royxati, chek)

    async def kp_kuzatuv_yoz(
        self,
        raqam: str,
        mijoz: str | None = None,
        summa: float | None = None,
        yaratildi: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._kp_kuzatuv_yoz, raqam, mijoz, summa, yaratildi
        )

    async def kp_holat_yoz(self, raqam: str, holat: str, izoh: str = "") -> bool:
        return await asyncio.to_thread(self._kp_holat_yoz, raqam, holat, izoh)

    async def kp_kuzatuv(
        self, holat: str | None = None, chek: int = 50
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._kp_kuzatuv, holat, chek)

    async def javobsiz_kplar(
        self, kun: int = 5, chek: int = 50
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._javobsiz_kplar, kun, chek)

    async def kp_xulosasi(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._kp_xulosasi)

    async def murojaat_yoz(self, yozuv: dict[str, Any]) -> int:
        return await asyncio.to_thread(self._murojaat_yoz, yozuv)

    async def murojaatlar(
        self, holat: str | None = None, chek: int = 50
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._murojaatlar, holat, chek)

    async def murojaat_bormi(self, tg_id: Any) -> bool:
        return await asyncio.to_thread(self._murojaat_bormi, tg_id)

    async def murojaat_korildi(self, murojaat_id: int) -> bool:
        return await asyncio.to_thread(self._murojaat_korildi, murojaat_id)

    async def menejer(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._menejer, tg_id)

    async def menejer_yoz(self, tg_id: Any, ism: str, telefon: str) -> None:
        await asyncio.to_thread(self._menejer_yoz, tg_id, ism, telefon)

    async def menejer_ochir(self, tg_id: Any) -> None:
        await asyncio.to_thread(self._menejer_ochir, tg_id)

    # --- rejali ish (tender, hisobot) ---------------------------------------

    def _rejali_ish_yoz(self, nomi: str, kun: str) -> None:
        with self._ulanish() as u:
            u.execute(
                "INSERT INTO rejali_ish (nomi, oxirgi_kun, vaqt) VALUES (?, ?, ?) "
                "ON CONFLICT(nomi) DO UPDATE SET oxirgi_kun=excluded.oxirgi_kun, "
                "vaqt=excluded.vaqt",
                (nomi, kun, _hozir()),
            )

    def _rejali_ish_kuni(self, nomi: str) -> str | None:
        with self._ulanish() as u:
            qator = u.execute(
                "SELECT oxirgi_kun FROM rejali_ish WHERE nomi = ?", (nomi,)
            ).fetchone()
        return qator["oxirgi_kun"] if qator else None

    async def rejali_ish_yoz(self, nomi: str, kun: str) -> None:
        """Ish bajarilganini belgilaydi (kun — YYYY-MM-DD)."""
        await asyncio.to_thread(self._rejali_ish_yoz, nomi, kun)

    async def rejali_ish_kuni(self, nomi: str) -> str | None:
        """Oxirgi bajarilgan kun (hech qachon bajarilmagan bo'lsa None)."""
        return await asyncio.to_thread(self._rejali_ish_kuni, nomi)

    async def sozlama_yoz(self, tg_id: Any, kp_tili: str) -> None:
        await asyncio.to_thread(self._sozlama_yoz, tg_id, kp_tili)

    async def foydalanuvchi_sozlamasi(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._foydalanuvchi_sozlamasi, tg_id)

    async def oxirgi_kp_yoz(self, tg_id: Any, raqam: str, malumot: str) -> None:
        await asyncio.to_thread(self._oxirgi_kp_yoz, tg_id, raqam, malumot)

    async def oxirgi_kp(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._oxirgi_kp, tg_id)

    async def suhbat_yoz(
        self, kanal: str, tg_id: Any, sorov: str, savollar: str = "", qadam: int = 1
    ) -> None:
        await asyncio.to_thread(
            self._suhbat_yoz, kanal, tg_id, sorov, savollar, qadam
        )

    async def suhbat(self, kanal: str, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._suhbat, kanal, tg_id)

    async def suhbat_ochir(self, kanal: str, tg_id: Any) -> None:
        await asyncio.to_thread(self._suhbat_ochir, kanal, tg_id)

    async def savol_yoz(self, tg_id: Any, tur: str, sorov: str) -> None:
        await asyncio.to_thread(self._savol_yoz, tg_id, tur, sorov)

    async def savol(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._savol, tg_id)

    async def savol_ochir(self, tg_id: Any) -> None:
        await asyncio.to_thread(self._savol_ochir, tg_id)

    async def kp_shakli_yoz(self, tg_id: Any, javoblar: dict[str, Any]) -> None:
        await asyncio.to_thread(self._kp_shakli_yoz, tg_id, javoblar)

    async def kp_shakli(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._kp_shakli, tg_id)

    async def kp_shakli_ochir(self, tg_id: Any) -> None:
        await asyncio.to_thread(self._kp_shakli_ochir, tg_id)

    async def korilgan_tenderlar(self, kalitlar: list[str]) -> set[str]:
        return await asyncio.to_thread(self._korilgan_tenderlar, kalitlar)

    async def tender_yoz(self, yozuvlar: list[dict[str, Any]]) -> int:
        return await asyncio.to_thread(self._tender_yoz, yozuvlar)

    async def tender_tarixi(self, chek: int = 20) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._tender_tarixi, chek)

    async def tasdiq_yoz(self, yozuv: dict[str, Any]) -> int:
        return await asyncio.to_thread(self._tasdiq_yoz, yozuv)

    async def tasdiq(self, iz_id: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._tasdiq, iz_id)

    async def kutilayotgan_tasdiqlar(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._kutilayotgan_tasdiqlar)

    async def tasdiq_hal_qil(self, iz_id: int, tasdiqlandi: bool, izoh: str = "") -> None:
        await asyncio.to_thread(self._tasdiq_hal_qil, iz_id, tasdiqlandi, izoh)

    async def narx_yoz(self, yozuv: dict[str, Any]) -> None:
        await asyncio.to_thread(self._narx_yoz, yozuv)

    async def oxirgi_narx(self, mahsulot: str, valyuta: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._oxirgi_narx, mahsulot, valyuta)

    async def topilma_yoz(self, yozuv: dict[str, Any]) -> None:
        await asyncio.to_thread(self._topilma_yoz, yozuv)

    async def topilmalar(self, chek: int = 40) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._topilmalar, chek)

    async def sorov_bajar(self, sql: str, yozish: bool = False) -> list[dict[str, Any]]:
        """Doston uchun cheklangan SQL ijrosi (standart: faqat o'qish)."""
        return await asyncio.to_thread(self._sorov_bajar, sql, yozish)

    async def jadval_sxemasi(self) -> str:
        return await asyncio.to_thread(self._jadval_sxemasi)

    async def statistika(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._statistika)

    async def ozgarish_belgisi(self) -> str:
        return await asyncio.to_thread(self._ozgarish_belgisi)

    async def agent_faoliyati(self) -> dict[str, dict[str, Any]]:
        return await asyncio.to_thread(self._agent_faoliyati)

    async def xodimlar(self, bolim: str | None = None) -> list[dict[str, Any]]:
        """Hilola uchun cheklangan xodim ma'lumoti (maosh/telefon chiqmaydi)."""
        return await asyncio.to_thread(self._xodimlar, bolim)

    # --- LLM sarfi (async) --------------------------------------------------

    async def sarf_yoz(self, yozuv: dict[str, Any]) -> None:
        await asyncio.to_thread(self._sarf_yoz, yozuv)

    async def sarf_kunlik(self, provayder: str, kun: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sarf_kunlik, provayder, kun)

    async def sarf_rollar(self, provayder: str, kun: str, chek: int = 12) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sarf_rollar, provayder, kun, chek)

    async def sarf_kunlar(self, provayder: str, chek: int = 7) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sarf_kunlar, provayder, chek)

    async def sarf_provayderlar(self, kun: str) -> list[str]:
        return await asyncio.to_thread(self._sarf_provayderlar, kun)

    async def sarf_oxirgi_daqiqa(self, provayder: str, chegara: str) -> int:
        return await asyncio.to_thread(self._sarf_oxirgi_daqiqa, provayder, chegara)

    async def sarf_xatolari(self, provayder: str, kun: str, chek: int = 5) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sarf_xatolari, provayder, kun, chek)

    async def sarf_modellar(self, provayder: str, kun: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sarf_modellar, provayder, kun)

    # --- So'rovnoma (async) -------------------------------------------------

    async def sorovnoma_holati_yoz(self, tg_id: Any, bolim: str,
                                   javoblar: dict[str, Any],
                                   savat: list[Any] | None = None) -> None:
        await asyncio.to_thread(
            self._sorovnoma_holati_yoz, tg_id, bolim, javoblar, savat)

    async def sorovnoma_holati(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._sorovnoma_holati, tg_id)

    async def sorovnoma_holati_ochir(self, tg_id: Any) -> None:
        await asyncio.to_thread(self._sorovnoma_holati_ochir, tg_id)

    async def sorovnoma_yoz(self, yozuv: dict[str, Any]) -> int:
        return await asyncio.to_thread(self._sorovnoma_yoz, yozuv)

    async def sorovnomalar(self, holat: str | None = "yangi",
                           chek: int = 20) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sorovnomalar, holat, chek)

    async def sorovnoma_korildi(self, sorovnoma_id: int) -> None:
        await asyncio.to_thread(self._sorovnoma_korildi, sorovnoma_id)

    async def aloqa_yoz(self, tg_id: Any, telefon: str, ism: str = "") -> None:
        await asyncio.to_thread(self._aloqa_yoz, tg_id, telefon, ism)

    async def aloqa(self, tg_id: Any) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._aloqa, tg_id)

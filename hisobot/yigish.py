"""Hisobot ma'lumotini bazadan yig'ish."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Hisobotda ko'rsatiladigan javobsiz savol soni.
MAKS_SAVOL = 8
# Eng ko'p so'ralgan mavzu soni.
MAKS_MAVZU = 5

# `izlar.xato` ustuni HAR QANDAY muvaffaqiyatsiz yakunni yozadi — shu
# jumladan mutlaqo normal holatlarni. Ularni "xato" deb sanash hisobotni
# yolg'on qiladi: 19 tadan faqat 6 tasi haqiqiy nosozlik ekan.
#
# Shuning uchun uch guruhga ajratamiz.
RAD_ETISH = (
    ("inson rad etdi", "tasdiqda rad etildi"),
    ("qat'iyan taqiqlangan", "xavfsizlik qoidasi to'sdi"),
    ("so'rov rad etildi", "xavfsizlik qoidasi to'sdi"),
)
BAJARILMADI = (
    ("kodda ulanmagan", "agent ulanmagan"),
    ("agent kontraktiga kirmaydi", "mos agent yo'q"),
    ("mahsulot aniqlanmadi", "mahsulot topilmadi"),
)

# Mavzu ajratish uchun kalit so'zlar. Model ishlatilmaydi — mavzu
# ro'yxati barqaror bo'lishi kerak, aks holda haftalar solishtirilmaydi.
MAVZULAR = {
    "narx": r"narx|стоим|цена|qancha turadi|pul",
    "ventilyatsiya hisobi": r"ventilyatsiya|hisob|havo sarfi|расчет|вентиляц",
    "mahsulot/texnik": r"xususiyat|texnik|характер|модел|model|spetsifikatsiya",
    "muddat/yetkazish": r"muddat|qachon|yetkaz|срок|доставк",
    "kafolat/servis": r"kafolat|servis|гарант|ремонт",
    "montaj": r"montaj|o'rnat|монтаж|установк",
}


@dataclass(frozen=True)
class Davr:
    """Hisobot davri."""

    boshi: datetime
    oxiri: datetime
    nomi: str

    @staticmethod
    def kunlar(soni: int, nomi: str = "") -> "Davr":
        oxiri = datetime.now(timezone.utc)
        return Davr(
            boshi=oxiri - timedelta(days=soni),
            oxiri=oxiri,
            nomi=nomi or f"oxirgi {soni} kun",
        )

    def sql_juftligi(self) -> tuple[str, str]:
        return self.boshi.isoformat(), self.oxiri.isoformat()


@dataclass
class Hisobot:
    davr: Davr
    # Mijozlar boti
    mijoz_savollari: int = 0
    javob_berildi: int = 0
    javobsiz: int = 0
    lidlar: int = 0
    yangi_mijozlar: int = 0
    javobsiz_savollar: list[str] = field(default_factory=list)
    mavzular: list[tuple[str, int]] = field(default_factory=list)
    # Ichki tizim
    ichki_sorovlar: int = 0
    xatolar: int = 0                 # HAQIQIY nosozlik
    rad_etilgan: int = 0             # inson yoki qoida to'sdi — normal
    bajarilmadi: int = 0             # mos agent yoki ma'lumot yo'q
    xato_turlari: list[tuple[str, int]] = field(default_factory=list)
    ortacha_soniya: float = 0.0
    # KP
    kp_yaratildi: int = 0
    kp_javob_keldi: int = 0
    kp_shartnoma: int = 0
    kp_ochiq: int = 0
    # Tender
    tender_korildi: int = 0
    tender_mos: int = 0
    # Tasdiq
    tasdiq_kutilmoqda: int = 0

    @property
    def javob_foizi(self) -> float:
        return (
            100.0 * self.javob_berildi / self.mijoz_savollari
            if self.mijoz_savollari
            else 0.0
        )


@dataclass(frozen=True)
class XatoTuri:
    guruh: str      # rad | bajarilmadi | xato
    nomi: str


def _xato_turi(matn: str) -> XatoTuri:
    """Yozuvni uch guruhdan biriga ajratadi.

    Sabab: "Inson rad etdi" — bu tizimning NORMAL ishlashi, menejer
    tasdiqni bermadi. Uni nosozlik deb sanash rahbarni chalg'itadi va
    haqiqiy xatolarni ko'rinmas qiladi.
    """
    past = (matn or "").lower()
    for kalit, nomi in RAD_ETISH:
        if kalit in past:
            return XatoTuri("rad", nomi)
    for kalit, nomi in BAJARILMADI:
        if kalit in past:
            return XatoTuri("bajarilmadi", nomi)

    # Haqiqiy nosozliklar — qisqa nom bilan guruhlaymiz.
    if "api key" in past or "anthropic_api_key" in past:
        return XatoTuri("xato", "API kaliti yaroqsiz")
    if "http 500" in past:
        return XatoTuri("xato", "backend 500 qaytardi")
    if "http 401" in past or "token" in past:
        return XatoTuri("xato", "token eskirgan yoki yo'q")
    if "api xatosi" in past:
        return XatoTuri("xato", "model API xatosi")
    return XatoTuri("xato", matn.split(":")[0][:40])


def _mavzu(matn: str) -> str | None:
    past = (matn or "").lower()
    for nom, andoza in MAVZULAR.items():
        if re.search(andoza, past):
            return nom
    return None


def hisobot_yig(baza_yoli, davr: Davr) -> Hisobot:
    """Bazadan hisobot yig'adi. Model ishlatilmaydi — faqat SQL."""
    h = Hisobot(davr=davr)
    boshi, oxiri = davr.sql_juftligi()

    u = sqlite3.connect(str(baza_yoli))
    u.row_factory = sqlite3.Row
    try:
        # --- mijozlar boti ---
        murojaatlar = u.execute(
            "SELECT savol, javob, sabab FROM mijoz_murojaatlari"
            " WHERE vaqt >= ? AND vaqt <= ?",
            (boshi, oxiri),
        ).fetchall()

        sanoq: dict[str, int] = {}
        for m in murojaatlar:
            h.mijoz_savollari += 1
            if m["javob"]:
                h.javob_berildi += 1
            sabab = (m["sabab"] or "").lower()
            if "aloqa qoldirdi" in sabab or "raqamini yubordi" in sabab:
                h.lidlar += 1
            elif m["sabab"]:
                h.javobsiz += 1
                if len(h.javobsiz_savollar) < MAKS_SAVOL:
                    h.javobsiz_savollar.append(m["savol"][:120])
            mavzu = _mavzu(m["savol"])
            if mavzu:
                sanoq[mavzu] = sanoq.get(mavzu, 0) + 1

        h.mavzular = sorted(sanoq.items(), key=lambda x: -x[1])[:MAKS_MAVZU]

        # --- ichki tizim ---
        qator = u.execute(
            "SELECT COUNT(*) n, AVG(davomiylik_ms) o FROM izlar"
            " WHERE vaqt >= ? AND vaqt <= ?",
            (boshi, oxiri),
        ).fetchone()
        h.ichki_sorovlar = qator["n"] or 0
        h.ortacha_soniya = round((qator["o"] or 0) / 1000, 1)

        xato_sanoq: dict[str, int] = {}
        for r in u.execute(
            "SELECT xato FROM izlar WHERE vaqt >= ? AND vaqt <= ?"
            " AND xato IS NOT NULL AND xato != ''",
            (boshi, oxiri),
        ):
            tur = _xato_turi(r["xato"])
            if tur.guruh == "rad":
                h.rad_etilgan += 1
            elif tur.guruh == "bajarilmadi":
                h.bajarilmadi += 1
            else:
                h.xatolar += 1
                xato_sanoq[tur.nomi] = xato_sanoq.get(tur.nomi, 0) + 1
        h.xato_turlari = sorted(xato_sanoq.items(), key=lambda x: -x[1])[:MAKS_MAVZU]

        # --- KP ---
        for r in u.execute(
            "SELECT holat, COUNT(*) n FROM kp_kuzatuv"
            " WHERE yaratildi >= ? AND yaratildi <= ? GROUP BY holat",
            (boshi, oxiri),
        ):
            h.kp_yaratildi += r["n"]
            if r["holat"] == "javob_keldi":
                h.kp_javob_keldi = r["n"]
            elif r["holat"] == "shartnoma":
                h.kp_shartnoma = r["n"]
        h.kp_ochiq = u.execute(
            "SELECT COUNT(*) FROM kp_kuzatuv WHERE holat = 'yuborildi'"
        ).fetchone()[0]

        # --- tender ---
        qator = u.execute(
            "SELECT COUNT(*) n, SUM(mosmi) m FROM tenderlar"
            " WHERE korildi >= ? AND korildi <= ?",
            (boshi, oxiri),
        ).fetchone()
        h.tender_korildi = qator["n"] or 0
        h.tender_mos = qator["m"] or 0

        # --- tasdiq (joriy holat, davrga bog'liq emas) ---
        h.tasdiq_kutilmoqda = u.execute(
            "SELECT COUNT(*) FROM tasdiqlar WHERE holat = 'kutilmoqda'"
        ).fetchone()[0]
    finally:
        u.close()

    return h


CHIZIQ = "━━━━━━━━━━━━━━━━━━━━"


def hisobot_matni(h: Hisobot) -> str:
    """Telegram uchun o'qiladigan matn.

    NEGA IZOHLAR BILAN: ilgari hisobot faqat raqamlar ro'yxati edi —
    "Ko'rildi: 4", "Mos keldi: 0". Raqamni ko'rgan odam nima qilishini
    bilmaydi: 0 yomonmi yoki normalmi? 25 ta javobsiz KP ko'pmi?
    Shuning uchun har bo'lim NIMA ekanini bir qatorda aytadi, har raqam
    nimani anglatishini yozadi, oxirida esa "nima qilish kerak" turadi.
    """
    q: list[str] = [
        f"📊 HISOBOT — {h.davr.nomi}",
        f"{h.davr.boshi:%d.%m} – {h.davr.oxiri:%d.%m.%Y}",
    ]

    q += _mijozlar_bolimi(h)
    q += _kp_bolimi(h)
    q += _tender_bolimi(h)
    q += _tizim_bolimi(h)
    q += _nima_qilish(h)

    return "\n".join(q)


# --- bo'limlar ----------------------------------------------------------------


def _mijozlar_bolimi(h: Hisobot) -> list[str]:
    """Ochiq bot: mijoz savol beradi, tizim javob beradi."""
    q = [
        "",
        CHIZIQ,
        "👥 MIJOZLAR BOTI",
        "Telegramdagi ochiq bot — mijoz yozadi, tizim javob beradi.",
        "",
    ]
    if not h.mijoz_savollari:
        # Nol yomon xabar EMAS — lekin buni aytmasak, o'quvchi "bot
        # buzilganmi?" deb o'ylaydi.
        q.append("   Bu davrda murojaat bo'lmadi.")
        q.append("   Bot ishlayapti — shunchaki hech kim yozmadi.")
        return q

    q.append(f"   Savol keldi        {h.mijoz_savollari} ta")
    q.append(
        f"   Javob berildi      {h.javob_berildi} ta ({h.javob_foizi:.0f}%)"
    )
    if h.lidlar:
        q.append(f"   📞 Telefon qoldirdi {h.lidlar} ta")
        q.append("      → yangi mijoz, qo'ng'iroq qilish kerak")
    if h.javobsiz:
        q.append(f"   ⚠️ Menejerga o'tdi  {h.javobsiz} ta")
        q.append("      → bot javob berolmadi, odam qaraydi")

    if h.mavzular:
        q.append("")
        q.append("   Nima haqida so'rashdi:")
        q += [f"   • {nom} — {soni} marta" for nom, soni in h.mavzular]

    if h.javobsiz_savollar:
        q.append("")
        q.append("❓ JAVOB BEROLMAGAN SAVOLLAR")
        q.append("Bular tizim bilmagan narsalar. Javobini bilim bazasiga")
        q.append("qo'shsak, keyingi safar bot o'zi javob beradi.")
        q.append("")
        q += [f"   • {s}" for s in h.javobsiz_savollar]
    return q


def _kp_bolimi(h: Hisobot) -> list[str]:
    """Tijorat takliflari — pul shu yerdan keladi."""
    q = [
        "",
        CHIZIQ,
        "💼 TIJORAT TAKLIFI (KP)",
        "Mijozga yuborilgan narx takliflari.",
        "",
    ]
    if h.kp_yaratildi:
        q.append(f"   Tayyorlandi        {h.kp_yaratildi} ta")
    else:
        q.append("   Bu davrda yangi taklif tayyorlanmadi.")
    if h.kp_javob_keldi:
        q.append(f"   Mijoz javob berdi  {h.kp_javob_keldi} ta")
    if h.kp_shartnoma:
        q.append(f"   ✅ Shartnoma bo'ldi {h.kp_shartnoma} ta")

    if h.kp_ochiq:
        q.append("")
        q.append(f"   ⏳ Javobsiz turibdi {h.kp_ochiq} ta")
        q.append("      Yuborilgan, lekin mijozdan javob yo'q.")
        q.append("      Bu — avvalgi davrlar bilan JAMI son.")
        q.append("      Har biri hali ham shartnomaga aylanishi mumkin.")
    return q


def _tender_bolimi(h: Hisobot) -> list[str]:
    """Xarid e'lonlari — biz bajara oladigan ish bormi?"""
    q = [
        "",
        CHIZIQ,
        "📋 TENDERLAR",
        "Ochiq xarid e'lonlari avtomatik kuzatiladi.",
        "",
    ]
    if not h.tender_korildi:
        q.append("   Bu davrda e'lon ko'rilmadi.")
        q.append("   Manbada yangi e'lon chiqmagan bo'lishi mumkin —")
        q.append("   tekshirish uchun: /tender")
        return q

    q.append(f"   Ko'rildi           {h.tender_korildi} ta e'lon")
    q.append(f"   Bizga mos keldi    {h.tender_mos} ta")
    if not h.tender_mos:
        # 0 ni yomon xabar deb o'qimaslik kerak.
        q.append("      → mos e'lon chiqmadi. Bu odatiy holat:")
        q.append("        e'lonlarning ko'pi boshqa sohaga tegishli.")
    return q


def _tizim_bolimi(h: Hisobot) -> list[str]:
    """Menejerlarning ichki botga bergan so'rovlari."""
    q = [
        "",
        CHIZIQ,
        "⚙️ TIZIM",
        "Menejerlar ichki botga bergan so'rovlar.",
        "",
    ]
    if not h.ichki_sorovlar:
        q.append("   Bu davrda so'rov bo'lmadi.")
    else:
        q.append(f"   So'rov bajarildi   {h.ichki_sorovlar} ta")
        q.append(f"   O'rtacha vaqt      {h.ortacha_soniya} s")
        q.append("      → so'rovdan to javobgacha ketgan vaqt")

    # Rad etish va bajarilmaslik — NORMAL holatlar, xato emas.
    if h.rad_etilgan:
        q.append(f"   ✋ Menejer rad etdi {h.rad_etilgan} ta")
        q.append("      → tasdiq so'ralgan, javob \"yo'q\" bo'lgan")
    if h.bajarilmadi:
        q.append(f"   ➖ Bajarilmadi      {h.bajarilmadi} ta")
        q.append("      → mos agent yoki ma'lumot topilmadi")
    if h.tasdiq_kutilmoqda:
        q.append(f"   ⏸ Tasdiq kutmoqda  {h.tasdiq_kutilmoqda} ta")
        q.append("      → ish to'xtab turibdi, javobingiz kerak")

    if h.xatolar:
        q.append("")
        q.append(f"🔧 NOSOZLIK — {h.xatolar} ta")
        q.append("Bular haqiqiy buzilish, tuzatilishi kerak:")
        q += [f"   • {nom} — {soni} marta" for nom, soni in h.xato_turlari]
    return q


def _nima_qilish(h: Hisobot) -> list[str]:
    """Xulosa: raqamlardan kelib chiqadigan aniq ishlar.

    Hisobotning maqsadi — raqam ko'rsatish emas, QAROR chiqarish. Shu
    bo'lim bo'lmasa, o'quvchi raqamlarni o'qib chiqadi-yu, hech nima
    qilmaydi.
    """
    ishlar: list[str] = []
    if h.tasdiq_kutilmoqda:
        ishlar.append(
            f"{h.tasdiq_kutilmoqda} ta ish tasdiqingizni kutmoqda — /tasdiq"
        )
    if h.lidlar:
        ishlar.append(
            f"{h.lidlar} ta mijoz telefon qoldirdi — qo'ng'iroq qiling"
        )
    if h.kp_ochiq:
        ishlar.append(
            f"{h.kp_ochiq} ta taklif javobsiz — mijozlarga eslating"
        )
    if h.javobsiz_savollar:
        ishlar.append(
            "Yuqoridagi javobsiz savollarni bilim bazasiga qo'shing"
        )
    if h.xatolar:
        ishlar.append(f"{h.xatolar} ta nosozlik bor — texnik ko'rsin")

    q = ["", CHIZIQ]
    if not ishlar:
        q.append("✅ Shoshilinch ish yo'q.")
        return q
    q.append("❗ E'TIBOR BERING")
    q.append("")
    q += [f"{i}. {ish}" for i, ish in enumerate(ishlar, 1)]
    return q

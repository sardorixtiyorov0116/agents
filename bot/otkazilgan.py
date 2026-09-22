"""O'tkazib yuborilgan rejali ishni ushlab qolish (catch-up).

MUAMMO
------
Tender tekshiruvi har kuni 09:00 da, haftalik hisobot dushanba 09:00 da
ishga tushadi. Lekin jadval faqat tizim YOQIQ bo'lganda ishlaydi.
Kompyuter o'chiq bo'lsa — o'sha kunlik xabar butunlay yo'qoladi va
hech kim buni sezmaydi.

Jonli o'lchov (2026-08-11): tender kuzatuvi 7 kunda atigi **2 marta**
ishlagan. Qolgan kunlari kompyuter o'chiq edi.

YECHIM
------
Har bajarilgan ish bazaga yoziladi (`rejali_ish` jadvali). Tizim ishga
tushganda tekshiriladi:

    bugungi belgilangan vaqt O'TGANMI?  va  bugun hali bajarilmaganmi?
        -> DARHOL bajariladi

Ya'ni soat 11:00 da kompyuter yoqilsa, 09:00 dagi tender xabari
shu zahoti keladi.

NEGA BAZAGA YOZILADI
--------------------
Xotirada saqlansa, tizim qayta ishga tushganda "bajarilmagan" deb
hisoblanadi va xabar TAKRORLANADI. Kun bazada turgani uchun bir
kunda bir marta ishlashi kafolatlanadi.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time as dt_time, timedelta

log = logging.getLogger("bot.otkazilgan")

# Ishga tushgandan keyin shuncha kutamiz, keyin o'tkazilganini bajaramiz.
# Bot Telegramga ulanib olsin va menejer xabarni "kutilmaganda" emas,
# tizim tayyor bo'lgach olsin.
KECHIKISH = 25.0

# Faqat ENG OXIRGI belgilangan vaqt ushlab qolinadi, hammasi emas.
# Kompyuter 5 kun o'chiq tursa, 5 ta tender xabari kelmaydi — bittasi,
# eng yangisi keladi. Eski tender e'lonlari bo'yicha ariza berib
# bo'lmaydi, ular faqat shovqin.
#
# Shu sababli kunlik ish uchun chegara kerak emas: "oxirgi belgilangan
# vaqt" har doim bugun yoki kecha. Haftalik ish uchun esa u 6 kungacha
# eski bo'lishi mumkin — dushanbagi hisobot jumada kelsa ham foydali,
# chunki u o'tgan HAFTA haqida.
ENG_KOP_KECHIKISH_KUN_HAFTALIK = 6


def bajarilishi_kerakmi(
    oxirgi_kun: str | None,
    belgilangan: dt_time,
    hozir: datetime,
    hafta_kuni: int | None = None,
) -> bool:
    """Ish o'tkazib yuborilganmi va uni hozir bajarish kerakmi.

    `hafta_kuni` berilsa (0 = dushanba), ish haftalik hisoblanadi:
    o'sha kundan beri bajarilmagan bo'lsa ushlab qolinadi.
    """
    # Kunlar farqi ham jadval mintaqasidagi sana bilan hisoblansin —
    # aks holda UTC dagi `hozir` chegarada bir kunga adashardi.
    if belgilangan.tzinfo is not None and hozir.tzinfo is not None:
        hozir = hozir.astimezone(belgilangan.tzinfo)
    kerakli_kun = _oxirgi_belgilangan_kun(belgilangan, hozir, hafta_kuni)
    if kerakli_kun is None:
        return False
    # Juda eskisini ushlab qolmaymiz (faqat haftalik ishda uchraydi).
    if (
        hafta_kuni is not None
        and (hozir.date() - kerakli_kun).days > ENG_KOP_KECHIKISH_KUN_HAFTALIK
    ):
        return False
    if oxirgi_kun is None:
        return True
    try:
        bajarilgan = date.fromisoformat(oxirgi_kun)
    except ValueError:
        return True
    return bajarilgan < kerakli_kun


def _oxirgi_belgilangan_kun(
    belgilangan: dt_time, hozir: datetime, hafta_kuni: int | None
) -> date | None:
    """Eng yaqin O'TGAN belgilangan sana (hali kelmagan bo'lsa None)."""
    # MINTAQALI VAQT. Jadval vaqti Toshkent mintaqasi bilan keladi. Python
    # mintaqali va mintaqasiz `time` ni solishtirmaydi (TypeError), shuning
    # uchun `hozir` shu mintaqaga o'tkaziladi va keyin ikkalasi ham bir
    # mintaqadagi "devor soati" sifatida solishtiriladi.
    if belgilangan.tzinfo is not None:
        if hozir.tzinfo is not None:
            hozir = hozir.astimezone(belgilangan.tzinfo)
        belgilangan = belgilangan.replace(tzinfo=None)
    if hafta_kuni is None:
        # Kunlik ish: bugungi vaqt o'tgan bo'lsa — bugun, aks holda kecha.
        if hozir.time() >= belgilangan:
            return hozir.date()
        return hozir.date() - timedelta(days=1)

    # Haftalik ish: shu haftaning belgilangan kuni.
    orqaga = (hozir.weekday() - hafta_kuni) % 7
    kun = hozir.date() - timedelta(days=orqaga)
    if kun == hozir.date() and hozir.time() < belgilangan:
        # Bugun o'sha kun, lekin vaqti hali kelmagan — o'tgan haftaniki.
        kun -= timedelta(days=7)
    return kun


async def ushlab_qol(
    baza,
    nomi: str,
    ish,
    ctx,
    belgilangan: dt_time,
    hafta_kuni: int | None = None,
    kechikish: float = KECHIKISH,
) -> bool:
    """O'tkazib yuborilgan bo'lsa ishni bajaradi.

    Natija: bajarildimi (`True`) yoki kerak emas edi (`False`).
    """
    # Jadval vaqti mintaqali bo'lsa — hozirgi vaqt ham O'SHA mintaqada.
    hozir = datetime.now(belgilangan.tzinfo)
    try:
        oxirgi = await baza.rejali_ish_kuni(nomi)
    except Exception as xato:
        log.warning("%s: oxirgi kunni o'qib bo'lmadi (%s)", nomi, xato)
        return False

    if not bajarilishi_kerakmi(oxirgi, belgilangan, hozir, hafta_kuni):
        return False

    kerakli = _oxirgi_belgilangan_kun(belgilangan, hozir, hafta_kuni)
    log.info(
        "%s: %s kungi ish o'tkazib yuborilgan (tizim o'chiq edi) — "
        "%.0f sekunddan keyin bajariladi",
        nomi, kerakli, kechikish,
    )
    await asyncio.sleep(kechikish)
    try:
        await ish(ctx)
    except Exception:
        log.exception("%s: o'tkazilgan ishni bajarishda xato", nomi)
        return False

    await belgila(baza, nomi, kerakli)
    log.info("%s: o'tkazilgan ish bajarildi (%s uchun)", nomi, kerakli)
    return True


async def belgila(baza, nomi: str, kun: date | None = None) -> None:
    """Ish bajarilganini bazaga yozadi."""
    try:
        await baza.rejali_ish_yoz(nomi, (kun or date.today()).isoformat())
    except Exception as xato:
        log.warning("%s: bajarilgan kunni yozib bo'lmadi (%s)", nomi, xato)

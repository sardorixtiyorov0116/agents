"""Suhbat konteksti — agent savol berganda, javob kontekstsiz qolmasin.

MUAMMO (jonli sinovda topilgan):

    mijoz: "Ofis uchun ventilyatsiya kerak, 120 kv metr"
    bot:   "Balandligi qancha? Necha kishi ishlaydi?"
    mijoz: "3 metr, 15 kishi"
    bot:   "Xona maydoni qancha?"          <- 120 m² UNUTILGAN

Har xabar mustaqil so'rov sifatida ishlanardi, shuning uchun mijoz uchun
bu cheksiz halqa bo'lardi. Real mijoz esa hech qachon hamma narsani
bitta xabarda yozmaydi.

YECHIM: agent `ANIQLIK_KERAK` qaytarganda asl so'rov bazaga yoziladi.
Keyingi xabar kelganda ikkalasi BIRLASHTIRILADI va router to'liq so'rovni
ko'radi.

MAVZU O'ZGARISHI. Ko'r-ko'rona birlashtirish yetarli emas:

    bot:   "Balandligi qancha?"
    mijoz: "ВК-250С haqida ayting"        <- javob emas, YANGI savol

Shuning uchun ikki qism BELGILANIB uzatiladi va router qaysi biri
haqiqiy so'rov ekanini o'zi hal qiladi (`app/router.py`, "SUHBAT
DAVOMI" qoidasi). Bu qo'shimcha model chaqiruvisiz ishlaydi.

Ikkala bot ham shu moduldan foydalanadi — mantiq bir joyda.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.baza import SUHBAT_MAKS_QADAM, Baza
from app.konvert import Holat
from app.orkestr import Natija

log = logging.getLogger("suhbat")

# Suhbat qaysi botda ketayotgani. Bir odam ikkala botga yozishi mumkin —
# suhbatlari aralashib ketmasligi kerak.
MIJOZ = "mijoz"
ICHKI = "ichki"
# Xaridor ilovasidagi «Climavent yordamchi» (`yordamchi/`). Kalit —
# backenddagi foydalanuvchi id'si, Telegram id emas, shuning uchun
# Telegram suhbati bilan bir kanalga tushmasligi SHART.
ILOVA = "ilova"

# Birlashtirilgan so'rovning maksimal uzunligi. Chegarasiz qo'yilsa,
# uzun suhbatda so'rov matni o'sib, har chaqiruvda ko'proq token yeydi.
MAKS_UZUNLIK = 2000

# Router shu belgilarga qarab qaysi qism yangi ekanini ajratadi.
OLDINGI = "[oldingi so'rov]"
YANGI = "[yangi xabar]"


def birlashtir(oldingi: str, yangi: str) -> str:
    """Ikki qismni router ajrata oladigan shaklda qo'shadi."""
    return "\n".join([f"{OLDINGI} {oldingi.strip()}", f"{YANGI} {yangi.strip()}"])


@dataclass(frozen=True)
class Davom:
    """Bir xabarni qanday ishlash kerakligi haqidagi qaror."""

    sorov: str            # routerga yuboriladigan matn (belgilangan)
    xom: str              # bazaga yoziladigan toza matn (belgilarsiz)
    davomimi: bool        # oldingi savolning davomimi
    qadam: int            # nechanchi almashinuv


async def boshla(baza: Baza, kanal: str, tg_id: int, matn: str) -> Davom:
    """Kelgan xabarni oldingi so'rov bilan birlashtiradi (kerak bo'lsa)."""
    try:
        oldingi = await baza.suhbat(kanal, tg_id)
    except Exception:
        log.exception("suhbat konteksti o'qilmadi: %s/%s", kanal, tg_id)
        oldingi = None

    if not oldingi:
        return Davom(sorov=matn, xom=matn, davomimi=False, qadam=1)

    yigilgan = birlashtir(oldingi["sorov"], matn)
    if len(yigilgan) > MAKS_UZUNLIK:
        # Suhbat cho'zilib ketdi — oxirgi xabardan qayta boshlaymiz.
        return Davom(sorov=matn, xom=matn, davomimi=False, qadam=1)

    return Davom(
        sorov=yigilgan,
        xom="\n".join([oldingi["sorov"].strip(), matn.strip()]),
        davomimi=True,
        qadam=int(oldingi["qadam"]) + 1,
    )


async def yakunla(
    baza: Baza, kanal: str, tg_id: int, davom: Davom, natija: Natija
) -> None:
    """Natijaga qarab kontekstni saqlaydi yoki tozalaydi.

    Kontekst IKKI holatda saqlanadi:

      1) `ANIQLIK_KERAK` — agent savol berdi, javob kutilyapti;
      2) javob BERILDI — mijoz ko'pincha shundan keyin aniqlashtiradi:
         "balandligini 4 metr qilsak?", "va 6 kishi ishlaydi",
         "narxi-chi?". Kontekst tozalansa, bu gaplar ma'nosini
         yo'qotadi va mijoz hammasini qaytadan yozishi kerak bo'ladi.

    Mavzu o'zgarganda ular birlashib ketmaydi: router `[yangi xabar]`
    mustaqil so'rov ekanini ko'rib, eskisini tashlab yuboradi.

    Tozalanadi: xato, mos agent yo'q, salomlashish, `/start`.
    """
    saqlanadi = natija.yakuniy.holat in (
        Holat.ANIQLIK_KERAK,
        Holat.TUGADI,
        Holat.TASDIQ_KUTILMOQDA,
    )
    if saqlanadi and davom.qadam < SUHBAT_MAKS_QADAM:
        savollar = "\n".join(
            str(s) for s in (natija.yakuniy.natija.get("savollar") or [])
        )
        try:
            await baza.suhbat_yoz(kanal, tg_id, davom.xom, savollar, davom.qadam)
        except Exception:
            # Kontekst saqlanmasa suhbat uziladi — buni JIM o'tkazib
            # yubormaymiz, aks holda sababini topib bo'lmaydi.
            log.exception("suhbat konteksti saqlanmadi: %s/%s", kanal, tg_id)
        return

    try:
        await baza.suhbat_ochir(kanal, tg_id)
    except Exception:
        log.exception("suhbat konteksti tozalanmadi: %s/%s", kanal, tg_id)


async def tozala(baza: Baza, kanal: str, tg_id: int) -> None:
    """Foydalanuvchi yangi mavzu boshladi (`/start`, salomlashish)."""
    try:
        await baza.suhbat_ochir(kanal, tg_id)
    except Exception:
        log.exception("suhbat konteksti tozalanmadi: %s/%s", kanal, tg_id)

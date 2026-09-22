"""Mijozlar boti uchun ruxsat — OQ RO'YXAT (allowlist) usuli.

Ichki botda "kim kirishi mumkin" tekshiriladi. Bu yerda esa foydalanuvchi
NOTANISH: bot ochiq, istalgan odam yozadi. Shuning uchun mantiq teskari:

    ICHKI BOT:   hamma agent mumkin, ba'zilari cheklangan
    MIJOZ BOTI:  hech qaysi agent mumkin emas, ikkitasi ochiq

Nega aynan shunday: yangi agent qo'shilganda u mijozlarga AVTOMATIK
ochilib qolmasligi kerak. Ro'yxatga qo'lda qo'shilmaguncha u yopiq.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from app.kontraktlar import Kontrakt, reyestr
from app.router import Reja

# Mijoz murojaat qila oladigan YAGONA agentlar.
#
#   product-spec (Sardor) — katalogdan mahsulot tanlash va xususiyatlar
#   hvac-calc   (Rustam) — ventilyatsiya hisobi
#   montaj-guide (Anvar) — o'rnatish bo'yicha maslahat
#
# ANVAR NEGA OCHIQ: mijoz "qayerga o'rnataman", "nega havo yo'q" deb
# ko'p so'raydi. Bu savolga javob berish sotuvga yordam beradi va
# menejerni bo'shatadi. Xavfli mavzular (ko'taruvchi konstruksiya,
# yong'in ventilyatsiyasi, elektr sxemasi) agent KODIDA ushlanadi va
# javob o'rniga "mutaxassisga murojaat qiling" deyiladi —
# `app/agentlar/montaj_maslahatchi.py::XAVFLI_MAVZU`.
#
# Qolganlari ataylab yopiq:
#   data-query    — ichki bazaga SQL yozadi (mijozlar, buyurtmalar)
#   catalog-admin — katalogni o'zgartiradi
#   hr-assist     — xodimlar ma'lumoti
#   proposal-builder, kp-tracker — narx va savdo hisoboti
#   price-monitor, competitor-watch — raqobatchilar ma'lumoti
#   marketing, sales-strategy, smm-analyst, tender-watch, legal-review
OCHIQ_AGENTLAR = frozenset({"product-spec", "hvac-calc", "montaj-guide"})

# Mijozga ko'rsatiladigan rad javobi. Agent nomi AYTILMAYDI — mijozga
# ichki tuzilma haqida ma'lumot bermaymiz.
MENEJERGA = (
    "Bu savolga menejerimiz aniqroq javob beradi.\n\n"
    "Telefon raqamingizni qoldiring — bugun bog'lanamiz. "
    "Yoki hoziroq: {telefon}"
)


def ochiq_kontraktlar() -> dict[str, Kontrakt]:
    """Router FAQAT shu kontraktlarni ko'radi.

    Bu xavfsizlik emas — xavfsizlik `rejani_tekshir` da qoladi. Bu TEJASH:
    to'liq reyestr router promptiga ~9 300 token qo'shadi, ochiq ikkitasi
    esa ~1 600. Har mijoz savolida farq sezilarli.

    Yopiq agent so'ralsa router "mos agent yo'q" deydi — natija bir xil:
    savol menejerga o'tadi.
    """
    return {r: k for r, k in reyestr().items() if r in OCHIQ_AGENTLAR}


@dataclass(frozen=True)
class MijozQarori:
    ruxsat: bool
    sabab: str = ""


class Tezlik:
    """Ikki qatlamli himoya: DAQIQALIK flood va KUNLIK kvota.

    NEGA IKKITA. Ular boshqa-boshqa narsadan himoya qiladi:

      - daqiqalik — skript bilan bombardimon qilishdan. Odam bunga
        urilmasligi kerak: uskuna qidirayotgan mijoz bir daqiqada
        6-7 savol berishi normal;
      - kunlik — XARAJATDAN. Gemini bepul tarifida kuniga JAMI 20 ta
        so'rov, ya'ni kunlik chegarasiz bitta qiziquvchan odam butun
        kvotani yeb qo'yishi va qolgan mijozlar javobsiz qolishi
        mumkin.

    JONLI XATO (2026-08-28): daqiqalik chegara 5 edi va oddiy mijoz
    unga urilardi — «Biroz sekinroq yozing» degan javob olib ketib
    qolardi.
    """

    def __init__(self, limit: int, oyna: float = 60.0,
                 kunlik: int = 0, kun_oynasi: float = 86400.0):
        self.limit = max(limit, 1)
        self.oyna = oyna
        self.kunlik = max(kunlik, 0)
        self.kun_oynasi = kun_oynasi
        self._tarix: dict[int, deque[float]] = {}
        self._kunlik: dict[int, deque[float]] = {}

    @staticmethod
    def _tozala(navbat: deque[float], hozir: float, oyna: float) -> None:
        while navbat and hozir - navbat[0] > oyna:
            navbat.popleft()

    def ruxsatmi(self, tg_id: int) -> bool:
        """Daqiqalik chegara. Faqat tekshiradi VA sanaydi."""
        hozir = time.monotonic()
        navbat = self._tarix.setdefault(tg_id, deque())
        self._tozala(navbat, hozir, self.oyna)
        if len(navbat) >= self.limit:
            return False
        navbat.append(hozir)
        return True

    def kunlik_ruxsatmi(self, tg_id: int) -> bool:
        """Kunlik kvota. `kunlik=0` bo'lsa chegara YO'Q."""
        if not self.kunlik:
            return True
        hozir = time.monotonic()
        navbat = self._kunlik.setdefault(tg_id, deque())
        self._tozala(navbat, hozir, self.kun_oynasi)
        if len(navbat) >= self.kunlik:
            return False
        navbat.append(hozir)
        return True


def rejani_tekshir(reja: Reja) -> MijozQarori:
    """Reja mijozga ochiq agentlardan iboratmi.

    BITTA yopiq agent bo'lsa ham butun reja rad etiladi: zanjir o'rtasida
    to'xtatish yarim javob beradi, bu mijozni chalg'itadi.
    """
    rollar = [q.agent for q in (reja.qadamlar or [])]
    if not rollar:
        return MijozQarori(False, "mos agent yo'q")
    yopiq = [r for r in rollar if r not in OCHIQ_AGENTLAR]
    if yopiq:
        return MijozQarori(False, f"mijozga yopiq: {', '.join(yopiq)}")
    return MijozQarori(True)

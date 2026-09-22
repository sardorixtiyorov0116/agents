"""Limitga yaqinlashganda OLDINDAN ogohlantirish.

NEGA KERAK
----------
`/sarf` sonni ko'rsatadi, lekin uni MENEJER YOZISHI kerak. Hech kim
har soatda buyruq yozib turmaydi — demak limit baribir kutilmaganda
uriladi, aynan KP so'ralgan payt.

Bu modul teskari yo'nalishda ishlaydi: chegara oshganda o'zi xabar
beradi.

UCHTA MUSTAQIL SABAB
--------------------
1. FOIZ — sarf kunlik limitning 75/90/100% iga yetdi.
2. LIMIT XATOSI — Google `RESOURCE_EXHAUSTED` qaytardi.
3. LOKAL MODELGA TUSHILDI — bulut zanjiri to'liq yiqilgan.

Uchinchisi JIM XAVF edi: zanjir oxirida lokal model turadi va u
ishlayveradi, ya'ni tizim "sog'" ko'rinadi. Lekin javob sifati
o'lchangan darajada pastroq (`app/ollama.py`): tender saralashda
aniqlik 1.000 dan 0.718 ga tushadi. Menejer buni BILISHI kerak —
aks holda pastroq javobni odatdagi javob deb qabul qiladi.

Ikkinchisi shunchaki qo'shimcha emas, ASOSIYSI. `GEMINI_KUNLIK_LIMIT`
standart holatda 0 ("noma'lum") — chunki Google chegaralarni e'lonsiz
o'zgartiradi va biz taxminiy raqam yozishni rad etdik. Ya'ni ko'p
o'rnatmada foiz yo'li UMUMAN ishlamaydi. Xato yo'li esa hech qanday
sozlamaga bog'liq emas va har doim ishlaydi.

TAKRORLANMASLIK
---------------
Har chegara uchun kvota kunida BIR MARTA xabar beriladi. Aks holda
limitga yetgan bot har chaqiruvda xabar yuborib, menejer telefonini
ko'mib tashlardi — va o'sha xabarlar orasida haqiqiy KP yo'qolardi.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .sarf import kvota_kuni, limit_xatosimi

log = logging.getLogger("sarf.ogoh")

# Foiz chegaralari — kattadan kichikka tekshiriladi.
CHEGARALAR: tuple[float, ...] = (1.00, 0.90, 0.75)

# Nechta limit xatosidan keyin xabar berilsin.
#
# Bitta xato tasodif bo'lishi mumkin (bir zumlik RPM cho'qqisi). Uchtasi
# esa tizimli: kunlik kvota tugagan yoki so'rov oqimi juda tez.
XATO_CHEGARASI = 3

# Lokal (zaxira) provayder nomi — `app/llm.py` dagi PROVAYDERLAR bilan
# bir xil bo'lishi shart.
LOKAL_PROVAYDER = "ollama"

BELGILAR = {1.00: "⛔", 0.90: "🔴", 0.75: "🟡"}


class Ogohlantiruvchi:
    """Sarf yozuvlarini kuzatadi va kerak bo'lganda matn qaytaradi.

    Telegramni BILMAYDI — faqat matn qaytaradi. Shu tufayli testda
    tarmoqsiz tekshiriladi va keyin panelda ham ishlatilishi mumkin.
    """

    def __init__(self, baza: Any, limit_ol: Callable[[str], int]):
        self.baza = baza
        self.limit_ol = limit_ol
        # (provayder, kun) -> yuborilgan chegaralar
        self._yuborilgan: dict[tuple[str, str], set[str]] = {}
        # (provayder, kun) -> sanoq. Bazaga har chaqiruvda bormaslik uchun.
        self._son: dict[tuple[str, str], int] = {}
        self._xato_soni: dict[tuple[str, str], int] = {}

    async def yozuvdan_keyin(self, yozuv: dict[str, Any]) -> str | None:
        """Bitta sarf yozuvidan keyin chaqiriladi.

        Ogohlantirish kerak bo'lsa — matn, aks holda `None`.
        """
        provayder = str(yozuv.get("provayder") or "")
        kun = str(yozuv.get("kun") or kvota_kuni(provayder))
        kalit = (provayder, kun)

        # Kun almashgan bo'lsa eski holat kerak emas.
        self._eski_kunlarni_tozala(provayder, kun)

        self._son[kalit] = self._son.get(kalit, 0) + 1
        if limit_xatosimi(yozuv.get("xato")):
            self._xato_soni[kalit] = self._xato_soni.get(kalit, 0) + 1

        matn = self._lokal_ogohi(kalit)
        if matn:
            return matn
        matn = await self._xato_ogohi(kalit)
        if matn:
            return matn
        return await self._foiz_ogohi(kalit)

    # --- Sabab 3: lokal modelga tushildi -------------------------------------

    def _lokal_ogohi(self, kalit: tuple[str, str]) -> str | None:
        """Zaxira lokal model ishlagan bo'lsa — kuniga bir marta xabar.

        Bazaga BORMAYDI: bu yerda son emas, HODISA muhim. Bitta
        chaqiruv ham bulut zanjiri to'liq yiqilganini bildiradi.
        """
        provayder, kun = kalit
        if provayder != LOKAL_PROVAYDER:
            return None
        if not self._birinchi_marta(kalit, "lokal"):
            return None
        return (
            "🟠 Bulut modellari javob bermadi — LOKAL modelga o'tildi\n\n"
            f"Kvota kuni: {kun}\n\n"
            "Javoblar ishlayapti, lekin sifati pastroq: lokal model "
            "tender saralashda keraksiz e'lonlarni ham mos deb "
            "belgilaydi va ishonch darajasini ajratmaydi.\n\n"
            "Muhim qarorni bulut tiklangach qayta tekshiring."
        )

    # --- Sabab 1: limit xatolari ---------------------------------------------

    async def _xato_ogohi(self, kalit: tuple[str, str]) -> str | None:
        provayder, kun = kalit
        if self._xato_soni.get(kalit, 0) < XATO_CHEGARASI:
            return None
        if not self._birinchi_marta(kalit, "xato"):
            return None

        # Xotiradagi sanoq faqat ARZON darvoza. Xabar yuborishdan oldin
        # haqiqiy son bazadan olinadi: panel va bot alohida jarayonlar,
        # xotiradagi sanoq ikkalasining yig'indisini bilmaydi.
        xatolar = await self.baza.sarf_xatolari(provayder, kun, chek=50)
        haqiqiy = sum(1 for x in xatolar if limit_xatosimi(x.get("xato")))
        if haqiqiy < XATO_CHEGARASI:
            self._yuborilgan[kalit].discard("xato")
            return None

        oxirgi = next((x for x in xatolar if limit_xatosimi(x.get("xato"))), {})
        return (
            f"⛔ {provayder}: limit xatosi {haqiqiy} marta\n\n"
            f"Kvota kuni: {kun}\n"
            f"Oxirgisi: {str(oxirgi.get('vaqt') or '')[11:16]} "
            f"({oxirgi.get('rol') or '—'})\n\n"
            "Model so'rovlarni rad etyapti. Bu paytda:\n"
            "• /kp qo'lda to'ldirish BARIBIR ishlaydi — hisob va hujjat\n"
            "  modelsiz tuziladi\n"
            "• TZ fayldan avtomatik to'ldirish va erkin matn ishlamaydi\n\n"
            "Batafsil: /sarf"
        )

    # --- Sabab 2: limitning foizi --------------------------------------------

    async def _foiz_ogohi(self, kalit: tuple[str, str]) -> str | None:
        provayder, kun = kalit
        limit = self.limit_ol(provayder)
        if limit <= 0:
            return None                      # limit noma'lum — foiz yo'q

        taxminiy = self._son.get(kalit, 0)
        chegara = self._oshgan_chegara(taxminiy, limit)
        if chegara is None or not self._birinchi_marta(kalit, f"foiz-{chegara}"):
            return None

        yigindi = await self.baza.sarf_kunlik(provayder, kun)
        haqiqiy = int(yigindi.get("soni") or 0)
        self._son[kalit] = haqiqiy
        if self._oshgan_chegara(haqiqiy, limit) != chegara:
            self._yuborilgan[kalit].discard(f"foiz-{chegara}")
            return None

        qolgan = max(limit - haqiqiy, 0)
        belgi = BELGILAR.get(chegara, "⚠️")
        sarlavha = (
            f"{belgi} {provayder}: kunlik limit TUGADI"
            if chegara >= 1.0
            else f"{belgi} {provayder}: kunlik limitning {chegara:.0%} i ishlatildi"
        )
        return (
            f"{sarlavha}\n\n"
            f"Kvota kuni: {kun}\n"
            f"So'rovlar: {haqiqiy}/{limit}\n"
            f"Qolgan: {qolgan}\n\n"
            + ("Yangi so'rovlar rad etiladi. /kp qo'lda to'ldirish ishlayveradi.\n\n"
               if chegara >= 1.0 else "")
            + "Batafsil: /sarf"
        )

    @staticmethod
    def _oshgan_chegara(soni: int, limit: int) -> float | None:
        ulush = soni / limit
        for chegara in CHEGARALAR:
            if ulush >= chegara:
                return chegara
        return None

    # --- Holat ---------------------------------------------------------------

    def _birinchi_marta(self, kalit: tuple[str, str], belgi: str) -> bool:
        yuborilgan = self._yuborilgan.setdefault(kalit, set())
        if belgi in yuborilgan:
            return False
        yuborilgan.add(belgi)
        return True

    def _eski_kunlarni_tozala(self, provayder: str, kun: str) -> None:
        eskilar = [k for k in self._yuborilgan
                   if k[0] == provayder and k[1] != kun]
        for k in eskilar:
            self._yuborilgan.pop(k, None)
            self._son.pop(k, None)
            self._xato_soni.pop(k, None)

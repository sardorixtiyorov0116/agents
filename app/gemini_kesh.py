"""Gemini prompt keshi — router promptining katta qismini takror to'lamaslik.

NEGA KERAK
----------
O'lchandi (2026-08-28): bitta erkin matnli so'rov 8 465 kirish tokeni
yeydi, shundan 4 412 tasi — kontraktlar ro'yxati. U HAR SO'ROVDA bir
xil, lekin har safar to'liq to'lanadi.

Anthropic tomonida bu allaqachon hal: `app/router.py` o'sha blokka
`cache_control` qo'yadi. Gemini adapterida esa u jimgina tashlanardi.

BEPUL TARIFDA ISHLAMAYDI — BU O'LCHANGAN
----------------------------------------
2026-08-28 da tekshirildi:

  - ochiq kesh (`cachedContents`): 429, «TotalCachedContentStorage
    TokensPerModelFreeTier limit=0» — ya'ni butunlay yopiq;
  - avtomatik kesh: bir xil 4 525 tokenli prefiks ikki marta
    yuborilganda `cachedContentTokenCount` ikkalasida ham 0.

Shuning uchun bu modul HOZIR o'chiq turadi va birinchi urinishdayoq
o'zini o'chiradi. Billing yoqilganda esa qo'shimcha kodsiz ishlaydi.

NEGA ALLAQACHON YOZILDI
-----------------------
Billing yoqilgan kuni bu kod SINALMAGAN holda ishga tushishi eng yomon
variant bo'lardi. Mantiq shu yerda, testlari soxta transport ustida —
ya'ni Google'siz ham tekshirilgan.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

log = logging.getLogger("gemini.kesh")

# Keshga arziydigan eng kichik blok. Kichik bloklarni keshlash
# foydasiz: saqlash haqi tejamdan oshib ketadi.
ENG_KAM_TOKEN = 2048

# Belgidan tokenga taxminiy nisbat — faqat "arziydimi" degan darvoza
# uchun. Aniq son kerak emas.
BELGI_TOKENGA = 3

# Kesh qancha yashaydi. Router prompti kun bo'yi o'zgarmaydi, lekin
# uzoq TTL saqlash haqini oshiradi.
TTL_SONIYA = 3600

# Muddatidan qancha oldin yangilanadi — so'rov o'rtasida tugab
# qolmasin.
ZAXIRA_SONIYA = 300


class KeshYopiq(RuntimeError):
    """Provayder keshni rad etdi (bepul tarif yoki o'chirilgan)."""


class GeminiKesh:
    """Bitta matn bloki uchun kesh yozuvini boshqaradi.

    Telegramni ham, bazani ham bilmaydi. HTTP `so'rovchi` tashqaridan
    beriladi — shu tufayli testda soxta transport bilan tekshiriladi.
    """

    def __init__(
        self,
        sorovchi: Callable[[str, str, dict[str, Any]], Awaitable[Any]],
        ttl: int = TTL_SONIYA,
    ):
        self._sorov = sorovchi
        self._ttl = ttl
        # (model, matn) -> (kesh nomi, qachongacha amal qiladi)
        self._keshlar: dict[tuple[str, str], tuple[str, float]] = {}
        # Provayder rad etgan bo'lsa qayta urinmaymiz: har so'rovda
        # 429 olish sekin va kvotani yeydi.
        self._yopiq = False

    @property
    def yopiqmi(self) -> bool:
        return self._yopiq

    @staticmethod
    def arziydimi(matn: str) -> bool:
        """Bu blokni keshlash foydalimi?"""
        return len(matn or "") // BELGI_TOKENGA >= ENG_KAM_TOKEN

    async def nomi(self, model: str, matn: str) -> str | None:
        """Shu matn uchun kesh nomi. Yo'q yoki imkonsiz bo'lsa `None`.

        XATO YUTILADI. Kesh — TEJAMKORLIK, majburiyat emas: u ishlamasa
        so'rov keshsiz ketaveradi. Aks holda kesh nosozligi butun
        tizimni to'xtatardi.
        """
        if self._yopiq or not self.arziydimi(matn):
            return None

        kalit = (model, matn)
        yozuv = self._keshlar.get(kalit)
        if yozuv is not None and yozuv[1] - ZAXIRA_SONIYA > time.monotonic():
            return yozuv[0]

        try:
            nom = await self._yarat(model, matn)
        except KeshYopiq as xato:
            # Bir marta aytamiz va boshqa urinmaymiz.
            log.info("Gemini keshi mavjud emas, keshsiz davom etamiz: %s", xato)
            self._yopiq = True
            return None
        except Exception:
            log.warning("Gemini keshi yaratilmadi", exc_info=True)
            return None

        self._keshlar[kalit] = (nom, time.monotonic() + self._ttl)
        log.info("Gemini keshi yaratildi: %s (%d belgi)", nom, len(matn))
        return nom

    async def _yarat(self, model: str, matn: str) -> str:
        javob = await self._sorov(
            "POST",
            "cachedContents",
            {
                # Gemini `models/` prefiksini talab qiladi.
                "model": model if model.startswith("models/") else f"models/{model}",
                "systemInstruction": {"parts": [{"text": matn}]},
                "ttl": f"{self._ttl}s",
            },
        )
        kod = getattr(javob, "status_code", 200)
        if kod == 429:
            raise KeshYopiq(_xabar(javob))
        if kod >= 400:
            raise RuntimeError(f"HTTP {kod}: {_xabar(javob)}")
        nom = (javob.json() or {}).get("name")
        if not nom:
            raise RuntimeError("javobda kesh nomi yo'q")
        return str(nom)


def _xabar(javob: Any) -> str:
    try:
        return str((javob.json().get("error") or {}).get("message") or "")[:200]
    except Exception:
        return str(getattr(javob, "text", ""))[:200]

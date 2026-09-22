"""Zaxira zanjiri — bir model yiqilsa, keyingisi urinadi.

NEGA KERAK
----------
Butun tizim bitta modelga bog'lanib qolgan edi: `TEZ_MODEL` bitta nom,
u rad etsa so'rov tugaydi. 2026-08-27 da o'lchandi — Gemini bepul
tarifi "high demand" bilan rad etdi va butun /kp oqimining TZ o'qish
qismi ishlamay qoldi. Bepul tarifda bu tasodif emas, kutiladigan hol.

Endi `TEZ_MODEL` vergul bilan ajratilgan RO'YXAT bo'lishi mumkin:

    TEZ_MODEL=gemini-3.5-flash,claude-haiku-4-5

Birinchisi yiqilsa ikkinchisi urinadi. Bitta nom yozilsa — hech qanday
o'ram qo'shilmaydi va xatti-harakat avvalgidek qoladi.

QAYSI XATODA O'TILADI — ENG NOZIK QARORI
----------------------------------------
400 (Bad Request) da O'TILMAYDI. Sababi aniq: `app/agentlar/asos.py`
structured-output rad etilganini AYNAN `BadRequestError` turidan
biladi va matn rejimiga o'zi o'tadi. Agar biz 400 ni ushlab boshqa
modelga o'tsak, o'sha zaxira yo'l ishlamay qoladi — va sxemani
tushunmaydigan model o'rniga sxemani tushunmaydigan BOSHQA modelga
borib, baribir yiqilardik, faqat sekinroq.

Shuningdek o'z kodimizdagi xato (`TypeError` va h.k.) ham o'tkazilmaydi:
u boshqa modelda ham aynan takrorlanardi. Faqat `anthropic.APIError`
oilasi o'tkaziladi — ya'ni provayder qaytargan javob.

DAM OLISH (cooldown)
--------------------
Kunlik kvota tugaganda har so'rov Gemini'ni qayta-qayta urinib, har
safar to'liq javob kutadi — bu sekinlik menejerga ko'rinadi. Limit
xatosidan keyin model qisqa muddatga chetga suriladi va zanjir
to'g'ridan-to'g'ri keyingisidan boshlanadi.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Sequence

import anthropic

from .sarf import limit_xatosimi

log = logging.getLogger("zanjir")

# Limit xatosidan keyin model necha soniya chetda tursin.
DAM_MUDDATI = 300.0

# Boshqa (vaqtinchalik) xatolardan keyingi qisqaroq dam.
QISQA_DAM = 30.0


def otish_kerakmi(xato: BaseException) -> bool:
    """Shu xatoda keyingi modelga o'tiladimi?"""
    # O'z kodimizdagi xato boshqa modelda ham takrorlanadi.
    if not isinstance(xato, anthropic.APIError):
        return False
    # 400 — `asos.py` uni O'ZI ushlaydi (structured output zaxirasi).
    if isinstance(xato, anthropic.BadRequestError):
        return False
    kod = getattr(xato, "status_code", None)
    if kod == 400:
        return False
    return True


class ZanjirLlm:
    """Modellarni ketma-ket sinaydigan `Llm`.

    Telegramni ham, bazani ham bilmaydi. Har urinish `app/sarf.py`
    orqali alohida yoziladi (chunki o'lchov provayder ichida), shuning
    uchun `/sarf` da zanjir qanday ishlagani ko'rinib turadi: yiqilgan
    urinish xato bilan, ishlagani muvaffaqiyat bilan.
    """

    def __init__(self, modellar: Sequence[str], yasovchi: Callable[[str], Any]):
        self.modellar = list(modellar)
        if not self.modellar:
            raise ValueError("ZanjirLlm: kamida bitta model kerak")
        self._yasovchi = yasovchi
        self._mijozlar: dict[str, Any] = {}
        # model -> qachongacha chetda turadi (monotonic soniya)
        self._dam: dict[str, float] = {}

    @property
    def VEB_QIDIRUV(self) -> bool:
        """Zanjirda veb qidiruvni biladigan model bormi?

        KAMIDA BITTASI yetarli emas deb hisoblanadi — aksincha, agar
        birinchi model qidira olsa ham, u yiqilib zaxiraga o'tilsa
        qidiruv yo'qoladi. Lekin bu yerda maqsad AGENTGA oldindan
        aytish, ya'ni "umuman imkoniyat bormi" savoli. Zanjir to'liq
        qidiruvsiz bo'lsa — agent buni ANIQ biladi.
        """
        from .llm import veb_qidiruv_qollanadi

        return any(veb_qidiruv_qollanadi(m) for m in self.modellar)

    # --- Llm protokoli -------------------------------------------------------

    async def javob(self, **soro: Any) -> Any:
        birinchi_xato: BaseException | None = None
        sinalganlar: list[str] = []

        for model in self._navbat():
            sinalganlar.append(model)
            try:
                javob = await self._mijoz(model).javob(**{**soro, "model": model})
            except BaseException as xato:
                if not otish_kerakmi(xato):
                    raise
                if birinchi_xato is None:
                    birinchi_xato = xato
                self._damga_qoy(model, xato)
                log.warning("zanjir: %s yiqildi (%s), keyingisiga o'tildi",
                            model, type(xato).__name__)
                continue
            if len(sinalganlar) > 1:
                log.info("zanjir: %s javob berdi (%d urinishdan keyin)",
                         model, len(sinalganlar))
            return javob

        # Hammasi yiqildi — BIRINCHI (asosiy model) xatosi uzatiladi.
        #
        # Nega birinchisi, oxirgisi emas: menejer ko'radigan xabar shu
        # xatodan yasaladi (`llm_xato_matni`). Zanjir
        # `gemini,claude-haiku` bo'lib Gemini kvotasi tugasa va
        # Anthropic'da mablag' bo'lmasa, oxirgi xato "hisobda mablag'
        # yo'q" bo'lardi — bu ASL sabab emas va menejerni noto'g'ri
        # tomonga yuborardi.
        #
        # Xato turi O'ZGARTIRILMAYDI: chaqiruvchi kod (`asos.py`) turga
        # qarab qaror qabul qiladi.
        log.error("zanjir: hamma model yiqildi (%s)", ", ".join(sinalganlar))
        if birinchi_xato is not None:
            raise birinchi_xato
        raise RuntimeError("zanjirda ishlaydigan model qolmadi")

    async def tekshir(self) -> str | None:
        """`/salomat` uchun — kamida bittasi ishlasa, zanjir sog'."""
        sabablar = []
        for model in self.modellar:
            mijoz = self._mijoz(model)
            tekshiruvchi = getattr(mijoz, "tekshir", None)
            if tekshiruvchi is None:
                continue
            sabab = await tekshiruvchi()
            if sabab is None:
                return None
            sabablar.append(f"{model}: {sabab}")
        return "; ".join(sabablar) if sabablar else None

    # --- Ichki ---------------------------------------------------------------

    def _mijoz(self, model: str) -> Any:
        if model not in self._mijozlar:
            self._mijozlar[model] = self._yasovchi(model)
        return self._mijozlar[model]

    def _navbat(self) -> list[str]:
        """Sinaladigan modellar — dam olayotganlari oxiriga suriladi.

        CHETGA SURILADI, O'CHIRILMAYDI: dam muddati noto'g'ri
        hisoblangan bo'lsa ham (masalan kvota kutilganidan erta
        yangilangan) tizim butunlay to'xtab qolmasin.
        """
        hozir = time.monotonic()
        tayyor = [m for m in self.modellar if self._dam.get(m, 0.0) <= hozir]
        dam_olayotgan = [m for m in self.modellar if self._dam.get(m, 0.0) > hozir]
        return tayyor + dam_olayotgan

    def _damga_qoy(self, model: str, xato: BaseException) -> None:
        muddat = DAM_MUDDATI if limit_xatosimi(str(xato)) else QISQA_DAM
        self._dam[model] = time.monotonic() + muddat


def zanjir_yasa(modellar: Sequence[str], yasovchi: Callable[[str], Any]) -> Any:
    """Bitta model bo'lsa — O'RAMSIZ o'zini qaytaradi.

    Shu tufayli bitta model yozilgan eski o'rnatmalarda xatti-harakat
    aynan avvalgidek qoladi: qo'shimcha qatlam ham, boshqacha xato
    ham yo'q.
    """
    modellar = [m for m in modellar if m]
    if not modellar:
        raise ValueError("zanjir_yasa: model ro'yxati bo'sh")
    if len(modellar) == 1:
        return yasovchi(modellar[0])
    return ZanjirLlm(modellar, yasovchi)

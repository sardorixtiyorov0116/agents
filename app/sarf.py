"""LLM sarfini hisoblash — nechta so'rov, qancha token, qancha xato.

NEGA KERAK
----------
Tizim bepul tarifdagi modelga tayanib qolganda limit real xavfga aylanadi.
Ilgari sarf umuman hisoblanmasdi: limitga yaqinlashganimizni LIMITGA
URILGANDA bilardik, undan oldin emas. Menejer esa buni KP so'ragan payt,
mijoz kutib turganda ko'rardi.

Bu modul har bir LLM chaqiruvini yozib boradi va `/sarf` buyrug'i orqali
ko'rsatadi.

KVOTA KUNI — NOZIK JOY
----------------------
Google bepul tarifning kunlik limiti TINCH OKEANI vaqti bo'yicha yarim
tunda yangilanadi, Toshkent yarim tunida emas. Ikkalasi orasida 12-13
soat farq bor: Toshkentda 27-avgust ertalab bo'lsa, Google uchun hali
26-avgust kechqurun. Shuning uchun kun MAHALLIY emas, PROVAYDER vaqti
bo'yicha hisoblanadi — aks holda ko'rsatkichimiz Google ko'rsatkichi
bilan mos kelmasdi va bir kunning sarfi ikki kunga bo'linib ketardi.
"""

from __future__ import annotations

import contextvars
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

log = logging.getLogger("sarf")

# Provayderning kvota mintaqasi. Bu yerda yo'q provayder UTC bo'yicha
# hisoblanadi.
KVOTA_MINTAQASI = {
    "gemini": "America/Los_Angeles",   # Google bepul tarif
}

NOMA_LUM_ROL = "—"

# Joriy rol. `ContextVar` tanlandi, chunki chaqiruv zanjiri uzun
# (orkestr -> agent -> asos -> llm) va har bosqichga `rol` parametrini
# qo'shish har bir agentga tegishni talab qilardi. ContextVar asyncio
# vazifalari orasida to'g'ri ko'chadi.
_rol: contextvars.ContextVar[str] = contextvars.ContextVar("llm_roli", default=NOMA_LUM_ROL)


@contextmanager
def rol_bilan(rol: str):
    """Shu blok ichidagi LLM chaqiruvlari `rol` nomi bilan yoziladi."""
    belgi = _rol.set(rol or NOMA_LUM_ROL)
    try:
        yield
    finally:
        _rol.reset(belgi)


def joriy_rol() -> str:
    return _rol.get()


def kvota_kuni(provayder: str, payt: datetime | None = None) -> str:
    """Shu provayder kvotasi uchun "bugun" qaysi sana (YYYY-MM-DD)."""
    payt = payt or datetime.now(timezone.utc)
    mintaqa = KVOTA_MINTAQASI.get(provayder)
    if mintaqa:
        try:
            payt = payt.astimezone(ZoneInfo(mintaqa))
        except Exception:  # tzdata yo'q bo'lsa — UTC bilan davom etamiz
            log.warning("mintaqa topilmadi: %s, UTC ishlatiladi", mintaqa)
    return payt.date().isoformat()


# --- Yozuvchi ----------------------------------------------------------------
#
# Baza obyekti bu yerga TASHQARIDAN beriladi (`yozuvchini_ol`). Sabab:
# `app/llm.py` bazaga bog'lanib qolmasligi kerak — u testlarda va
# alohida skriptlarda bazasiz ham ishlatiladi.

_yozuvchi: Callable[[dict[str, Any]], Awaitable[None]] | None = None


def yozuvchini_ol(funksiya: Callable[[dict[str, Any]], Awaitable[None]] | None) -> None:
    """Sarf yozuvlarini qabul qiladigan funksiyani o'rnatadi."""
    global _yozuvchi
    _yozuvchi = funksiya


def _tokenlar(javob: Any) -> tuple[int, int, int]:
    """Javobdan (kirish, chiqish, keshdan) tokenlari.

    Ikkala provayder ham bir xil nom ishlatadi (`usage.input_tokens`),
    chunki Gemini javobi `app/gemini.py` da Anthropic shakliga
    o'girilgan.

    KESHDAN o'qilgan tokenlar ALOHIDA hisoblanadi: ular arzon (odatda
    to'liq narxning 10%i) va ularni oddiy kirish bilan qo'shib
    yuborsak, xarajat KO'P ko'rinardi.
    """
    sarf = getattr(javob, "usage", None)
    if sarf is None:
        return 0, 0, 0
    return (
        int(getattr(sarf, "input_tokens", 0) or 0),
        int(getattr(sarf, "output_tokens", 0) or 0),
        int(getattr(sarf, "cache_read_input_tokens", 0) or 0),
    )


async def qayd_bilan(provayder: str, model: str, chaqiruv: Callable[[], Awaitable[Any]]) -> Any:
    """`chaqiruv()` ni bajaradi va sarfini yozadi.

    XATO YUTILMAYDI. Chaqiruvning xatosi chaqiruvchiga o'zgarishsiz
    yetib boradi — faqat yozuvda qayd etiladi. Aks holda `asos.py` dagi
    zaxira yo'llar (structured output rad etilishi) ishlamay qolardi.

    Yozuvning O'ZI xato bersa — jim o'tiladi. Hisob yuritish asosiy
    ishni to'xtatishi mumkin emas.
    """
    boshlandi = time.perf_counter()
    xato_matni: str | None = None
    javob: Any = None
    try:
        javob = await chaqiruv()
        return javob
    except BaseException as xato:
        xato_matni = f"{type(xato).__name__}: {xato}"[:300]
        raise
    finally:
        kirish, chiqish, keshdan = _tokenlar(javob)
        await _yoz({
            "vaqt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kun": kvota_kuni(provayder),
            "provayder": provayder,
            "model": model or "",
            "rol": joriy_rol(),
            "kirish": kirish,
            "chiqish": chiqish,
            "keshdan": keshdan,
            "ms": int((time.perf_counter() - boshlandi) * 1000),
            "xato": xato_matni,
        })


async def _yoz(yozuv: dict[str, Any]) -> None:
    if _yozuvchi is None:
        return
    try:
        await _yozuvchi(yozuv)
    except Exception:
        log.debug("sarf yozilmadi", exc_info=True)


# --- Xato turini ajratish ----------------------------------------------------
#
# Hamma xato ham limit emas. Limitni ALOHIDA ko'rsatish kerak: 3 ta
# tarmoq uzilishi bilan 3 ta kvota xatosi butunlay boshqa ma'no beradi.

LIMIT_BELGILARI = ("resource_exhausted", "quota", "rate_limit", "429", "too many requests")


def limit_xatosimi(xato: str | None) -> bool:
    past = (xato or "").lower()
    return any(belgi in past for belgi in LIMIT_BELGILARI)

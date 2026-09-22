"""Anthropic API bilan ishlash qatlami.

Bu yerda bitta yupqa `Llm` protokoli bor — test paytida uni soxta (fake)
implementatsiya bilan almashtirish mumkin, shunda router va agentlarni
API'ga chiqmasdan tekshirib ko'rish oson.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from collections.abc import Sequence
from typing import Any, Protocol

import anthropic

from .config import sozlama
from .sarf import qayd_bilan


class Llm(Protocol):
    """Router va agentlar shu interfeys orqali modelga murojaat qiladi."""

    async def javob(self, **soro: Any) -> Any:  # pragma: no cover - protokol
        """`messages.create` chaqiruvini bajaradi va javob obyektini qaytaradi."""
        ...


# HTTP kodi -> nima qilish kerakligi
XATO_IZOHLARI: dict[int, str] = {
    401: (
        "ANTHROPIC_API_KEY yaroqsiz yoki bekor qilingan. "
        ".env faylidagi kalitni yangilang va serverni qayta ishga tushiring."
    ),
    403: "Bu API kalitida so'ralgan modelga ruxsat yo'q.",
    404: "So'ralgan model topilmadi — .env dagi LLM_MODEL nomini tekshiring.",
    429: "So'rovlar limitiga yetildi. Bir necha soniyadan keyin qayta urinib ko'ring.",
    500: "Anthropic serverida ichki xato. Qayta urinib ko'ring.",
    529: "Anthropic serveri hozir band. Bir oz kutib qayta urinib ko'ring.",
}

# 400 xatosi ichidagi maxsus holatlar (kod bir xil, sababi har xil)
XATO_KALIT_SOZLARI: list[tuple[str, str]] = [
    (
        "credit balance",
        "Anthropic hisobingizdagi mablag' tugagan. Konsolda balansni to'ldiring.",
    ),
    (
        "max_tokens",
        "So'rov modelning token chegarasidan oshdi — .env dagi MAKS_TOKEN ni kamaytiring.",
    ),
    # GEMINI xatolari. Tizim `TEZ_MODEL` orqali Gemini'ni ham ishlatadi
    # (router, TZ o'qish), shuning uchun uning kvota xatosi ham
    # menejerga TUSHUNARLI bo'lishi kerak — xom xato matni emas.
    (
        "resource_exhausted",
        "Gemini kunlik/daqiqalik limitiga yetildi. Bir necha daqiqadan keyin "
        "urinib ko'ring — yoki savollarga qo'lda javob bering, /kp buningsiz "
        "ham ishlaydi.",
    ),
    (
        "quota",
        "Gemini kvotasi tugadi. Google AI Studio'da limitni tekshiring — "
        "/kp qo'lda to'ldirish orqali baribir ishlaydi.",
    ),
    (
        "api key not valid",
        "GEMINI_API_KEY yaroqsiz. .env dagi kalitni yangilang va serverni "
        "qayta ishga tushiring.",
    ),
]


def llm_xato_matni(xato: Exception) -> str:
    """Anthropic xatosini menejer tushunadigan jumlaga aylantiradi.

    XATO TURI O'ZGARMAYDI — faqat MATN tarjima qilinadi. Buning sababi:
    `asos.py` structured-output rad etilganini aynan `BadRequestError`
    matnidan biladi. Xatoni o'rab qo'ysak, o'sha zaxira yo'l buzilardi.
    """
    xom = str(xato).lower()
    for kalit, izoh in XATO_KALIT_SOZLARI:
        if kalit in xom:
            return izoh
    if isinstance(xato, anthropic.APIConnectionError):
        return "Anthropic serveriga ulanib bo'lmadi — internet aloqasini tekshiring."
    kod = getattr(xato, "status_code", None)
    izoh = XATO_IZOHLARI.get(kod) if isinstance(kod, int) else None
    if izoh:
        return izoh
    if kod == 429:
        return XATO_IZOHLARI[429]
    return f"Anthropic API xatosi (HTTP {kod})." if kod else f"LLM xatosi: {xato}"


# `output_config.effort` NI QABUL QILMAYDIGAN modellar.
#
# Effort — yangi avlod modellaridagi "qanchalik chuqur o'ylasin" tugmasi.
# Haiku 4.5 va Sonnet 4.5 da u umuman yo'q va yuborilsa so'rov 400 xatosi
# bilan rad etiladi. Agent kodi esa effortni HAR DOIM yuboradi.
#
# Shuning uchun tekshiruv shu yerda — bitta joyda. Aks holda tez modelga
# o'tkazilgan har bir agentda alohida shart yozishga to'g'ri kelardi va
# biri unutilsa o'sha agent jimgina ishlamay qolardi.
EFFORTSIZ_MODELLAR = ("haiku-4-5", "sonnet-4-5", "haiku-3", "sonnet-3")


def _effortni_moslash(soro: dict[str, Any]) -> dict[str, Any]:
    """Model effortni tushunmasa — o'sha maydonni olib tashlaydi."""
    model = str(soro.get("model") or "")
    if not any(belgi in model for belgi in EFFORTSIZ_MODELLAR):
        return soro
    konfig = soro.get("output_config")
    if not isinstance(konfig, dict) or "effort" not in konfig:
        return soro

    # Chaqiruvchining lug'ati o'zgartirilmaydi — u qayta ishlatilishi mumkin.
    soro = dict(soro)
    qolgani = {k: v for k, v in konfig.items() if k != "effort"}
    if qolgani:
        soro["output_config"] = qolgani
    else:
        soro.pop("output_config", None)
    return soro


class AnthropicLlm:
    """Haqiqiy Anthropic mijozi."""

    # Server tomonidagi veb qidiruv faqat shu provayderda bor.
    VEB_QIDIRUV = True

    def __init__(self, mijoz: anthropic.AsyncAnthropic | None = None, model: str | None = None):
        s = sozlama()
        if mijoz is None:
            if not s.anthropic_api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY topilmadi. .env fayliga kalitni qo'shing "
                    "(.env.example dan nusxa oling)."
                )
            mijoz = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
        self.mijoz = mijoz
        self.model = model or s.llm_model

    async def javob(self, **soro: Any) -> Any:
        soro.setdefault("model", self.model)
        soro.setdefault("max_tokens", sozlama().maks_token)
        tayyor = _effortni_moslash(soro)
        return await qayd_bilan(
            "anthropic",
            str(tayyor.get("model") or ""),
            lambda: self.mijoz.messages.create(**tayyor),
        )

    def model_bilan(self, model: str) -> "AnthropicLlm":
        """Boshqa modelga o'tgan nusxa. HTTP mijozi BIR XIL qoladi.

        Yangi `AnthropicLlm()` yasash yangi ulanish hovuzi ochadi va har
        so'rov qaytadan TLS qo'l berishga ketadi. Bu yerda faqat model
        nomi almashadi — ulanish o'sha-o'sha.
        """
        if not model or model == self.model:
            return self
        return AnthropicLlm(mijoz=self.mijoz, model=model)

    async def tekshir(self) -> str | None:
        """Kalit haqiqatan ishlayaptimi? Ishlasa `None`, aks holda sabab.

        `/salomat` "ulangan" deb yozishi uchun kalit BORLIGI yetarli emas —
        u yaroqsiz bo'lsa ham bor. Shuning uchun eng arzon (1 token)
        so'rov bilan tekshiriladi.
        """
        try:
            await self.javob(
                max_tokens=1, messages=[{"role": "user", "content": "."}]
            )
        except anthropic.APIError as xato:
            return llm_xato_matni(xato)
        return None


@lru_cache
def llm() -> Llm:
    return AnthropicLlm()


# Provayder MODEL NOMIDAN aniqlanadi.
#
# Alohida "provayder" sozlamasi qo'shilmadi: u model nomi bilan mos
# kelmay qolishi mumkin (`PROVAYDER=gemini`, lekin `TEZ_MODEL=claude-...`)
# va buni hech kim sezmaydi. Nom o'zi yetarli belgi.
PROVAYDERLAR = {"gemini": "gemini", "ollama:": "ollama"}


def veb_qidiruv_qollanadi(model: str) -> bool:
    """Shu modelda server tomonidagi veb qidiruv ishlaydimi?

    NEGA ALOHIDA FUNKSIYA. Veb qidiruv faqat Anthropic'da bor. Gemini
    va lokal modelda so'rov JIMGINA tashlanadi — agent esa izlagan deb
    javob yozaverardi va manbasiz "topilma" menejerga haqiqatdek
    ko'rinardi.
    """
    return provayder(model) == "anthropic"


def provayder(model: str) -> str:
    """Model nomidan provayder ("anthropic", "gemini" yoki "ollama")."""
    past = (model or "").strip().lower()
    for belgi, nomi in PROVAYDERLAR.items():
        if past.startswith(belgi):
            return nomi
    return "anthropic"


@lru_cache
def _gemini_mijoz(model: str) -> Llm:
    from .gemini import GeminiLlm

    return GeminiLlm(model=model)


@lru_cache
def _ollama_mijoz(model: str) -> Llm:
    from .ollama import OllamaLlm

    return OllamaLlm(model=model)


def llm_yasa(model: str, asos: Llm | None = None) -> Llm:
    """Shu model uchun mijoz qaytaradi.

    `asos` — mavjud Anthropic mijozi. Anthropic modeli so'ralganda uning
    ULANISHI qayta ishlatiladi (`model_bilan`), aks holda har so'rovda
    yangi TLS qo'l berishga vaqt ketardi.
    """
    nomi = provayder(model)
    if nomi == "gemini":
        return _gemini_mijoz(model)
    if nomi == "ollama":
        return _ollama_mijoz(model)

    almashtir = getattr(asos, "model_bilan", None)
    if almashtir is not None:
        return almashtir(model)
    return asos if asos is not None else AnthropicLlm(model=model)


# --- Zaxira zanjiri -----------------------------------------------------------


@lru_cache
def _zanjir(modellar: tuple[str, ...]) -> Llm:
    """Model ro'yxati uchun zanjir. KESHLANADI — holati saqlanishi kerak.

    Zanjir yiqilgan modelni qisqa muddatga chetga suradi
    (`app/zanjir.py`). Har so'rovda yangi zanjir yasalsa, o'sha holat
    yo'qolardi va kvota tugagan model qayta-qayta sinalib, har safar
    to'liq javob kutilardi.

    `Orkestr` har so'rovga yangidan yasaladi, shuning uchun kesh shu
    yerda — modul darajasida.
    """
    from .zanjir import zanjir_yasa

    return zanjir_yasa(modellar, lambda nom: llm_yasa(nom))


def tez_llm(modellar: Sequence[str], asos: Llm | None = None) -> Llm:
    """`TEZ_MODEL` dagi ro'yxat uchun mijoz.

    Bitta model bo'lsa `asos` ulanishi qayta ishlatiladi (zanjir kerak
    emas). Bir nechta bo'lsa keshlangan zanjir qaytariladi.
    """
    modellar = [m for m in modellar if m]
    if not modellar:
        raise ValueError("TEZ_MODEL bo'sh")
    if len(modellar) == 1:
        return llm_yasa(modellar[0], asos)
    return _zanjir(tuple(modellar))


# --- Javobni o'qish yordamchilari -------------------------------------------

KOD_BLOK = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def matn_yig(javob: Any) -> str:
    """Javobdagi barcha `text` bloklarini bitta matnga yig'adi."""
    qismlar: list[str] = []
    for blok in getattr(javob, "content", []) or []:
        if getattr(blok, "type", None) == "text":
            qismlar.append(getattr(blok, "text", "") or "")
    return "\n".join(q for q in qismlar if q.strip()).strip()


def json_ajrat(matn: str) -> dict[str, Any]:
    """Matndan JSON obyektini ajratib oladi.

    Structured output yoqilganda matn to'g'ridan-to'g'ri JSON bo'ladi; agar
    model kod bloki yoki qo'shimcha izoh bilan qaytarsa, shu yerda tozalanadi.
    """
    matn = (matn or "").strip()
    if not matn:
        raise ValueError("Model bo'sh javob qaytardi")

    for nomzod in (matn, *(m.group(1) for m in KOD_BLOK.finditer(matn))):
        try:
            qiymat = json.loads(nomzod)
        except json.JSONDecodeError:
            continue
        if isinstance(qiymat, dict):
            return qiymat

    # Oxirgi urinish: birinchi '{' dan oxirgi '}' gacha.
    bosh, oxir = matn.find("{"), matn.rfind("}")
    if bosh != -1 and oxir > bosh:
        qiymat = json.loads(matn[bosh : oxir + 1])
        if isinstance(qiymat, dict):
            return qiymat

    raise ValueError("Model javobidan JSON ajratib bo'lmadi")


def veb_manbalar(javob: Any) -> list[dict[str, Any]]:
    """`web_search_tool_result` bloklaridan manbalarni yig'adi.

    Diqqat: server tool xatosi HTTP 200 bilan qaytadi — bunda `content` ro'yxat
    emas, balki xato obyekti bo'ladi. Shuning uchun turini tekshiramiz.
    """
    manbalar: list[dict[str, Any]] = []
    for blok in getattr(javob, "content", []) or []:
        if getattr(blok, "type", None) != "web_search_tool_result":
            continue
        ichki = getattr(blok, "content", None)
        if not isinstance(ichki, list):
            # Xato holati: {"error_code": "max_uses_exceeded"} kabi
            kod = getattr(ichki, "error_code", None)
            if kod:
                manbalar.append({"xato": str(kod)})
            continue
        for natija in ichki:
            manbalar.append(
                {
                    "nom": getattr(natija, "title", None) or "",
                    "havola": getattr(natija, "url", None),
                    "sana": getattr(natija, "page_age", None),
                }
            )
    return manbalar

"""Lokal model (Ollama) — zanjirning ENG OXIRGI halqasi.

NEGA KERAK
----------
Gemini bepul tarifda: daqiqasiga 5, kuniga 20 so'rov. Kvota tugasa
butun tizim to'xtaydi. Lokal model internetsiz va cheksiz ishlaydi —
sifati pastroq, lekin NOL dan yaxshiroq.

SIFATI O'LCHANDI (2026-09-07), 49 ta haqiqiy tender loti:
    gemini-3.6-flash       aniqlik 1.000, ortiqcha 0
    gemini-3.5-flash-lite  aniqlik 0.974, ortiqcha 0
    qwen3:8b (lokal)       aniqlik 0.718, ortiqcha 10

Shuning uchun u ZAXIRA — birinchi emas, oxirgi. Ro'yxatda oldiga
qo'yilsa sifat tushadi va buni hech kim sezmaydi.

CHEKLOVLARI (ochiq aytiladi, jimgina o'tkazilmaydi)
---------------------------------------------------
1. Structured output YO'Q. `output_config.format` so'ralsa 400
   qaytaramiz — `app/agentlar/asos.py` buni o'zi ushlaydi va matn
   rejimida JSON so'raydi. Bu mavjud, sinovdan o'tgan yo'l.
2. Veb qidiruv YO'Q. `tools` tashlab yuboriladi va ogohlantirish
   yoziladi: javobda tashqi manba bo'lmaydi.
3. Rasm YO'Q. Rasmli so'rov ochiq xato bilan rad etiladi — jimgina
   matnni o'qib, rasmni ko'rmagandek javob berish battari bo'lardi.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
import httpx

from .config import sozlama
from .gemini import _Javob, _Sarf
from .sarf import qayd_bilan

log = logging.getLogger("ollama")

# Model nomi shu bilan boshlansa — lokal model.
# Misol: `ollama:qwen3:8b`
BELGI = "ollama:"

_mijoz: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _mijoz
    if _mijoz is None or _mijoz.is_closed:
        # Lokal model sekin: 49 ta lotli ro'yxat 23 soniya oldi, uzun
        # kontekstda undan ham ko'p. Bulut uchun mos kutish vaqti bu
        # yerda erta uzardi.
        _mijoz = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
    return _mijoz


def model_nomi(model: str) -> str:
    """`ollama:qwen3:8b` -> `qwen3:8b`."""
    past = (model or "").strip()
    return past[len(BELGI):] if past.lower().startswith(BELGI) else past


def _matn(mazmun: Any) -> str:
    """Xabar mazmunidan matnni oladi. Rasm bo'lsa — xato."""
    if isinstance(mazmun, str):
        return mazmun
    qismlar = []
    for qism in mazmun or []:
        if not isinstance(qism, dict):
            continue
        if qism.get("type") == "image":
            raise anthropic.BadRequestError(
                "Lokal model rasmni ko'ra olmaydi (matn modeli). "
                "Rasmli so'rov uchun bulut modeli kerak.",
                response=httpx.Response(400, request=httpx.Request("POST", "/")),
                body=None,
            )
        if qism.get("type") == "text":
            qismlar.append(qism.get("text") or "")
    return "\n".join(q for q in qismlar if q)


def _tizim(qiymat: Any) -> str:
    """`system` matn yoki bloklar ro'yxati bo'lishi mumkin."""
    if isinstance(qiymat, str):
        return qiymat
    return "\n".join(
        b.get("text") or "" for b in (qiymat or []) if isinstance(b, dict)
    ).strip()


def sorovni_ogir(soro: dict[str, Any]) -> dict[str, Any]:
    """Anthropic shaklidagi so'rovni Ollama shakliga o'giradi."""
    xabarlar = []
    tizim = _tizim(soro.get("system"))
    if tizim:
        xabarlar.append({"role": "system", "content": tizim})
    for xabar in soro.get("messages") or []:
        xabarlar.append(
            {"role": xabar.get("role", "user"), "content": _matn(xabar.get("content"))}
        )

    imkoniyat: dict[str, Any] = {
        # Aniqlik kerak, ijod emas: bir xil so'rovga bir xil javob.
        "temperature": 0,
        # TAKRORLANISHDAN HIMOYA — O'LCHANDI (2026-09-07).
        #
        # `options` berilganda Ollama bu qiymatni 1.0 deb oladi va
        # temperature 0 bilan birga model aylanib qoladi:
        #   «Rekuperator - havo sifatini saqlash uchun havo sifatini
        #    saqlash uchun havo sifatini saqlash uchun ...»
        # 1.1 da takror yo'qoladi. 1.2 da esa sifat buziladi — model
        # yo'q so'z o'ylab topa boshlaydi ("xavol").
        "repeat_penalty": 1.1,
    }
    if soro.get("max_tokens"):
        imkoniyat["num_predict"] = soro["max_tokens"]

    return {
        "messages": xabarlar,
        "stream": False,
        # Qwen3 "o'ylash" bloklarini yozadi — ular javobni uzaytiradi
        # va JSON ni o'rab qo'yadi. Kerak emas.
        "think": False,
        "options": imkoniyat,
    }


def javobni_ogir(d: dict[str, Any], model: str) -> _Javob:
    matn = (d.get("message") or {}).get("content") or ""
    # Ba'zi modellar o'ylash blokini baribir matnga qo'shadi.
    if "</think>" in matn:
        matn = matn.split("</think>", 1)[1]
    tugash = "max_tokens" if d.get("done_reason") == "length" else "end_turn"
    return _Javob(
        matn.strip(),
        tugash,
        _Sarf(d.get("prompt_eval_count") or 0, d.get("eval_count") or 0),
        model,
    )


class OllamaLlm:
    """`Llm` protokoli — lokal model uchun."""

    # Lokal model internetga chiqmaydi.
    VEB_QIDIRUV = False

    def __init__(self, model: str | None = None, asos: str | None = None):
        s = sozlama()
        self.model = model_nomi(model or s.ollama_model)
        self.asos = (asos or s.ollama_asos).rstrip("/")

    def model_bilan(self, model: str) -> "OllamaLlm":
        yangi = model_nomi(model)
        if not yangi or yangi == self.model:
            return self
        return OllamaLlm(model=yangi, asos=self.asos)

    async def javob(self, **soro: Any) -> Any:
        model = model_nomi(soro.get("model") or self.model)

        # STRUCTURED OUTPUT — qo'llab-quvvatlanmaydi.
        #
        # Xabarda "output_config" so'zi ATAYLAB bor: `asos.py` aynan
        # shu so'zga qarab matn rejimiga o'tadi va JSON skeletini
        # promptga qo'shadi. Shunday qilib agent ishlayveradi.
        if (soro.get("output_config") or {}).get("format"):
            raise anthropic.BadRequestError(
                "Lokal model output_config format ni qo'llab-quvvatlamaydi",
                response=httpx.Response(400, request=httpx.Request("POST", self.asos)),
                body=None,
            )

        if soro.get("tools"):
            # Jimgina tashlamaymiz: javobda tashqi manba bo'lmasligi
            # menejerga ko'rinishi kerak.
            log.warning(
                "lokal model veb qidiruvni bajara olmaydi — %s uchun "
                "tashqi manbasiz javob qaytadi", model,
            )

        tana = sorovni_ogir(soro) | {"model": model}

        async def yubor() -> Any:
            try:
                javob = await _http().post(f"{self.asos}/api/chat", json=tana)
            except httpx.HTTPError as xato:
                raise anthropic.APIConnectionError(
                    request=httpx.Request("POST", f"{self.asos}/api/chat")
                ) from xato
            if javob.status_code >= 400:
                raise anthropic.APIStatusError(
                    f"Ollama: {javob.text}"[:500], response=javob, body=None
                )
            return javobni_ogir(javob.json(), model)

        # Sarf NOL turadi, lekin `/sarf` da ko'rinishi kerak: zaxiraga
        # qanchalik tez-tez tushayotganimiz muhim belgi.
        return await qayd_bilan("ollama", model, yubor)

    async def tekshir(self) -> str | None:
        """`/salomat` uchun — Ollama ishlayaptimi va model bormi."""
        try:
            javob = await _http().get(f"{self.asos}/api/tags")
        except httpx.HTTPError:
            return f"Ollama ishlamayapti ({self.asos})"
        if javob.status_code >= 400:
            return f"Ollama javob bermadi (HTTP {javob.status_code})"
        nomlar = {m.get("name") for m in javob.json().get("models") or []}
        if self.model not in nomlar:
            return f"'{self.model}' modeli yuklanmagan (`ollama pull {self.model}`)"
        return None

"""Gemini API — `Llm` protokolining ikkinchi implementatsiyasi.

NEGA KERAK
----------
Butun tizim bitta provayderga bog'lanib qolgan: hisobda mablag' tugasa
hamma agent to'xtaydi. Bu qatlam ZAXIRA yo'l ochadi — agentlarga umuman
tegmasdan, ayrim rollarni boshqa modelga o'tkazish mumkin.

QANDAY ISHLAYDI
---------------
Agentlar va router so'rovni ANTHROPIC shaklida quradi (`system` bloklari,
`output_config.format`, `messages`). Bu yerda o'sha shakl Gemini shakliga
tarjima qilinadi, javob esa teskari yo'nalishda — agentlar kutayotgan
`.content[].text` / `.stop_reason` ko'rinishiga.

Shu tufayli `app/agentlar/` va `app/router.py` ga bitta qator ham
qo'shilmaydi.

DIQQAT — BEPUL TARIF
--------------------
Google bepul tarifda so'rovlarni o'z modellarini yaxshilash uchun
ishlatadi. Ya'ni mijoz ismi, telefoni, narx va maosh BEPUL TARIFGA
YUBORILMASLIGI kerak. Shuning uchun zaxira model faqat ma'lumotga
tegmaydigan rollar uchun mo'ljallangan (`TEZ_ROLLAR_ROYXATI`).
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
import httpx

from .config import sozlama
from .sarf import qayd_bilan

log = logging.getLogger("gemini")

ASOS = "https://generativelanguage.googleapis.com/v1beta"

# Bitta umumiy HTTP mijozi: har so'rovda yangi ulanish ochish TLS qo'l
# berishga vaqt sarflaydi.
_mijoz: httpx.AsyncClient | None = None

# Kesh boshqaruvchisi — modul darajasida, bitta nusxa.
_kesh_boshqaruvchi: Any = None


def _http() -> httpx.AsyncClient:
    global _mijoz
    if _mijoz is None or _mijoz.is_closed:
        _mijoz = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    return _mijoz


# --- JSON sxemasini tarjima qilish -------------------------------------------
#
# Pydantic ichma-ich modellarni `$defs` + `$ref` orqali beradi, Anthropic
# esa `additionalProperties: false` talab qiladi. Gemini ikkalasini ham
# tushunmaydi: sxemada `$ref` bo'lsa so'rov 400 bilan rad etiladi.
#
# Shuning uchun havolalar joyiga qo'yiladi (inline) va qo'llab-quvvatlanmagan
# kalitlar tashlanadi.

GEMINI_TUSHUNADI = frozenset({
    "type", "description", "enum", "items", "properties", "required",
    "nullable", "propertyOrdering",
})


def sxemani_ogir(sxema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic uslubidagi JSON Schema -> Gemini `responseSchema`."""
    deflar = sxema.get("$defs") or {}

    def yoy(tugun: Any, chuqurlik: int = 0) -> Any:
        # Chuqurlik chegarasi — o'ziga havola qiluvchi model cheksiz
        # rekursiyaga olib bormasin. Bizdagi modellarda bunday yo'q, lekin
        # keyin qo'shilsa sxema buzilgandan ko'ra soddalashgani yaxshi.
        if chuqurlik > 12:
            return {"type": "string"}
        if isinstance(tugun, list):
            return [yoy(x, chuqurlik + 1) for x in tugun]
        if not isinstance(tugun, dict):
            return tugun

        # $ref -> ta'rifning o'zi.
        havola = tugun.get("$ref")
        if isinstance(havola, str) and havola.startswith("#/$defs/"):
            nomi = havola.removeprefix("#/$defs/")
            return yoy(deflar.get(nomi, {}), chuqurlik + 1)

        # `X | None` -> pydantic `anyOf: [..., {"type": "null"}]` beradi.
        # Gemini buni tushunmaydi, lekin `nullable` ni tushunadi.
        nomzodlar = tugun.get("anyOf") or tugun.get("oneOf")
        if isinstance(nomzodlar, list):
            haqiqiy = [x for x in nomzodlar
                       if not (isinstance(x, dict) and x.get("type") == "null")]
            natija = yoy(haqiqiy[0], chuqurlik + 1) if haqiqiy else {"type": "string"}
            if isinstance(natija, dict) and len(haqiqiy) < len(nomzodlar):
                natija["nullable"] = True
            return natija

        yangi: dict[str, Any] = {}
        for kalit, qiymat in tugun.items():
            if kalit not in GEMINI_TUSHUNADI:
                continue
            if kalit == "properties" and isinstance(qiymat, dict):
                # DIQQAT: `properties` — XARITA. Uning kalitlari maydon
                # nomlari ("nomi", "soni"), sxema kalit so'zlari emas.
                # Ularga ham filtr qo'llasak, hamma maydon o'chib ketadi
                # va Gemini bo'sh obyekt qaytaradi.
                yangi[kalit] = {
                    nom: yoy(ichki, chuqurlik + 1) for nom, ichki in qiymat.items()
                }
            elif kalit in ("enum", "required"):
                # Oddiy satrlar ro'yxati — sxema emas, tegilmaydi.
                yangi[kalit] = qiymat
            else:
                yangi[kalit] = yoy(qiymat, chuqurlik + 1)
        # Obyektda `properties` bo'lsa `type` majburiy.
        if "properties" in yangi:
            yangi.setdefault("type", "object")
            # Maydonlar tartibi — javob barqarorroq chiqadi.
            yangi["propertyOrdering"] = list(yangi["properties"].keys())
        return yangi

    return yoy(sxema)


# --- So'rovni tarjima qilish --------------------------------------------------


def _matn_yig(qiymat: Any) -> str:
    """`system` bloklari yoki oddiy satrdan matn."""
    if isinstance(qiymat, str):
        return qiymat
    if isinstance(qiymat, list):
        return "\n".join(
            b.get("text", "") for b in qiymat
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _qismlar(mazmun: Any) -> list[dict[str, Any]]:
    """Anthropic `content` -> Gemini `parts` (matn va rasm)."""
    if isinstance(mazmun, str):
        return [{"text": mazmun}]
    qismlar: list[dict[str, Any]] = []
    for blok in mazmun or []:
        if not isinstance(blok, dict):
            continue
        if blok.get("type") == "text":
            qismlar.append({"text": blok.get("text", "")})
        elif blok.get("type") == "image":
            manba = blok.get("source") or {}
            if manba.get("type") == "base64":
                qismlar.append({
                    "inline_data": {
                        "mime_type": manba.get("media_type", "image/jpeg"),
                        "data": manba.get("data", ""),
                    }
                })
    return qismlar


def keshlanadigan_blok(soro: dict[str, Any]) -> str:
    """`cache_control` bilan belgilangan system bloki matni.

    `app/router.py` kontraktlar ro'yxatiga `cache_control` qo'yadi —
    u har so'rovda bir xil va eng katta qism (o'lchandi: 4 412 token,
    so'rovning yarmi). Anthropic uni keshlaydi, Gemini adapteri esa
    ilgari jimgina tashlab yuborardi.
    """
    bloklar = soro.get("system")
    if not isinstance(bloklar, list):
        return ""
    for blok in bloklar:
        if isinstance(blok, dict) and blok.get("cache_control"):
            return str(blok.get("text") or "")
    return ""


def sorovni_ogir(soro: dict[str, Any], keshsiz: str = "") -> dict[str, Any]:
    """Anthropic `messages.create` argumentlari -> Gemini tanasi.

    `keshsiz` — kesh yozuviga o'tkazilgan matn. U `systemInstruction`
    dan OLIB TASHLANADI: aks holda ikki marta yuborilardi va kesh
    hech narsa tejamasdi.
    """
    tana: dict[str, Any] = {"contents": []}

    tizim = _matn_yig(soro.get("system"))
    if keshsiz and keshsiz in tizim:
        tizim = tizim.replace(keshsiz, "").strip()
    if tizim:
        tana["systemInstruction"] = {"parts": [{"text": tizim}]}

    for xabar in soro.get("messages") or []:
        rol = "model" if xabar.get("role") == "assistant" else "user"
        qismlar = _qismlar(xabar.get("content"))
        if qismlar:
            tana["contents"].append({"role": rol, "parts": qismlar})

    konfig: dict[str, Any] = {}
    if soro.get("max_tokens"):
        konfig["maxOutputTokens"] = soro["max_tokens"]

    format_ = (soro.get("output_config") or {}).get("format") or {}
    if format_.get("type") == "json_schema" and format_.get("schema"):
        konfig["responseMimeType"] = "application/json"
        konfig["responseSchema"] = sxemani_ogir(format_["schema"])

    if konfig:
        tana["generationConfig"] = konfig

    # `effort` — Anthropic'ga xos, Gemini'da yo'q. Veb qidiruv ham
    # boshqacha ishlaydi; ikkalasi ham jimgina tashlanadi, lekin logga
    # yoziladi — agent nega manbasiz javob qaytarganini bilish uchun.
    if soro.get("tools"):
        log.info("Gemini: veb qidiruv qo'llab-quvvatlanmaydi, tashlandi")
    return tana


# --- Javobni tarjima qilish ---------------------------------------------------

# Gemini tugash sabablari -> Anthropic nomlari.
#
# `refusal` MUHIM: router aynan shu qiymatga qarab "model rad etdi" deb
# hulosa qiladi (`app/router.py`).
TUGASH = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
    "SAFETY": "refusal",
    "RECITATION": "refusal",
    "PROHIBITED_CONTENT": "refusal",
    "BLOCKLIST": "refusal",
}


class _Blok:
    """Anthropic javob blokiga o'xshash eng kichik obyekt."""

    __slots__ = ("type", "text")

    def __init__(self, matn: str):
        self.type = "text"
        self.text = matn


class _Sarf:
    __slots__ = ("input_tokens", "output_tokens", "cache_read_input_tokens")

    def __init__(self, kirish: int, chiqish: int, keshdan: int = 0):
        self.input_tokens = kirish
        self.output_tokens = chiqish
        # Anthropic nomi bilan atayapmiz: `app/sarf.py` ikkala
        # provayderni bir xil o'qiydi va provayder nomiga qarab shart
        # yozish kerak bo'lmaydi.
        self.cache_read_input_tokens = keshdan


class _Javob:
    """Agentlar `matn_yig()` va `stop_reason` orqali shu obyektni o'qiydi."""

    __slots__ = ("content", "stop_reason", "usage", "model")

    def __init__(self, matn: str, tugash: str, sarf: _Sarf, model: str):
        self.content = [_Blok(matn)] if matn else []
        self.stop_reason = tugash
        self.usage = sarf
        self.model = model


def javobni_ogir(j: dict[str, Any], model: str) -> _Javob:
    nomzodlar = j.get("candidates") or []
    matn = ""
    tugash = "end_turn"
    if nomzodlar:
        birinchi = nomzodlar[0]
        tugash = TUGASH.get(str(birinchi.get("finishReason") or "STOP"), "end_turn")
        for qism in (birinchi.get("content") or {}).get("parts") or []:
            if isinstance(qism, dict) and "text" in qism:
                matn += qism["text"]
    elif j.get("promptFeedback", {}).get("blockReason"):
        # Nomzod umuman yo'q — so'rovning o'zi to'silgan.
        tugash = "refusal"

    sarf = j.get("usageMetadata") or {}
    # `cachedContentTokenCount` — kesh ishlaganda 10% narxda hisoblanadi.
    # Bepul tarifda u DOIM 0 (2026-08-28 da o'lchandi: kesh limiti nol),
    # lekin billing yoqilganda o'zi to'lib boshlaydi va `/sarf` da
    # tejamkorlik ko'rinadi.
    return _Javob(
        matn,
        tugash,
        _Sarf(sarf.get("promptTokenCount", 0),
              sarf.get("candidatesTokenCount", 0),
              sarf.get("cachedContentTokenCount", 0)),
        model,
    )


# --- Mijoz --------------------------------------------------------------------


def _anthropic_xatosi(javob: httpx.Response) -> Exception:
    """Gemini xatosini Anthropic xatosiga o'raydi.

    NEGA: agentlar `anthropic.APIError` ni ushlaydi va `llm_xato_matni()`
    uni menejer tushunadigan jumlaga aylantiradi. Boshqa turdagi xato
    tashlasak, u "Agent ichki xatosi" bo'lib chiqadi va sabab yo'qoladi.

    Sxema rad etilgan holat alohida: xabarga "format" so'zi qo'shiladi,
    shunda `asos.py` matn rejimida JSON so'rashga o'zi o'tadi.
    """
    try:
        xabar = (javob.json().get("error") or {}).get("message") or javob.text
    except Exception:
        xabar = javob.text
    xabar = f"Gemini: {xabar}"[:500]

    if javob.status_code == 400 and any(
        k in xabar.lower() for k in ("schema", "responseschema", "json")
    ):
        xabar += " (output_config format qabul qilinmadi)"
    return anthropic.APIStatusError(xabar, response=javob, body=None)


class GeminiLlm:
    """`Llm` protokoli — Gemini uchun."""

    # Veb qidiruv YO'Q — `sorovni_ogir` da `tools` tashlanadi.
    VEB_QIDIRUV = False

    def __init__(self, kalit: str | None = None, model: str | None = None):
        s = sozlama()
        self.kalit = kalit or s.gemini_api_key
        if not self.kalit:
            raise RuntimeError(
                "GEMINI_API_KEY topilmadi. .env fayliga kalitni qo'shing."
            )
        self.model = model or s.gemini_model

    def model_bilan(self, model: str) -> "GeminiLlm":
        if not model or model == self.model:
            return self
        return GeminiLlm(kalit=self.kalit, model=model)

    def _kesh(self) -> Any:
        """Kesh boshqaruvchisi — BUTUN JARAYON uchun bitta.

        Har mijozda alohida bo'lsa, zanjirdagi har model o'z keshini
        yaratardi va "yopiq" belgisi ham tarqab ketardi.
        """
        global _kesh_boshqaruvchi
        if _kesh_boshqaruvchi is None:
            from .gemini_kesh import GeminiKesh

            async def sorovchi(usul: str, yol: str, tana: dict[str, Any]) -> Any:
                return await _http().request(
                    usul, f"{ASOS}/{yol}",
                    headers={"x-goog-api-key": self.kalit,
                             "Content-Type": "application/json"},
                    json=tana,
                )

            _kesh_boshqaruvchi = GeminiKesh(sorovchi)
        return _kesh_boshqaruvchi

    async def javob(self, **soro: Any) -> Any:
        model = soro.get("model") or self.model
        soro.setdefault("max_tokens", sozlama().maks_token)

        # KESH — mavjud bo'lsa katta blok bir marta yuboriladi.
        # Bepul tarifda `nomi()` doim `None` qaytaradi va bu yerda
        # hech narsa o'zgarmaydi (`app/gemini_kesh.py`).
        kesh_nomi = None
        blok = keshlanadigan_blok(soro)
        if blok:
            kesh_nomi = await self._kesh().nomi(model, blok)

        tana = sorovni_ogir(soro, keshsiz=blok if kesh_nomi else "")
        if kesh_nomi:
            tana["cachedContent"] = kesh_nomi

        async def yubor() -> Any:
            javob = await _http().post(
                f"{ASOS}/models/{model}:generateContent",
                headers={"x-goog-api-key": self.kalit,
                         "Content-Type": "application/json"},
                json=tana,
            )
            if javob.status_code >= 400:
                raise _anthropic_xatosi(javob)
            return javobni_ogir(javob.json(), model)

        return await qayd_bilan("gemini", model, yubor)

    async def tekshir(self) -> str | None:
        """Kalit ishlayaptimi? Ishlasa `None`, aks holda sabab."""
        try:
            await self.javob(
                max_tokens=1, messages=[{"role": "user", "content": "."}]
            )
        except anthropic.APIError as xato:
            from .llm import llm_xato_matni

            return llm_xato_matni(xato)
        return None

"""Yordamchi serveri — xaridor ilovasi shu yerga yozadi.

ALOHIDA SERVER, ALOHIDA JARAYON
-------------------------------
Bu fayl `app.main` (ichki panel) BILAN BIRGA ISHLAMAYDI. Ichki panelda
kompaniya ma'lumoti bor va u faqat ichki tarmoqqa ochiladi
(`docker-compose.yml`). Bu server esa internetga ochiq — shuning uchun
unda faqat ikkita yo'l bor: `/yordamchi/xabar` va `/salomat`.

Mijozga qaysi agent ochiqligi `bot/mijoz_ruxsat.OCHIQ_AGENTLAR` da:
narx (Temur), HR, yurist, ichki baza bu yerdan CHAQIRILMAYDI.

Ishga tushirish:
    .venv\\Scripts\\python -m yordamchi
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.baza import Baza
from app.config import sozlama
from app.kurs import yangila as kurs_yangila
from app.llm import AnthropicLlm, llm_yasa, tez_llm
from app.orkestr import Orkestr
from app.profil import profil
from app.sarf import yozuvchini_ol
from bot.mijoz_ruxsat import Tezlik, ochiq_kontraktlar
from integrations.climavent_client import ClimaventKlient

from .kirish import Kirish, KirishXatosi
from .til import tarjimasiz, tarjimon_yasa, til as til_ol
from .yadro import MAKS_MATN, Yordamchi

log = logging.getLogger("yordamchi.api")


class XabarTanasi(BaseModel):
    user_id: int
    text: str = Field(min_length=1, max_length=MAKS_MATN * 2)
    # Ilova tili. 0.8.1 va undan eski ilova yubormaydi — o'zbekcha.
    lang: str = "uz"


def _menejerga_yasa(s):
    """Lid xabari ICHKI bot orqali ketadi (`bot/mijoz.py::_menejerga` dagidek).

    Token yo'q bo'lsa — jim: murojaat baribir bazada qoladi.
    """
    if not s.bot_token:
        log.warning("BOT_TOKEN yo'q — menejerlarga xabar ketmaydi")

        async def jim(_: str) -> None:
            return None
        return jim

    from telegram import Bot as TelegramBot

    bot = TelegramBot(s.bot_token)
    idlar = sorted(s.mijoz_menejer_idlar)

    async def yubor(matn: str) -> None:
        for menejer_id in idlar:
            try:
                await bot.send_message(menejer_id, matn[: s.bot_maks_belgi],
                                       disable_web_page_preview=True)
            except Exception:
                log.warning("menejerga xabar ketmadi: id=%s", menejer_id)
    return yubor


def _tarjima_llm(s, llm):
    """Sozlamada model aytilgan bo'lsa — o'sha, bo'lmasa TEZ_MODEL zanjiri."""
    if s.yordamchi_tarjima_model:
        return llm_yasa(s.yordamchi_tarjima_model, llm)
    return tez_llm(s.tez_modellar, llm)


@asynccontextmanager
async def hayot(app: FastAPI):
    s = sozlama()
    baza = Baza()
    await baza.tayyorla()
    yozuvchini_ol(baza.sarf_yoz)

    kompaniya = profil().malumot.get("kompaniya") or {}
    telefon = str(kompaniya.get("telefon") or "").strip()

    kontraktlar = ochiq_kontraktlar()
    try:
        llm = AnthropicLlm(model=s.mijoz_bot_model or None)
        app.state.llm_xatosi = None
    except Exception as xato:
        llm = None
        app.state.llm_xatosi = str(xato)
        log.error("LLM sozlanmagan: %s", xato)

    def orkestr() -> Orkestr:
        if llm is None:
            raise RuntimeError(f"LLM sozlanmagan: {app.state.llm_xatosi}")
        return Orkestr(llm, baza, kontraktlar)

    api = ClimaventKlient()
    app.state.llm = llm
    app.state.kirish = Kirish(s.climavent_api_asos)
    app.state.yordamchi = Yordamchi(
        baza=baza,
        orkestr=orkestr,
        katalog=api.mahsulotlar,
        tezlik=Tezlik(s.mijoz_bot_limit, kunlik=s.yordamchi_kunlik_limit),
        menejerga=_menejerga_yasa(s),
        telefon=telefon,
        # Tarjima — tez va arzon modelda: u faqat tilni almashtiradi.
        tarjimon=tarjimon_yasa(_tarjima_llm(s, llm)) if llm else tarjimasiz,
    )
    # Sovuq katalog ~11 s oladi — birinchi mijoz buni kutmasin. Dollar
    # kursi ham shu yerda: narx saytdagi bilan bir xil kursda chiqsin.
    isitish = asyncio.create_task(_isit(api))
    yield
    isitish.cancel()


async def _isit(api: ClimaventKlient) -> None:
    for nomi, vazifa in (("katalog", api.mahsulotlar()), ("dollar kursi", kurs_yangila(api))):
        try:
            await vazifa
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("%s oldindan yuklanmadi", nomi, exc_info=True)


app = FastAPI(title="Climavent yordamchi", lifespan=hayot,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/salomat")
async def salomat(request: Request) -> dict[str, Any]:
    return {"holat": "ishlayapti", "llm": request.app.state.llm is not None}


@app.post("/yordamchi/xabar")
async def xabar(
    tana: XabarTanasi,
    request: Request,
    authorization: str = Header(default=""),
) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        kim = await request.app.state.kirish.tekshir(token, tana.user_id)
    except KirishXatosi as xato:
        log.info("kirish rad etildi: id=%s sabab=%s", tana.user_id, xato)
        raise HTTPException(status_code=401, detail="unauthorized") from xato
    except ConnectionError as xato:
        raise HTTPException(status_code=503, detail="backend unavailable") from xato

    javob = await request.app.state.yordamchi.javob(kim, tana.text, til_ol(tana.lang))
    return javob.json()

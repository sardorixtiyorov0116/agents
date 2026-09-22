"""FastAPI ilovasi — so'rovni qabul qiladi, natijani va logni qaytaradi."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.kurs import joriy as kurs_joriy
from app.kurs import manba as kurs_manbasi
from app.kurs import yangila as kurs_yangila
from integrations.climavent_client import ClimaventKlient

from .baza import Baza
from .config import sozlama
from .himoya import PanelHimoyasi

from .sarf import yozuvchini_ol

log = logging.getLogger(__name__)

STATIK = Path(__file__).resolve().parent / "static"

# SSE tekshiruv oralig'i (sekund).
SSE_ORALIQ = 1.5
from .kontraktlar import reyestr
from .llm import AnthropicLlm
from .orkestr import Natija, Orkestr, TasdiqXatosi


class SorovTanasi(BaseModel):
    matn: str = Field(min_length=1, description="Tabiiy tildagi so'rov")
    kontekst: dict[str, Any] = Field(default_factory=dict)


class TasdiqTanasi(BaseModel):
    tasdiqlaymi: bool = Field(description="true — tasdiqlash, false — rad etish")
    izoh: str = Field(default="", description="Qaror sababi (rad etishda ayniqsa muhim)")


@asynccontextmanager
async def hayot(app: FastAPI):
    baza = Baza()
    await baza.tayyorla()
    # LLM sarfini yozish shu yerda YOQILADI. `app/llm.py` bazani
    # import qilmaydi — u testlarda va alohida skriptlarda
    # bazasiz ham ishlashi kerak, shuning uchun bog'lanish teskari.
    yozuvchini_ol(baza.sarf_yoz)
    app.state.baza = baza
    app.state.kontraktlar = reyestr()

    # LLM'ni dangasa yaratamiz: kalit bo'lmasa ham ilova ko'tariladi va log
    # ko'rinishi ishlaydi, faqat /sorov 503 qaytaradi.
    try:
        app.state.llm = AnthropicLlm()
        app.state.llm_xatosi = None
    except Exception as xato:
        app.state.llm = None
        app.state.llm_xatosi = str(xato)

    # Katalogni fonda oldindan yuklaymiz. Sovuq katalog 11.5 s oladi va u
    # birinchi KP so'rovining ustiga qo'shilib ketardi — menejer aynan shu
    # kutishni sezardi. Bu yerda u tizim yoqilishi bilan, hech kim
    # kutmayotgan paytda yuklanadi. Yiqilsa ham hech narsa buzilmaydi:
    # keyin oddiy yo'l bilan qayta so'raladi.
    app.state.katalog_isitish = asyncio.create_task(_katalogni_isit())

    yield

    app.state.katalog_isitish.cancel()


async def _katalogni_isit() -> None:
    """Katalogni keshga oldindan solib qo'yadi (xatoni yutadi).

    Shu yerda DOLLAR KURSI ham saytdan olinadi. Narx dollardan so'mga
    shu kurs bilan hisoblangani uchun bot va sayt bir xil raqamdan
    ishlashi kerak — aks holda mijoz saytda bir narx, KP da boshqa
    narx ko'radi. Olinmasa sozlamadagi zaxira qiymat qoladi.
    """
    klient = ClimaventKlient()

    # HAR BIRI ALOHIDA. Ilgari hammasi bitta `try` da edi va bitta
    # `gather` ichida turardi — natijada `modellar()` yiqilishi (backend
    # `/api/product-models/all` ni olib tashlagan) undan keyingi kursni
    # yangilashni ham to'xtatib qo'yardi. Bog'liq bo'lmagan ikki ish
    # bir-birini yiqitmasligi kerak.
    async def himoyalangan(nomi: str, vazifa) -> None:
        try:
            await vazifa
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("%s: bajarilmadi", nomi, exc_info=True)

    await asyncio.gather(
        himoyalangan("katalog", klient.mahsulotlar()),
        himoyalangan("dollar kursi", kurs_yangila(klient)),
    )
    log.info(
        "oldindan yuklash tugadi; dollar kursi: %s (%s)",
        kurs_joriy(), kurs_manbasi(),
    )


app = FastAPI(
    title="Agentlar tizimi",
    version="0.1.0",
    description="Markaziy LLM-router va 7 ta agent kontrakti. 1-bosqich: Narx analitigi Zara.",
    lifespan=hayot,
)


class TekshirilarStatik(StaticFiles):
    """Statik fayllar — har safar server bilan tekshiriladi.

    ES-modul importi (`ofis3d.js` -> `ofis-model.js`) URL'ga versiya
    qo'shishga imkon bermaydi: bola modul manzili kodda qat'iy yozilgan.
    Shuning uchun kesh emas, **revalidatsiya**: fayl o'zgarmagan bo'lsa
    brauzer `304` oladi, o'zgargan bo'lsa yangisini.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        javob = super().file_response(*args, **kwargs)
        javob.headers["Cache-Control"] = "no-cache"
        return javob


# HIMOYA eng tashqarida turadi: statik fayllar ham panelning bir qismi.
app.add_middleware(PanelHimoyasi)

app.mount("/statik", TekshirilarStatik(directory=STATIK), name="statik")

# `/statik/panel.js` kabi havolalar — versiya qo'shish uchun topiladi.
STATIK_HAVOLA = re.compile(r'(?:src|href)="(/statik/([^"?]+))"')


def _qobiq(nomi: str) -> HTMLResponse:
    """HTML qobiq: ichidagi statik havolalarga `?v=<mtime>` qo'shadi.

    Braurez CSS/JS ni uzoq keshlaydi. Fayl o'zgargach versiya ham
    o'zgaradi — shuning uchun foydalanuvchi eski koddan qutuladi va
    o'zgarmagan fayl bekorga qayta yuklanmaydi.
    """

    def versiyala(mos: re.Match[str]) -> str:
        yol = STATIK / mos.group(2)
        if not yol.is_file():
            return mos.group(0)
        return mos.group(0).replace(
            mos.group(1), f"{mos.group(1)}?v={int(yol.stat().st_mtime)}"
        )

    matn = (STATIK / nomi).read_text(encoding="utf-8")
    return HTMLResponse(
        STATIK_HAVOLA.sub(versiyala, matn), headers={"Cache-Control": "no-cache"}
    )


@app.get("/panel", response_class=HTMLResponse)
async def panel() -> HTMLResponse:
    """Nazorat paneli — so'rov yuborish, jonli zanjir, tasdiqlar, tarix."""
    return _qobiq("panel.html")


@app.get("/ofis", response_class=HTMLResponse)
async def ofis() -> HTMLResponse:
    """3D ofis: agentlar yuradi, holat jonli ko'rinadi."""
    return _qobiq("ofis.html")


def orkestr_ol(request: Request) -> Orkestr:
    if request.app.state.llm is None:
        raise HTTPException(
            status_code=503,
            detail=f"LLM sozlanmagan: {request.app.state.llm_xatosi}",
        )
    return Orkestr(
        llm=request.app.state.llm,
        baza=request.app.state.baza,
        kontraktlar=request.app.state.kontraktlar,
    )


@app.get("/salomat")
async def salomat(request: Request, tekshir: bool = False) -> dict[str, Any]:
    """Tizim holati.

    `?tekshir=1` — kalitni HAQIQATAN sinaydi (1 tokenlik so'rov). Kalit
    borligining o'zi yetarli emas: yaroqsiz kalit ham `.env` da turaveradi
    va tizim "ulangan" deb ko'rsatib, har bir so'rovda 401 bilan yiqilardi.
    """
    llm = request.app.state.llm
    holat = "ulangan" if llm else "sozlanmagan"
    xato = request.app.state.llm_xatosi

    if tekshir and llm is not None:
        sabab = await llm.tekshir()
        if sabab:
            holat = "kalit ishlamayapti"
            xato = sabab

    return {
        "holat": "ishlayapti",
        "model": sozlama().llm_model,
        "llm": holat,
        "llm_xatosi": xato,
        "agentlar_soni": len(request.app.state.kontraktlar),
        "ulangan_agentlar": [
            k.rol for k in request.app.state.kontraktlar.values() if k.amalga_oshirilgan
        ],
    }


@app.get("/agentlar")
async def agentlar(request: Request) -> list[dict[str, Any]]:
    """Interfeys uchun agentlar ro'yxati (lavozim + ism)."""
    return [
        {
            "rol": k.rol,
            "lavozim": k.lavozim,
            "ism": k.ism,
            "korinish": k.korinish,
            "xavf": k.xavf.value,
            "amalga_oshirilgan": k.amalga_oshirilgan,
            "maqsad": k.maqsad.strip(),
        }
        for k in request.app.state.kontraktlar.values()
    ]


@app.get("/agentlar/{rol}")
async def agent_kontrakti(rol: str, request: Request) -> dict[str, Any]:
    kontrakt = request.app.state.kontraktlar.get(rol)
    if kontrakt is None:
        raise HTTPException(status_code=404, detail=f"Bunday agent yo'q: {rol}")
    return kontrakt.model_dump(mode="json") | {"korinish": kontrakt.korinish}


@app.post("/sorov", response_model=Natija)
async def sorov(tana: SorovTanasi, orkestr: Orkestr = Depends(orkestr_ol)) -> Natija:
    return await orkestr.bajar(tana.matn, tana.kontekst or None)


@app.get("/statistika")
async def statistika(request: Request) -> dict[str, Any]:
    """Panel uchun yig'ma ko'rsatkichlar."""
    baza = request.app.state.baza
    kontraktlar = request.app.state.kontraktlar
    yigma = await baza.statistika()
    return yigma | {
        "agentlar_soni": len(kontraktlar),
        "ulangan_agentlar_soni": sum(1 for k in kontraktlar.values() if k.amalga_oshirilgan),
    }


@app.get("/agent-faoliyati")
async def agent_faoliyati(request: Request) -> list[dict[str, Any]]:
    """Har agentning oxirgi holati — panel va ofis ko'rinishi uchun."""
    oxirgi = await request.app.state.baza.agent_faoliyati()
    return [
        {
            "rol": k.rol,
            "lavozim": k.lavozim,
            "ism": k.ism,
            "korinish": k.korinish,
            "xavf": k.xavf.value,
            "amalga_oshirilgan": k.amalga_oshirilgan,
            "maqsad": k.maqsad.strip(),
            "oxirgi": oxirgi.get(k.rol),
        }
        for k in request.app.state.kontraktlar.values()
    ]


@app.get("/events")
async def hodisalar(request: Request) -> StreamingResponse:
    """Jonli yangilanish (SSE).

    Bazadagi o'zgarish belgisini kuzatadi — pub/sub navbat kerak emas, shuning
    uchun bir nechta worker bilan ham, server qayta ishga tushgach ham ishlaydi.
    """
    baza = request.app.state.baza

    async def oqim() -> AsyncIterator[str]:
        oldingi = ""
        while True:
            if await request.is_disconnected():
                return
            try:
                belgi = await baza.ozgarish_belgisi()
            except Exception:
                belgi = oldingi
            if belgi != oldingi:
                oldingi = belgi
                yield f"event: yangilandi\ndata: {belgi}\n\n"
            else:
                # Proksi ulanishni uzib yubormasligi uchun izoh-qator.
                yield ": kutilmoqda\n\n"
            await asyncio.sleep(SSE_ORALIQ)

    return StreamingResponse(
        oqim(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/tasdiq")
async def kutilayotgan_tasdiqlar(request: Request) -> list[dict[str, Any]]:
    """Inson qarorini kutayotgan natijalar."""
    return await request.app.state.baza.kutilayotgan_tasdiqlar()


@app.post("/tasdiq/{iz_id}", response_model=Natija)
async def tasdiq_qarori(
    iz_id: int, tana: TasdiqTanasi, orkestr: Orkestr = Depends(orkestr_ol)
) -> Natija:
    """Tasdiqlash yoki rad etish — zanjir shundan keyin davom etadi yoki to'xtaydi."""
    try:
        return await orkestr.davom_ettir(iz_id, tana.tasdiqlaymi, tana.izoh)
    except TasdiqXatosi as xato:
        raise HTTPException(status_code=409, detail=str(xato)) from xato


@app.get("/izlar")
async def izlar(request: Request, chek: int = 50) -> list[dict[str, Any]]:
    return await request.app.state.baza.izlar(max(1, min(chek, 200)))


@app.get("/izlar/{iz_id}")
async def iz(iz_id: int, request: Request) -> dict[str, Any]:
    yozuv = await request.app.state.baza.iz(iz_id)
    if yozuv is None:
        raise HTTPException(status_code=404, detail=f"Iz topilmadi: {iz_id}")
    return yozuv


# --- Oddiy log ko'rinishi (1-bosqich talabi) ---------------------------------

USLUB = """
body { font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 24px;
       background: #14161a; color: #e6e8eb; }
h1 { font-size: 20px; margin: 0 0 4px; }
p.izoh { color: #9aa4b2; margin: 0 0 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #2a2f37;
         vertical-align: top; }
th { color: #9aa4b2; font-weight: 600; font-size: 12px; text-transform: uppercase; }
pre { background: #1d2026; padding: 10px; border-radius: 6px; overflow-x: auto;
      max-width: 900px; }
.holat { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.tugadi { background: #14432c; color: #7ee2a8; }
.tasdiq_kutilmoqda { background: #453a13; color: #f5d97a; }
.aniqlik_kerak { background: #3d2f4d; color: #d3b0f5; }
.mos_agent_yoq { background: #2a2f37; color: #9aa4b2; }
.ulanmagan { background: #16304d; color: #8ec2ff; }
.xato { background: #4a1d1d; color: #ff9a9a; }
"""


def _holat_belgi(holat: str) -> str:
    sinf = html.escape(holat)
    return f'<span class="holat {sinf}">{sinf}</span>'


@app.get("/", response_class=HTMLResponse)
async def korinish(request: Request) -> HTMLResponse:
    """Qaysi agent chaqirildi, nima kirdi, nima chiqdi — oddiy ko'rinish."""
    yozuvlar = await request.app.state.baza.izlar(20)
    kontraktlar = request.app.state.kontraktlar

    agent_qatorlari = "".join(
        f"<tr><td>{html.escape(k.korinish)}</td><td><code>{html.escape(k.rol)}</code></td>"
        f"<td>{html.escape(k.xavf.value)}</td>"
        f"<td>{'ulangan' if k.amalga_oshirilgan else 'kontrakt tayyor'}</td></tr>"
        for k in kontraktlar.values()
    )

    iz_qatorlari = []
    for y in yozuvlar:
        yakuniy = y.get("yakuniy") or {}
        qadamlar = y.get("qadamlar") or []
        zanjir = " -> ".join(html.escape(q.get("korinish", "?")) for q in qadamlar) or "—"
        toliq = html.escape(json.dumps(y, ensure_ascii=False, indent=2))
        iz_qatorlari.append(
            "<tr>"
            f"<td>{y['id']}</td>"
            f"<td>{html.escape(y['vaqt'])}</td>"
            f"<td>{html.escape(y['sorov'])[:160]}</td>"
            f"<td>{zanjir}</td>"
            f"<td>{_holat_belgi(str(yakuniy.get('holat', '—')))}</td>"
            f"<td>{html.escape(str(yakuniy.get('ishonch', '—')))}</td>"
            f"<td>{y.get('davomiylik_ms') or 0} ms</td>"
            f"</tr>"
            f'<tr><td colspan="7"><details><summary>to\'liq iz</summary>'
            f"<pre>{toliq}</pre></details></td></tr>"
        )

    if not iz_qatorlari:
        iz_qatorlari.append('<tr><td colspan="7">Hali so\'rov bo\'lmadi.</td></tr>')

    sahifa = f"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><title>Agentlar tizimi — log</title>
<style>{USLUB}</style></head><body>
<h1>Agentlar tizimi</h1>
<p class="izoh">Model: {html.escape(sozlama().llm_model)} &middot;
So'rov yuborish: <code>POST /sorov</code> &middot; API hujjati: <a href="/docs">/docs</a></p>

<h2>Agentlar</h2>
<table><thead><tr><th>Kim</th><th>Rol nomi</th><th>Xavf</th><th>Holat</th></tr></thead>
<tbody>{agent_qatorlari}</tbody></table>

<h2>Oxirgi so'rovlar</h2>
<table><thead><tr><th>#</th><th>Vaqt</th><th>So'rov</th><th>Zanjir</th>
<th>Holat</th><th>Ishonch</th><th>Vaqt</th></tr></thead>
<tbody>{''.join(iz_qatorlari)}</tbody></table>
</body></html>"""
    return HTMLResponse(sahifa)

"""`/sarf` uchun matn — LLM sarfi qanchaga yetdi.

Alohida modul: `app/sarf.py` O'LCHAYDI, bu yerda esa o'lchov MATNGA
aylanadi. Ikkalasi bir faylda bo'lsa, o'lchov qatlami botga bog'lanib
qolardi va panelda qayta ishlatib bo'lmasdi.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import sozlama
from .sarf import kvota_kuni, limit_xatosimi
from app.kurs import joriy as kurs_joriy

# Limitning qancha qismidan keyin ogohlantirish.
OGOHLANTIRISH = 0.75
XAVF = 0.90

DAQIQA_OYNASI = 60  # soniya


def _ulush_belgisi(ishlatilgan: int, limit: int) -> str:
    """Limitga nisbatan holat. Limit noma'lum bo'lsa — belgi yo'q."""
    if limit <= 0:
        return ""
    ulush = ishlatilgan / limit
    belgi = "🔴" if ulush >= XAVF else ("🟡" if ulush >= OGOHLANTIRISH else "🟢")
    return f" {belgi} {ishlatilgan}/{limit} ({ulush:.0%})"


# --- Xarajat ------------------------------------------------------------------


@lru_cache
def _narxlar() -> dict[str, dict[str, float]]:
    """Model narxlari — 1 mln token uchun dollarda."""
    yol = Path("config/llm_narxlari.yaml")
    if not yol.exists():
        return {}
    xom = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    return {str(k): v for k, v in (xom.get("modellar") or {}).items()}


def model_narxi(model: str) -> tuple[float, float] | None:
    """(kirish, chiqish) — 1 mln token uchun dollarda. Noma'lum -> None.

    Nom MODEL NOMINING BOSHI bilan solishtiriladi: "claude-haiku-4-5"
    yozuvi "claude-haiku-4-5-20251001" ga ham mos keladi. Eng UZUN mos
    kelgani tanlanadi — aks holda "gemini" yozuvi
    "gemini-3.5-flash-lite" dan oldin tushib qolishi mumkin edi.
    """
    past = (model or "").strip().lower()
    mos = [(k, v) for k, v in _narxlar().items() if past.startswith(k.lower())]
    if not mos:
        return None
    _, narx = max(mos, key=lambda x: len(x[0]))
    return float(narx.get("kirish", 0)), float(narx.get("chiqish", 0))


# Keshdan o'qilgan token to'liq narxning necha qismini turadi.
# Anthropic ham, Google ham 10% e'lon qilgan.
KESH_ULUSHI = 0.1


def xarajat_somda(model: str, kirish: int, chiqish: int, kurs: float,
                  keshdan: int = 0) -> float | None:
    """Chaqiruv narxi so'mda. Model narxi noma'lum bo'lsa `None`.

    `keshdan` — keshdan o'qilgan tokenlar. Ular `kirish` ICHIDA
    hisoblangan (provayder shunday qaytaradi), shuning uchun avval
    ayriladi va keyin arzon narxda qaytariladi. Aks holda kesh
    tejamkorligi umuman ko'rinmasdi.
    """
    narx = model_narxi(model)
    if narx is None:
        return None
    keshdan = max(0, min(keshdan, kirish))
    toliq = kirish - keshdan
    return (
        toliq / 1e6 * narx[0]
        + keshdan / 1e6 * narx[0] * KESH_ULUSHI
        + chiqish / 1e6 * narx[1]
    ) * kurs


def _pul(som: float) -> str:
    if som < 1:
        return "1 so'mdan kam"
    return f"{som:,.0f}".replace(",", " ") + " so'm"


def _minglab(son: int) -> str:
    if son >= 1_000_000:
        return f"{son / 1_000_000:.1f} mln"
    if son >= 1_000:
        return f"{son / 1_000:.1f} ming"
    return str(son)


def _limitlar(provayder: str) -> tuple[int, int]:
    s = sozlama()
    if provayder == "gemini":
        return s.gemini_kunlik_limit, s.gemini_daqiqalik_limit
    return 0, 0


async def hisobot_matni(baza: Any, kunlar: int = 7) -> str:
    """`/sarf` javobi."""
    hozir = datetime.now(timezone.utc)
    # Provayderlarni oxirgi 2 kun ichida ishlatilganlaridan olamiz —
    # kvota kuni mintaqaga qarab surilgani uchun 1 kun kamlik qilishi
    # mumkin.
    chegara_kun = (hozir - timedelta(days=2)).date().isoformat()
    provayderlar = await baza.sarf_provayderlar(chegara_kun)

    if not provayderlar:
        return (
            "📊 LLM sarfi\n\n"
            "Hali birorta ham so'rov yozilmagan.\n\n"
            "Hisob shu paytdan boshlab yuritiladi — bot qayta ishga "
            "tushirilgandan keyingi chaqiruvlar yoziladi."
        )

    qismlar: list[str] = ["📊 LLM sarfi"]

    for provayder in provayderlar:
        kun = kvota_kuni(provayder, hozir)
        yigindi = await baza.sarf_kunlik(provayder, kun)
        soni = int(yigindi.get("soni") or 0)
        xatolar = int(yigindi.get("xatolar") or 0)
        tokenlar = int(yigindi.get("kirish") or 0) + int(yigindi.get("chiqish") or 0)

        kunlik_limit, daqiqalik_limit = _limitlar(provayder)

        qismlar.append(f"\n━━ {provayder} ━━")
        qismlar.append(f"Kvota kuni: {kun}")
        qismlar.append(f"So'rovlar: {soni}{_ulush_belgisi(soni, kunlik_limit)}")
        if soni:
            qismlar.append(f"Tokenlar: {_minglab(tokenlar)}")
        if xatolar:
            qismlar.append(f"Xatolar: {xatolar}")

        # Daqiqalik bosim — 429 ning eng tez-tez sababi.
        oyna = (hozir - timedelta(seconds=DAQIQA_OYNASI)).isoformat(timespec="seconds")
        daqiqada = await baza.sarf_oxirgi_daqiqa(provayder, oyna)
        if daqiqada:
            qismlar.append(
                f"Oxirgi daqiqada: {daqiqada}{_ulush_belgisi(daqiqada, daqiqalik_limit)}"
            )

        if kunlik_limit <= 0:
            qismlar.append(
                "⚠️ Kunlik limit noma'lum — foiz ko'rsatilmayapti.\n"
                "   Google AI Studio → Rate limits dan ko'rib, .env ga\n"
                "   GEMINI_KUNLIK_LIMIT=... yozing."
                if provayder == "gemini" else ""
            )

        # Modellar — zanjirda qaysi biri ishlaganini ko'rsatadi.
        # Bitta model bo'lsa ortiqcha qator qo'shmaymiz.
        modellar = await baza.sarf_modellar(provayder, kun)
        if len(modellar) > 1:
            qismlar.append("\nModellar (zanjir):")
            for m in modellar:
                belgi = f"  {m['model']}: {m['soni']} ta"
                if m.get("xatolar"):
                    belgi += f" ({m['xatolar']} xato)"
                qismlar.append(belgi)

        # XARAJAT — "tokenlar suvday ketdi" degan tuyg'u o'lchovsiz
        # paydo bo'ladi. Bu yerda u so'mga aylanadi.
        kurs = float(kurs_joriy() or 0)
        jami_som = 0.0
        nomalum = False
        for m in modellar:
            som = xarajat_somda(str(m["model"]), int(m.get("kirish") or 0),
                                int(m.get("chiqish") or 0), kurs,
                                int(m.get("keshdan") or 0))
            if som is None:
                nomalum = True
            else:
                jami_som += som
        if soni and kurs:
            if nomalum:
                qismlar.append("\n💰 Xarajat: qisman noma'lum "
                               "(config/llm_narxlari.yaml ga model qo'shing)")
            elif jami_som <= 0:
                qismlar.append("\n💰 Xarajat: 0 — bepul tarif")
                # BILLING YOQILGANINI SEZISH.
                #
                # Narx fayli nol deb tursa-yu, Google'da billing
                # yoqilgan bo'lsa, pul ketadi va `/sarf` uni
                # ko'rsatmaydi — aynan biz qochmoqchi bo'lgan holat.
                #
                # Bepul tarifda har model kuniga `kunlik_limit` ta
                # so'rovdan oshmaydi. Oshgan bo'lsa — bu bepul tarif
                # emas.
                if kunlik_limit > 0:
                    oshgan = [m["model"] for m in modellar
                              if int(m["soni"]) > kunlik_limit]
                    if oshgan:
                        qismlar.append(
                            "   ⚠️ Lekin " + ", ".join(oshgan)
                            + f" bepul chegaradan ({kunlik_limit}/kun) OSHDI —"
                            + " billing yoqilgan bo'lishi mumkin."
                            + "\n   config/llm_narxlari.yaml ga haqiqiy narxni yozing.")
            else:
                qismlar.append(f"\n💰 Bugungi xarajat: {_pul(jami_som)}")
                qismlar.append(f"   O'rtacha: {_pul(jami_som / soni)} / so'rov")
                keshdan = sum(int(m.get("keshdan") or 0) for m in modellar)
                if keshdan:
                    tejaldi = sum(
                        (xarajat_somda(str(m["model"]),
                                       int(m.get("keshdan") or 0), 0, kurs) or 0)
                        * (1 - KESH_ULUSHI) for m in modellar)
                    qismlar.append(
                        f"   🗄 Keshdan: {_minglab(keshdan)} token "
                        f"(~{_pul(tejaldi)} tejaldi)")

        rollar = await baza.sarf_rollar(provayder, kun)
        if rollar:
            qismlar.append("\nRollar bo'yicha:")
            for r in rollar:
                qismlar.append(
                    f"  {r['rol'] or '—'}: {r['soni']} ta"
                    f" ({_minglab(int(r['tokenlar'] or 0))} token)"
                )

        oxirgi_xatolar = await baza.sarf_xatolari(provayder, kun)
        if oxirgi_xatolar:
            limitlar = [x for x in oxirgi_xatolar if limit_xatosimi(x.get("xato"))]
            qismlar.append(
                f"\nOxirgi xatolar ({len(limitlar)} tasi limit bilan bog'liq):"
            )
            for x in oxirgi_xatolar[:3]:
                belgi = "⛔" if limit_xatosimi(x.get("xato")) else "•"
                vaqt = str(x.get("vaqt") or "")[11:16]
                qismlar.append(f"  {belgi} {vaqt} {x.get('rol') or '—'}: "
                               f"{str(x.get('xato') or '')[:90]}")

        tarix = await baza.sarf_kunlar(provayder, kunlar)
        if len(tarix) > 1:
            qismlar.append("\nOxirgi kunlar:")
            for t in tarix:
                belgi = f"  {t['kun']}: {t['soni']} ta"
                if t.get("xatolar"):
                    belgi += f" ({t['xatolar']} xato)"
                qismlar.append(belgi)

    return "\n".join(q for q in qismlar if q != "")

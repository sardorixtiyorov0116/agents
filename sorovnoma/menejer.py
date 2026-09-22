"""So'rovnoma -> menejerga KP loyihasi + tugmalar.

NEGA TUGMA, AVTOMAT YUBORISH EMAS
---------------------------------
KP tijorat majburiyati: blankada kompaniya nomi, direktor imzosi va
narx amal qilish muddati turadi. Botga yozgan istalgan odamga uni
avtomat yuborish narx E'LON QILISH degani va xato narxni qaytarib
bo'lmaydi.

Shuning uchun oxirgi qadamda odam turadi. Menejerning vaqti KP
TUZISHGA ketardi — shu qism avtomatlashdi; yuborish esa bir tugma.

IKKI YO'L — IKKALASI HAM KERAK
------------------------------
1. TUGMA — bot mijozga yuboradi. Har doim ishlaydi: mijoz botga o'zi
   yozgan, demak chat ochiq.
2. O'ZI YUBORISH — menejer mijoz bilan shaxsan gaplashadi. Buning
   uchun unga mijoz kontakti kerak; username bo'lsa bosiladigan
   havola beriladi, bo'lmasa telefon.

Ikkinchisi zarur: ba'zi mijoz bilan gaplashish kerak, quruq hujjat
yuborish yetarli emas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .talab import SorovnomaShakli, bolim
from app.kurs import joriy as kurs_joriy

log = logging.getLogger("sorovnoma.menejer")

TUGMA_OLDI = "snm:"
YUBOR = "yubor"
OZIM = "ozim"

# Loyiha KP raqami — HAQIQIY KP raqamidan farq qilsin.
#
# Menejer tasdiqlamagan hujjat rasmiy raqamni band qilmasligi kerak:
# mijoz "KP-2026-0042 qani" deb so'rasa, u raqam boshqa taklifga
# berilgan bo'lardi.
LOYIHA_OLDI = "LOYIHA"


def loyiha_raqami(sorovnoma_id: int) -> str:
    from datetime import date

    return f"{LOYIHA_OLDI}-{date.today().year}-{sorovnoma_id:04d}"


def mijoz_havolasi(aloqa: str, tg_id: Any) -> str:
    """Menejer bosib chatga o'tadigan havola.

    Username bo'lsa `t.me/...`, bo'lmasa telefon. Ikkalasi ham
    bo'lmasa — bo'sh: yolg'on havola berishdan ko'ra hech nima
    bermagan yaxshi.
    """
    toza = str(aloqa or "").strip()
    if toza.startswith("@"):
        return f"[{toza}](https://t.me/{toza[1:]})"
    if toza.startswith("+") or toza.replace(" ", "").isdigit():
        return toza
    return ""


def tugmalar(sorovnoma_id: int, mijoz_tg_id: Any) -> InlineKeyboardMarkup:
    asos = f"{TUGMA_OLDI}{sorovnoma_id}:{mijoz_tg_id}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tekshirdim — mijozga yuborish",
                              callback_data=f"{asos}:{YUBOR}")],
        [InlineKeyboardButton("✏️ O'zim yuboraman",
                              callback_data=f"{asos}:{OZIM}")],
    ])


def xabar_matni(
    savat: list[dict[str, Any]],
    ism: str,
    aloqa: str,
    tg_id: Any,
    kp: Any = None,
    narxsiz_soni: int = 0,
) -> str:
    """Menejerga ketadigan xabar."""
    from .oqim import _yorliq

    qatorlar = [f"📋 *Yangi so'rov* — {len(savat)} ta pozitsiya", ""]
    if ism:
        qatorlar.append(f"👤 {ism}")
    havola = mijoz_havolasi(aloqa, tg_id)
    if havola:
        qatorlar.append(f"📞 {havola}")
    else:
        qatorlar.append("⚠️ Aloqa yo'q — faqat bot orqali javob berish mumkin")
    qatorlar.append(f"🆔 `{tg_id}`")

    for raqam, pozitsiya in enumerate(savat, 1):
        b = bolim(pozitsiya.get("bolim", ""))
        shakl = SorovnomaShakli(bolim_kaliti=pozitsiya.get("bolim", ""),
                                javoblar=pozitsiya.get("javoblar") or {})
        qatorlar += ["", f"━━ {raqam}. {b.belgi if b else '•'} "
                         f"*{b.nomi if b else pozitsiya.get('bolim', '')}* ━━"]
        for kalit, qiymat in shakl.javoblar.items():
            savol, javob = _yorliq(shakl, kalit, qiymat)
            qatorlar.append(f"*{savol}* — {javob if javob else 'bilmayman'}")

    if kp is not None:
        qatorlar += ["", "━━━━━━━━━━━━━━━━━━"]
        jami = getattr(kp, "jami", None)
        if jami:
            summa = f"{jami:,.0f}".replace(",", " ")
            qatorlar.append(f"💰 *KP loyihasi: {summa} so'm* (QQS bilan)")
        else:
            qatorlar.append("💰 *KP loyihasi tayyor* — summa to'liq emas")
        if narxsiz_soni:
            qatorlar.append(
                f"⚠️ {narxsiz_soni} pozitsiyada narx yo'q — to'ldiring")
        qatorlar += [
            "",
            "_Hujjat quyida. TEKSHIRING: narx, miqdor, shartlar._",
            "_Tugmani bosganingizda mijozga PDF yuboriladi._",
        ]
    return "\n".join(qatorlar)


def yuborildi_matni(ism: str) -> str:
    return f"✅ KP mijozga yuborildi{f' — {ism}' if ism else ''}."


def ozim_matni(aloqa: str, tg_id: Any) -> str:
    havola = mijoz_havolasi(aloqa, tg_id)
    qatorlar = ["✏️ Yaxshi — o'zingiz yuborasiz."]
    if havola:
        qatorlar += ["", f"Mijoz: {havola}"]
    else:
        qatorlar += [
            "",
            "⚠️ Mijoz aloqa qoldirmagan va Telegramda username yo'q — "
            "unga faqat bot orqali yozish mumkin.",
            "Botdan yuborish uchun xabardagi birinchi tugmani bosing.",
        ]
    qatorlar += ["", "_Yuqoridagi `.docx` ni tahrirlab yuborishingiz mumkin._"]
    return "\n".join(qatorlar)


MIJOZGA = (
    "📄 *Tijorat taklifi tayyor*\n\n"
    "So'rovingiz bo'yicha menejerimiz taklif tayyorladi — hujjat quyida.\n\n"
    "Savollar bo'lsa shu yerda yozing."
)


async def loyihani_yasa(baza, api, savat: list[dict[str, Any]],
                        sorovnoma_id: int, ism: str, aloqa: str,
                        papka: Path) -> tuple[Any, dict[str, Path], int] | None:
    """KP loyihasi + hujjatlar. Xato bo'lsa `None`.

    Loyiha YASALMASA so'rovnoma baribir menejerga boradi — hujjatsiz.
    KP yasashdagi nosozlik butun murojaatni yo'qotmasligi kerak.
    """
    from app.config import sozlama
    from kp.hujjat import hujjatlarni_yasa
    from kp.narx import narxlar, rekvizitlar

    from .kp_loyiha import loyiha_yasa, savatdan_qatorlar

    try:
        katalog = await api.mahsulotlar()
        parametrlar = await api.texnik_parametrlar()
    except Exception:
        log.warning("KP loyihasi uchun katalog olinmadi", exc_info=True)
        return None

    try:
        royxat = narxlar()
        qqs = float(getattr(royxat, "qqs_foizi", 0) or 0)
        _, _, narxsiz = savatdan_qatorlar(
            savat, katalog, parametrlar, kurs_joriy(), qqs)
        kp = loyiha_yasa(
            savat, loyiha_raqami(sorovnoma_id), ism, aloqa,
            katalog, parametrlar, kurs_joriy(),
            royxat, dict(rekvizitlar()), til="uz")
        papka.mkdir(parents=True, exist_ok=True)
        fayllar = hujjatlarni_yasa(kp, papka)
    except Exception:
        log.exception("KP loyihasi yasalmadi")
        return None
    return kp, fayllar, len(narxsiz)

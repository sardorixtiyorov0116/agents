"""Katalogdagi bo'shliqlarni sanaydi — Nodiraning kunlik ko'zi.

NEGA KERAK
----------
O'LCHANDI (2026-09-08): jonli katalogdagi 342 variantdan atigi 21 tasida
narx bor (6.1%). Bu tizimning eng katta to'sig'i: narxsiz KP — KP emas,
va mijoz botga "narxi qancha" deb yozganda javob yo'q.

Muammo KO'RINMASDI: uni bilish uchun kimdir katalogni ochib sanashi
kerak edi. Endi haftada bir marta o'zi hisoblab, menejerga aytadi.

LLM CHAQIRILMAYDI. Bu sanoq — sof kod. Model bu yerda hech narsa
qo'shmaydi, faqat xato qo'shishi mumkin edi.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("katalog.salomatlik")

# Bosma katalog oilalari — bazada bor-yo'qligini solishtirish uchun.
OILALAR_FAYLI = Path("chiqish/katalog_oilalari.json")


def _son(qiymat: Any) -> float:
    try:
        return float(qiymat or 0)
    except (TypeError, ValueError):
        return 0.0


def hisobla(mahsulotlar: list[dict[str, Any]]) -> dict[str, Any]:
    """Katalog bo'shliqlarini sanaydi.

    `characters` — mahsulotning variantlari (model o'lchamlari). Narx va
    texnik ko'rsatkich aynan shu yerda turadi, mahsulotda emas.
    """
    variant = narxsiz = texnikasiz = 0
    narxsiz_mahsulot: list[str] = []

    for mahsulot in mahsulotlar:
        variantlar = mahsulot.get("characters") or []
        if not variantlar:
            continue
        mahsulotda_narx = False
        for ch in variantlar:
            variant += 1
            if _son(ch.get("price")) > 0:
                mahsulotda_narx = True
            else:
                narxsiz += 1
            # Rustam ventilyatorni HAVO SARFIGA qarab tanlaydi — bu
            # maydonsiz hisob natijasi uskunaga bog'lanmaydi.
            if not _son(ch.get("airflow_m3h")) and not _son(ch.get("pressure_pa")):
                texnikasiz += 1
        if not mahsulotda_narx:
            nomi = (mahsulot.get("name_uz") or mahsulot.get("name_ru") or "").strip()
            if nomi:
                narxsiz_mahsulot.append(nomi)

    return {
        "mahsulot": len(mahsulotlar),
        "variant": variant,
        "narxsiz": narxsiz,
        "narxli": variant - narxsiz,
        "texnikasiz": texnikasiz,
        "butunlay_narxsiz_mahsulotlar": narxsiz_mahsulot,
    }


def bosma_katalogdan_yoq(mahsulotlar: list[dict[str, Any]]) -> list[str]:
    """Bosma katalogda bor, bazada yo'q oilalar.

    Fayl bo'lmasa BO'SH qaytadi — hisobot baribir chiqadi, faqat shu
    bo'lim tushib qoladi. Jimgina xato berib butun hisobotni
    yiqitishdan yaxshiroq.
    """
    try:
        oilalar = json.loads(OILALAR_FAYLI.read_text(encoding="utf-8"))
    except (OSError, ValueError) as xato:
        log.info("bosma katalog ro'yxati o'qilmadi: %s", xato)
        return []

    bazadagi = " ".join(
        (m.get("name_uz") or "") + " " + (m.get("name_ru") or "")
        for m in mahsulotlar
    ).lower()

    yoq = []
    for oila in oilalar:
        kod = str(oila.get("kod") or "").strip()
        if not kod:
            continue
        # Birinchi so'z — model kodi ("ВКП 40х20" -> "ВКП").
        belgi = kod.split()[0].split("/")[0].strip().lower()
        if len(belgi) >= 2 and belgi not in bazadagi:
            yoq.append(kod)
    return yoq


def matn(olchov: dict[str, Any], yoq_oilalar: list[str], maks: int = 8) -> str:
    """Hisobotni menejer o'qiydigan xabarga aylantiradi."""
    variant = olchov["variant"]
    if not variant:
        return (
            "🗂 Katalog salomatligi\n\n"
            "⚠️ Katalogda variant topilmadi — API bo'sh qaytardi."
        )

    foiz = 100 * olchov["narxli"] / variant
    qatorlar = [
        "🗂 Katalog salomatligi",
        "",
        f"Mahsulot: {olchov['mahsulot']} ta, variant: {variant} ta",
        "",
        f"💰 Narxi bor: {olchov['narxli']} ta ({foiz:.0f}%)",
        f"   Narxsiz:   {olchov['narxsiz']} ta",
    ]
    if olchov["texnikasiz"]:
        qatorlar.append(
            f"📐 Havo sarfi/bosimi yo'q: {olchov['texnikasiz']} ta variant"
        )

    butunlay = olchov["butunlay_narxsiz_mahsulotlar"]
    if butunlay:
        qatorlar += [
            "",
            f"Butunlay narxsiz mahsulotlar — {len(butunlay)} ta:",
        ]
        qatorlar += [f"• {n[:56]}" for n in butunlay[:maks]]
        if len(butunlay) > maks:
            qatorlar.append(f"…yana {len(butunlay) - maks} ta")

    if yoq_oilalar:
        qatorlar += [
            "",
            f"📕 Bosma katalogda bor, bazada yo'q — {len(yoq_oilalar)} ta:",
        ]
        qatorlar += [f"• {k[:56]}" for k in yoq_oilalar[:maks]]
        if len(yoq_oilalar) > maks:
            qatorlar.append(f"…yana {len(yoq_oilalar) - maks} ta")

    if olchov["narxsiz"]:
        qatorlar += [
            "",
            "Narxsiz mahsulot KP ga to'liq tushmaydi va mijozga javob "
            "berilmaydi. To'ldirish: /katalog",
        ]
    return "\n".join(qatorlar)

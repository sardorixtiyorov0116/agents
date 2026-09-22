"""Nodiraning yozish amallarini backend Swagger'i bilan solishtiradi.

NEGA KERAK
----------
2026-09-09 da ma'lum bo'ldiki, `model_yarat` / `model_yangila` /
`model_ochir` amallari `/api/product-models/*` ga qarab turgan, backendda
esa bunday yo'l umuman yo'q edi. Ya'ni Nodira amalni taklif qilardi, odam
uni tasdiqlardi, va faqat shundan keyin 404 chiqardi — xato eng qimmat
joyda, inson vaqtidan keyin ko'rinardi.

Shu bilan birga `mahsulot_yarat` `CreateProductDto` qabul qilmaydigan 8 ta
maydon yuborardi (`sizes`, `opisaniya`, `naznacheniya`, `markirovka` va
ularning `Json` juftlari) — ular jimgina yo'qolardi.

Ikkala nuqson ham bir sababdan: AMALLAR jadvali qo'lda yozilgan, backend
esa mustaqil o'zgaradi. Shuning uchun bu skript.

NIMA QILADI
-----------
1. `/api/docs-json` dan OpenAPI tavsifini oladi;
2. har amal uchun yo'l va metod backendda BORMI — tekshiradi;
3. so'rov tanasi maydonlarini DTO bilan solishtiradi va farqni ko'rsatadi.

Farq ikki tomonlama muhim:
  YETISHMAYDI — DTO da bor, bizda yo'q. To'liq DTO talab qiladigan PATCH
                da bu maydon YO'QOLISHI mumkin (`store_id` bilan aynan
                shunday bo'lgan edi).
  ORTIQCHA    — bizda bor, DTO da yo'q. Backend uni tashlab yuboradi yoki
                butun so'rovni rad etadi.

ISHLATISH
---------
    python -m skriptlar.amal_swagger_solishtir

Tarmoqqa chiqadi, hech narsa YOZMAYDI. Chiqish kodi: 0 — hammasi mos,
1 — nomuvofiqlik bor.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from integrations.climavent_yozuvchi import (
    AMALLAR,
    MAHSULOT_YARATISH_MAYDONLARI,
    ClimaventYozuvchi,
)

SWAGGER_YOLI = "/api/docs-json"


def _dto_maydonlari(amal_op: dict, sxemalar: dict) -> set[str]:
    """Operatsiyaning so'rov tanasidagi maydon nomlari."""
    havola = (
        amal_op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref", "")
    )
    if not havola:
        return set()
    nom = havola.rsplit("/", 1)[-1]
    return set(sxemalar.get(nom, {}).get("properties", {}))


async def solishtir() -> int:
    yozuvchi = ClimaventYozuvchi()
    async with httpx.AsyncClient(timeout=30) as mijoz:
        javob = await mijoz.get(yozuvchi.asos + SWAGGER_YOLI)
        javob.raise_for_status()
        tavsif = javob.json()

    yollar = tavsif.get("paths", {})
    sxemalar = tavsif.get("components", {}).get("schemas", {})
    nomuvofiq = 0

    for nom, amal in AMALLAR.items():
        operatsiya = (yollar.get(amal.yol) or {}).get(amal.metod.lower())
        if operatsiya is None:
            print(f"YO'Q  {nom}: backendda {amal.metod} {amal.yol} yo'q")
            nomuvofiq += 1
            continue

        # Yaratish ikki bosqichli bo'lsa, POST ga faqat tor ro'yxat ketadi.
        bizniki = (
            set(MAHSULOT_YARATISH_MAYDONLARI)
            if amal.yaratish_maydonlari
            else set(amal.maydonlar)
        )
        dto = _dto_maydonlari(operatsiya, sxemalar)

        yetishmaydi = sorted(dto - bizniki)
        ortiqcha = sorted(bizniki - dto)
        if not yetishmaydi and not ortiqcha:
            print(f"OK    {nom}")
            continue

        nomuvofiq += 1
        print(f"FARQ  {nom} ({amal.metod} {amal.yol})")
        if yetishmaydi:
            print(f"        yetishmaydi (DTO da bor, bizda yo'q): {yetishmaydi}")
        if ortiqcha:
            print(f"        ortiqcha (bizda bor, DTO da yo'q):    {ortiqcha}")

    print(f"\nJami {len(AMALLAR)} amal, nomuvofiqlik: {nomuvofiq}")
    return 1 if nomuvofiq else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(solishtir()))

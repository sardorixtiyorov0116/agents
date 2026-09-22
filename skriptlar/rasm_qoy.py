"""Mahsulotga rasm biriktiradi (bitta fayl, bitta mahsulot).

NEGA SKRIPT, AGENT EMAS
-----------------------
Nodira katalogdagi hamma narsani rejalashtira oladi, rasmni esa yo'q:
model surat yarata olmaydi, u faqat HAVOLA yozishi mumkin va havolani
o'ylab topib qo'yadi. Shuning uchun rasm zanjiri teskari qurilgan —
mazmun ODAMDAN keladi, havolani BACKEND beradi:

    fayl -> POST /api/images/upload-image (Cloudinary) -> havola
         -> POST /api/product-images/create -> mahsulotga bog'landi

QACHON KERAK
------------
Katalogdagi 177 mahsulotdan 176 tasida rasm bor (2026-09-09 da
o'lchandi), ya'ni bu ommaviy to'ldirish vositasi emas. U ikki holat
uchun: yangi qo'shilgan mahsulotga surat qo'yish, va rasmsiz qolgan
yozuvni tuzatish.

ISHLATISH
---------
    python -m skriptlar.rasm_qoy <mahsulot_id> <rasm_fayli>
    python -m skriptlar.rasm_qoy 158 D:/rasmlar/rsk-klapani.jpg

    --korish     faqat ko'rsatadi, YUKLAMAYDI (avval tekshirib olish uchun)

Yozadi: rasm Cloudinary'ga yuklanadi va mahsulotga biriktiriladi.
Chiqish kodi: 0 — bajarildi, 1 — xato.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from integrations.climavent_client import ApiXatosi, ClimaventKlient
from integrations.climavent_yozuvchi import ClimaventYozuvchi, YozishXatosi

# Cloudinary katta faylni ham qabul qiladi, lekin katalog uchun bunchasi
# keragi yo'q — tasodifan RAW surat yuborilib qolmasin.
MAKS_HAJM_MB = 10
QABUL_QILINADI = {".jpg", ".jpeg", ".png", ".webp"}


async def bajar(mahsulot_id: int, fayl: Path, korish: bool) -> int:
    if not fayl.is_file():
        print(f"Fayl topilmadi: {fayl}")
        return 1
    if fayl.suffix.lower() not in QABUL_QILINADI:
        print(f"Qo'llab-quvvatlanmaydigan tur: {fayl.suffix} "
              f"(kutilgan: {', '.join(sorted(QABUL_QILINADI))})")
        return 1
    hajm_mb = fayl.stat().st_size / 1024 / 1024
    if hajm_mb > MAKS_HAJM_MB:
        print(f"Fayl juda katta: {hajm_mb:.1f} MB (chegara {MAKS_HAJM_MB} MB)")
        return 1

    # Mahsulot BORLIGINI oldindan tekshiramiz: aks holda rasm
    # Cloudinary'ga yuklanib, keyin biriktirish 404 bilan yiqilardi va
    # bulutda egasiz fayl qolardi.
    klient = ClimaventKlient()
    try:
        mahsulot = await klient.mahsulot(mahsulot_id)
    except ApiXatosi as xato:
        print(f"Mahsulot o'qilmadi: {xato}")
        return 1
    if not mahsulot:
        print(f"Mahsulot topilmadi: id={mahsulot_id}")
        return 1

    nomi = mahsulot.get("name_uz") or mahsulot.get("name_ru") or "(nomsiz)"
    bor = mahsulot.get("images") or []
    print(f"Mahsulot: {nomi} (id={mahsulot_id})")
    print(f"Hozirgi rasmlar: {len(bor)} ta")
    print(f"Yuklanadi: {fayl.name} ({hajm_mb:.2f} MB)")

    if korish:
        print("\n--korish rejimi: hech narsa yuklanmadi.")
        return 0

    yozuvchi = ClimaventYozuvchi()
    if not yozuvchi.sozlanganmi():
        print("\nGuvohnoma yo'q: `.env` ga SERVICE_API_KEY qo'shing.")
        return 1

    try:
        natija = await yozuvchi.rasm_qoy(mahsulot_id, fayl.read_bytes(), fayl.name)
    except YozishXatosi as xato:
        print(f"\nBajarilmadi: {xato}")
        return 1

    print(f"\nBajarildi. Havola: {natija['havola']}")
    return 0


def main() -> int:
    tahlilchi = argparse.ArgumentParser(
        description="Mahsulotga rasm biriktiradi.",
    )
    tahlilchi.add_argument("mahsulot_id", type=int, help="katalogdagi mahsulot id")
    tahlilchi.add_argument("fayl", type=Path, help="rasm fayli (jpg/png/webp)")
    tahlilchi.add_argument(
        "--korish", action="store_true",
        help="faqat ko'rsatadi, yuklamaydi",
    )
    args = tahlilchi.parse_args()
    return asyncio.run(bajar(args.mahsulot_id, args.fayl, args.korish))


if __name__ == "__main__":
    sys.exit(main())

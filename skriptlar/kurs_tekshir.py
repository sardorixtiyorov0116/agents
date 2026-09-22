"""Dollar kursini uch manbada solishtiradi.

NEGA KERAK
----------
`product_model_inside.price` bazada DOLLARDA saqlanadi, so'm narxi esa
o'qiyotganda kursga ko'paytiriladi. Ya'ni bu bitta raqam butun katalog
narxini ko'paytiradi: xato bo'lsa, KP ham, tender bahosi ham, saytdagi
narx ham bir vaqtda xato bo'ladi.

2026-09-09 da o'lchandi: saytda va sozlamada 12 000 turgan, Markaziy
bankda esa 11 813.21 edi — hamma so'm narxi ~1.6% yuqori ko'rsatilgan.
Buni hech kim kuzatmasdi, chunki ikkala tomon ham "o'zicha to'g'ri"
ishlardi.

QAROR QILMAYDI
--------------
Skript faqat ko'rsatadi. Qaysi kurs to'g'ri ekani BIZNES qarori:
ko'p kompaniya narxni Markaziy bank kursidan yuqoriroq oladi. Shu
siyosatni `USD_USTAMA_FOIZ` orqali ochiq yozib qo'yish mumkin — o'shanda
tavsiya "MB kursi + ustama" bo'lib hisoblanadi.

ISHLATISH
---------
    python -m skriptlar.kurs_tekshir

Tarmoqqa chiqadi (Markaziy bank va sayt), hech narsa YOZMAYDI.
Chiqish kodi: 0 — farq chegaradan kichik, 1 — sezilarli farq bor.
"""

from __future__ import annotations

import asyncio
import sys

from app.config import sozlama
from integrations.climavent_client import ClimaventKlient
from integrations.valyuta import KursXatosi, markaziy_bank_kursi, matn, solishtir


async def tekshir() -> int:
    s = sozlama()

    try:
        mb = await markaziy_bank_kursi()
    except KursXatosi as xato:
        print(f"Markaziy bank kursi olinmadi: {xato}")
        return 1

    backend = await ClimaventKlient().kurs()
    if backend is None:
        print("DIQQAT: saytdagi kurs o'qilmadi — quyida faqat zaxira qiymat.")

    natija = solishtir(mb, backend, s.usd_ustama_foiz)
    print(matn(natija))
    print(f"\nZaxira qiymat (sozlamada): {s.usd_kursi:,.2f}".replace(",", " "))

    if natija.sezilarlimi(s.usd_farq_chegarasi):
        print(
            f"\nFarq chegaradan ({s.usd_farq_chegarasi}%) katta. "
            "Kursni yangilash kerakmi — inson hal qiladi."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(tekshir()))

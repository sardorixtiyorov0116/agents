"""Oxirgi tender tekshiruvi natijasi — `/tender` bir zumda javob bersin.

MUAMMO
------
`/tender` har safar manbalarga chiqib, keyin modelga so'rov yuborardi:
manba ~8 s, model ~12 s — jami 20 soniyagacha. Menejer "Tekshiryapman…"
xabarini olib, kutib turardi. Holbuki kunlik tekshiruv ertalab
allaqachon bajarilgan va natija tayyor edi.

YECHIM
------
Rejali tekshiruv natijasi shu yerga yoziladi. `/tender` avval SHU
NATIJANI beradi — darhol, sanasi bilan. Eskirgan bo'lsa, keyin yangisi
tekshiriladi va o'zgargan bo'lsa qo'shimcha xabar keladi.

FAYLDA saqlanadi, xotirada emas: bot qayta ishga tushganda kesh
yo'qolmasin — aks holda har restartdan keyin birinchi `/tender` yana
20 soniya kutardi.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

log = logging.getLogger("bot.tender_keshi")

FAYL = Path("chiqish/tender_keshi.json")


def yoz(matn: str) -> None:
    """Tekshiruv natijasini saqlaydi. Xato bo'lsa ish TO'XTAMAYDI."""
    try:
        FAYL.parent.mkdir(parents=True, exist_ok=True)
        FAYL.write_text(
            json.dumps(
                {
                    "vaqt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "matn": matn,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        log.debug("tender keshi yozilmadi", exc_info=True)


def oqi() -> tuple[str, datetime] | None:
    """Saqlangan natija va uning vaqti. Yo'q/buzuq bo'lsa — `None`."""
    try:
        malumot = json.loads(FAYL.read_text(encoding="utf-8"))
        matn = str(malumot["matn"])
        vaqt = datetime.fromisoformat(str(malumot["vaqt"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not matn.strip():
        return None
    if vaqt.tzinfo is None:
        vaqt = vaqt.replace(tzinfo=timezone.utc)
    return matn, vaqt


def yoshi_daqiqa(vaqt: datetime) -> int:
    return max(int((datetime.now(timezone.utc) - vaqt).total_seconds() // 60), 0)


# Keshdagi matndan lot sarlavhasi va muddatini ajratish.
#
# Kesh — TAYYOR XABAR, tuzilgan ma'lumot emas. Uni qaytadan
# tuzilgan holda saqlash ham mumkin edi, lekin u holda ko'rinish
# o'zgarganda kesh formati ham o'zgarardi va eski kesh o'qilmay
# qolardi. Matndan o'qish esa ko'rinishga bog'liq — shuning uchun
# naqsh ATAYLAB sodda: raqamli sarlavha va `Muddat:` qatori.
_SARLAVHA = re.compile(r"^\d+\.\s+(.+?)(?:\s+·\s+\d{4}-\d{2}-\d{2})?$", re.M)
_MUDDAT = re.compile(r"^Muddat:\s+(\d{4}-\d{2}-\d{2})", re.M)


def shoshilinchlar(matn: str, kun: int) -> str:
    """Muddatiga `kun` yoki undan kam qolgan lotlar haqida xabar.

    Bo'sh satr qaytsa — eslatadigan narsa yo'q, xabar yuborilmaydi.
    """
    from datetime import date

    bugun = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    # Har lot bo'lagi ajratgich bilan boshlanadi.
    bolaklar = matn.split("=" * 28)
    yaqinlar: list[tuple[int, str]] = []
    for bolak in bolaklar:
        nom = _SARLAVHA.search(bolak)
        muddat = _MUDDAT.search(bolak)
        if not (nom and muddat):
            continue
        try:
            qolgan = (date.fromisoformat(muddat.group(1)) - bugun).days
        except ValueError:
            continue
        if 0 <= qolgan <= kun:
            yaqinlar.append((qolgan, nom.group(1).strip()))

    if not yaqinlar:
        return ""
    yaqinlar.sort()
    qatorlar = ["⏰ Tender muddati yaqin", ""]
    for qolgan, nom in yaqinlar:
        belgi = "BUGUN tugaydi" if qolgan == 0 else f"{qolgan} kun qoldi"
        qatorlar.append(f"• {nom[:70]}\n   {belgi}")
    qatorlar += ["", "To'liq ro'yxat: /tender"]
    return "\n".join(qatorlar)


def lotlimi(matn: str) -> bool:
    """Saqlangan matnda haqiqiy lot bormi?

    "Bizga mos e'lon topilmadi" degan xabarni `/tender` ga qaytarish
    ma'nosiz — menejer lot ro'yxatini kutadi. Lot bo'lagi ajratgich
    bilan boshlanadi, shuning uchun uni sanash yetarli.
    """
    return _MUDDAT.search(matn or "") is not None or "=" * 28 in (matn or "")

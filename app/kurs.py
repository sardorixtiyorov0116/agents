"""Amaldagi dollar kursi — bitta joyda.

MUAMMO
------
`product_model_inside.price` bazada DOLLARDA saqlanadi va so'm narxi
o'qiyotganda kursga ko'paytiriladi. Ya'ni kurs butun katalog narxini
ko'paytiruvchi yagona raqam.

Shu raqam ikki joyda mustaqil yashardi: backendning `settings.usd-rate`
da (sayt shundan hisoblaydi) va bizning `sozlama().usd_kursi` da (bot
shundan hisoblardi). Ular ajralib ketsa mijoz saytda bir narx, KP da
boshqa narx ko'radi — va buni hech kim sezmaydi, chunki ikkala tomon ham
"o'zicha to'g'ri" ishlaydi.

YECHIM
------
Manba — BACKEND. Bu modul o'sha qiymatni jarayon davomida saqlab turadi,
narx hisoblaydigan joylar esa `joriy()` dan oladi.

Nega alohida modul: narx hisoblanadigan joylar SINXRON (`narxni_top`,
KP yig'ish, so'rovnoma), `klient.kurs()` esa asinxron. Har hisobda
tarmoqqa chiqib bo'lmaydi, shuning uchun qiymat ishga tushishda va
kunlik tekshiruvda yangilanadi, orada esa keshdan o'qiladi.

Backend javob bermasa — `sozlama().usd_kursi` zaxira sifatida ishlaydi
va tizim to'xtamaydi, lekin `manba()` buni ochiq aytadi.
"""

from __future__ import annotations

from app.config import sozlama

_joriy: float | None = None
_manba: str = "zaxira"


def joriy() -> float:
    """Hozir qo'llanadigan kurs.

    Backenddan olingan bo'lsa — o'sha; olinmagan bo'lsa sozlamadagi
    zaxira qiymat.
    """
    if _joriy and _joriy > 0:
        return _joriy
    return float(sozlama().usd_kursi)


def manba() -> str:
    """Joriy qiymat qayerdan: `sayt` yoki `zaxira`."""
    return _manba


def qoy(qiymat: float | None, manbasi: str = "sayt") -> float:
    """Kursni ochiq belgilaydi (yangilash va testlar uchun)."""
    global _joriy, _manba
    if qiymat and qiymat > 0:
        _joriy = float(qiymat)
        _manba = manbasi
    return joriy()


def tozala() -> None:
    """Zaxira qiymatga qaytaradi (testlar orasida holat oqib ketmasin)."""
    global _joriy, _manba
    _joriy = None
    _manba = "zaxira"


async def yangila(klient) -> float:
    """Backenddan kursni o'qib, joriy qiymatni yangilaydi.

    `klient` — `ClimaventKlient`. Xato yutilmaydi, lekin tizimni ham
    to'xtatmaydi: qiymat olinmasa zaxira o'z kuchida qoladi.
    """
    qiymat = await klient.kurs()
    if qiymat:
        return qoy(qiymat, "sayt")
    return joriy()

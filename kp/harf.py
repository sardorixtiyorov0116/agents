"""O'zbekcha ism-familiyani lotin <-> kirill o'girish.

NEGA KERAK
----------
KP ikki tilda chiqadi. Ruscha KP da menejer ismi ham kirill harfda
turishi kerak — lotincha ism ruscha blankada begona ko'rinadi:

    Коммерческое предложение
    ...
    Менеджер: Aziz Karimov          <- xato
    Менеджер: Азиз Каримов          <- to'g'ri

Aksincha ham: menejer ismini kirillda kiritgan bo'lsa, o'zbekcha KP da
lotinda chiqishi kerak.

QOIDA: QO'LDA YOZILGANI HAR DOIM USTUN
--------------------------------------
Avtomatik o'girish ismlar uchun 100% aniq bo'lolmaydi — "Шухрат" ham
"Shuhrat", ham "Shukhrat" bo'lishi mumkin, odam o'z pasportidagini
biladi. Shuning uchun `rekvizitlar.yaml` da ikkala variantni yozish
mumkin:

    menejerlar:
      "123456789":
        ism: "Aziz Karimov"
        ism_kiril: "Азиз Каримов"     # ixtiyoriy — bo'lsa shu ishlatiladi

Bu modul faqat qo'lda yozilgani BO'LMAGANDA ishga tushadi.
"""

from __future__ import annotations

import re

# O'zbek lotinidagi tutuq belgisining barcha ko'rinishlari. Klaviatura,
# Word avtoto'g'rilash va nusxa-ko'chirish har xil belgi qoldiradi —
# hammasi bir xil ma'noni beradi.
TUTUQ = "'‘’ʻʼ`´"
_TUTUQ_BIR_XIL = {ord(b): "'" for b in TUTUQ}

# --- lotin -> kirill ---------------------------------------------------------
#
# Tartib MUHIM: uzun birikma oldin tekshiriladi, aks holda "sh" ni
# "s"+"h" deb o'qib "сҳ" chiqaradi.
LOTIN_KIRIL: list[tuple[str, str]] = [
    # "yo'" eng oldin: aks holda "yo" ushlanib "Yo'ldoshev" -> "Ёълдошев"
    # bo'lib qoladi, to'g'risi "Йўлдошев".
    ("yo'", "йў"),
    ("o'", "ў"), ("g'", "ғ"),
    ("sh", "ш"), ("ch", "ч"), ("ts", "ц"),
    ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ye", "е"),
    ("a", "а"), ("b", "б"), ("d", "д"), ("e", "е"), ("f", "ф"),
    ("g", "г"), ("h", "ҳ"), ("i", "и"), ("j", "ж"), ("k", "к"),
    ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"),
    ("q", "қ"), ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"),
    ("v", "в"), ("x", "х"), ("y", "й"), ("z", "з"),
    ("'", "ъ"),
]

# --- kirill -> lotin ---------------------------------------------------------
KIRIL_LOTIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g'", "д": "d",
    "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o",
    "ў": "o'", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}

KIRIL_HARFLAR = set(KIRIL_LOTIN) | {"Ъ", "Ь"}
LOTIN_HARFLAR = set("abcdefghijklmnopqrstuvwxyz")

_SOZ = re.compile(r"[^\s\-]+")

# Kirilldagi "е" ikki xil o'qiladi: undoshdan keyin "e" (Эргашев ->
# Ergashev), so'z boshida yoki unlidan keyin "ye" (Чориева ->
# Choriyeva, Елена -> Yelena).
KIRIL_UNLILAR = set("аеёиоуўэюя")


def yozuvi(matn: str) -> str:
    """Matn qaysi alifboda: `"kiril"`, `"lotin"` yoki `"nomalum"`."""
    past = str(matn or "").lower()
    kiril = sum(1 for b in past if b in KIRIL_HARFLAR)
    lotin = sum(1 for b in past if b in LOTIN_HARFLAR)
    if kiril > lotin:
        return "kiril"
    if lotin > kiril:
        return "lotin"
    return "nomalum"


def _bosh_harfni_saqla(asl: str, yangi: str) -> str:
    """Asl so'z bosh harfli bo'lsa, natijani ham bosh harfli qiladi.

    Ism-familiya har doim bosh harf bilan yoziladi, o'girish esa
    kichik harflar ustida ishlaydi.
    """
    if not yangi:
        return yangi
    if asl[:1].isupper():
        return yangi[:1].upper() + yangi[1:]
    return yangi


def _sozni_kirilga(soz: str) -> str:
    past = soz.lower().translate(_TUTUQ_BIR_XIL)
    natija: list[str] = []
    i = 0
    while i < len(past):
        for lot, kir in LOTIN_KIRIL:
            if past.startswith(lot, i):
                # So'z boshidagi "e" kirillda "э" bo'ladi: Erkin -> Эркин.
                if lot == "e" and i == 0:
                    kir = "э"
                natija.append(kir)
                i += len(lot)
                break
        else:
            natija.append(past[i])
            i += 1
    return _bosh_harfni_saqla(soz, "".join(natija))


def _sozni_lotinga(soz: str) -> str:
    past = soz.lower()
    natija: list[str] = []
    for orin, belgi in enumerate(past):
        almash = KIRIL_LOTIN.get(belgi)
        if almash is None:
            natija.append(belgi)
            continue
        if belgi == "е" and (orin == 0 or past[orin - 1] in KIRIL_UNLILAR):
            almash = "ye"
        natija.append(almash)
    return _bosh_harfni_saqla(soz, "".join(natija))


def kirilga(matn: str) -> str:
    """Lotincha matnni kirillga o'giradi (kirill bo'lsa — tegmaydi)."""
    matn = str(matn or "")
    if not matn.strip() or yozuvi(matn) == "kiril":
        return matn
    return _SOZ.sub(lambda m: _sozni_kirilga(m.group()), matn)


def lotinga(matn: str) -> str:
    """Kirillcha matnni lotinga o'giradi (lotin bo'lsa — tegmaydi)."""
    matn = str(matn or "")
    if not matn.strip() or yozuvi(matn) == "lotin":
        return matn
    return _SOZ.sub(lambda m: _sozni_lotinga(m.group()), matn)


def moslash(ism: str, til: str, qolda_yozilgan: dict | None = None) -> str:
    """Ismni KP tiliga moslaydi.

    `qolda_yozilgan` — `rekvizitlar.yaml` dagi variantlar (`ism_kiril`,
    `ism_lotin`). Bo'lsa — avtomatik o'girish umuman qilinmaydi.
    """
    ism = str(ism or "").strip()
    if not ism:
        return ""
    qolda_yozilgan = qolda_yozilgan or {}
    kiril_kerak = str(til or "").lower().startswith("ru")

    kalit = "ism_kiril" if kiril_kerak else "ism_lotin"
    qolda = str(qolda_yozilgan.get(kalit) or "").strip()
    if qolda:
        return qolda

    return kirilga(ism) if kiril_kerak else lotinga(ism)

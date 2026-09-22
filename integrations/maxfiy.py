"""Tashqi modelga yuborishdan oldin shaxsiy ma'lumotni yashirish.

NEGA KERAK. Jasur `TEZ_ROLLAR_ROYXATI=*` bilan Gemini BEPUL tarifida
ishlaydi, Google esa bepul tarif so'rovlarini model o'qitishga
ishlatishi mumkin (`app/config.py`). Tender hujjatlari ochiq bo'lsa ham
ichida mansabdorlarning ismi, telefoni, emaili, hisob raqami va STIR
turadi (511261 TZ: bosh direktor F.I.Sh., hisob raqam, INN). Lotni
baholash uchun ularning birortasi kerak emas.

CHEKLOV: ism EVRISTIKA bilan topiladi — initsiallar ("M.M. Parpiyev",
"Х.Мамарасулов") va otasining ismi ("… Karabayevich"). Initsialsiz
yolg'iz familiya qolib ketishi mumkin.

SUMMALAR SAQLANADI: "145 208 000 сум", "72 kVA", "30–80 kW" baho uchun
kerak. Shuning uchun yalang'och 9 xonali son (STIR ham, summa ham
bo'lishi mumkin) faqat YORLIQ bilan ("INN:", "STIR", "tel.") yashiriladi.
"""

from __future__ import annotations

import re

_KATTA = "A-ZА-ЯЁЎҚҒҲ"
_KICHIK = "a-zа-яёўқғҳ'‘’ʼʻ"

QOIDALAR: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    # Hisob raqam: 20 xona — yaxlit yoki to'rttalik guruhlarda.
    (re.compile(r"(?<!\d)(?:\d{20}|\d{4}(?: \d{4}){4})(?!\d)"), "[hisob raqam]"),
    # Telefon: +998 bilan, qavsdagi kod bilan yoki "93 524 10 60" shaklida.
    (re.compile(r"\+?998[\s\-()]*\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"),
     "[telefon]"),
    (re.compile(r"\(\d{2,3}\)\s*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)"), "[telefon]"),
    # Chegarada faqat O'NLI SON to'xtatadi ("1,25"), gap oxiridagi nuqta emas.
    (re.compile(r"(?<!\d)(?<!\d[,.])\d{2}[\s\-]\d{3}[\s\-]\d{2}[\s\-]\d{2}(?!\d|[,.]\d)"),
     "[telefon]"),
    # Yorliqli raqamlar: STIR/INN, JShShIR, MFO, telefon.
    (re.compile(
        r"(?i)(\b(?:ИНН|INN|STIR|СТИР|TIN|JShShIR|ПИНФЛ|PINFL|MFO|МФО|"
        r"tel(?:efon)?|тел(?:ефон)?|phone)\.?\s*[:№#]?\s*)(\+?\d[\d \-()]{3,}\d)"
    ), r"\1[yashirildi]"),
    # Raqam ichida faqat BO'SHLIQ — yangi qator emas. Aks holda
    # "Телефон: 933690039\n4. Ish joyi" keyingi band raqamini ham yutardi
    # (511606 TZ da shunday edi).
    # F.I.Sh. initsiallar bilan. Bitta initsial faqat BO'SHLIQSIZ olinadi:
    # "I. Malakaviy baholash" (rim raqamli sarlavha) ism emas.
    (re.compile(rf"(?<![{_KATTA}{_KICHIK}])[{_KATTA}]\.\s?[{_KATTA}]\.\s?[{_KATTA}][{_KICHIK}]{{2,}}"),
     "[shaxs]"),
    (re.compile(rf"(?<![{_KATTA}{_KICHIK}])[{_KATTA}]\.[{_KATTA}][{_KICHIK}]{{2,}}"), "[shaxs]"),
    (re.compile(rf"[{_KATTA}][{_KICHIK}]{{2,}}\s[{_KATTA}]\.\s?[{_KATTA}]\.?"), "[shaxs]"),
    # To'liq ism otasining ismi bilan.
    (re.compile(
        rf"[{_KATTA}][{_KICHIK}]+\s+[{_KATTA}][{_KICHIK}]+\s+"
        rf"(?:[{_KATTA}][{_KICHIK}]+(?:vich|vna|вич|вна)\b|"
        rf"[{_KATTA}][{_KICHIK}]+\s+(?:o['‘ʻ’]?g['‘ʻ’]?li|qizi|ўғли|қизи)\b)"
    ), "[shaxs]"),
)


def yashir(matn: str) -> str:
    """Email, telefon, hisob raqam, yorliqli STIR/JShShIR va ismlarni almashtiradi."""
    for naqsh, orinbosar in QOIDALAR:
        matn = naqsh.sub(orinbosar, matn)
    return matn

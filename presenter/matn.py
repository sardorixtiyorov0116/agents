"""Javobni odamcha matnga aylantirish.

Tizim ichida konvert strukturalangan bo'lib qoladi (o'zgarmaydi). Bu qatlam
faqat CHIQISHDA ishlaydi: texnik maydonlarni yashiradi, bo'shlarini olib
tashlaydi, uzun ro'yxatlarni qisqartiradi va manbani bitta qatorga yig'adi.

Agent kodida formatlash yo'q — hammasi shu yerda.
"""

from __future__ import annotations

from typing import Any

from app.konvert import Holat, Ishonch, Konvert, Manba

# Foydalanuvchiga HECH QACHON ko'rsatilmaydigan maydonlar.
TEXNIK_MAYDONLAR = frozenset(
    {
        "manba_turi", "havola", "ichki_manba", "tashqi_bozor", "manba_ishonchsiz",
        "sql", "katalogdan_javob", "taklif_sql", "rad_etilgan_sql", "kesildi",
        "product_id", "category_id", "contentJson", "sizesJson", "opisaniyaJson",
        "naznacheniyaJson", "markirovkaJson", "yozish", "manba_nomi",
    }
)

# Uzun ro'yxatlar shuncha elementdan keyin qisqartiriladi.
MAKS_ROYXAT = 6

MANBA_NOMI = {
    "ichki_api": "Climavent ichki katalogi",
    "tashqi_veb": "tashqi manbalar",
    "profil": "kompaniya profili",
    "baza": "ichki baza",
    "bilim": "bilim bazasi",
    "kontrakt": "agent kontrakti",
    "agent": "oldingi agent natijasi",
    "hujjat": "hujjat",
    "veb": "veb",
}

ISHONCH_OGOHI = {
    Ishonch.PAST: "⚠️ Ishonch past — ma'lumot to'liq emas yoki manba ishonchsiz.",
    Ishonch.ORTA: "",
    Ishonch.YUQORI: "",
}


def _bosh(qiymat: Any) -> bool:
    if qiymat is None or qiymat is False:
        return True
    if isinstance(qiymat, str):
        return not qiymat.strip()
    if isinstance(qiymat, (list, dict, tuple, set)):
        return len(qiymat) == 0
    return False


def _sarlavha(kalit: str) -> str:
    return kalit.replace("_", " ").capitalize()


def xabarni_bol(matn: str, maks: int) -> list[str]:
    """Uzun xabarni bo'laklarga bo'ladi — KESMAYDI.

    Telegram bitta xabarda 4096 belgidan ko'pini qabul qilmaydi.
    Ilgari ortiqchasi shunchaki kesilardi va menejer 12 ta e'londan
    5 tasini ko'rardi — qolgani yo'qolgani BILINMASDI.

    Bo'lish joyi tanlanadi, tasodifiy emas:
      1) e'lonlar orasidagi ajratgich (`====`) — eng yaxshi joy;
      2) bo'sh qator;
      3) oddiy qator.
    Hech biri bo'lmasa (bitta juda uzun qator) — o'sha joydan kesiladi,
    aks holda tsikl tugamasdi.
    """
    matn = (matn or "").strip()
    if not matn:
        return []
    if maks <= 0 or len(matn) <= maks:
        return [matn]

    bolaklar: list[str] = []
    qoldiq = matn
    while len(qoldiq) > maks:
        oyna = qoldiq[:maks]
        # Ajratgichdan oldin bo'lish — e'lon ikkiga bo'linib qolmasin.
        kesim = oyna.rfind("\n" + "=" * 10)
        if kesim <= 0:
            kesim = oyna.rfind("\n\n")
        if kesim <= 0:
            kesim = oyna.rfind("\n")
        if kesim <= 0:
            kesim = maks
        bolaklar.append(qoldiq[:kesim].strip())
        qoldiq = qoldiq[kesim:].strip()
    if qoldiq:
        bolaklar.append(qoldiq)
    return bolaklar


def qisqartir(elementlar: list[str], maks: int = MAKS_ROYXAT) -> str:
    """Uzun ro'yxatni qisqartiradi: "a, b, c (yana 5 ta)"."""
    toza = [str(e).strip() for e in elementlar if str(e).strip()]
    if not toza:
        return ""
    if len(toza) <= maks:
        return ", ".join(toza)
    return f"{', '.join(toza[:maks])} (yana {len(toza) - maks} ta)"


def manba_qatori(manbalar: list[Manba]) -> str:
    """Manbalarni bitta qisqa qatorga yig'adi."""
    if not manbalar:
        return ""

    nomlar: list[str] = []
    korilgan: set[str] = set()
    for manba in manbalar:
        nom = MANBA_NOMI.get(manba.tur, manba.tur)
        # Aniq hujjat nomi bo'lsa — o'shani ko'rsatamiz.
        if manba.tur in ("bilim", "hujjat", "kontrakt") and manba.nom:
            nom = manba.nom
        if nom in korilgan:
            continue
        korilgan.add(nom)
        nomlar.append(nom)

    return "Manba: " + qisqartir(nomlar, 4)


# --- qiymatlarni matnga aylantirish -----------------------------------------


def _juft_matni(element: dict[str, Any]) -> str:
    """{"nomi": X, "qiymat": Y} kabi juftlikni "X: Y" ga aylantiradi."""
    nomi = element.get("nomi") or element.get("nom") or element.get("title")
    qiymat = element.get("qiymat") or element.get("value")
    if nomi and qiymat:
        return f"{nomi}: {qiymat}"
    return ""


def _element_matni(element: Any) -> str:
    if isinstance(element, str):
        return element.strip()
    if not isinstance(element, dict):
        return str(element)

    juft = _juft_matni(element)
    if juft:
        return juft

    # Umumiy holat: texnik va bo'sh maydonlarsiz "kalit: qiymat" qatori.
    bolaklar = [
        f"{_sarlavha(k)}: {v}"
        for k, v in element.items()
        if k not in TEXNIK_MAYDONLAR and not _bosh(v) and not isinstance(v, (list, dict))
    ]
    return " · ".join(bolaklar)


def _royxat_matni(kalit: str, elementlar: list[Any]) -> str:
    qatorlar = [_element_matni(e) for e in elementlar]
    qatorlar = [q for q in qatorlar if q]
    if not qatorlar:
        return ""

    # Qisqa ro'yxatlar bitta qatorda, uzunlari — punktlar bilan.
    if all(len(q) < 45 for q in qatorlar) and len(qatorlar) <= 3:
        return f"{_sarlavha(kalit)}: {', '.join(qatorlar)}"

    kesilgan = qatorlar[:MAKS_ROYXAT]
    matn = "\n".join(f"• {q}" for q in kesilgan)
    if len(qatorlar) > MAKS_ROYXAT:
        matn += f"\n• … yana {len(qatorlar) - MAKS_ROYXAT} ta"
    return f"{_sarlavha(kalit)}:\n{matn}"


def natija_matni(natija: dict[str, Any]) -> str:
    """`natija` lug'atini o'qish uchun qulay matnga aylantiradi (umumiy holat)."""
    bolaklar: list[str] = []
    for kalit, qiymat in (natija or {}).items():
        if kalit in TEXNIK_MAYDONLAR or _bosh(qiymat):
            continue
        if isinstance(qiymat, list):
            matn = _royxat_matni(kalit, qiymat)
        elif isinstance(qiymat, dict):
            ichki = natija_matni(qiymat)
            matn = f"{_sarlavha(kalit)}:\n{ichki}" if ichki else ""
        else:
            matn = f"{_sarlavha(kalit)}: {qiymat}"
        if matn:
            bolaklar.append(matn)
    return "\n\n".join(bolaklar)

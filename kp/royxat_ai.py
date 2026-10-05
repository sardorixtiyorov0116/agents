"""Mijoz ro'yxatidagi nomlarni katalog nomiga moslashtirish — AI bilan.

NEGA KERAK
----------
«Mahsulot bilaman» yo'lida AI umuman yo'q edi: tizim faqat aniq
moslikni qidirardi. Menejer nomni bir oz boshqacha yozsa — jimgina
bo'sh natija. Tashqaridan «qotib qolgan» bo'lib ko'rinardi:
ishlayotgani yoki ishlamayotgani bilinmasdi.

Qotib qolgan moslik jadvali bu muammoni HAL QILMAYDI — u faqat
oldindan yozilgan holatlarni biladi. Har yangi yozilish uchun jadvalga
qator qo'shish kerak bo'lardi.

TUZILMA: KOD TORAYTIRADI -> AI TANLAYDI -> KOD NARXLAYDI
--------------------------------------------------------
1. Kod har qator uchun katalogdan NOMZODLARNI topadi (`_variantlar`).
2. Nomzod bitta bo'lsa — AI chaqirilmaydi.
3. Ko'p yoki noaniq bo'lsa — AI BITTA chaqiruvda hammasini hal qiladi.
4. Narx keyin KOD orqali topiladi.

AI FAQAT TANLAYDI, O'YLAB TOPMAYDI. Unga nomzodlar ro'yxati beriladi
va u faqat o'sha ro'yxatdan raqam qaytaradi. Qaytgan raqam nomzodlar
sonidan tashqarida bo'lsa — natija RAD ETILADI. Shu tufayli model
katalogda yo'q nomni KP ga kirita olmaydi.

NEGA BITTA CHAQIRUV. Gemini bepul tarifida kuniga 20 ta so'rov
(2026-08-28 da o'lchandi). Har qator uchun alohida chaqiruv bitta KP
bilan kunlik kvotani tugatardi.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("kp.royxat")

# AI ga beriladigan eng ko'p nomzod — prompt cheksiz o'smasin.
MAKS_NOMZOD = 12

# AI ga beriladigan eng ko'p qator. Undan ortig'i kesiladi va
# ogohlantiriladi: yarim natija bergandan ko'ra chegarani aytish
# halolroq.
MAKS_QATOR = 60

TOPILMADI = -1

TIZIM_PROMPT = """Sen ventilyatsiya katalogi bo'yicha yordamchisan.

VAZIFA: mijoz yozgan har bir qator uchun KATALOGDAGI to'g'ri modelni
tanlash.

QAT'IY QOIDALAR:
1. Faqat berilgan nomzodlar ro'yxatidan tanlaysan. Yangi nom
   O'YLAB TOPMAYSAN.
2. Javob — nomzodning RAQAMI (0 dan boshlab).
3. Ishonchli mos kelmasa -1 qaytar. Taxmin qilma: noto'g'ri model
   noto'g'ri narx degani.
4. O'lcham (masalan 500х300) MOS KELISHI SHART. O'lchami boshqa
   model — boshqa mahsulot.
5. Dvigatel quvvati yoki bajarilish raqami farq qilsa va mijoz uni
   ko'rsatmagan bo'lsa — -1 qaytar, menejer o'zi tanlaydi.

Javobni faqat JSON ko'rinishida ber."""

JSON_SKELET = """Javob shakli:
{"tanlovlar": [{"qator": 0, "nomzod": 3}, {"qator": 1, "nomzod": -1}]}"""


@dataclass
class Taklif:
    """Bitta qator uchun AI tanlovi."""

    index: int
    nomi: str
    nomzodlar: list[str] = field(default_factory=list)
    tanlangan: str = ""


def sorov_matni(qatorlar: list[tuple[int, str, list[str]]]) -> str:
    """AI ga beriladigan matn."""
    bolaklar = []
    for raqam, (_, nomi, nomzodlar) in enumerate(qatorlar):
        bolaklar.append(f"\n--- Qator {raqam} ---")
        bolaklar.append(f"Mijoz yozgan: {nomi}")
        bolaklar.append("Nomzodlar:")
        for i, n in enumerate(nomzodlar):
            bolaklar.append(f"  {i}. {n}")
    return "\n".join(bolaklar)


def javobni_oqi(
    xom: dict[str, Any], qatorlar: list[tuple[int, str, list[str]]]
) -> dict[int, str]:
    """AI javobidan {qator index: tanlangan nom}.

    CHEGARADAN TASHQARI raqam RAD ETILADI — model katalogda yo'q
    nomni KP ga kirita olmasin.
    """
    natija: dict[int, str] = {}
    for tanlov in xom.get("tanlovlar") or []:
        if not isinstance(tanlov, dict):
            continue
        try:
            raqam = int(tanlov.get("qator"))
            nomzod = int(tanlov.get("nomzod"))
        except (TypeError, ValueError):
            continue
        if not 0 <= raqam < len(qatorlar):
            continue
        _, _, nomzodlar = qatorlar[raqam]
        if nomzod == TOPILMADI or not 0 <= nomzod < len(nomzodlar):
            continue
        natija[qatorlar[raqam][0]] = nomzodlar[nomzod]
    return natija


def _nomzodlar(katalog: list[dict[str, Any]], nom: str) -> list[str]:
    from .shakldan import _variantlar

    korilgan: list[str] = []
    for v in _variantlar(katalog, nom):
        if v["nomi"] not in korilgan:
            korilgan.append(v["nomi"])
    return korilgan[:MAKS_NOMZOD]


def hal_qilinishi_kerakmi(nomzodlar: list[str], nom: str) -> bool:
    """Bu qator uchun AI kerakmi?

    Nomzod bitta bo'lsa yoki mijoz nomi nomzodlardan biriga AYNAN
    teng bo'lsa — AI kerak emas. Kvota tejaladi.
    """
    if len(nomzodlar) <= 1:
        return False
    past = nom.strip().lower()
    return not any(n.strip().lower() == past for n in nomzodlar)


async def moslashtir(
    mahsulotlar: list[dict[str, Any]],
    katalog: list[dict[str, Any]],
    llm: Any,
) -> tuple[dict[int, str], list[str]]:
    """({index: katalog nomi}, ogohlantirishlar).

    XATO YUTILADI. AI ishlamasa (kvota, tarmoq) ro'yxat AVVALGIDEK
    ishlanadi — KP baribir chiqadi, faqat moslashtirishsiz. Menejer
    uchun moslashtirilmagan KP — umuman KP yo'qligidan yaxshi.
    """
    from app.llm import json_ajrat, matn_yig
    from app.sarf import rol_bilan

    kerakli: list[tuple[int, str, list[str]]] = []
    ogohlantirishlar: list[str] = []

    for index, xom in enumerate(mahsulotlar[:MAKS_QATOR]):
        nom = str(xom.get("nomi") or "").strip()
        if not nom or xom.get("sarlavha"):        # seksiya sarlavhasi — mahsulot emas
            continue
        nomzodlar = _nomzodlar(katalog, nom)
        if not nomzodlar:
            continue
        if hal_qilinishi_kerakmi(nomzodlar, nom):
            kerakli.append((index, nom, nomzodlar))

    if len(mahsulotlar) > MAKS_QATOR:
        ogohlantirishlar.append(
            f"Ro'yxatda {len(mahsulotlar)} qator — birinchi {MAKS_QATOR} tasi "
            "katalog bilan solishtirildi, qolgani menejer tomonidan tekshirilsin")

    if not kerakli:
        return {}, ogohlantirishlar

    try:
        with rol_bilan("royxat-moslash"):
            javob = await llm.javob(
                system=TIZIM_PROMPT,
                messages=[{"role": "user",
                           "content": sorov_matni(kerakli) + "\n\n" + JSON_SKELET}],
            )
        tanlovlar = javobni_oqi(json_ajrat(matn_yig(javob)), kerakli)
    except Exception as xato:                       # noqa: BLE001
        log.warning("ro'yxatni moslashtirib bo'lmadi: %s", xato)
        ogohlantirishlar.append(
            "Ro'yxat katalog bilan avtomatik solishtirilmadi — "
            "nomlarni menejer tekshirsin")
        return {}, ogohlantirishlar

    hal_bolmagan = [nom for index, nom, _ in kerakli if index not in tanlovlar]
    if hal_bolmagan:
        ogohlantirishlar.append(
            "Katalogdan aniq mos kelmadi: " + ", ".join(hal_bolmagan[:8])
            + (" va boshqalar" if len(hal_bolmagan) > 8 else "")
            + " — menejer tanlasin")
    return tanlovlar, ogohlantirishlar


def qollash(
    mahsulotlar: list[dict[str, Any]], tanlovlar: dict[int, str]
) -> list[dict[str, Any]]:
    """Tanlangan nomlarni ro'yxatga yozadi. ASL nom saqlanadi."""
    natija = []
    for index, xom in enumerate(mahsulotlar):
        yozuv = dict(xom)
        yangi = tanlovlar.get(index)
        if yangi and yangi != yozuv.get("nomi"):
            yozuv.setdefault("asl_nomi", yozuv.get("nomi"))
            yozuv["nomi"] = yangi
        natija.append(yozuv)
    return natija

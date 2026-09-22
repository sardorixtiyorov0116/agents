"""Javob formatlash qatlami — konvertni odamcha matnga aylantiradi.

Tizim ichida konvert strukturalangan bo'lib qoladi; bu qatlam faqat
foydalanuvchiga chiqishda ishlaydi. Agent kodida formatlash yo'q.

Kanallar:
  - `telegram` — qisqa, emoji o'rinli
  - `web`      — kengroq, panel uchun
"""

from __future__ import annotations

from typing import Any

from app.konvert import Holat, Ishonch, Konvert
from app.orkestr import Natija

from .agentlar import agent_matni
from .matn import ISHONCH_OGOHI, manba_qatori, natija_matni, qisqartir

# Har holat uchun tushunarli xabar — tizim hech qachon jim qolmaydi.
HOLAT_XABARI = {
    Holat.MOS_AGENT_YOQ: (
        "➖ Bu so'rovni bajaradigan agent yo'q.\n"
        "Tizimdagi agentlar: narx, raqobat, mahsulot, ma'lumot, marketing, HR, yuridik."
    ),
    Holat.ULANMAGAN: "🔧 Bu agent hali kodda ulanmagan.",
    Holat.XATO: "⚠️ So'rov bajarilmadi.",
}

HOLAT_BELGISI = {
    Holat.TUGADI: "✅",
    Holat.TASDIQ_KUTILMOQDA: "⏸",
    Holat.ANIQLIK_KERAK: "❓",
    Holat.MOS_AGENT_YOQ: "➖",
    Holat.ULANMAGAN: "🔧",
    Holat.XATO: "⚠️",
}


def _aniqlik_matni(konvert: Konvert) -> str:
    savollar = konvert.natija.get("savollar") or []
    qatorlar = ["❓ Davom etish uchun aniqlashtirish kerak:", ""]
    qatorlar.extend(f"{i}. {savol}" for i, savol in enumerate(savollar, 1))
    qatorlar.append("")
    qatorlar.append("Javobingizni yozing — so'rov shundan keyin ishga tushadi.")
    return "\n".join(qatorlar)


def konvert_matni(konvert: Konvert, korinishlar: dict[str, str] | None = None) -> str:
    """Bitta konvertni odamcha matnga aylantiradi."""
    korinishlar = korinishlar or {}

    if konvert.holat is Holat.ANIQLIK_KERAK:
        return _aniqlik_matni(konvert)

    # Router tizim haqidagi savolga o'zi javob bergan.
    if konvert.kim == "router" and konvert.natija.get("javob"):
        return str(konvert.natija["javob"]).strip()

    if konvert.holat in (Holat.MOS_AGENT_YOQ, Holat.ULANMAGAN, Holat.XATO):
        # Konstruktiv taklif bo'lsa — asosiy javob o'sha, quruq rad etish emas.
        taklif = str(konvert.natija.get("taklif") or "").strip()
        if taklif:
            return taklif

        # Sabab har doim aytiladi — foydalanuvchi jim qolmaydi.
        bosh = HOLAT_XABARI.get(konvert.holat, "")
        sabab = konvert.izoh.strip()
        return f"{bosh}\n\n{sabab}" if sabab else bosh

    bolaklar: list[str] = []
    tana = agent_matni(konvert.kim, konvert.natija)
    if tana:
        bolaklar.append(tana)

    ogoh = ISHONCH_OGOHI.get(konvert.ishonch, "")
    if ogoh:
        bolaklar.append(ogoh)

    manba = manba_qatori(konvert.manba)
    if manba:
        bolaklar.append(manba)

    return "\n\n".join(b for b in bolaklar if b)


def javob_matni(
    natija: Natija,
    korinishlar: dict[str, str] | None = None,
    kanal: str = "telegram",
) -> str:
    """Yakuniy javob — foydalanuvchiga ko'rsatiladigan to'liq matn."""
    korinishlar = korinishlar or {}
    yakuniy = natija.yakuniy

    if yakuniy.holat is Holat.ANIQLIK_KERAK:
        return _aniqlik_matni(yakuniy)

    kim = korinishlar.get(yakuniy.kim, yakuniy.kim)
    belgi = HOLAT_BELGISI.get(yakuniy.holat, "•")

    bolaklar: list[str] = []

    # Tizim savoliga javob — sarlavhasiz, to'g'ridan-to'g'ri matn.
    if yakuniy.kim == "router" and yakuniy.natija.get("javob"):
        return str(yakuniy.natija["javob"]).strip()

    # Sarlavha: kim javob bermoqda
    if yakuniy.holat is Holat.TUGADI:
        bolaklar.append(f"{belgi} {kim}")
    elif yakuniy.holat is Holat.TASDIQ_KUTILMOQDA:
        bolaklar.append(f"{belgi} {kim} — tasdiq kutilmoqda")

    # Zanjir bo'lsa — qisqacha ko'rsatamiz
    if len(natija.qadamlar) > 1:
        zanjir = " → ".join(korinishlar.get(q.agent, q.agent) for q in natija.qadamlar)
        bolaklar.append(f"Zanjir: {zanjir}")

    # Zanjir o'rtasida to'xtagan bo'lsa — qayerda to'xtagani aytiladi
    toxtash = _toxtash_xabari(natija, korinishlar)
    if toxtash:
        bolaklar.append(toxtash)

    tana = konvert_matni(yakuniy, korinishlar)
    if tana:
        bolaklar.append(tana)

    matn = "\n\n".join(b for b in bolaklar if b)
    return matn.strip() or "Javob bo'sh qaytdi — qayta urinib ko'ring."


def mijoz_matni(natija: Natija) -> str:
    """MIJOZ ko'radigan matn — ichki bezaklarsiz.

    Ichki botda "✅ Loyihachi muhandis Rustam", "⏸ tasdiq kutilmoqda",
    "Manba: hvac-calc kontrakti" foydali: xodim kim ishlaganini va
    natija tasdiq kutayotganini bilishi kerak.

    Mijozga esa bularning hammasi zarar:
      - agent ismlari — ichki tuzilma, tashqariga chiqmasligi kerak;
      - "tasdiq kutilmoqda" — mijoz javob chala qolgan deb o'ylaydi,
        aslida hisob tayyor, faqat ichkarida muhandis ko'rib chiqadi;
      - "Manba: kontrakt" — mijoz uchun ma'nosiz.

    Shuning uchun bu yerda faqat javobning O'ZI qoladi.
    """
    yakuniy = natija.yakuniy

    if yakuniy.holat is Holat.ANIQLIK_KERAK:
        return _aniqlik_matni(yakuniy)

    if yakuniy.kim == "router" and yakuniy.natija.get("javob"):
        return str(yakuniy.natija["javob"]).strip()

    bolaklar: list[str] = []
    tana = agent_matni(yakuniy.kim, yakuniy.natija)
    if tana:
        bolaklar.append(tana)

    # Ishonch ogohlantirishi QOLADI — bu mijozga ham kerak ("ma'lumot
    # to'liq emas" degan gapni yashirish yaxshi emas).
    ogoh = ISHONCH_OGOHI.get(yakuniy.ishonch, "")
    if ogoh:
        bolaklar.append(ogoh)

    return "\n\n".join(b for b in bolaklar if b).strip()


def _toxtash_xabari(natija: Natija, korinishlar: dict[str, str]) -> str:
    """Reja to'liq bajarilmagan bo'lsa, qaysi qadamda to'xtaganini aytadi."""
    reja = natija.reja
    if reja is None or len(reja.qadamlar) <= len(natija.qadamlar):
        return ""
    if natija.yakuniy.holat is Holat.TASDIQ_KUTILMOQDA:
        return ""  # bu to'xtash emas, kutish

    bajarilgan = len(natija.qadamlar)
    keyingi = reja.qadamlar[bajarilgan]
    nomi = korinishlar.get(keyingi.agent, keyingi.agent)
    return f"⏹ Zanjir {bajarilgan}-qadamda to'xtadi — {nomi} boshlanmadi."


def xom_json(konvert: Konvert) -> str:
    """"Batafsil" uchun xom ko'rinish (faqat so'ralganda)."""
    return konvert.model_dump_json(indent=2)


__all__ = [
    "HOLAT_BELGISI",
    "HOLAT_XABARI",
    "agent_matni",
    "javob_matni",
    "konvert_matni",
    "mijoz_matni",
    "manba_qatori",
    "natija_matni",
    "qisqartir",
    "xom_json",
]

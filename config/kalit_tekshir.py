"""`.env` dagi ANTHROPIC_API_KEY ni tekshiradi.

Serverni ko'tarmasdan, bir soniyada javob beradi: kalit ishlayaptimi,
ishlamasa — aynan nimasi noto'g'ri. Kalitning o'zi ekranga chiqmaydi,
faqat uzunligi va boshlanishi ko'rsatiladi.

    .venv\\Scripts\\python config/kalit_tekshir.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ILDIZ = Path(__file__).resolve().parent.parent
ASOS = "https://api.anthropic.com"
# Oldingi kalitning barmoq izi. Kalitning o'zi emas — faqat xesh, shuning
# uchun bu faylda maxfiy ma'lumot yo'q.
IZ_FAYLI = ILDIZ / "config" / ".kalit_izi"


def _iz(kalit: str) -> str:
    return hashlib.sha256(kalit.encode()).hexdigest()[:16]


def _ozgardimi(kalit: str) -> bool | None:
    """Kalit oldingi tekshiruvdagidan farq qiladimi? Birinchi marta — `None`."""
    yangi = _iz(kalit)
    eski = IZ_FAYLI.read_text(encoding="utf-8").strip() if IZ_FAYLI.is_file() else ""
    IZ_FAYLI.write_text(yangi, encoding="utf-8")
    return None if not eski else yangi != eski


def _shakl_tekshiruvi(kalit: str) -> list[str]:
    """Serverdan so'ramasdan ko'rinadigan xatolar."""
    ogohlantirish = []
    if kalit != kalit.strip():
        ogohlantirish.append("boshida yoki oxirida bo'sh joy bor")
    if kalit.startswith(('"', "'")) or kalit.endswith(('"', "'")):
        ogohlantirish.append("qo'shtirnoq ichida — qo'shtirnoqsiz yozing")
    if not kalit.startswith("sk-ant-"):
        ogohlantirish.append("`sk-ant-` bilan boshlanmayapti — bu Anthropic kaliti emas")
    if "..." in kalit or "…" in kalit:
        ogohlantirish.append(
            "ichida `...` bor — konsolda YASHIRILGAN ko'rinish nusxalangan. "
            "Kalit faqat yaratilgan paytda to'liq ko'rsatiladi."
        )
    if len(kalit) < 90:
        ogohlantirish.append(f"juda qisqa ({len(kalit)} belgi) — to'liq nusxalanmagan")
    return ogohlantirish


def _sorov(kalit: str) -> tuple[int, str]:
    """Eng arzon chaqiruv: model ro'yxati. Token sarflamaydi."""
    req = urllib.request.Request(
        f"{ASOS}/v1/models?limit=1",
        headers={"x-api-key": kalit, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as javob:
            return javob.status, ""
    except urllib.error.HTTPError as xato:
        tana = json.loads(xato.read().decode() or "{}")
        return xato.code, tana.get("error", {}).get("message", "")
    except urllib.error.URLError as xato:
        return 0, f"ulanib bo'lmadi: {xato.reason}"


YECHIMLAR = {
    401: (
        "Kalit Anthropic tomonidan tanilmadi. Ehtimoli bo'yicha:\n"
        "  1. Kalit o'chirilgan yoki qayta yaratilgan (eskisi bekor bo'ladi).\n"
        "  2. Nusxalashda bir qismi tushib qolgan.\n"
        "  3. Boshqa tashkilot (organization) kaliti.\n"
        "Yechim: console.anthropic.com -> Settings -> API keys -> Create Key,\n"
        "        `Copy` tugmasi bilan nusxalang (kalit FAQAT shu payt to'liq\n"
        "        ko'rinadi) va .env dagi qatorni butunlay almashtiring."
    ),
    403: "Kalit bor, lekin bu amalga ruxsati yo'q. Tashkilot sozlamalarini ko'ring.",
    429: "Kalit ishlayapti, lekin so'rovlar limitiga yetilgan.",
}


def main() -> int:
    env = dotenv_values(ILDIZ / ".env")
    kalit = env.get("ANTHROPIC_API_KEY") or ""

    if not kalit:
        print("[X] .env da ANTHROPIC_API_KEY yo'q.")
        return 1

    print(f"Kalit: {len(kalit)} belgi, boshlanishi {kalit[:14]}...")
    ozgardi = _ozgardimi(kalit)
    if ozgardi is False:
        print(
            "[!] Bu kalit oldingi tekshiruvdagi bilan AYNAN BIR XIL.\n"
            "    Ya'ni .env saqlandi, lekin ichidagi satr o'zgarmadi —\n"
            "    ehtimol o'sha eski kalit qayta nusxalanyapti."
        )
    for ogoh in _shakl_tekshiruvi(kalit):
        print(f"[!] {ogoh}")

    kod, xabar = _sorov(kalit.strip().strip("\"'"))
    if kod == 200:
        print("[OK] Kalit ishlayapti.")
        return 0

    print(f"[X] Anthropic javobi: HTTP {kod} {xabar}".rstrip())
    yechim = YECHIMLAR.get(kod)
    if yechim:
        print(yechim)
    return 1


if __name__ == "__main__":
    sys.exit(main())

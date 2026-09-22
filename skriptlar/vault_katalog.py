"""Obsidian katalogini tartibga soladi.

NEGA KERAK
----------
Bosma katalog PDF dan Obsidian'ga ko'chirilganda TAVSIF matni olindi,
TEXNIK JADVALLAR esa qolib ketdi: 103 ta yozuvning BIRORTASIDA ham
jadval yo'q edi (2026-08-28 da tekshirildi). Ya'ni "ВЦ 4-75 nima
qiladi" degan savolga javob bor, "6,3-raqamli qancha havo beradi"
degan savolga yo'q.

Raqamlar backendda BOR (`texnik_parametrlar` — 297 yozuv). Bu skript
ularni yozuvlarga qo'shadi.

Shuningdek:
  - katalog -> bo'limlar -> mahsulotlar ko'rinishini yasaydi;
  - yo'q oilalarga yozuv ochadi;
  - PDF dan tushib qolgan NUL baytlarini tozalaydi.

QAYTA ISHGA TUSHIRISH XAVFSIZ. Jadval bo'limi belgilar orasiga
yoziladi va har safar QAYTA yoziladi — takrorlanmaydi.

    .venv\\Scripts\\python -m skriptlar.vault_katalog
"""

from __future__ import annotations

import asyncio
import pathlib
import re
from collections import defaultdict

from integrations.climavent_client import ClimaventKlient

VAULT = pathlib.Path(r"D:\AGENTS\Jihozvent-Vault\02-Mahsulotlar\Katalog-2021")

# Jadval shu ikki belgi orasiga yoziladi — qayta ishga tushganda
# eskisi almashadi, tagiga yana bittasi qo'shilmaydi.
BOSH = "<!-- TEXNIK-JADVAL:boshi -->"
OXIR = "<!-- TEXNIK-JADVAL:oxiri -->"

BOLIMLAR_FAYLI = "Katalog 2021 — indeks.md"   # MAVJUD indeks


def _matn(yol: pathlib.Path) -> str:
    """NUL baytlarni tozalab o'qiydi.

    PDF dan ko'chirishda 3 ta faylga NUL tushgan — Obsidian ularni
    g'alati ko'rsatadi va `grep` "binary file" deb o'tkazib yuboradi.
    """
    xom = yol.read_bytes()
    if b"\x00" in xom:
        xom = xom.replace(b"\x00", b"")
        yol.write_bytes(xom)
        print(f"   NUL tozalandi: {yol.name}")
    return xom.decode("utf-8", errors="replace")


def raqamsiz(nom: str) -> str:
    """Model nomidan O'LCHAM raqamlarini olib tashlaydi.

    «ВК-250П» -> «ВК-П», «ВНР-10-15,0/1000» -> «ВНР».

    NEGA KERAK: vaultda oila nomi «ВК-П» ko'rinishida, backendda esa
    o'lcham nom O'RTASIDA turadi («ВК-250П»). To'g'ridan-to'g'ri
    solishtirilsa oila «yo'q» deb chiqadi va bo'sh yozuv yasaladi —
    aslida u joyida.
    """
    toza = re.sub(r"[\d,\.]+", "", nom)          # raqamlarni olib tashlaymiz
    toza = re.sub(r"/+", "", toza)                # «/1000» qoldig'i
    toza = re.sub(r"[-\s]{2,}", "-", toza)       # ketma-ket ajratgichlar
    return toza.strip(" -№").upper()


def _maydon(matn: str, nom: str) -> str:
    mos = re.search(rf"^{nom}:\s*(.+)$", matn, re.M)
    return mos.group(1).strip() if mos else ""


def _oraliq(qiymat) -> str:
    if isinstance(qiymat, list) and len(qiymat) >= 2:
        a, b = qiymat[0], qiymat[1]
        return f"{a:g}–{b:g}" if a != b else f"{a:g}"
    if isinstance(qiymat, (int, float)):
        return f"{qiymat:g}"
    return "—"


def jadval_yasa(yozuvlar: list[tuple[str, dict]]) -> str:
    """Model o'lchamlari jadvali."""
    qatorlar = [
        BOSH,
        "",
        "## Texnik ko'rsatkichlar",
        "",
        "> [!note] Manba",
        "> Raqamlar Climavent backendidan olingan (`texnik_parametrlar`).",
        "> Bosma katalogdagi jadvallar PDF dan ko'chirilmagan edi.",
        "",
        "| Model | Havo sarfi, m³/soat | To'liq bosim, Pa |",
        "|---|---|---|",
    ]
    for nom, y in sorted(yozuvlar):
        qatorlar.append(
            f"| `{nom}` | {_oraliq(y.get('havo_sarfi'))} | {_oraliq(y.get('bosim'))} |")
    qatorlar += ["", f"Jami {len(yozuvlar)} ta o'lcham.", "", OXIR]
    return "\n".join(qatorlar)


def jadvalni_qoy(matn: str, jadval: str) -> str:
    """Jadvalni qo'yadi yoki mavjudini ALMASHTIRADI."""
    if BOSH in matn and OXIR in matn:
        return re.sub(re.escape(BOSH) + r".*?" + re.escape(OXIR),
                      jadval, matn, flags=re.S)
    return matn.rstrip() + "\n\n---\n\n" + jadval + "\n"


async def main() -> None:
    par = await ClimaventKlient().texnik_parametrlar()
    print(f"backend: {len(par)} texnik yozuv")

    # --- Yozuvlarni o'qiymiz ---
    yozuvlar: dict[str, dict] = {}
    for f in sorted(VAULT.glob("*.md")):
        if f.name.startswith("00 ") or f.name.startswith("Katalog 2021"):
            continue
        matn = _matn(f)
        kod = _maydon(matn, "model_kodi")
        if not kod:
            continue
        # `model_kodi` BIR NECHTA bo'lishi mumkin: «ДН, ВДН» — bitta
        # yozuv ikkita oilani qamraydi. Vergul bo'yicha ajratilmasa
        # ikkalasi ham "yo'q" deb chiqardi.
        kodlar_royxati = [k.strip() for k in kod.split(",") if k.strip()]
        yozuvlar[f.name] = {"yol": f, "kod": kod, "kodlar": kodlar_royxati,
                            "matn": matn,
                            "bolim": _maydon(matn, "bolim") or "Boshqa"}
    print(f"vault: {len(yozuvlar)} model yozuvi")

    # --- Har yozuvga jadval ---
    qoshildi = bosh_qoldi = 0
    for nom, y in yozuvlar.items():
        mos = [(n, p) for n, p in par.items()
               if any(n.startswith(k) or str(p.get("model", "")).startswith(k)
                      for k in y["kodlar"])]
        if not mos:
            bosh_qoldi += 1
            continue
        yangi = jadvalni_qoy(y["matn"], jadval_yasa(mos))
        if yangi != y["matn"]:
            y["yol"].write_text(yangi, encoding="utf-8")
            qoshildi += 1
    print(f"jadval qo'shildi: {qoshildi} | ma'lumot topilmadi: {bosh_qoldi}")

    # BO'LIMLAR INDEKSI YASALMAYDI.
    #
    # JONLI E'TIROZ (2026-08-28): men «00 — Bo'limlar.md» qo'shgandim,
    # lekin vaultda ALLAQACHON «Katalog 2021 — indeks.md» bor edi va u
    # xuddi shu ishni qiladi — ustiga bosma katalog sahifa raqamlari
    # bilan. Ikkita bir xil indeks vaultni chalkashtirardi.

    # --- Yo'q oilalar ---
    kodlar = {k for y in yozuvlar.values() for k in y["kodlar"]}
    oilalar = sorted({str(p.get("model") or n).strip() for n, p in par.items()})
    # Guruhlash TO'LIQ oila nomi bo'yicha, prefiks bo'yicha EMAS.
    #
    # JONLI XATO (2026-08-28): prefiks bilan guruhlaganda «ВЦ 9-55»
    # yo'qligi «ВЦ oilasi yo'q» degan yozuv yasadi — vaultda esa
    # «ВЦ 4-75» bemalol turardi. Noto'g'ri yozuv yo'qlikdan yomonroq.
    kodlar_raqamsiz = {raqamsiz(k) for k in kodlar if raqamsiz(k)}
    yoq = defaultdict(list)
    for oila in oilalar:
        if any(oila.startswith(k) or k.startswith(oila) for k in kodlar):
            continue
        # Raqamsiz shakl ham solishtiriladi (`raqamsiz`).
        if raqamsiz(oila) in kodlar_raqamsiz:
            continue
        # OILA bo'yicha guruhlanadi, o'lcham bo'yicha emas.
        #
        # «ВНР-4», «ВНР-5», «ВНР-10» — bitta oila, uchta o'lcham.
        # Har biriga alohida yozuv ochilsa vault bo'lak-bo'lak bo'lib
        # ketardi va bittasini ochgan odam qolganini ko'rmasdi.
        yoq[raqamsiz(oila) or oila].append(oila)

    for prefiks, ro in sorted(yoq.items()):
        mos = [(n, p) for n, p in par.items()
               if any(str(p.get("model") or n).strip() == o for o in ro)]
        if not mos:
            continue
        xavfsiz = prefiks.replace("/", "-")
        fayl = VAULT / f"{xavfsiz} — bosma katalogda yo'q.md"
        matn = "\n".join([
            "---",
            "tags: [mahsulot, katalog, backenddan]",
            f"bolim: Aniqlanmagan",
            f"model_kodi: {prefiks}",
            "manba: Climavent backend (bosma katalogda yozuv yo'q)",
            "---",
            "",
            f"# {prefiks}",
            "",
            "> [!warning] Bosma katalogda yo'q",
            "> Bu oila backendda bor, lekin JIHOZVENT 2021 katalogidan",
            "> ko'chirilgan yozuvlar orasida topilmadi. Tavsif matni yo'q —",
            "> faqat texnik ko'rsatkichlar. Muhandis tekshirsin: oila",
            "> haqiqatan ishlab chiqariladimi yoki bazada eskirgan yozuvmi.",
            "",
            f"[[{BOLIMLAR_FAYLI[:-3]}|← Bo'limlarga]]",
            "",
            "---",
            "",
            jadval_yasa(mos),
            "",
        ])
        fayl.write_text(matn, encoding="utf-8")
        print(f"   yangi yozuv: {fayl.name} ({len(mos)} o'lcham)")


if __name__ == "__main__":
    asyncio.run(main())

"""Bosma katalog (PDF) va backend bazasini solishtiradi.

FAQAT YO'QLARINI ko'rsatadi — borlari sanalmaydi.

MANBALAR
--------
PDF tomoni: `Jihozvent-Vault/02-Mahsulotlar/Katalog-2021/` yozuvlari.
Ular JIHOZVENT 2021 katalogidan (260 sahifa) ko'chirilgan va har
birida `model_kodi` hamda bosma sahifa matni bor.

Baza tomoni: Climavent backendi — `mahsulotlar()` (nom va o'lchamlar)
va `texnik_parametrlar()` (sarf, bosim).

IKKI DARAJADA SOLISHTIRILADI
----------------------------
1. OILA — «ВЦ 4-75» butunlay bormi?
2. O'LCHAM — oila bor, lekin «ВЦ 4-75-8» o'lchami bormi?

Ikkinchisi muhimroq: oila bor deb qo'yib, o'lchamlari yo'qligi
sababli KP narxsiz chiqadi.

    .venv\\Scripts\\python -m skriptlar.pdf_baza_solishtir
"""

from __future__ import annotations

import asyncio
import pathlib
import re
from collections import defaultdict

from integrations.climavent_client import ClimaventKlient

VAULT = pathlib.Path(r"D:\AGENTS\Jihozvent-Vault\02-Mahsulotlar\Katalog-2021")
CHIQISH = pathlib.Path("chiqish/pdf_baza_farqi.md")

# Vault yozuvidagi bosma matndan model belgisini ajratish.
#
# Belgini OILA KODI bilan bog'lab qidiramiz — umumiy regex «УХЛ»
# (iqlim ijrosi) va «ГОСТ» kabi narsalarni ham model deb olardi.
def _olchamlar(matn: str, kod: str) -> set[str]:
    """Matndan shu oilaga tegishli to'liq belgilar."""
    if not kod:
        return set()
    namuna = re.compile(
        re.escape(kod) + r"[\s\-№]*(\d[\d,\.\-/xх×]*)", re.IGNORECASE)
    natija = set()
    for mos in namuna.finditer(matn):
        olcham = mos.group(1).strip(" -,.")
        # Bir belgili «raqam» odatda jadval ustuni, o'lcham emas.
        if len(olcham) >= 2 or "," in olcham:
            natija.add(olcham)
    return natija


# Tavsifiy so'zlar — model kodi EMAS. «Чиллер JV» dagi kod «JV».
TAVSIF_SOZLARI = (
    "чиллер", "клапан", "ккб", "циклоны", "циклон", "вентилятор",
    "решетка", "агрегат", "установка", "фильтр", "шумоглушитель",
)


def _kod_tozala(xom: str) -> str:
    """«Чиллер JV» -> «JV», «КПУ (НО» -> «КПУ»."""
    toza = xom.strip()
    # Qavs ichidagi izoh kesiladi.
    toza = re.split(r"[(\[]", toza)[0].strip()
    # Tavsifiy so'z olib tashlanadi.
    for soz in TAVSIF_SOZLARI:
        namuna = re.compile(rf"^{soz}\s+", re.IGNORECASE)
        toza = namuna.sub("", toza).strip()
    return toza


def _kodmi(nom: str) -> bool:
    """Bu haqiqiy model kodimi?

    Model kodi — BOSH HARFLAR va raqamlardan iborat («ВЦ 4-75»,
    «РКВ», «JV»). «lyuk», «montaj burchagi», «НЗ» kabi bo'laklar
    ko'p kodli sarlavhadan tushib qolgan — ular oila emas.
    """
    toza = (nom or "").strip()
    if len(toza) < 2:
        return False
    # Kichik harf bo'lsa — bu izoh so'zi, kod emas.
    harflar = [c for c in toza if c.isalpha()]
    if not harflar or any(c.islower() for c in harflar):
        return False
    # Kamida ikkita bosh harf bo'lsin.
    return len(harflar) >= 2


def _kodlar(matn: str) -> list[str]:
    """Yozuvdagi model kodlari — tozalangan va tekshirilgan."""
    mos = re.search(r"^model_kodi:\s*(.+)$", matn, re.M)
    if not mos:
        return []
    # Qavs ichi BUTUN qatordan olib tashlanadi.
    #
    # «КПУ (НО, НЗ, ДД)» — bitta oila, uchta ish holati. Qavsni
    # bo'lakma-bo'lak kesganda «НЗ» va «ДД)» alohida oila bo'lib
    # chiqib, «bazada yo'q» ro'yxatiga tushib qolardi.
    xom = re.sub(r"\([^)]*\)?", " ", mos.group(1))
    # «ДН, ВДН» va «ЦН-11 / ЦН-15 / 4БЦШ» — ikkalasi ham ajratiladi.
    bolaklar = re.split(r"[,/]|\sva\s", xom)
    natija = []
    for b in bolaklar:
        kod = _kod_tozala(b)
        if _kodmi(kod) and kod not in natija:
            natija.append(kod)
    return natija


def _raqamsiz(nom: str) -> str:
    toza = re.sub(r"[\d,\.]+", "", nom or "")
    toza = re.sub(r"/+", "", toza)
    return re.sub(r"[-\s]{2,}", "-", toza).strip(" -№").upper()


async def main() -> None:
    api = ClimaventKlient()
    katalog = await api.mahsulotlar()
    parametrlar = await api.texnik_parametrlar()

    # --- Baza tomoni ---
    baza_modellar: set[str] = set()
    for mahsulot in katalog:
        for xususiyat in mahsulot.get("characters") or []:
            if not isinstance(xususiyat, dict):
                continue
            baza_modellar.add(str(xususiyat.get("title") or "").strip())
            for ichki in xususiyat.get("insides") or []:
                if isinstance(ichki, dict):
                    baza_modellar.add(str(ichki.get("in_model_name") or "").strip())
    baza_modellar |= set(parametrlar)
    baza_modellar.discard("")
    baza_raqamsiz = {_raqamsiz(m) for m in baza_modellar}

    # --- PDF tomoni ---
    pdf_oilalar: dict[str, dict] = {}
    for fayl in sorted(VAULT.glob("*.md")):
        if fayl.name.startswith("Katalog 2021") or "bosma katalogda yo'q" in fayl.name:
            continue
        matn = fayl.read_text(encoding="utf-8", errors="replace")
        for kod in _kodlar(matn):
            pdf_oilalar[kod] = {
                "fayl": fayl.name,
                "sahifa": (re.search(r"(\d+)-sahifa", matn) or [None, "?"])[1],
                "olchamlar": _olchamlar(matn, kod),
            }

    # --- 1) Bazada YO'Q oilalar ---
    #
    # IKKIGA AJRATILADI. «Yo'q» degan xulosa nomlanish farqi tufayli
    # NOTO'G'RI bo'lishi mumkin: `ПД` bazada «ПОДДОН ПД» deb turibdi,
    # `ВМ` esa «СВМ» — boshi bilan solishtirganda ikkalasi ham
    # «yo'q» bo'lib chiqardi.
    yoq_oila = []           # umuman izi yo'q
    boshqa_nomda = []       # izi bor, nomi boshqacha — TEKSHIRISH kerak
    for kod, malumot in sorted(pdf_oilalar.items()):
        katta = kod.upper()
        if any(m.upper().startswith(katta) for m in baza_modellar):
            continue
        if _raqamsiz(kod) in baza_raqamsiz:
            continue
        # Ichkarisida uchraydimi? («ПОДДОН ПД», «СВМ»)
        oxshash = sorted({m for m in baza_modellar if katta in m.upper()})
        if oxshash:
            boshqa_nomda.append((kod, malumot, oxshash[:4]))
        else:
            yoq_oila.append((kod, malumot))

    # --- 2) Oila bor, O'LCHAM yo'q ---
    yoq_olcham: dict[str, list[str]] = {}
    for kod, malumot in sorted(pdf_oilalar.items()):
        if (kod, malumot) in yoq_oila:
            continue
        if any(k == kod for k, _, _ in boshqa_nomda):
            continue
        yetishmagan = []
        for olcham in sorted(malumot["olchamlar"]):
            toliq = f"{kod}-{olcham}"
            qisqa = f"{kod} {olcham}"
            bormi = any(
                m.upper().replace(" ", "").replace("-", "").startswith(
                    toliq.upper().replace(" ", "").replace("-", ""))
                or m.upper().replace(" ", "").replace("-", "").startswith(
                    qisqa.upper().replace(" ", "").replace("-", ""))
                for m in baza_modellar
            )
            if not bormi:
                yetishmagan.append(olcham)
        if yetishmagan:
            yoq_olcham[kod] = yetishmagan

    # --- 3) Bazada bor, PDF da yo'q ---
    pdf_raqamsiz = {_raqamsiz(k) for k in pdf_oilalar}
    baza_oilalar = sorted({str(p.get("model") or n).strip()
                           for n, p in parametrlar.items()})
    yoq_pdfda = defaultdict(list)
    for oila in baza_oilalar:
        if any(oila.upper().startswith(k.upper()) or k.upper().startswith(oila.upper())
               for k in pdf_oilalar):
            continue
        if _raqamsiz(oila) in pdf_raqamsiz:
            continue
        yoq_pdfda[_raqamsiz(oila) or oila].append(oila)

    # --- Hisobot ---
    q: list[str] = [
        "# Bosma katalog ↔ baza: YETISHMAYOTGANLAR",
        "",
        "> [!info] Manba",
        f"> PDF: JIHOZVENT 2021 — {len(pdf_oilalar)} ta oila (vault yozuvlaridan).",
        f"> Baza: Climavent backend — {len(baza_modellar)} ta model belgisi.",
        "> Faqat YETISHMAYOTGANLAR sanalgan; borlari ko'rsatilmagan.",
        "",
        "---",
        "",
        f"## 1. Katalogda bor, BAZADA YO'Q — {len(yoq_oila)} ta oila",
        "",
    ]
    if yoq_oila:
        q += ["| Oila | Bosma sahifa | Yozuv |", "|---|---|---|"]
        for kod, m in yoq_oila:
            q.append(f"| `{kod}` | {m['sahifa']} | {m['fayl'][:-3]} |")
    else:
        q.append("_Yo'q — katalogdagi hamma oila bazada bor._")

    q += ["", f"## 1b. Bazada BOSHQA NOM bilan bo'lishi mumkin — "
              f"{len(boshqa_nomda)} ta", "",
          "_Kod baza nomlari ICHIDA uchradi. Bir xil mahsulotmi yoki "
          "boshqami — tekshirish kerak._", ""]
    if boshqa_nomda:
        q += ["| Katalogda | Bazada uchragan | Sahifa |", "|---|---|---|"]
        for kod, m, oxshash in boshqa_nomda:
            q.append(f"| `{kod}` | {', '.join(f'`{x}`' for x in oxshash)} "
                     f"| {m['sahifa']} |")
    else:
        q.append("_Yo'q._")

    q += ["", f"## 2. Oila bor, lekin O'LCHAMI yo'q — {len(yoq_olcham)} ta oilada", ""]
    if yoq_olcham:
        q += ["| Oila | Bazada yo'q o'lchamlar |", "|---|---|"]
        for kod, olchamlar in sorted(yoq_olcham.items(),
                                     key=lambda x: -len(x[1])):
            royxat = ", ".join(f"`{o}`" for o in olchamlar[:14])
            if len(olchamlar) > 14:
                royxat += f" …(+{len(olchamlar) - 14})"
            q.append(f"| `{kod}` | {royxat} |")
    else:
        q.append("_Yo'q._")

    q += ["", f"## 3. Bazada bor, BOSMA KATALOGDA YO'Q — {len(yoq_pdfda)} ta oila", ""]
    if yoq_pdfda:
        q += ["| Oila | Modellar |", "|---|---|"]
        for oila, modellar in sorted(yoq_pdfda.items()):
            q.append(f"| `{oila}` | {', '.join(f'`{m}`' for m in modellar[:8])}"
                     + (f" …(+{len(modellar) - 8})" if len(modellar) > 8 else "") + " |")
    else:
        q.append("_Yo'q._")

    CHIQISH.parent.mkdir(parents=True, exist_ok=True)
    CHIQISH.write_text("\n".join(q), encoding="utf-8")

    print(f"PDF oilalari      : {len(pdf_oilalar)}")
    print(f"Baza model belgisi: {len(baza_modellar)}")
    print()
    print(f"1. Bazada YO'Q oila          : {len(yoq_oila)}")
    print(f"1b. Boshqa nom bilan bo'lishi mumkin: {len(boshqa_nomda)}")
    print(f"2. O'lchami yetishmagan oila : {len(yoq_olcham)}")
    print(f"3. Bosma katalogda YO'Q oila : {len(yoq_pdfda)}")
    print()
    print("hisobot:", CHIQISH)


if __name__ == "__main__":
    asyncio.run(main())

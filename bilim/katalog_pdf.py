"""Bosma katalog (JIHOZVENT-2021, 260 sahifa) -> Obsidian yozuvlari.

NEGA KERAK
----------
Backend katalogida model NOMI va kategoriyasi bor, lekin bosma katalogdagi
TO'LIQ jadvallar yo'q: o'lchamlar, massa, quvvat, ishchi harorat, shartli
belgi (masalan "ГТП 300x200-500x400-980" nima degani), montaj talablari.

Sardor mahsulot tanlaganda va Temur KP yozganda aynan shu ma'lumot kerak
bo'ladi. U Obsidianda tursa — bilim bazasi (`bilim/`) uni indekslaydi va
agentlar qidiruv orqali topadi.

QANDAY ISHLAYDI
---------------
PDF matni sahifama-sahifa ajratiladi, har sahifadagi TAKRORLANUVCHI
navigatsiya sarlavhasi olib tashlanadi, so'ng mundarijaga qarab uskuna
OILALARIGA bo'linadi. Har oila — alohida yozuv.

DIQQAT: bu skript matnni QAYTA YOZMAYDI, faqat ko'chiradi va tartiblaydi.
Model o'ylab topgan raqam katalogga tushib qolmasligi kerak.

Ishga tushirish:
    .venv\\Scripts\\python -m bilim.katalog_pdf "<katalog.pdf>"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import sozlama

# Obsidian ichida qayerga yoziladi. `02-Mahsulotlar` -> `product` bo'limi
# (`bilim/indeks.py: VAULT_XARITASI`), ya'ni Sardor va Temur ko'radi.
PAPKA = "02-Mahsulotlar/Katalog-2021"

# PDF sahifa raqami = bosma sahifa raqami + SILJISH.
# Muqova va mundarija sababli ular bir xil emas: mundarijada "ГТП 234"
# deyilgan sahifa PDF da 236-o'rinda turadi.
SILJISH = 2

# Har sahifaning tepasida takrorlanadigan bo'lim navigatsiyasi. U 260 marta
# takrorlanadi va indeksga sof shovqin qo'shadi.
NAV_SOZLARI = frozenset({
    "кондиционер", "кондиционеры", "оборудование", "холодильное",
    "отопительное", "теплообменное", "канальное", "вентиляторы",
    "аспирационное", "клапаны", "вентиляционные", "решетки",
    "шумоглушители", "изделия", "фильтры", "комплектующие",
})


@dataclass(frozen=True)
class Oila:
    """Katalogdagi bitta uskuna oilasi."""

    kod: str          # "ВЦ 4-75"
    izoh: str         # "markazdan qochma ventilyator"
    bosma: int        # mundarijadagi sahifa raqami


@dataclass(frozen=True)
class Bolim:
    nomi: str
    oilalar: tuple[Oila, ...]


# Mundarija (3-7 sahifalar) KODDA yozilgan.
#
# Uni PDF dan avtomatik o'qib bo'lmadi: CorelDRAW eksporti ustunlarni
# aralashtirib yuboradi ("УЭО 42" bo'lim oxirida emas, o'rtasida chiqadi).
# Noto'g'ri o'qilgan mundarija butun bo'linishni buzadi, shuning uchun u
# qo'lda tekshirilgan holda shu yerda turadi.
MUNDARIJA: tuple[Bolim, ...] = (
    Bolim("Konditsionerlar", (
        Oila("КЦКП", "karkas-panelli markaziy konditsioner", 15),
        Oila("IXCHAM", "ixcham havo tayyorlash qurilmasi", 30),
    )),
    Bolim("Sovutish uskunalari", (
        Oila("Чиллер JV", "modulli chiller", 33),
        Oila("ККБ JVK", "kompressor-kondensator bloki", 34),
        Oila("Градирня ВГ", "sovutish minorasi", 35),
    )),
    Bolim("Isitish uskunalari", (
        Oila("АО2", "havo isitish agregati", 37),
        Oila("АВО-44", "issiqxona uchun isitish agregati", 38),
        Oila("АО", "havo isitish agregati", 39),
        Oila("АОЭ", "elektr havo isitish agregati", 41),
        Oila("УЭО", "elektr isitish qurilmasi", 42),
    )),
    Bolim("Issiqlik almashtirgichlar", (
        Oila("ВНВ va ВОВ", "suvli issiqlik almashtirgich", 44),
    )),
    Bolim("Kanal uskunalari — dumaloq", (
        Oila("ВК-С", "dumaloq kanal ventilyatori", 47),
        Oila("ВК-П", "dumaloq kanal ventilyatori", 48),
        Oila("КВН", "kanalli suvli isitgich", 49),
        Oila("КНЭ", "kanalli elektr isitgich", 51),
        Oila("ФКГ", "kanalli filtr", 53),
        Oila("КГТ", "kanalli shovqin bostirgich", 54),
        Oila("ДКСк", "dumaloq drossel klapan", 56),
        Oila("Клапан RSK", "teskari klapan", 57),
        Oila("ВКП", "kanal ventilyatori", 59),
        Oila("ВКПН", "kanal ventilyatori", 61),
        Oila("ВКПП", "kanal ventilyatori", 62),
    )),
    Bolim("Kanal uskunalari — to'rtburchak", (
        Oila("ПВН", "to'rtburchak suvli isitgich", 68),
        Oila("ПНЭ", "to'rtburchak elektr isitgich", 72),
        Oila("ПВО", "to'rtburchak sovutgich", 74),
        Oila("ПВФ", "freonli sovutgich", 76),
        Oila("КБС", "aralashtirish kamerasi", 78),
        Oila("ФПГ", "to'rtburchak filtr", 80),
        Oila("ФПК", "to'rtburchak filtr", 81),
        Oila("КГП", "plastinali shovqin bostirgich", 82),
        Oila("ДКСп", "to'rtburchak drossel klapan", 84),
    )),
    Bolim("Kanal uskunalari — kvadrat", (
        Oila("ВКК", "kvadrat kanal ventilyatori", 87),
        Oila("ВКК-Ш", "shovqinsiz kvadrat kanal ventilyatori", 88),
        Oila("ВКК-КХ", "issiqlikka chidamli kanal ventilyatori", 89),
    )),
    Bolim("Markazdan qochma ventilyatorlar", (
        Oila("ВЦ 4-75", "markazdan qochma ventilyator", 94),
        Oila("ВЦ 4-75 ДУ", "tutun chiqarish ventilyatori", 95),
        Oila("ВЦ 4-75 (исп.5)", "markazdan qochma ventilyator, 5-bajarilish", 100),
        Oila("ВЦ 14-46", "markazdan qochma ventilyator", 103),
        Oila("ВЦ 14-46 ДУ", "tutun chiqarish ventilyatori", 104),
        Oila("ВР 6-28", "markazdan qochma ventilyator", 109),
        Oila("ВР 6-28 (исп.5)", "markazdan qochma ventilyator, 5-bajarilish", 113),
        Oila("ВР 12-26", "yuqori bosimli ventilyator", 116),
        Oila("ВР 6-45 (исп.5)", "markazdan qochma ventilyator, 5-bajarilish", 119),
        Oila("ВР", "markazdan qochma ventilyator", 122),
        Oila("ВНР-ДУ", "devorga o'rnatiladigan tutun ventilyatori", 123),
    )),
    Bolim("Tomga o'rnatiladigan ventilyatorlar", (
        Oila("ВКР", "tom ventilyatori", 129),
        Oila("ВКР-ДУ", "tom tutun ventilyatori", 130),
        Oila("ВКРВ-ДУ", "tom tutun ventilyatori, vertikal", 134),
        Oila("ВКОП", "tom ventilyatori", 136),
    )),
    Bolim("O'qli ventilyatorlar", (
        Oila("ВО 6-300", "o'qli ventilyator", 139),
        Oila("ВОТ", "o'qli ventilyator", 154),
        Oila("ВОД-ДУ", "o'qli tutun ventilyatori", 156),
    )),
    Bolim("Maxsus ventilyatorlar", (
        Oila("СВМ", "maxsus ventilyator", 161),
        Oila("ДПЭ", "maxsus ventilyator", 162),
        Oila("В-2", "maxsus ventilyator", 163),
        Oila("ВДПЭ-52", "maxsus ventilyator", 164),
        Oila("В-3", "maxsus ventilyator", 165),
        Oila("ВДПЭ-4", "maxsus ventilyator", 166),
        Oila("ВДПБ-5", "maxsus ventilyator", 167),
    )),
    Bolim("Tortishma mashinalar", (
        Oila("Д, ВД", "tortishma tutun so'rgich va puflagich", 169),
        Oila("ДН, ВДН", "tortishma mashina, past bosimli", 175),
        Oila("ВМ", "shaxta ventilyatori", 193),
    )),
    Bolim("Aspiratsiya uskunalari", (
        Oila("ЗИЛ", "chang yig'uvchi agregat", 197),
        Oila("Циклоны ЦН-11 / ЦН-15 / ЦН-24 / 4БЦШ", "siklonlar", 198),
        Oila("СИОТ 5.907-2", "chang tozalagich", 201),
    )),
    Bolim("Yong'inga qarshi klapanlar", (
        Oila("КПУ (НО, НЗ, ДД)", "yong'inga qarshi klapan", 206),
        Oila("КПД", "yong'inga qarshi klapan", 207),
        Oila("КОГ", "tutun chiqarish klapani", 209),
        Oila("АВКв", "havo klapani", 211),
        Oila("КВУ", "havo klapani", 212),
        Oila("КОП", "tutun chiqarish klapani", 213),
        Oila("КО", "tutun chiqarish klapani", 214),
        Oila("КОПв", "tutun chiqarish klapani", 215),
        Oila("КОв", "tutun chiqarish klapani", 216),
        Oila("КИД", "klapan", 217),
        Oila("КС", "klapan", 218),
    )),
    Bolim("Umumsanoat klapanlari", (
        Oila("КЛ", "umumsanoat klapani", 219),
    )),
    Bolim("Ventilyatsiya panjaralari", (
        Oila("DVS", "havo taqsimlagich", 221),
        Oila("ДФА", "diffuzor", 222),
        Oila("РВ-1", "ventilyatsiya panjarasi", 223),
        Oila("РВР-1", "rostlanadigan panjara", 224),
        Oila("РВР-2", "rostlanadigan panjara", 225),
        Oila("4РВП", "panjara", 226),
        Oila("РВН", "panjara", 227),
        Oila("РВИ", "panjara", 228),
        Oila("РЩ", "tirqishli panjara", 229),
        Oila("ДФН", "diffuzor", 231),
    )),
    Bolim("Shovqin bostirgichlar", (
        Oila("ГТК", "dumaloq shovqin bostirgich", 233),
        Oila("ГТП", "to'rtburchak shovqin bostirgich", 234),
        Oila("ГП", "plastinali shovqin bostirgich", 235),
    )),
    Bolim("Ventilyatsiya buyumlari", (
        Oila("ДТ", "ventilyatsiya buyumi", 237),
        Oila("ДР", "ventilyatsiya buyumi", 238),
        Oila("НРВ", "ventilyatsiya buyumi", 240),
        Oila("УП", "ventilyatsiya buyumi", 241),
        Oila("КСД", "statik bosim kamerasi", 243),
    )),
    Bolim("Filtrlar", (
        Oila("ФЯК", "yacheykali filtr", 246),
        Oila("ФЯГ", "yacheykali filtr", 248),
        Oila("ФЯП", "yacheykali filtr", 250),
    )),
    Bolim("Butlovchi qismlar", (
        Oila("Виброизоляторы ДО, montaj burchagi, lyuk", "butlovchi qismlar", 253),
        Oila("Egiluvchan qo'shimcha va butlovchilar", "butlovchi qismlar", 254),
        Oila("Solenoid klapan, ШСАУ, ТРВ, chastota o'zgartirgich", "avtomatika", 255),
        Oila("ЩУВ, ПД, ko'rish oynasi", "avtomatika", 256),
    )),
)

# Fayl nomida ishlatib bo'lmaydigan belgilar (Windows).
YOMON_BELGI = re.compile(r'[<>:"/\\|?*]')


# Sahifa raqami sarlavhadan OLDIN ham, KEYIN ham kelishi mumkin, shuning
# uchun ikkita qator tekshiriladi.
#
# Chuqurroq qidirish XAVFLI: jadval ichida ham yolg'iz raqam turadi
# ("Масса, кг" ustuni ostidagi 94) va u sahifa raqami bilan bir xil
# bo'lsa, katalogdan HAQIQIY qiymat o'chib ketardi.
RAQAM_QIDIRUV_CHUQURLIGI = 2

# Navigatsiya bloki deb hisoblash uchun kamida shuncha qator kerak.
#
# Yolg'iz "Вентиляторы" — bo'lim sarlavhasi bo'lishi mumkin va uni
# o'chirish matnni buzadi. Navigatsiya esa doim uzun blok bo'lib keladi.
MIN_NAV_QATOR = 3

# ...lekin ba'zi sahifalarda butun navigatsiya BITTA qatorga sig'ib
# ketgan (PDF eksporti qatorlarni birlashtirgan). Unda qator soni emas,
# SO'Z soni hal qiladi: 12 ta bo'lim nomi bitta qatorda tursa, bu aniq
# navigatsiya, sarlavha emas.
MIN_NAV_SOZ = 5


def _nav_qatormi(qator: str) -> bool:
    """Qator faqat bo'lim nomlaridan iboratmi?

    PDF eksporti ba'zan so'zlarni YOPISHTIRIB yuboradi:
    "ШумоглушителиВентиляционные". Bunday token lug'atda topilmaydi,
    shuning uchun so'zlarni birma-bir tekshirish yetmaydi — qatordan
    barcha bo'lim nomlari olib tashlanadi va HARF qolmasa, bu navigatsiya.
    """
    sozlar = re.findall(r"[^\W\d_]+", qator.lower(), re.UNICODE)
    if not sozlar:
        return False
    if all(s in NAV_SOZLARI for s in sozlar):
        return True

    qoldiq = qator.lower()
    for soz in sorted(NAV_SOZLARI, key=len, reverse=True):
        qoldiq = qoldiq.replace(soz, " ")
    return not re.search(r"[^\W\d_]", qoldiq, re.UNICODE)


def nav_tozala(matn: str, bosma_raqam: int) -> str:
    """Takrorlanuvchi bo'lim navigatsiyasini olib tashlaydi.

    Navigatsiya — bo'lim nomlaridan iborat 6-10 qator. U har sahifada bir
    xil, ya'ni indeksda 260 marta takrorlanadi va qidiruvni buzadi.

    IKKI NOZIK JOY:

    1. Navigatsiya ichida BO'SH qator uchraydi (PDF eksporti shunday
       chiqargan). Uni "navigatsiya tugadi" deb hisoblasak, oxirgi bo'lim
       nomi ("Комплектующие") matn ichida qolib ketadi.

    2. Navigatsiya har doim sahifa BOSHIDA turmaydi. ВР 12-26 sahifasida
       u sarlavhadan KEYIN chiqadi. Shuning uchun butun sahifa bo'ylab
       qidiriladi.

    Yolg'iz turgan bitta "Вентиляторы" o'chirilmaydi — u bo'lim sarlavhasi
    bo'lishi mumkin. Faqat KETMA-KET kelgan navigatsiya bloki olinadi.
    """
    qatorlar = matn.splitlines()
    saqlanadi = [True] * len(qatorlar)

    i = 0
    while i < len(qatorlar):
        if not _nav_qatormi(qatorlar[i]):
            i += 1
            continue
        # Blok chegarasi: navigatsiya qatorlari + ular orasidagi bo'shliqlar.
        oxiri, nav_soni, soz_soni = i, 0, 0
        while oxiri < len(qatorlar) and (
            _nav_qatormi(qatorlar[oxiri]) or not qatorlar[oxiri].strip()
        ):
            if _nav_qatormi(qatorlar[oxiri]):
                nav_soni += 1
                soz_soni += len(
                    re.findall(r"[^\W\d_]+", qatorlar[oxiri], re.UNICODE)
                )
            oxiri += 1
        if nav_soni >= MIN_NAV_QATOR or soz_soni >= MIN_NAV_SOZ:
            for k in range(i, oxiri):
                saqlanadi[k] = False
        i = max(oxiri, i + 1)

    qolgani = [q for q, saqla in zip(qatorlar, saqlanadi) if saqla]
    # Bosma sahifa raqami — yolg'iz turgan qator. U sarlavhadan oldin ham,
    # keyin ham kelishi mumkin, shuning uchun bir necha qator tekshiriladi.
    for j, qator in enumerate(qolgani[:RAQAM_QIDIRUV_CHUQURLIGI]):
        if qator.strip() == str(bosma_raqam):
            del qolgani[j]
            break
    return "\n".join(qolgani).strip()


def _fayl_nomi(bolim: str, oila: Oila) -> str:
    nomi = f"{oila.kod} — {oila.izoh}"
    return YOMON_BELGI.sub("-", nomi).strip() + ".md"


def _oilalar_tartibda() -> list[tuple[Bolim, Oila]]:
    juftlar = [(b, o) for b in MUNDARIJA for o in b.oilalar]
    return sorted(juftlar, key=lambda x: x[1].bosma)


def yozuvlar_yasa(sahifalar: list[str], chiqish: Path) -> list[Path]:
    """Sahifa matnlaridan oila yozuvlarini yozadi. `sahifalar` — 0 dan.

    Har oila o'z boshlanish sahifasidan KEYINGI oilaning boshigacha
    bo'lgan sahifalarni oladi.
    """
    chiqish.mkdir(parents=True, exist_ok=True)
    tartib = _oilalar_tartibda()
    yozilgan: list[Path] = []

    for tartib_raqam, (bolim, oila) in enumerate(tartib):
        boshi = oila.bosma + SILJISH
        keyingi = tartib[tartib_raqam + 1][1] if tartib_raqam + 1 < len(tartib) else None
        oxiri = (keyingi.bosma + SILJISH) if keyingi else len(sahifalar) + 1

        bolaklar: list[str] = []
        for pdf_raqam in range(boshi, min(oxiri, len(sahifalar) + 1)):
            xom = sahifalar[pdf_raqam - 1]
            tanasi = nav_tozala(xom, pdf_raqam - SILJISH)
            if tanasi:
                bolaklar.append(
                    f"### Bosma sahifa {pdf_raqam - SILJISH}\n\n{tanasi}"
                )
        if not bolaklar:
            continue

        fayl = chiqish / _fayl_nomi(bolim.nomi, oila)
        fayl.write_text(
            _yozuv_matni(bolim, oila, boshi, oxiri - 1, bolaklar), encoding="utf-8"
        )
        yozilgan.append(fayl)

    yozilgan.append(_indeks_yoz(chiqish, tartib))
    return yozilgan


def _yozuv_matni(
    bolim: Bolim, oila: Oila, boshi: int, oxiri: int, bolaklar: list[str]
) -> str:
    sahifa_izohi = (
        f"{oila.bosma}" if boshi == oxiri else f"{oila.bosma}–{oxiri - SILJISH}"
    )
    return "\n".join([
        "---",
        "tags: [mahsulot, katalog, texnik-jadval, bosma-katalog]",
        f"bolim: {bolim.nomi}",
        f"model_kodi: {oila.kod}",
        f"manba: JIHOZVENT katalogi 2021, {sahifa_izohi}-sahifa",
        "---",
        "",
        f"# {oila.kod} — {oila.izoh}",
        "",
        "> [!info] Manba",
        f"> Bosma katalog **JIHOZVENT 2021**, {sahifa_izohi}-sahifa.",
        f"> Bo'lim: {bolim.nomi}. Matn PDF dan o'zgartirilmasdan ko'chirilgan —",
        "> raqamlar katalogdagidek. Shubha bo'lsa asl PDF bilan solishtiring.",
        "",
        "[[Katalog 2021 — indeks|← Katalog indeksiga]]",
        "",
        "---",
        "",
        *[f"{b}\n" for b in bolaklar],
    ])


def _indeks_yoz(chiqish: Path, tartib: list[tuple[Bolim, Oila]]) -> Path:
    qatorlar = [
        "---",
        "tags: [mahsulot, katalog, indeks, bosma-katalog]",
        f"oilalar: {len(tartib)}",
        "---",
        "",
        "# Katalog 2021 — indeks",
        "",
        "> [!info] Bir qatorda",
        f"> JIHOZVENT bosma katalogining (2021, 260 sahifa) **{len(tartib)} ta**",
        "> uskuna oilasi. Har yozuvda katalogdagi TO'LIQ texnik jadval bor:",
        "> o'lchamlar, massa, quvvat, shartli belgi.",
        "",
        "Backend katalogida model nomi va kategoriyasi bor, bu yerda esa —",
        "o'lchamlar va jadvallar. Ikkalasi bir-birini to'ldiradi.",
        "",
    ]
    oxirgi = ""
    for bolim, oila in sorted(tartib, key=lambda x: (x[0].nomi, x[1].bosma)):
        if bolim.nomi != oxirgi:
            qatorlar += ["", f"## {bolim.nomi}", ""]
            oxirgi = bolim.nomi
        nom = _fayl_nomi(bolim.nomi, oila).removesuffix(".md")
        qatorlar.append(f"- [[{nom}|{oila.kod}]] — {oila.izoh} (s. {oila.bosma})")

    qatorlar += [
        "",
        "---",
        "",
        f"*Bosma katalogdan avtomatik ko'chirilgan: {date.today().isoformat()}.*",
        "*Yangilash: `python -m bilim.katalog_pdf <katalog.pdf>`*",
    ]
    fayl = chiqish / "Katalog 2021 — indeks.md"
    fayl.write_text("\n".join(qatorlar), encoding="utf-8")
    return fayl


def pdfdan_oqi(yol: Path) -> list[str]:
    from pypdf import PdfReader

    r = PdfReader(str(yol))
    matnlar: list[str] = []
    for sahifa in r.pages:
        try:
            matnlar.append((sahifa.extract_text() or "").strip())
        except Exception:
            matnlar.append("")
    return matnlar


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    manba = Path(argv[1])
    if not manba.is_file():
        print(f"Fayl topilmadi: {manba}")
        return 1

    vault = sozlama().vault_papkasi
    if vault is None:
        print("Obsidian vault topilmadi (VAULT_YOLI).")
        return 1

    print(f"O'qilmoqda: {manba.name}")
    sahifalar = pdfdan_oqi(manba)
    print(f"  {len(sahifalar)} sahifa")

    chiqish = vault / PAPKA
    yozilgan = yozuvlar_yasa(sahifalar, chiqish)
    print(f"\n{len(yozilgan)} ta yozuv: {chiqish}")
    jami = sum(f.stat().st_size for f in yozilgan)
    print(f"Jami hajm: {jami / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

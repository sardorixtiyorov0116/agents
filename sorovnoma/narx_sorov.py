"""«Katalogda ko'rdim — narxi qancha?» savoliga javob.

NEGA ALOHIDA MODUL
------------------
Mijozning eng ko'p beradigan savoli shu. Hozir u routerga, undan
agentga borardi: sekin, qimmat va natija baribir "menejer bog'lanadi".
Bu yerda javob KODDAN keladi — model nomi katalogda qidiriladi.

HALOL CHEGARA
-------------
Katalogda 1482 modeldan atigi 24 tasida narx bor. Ya'ni bu funksiya
ko'pincha "narx yo'q" deydi va bu YASHIRILMAYDI:

  - narx bor bo'lsa      -> aniq son aytiladi (kurs va sana bilan)
  - model bor, narx yo'q -> texnik parametrlar aytiladi + menejerga
  - model topilmadi      -> yaqin nomlar taklif qilinadi

"Taxminan shuncha" degan javob ATAYLAB yo'q: mijoz uni eslab qoladi va
keyin haqiqiy narx chiqqanda nizo bo'ladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Model nomi shu belgilardan boshlanadi. Mijoz "ВЦ 4-75-6,3 narxi
# qancha" deb yozganda undan MODEL qismini ajratib olish kerak —
# butun jumlani katalogda qidirish natija bermaydi.
MODEL_NAMUNASI = re.compile(
    r"(?<![\w'ʻʼ’])("
    # Raqamdan keyin HARF ham bo'lishi mumkin: «MF-200P», «ВКК-250С».
    # JONLI XATO (2026-10-03 QA): «P» kesilib qolar, qidiruv «MF» bo'yicha
    # ketardi va mijozga MF-150P narxi aytilardi.
    r"[А-ЯA-Z]{2,5}[\s-]?\d[\w,.\-/xх×]*"      # ВЦ 4-75-6,3 / КЦКП-40
    # Seriya harfi ALOHIDA yozilishi mumkin: «MF 200 P».
    # JONLI XATO (2026-10-06): «P» tushib qolar, narxsiz MF-200 topilardi,
    # holbuki katalogda MF-200P narxi bor. Faqat seriya harflari olinadi —
    # «ВЦ 4-75 и …» dagi «и» model qismi emas.
    r"(?:\s[PПCСSШ](?![\w'ʻʼ’]))?"
    # Oila nomida chiziqcha bilan HARF: «ВК-С 100», «Vk-s 100», «ВКК-Ш 45».
    # JONLI XATO (2026-10-03): «Вк-с 100» dan faqat «ВК» ajratilardi va
    # mijozga «АВКв 200х200» klapanining narxi aytilardi.
    r"|[А-ЯA-Z]{2,5}-[А-ЯA-Z]{1,3}[\s-]?\d[\w,.\-/xх×]*"
    r")",
    re.IGNORECASE,
)

# O'zbekcha qo'shimchalar: «MF-200Pning», «ВЦ 4-75-4ni», «РКВ-150ga».
QOSHIMCHA = re.compile(r"(?i)(?<=[\dA-ZА-Я])(ning|ni|ga|dan|da|mi|lar\w*)$")

# Model prefiksi bo'la olmaydigan oddiy so'zlar: «вентилятор на 315»
# da «на 315» model emas; «ko'rsatmalar» dagi «ko» — КО klapani emas.
ODDIY_SOZLAR = frozenset({
    "НА", "ПО", "ОТ", "ДО", "ДА", "НЕ", "ЗА", "ИЗ", "ПРИ", "ДЛЯ", "КАК", "ЧТО",
    "ВА", "БУ", "НИ", "ГА", "МИ",
    "NA", "PO", "OT", "DO", "DA", "NE", "ZA", "VA", "BU", "NI", "GA", "MI",
    "HA", "OK", "KO", "MEN", "SIZ", "BIZ", "UN", "ON", "IN", "TO", "OF", "AT",
})

# Uzun matn — narx savoli emas, unga agent javob bersin (prompt
# injection kabi uzun xabar katalog bo'lagiga «mos» kelib qolmasin).
NARX_MAKS_SOZ = 12

# Mijoz XUSUSIYAT so'rayapti — narx moduli emas, mutaxassis javob bersin.
XUSUSIYAT_SOZLARI = (
    "xususiyat", "xarakteristik", "характеристик", "parametr", "параметр",
    "texnik", "техническ", "o'lcham", "olcham", "размер", "quvvat", "мощност",
    "spesifikats", "спецификац", "pasport", "паспорт",
)

# Raqamsiz oila nomlari (РКВ, РВН, ФЯК…) KATALOGDAN olinadi.
#
# JONLI XATO (2026-08-28): ular kodda QO'LDA sanalgan edi va ro'yxatda
# «РКВ» yo'q edi. Mijoz «РКВ narxi qancha» deb so'raganda model
# ajratilmadi, savol LLM yo'liga tushdi — 10-30 soniya kutish va
# oxirida «topilmadi», holbuki katalogda РКВ-150 bor va narxi ham bor.
#
# Endi ro'yxat katalogdan yig'iladi: yangi oila qo'shilsa kodga
# tegilmaydi.
OILA_NAMUNASI = re.compile(r"^([А-ЯA-Z]{2,6})", re.IGNORECASE)

# Juda qisqa prefiks har jumlaga mos kelib ketardi.
ENG_QISQA_OILA = 2

# O'lcham ORTADA, oila harfi OXIRIDA: «ВК-125С», «ВК-315П».
OXIRGI_HARF = re.compile(r"^([А-ЯA-Z]{2,6})[\s-]?\d[\d,.]*([А-ЯA-Z]{1,2})$",
                         re.IGNORECASE)


# Kirillcha oila nomini LOTINCHA yozish — ikki xil yo'l bilan.
#
# JONLI XATO (2026-08-28): mijoz «RKV narxi qancha» deb yozdi.
# Katalogda oila «РКВ» (kirillcha) va lotincha matn unga mos
# kelmasdi. Mijoz esa klaviaturasiga qarab yozadi, katalogga qarab
# emas.
#
# Ikki xil moslik kerak:
#   - TRANSLITERATSIYA: В -> V (talaffuz bo'yicha, «RKV»);
#   - KO'RINISH: В -> B (harf shakli bo'yicha, «PKB»).
# Mijoz ikkalasini ham yozishi mumkin.
TRANSLIT = str.maketrans({
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ж": "J",
    "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
    "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U", "Ф": "F",
    "Х": "X", "Ц": "S", "Ч": "C", "Ш": "S", "Щ": "S", "Ы": "I", "Э": "E",
    "Ю": "Y", "Я": "Y",
})

KORINISH = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
})


def lotincha_shakllar(nom: str) -> set[str]:
    """Kirillcha nomning lotincha yozilish variantlari."""
    katta = (nom or "").upper()
    return {katta.translate(TRANSLIT), katta.translate(KORINISH)} - {katta}


def _oilalar(katalog):
    """Katalogdagi oila nomlari: {«РКВ», «РВН», «ФЯК», …}."""
    natija = set()
    for mahsulot in katalog or []:
        for xususiyat in mahsulot.get("characters") or []:
            if not isinstance(xususiyat, dict):
                continue
            nomlar = [str(xususiyat.get("title") or "")]
            nomlar += [str(i.get("in_model_name") or "")
                       for i in (xususiyat.get("insides") or [])
                       if isinstance(i, dict)]
            for nom in nomlar:
                mos = OILA_NAMUNASI.match(nom.strip())
                if mos and len(mos.group(1)) >= ENG_QISQA_OILA:
                    natija.add(mos.group(1).upper())
                # «ВК-125С» — oila «ВК-С», mijoz uni «ВКС»/«VKS» deydi.
                oxiri = OXIRGI_HARF.match(nom.strip())
                if oxiri:
                    natija.add((oxiri.group(1) + oxiri.group(2)).upper())
    return natija


def _oila_jadvali(katalog) -> dict[str, str]:
    """{yozilishi: KATALOGDAGI nomi} — lotincha variantlar bilan."""
    jadval: dict[str, str] = {}
    for oila in _oilalar(katalog):
        jadval[oila] = oila
        for shakl in lotincha_shakllar(oila):
            # Kirillcha asl nom USTUN: ikki oila bir xil lotincha
            # shaklga tushsa, allaqachon yozilgani o'zgartirilmaydi.
            jadval.setdefault(shakl, oila)
    return jadval


# Narx so'ralayotganini bildiruvchi so'zlar.
# Narx so'ralayotganini bildiruvchi so'zlar — ANIQ belgi.
#
# Bu ro'yxat HECH QACHON TO'LIQ BO'LMAYDI: «nechpul», «pochom»,
# «skolko», imlo xatolari, aralash til. Shuning uchun u YAGONA
# mezon emas — pastdagi `narx_soralyaptimi` ga qarang.
NARX_SOZLARI = (
    "narx", "narx", "qancha", "necha pul", "nechpul", "necha so", "qiymat",
    "pul", "цена", "цену", "стоимост", "сколько", "почем", "pochom",
    "skolko", "price", "cost",
)

# Model nomidan tashqari nechta so'z bo'lsa ham «narx savoli» deb
# qaraladi.
#
# JONLI XATO (2026-08-28): mijoz «ПВН nechpul» deb yozdi. «nechpul»
# ro'yxatda yo'q edi va savol LLM yo'liga tushib, «menejer javob
# beradi» degan quruq javob oldi — holbuki ПВН katalogda bor va
# narxi ham bor.
#
# Endi QOIDA BOSHQACHA: mijoz KATALOGDAGI model nomini yozgan va
# jumla QISQA bo'lsa — u shu mahsulot haqida so'rayapti. Buning uchun
# maxsus so'z shart emas.
#
# Uzun jumla chetlab o'tiladi: «ПВН ni qanday o'rnatiladi» — bu narx
# savoli emas, unga agent javob bersin.
MODELSIZ_MAKS_SOZ = 4

# Nechta yaqin nom taklif qilinadi.
TAKLIF_SONI = 5

# O'lchamsiz oila so'ralganda nechta model sanaladi.
OILA_ROYXATI = 8


def narx_soralyaptimi(matn: str,
                      katalog: list[dict[str, Any]] | None = None) -> bool:
    """Mijoz narx (yoki umuman shu mahsulot) haqida so'rayaptimi?

    IKKI YO'L bilan aniqlanadi:

      1. Aniq so'z: «narxi», «qancha», «цена»…
      2. Katalogdagi MODEL NOMI qisqa jumlada. «ПВН», «ПВН nechpul»,
         «ПВН bormi» — hammasi shu mahsulot haqida.

    Ikkinchisi zarur, chunki birinchi ro'yxat hech qachon to'liq
    bo'lmaydi va uni to'ldirib borish — o'sha qotib qolgan jadval.
    """
    past = (matn or "").lower()
    if len(past.split()) > NARX_MAKS_SOZ:
        return False
    if any(soz in past for soz in NARX_SOZLARI):
        return True
    if any(soz in past for soz in XUSUSIYAT_SOZLARI):
        return False
    if not katalog:
        return False

    model = model_ajrat(matn, katalog)
    if not model:
        return False
    # Modeldan tashqari nechta so'z bor?
    qolgan = [s for s in re.split(r"[\s,.?!]+", past)
              if s and s not in model.lower()]
    return len(qolgan) <= MODELSIZ_MAKS_SOZ


def model_ajrat(matn: str, katalog: list[dict[str, Any]] | None = None) -> str | None:
    """Matndan model nomini ajratadi. Topilmasa `None`.

    Eng UZUN moslik olinadi: "ВЦ 4-75-6,3" va "ВЦ 4" ikkalasi ham mos
    keladi, lekin qisqasi bilan qidirsak noto'g'ri model chiqardi.

    `katalog` berilsa RAQAMSIZ oila nomlari ham taniladi («РКВ»,
    «ФЯК»). Ular kodda sanalmaydi — katalogdan yig'iladi (`_oilalar`).
    """
    mosliklar = []
    for m in MODEL_NAMUNASI.finditer(matn or ""):
        nom = QOSHIMCHA.sub("", m.group(1).strip().rstrip(".,-/"))
        # «MF 200 P» -> «MF 200P»: katalog nomida seriya harfi raqamga yopishgan.
        nom = re.sub(r"(\d)\s+([PПCСSШ])$", r"\1\2", nom, flags=re.IGNORECASE)
        prefiks = re.match(r"[А-ЯA-ZЁ]+", nom.upper())
        if prefiks and prefiks.group(0) in ODDIY_SOZLAR:
            continue
        mosliklar.append(nom)
    if mosliklar:
        return max(mosliklar, key=len)

    if katalog:
        jadval = _oila_jadvali(katalog)
        # Chiziqchali oila: «ВК-С narxi», «vk-s narxi». Chiziqcha SAQLANADI:
        # «ВК-П» (dumaloq, ВК-125П) va «ВКП» (to'rtburchak, ВКП 40х20) —
        # boshqa-boshqa oila, chiziqchasiz ular bir xil yoziladi.
        for mos in re.finditer(
                r"(?<![\w'ʻʼ’`])([А-ЯA-Za-zЁёа-я]{2,6})-([А-ЯA-Za-zЁёа-я]{1,2})(?![\w-])",
                matn or ""):
            if (mos.group(1) + mos.group(2)).upper() in jadval:
                return mos.group(0).upper()
        # Faqat BUTUN so'z: apostrofli o'zbekcha so'z bo'laklarga
        # bo'linmasin («ko'rsatma» -> «ko» -> КО klapani, 2026-10-03 QA).
        for soz in re.findall(r"[\w'ʻʼ’`]+", matn or ""):
            if not re.fullmatch(r"[А-ЯA-Za-zЁёа-я]{2,6}", soz):
                continue
            if soz.upper() in ODDIY_SOZLAR:
                continue
            topilgan = jadval.get(soz.upper())
            if topilgan:
                return topilgan
    return None


@dataclass
class NarxJavobi:
    """Qidiruv natijasi.

    `lid_kerak` — menejerga o'tkazish kerakmi. Narx topilganda ham
    `True` bo'lishi mumkin: mijoz baribir buyurtma beradi.
    """

    holat: str                      # narx | narxsiz | topilmadi
    model: str = ""
    narx: float | None = None
    valyuta: str = ""
    # `katalog_narxi` ikkinchi qiymat sifatida SANA emas, narx qaysi
    # variantdan olingani haqidagi izohni qaytaradi ("... 5 variantdan
    # eng arzoni"). Bu mijozga ham foydali: u qaysi ijro narxini
    # ko'rayotganini biladi.
    manba: str = ""
    parametrlar: dict[str, Any] = field(default_factory=dict)
    takliflar: list[str] = field(default_factory=list)
    lid_kerak: bool = True
    # Mijoz qanday yozgani — katalog nomidan farq qilsa javobda ko'rsatiladi
    # («VKS 100» -> «ВК-100С»), mijoz o'zi so'ragan narsani tanisin.
    sorov: str = ""


def _nomlar(katalog: list[dict[str, Any]]) -> list[str]:
    """Katalogdagi barcha model nomlari."""
    natija: list[str] = []
    for mahsulot in katalog:
        for belgi in mahsulot.get("characters") or []:
            sarlavha = str(belgi.get("title") or "").strip()
            if sarlavha:
                natija.append(sarlavha)
            for ichki in belgi.get("insides") or []:
                nom = str(ichki.get("in_model_name") or "").strip()
                if nom:
                    natija.append(nom)
    return natija


def _yaqin_nomlar(katalog: list[dict[str, Any]], sorov: str) -> list[str]:
    """Qidiruvga o'xshash nomlar — mijoz to'g'ri yozishi uchun.

    "Topilmadi" deb to'xtash mijozni ketkazadi. Yaqin nomlar bilan u
    o'zi to'g'rilaydi.
    """
    # OILA nomi bo'yicha qidiriladi (harfli old qism), birinchi N
    # belgi bo'yicha emas. "ВЦ 999-77" da birinchi 4 belgi "вц99" —
    # u hech qaysi nomda uchramaydi va taklif chiqmasdi. Oila "вц"
    # esa o'nlab modelga mos keladi.
    from integrations.climavent_client import kalitla

    # Kirill/lotin farqi hisobga olinadi: «vks» -> «ВКС» (2026-10-03).
    oilalar = kalitla("".join(ch for ch in sorov if ch.isalpha()))
    if not oilalar:
        return []
    ballar: list[tuple[int, str]] = []
    korilgan: set[str] = set()
    for nom in _nomlar(katalog):
        if nom in korilgan:
            continue
        korilgan.add(nom)
        tekis = nom.lower().replace(" ", "")
        nom_oilalari = kalitla("".join(ch for ch in nom if ch.isalpha()))
        if any(n.startswith(o) or o.startswith(n)
               for n in nom_oilalari for o in oilalar):
            ballar.append((len(tekis), nom))
    ballar.sort()
    return [nom for _, nom in ballar[:TAKLIF_SONI]]


def narxni_top(
    katalog: list[dict[str, Any]],
    matn: str,
    kurs: float,
    parametrlar: dict[str, dict[str, Any]] | None = None,
) -> NarxJavobi | None:
    """Mijoz matnidan model topib, narxini qidiradi.

    `None` — matnda model umuman yo'q (savol narx haqida emas).
    """
    from integrations.climavent_client import katalog_narxi, katalog_nomi

    model = model_ajrat(matn, katalog)
    if not model:
        return None

    # Mijoz yozgani -> katalogdagi yozilishi. «VKS 100», «Вк-с 100»,
    # «ВКС-100» — katalogda hammasi «ВК-100С» (2026-10-03 jonli xato:
    # birinchisi «topilmadi», qolganlari BOSHQA mahsulot narxini oldi).
    asl = model
    katalogda = katalog_nomi(katalog, model)
    if katalogda:
        model = katalogda

    # «ВК-П narxi» — chiziqchali, o'lchamsiz oila. Narx qidiruvi uni
    # «ВКП 40х20» (boshqa oila) ga bog'lab qo'yardi, shuning uchun AVVAL
    # oilaning o'z modellari: «ВК-100П», «ВК-125П»…
    if not katalogda and "-" in model and not any(ch.isdigit() for ch in model):
        from integrations.climavent_client import oila_modellari
        modellar = [nom for nom in oila_modellari(katalog, model)
                    if OXIRGI_HARF.match(nom)]
        if modellar:
            return NarxJavobi(
                holat="narxsiz", model=model, sorov=asl,
                takliflar=modellar[:OILA_ROYXATI],
            )

    topilgan = katalog_narxi(katalog, model, kurs=kurs)
    if topilgan is not None:
        return NarxJavobi(
            holat="narx", model=model, narx=topilgan[0],
            valyuta="so'm", manba=topilgan[1], sorov=asl,
        )

    # Narx yo'q — model KATALOGDA BORMI?
    #
    # Katalog nomi so'rov ichida uchrashi faqat nomda RAQAM bo'lsa
    # hisoblanadi. JONLI XATO (2026-10-02): `characters[].title` da oila
    # nomi turadi («ВКК»), u esa «вкк-250» ichida bor — natijada katalogda
    # YO'Q model uchun «katalogimizda bor» deb javob berilardi.
    tekis = model.lower().replace(" ", "")
    bor = any(
        tekis in nom_t or (nom_t in tekis and any(ch.isdigit() for ch in nom_t))
        for nom_t in (nom.lower().replace(" ", "") for nom in _nomlar(katalog))
    )
    # O'lchamsiz oila («vks narxi») — modellari ro'yxati bilan.
    if not katalogda:
        from integrations.climavent_client import oila_modellari
        modellar = oila_modellari(katalog, model)
        if modellar:
            return NarxJavobi(
                holat="narxsiz", model=model, sorov=asl,
                takliflar=modellar[:OILA_ROYXATI],
            )

    if bor or katalogda:
        return NarxJavobi(
            holat="narxsiz", model=model, sorov=asl,
            parametrlar=(parametrlar or {}).get(model, {}),
        )

    return NarxJavobi(
        holat="topilmadi", model=model,
        takliflar=_yaqin_nomlar(katalog, model),
    )


def javob_matni(j: NarxJavobi, telefon: str = "") -> str:
    """Mijozga ko'rsatiladigan matn."""
    aloqa = f"\n\nMenejerimiz: {telefon}" if telefon else ""
    # Katalog nomi mijoz yozganidan farq qilsa — u o'z so'rovini tanisin.
    sorov_izohi = ""
    if j.sorov and j.sorov.strip().upper() != j.model.strip().upper():
        sorov_izohi = f"_(so'rovingiz: «{j.sorov}»)_"

    if j.holat == "narx":
        narx = f"{j.narx:,.0f}".replace(",", " ")
        return (
            f"*{j.model}*\n"
            + (sorov_izohi + "\n" if sorov_izohi else "")
            + "\n"
            f"Narxi: *{narx} so'm* (QQS bilan)\n"
            + (f"_{j.manba}_\n" if j.manba else "")
            + "\n"
            + "Aniq taklif, yetkazish muddati va chegirmalar uchun "
            "menejerimiz bog'lanadi — telefon raqamingizni qoldiring."
            + aloqa
        )

    if j.holat == "narxsiz":
        qatorlar = [f"*{j.model}* — katalogimizda bor."]
        if sorov_izohi:
            qatorlar.append(sorov_izohi)
        if j.takliflar:
            qatorlar += ["", "O'lchamlar: " + ", ".join(j.takliflar)]
        if j.parametrlar:
            qatorlar.append("")
            for kalit, qiymat in list(j.parametrlar.items())[:5]:
                qatorlar.append(f"• {kalit}: {qiymat}")
        qatorlar += [
            "",
            "Bu model narxi buyurtma parametrlariga bog'liq "
            "(o'lchov, ijro, miqdor), shuning uchun uni menejerimiz "
            "hisoblab beradi.",
            "",
            "Telefon raqamingizni qoldiring — bugun bog'lanamiz.",
        ]
        return "\n".join(qatorlar) + aloqa

    qatorlar = [f"«{j.model}» nomli modelni katalogimizdan topa olmadim."]
    if j.takliflar:
        qatorlar += ["", "Balki bulardan biri?"]
        qatorlar += [f"• {t}" for t in j.takliflar]
    qatorlar += ["", "Yoki menejerimizga yozing — u aniq topib beradi."]
    return "\n".join(qatorlar) + aloqa

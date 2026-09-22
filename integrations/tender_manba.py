"""Tender e'lonlari manbalari.

TANLASH MEZONI: TAKLIF BERISH MUMKINMI
-------------------------------------
Standart holatda faqat ISHTIROK ETILADIGAN maydonchalar yoqilgan —
ya'ni lot sahifasida taklif berish bor:

    etender.uzex.uz  — kompaniya ERI kaliti bilan ro'yxatdan o'tgan;
    tender.mc.uz     — "Shaffof qurilish", `bidders_count` va muddat
                       ochiq keladi.

O'CHIRILGANLAR va SABABI (o'lchandi 2026-09-09):

    dxmap (xarid.icppa.uz) — AXBOROT portali. Havolasi taklif berish
      sahifasiga OLIB BORMAYDI, o'z kartochkasini ko'rsatadi, va API
      haqiqiy maydoncha havolasini bermaydi. Ustiga `IN_PROCESS`
      lotlarning 84% ida shartnoma allaqachon tuzilgan.
    uzex — erkin matnli e'lonlar, lot raqami ham yo'q.

Boshqa maydonchada ro'yxatdan o'tilsa `.env` da yoqiladi:
    TENDER_MANBALARI=etender,mcuz,dxmap

FILTRLASH HAQIDA
----------------
Bazada 5 mln dan ortiq lot bor, hammasini olib bo'lmaydi — shuning uchun
DXMAP dan KALIT SO'Z bo'yicha so'raladi. Bu qamrovni cheklaydi, shuning
uchun ishlatilgan kalit so'zlar javobda OCHIQ ko'rsatiladi: topilmagan
e'lon jimgina yo'qolmaydi, qaysi so'z bo'yicha qidirilgani ko'rinib turadi.
Tor filtrlashni (bizga mos-nomos) agent qiladi, manba emas.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any, Protocol

import httpx

UZEX_ASOS = "https://uzex.uz"
UZEX_ROYXAT = UZEX_ASOS + "/Announces?page={sahifa}&limit=20&status=1"

# Sahifadagi e'lon kartochkasi: sana, havola, sarlavha.
KARTOCHKA = re.compile(
    r'blog__date">(?P<sana>[^<]*)</div>.*?'
    r'blog__title"\s+href="(?P<yol>/Announces/[^"]+)">(?P<sarlavha>.*?)</a>',
    re.DOTALL,
)
TEG = re.compile(r"<[^>]+>")


class TenderXatosi(RuntimeError):
    """E'lonlarni olib bo'lmadi (tarmoq, sayt tuzilmasi o'zgargan)."""


@dataclass
class Elon:
    """Bitta e'lon — manbadan olingan xom ko'rinishda.

    Pastdagi tuzilgan maydonlar DXMAP dan keladi. Erkin matnli manbalarda
    (masalan `uzex.uz/Announces`) ular BO'SH qoladi — bu normal holat,
    to'ldirilgan deb ko'rsatilmaydi.
    """

    sarlavha: str
    havola: str
    sana: str = ""
    tavsif: str = ""
    manba: str = ""

    lot_raqami: str = ""
    buyurtmachi: str = ""
    buyurtmachi_stir: str = ""
    # Summa LOT VALYUTASIDA — `valyuta` maydoniga qarang.
    summa: float | None = None
    hudud: str = ""
    maydoncha: str = ""                 # qaysi savdo maydonchasi
    tasnif: str = ""                    # milliy klassifikator kodi
    xarid_turi: str = ""
    # Taklif qabul qilish TUGASH muddati (YYYY-MM-DD).
    #
    # DXMAP buni bermaydi va Jasur uni to'ldira olmaydi (promptda
    # "muddatni o'ylab topmaysan" deb yozilgan). `etender.uzex.uz`
    # esa haqiqiy `end_date` beradi — menejer uchun eng muhim
    # maydonlardan biri: muddati o'tgan lotga ariza berilmaydi.
    muddat: str = ""
    # Nechta ishtirokchi allaqachon taklif bergan.
    #
    # `tender.mc.uz` beradi. Menejer uchun kuchli belgi: 0 bo'lsa
    # raqobat yo'q, ko'p bo'lsa narx allaqachon pasaygan bo'lishi
    # mumkin. `None` — manba bu ma'lumotni bermaydi (bilmaymiz).
    takliflar: int | None = None
    # Summa qaysi valyutada (ISO kod). etender lotni dollarda va yevroda
    # ham e'lon qiladi (2026-09-14: 866 lotdan 54 tasi USD, 10 tasi EUR);
    # tender.mc.uz va DXMAP — faqat so'mda.
    valyuta: str = "UZS"

    @property
    def kalit(self) -> str:
        """Takrorlanmaslik uchun barqaror kalit."""
        return self.havola.strip().lower()

    def qisqa(self) -> dict[str, Any]:
        asos = {
            "sarlavha": self.sarlavha,
            "havola": self.havola,
            "sana": self.sana,
            "tavsif": self.tavsif[:400],
            "manba": self.manba,
        }
        # Bo'sh maydon natijaga tushmaydi — menejer "ma'lumot bor" deb
        # o'ylab qolmasin.
        qoshimcha = {
            "lot_raqami": self.lot_raqami,
            "buyurtmachi": self.buyurtmachi,
            "buyurtmachi_stir": self.buyurtmachi_stir,
            "summa": self.summa,
            "hudud": self.hudud,
            "maydoncha": self.maydoncha,
            "tasnif": self.tasnif,
            "xarid_turi": self.xarid_turi,
            "muddat": self.muddat,
            "takliflar": self.takliflar,
            "valyuta": self.valyuta,
        }
        asos.update({k: v for k, v in qoshimcha.items() if v not in ("", None)})
        return asos


class Manba(Protocol):
    """Har qanday e'lon manbasi shu shaklda bo'ladi."""

    nomi: str

    async def elonlar(self, chek: int = 40) -> list[Elon]: ...


def _matn(xom: str) -> str:
    """HTML bo'lagini o'qiladigan matnga aylantiradi."""
    return " ".join(html.unescape(TEG.sub(" ", xom or "")).split())


@dataclass
class UzexManba:
    """`uzex.uz/Announces` — server tomonda render qilinadi, ochiq.

    DIQQAT: bu birjaning O'Z e'lonlari (ofis xaridlari, yer auksionlari).
    Sanoat ventilyatsiyasi tenderlari asosan yopiq portalda bo'ladi —
    shuning uchun bu manbadan kam natija kutiladi.
    """

    nomi: str = "uzex.uz e'lonlari"
    sahifalar: int = 3
    mijoz: httpx.AsyncClient | None = None
    kutish: float = 25.0
    sarlavhalar: dict[str, str] = field(
        default_factory=lambda: {"User-Agent": "Mozilla/5.0 (Climavent agent)"}
    )

    async def elonlar(self, chek: int = 40) -> list[Elon]:
        topilgan: dict[str, Elon] = {}
        try:
            if self.mijoz is not None:
                await self._yig(self.mijoz, topilgan, chek)
            else:
                async with httpx.AsyncClient(
                    timeout=self.kutish, follow_redirects=True,
                    headers=self.sarlavhalar,
                ) as mijoz:
                    await self._yig(mijoz, topilgan, chek)
        except httpx.HTTPError as xato:
            raise TenderXatosi(f"{self.nomi}: ulanib bo'lmadi ({xato})") from xato
        return list(topilgan.values())[:chek]

    async def _yig(
        self, mijoz: httpx.AsyncClient, topilgan: dict[str, Elon], chek: int
    ) -> None:
        for sahifa in range(1, self.sahifalar + 1):
            if len(topilgan) >= chek:
                return
            javob = await mijoz.get(UZEX_ROYXAT.format(sahifa=sahifa))
            if javob.status_code >= 400:
                # Bitta sahifa ochilmasa ham qolganlari ishlaydi.
                continue
            yangi = 0
            for mos in KARTOCHKA.finditer(javob.text):
                elon = Elon(
                    sarlavha=_matn(mos.group("sarlavha")),
                    havola=UZEX_ASOS + mos.group("yol"),
                    sana=_matn(mos.group("sana")),
                    manba=self.nomi,
                )
                if elon.sarlavha and elon.kalit not in topilgan:
                    topilgan[elon.kalit] = elon
                    yangi += 1
            if not yangi:
                return  # sahifalar tugadi


DXMAP_ASOS = "https://xarid.icppa.uz"
DXMAP_QIDIRUV = DXMAP_ASOS + "/api/v1/lot/searchlots?page=0&size={hajm}"
DXMAP_LOT = DXMAP_ASOS + "/contracts/organ/{stir}/{lot}/{tur}"

# Bazada 5 mln lot bor — hammasini olib bo'lmaydi, kalit so'z bilan
# so'raladi. Ro'yxat ATAYLAB kengroq: tor filtrlashni agent qiladi.
# Yangi so'z kerak bo'lsa shu yerga qo'shiladi, kodga tegilmaydi.
DXMAP_KALIT_SOZLAR: tuple[str, ...] = (
    "ventilyatsiya",
    "вентиляц",          # kirilcha yozilgan lotlar uchun
    "shamollatish",
    "konditsion",
    "кондицион",
    "rekuperator",
    "issiqlik almash",
    "havo tozalash",
    "panjara",
    "aspiratsiya",
    # 2026-09-09 da QO'SHILDI — o'lchov bilan tanlandi.
    #
    # `chiller` +2 lot (LESSAR chillerini ta'mirlash, binodagi chiller),
    # `isitish` +1. Ruscha juftliklari xavfsiz, aniq so'zlar.
    "chiller",
    "чиллер",
    "isitish",
    "отоплен",
)

# SINALGAN VA RAD ETILGAN so'zlar — qayta qo'shilmasin.
#
# Har biri o'lchandi (2026-09-09, 906 ta etender loti) va shovqin
# keltirishi aniqlandi:
#   kanal    +12 — hammasi SUG'ORISH kanali ("Katta Andijon kanali");
#   issiqlik  +6 — issiqlik tashuvchi moy, metallga issiqlik ishlovi;
#   ovk       +4 — "kalibrovka", "obmurovka" ichida uchraydi;
#   klapan    +2 — predoxranitel klapan (mexanik, HVAC emas);
#   filtr     +1 — press-filtr, elektr filtr.
RAD_ETILGAN_SOZLAR = ("kanal", "issiqlik", "ovk", "klapan", "filtr")

# Lot bosqichi. `IN_PROCESS` — e'lon berilgan, shartnoma hali tuzilmagan,
# ya'ni QATNASHISH MUMKIN bo'lgan holat. Tugagan lotlar menejerga
# kerak emas, ular faqat bozor tahlili uchun.
DXMAP_BOSQICH = "IN_PROCESS"

# `IN_PROCESS` "TAKLIF BERISH MUMKIN" DEGANI EMAS.
#
# O'LCHANDI (2026-09-09). 200 ta `IN_PROCESS` lotning bosqichlari:
#   Shartnoma shakllandi    150   <- ish TUGAGAN
#   E'lon                    29   <- hali ochiq
#   G'olib aniqlanmoqda      16   <- taklif berish YOPILGAN
#   To'lov to'liq to'landi    1   <- butunlay tugagan
#   (bosqichsiz, g'olibi bor) 4
#
# Ya'ni menejerga ko'rsatilayotganning 84% iga QATNASHIB BO'LMAYDI.
# U havolani ochadi, o'qiydi va vaqtini behuda sarflaydi.
#
# `lotStatuses` da har bosqich `order` va `isCompleted` bilan keladi.
# `order >= 2` bajarilgan bo'lsa — shartnoma bor. `order == 1` da
# "G'olib aniqlanmoqda" bajarilgan bo'lsa — savdo yopilgan.
DXMAP_YOPIQ_BOSQICH = "g'olib"
DXMAP_SHARTNOMA_ORDER = 2


def _dxmap_ochiqmi(yozuv: dict[str, Any]) -> bool:
    """Bu lotga hali taklif berish mumkinmi?"""
    # G'olib allaqachon ma'lum — savdo tugagan.
    if yozuv.get("vendor") or yozuv.get("vendorInn"):
        return False
    for bosqich in yozuv.get("lotStatuses") or []:
        if not bosqich.get("isCompleted"):
            continue
        tartib = bosqich.get("order")
        if isinstance(tartib, int) and tartib >= DXMAP_SHARTNOMA_ORDER:
            return False
        if DXMAP_YOPIQ_BOSQICH in str(bosqich.get("name") or "").lower():
            return False
    return True

# Summa API da TIYINDA keladi.
#
# JONLI TEKSHIRUV (2026-09-04): portal sahifasida "1 000 000,00 so'm" deb
# ko'rsatilgan lotning API dagi qiymati 100000000 edi. Bo'linmasa har bir
# narx 100 barobar katta chiqardi.
TIYIN = 100


def _dxmap_sarlavha(yozuv: dict[str, Any]) -> str:
    """`enktNames` bir nechta mahsulotni yangi qatorlar bilan beradi."""
    xom = str(yozuv.get("enktNames") or "").strip()
    qismlar = [q.strip() for q in xom.splitlines() if q.strip()]
    if not qismlar:
        return ""
    sarlavha = " / ".join(qismlar[:3])
    if len(qismlar) > 3:
        sarlavha += f" (+{len(qismlar) - 3} pozitsiya)"
    return sarlavha


@dataclass
class DxmapManba:
    """DXMAP — davlat xaridlarining markaziy portali (`xarid.icppa.uz`).

    Beshta savdo maydonchasini qamrab oladi va lot raqami bilan tuzilgan
    ma'lumot beradi. Ochiq API, avtorizatsiya talab qilmaydi.
    """

    nomi: str = "DXMAP (xarid.icppa.uz)"
    kalit_sozlar: tuple[str, ...] = DXMAP_KALIT_SOZLAR
    bosqich: str = DXMAP_BOSQICH
    # Har kalit so'zdan olinadigan lot soni.
    #
    # O'LCHANDI (2026-09-04): kalit so'zlar bo'yicha ayni damda 329 ta
    # takrorsiz ochiq lot bor. 15 tadan olganda ularning uchdan biri ham
    # ko'rinmasdi — menejer "tenderlar kam ekan" deb o'ylardi.
    soz_boshiga: int = 45
    mijoz: httpx.AsyncClient | None = None
    kutish: float = 25.0
    sarlavhalar: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": "Mozilla/5.0 (Climavent agent)",
            "Content-Type": "application/json",
        }
    )

    async def elonlar(self, chek: int = 40) -> list[Elon]:
        topilgan: dict[str, Elon] = {}
        nosozlik: list[str] = []
        try:
            if self.mijoz is not None:
                await self._yig(self.mijoz, topilgan, chek, nosozlik)
            else:
                async with httpx.AsyncClient(
                    timeout=self.kutish, follow_redirects=True,
                    headers=self.sarlavhalar,
                ) as mijoz:
                    await self._yig(mijoz, topilgan, chek, nosozlik)
        except httpx.HTTPError as xato:
            raise TenderXatosi(f"{self.nomi}: ulanib bo'lmadi ({xato})") from xato

        # Bitta kalit so'z yiqilsa qolganlari ishlaydi. Lekin HAMMASI
        # yiqilsa — bu jimgina "e'lon yo'q" emas, nosozlik.
        if not topilgan and len(nosozlik) == len(self.kalit_sozlar):
            raise TenderXatosi(
                f"{self.nomi}: birorta so'rov ham bajarilmadi "
                f"({'; '.join(nosozlik[:3])})"
            )
        return list(topilgan.values())[:chek]

    async def _yig(
        self, mijoz: httpx.AsyncClient, topilgan: dict[str, Elon],
        chek: int, nosozlik: list[str],
    ) -> None:
        for soz in self.kalit_sozlar:
            if len(topilgan) >= chek:
                return
            tana: dict[str, Any] = {"search": soz}
            if self.bosqich:
                tana["lotStatus"] = self.bosqich
            javob = await mijoz.post(
                DXMAP_QIDIRUV.format(hajm=self.soz_boshiga), json=tana
            )
            if javob.status_code >= 400:
                nosozlik.append(f"«{soz}» — HTTP {javob.status_code}")
                continue
            try:
                yozuvlar = (javob.json() or {}).get("content") or []
            except ValueError as xato:
                nosozlik.append(f"«{soz}» — javob JSON emas ({xato})")
                continue
            for yozuv in yozuvlar:
                elon = self._elon(yozuv, soz)
                if elon is not None and elon.kalit not in topilgan:
                    topilgan[elon.kalit] = elon

    def _elon(self, yozuv: dict[str, Any], soz: str) -> Elon | None:
        """Bitta API yozuvini `Elon` ga aylantiradi.

        Lot raqami yoki STIR bo'lmasa havola yasab bo'lmaydi — bunday
        yozuv TASHLANADI. Shartnoma bo'yicha havolasiz e'lon
        ko'rsatilmaydi.
        """
        lot = str(yozuv.get("lotId") or "").strip()
        stir = str(yozuv.get("organInn") or "").strip()
        tur = str(yozuv.get("organizationType") or "").strip()
        sarlavha = _dxmap_sarlavha(yozuv)
        if not (lot and stir and tur and sarlavha):
            return None
        # QATNASHIB BO'LMAYDIGAN LOT KO'RSATILMAYDI (yuqoridagi izoh).
        if not _dxmap_ochiqmi(yozuv):
            return None

        xom_summa = yozuv.get("startSumma")
        summa = None
        if isinstance(xom_summa, (int, float)) and xom_summa > 0:
            summa = round(float(xom_summa) / TIYIN, 2)

        hudud = " ".join(
            q for q in (str(yozuv.get("regionName") or ""),
                        str(yozuv.get("districtName") or "")) if q
        ).strip()

        return Elon(
            sarlavha=sarlavha,
            havola=DXMAP_LOT.format(stir=stir, lot=lot, tur=tur),
            sana=str(yozuv.get("startDate") or yozuv.get("date") or ""),
            manba=self.nomi,
            lot_raqami=lot,
            buyurtmachi=str(yozuv.get("organ") or "").strip(),
            buyurtmachi_stir=stir,
            summa=summa,
            hudud=hudud,
            maydoncha=str(yozuv.get("platformName") or "").strip(),
            tasnif=str(yozuv.get("enktCodes") or "").replace("\n", ", ").strip(),
            xarid_turi=str(yozuv.get("purchaseType") or "").strip(),
        )

    def qamrov(self) -> str:
        """Foydalanuvchiga ko'rsatiladigan qamrov izohi."""
        return (
            f"{self.nomi}: 5 ta savdo maydonchasi "
            f"({len(self.kalit_sozlar)} ta kalit so'z bo'yicha, "
            f"bosqich «{self.bosqich or 'hammasi'}»). "
            f"Kalit so'zlar: {', '.join(self.kalit_sozlar)}."
        )


ETENDER_ASOS = "https://etender.uzex.uz"
ETENDER_API_ASOS = "https://apietender.uzex.uz"
ETENDER_LOT = ETENDER_ASOS + "/lot/{id}"

# IKKI RO'YXAT — kesishmasi NOL.
#
# O'LCHANDI (2026-09-09):
#   /api/common/TradeList          — 676 lot (savdo ochiq);
#   /api/Common/DiscussionTradeList — 236 lot, ularning HECH BIRI
#     birinchi ro'yxatda yo'q. 236 tadan 233 tasining muddati
#     kelajakda, ya'ni bu arxiv emas — tirik ro'yxat.
#
# `TradeList` ni `typeId` SIZ so'raymiz: `typeId=2` (portalda
# `/lots/2/0` sahifasi) 49 lot beradi va o'sha 49 tasi ham
# typeId'siz ro'yxat ichida. Ya'ni filtrsiz so'rov — ustki to'plam.
ETENDER_ROYXATLAR: tuple[tuple[str, str], ...] = (
    ("/api/common/TradeList", "savdo"),
    ("/api/Common/DiscussionTradeList", "muhokama"),
)

# Bitta so'rovda olinadigan lot soni. API `from`/`to` bilan sahifalaydi
# (boshqa nomlar — `page`, `offset`, `skip` — 400 qaytaradi).
ETENDER_SAHIFA = 100
# Nechta sahifadan ko'p olinmaydi — himoya, cheksiz tsikl bo'lmasin.
ETENDER_MAKS_SAHIFA = 12


@dataclass
class EtenderManba:
    """`etender.uzex.uz` — UzEX ning TENDER (tanlov) maydonchasi.

    NEGA ALOHIDA MANBA KERAK
    ------------------------
    DXMAP beshta maydonchani qamraydi, LEKIN `etender.uzex.uz` ular
    orasida YO'Q. Bu boshqa xarid turi: `xarid.uzex.uz` — kichik to'g'ridan
    xaridlar, `etender` — tanlov va tenderlar, ya'ni KATTA shartnomalar.

    O'LCHANDI (2026-09-09): shu maydonchada 679 ochiq lot bor, ulardan
    9 tasi bizning doiramizga tegishli — JAMI 17,58 MLRD so'm. Eng
    kattasi 9,58 mlrd (pretsizion konditsioner yetkazib berish va
    montaj). DXMAP dan topilgan lotlar esa 1–54 mln oralig'ida edi,
    ya'ni bu maydoncha 100-1000 barobar kattaroq shartnomalarni beradi
    va u butunlay ko'rilmayotgan edi.

    IKKI USTUNLIGI BOR
    ------------------
    1. `end_date` — HAQIQIY tugash muddati. DXMAP da muddat bo'sh
       keladi va Jasur uni to'ldira olmaydi;
    2. summa SO'MDA (DXMAP tiyinda beradi) — buni ma'lumotning o'zi
       ko'rsatdi: 679 narxning 40%i 100 ga bo'linmaydi va ba'zilari
       kasrli (`42227893695.4`). Tiyin butun son bo'lardi.

    Kalit so'z bo'yicha FILTRLASH KODDA: API qidiruv qabul qilmaydi,
    shuning uchun butun ro'yxat olinadi va shu yerda saralanadi.
    """

    nomi: str = "etender.uzex.uz (tanlovlar)"
    kalit_sozlar: tuple[str, ...] = DXMAP_KALIT_SOZLAR
    mijoz: httpx.AsyncClient | None = None
    kutish: float = 40.0
    sarlavhalar: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": "Mozilla/5.0 (Climavent agent)",
            "Content-Type": "application/json",
        }
    )

    async def elonlar(self, chek: int = 40) -> list[Elon]:
        try:
            if self.mijoz is not None:
                yozuvlar = await self._yig(self.mijoz)
            else:
                async with httpx.AsyncClient(
                    timeout=self.kutish, follow_redirects=True,
                    headers=self.sarlavhalar,
                ) as mijoz:
                    yozuvlar = await self._yig(mijoz)
        except httpx.HTTPError as xato:
            raise TenderXatosi(f"{self.nomi}: ulanib bo'lmadi ({xato})") from xato

        topilgan: dict[str, Elon] = {}
        for yozuv in yozuvlar:
            if not self._mosmi(yozuv):
                continue
            elon = self._elon(yozuv)
            if elon is not None:
                topilgan.setdefault(elon.kalit, elon)
        return list(topilgan.values())[:chek]

    async def _yig(self, mijoz: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Ikkala ro'yxatni sahifalab oladi (kesishmasi yo'q)."""
        hammasi: list[dict[str, Any]] = []
        for yol, bosqich in ETENDER_ROYXATLAR:
            hammasi += await self._royxat(mijoz, yol, bosqich)
        return hammasi

    async def _royxat(
        self, mijoz: httpx.AsyncClient, yol: str, bosqich: str
    ) -> list[dict[str, Any]]:
        olingan: list[dict[str, Any]] = []
        for sahifa in range(ETENDER_MAKS_SAHIFA):
            boshi = sahifa * ETENDER_SAHIFA + 1
            javob = await mijoz.post(
                ETENDER_API_ASOS + yol,
                json={"from": boshi, "to": boshi + ETENDER_SAHIFA - 1},
            )
            if javob.status_code >= 400:
                raise TenderXatosi(
                    f"{self.nomi}: {yol} — API {javob.status_code} qaytardi"
                )
            yozuvlar = javob.json()
            if not isinstance(yozuvlar, list) or not yozuvlar:
                break
            for yozuv in yozuvlar:
                if isinstance(yozuv, dict):
                    # Qaysi ro'yxatdan kelgani menejerga ko'rinsin:
                    # muhokama bosqichi savdodan farq qiladi.
                    yozuv.setdefault("_bosqich", bosqich)
            olingan += yozuvlar
            # `total_count` har yozuvda keladi — oxiriga yetganini biladi.
            jami = yozuvlar[0].get("total_count")
            if isinstance(jami, (int, float)) and len(olingan) >= jami:
                break
        return olingan

    def _mosmi(self, yozuv: dict[str, Any]) -> bool:
        nomi = str(yozuv.get("name") or "").lower()
        return any(soz in nomi for soz in self.kalit_sozlar)

    def _elon(self, yozuv: dict[str, Any]) -> Elon | None:
        """Bitta lotni `Elon` ga aylantiradi. `id` bo'lmasa tashlanadi."""
        lot_id = str(yozuv.get("id") or "").strip()
        sarlavha = str(yozuv.get("name") or "").strip()
        if not (lot_id and sarlavha):
            return None

        xom = yozuv.get("cost")
        # LOT VALYUTASIDA — tiyinga bo'linMAYDI (yuqoridagi izohga qarang).
        summa = float(xom) if isinstance(xom, (int, float)) and xom > 0 else None
        # VALYUTA LOTNING O'ZIDAN. Ilgari o'qilmasdi va hamma summa "so'm"
        # deb ko'rsatilardi: 81 205,70 dollarlik lot "81 206 so'm" bo'lib
        # chiqardi (2026-09-14: 866 lotdan 54 tasi USD, 10 tasi EUR).
        valyuta = str(yozuv.get("currency_codeabc") or "UZS").strip().upper() or "UZS"

        hudud = " ".join(
            q for q in (str(yozuv.get("region_name") or ""),
                        str(yozuv.get("district_name") or "")) if q and q != "None"
        ).strip()

        return Elon(
            sarlavha=sarlavha,
            havola=ETENDER_LOT.format(id=lot_id),
            sana=str(yozuv.get("start_date") or "")[:10],
            manba=self.nomi,
            # Portalda ko'rinadigan raqam — menejer shu bilan qidiradi.
            lot_raqami=str(yozuv.get("display_no") or lot_id).strip(),
            buyurtmachi=str(yozuv.get("seller_name") or "").strip(),
            buyurtmachi_stir=str(yozuv.get("seller_tin") or "").strip(),
            summa=summa,
            hudud=hudud,
            maydoncha=(
                "etender.uzex.uz"
                + (" (muhokama)" if yozuv.get("_bosqich") == "muhokama" else "")
            ),
            # HAQIQIY MUDDAT — DXMAP bunga ega emas.
            muddat=str(yozuv.get("end_date") or "")[:10],
            valyuta=valyuta,
        )

    def qamrov(self) -> str:
        return (
            f"{self.nomi}: tanlov va tenderlar "
            f"({len(self.kalit_sozlar)} ta kalit so'z bo'yicha). "
            "Bu maydonchada katta shartnomalar bo'ladi."
        )


# --- lot hujjatlari: kartochka, texnik topshiriq, shartnoma loyihasi ---------
#
# NEGA KERAK. Lot SARLAVHASI eng muhim narsani yashiradi — o'lchandi
# (2026-09-14):
#   - 867 ta etender sarlavhasida brend lug'ati BIRORTA ham moslik
#     bermadi. Brend TZ da turadi: 510351 "Марка/модель: ARV6-H610/SR1MV"
#     (AUX) — biz uni "bizga mos" deb ko'rsatganmiz;
#   - 287840 (tender.mc.uz) "oshxona ventilyatsiyasini joriy ta'mirlash"
#     deb chiqdi — aslida LOYIHA-SMETA hujjatini tuzish xizmati. Bu faqat
#     kartochkadagi obyekt turi va ENKT kodida yozilgan;
#   - 511606 da ehtiyot qismlar IJROCHI hisobidan — bu shartnoma
#     loyihasida (DOCX), sarlavhada ham, TZ da ham yo'q;
#   - 511261 ning TZ si ZIP ichida, 511606 niki ZIP ichidagi papkada.
# Shuning uchun TZ, texnik hujjat VA shartnoma loyihasi o'qiladi: PDF,
# DOCX va ular solingan ZIP.
#
# Yo'llar sayt JS dan olingan: `getLot` -> `/api/common/GetTrade/{id}/0`,
# `downloadFile` -> `POST /api/common/DownloadFile?path=...` (GET 405 beradi).

ETENDER_API_LOT = ETENDER_API_ASOS + "/api/common/GetTrade/{id}/0"
ETENDER_API_FAYL = ETENDER_API_ASOS + "/api/common/DownloadFile"
# Kartochkadagi fayl maydonlari. Nomi yonidagi `*_name` maydonida.
ETENDER_FAYL_MAYDONLARI = (
    "tech_file_path", "tech_doc_file_path", "contract_proform_file_path",
)
# Chegaralar — buzuq yoki juda katta fayl kuzatuvni to'xtatmasin.
# 8 MB edi — 510281-lot TZ si 8 410 982 bayt chiqib, 22 KB farq bilan
# TEKSHIRILMAY qoldi (2026-09-14). Aynan katta obyekt loyihalarida TZ
# og'ir bo'ladi. Sahifa chegarasi (TZ_MAKS_BET) baribir ishlaydi.
TZ_MAKS_BAYT = 25 * 1024 * 1024
TZ_MAKS_BET = 40
# Bitta lotdan olinadigan jami matn. 80 000 edi — endi shartnoma va ZIP
# ichidagi hujjatlar ham o'qiladi: 511261 ning o'zi 6 ta PDF, ~190 ming
# belgi. Modelga bundan ancha kami boradi (agentdagi chegara).
TZ_MAKS_BELGI = 200_000
# ZIP ichidan ko'pi bilan shuncha fayl ochiladi.
ZIP_MAKS_FAYL = 20
TZ_KUTISH = 30.0

# tender.mc.uz kartochkasida fayl shunday keladi:
#   "loyiha_pdf": {"file": "/storage/268877/loyiha_pdf/58/….pdf",
#                  "file_name": "Илова 1,2.pdf"}
MCUZ_FAYL_ASOS = "https://apisitender.mc.uz"
MCUZ_MAKS_FAYL = 10


@dataclass
class LotHujjati:
    """Lot hujjatlaridan olingan matn va aniq shartlar.

    `shartlar` — API maydonlaridan KODDA ko'chiriladi (baholash usuli,
    avans, obyekt turi): model ularni o'ylab topa olmaydi.
    `oqilmagan` — o'qib bo'lmagan fayllar SABABI bilan. Jimgina "hujjatda
    hech narsa yo'q" deb hisoblanmasin.
    """

    karta: str = ""
    shartlar: list[str] = field(default_factory=list)
    fayllar: list[tuple[str, str]] = field(default_factory=list)
    oqilmagan: list[str] = field(default_factory=list)

    def qosh(self, oqilgan: list[tuple[str, str]], oqilmagan: list[str]) -> None:
        self.fayllar.extend(oqilgan)
        self.oqilmagan.extend(oqilmagan)

    @property
    def matn(self) -> str:
        """Hammasi bitta matnda — brend qidiruvi shu bo'yicha."""
        bolaklar = [self.karta, *self.shartlar, *(m for _, m in self.fayllar)]
        return "\n".join(b for b in bolaklar if b)[:TZ_MAKS_BELGI]

    @property
    def bosh(self) -> bool:
        return not (self.karta or self.shartlar or self.fayllar)


def etender_lot_id(havola: str) -> str | None:
    """`https://etender.uzex.uz/lot/510351` -> `"510351"`. Boshqa manba — None."""
    mos = re.search(r"etender\.uzex\.uz/lot/(\d+)", havola or "")
    return mos.group(1) if mos else None


def _pdf_matni(mazmun: bytes) -> str:
    import io

    from pypdf import PdfReader

    betlar = []
    for tartib, bet in enumerate(PdfReader(io.BytesIO(mazmun)).pages):
        if tartib >= TZ_MAKS_BET:
            break
        try:
            betlar.append(bet.extract_text() or "")
        except Exception:  # noqa: BLE001 — bitta bet buzuq bo'lsa qolgani olinsin
            continue
    return "\n".join(betlar)


def mcuz_lot_id(havola: str) -> str | None:
    """`https://tender.mc.uz/tender-list/tender/287840/view` -> `"287840"`."""
    mos = re.search(r"tender\.mc\.uz/tender-list/tender/(\d+)", havola or "")
    return mos.group(1) if mos else None


def _docx_matni(mazmun: bytes) -> str:
    import io

    from docx import Document

    hujjat = Document(io.BytesIO(mazmun))
    bolaklar = [p.text for p in hujjat.paragraphs]
    # Miqdor va narx odatda JADVALDA turadi (511606 shartnomasi:
    # "205 dona | 420 000,00 | 86 100 000,00").
    for jadval in hujjat.tables:
        for qator in jadval.rows:
            bolaklar.append(" | ".join(k.text.strip() for k in qator.cells))
    return "\n".join(b for b in bolaklar if b.strip())


def _zip_nomi(info: Any) -> str:
    """ZIP ichidagi fayl nomi.

    UTF-8 bayrog'i bo'lmasa `zipfile` nomni CP437 deb o'qiydi, Windows
    arxivatori esa kirillni CP866 da yozadi — "Техническое задание.pdf"
    tushunarsiz belgilar bo'lib chiqardi.
    """
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp866")
    except UnicodeError:
        return info.filename


def _hujjatni_oqi(
    nomi: str, mazmun: bytes, arxivdan: bool = False
) -> tuple[list[tuple[str, str]], list[str]]:
    """Fayl -> (o'qilgan `(nom, matn)` lar, o'qilmaganlar SABABI bilan).

    Tur KENGAYTMADAN emas, BAYTLARDAN aniqlanadi: sayt fayl o'rniga HTML
    sahifa qaytarishi mumkin, DOCX ham ZIP imzosi bilan boshlanadi.
    Arxiv ichidagi arxiv ochilmaydi.
    """
    import io
    import zipfile

    if len(mazmun) > TZ_MAKS_BAYT:
        return [], [f"{nomi}: juda katta"]
    try:
        if mazmun.startswith(b"%PDF"):
            matn = _pdf_matni(mazmun)
            if not matn.strip():
                return [], [f"{nomi}: matn qatlami yo'q (skanerlangan rasm)"]
            return [(nomi, matn)], []

        if mazmun.startswith(b"PK"):
            arxiv = zipfile.ZipFile(io.BytesIO(mazmun))
            ichidagi = set(arxiv.namelist())
            if "word/document.xml" in ichidagi:
                matn = _docx_matni(mazmun)
                return ([(nomi, matn)], []) if matn else ([], [f"{nomi}: bo'sh hujjat"])
            if "xl/workbook.xml" in ichidagi:
                return [], [f"{nomi}: Excel jadvali o'qilmaydi"]
            if arxivdan:
                return [], [f"{nomi}: arxiv ichidagi arxiv ochilmaydi"]

            oqilgan: list[tuple[str, str]] = []
            oqilmagan: list[str] = []
            fayllar = [i for i in arxiv.infolist() if not i.is_dir()]
            jami = 0
            for info in fayllar[:ZIP_MAKS_FAYL]:
                ichki = _zip_nomi(info).rsplit("/", 1)[-1]
                jami += info.file_size
                # Siqilgan hajm kichik, ochilgani ulkan bo'lishi mumkin.
                if info.file_size > TZ_MAKS_BAYT or jami > 2 * TZ_MAKS_BAYT:
                    oqilmagan.append(f"{ichki}: juda katta")
                    continue
                o, q = _hujjatni_oqi(ichki, arxiv.read(info), arxivdan=True)
                oqilgan.extend(o)
                oqilmagan.extend(q)
            if len(fayllar) > ZIP_MAKS_FAYL:
                oqilmagan.append(
                    f"{nomi}: yana {len(fayllar) - ZIP_MAKS_FAYL} ta fayl ochilmadi"
                )
            return oqilgan, oqilmagan

        if mazmun.startswith(b"\xd0\xcf\x11\xe0"):
            return [], [f"{nomi}: eski Word/Excel formati (.doc, .xls) o'qilmaydi"]
        if mazmun.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
            return [], [f"{nomi}: fayl o'rniga sayt sahifasi keldi"]
        return [], [f"{nomi}: formati o'qilmaydi"]
    except Exception as xato:  # noqa: BLE001 — pypdf, zipfile va docx turli xato beradi
        return [], [f"{nomi}: o'qilmadi ({xato})"]


def _json_royxat(qiymat: Any) -> list[Any]:
    """etender ba'zi ro'yxatlarni JSON MATN sifatida beradi."""
    import json

    if isinstance(qiymat, str):
        try:
            qiymat = json.loads(qiymat)
        except ValueError:
            return []
    return qiymat if isinstance(qiymat, list) else []


def _foiz(qiymat: Any) -> str | None:
    try:
        son = float(qiymat)
    except (TypeError, ValueError):
        return None
    return f"{son:g}%" if son > 0 else None


def _etender_karta(lot: dict[str, Any]) -> str:
    """Kartochka matni: nomi, tavsif, mahsulotlar, baholash va malaka mezonlari."""
    bolaklar = [
        str(lot.get(k) or "")
        for k in ("name", "addon_description", "technical_description")
    ]
    for mahsulot in _json_royxat(lot.get("budget_products")):
        if isinstance(mahsulot, dict):
            bolaklar.append(str(mahsulot.get("Product_Name") or ""))
            bolaklar.append(str(mahsulot.get("Description") or ""))
    # BAHOLASH MEZONLARI — to'xtatuvchi shart aynan shu yerda yoziladi.
    # 511261: "tajribasi yetarli darajada deb topilmasa, ishtirokchi
    # chetlashtiriladi".
    for mezon in _json_royxat(lot.get("js_fields") or lot.get("fields")):
        if isinstance(mezon, dict):
            nomi = str(mezon.get("label") or mezon.get("Label") or "")
            tavsif = str(mezon.get("description") or mezon.get("Description") or "")
            if nomi or tavsif:
                bolaklar.append(f"Baholash mezoni: {nomi} {tavsif}".strip())
    malaka = [
        str(m.get("name") or m.get("Name") or "")
        for m in _json_royxat(
            lot.get("js_qualification_fields") or lot.get("qualification_fields")
        )
        if isinstance(m, dict)
    ]
    if any(malaka):
        bolaklar.append("Malaka talablari: " + "; ".join(m for m in malaka if m))
    return "\n".join(b for b in bolaklar if b)


def _etender_shartlar(lot: dict[str, Any]) -> list[str]:
    """API maydonlaridan ANIQ shartlar.

    ZAKALAT ATAYLAB YO'Q: `pledge_value` birligi noma'lum (511606 da 1.0),
    511261 kartochkasi "zakalat talab etiladi" desa, xarid hujjati 0%
    deydi. Noaniq raqamni ko'rsatgandan ko'rsatmagan yaxshi — hujjatdagisini
    model o'qiydi.
    """
    shartlar: list[str] = []
    usul = str(lot.get("valuation_name") or "").strip()
    if usul:
        texnika = _foiz(lot.get("tech_coef"))
        if texnika:
            usul += f" (texnika {texnika}, narx {_foiz(lot.get('cost_coef')) or '0%'})"
        shartlar.append(f"Baholash: {usul}")
    if avans := _foiz(lot.get("advance_payment_perc")):
        shartlar.append(f"Avans: {avans}")
    if tolov := str(lot.get("payment_type_name") or "").strip():
        shartlar.append(f"To'lov: {tolov}")
    if joy := str(lot.get("delivering_address") or "").strip():
        shartlar.append(f"Bajarish joyi: {joy}")
    return shartlar


async def _ulanib(
    ish: Any, mijoz: Any, lot_id: str, sarlavhalar: dict[str, str] | None = None
) -> LotHujjati:
    try:
        if mijoz is not None:
            return await ish(mijoz)
        async with httpx.AsyncClient(
            timeout=TZ_KUTISH, follow_redirects=True, headers=sarlavhalar,
        ) as m:
            return await ish(m)
    except httpx.HTTPError as xato:
        raise TenderXatosi(f"lot {lot_id}: tarmoq xatosi ({xato})") from xato


def _lot_json(javob: Any, lot_id: str) -> Any:
    if javob.status_code >= 400 or not javob.content:
        raise TenderXatosi(f"lot {lot_id}: tafsilot {javob.status_code} qaytardi")
    try:
        return javob.json()
    except ValueError as xato:
        raise TenderXatosi(f"lot {lot_id}: tafsilot JSON emas") from xato


async def _faylni_qosh(m: Any, hujjat: LotHujjati, nomi: str, sorov: Any) -> None:
    """Bitta faylni yuklab o'qiydi. Yiqilsa — sababi `oqilmagan` ga."""
    try:
        fayl = await sorov(m)
    except httpx.HTTPError as xato:
        hujjat.oqilmagan.append(f"{nomi}: yuklanmadi ({type(xato).__name__})")
        return
    if fayl.status_code >= 400:
        hujjat.oqilmagan.append(f"{nomi}: yuklanmadi ({fayl.status_code})")
        return
    hujjat.qosh(*_hujjatni_oqi(nomi, fayl.content))


async def etender_lot_hujjatlari(lot_id: str, mijoz: Any = None) -> LotHujjati:
    """etender lotining kartochkasi, shartlari va fayllari.

    Kartochka ochilmasa `TenderXatosi` — chaqiruvchi lotni "tekshirilmadi"
    deb hisoblashi kerak, jimgina "brend yo'q" deb emas. Bitta FAYL
    o'qilmasa esa xato ko'tarilmaydi: u sababi bilan `oqilmagan` ga
    yoziladi, qolganlari o'qiladi.
    """

    async def ish(m: Any) -> LotHujjati:
        lot = _lot_json(
            await m.get(ETENDER_API_LOT.format(id=lot_id), timeout=TZ_KUTISH), lot_id
        )
        if not isinstance(lot, dict):
            raise TenderXatosi(f"lot {lot_id}: tafsilot kutilgan shaklda emas")

        hujjat = LotHujjati(karta=_etender_karta(lot), shartlar=_etender_shartlar(lot))
        for kalit in ETENDER_FAYL_MAYDONLARI:
            yol = str(lot.get(kalit) or "").strip()
            if not yol:
                continue
            nomi = str(lot.get(kalit.replace("_path", "_name")) or yol.rsplit("/", 1)[-1])
            await _faylni_qosh(
                m, hujjat, nomi,
                lambda k, yol=yol: k.post(
                    ETENDER_API_FAYL, params={"path": yol}, timeout=TZ_KUTISH
                ),
            )
        return hujjat

    return await _ulanib(ish, mijoz, lot_id)


def _mcuz_nomi(qiymat: Any) -> str:
    return str(qiymat.get("name") or "").strip() if isinstance(qiymat, dict) else ""


def _mcuz_shartlar(lot: dict[str, Any]) -> list[str]:
    shartlar: list[str] = []
    if tur := _mcuz_nomi(lot.get("object_type")):
        shartlar.append(f"Obyekt turi: {tur}")
    if ish := _mcuz_nomi(lot.get("service_type")):
        shartlar.append(f"Ish turi: {ish}")
    # ENKT — xarid PREDMETI. 287840 da "Услуга по разработке
    # проектно-сметных работ": ta'mir emas, loyiha.
    plan = lot.get("plan") if isinstance(lot.get("plan"), dict) else {}
    predmetlar = dict.fromkeys(
        nomi
        for band in plan.get("items") or []
        if isinstance(band, dict) and (nomi := _mcuz_nomi(band.get("enkt_code")))
    )
    if predmetlar:
        shartlar.append("Xarid predmeti (ENKT): " + "; ".join(predmetlar))
    for ixtisoslik in lot.get("specializations") or []:
        if nomi := _mcuz_nomi(ixtisoslik):
            toifa = " — toifa talab qilinadi" if ixtisoslik.get("toifa_required") else ""
            shartlar.append(f"Talab qilinadigan ixtisoslik: {nomi}{toifa}")
    kun = lot.get("end_term_work_days")
    if isinstance(kun, (int, float)) and kun > 0:
        shartlar.append(f"Bajarish muddati: {kun:g} kun")
    return shartlar


async def mcuz_lot_hujjatlari(tender_id: str, mijoz: Any = None) -> LotHujjati:
    """tender.mc.uz lotining kartochkasi, shartlari va fayllari.

    JONLI HOLAT (2026-09-14): 287840 "Oliy sud oshxonasi ventilyatsiyasini
    joriy ta'mirlash" deb chiqdi. Kartochkada esa obyekt turi
    "Проектно-изыскательный", ENKT "Услуга по разработке проектно-сметных
    работ" — ta'mirning o'zi emas, LOYIHASI.
    """

    async def ish(m: Any) -> LotHujjati:
        tana = _lot_json(await m.get(f"{MCUZ_API}/{tender_id}", timeout=TZ_KUTISH), tender_id)
        lot = ((tana.get("result") or {}).get("data")) if isinstance(tana, dict) else None
        if not isinstance(lot, dict):
            raise TenderXatosi(f"lot {tender_id}: tafsilot kutilgan shaklda emas")

        hujjat = LotHujjati(
            karta="\n".join(str(lot[k]) for k in ("name", "address") if lot.get(k)),
            shartlar=_mcuz_shartlar(lot),
        )
        fayllar = [
            element
            for qiymat in lot.values()
            for element in (qiymat if isinstance(qiymat, list) else [qiymat])
            if isinstance(element, dict)
            and str(element.get("file") or "").startswith("/")
        ]
        for element in fayllar[:MCUZ_MAKS_FAYL]:
            yol = str(element["file"])
            nomi = str(element.get("file_name") or yol.rsplit("/", 1)[-1])
            await _faylni_qosh(
                m, hujjat, nomi,
                lambda k, yol=yol: k.get(MCUZ_FAYL_ASOS + yol, timeout=TZ_KUTISH),
            )
        return hujjat

    return await _ulanib(
        ish, mijoz, tender_id, {"User-Agent": "Mozilla/5.0 (Climavent agent)"}
    )


async def elonlarni_yig(
    manbalar: list[Manba], chek: int = 40
) -> tuple[list[Elon], list[str]]:
    """Barcha manbalardan e'lon yig'adi.

    Bitta manba yiqilsa qolganlari ishlaydi — nosozlik ro'yxat sifatida
    qaytadi va agent uni ochiq aytadi (jimgina yutilmaydi).
    """
    hammasi: dict[str, Elon] = {}
    nosozliklar: list[str] = []
    for manba in manbalar:
        try:
            for elon in await manba.elonlar(chek):
                hammasi.setdefault(elon.kalit, elon)
        except TenderXatosi as xato:
            nosozliklar.append(str(xato))
        except Exception as xato:  # manba kutilmaganda o'zgarsa ham to'xtamaydi
            nosozliklar.append(f"{getattr(manba, 'nomi', 'manba')}: {xato}")

    # UMUMIY CHEK QO'YILMAYDI — `chek` HAR MANBAGA alohida beriladi.
    #
    # JIM YO'QOTISH EDI: ilgari bu yerda `[:chek]` turardi. DXMAP yolg'iz
    # 156 ta e'lon berardi, chek esa 150 — ya'ni undan keyin keladigan
    # `etender.uzex.uz` lotlari ro'yxatga UMUMAN kirmasdi. Aynan o'sha
    # lotlar esa eng qimmatlisi (mediana 130 mln, DXMAP da 11 mln).
    #
    # Kesish endi CHAQIRUVCHIDA, TARTIBLAGANDAN KEYIN bo'ladi — shunda
    # kesilgani eng kamahamiyatlisi bo'ladi, tasodifiy oxirgisi emas.
    return list(hammasi.values()), nosozliklar


MCUZ_ASOS = "https://tender.mc.uz"
MCUZ_API = "https://apisitender.mc.uz/api/tenders"
MCUZ_LOT = MCUZ_ASOS + "/tender-list/tender/{id}/view"

# `status=2` — E'LON bosqichi, ya'ni taklif berish OCHIQ.
#
# O'LCHANDI (2026-09-09): filtrsiz 115 390 lot (butun arxiv),
# `status=2` bilan 498 ta. Ya'ni filtrsiz so'rash ma'nosiz.
MCUZ_OCHIQ_HOLAT = "2"

# Qidiruv parametri `name` — `search`, `q`, `keyword` ISHLAMAYDI
# (jimgina butun ro'yxatni qaytaradi, ya'ni filtr yo'qday). Bu sinab
# aniqlangan: har biri 115 390 ta qaytardi, `name` esa 10 ta.
MCUZ_QIDIRUV = "name"

# Bir kalit so'z uchun olinadigan lot soni.
MCUZ_SAHIFA = 50


@dataclass
class McuzManba:
    """`tender.mc.uz` — "Shaffof qurilish" tender maydonchasi.

    ISHTIROK ETILADI: lot sahifasida taklif berish bor, `bidders_count`
    va `placement_term` (muddat) ochiq keladi.

    DIQQAT — BU QURILISH MAYDONCHASI. O'LCHANDI (2026-09-09): 498 ta
    ochiq tenderdan bizning kalit so'zlarimiz bo'yicha VENTILYATSIYA
    lotlari NOL ta. "Panjara" ga tushgan 4 tasi yo'l va park qurilishi
    loyihalari (17 mlrd, 13 mlrd) — ya'ni bosh pudratchi tenderlari,
    ventilyatsiya ularning ichidagi qism.

    Shunga qaramay ulangan: ventilyatsiya loti alohida chiqishi mumkin
    va o'shanda ko'rmaslik qimmatga tushadi. Bugun nol natija berishi
    kutilgan hol, xato emas.
    """

    nomi: str = "tender.mc.uz (Shaffof qurilish)"
    kalit_sozlar: tuple[str, ...] = DXMAP_KALIT_SOZLAR
    mijoz: httpx.AsyncClient | None = None
    kutish: float = 40.0
    soz_boshiga: int = MCUZ_SAHIFA
    sarlavhalar: dict[str, str] = field(
        default_factory=lambda: {"User-Agent": "Mozilla/5.0 (Climavent agent)"}
    )

    async def elonlar(self, chek: int = 40) -> list[Elon]:
        topilgan: dict[str, Elon] = {}
        nosozlik: list[str] = []
        try:
            if self.mijoz is not None:
                await self._yig(self.mijoz, topilgan, nosozlik)
            else:
                async with httpx.AsyncClient(
                    timeout=self.kutish, follow_redirects=True,
                    headers=self.sarlavhalar,
                ) as mijoz:
                    await self._yig(mijoz, topilgan, nosozlik)
        except httpx.HTTPError as xato:
            raise TenderXatosi(f"{self.nomi}: ulanib bo'lmadi ({xato})") from xato

        # HAMMA so'rov yiqilsa — bu nosozlik, "lot yo'q" emas.
        if nosozlik and not topilgan:
            raise TenderXatosi(f"{self.nomi}: {nosozlik[0]}")
        return list(topilgan.values())[:chek]

    async def _yig(
        self,
        mijoz: httpx.AsyncClient,
        topilgan: dict[str, Elon],
        nosozlik: list[str],
    ) -> None:
        for soz in self.kalit_sozlar:
            javob = await mijoz.get(
                MCUZ_API,
                params={
                    "status": MCUZ_OCHIQ_HOLAT,
                    MCUZ_QIDIRUV: soz,
                    "per_page": self.soz_boshiga,
                },
            )
            if javob.status_code >= 400:
                nosozlik.append(f"«{soz}» so'rovi {javob.status_code} qaytardi")
                continue
            try:
                yozuvlar = (javob.json().get("result") or {}).get("data") or []
            except ValueError:
                nosozlik.append(f"«{soz}» javobi JSON emas")
                continue
            for yozuv in yozuvlar:
                elon = self._elon(yozuv)
                if elon is not None:
                    topilgan.setdefault(elon.kalit, elon)

    def _elon(self, yozuv: dict[str, Any]) -> Elon | None:
        """Bitta tenderni `Elon` ga aylantiradi."""
        lot_id = str(yozuv.get("id") or "").strip()
        sarlavha = " ".join(str(yozuv.get("name") or "").split())
        if not (lot_id and sarlavha):
            return None
        # G'olibi bor — taklif berib bo'lmaydi.
        if yozuv.get("winner_id"):
            return None

        xom = yozuv.get("start_price")
        summa = None
        try:
            # SO'MDA — tiyinga bo'linMAYDI. O'lchandi (2026-09-09):
            # 200 narxdan 66%i 100 ga bo'linmaydi, kasrlisi yo'q.
            if xom is not None and float(xom) > 0:
                summa = float(xom)
        except (TypeError, ValueError):
            summa = None

        mijoz_ = yozuv.get("customer") or {}
        hudud = " ".join(
            q for q in (
                str((yozuv.get("region") or {}).get("name") or ""),
                str((yozuv.get("district") or {}).get("name") or ""),
            ) if q
        ).strip()

        takliflar = yozuv.get("bidders_count")
        return Elon(
            sarlavha=sarlavha,
            havola=MCUZ_LOT.format(id=lot_id),
            sana=str(yozuv.get("confirmed_date") or "")[:10],
            manba=self.nomi,
            lot_raqami=str(yozuv.get("unique_name") or lot_id).strip(),
            buyurtmachi=str(mijoz_.get("name") or "").strip(),
            buyurtmachi_stir=str(mijoz_.get("inn") or "").strip(),
            summa=summa,
            hudud=hudud,
            maydoncha="tender.mc.uz",
            muddat=str(yozuv.get("placement_term") or "")[:10],
            takliflar=takliflar if isinstance(takliflar, int) else None,
        )

    def qamrov(self) -> str:
        return (
            f"{self.nomi}: faqat ochiq (e'lon bosqichidagi) tenderlar, "
            f"{len(self.kalit_sozlar)} ta kalit so'z bo'yicha. Bu qurilish "
            "maydonchasi — ventilyatsiya ko'pincha bino shartnomasining "
            "ichida bo'ladi, alohida lot sifatida kam chiqadi."
        )


# Nom -> manba. `.env` dagi `TENDER_MANBALARI` shu nomlar bilan ishlaydi.
MANBALAR: dict[str, Any] = {
    "etender": EtenderManba,
    "mcuz": McuzManba,
    "dxmap": DxmapManba,
    "uzex": UzexManba,
}

# Standart holat — FAQAT `etender`.
#
# NEGA FAQAT BITTASI. Menejer taklifni QAYERDA berishini bilishi kerak,
# aks holda e'lon ma'lumot emas, shovqin.
#
#   etender.uzex.uz — kompaniya ERI kaliti bilan ro'yxatdan o'tgan,
#     lot sahifasida "o'z taklifingizni bering" bor. Ishtirok ETILADI.
#
#   DXMAP (xarid.icppa.uz) — AXBOROT portali. Uning havolasi taklif
#     berish sahifasiga OLIB BORMAYDI, faqat o'z kartochkasini
#     ko'rsatadi, va API haqiqiy maydoncha havolasini bermaydi.
#     Ustiga (o'lchandi 2026-09-09) `IN_PROCESS` lotlarning 84% ida
#     shartnoma allaqachon tuzilgan. Ochiqlarini filtrladik, lekin
#     ular ham BOSHQA maydonchalarda (xarid.uzex.uz, xt-xarid.uz) va
#     u yerlarda alohida ro'yxatdan o'tish kerak.
#
#   uzex.uz/Announces — erkin matn, lot raqami ham yo'q.
#
# Boshqa maydonchada ham ro'yxatdan o'tilsa, `.env` da yoqiladi:
#     TENDER_MANBALARI=etender,dxmap
# `mcuz` ham ISHTIROK ETILADIGAN maydoncha (lot sahifasida taklif
# berish bor), shuning uchun standart holatda yoqilgan. Bugun undan
# ventilyatsiya lotlari kelmaydi (qurilish maydonchasi) — bu kutilgan
# hol, xato emas.
STANDART_MANBALAR = ("etender", "mcuz")


def standart_manbalar(nomlar: Sequence[str] | None = None) -> list[Manba]:
    """Yoqilgan manbalar ro'yxati.

    Noma'lum nom JIMGINA TASHLANMAYDI — u `ValueError` beradi, aks holda
    `.env` da xato yozilsa manba jimgina o'chib qolardi va tender
    topilmagani sabab ko'rinmasdi.
    """
    tanlangan = tuple(nomlar) if nomlar else STANDART_MANBALAR
    natija: list[Manba] = []
    for nom in tanlangan:
        kalit = nom.strip().lower()
        if not kalit:
            continue
        if kalit not in MANBALAR:
            raise ValueError(
                f"noma'lum tender manbasi: {nom!r}. "
                f"Mavjudlari: {', '.join(sorted(MANBALAR))}"
            )
        natija.append(MANBALAR[kalit]())
    if not natija:
        raise ValueError("tender manbalari ro'yxati bo'sh")
    return natija

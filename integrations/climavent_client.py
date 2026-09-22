"""Climavent backend API klienti — agentlar uchun BIRLAMCHI ma'lumot manbai.

Qoidalar:
  - faqat O'QISH: bu klientda yozish/o'zgartirish metodlari umuman yo'q,
    shuning uchun agent (jumladan Doston) yozish endpointiga murojaat qila
    olmaydi — bu kodda ta'minlangan, promptda emas;
  - API ishlamasa xato YUTILMAYDI: `ApiXatosi` ko'tariladi va agent
    "ichki manba mavjud emas" deb ochiq aytadi, to'qib chiqarmaydi;
  - katalog tez-tez o'zgarmaydi — javoblar qisqa muddatga keshlanadi.

Hujjat: `docs/climavent-api.md`
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import sozlama
from app.kurs import joriy as kurs_joriy

from .texnik import ModelParametri, hujjatdan_parametrlar, moslashtir

log = logging.getLogger("climavent")

# Fonda ketayotgan texnik-kesh yangilash vazifasi. Havola saqlanmasa
# asyncio uni yig'ib yuborishi mumkin.
_TEXNIK_YANGILASH: "asyncio.Task[None] | None" = None

# Bitta mahsulotdan nechta texnik hujjat o'qiladi.
#
# Ilgari 3 edi va o'shanda mantiqiy: model NOMLARI alohida jadvaldan
# kelardi, hujjat esa faqat parametrni to'ldirardi.
#
# Endi nom ham, hujjat ham bitta joydan — `characters[]` dan keladi.
# Shu sababli cheklov to'g'ridan-to'g'ri MA'LUMOT YO'QOTADI: o'lchandi
# (2026-09-09) — 31 mahsulotda 3 tadan ko'p xususiyat bor va jami 107 ta
# hujjat umuman o'qilmay qolardi. "Ventilyator VR 6-28" da 11 ta
# xususiyatdan 3 tasi o'qilib, qolgani tashlab ketilardi.
#
# Chegara baribir qoladi — buzuq ma'lumot cheksiz so'rovga aylanmasin.
MAKS_TEXNIK_HUJJAT = 20

# Matn maydonlari uch tilda keladi; shu tartibda tanlanadi.
TIL_TARTIBI = ("uz", "ru", "en")

# Katalogda model kodlari kirillcha yozilgan (ВК-250П), foydalanuvchi esa
# lotincha yozadi (VK-250P). Ikki xil moslashtirish kerak:
#
#   1) TO'LIQ TRANSLITERATSIYA — П→P, Ф→F kabi. Aynan shu "ВК-250П" ni
#      "VK-250P" ga bog'laydi.
#   2) KO'RINISH BO'YICHA — В→B kabi, ba'zi kataloglarda lotin harfi
#      kirillchaga o'xshatib yozilgan bo'ladi.
#
# Ikkalasi ham sinaladi: biri mos kelmasa, ikkinchisi ishlaydi.
TRANSLIT = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Ғ": "G", "Д": "D", "Е": "E",
    "Ё": "YO", "Ж": "J", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Қ": "Q",
    "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "У": "U", "Ў": "O", "Ф": "F", "Х": "X", "Ҳ": "H", "Ц": "TS",
    "Ч": "CH", "Ш": "SH", "Щ": "SH", "Ъ": "", "Ы": "I", "Ь": "", "Э": "E",
    "Ю": "YU", "Я": "YA",
}
# Ko'rinishi bir xil harflar (В→B, Р→P): transliteratsiyadan farq qiladi.
KORINISH = str.maketrans("АВСЕКМНОРТУХ", "ABCEKMHOPTYX")


def kalitla(matn_qiymati: str) -> set[str]:
    """Solishtirish uchun kalit variantlari (kirill/lotin, belgisiz)."""
    asos = "".join(ch for ch in (matn_qiymati or "").upper() if ch.isalnum())
    if not asos:
        return set()
    return {
        asos,
        "".join(TRANSLIT.get(ch, ch) for ch in asos),
        asos.translate(KORINISH),
    }


def _mos_keladimi(sorov: str, nomzod: str) -> bool:
    """Model kodi mos keladimi (kirill/lotin farqini hisobga olib)."""
    sorov_kalitlari = kalitla(sorov)
    nomzod_kalitlari = kalitla(nomzod)
    if not sorov_kalitlari or not nomzod_kalitlari:
        return False
    return any(s in n or n in s for s in sorov_kalitlari for n in nomzod_kalitlari)


class ApiXatosi(RuntimeError):
    """Ichki API'dan ma'lumot olib bo'lmadi (tarmoq, 4xx/5xx, buzuq javob)."""


# Ajratuvchi belgilar: katalogda `ПВН 500-250-2`, SAP jadvalida
# `ПВН 500-250/2`. Taqqoslash uchun ikkalasini bir ko'rinishga keltiramiz.
_AJRATUVCHI = re.compile(r"[\s\-/_.]+")


def sap_kaliti(nom: Any) -> str:
    """Nomni taqqoslash kalitiga aylantiradi (ajratuvchilarsiz, katta harfda)."""
    return _AJRATUVCHI.sub("", str(nom or "")).upper()


def matn(obyekt: dict[str, Any], asos: str, til: str = "uz") -> str:
    """Ko'p tilli maydondan matn oladi: `name_uz` -> `name_ru` -> `name_en`."""
    tartib = (til, *(t for t in TIL_TARTIBI if t != til))
    for t in tartib:
        qiymat = obyekt.get(f"{asos}_{t}")
        if isinstance(qiymat, str) and qiymat.strip():
            return qiymat.strip()
    qiymat = obyekt.get(asos)
    return qiymat.strip() if isinstance(qiymat, str) else ""


class _Kesh:
    """Juda oddiy TTL kesh (katalog tez-tez o'zgarmaydi)."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._malumot: dict[str, tuple[float, Any]] = {}
        self._qulf = asyncio.Lock()

    async def ol(self, kalit: str) -> Any | None:
        async with self._qulf:
            yozuv = self._malumot.get(kalit)
            if yozuv is None:
                return None
            vaqt, qiymat = yozuv
            if time.monotonic() - vaqt > self.ttl:
                self._malumot.pop(kalit, None)
                return None
            return qiymat

    async def qoy(self, kalit: str, qiymat: Any) -> None:
        async with self._qulf:
            self._malumot[kalit] = (time.monotonic(), qiymat)

    def yangi_ttl(self, ttl: float) -> None:
        self.ttl = ttl

    async def tozala(self) -> None:
        async with self._qulf:
            self._malumot.clear()


# Katalogni sahifama-sahifa o'qish. Backend `/api/products/all` ga
# standart chegara (20) qo'ygan — parametrsiz chaqiruv butun katalogni
# bermaydi.
SAHIFA_HAJMI = 100
# Cheksiz tsikl bo'lmasin: 100 × 100 = 10 000 mahsulot yetarlidan ortiq.
MAKS_SAHIFA = 100


# Jarayon bo'yicha bitta umumiy kesh — pastdagi izohga qarang.
_UMUMIY_KESH = _Kesh(sozlama().climavent_kesh_ttl)


class ClimaventKlient:
    """Climavent backend bilan ishlash (faqat o'qish)."""

    def __init__(
        self,
        asos: str | None = None,
        token: str | None = None,
        mijoz: httpx.AsyncClient | None = None,
        kesh_ttl: float | None = None,
    ):
        s = sozlama()
        self.asos = (asos or s.climavent_api_asos).rstrip("/")
        self.token = token if token is not None else s.climavent_token
        self.kutish = s.climavent_kutish
        self._mijoz = mijoz
        # KESH JARAYON BO'YICHA UMUMIY.
        #
        # Ilgari har nusxaning o'z keshi bor edi. Har agent esa o'ziga yangi
        # klient yasaydi (`asos.py`, `orkestr.py`), shuning uchun katalog
        # HAR so'rovda qaytadan yuklanardi — 11.5 s (137 mahsulot + 1482
        # model). TTL qancha uzun bo'lmasin, foydasi yo'q edi.
        #
        # Endi kesh modul darajasida: bir agent yuklasa, qolganlari tayyor
        # oladi va tizim yoqilishida oldindan isitib qo'yish ham ishlaydi.
        # `kesh_ttl` ochiq berilgan bo'lsa (testlar) — alohida kesh, aks
        # holda testlar bir-birining ma'lumotini ko'rib qolardi.
        if kesh_ttl is not None:
            self._kesh = _Kesh(kesh_ttl)
        else:
            _UMUMIY_KESH.yangi_ttl(s.climavent_kesh_ttl)
            self._kesh = _UMUMIY_KESH
        # Ma'lumot to'liq olinmagan bo'lsa shu yerga yoziladi (agent uni
        # javobda ko'rsatadi — jimgina chala ma'lumot bermaymiz).
        self.ogohlantirish: str = ""

    # --- ichki ---------------------------------------------------------------

    def _sarlavhalar(self) -> dict[str, str]:
        sarlavhalar = {"Accept": "application/json"}
        if self.token:
            sarlavhalar["Authorization"] = f"Bearer {self.token}"
        return sarlavhalar

    async def _sorov(self, metod: str, yol: str, tana: dict[str, Any] | None = None) -> Any:
        kalit = f"{metod} {yol} {tana or ''}"
        keshdan = await self._kesh.ol(kalit)
        if keshdan is not None:
            return keshdan

        manzil = f"{self.asos}{yol}"
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.request(
                    metod, manzil, json=tana, headers=self._sarlavhalar(), timeout=self.kutish
                )
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.request(
                        metod, manzil, json=tana, headers=self._sarlavhalar()
                    )
        except httpx.HTTPError as xato:
            raise ApiXatosi(f"Ichki API'ga ulanib bo'lmadi ({yol}): {xato}") from xato

        if javob.status_code >= 400:
            raise ApiXatosi(
                f"Ichki API xatosi ({yol}): HTTP {javob.status_code} {javob.text[:200]}"
            )

        try:
            malumot = javob.json()
        except ValueError as xato:
            raise ApiXatosi(f"Ichki API buzuq javob qaytardi ({yol}): {xato}") from xato

        await self._kesh.qoy(kalit, malumot)
        return malumot

    @staticmethod
    def _royxat(malumot: Any) -> list[dict[str, Any]]:
        """Javobni ro'yxatga keltiradi (API ba'zan o'ram bilan qaytaradi)."""
        if isinstance(malumot, list):
            return [x for x in malumot if isinstance(x, dict)]
        if isinstance(malumot, dict):
            for kalit in ("rows", "data", "products", "items", "result"):
                ichki = malumot.get(kalit)
                if isinstance(ichki, list):
                    return [x for x in ichki if isinstance(x, dict)]
        return []

    # --- ochiq metodlar (faqat o'qish) ---------------------------------------

    async def kurs(self) -> float | None:
        """Saytdagi joriy dollar kursi (`settings.usd-rate`).

        MANBA SHU YERDA, sozlamada emas. Narx bazada dollarda saqlanib,
        so'mga kursga ko'paytirib hisoblangani uchun bot bilan sayt bir
        xil raqamdan foydalanishi SHART — aks holda mijoz saytda bir
        narx, KP da boshqa narx ko'radi.

        Ilgari kurs faqat `sozlama().usd_kursi` da turardi va u
        backenddagi qiymat bilan mustaqil o'zgarardi.

        Olinmasa `None` qaytaradi — chaqiruvchi zaxira qiymatga o'tadi
        va buni jimgina emas, ochiq qiladi.
        """
        try:
            malumot = await self._sorov("GET", "/api/settings/usd-rate")
        except ApiXatosi:
            return None
        if not isinstance(malumot, dict):
            return None
        try:
            qiymat = float(malumot.get("rate"))
        except (TypeError, ValueError):
            return None
        return qiymat if qiymat > 0 else None

    async def mahsulotlar(self) -> list[dict[str, Any]]:
        """Butun katalog — SAHIFAMA-SAHIFA yig'iladi.

        DIQQAT, bu shunchaki optimizatsiya emas. Backend 2026-08-06 da
        `/api/products/all` ga STANDART CHEGARA (20 ta) qo'ydi — buni biz
        so'ragan edik, sahifa 698 KB yuklamasin deb.

        Natijada klient jimgina 137 mahsulot o'rniga 20 tasini olib
        qoldi va bu butun zanjirni buzdi:
          - Rustam Ø315 uchun bironta uskuna topa olmadi (ro'yxat bo'sh);
          - Temur o'zi qidirib, omborga SHAXTA ventilyatorini tanladi.

        Xatolik hech qayerda ko'rinmadi — API 200 qaytardi, shunchaki
        ma'lumot kam edi. Shuning uchun endi sahifalar oxirigacha
        o'qiladi va to'liqligi tekshiriladi.
        """
        kesh = await self._kesh.ol("mahsulotlar")
        if kesh is not None:
            return kesh

        yigilgan = await self._sahifalab("/api/products/all", "katalog")
        await self._kesh.qoy("mahsulotlar", yigilgan)
        return yigilgan

    async def _sahifalab(self, yol: str, nomi: str) -> list[dict[str, Any]]:
        """Sahifama-sahifa to'liq ro'yxat.

        HAR BIR ro'yxat endpointi shu orqali o'qiladi. Sababi ikki marta
        isbotlangan:

          2026-08-06 — backend `/api/products/all` ga standart chegara
          (20 ta) qo'ydi. Klient parametrsiz so'rardi va 137 o'rniga 20 ta
          oldi. API 200 qaytardi, xato hech qayerda ko'rinmadi — shunchaki
          Rustam Ø315 ga uskuna topa olmay qoldi.

          2026-08-11 — backend `product-models/all` ga ham sahifalash
          qo'shdi (buni ham biz so'ragan edik). Endi parametrsiz so'rov
          1482 o'rniga 50 ta qaytaradi — ya'ni narx va SAP kodi
          modellarning 3% ida qidirilardi.

        Xulosa: ro'yxatni parametrsiz so'ramaymiz. Hech qachon.
        """
        yigilgan: list[dict[str, Any]] = []
        ajratgich = "&" if "?" in yol else "?"
        for sahifa in range(1, MAKS_SAHIFA + 1):
            bolak = self._royxat(
                await self._sorov(
                    "GET", f"{yol}{ajratgich}limit={SAHIFA_HAJMI}&page={sahifa}"
                )
            )
            yigilgan.extend(bolak)
            if len(bolak) < SAHIFA_HAJMI:
                break
        else:
            self.ogohlantirish = (
                f"{nomi} {MAKS_SAHIFA} sahifadan uzun — hammasi o'qilmadi"
            )
        return yigilgan

    async def mahsulotlar_soni(self) -> int:
        malumot = await self._sorov("GET", "/api/products/allcount")
        if isinstance(malumot, int):
            return malumot
        if isinstance(malumot, dict):
            for kalit in ("count", "total", "soni"):
                if isinstance(malumot.get(kalit), int):
                    return malumot[kalit]
        try:
            return int(malumot)
        except (TypeError, ValueError):
            raise ApiXatosi(f"Mahsulot sonini o'qib bo'lmadi: {malumot!r}") from None

    async def mahsulot(self, mahsulot_id: int) -> dict[str, Any]:
        malumot = await self._sorov("GET", f"/api/products/one/{int(mahsulot_id)}")
        if not isinstance(malumot, dict) or not malumot:
            raise ApiXatosi(f"Mahsulot topilmadi: id={mahsulot_id}")
        return malumot

    async def qidir(self, matn_sorovi: str) -> list[dict[str, Any]]:
        """Matn bo'yicha mahsulot qidirish."""
        return self._royxat(
            await self._sorov("POST", "/api/products/search", {"text": matn_sorovi})
        )

    async def kategoriyalar(self) -> list[dict[str, Any]]:
        return self._royxat(await self._sorov("GET", "/api/category/all"))

    async def kategoriya_mahsulotlari(
        self, kategoriya_id: int, chek: int = 50, sahifa: int = 1
    ) -> list[dict[str, Any]]:
        return self._royxat(
            await self._sorov(
                "POST",
                "/api/products/categoryslug",
                {
                    "category_id": int(kategoriya_id),
                    "limit": int(chek),
                    "page": int(sahifa),
                    "price": "asc",
                },
            )
        )

    async def model_boyicha_qidir(self, kod: str) -> list[dict[str, Any]]:
        """Model kodi bo'yicha qidiradi (masalan "VK-250").

        Katalogda model kodlari mahsulot NOMIDA emas, `models[].name` va
        `characters[].title` ichida turadi va kirillcha yozilgan. Shuning
        uchun API qidiruvi ularni topa olmaydi — butun katalogni (keshdan)
        o'zimiz ko'rib chiqamiz.
        """
        if not kalitla(kod):
            return []

        topilgan: list[dict[str, Any]] = []
        for mahsulot in await self.mahsulotlar():
            nomzodlar = [matn(mahsulot, "name", til) for til in TIL_TARTIBI]
            nomzodlar += [
                m.get("name", "") for m in (mahsulot.get("models") or []) if isinstance(m, dict)
            ]
            nomzodlar += [
                x.get("title", "")
                for x in (mahsulot.get("characters") or [])
                if isinstance(x, dict)
            ]
            if any(_mos_keladimi(kod, n) for n in nomzodlar if n):
                topilgan.append(mahsulot)
        return topilgan

    async def sap_kodlari(self) -> dict[str, str]:
        """Model nomi -> rasmiy SAP kodi.

        YAGONA MANBA — `product_model_inside` (`artikullar()`).

        Ilgari birinchi navbatda `product_models.sap_name` o'qilardi.
        Backend o'sha jadvalni butunlay olib tashladi (2026-09-09) va
        chaqiruv 404 qaytarardi — natija jimgina shu manbaga tushardi.
        Endi u zaxira emas, asosiy va yagona.

        Bog'lanish NOM bo'yicha quriladi: yozuvdagi `product_model_id`
        `characteristics.id` ga ishora qiladi va tarixan ishonchsiz
        bo'lgan. Batafsil: docs/backend-topshiriq-2.md, 1.5-bo'lim.

        Nomlar ajratuvchi belgi bilan farq qiladi (`ПВН 500-250-2` va
        `ПВН 500-250/2`), shuning uchun taqqoslashdan oldin
        `sap_kaliti()` bilan soddalashtiriladi.
        """
        kesh = await self._kesh.ol("sap")
        if kesh is not None:
            return kesh

        # Bir kalitga ikki xil kod tushsa — ishlatmaymiz. Noto'g'ri kod
        # mijozga ketgandan ko'ra, kodsiz chiqqani yaxshi.
        yigilgan: dict[str, set[str]] = {}

        def qosh(kalit_manbasi: Any, sap: str) -> None:
            kalit = sap_kaliti(kalit_manbasi)
            if kalit and sap:
                yigilgan.setdefault(kalit, set()).add(sap)

        # YAGONA MANBA: `product-model-inside`.
        #
        # Ilgari bundan oldin `modellar()` (`/api/product-models/all`)
        # o'qilardi. O'sha jadval backenddan olib tashlangan — chaqiruv
        # 404 qaytarib, natija jimgina shu zaxira manbaga tushardi.
        # Endi zaxira emas, asosiy.
        for yozuv in await self.artikullar():
            if not isinstance(yozuv, dict):
                continue
            sap = str(yozuv.get("sap_name") or "").strip()
            if not sap:
                continue
            qosh(yozuv.get("in_model_name"), sap)
            qosh(sap, sap)

        karta = {k: next(iter(v)) for k, v in yigilgan.items() if len(v) == 1}
        await self._kesh.qoy("sap", karta)
        return karta

    # `modellar()` OLIB TASHLANDI (2026-09-09).
    #
    # U `/api/product-models/all` ni o'qirdi; backend o'sha jadvalni
    # butunlay olib tashlagan va yo'l 404 qaytaradi. Metodni saqlab
    # turish zararli edi: chaqiruvchilar `ApiXatosi` ni ushlab, jimgina
    # chala ma'lumot bilan davom etardi (texnik parametrlar 14 kun
    # muzlab qolgani aynan shundan).
    #
    # Uning vazifasi ikkiga bo'lindi:
    #   model nomi + texnik jadval  -> `products` dagi `characters[]`
    #                                  (`title` va `contentJson`);
    #   SAP kodi + artikul narxi    -> `/api/product-model-inside`.

    async def artikullar(self) -> list[dict[str, Any]]:
        """Buyurtma qilinadigan artikullar (`/api/product-model-inside`).

        Har yozuvda: `sap_name`, `in_model_name`, `price` (DOLLARDA) va
        `product_model_id` — u `characteristics.id` ga ishora qiladi,
        `product_models.id` ga EMAS (nomi aldaydi).

        Bu ro'yxat ikki joyda kerak — SAP kodlari va texnik parametrlar
        uchun model NOMLARI — shuning uchun alohida metod va keshlanadi.
        """
        kesh = await self._kesh.ol("artikullar")
        if kesh is not None:
            return kesh

        try:
            yozuvlar = await self._sahifalab(
                "/api/product-model-inside", "model ichki yozuvlari"
            )
        except ApiXatosi:
            return []
        if not isinstance(yozuvlar, list):
            yozuvlar = (yozuvlar or {}).get("data") or []
        yozuvlar = [y for y in yozuvlar if isinstance(y, dict)]
        await self._kesh.qoy("artikullar", yozuvlar)
        return yozuvlar

    async def sap_kodi(self, nom: str) -> str:
        """Bitta model nomi uchun SAP kodi (topilmasa bo'sh matn)."""
        kalit = sap_kaliti(nom)
        return (await self.sap_kodlari()).get(kalit, "") if kalit else ""

    async def model_narxi(self, nom: str) -> tuple[float, str] | None:
        """Model nomi bo'yicha narx: (narx, topilgan yozuv nomi).

        DIQQAT: qidiruv endpointi (`/api/products/search`) mahsulotni
        `models` massivisiz qaytaradi, ya'ni uning natijasida narx UMUMAN
        bo'lmaydi. Narx faqat `/api/products/all` da bor — shuning uchun
        narx har doim shu yerdan (keshdan) qidiriladi.
        """
        if not nom:
            return None
        return katalog_narxi(await self.mahsulotlar(), nom)

    async def qidir_keng(self, sorov: str) -> list[dict[str, Any]]:
        """Qidiruv, moslashuvchan.

        API qidiruvi oddiy matn mosligiga tayanadi: "kanal ventilyatori" hech
        narsa topmaydi, "ventilyator" esa 40 ta topadi. Model kodlari esa
        umuman qidiruvga tushmaydi. Shuning uchun tartib:
          1) model kodiga o'xshash bo'lak bo'yicha katalogni ko'rib chiqamiz
             (eng aniq natija);
          2) to'liq so'rov bilan API qidiruvi;
          3) so'zma-so'z, uzunidan boshlab.
        """
        sorov = (sorov or "").strip()
        if not sorov:
            return []

        bolaklar = [b.strip(".,;:!?()[]") for b in sorov.split()]
        # Raqam va harf aralash bo'lak — odatda model kodi (VK-250, ВКР-4).
        kodlar = [
            b for b in bolaklar
            if any(ch.isdigit() for ch in b) and any(ch.isalpha() for ch in b)
        ]
        # Model kodi ikki bo'lakka bo'linib yozilishi mumkin: "ПВН 500-250-2"
        # — harfli bo'lak + raqamli bo'lak. Bittasida ham harf-raqam aralashmasa,
        # bu holat butunlay e'tibordan chetda qolardi.
        for oldingi, keyingi in zip(bolaklar, bolaklar[1:]):
            if (
                any(ch.isalpha() for ch in oldingi)
                and any(ch.isdigit() for ch in keyingi)
                and not any(ch.isdigit() for ch in oldingi)
            ):
                kodlar.append(f"{oldingi} {keyingi}")

        for kod in kodlar:
            topilgan = await self.model_boyicha_qidir(kod)
            if topilgan:
                return topilgan

        nomzodlar = [sorov, *kodlar]
        sozlar = [b for b in bolaklar if len(b) > 2 and b not in kodlar]
        nomzodlar.extend(sorted(sozlar, key=len, reverse=True))

        korilgan: set[str] = set()
        for nomzod in nomzodlar:
            kalit = nomzod.lower()
            if not nomzod or kalit in korilgan:
                continue
            korilgan.add(kalit)
            topilgan = await self.qidir(nomzod)
            if topilgan:
                return topilgan
        return []

    async def xususiyat_matni(self, havola: str) -> str:
        """R2 dagi boy matn hujjatini o'qiladigan matnga aylantiradi.

        `characters[].contentJson` — ProseMirror/TipTap hujjati bo'lib,
        ichida texnik xususiyatlar jadvali turadi.
        """
        if not havola or not str(havola).startswith("http"):
            return ""
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.get(str(havola), timeout=self.kutish)
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.get(str(havola))
            javob.raise_for_status()
            return hujjat_matni(javob.json())
        except (httpx.HTTPError, ValueError):
            # Xususiyat fayli ochilmasa — bu xato emas, shunchaki bo'sh.
            return ""

    async def mahsulot_xususiyatlari(
        self, mahsulot: dict[str, Any], maks: int = 4
    ) -> list[dict[str, Any]]:
        """Mahsulotning texnik xususiyatlari (R2 fayllari ochilgan holda)."""
        natija: list[dict[str, Any]] = []
        for xususiyat in (mahsulot.get("characters") or [])[:maks]:
            if not isinstance(xususiyat, dict):
                continue
            mazmun = xususiyat.get("content") or ""
            if str(mazmun).startswith("http"):
                mazmun = await self.xususiyat_matni(
                    xususiyat.get("contentJson") or xususiyat.get("content")
                )
            natija.append({"nomi": xususiyat.get("title") or "", "qiymat": mazmun})
        return natija

    async def katalog_xulosasi(self, til: str = "uz") -> dict[str, Any]:
        """Katalog bo'yicha yig'ma ko'rsatkichlar (shaxsiy ma'lumotsiz).

        Doston shu xulosaga tayanadi: mahsulot soni, kategoriya taqsimoti,
        ombor holati va narx to'ldirilganligi.
        """
        mahsulotlar = await self.mahsulotlar()

        kategoriyalar: dict[str, int] = {}
        ombordagi = 0
        narxli = 0
        for mahsulot in mahsulotlar:
            kategoriya = mahsulot.get("category") or {}
            nomi = matn(kategoriya, "name", til) or "(kategoriyasiz)"
            kategoriyalar[nomi] = kategoriyalar.get(nomi, 0) + 1
            try:
                ombordagi += int(mahsulot.get("quantity") or 0)
            except (TypeError, ValueError):
                pass
            if narx_bormi(mahsulot):
                narxli += 1

        return {
            "mahsulotlar_soni": len(mahsulotlar),
            "kategoriyalar_soni": len(kategoriyalar),
            "kategoriya_boyicha": dict(
                sorted(kategoriyalar.items(), key=lambda x: -x[1])
            ),
            "ombordagi_jami": ombordagi,
            "narxi_toldirilgan": narxli,
            "narxi_bosh": len(mahsulotlar) - narxli,
        }

    # --- texnik parametrlar (havo sarfi, bosim) ------------------------------

    def _fonda_yangila(self) -> None:
        """Texnik keshni fonda yangilaydi (bir vaqtda faqat bittasi)."""
        global _TEXNIK_YANGILASH
        if _TEXNIK_YANGILASH is not None and not _TEXNIK_YANGILASH.done():
            return
        try:
            halqa = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def ishla() -> None:
            try:
                await self.texnik_parametrlar(yangila=True)
                log.info("texnik kesh fonda yangilandi")
            except Exception:                      # noqa: BLE001
                # Fon vazifasi hech qachon asosiy oqimni yiqitmasligi kerak.
                log.exception("texnik keshni fonda yangilab bo'lmadi")

        _TEXNIK_YANGILASH = halqa.create_task(ishla())

    async def texnik_parametrlar(
        self, yangila: bool = False
    ) -> dict[str, dict[str, Any]]:
        """`{model nomi: {havo_sarfi, bosim, quvvat_kvt}}` — butun katalog.

        Backendda bu maydonlar YO'Q (`docs/backend-topshiriq-5.md`, 1-bo'lim).
        Ma'lumot faqat `characters[].contentJson` → R2 dagi jadvalda turadi,
        shuning uchun uni o'zimiz o'qib olamiz.

        QIMMAT: 137 mahsulot × (1 ta `products/one` + 1-3 ta R2 fayl) —
        taxminan 4 daqiqa. Shu sababli natija DISKKA keshlanadi va
        `texnik_kesh_kunlari` davomida qayta yig'ilmaydi.
        """
        if not yangila:
            keshdan = _texnik_keshdan_oqi(eskirgan_ham=True)
            if keshdan is not None:
                parametrlar, eskirgan = keshdan
                if eskirgan:
                    # ESKIRGAN KESHNI HAM QAYTARAMIZ.
                    #
                    # Qayta yig'ish 2-4 daqiqa turadi. Ilgari muddat o'tgan
                    # zahoti KEYINGI so'rov shuncha kutardi — menejer uchun
                    # tizim "osilib qolgan" ko'rinardi, kunlar davomida bir
                    # marta. Endi eski ma'lumot darrov beriladi, yangisi
                    # fonda yig'iladi. Katalog kamdan-kam o'zgaradi,
                    # shuning uchun bir necha daqiqalik eskilik zararsiz.
                    self._fonda_yangila()
                return parametrlar

        try:
            mahsulotlar = await self.mahsulotlar()
        except ApiXatosi:
            return {}

        # MODEL NOMLARI XUSUSIYATDAN OLINADI.
        #
        # 2026-09-09 gacha ular `/api/product-models/all` dan kelardi va
        # o'sha endpointda `airflow_m3h` / `pressure_pa` ustunlari ham
        # bor edi. Backend o'sha jadvalni BUTUNLAY olib tashladi — yo'l
        # 404 qaytaradi.
        #
        # Buzilish jimgina kechgan: bu yerdagi `except ApiXatosi: return {}`
        # ishga tushib, funksiya ERTA chiqib ketardi va pastdagi R2
        # jadvallari ham o'qilmasdi. Kesh esa muvaffaqiyatli yo'lning
        # oxirida yozilgani uchun eskisi joyida qolar, jurnalga "texnik
        # kesh fonda yangilandi" deb yozilardi. Natijada tizim 2026-08-26
        # dagi suratda muzlab qolgan va buni hech narsa ko'rsatmagan.
        #
        # Endi nomlar `characters[].title` dan olinadi — o'sha yozuvning
        # `contentJson` maydoni allaqachon shu yerda o'qilayotgan R2
        # hujjatiga ishora qiladi, ya'ni nom va jadval bir manbadan
        # keladi va ular bir-biriga kafolatlangan holda mos tushadi.
        #
        # HAVO SARFI/BOSIM uchun backend maydonlari ham SHU YERDA.
        #
        # `airflow_m3h` va `pressure_pa` ustunlari yo'qolmagan — ular
        # `product_models` dan `characteristics` ga KO'CHGAN. Boshida
        # ularni butunlay yo'q deb o'ylab, shoxni olib tashlagandim; jonli
        # o'lchov buni rad etdi: 342 xususiyatdan 71 tasida havo sarfi,
        # 67 tasida bosim to'ldirilgan.
        # NOMZOD NOMLAR IKKI MANBADAN.
        #
        # Faqat `characters[].title` bilan cheklansak qamrov keskin
        # tushadi: o'lchandi — 342 nomzod bilan atigi 73 model topildi,
        # eski keshda esa jadvaldan kelgan 196 tasi bor edi. Sabab
        # oddiy: jadvalda `ВЦ 4-75-2,5-О-1-0,37/1500` kabi TO'LIQ
        # artikul nomlari uchraydi, xususiyat sarlavhasi esa qisqa
        # (`ВЦ 4-75-2,5`).
        #
        # Shuning uchun artikul nomlari ham qo'shiladi. Ular
        # `product_model_id` orqali XUSUSIYATGA bog'lanadi (nomi
        # aldaydi — u `characteristics.id`), xususiyat esa mahsulotga.
        artikullar = await self.artikullar()
        xususiyat_mahsuloti: dict[Any, Any] = {}
        for mahsulot in mahsulotlar:
            for x in mahsulot.get("characters") or []:
                if isinstance(x, dict) and x.get("id") is not None:
                    xususiyat_mahsuloti[x["id"]] = mahsulot.get("id")

        artikul_nomlari: dict[Any, list[str]] = {}
        for yozuv in artikullar:
            mahsulot_id = xususiyat_mahsuloti.get(yozuv.get("product_model_id"))
            if mahsulot_id is None:
                continue
            for kalit in ("in_model_name", "sap_name"):
                nomi = str(yozuv.get(kalit) or "").strip()
                if nomi:
                    artikul_nomlari.setdefault(mahsulot_id, []).append(nomi)

        yigilgan: dict[str, dict[str, Any]] = {}
        for mahsulot in mahsulotlar:
            nomzodlar = [
                nomi
                for x in (mahsulot.get("characters") or [])
                if isinstance(x, dict) and (nomi := str(x.get("title") or "").strip())
            ]
            nomzodlar.extend(artikul_nomlari.get(mahsulot.get("id")) or [])
            # Takrorlarni olib tashlaymiz, tartibni saqlaymiz.
            nomzodlar = list(dict.fromkeys(nomzodlar))
            if not nomzodlar:
                continue
            xom: list[ModelParametri] = []
            for xususiyat in (mahsulot.get("characters") or [])[:MAKS_TEXNIK_HUJJAT]:
                if not isinstance(xususiyat, dict):
                    continue
                hujjat = await self._hujjat_json(xususiyat.get("contentJson"))
                if hujjat is not None:
                    xom.extend(
                        hujjatdan_parametrlar(hujjat, manba=str(mahsulot.get("id")))
                    )
            turi = mahsulot_qisqa(mahsulot)["nomi"]
            for nomi, parametr in moslashtir(xom, nomzodlar).items():
                yigilgan[nomi] = {
                    **parametr.dict_holida(), "turi": turi, "manba": "jadval",
                }

        # BACKEND QIYMATI — jadval bermagan joyni to'ldiradi.
        #
        # ZIDLIKDA JADVAL OLINADI: backend ustuniga aylanish tezligi
        # tushib qolgan holatlar o'lchangan (`_zid_keladimi` izohiga
        # qarang), jadval esa ishlab chiqaruvchining o'z ma'lumoti.
        zidlar: list[str] = []
        for mahsulot in mahsulotlar:
            turi = mahsulot_qisqa(mahsulot)["nomi"]
            for x in mahsulot.get("characters") or []:
                if not isinstance(x, dict):
                    continue
                nomi = str(x.get("title") or "").strip()
                havo = _musbat(x.get("airflow_m3h"))
                if not nomi or havo is None:
                    continue
                bosim = _musbat(x.get("pressure_pa"))
                yozuv: dict[str, Any] = {
                    "model": nomi, "havo_sarfi": havo,
                    "turi": turi, "manba": "backend",
                }
                if bosim is not None:
                    yozuv["bosim"] = bosim

                oldingi = yigilgan.get(nomi)
                if oldingi is None:
                    yigilgan[nomi] = yozuv
                    continue
                if _zid_keladimi(havo, oldingi.get("havo_sarfi")):
                    zidlar.append(nomi)
                    oldingi["backend_zid"] = havo
                    continue
                yigilgan[nomi] = yozuv

        if zidlar:
            log.warning(
                "backend havo sarfi jadvalga zid (%d ta, jadval olindi): %s",
                len(zidlar), ", ".join(sorted(zidlar)[:8]),
            )

        # BO'SH NATIJANI KESHGA YOZMAYMIZ.
        #
        # Aks holda bitta muvaffaqiyatsiz yig'ish 297 yozuvlik ishlaydigan
        # keshni bo'sh fayl bilan almashtirib yuborardi va Rustam butunlay
        # ma'lumotsiz qolardi. Eski ma'lumot — bo'sh ma'lumotdan yaxshi.
        if not yigilgan:
            log.warning(
                "texnik parametrlar yig'ilmadi (0 model) — eski kesh saqlanadi"
            )
            return {}

        backend_soni = sum(
            1 for v in yigilgan.values() if v.get("manba") == "backend"
        )
        log.info(
            "texnik parametrlar: %d model (backend: %d, jadval: %d, zid: %d)",
            len(yigilgan), backend_soni, len(yigilgan) - backend_soni,
            len(zidlar),
        )
        _texnik_keshga_yoz(yigilgan)
        return yigilgan

    async def _hujjat_json(self, havola: Any) -> Any | None:
        """R2 dagi ProseMirror hujjatini oladi (ochilmasa None)."""
        if not (isinstance(havola, str) and havola.startswith("http")):
            return None
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.get(havola, timeout=self.kutish)
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.get(havola)
            javob.raise_for_status()
            return javob.json()
        except (httpx.HTTPError, ValueError):
            # Bitta fayl ochilmasa qolganlari baribir o'qiladi.
            return None

    async def keshni_tozala(self) -> None:
        await self._kesh.tozala()


# --- texnik parametrlar keshi (diskda) ---------------------------------------
#
# Yig'ish ~4 daqiqa turadi, katalog esa oyiga bir marta o'zgaradi. Bot qayta
# ishga tushganda uni qaytadan yig'ish ma'nosiz — shuning uchun natija JSON
# faylga yoziladi.


def _musbat(qiymat: Any) -> float | None:
    """Musbat son bo'lsa qaytaradi, aks holda `None`.

    Nol "to'ldirilmagan" degani, "sarfi nol" emas — shuning uchun u ham
    `None` ga tushadi.
    """
    try:
        son = float(str(qiymat).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return son if son > 0 else None


# Jadval qiymati oralig'idan chetga chiqishga ruxsat (10%).
ZIDLIK_BOSHASHUVI = 0.1


def _zid_keladimi(backend: Any, jadval: Any) -> bool:
    """Backend qiymati jadval oralig'iga to'g'ri kelmayaptimi.

    NEGA KERAK — jonli o'lchov (2026-08-11): ikkala manbada ham qiymat
    bor 91 modeldan 18 tasida backend qiymati jadval oralig'idan
    tashqarida edi va xato TIZIMLI — aylanish tezligi (об/мин) havo
    sarfi o'rniga tushgan:

        ВО 12-300-3,15 / -4 / -5  ->  uchalasida ham "1500"
        ВКР-4, ВКР-5              ->  ikkalasida ham "1000"
        ВНР-10-22-1000            ->  "22"  (nomdagi son)

    Bir o'lchamdagi uch xil ventilyatorning havo sarfi bir xil
    bo'lmaydi — bu aniq belgi.

    O'lchab bo'lmaydigan holat (biror tomoni yo'q) zid HISOBLANMAYDI:
    shubha ustiga xato qo'shmaymiz.
    """
    b = _musbat(backend)
    if b is None or jadval is None:
        return False
    qiymatlar = jadval if isinstance(jadval, (list, tuple)) else [jadval]
    sonlar = [s for s in (_musbat(q) for q in qiymatlar) if s is not None]
    if not sonlar:
        return False
    past = min(sonlar) * (1 - ZIDLIK_BOSHASHUVI)
    yuqori = max(sonlar) * (1 + ZIDLIK_BOSHASHUVI)
    return not (past <= b <= yuqori)


def _texnik_kesh_fayli() -> Path:
    return sozlama().texnik_kesh_fayli


def _texnik_keshdan_oqi(
    eskirgan_ham: bool = False,
) -> tuple[dict[str, dict[str, Any]], bool] | None:
    """Keshdagi parametrlar va u eskirganmi.

    `eskirgan_ham=True` bo'lsa muddati o'tgan kesh ham qaytariladi — uni
    darhol ishlatib, yangilashni FONDA qilamiz (pastga qara).
    """
    fayl = _texnik_kesh_fayli()
    try:
        malumot = json.loads(fayl.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    yozilgan = malumot.get("yozilgan")
    parametrlar = malumot.get("parametrlar")
    if not isinstance(parametrlar, dict) or not isinstance(yozilgan, (int, float)):
        return None
    eskirgan = time.time() - yozilgan > sozlama().texnik_kesh_kunlari * 86400
    if eskirgan and not eskirgan_ham:
        return None
    return parametrlar, eskirgan


def _texnik_keshga_yoz(parametrlar: dict[str, dict[str, Any]]) -> None:
    fayl = _texnik_kesh_fayli()
    try:
        fayl.parent.mkdir(parents=True, exist_ok=True)
        fayl.write_text(
            json.dumps(
                {"yozilgan": time.time(), "parametrlar": parametrlar},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError as xato:
        # Kesh yozilmasa ish to'xtamaydi — faqat keyingi safar sekinroq.
        log.warning("texnik kesh yozilmadi: %s", xato)


# --- agentlar uchun qulay ko'rinishlar ---------------------------------------


def mahsulot_qisqa(mahsulot: dict[str, Any], til: str = "uz") -> dict[str, Any]:
    """Mahsulotni agent promptiga sig'adigan qisqa ko'rinishga keltiradi."""
    kategoriya = mahsulot.get("category") or {}
    return {
        "id": mahsulot.get("id"),
        "nomi": matn(mahsulot, "name", til),
        "tavsif": matn(mahsulot, "description_short", til),
        "kategoriya": matn(kategoriya, "name", til) if kategoriya else "",
        "ishlab_chiqaruvchi": mahsulot.get("producer") or "",
        "ombor": mahsulot.get("quantity"),
        # MODEL NOMLARI IKKI JOYDAN.
        #
        # `models` maydoni backenddan yo'qolgan — o'lchandi (2026-09-09):
        # 177 mahsulotning HECH BIRIDA yo'q. Ya'ni bu ro'yxat har doim
        # bo'sh chiqardi va agentlar promptida bironta model nomi
        # ko'rinmasdi. Nomlar endi `characters[].title` da.
        #
        # `models` baribir birinchi o'qiladi: qaytsa ishlayveradi.
        "modellar": list(dict.fromkeys(
            [
                nomi
                for m in (mahsulot.get("models") or []) if isinstance(m, dict)
                if (nomi := str(m.get("name") or "").strip())
            ] + [
                nomi
                for x in (mahsulot.get("characters") or []) if isinstance(x, dict)
                if (nomi := str(x.get("title") or "").strip())
            ]
        )),
    }


def hujjat_matni(tugun: Any) -> str:
    """ProseMirror/TipTap hujjatidan o'qiladigan matn ajratadi.

    Jadval qatorlari `|` bilan ajratiladi — texnik xususiyatlar jadvali shu
    ko'rinishda o'qilishi oson bo'ladi.
    """
    if isinstance(tugun, str):
        return tugun
    if isinstance(tugun, list):
        return "\n".join(q for q in (hujjat_matni(x) for x in tugun) if q)
    if not isinstance(tugun, dict):
        return ""

    tur = tugun.get("type")
    if tur == "text":
        return str(tugun.get("text") or "")

    ichi = tugun.get("content") or []

    if tur in ("tableHeader", "tableCell"):
        # Katak ichidagi matnni bitta qatorga yig'amiz.
        return " ".join(q for q in (hujjat_matni(x) for x in ichi) if q).strip()
    if tur == "tableRow":
        kataklar = [hujjat_matni(x) for x in ichi]
        return " | ".join(k for k in kataklar if k)

    bolaklar = [hujjat_matni(x) for x in ichi]
    ajratgich = "\n" if tur in ("doc", "table", "bulletList", "orderedList") else " "
    return ajratgich.join(b for b in bolaklar if b).strip()


def xususiyatlar_qisqa(mahsulot: dict[str, Any]) -> list[dict[str, Any]]:
    """`characters[]` ni xususiyat ro'yxatiga aylantiradi."""
    natija: list[dict[str, Any]] = []
    for xususiyat in mahsulot.get("characters") or []:
        if not isinstance(xususiyat, dict):
            continue
        natija.append(
            {
                "nomi": xususiyat.get("title") or "",
                "qiymat": xususiyat.get("content") or "",
            }
        )
    return natija


def _narx_soni(qiymat: Any) -> float:
    """API narxni matn ("1200000") yoki son sifatida qaytaradi."""
    try:
        son = float(str(qiymat).replace(" ", "").replace(",", ".") or 0)
    except (TypeError, ValueError):
        return 0.0
    return son if son > 0 else 0.0


def _ichki_variantlar(
    mahsulot: dict[str, Any]
) -> list[tuple[str, float]]:
    """`characters[].insides[]` — variant narxlari, DOLLARDA.

    Bu jadval 2026-iyunda paydo bo'ldi va narx AYNAN shu yerda turadi:
    nomida quvvat ham, aylanish ham bor (`ВЦ 4-75-2,5-1-0,75/3000`).
    Eski `models[].price` esa SO'MDA va 2025-noyabrdan beri to'ldirilmaydi.
    """
    natija: list[tuple[str, float]] = []
    for xususiyat in mahsulot.get("characters") or []:
        if not isinstance(xususiyat, dict):
            continue
        for ichki in xususiyat.get("insides") or []:
            if not isinstance(ichki, dict):
                continue
            narx = _narx_soni(ichki.get("price"))
            if narx > 0:
                natija.append((str(ichki.get("in_model_name") or ""), narx))
    return natija


def _ichki_narx(
    mahsulotlar: list[dict[str, Any]], nom: str, kurs: float
) -> tuple[float, str] | None:
    """Variant narxini topadi va so'mga o'giradi.

    Bir nechta variant mos kelsa (menejer quvvatni aytmagan) — ENG ARZONI
    olinadi va manba matnida buni ochiq yoziladi. Jim tanlab qo'yish xato
    bo'lardi: `ВЦ 4-75 №2,5` da narx 156 dan 199 dollargacha.
    """
    aniq: list[tuple[float, str]] = []
    keng: list[tuple[float, str]] = []
    sorov_kalitlari = kalitla(nom)
    for mahsulot in mahsulotlar:
        for variant_nomi, usd in _ichki_variantlar(mahsulot):
            if not variant_nomi:
                continue
            if sorov_kalitlari & kalitla(variant_nomi):
                aniq.append((usd, variant_nomi))
            elif _mos_keladimi(nom, variant_nomi):
                keng.append((usd, variant_nomi))

    nomzodlar = aniq or keng
    if not nomzodlar:
        return None

    nomzodlar.sort()
    usd, variant_nomi = nomzodlar[0]
    hisob = f"{usd:g} $ x {kurs:g}"
    if len(nomzodlar) > 1:
        manba = f"{variant_nomi} ({hisob}) — {len(nomzodlar)} variantdan eng arzoni"
    else:
        manba = f"{variant_nomi} ({hisob})"
    return usd * kurs, manba


def katalog_narxi(
    mahsulotlar: list[dict[str, Any]], nom: str, kurs: float | None = None
) -> tuple[float, str] | None:
    """Katalogdan mahsulot narxini topadi: (narx SO'MDA, qaysi yozuvdan).

    VALYUTA MANBAGA QARAB FARQ QILADI. Bu 2026-08-28 da o'lchandi:

      - `models` maydoni katalogda UMUMAN YO'Q (0/137 mahsulot);
      - `insides[].price` — 419 ta yozuv, 5…4746 oralig'ida;
      - `characters[].price` — butun katalogda BITTA yozuv (JV-65 =
        12391) va u DOLLARDA;
      - `models[].price` esa SO'MDA edi — u qaytsa ko'paytirilmaydi.

    JONLI XATO: `characters[].price` SO'M deb o'qilardi va chiller
    narxi 12 391 so'm bo'lib chiqardi — haqiqiysi 148 692 000 so'm,
    ya'ni 12 000 BAROBAR kam. Sabab: eski sxemada u so'mda edi,
    backend esa dollarga o'tgan va bu yerda e'tiborsiz qolgan.

    Narx 0 bo'lsa — "kiritilmagan" degani, "bepul" emas.
    """
    if not nom:
        return None

    kurs_qiymati = kurs_joriy() if kurs is None else kurs
    ichki = _ichki_narx(mahsulotlar, nom, kurs_qiymati)
    if ichki is not None:
        return ichki

    zaxira: tuple[float, str] | None = None
    for mahsulot in mahsulotlar:
        mahsulot_nomi = matn(mahsulot, "name")
        # VALYUTA MANBAGA QARAB FARQ QILADI — bu o'lchangan, taxmin emas:
        #
        #   `models[].price`     — SO'MDA (eski sxema). Katalogda hozir
        #                          umuman yo'q (0/137 mahsulot), lekin
        #                          qaytsa ko'paytirilmasligi kerak.
        #   `characters[].price` — DOLLARDA, `insides[].price` kabi.
        #
        # JONLI XATO (2026-08-28): `characters[].price` ham so'm deb
        # o'qilardi va chiller narxi 12 391 so'm bo'lib chiqardi —
        # haqiqiysi 148 692 000 so'm, ya'ni 12 000 barobar kam.
        yozuvlar = [
            (m.get("name", ""), m.get("price"), False)      # so'mda
            for m in (mahsulot.get("models") or [])
            if isinstance(m, dict)
        ] + [
            (x.get("title", ""), x.get("price"), True)      # dollarda
            for x in (mahsulot.get("characters") or [])
            if isinstance(x, dict)
        ]
        for yozuv_nomi, xom_narx, dollarda in yozuvlar:
            narx = _narx_soni(xom_narx)
            if dollarda:
                narx *= kurs_qiymati
            if narx <= 0:
                continue
            if _mos_keladimi(nom, yozuv_nomi):
                return narx, yozuv_nomi
            # Mahsulot nomi mos kelsa — modeli aniq aytilmagan bo'lishi
            # mumkin; birinchi narxli modelni zaxira sifatida saqlaymiz.
            if zaxira is None and mahsulot_nomi and _mos_keladimi(nom, mahsulot_nomi):
                zaxira = (narx, f"{mahsulot_nomi} / {yozuv_nomi}")
    return zaxira


def narx_bormi(mahsulot: dict[str, Any]) -> bool:
    """Ichki tizimda haqiqiy narx bormi?

    Hozircha deyarli barcha mahsulotda `price = 0` — bu "narx yo'q" degani,
    "bepul" emas. Shuning uchun 0 narx sifatida ko'rsatilmaydi.
    """
    try:
        return float(mahsulot.get("price") or 0) > 0
    except (TypeError, ValueError):
        return False

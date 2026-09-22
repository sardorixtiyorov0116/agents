"""Climavent backendga YOZISH klienti — katalog administratori uchun.

Nega alohida klass?
  `ClimaventKlient` ataylab faqat o'qiydi: unda yozish metodi umuman yo'q,
  shuning uchun Sardor, Doston, Temur kabi agentlar katalogni buza olmaydi —
  bu kodda ta'minlangan, promptda emas. Yozish huquqi faqat shu klassni olgan
  agentda bo'ladi.

O'ZGARMAS QOIDALAR (kodda):
  - faqat `AMALLAR` jadvalidagi amallar mumkin; yo'l va metod LLM'dan
    kelmaydi, jadvaldan olinadi — ixtiyoriy endpointga so'rov yuborib
    bo'lmaydi;
  - har amal uchun maydonlar OQ RO'YXATDAN o'tadi: begona kalit tashlanadi;
  - token bo'lmasa yozish umuman boshlanmaydi;
  - `mahsulot_yangila` avval mavjud yozuvni o'qib, ustiga qo'yadi — PATCH
    to'liq DTO talab qilgani uchun aks holda maydonlar o'chib ketardi;
  - klass hech qachon o'zi qaror qilmaydi: har amal inson tasdig'idan keyin
    `bajar()` orqali chaqiriladi (tasdiqni orkestr boshqaradi).
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import sozlama

from .climavent_client import ApiXatosi

# Har amal: (HTTP metodi, yo'l shakli, id kerakmi, maydon oq ro'yxati,
#            majburiy maydonlar).
# `store_id` SHART. `UpdateProductDto` da u bor (backend Swagger), bizda
# esa yo'q edi — ya'ni birlashtirishda u DTO'ga tushmasdi. PATCH to'liq
# DTO talab qilgani uchun bu mahsulotni do'kondan uzib qo'yishi mumkin
# edi. Endi mavjud yozuvdan o'qilib, o'zgarishsiz qaytariladi.
MAHSULOT_MAYDONLARI = (
    "name_uz", "name_ru", "name_en",
    "description_short_uz", "description_short_ru", "description_short_en",
    "sizes", "sizesJson", "opisaniya", "opisaniyaJson",
    "naznacheniya", "naznacheniyaJson", "markirovka", "markirovkaJson",
    "quantity", "producer", "category_id", "store_id",
)
# YARATISHDA backend kamroq maydon qabul qiladi: `CreateProductDto` da
# atigi shu 10 tasi bor. Ilgari yaratishga ham to'liq ro'yxat yuborilardi
# va `sizes`, `opisaniya`, `naznacheniya`, `markirovka` (hamda ularning
# `Json` juftlari) jimgina yo'qolardi. Endi yaratish ikki bosqichda:
# avval shu maydonlar bilan POST, so'ng qolganlari PATCH bilan qo'yiladi.
MAHSULOT_YARATISH_MAYDONLARI = (
    "name_uz", "name_ru", "name_en",
    "description_short_uz", "description_short_ru", "description_short_en",
    "quantity", "producer", "category_id", "store_id",
)

XUSUSIYAT_MAYDONLARI = ("title", "content", "contentJson", "price", "product_id")
# `product_model_inside` — bitta buyurtma qilinadigan artikul (quvvat + aylanish).
# DIQQAT: `product_model_id` nomi aldaydi — u `characteristics.id` ga ishora
# qiladi, `product_models.id` ga EMAS (backend Swagger: "Characteristic (model) id").
ICHKI_MAYDONLARI = ("sap_name", "in_model_name", "product_model_id", "price")

MAHSULOT_MAJBURIY = (
    "name_uz", "name_ru", "name_en",
    "description_short_uz", "description_short_ru", "description_short_en",
    "quantity", "producer", "category_id",
)


class AmalTuri(BaseModel):
    metod: str
    yol: str
    id_kerak: bool
    maydonlar: tuple[str, ...]
    majburiy: tuple[str, ...] = ()
    # Yangilashdan oldin mavjud yozuv o'qilsinmi (to'liq DTO talab qiladi).
    birlashtir: bool = False
    # To'ldirilgan bo'lsa — yaratish IKKI BOSQICHLI: shu maydonlar bilan
    # POST qilinadi, `maydonlar` dagi qolganlari esa yangi yozuvga PATCH
    # bilan qo'yiladi (yaratish DTO'si ularni qabul qilmaydi).
    yaratish_maydonlari: tuple[str, ...] = ()
    tavsif: str = ""


AMALLAR: dict[str, AmalTuri] = {
    "mahsulot_yarat": AmalTuri(
        metod="POST", yol="/api/products/create", id_kerak=False,
        maydonlar=MAHSULOT_MAYDONLARI, majburiy=MAHSULOT_MAJBURIY,
        yaratish_maydonlari=MAHSULOT_YARATISH_MAYDONLARI,
        tavsif="katalogga yangi mahsulot qo'shish",
    ),
    "mahsulot_yangila": AmalTuri(
        metod="PATCH", yol="/api/products/update/{id}", id_kerak=True,
        maydonlar=MAHSULOT_MAYDONLARI, birlashtir=True,
        tavsif="mavjud mahsulot ma'lumotini o'zgartirish",
    ),
    "mahsulot_ochir": AmalTuri(
        metod="DELETE", yol="/api/products/delete/{id}", id_kerak=True,
        maydonlar=(), tavsif="mahsulotni katalogdan o'chirish",
    ),
    # `model_yarat` / `model_yangila` / `model_ochir` OLIB TASHLANDI.
    #
    # Ular `/api/product-models/*` ga qarardi, backendda esa bunday yo'l
    # umuman yo'q (Swagger bilan tekshirilgan) — har chaqiruv 404 bilan
    # tugardi. Yomoni: Nodira amalni taklif qilardi, odam tasdiqlardi,
    # va faqat shundan keyin xato chiqardi.
    #
    # "Model" bu katalogda aslida `characteristics` — quyidagi
    # `xususiyat_*` amallari aynan shuni boshqaradi va ishlaydi.
    "xususiyat_yarat": AmalTuri(
        metod="POST", yol="/api/characteristics/create", id_kerak=False,
        maydonlar=XUSUSIYAT_MAYDONLARI,
        majburiy=("title", "content", "price", "product_id"),
        tavsif="mahsulotga texnik xususiyat qo'shish",
    ),
    "xususiyat_yangila": AmalTuri(
        metod="PATCH", yol="/api/characteristics/update/{id}", id_kerak=True,
        maydonlar=XUSUSIYAT_MAYDONLARI,
        tavsif="xususiyat matnini yoki narxini o'zgartirish",
    ),
    "xususiyat_ochir": AmalTuri(
        metod="DELETE", yol="/api/characteristics/delete/{id}", id_kerak=True,
        maydonlar=(), tavsif="xususiyatni o'chirish",
    ),
    "ichki_yarat": AmalTuri(
        metod="POST", yol="/api/product-model-inside", id_kerak=False,
        maydonlar=ICHKI_MAYDONLARI,
        majburiy=("sap_name", "in_model_name", "product_model_id"),
        tavsif="model variantini (quvvat/aylanish) qo'shish",
    ),
    "ichki_yangila": AmalTuri(
        metod="PATCH", yol="/api/product-model-inside/{id}", id_kerak=True,
        maydonlar=ICHKI_MAYDONLARI,
        tavsif="model variantining narxini (USD) yoki nomini o'zgartirish",
    ),
    "ichki_ochir": AmalTuri(
        metod="DELETE", yol="/api/product-model-inside/{id}", id_kerak=True,
        maydonlar=(), tavsif="model variantini o'chirish",
    ),
}

# O'chirish amallari — alohida ajratilgan: hisobotda va tasdiq matnida
# ochiq ko'rsatiladi, chunki bu qaytarib bo'lmaydigan harakat.
OCHIRISH_AMALLARI = frozenset(nom for nom in AMALLAR if nom.endswith("_ochir"))


# API maydon turlariga qat'iy: matn kutilgan joyga son yuborilsa 400 qaytaradi.
SON_MAYDONLARI = frozenset(
    {"quantity", "category_id", "product_id", "product_model_id"}
)
# Narx HAR DOIM son. Ilgari bu yerda `NARX_MATN_AMALLARI` bor edi:
# `product_models.price` matn bo'lgani uchun. O'sha jadval API'da yo'q va
# unga tegishli amallar olib tashlandi, qolgan ikkalasida esa —
# `characteristics.price` va `product_model_inside.price` — Swagger
# bo'yicha tur `number`. Ikkinchisi DOLLARDA saqlanadi.


def _songa(qiymat: Any) -> Any:
    """Raqamli maydonni songa keltiradi (keltirib bo'lmasa — o'zicha)."""
    matn_qiymati = str(qiymat).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        son = float(matn_qiymati)
    except (TypeError, ValueError):
        return qiymat
    return int(son) if son.is_integer() else son


class YozishXatosi(RuntimeError):
    """Amal bajarilmadi (token yo'q, maydon yetishmadi, API rad etdi)."""


class Amal(BaseModel):
    """Bajarilishi kutilayotgan bitta o'zgarish."""

    tur: str
    nishon_id: int | None = None
    maydonlar: dict[str, Any] = Field(default_factory=dict)
    izoh: str = ""

    def turi(self) -> AmalTuri:
        amal_turi = AMALLAR.get(self.tur)
        if amal_turi is None:
            raise YozishXatosi(
                f"Noma'lum amal: {self.tur!r}. "
                f"Ruxsat etilganlari: {', '.join(sorted(AMALLAR))}"
            )
        return amal_turi

    def ochirishmi(self) -> bool:
        return self.tur in OCHIRISH_AMALLARI

    def tavsifi(self) -> str:
        """Odam o'qiy oladigan bitta qator (tasdiq matni uchun)."""
        try:
            izoh = self.turi().tavsif
        except YozishXatosi:
            izoh = self.tur
        nishon = f" (id={self.nishon_id})" if self.nishon_id else ""
        maydon = ", ".join(f"{k}={v}" for k, v in self.tozalangan().items())
        return f"{izoh}{nishon}" + (f": {maydon}" if maydon else "")

    def tozalangan(self) -> dict[str, Any]:
        """Oq ro'yxatdan o'tgan maydonlar, API kutgan turga keltirilgan.

        Begona kalitlar tashlanadi; `quantity`, `product_id` va `price`
        kabi maydonlar songa keltiriladi — model "3 200 000" deb yozsa
        ham API to'g'ri qiymat oladi.
        """
        ruxsat = set(self.turi().maydonlar)
        natija: dict[str, Any] = {}
        for kalit, qiymat in self.maydonlar.items():
            if kalit not in ruxsat:
                continue
            if kalit in SON_MAYDONLARI or kalit == "price":
                natija[kalit] = _songa(qiymat)
            else:
                natija[kalit] = qiymat
        return natija

    def tekshir(self) -> list[str]:
        """Bajarishdan oldingi tekshiruv — muammolar ro'yxati."""
        muammolar: list[str] = []
        try:
            amal_turi = self.turi()
        except YozishXatosi as xato:
            return [str(xato)]

        if amal_turi.id_kerak and not self.nishon_id:
            muammolar.append(f"{self.tur}: qaysi yozuv ekani (id) ko'rsatilmagan")

        tozalangan = self.tozalangan()
        # Yangilashda mavjud yozuv o'qib birlashtiriladi — majburiy maydonlar
        # o'sha yerdan keladi, shuning uchun faqat yaratishda tekshiramiz.
        if not amal_turi.birlashtir:
            yetishmagan = [m for m in amal_turi.majburiy if not str(tozalangan.get(m, "")).strip()]
            if yetishmagan:
                muammolar.append(f"{self.tur}: yetishmayapti — {', '.join(yetishmagan)}")

        begona = set(self.maydonlar) - set(amal_turi.maydonlar)
        if begona:
            muammolar.append(
                f"{self.tur}: bu maydonlar API'da yo'q, e'tiborga olinmaydi — "
                f"{', '.join(sorted(begona))}"
            )
        return muammolar


class ClimaventYozuvchi:
    """Katalogga yozish (faqat tasdiqlangan amallar uchun)."""

    def __init__(
        self,
        asos: str | None = None,
        token: str | None = None,
        mijoz: httpx.AsyncClient | None = None,
        xizmat_kaliti: str | None = None,
    ):
        s = sozlama()
        self.asos = (asos or s.climavent_api_asos).rstrip("/")
        self.token = token if token is not None else s.climavent_token
        self.xizmat_kaliti = (
            xizmat_kaliti if xizmat_kaliti is not None else s.service_api_key
        )
        self.kutish = s.climavent_kutish
        self._mijoz = mijoz

    def sozlanganmi(self) -> bool:
        """Yozish uchun guvohnoma bormi? Bo'lmasa yozish boshlanmaydi."""
        return bool(self.xizmat_kaliti or self.token)

    def _sarlavhalar(self) -> dict[str, str]:
        """Ikkala guvohnoma ham yuboriladi.

        Backend qaysi birini tekshirishini bilmaymiz (xizmat kaliti yangi
        qo'shilgan, eski endpointlar hamon Bearer talab qilishi mumkin) —
        ikkalasini birga yuborish har ikki holatda ham ishlaydi.
        """
        sarlavhalar = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.xizmat_kaliti:
            sarlavhalar["X-API-Key"] = self.xizmat_kaliti
        if self.token:
            sarlavhalar["Authorization"] = f"Bearer {self.token}"
        return sarlavhalar

    async def _sorov(
        self, metod: str, yol: str, tana: dict[str, Any] | None = None
    ) -> Any:
        manzil = f"{self.asos}{yol}"
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.request(
                    metod, manzil, json=tana, headers=self._sarlavhalar(),
                    timeout=self.kutish,
                )
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.request(
                        metod, manzil, json=tana, headers=self._sarlavhalar()
                    )
        except httpx.HTTPError as xato:
            raise YozishXatosi(f"Backendga ulanib bo'lmadi ({yol}): {xato}") from xato

        if javob.status_code in (401, 403):
            qaysi = "SERVICE_API_KEY" if self.xizmat_kaliti else "CLIMAVENT_TOKEN"
            raise YozishXatosi(
                f"Backend ruxsat bermadi ({yol}): HTTP {javob.status_code}. "
                f"{qaysi} noto'g'ri, eskirgan yoki huquqi yetmaydi."
            )
        if javob.status_code >= 400:
            raise YozishXatosi(
                f"Backend rad etdi ({yol}): HTTP {javob.status_code} {javob.text[:300]}"
            )

        try:
            return javob.json()
        except ValueError:
            return {"holat": javob.status_code}

    # --- rasm ------------------------------------------------------------------
    #
    # NEGA AMAL JADVALIDA EMAS.
    #
    # Qolgan hamma o'zgarishni model REJALASHTIRADI: u maydon nomi va
    # qiymatini yozadi, odam tasdiqlaydi, kod bajaradi. Rasm bilan bunday
    # bo'lmaydi — model rasm yarata olmaydi, u faqat HAVOLA yozishi
    # mumkin, havolani esa o'ylab topib qo'yadi. Natijada katalogga
    # ishlamaydigan yoki begona surat biriktirilardi.
    #
    # Shuning uchun zanjir teskari qurilgan:
    #   1) rasm MAZMUNI odamdan keladi (fayl yoki Telegramdagi surat);
    #   2) `rasm_yukla()` uni backendga beradi, backend Cloudinary'ga
    #      qo'yib HAVOLANI qaytaradi;
    #   3) `rasmni_biriktir()` aynan o'sha havolani mahsulotga bog'laydi.
    #
    # Ya'ni havola hech qachon modeldan kelmaydi.

    async def rasm_yukla(self, mazmun: bytes, nom: str = "rasm.jpg") -> str:
        """Rasmni backend orqali Cloudinary'ga yuklaydi va havolasini qaytaradi.

        Bu yagona MULTIPART so'rov — qolgani JSON. Shuning uchun umumiy
        `_sorov` ishlatilmaydi: u `json=` bilan yuboradi va `Content-Type`
        ni qo'lda qo'yadi, multipart chegarasini esa `httpx` o'zi yozishi
        kerak.
        """
        if not self.sozlanganmi():
            raise YozishXatosi(
                "Rasm yuklash uchun guvohnoma yo'q. `.env` fayliga "
                "SERVICE_API_KEY (afzal) yoki CLIMAVENT_TOKEN qo'shing."
            )
        if not mazmun:
            raise YozishXatosi("Rasm bo'sh — yuklanmadi.")

        # `Content-Type` ni OLIB TASHLAYMIZ: multipart chegarasini kutubxona
        # qo'yadi, biz `application/json` yozib qo'ysak so'rov buziladi.
        sarlavhalar = {
            k: v for k, v in self._sarlavhalar().items() if k != "Content-Type"
        }
        fayllar = {"file": (nom, mazmun)}
        manzil = f"{self.asos}/api/images/upload-image"
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.post(
                    manzil, files=fayllar, headers=sarlavhalar, timeout=self.kutish,
                )
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.post(manzil, files=fayllar, headers=sarlavhalar)
        except httpx.HTTPError as xato:
            raise YozishXatosi(f"Rasm yuklanmadi (tarmoq): {xato}") from xato

        if javob.status_code in (401, 403):
            raise YozishXatosi(
                f"Backend rasm yuklashga ruxsat bermadi: HTTP {javob.status_code}."
            )
        if javob.status_code >= 400:
            raise YozishXatosi(
                f"Backend rasmni rad etdi: HTTP {javob.status_code} {javob.text[:300]}"
            )

        havola = self._havolani_ajrat(javob)
        if not havola:
            raise YozishXatosi(
                f"Rasm yuklandi, lekin javobdan havola topilmadi: {javob.text[:300]}"
            )
        return havola

    @staticmethod
    def _havolani_ajrat(javob: Any) -> str:
        """Yuklash javobidan rasm havolasini ajratadi.

        Backend javob shaklini kafolatlamaydi, shuning uchun bir nechta
        keng tarqalgan kalit sinaladi. Topilmasa — bo'sh matn, chaqiruvchi
        buni xatoga aylantiradi (jimgina "muvaffaqiyat" bo'lmasin).
        """
        try:
            malumot = javob.json()
        except ValueError:
            matn_javob = (getattr(javob, "text", "") or "").strip()
            return matn_javob if matn_javob.startswith("http") else ""

        if isinstance(malumot, str):
            return malumot if malumot.startswith("http") else ""
        qatlamlar = [malumot]
        if isinstance(malumot, dict) and isinstance(malumot.get("data"), dict):
            qatlamlar.append(malumot["data"])
        for qatlam in qatlamlar:
            if not isinstance(qatlam, dict):
                continue
            for kalit in ("image_link", "url", "secure_url", "link", "path"):
                qiymat = qatlam.get(kalit)
                if isinstance(qiymat, str) and qiymat.strip():
                    return qiymat.strip()
        return ""

    async def rasmni_biriktir(self, mahsulot_id: int, havola: str) -> dict[str, Any]:
        """Yuklangan rasmni mahsulotga bog'laydi.

        `havola` FAQAT `rasm_yukla()` qaytargan qiymat bo'lishi kerak —
        shuning uchun bu metod ochiq, amal jadvalida esa yo'q.
        """
        if not havola:
            raise YozishXatosi("Rasm havolasi bo'sh — biriktirilmadi.")
        return await self._sorov(
            "POST", "/api/product-images/create",
            {"image_link": havola, "product_id": int(mahsulot_id)},
        )

    async def rasmni_ochir(self, rasm_id: int) -> dict[str, Any]:
        """Mahsulotdagi rasm yozuvini o'chiradi (Cloudinary faylini emas)."""
        return await self._sorov(
            "DELETE", f"/api/product-images/delete/{int(rasm_id)}", None,
        )

    async def rasm_qoy(
        self, mahsulot_id: int, mazmun: bytes, nom: str = "rasm.jpg"
    ) -> dict[str, Any]:
        """Yuklash + biriktirish — bitta chaqiruvda.

        Ikki bosqich orasida uzilib qolsa buni YASHIRMAYDI: rasm
        Cloudinary'da qolib, mahsulotga bog'lanmagani ochiq aytiladi.
        """
        havola = await self.rasm_yukla(mazmun, nom)
        try:
            javob = await self.rasmni_biriktir(mahsulot_id, havola)
        except YozishXatosi as xato:
            raise YozishXatosi(
                f"Rasm yuklandi ({havola}), lekin mahsulotga biriktirilmadi: {xato}"
            ) from xato
        return {"havola": havola, "mahsulot_id": int(mahsulot_id), "javob": javob}

    @staticmethod
    def _yangi_id(javob: Any) -> int | None:
        """Yaratish javobidan yangi yozuv `id` sini ajratadi.

        Backend javob shaklini kafolatlamaydi: `{id: N}` ham, `{data:
        {id: N}}` ham kelishi mumkin. Ikkalasini ham qabul qilamiz.
        """
        for qatlam in (javob, (javob or {}).get("data") if isinstance(javob, dict) else None):
            if isinstance(qatlam, dict) and qatlam.get("id") is not None:
                try:
                    return int(qatlam["id"])
                except (TypeError, ValueError):
                    return None
        return None

    async def _ikki_bosqichda_yarat(
        self, amal: "Amal", amal_turi: AmalTuri, yol: str, tana: dict[str, Any]
    ) -> dict[str, Any]:
        """Yaratish DTO'si tor bo'lganda: avval POST, so'ng PATCH.

        `CreateProductDto` `sizes`, `opisaniya`, `naznacheniya`,
        `markirovka` va ularning `Json` juftlarini QABUL QILMAYDI —
        ilgari ular jimgina yo'qolardi. Shuning uchun yaratishdan keyin
        qolgan maydonlar darhol yangilash amali orqali qo'yiladi.
        """
        ruxsat = set(amal_turi.yaratish_maydonlari)
        yaratish = {k: v for k, v in tana.items() if k in ruxsat}
        qolgan = {k: v for k, v in tana.items() if k not in ruxsat}

        javob = await self._sorov(amal_turi.metod, yol, yaratish or None)
        natija: dict[str, Any] = {
            "amal": amal.tur, "yol": yol, "metod": amal_turi.metod,
            "yuborilgan": yaratish, "javob": javob,
        }
        if not qolgan:
            return natija

        yangi_id = self._yangi_id(javob)
        if yangi_id is None:
            # Mahsulot YARATILDI, lekin qolgan maydonlar qo'yilmadi.
            # Buni yashirish mumkin emas — yarim bajarilgan o'zgarish.
            natija["ogohlantirish"] = (
                "Mahsulot yaratildi, lekin javobdan `id` topilmadi — "
                f"qolgan maydonlar qo'yilmadi: {', '.join(sorted(qolgan))}. "
                "Ularni `mahsulot_yangila` bilan qo'lda qo'shish kerak."
            )
            return natija

        # Qolganini yangilash amali orqali qo'yamiz: u mavjud yozuvni
        # o'qib ustiga qo'yadi, shuning uchun yangi yaratilgan maydonlar
        # o'chib ketmaydi.
        toldirish = await self.bajar(
            Amal(tur="mahsulot_yangila", nishon_id=yangi_id, maydonlar=qolgan)
        )
        natija["nishon_id"] = yangi_id
        natija["toldirish"] = toldirish
        return natija

    async def _mavjud_yozuv(self, mahsulot_id: int) -> dict[str, Any]:
        """Yangilashdan oldin mavjud mahsulotni o'qiydi."""
        manzil = f"{self.asos}/api/products/one/{int(mahsulot_id)}"
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.get(manzil, timeout=self.kutish)
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.get(manzil)
            javob.raise_for_status()
            malumot = javob.json()
        except (httpx.HTTPError, ValueError) as xato:
            raise YozishXatosi(
                f"Yangilanadigan mahsulot o'qilmadi (id={mahsulot_id}): {xato}"
            ) from xato
        if not isinstance(malumot, dict) or not malumot:
            raise YozishXatosi(f"Mahsulot topilmadi: id={mahsulot_id}")
        return malumot

    async def bajar(self, amal: Amal) -> dict[str, Any]:
        """Bitta tasdiqlangan amalni bajaradi.

        Chaqirilishidan oldin inson tasdig'i olingan bo'lishi SHART — buni
        orkestr ta'minlaydi, bu yerda faqat texnik tekshiruv bor.
        """
        if not self.sozlanganmi():
            raise YozishXatosi(
                "Katalogga yozish guvohnomasi yo'q. `.env` fayliga "
                "SERVICE_API_KEY (afzal) yoki CLIMAVENT_TOKEN qo'shing."
            )

        amal_turi = amal.turi()
        muammolar = [m for m in amal.tekshir() if "e'tiborga olinmaydi" not in m]
        if muammolar:
            raise YozishXatosi("; ".join(muammolar))

        yol = amal_turi.yol.format(id=int(amal.nishon_id or 0))
        tana: dict[str, Any] | None = amal.tozalangan() or None

        if amal_turi.yaratish_maydonlari and tana:
            return await self._ikki_bosqichda_yarat(amal, amal_turi, yol, tana)

        if amal_turi.birlashtir and tana:
            mavjud = await self._mavjud_yozuv(int(amal.nishon_id or 0))
            asos = {m: mavjud.get(m) for m in amal_turi.maydonlar if m in mavjud}
            # Kategoriya alohida obyekt bo'lib kelishi mumkin.
            if not asos.get("category_id") and isinstance(mavjud.get("category"), dict):
                asos["category_id"] = mavjud["category"].get("id")
            asos.update(tana)
            tana = {k: v for k, v in asos.items() if v is not None}

        if amal_turi.metod == "DELETE":
            tana = None

        javob = await self._sorov(amal_turi.metod, yol, tana)
        return {
            "amal": amal.tur,
            "yol": yol,
            "metod": amal_turi.metod,
            "yuborilgan": tana or {},
            "javob": javob,
        }

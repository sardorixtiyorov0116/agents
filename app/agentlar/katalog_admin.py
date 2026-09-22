"""Katalog administratori Nodira — `catalog-admin`.

Maqsad: Climavent katalogini tartibda tutish — mahsulot qo'shish, tuzatish,
o'chirish va eng muhimi NARX to'ldirish.

XAVFSIZLIK. Bu agentning himoyasi promptga TAYANMAYDI:
  - yozish `ClimaventYozuvchi` orqali boradi; unda faqat 9 ta oldindan
    belgilangan amal bor, HTTP metodi va yo'l jadvaldan olinadi — model
    ixtiyoriy endpointga so'rov yubora olmaydi;
  - har amalning maydonlari oq ro'yxatdan o'tadi;
  - agent HECH QACHON o'z-o'zidan yozmaydi: `ishla()` faqat REJA tuzadi va
    `TASDIQ_KUTILMOQDA` bilan to'xtaydi. Yozish faqat orkestr tasdiqdan keyin
    `kontekst["tasdiqlandi"]` bilan qayta chaqirganda sodir bo'ladi.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from integrations import (
    AMALLAR,
    Amal,
    ApiXatosi,
    ClimaventYozuvchi,
    YozishXatosi,
    mahsulot_qisqa,
)

from ..konvert import (
    Holat,
    Ishonch,
    Konvert,
    Manba,
    aniqlik_kerak_konvert,
    tasdiq_konverti,
    xato_konvert,
)
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Bitta so'rovda ruxsat etilgan maksimal amal soni — "ommaviy o'zgartirish
# qilmaydi" chegarasi kodda ta'minlanadi, promptda emas.
MAKS_AMAL = 20

# Modelga ko'rsatiladigan katalog qatorlari soni.
MAKS_KATALOG = 10


def _amallar_matni() -> str:
    qatorlar = []
    for nom, turi in AMALLAR.items():
        maydonlar = ", ".join(turi.maydonlar) or "(maydon kerak emas)"
        id_izoh = "id SHART" if turi.id_kerak else "id kerak emas"
        qatorlar.append(f"- {nom}: {turi.tavsif} | {id_izoh} | maydonlar: {maydonlar}")
    return "\n".join(qatorlar)


TIZIM_PROMPT = f"""Sen "Katalog administratori Nodira" — Climavent mahsulot
katalogini tartibda tutadigan agentsan.

VAZIFAN: foydalanuvchi so'ragan o'zgarishni ANIQ amallar ro'yxatiga aylantirish.
Sen amallarni BAJARMAYSAN — faqat rejalashtirasan. Bajarishdan oldin inson
tasdiqlaydi.

MUMKIN BO'LGAN AMALLAR (boshqasi yo'q):
{_amallar_matni()}

QAT'IY QOIDALAR:
1) NARXNI O'ZING O'YLAB TOPMAYSAN. Faqat foydalanuvchi aytgan raqamni
   yozasan. Narx aytilmagan bo'lsa — amal tuzmaysan, `sorash_kerak` ga
   yozasan.
2) ID NI TAXMIN QILMAYSAN. `nishon_id` faqat "KATALOGDAN TOPILDI" bo'limida
   ko'rsatilgan haqiqiy id bo'lishi mumkin. Yozuv topilmagan bo'lsa —
   `topilmadi` ga yozasan va amal tuzmaysan.
   FOYDALANUVCHIDAN ID SO'RAMAYSAN — u ichki raqamlarni bilmaydi. Buning
   o'rniga: mahsulot katalogda yo'qligini aytasan va "yangi mahsulot sifatida
   qo'shaymi?" deb so'raysan yoki aniqroq nom/model kodini so'raysan.
3) Bir nechta yozuv mos kelsa — TANLAMAYSAN, `sorash_kerak` ga qaysi biri
   kerakligini so'rab yozasan.
4) MA'LUMOTNI TO'QIMAYSAN: bilmagan maydonni umuman yozma (bo'sh qoldir).
   Tavsif, o'lcham, ishlab chiqaruvchi — faqat aytilgan bo'lsa.
5) O'CHIRISH so'ralmasa — o'chirish amali tuzmaysan. So'ralganda esa `xavf`
   maydoniga nima yo'qolishini aniq yozasan.
6) Har amalga qisqa `izoh` yozasan — inson nimani tasdiqlayotganini bilsin.

SEN QILMAYDIGAN ISHLAR:
- Foydalanuvchi, buyurtma, sharh, savat yozuvlariga tegmaysan.
- Mijozga hech narsa yubormaysan.
- Tijorat taklifi tuzmaysan (bu Tijorat menejeri Temurning ishi).
- Narx siyosati yoki chegirma belgilamaysan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "niyat": "foydalanuvchi nima qilmoqchi (qisqa)",
  "amallar": [
    {"tur": "xususiyat_yangila", "nishon_id": 91,
     "maydonlar": [{"nomi": "price", "qiymati": "2400000"}],
     "izoh": "nima uchun"}
  ],
  "topilmadi": ["katalogdan topilmagan yozuv nomi"],
  "sorash_kerak": ["aniqlashtirish kerak bo'lgan narsa"],
  "xavf": "o'chirish yoki katta o'zgarish bo'lsa — nima yo'qolishi"
}"""


class NodiraMaydon(BaseModel):
    """Bitta maydon: nomi va qiymati.

    Ataylab erkin `dict` emas: structured output sxemasida ochiq obyekt
    `additionalProperties: false` bo'lib qoladi va model unga hech narsa
    yoza olmaydi. Kalit/qiymat juftligi esa sxemada to'g'ri ifodalanadi.
    """

    nomi: str
    qiymati: str


class NodiraAmal(BaseModel):
    tur: str
    nishon_id: int | None = None
    maydonlar: list[NodiraMaydon] = Field(default_factory=list)
    izoh: str = ""

    def maydon_lugati(self) -> dict[str, Any]:
        return {m.nomi: m.qiymati for m in self.maydonlar if m.nomi}


class NodiraNatija(BaseModel):
    niyat: str = ""
    amallar: list[NodiraAmal] = Field(default_factory=list)
    topilmadi: list[str] = Field(default_factory=list)
    sorash_kerak: list[str] = Field(default_factory=list)
    xavf: str = ""


class KatalogAdmin(Agent):
    """Katalog administratori Nodira."""

    def __init__(self, *args: Any, yozuvchi: ClimaventYozuvchi | None = None, **kw: Any):
        super().__init__(*args, **kw)
        # Yozish huquqi FAQAT shu agentda. Boshqa agentlarda bu obyekt yo'q.
        self.yozuvchi = yozuvchi if yozuvchi is not None else ClimaventYozuvchi()

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        kontekst = kontekst or {}

        # Tasdiqdan keyingi chaqiruv — endi haqiqatan yoziladi.
        if kontekst.get("tasdiqlandi") and kontekst.get("tasdiqlangan_amal"):
            return await self._amallarni_bajar(kontekst["tasdiqlangan_amal"])

        if not self.yozuvchi.sozlanganmi():
            return xato_konvert(
                self.rol,
                "Katalogga yozish guvohnomasi sozlanmagan. `.env` fayliga "
                "SERVICE_API_KEY qo'shing, keyin qayta so'rang.",
            )

        return await self._reja_tuz(vazifa, kontekst)

    # --- reja tuzish ---------------------------------------------------------

    async def _reja_tuz(self, vazifa: str, kontekst: dict[str, Any]) -> Konvert:
        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += await self._katalog_matni(vazifa)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=NodiraNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = NodiraNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        if not natija.amallar:
            savollar = natija.sorash_kerak or [
                f"'{n}' katalogda topilmadi — aniqroq nom yoki model kodini bering"
                for n in natija.topilmadi
            ]
            return aniqlik_kerak_konvert(
                savollar or ["Katalogda nimani o'zgartirish kerakligini aniqroq yozing."],
                "Katalogni o'zgartirish uchun ma'lumot yetishmayapti.",
                kim=self.rol,
            )

        # Chegara KODDA: model qancha so'rasa ham, bir so'rovda shundan
        # ko'p yozuv o'zgarmaydi.
        kesildi = len(natija.amallar) > MAKS_AMAL
        amallar = natija.amallar[:MAKS_AMAL]

        tekshirilgan: list[dict[str, Any]] = []
        ogohlantirishlar: list[str] = []
        for xom in amallar:
            amal = Amal(
                tur=xom.tur,
                nishon_id=xom.nishon_id,
                maydonlar=xom.maydon_lugati(),
                izoh=xom.izoh,
            )
            muammolar = amal.tekshir()
            if any("e'tiborga olinmaydi" not in m for m in muammolar):
                ogohlantirishlar.extend(muammolar)
                continue
            ogohlantirishlar.extend(muammolar)
            tekshirilgan.append(amal.model_dump())

        if not tekshirilgan:
            return xato_konvert(
                self.rol,
                "Bajarish mumkin bo'lgan amal qolmadi: " + "; ".join(ogohlantirishlar),
                {"ogohlantirishlar": ogohlantirishlar},
            )

        if kesildi:
            ogohlantirishlar.append(
                f"{len(natija.amallar)} ta amal so'raldi — bir so'rovda "
                f"{MAKS_AMAL} tadan ko'p o'zgartirilmaydi, qolgani uchun "
                "qayta so'rov yuboring"
            )

        ochirishlar = [a for a in tekshirilgan if a["tur"].endswith("_ochir")]
        return tasdiq_konverti(
            self.rol,
            self._tasdiq_izohi(natija, tekshirilgan, ochirishlar),
            {
                "niyat": natija.niyat,
                "taklif_amal": tekshirilgan,
                "amal_soni": len(tekshirilgan),
                "ochirish_soni": len(ochirishlar),
                "topilmadi": natija.topilmadi,
                "sorash_kerak": natija.sorash_kerak,
                "xavf": natija.xavf,
                "ogohlantirishlar": ogohlantirishlar,
                "bajarildi": False,
            },
        )

    @staticmethod
    def _tasdiq_izohi(
        natija: NodiraNatija,
        amallar: list[dict[str, Any]],
        ochirishlar: list[dict[str, Any]],
    ) -> str:
        bolaklar = [f"{len(amallar)} ta katalog o'zgarishi tasdiq kutmoqda"]
        if ochirishlar:
            bolaklar.append(
                f"DIQQAT: shundan {len(ochirishlar)} tasi O'CHIRISH — "
                "qaytarib bo'lmaydi"
            )
        if natija.xavf:
            bolaklar.append(natija.xavf)
        bolaklar.append("HECH NARSA HALI YOZILMADI")
        return " | ".join(bolaklar)

    # --- tasdiqdan keyin bajarish --------------------------------------------

    async def _amallarni_bajar(self, xom_amallar: Any) -> Konvert:
        """Tasdiqlangan amallarni ketma-ket bajaradi.

        Bittasi yiqilsa qolganlari to'xtaydi: yarim bajarilgan o'zgarish
        yashirin qolmasligi kerak — nima bajarilgani ochiq ko'rsatiladi.
        """
        if not isinstance(xom_amallar, list) or not xom_amallar:
            return xato_konvert(self.rol, "Tasdiqlangan amal topilmadi.")

        bajarilgan: list[dict[str, Any]] = []
        xatolar: list[str] = []

        for xom in xom_amallar[:MAKS_AMAL]:
            try:
                amal = Amal.model_validate(xom)
            except ValidationError as xato:
                xatolar.append(f"amal o'qilmadi: {xato}")
                break
            try:
                natija = await self.yozuvchi.bajar(amal)
            except YozishXatosi as xato:
                xatolar.append(f"{amal.tavsifi()} — {xato}")
                break
            bajarilgan.append({"tavsif": amal.tavsifi(), **natija})

        # Katalog o'zgardi — o'qish keshi eskirdi.
        try:
            await self.api.keshni_tozala()
        except (ApiXatosi, AttributeError):
            pass

        natija_malumot = {
            "bajarildi": True,
            "bajarilgan_soni": len(bajarilgan),
            "bajarilgan": bajarilgan,
            "xatolar": xatolar,
        }
        manba = [
            self.kontrakt_manbasi(),
            Manba(tur="ichki_api", nom="Climavent katalogi (yozildi)"),
        ]

        if xatolar and not bajarilgan:
            return xato_konvert(
                self.rol,
                "Katalog o'zgartirilmadi: " + "; ".join(xatolar),
                natija_malumot,
            )

        izoh = f"{len(bajarilgan)} ta o'zgarish katalogga yozildi"
        if xatolar:
            izoh += f" | {len(xatolar)} ta amal bajarilmadi: {'; '.join(xatolar)}"

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija_malumot,
            manba=manba,
            ishonch=Ishonch.YUQORI if not xatolar else Ishonch.ORTA,
            tasdiq_kerak=False,
            izoh=izoh,
        )

    # --- katalog konteksti ---------------------------------------------------

    async def _katalog_matni(self, vazifa: str) -> str:
        """Modelga haqiqiy id'larni beradi — taxmin qilmasligi uchun."""
        try:
            topilgan = await self.api.qidir_keng(vazifa)
        except ApiXatosi as xato:
            self.ogohlantirish = f"katalogga ulanib bo'lmadi ({xato})"
            return (
                "\n\nKATALOGDAN TOPILDI: katalog hozir ochilmadi. "
                "Mavjud yozuvni yangilash yoki o'chirish AMALINI TUZMA "
                "(id noma'lum) — buni `sorash_kerak` ga yoz."
            )

        if not topilgan:
            return (
                "\n\nKATALOGDAN TOPILDI: mos yozuv yo'q. "
                "Yangilash yoki o'chirish amalini tuzma — id noma'lum. "
                "Yangi mahsulot qo'shish so'ralgan bo'lsa, `mahsulot_yarat` mumkin."
            )

        qatorlar = ["\n\nKATALOGDAN TOPILDI (nishon_id faqat shu yerdan olinadi):"]
        for mahsulot in topilgan[:MAKS_KATALOG]:
            qisqa = mahsulot_qisqa(mahsulot)
            qatorlar.append(
                f"- mahsulot id={qisqa['id']} | {qisqa['nomi']} "
                f"| kategoriya: {qisqa['kategoriya']} | ombor: {qisqa['ombor']}"
            )
            for model in (mahsulot.get("models") or [])[:12]:
                if not isinstance(model, dict):
                    continue
                qatorlar.append(
                    f"    model id={model.get('id')} | {model.get('name')} "
                    f"| narx: {model.get('price')}"
                )
            for xususiyat in (mahsulot.get("characters") or [])[:6]:
                if not isinstance(xususiyat, dict):
                    continue
                qatorlar.append(
                    f"    xususiyat id={xususiyat.get('id')} "
                    f"| {xususiyat.get('title')} | narx: {xususiyat.get('price')}"
                )
        return "\n".join(qatorlar)

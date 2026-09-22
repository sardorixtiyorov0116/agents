"""Ma'lumot muhandisi Doston — `data-query`.

Maqsad: bazadan so'rov orqali ma'lumot oladi, qisqa tahlil qiladi va
ishlatilgan so'rovni ham ko'rsatadi (shaffoflik).

XAVFSIZLIK. Bu agentning himoyasi promptga TAYANMAYDI:
  - so'rov `baza.sorov_bajar()` orqali SQLite avtorizatori qo'yilgan
    ulanishda bajariladi — DELETE / DROP / TRUNCATE / ALTER va ruxsat
    etilmagan jadvallar SQLite darajasida rad etiladi;
  - o'qish ulanishi `mode=ro` bilan ochiladi, ya'ni yozish jismonan imkonsiz;
  - `execute` bitta buyruq bilan cheklangan — `;` orqali ikkinchi buyruq
    qo'shib bo'lmaydi.
Quyidagi kalit so'z tekshiruvi — qo'shimcha qatlam va aniq xato xabari uchun,
asosiy himoya emas.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from integrations import ApiXatosi
from integrations.climavent_client import mahsulot_qisqa

from ..konvert import Holat, Ishonch, Konvert, Manba, tasdiq_konverti, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Javobda ko'rsatiladigan maksimal qator soni (kontekstni to'ldirib yubormaslik).
MAKS_QATOR = 50

# Hech qanday holatda bajarilmaydigan amallar (tasdiq bilan ham).
OCHIRUVCHI = re.compile(
    r"\b(delete|drop|truncate|alter|attach|detach|vacuum|reindex|replace)\b", re.IGNORECASE
)
YOZUVCHI = re.compile(r"\b(insert|update)\b", re.IGNORECASE)

TIZIM_PROMPT = """Sen "Ma'lumot muhandisi Doston" — kompaniya bazasi bilan ishlaydigan agentsan.

VAZIFAN: berilgan savolga javob beradigan SQL so'rovini yozish (SQLite
dialekti) va nima qilayotganingni ochiq tushuntirish.

QAT'IY QOIDALAR:
1) FAQAT O'QISH (SELECT). O'chirish (DELETE, DROP, TRUNCATE) — mutlaqo yo'q,
   hech qanday sababda, hech kim so'rasa ham. Bunday so'rov kelsa, `sql` ni
   bo'sh qoldirasan va `izoh` da rad etganingni aytasan.
2) YOZISH (INSERT / UPDATE) so'ralsa — so'rovni YOZASAN, lekin
   `yozish_kerakmi: true` qilasan va sababini `yozish_sababi` ga yozasan.
   Yozish faqat inson tasdig'idan keyin bajariladi — buni o'zing hal qilmaysan.
3) FAQAT berilgan jadvallardan foydalanasan. Boshqa jadval nomini yozmaysan.
4) Natijani cheklab yoz (LIMIT), agregat so'rovlarda esa kerak emas.
5) Savol noaniq bo'lsa — taxmin qilmaysan: `sql` ni bo'sh qoldirib, `izoh` da
   nimani aniqlashtirish kerakligini so'raysan.
6) Natijani O'YLAB TOPMAYSAN. Sen faqat so'rov yozasan; raqamlarni bazaning
   o'zi qaytaradi.

SEN QILMAYDIGAN ISHLAR:
- Ma'lumotni o'chirmaysan.
- Tasdiqsiz ommaviy o'zgartirish qilmaysan.
- Maxfiy maydonlarni ruxsatsiz ochmaysan.
- Bazadan tashqariga ma'lumot chiqarmaysan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "sql": "SELECT ... (yoki bo'sh matn)",
  "izoh": "so'rov nima qilishini tushuntirish (yoki katalogdan javobning o'zi)",
  "yozish_kerakmi": true/false,
  "yozish_sababi": "matn yoki bo'sh",
  "katalogdan_javob": true/false
}"""


class DostonSorov(BaseModel):
    """Modelning javobi: bajariladigan so'rov va uning tavsifi."""

    sql: str = ""
    izoh: str = ""
    yozish_kerakmi: bool = False
    yozish_sababi: str = ""
    # Javob ichki katalog ko'rsatkichlaridan olingan — SQL kerak emas.
    katalogdan_javob: bool = False


class MalumotMuhandisi(Agent):
    """Ma'lumot muhandisi Doston."""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        kontekst = kontekst or {}

        # Tasdiqdan keyingi ikkinchi chaqiruv: so'rov allaqachon yozilgan va
        # inson uni ko'rib tasdiqlagan — endi bajaramiz.
        if kontekst.get("tasdiqlandi") and kontekst.get("tasdiqlangan_sql"):
            return await self._bajar(str(kontekst["tasdiqlangan_sql"]), yozish=True)

        sxema = await self.baza.jadval_sxemasi()
        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq = f"{topshiriq}\n\nMavjud jadvallar (faqat shular):\n{sxema}"
        topshiriq += await self._katalog_xulosasi()
        topshiriq += await self._mahsulot_qoldigi(vazifa)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=DostonSorov,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            taklif = DostonSorov.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return await self._taklifni_kor(taklif)

    async def _katalog_xulosasi(self) -> str:
        """Ichki katalog ko'rsatkichlari — SQL kerak bo'lmaydigan savollar uchun.

        Katalog savoliga javob shu yerda bo'lsa, `sql` ni bo'sh qoldirib
        `izoh` da javob berish mumkin.
        """
        try:
            xulosa = await self.api.katalog_xulosasi()
        except ApiXatosi as xato:
            self.ogohlantirish = f"ichki katalogga ulanib bo'lmadi ({xato})"
            return (
                "\n\nICHKI KATALOG: mavjud emas (API'ga ulanib bo'lmadi). "
                "Katalog haqidagi savolga javob berma — manba yo'qligini ayt."
            )

        eng_kattalar = list(xulosa["kategoriya_boyicha"].items())[:12]
        qatorlar = "\n".join(f"  - {nomi}: {soni} ta" for nomi, soni in eng_kattalar)
        return (
            "\n\nICHKI KATALOG (Climavent API, yig'ma ko'rsatkichlar):\n"
            f"- mahsulotlar soni: {xulosa['mahsulotlar_soni']}\n"
            f"- kategoriyalar soni: {xulosa['kategoriyalar_soni']}\n"
            f"- ombordagi jami miqdor: {xulosa['ombordagi_jami']}\n"
            f"- narxi to'ldirilgan: {xulosa['narxi_toldirilgan']}, "
            f"narxi bo'sh: {xulosa['narxi_bosh']}\n"
            f"- eng katta kategoriyalar:\n{qatorlar}\n"
            "Agar savol AYNAN shu ko'rsatkichlar haqida bo'lsa, `sql` ni bo'sh "
            "qoldirib, javobni `izoh` da ber va manbani \"ichki katalog (API)\" "
            "deb ayt. Buyurtma va mijozlar ma'lumoti API'da yopiq (token kerak) — "
            "ular haqida so'ralsa, yuqoridagi SQLite jadvallaridan foydalan."
        )

    # Nechta mahsulot ko'rsatiladi — prompt shishib ketmasin.
    MAKS_TOPILMA = 5

    async def _mahsulot_qoldigi(self, vazifa: str) -> str:
        """So'rovda model kodi bo'lsa — o'sha mahsulotning ombor qoldig'i.

        Yig'ma ko'rsatkichlar ("jami 3537 dona") "VK 250 dan nechta bor?"
        degan savolga javob bermaydi. Qoldiq mahsulot darajasida
        (`quantity`) turadi, model esa uning ichida — shuning uchun model
        kodi bo'yicha topib, ona mahsulotning qoldig'ini ko'rsatamiz.
        """
        try:
            topilgan = await self.api.qidir_keng(vazifa)
        except ApiXatosi:
            return ""      # xulosa allaqachon ogohlantirgan
        if not topilgan:
            return ""

        qatorlar = []
        for mahsulot in topilgan[: self.MAKS_TOPILMA]:
            q = mahsulot_qisqa(mahsulot)
            modellar = ", ".join(q["modellar"][:8]) or "—"
            qatorlar.append(
                f"  - {q['nomi']} (id={q['id']}) — ombor: {q['ombor']} dona\n"
                f"    modellari: {modellar}"
            )

        return (
            "\n\nSO'ROVGA MOS MAHSULOTLAR (Climavent API, aniq qoldiq):\n"
            + "\n".join(qatorlar)
            + "\nDIQQAT: `ombor` qiymati MAHSULOT bo'yicha, alohida model "
            "bo'yicha emas — javobda shuni aniq ayt. Savol shu mahsulotlar "
            "qoldig'i haqida bo'lsa, `sql` ni bo'sh qoldirib `izoh` da javob "
            'ber va manbani "ichki katalog (API)" deb ko\'rsat.'
        )

    # --- qaror qabul qilish --------------------------------------------------

    async def _taklifni_kor(self, taklif: DostonSorov) -> Konvert:
        sql = taklif.sql.strip().rstrip(";").strip()

        if not sql and taklif.katalogdan_javob and taklif.izoh:
            # Javob ichki katalog ko'rsatkichlaridan — SQL kerak emas.
            return Konvert(
                kim=self.rol,
                holat=Holat.TUGADI,
                natija={"javob": taklif.izoh, "manba_turi": "ichki_api", "sql": None},
                manba=[Manba(tur="ichki_api", nom="Climavent ichki katalogi (API)")],
                ishonch=Ishonch.YUQORI,
                tasdiq_kerak=False,
                izoh=f"ichki katalog ko'rsatkichlaridan javob berildi; {taklif.izoh}",
            )

        if not sql:
            # Model o'zi rad etdi yoki aniqlashtirish so'radi.
            return xato_konvert(
                self.rol,
                taklif.izoh or "So'rov aniq emas — qaysi ma'lumot kerakligini aniqlashtiring.",
            )

        if OCHIRUVCHI.search(sql):
            return xato_konvert(
                self.rol,
                "O'chirish/o'zgartirish amali (DELETE / DROP / TRUNCATE / ALTER) rad etildi — "
                "bu agentda bunday huquq umuman yo'q.",
                {"rad_etilgan_sql": sql},
            )

        if taklif.yozish_kerakmi or YOZUVCHI.search(sql):
            # Harakatdan OLDIN tasdiq: so'rov bajarilmaydi, faqat taklif qilinadi.
            return tasdiq_konverti(
                self.rol,
                "Yozish so'rovi tayyorlandi, lekin BAJARILMADI — inson tasdig'i kutilmoqda. "
                + (taklif.yozish_sababi or taklif.izoh),
                {"taklif_sql": sql, "sabab": taklif.yozish_sababi, "izoh": taklif.izoh},
            )

        return await self._bajar(sql, yozish=False, izoh=taklif.izoh)

    async def _bajar(self, sql: str, yozish: bool, izoh: str = "") -> Konvert:
        """So'rovni cheklangan ulanishda bajaradi."""
        try:
            qatorlar = await self.baza.sorov_bajar(sql, yozish=yozish)
        except sqlite3.Error as xato:
            return xato_konvert(
                self.rol,
                f"So'rov bajarilmadi (baza rad etdi yoki so'rov noto'g'ri): {xato}",
                {"sql": sql},
            )

        kesildi = len(qatorlar) > MAKS_QATOR
        natija: dict[str, Any] = {
            # Shaffoflik: ishlatilgan so'rov har doim javobda ko'rinadi.
            "sql": sql,
            "qatorlar": qatorlar[:MAKS_QATOR],
            "qatorlar_soni": len(qatorlar),
            "kesildi": kesildi,
            "izoh": izoh,
            "yozish": yozish,
        }

        # Jadvallar hali namunaviy — javob ishonchli ohangda chiqadi va
        # menejer uni haqiqat deb qabul qilishi mumkin.
        ogoh = self.demo_ogohi()
        if ogoh:
            natija["demo_ogohi"] = ogoh

        bolaklar = [f"{len(qatorlar)} ta qator"]
        if ogoh:
            bolaklar.insert(0, "NAMUNAVIY MA'LUMOT")
        if kesildi:
            bolaklar.append(f"birinchi {MAKS_QATOR} tasi ko'rsatildi")
        if not qatorlar:
            bolaklar.append("topilmadi — natija bo'sh")
        if yozish:
            bolaklar.append("tasdiqlangan yozish bajarildi")
        bolaklar.append(f"so'rov: {sql}")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija,
            manba=[Manba(tur="baza", nom="ichki baza (mijozlar, buyurtmalar)")],
            ishonch=Ishonch.YUQORI if qatorlar else Ishonch.ORTA,
            tasdiq_kerak=False,
            izoh="; ".join(bolaklar),
        )

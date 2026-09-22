"""Savdo koordinatori Aziza — `kp-tracker`.

Maqsad: yuborilgan tijorat takliflarining taqdirini kuzatadi. KP tuziladi,
mijozga ketadi — keyin nima bo'ldi? Shu savolga javob beradi.

O'ZGARMAS QOIDALAR (kodda, promptda emas):
  - RAQAMLAR bazadan olinadi va model javobidan OLINMAYDI: konversiya,
    summa va kunlar sxemada umuman yo'q — model ularni qaytara olmaydi;
  - KP ga murojaat `raqam` orqali bo'ladi va u BAZADA borligi tekshiriladi —
    mavjud bo'lmagan KP holatini o'zgartirib bo'lmaydi;
  - holat faqat to'rtta ruxsat etilgan qiymatdan biri bo'ladi (baza
    darajasida), aks holda statistika buziladi;
  - agent MIJOZGA hech narsa yubormaydi.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from ..baza import Baza
from ..konvert import (
    Holat,
    Ishonch,
    Konvert,
    Manba,
    tasdiq_konverti,
    xato_konvert,
)
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Promptga tushadigan KP soni.
MAKS_KP = 60

# Shuncha kundan keyin javobsiz KP "e'tibor kerak" deb belgilanadi.
KUTISH_KUNI = 5

HOLAT_MATNI = {
    "yuborildi": "yuborildi, javob yo'q",
    "javob_keldi": "javob keldi",
    "shartnoma": "shartnoma tuzildi",
    "rad_etildi": "rad etildi",
}

TIZIM_PROMPT = """Sen "Savdo koordinatori Aziza" — yuborilgan tijorat
takliflarini kuzatib boradigan agentsan.

VAZIFAN: menejerning so'rovini tushunib, ikki ishdan birini qilish:
  a) KP lar holatini KO'RSATISH (ro'yxat, javobsizlar, xulosa);
  b) bitta KP holatini O'ZGARTIRISH — menejer aytgan bo'lsa.

QAT'IY QOIDALAR:
1) RAQAM YOZMAYSAN. Summa, konversiya, kunlar soni — hammasi tayyor
   berilgan va javobda takrorlanmaydi. Sen faqat NIMA QILISH kerakligini
   aytasan.
2) KP GA `raqam` ORQALI murojaat qilasan — aynan ro'yxatdagi shaklda
   ("12969/8"). Yangi raqam O'YLAB TOPMAYSAN.
3) HOLATNI O'ZING QARORLASHTIRMAYSAN. `yangi_holat` ni faqat menejer aniq
   aytgan bo'lsa to'ldirasan ("AGMK shartnoma tuzdi", "rad etishdi").
   Aytilmagan bo'lsa bo'sh qoldirasan — bu KO'RSATISH so'rovi.
4) Ruxsat etilgan holatlar faqat shular:
   - `javob_keldi` — mijoz javob berdi, lekin hali qaror yo'q
   - `shartnoma` — shartnoma tuzildi
   - `rad_etildi` — mijoz rad etdi
   Boshqa so'z yozmaysan.
5) BASHORAT QILMAYSAN: "bu KP g'alaba qiladi", "mijoz rozi bo'ladi" kabi
   gap yozmaysan.
6) MIJOZ BILAN ALOQA TARIXINI TO'QIMAYSAN. "Qo'ng'iroq qilingan edi" kabi
   gap faqat menejer aytgan bo'lsa o'rinli.

SEN QILMAYDIGAN ISHLAR:
- Mijozga xat yoki xabar yubormaysan.
- KP tuzmaysan va o'zgartirmaysan (bu Temurning ishi).
- Chegirma taklif qilmaysan.
- Shartnoma matnini tekshirmaysan (bu Lazizning ishi).

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "xulosa": "menejerga 2-3 jumlalik javob",
  "etibor_kerak": [
    {"raqam": "12969/8", "nega": "5 kundan beri javob yo'q"}
  ],
  "tavsiyalar": ["aniq, bajariladigan qadam"],
  "yangi_holat": "javob_keldi | shartnoma | rad_etildi (yoki bo'sh)",
  "nishon_raqam": "holat o'zgartiriladigan KP raqami (yoki bo'sh)",
  "holat_izohi": "nima uchun o'zgardi (menejer aytgani)"
}"""


class EtiborKerak(BaseModel):
    raqam: str
    nega: str = ""


class AzizaNatija(BaseModel):
    """Model javobi. Ko'rsatkich maydonlari ATAYLAB yo'q."""

    xulosa: str = ""
    etibor_kerak: list[EtiborKerak] = Field(default_factory=list)
    tavsiyalar: list[str] = Field(default_factory=list)
    yangi_holat: str = ""
    nishon_raqam: str = ""
    holat_izohi: str = ""


def _kun_farqi(iso: str) -> int:
    """Bugungacha necha kun o'tgan."""
    try:
        sana = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 0
    if sana.tzinfo is None:
        sana = sana.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - sana).days, 0)


class KpKuzatuvchi(Agent):
    """Savdo koordinatori Aziza."""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        kontekst = kontekst or {}

        # Tasdiqdan keyingi ikkinchi chaqiruv: menejer o'zgarishni ko'rib
        # tasdiqladi — endi yozamiz.
        tasdiqlangan = kontekst.get("tasdiqlangan_holat")
        if kontekst.get("tasdiqlandi") and tasdiqlangan:
            return await self._holatni_yoz(
                str(tasdiqlangan.get("raqam") or ""),
                str(tasdiqlangan.get("holat") or ""),
                str(tasdiqlangan.get("izoh") or ""),
            )

        kuzatuv = await self.baza.kp_kuzatuv(chek=MAKS_KP)
        if not kuzatuv:
            return Konvert(
                kim=self.rol,
                holat=Holat.TUGADI,
                natija={"jami": 0, "holatlar": {}, "kp_lar": []},
                manba=[self.kontrakt_manbasi()],
                ishonch=Ishonch.YUQORI,
                izoh="Hali birorta KP kuzatuvga tushmagan.",
            )

        xulosa = await self.baza.kp_xulosasi()
        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += self._kuzatuv_matni(kuzatuv, xulosa)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=AzizaNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = AzizaNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        if natija.yangi_holat:
            return await self._ozgarishni_taklif(natija, kuzatuv)
        return self._javob(natija, kuzatuv, xulosa)

    # --- ma'lumot ------------------------------------------------------------

    def _kuzatuv_matni(
        self, kuzatuv: list[dict[str, Any]], xulosa: dict[str, Any]
    ) -> str:
        qatorlar = [
            "\n\nKP KUZATUVI (baza, joriy holat):",
            f"- jami: {xulosa['jami']} ta",
        ]
        for holat, soni in xulosa["holatlar"].items():
            qatorlar.append(f"  - {HOLAT_MATNI.get(holat, holat)}: {soni} ta")
        qatorlar.append(f"- konversiya: {xulosa['konversiya']}%")
        if xulosa["shartnoma_summasi"]:
            summa = f"{xulosa['shartnoma_summasi']:,.0f}".replace(",", " ")
            qatorlar.append(f"- shartnomalar summasi: {summa} so'm")

        qatorlar.append("\nRO'YXAT (yangisidan eskisiga):")
        for yozuv in kuzatuv:
            kun = _kun_farqi(str(yozuv.get("yaratildi") or ""))
            belgi = ""
            if yozuv.get("holat") == "yuborildi" and kun >= KUTISH_KUNI:
                belgi = "  <-- javobsiz, e'tibor kerak"
            summa = yozuv.get("summa")
            summa_matni = (
                f", {summa:,.0f} so'm".replace(",", " ") if summa else ""
            )
            mijoz = yozuv.get("mijoz") or "mijoz ko'rsatilmagan"
            holat = HOLAT_MATNI.get(yozuv["holat"], yozuv["holat"])
            qatorlar.append(
                f"- {yozuv['raqam']} | {mijoz}{summa_matni} | {holat}"
                f" | {kun} kun oldin{belgi}"
            )
            if yozuv.get("izoh"):
                qatorlar.append(f"    izoh: {yozuv['izoh']}")

        qatorlar.append(
            f"\nDIQQAT: {KUTISH_KUNI} kundan ortiq javobsiz turgan KP lar "
            "yuqorida belgilangan. `etibor_kerak` ga AYNAN shularni kirit."
        )
        return "\n".join(qatorlar)

    # --- holat o'zgartirish --------------------------------------------------

    async def _ozgarishni_taklif(
        self, natija: AzizaNatija, kuzatuv: list[dict[str, Any]]
    ) -> Konvert:
        """Yozishdan OLDIN menejerga ko'rsatadi — o'zi yozmaydi."""
        raqam = natija.nishon_raqam.strip()
        mavjud = {y["raqam"] for y in kuzatuv}
        if raqam not in mavjud:
            namuna = ", ".join(sorted(mavjud)[:5])
            korsatilgan = raqam or "(ko'rsatilmagan)"
            return xato_konvert(
                self.rol,
                f"KP raqami topilmadi: {korsatilgan}. "
                f"Mavjud raqamlardan: {namuna}",
            )
        if natija.yangi_holat not in Baza.KP_HOLATLARI:
            return xato_konvert(
                self.rol,
                f"Noma'lum holat: {natija.yangi_holat}. Ruxsat etilganlari: "
                + ", ".join(Baza.KP_HOLATLARI),
            )

        yozuv = next(y for y in kuzatuv if y["raqam"] == raqam)
        return tasdiq_konverti(
            self.rol,
            f"{raqam} ({yozuv.get('mijoz') or 'mijoz'}) holati "
            f"\"{HOLAT_MATNI.get(yozuv['holat'], yozuv['holat'])}\" dan "
            f"\"{HOLAT_MATNI[natija.yangi_holat]}\" ga o'zgartirilsinmi?",
            natija={
                "taklif_holat": {
                    "raqam": raqam,
                    "holat": natija.yangi_holat,
                    "izoh": natija.holat_izohi,
                },
                "xulosa": natija.xulosa,
            },
        )

    async def _holatni_yoz(self, raqam: str, holat: str, izoh: str) -> Konvert:
        """Tasdiqdan keyin — haqiqiy yozuv."""
        try:
            yozildi = await self.baza.kp_holat_yoz(raqam, holat, izoh)
        except ValueError as xato:
            return xato_konvert(self.rol, str(xato))
        if not yozildi:
            return xato_konvert(self.rol, f"KP topilmadi: {raqam}")

        xulosa = await self.baza.kp_xulosasi()
        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija={
                "ozgardi": {"raqam": raqam, "holat": holat, "izoh": izoh},
                "jami": xulosa["jami"],
                "holatlar": xulosa["holatlar"],
                "konversiya": xulosa["konversiya"],
                "shartnoma_summasi": xulosa["shartnoma_summasi"],
            },
            manba=[self.kontrakt_manbasi()],
            ishonch=Ishonch.YUQORI,
            izoh=f"{raqam}: {HOLAT_MATNI[holat]}",
        )

    # --- javob ---------------------------------------------------------------

    def _javob(
        self,
        natija: AzizaNatija,
        kuzatuv: list[dict[str, Any]],
        xulosa: dict[str, Any],
    ) -> Konvert:
        mavjud = {y["raqam"]: y for y in kuzatuv}

        # Model o'ylab topgan raqamni o'tkazmaymiz.
        etibor = []
        for element in natija.etibor_kerak:
            yozuv = mavjud.get(element.raqam.strip())
            if yozuv is None:
                continue
            etibor.append({
                "raqam": yozuv["raqam"],
                "mijoz": yozuv.get("mijoz") or "",
                "kun": _kun_farqi(str(yozuv.get("yaratildi") or "")),
                "nega": element.nega,
            })

        javobsiz = [
            y for y in kuzatuv
            if y["holat"] == "yuborildi"
            and _kun_farqi(str(y.get("yaratildi") or "")) >= KUTISH_KUNI
        ]

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija={
                "jami": xulosa["jami"],
                "holatlar": xulosa["holatlar"],
                "konversiya": xulosa["konversiya"],
                "shartnoma_summasi": xulosa["shartnoma_summasi"],
                "javobsiz_soni": len(javobsiz),
                "etibor_kerak": etibor,
                "xulosa": natija.xulosa,
                "tavsiyalar": natija.tavsiyalar,
                "kp_lar": [
                    {
                        "raqam": y["raqam"],
                        "mijoz": y.get("mijoz") or "",
                        "summa": y.get("summa"),
                        "holat": y["holat"],
                        "kun": _kun_farqi(str(y.get("yaratildi") or "")),
                    }
                    for y in kuzatuv[:20]
                ],
            },
            manba=[self.kontrakt_manbasi()],
            ishonch=Ishonch.YUQORI,
            izoh=(
                f"{xulosa['jami']} ta KP, {len(javobsiz)} tasi javobsiz, "
                f"konversiya {xulosa['konversiya']}%"
            ),
        )

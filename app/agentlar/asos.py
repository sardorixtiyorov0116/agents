"""Barcha agentlar uchun umumiy asos."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any

import anthropic
from pydantic import BaseModel

from bilim import Qidiruv, Topilma, kontekst_matni, qidiruv
from integrations import ClimaventKlient

from ..baza import Baza
from ..config import sozlama
from ..kontraktlar import Kontrakt
from ..konvert import Konvert, Manba
from ..llm import Llm
from ..profil import Profil, profil
from ..sxema import json_format

MAKS_DAVOM = 3  # `pause_turn` uchun maksimal davom ettirish soni

# Ichki ish jadvallari (mijozlar, buyurtmalar, xodimlar) hali namunaviy
# ma'lumot bilan to'ldirilgan. Javob ishonchli ohangda chiqadi va menejer
# uni haqiqat deb qabul qilishi mumkin — shuning uchun OCHIQ aytamiz.
DEMO_OGOHI = (
    "⚠️ DIQQAT: bu javob NAMUNAVIY ma'lumotdan olindi — haqiqiy mijoz, "
    "buyurtma yoki xodim ma'lumoti emas. Qaror qabul qilish uchun "
    "ishlatmang. Real baza ulangach bu ogohlantirish yo'qoladi."
)

# Anthropic'ning veb qidiruv vositasi (dinamik filtrlash bilan yangi variant).
VEB_QIDIRUV = {"type": "web_search_20260209", "name": "web_search"}
VEB_MAKS_STANDART = 8

# Veb qidiruv so'ralgan, lekin joriy provayder uni qo'llamaydi.
#
# Menejer buni KO'RISHI shart: javob to'liq ko'rinadi, lekin tashqi
# manba umuman yo'q. Ayniqsa Zara (narx) va Karim (raqobat) uchun —
# ularning ishi asosan tashqi ma'lumotga tayanadi.
VEB_YOQ_OGOHI = (
    "veb qidiruv ishlamadi (joriy model uni qo'llamaydi) — "
    "javob faqat ichki manbalarga tayanadi"
)


class Agent(ABC):
    """Agentning umumiy shakli.

    Har agent o'z kontraktiga bog'langan va natijani umumiy konvert
    formatida qaytaradi.
    """

    # Fikrlash chuqurligi. `None` — umumiy sozlama (`AGENT_EFFORT`).
    # Agent o'ylashi emas, faqat matndan parametr ajratishi kerak bo'lsa,
    # bu yerda "low" qo'yiladi: sifat o'zgarmaydi, chiqish tokeni tushadi.
    EFFORT: str | None = None

    def __init__(
        self,
        kontrakt: Kontrakt,
        llm: Llm,
        baza: Baza,
        kompaniya: Profil | None = None,
        api: ClimaventKlient | None = None,
        qidiruv_manbasi: Qidiruv | None = None,
    ):
        self.kontrakt = kontrakt
        self.llm = llm
        self.baza = baza
        # Kompaniya profili — agent kim uchun ishlayotganini biladi.
        self.kompaniya = kompaniya if kompaniya is not None else profil()
        # Ichki API — BIRLAMCHI ma'lumot manbai (faqat o'qish).
        self.api = api if api is not None else ClimaventKlient()
        # Bilim bazasi (RAG) — ishonchli hujjat manbai.
        self.qidiruv = qidiruv_manbasi if qidiruv_manbasi is not None else qidiruv()
        self.ogohlantirish: str = ""

    @property
    def rol(self) -> str:
        return self.kontrakt.rol

    @property
    def korinish(self) -> str:
        return self.kontrakt.korinish

    @abstractmethod
    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        """Vazifani bajaradi va konvert qaytaradi."""

    # --- yordamchilar --------------------------------------------------------

    def chegaralar_matni(self) -> str:
        """Kontraktdagi chegaralarni prompt uchun matnga aylantiradi."""
        qatorlar = "\n".join(f"- {c}" for c in self.kontrakt.chegaralar)
        return f"Sen QILMAYDIGAN ishlar (chegaralar):\n{qatorlar}"

    def demo_ogohi(self) -> str:
        """Ish jadvallari namunaviy bo'lsa — ogohlantirish, aks holda bo'sh."""
        return "" if sozlama().ish_bazasi_haqiqiy else DEMO_OGOHI

    def kontrakt_manbasi(self) -> Manba:
        return Manba(tur="kontrakt", nom=f"{self.rol} kontrakti")

    def veb_qidiruv_bormi(self) -> bool:
        """Joriy model server tomonidagi veb qidiruvni qo'llaydimi?

        Standart — HA: noma'lum mijoz (masalan testdagi soxta) eski
        xatti-harakatni saqlaydi.
        """
        return bool(getattr(self.llm, "VEB_QIDIRUV", True))

    def bilimni_qidir(self, savol: str, chek: int | None = None) -> list[Topilma]:
        """Bilim bazasidan tegishli parchalarni qidiradi.

        Agent FAQAT o'z papkasidan va `umumiy` dan qidiradi — boshqa agentning
        bilim bazasini ko'rmaydi (`bilim.AGENT_PAPKALARI`).
        """
        try:
            return self.qidiruv.agent_uchun(self.rol, savol, chek)
        except Exception as xato:  # baza yo'q/indekslanmagan bo'lsa ish to'xtamaydi
            self.ogohlantirish = f"bilim bazasi mavjud emas ({xato})"
            return []

    def bilim_manbalari(self, topilmalar: list[Topilma]) -> list[Manba]:
        """Topilmalarni konvert manbasiga aylantiradi."""
        manbalar: list[Manba] = []
        korilgan: set[str] = set()
        for topilma in topilmalar:
            nom = topilma.manba_nomi
            if nom in korilgan:
                continue
            korilgan.add(nom)
            manbalar.append(Manba(tur="bilim", nom=nom))
        return manbalar

    def kompaniya_matni(self) -> str:
        """Kompaniya profili — har agent promptining boshiga qo'shiladi.

        Agent shu ma'lumot uchun foydalanuvchidan savol so'ramasligi kerak:
        u allaqachon bilishi lozim bo'lgan narsa.
        """
        if not self.kompaniya.bormi:
            return ""
        # Har agentga faqat o'ziga kerakli bo'limlar (token tejaladi).
        matn = self.kompaniya.agent_uchun(self.rol)
        if not matn:
            return ""
        return (
            "SEN QAYSI KOMPANIYA UCHUN ISHLAYSAN:\n\n"
            f"{matn}\n\n"
            "Bu ma'lumot senga ALLAQACHON berilgan — u haqida foydalanuvchidan\n"
            "savol so'rama. \"Kompaniya nomi ko'rsatilmagan\", \"mahsulot noma'lum\"\n"
            "kabi javob berma: yuqoridagi profilga tayan.\n"
            "Profilda YO'Q narsani esa o'ylab topma — o'sha yerda yo'qligini ayt.\n"
            "Brend taqiqlariga qat'iy amal qil.\n\n"
            "---\n\n"
        )

    @staticmethod
    def topshiriq_matni(vazifa: str, kontekst: dict[str, Any] | None) -> str:
        """Vazifa + kontekstni bitta foydalanuvchi xabariga yig'adi."""
        if not kontekst:
            return f"Topshiriq:\n{vazifa}"
        juftlar = "\n".join(f"- {k}: {v}" for k, v in kontekst.items())
        return f"Topshiriq:\n{vazifa}\n\nKontekst:\n{juftlar}"

    # --- model bilan muloqot -------------------------------------------------

    async def modelga_sorov(
        self,
        topshiriq: str,
        tizim_prompt: str,
        natija_modeli: type[BaseModel],
        json_skelet: str,
        veb_qidiruv: bool = False,
        veb_maks: int = VEB_MAKS_STANDART,
        rasmlar: list[tuple[str, bytes]] | None = None,
        effort: str | None = None,
    ) -> Any:
        """Modelga so'rov yuboradi va javob obyektini qaytaradi.

        `rasmlar` — `(media_type, baytlar)` juftliklari. Matn bilan birga
        yuboriladi: masalan Instagram videosining birinchi kadri, uni
        modelning o'zi ko'rib tahlil qiladi.

        Ikkita nozik holatni o'zi hal qiladi:
          - `pause_turn` (server vositasi tsikli cheklovga yetdi) — davom ettiradi;
          - `output_config.format` rad etilsa — matn rejimida JSON so'raydi
            (`json_skelet` promptga qo'shiladi) va buni `ogohlantirish`ga yozadi.
        """
        s = sozlama()
        # Chaqiruv > agent > umumiy sozlama. Bitta agentning ba'zi ishi
        # og'ir, ba'zisi yengil bo'lishi mumkin.
        effort = effort or self.EFFORT or s.agent_effort
        soro: dict[str, Any] = {
            # Profil + agent prompti — ikkalasi ham barqaror prefiks, keshlanadi.
            "system": [
                {"type": "text", "text": self.kompaniya_matni() + tizim_prompt,
                 "cache_control": {"type": "ephemeral"}}
            ],
            "output_config": {
                "effort": effort,
                "format": json_format(natija_modeli),
            },
        }
        if veb_qidiruv and not self.veb_qidiruv_bormi():
            # JIM XATO EDI: veb qidiruv faqat Anthropic'da bor, Gemini
            # va lokal modelda so'rov jimgina tashlanardi. Agent esa
            # izlagan deb javob yozaverardi — manbasiz "topilma"
            # menejerga haqiqatdek ko'rinardi.
            #
            # Ikki tomonga ham aytiladi: modelga (izlay olmaysan) va
            # menejerga (`ogohlantirish` javobga chiqadi).
            veb_qidiruv = False
            self.ogohlantirish = "; ".join(
                filter(None, [self.ogohlantirish, VEB_YOQ_OGOHI])
            )
            topshiriq += (
                "\n\nDIQQAT: VEB QIDIRUV HOZIR ISHLAMAYDI. Internetdan "
                "yangi ma'lumot ololmaysan. Faqat topshiriqda berilgan "
                "va o'zingdagi ichki manbalardan foydalanasan. Izlab "
                "topgandek yozmaysan — ma'lumot yetishmasa buni OCHIQ "
                "ayt."
            )
        if veb_qidiruv:
            soro["tools"] = [dict(VEB_QIDIRUV) | {"max_uses": veb_maks}]

        def tana(matn: str) -> Any:
            if not rasmlar:
                return matn      # rasm yo'q — oddiy matn, xabar shakli o'zgarmaydi
            # Matn OXIRIDA: model avval rasmlarni ko'rib, keyin savolni o'qiydi.
            return [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": tur,
                        "data": base64.b64encode(baytlar).decode(),
                    },
                }
                for tur, baytlar in rasmlar
            ] + [{"type": "text", "text": matn}]

        try:
            return await self._davom_bilan(
                [{"role": "user", "content": tana(topshiriq)}], soro
            )
        except anthropic.BadRequestError as xato:
            xabar = str(xato)
            if "format" not in xabar and "output_config" not in xabar:
                raise
            self.ogohlantirish = "structured output qabul qilinmadi — matn rejimida JSON so'raldi"
            soro["output_config"] = {"effort": effort}
            return await self._davom_bilan(
                [{"role": "user", "content": tana(f"{topshiriq}\n\n{json_skelet}")}], soro
            )

    async def _davom_bilan(self, xabarlar: list[dict[str, Any]], soro: dict[str, Any]) -> Any:
        """`pause_turn` bo'lsa, server tomonidagi tsiklni davom ettiradi."""
        for _ in range(MAKS_DAVOM + 1):
            javob = await self.llm.javob(messages=xabarlar, **soro)
            if getattr(javob, "stop_reason", None) != "pause_turn":
                return javob
            # Hujjatlashtirilgan davom ettirish shakli: assistant javobini
            # tarixga qo'shib, qayta yuboramiz (qo'shimcha "Continue." yozmaymiz).
            xabarlar = [xabarlar[0], {"role": "assistant", "content": javob.content}]
        return javob

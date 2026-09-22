"""Router (orkestrator) — tizimning miyasi.

Router hech qanday vazifani o'zi BAJARMAYDI. U faqat:
  1) niyatni tushunadi (nechta vazifa bor),
  2) kontraktlarga (ayniqsa "chegaralar") qarab agent(lar)ni tanlaydi,
  3) "inson tasdig'i qachon" qismiga qarab xavf tekshiruvini o'tkazadi.

Birinchi versiyada to'liq LLM-router. Keyinchalik tez-tez takrorlanadigan
oddiy so'rovlar uchun qoidalar qo'shish mumkin (optimizatsiya).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .config import sozlama
from .kontraktlar import Kontrakt, kontraktlar_matni, reyestr
from .llm import Llm, json_ajrat, matn_yig
from .profil import Profil, profil

log = logging.getLogger(__name__)

# --- KP zanjiridagi ortiqcha qadamlar --------------------------------------
#
# O'lchandi (135 ta izdan, 2026-08-19): AYNI BIR so'rov turlicha zanjir olgan
#     hvac-calc -> product-spec -> proposal-builder                    80 s
#     hvac-calc -> product-spec -> sales-strategy -> proposal-builder  105-156 s
#     hvac-calc -> product-spec -> price-monitor  -> proposal-builder  225-230 s
#
# Ikkala qo'shimcha qadam ham KP uchun KERAK EMAS:
#   price-monitor  — BOZOR/raqobat narxini qaraydi. KP narxi esa ichki
#                    API'dan olinadi (`TijoratMenejeri._backend_narxi`).
#   sales-strategy — savdo taktikasi yozadi. KP matnini Temur o'zi yozadi.
#
# Shuning uchun ular KP zanjiridan OLIB TASHLANADI — foydalanuvchi ularni
# ATAYLAB so'ramagan bo'lsa. So'rov matnida quyidagi so'zlar bo'lsa, demak
# atayin so'ralgan va qadam qoldiriladi.
ORTIQCHA_KP_QADAMI: dict[str, re.Pattern[str]] = {
    "price-monitor": re.compile(
        r"bozor\s*narx|raqib|raqobat|konkurent|рынок|рыночн|конкурент|"
        r"market\s*price|narxni\s*kuzat|narx\s*monitoring|qancha\s*turadi\s*bozor",
        re.I,
    ),
    "sales-strategy": re.compile(
        r"strategi|страteg|стратег|taktika|тактик|chegirma\s*siyosat|"
        r"qanday\s*sot|savdo\s*rejasi|sales\s*strategy",
        re.I,
    ),
}
KP_AGENTI = "proposal-builder"

TIZIM_PROMPT = """Sen kompaniya ichidagi agentlar tizimining ROUTER'isan (orkestrator).

Sen O'ZING hech qanday vazifani bajarmaysan: narx qidirmaysan, matn yozmaysan,
tahlil qilmaysan. Sening yagona ishing — so'rovni tahlil qilib, qaysi agent(lar)
ni qanday tartibda ishga solish kerakligini aniqlash.

QAROR QADAMLARI:
0) Niyat TURINI aniqla:
   - TIZIM SAVOLI — foydalanuvchi tizimning O'ZI haqida so'rayapti: qanday
     agentlar bor, kim nima qiladi, falon agent nimaga qodir, chegarasi
     qayerda, sen nima qila olasan, qanday so'rov berish mumkin, xavf va
     tasdiq qoidalari. Bunda `tizim_savoli=true` va `javob` ga TO'LIQ javob
     yozasan (pastdagi qoidaga qara). Agent chaqirilmaydi, qadamlar bo'sh.
   - VAZIFA — ish bajarish kerak: agent(lar) tanlanadi.

1) Niyatni tushun: so'rovda nechta alohida vazifa bor?
   - bitta vazifa -> bitta agent
   - bir nechta vazifa -> zanjir (ketma-ket qadamlar)
2) Agent(lar)ni tanla: har agentning kontraktiga, ayniqsa "QILMAYDI (chegaralar)"
   qismiga qara. Chegaralar agentlarni bir-biridan ajratadi (narx -> price-monitor,
   raqib -> competitor-watch, spesifikatsiya -> product-spec va h.k.).
   Hech qaysi agent mos kelmasa — mos_agent_yoq=true qilib ochiq ayt, zo'rlab
   yubormang.
3) Xavf tekshiruvi: tanlangan agentning "Inson tasdig'i qachon" qismiga qara.
   Shu so'rov uchun tasdiq kerak bo'lsa, qadamda tasdiq_kerak=true va sababini yoz.
   Xavf darajasi "yuqori" bo'lgan agentlar (hr-assist, legal-review) uchun tasdiq
   deyarli har doim kerak.
4) Aniqlik tekshiruvi: agentlarni ishga solish uchun zarur ma'lumot bormi?

SUHBAT DAVOMI:
So'rovda `[oldingi so'rov]` va `[yangi xabar]` belgilari bo'lsa — bu
suhbat davomi. Foydalanuvchi oldin so'ragan, tizim aniqlashtirish
so'ragan, endi javob keldi.
- Odatda ikkalasini BIRGA olasan: `[yangi xabar]` — yetishmagan
  ma'lumot ("3 metr, 15 kishi").
- LEKIN `[yangi xabar]` mustaqil, TO'LIQ so'rov bo'lsa (mavzu
  o'zgargan: "ВК-250С haqida ayting"), `[oldingi so'rov]` ni TASHLAB
  YUBOR va faqat yangisini bajar.
- Belgilarning o'zini `vazifa` ga ko'chirma.

ANIQLASHTIRISH QOIDALARI (juda muhim):
- Kompaniya, mahsulot yo'nalishlari, raqobatchilar, hudud, valyuta — bular
  KOMPANIYA bo'limida berilgan. Bular haqida SAVOL BERMA.
- DIQQAT: profilda ma'lumot borligi agentni chaqirmaslik uchun sabab EMAS.
  Sen javobni O'ZING yozmaysan. "Raqiblarimiz kimlar" kabi so'rovda ham
  tegishli agentni (competitor-watch) ishga sol — u profildagi ma'lumotni
  ishlatib to'liq javob, manba va xulosa tayyorlaydi. mos_agent_yoq faqat
  vazifa hech bir kontraktga tushmaganda qo'yiladi.
- Mahsulot katalogi, uning xususiyatlari va narx holati agentlar tomonidan
  ICHKI API'dan olinadi. "Qaysi mahsulot bor?", "xususiyatlari qanday?" —
  bular uchun ham savol berma, agent o'zi topadi.
- Savol FAQAT chindan yetishmayotgan va faqat INSON ayta oladigan narsa uchun
  beriladi. Masalan: qaysi hujjat tekshirilsin (matn berilmagan), qaysi
  nomzod, qaysi davr uchun hisobot, qaysi aniq mahsulot (agar so'rovda
  umuman ko'rsatilmagan bo'lsa).
- Shubha bo'lsa — SAVOL BERMA, agentni ishga sol: agent o'zi topadi yoki
  "topilmadi" deb aytadi. Bo'sh savol berish yomonroq.
- Aniqlashtirish kerak bo'lsa: aniqlik_kerak=true, qadamlar=[] va
  `savollar` ga 1-3 ta ANIQ savol yoz (umumiy emas).

TIZIM SAVOLIGA JAVOB QANDAY BO'LADI:
Javobni AGENT KONTRAKTLARIDAN olasan — boshqa manba kerak emas.
- Quruq ro'yxat berma. Har agent uchun: nima QILA OLADI (2-3 aniq misol
  bilan) va nima QILMAYDI (chegarasi).
- Bitta agent haqida so'ralsa — o'sha agentga chuqur javob ber.
- Javob oxirida AMALIY taklif: "Masalan shunday so'rov berishingiz mumkin:
  …" — 1-3 ta tayyor so'rov namunasi.
- O'zbek tilida, ravon matn bilan yoz (JSON emas, punktlar mumkin).

KONSTRUKTIV RAD ETISH (mos_agent_yoq dan OLDIN majburiy ikki tekshiruv):
1) PARCHALASH: so'rovni mayda vazifalarga bo'lib, mavjud agentlardan
   foydali zanjir tuzsa bo'ladimi? Bo'lsa — o'sha zanjirni QUR (qadamlar
   bilan), rad etma. Masalan "savdo rejasi" uchun to'g'ridan-to'g'ri agent
   bo'lmasa ham: bozor tahlili (competitor-watch) + o'tgan savdo raqamlari
   (data-query) + kampaniya (marketing) foydali natija beradi.
2) QISMAN BAJARISH: so'rovning bir qismi bajarilsa — o'sha qismni bajar,
   qolganini `taklif` da ochiq ayt.

Chindan hech nima qilib bo'lmasagina `mos_agent_yoq=true`. Bunda ham
`taklif` MAJBURIY va u uch qismdan iborat:
  (a) nima qila olmasliging — qisqa;
  (b) nima qila OLASAN — eng yaqin imkoniyat;
  (c) qanday so'rov berilsa foyda bo'ladi — aniq namuna.
Quruq "agent yo'q" + agentlar ro'yxati — YAROQSIZ javob.

QOIDALAR:
- `agent` maydoniga faqat berilgan rol nomlarini yoz.
- `vazifa` — shu agent uchun aniq, qisqa topshiriq (foydalanuvchi tilida).
- Zanjirda oldingi agentning natijasi keyingisiga input bo'ladi; shuni hisobga
  olib qadamlarni to'g'ri tartibda joyla.
- Bitta agentni takrorlamang, keraksiz qadam qo'shmang.
- Javob faqat so'ralgan JSON sxemasi bo'yicha bo'ladi, boshqa matn yozmang."""


class RejaQadam(BaseModel):
    """Zanjirning bitta qadami."""

    agent: str
    vazifa: str
    tasdiq_kerak: bool = False
    tasdiq_sababi: str = ""


class Reja(BaseModel):
    """Routerning qarori."""

    # `niyat` endi sxemada majburiy emas (tezlik uchun) — standart qiymat
    # bo'lishi shart, aks holda model uni yozmagan chaqiruv yiqiladi.
    niyat: str = ""
    vazifa_soni: int = 0
    qadamlar: list[RejaQadam] = Field(default_factory=list)
    mos_agent_yoq: bool = False
    # Zarur ma'lumot yetishmayapti — agentlar chaqirilmaydi, savol beriladi.
    aniqlik_kerak: bool = False
    savollar: list[str] = Field(default_factory=list)
    # Tizim haqidagi savol — router o'zi javob beradi, agent chaqirilmaydi.
    tizim_savoli: bool = False
    javob: str = ""
    # Konstruktiv taklif: nima qila olmaydi, nima qila oladi, qanday so'rash.
    taklif: str = ""
    izoh: str = ""


def reja_sxemasi(rollar: list[str]) -> dict[str, Any]:
    """Router uchun qat'iy JSON Schema (agent nomlari enum sifatida).

    MAJBURIY MAYDONLAR QASDDAN KAM. `required` ga qo'yilgan har maydonni
    model HAR chaqiruvda yozadi — hatto kerak bo'lmasa ham. `javob` va
    `taklif` esa uzun matn maydonlari: ular majburiy bo'lganda oddiy
    "qaysi agent" qaroriga 500+ chiqish tokeni ketardi va javob bir necha
    soniyaga cho'zilardi.

    Endi majburiysi faqat QARORNING O'ZI. Qolganini model kerak bo'lganda
    yozadi, `Reja` modelida esa ularning hammasi standart qiymatga ega.

    Maydonlar tartibi ham muhim: model yuqoridan pastga yozadi, shuning
    uchun `qadamlar` birinchi turadi — qaror darrov chiqadi.
    """
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "qadamlar",
                "mos_agent_yoq",
                "aniqlik_kerak",
                "tizim_savoli",
            ],
            "properties": {
                "qadamlar": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["agent", "vazifa", "tasdiq_kerak", "tasdiq_sababi"],
                        "properties": {
                            "agent": {"type": "string", "enum": rollar},
                            "vazifa": {"type": "string"},
                            "tasdiq_kerak": {"type": "boolean"},
                            "tasdiq_sababi": {"type": "string"},
                        },
                    },
                },
                "mos_agent_yoq": {"type": "boolean"},
                "aniqlik_kerak": {
                    "type": "boolean",
                    "description": "Zarur ma'lumot yetishmayapti — savol berish kerak",
                },
                "savollar": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "FAQAT aniqlik_kerak=true bo'lganda: 1-3 ta aniq savol."
                    ),
                },
                "tizim_savoli": {
                    "type": "boolean",
                    "description": "Tizimning o'zi haqida savol — router javob beradi",
                },
                "javob": {
                    "type": "string",
                    "description": (
                        "FAQAT tizim_savoli=true bo'lganda to'ldiriladi. "
                        "Aks holda bu maydonni umuman yozma."
                    ),
                },
                "taklif": {
                    "type": "string",
                    "description": (
                        "FAQAT mos_agent_yoq=true bo'lganda to'ldiriladi: "
                        "nima qila olaman va qanday so'rash kerak. "
                        "Aks holda bu maydonni umuman yozma."
                    ),
                },
                "izoh": {
                    "type": "string",
                    "description": "Qaror sababi. Kerak bo'lmasa yozma.",
                },
                "niyat": {
                    "type": "string",
                    "description": "So'rovning qisqa qayta ifodasi (ixtiyoriy)",
                },
                "vazifa_soni": {"type": "integer"},
            },
        },
    }


class Router:
    """LLM asosidagi orkestrator."""

    def __init__(
        self,
        llm: Llm,
        kontraktlar: dict[str, Kontrakt] | None = None,
        kompaniya: Profil | None = None,
    ):
        self.llm = llm
        self.kontraktlar = kontraktlar or reyestr()
        self.kompaniya = kompaniya if kompaniya is not None else profil()

    async def reja_tuz(self, sorov: str, kontekst: dict[str, Any] | None = None) -> Reja:
        """So'rovdan reja tuzadi.

        IKKI BOSQICHLI, ataylab. Birinchi chaqiruv kontraktlarning QISQA
        shakli bilan ketadi — agent tanlash uchun shuning o'zi yetarli va
        u ikki barobar arzon. Faqat TIZIM SAVOLI ("kim nima qiladi?")
        chiqqanda to'liq kontraktlar bilan qayta so'raymiz: bunday javob
        aynan kontrakt tafsilotidan yoziladi.

        Tizim savoli kam uchraydi, shuning uchun o'rtacha narx tushadi.
        """
        reja = await self._chaqir(sorov, kontekst, qisqa=True)
        if reja is None:
            return self._rad_javobi(sorov)

        # `_xavf_tekshiruvi` javobsiz "tizim savoli" ni bekor qiladi — shu
        # sababli qayta so'rashdan OLDIN uni o'tkazamiz, aks holda bekor
        # qilinadigan javob uchun ikkinchi chaqiruv qilib pul sarflaymiz.
        reja = self._ortiqchani_olib_tashla(self._xavf_tekshiruvi(reja), sorov)
        if not reja.tizim_savoli:
            return reja

        toliq = await self._chaqir(sorov, kontekst, qisqa=False)
        if toliq is None:
            return reja
        return self._ortiqchani_olib_tashla(self._xavf_tekshiruvi(toliq), sorov)

    async def _chaqir(
        self, sorov: str, kontekst: dict[str, Any] | None, qisqa: bool
    ) -> Reja | None:
        """Bitta model chaqiruvi. Model rad etsa `None` qaytaradi."""
        s = sozlama()

        kontekst_matni = ""
        if kontekst:
            juftlar = "\n".join(f"- {k}: {v}" for k, v in kontekst.items())
            kontekst_matni = f"\n\nQo'shimcha kontekst:\n{juftlar}"

        javob = await self.llm.javob(
            system=self._tizim_bloklari(qisqa),
            messages=[
                {
                    "role": "user",
                    "content": f"Foydalanuvchi so'rovi:\n{sorov}{kontekst_matni}",
                }
            ],
            output_config={
                "effort": s.router_effort,
                "format": reja_sxemasi(list(self.kontraktlar.keys())),
            },
        )

        if getattr(javob, "stop_reason", None) == "refusal":
            return None

        try:
            return Reja.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            raise RouterXatosi(f"Router javobini o'qib bo'lmadi: {xato}") from xato

    def _tizim_bloklari(self, qisqa: bool) -> list[dict[str, Any]]:
        tizim: list[dict[str, Any]] = [{"type": "text", "text": TIZIM_PROMPT}]
        if self.kompaniya.bormi:
            tizim.append(
                {
                    "type": "text",
                    "text": (
                        "KOMPANIYA (bu ma'lumot allaqachon ma'lum — "
                        "buning uchun savol bermang):\n\n" + self.kompaniya.qisqa()
                    ),
                }
            )
        tizim.append(
            {
                "type": "text",
                "text": "AGENT KONTRAKTLARI:\n\n"
                + kontraktlar_matni(self.kontraktlar, qisqa=qisqa),
                # Profil + kontraktlar barqaror prefiks — keshlaymiz.
                "cache_control": {"type": "ephemeral"},
            }
        )
        return tizim

    @staticmethod
    def _rad_javobi(sorov: str) -> Reja:
        return Reja(
            niyat=sorov,
            mos_agent_yoq=True,
            izoh="Model bu so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati).",
        )

    def _ortiqchani_olib_tashla(self, reja: Reja, sorov: str) -> Reja:
        """KP zanjiridan ATAYLAB so'ralmagan qimmat qadamlarni olib tashlaydi.

        Model bir xil so'rovga har safar boshqacha zanjir tuzadi — o'lchandi.
        Shuning uchun bu qoida promptda emas, KODDA: natija barqaror bo'lsin.
        """
        nomlar = {q.agent for q in reja.qadamlar}
        if KP_AGENTI not in nomlar:
            return reja

        qoldirilgan: list[RejaQadam] = []
        for qadam in reja.qadamlar:
            shablon = ORTIQCHA_KP_QADAMI.get(qadam.agent)
            if shablon is not None and not shablon.search(sorov):
                log.info(
                    "KP zanjiridan %s olib tashlandi (so'rovda so'ralmagan)",
                    qadam.agent,
                )
                continue
            qoldirilgan.append(qadam)
        reja.qadamlar = qoldirilgan
        return reja

    def _xavf_tekshiruvi(self, reja: Reja) -> Reja:
        """Kontraktdagi xavf darajasini majburan qo'llaydi.

        LLM adashsa ham, xavfi "yuqori" bo'lgan agent tasdiqsiz o'tmasligi kerak
        (9-bo'lim: Hilola va Laziz natijasi inson tasdig'isiz chiqmaydi).
        """
        # Tizim savoli hamma narsadan ustun: agent chaqirilmaydi.
        if reja.tizim_savoli:
            if reja.javob.strip():
                reja.qadamlar = []
                reja.aniqlik_kerak = False
                reja.mos_agent_yoq = False
                return reja
            # Javobsiz "tizim savoli" foydasiz — oddiy yo'l bilan davom etamiz.
            reja.tizim_savoli = False

        # Aniqlashtirish so'ralgan bo'lsa, qadamlar bajarilmaydi.
        if reja.aniqlik_kerak:
            reja.savollar = [s.strip() for s in reja.savollar if s.strip()]
            if not reja.savollar:
                # Savolsiz "aniqlik kerak" — foydasiz. Rejani davom ettiramiz.
                reja.aniqlik_kerak = False
            else:
                reja.qadamlar = []
                return reja

        haqiqiy: list[RejaQadam] = []
        for qadam in reja.qadamlar:
            kontrakt = self.kontraktlar.get(qadam.agent)
            if kontrakt is None:
                # Sxema enum bilan cheklaydi, lekin himoya bo'lib turadi.
                reja.izoh = (
                    f"{reja.izoh} [router mavjud bo'lmagan agentni tanladi: {qadam.agent}]"
                ).strip()
                continue
            if kontrakt.xavf.value == "yuqori" and not qadam.tasdiq_kerak:
                qadam.tasdiq_kerak = True
                qadam.tasdiq_sababi = (
                    qadam.tasdiq_sababi
                    or f"{kontrakt.korinish} — yuqori xavfli agent, natija tasdiqdan o'tadi"
                )
            haqiqiy.append(qadam)

        reja.qadamlar = haqiqiy
        if not haqiqiy:
            reja.mos_agent_yoq = True
        if reja.vazifa_soni <= 0:
            reja.vazifa_soni = len(haqiqiy)
        return reja


class RouterXatosi(RuntimeError):
    """Router qaror qabul qila olmadi."""

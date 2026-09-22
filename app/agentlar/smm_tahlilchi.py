"""SMM tahlilchisi Nilufar — `smm-analyst`.

Maqsad: Instagram profil havolasi berilsa, uni to'liq tahlil qiladi.

O'ZGARMAS QOIDALAR (kodda, promptda emas):
  - RAQAMLAR API'dan olinadi va model javobidan OLINMAYDI: ko'rishlar, layk,
    obunachi soni sxemada umuman yo'q — model ularni qaytara olmaydi;
  - postga murojaat `raqam` orqali bo'ladi, havolani kod qo'yadi — mavjud
    bo'lmagan post ko'rsatib bo'lmaydi;
  - agent hech narsa nashr qilmaydi va izohga javob yozmaydi.

CHEKLOV: videoning o'zi (birinchi kadr, ovoz, montaj) API'da yo'q. "Hook"
deganda faqat SARLAVHA matni tushuniladi va bu foydalanuvchiga aytiladi.
"""

from __future__ import annotations

import re
import statistics
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from integrations import InstagramKlient, InstagramXatosi, Profil

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Promptga tushadigan post soni (sarlavha + kommentlar bilan hajm oshadi).
MAKS_POST = 25
MAKS_KOMMENT = 8
# Shundan kam post bo'lsa xulosa ishonchi past.
YETARLI_POST = 6

# Nechta eng ko'p ko'rilgan videoning muqovasi modelga yuboriladi.
MAKS_MUQOVA = 6

# Kommentlarni mavzuga ajratish. Modelning o'zi ham ajratadi, lekin
# SANOQ kodda bo'lishi kerak: "30 marta so'ralgan" degan raqamni model
# taxmin qilmasin, biz sanaymiz.
KOMMENT_MAVZULARI: tuple[tuple[str, str], ...] = (
    ("narx", r"narx|нарх|цена|стоимость|qancha|скольк|pochom|почём|почем|price"),
    ("yetkazib berish", r"yetkaz|достав|dostav|jo['`]?nat|отправ"),
    ("mavjudligi", r"bormi|мавжуд|есть ли|в наличии|qoldiq|остат"),
    ("o'rnatish", r"o['`]?rnat|montaj|монтаж|установ|ustanovka"),
    ("kafolat", r"kafolat|гарант|garantiya"),
    ("texnik savol", r"quvvat|мощность|o['`]?lcham|размер|xarakteristika|характеристик"),
    ("manzil / do'kon", r"manzil|адрес|qayerda|где|filial|магазин|do['`]?kon"),
    ("shikoyat", r"yomon|плох|ishlamadi|не работа|obman|обман|aldov|brak|брак"),
)

VIDEO_IZOHI = (
    "Diqqat: Instagram API videoning O'ZINI bermaydi — ovoz, montaj va "
    "keyingi kadrlar ko'rinmaydi. Lekin eng ko'p ko'rilgan videolarning "
    "MUQOVASI (birinchi kadr) rasm sifatida biriktirilgan — ekrandagi "
    "yozuv, yuz, rang va kompozitsiyani o'sha rasmlardan bahola. "
    "Muqovasi biriktirilmagan post uchun faqat sarlavhaga tayan va buni "
    "ochiq ayt."
)

TIZIM_PROMPT = """Sen "SMM tahlilchisi Nilufar" — Instagram profilini tahlil
qiladigan agentsan.

VAZIFAN: berilgan PROFIL MA'LUMOTIDAN foydali xulosa chiqarish — qanday
kontent ishlayapti, nima uchun, va nima qilish kerak.

QAT'IY QOIDALAR:
1) RAQAM YOZMAYSAN. Ko'rishlar, layk, obunachi soni — hammasi tayyor
   berilgan va javobda takrorlanmaydi. Sen faqat NIMA UCHUN shunday
   ekanini tushuntirasan.
2) POSTGA `raqam` ORQALI murojaat qilasan (ro'yxatdagi tartib raqami).
   Havolani o'zing yozmaysan.
3) HOOK TAHLILI ikki manbaga tayanadi:
   a) SARLAVHA matni — hamma post uchun bor;
   b) MUQOVA RASMI — faqat biriktirilgan postlar uchun. Rasmda ekrandagi
      yozuvni O'QI, yuz bor-yo'qligini, plan yaqinligini, rang va
      kontrastni bahola.
   Muqovasi BIRIKTIRILMAGAN post haqida vizual gap yozmaysan — sen uni
   ko'rmading. "Videoda yaqin plan ishlatgan" degan gap faqat rasmni
   ko'rgan bo'lsang o'rinli.
   OVOZ, MONTAJ va KEYINGI KADRLAR hech qaysi holatda ko'rinmaydi —
   ular haqida taxmin qilmaysan.
4) KOMMENTLARDAN takrorlanuvchi savol va shikoyatlarni ajratasan. Bitta
   odamning fikrini "hamma shunday deyapti" deb ko'rsatmaysan.
5) BASHORAT QILMAYSAN: "bu 100 ming ko'rish oladi" kabi gap yozmaysan.
6) Ma'lumot kam bo'lsa (post soni oz) — xulosani ehtiyotkor qilasan va
   buni `cheklovlar` da aytasan.

SEN QILMAYDIGAN ISHLAR:
- Kontent nashr qilmaysan, izohga javob yozmaysan.
- Kampaniya matni yozmaysan (bu Marketolog Malikaning ishi).
- Reklama byudjeti haqida qaror qilmaysan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "umumiy_baho": "profil haqida 2-3 jumla",
  "kontent_turlari": ["qanday kontent chiqarilgan"],
  "ishlagan_postlar": [
    {"raqam": 1, "nega_ishladi": "sabab (sarlavha, mavzu, format)"}
  ],
  "hook_naqshlari": [
    {"naqsh": "masalan: savol bilan boshlash", "misol": "sarlavhadan parcha",
     "izoh": "qanchalik tez-tez va qanday natija bilan"}
  ],
  "komment_muammolari": [
    {"mavzu": "takrorlanuvchi savol yoki shikoyat", "necha_marta": 3,
     "izoh": "nima qilish kerak"}
  ],
  "tavsiyalar": ["aniq, bajariladigan tavsiya"],
  "cheklovlar": ["xulosani cheklaydigan narsa (kam post, kam komment)"]
}"""


class IshlaganPost(BaseModel):
    raqam: int
    nega_ishladi: str = ""


class Hook(BaseModel):
    naqsh: str
    misol: str = ""
    izoh: str = ""


class KommentMuammosi(BaseModel):
    mavzu: str
    necha_marta: int = 0
    izoh: str = ""


class NilufarNatija(BaseModel):
    """Model javobi. Ko'rsatkich maydonlari ATAYLAB yo'q."""

    umumiy_baho: str = ""
    kontent_turlari: list[str] = Field(default_factory=list)
    ishlagan_postlar: list[IshlaganPost] = Field(default_factory=list)
    hook_naqshlari: list[Hook] = Field(default_factory=list)
    komment_muammolari: list[KommentMuammosi] = Field(default_factory=list)
    tavsiyalar: list[str] = Field(default_factory=list)
    cheklovlar: list[str] = Field(default_factory=list)


class SmmTahlilchi(Agent):
    """SMM tahlilchisi Nilufar."""

    def __init__(self, *args: Any, instagram: InstagramKlient | None = None, **kw: Any):
        super().__init__(*args, **kw)
        self.instagram = instagram if instagram is not None else InstagramKlient()

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""

        if not self.instagram.sozlanganmi():
            return xato_konvert(
                self.rol,
                "Instagram ulanmagan. `.env` fayliga INSTAGRAM_TOKEN va "
                "INSTAGRAM_USER_ID qo'shing (Meta Graph API, Business akkaunt).",
            )

        nishon = self._nishon(vazifa, kontekst)
        if not nishon:
            return xato_konvert(
                self.rol,
                "Qaysi profilni tahlil qilay? Instagram havolasini yoki "
                "nomini yozing (masalan instagram.com/climaventuz).",
            )

        try:
            profil = await self.instagram.tahlil(nishon, postlar=MAKS_POST)
        except InstagramXatosi as xato:
            return xato_konvert(self.rol, str(xato))

        if not profil.postlar:
            return xato_konvert(
                self.rol,
                f"@{profil.nomi} topildi, lekin ochiq post yo'q — tahlil qilishga "
                "ma'lumot yetmaydi.",
            )

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += self._profil_matni(profil)

        rasmlar, muqovali = await self._muqovalar(profil)
        if muqovali:
            topshiriq += (
                "\n\nBIRIKTIRILGAN MUQOVALAR (yuqoridagi ro'yxat tartibida): "
                + ", ".join(f"#{r}" for r in muqovali)
                + ". Ularni post raqami bo'yicha bog'la."
            )

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=NilufarNatija,
                json_skelet=JSON_SKELET,
                rasmlar=rasmlar,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        try:
            natija = NilufarNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return self._javob(profil, natija)

    # --- yordamchilar --------------------------------------------------------

    @staticmethod
    def _nishon(vazifa: str, kontekst: dict[str, Any] | None) -> str:
        """So'rovdan profil havolasini/nomini ajratadi."""
        from integrations import foydalanuvchi_nomi

        manbalar = [vazifa, *(str(v) for v in (kontekst or {}).values())]
        for matn in manbalar:
            for bolak in str(matn).split():
                if "instagram.com" in bolak or bolak.startswith("@"):
                    nom = foydalanuvchi_nomi(bolak)
                    if nom:
                        return nom
        return ""

    def _profil_matni(self, profil: Profil) -> str:
        """Profil ma'lumotini promptga yozadi (raqamlar tayyor holda)."""
        reelslar = profil.reelslar
        korishlar = [p.korishlar for p in reelslar if p.korishlar > 0]
        ortacha = statistics.median(korishlar) if korishlar else 0

        qatorlar = [
            f"\n\nPROFIL: @{profil.nomi}",
            f"- obunachilar: {profil.obunachilar:,}".replace(",", " "),
            f"- jami post: {profil.postlar_soni}",
            f"- tahlilga olingan: {len(profil.postlar)} ta "
            f"(shundan {len(reelslar)} ta video/reels)",
        ]
        if ortacha:
            qatorlar.append(
                f"- video ko'rishlar medianasi: {ortacha:,.0f}".replace(",", " ")
            )
        # Insights — faqat o'z akkauntimizda. Boshqa profilda bu ma'lumot
        # umuman yo'q va model buni BILISHI kerak, aks holda "qamrov past"
        # kabi asossiz xulosa chiqadi.
        if profil.ozimizniki:
            qatorlar.append(
                "\nBU BIZNING AKKAUNTIMIZ — Insights ma'lumoti bor: qamrov "
                "(nechta ODAM ko'rdi), saqlashlar, ulashishlar, profilga "
                "o'tish va obuna. Xulosani ko'rishlar soniga emas, AYNAN shu "
                "ko'rsatkichlarga qur: saqlash va ulashish kontent qiymatini, "
                "profil tashrifi va obuna esa biznes natijasini ko'rsatadi."
            )
            if profil.insights_izohi:
                qatorlar.append(f"Insights qisman keldi: {profil.insights_izohi}")
        else:
            qatorlar.append(
                "\nBU BOSHQA PROFIL — qamrov, saqlash va ulashish ma'lumoti "
                "YO'Q (Meta boshqa akkauntning bu raqamlarini bermaydi). "
                "Ular haqida xulosa chiqarma."
            )

        if profil.auditoriya.bormi:
            a = profil.auditoriya
            qatorlar.append("\nAUDITORIYA (obunachilar tarkibi):")
            if a.shaharlar:
                qatorlar.append("- shaharlar: " + ", ".join(
                    f"{k} {v}" for k, v in list(a.shaharlar.items())[:6]))
            if a.yoshlar:
                qatorlar.append("- yosh: " + ", ".join(
                    f"{k} {v}" for k, v in a.yoshlar.items()))
            if a.jins:
                qatorlar.append("- jins: " + ", ".join(
                    f"{k} {v}" for k, v in a.jins.items()))

        sanoq = self._komment_sanogi(profil)
        if sanoq:
            qatorlar.append(
                "\nKOMMENTLARDA TAKRORLANGAN MAVZULAR (kod sanadi, taxmin emas):"
            )
            for mavzu, soni, misol in sanoq:
                qatorlar.append(f'- {mavzu}: {soni} marta — masalan: "{misol}"')
            qatorlar.append(
                "`komment_muammolari` da `necha_marta` ni AYNAN shu "
                "raqamlardan ol, o'zingdan sanama."
            )

        qatorlar.append(f"\n{VIDEO_IZOHI}")
        qatorlar.append("\nPOSTLAR (ko'rishlar bo'yicha kamayish tartibida):")

        tartib = sorted(
            profil.postlar, key=lambda p: (p.korishlar, p.layklar), reverse=True
        )
        for i, post in enumerate(tartib, 1):
            belgi = "REELS" if post.reelsmi else (post.mahsulot_turi or post.turi)
            olcham = f"{post.korishlar} ko'rish" if post.korishlar else "ko'rish yo'q"
            nisbat = ""
            if ortacha and post.korishlar:
                nisbat = f", medianadan {post.korishlar / ortacha:.1f}x"
            qatorlar.append(
                f"\n{i}. [{belgi}] {post.sana[:10]} — {olcham}{nisbat}, "
                f"{post.layklar} layk, {post.kommentlar_soni} komment"
            )
            if post.insightsmi:
                olchovlar = [
                    (post.qamrov, "qamrov"),
                    (post.saqlash, "saqlash"),
                    (post.ulashish, "ulashish"),
                    (post.profil_tashrifi, "profilga o'tish"),
                    (post.obuna_boldi, "obuna"),
                ]
                bor = [f"{nomi} {q}" for q, nomi in olchovlar if q >= 0]
                if bor:
                    qatorlar.append("   INSIGHTS: " + ", ".join(bor))
            if post.hook:
                qatorlar.append(f"   HOOK (sarlavha 1-qatori): {post.hook[:180]}")
            for komment in post.kommentlar[:MAKS_KOMMENT]:
                qatorlar.append(f"   komment: {komment.matn[:160]}")
        return "\n".join(qatorlar)

    @staticmethod
    def _komment_sanogi(profil: Profil) -> list[tuple[str, int, str]]:
        """Kommentlarni mavzu bo'yicha sanaydi: `(mavzu, soni, misol)`.

        Nega kodda: "narx 30 marta so'ralgan" — bu QAROR qabul qildiradigan
        raqam (bio'ga narx qo'yish kerakmi?). Model uni taxmin qilsa,
        raqam ishonchsiz bo'ladi.
        """
        topilgan: dict[str, list[str]] = {}
        for post in profil.postlar:
            for komment in post.kommentlar:
                matn = komment.matn
                for mavzu, andoza in KOMMENT_MAVZULARI:
                    if re.search(andoza, matn, re.IGNORECASE):
                        topilgan.setdefault(mavzu, []).append(matn)
        return [
            (mavzu, len(matnlar), matnlar[0][:90])
            for mavzu, matnlar in sorted(topilgan.items(), key=lambda x: -len(x[1]))
        ]

    async def _muqovalar(self, profil: Profil) -> tuple[list[tuple[str, bytes]], list[int]]:
        """Eng ko'p ko'rilgan videolarning muqovasini yuklaydi.

        Qaytadi: `(rasmlar, post_raqamlari)`. Raqamlar promptdagi ro'yxat
        tartibiga mos — model qaysi rasm qaysi postniki ekanini shundan
        biladi.

        Muqova yuklanmasa (Meta maydonni bermadi, havola eskirdi) — tahlil
        to'xtamaydi, shunchaki matnga tayanadi.
        """
        tartib = sorted(
            profil.postlar, key=lambda p: (p.korishlar, p.layklar), reverse=True
        )
        rasmlar: list[tuple[str, bytes]] = []
        raqamlar: list[int] = []
        for raqam, post in enumerate(tartib, 1):
            if len(rasmlar) >= MAKS_MUQOVA:
                break
            if not post.muqova:
                continue
            yuklangan = await self.instagram.muqova_yukla(post)
            if yuklangan is None:
                continue
            rasmlar.append(yuklangan)
            raqamlar.append(raqam)

        if not rasmlar and any(p.reelsmi for p in profil.postlar):
            self.ogohlantirish = (
                "video muqovalari olinmadi — tahlil faqat sarlavha matniga tayandi"
            )
        return rasmlar, raqamlar

    def _javob(self, profil: Profil, natija: NilufarNatija) -> Konvert:
        """Model xulosasini API raqamlari bilan birlashtiradi."""
        tartib = sorted(
            profil.postlar, key=lambda p: (p.korishlar, p.layklar), reverse=True
        )

        ishlagan: list[dict[str, Any]] = []
        for baho in natija.ishlagan_postlar:
            if not 1 <= baho.raqam <= len(tartib):
                continue  # noto'g'ri raqam — post o'ylab topilgan
            ishlagan.append(
                {**tartib[baho.raqam - 1].qisqa(), "nega_ishladi": baho.nega_ishladi}
            )

        reelslar = profil.reelslar
        korishlar = [p.korishlar for p in reelslar if p.korishlar > 0]
        cheklovlar = list(natija.cheklovlar)
        if len(profil.postlar) < YETARLI_POST:
            cheklovlar.append(
                f"Faqat {len(profil.postlar)} ta post ko'rildi — xulosa taxminiy."
            )
        cheklovlar.append(VIDEO_IZOHI)

        malumot = {
            "profil": profil.nomi,
            "havola": f"https://instagram.com/{profil.nomi}",
            "obunachilar": profil.obunachilar,
            "postlar_soni": profil.postlar_soni,
            "korilgan_postlar": len(profil.postlar),
            "video_soni": len(reelslar),
            "korishlar_medianasi": int(statistics.median(korishlar)) if korishlar else 0,
            "eng_kop_korilgan": tartib[0].qisqa() if tartib else {},
            "umumiy_baho": natija.umumiy_baho,
            "kontent_turlari": natija.kontent_turlari,
            "ishlagan_postlar": ishlagan,
            "hook_naqshlari": [h.model_dump() for h in natija.hook_naqshlari],
            "komment_muammolari": [k.model_dump() for k in natija.komment_muammolari],
            "tavsiyalar": natija.tavsiyalar,
            "cheklovlar": cheklovlar,
        }

        # Insights faqat o'z akkauntimizda bo'ladi — bo'lmasa maydonni
        # umuman qo'shmaymiz, nol bilan chalg'itmaymiz.
        if profil.ozimizniki:
            jami = lambda maydon: sum(  # noqa: E731
                max(getattr(p, maydon), 0) for p in profil.postlar
            )
            malumot["oz_akkaunt"] = True
            malumot["jami_qamrov"] = jami("qamrov")
            malumot["jami_saqlash"] = jami("saqlash")
            malumot["jami_ulashish"] = jami("ulashish")
            malumot["jami_obuna"] = jami("obuna_boldi")
            if profil.auditoriya.bormi:
                malumot["auditoriya"] = {
                    "shaharlar": profil.auditoriya.shaharlar,
                    "yoshlar": profil.auditoriya.yoshlar,
                    "jins": profil.auditoriya.jins,
                }
            if profil.insights_izohi:
                cheklovlar.append(f"Insights qisman: {profil.insights_izohi}")

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=malumot,
            manba=[
                self.kontrakt_manbasi(),
                Manba(
                    tur="veb",
                    nom=f"Instagram @{profil.nomi}",
                    havola=f"https://instagram.com/{profil.nomi}",
                ),
            ],
            ishonch=(
                Ishonch.YUQORI if len(profil.postlar) >= YETARLI_POST else Ishonch.ORTA
            ),
            tasdiq_kerak=False,
            izoh=(
                f"@{profil.nomi}: {len(profil.postlar)} ta post tahlil qilindi "
                f"({len(reelslar)} ta video)"
            ),
        )

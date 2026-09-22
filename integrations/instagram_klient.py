"""Instagram Graph API klienti — SMM tahlili uchun (FAQAT O'QISH).

Meta'ning rasmiy API'si. Sindirish, sahifa qirqish (scraping) yoki uchinchi
tomon xizmati YO'Q — Instagram shartlariga zid yo'lga kirilmaydi.

IKKI XIL KIRISH:
  1) O'Z akkauntimiz — to'liq Insights (qamrov, saqlashlar, profil tashrifi).
  2) BOSHQA profil (`business_discovery`) — ochiq maydonlar: sarlavha,
     ko'rishlar soni, layk, komment soni va kommentlar MATNI.

CHEKLOVLAR (foydalanuvchiga ochiq aytiladi):
  - tahlil qilinadigan profil Business yoki Creator bo'lishi SHART;
    oddiy shaxsiy akkaunt API orqali umuman ko'rinmaydi;
  - videoning O'ZI (birinchi kadr, ovoz) API'da yo'q — faqat sarlavha matni.
    Videoni yuklab olib tahlil qilish shartlarga zid, shuning uchun qilinmaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import sozlama

GRAPH_ASOS = "https://graph.facebook.com/v21.0"

# Boshqa profil uchun ochiq maydonlar (Meta hujjatida "Public" deb belgilangan).
OCHIQ_MEDIA = (
    "id,caption,media_type,media_product_type,permalink,timestamp,"
    "like_count,comments_count,view_count,media_url,thumbnail_url"
)

# Muqova rasmi uchun cheklovlar: modelga yuborishdan oldin hajmni cheklaymiz.
MUQOVA_MAKS_BAYT = 3 * 1024 * 1024
RASM_TURLARI = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# O'Z akkauntimiz uchun so'raladigan post metrikalari.
#
# DIQQAT: Meta metrika nomlarini versiyadan versiyaga o'zgartiradi va
# post turiga qarab ba'zilarini rad etadi (Reels da `impressions` yo'q,
# karuselda `shares` yo'q...). Shuning uchun ro'yxat "iltimos" tarzida
# yuboriladi: rad etilgani tashlab yuborilib, qaytadan so'raladi.
OZ_METRIKALAR = (
    "reach",              # nechta ODAM ko'rdi (ko'rishlar soni emas)
    "saved",              # saqlab qo'yganlar — eng kuchli signal
    "shares",             # ulashishlar
    "total_interactions",  # layk + komment + saqlash + ulashish
    "profile_visits",     # postdan profilga o'tganlar
    "follows",            # postdan keyin obuna bo'lganlar
    "views",              # ko'rishlar (yangi nom, eski `plays`/`impressions`)
)

# Metrika nomi -> bizdagi maydon
METRIKA_MAYDONI = {
    "reach": "qamrov",
    "saved": "saqlash",
    "shares": "ulashish",
    "total_interactions": "hamkorlik",
    "profile_visits": "profil_tashrifi",
    "follows": "obuna_boldi",
}


class InstagramXatosi(RuntimeError):
    """Profil olinmadi (token, ruxsat, profil turi yoki tarmoq)."""


def foydalanuvchi_nomi(havola_yoki_nom: str) -> str:
    """Havoladan yoki matndan Instagram username ajratadi.

    Foydalanuvchi havola tashlaydi, `@nom` yozadi yoki shunchaki nom yozadi —
    uchalasi ham ishlashi kerak.
    """
    matn = (havola_yoki_nom or "").strip()
    mos = re.search(r"instagram\.com/([A-Za-z0-9._]+)", matn)
    if mos:
        return mos.group(1).strip("/")
    return matn.lstrip("@").strip("/ ").split("?")[0].split("/")[0]


@dataclass
class Komment:
    matn: str
    layk: int = 0
    sana: str = ""


@dataclass
class Post:
    """Bitta post/reels."""

    id: str
    turi: str = ""              # IMAGE | VIDEO | CAROUSEL_ALBUM
    mahsulot_turi: str = ""     # REELS | FEED | AD | STORY
    sarlavha: str = ""
    havola: str = ""
    sana: str = ""
    korishlar: int = 0
    layklar: int = 0
    kommentlar_soni: int = 0
    kommentlar: list[Komment] = field(default_factory=list)
    # Video muqovasi (birinchi kadr). Meta bu maydonni har doim ham
    # bermaydi — bo'sh bo'lsa tahlil faqat matnga tayanadi.
    muqova: str = ""

    # --- faqat O'Z akkauntimiz uchun (Insights) --------------------------
    # Boshqa profilda bular HECH QACHON kelmaydi — Meta siyosati.
    # -1 = "so'ralmadi/kelmadi", 0 = "haqiqatan nol".
    qamrov: int = -1
    saqlash: int = -1
    ulashish: int = -1
    hamkorlik: int = -1
    profil_tashrifi: int = -1
    obuna_boldi: int = -1

    @property
    def insightsmi(self) -> bool:
        """Insights ma'lumoti bormi (o'z akkauntimiz)."""
        return self.qamrov >= 0 or self.saqlash >= 0

    @property
    def reelsmi(self) -> bool:
        return self.mahsulot_turi.upper() == "REELS" or self.turi.upper() == "VIDEO"

    @property
    def hook(self) -> str:
        """Sarlavhaning birinchi qatori — matnli hook."""
        for qator in (self.sarlavha or "").splitlines():
            if qator.strip():
                return qator.strip()
        return ""

    def qisqa(self) -> dict[str, Any]:
        natija = {
            "havola": self.havola,
            "turi": self.mahsulot_turi or self.turi,
            "sana": self.sana[:10],
            "korishlar": self.korishlar,
            "layklar": self.layklar,
            "kommentlar_soni": self.kommentlar_soni,
            "hook": self.hook[:160],
        }
        # Kelmagan metrikani 0 deb ko'rsatmaymiz — u yo'q, nol emas.
        for maydon in ("qamrov", "saqlash", "ulashish", "profil_tashrifi", "obuna_boldi"):
            qiymat = getattr(self, maydon)
            if qiymat >= 0:
                natija[maydon] = qiymat
        return natija


@dataclass
class Auditoriya:
    """Obunachilar tarkibi — faqat o'z akkauntimizda ko'rinadi."""

    shaharlar: dict[str, int] = field(default_factory=dict)
    yoshlar: dict[str, int] = field(default_factory=dict)
    jins: dict[str, int] = field(default_factory=dict)

    @property
    def bormi(self) -> bool:
        return bool(self.shaharlar or self.yoshlar or self.jins)


@dataclass
class Profil:
    nomi: str
    obunachilar: int = 0
    postlar_soni: int = 0
    postlar: list[Post] = field(default_factory=list)
    # `True` — bu bizning akkauntimiz, Insights ma'lumoti bor.
    ozimizniki: bool = False
    auditoriya: Auditoriya = field(default_factory=Auditoriya)
    # Insights so'ralgan, lekin kelmagan bo'lsa — sabab shu yerda.
    insights_izohi: str = ""

    @property
    def reelslar(self) -> list[Post]:
        return [p for p in self.postlar if p.reelsmi]


class InstagramKlient:
    """Instagram Graph API (faqat o'qish)."""

    def __init__(
        self,
        token: str | None = None,
        ig_user_id: str | None = None,
        mijoz: httpx.AsyncClient | None = None,
    ):
        s = sozlama()
        self.token = token if token is not None else s.instagram_token
        self.ig_user_id = (
            ig_user_id if ig_user_id is not None else s.instagram_user_id
        )
        self.kutish = s.instagram_kutish
        self._mijoz = mijoz
        self._oz_nomi: str | None = None

    def sozlanganmi(self) -> bool:
        return bool(self.token and self.ig_user_id)

    async def _sorov(self, yol: str, parametrlar: dict[str, Any]) -> dict[str, Any]:
        parametrlar = {**parametrlar, "access_token": self.token}
        manzil = f"{GRAPH_ASOS}/{yol.lstrip('/')}"
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.get(
                    manzil, params=parametrlar, timeout=self.kutish
                )
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.get(manzil, params=parametrlar)
        except httpx.HTTPError as xato:
            raise InstagramXatosi(f"Instagram API'ga ulanib bo'lmadi: {xato}") from xato

        try:
            malumot = javob.json()
        except ValueError as xato:
            raise InstagramXatosi(f"Instagram buzuq javob qaytardi: {xato}") from xato

        if "error" in malumot:
            xato_malumoti = malumot["error"]
            raise InstagramXatosi(
                f"Instagram rad etdi ({xato_malumoti.get('code')}): "
                f"{xato_malumoti.get('message', '')}"
            )
        if javob.status_code >= 400:
            raise InstagramXatosi(f"Instagram HTTP {javob.status_code}")
        return malumot

    async def oz_nomi(self) -> str:
        """Bizning akkauntimizning username'i (bir marta so'raladi)."""
        if self._oz_nomi is None:
            try:
                javob = await self._sorov(self.ig_user_id, {"fields": "username"})
                self._oz_nomi = str(javob.get("username") or "")
            except InstagramXatosi:
                self._oz_nomi = ""
        return self._oz_nomi

    async def tahlil(self, havola_yoki_nom: str, postlar: int = 25) -> Profil:
        """Profilni oladi — o'zimizniki bo'lsa Insights bilan.

        O'z akkauntimizda Meta ancha ko'p ma'lumot beradi: qamrov,
        saqlashlar, ulashishlar, profilga o'tish, obuna va auditoriya
        tarkibi. Boshqa profilda bular UMUMAN yo'q (Meta siyosati), faqat
        ochiq raqamlar qoladi.
        """
        nom = foydalanuvchi_nomi(havola_yoki_nom)
        if nom and nom.lower() == (await self.oz_nomi()).lower():
            return await self.oz_profil(postlar=postlar)
        return await self.profil(nom, postlar=postlar)

    async def oz_profil(self, postlar: int = 25) -> Profil:
        """O'z akkauntimiz — Insights bilan to'liq ko'rinish."""
        if not self.sozlanganmi():
            raise InstagramXatosi(
                "INSTAGRAM_TOKEN yoki INSTAGRAM_USER_ID sozlanmagan."
            )

        asos = await self._sorov(
            self.ig_user_id, {"fields": "username,followers_count,media_count"}
        )
        media = await self._sorov(
            f"{self.ig_user_id}/media",
            {
                "fields": f"{OCHIQ_MEDIA},comments.limit(15){{text,like_count,timestamp}}",
                "limit": int(postlar),
            },
        )

        profil = self._profil_yasa(
            str(asos.get("username") or ""),
            {
                "followers_count": asos.get("followers_count"),
                "media_count": asos.get("media_count"),
                "media": {"data": media.get("data") or []},
            },
        )
        profil.ozimizniki = True

        izohlar: list[str] = []
        for post in profil.postlar:
            xato = await self._post_insights(post)
            if xato and xato not in izohlar:
                izohlar.append(xato)
        profil.auditoriya = await self._auditoriya(izohlar)
        profil.insights_izohi = "; ".join(izohlar)
        return profil

    async def _post_insights(self, post: Post) -> str:
        """Bitta postning Insights ko'rsatkichlari.

        Meta post turiga qarab ba'zi metrikani rad etadi va xato matnida
        AYNAN qaysi biri ekanini yozadi. Shuni ushlab, o'sha metrikani
        tashlab, qaytadan so'raymiz — shunda qolganlari baribir keladi.
        """
        metrikalar = list(OZ_METRIKALAR)
        for _ in range(len(OZ_METRIKALAR)):
            if not metrikalar:
                return "post metrikalari qabul qilinmadi"
            try:
                javob = await self._sorov(
                    f"{post.id}/insights", {"metric": ",".join(metrikalar)}
                )
            except InstagramXatosi as xato:
                tashlandi = [m for m in metrikalar if m in str(xato)]
                if not tashlandi:
                    return f"Insights olinmadi: {str(xato)[:120]}"
                metrikalar = [m for m in metrikalar if m not in tashlandi]
                continue

            for element in javob.get("data") or []:
                nomi = str(element.get("name") or "")
                maydon = METRIKA_MAYDONI.get(nomi)
                qiymatlar = element.get("values") or []
                if not maydon or not qiymatlar:
                    continue
                setattr(post, maydon, int(qiymatlar[0].get("value") or 0))
            return ""
        return ""

    async def _auditoriya(self, izohlar: list[str]) -> Auditoriya:
        """Obunachilar tarkibi: shahar, yosh, jins."""
        auditoriya = Auditoriya()
        boliklar = {"city": "shaharlar", "age": "yoshlar", "gender": "jins"}
        for bolik, maydon in boliklar.items():
            try:
                javob = await self._sorov(
                    f"{self.ig_user_id}/insights",
                    {
                        "metric": "follower_demographics",
                        "period": "lifetime",
                        "metric_type": "total_value",
                        "breakdown": bolik,
                    },
                )
            except InstagramXatosi as xato:
                izoh = f"auditoriya ({bolik}) olinmadi"
                if izoh not in izohlar:
                    izohlar.append(izoh)
                _ = xato
                continue

            natija: dict[str, int] = {}
            for element in javob.get("data") or []:
                jami = element.get("total_value") or {}
                for qator in jami.get("breakdowns") or []:
                    for qiymat in qator.get("results") or []:
                        kalit = ", ".join(qiymat.get("dimension_values") or [])
                        if kalit:
                            natija[kalit] = int(qiymat.get("value") or 0)
            if natija:
                # Eng kattalari muhim — 10 tasi yetarli.
                setattr(auditoriya, maydon, dict(
                    sorted(natija.items(), key=lambda x: -x[1])[:10]
                ))
        return auditoriya

    async def profil(self, havola_yoki_nom: str, postlar: int = 25) -> Profil:
        """Boshqa (yoki o'z) biznes-profilini tahlil uchun oladi."""
        if not self.sozlanganmi():
            raise InstagramXatosi(
                "INSTAGRAM_TOKEN yoki INSTAGRAM_USER_ID sozlanmagan — "
                "profilni tahlil qilib bo'lmaydi."
            )

        nom = foydalanuvchi_nomi(havola_yoki_nom)
        if not nom:
            raise InstagramXatosi("Profil nomi aniqlanmadi.")

        # `business_discovery` — boshqa biznes-profilning ochiq ma'lumoti.
        soralgan = (
            f"business_discovery.username({nom})"
            f"{{followers_count,media_count,media.limit({int(postlar)})"
            f"{{{OCHIQ_MEDIA},comments.limit(15){{text,like_count,timestamp}}}}}}"
        )
        malumot = await self._sorov(self.ig_user_id, {"fields": soralgan})

        topilgan = malumot.get("business_discovery")
        if not topilgan:
            raise InstagramXatosi(
                f"@{nom} topilmadi. Sabab odatda: profil Business/Creator emas "
                "(oddiy shaxsiy akkaunt API orqali ko'rinmaydi) yoki nom noto'g'ri."
            )
        return self._profil_yasa(nom, topilgan)

    async def muqova_yukla(self, post: Post) -> tuple[str, bytes] | None:
        """Post muqovasini yuklab oladi: `(media_type, baytlar)`.

        Modelning o'zi birinchi kadrni KO'RADI — matndagi hook emas,
        ekrandagi yozuv, yuz, rang va kompozitsiya baholanadi.

        Rasm faqat tahlil vaqtida xotirada turadi, saqlanmaydi (Meta
        platforma shartlari media'ni uzoq saqlashni taqiqlaydi).
        """
        if not post.muqova:
            return None
        try:
            if self._mijoz is not None:
                javob = await self._mijoz.get(post.muqova, timeout=self.kutish)
            else:
                async with httpx.AsyncClient(timeout=self.kutish) as mijoz:
                    javob = await mijoz.get(post.muqova)
        except httpx.HTTPError:
            return None
        if javob.status_code >= 400:
            return None

        tur = (javob.headers.get("content-type") or "").split(";")[0].strip().lower()
        if tur not in RASM_TURLARI:
            return None
        baytlar = javob.content
        if not baytlar or len(baytlar) > MUQOVA_MAKS_BAYT:
            return None
        return tur, baytlar

    @staticmethod
    def _profil_yasa(nom: str, xom: dict[str, Any]) -> Profil:
        postlar: list[Post] = []
        for element in (xom.get("media") or {}).get("data") or []:
            kommentlar = [
                Komment(
                    matn=str(k.get("text") or "").strip(),
                    layk=int(k.get("like_count") or 0),
                    sana=str(k.get("timestamp") or ""),
                )
                for k in (element.get("comments") or {}).get("data") or []
                if str(k.get("text") or "").strip()
            ]
            postlar.append(
                Post(
                    id=str(element.get("id") or ""),
                    turi=str(element.get("media_type") or ""),
                    mahsulot_turi=str(element.get("media_product_type") or ""),
                    sarlavha=str(element.get("caption") or ""),
                    havola=str(element.get("permalink") or ""),
                    sana=str(element.get("timestamp") or ""),
                    korishlar=int(element.get("view_count") or 0),
                    layklar=int(element.get("like_count") or 0),
                    kommentlar_soni=int(element.get("comments_count") or 0),
                    kommentlar=kommentlar,
                    # Videoda `thumbnail_url` — muqova; rasmda `media_url`.
                    muqova=str(
                        element.get("thumbnail_url")
                        or (element.get("media_url") if
                            str(element.get("media_type") or "").upper() == "IMAGE" else "")
                        or ""
                    ),
                )
            )
        return Profil(
            nomi=nom,
            obunachilar=int(xom.get("followers_count") or 0),
            postlar_soni=int(xom.get("media_count") or 0),
            postlar=postlar,
        )

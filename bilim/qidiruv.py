"""Bilim bazasidan gibrid qidiruv.

Ikki qidiruv birlashtiriladi:
  - SEMANTIK (vektor) — boshqacha yozilgan savolni ham topadi;
  - KALIT SO'Z (BM25) — modda raqami, model kodi, aniq atama uchun.

Birlashtirish — Reciprocal Rank Fusion: har ro'yxatdagi o'rin bo'yicha ball.
Bu ikki xil o'lchov birligini normallashtirishdan ko'ra barqarorroq.

Har agent FAQAT o'z papkasidan va `umumiy` dan qidiradi — boshqa agentning
bilim bazasini ko'rmaydi.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.config import sozlama

from .indeks import Indeks, vektorla

log = logging.getLogger("bilim.qidiruv")

# Har agent qaysi papkalarni ko'radi.
AGENT_PAPKALARI = {
    "legal-review": ["legal", "umumiy"],
    "hr-assist": ["hr", "umumiy"],
    "marketing": ["marketing", "umumiy"],
    # Bekzod savdo yondashuvini tuzadi — unga mijoz portreti (`sales`),
    # bozor va raqobat (`market`), pozitsiyalash (`marketing`) — uchalasi
    # ham kerak. Vault aynan shu uchtasini beradi.
    "sales-strategy": ["sales", "market", "marketing", "umumiy"],
    # Faqat `sales`: KP mazmuni shablon, shart va narx hujjatlaridan olinadi.
    # `umumiy` qo'shilsa, KP manbalariga aloqasiz hujjatlar tushib qoladi.
    "proposal-builder": ["sales"],
    "product-spec": ["product", "umumiy"],
    # Montaj maslahatchisi: o'rnatish qoidalari + mahsulot tavsifi
    # (uskunaning o'lchami va og'irligi mahkamlashga ta'sir qiladi).
    #
    # `normativ` — SHNQ/QMQ matnlari: loyiha tarkibi, energiya
    # samaradorlik bo'limi, texnik tekshiruv talablari.
    "montaj-guide": ["montaj", "product", "normativ", "umumiy"],
    "competitor-watch": ["market", "umumiy"],
    "price-monitor": ["umumiy"],
    "data-query": ["umumiy"],
    # Nodira katalog bilan ishlaydi, hujjat bilan emas — RAG deyarli kerak emas.
    "catalog-admin": ["umumiy"],
    # Jasur e'lonlar bilan ishlaydi, hujjat bilan emas.
    "tender-watch": ["umumiy"],
    # Nilufar Instagram ma'lumoti bilan ishlaydi. Papka ochiq, lekin kod
    # so'ramaydi.
    #
    # TEKSHIRILDI (2026-09-08): ilgari "brend qoidalari kerak" deb
    # yozilgandi. Aslida uning prompti brendga MUVOFIQLIKNI emas,
    # faollik ko'rsatkichlarini (hook, ko'rish, saqlash) tahlil qiladi —
    # ya'ni brend hujjati javobga ta'sir qilmasdi. Nilufar kontent
    # QORALAMASINI ham yozadigan bo'lsa, o'shanda ulanadi.
    "smm-analyst": ["marketing", "umumiy"],
    # Aziza baza bilan ishlaydi. Papka biriktirilgan, LEKIN kod uni
    # so'ramaydi va bu ATAYLAB.
    #
    # TEKSHIRILDI (2026-09-08): bu yerda ilgari "savdo qoidalari (kutish
    # muddati, eslatma tartibi) `sales` da bo'ladi" deb yozilgandi — bu
    # NOTO'G'RI. `sales` papkasida bunday hujjat yo'q: CustDev tadqiqoti,
    # KP shabloni, mijoz portretlari, CJM va README. Eslatma muddati
    # kodda va sozlamada turadi.
    #
    # Ya'ni RAG ni bu yerga ulash foyda bermaydi. Kerak bo'lsa avval
    # HUJJAT yozilishi kerak, keyin ulanadi.
    "kp-tracker": ["sales", "umumiy"],
    # Rustam mahsulot va normativ hujjatlarga tayanadi. Hisob
    # chiqqach "qayerga qo'yamiz" savoli darhol keladi — shuning
    # uchun montaj bilimi ham ochiq.
    #
    # `normativ` — loyiha hujjati tarkibi va "Energiya samaradorlik"
    # bo'limi (SHNQ 1.03.03-23) hisob natijasini qayerda va qanday
    # ko'rsatish kerakligini belgilaydi.
    "hvac-calc": ["montaj", "product", "normativ", "umumiy"],
}

# RRF doimiysi. Standart 60 — bizning korpus kichik bo'lgani uchun
# pastroq qiymat yuqori o'rinlarni yaxshiroq ajratadi.
RRF_K = 20

# Bitta hujjatdan javobga tushadigan maksimal bo'lak soni.
#
# O'LCHANDI (2026-09-07): cheklovsiz holatda uchlikda o'rtacha 2.00 XIL
# hujjat chiqardi — ya'ni bitta hujjat ko'pincha ikki-uch o'rinni
# egallardi. «Шум от вентиляции» so'roviga «ВКПП» hujjatining uchala
# bo'lagi chiqib, shovqin bostirgich hujjati siqib chiqarilgandi.
#
# Agent uchun bitta hujjatning uch bo'lagi emas, uch xil hujjat
# foydaliroq: javob bir manbada bo'lmasa, ikkinchisida topiladi.
HUJJATDAN_MAKS = 2

# Bitta parchaning promptga tushadigan maksimal uzunligi (token tejash).
MAKS_PARCHA = 1400


@dataclass
class Topilma:
    """Bitta topilgan parcha."""

    matn: str
    hujjat: str
    sarlavha: str
    papka: str
    tur: str
    ball: float
    eskirgan: bool = False

    @property
    def manba_nomi(self) -> str:
        """Javobda ko'rsatiladigan manba: hujjat + bo'lim."""
        if self.sarlavha:
            return f"{self.hujjat}, {self.sarlavha}"
        return self.hujjat


# Qidiruvda ma'no bermaydigan so'zlar. Savol so'zlari ayniqsa muhim: ularsiz
# "qachon tashkil etilgan?" so'rovi savollar ro'yxati bo'lgan hujjatga
# yopishib qolmaydi.
TOXTATUVCHI = frozenset(
    """
    va yoki ham ammo lekin uchun bilan bo'yicha haqida qanday qancha qaysi
    qachon kim nima nima'ga nega qayer qayerda bu shu u ular biz siz men
    bor yoq bo'lsa bo'ladi bo'lgan bo'lishi kerak mumkin emas edi ekan
    hamda esa faqat yana eng juda barcha har ba'zi ushbu o'z ular'ning
    i v na s po dlya kak chto eto tot etot ili no dolzhen mozhet
    the and for with about how what when who which this that from are was
    """.split()
)


# Qonun matnlari kirillcha (lex.uz), foydalanuvchi lotincha yozadi.
# Ikkalasini bitta shaklga keltiramiz — aks holda BM25 hech narsa topmaydi.
KIRILL_LOTIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ў": "o", "ф": "f", "х": "x", "ҳ": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def transliteratsiya(matn: str) -> str:
    """Kirillcha matnni lotinchaga o'giradi (qidiruvda solishtirish uchun)."""
    return "".join(KIRILL_LOTIN.get(ch, ch) for ch in matn.lower())


def _tokenla(matn: str) -> list[str]:
    """BM25 uchun tokenizatsiya.

    Kirill/lotin farqi yo'qotiladi, to'xtatuvchi so'zlar va juda qisqa
    tokenlar tashlanadi, raqamlar (modda nomerlari) saqlanadi.
    """
    xom = re.findall(r"\w+", transliteratsiya(matn), flags=re.UNICODE)
    return [t for t in xom if len(t) > 2 and t not in TOXTATUVCHI]


class Qidiruv:
    """Papkalar bo'yicha gibrid qidiruv (bo'laklar xotirada keshlanadi)."""

    def __init__(self, indeks: Indeks | None = None):
        self.indeks = indeks or Indeks()
        self._kesh: dict[tuple[str, ...], tuple] = {}
        self._kesh_versiyasi: tuple | None = None

    def _eskirganmi(self) -> None:
        """Indeks o'zgargan bo'lsa keshni tashlaydi.

        JIM ESKIRISH EDI (2026-09-15): `keshni_tozala()` ni hech kim
        chaqirmasdi. Vaultga yangi normativ qo'shilib indeks yangilangach
        ham ishlab turgan bot ESKI bo'laklardan qidirardi — qayta ishga
        tushirilmaguncha yangi hujjat ko'rinmasdi.
        """
        try:
            versiya = self.indeks.versiya()
        except Exception:  # soxta yoki eski indeks — kesh avvalgidek ishlaydi
            return
        if versiya != self._kesh_versiyasi:
            self._kesh.clear()
            self._kesh_versiyasi = versiya

    def _yukla(self, papkalar: list[str]) -> tuple:
        """Papkalardagi bo'laklar, vektor matritsasi va BM25 indeksi."""
        self._eskirganmi()
        kalit = tuple(sorted(papkalar))
        if kalit in self._kesh:
            return self._kesh[kalit]

        bolaklar = self.indeks.bolaklar(list(kalit))
        if not bolaklar:
            natija = ([], None, None)
            self._kesh[kalit] = natija
            return natija

        # ARALASH O'LCHAM. Model almashtirilib indeks qayta qurilayotganda
        # bazada eski (384) va yangi (1024) vektorlar BIR VAQTDA turadi —
        # qayta qurish uch soat davom etadi. Turli uzunlikdagi massivlarni
        # `np.array` ga yig'ish xato beradi va butun qidiruv yiqilardi.
        #
        # Eng ko'p uchraydigan o'lcham olinadi, qolganlari VAQTINCHA
        # chetda qoladi. Qayta qurish tugagach hammasi bir xil bo'ladi.
        xom = [np.frombuffer(b["vektor"], dtype=np.float32) for b in bolaklar]
        uzunliklar = Counter(v.shape[0] for v in xom)
        asosiy = uzunliklar.most_common(1)[0][0]
        if len(uzunliklar) > 1:
            log.warning(
                "indeksda %d xil vektor o'lchami bor %s — %d o'lchamlisi "
                "olindi, qolgani qayta qurilishini kutmoqda",
                len(uzunliklar), dict(uzunliklar), asosiy,
            )
            juft = [(b, v) for b, v in zip(bolaklar, xom) if v.shape[0] == asosiy]
            bolaklar = [b for b, _ in juft]
            xom = [v for _, v in juft]

        vektorlar = np.array(xom)

        bm25 = None
        try:
            from rank_bm25 import BM25Okapi

            bm25 = BM25Okapi([_tokenla(b["matn"]) for b in bolaklar])
        except Exception:
            bm25 = None  # BM25 bo'lmasa faqat semantik qidiruv ishlaydi

        natija = (bolaklar, vektorlar, bm25)
        self._kesh[kalit] = natija
        return natija

    def keshni_tozala(self) -> None:
        self._kesh.clear()

    def qidir(self, sorov: str, papkalar: list[str], chek: int = 5) -> list[Topilma]:
        """Gibrid qidiruv: semantik + BM25, RRF bilan birlashtirilgan."""
        sorov = (sorov or "").strip()
        if not sorov:
            return []

        bolaklar, vektorlar, bm25 = self._yukla(papkalar)
        if not bolaklar:
            return []

        # Dastlab kengroq olamiz, keyin eng mosini tanlaymiz (reranking).
        keng = min(len(bolaklar), max(chek * 4, 20))

        ballar: dict[int, float] = {}

        # 1) Semantik
        sorov_vektori = vektorla([sorov], tur="query")[0]
        # O'LCHAM MOS KELMASA — semantik qidiruv O'TKAZIB YUBORILADI.
        #
        # Model almashtirilib, indeks qayta qurilmagan bo'lsa vektorlar
        # eski o'lchamda qoladi (384 va 1024 kabi). Ko'paytirish xato
        # beradi yoki — battari — mutlaqo ma'nosiz ball chiqaradi.
        # BM25 ishlayveradi, ya'ni qidiruv butunlay to'xtamaydi.
        if vektorlar.shape[1] != sorov_vektori.shape[0]:
            log.warning(
                "vektor o'lchami mos emas (indeks %d, model %d) — "
                "semantik qidiruv o'chirildi, indeksni qayta quring",
                vektorlar.shape[1], sorov_vektori.shape[0],
            )
        else:
            oxshashlik = vektorlar @ sorov_vektori
            semantik = np.argsort(-oxshashlik)[:keng]
            for orin, indeks in enumerate(semantik):
                ballar[int(indeks)] = ballar.get(int(indeks), 0.0) + 1.0 / (RRF_K + orin + 1)

        # 2) Kalit so'z
        if bm25 is not None:
            bm_ballar = bm25.get_scores(_tokenla(sorov))
            kalit = np.argsort(-bm_ballar)[:keng]
            for orin, indeks in enumerate(kalit):
                if bm_ballar[indeks] <= 0:
                    continue
                ballar[int(indeks)] = ballar.get(int(indeks), 0.0) + 1.0 / (RRF_K + orin + 1)

        tartib = sorted(ballar.items(), key=lambda x: -x[1])

        # Bitta hujjat butun javobni egallab olmasligi uchun cheklov.
        # Chetga surilganlar TASHLANMAYDI: joy qolsa, o'sha tartibda
        # qaytariladi. Shu sababli javob soni hech qachon kamaymaydi —
        # faqat tartibi xilma-xil bo'ladi.
        tanlangan: list[tuple[int, float]] = []
        chetda: list[tuple[int, float]] = []
        sanoq: Counter[str] = Counter()
        for indeks, ball in tartib:
            if len(tanlangan) >= chek:
                break
            bolak = bolaklar[indeks]
            # Hujjat kimligi — yo'li (ikki papkada bir xil nomli hujjat
            # bo'lishi mumkin). Yo'l bo'lmasa nomi bilan guruhlanadi.
            kalit = bolak.get("yol") or bolak["nomi"]
            if sanoq[kalit] >= HUJJATDAN_MAKS:
                chetda.append((indeks, ball))
                continue
            sanoq[kalit] += 1
            tanlangan.append((indeks, ball))

        if len(tanlangan) < chek:
            tanlangan.extend(chetda[: chek - len(tanlangan)])

        topilmalar: list[Topilma] = []
        for indeks, ball in tanlangan:
            bolak = bolaklar[indeks]
            topilmalar.append(
                Topilma(
                    matn=bolak["matn"],
                    hujjat=bolak["nomi"],
                    sarlavha=bolak["sarlavha"] or "",
                    papka=bolak["papka"],
                    tur=bolak["tur"] or "matn",
                    ball=float(ball),
                    eskirgan=bool(bolak["eskirgan"]),
                )
            )
        return topilmalar

    def agent_uchun(self, rol: str, sorov: str, chek: int | None = None) -> list[Topilma]:
        """Agent o'z papkalaridan qidiradi (boshqasiniki ko'rinmaydi)."""
        papkalar = AGENT_PAPKALARI.get(rol, ["umumiy"])
        return self.qidir(sorov, papkalar, chek or sozlama().bilim_chek)


@lru_cache
def qidiruv() -> Qidiruv:
    """Umumiy qidiruv nusxasi (kesh bo'linadi)."""
    return Qidiruv()


def kontekst_matni(topilmalar: list[Topilma]) -> str:
    """Topilmalarni agent promptiga qo'shiladigan matnga aylantiradi."""
    if not topilmalar:
        return ""

    bolaklar = [
        "BILIM BAZASIDAN TOPILDI (javobingni SHU matnga asosla va manbani ko'rsat):",
    ]
    for i, topilma in enumerate(topilmalar, 1):
        eskirgan = " [ESKIRGAN — ehtiyot bo'l]" if topilma.eskirgan else ""
        # Juda uzun parcha kontekstni to'ldirib yubormasin.
        matn = topilma.matn
        if len(matn) > MAKS_PARCHA:
            matn = matn[:MAKS_PARCHA].rsplit(" ", 1)[0] + " […]"
        bolaklar.append(
            f"\n--- [{i}] {topilma.manba_nomi}{eskirgan} ---\n{matn}"
        )
    bolaklar.append(
        "\n--- \nYuqoridagi parchalarda javob bo'lmasa, buni OCHIQ ayt — "
        "xotirangdan javob berma."
    )
    return "\n".join(bolaklar)

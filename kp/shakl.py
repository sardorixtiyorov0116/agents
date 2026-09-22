"""KP savol-javob shakli — savollar RO'YXATI va holat mantig'i.

NEGA ALOHIDA MODUL:

  1. Savollar — MA'LUMOT, kod emas. O'zgartirish uchun bot kodiga
     tegish shart emas.
  2. Telegramsiz test qilinadi. Butun mantiq shu yerda, `bot/asosiy.py`
     faqat xabar yuboradi va tugma chizadi.
  3. Erkin matnli yo'l (router -> agentlar) O'ZGARMAYDI. Bu unga
     QO'SHIMCHA yo'l: vazifa oldindan ma'lum bo'lgani uchun router ham,
     matndan raqam ajratish ham kerak emas.

IKKI YO'L:

  A) Menejer model nomini biladi  -> narx qidiriladi, hujjat yasaladi.
     LLM UMUMAN chaqirilmaydi (o'lchandi: ~0,2 s issiq keshda).
  B) Menejer obyektni tasvirlaydi -> havo sarfi KODDA hisoblanadi
     (o'lchandi: 2,8 ms), uskuna sarf va bosim bo'yicha filtrlanadi.

TO'XTASH QOIDASI: shakl javobni TAXMIN QILMAYDI. Yetishmagan narsa
so'raladi yoki ochiq "aniqlanmadi" deb qoladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from hisob import normalar
from hisob.bosim import TIPIK_TARMOQ

# Menejer shakldan chiqib ketishi uchun.
BEKOR = {"/bekor", "/cancel", "bekor", "otmena", "отмена"}


class ShaklXatosi(ValueError):
    """Javob tushunarsiz — savol kuchda qoladi."""


@dataclass(frozen=True)
class Tanlov:
    """Tugmadagi bitta variant."""

    qiymat: str
    yorliq: str
    izoh: str = ""


@dataclass(frozen=True)
class Savol:
    """Shakldagi bitta savol.

    `tekshir` javobni qabul qilinadigan qiymatga aylantiradi yoki
    `ShaklXatosi` ko'taradi. Xato bo'lsa savol QAYTA beriladi —
    noto'g'ri javob bilan davom etmaymiz.
    """

    kalit: str
    matn: str
    # Bosma oprosniy listdagi ASL nomi (ruscha).
    #
    # JONLI E'TIROZ (2026-08-28): atamalar o'zbekchaga tarjima
    # qilingandi va loyihachi ularni tanimay qoldi — u bosma list
    # bilan ishlaydi. Endi savol yonida asl nom turadi va ikkalasi
    # 1:1 solishtiriladi.
    asl: str = ""
    tanlovlar: tuple[Tanlov, ...] = ()
    tekshir: Callable[[str], Any] | None = None
    otkazsa_boladi: bool = False
    izoh: str = ""
    # Shu savol faqat shart bajarilganda beriladi (masalan B yo'lida).
    shart: Callable[[dict[str, Any]], bool] | None = None


# --- tekshiruvlar -------------------------------------------------------------

_OLCHAM = re.compile(r"([\d.,]+)\s*(?:kv|кв|m2|m²|м2|м²|kvadrat)?", re.I)
_BALANDLIK = re.compile(r"([\d.,]+)\s*(?:m|м|metr|метр)?", re.I)


def _son(matn: str) -> float:
    tozalangan = str(matn).replace(",", ".").strip()
    try:
        qiymat = float(tozalangan)
    except ValueError as xato:
        raise ShaklXatosi(f"Raqam kutilgan edi: {matn!r}") from xato
    if qiymat <= 0:
        raise ShaklXatosi("Raqam noldan katta bo'lishi kerak")
    return qiymat


def olcham_balandlik(matn: str) -> dict[str, float]:
    """«250 kv, 3 metr» yoki «250 3» -> maydon va balandlik.

    Ikki raqam bir qatorda beriladi — menejer uchun ikkita alohida
    savoldan qulayroq.
    """
    raqamlar = re.findall(r"[\d]+(?:[.,][\d]+)?", str(matn))
    if len(raqamlar) < 2:
        raise ShaklXatosi(
            "Ikkita raqam kerak: maydon va balandlik. Masalan: 250 kv, 3 metr"
        )
    maydon, balandlik = _son(raqamlar[0]), _son(raqamlar[1])
    if balandlik > 30:
        raise ShaklXatosi(
            f"Balandlik {balandlik:g} m — bu juda katta. Tartibi to'g'rimi? "
            "Avval maydon, keyin balandlik."
        )
    return {"maydon": maydon, "balandlik": balandlik}


def butun_son(matn: str) -> int:
    return int(_son(matn))


def bosh_bolmagan_matn(matn: str) -> str:
    tozalangan = " ".join(str(matn).split())
    if not tozalangan:
        raise ShaklXatosi("Bo'sh javob")
    return tozalangan


# Model nomida TIRE VA RAQAM bor: `ВК-250П`, `ВЦ 4-75-2,5-1-0,75/3000`.
# Shuning uchun ajratgich BO'SHLIQ bilan o'ralgan bo'lishi shart —
# aks holda `ВК-250П` da «250» miqdor deb o'qilardi va KP ga bitta
# o'rniga 250 dona tushardi (test bilan tutilgan xato).
_QATOR_AJRATGICH = re.compile(r"^(.+?)\s+[—–\-:]\s+([\d.,]+)\s*(\S+)?$")

# Ajratgichsiz shakl: «ВК-250П 5 dona». Miqdordan keyin BIRLIK turishi
# shart, aks holda model nomining oxiridagi raqam miqdor deb o'qilardi.
BIRLIKLAR = ("dona", "шт", "компл", "komplekt", "m", "м", "pm", "пм", "kg", "кг")
_QATOR_BIRLIK = re.compile(
    r"^(.+?)\s+([\d.,]+)\s*(" + "|".join(BIRLIKLAR) + r")\.?$", re.I
)


def sarlavhami(qator: str) -> bool:
    """Bu qator BO'LIM SARLAVHASImi, mahsulotmi?

    JONLI XATO (2026-08-28): loyiha spetsifikatsiyasi berilganda
    «Клп ДКС:» degan sarlavha KP ga MAHSULOT bo'lib tushdi — miqdori
    1, narxi bo'sh. Ro'yxatda 9 ta sarlavha bor edi va KP ning har
    biriga ortiqcha qator qo'shildi.

    Sarlavhaning belgisi: ikki nuqta bilan tugaydi va MIQDOR yo'q.
    «Клапан 500х300 — 21 dona» da ham raqam bor, lekin u ajratgichdan
    KEYIN — bunday qator sarlavha emas.
    """
    toza = qator.strip()
    if not toza.endswith(":"):
        return False
    return not (_QATOR_AJRATGICH.match(toza) or _QATOR_BIRLIK.match(toza))


def mahsulot_royxati(matn: str) -> list[dict[str, Any]]:
    """Har qatorga bitta mahsulot: «ВКП 40х20-4E20 — 4 dona».

    BO'LIM SARLAVHALARI mahsulot bo'lmaydi, lekin TASHLAB HAM
    yuborilmaydi: keyingi qatorlar qaysi bo'limga tegishli ekani
    ulardan bilinadi va loyiha qisqartmasi shu orqali katalog nomiga
    aylantiriladi (`kp/qisqartma.py`).

    Miqdor ko'rsatilmasa 1 deb olinadi — bu xavfsiz standart, chunki
    menejer miqdorni KP da ko'radi va tuzatishi mumkin.
    """
    from .qisqartma import qollash

    natija: list[dict[str, Any]] = []
    sarlavha = ""
    for qator in str(matn).splitlines():
        qator = qator.strip(" •-	")
        if not qator:
            continue
        if sarlavhami(qator):
            sarlavha = qator.rstrip(" :")
            continue

        mos = _QATOR_AJRATGICH.match(qator) or _QATOR_BIRLIK.match(qator)
        if mos:
            nomi = mos.group(1).strip().rstrip(" —–-:")
            miqdor = _son(mos.group(2))
            birlik = (mos.group(3) or "dona").strip()
        else:
            nomi, miqdor, birlik = qator, 1.0, "dona"

        yozuv: dict[str, Any] = {"nomi": nomi, "miqdor": miqdor, "birlik": birlik}
        if sarlavha:
            yozuv["bolim"] = sarlavha
            # Qisqartma tanilsa katalog nomiga aylantiriladi. Tanilmasa
            # asl matn QOLADI: taxminiy nom yasashdan ko'ra menejer
            # nimani tuzatish kerakligini ko'rgani yaxshi.
            tarjima = qollash(sarlavha, qator)
            if tarjima is not None:
                yozuv["asl_nomi"] = nomi
                yozuv["nomi"] = tarjima.nomi
                if tarjima.ogohlantirishlar:
                    yozuv["ogohlantirishlar"] = tarjima.ogohlantirishlar
        natija.append(yozuv)

    if not natija:
        raise ShaklXatosi("Kamida bitta mahsulot yozing")
    return natija


# --- savollar -----------------------------------------------------------------

YO_L_MODEL = "model"
YO_L_OBYEKT = "obyekt"

# Tizim yo'nalishi — nechta ventilyator va QAYSI panjara kerakligini
# belgilaydi. Ilgari so'ralmasdi va KP ga har doim BITTA ventilyator
# tushardi, panjara esa har doim РВН bo'lardi.
#
# РВИ FAQAT SO'RISH uchun: jalyuzisi havo oqimi bilan ochiladi va tizim
# to'xtaganda og'irlik kuchi bilan yopiladi (teskari klapan). Kirish
# tizimiga qo'yilsa ochilmaydi. Manba: bosma katalog 2021, 228-sahifa.
YONALISH_KIRISH = "kirish"
YONALISH_CHIQISH = "chiqish"
YONALISH_IKKALASI = "ikkalasi"

# Xona halqasi javoblari.
YANA_XONA_HA = "ha"
YANA_XONA_YOQ = "yoq"

# Bitta KP da shuncha xonadan ko'p bo'lsa, bu bitta tizim emas — bir
# necha alohida loyiha. Cheklov qo'yamiz, aks holda shakl cheksiz
# davom etishi mumkin.
MAKS_XONA = 15

# Xona halqasida qaytadan so'raladigan savollar.
XONA_KALITLARI = ("olcham", "xona_turi", "odamlar")

# Markaziy qurilma javoblari.
MARKAZIY_HA = "ha"
MARKAZIY_YOQ = "yoq"


def _taxminiy_sarf(javoblar: dict[str, Any]) -> float:
    """Kiritilgan xonalar bo'yicha TAXMINIY jami sarf.

    Shakl ichida ishlatiladi: qaysi savolni berish kerakligini
    hal qilish uchun. To'liq hisob `kp/shakldan.py` da.
    """
    from hisob import Xona, havo_sarfi

    jami = 0.0
    for xom in javoblar.get("xonalar") or []:
        if not isinstance(xom, dict):
            continue
        try:
            jami += havo_sarfi(Xona(
                turi=str(xom.get("turi") or "ofis"),
                maydon=float(xom.get("maydon") or 0),
                balandlik=float(xom.get("balandlik") or 3.0),
                odamlar=int(xom.get("odamlar") or 0),
            )).sarf
        except Exception:      # noqa: BLE001 — savol tanlashda yiqilmasin
            continue
    return jami


def _xona_turlari() -> tuple[Tanlov, ...]:
    """Tanlovlar normalar faylidan olinadi — ro'yxat ikki joyda turmasin."""
    return tuple(
        Tanlov(qiymat=tur, yorliq=tur.replace("_", " "), izoh=norma.get("izoh", ""))
        for tur, norma in normalar().items()
    )


# Tanlanadigan qismlar: (kalit, yorliq, `USKUNA` jadvalidagi nom).
# Bosim qiymati KODDA emas — `hisob/bosim.py::USKUNA` da turadi.
USKUNA_TANLOVI: tuple[tuple[str, str, str], ...] = (
    ("filtr", "Filtr", "filtr_g4"),
    ("isitgich", "Isitgich (suvli)", "isitgich_suvli"),
    ("sovutgich", "Sovutgich", "sovutgich"),
    ("rekuperator", "Rekuperator", "rekuperator"),
    ("shovqin", "Shovqin pasaytirgich", "shovqin_yutgich"),
    ("klapan", "Klapan", "klapan"),
)
USKUNA_TAYYOR = "__tayyor__"
# Qisqa kanal — uskunasiz, devordan devorga.
USKUNA_QISQA = "__qisqa__"


def _uskuna_tanlovlari() -> tuple[Tanlov, ...]:
    from hisob.bosim import USKUNA

    tanlovlar = [
        Tanlov(kalit, yorliq, f"+{USKUNA.get(nom, 0)} Pa")
        for kalit, yorliq, nom in USKUNA_TANLOVI
    ]
    # Belgi ATAYLAB ✅ EMAS: tanlangan qismlar ✅ bilan belgilanadi va
    # ikkalasi bir xil bo'lsa menejer «Tayyor» ni ham tanlangan deb
    # o'ylardi.
    tanlovlar.append(Tanlov(
        USKUNA_TAYYOR, "▶️ Tayyor", "tanlanganlari bilan davom etamiz"))
    tanlovlar.append(Tanlov(
        USKUNA_QISQA, "Qisqa kanal, uskunasiz", "devordan devorga"))
    return tuple(tanlovlar)


def _tarmoq_turlari() -> tuple[Tanlov, ...]:
    return tuple(
        Tanlov(qiymat=tur,
               yorliq=yozuv["izoh"],
               izoh=f"{yozuv['oraliq'][0]}–{yozuv['oraliq'][1]} Pa")
        for tur, yozuv in TIPIK_TARMOQ.items()
    )


def savollar() -> tuple[Savol, ...]:
    """Shaklning to'liq ro'yxati, tartib bilan."""
    obyekt = lambda j: j.get("yol") == YO_L_OBYEKT      # noqa: E731
    model = lambda j: j.get("yol") == YO_L_MODEL        # noqa: E731

    def katta_obyekt(j: dict[str, Any]) -> bool:
        from hisob.markaziy import ENG_KAM_SARF

        return obyekt(j) and _taxminiy_sarf(j) >= ENG_KAM_SARF
    return (
        Savol(
            kalit="mijoz",
            matn="Mijoz kim? (tashkilot nomi)",
            tekshir=bosh_bolmagan_matn,
            otkazsa_boladi=True,
            izoh="KP tepasida shu nom chiqadi",
        ),
        Savol(
            kalit="yol",
            matn="Nima kerak?",
            tanlovlar=(
                Tanlov(YO_L_MODEL, "Model nomini bilaman",
                       "narx darrov qidiriladi"),
                Tanlov(YO_L_OBYEKT, "Obyektni tasvirlayman",
                       "havo sarfi hisoblanadi"),
            ),
        ),
        # --- A yo'l ---
        Savol(
            kalit="mahsulotlar",
            matn=("Model va miqdorni yozing, har qatorga bittadan:\n"
                  "ВКП 40х20-4E20 — 4 dona\n"
                  "РВН 300х300 — 12 dona"),
            tekshir=mahsulot_royxati,
            shart=model,
        ),
        # --- B yo'l ---
        Savol(
            kalit="olcham",
            matn="Maydon va balandlik? Masalan: 250 kv, 3 metr",
            tekshir=olcham_balandlik,
            shart=obyekt,
        ),
        Savol(
            kalit="xona_turi",
            matn="Xona turi?",
            tanlovlar=_xona_turlari(),
            shart=obyekt,
        ),
        Savol(
            kalit="odamlar",
            matn="Necha kishi bo'ladi?",
            tekshir=butun_son,
            otkazsa_boladi=True,
            izoh="bo'sh qoldirsangiz faqat karralik bo'yicha hisoblanadi",
            shart=obyekt,
        ),
        # XONA HALQASI. "Ha" javobi `olcham`/`xona_turi`/`odamlar` ni
        # TOZALAYDI va uchala savol yangi xona uchun qaytadan beriladi
        # (`Shakl.javob_ber` ga qara). Shu tariqa bitta shaklda
        # istagancha xona kiritiladi.
        #
        # Ilgari faqat BITTA xona kiritish mumkin edi: hisob qismi ko'p
        # xonani ko'targani bilan menejerda unga yo'l yo'q edi —
        # ko'p xonali obyekt faqat TZ fayli orqali kelardi.
        Savol(
            kalit="yana_xona",
            matn="Yana xona bormi?",
            tanlovlar=(
                Tanlov(YANA_XONA_HA, "➕ Ha, yana xona",
                       "o'lcham va tur qaytadan so'raladi"),
                Tanlov(YANA_XONA_YOQ, "Yo'q, davom etamiz"),
            ),
            shart=obyekt,
        ),
        Savol(
            kalit="yonalish",
            matn="Tizim qaysi yo'nalishda?",
            tanlovlar=(
                Tanlov(YONALISH_KIRISH, "Kirish (приточная)",
                       "toza havo beriladi"),
                Tanlov(YONALISH_CHIQISH, "Chiqish (вытяжная)",
                       "havo so'rib chiqariladi"),
                Tanlov(YONALISH_IKKALASI, "Kirish + chiqish",
                       "ikkita ventilyator kerak"),
            ),
            shart=obyekt,
            izoh="nechta ventilyator va qaysi panjara kerakligini belgilaydi",
        ),
        # MARKAZIY QURILMA — faqat KATTA obyektda so'raladi.
        #
        # 18 000 m³/soat lik binoga tizim 15 ta kanal isitgichi taklif
        # qilardi. Arifmetik to'g'ri, amaliy jihatdan noto'g'ri: bunday
        # masshtabda muhandis BITTA markaziy qurilma qo'yadi.
        #
        # Kichik obyektda bu savol BERILMAYDI — u yerda markaziy
        # qurilma ortiqcha qimmat va ortiqcha joy egallaydi.
        Savol(
            kalit="markaziy",
            matn="Markaziy qurilma (КЦКП) qo'yamizmi?",
            tanlovlar=(
                Tanlov(MARKAZIY_HA, "Ha, markaziy qurilma",
                       "ventilyator, isitgich, sovutgich, filtr — bitta korpusda"),
                Tanlov(MARKAZIY_YOQ, "Yo'q, tarqoq tizim",
                       "har qism alohida, kanalga o'rnatiladi"),
            ),
            shart=katta_obyekt,
            izoh="markaziy qurilmaga alohida ventkamera kerak",
        ),
        # KANAL UZUNLIGI — taxminni HAQIQIY hisobga aylantiradi.
        #
        # Bu javob bo'lmasa bosim tayyor oraliqdan olinadi (250-450 Pa)
        # va u har doim YUQORI chegara bo'yicha talab qilinadi. Jonli
        # holat: sanuzelning qisqa so'rish kanaliga ham 450 Pa talab
        # qilindi, holbuki haqiqiy hisob 104 Pa berardi — natijada
        # mos ventilyator umuman topilmadi.
        #
        # Uzunlik aytilsa `hisob/bosim.py::bosim_yoqotishi` ishlaydi:
        # uzunlik x ishqalanish + burilishlar + uskunalar + zaxira.
        Savol(
            kalit="kanal_uzunligi",
            matn="Kanal tarmog'i taxminan necha metr?",
            tekshir=butun_son,
            otkazsa_boladi=True,
            shart=obyekt,
            izoh="bilmasangiz o'tkazing — taxminiy oraliq ishlatiladi",
        ),
        # USKUNA HALQASI. Har bosishda bitta qism qo'shiladi va savol
        # QAYTA beriladi — shu tariqa ISTALGAN birikma yig'iladi.
        #
        # Ilgari bu yerda to'rtta TAYYOR to'plam bor edi va ular
        # bir-birini istisno qilardi. Menejer "filtr + sovutgich, lekin
        # rekuperatorsiz" desa — mos variant yo'q edi.
        Savol(
            kalit="uskuna",
            matn="Tizimga nima qo'shamiz?",
            tanlovlar=_uskuna_tanlovlari(),
            shart=obyekt,
            izoh="bittalab qo'shing; tugagach «Tayyor» bosing",
        ),
        # --- ikkalasida ham ---
        # STIR VA OBYEKT SO'RALMAYDI.
        #
        # Ular KP blankasida chiqmaydi (murojaat blokida joy yo'q), va
        # faqat saqlash uchun savol berish menejer vaqtini oladi.
        # TZ faylida uchrasa — bepul olinadi va `Mijoz` modelida
        # saqlanadi (`kp/tz.py`), lekin buning uchun savol kerak emas.
        Savol(
            kalit="yetkazish",
            matn="Yetkazish muddati?",
            tekshir=bosh_bolmagan_matn,
            otkazsa_boladi=True,
            izoh="bo'sh qoldirsangiz shablondagi standart qo'yiladi",
        ),
        Savol(
            kalit="shartlar",
            matn="Maxsus shartlar? (o'rnatish, kafolat va h.k.)",
            tekshir=bosh_bolmagan_matn,
            otkazsa_boladi=True,
        ),
    )


# --- holat --------------------------------------------------------------------


@dataclass
class Shakl:
    """To'ldirilayotgan shakl holati."""

    javoblar: dict[str, Any] = field(default_factory=dict)

    def _kerakli(self) -> list[Savol]:
        return [s for s in savollar() if s.shart is None or s.shart(self.javoblar)]

    def joriy(self) -> Savol | None:
        """Hozirgi savol. Hammasi to'lgan bo'lsa — None."""
        for savol in self._kerakli():
            if savol.kalit not in self.javoblar:
                return savol
        return None

    def tugadimi(self) -> bool:
        return self.joriy() is None

    def qadam(self) -> tuple[int, int]:
        """(nechanchi, jami) — «3/8» ko'rinishi uchun.

        Yo'l tanlanmaguncha UZUNROQ tarmoqning uzunligi ko'rsatiladi.
        Aks holda hisob «1/4» dan «3/8» ga sakrab, menejerga savollar
        ko'payib ketgandek tuyulardi. Bu yo'nalishda xato qilamiz:
        kutilgandan kam savol — yoqimli, ko'p savol — yoqimsiz.
        """
        kerakli = self._kerakli()
        berilgan = sum(1 for s in kerakli if s.kalit in self.javoblar)
        jami = len(kerakli)
        if "yol" not in self.javoblar:
            for tarmoq in (YO_L_OBYEKT, YO_L_MODEL):
                sinov = {**self.javoblar, "yol": tarmoq}
                uzunlik = sum(1 for s in savollar()
                              if s.shart is None or s.shart(sinov))
                jami = max(jami, uzunlik)
        return min(berilgan + 1, jami), jami

    def belgi(self) -> str:
        """Savol tepasidagi holat yozuvi: «3/12» yoki «2-xona · 3/12».

        NEGA ALOHIDA: xona halqasida `qadam()` ORQAGA sakraydi (6/12 dan
        3/12 ga), chunki xona savollari tozalanib qaytadan beriladi.
        Menejerga bu "ish orqaga ketdi" bo'lib ko'rinardi. Xona raqami
        qo'shilsa, sakrash TUSHUNARLI bo'ladi: yangi xona boshlandi.
        """
        nechanchi, jami = self.qadam()
        asos = f"{nechanchi}/{jami}"
        savol = self.joriy()
        if savol is None or savol.kalit not in (*XONA_KALITLARI, "yana_xona"):
            return asos
        raqam = len(self.javoblar.get("xonalar") or []) + 1
        if raqam == 1 and savol.kalit != "yana_xona":
            return asos
        return f"{raqam}-xona · {asos}"

    def javob_ber(self, matn: str) -> None:
        """Joriy savolga javob yozadi. Tushunarsiz bo'lsa `ShaklXatosi`."""
        savol = self.joriy()
        if savol is None:
            raise ShaklXatosi("Shakl allaqachon to'ldirilgan")

        if savol.tanlovlar:
            tanlangan = _tanlovni_top(savol, matn)
            if tanlangan is None:
                yorliqlar = ", ".join(t.yorliq for t in savol.tanlovlar)
                raise ShaklXatosi(f"Variantlardan birini tanlang: {yorliqlar}")
            self.javoblar[savol.kalit] = tanlangan.qiymat
            if savol.kalit == "yana_xona":
                self._xonani_yakunla(tanlangan.qiymat == YANA_XONA_HA)
            elif savol.kalit == "uskuna":
                self._uskunani_qoshi(tanlangan.qiymat)
            else:
                self._bir_nafasda(_tanlovsiz(tanlangan, matn))
            return

        if savol.tekshir is None:
            self.javoblar[savol.kalit] = matn
            return
        self.javoblar[savol.kalit] = savol.tekshir(matn)

    def _bir_nafasda(self, matn: str) -> None:
        """Xuddi shu xabarda aytilgan KEYINGI javobni ham oladi.

        Odam ovozli xabarda hammasini bir nafasda aytadi:
        «Obyekt tasvirlayman, 250 metr kvadrat, balandligi 3 metr».
        Yo'l tanlangach maydonni QAYTA so'rash ortiqcha — u aytilgan.

        FAQAT BITTA QADAM oldinga. Ikkinchisiga o'tilsa, o'sha raqamlar
        boshqa savolga ham tushib ketardi: «250 kv, 3 metr» dagi 250 ni
        «necha kishi?» savoliga 250 kishi deb yozib qo'yardi.

        FAQAT TEKSHIRUVCHISI BORIGA. Tekshiruvchi qat'iy: matn mos
        kelmasa xato beradi va savol oddiy tartibda so'raladi. Tanlovli
        savolga esa tegilmaydi — u kalit so'z bo'yicha topiladi va
        qoldiq matndan tasodifan mos kelib qolishi mumkin edi.
        """
        keyingi = self.joriy()
        if keyingi is None or keyingi.tanlovlar or keyingi.tekshir is None:
            return
        try:
            self.javoblar[keyingi.kalit] = keyingi.tekshir(matn)
        except ShaklXatosi:
            pass   # aytilmagan — savol o'z navbatida beriladi

    def _xonani_yakunla(self, yana: bool) -> None:
        """Joriy xonani `xonalar` ro'yxatiga ko'chiradi.

        `yana=True` bo'lsa xona savollari TOZALANADI va ular keyingi
        xona uchun qaytadan beriladi — `joriy()` javob berilmagan
        birinchi savolni qidirgani uchun bu o'z-o'zidan ishlaydi.
        """
        olcham = self.javoblar.get("olcham") or {}
        maydon = float(olcham.get("maydon") or 0)
        if maydon > 0:
            turi = str(self.javoblar.get("xona_turi") or "ofis")
            xonalar = list(self.javoblar.get("xonalar") or [])
            xonalar.append({
                "nomi": f"{turi} {len(xonalar) + 1}" if xonalar else turi,
                "turi": turi,
                "maydon": maydon,
                "balandlik": float(olcham.get("balandlik") or 3.0),
                "odamlar": int(self.javoblar.get("odamlar") or 0),
            })
            self.javoblar["xonalar"] = xonalar

        if not yana:
            return
        if len(self.javoblar.get("xonalar") or []) >= MAKS_XONA:
            # Cheklovga yetildi — halqa to'xtaydi. Bu holat menejerga
            # `bot/kp_oqim.py` da aytiladi.
            self.javoblar["yana_xona"] = YANA_XONA_YOQ
            return
        for kalit in (*XONA_KALITLARI, "yana_xona"):
            self.javoblar.pop(kalit, None)

    def _uskunani_qoshi(self, qiymat: str) -> None:
        """Tanlangan qismni ro'yxatga qo'shadi va savolni QAYTARADI.

        «Tayyor» yoki «qisqa kanal» bosilsa halqa tugaydi.
        """
        if qiymat == USKUNA_QISQA:
            self.javoblar["uskunalar"] = []
            self.javoblar["qisqa_kanal"] = True
            return
        if qiymat == USKUNA_TAYYOR:
            self.javoblar.setdefault("uskunalar", [])
            return

        tanlangan = list(self.javoblar.get("uskunalar") or [])
        if qiymat not in tanlangan:
            tanlangan.append(qiymat)
        self.javoblar["uskunalar"] = tanlangan
        # Savolni qaytarish: keyingi qismni ham qo'shsa bo'ladi.
        self.javoblar.pop("uskuna", None)

    def orqaga(self) -> bool:
        """Oxirgi javobni bekor qiladi. `False` — qaytadigan joy yo'q.

        NEGA KERAK: shakl 12 qadamdan iborat va menejer o'rtada xato
        tugma bosib qo'ysa, ilgari butun KP ni `/bekor` qilib boshidan
        boshlashi kerak edi.

        UCH HOLAT alohida ishlanadi, chunki ularda javob oddiy kalitda
        emas — RO'YXATDA turadi:

          1. Uskuna halqasi  -> oxirgi TANLOV olib tashlanadi;
          2. Xona halqasi    -> oxirgi XONA shakl maydonlariga qaytadi;
          3. Oddiy savol     -> javob o'chiriladi.
        """
        joriy = self.joriy()

        # 1) Uskuna halqasi — oxirgi qo'shilgan qismni olib tashlaymiz.
        if joriy is not None and joriy.kalit == "uskuna":
            tanlangan = list(self.javoblar.get("uskunalar") or [])
            if tanlangan:
                tanlangan.pop()
                self.javoblar["uskunalar"] = tanlangan
                return True
            # Hech narsa tanlanmagan — halqadan OLDINGI savolga chiqamiz.
            self.javoblar.pop("uskunalar", None)
            self.javoblar.pop("qisqa_kanal", None)

        # 2) Xona halqasi — yangi xona boshlangan, oldingisini qaytaramiz.
        xonalar = list(self.javoblar.get("xonalar") or [])
        if xonalar and "olcham" not in self.javoblar:
            oxirgi = xonalar.pop()
            self.javoblar["xonalar"] = xonalar
            self.javoblar["olcham"] = {
                "maydon": oxirgi.get("maydon", 0),
                "balandlik": oxirgi.get("balandlik", 3.0),
            }
            self.javoblar["xona_turi"] = oxirgi.get("turi", "ofis")
            self.javoblar["odamlar"] = oxirgi.get("odamlar", 0)
            self.javoblar.pop("yana_xona", None)
            if not xonalar:
                self.javoblar.pop("xonalar", None)
            return True

        # 3) Oddiy savol — oxirgi javob berilganini o'chiramiz.
        for savol in reversed(self._kerakli()):
            if savol.kalit not in self.javoblar:
                continue
            self.javoblar.pop(savol.kalit, None)
            # «Yo'l» o'zgarsa keyingi savollar boshqacha bo'ladi —
            # o'sha tarmoqning javoblari qolib ketmasin.
            if savol.kalit == "yol":
                for kalit in (*XONA_KALITLARI, "xonalar", "yana_xona",
                              "mahsulotlar", "yonalish", "uskunalar",
                              "qisqa_kanal", "tarmoq"):
                    self.javoblar.pop(kalit, None)
            # Xona yakunlangan bo'lsa, u ro'yxatga ham tushgan.
            elif savol.kalit == "yana_xona" and xonalar:
                oxirgi = xonalar.pop()
                self.javoblar["xonalar"] = xonalar
                if not xonalar:
                    self.javoblar.pop("xonalar", None)
                self.javoblar["olcham"] = {
                    "maydon": oxirgi.get("maydon", 0),
                    "balandlik": oxirgi.get("balandlik", 3.0),
                }
                self.javoblar["xona_turi"] = oxirgi.get("turi", "ofis")
                self.javoblar["odamlar"] = oxirgi.get("odamlar", 0)
            return True
        return False

    def otkaz(self) -> None:
        """Savolni o'tkazib yuboradi (faqat ruxsat etilganini)."""
        savol = self.joriy()
        if savol is None:
            raise ShaklXatosi("Shakl allaqachon to'ldirilgan")
        if not savol.otkazsa_boladi:
            raise ShaklXatosi("Bu savolni o'tkazib bo'lmaydi")
        self.javoblar[savol.kalit] = None


# Yorliqdagi eng uzun so'z shu uzunlikdan qisqa bo'lsa, gap ichidan
# qidirilmaydi — qisqa so'z tasodifan uchrab, noto'g'ri tanlov qilinardi.
ENG_QISQA_KALIT = 5

_SOZLAR = re.compile(r"[^\W\d_]+", re.UNICODE)


def _kalit_soz(yorliq: str) -> str:
    """Yorliqning eng uzun so'zi — uning eng ajralib turadigan qismi.

    «Obyektni tasvirlayman» -> «tasvirlayman»
    «Model nomini bilaman»  -> «bilaman»

    NEGA ENG UZUNI: u odatda fe'l bo'ladi va inkorda SHAKLI O'ZGARADI
    («bilaman» -> «bilmayman»). Shuning uchun «model nomini bilmayman»
    degan javob «Model nomini bilaman» ga MOS KELMAYDI — bu to'g'ri,
    chunki odam aynan teskarisini aytyapti.
    """
    sozlar = _SOZLAR.findall(yorliq.lower())
    return max(sozlar, key=len) if sozlar else ""


def _tanlovsiz(tanlov: Tanlov, matn: str) -> str:
    """Xabardan TANLOV so'zlarini olib tashlaydi, qolganini qaytaradi.

    «Model nomini bilaman, ВКП 40х20-4E20 — 4 dona»
        -> «ВКП 40х20-4E20 — 4 dona»

    NEGA KERAK: qoldiq keyingi savolga uzatiladi. Tozalanmasa,
    mahsulot nomi «Model nomini bilaman, ВКП 40х20-4E20» bo'lib
    qolardi va shu holda KP ga tushardi.
    """
    olib = {tanlov.qiymat.lower(), *_SOZLAR.findall(tanlov.yorliq.lower())}
    qolgan = _SOZLAR.sub(
        lambda m: "" if m.group().lower() in olib else m.group(), matn)
    # Olib tashlangan so'z o'rnida osilib qolgan tinish belgilari.
    return re.sub(r"\s{2,}", " ", qolgan).strip(" ,.;:—-\n\t")


def _tanlovni_top(savol: Savol, matn: str) -> Tanlov | None:
    """Tugma qiymati, yorlig'i, tartib raqami yoki GAP ICHIDAN topadi."""
    toza = str(matn).strip().lower()
    for tanlov in savol.tanlovlar:
        if toza in (tanlov.qiymat.lower(), tanlov.yorliq.lower()):
            return tanlov
    if toza.isdigit():
        raqam = int(toza)
        if 1 <= raqam <= len(savol.tanlovlar):
            return savol.tanlovlar[raqam - 1]

    # Odam tugma bosish o'rniga gapirib yuboradi — ayniqsa OVOZLI
    # xabarda: «Obyekt tasvirlayman, 250 metr kvadrat, balandligi 3 metr».
    # Bunda yorliqning kalit so'zi gap ichida turadi.
    #
    # JONLI XATO (2026-09-05): shunday ovozli xabar «Variantlardan
    # birini tanlang» degan javob oldi — javob AYTILGAN bo'lsa ham.
    sozlar = set(_SOZLAR.findall(toza))
    nomzodlar = [
        tanlov for tanlov in savol.tanlovlar
        if (kalit := _kalit_soz(tanlov.yorliq))
        and len(kalit) >= ENG_QISQA_KALIT and kalit in sozlar
    ]
    # BITTA nomzod bo'lsagina tanlanadi. Ikkitasi ham uchrasa — bu
    # noaniqlik, taxmin qilmaymiz va savol qayta beriladi.
    return nomzodlar[0] if len(nomzodlar) == 1 else None

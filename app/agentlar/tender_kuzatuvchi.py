"""Tender kuzatuvchisi Jasur — `tender-watch`.

Maqsad: xarid e'lonlarini kuzatib, kompaniya katalogiga mos keladiganlarini
ajratib beradi.

O'ZGARMAS QOIDALAR (kodda, promptda emas):
  - e'lonlar MANBADAN olinadi; model o'zidan e'lon qo'sha olmaydi — sxemada
    faqat `raqam` (manbadagi tartib raqami) bor, havola kodda qo'yiladi;
  - bir marta ko'rsatilgan e'lon qayta chiqmaydi (baza);
  - agent hech qanday tenderga ARIZA TOPSHIRMAYDI — faqat xabar beradi.

QAMROV: standart holatda FAQAT `etender.uzex.uz` — kompaniya ERI kaliti
bilan ro'yxatdan o'tgan va lot sahifasida "o'z taklifingizni bering" bor,
ya'ni ISHTIROK ETILADI. DXMAP (`xarid.icppa.uz`) o'chirilgan: u axborot
portali, havolasi taklif berish sahifasiga olib bormaydi va lotlarining
84% ida shartnoma allaqachon tuzilgan (2026-09-09 da o'lchandi).
Boshqa maydonchada ro'yxatdan o'tilsa `TENDER_MANBALARI` ga qo'shiladi.

Cheklov kalit so'zlarda: baza 5 mln lotdan iborat, shuning uchun so'rov
kalit so'z bo'yicha ketadi. Ishlatilgan so'zlar javobda ochiq ko'rsatiladi.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import anthropic
from pydantic import BaseModel, Field, ValidationError

from integrations import ApiXatosi, mahsulot_qisqa
from integrations.tender_manba import (
    Elon,
    LotHujjati,
    Manba,
    elonlarni_yig,
    standart_manbalar,
)
# Modul ORQALI chaqiriladi (nom import qilinmaydi): testlar TZ yuklash va
# kursni `monkeypatch` bilan almashtira olsin, tarmoqqa chiqilmasin.
import integrations.tender_manba as tender_moduli
import integrations.valyuta as valyuta_moduli
from integrations.brend import begona_brendlar
from integrations.maxfiy import yashir

from ..config import sozlama
from ..konvert import Holat, Ishonch, Konvert, xato_konvert
from ..konvert import Manba as KonvertManba
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Bir chaqiruvda ko'riladigan e'lon soni.
#
# 40 ta edi — manba 329 ta ochiq lot bergani uchun ularning ko'pi
# promptga umuman yetib bormasdi. Har lot promptda ~2 qator egallaydi,
# 150 tasi ham model uchun og'ir emas.
MAKS_ELON = 150

# Tartib: `etender.uzex.uz` BIRINCHI, keyin summa bo'yicha kattadan
# kichikka.
#
# NEGA SHUNDAY — O'LCHANDI (2026-09-09). Ikki manba butunlay boshqa
# ishni beradi (lot raqami, STIR va sarlavha bo'yicha kesishmasi NOL):
#
#   DXMAP    134 toza lot, mediana  11 mln, jami  4,31 mlrd, muddat 0/156
#   etender    8 toza lot, mediana 130 mln, jami 16,84 mlrd, muddat 9/9
#
# Ya'ni sakkizta etender loti 134 tadan TO'RT BAROBAR ko'p pul olib
# keladi va faqat ular muddat beradi. Zavod uchun mazmunli shartnoma
# o'sha yerda — shuning uchun ro'yxat boshida turadi.
#
# Tartib PROMPTGA ham ta'sir qiladi: `MAKS_ELON` ga urilganda pastdagi
# lotlar kesiladi, kattalari esa saqlanadi.
ETENDER_BELGISI = "etender"
# Bir vaqtda nechta lotning hujjatlari yuklanadi. Ko'p bo'lsa
# etender so'rovlarni cheklashi mumkin, kam bo'lsa kuzatuv sekinlashadi.
HUJJAT_PARALLEL = 3

# HUJJAT BAHOSI — modelga yuboriladigan matn chegarasi.
#
# Gemini bepul tarifida kuniga JAMI 20 ta so'rov (`app/config.py`) —
# shuning uchun hamma lotning hujjati BITTA so'rovda boradi, har lotga
# alohida emas. Hajm esa cheklanadi: 511261 ning o'zi ~190 ming belgi
# (6 ta PDF, uchtasi bitta xarid hujjatining tarjimasi).
TZ_BAHO_LOT_BELGI = 24_000
TZ_BAHO_JAMI_BELGI = 120_000
TZ_KARTA_BELGI = 6_000
# Nomi shunga mos fayl UCH BAROBAR ko'p joy oladi. 511261: 16 betlik
# "Chiller TZ" 25 betlik xarid tartibi andozasidan muhimroq.
MUHIM_FAYL = re.compile(
    r"(?i)texnik|техни|topshiri|топшири|задани|specification|\btz\b|\bтз\b|"
    r"defekt|дефект|ilova|илова|smeta|смета"
)
MUHIM_ULUSH = 3
# Bir lotga ko'rsatiladigan hujjatdagi shartlar soni.
MAKS_TALAB = 5


# Muddat solishtiriladigan mintaqa.
#
# Mashina sozlamasiga TAYANMAYDI: server boshqa mintaqada bo'lsa
# "bugun" siljib ketardi va muddati bugun tugaydigan lot jimgina
# tashlanardi. Portal sanalari mahalliy vaqtda keladi.
MINTAQA = ZoneInfo("Asia/Tashkent")


def _muddati_otmaganlar(elonlar: list[Elon]) -> tuple[list[Elon], int]:
    """Muddati o'tgan lotlarni chiqarib tashlaydi.

    Qaytaradi: (qolganlar, tashlanganlar soni).

    IKKI QOIDA:
      - BUGUN tugaydigan lot QOLADI. Muddat 23:59 da tugaydi, ya'ni
        kun bo'yi taklif berish mumkin. Sanani solishtirganimiz uchun
        `>= bugun` deb tekshiriladi.
      - MUDDATI NOMA'LUM lot ham QOLADI. Manba muddat bermasa (DXMAP
        shunday) — biz u o'tgan deb qaror qila olmaymiz. Jimgina
        tashlash — bor imkoniyatni yo'qotish.
    """
    bugun = datetime.now(MINTAQA).date().isoformat()
    qolgan: list[Elon] = []
    tashlangan = 0
    for elon in elonlar:
        muddat = (elon.muddat or "").strip()[:10]
        if muddat and muddat < bugun:
            tashlangan += 1
            continue
        qolgan.append(elon)
    return qolgan, tashlangan


def _tartibla(
    elonlar: list[Elon], kurslar: dict[str, float] | None = None
) -> list[Elon]:
    """etender lotlari birinchi, keyin summa bo'yicha kamayib boradi.

    Summasi yo'q e'lon oxirida qoladi (0 deb hisoblanadi) — u haqida
    hech narsa deya olmaymiz, shuning uchun tepaga chiqarmaymiz.

    SUMMALAR SO'MGA KELTIRILIB solishtiriladi. etender lotni dollarda va
    yevroda ham e'lon qiladi — xom son bilan saralansa 700 000 yevrolik
    lot 1 mln so'mlik lotdan pastda qolardi. Kursi noma'lum valyuta
    summasiz lot kabi oxiriga tushadi: taxminiy kurs O'YLAB TOPILMAYDI.
    """
    return sorted(
        elonlar,
        key=lambda e: (
            0 if ETENDER_BELGISI in (e.maydoncha or e.manba).lower() else 1,
            -(valyuta_moduli.somga(e.summa, e.valyuta, kurslar) or 0),
        ),
    )
# Katalogdan promptga tushadigan kategoriya soni.
MAKS_KATEGORIYA = 30
# Har kategoriyadan promptga tushadigan mahsulot nomi soni.
MAKS_NOM = 12

QAMROV_IZOHI = (
    "Qamrov: etender.uzex.uz — kompaniya ro'yxatdan o'tgan va TAKLIF "
    "BERISH mumkin bo'lgan maydoncha. Savdo va muhokama ro'yxatlari, "
    "kalit so'zlar bo'yicha — shuning uchun ro'yxatga tushmagan e'lon "
    "bo'lishi mumkin. Boshqa maydonchalar (DXMAP orqali xarid.uzex.uz, "
    "xt-xarid.uz va h.k.) O'CHIRILGAN: u yerlarda taklif berish uchun "
    "alohida ro'yxatdan o'tish kerak."
)

TIZIM_PROMPT = """Sen "Tender kuzatuvchisi Jasur" — xarid e'lonlarini kuzatib
boradigan agentsan.

VAZIFAN: berilgan E'LONLAR ro'yxatidan kompaniyamiz BAJARA OLADIGANLARINI
ajratish.

Kompaniya IKKI XIL ish qiladi va IKKALASI ham tenderga yaraydi:
  1) USKUNA — ventilyatsiya va iqlim texnikasini ishlab chiqaradi va
     sotadi (ventilyator, kanal, panjara, klapan, filtr, konditsioner,
     chiller, rekuperator, issiqlik almashtirgich);
  2) XIZMAT — loyihalash, MONTAJ va o'rnatish, puskonaladka, SERVIS
     va texnik xizmat, ta'mirlash.

Ya'ni "ventilyatsiya tizimiga texnik xizmat ko'rsatish", "konditsioner
montaj qilish", "ventilyatsiya tizimini ta'mirlash" kabi lotlar ham
BIZNIKI. Ularni uskuna sotilmayapti deb rad ETMAYSAN.

BIZ ISHLAB CHIQARMAYDIGAN USKUNA — ALOHIDA TOIFA.

Quyidagilar bizning ishlab chiqarish doiramizda YO'Q:
  - MAISHIY split konditsioner (bizniki sanoat/markaziy: КЦКП, IXCHAM);
  - PRETSIZION konditsioner (server xonasi, ma'lumot markazi uchun);
  - aniq CHET EL brendi va modeli so'ralgan lot (masalan "TADIRAN
    ANLN-903H", "Daikin FTX-25") — bu bizning mahsulotimiz emas,
    biz distribyutor emasmiz.

BULARNI RAD ETMAYSAN, lekin `ishonch: "past"` qo'yasan va izohda
NIMA UCHUNini yozasan (masalan "pretsizion konditsioner ishlab
chiqarmaymiz; montaj qismi bizga tegishli bo'lishi mumkin").

Sababi: uskunani biz bermasak ham, MONTAJ va SERVIS bizning
xizmatimiz — menejer o'zi qaraydi. Lekin u buni "to'liq bizniki" deb
o'ylab, tayyorgarlik ko'rib, keyin uskunani bera olmasligini bilib
qolmasligi kerak.

`ishonch: "yuqori"` — faqat uskunasi HAM, xizmati HAM bizniki bo'lgan
lotga (ventilyatsiya tizimi, kanal, panjara, rekuperator, markaziy
konditsioner, issiqlik almashtirgich va shular bo'yicha montaj/servis).

QAT'IY QOIDALAR:
1) E'LON O'YLAB TOPMAYSAN. Faqat "E'LONLAR" bo'limida berilganlarini
   ko'rasan. Har biriga `raqam` orqali murojaat qilasan — havolani o'zing
   yozmaysan, uni tizim qo'yadi.
2) MOSLIKNI KENG OLMAYSAN. E'lon bizning doiramizga — ventilyatsiya va
   iqlim texnikasi USKUNASIGA yoki shu tizimlar bo'yicha XIZMATGA —
   tegishli bo'lsagina `mos` deb belgilaysan. Ofis mebeli, kompyuter,
   yer uchastkasi, avto ehtiyot qismi — mos EMAS.

   Kalit so'z tushgani mos degani ham emas. Jonli misollar
   (2026-09-09 da o'lchandi, model shularda adashgan):
     - "o'pkani sun'iy ventilyatsiyalash" — tibbiy apparat;
     - "deraza panjarasi", "RULONLI panjara", "to'siq panjara" —
       bular JALYUZI va TO'SIQ. Bizning panjaralarimiz havo uchun:
       RVR-2, 4RVP, RVN, RVI, РВ-1, RSH, ДФН;
     - "QOBIQ-TRUBALI (кожухотрубный) issiqlik almashtirgich" —
       neft-gaz jarayon uskunasi. Bizniki HAVO uchun mis-alyuminiy
       (VNV, VOV, KSK) — boshqa uskuna sinfi;
     - "muzlatgich", "sovutgich kamera" — maishiy/savdo sovutish,
       bizning sovutish uskunalarimiz sanoat chilleri va ККБ.

   ARALASH LOT (ventilyatsiya + elektr ta'minoti + nasos stansiyasi
   kabi) — `ishonch: "past"`, chunki lotning faqat bir qismi bizniki.
3) SHUBHALI bo'lsa `mos` deb belgila, lekin `ishonch: "past"` qo'y va
   nimasi noaniqligini yoz. Menejer o'zi qaraydi — biz faqat filtr emas,
   e'tiborni qaratamiz.
4) G'ALABA EHTIMOLINI BASHORAT QILMAYSAN, narx taklif qilmaysan.
5) Har mos e'lon uchun QAYSI mahsulotimizga YOKI QAYSI XIZMATIMIZGA
   tegishli ekanini yozasan (masalan "ventilyatsiya tizimiga servis").

   SARLAVHANI TAKRORLAMAYSAN. `nimaga_kerak` va `izoh` ga e'lon
   sarlavhasidagi gapni boshqa so'z bilan qayta yozish KERAK EMAS —
   menejer sarlavhani allaqachon ko'rgan. Faqat sarlavhada YO'Q
   ma'lumot yozasan: miqdor, o'lcham, model kodi, muddat sharti.
   Yangi ma'lumot bo'lmasa — ikkalasini ham BO'SH qoldirasan.
6) Mos e'lon bo'lmasa — bo'sh ro'yxat qaytarasan. Bu ham to'g'ri javob,
   ro'yxatni to'ldirish uchun aloqasiz e'lon qo'shmaysan.
7) MUDDATNI O'YLAB TOPMAYSAN. `muddat` ni faqat e'lon matnida taklif
   qabul qilish muddati ANIQ yozilgan bo'lsa to'ldirasan. E'lon sanasini
   muddat deb ko'chirmaysan — bu menejerni chalg'itadi. Muddat noma'lum
   bo'lsa bo'sh qoldirasan.
8) BUYURTMACHI allaqachon berilgan bo'lsa qayta yozmaysan — bo'sh
   qoldirasan. Nomni qisqartirish yoki "tuzatish" kerak emas.

SEN QILMAYDIGAN ISHLAR:
- Hech qanday tenderga ariza topshirmaysan.
- Tijorat taklifi tuzmaysan (bu Tijorat menejeri Temurning ishi).
- Raqobatchilarni tahlil qilmaysan (bu Raqobat tahlilchisi Karimning ishi).

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "mos_elonlar": [
    {
      "raqam": 1,
      "nimaga_kerak": "qaysi mahsulotimizga tegishli",
      "buyurtmachi": "e'londan olingan tashkilot nomi yoki bo'sh",
      "muddat": "e'londa aytilgan muddat yoki bo'sh",
      "ishonch": "yuqori | orta | past",
      "izoh": "qisqa izoh"
    }
  ],
  "mos_emas_soni": 0,
  "xulosa": "bir-ikki jumla"
}"""


class MosElon(BaseModel):
    """Modelning bahosi. `havola` maydoni ATAYLAB yo'q — kodda qo'yiladi."""

    raqam: int
    nimaga_kerak: str = ""
    buyurtmachi: str = ""
    muddat: str = ""
    ishonch: Ishonch = Ishonch.ORTA
    izoh: str = ""


class JasurNatija(BaseModel):
    mos_elonlar: list[MosElon] = Field(default_factory=list)
    mos_emas_soni: int = 0
    xulosa: str = ""


HUJJAT_PROMPT = """Sen "Tender kuzatuvchisi Jasur"san. Lotlar SARLAVHASI bo'yicha
"bizga mos" deb tanlangan. Endi ularning HUJJATLARINI — lot kartochkasi,
texnik topshiriq, baholash tartibi, shartnoma loyihasi — o'qib, bahoni
aniqlashtirasan.

NEGA: sarlavha adashtiradi. Jonli holatlar (2026-09-14):
  - "oshxona ventilyatsiyasini joriy ta'mirlash" — hujjatda bu faqat
    LOYIHA-SMETA hujjatlarini tuzish xizmati, ta'mirning o'zi emas;
  - "konditsionerlarni ko'rikdan o'tkazish va ta'mirlash" — shartnomada
    ehtiyot qismlar IJROCHI hisobidan, TZ esa ta'mirni alohida narxlaydi
    (hujjatlar bir-biriga zid);
  - "saroyning shamollatish tizimlari" — ishning katta qismi 10 kV
    podstansiya va nasos stansiyasi, 24/7 navbatchilik;
  - "sanoat chilleri" — o'xshash tovar yetkazganlik hujjati bo'lmasa
    ishtirokchi chetlashtiriladi.

HAR LOT UCHUN:
- `aslida` — hujjatga ko'ra ASLIDA nima xarid qilinadi, bitta jumla.
  Sarlavhaga yangi narsa qo'shmasa BO'SH qoldirasan.
- `talablar` — bizni TO'XTATISHI yoki PULGA TUSHIRISHI mumkin bo'lgan
  eng muhim shartlar, ko'pi bilan 5 ta, har biri qisqa: litsenziya yoki
  ruxsatnoma, majburiy tajriba hujjati, ehtiyot qism ijrochi hisobidan,
  jarima, qisqa muddat, uzoq joy, 24/7 navbatchilik, hujjatlar orasidagi
  ZIDDIYAT. Tayyorgarlik uchun muhim parametr ham bo'lishi mumkin
  (masalan "chiller 30–80 kW, ±1°C, 24/7").
  Hamma lotda bo'ladigan formal talablarni YOZMAYSAN: soliq qarzi
  yo'qligi, bankrot emaslik, insofsiz ijrochilar reyestri, korrupsiyaga
  qarshi ariza. "Shartlar:" qatorida berilganini ham takrorlamaysan.
- `ishonch` — asosiy qoidadagidek: "yuqori" faqat uskunasi HAM,
  xizmati HAM bizniki bo'lsa; "past" — uskunasi bizniki emas, lot
  aralash yoki bizni to'xtatadigan jiddiy talab bor.
- `mos: false` — FAQAT hujjat lot predmeti butunlay bizning doiramizdan
  tashqarida ekanini ko'rsatsa (sarlavhada "ventilyatsiya" bor, ish esa
  yo'l qurilishi). Sababini `aslida` ga yozasan. Shubha bo'lsa
  `mos: true` va `ishonch: "past"`.

QAT'IY QOIDALAR:
1) FAQAT hujjatda yozilganni yozasan, shart O'YLAB TOPMAYSAN. Matn
   skanerdan tanilgan bo'lib buzuq bo'lishi mumkin — o'qib bo'lmagan
   joyni taxmin qilmaysan.
   SHARTLI va ANDOZA gapni qat'iy talab deb YOZMAYSAN. "Agar sug'urta
   talab etilsa…", "Ishlar va xizmatlarda sug'urtalashga qo'yiladigan
   talablar" — bu portalning har lotdagi andoza mezoni, talabning o'zi
   emas. Talab faqat TZ yoki shartnomada QAT'IY yozilgan bo'lsa yoziladi
   ("montajdan oldin ijrochi sug'urta shartnomasini tuzishi shart").
2) Narx taklif qilmaysan, g'alaba ehtimolini bashorat qilmaysan.
3) Brendni tekshirmaysan — buni tizim alohida qiladi.
4) Ism, telefon, hisob raqam yozmaysan (matnda [shaxs], [telefon] deb
   yashirilgan).
5) Hujjati berilgan HAR lot uchun bitta baho, `raqam` bilan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

HUJJAT_JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "baholar": [
    {
      "raqam": 1,
      "mos": true,
      "ishonch": "yuqori | orta | past",
      "aslida": "hujjatga ko'ra aslida nima xarid qilinadi yoki bo'sh",
      "talablar": ["bizni to'xtatishi yoki pulga tushirishi mumkin bo'lgan shart"]
    }
  ]
}"""


class HujjatBaho(BaseModel):
    """Hujjat o'qilgandan keyingi baho. `havola` bu yerda ham YO'Q."""

    raqam: int
    mos: bool = True
    # Berilmasa sarlavha bo'yicha baho QOLADI — standart qiymat uni
    # jimgina "orta" ga almashtirmasin.
    ishonch: Ishonch | None = None
    aslida: str = ""
    talablar: list[str] = Field(default_factory=list)


class HujjatNatija(BaseModel):
    baholar: list[HujjatBaho] = Field(default_factory=list)


def _hujjat_parchasi(hujjat: LotHujjati, byudjet: int) -> str:
    """Modelga ketadigan qism — taxminan `byudjet` belgi.

    BO'SHLIQLAR SIQILADI: pypdf ko'p PDF da har so'zni alohida qatorga
    chiqaradi (511261 "Chiller TZ": 1379 qator, ruscha qismida deyarli
    har so'z yolg'iz) — bu joyning yarmi edi.

    JOY OG'IRLIK bilan taqsimlanadi, kalta fayldan ortgani qolganlarga
    o'tadi: TZ to'liq kirsin, xarid tartibi andozasi qisqarsin.
    """

    def siq(matn: str) -> str:
        return re.sub(r"\s+", " ", matn).strip()

    bolaklar: list[str] = []
    if hujjat.karta:
        bolaklar.append(siq(hujjat.karta)[:TZ_KARTA_BELGI])
    if hujjat.shartlar:
        bolaklar.append("Shartlar: " + "; ".join(hujjat.shartlar))
    qolgan = max(byudjet - sum(len(b) for b in bolaklar), 0)

    fayllar = [(nomi, siq(matn)) for nomi, matn in hujjat.fayllar]
    ogirlik = [MUHIM_ULUSH if MUHIM_FAYL.search(nomi) else 1 for nomi, _ in fayllar]
    joy = [0] * len(fayllar)
    qolgan_ogirlik = sum(ogirlik)
    for i in sorted(range(len(fayllar)), key=lambda i: len(fayllar[i][1]) / ogirlik[i]):
        joy[i] = min(len(fayllar[i][1]), qolgan * ogirlik[i] // qolgan_ogirlik)
        qolgan -= joy[i]
        qolgan_ogirlik -= ogirlik[i]
    for (nomi, matn), belgi in zip(fayllar, joy):
        kesildi = " …[qisqartirildi]" if belgi < len(matn) else ""
        bolaklar.append(f"--- {nomi} ---\n{matn[:belgi]}{kesildi}")
    return "\n".join(bolaklar)


class TenderKuzatuvchi(Agent):
    """Tender kuzatuvchisi Jasur."""

    def __init__(self, *args: Any, manbalar: list[Manba] | None = None, **kw: Any):
        super().__init__(*args, **kw)
        if manbalar is not None:
            self.manbalar = manbalar
        else:
            # `.env` dagi `TENDER_MANBALARI` — standart holat faqat
            # `etender` (ishtirok etsa bo'ladigan yagona maydoncha).
            self.manbalar = standart_manbalar(sozlama().tender_manba_nomlari)

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        self._muddati_otgan = 0
        self._kurslar: dict[str, float] = {"UZS": 1.0}

        elonlar, nosozliklar = await elonlarni_yig(self.manbalar, MAKS_ELON)
        if nosozliklar:
            self.ogohlantirish = "; ".join(nosozliklar)
        if not elonlar:
            return await self._bosh_javob(nosozliklar)

        # Ko'rilganlar chiqarib tashlanadi — har kuni bir xil ro'yxat kelmasin.
        #
        # TARTIBLAB, KEYIN kesamiz: chegaraga urilganda eng arzoni
        # tushib qolsin, tasodifiy oxirgisi emas.
        # ODAM O'ZI SO'RAGANDA JURNALGA QARAMAYMIZ.
        #
        # `/tender` yozgan menejer "yangi nima bor" degan savolni emas,
        # "hozir nima bor" degan savolni beradi. Ilgari ikkalasi bir xil
        # ishlardi va javob "hammasi ilgari ko'rilgan" bo'lib chiqardi —
        # holbuki menejer o'sha ro'yxatni umuman ko'rmagan bo'lishi
        # mumkin (xabar yo'qolgan, bot qayta ishga tushgan, o'tkazib
        # yuborilgan ish jimgina bajarilgan).
        #
        # KUNLIK ish esa jurnalni ishlatadi — aks holda har kuni bir xil
        # ro'yxat kelib, menejer o'qishni to'xtatadi.
        # MUDDATI O'TGAN LOT KO'RSATILMAYDI — unga taklif berib
        # bo'lmaydi. Nechtasi tashlangani ochiq aytiladi: jimgina
        # yo'qolsa, manba ishlamayapti deb o'ylash mumkin edi.
        elonlar, muddati_otgan = _muddati_otmaganlar(elonlar)
        if not elonlar:
            return await self._javob(
                natija=JasurNatija(
                    xulosa=(
                        f"Ochiq e'lon yo'q — topilgan {muddati_otgan} ta "
                        "lotning muddati o'tgan."
                    )
                ),
                yangilar=[],
                korilgan_soni=muddati_otgan,
            )

        hammasini = bool((kontekst or {}).get("hammasini_korsat"))
        korilishi = elonlar if hammasini else await self._yangilari(elonlar)
        self._kurslar = await self._kurslarni_ol(korilishi)
        yangilar = _tartibla(korilishi, self._kurslar)[:MAKS_ELON]
        self._muddati_otgan = muddati_otgan
        if not yangilar:
            return await self._javob(
                natija=JasurNatija(xulosa="Yangi e'lon yo'q — hammasi ilgari ko'rilgan."),
                yangilar=[],
                korilgan_soni=len(elonlar),
            )

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += await self._katalog_matni()
        topshiriq += self._elon_matni(yangilar)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=JasurNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        try:
            natija = JasurNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return await self._javob(natija, yangilar, korilgan_soni=len(elonlar))

    # --- yordamchilar --------------------------------------------------------

    async def _yangilari(self, elonlar: list[Elon]) -> list[Elon]:
        try:
            korilgan = await self.baza.korilgan_tenderlar([e.kalit for e in elonlar])
        except Exception:  # jurnal ishlamasa ham kuzatuv to'xtamaydi
            korilgan = set()
        return [e for e in elonlar if e.kalit not in korilgan]

    async def _katalog_matni(self) -> str:
        """Nimaga mos kelishini bilishi uchun mahsulot doirasi."""
        try:
            mahsulotlar = await self.api.mahsulotlar()
        except ApiXatosi as xato:
            self.ogohlantirish = "; ".join(
                filter(None, [self.ogohlantirish, f"katalog ochilmadi ({xato})"])
            )
            return ""

        # MAHSULOT NOMLARI beriladi, faqat kategoriya emas.
        #
        # O'LCHANDI (2026-09-09): modelga faqat "Issiqlik almashish
        # uskunalari: 14" kabi kategoriya nomi berilardi. Natijada u
        # neftni qayta ishlash uchun QOBIQ-TRUBALI apparatni ham shu
        # kategoriyaga qo'shdi — holbuki bizniki mis-alyuminiy HAVO
        # issiqlik almashtirgichi (VNV, VOV). Xuddi shunday
        # "Ventilyatsiya panjaralari: 11" ni ko'rib RULONLI panjarani
        # (to'siq jalyuzi) ham mos dedi.
        #
        # Nom bilan model aniq solishtira oladi: katalogda "rulonli
        # panjara" yo'q, "RVR-2", "ДФН", "RSH" bor.
        kategoriyalar: dict[str, list[str]] = {}
        for mahsulot in mahsulotlar:
            qisqa = mahsulot_qisqa(mahsulot)
            kategoriya = qisqa["kategoriya"] or "(kategoriyasiz)"
            nomi = (qisqa["nomi"] or "").strip()
            if nomi:
                kategoriyalar.setdefault(kategoriya, []).append(nomi)

        # "FAQAT USKUNA" ATAYLAB yozilgan: katalogda xizmat yo'q va
        # modelga shu ro'yxat butun doiramizdek ko'rinardi. Natijada
        # montaj/servis lotlari "katalogda yo'q" deb rad etilardi.
        qatorlar = [
            "\n\nBIZNING MAHSULOT DOIRAMIZ — FAQAT USKUNA qismi. "
            "Xizmatlar bu ro'yxatda YO'Q, ular kompaniya profilida "
            "sanalgan. Lot shu ro'yxatdagi ANIQ mahsulotga mos "
            "kelishini tekshir — kategoriya nomi o'xshash bo'lgani "
            "YETARLI EMAS:"
        ]
        for kategoriya, nomlar in sorted(
            kategoriyalar.items(), key=lambda x: -len(x[1])
        )[:MAKS_KATEGORIYA]:
            qatorlar.append(f"- {kategoriya}:")
            for nomi in nomlar[:MAKS_NOM]:
                qatorlar.append(f"    · {nomi[:70]}")
            if len(nomlar) > MAKS_NOM:
                qatorlar.append(f"    · …yana {len(nomlar) - MAKS_NOM} ta")
        return "\n".join(qatorlar)

    @staticmethod
    def _elon_matni(elonlar: list[Elon]) -> str:
        qatorlar = [f"\n\nE'LONLAR ({len(elonlar)} ta yangi):"]
        for i, elon in enumerate(elonlar, 1):
            # Sana ATAYLAB "e'lon sanasi" deb belgilanadi. Belgilanmaganda
            # model uni tugash muddati deb o'ylab, `muddat` maydoniga
            # ko'chirib qo'yardi — menejer uchun bu yolg'on muddat.
            sana = f" [e'lon sanasi: {elon.sana}]" if elon.sana else ""
            qatorlar.append(f"{i}.{sana} {elon.sarlavha}")
            # Tuzilgan maydonlar — modelga qaror uchun kontekst beradi
            # (masalan «texnik xizmat» bilan «yetkazib berish» farqi).
            tafsilot = []
            if elon.buyurtmachi:
                tafsilot.append(f"buyurtmachi: {elon.buyurtmachi[:70]}")
            if elon.summa:
                tafsilot.append(
                    f"summa: {valyuta_moduli.pul_matni(elon.summa, elon.valyuta)}"
                )
            if elon.hudud:
                tafsilot.append(f"hudud: {elon.hudud}")
            if tafsilot:
                qatorlar.append("   " + " | ".join(tafsilot))
            if elon.tavsif:
                qatorlar.append(f"   {elon.tavsif[:300]}")
        qatorlar.append(
            "\nHar biriga `raqam` (yuqoridagi tartib raqami) bilan murojaat qil. "
            "Buyurtmachi allaqachon berilgan bo'lsa uni QAYTA yozma — bo'sh qoldir."
        )
        return "\n".join(qatorlar)

    async def _kurslarni_ol(self, elonlar: list[Elon]) -> dict[str, float]:
        """Markaziy bank kurslari — faqat so'mdan boshqa valyutadagi lot bo'lsa.

        Kurs olinmasa kuzatuv to'xtamaydi: xorijiy valyutadagi lotlar
        ro'yxat oxiriga tushadi va buni menejer ogohlantirishda ko'radi.
        """
        if all((e.valyuta or "UZS").upper() == "UZS" for e in elonlar):
            return {"UZS": 1.0}
        try:
            return await valyuta_moduli.markaziy_bank_kurslari()
        except valyuta_moduli.KursXatosi as xato:
            self.ogohlantirish = "; ".join(filter(None, [
                self.ogohlantirish,
                f"valyuta kursi olinmadi ({xato}) — dollar va yevrodagi "
                "lotlar ro'yxat oxirida",
            ]))
            return {"UZS": 1.0}

    async def _hujjatlarni_ol(
        self, mos: list[dict[str, Any]]
    ) -> tuple[dict[int, LotHujjati], int]:
        """Mos lotlarning hujjatlari: kartochka, shartlar, TZ, shartnoma.

        Shu yerda BEGONA BREND ham belgilanadi. JONLI HOLAT (2026-09-14):
        510351-lot "VRF tashqi bloklariga ta'mir" "bizga mos" deb
        ko'rsatilgan, texnik topshiriqda esa "Марка/модель: ARV6-H610/SR1MV"
        — AUX, bizning brend emas. Boshqaruv platasi (lotning 30 foizi)
        aynan shu brendning original qismini talab qilardi.

        Qaytaradi: (`mos` dagi o'rni -> hujjat, hujjatlari O'QILMAGAN lotlar
        soni). Kartochkasi ochilmagan yoki birorta fayli o'qilmagan lot
        "brend yo'q" deb jimgina hisoblanmaydi.
        """
        nishonlar = []
        for orni, yozuv in enumerate(mos):
            havola = str(yozuv.get("havola") or "")
            if lot_id := tender_moduli.etender_lot_id(havola):
                nishonlar.append((orni, tender_moduli.etender_lot_hujjatlari, lot_id))
            elif lot_id := tender_moduli.mcuz_lot_id(havola):
                nishonlar.append((orni, tender_moduli.mcuz_lot_hujjatlari, lot_id))
        if not nishonlar:
            return {}, 0

        cheklov = asyncio.Semaphore(HUJJAT_PARALLEL)

        async def ol(orni: int, yukla: Any, lot_id: str) -> tuple[int, LotHujjati | None]:
            async with cheklov:
                try:
                    return orni, await yukla(lot_id)
                except Exception:  # noqa: BLE001 — bitta lot butun javobni yiqitmasin
                    return orni, None

        hujjatlar: dict[int, LotHujjati] = {}
        oqilmadi = 0
        for orni, hujjat in await asyncio.gather(*(ol(*n) for n in nishonlar)):
            if hujjat is None or (hujjat.oqilmagan and not hujjat.fayllar):
                oqilmadi += 1
            if hujjat is None:
                continue
            yozuv = mos[orni]
            hujjatlar[orni] = hujjat
            if hujjat.shartlar:
                yozuv["shartlar"] = hujjat.shartlar
            if hujjat.oqilmagan:
                yozuv["oqilmagan_fayllar"] = hujjat.oqilmagan
            if topilgan := begona_brendlar(hujjat.matn):
                yozuv["begona_brend"] = [t.korinish for t in topilgan]
        return hujjatlar, oqilmadi

    async def _hujjat_bilan_bahola(
        self, mos: list[dict[str, Any]], hujjatlar: dict[int, LotHujjati]
    ) -> str:
        """Hujjatlarni modelga o'qitib, bahoni aniqlashtiradi.

        Hamma lot BITTA so'rovda (kvota). Model yiqilsa sarlavha bo'yicha
        baho QOLADI, sababi esa qaytariladi — menejer uni ochiq ko'radi.

        Qaytaradi: bo'sh satr — baholandi yoki baholanadigan hujjat yo'q;
        aks holda nega baholanmagani.
        """
        tanlangan = [(orni, h) for orni, h in sorted(hujjatlar.items()) if not h.bosh]
        if not tanlangan:
            return ""
        byudjet = min(TZ_BAHO_LOT_BELGI, TZ_BAHO_JAMI_BELGI // len(tanlangan))

        qatorlar = [f"LOTLAR HUJJATLARI ({len(tanlangan)} ta):"]
        for raqam, (orni, hujjat) in enumerate(tanlangan, 1):
            yozuv = mos[orni]
            qatorlar.append("")
            qatorlar.append(f"=== {raqam}. {yozuv.get('sarlavha') or '—'} ===")
            tafsilot = []
            if yozuv.get("summa"):
                tafsilot.append(
                    "summa: "
                    + valyuta_moduli.pul_matni(yozuv["summa"], yozuv.get("valyuta"))
                )
            if yozuv.get("hudud"):
                tafsilot.append(f"hudud: {yozuv['hudud']}")
            if yozuv.get("muddat"):
                tafsilot.append(f"taklif muddati: {yozuv['muddat']}")
            if tafsilot:
                qatorlar.append(" | ".join(tafsilot))
            # SHAXSIY MA'LUMOT YASHIRILADI — so'rov tashqi modelga ketadi.
            qatorlar.append(yashir(_hujjat_parchasi(hujjat, byudjet)))

        try:
            javob = await self.modelga_sorov(
                topshiriq="\n".join(qatorlar),
                tizim_prompt=HUJJAT_PROMPT,
                natija_modeli=HujjatNatija,
                json_skelet=HUJJAT_JSON_SKELET,
            )
            natija = HujjatNatija.model_validate(json_ajrat(matn_yig(javob)))
        except anthropic.APIError as xato:
            return llm_xato_matni(xato)
        except Exception as xato:  # noqa: BLE001 — qo'shimcha baho yiqilsa asosiy javob qoladi
            return f"{type(xato).__name__}: {xato}"[:200]

        for baho in natija.baholar:
            if not 1 <= baho.raqam <= len(tanlangan):
                continue  # noto'g'ri raqam — jimgina tashlanadi
            yozuv = mos[tanlangan[baho.raqam - 1][0]]
            aslida = baho.aslida.strip()
            if aslida:
                yozuv["tz_aslida"] = aslida
            talablar = [t.strip() for t in baho.talablar if t and t.strip()]
            if talablar:
                yozuv["tz_talablar"] = talablar[:MAKS_TALAB]
            if baho.ishonch is not None:
                yozuv["ishonch"] = baho.ishonch.value
            # Chiqarish faqat SABABI bilan — sababsiz "mos emas" e'tiborsiz.
            if not baho.mos and aslida:
                yozuv["tz_mos_emas"] = True
        return ""

    async def _jurnalga_yoz(self, yangilar: list[Elon], mos_kalitlar: set[str]) -> None:
        """Ko'rilgan e'lonlarni belgilaydi — ertaga qayta ko'rsatilmasin."""
        if not yangilar:
            return
        try:
            await self.baza.tender_yoz([
                {**e.qisqa(), "kalit": e.kalit, "mosmi": e.kalit in mos_kalitlar}
                for e in yangilar
            ])
        except Exception as xato:  # jurnal yiqilsa ham natija yo'qolmaydi
            self.ogohlantirish = "; ".join(
                filter(None, [self.ogohlantirish, f"jurnalga yozilmadi ({xato})"])
            )

    async def _bosh_javob(self, nosozliklar: list[str]) -> Konvert:
        """Manbalarda hech narsa yo'q: nosozlikmi yoki chindan bo'shmi?"""
        if nosozliklar:
            return xato_konvert(
                self.rol,
                "E'lon manbalariga ulanib bo'lmadi: " + "; ".join(nosozliklar),
                {"qamrov_izohi": QAMROV_IZOHI},
            )
        return await self._javob(
            JasurNatija(xulosa="Manbalarda umuman e'lon topilmadi."), [], 0
        )

    async def _javob(
        self, natija: JasurNatija, yangilar: list[Elon], korilgan_soni: int
    ) -> Konvert:
        """Model bahosini e'lon ma'lumoti bilan birlashtiradi.

        Havola va sarlavha MANBADAN olinadi, modeldan emas — shuning uchun
        mavjud bo'lmagan tender ko'rsatilishi mumkin emas.
        """
        mos: list[dict[str, Any]] = []
        for baho in natija.mos_elonlar:
            if not 1 <= baho.raqam <= len(yangilar):
                continue  # noto'g'ri raqam — jimgina tashlanadi
            elon = yangilar[baho.raqam - 1]
            yozuv = {
                **elon.qisqa(),
                "nimaga_kerak": baho.nimaga_kerak,
                "ishonch": baho.ishonch.value,
                "izoh": baho.izoh,
            }
            # Buyurtmachini MANBA bergan bo'lsa o'sha qoladi. Model faqat
            # manba jim bo'lganda to'ldiradi — havoladagi tamoyilning
            # o'zi: tekshirib bo'ladigan ma'lumot taxmindan ustun.
            if not elon.buyurtmachi and baho.buyurtmachi:
                yozuv["buyurtmachi"] = baho.buyurtmachi
            # MUDDAT ham shunday. `etender.uzex.uz` haqiqiy `end_date`
            # beradi — model taxmini uni ustidan yozib yubormasin.
            # Ilgari `"muddat": baho.muddat` deb qo'yilardi va manbadagi
            # aniq sana yo'qolardi.
            if not elon.muddat and baho.muddat:
                yozuv["muddat"] = baho.muddat
            mos.append(yozuv)

        # HUJJATLAR — sarlavhada yo'q narsa shu yerda: begona brend, aslida
        # nima xarid qilinishi, bizni to'xtatadigan shart.
        dastlabki = {id(m): m.get("ishonch") for m in mos}
        hujjatlar, hujjat_oqilmadi = await self._hujjatlarni_ol(mos)
        hujjat_baholanmadi = await self._hujjat_bilan_bahola(mos, hujjatlar)
        if hujjat_baholanmadi:
            self.ogohlantirish = "; ".join(filter(None, [
                getattr(self, "ogohlantirish", ""),
                f"hujjatlar baholanmadi ({hujjat_baholanmadi})",
            ]))
        # BEGONA BREND model bahosidan USTUN: model "yuqori" desa ham lot
        # pastki bo'limga tushadi.
        for yozuv in mos:
            if yozuv.get("begona_brend"):
                yozuv["ishonch"] = "past"
        # Hujjat o'qilgach mos emasligi ANIQ bo'lganlar ro'yxatdan chiqadi,
        # lekin jimgina yo'qolmaydi — sababi bilan alohida sanaladi.
        chiqarilgan = [
            {"sarlavha": m.get("sarlavha"), "havola": m.get("havola"),
             "sabab": m.get("tz_aslida")}
            for m in mos if m.get("tz_mos_emas")
        ]
        mos = [m for m in mos if not m.get("tz_mos_emas")]
        # SARLAVHA XULOSASI ESKIRADI. Jonli holat (2026-09-14): model
        # "3 tasi yuqori ishonchli" deb yozgan, hujjat o'qilgach yuqorisi
        # bitta qoldi — ro'yxat va xulosa bir-biriga zid ko'rinardi.
        ozgargan = len(chiqarilgan) + sum(
            1 for m in mos if m.get("ishonch") != dastlabki.get(id(m))
        )
        xulosa = natija.xulosa
        if ozgargan and xulosa:
            xulosa = (
                f"Sarlavha bo'yicha dastlabki xulosa: {xulosa}\n"
                f"Hujjatlar o'qilgach {ozgargan} ta lotning bahosi o'zgardi — "
                "yuqoridagi ro'yxat hujjat bo'yicha."
            )

        # CHIQISH TARTIBI ham bir xil: model raqamlarni istalgan tartibda
        # qaytarishi mumkin, menejer esa kattasini birinchi ko'rishi kerak.
        mos.sort(
            key=lambda m: (
                0 if ETENDER_BELGISI in str(
                    m.get("maydoncha") or m.get("manba") or ""
                ).lower() else 1,
                -(valyuta_moduli.somga(
                    m.get("summa"), m.get("valyuta"), getattr(self, "_kurslar", None)
                ) or 0),
            )
        )

        mos_kalitlar = {m["havola"].strip().lower() for m in mos}
        await self._jurnalga_yoz(yangilar, mos_kalitlar)

        malumot = {
            "mos_elonlar": mos,
            "yangi_korildi": len(yangilar),
            "jami_korildi": korilgan_soni,
            "mos_emas_soni": max(len(yangilar) - len(mos), 0),
            # Hujjatlari o'qilmagan lotlar soni — brendi va shartlari
            # TEKSHIRILMAGAN. Kalit nomi eski: presenter va kesh shuni o'qiydi.
            "brend_tekshirilmadi": hujjat_oqilmadi,
            # Hujjat bahosi olinmagan bo'lsa sababi — baho sarlavha bo'yicha qoldi.
            "hujjat_baholanmadi": hujjat_baholanmadi,
            "hujjat_chiqargan": chiqarilgan,
            # Muddati o'tganlar OCHIQ sanaladi: jimgina tashlansa,
            # menejer manba ishlamayapti deb o'ylashi mumkin edi.
            "muddati_otgan": getattr(self, "_muddati_otgan", 0),
            "xulosa": xulosa,
            "qamrov_izohi": QAMROV_IZOHI,
            "manbalar": [getattr(m, "nomi", "manba") for m in self.manbalar],
            # Qaysi kalit so'zlar bo'yicha qidirilgani — topilmagan e'lon
            # jimgina yo'qolmasin, menejer qamrovni ko'rib tursin.
            "qidiruv_qamrovi": [
                m.qamrov() for m in self.manbalar if hasattr(m, "qamrov")
            ],
        }

        izoh = (
            f"{len(mos)} ta mos e'lon"
            if mos
            else "Yangi mos e'lon yo'q"
        )
        if yangilar:
            izoh += f" ({len(yangilar)} ta yangi e'lon ko'rildi)"

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=malumot,
            manba=[
                self.kontrakt_manbasi(),
                *[
                    KonvertManba(tur="veb", nom=m["manba"] or "e'lon sayti",
                                 havola=m["havola"])
                    for m in mos[:5]
                ],
            ]
            or [self.kontrakt_manbasi()],
            ishonch=Ishonch.YUQORI if mos else Ishonch.ORTA,
            tasdiq_kerak=False,
            izoh=izoh,
        )

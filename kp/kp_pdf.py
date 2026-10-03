"""Tayyor Climavent KP (PDF) ni qatorlarga ajratish.

NEGA KERAK
----------
Menejerlar KP ni o'z dasturida tuzadi va mijozga PDF yuboradi. Bu PDF
ni tizim o'qiy olmasa, uni TZ bilan SOLISHTIRIB bo'lmaydi
(`kp/solishtir.py`) va yangi TZ->KP natijasini haqiqiy KP bilan
o'lchab bo'lmaydi (etalon).

QANDAY O'QILADI
---------------
PDF da jadval yo'q — faqat sahifadagi joyi (x, y) bilan yozilgan matn
bo'laklari bor. Shuning uchun:

  1. har bo'lakning koordinatasi olinadi (`pypdf` visitor);
  2. chap chekkadagi «1», «2»… — qator raqamlari, ular qator chegarasi;
  3. qator raqami bilan bir balandlikdagi pul qiymatlari — narx/summa;
  4. nom ustunidagi bo'laklar o'z qatoriga yig'iladi. Sahifa boshida
     raqamsiz turgan nom — oldingi sahifadagi qatorning davomi.

PUL USTUNLARI TARTIBGA QARAB EMAS, HISOB BILAN aniqlanadi: QQS bo'lagi
PDF da alohida yoziladi va x bo'yicha saralasa joyi aralashadi. Shuning
uchun «narx × miqdor = summa» va «summa + QQS = jami» shartini
qanoatlantiradigan to'rtlik qidiriladi.

`pymupdf` ishlatilmaydi: serverda faqat `pypdf` bor (requirements.txt).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path

# «3 324 000,00», «0,00» — PDF dagi pul yozuvi.
_PUL = re.compile(r"\d{1,3}(?:[  ]\d{3})*,\d{2}")
# Qator boshidagi miqdor: « 12  196 200,00 …» -> 12.
_MIQDOR = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s{2,}")

# Ustunlar chegarasi (pt). Shablon bir xil — Crystal Reports blanki.
RAQAM_X = 40        # qator raqami shundan chapda
NOM_X = (35, 215)   # nom ustuni (bo'lak BOSHI shu oraliqda)
BIRLIK_X = (215, 250)

TOLERANS = 4.0      # bir qatordagi bo'laklar balandligi farqi

# Jadval sarlavhasi va undan tashqaridagi matn — nomga qo'shilmasin.
_SARLAVHA_SOZLARI = ("Наименование", "Цена за шт", "Ед.", "Кол-во", "НДС 12%",
                     "Сумма с учетом", "изм")


@dataclass
class KpQator:
    raqam: int
    nomi: str
    birlik: str = ""
    miqdor: float = 0
    narx: float | None = None
    summa: float | None = None
    qqs: float | None = None
    jami: float | None = None

    @property
    def sarlavhami(self) -> bool:
        """«- 9-секция», «- K1.K4» — bo'lim sarlavhasi, mahsulot emas.

        Menejer dasturida sarlavha ham qator bo'lib yoziladi va 0 narx
        bilan chiqadi. Uni mahsulot deb sanasak KP «ortiqcha qator»
        bilan to'lib ketadi.
        """
        return self.nomi.startswith("-") and not self.narx

    @property
    def toza_nomi(self) -> str:
        return self.nomi.lstrip("- ").strip()


@dataclass
class KpHujjat:
    yol: str
    raqam: str = ""
    sana: str = ""
    mijoz: str = ""
    qatorlar: list[KpQator] = field(default_factory=list)
    itogo_summa: float | None = None
    itogo_jami: float | None = None

    @property
    def mahsulotlar(self) -> list[KpQator]:
        return [q for q in self.qatorlar if not q.sarlavhami]

    def yigindi_mosmi(self) -> bool:
        """Qatorlar yig'indisi «Итого» bilan bir xilmi — o'qish to'g'riligi."""
        if self.itogo_summa is None:
            return False
        jami = sum(q.summa or 0 for q in self.qatorlar)
        return abs(jami - self.itogo_summa) < 1.0


def _pul(matn: str) -> float:
    return float(matn.replace(" ", "").replace(" ", "").replace(",", "."))


@dataclass
class _Bolak:
    x: float
    y: float
    matn: str


def _bolaklar(bet) -> list[_Bolak]:
    natija: list[_Bolak] = []

    def ushla(matn, cm, tm, _fd, _fs):
        if not matn or not matn.strip():
            return
        x = tm[4] * cm[0] + cm[4]
        y = tm[5] * cm[3] + cm[5]
        natija.append(_Bolak(round(x, 1), round(y, 1), matn))

    bet.extract_text(visitor_text=ushla)
    return natija


def _pul_tortligi(qiymatlar: list[float], miqdor: float):
    """(narx, summa, qqs, jami) — hisob bo'yicha mos to'rtlik."""
    for narx, summa in itertools.permutations(qiymatlar, 2):
        if abs(narx * miqdor - summa) > max(1.0, summa * 1e-6):
            continue
        qolgan = list(qiymatlar)
        qolgan.remove(narx)
        qolgan.remove(summa)
        for qqs, jami in itertools.permutations(qolgan, 2):
            if abs(summa + qqs - jami) < 1.0:
                return narx, summa, qqs, jami
        if not qolgan:
            return narx, summa, None, None
    return None


def kp_oqi(yol: str | Path) -> KpHujjat:
    """Climavent KP PDF faylidan raqam, mijoz va qatorlarni o'qiydi."""
    from pypdf import PdfReader

    hujjat = KpHujjat(yol=str(yol))
    oxirgi: KpQator | None = None
    tugadi = False

    for bet_n, bet in enumerate(PdfReader(str(yol)).pages):
        if tugadi:
            break
        bolaklar = _bolaklar(bet)

        if bet_n == 0:
            _boshni_oqi(hujjat, bolaklar)

        # Jadval chegaralari: tepada sarlavha, pastda «Итого».
        tepa = min((b.y for b in bolaklar if "Наименование" in b.matn and b.y < 800),
                   default=None)
        if tepa is None:
            tepa = min((b.y for b in bolaklar if "Сумма" == b.matn.strip()),
                       default=10_000)
        itogo = [b for b in bolaklar if b.matn.strip().startswith("Итого")]
        past = itogo[0].y if itogo else -1
        if itogo:
            tugadi = True
            _itogoni_oqi(hujjat, bolaklar, itogo[0].y)

        raqamlar = sorted(
            (b for b in bolaklar
             if b.x < RAQAM_X and re.fullmatch(r"\d+", b.matn.strip())
             and past < b.y < tepa),
            key=lambda b: -b.y)

        # Har qatorning y oralig'i: o'z raqamidan keyingisigacha.
        chegaralar = [r.y for r in raqamlar]
        for i, r in enumerate(raqamlar):
            yuqori = r.y + TOLERANS
            quyi = (chegaralar[i + 1] + TOLERANS) if i + 1 < len(raqamlar) else past
            bir_qatorda = [b for b in bolaklar if abs(b.y - r.y) < TOLERANS and b.x > BIRLIK_X[1]]
            qator = KpQator(raqam=int(r.matn.strip()), nomi="")
            _pullarni_qoy(qator, bir_qatorda)
            birlik = [b.matn.strip() for b in bolaklar
                      if BIRLIK_X[0] <= b.x < BIRLIK_X[1] and quyi < b.y <= yuqori]
            qator.birlik = birlik[0] if birlik else ""
            qator.nomi = _nom_yig(bolaklar, quyi, yuqori)
            hujjat.qatorlar.append(qator)
            oxirgi = qator

        # Sahifa boshida raqamsiz nom — oldingi qatorning davomi.
        if oxirgi is not None and bet_n > 0:
            birinchi = raqamlar[0].y + TOLERANS if raqamlar else past
            davomi = _nom_yig(bolaklar, birinchi, tepa)
            if davomi:
                # Davom oldingi sahifadagi oxirgi qatorga tegishli —
                # shu sahifa qatorlari qo'shilishidan OLDINGI qator.
                indeks = len(hujjat.qatorlar) - len(raqamlar) - 1
                if indeks >= 0:
                    hujjat.qatorlar[indeks].nomi = (
                        hujjat.qatorlar[indeks].nomi + " " + davomi).strip()

    return hujjat


def _nom_yig(bolaklar: list[_Bolak], quyi: float, yuqori: float) -> str:
    qismlar = [b for b in bolaklar
               if NOM_X[0] <= b.x < NOM_X[1] and quyi < b.y <= yuqori
               and not any(s in b.matn for s in _SARLAVHA_SOZLARI)
               # Eski blankada qator raqami nom ustuniga yaqin turadi.
               and not (b.x < 45 and re.fullmatch(r"\d+", b.matn.strip()))]
    # Yuqoridan pastga, bir qatorda chapdan o'ngga.
    qismlar.sort(key=lambda b: (-round(b.y), b.x))
    matn = " ".join(b.matn.replace("\n", " ").strip() for b in qismlar)
    return re.sub(r"\s+", " ", matn).strip()


def _pullarni_qoy(qator: KpQator, bolaklar: list[_Bolak]) -> None:
    bolaklar = sorted(bolaklar, key=lambda b: b.x)
    matn = "  ".join(b.matn for b in bolaklar)
    mos = _MIQDOR.match(bolaklar[0].matn) if bolaklar else None
    if mos:
        qator.miqdor = float(mos.group(1).replace(",", "."))
        # Miqdor raqamini pul qatoridan olib tashlaymiz.
        matn = matn.replace(mos.group(0), " ", 1)
    qiymatlar = [_pul(p) for p in _PUL.findall(matn)]
    if not qator.miqdor:
        return
    tortlik = _pul_tortligi(qiymatlar, qator.miqdor)
    if tortlik:
        qator.narx, qator.summa, qator.qqs, qator.jami = tortlik


def _boshni_oqi(hujjat: KpHujjat, bolaklar: list[_Bolak]) -> None:
    for b in bolaklar:
        matn = b.matn.strip()
        if matn.startswith("№") and not hujjat.raqam:
            hujjat.raqam = matn.lstrip("№ ").strip()
        mos = re.search(r"от\s+(\d{2}\.\d{2}\.\d{4})", matn)
        if mos and not hujjat.sana:
            hujjat.sana = mos.group(1)
    murojaat = [b for b in bolaklar if b.matn.strip().startswith("Руководителю")]
    if murojaat:
        m = murojaat[0]
        pastda = [b for b in bolaklar
                  if abs(b.x - m.x) < 5 and m.y - 40 < b.y < m.y - 1]
        pastda.sort(key=lambda b: -b.y)
        hujjat.mijoz = " ".join(b.matn.strip() for b in pastda).strip()


def _itogoni_oqi(hujjat: KpHujjat, bolaklar: list[_Bolak], y: float) -> None:
    qiymatlar = []
    for b in sorted(bolaklar, key=lambda b: b.x):
        if abs(b.y - y) < TOLERANS + 4:
            qiymatlar += [_pul(p) for p in _PUL.findall(b.matn)]
    if qiymatlar:
        hujjat.itogo_summa = min(qiymatlar)
        hujjat.itogo_jami = max(qiymatlar)

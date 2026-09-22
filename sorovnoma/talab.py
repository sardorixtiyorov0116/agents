"""So'rovnoma ta'riflari — YAML dan o'qiladi, kodda emas.

NEGA AYNAN SHUNDAY
------------------
Zavodda 12 ta oprosniy list bor va ular o'zgarib turadi: yangi model
qatori qo'shiladi, tozalash klassi olib tashlanadi. Savollar kodda
bo'lsa har o'zgarishga dasturchi kerak bo'lardi. YAML da esa muhandis
o'zi tahrirlaydi.

`Savol` va `Tanlov` KP shaklidan olinadi (`kp/shakl.py`) — ikkalasi bir
xil tugmali oqim, ikkita alohida dvigatel yozish takror bo'lardi.
Farqi: KP shaklida savollar ro'yxati QAT'IY (kodda yozilgan), bu yerda
esa bo'limga qarab ALMASHADI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yaml

from app.config import sozlama
from kp.shakl import Savol, ShaklXatosi, Tanlov, bosh_bolmagan_matn, butun_son

SOROVNOMA_PAPKASI = Path("hujjatlar/sorovnoma")


def _musbat_son(matn: str) -> float:
    toza = (matn or "").replace(",", ".").replace(" ", "")
    try:
        qiymat = float(toza)
    except ValueError:
        raise ShaklXatosi("Raqam kiriting, masalan: 5000") from None
    if qiymat <= 0:
        raise ShaklXatosi("Raqam noldan katta bo'lishi kerak")
    return qiymat


# Savol tekshiruvi YAML da NOM bilan yoziladi (`tekshir: son`).
#
# Funksiyani YAML dan to'g'ridan-to'g'ri chaqirib bo'lmaydi va bu
# YAXSHI: ta'rif fayli faqat ma'lumot bo'lib qoladi, u orqali kod ishga
# tushmaydi. Noma'lum nom yozilsa — darhol xato, jimgina o'tib
# ketmaydi.
TEKSHIRUVLAR: dict[str, Callable[[str], Any]] = {
    "son": _musbat_son,
    "butun_son": butun_son,
    "bosh_bolmagan_matn": bosh_bolmagan_matn,
}


@dataclass(frozen=True)
class Bolim:
    """Bitta oprosniy list."""

    kalit: str
    nomi: str
    nomi_ru: str
    belgi: str
    fayl: str
    izoh: str
    savollar: tuple[Savol, ...]
    # Katalogdagi model nomi qaysi javoblardan yig'ilishi
    # («{model} {olcham}»). Bo'sh bo'lsa nom yig'ilmaydi — masalan
    # ventilyatorda mijoz modelni bilmaydi, u sarf va bosim beradi.
    nom_qolipi: str = ""

    def yorliq(self) -> str:
        return f"{self.belgi} {self.nomi}"


def _tanlovlar(
    xom: list[dict[str, Any]] | None,
    javoblar: dict[str, Any],
    shart_kalit: str | None,
) -> tuple[Tanlov, ...]:
    """Tanlovlar — ba'zilari oldingi javobga qarab YASHIRILADI.

    Masalan F5-F9 tozalash klassi FAQAT ФЯК filtrida bor. ФЯГ tanlagan
    mijozga uni ko'rsatish shunchaki chalkashlik emas: u tanlab qo'ysa,
    menejerga ishlab chiqarib BO'LMAYDIGAN buyurtma tushardi va buni
    faqat zavodda sezishardi.
    """
    natija = []
    for t in xom or []:
        kerak = t.get("shart_qiymat")
        if kerak is not None and shart_kalit:
            mos = kerak if isinstance(kerak, list) else [kerak]
            if javoblar.get(shart_kalit) not in mos:
                continue
        natija.append(
            Tanlov(
                qiymat=str(t["qiymat"]),
                yorliq=str(t.get("yorliq") or t["qiymat"]),
                izoh=str(t.get("izoh") or ""),
            )
        )
    return tuple(natija)


def _shart(xom: dict[str, Any] | None) -> Callable[[dict[str, Any]], bool] | None:
    if not xom:
        return None
    kalit = str(xom.get("kalit") or "")
    kutilgan = xom.get("qiymat")
    mos = kutilgan if isinstance(kutilgan, list) else [kutilgan]

    def tekshir(javoblar: dict[str, Any]) -> bool:
        return javoblar.get(kalit) in mos

    return tekshir


def _savol(xom: dict[str, Any], javoblar: dict[str, Any]) -> Savol:
    nomi = xom.get("tekshir")
    tekshir = TEKSHIRUVLAR.get(str(nomi)) if nomi else None
    if nomi and tekshir is None:
        raise ValueError(
            f"sorovnoma.yaml: noma'lum tekshiruv '{nomi}' "
            f"(mavjudlari: {', '.join(sorted(TEKSHIRUVLAR))})"
        )
    return Savol(
        kalit=str(xom["kalit"]),
        matn=str(xom["matn"]),
        asl=str(xom.get("asl") or ""),
        tanlovlar=_tanlovlar(xom.get("tanlovlar"), javoblar, xom.get("shart_kalit")),
        tekshir=tekshir,
        otkazsa_boladi=bool(xom.get("otkazsa_boladi")),
        izoh=str(xom.get("izoh") or ""),
        shart=_shart(xom.get("shart")),
    )


@lru_cache
def _xom() -> dict[str, Any]:
    yol = Path(sozlama().bilim_yoli) / "product" / "sorovnoma.yaml"
    if not yol.exists():
        return {"bolimlar": {}}
    return yaml.safe_load(yol.read_text(encoding="utf-8")) or {"bolimlar": {}}


def bolimlar() -> tuple[Bolim, ...]:
    """Barcha bo'limlar — YAML dagi TARTIBDA.

    Tartib ma'noli: eng ko'p so'raladigani tepada turadi va mijoz uni
    birinchi ko'radi.
    """
    natija = []
    for kalit, xom in (_xom().get("bolimlar") or {}).items():
        natija.append(
            Bolim(
                kalit=str(kalit),
                nomi=str(xom.get("nomi") or kalit),
                nomi_ru=str(xom.get("nomi_ru") or ""),
                belgi=str(xom.get("belgi") or "•"),
                fayl=str(xom.get("fayl") or ""),
                izoh=str(xom.get("izoh") or ""),
                savollar=tuple(_savol(s, {}) for s in (xom.get("savollar") or [])),
                nom_qolipi=str(xom.get("nom_qolipi") or ""),
            )
        )
    return tuple(natija)


def bolim(kalit: str) -> Bolim | None:
    for b in bolimlar():
        if b.kalit == kalit:
            return b
    return None


def fayl_yoli(b: Bolim) -> Path | None:
    """Oprosniy list faylining yo'li. Fayl yo'q bo'lsa `None`.

    Fayl YO'QLIGI xato emas: bo'lim savollari baribir ishlaydi, faqat
    "faylni yuborish" tugmasi ko'rsatilmaydi.
    """
    if not b.fayl:
        return None
    yol = SOROVNOMA_PAPKASI / b.fayl
    return yol if yol.exists() else None


@dataclass
class SorovnomaShakli:
    """To'ldirilayotgan so'rovnoma.

    `kp.shakl.Shakl` dan farqi: savollar ro'yxati BO'LIMGA bog'liq va
    tanlovlar oldingi javobga qarab qayta hisoblanadi.
    """

    bolim_kaliti: str
    javoblar: dict[str, Any] = field(default_factory=dict)

    def _bolim(self) -> Bolim | None:
        return bolim(self.bolim_kaliti)

    def _xom_savollar(self) -> list[dict[str, Any]]:
        xom = (_xom().get("bolimlar") or {}).get(self.bolim_kaliti) or {}
        return list(xom.get("savollar") or [])

    def _kerakli(self) -> list[Savol]:
        """Shu javoblarda beriladigan savollar.

        Har chaqiruvda QAYTA quriladi: tanlovlar oldingi javobga bog'liq
        (F5-F9 faqat ФЯК da) va javob o'zgarsa ro'yxat ham o'zgarishi
        kerak.
        """
        natija = []
        for xom in self._xom_savollar():
            savol = _savol(xom, self.javoblar)
            if savol.shart is None or savol.shart(self.javoblar):
                natija.append(savol)
        return natija

    def joriy(self) -> Savol | None:
        for savol in self._kerakli():
            if savol.kalit not in self.javoblar:
                return savol
        return None

    def tugadimi(self) -> bool:
        return self.joriy() is None

    def qadam(self) -> tuple[int, int]:
        """(nechanchi, jami).

        Shart hali hal bo'lmaganda UZUNROQ tarmoq uzunligi ko'rsatiladi.
        Aks holda hisob orqaga sakrardi: filtr bo'limi «1/5» dan
        boshlanib, ФЯК tanlangach «2/7» bo'lardi va mijozga savollar
        ko'payib ketgandek tuyulardi. Bu yo'nalishda xato qilamiz —
        kutilgandan kam savol yoqimli, ko'p savol yoqimsiz.
        """
        kerakli = self._kerakli()
        berilgan = sum(1 for s in kerakli if s.kalit in self.javoblar)
        jami = len(kerakli)
        for uzunlik in self._tarmoq_uzunliklari():
            jami = max(jami, uzunlik)
        return min(berilgan + 1, jami), jami

    def _tarmoq_uzunliklari(self) -> list[int]:
        """Hali tanlanmagan shartlar bo'yicha mumkin bo'lgan uzunliklar."""
        xom_savollar = self._xom_savollar()
        shart_kalitlari = {
            str((x.get("shart") or {}).get("kalit"))
            for x in xom_savollar
            if x.get("shart")
        } - {"None"}
        ochiq = [k for k in shart_kalitlari if k not in self.javoblar]
        if not ochiq:
            return []

        # Har shart kaliti uchun mumkin bo'lgan qiymatlarni sinab
        # ko'ramiz va eng uzun tarmoqni olamiz.
        uzunliklar = []
        for kalit in ochiq:
            for xom in xom_savollar:
                shart = xom.get("shart") or {}
                if str(shart.get("kalit")) != kalit:
                    continue
                qiymatlar = shart.get("qiymat")
                for q in (qiymatlar if isinstance(qiymatlar, list) else [qiymatlar]):
                    sinov = {**self.javoblar, kalit: q}
                    uzunliklar.append(sum(
                        1 for x in xom_savollar
                        if not x.get("shart")
                        or (_shart(x["shart"]) or (lambda _: True))(sinov)
                    ))
        return uzunliklar

    def belgi(self) -> str:
        joriy, jami = self.qadam()
        return f"{joriy}/{jami}"

    def javob_ber(self, matn: str) -> None:
        savol = self.joriy()
        if savol is None:
            raise ShaklXatosi("So'rovnoma allaqachon to'ldirilgan")
        if savol.tanlovlar:
            tanlov = next((t for t in savol.tanlovlar if t.qiymat == matn), None)
            if tanlov is None:
                raise ShaklXatosi("Tugmalardan birini tanlang")
            self.javoblar[savol.kalit] = tanlov.qiymat
            return
        self.javoblar[savol.kalit] = (
            savol.tekshir(matn) if savol.tekshir else matn.strip()
        )

    def otkaz(self) -> None:
        savol = self.joriy()
        if savol is None:
            raise ShaklXatosi("So'rovnoma allaqachon to'ldirilgan")
        if not savol.otkazsa_boladi:
            raise ShaklXatosi("Bu savolni o'tkazib bo'lmaydi")
        self.javoblar[savol.kalit] = ""

    def orqaga(self) -> bool:
        """Oxirgi javobni o'chiradi. Qaytadigan joy bo'lmasa `False`."""
        berilganlar = [s.kalit for s in self._kerakli() if s.kalit in self.javoblar]
        if not berilganlar:
            return False
        self.javoblar.pop(berilganlar[-1], None)
        return True

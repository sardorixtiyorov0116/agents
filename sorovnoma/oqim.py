"""So'rovnoma oqimi — MIJOZLAR botida.

`bot/kp_oqim.py` ga o'xshaydi, lekin auditoriyasi boshqa va shu farq
hamma joyda seziladi:

  - menejer atamalarni biladi, mijoz bilmaydi -> savol matni soddaroq,
    har texnik belgi yonida izoh turadi;
  - menejerdan to'liq javob talab qilinadi, mijozdan YO'Q -> deyarli
    har savolni o'tkazib yuborish mumkin, chunki yarim to'ldirilgan
    so'rovnoma ham to'ldirilmaganidan yaxshi;
  - oxirida KP emas, MENEJERGA XABAR chiqadi.
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from kp.shakl import ShaklXatosi

from .talab import SorovnomaShakli, bolim, bolimlar, fayl_yoli

log = logging.getLogger("sorovnoma")

TUGMA_OLDI = "sn:"
BOLIM_OLDI = "snb:"

ORQAGA = "__orqaga__"
OTKAZ = "__otkaz__"
FAYL = "__fayl__"
BEKOR = "__bekor__"

QATORDAGI_TUGMA = 2

# Telegram tugma yorlig'i chegarasi.
YORLIQ_UZUNLIGI = 32


# --- Bo'limlar menyusi --------------------------------------------------------


def bolimlar_tugmalari() -> InlineKeyboardMarkup:
    """Mijoz nima kerakligini TANLAYDI, yozib o'tirmaydi.

    Erkin matn ham ishlaydi, lekin ko'p mijoz nimadan boshlashni
    bilmaydi va umuman yozmaydi. Ro'yxat esa savol o'rniga tanlov
    beradi — bu ancha oson.
    """
    qatorlar = [
        [InlineKeyboardButton(b.yorliq()[:YORLIQ_UZUNLIGI],
                              callback_data=f"{BOLIM_OLDI}{b.kalit}")]
        for b in bolimlar()
    ]
    return InlineKeyboardMarkup(qatorlar)


def bolimlar_matni(savat_soni: int = 0) -> str:
    """Bo'limlar menyusi — QISQA.

    Ilgari bu yerda 12 ta bo'lim tavsifi bilan sanalardi va ostidan
    yana 12 ta tugma chiqardi: bir xil ro'yxat ikki marta, telefon
    ekranini to'ldirib. Nomlar tugmalarda allaqachon bor, tavsif esa
    bo'lim ichidagi birinchi savolda beriladi.
    """
    bolaklar = [
        "📋 *Qaysi uskuna kerak?*",
        "_Tanlang — bir necha savol beraman va menejerimizga tayyor "
        "so'rovnoma yuboraman._",
    ]
    # SAVAT ESLATMASI. Mijoz «yana qo'shish» bosib bu ro'yxatga
    # qaytadi — to'plangani shu yerda ko'rinib tursin, aks holda
    # unutilib ketardi.
    if savat_soni:
        bolaklar.append(
            f"🧺 So'rovingizda *{savat_soni} ta pozitsiya* bor — /savat")
    bolaklar.append("Yoki savolingizni shundoq yozing.")
    return "\n\n".join(bolaklar)


# --- Savol ko'rinishi ---------------------------------------------------------


def tugmalar(shakl: SorovnomaShakli) -> InlineKeyboardMarkup | None:
    savol = shakl.joriy()
    if savol is None:
        return None

    qatorlar: list[list[InlineKeyboardButton]] = []
    joriy: list[InlineKeyboardButton] = []
    for tanlov in savol.tanlovlar:
        joriy.append(InlineKeyboardButton(
            tanlov.yorliq[:YORLIQ_UZUNLIGI],
            callback_data=f"{TUGMA_OLDI}{savol.kalit}:{tanlov.qiymat}",
        ))
        if len(joriy) == QATORDAGI_TUGMA:
            qatorlar.append(joriy)
            joriy = []
    if joriy:
        qatorlar.append(joriy)

    boshqaruv: list[InlineKeyboardButton] = []
    if shakl.javoblar:
        boshqaruv.append(InlineKeyboardButton(
            "⬅️ Orqaga", callback_data=f"{TUGMA_OLDI}{savol.kalit}:{ORQAGA}"))
    if savol.otkazsa_boladi:
        boshqaruv.append(InlineKeyboardButton(
            "⏭ Bilmayman", callback_data=f"{TUGMA_OLDI}{savol.kalit}:{OTKAZ}"))
    if boshqaruv:
        qatorlar.append(boshqaruv)

    # FAYL — loyihachi yoki muhandis mijoz oprosniy listni O'Z ishi
    # uchun so'rashi mumkin (proyekt papkasiga, subpodryadchiga).
    # Savollar bilan to'ldirish undan ko'ra oson, lekin tanlov mijozda
    # qolsin.
    b = bolim(shakl.bolim_kaliti)
    if b is not None and fayl_yoli(b) is not None:
        qatorlar.append([InlineKeyboardButton(
            "📎 Oprosniy list faylini yuborish",
            callback_data=f"{TUGMA_OLDI}{savol.kalit}:{FAYL}")])

    qatorlar.append([InlineKeyboardButton(
        "✖️ Bekor qilish", callback_data=f"{TUGMA_OLDI}{savol.kalit}:{BEKOR}")])
    return InlineKeyboardMarkup(qatorlar)


def savol_matni(shakl: SorovnomaShakli) -> str:
    savol = shakl.joriy()
    if savol is None:
        return ""
    b = bolim(shakl.bolim_kaliti)
    sarlavha = f"{b.belgi} {b.nomi}" if b else ""

    bolaklar = [f"*{sarlavha}* · {shakl.belgi()}", savol.matn]
    # Bosma listdagi asl nomi — loyihachi solishtira olsin.
    if savol.asl:
        bolaklar.append(f"_({savol.asl})_")
    if savol.izoh:
        bolaklar.append(f"_{savol.izoh}_")
    # Variantlar izohi — mijoz atamani bilmasligi mumkin, tugmada esa
    # joy yo'q (32 belgi).
    if savol.tanlovlar and any(t.izoh for t in savol.tanlovlar):
        bolaklar.append("\n".join(
            f"• {t.yorliq} — {t.izoh}" for t in savol.tanlovlar if t.izoh))
    if not savol.tanlovlar:
        bolaklar.append("_Javobni yozib yuboring._")
    return "\n\n".join(bolaklar)


# --- Yakuniy ro'yxat ----------------------------------------------------------


def _son_matni(qiymat: Any) -> str:
    """Raqamni ortiqcha kasrsiz ko'rsatadi.

    `son` tekshiruvi `float` qaytaradi, shuning uchun cho'ntak
    uzunligi «500.0» bo'lib chiqardi. Mijoz «500» deb yozgan edi va
    o'zi yozgan raqamni boshqacha ko'rish ishonchni yo'qotadi.
    """
    if isinstance(qiymat, float) and qiymat.is_integer():
        return str(int(qiymat))
    return str(qiymat)


def _yorliq(shakl: SorovnomaShakli, kalit: str, qiymat: Any) -> tuple[str, str]:
    """(savol matni, javob yorlig'i) — menejer o'qiydigan ko'rinishda."""
    for savol in shakl._kerakli():
        if savol.kalit != kalit:
            continue
        yorliqlar = {t.qiymat: t.yorliq for t in savol.tanlovlar}
        return savol.matn, yorliqlar.get(str(qiymat), _son_matni(qiymat))
    return kalit, _son_matni(qiymat)


def natija_matni(shakl: SorovnomaShakli) -> str:
    """Mijozga ko'rsatiladigan xulosa."""
    b = bolim(shakl.bolim_kaliti)
    qatorlar = [f"✅ *{b.nomi if b else shakl.bolim_kaliti}* — so'rovnoma to'ldirildi", ""]
    for kalit, qiymat in shakl.javoblar.items():
        savol, javob = _yorliq(shakl, kalit, qiymat)
        # O'tkazib yuborilgan savol — mijoz bilmasligini AYTAMIZ,
        # jimgina tashlab ketmaymiz: menejer nimani so'rashini bilsin.
        qatorlar.append(f"• {savol}\n  → {javob if javob else '_bilmayman_'}")
    return "\n".join(qatorlar)


def menejer_matni(shakl: SorovnomaShakli, ism: str = "",
                  aloqa: str = "", tg_id: Any = "") -> str:
    """Ichki botga ketadigan xabar."""
    b = bolim(shakl.bolim_kaliti)
    qatorlar = [
        f"📋 *Yangi so'rovnoma* — {b.nomi if b else shakl.bolim_kaliti}",
        "",
    ]
    if ism:
        qatorlar.append(f"👤 {ism}")
    if aloqa:
        qatorlar.append(f"📞 {aloqa}")
    if not aloqa:
        # Aloqa YO'QLIGI eng muhim ma'lumot: menejer bog'lana olmaydi
        # va buni darhol bilishi kerak.
        qatorlar.append("⚠️ Aloqa qoldirilmagan — mijoz botda javob kutyapti")
    qatorlar.append(f"🆔 `{tg_id}`")
    qatorlar.append("")
    for kalit, qiymat in shakl.javoblar.items():
        savol, javob = _yorliq(shakl, kalit, qiymat)
        qatorlar.append(f"*{savol}*\n{javob if javob else '— bilmayman'}")
    return "\n".join(qatorlar)


# --- Savat --------------------------------------------------------------------
#
# Mijoz bitta uskuna bilan cheklanmaydi. Bitta obyektga ventilyator ham,
# panjara ham, filtr ham kerak bo'ladi — hatto bitta bo'limdan BIR NECHA
# xil o'lchamda (zalga 500x300, koridorga 200x200).
#
# Har pozitsiya alohida yuborilsa menejer bitta obyektning bo'laklarini
# bog'lay olmasdi va bir mijozdan uchta uzuq so'rov ko'rardi.

SAVAT_QOSH = "__yana__"
SAVAT_YUBOR = "__yubor__"

# Bitta so'rovda nechta pozitsiya. Chegara kerak: xato bosish yoki
# hazil tufayli yuzlab pozitsiya to'planib qolmasin.
MAKS_POZITSIYA = 20


def savat_tugmalari(savat: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    qatorlar = [[InlineKeyboardButton(
        "➕ Yana uskuna qo'shish",
        callback_data=f"{TUGMA_OLDI}savat:{SAVAT_QOSH}")]]
    if savat:
        qatorlar.append([InlineKeyboardButton(
            f"✅ Tayyor — yuborish ({len(savat)} ta)",
            callback_data=f"{TUGMA_OLDI}savat:{SAVAT_YUBOR}")])
    return InlineKeyboardMarkup(qatorlar)


def savat_matni(savat: list[dict[str, Any]]) -> str:
    qatorlar = [f"🧺 *So'rovingiz — {len(savat)} ta pozitsiya*", ""]
    for raqam, pozitsiya in enumerate(savat, 1):
        b = bolim(pozitsiya.get("bolim", ""))
        nomi = b.nomi if b else pozitsiya.get("bolim", "")
        belgi = b.belgi if b else "•"
        qatorlar.append(f"{raqam}. {belgi} *{nomi}* — {_qisqa(pozitsiya)}")
    qatorlar += ["", "Yana uskuna kerakmi?",
                 "_Bu ro'yxatga istalgan payt qaytish: /savat_"]
    return "\n".join(qatorlar)


def _qisqa(pozitsiya: dict[str, Any]) -> str:
    """Savatda bitta qator — eng muhim ikki-uch qiymat.

    To'liq javoblar menejerga ketadi; mijozga esa pozitsiyani TANIB
    olish uchun yetarli qism ko'rsatiladi.
    """
    javoblar = pozitsiya.get("javoblar") or {}
    bolaklar = [str(q) for q in javoblar.values() if str(q).strip()][:3]
    soni = javoblar.get("soni")
    qisqa = ", ".join(bolaklar) if bolaklar else "—"
    if soni and str(soni) not in qisqa:
        qisqa += f" · {_son_matni(soni)} dona"
    return qisqa


# --- Holat --------------------------------------------------------------------


async def savatni_ol(baza, tg_id: Any) -> list[dict[str, Any]]:
    holat = await baza.sorovnoma_holati(tg_id)
    return list(holat.get("savat") or []) if holat else []


async def boshla(baza, tg_id: Any, bolim_kaliti: str,
                 savat: list[dict[str, Any]] | None = None) -> SorovnomaShakli | None:
    """Bo'lim tanlandi — yangi pozitsiya boshlanadi.

    `savat` SAQLANADI: mijoz ikkinchi uskunani tanlaganda birinchisi
    yo'qolib ketmasligi kerak.
    """
    if bolim(bolim_kaliti) is None:
        return None
    shakl = SorovnomaShakli(bolim_kaliti=bolim_kaliti)
    if savat is None:
        savat = await savatni_ol(baza, tg_id)
    await baza.sorovnoma_holati_yoz(tg_id, bolim_kaliti, shakl.javoblar, savat)
    return shakl


async def joriy_shakl(baza, tg_id: Any) -> SorovnomaShakli | None:
    """Ochiq so'rovnoma. Yo'q bo'lsa `None` — savat SAQLANADI.

    Bo'lim BO'SH bo'lishi normal holat: pozitsiya savatga qo'shilgan,
    mijoz esa hali keyingi bo'limni tanlamagan. Shu payt savat bor,
    lekin to'ldiriladigan so'rovnoma yo'q.
    """
    holat = await baza.sorovnoma_holati(tg_id)
    if holat is None:
        return None
    kalit = str(holat.get("bolim") or "")
    if not kalit:
        return None                      # savat bor, so'rovnoma yo'q
    if bolim(kalit) is None:
        # Bo'lim YAML dan olib tashlangan — eski shakl ishlamaydi.
        # Savat ham ketadi: uning pozitsiyalari o'sha bo'limdan.
        await baza.sorovnoma_holati_ochir(tg_id)
        return None
    return SorovnomaShakli(bolim_kaliti=kalit, javoblar=holat["javoblar"])


async def javobni_qabul_qil(baza, tg_id: Any, shakl: SorovnomaShakli,
                            qiymat: str) -> str | None:
    """Javobni yozadi. Xato bo'lsa — sabab matni, aks holda `None`."""
    try:
        if qiymat == OTKAZ:
            shakl.otkaz()
        else:
            shakl.javob_ber(qiymat)
    except ShaklXatosi as xato:
        return str(xato)
    # Savat berilmaydi -> tegilmaydi (`app/baza.py`).
    await baza.sorovnoma_holati_yoz(tg_id, shakl.bolim_kaliti, shakl.javoblar)
    return None


async def savatga_qosh(baza, tg_id: Any,
                       shakl: SorovnomaShakli) -> list[dict[str, Any]]:
    """Tugatilgan pozitsiyani savatga qo'shadi va uni qaytaradi.

    Bo'lim BO'SHATILADI — bu nozik joy.

    JONLI XATO (2026-08-28 da topildi): ilgari bo'lim o'sha-o'sha
    qolardi va savat ko'rsatilgach ham SHAKL OCHIQ turardi. Mijoz
    tugma o'rniga biror narsa yozsa (masalan "rahmat"), u o'sha
    bo'limning YANGI nusxasiga birinchi javob bo'lib tushardi va
    jimgina takroriy pozitsiya boshlanardi. Sinovda shu tarzda 20 ta
    (chegara) pozitsiya to'planib qoldi.
    """
    savat = await savatni_ol(baza, tg_id)
    if len(savat) < MAKS_POZITSIYA:
        savat.append({"bolim": shakl.bolim_kaliti, "javoblar": dict(shakl.javoblar)})
    await baza.sorovnoma_holati_yoz(tg_id, "", {}, savat)
    return savat


async def yakunla(baza, tg_id: Any, savat: list[dict[str, Any]],
                  ism: str = "", aloqa: str = "") -> list[int]:
    """Savatdagi HAMMA pozitsiyani saqlaydi va holatni tozalaydi.

    Har pozitsiya alohida yozuv bo'lib tushadi — menejer ularni
    bittalab ko'radi va bittasini bajarib, boshqasini kutishi mumkin.
    Bog'lovchi ip — `tg_id` va vaqt.
    """
    idlar = []
    for pozitsiya in savat:
        idlar.append(await baza.sorovnoma_yoz({
            "tg_id": tg_id,
            "ism": ism,
            "aloqa": aloqa,
            "bolim": pozitsiya.get("bolim", ""),
            "javoblar": pozitsiya.get("javoblar") or {},
        }))
    await baza.sorovnoma_holati_ochir(tg_id)
    return idlar


def bolaklarga_boling(matn: str, chek: int) -> list[str]:
    """Uzun xabarni pozitsiya chegarasidan bo'ladi.

    JONLI XATO (2026-08-28): 12 pozitsiyali savat menejerga
    yuborilganda xabar 3000 belgida QIRQILDI — oxirgi ikki pozitsiya
    umuman ko'rinmadi va menejer buni bilmasdi ham.

    Oddiy qirqish o'rniga `━━` chizig'i bo'yicha bo'linadi: har bo'lak
    butun pozitsiyalardan iborat bo'ladi va o'rtasidan uzilmaydi.
    """
    if len(matn) <= chek:
        return [matn]

    bolaklar: list[str] = []
    joriy = ""
    for qism in matn.split("\n━━ "):
        qism = qism if not bolaklar and not joriy else "━━ " + qism
        if joriy and len(joriy) + len(qism) + 1 > chek:
            bolaklar.append(joriy)
            joriy = qism
        else:
            joriy = f"{joriy}\n{qism}" if joriy else qism
    if joriy:
        bolaklar.append(joriy)

    # Bitta pozitsiyaning o'zi chekdan uzun bo'lsa — noiloj qirqamiz,
    # lekin BUNI AYTAMIZ.
    natija = []
    for b in bolaklar:
        while len(b) > chek:
            natija.append(b[:chek - 20] + "\n… (davomi hujjatda)")
            b = b[chek - 20:]
        natija.append(b)
    return [b for b in natija if b.strip()]


def savat_menejer_matni(savat: list[dict[str, Any]], ism: str = "",
                        aloqa: str = "", tg_id: Any = "") -> str:
    """Menejerga ketadigan YAGONA xabar — hamma pozitsiya bilan."""
    qatorlar = [f"📋 *Yangi so'rov* — {len(savat)} ta pozitsiya", ""]
    if ism:
        qatorlar.append(f"👤 {ism}")
    if aloqa:
        qatorlar.append(f"📞 {aloqa}")
    else:
        qatorlar.append("⚠️ Aloqa yo'q — mijoz botda javob kutyapti")
    qatorlar.append(f"🆔 `{tg_id}`")

    for raqam, pozitsiya in enumerate(savat, 1):
        b = bolim(pozitsiya.get("bolim", ""))
        shakl = SorovnomaShakli(bolim_kaliti=pozitsiya.get("bolim", ""),
                                javoblar=pozitsiya.get("javoblar") or {})
        qatorlar += ["", f"━━ {raqam}. {b.belgi if b else '•'} "
                         f"*{b.nomi if b else pozitsiya.get('bolim', '')}* ━━"]
        for kalit, qiymat in shakl.javoblar.items():
            savol, javob = _yorliq(shakl, kalit, qiymat)
            qatorlar.append(f"*{savol}* — {javob if javob else 'bilmayman'}")
    qatorlar += ["", "To'liq ro'yxat: /sorovnomalar"]
    return "\n".join(qatorlar)

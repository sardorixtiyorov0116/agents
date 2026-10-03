"""`/kp` — boshqariladigan savol-javob oqimi.

NEGA ALOHIDA MODUL: `bot/asosiy.py` allaqachon katta. Bu yerda faqat
Telegram qismi — savolni chizish, tugma bosilishi, faylni yuborish.
Butun mantiq `kp/shakl.py` va `kp/shakldan.py` da va u Telegramsiz
test qilinadi.

NEGA ROUTER CHAQIRILMAYDI: `/kp` bosilganda vazifa ALLAQACHON ma'lum.
Router — «menejer nima demoqchi?» degan savolga javob, bu yerda esa
savol yo'q. Shu sababli butun bir LLM chaqiruvi tushib qoladi
(o'lchandi: erkin matnli yo'l 80 s, shakl orqali 0,04 s).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import sozlama
from app.kurs import joriy as kurs_joriy
from integrations import ClimaventKlient
from kp import hujjatlarni_yasa
from kp.shakl import MARKAZIY_YOQ, Shakl, ShaklXatosi
from kp.shakldan import Natija, yig

log = logging.getLogger(__name__)

# Tugmaning callback ma'lumoti: `kp:<kalit>:<qiymat>`.
# Telegram cheklovi — 64 bayt, shuning uchun qiymatlar qisqa bo'lishi kerak.
TUGMA_OLDI = "kp:"
OTKAZ = "__otkaz__"
ORQAGA = "__orqaga__"

# Aniqlik savolida ko'rsatiladigan ogohlantirishlar soni.
# Hammasi chiqarilsa savol ko'milib ketardi va menejer
# tugmani topmasdi.
ANIQLIK_OGOH_SONI = 4

# KP xulosasidagi ogohlantirishlar soni. Excel TZ dan qatorlar ko'p bo'ladi
# va har biri ogohlantirish bersa, xulosa o'qib bo'lmas holga keladi.
OGOH_XABARDA = 15

# Telegram bitta xabar chegarasi 4096 — Markdown belgilari uchun zaxira.
XABAR_CHEGARASI = 3800


def _bolaklar(qatorlar: list[str]) -> list[str]:
    """Qatorlarni Telegram chegarasidan oshmaydigan xabarlarga bo'ladi.

    Qator o'rtasidan BO'LINMAYDI — Markdown (`*…*`) qator ichida yopiladi,
    shuning uchun har bo'lak o'zicha to'g'ri formatlangan bo'ladi.
    """
    natija: list[str] = []
    joriy: list[str] = []
    uzunlik = 0
    for qator in qatorlar:
        if joriy and uzunlik + len(qator) + 1 > XABAR_CHEGARASI:
            natija.append("\n".join(joriy))
            joriy, uzunlik = [], 0
        joriy.append(qator)
        uzunlik += len(qator) + 1
    if joriy:
        natija.append("\n".join(joriy))
    return natija

# `Shakl` faqat `savollar()` ro'yxatidagi kalitlarni ko'radi (`Shakl.qadam`,
# `.tugadimi` shundan hisoblanadi), shuning uchun bu KO'SHIMCHA kalitni
# `javoblar` ichida saqlash xavfsiz — shaklning o'z mantig'iga ta'sir
# qilmaydi. HAQIQIY XATO TUFAYLI qo'shildi: aniqlashtiruv savoli
# javobsiz qolganda keyingi xabar "Shakl allaqachon to'ldirilgan" deb
# rad etilardi — menejer KP ni yakunlay olmasdi.
KUTILAYOTGAN_ANIQLIK = "_kutilayotgan_aniqlik_indeksi"

# Bir qatorga shuncha tugma. Xona turlari 14 ta — ustunga tizilsa uzun
# ro'yxat chiqadi, ikkitadan bo'lsa ekranga sig'adi.
QATORDAGI_TUGMA = 2


def _mijoz() -> ClimaventKlient:
    """Katalog keshi modul darajasida — har chaqiruvda qayta yuklanmaydi."""
    return ClimaventKlient()


# --- savolni chizish ----------------------------------------------------------


def _tugmalar(shakl: Shakl) -> InlineKeyboardMarkup | None:
    savol = shakl.joriy()
    if savol is None:
        return None
    # Ko'p marta tanlanadigan savolda allaqachon tanlanganlar belgilanadi.
    tanlanganlar = set(shakl.javoblar.get("uskunalar") or []) \
        if savol.kalit == "uskuna" else set()

    qatorlar: list[list[InlineKeyboardButton]] = []
    joriy: list[InlineKeyboardButton] = []
    for tanlov in savol.tanlovlar:
        yorliq = tanlov.yorliq
        # Ko'p tanlanadigan savolda izoh («+200 Pa») TUGMAGA ko'chadi:
        # ostidagi ro'yxat ekranni egallamasin.
        if savol.kalit == "uskuna" and tanlov.izoh.startswith("+"):
            yorliq = f"{yorliq} {tanlov.izoh}"
        if tanlov.qiymat in tanlanganlar:
            yorliq = f"✅ {yorliq}"
        joriy.append(InlineKeyboardButton(
            yorliq[:32], callback_data=f"{TUGMA_OLDI}{savol.kalit}:{tanlov.qiymat}"
        ))
        if len(joriy) == QATORDAGI_TUGMA:
            qatorlar.append(joriy)
            joriy = []
    if joriy:
        qatorlar.append(joriy)
    oxirgi_qator: list[InlineKeyboardButton] = []
    # ORQAGA — birinchi savoldan tashqari hamma joyda. Menejer xato
    # tugma bossa, butun KP ni `/bekor` qilib boshidan boshlashi shart
    # emas.
    if shakl.javoblar:
        oxirgi_qator.append(InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data=f"{TUGMA_OLDI}{savol.kalit}:{ORQAGA}",
        ))
    if savol.otkazsa_boladi:
        oxirgi_qator.append(InlineKeyboardButton(
            "⏭ O'tkazib yuborish",
            callback_data=f"{TUGMA_OLDI}{savol.kalit}:{OTKAZ}",
        ))
    if oxirgi_qator:
        qatorlar.append(oxirgi_qator)
    return InlineKeyboardMarkup(qatorlar) if qatorlar else None


def _savol_matni(shakl: Shakl) -> str:
    savol = shakl.joriy()
    if savol is None:
        return ""
    bolaklar = [f"*{shakl.belgi()}* · {savol.matn}"]
    # Tanlanganlar savol matnida ham ko'rinib tursin — tugmalar
    # ekranga sig'masa ham menejer nima tanlaganini biladi.
    if savol.kalit == "uskuna":
        tanlangan = shakl.javoblar.get("uskunalar") or []
        if tanlangan:
            yorliqlar = {t.qiymat: t.yorliq for t in savol.tanlovlar}
            bolaklar.append(
                "*Tanlandi:* " + ", ".join(yorliqlar.get(k, k) for k in tanlangan)
            )
    if savol.izoh:
        bolaklar.append(f"_{savol.izoh}_")
    # Uskuna savolida izohlar («+200 Pa») TUGMALARDA turadi —
    # ostida yana ro'yxat chiqarilsa xabar ikki barobar uzayadi.
    if (savol.kalit != "uskuna"
            and savol.tanlovlar and any(t.izoh for t in savol.tanlovlar)):
        bolaklar.append("\n".join(
            f"• {t.yorliq} — {t.izoh}" for t in savol.tanlovlar if t.izoh
        ))
    return "\n\n".join(bolaklar)


async def _savolni_yubor(xabar, shakl: Shakl) -> None:
    await xabar.reply_text(
        _savol_matni(shakl), reply_markup=_tugmalar(shakl), parse_mode="Markdown"
    )


# --- oqim ---------------------------------------------------------------------


async def boshla(baza, xabar, tg_id: int) -> None:
    """`/kp` — yangi shakl. Eskisi bo'lsa tashlab yuboriladi."""
    shakl = Shakl()
    await baza.kp_shakli_yoz(tg_id, shakl.javoblar)
    # TZ HAQIDA SHU YERDA AYTAMIZ.
    #
    # Menejer fayl tashlash mumkinligini bilmasa, bu imkoniyat umuman
    # ishlatilmaydi. Va aytadigan payt aynan SHU: keyinroq tashlansa,
    # qo'lda berilgan javoblar TZ nikidan ustun turadi va fayldan
    # olinadigan foyda kamayadi.
    await xabar.reply_text(
        "🧾 *Yangi KP*\n\n"
        "📄 *Mijozda texnik topshiriq bormi?* Faylni shu yerga tashlang — "
        "savollarni o'zim to'ldiraman.\n"
        "_Word, PDF, Excel. Skanerlangan (rasm) fayl o'qilmaydi._\n\n"
        "Bo'lmasa — savollarga javob bering. Ko'pini o'tkazib yuborsangiz "
        "ham bo'ladi.\nTo'xtatish uchun: /bekor",
        parse_mode="Markdown",
    )
    await _savolni_yubor(xabar, shakl)


async def faolmi(baza, tg_id: int) -> bool:
    return await baza.kp_shakli(tg_id) is not None


async def hujjat(baza, xabar, tg_id: int, fayl, fayl_nomi: str) -> bool:
    """Menejer TZ faylini yubordi — undan shakl javoblari TAKLIF qilinadi.

    `True` — shakl bu faylni o'zi ishlatdi.

    MUHIM: TZ dan olingan qiymat shaklga JIMGINA yozilmaydi. Avval
    menejerga "nima topildi" ro'yxati ko'rsatiladi, u tasdiqlagandan
    keyingina javoblarga tushadi. Sabab: TZ hujjatlari har xil yoziladi
    va model xato o'qishi mumkin — bu esa KP ga noto'g'ri raqam bo'lib
    tushardi.
    """
    if not await faolmi(baza, tg_id):
        return False

    from kp.tz import TzXatosi, matn_ol

    papka = Path(sozlama().kp_papkasi) / "tz"
    papka.mkdir(parents=True, exist_ok=True)
    yol = papka / f"{tg_id}_{Path(fayl_nomi).name}"
    try:
        await fayl.download_to_drive(str(yol))
    except Exception as xato:                       # noqa: BLE001
        log.exception("TZ fayli yuklab olinmadi")
        await xabar.reply_text(f"⚠️ Faylni olib bo'lmadi: {xato}")
        return True

    await xabar.reply_text("📄 TZ o'qilmoqda…")

    # EXCEL JADVAL — MODELSIZ. Spetsifikatsiya / ro'yxat / zayavka miqdori
    # bilan o'qiladi va har qator Climavent nomiga aylantiriladi
    # (`kp/tz_qoralama.py`). Ilgari Excel ham matn bo'lib modelga ketardi:
    # 20 ta nom, hammasiga miqdor 1, raqib nomlari o'zgarishsiz.
    # DWG CHIZMA — qoralama YASALMAYDI (yozuvlar soni dona emas). Menejerga
    # chizmada qanday uskuna borligi ko'rsatiladi (`kp/dwg.py`).
    if yol.suffix.lower() == ".dwg":
        await _chizmadan(xabar, yol)
        return True

    # PDF bo'lsa — konditsioner so'rovnoma varaqasi (ОЛ) bo'lishi mumkin.
    if yol.suffix.lower() in (".xlsx", ".pdf"):
        import asyncio

        from kp.tz_qoralama import fayldan_taklif

        try:
            taklif = await asyncio.to_thread(fayldan_taklif, yol)
        except Exception:                           # noqa: BLE001
            log.warning("Excel TZ jadval sifatida o'qilmadi", exc_info=True)
            taklif = None
        if taklif is not None:
            await _taklifni_qolla(baza, xabar, tg_id, taklif)
            return True

    # RASM yoki SKAN PDF — model faqat jadvalni KO'CHIRADI (`kp/tz_rasm.py`),
    # nomga aylantirish yana kodda. Ilgari skan PDF «matn topilmadi» bilan
    # rad etilardi, rasm esa umuman qabul qilinmasdi.
    import asyncio

    from kp.tz_rasm import RASM_KENGAYTMALARI, rasmlar

    try:
        skanmi = yol.suffix.lower() in RASM_KENGAYTMALARI or (
            yol.suffix.lower() == ".pdf" and bool(await asyncio.to_thread(rasmlar, yol)))
    except Exception:                               # noqa: BLE001
        log.warning("rasm tekshirilmadi", exc_info=True)
        skanmi = False
    if skanmi:
        await _rasmdan(baza, xabar, tg_id, yol)
        return True

    try:
        matn = matn_ol(yol)
    except TzXatosi as xato:
        await xabar.reply_text(f"⚠️ {xato}")
        return True

    await _tzni_qolla(baza, xabar, tg_id, matn)
    return True


async def _tzni_qolla(baza, xabar, tg_id: int, tz_matni: str) -> None:
    """TZ matnidan parametrlarni ajratib, shaklga TAKLIF qiladi."""
    from hisob import normalar
    from kp.tz import shaklga_aylantir

    try:
        natija = await _tz_ajrat(tz_matni, sorted(normalar()))
    except Exception as xato:                       # noqa: BLE001
        # Xom xato matni menejerga hech narsa aytmaydi. `llm_xato_matni`
        # uni tushunarli jumlaga aylantiradi (kvota tugashi, kalit
        # yaroqsizligi va h.k.).
        from app.llm import llm_xato_matni

        log.exception("TZ tahlil qilinmadi")
        await xabar.reply_text(
            "⚠️ TZ ni tahlil qilib bo'lmadi.\n"
            + llm_xato_matni(xato)
            + "\n\nSavollarga qo'lda javob bering — KP baribir chiqadi."
        )
        return

    taklif = shaklga_aylantir(natija, set(normalar()))
    await _taklifni_qolla(baza, xabar, tg_id, taklif)


async def _taklifni_qolla(baza, xabar, tg_id: int, taklif) -> None:
    """TZ taklifini menejerga ko'rsatadi va shaklga yozadi.

    Ikki manbadan keladi: modeldan (`kp/tz.py`, matnli TZ) va Excel
    jadvaldan (`kp/tz_qoralama.py`). Qoida bir xil: qo'lda berilgan
    javob ustidan yozilmaydi va nima topilgani ochiq aytiladi.
    """
    if not taklif.bormi:
        await xabar.reply_text(
            "⚠️ TZ dan KP uchun yetarli ma'lumot topilmadi. "
            "Savollarga qo'lda javob bering."
            + ("\n\n" + "\n".join(f"• {o}" for o in taklif.ogohlantirishlar)
               if taklif.ogohlantirishlar else "")
        )
        return

    saqlangan = await baza.kp_shakli(tg_id)
    javoblar = dict(saqlangan["javoblar"]) if saqlangan else {}
    # TZ BIR NECHTA FAYL bo'lishi mumkin: zayavka + so'rovnoma varaqasi (ОЛ),
    # qavatlar bo'yicha spetsifikatsiyalar. Ikkala tomon ham mahsulot
    # ro'yxati bo'lsa — ro'yxat QO'SHILADI. Aks holda ikkinchi fayl «allaqachon
    # javob berilgan» deb jimgina tashlab yuborilardi.
    taklif_javoblari = dict(taklif.javoblar)
    if (javoblar.get("yol") == "model" == taklif_javoblari.get("yol")
            and javoblar.get("mahsulotlar") and taklif_javoblari.get("mahsulotlar")):
        qoshilgan = taklif_javoblari.pop("mahsulotlar")
        javoblar["mahsulotlar"] = list(javoblar["mahsulotlar"]) + list(qoshilgan)
        taklif_javoblari.pop("yol")
        taklif.topilganlar.append(
            f"Oldingi ro'yxatga {len(qoshilgan)} qator QO'SHILDI — "
            f"jami {len(javoblar['mahsulotlar'])}")
    # Menejer ALLAQACHON javob bergan savol ustidan yozilmaydi.
    yangilar = {k: v for k, v in taklif_javoblari.items() if k not in javoblar}
    # Nima TUSHIB QOLGANINI aytamiz. Fayl kechroq tashlansa, qo'lda
    # berilgan javoblar ustun turadi va menejer TZ dagi qiymat
    # ishlatilmaganini bilmay qoladi.
    otkazilgan = [k for k in taklif_javoblari if k in javoblar]
    javoblar.update(yangilar)
    await baza.kp_shakli_yoz(tg_id, javoblar)

    qatorlar = ["📄 *TZ dan topildi:*", ""]
    qatorlar += [f"✅ {t}" for t in taklif.topilganlar]
    if otkazilgan:
        nomlar = {
            "mijoz": "mijoz nomi", "inn": "STIR", "obyekt": "obyekt",
            "yol": "yo'l", "xonalar": "xonalar", "olcham": "o'lcham",
            "xona_turi": "xona turi", "odamlar": "odamlar soni",
            "mahsulotlar": "mahsulotlar",
        }
        qatorlar += ["", "ℹ️ TZ da bor edi, lekin siz allaqachon javob "
                     "berganingiz uchun OLINMADI: "
                     + ", ".join(nomlar.get(k, k) for k in otkazilgan)]
    if taklif.ogohlantirishlar:
        qatorlar += [""] + [f"⚠️ {o}" for o in taklif.ogohlantirishlar]
    qatorlar += ["", "_Noto'g'ri bo'lsa /bekor bosib qaytadan boshlang._"]
    await xabar.reply_text("\n".join(qatorlar), parse_mode="Markdown")

    await _keyingisi(baza, xabar, tg_id, Shakl(javoblar=javoblar))


async def _chizmadan(xabar, yol: Path) -> None:
    """DWG: chizmadagi uskuna turlari ro'yxati. Shaklga hech narsa yozilmaydi."""
    import asyncio

    from kp.dwg import DwgXatosi, dwg_yozuvlari, xulosa

    await xabar.reply_text("📐 Chizma o'qilmoqda (bir necha soniya)…")
    try:
        x = await asyncio.to_thread(lambda: xulosa(dwg_yozuvlari(yol)))
    except DwgXatosi as xato:
        await xabar.reply_text(f"⚠️ {xato}")
        return
    except Exception:                               # noqa: BLE001
        log.exception("DWG o'qilmadi")
        await xabar.reply_text("⚠️ Chizmani o'qib bo'lmadi — PDF qilib yuboring.")
        return
    satrlar = x.satrlar(eng_kam=2)
    if not satrlar:
        await xabar.reply_text(
            "📐 Chizmada ventilyatsiya/konditsioner uskunasi belgilari topilmadi.")
        return
    # Markdownsiz: chizma yozuvlarida «*» bor («КПД-4-01-600х500-2*ф»).
    await xabar.reply_text(
        "📐 Chizmada topilgan uskunalar — YOZUVLAR SONI, dona emas:\n\n"
        + "\n".join(f"• {s}" for s in satrlar[:20])
        + "\n\nKP qoralamasi chizmadan YASALMAYDI: bitta uskuna chizmada bir necha "
          "marta yoziladi. Spetsifikatsiyani Excel, PDF yoki rasm qilib yuboring. "
          "Tayyor KP ni chizma bilan solishtirish — /tekshir.")


async def _rasmdan(baza, xabar, tg_id: int, yol: Path) -> None:
    """Rasm/skan TZ: model jadvalni ko'chiradi, kod qoralama yasaydi."""
    from kp.tz_qoralama import qatorlardan_taklif
    from kp.tz_rasm import RasmXatosi

    await xabar.reply_text("🖼 Rasmdan jadval o'qilmoqda…")
    try:
        qatorlar, ogohlar = await _rasm_ajrat(yol)
    except RasmXatosi as xato:
        await xabar.reply_text(f"⚠️ {xato}")
        return
    except Exception as xato:                       # noqa: BLE001
        from app.llm import llm_xato_matni

        log.exception("rasmdan TZ o'qilmadi")
        await xabar.reply_text(
            "⚠️ Rasmdan jadvalni o'qib bo'lmadi.\n" + llm_xato_matni(xato)
            + "\n\nRo'yxatni matn qilib yozing yoki Excel yuboring.")
        return
    taklif = qatorlardan_taklif(qatorlar, ogohlar, "Rasm") if qatorlar else None
    if taklif is None:
        await xabar.reply_text(
            "⚠️ Rasmda ventilyatsiya mahsulotlari jadvali topilmadi."
            + ("\n\n" + "\n".join(f"• {o}" for o in ogohlar) if ogohlar else ""))
        return
    await _taklifni_qolla(baza, xabar, tg_id, taklif)


async def _rasm_ajrat(yol: Path):
    """Rasm modeli (faqat Gemini) bilan jadvalni ko'chirish.

    Alohida funksiya: testda soxtalashtirish oson bo'lsin.
    """
    from app.llm import tez_llm
    from app.sarf import rol_bilan
    from kp.tz_rasm import RasmXatosi, rasm_modellari, rasmdan_qatorlar

    modellar = rasm_modellari(sozlama().tez_modellar)
    if not modellar:
        raise RasmXatosi(
            "Rasm o'qish uchun Gemini modeli kerak — TEZ_MODEL da yo'q. "
            "Ro'yxatni matn qilib yozing yoki Excel yuboring")
    with rol_bilan("tz-rasm"):
        return await rasmdan_qatorlar(yol, tez_llm(modellar))


async def _tz_ajrat(tz_matni: str, turlar: list[str]):
    """Modelga so'rov — TZ matnidan parametrlarni ajratish.

    TEZ MODEL ishlatiladi (`TEZ_MODEL`). Bu ish MEXANIK: matnda yozilgan
    raqamni ko'chirish, o'ylash emas. Katta model bu yerda natijani
    yaxshilamaydi, faqat qimmat va sekin bo'ladi.

    Alohida funksiya: testda soxtalashtirish oson bo'lsin.
    """
    from app.llm import AnthropicLlm, json_ajrat, matn_yig, tez_llm
    from kp.tz import JSON_SKELET, TIZIM_PROMPT, TzNatija, sorov_matni

    from app.sarf import rol_bilan

    s = sozlama()
    llm = tez_llm(s.tez_modellar) if s.tez_modellar else AnthropicLlm()
    with rol_bilan("tz-ajratish"):
        javob = await llm.javob(
            system=TIZIM_PROMPT,
            messages=[{"role": "user",
                       "content": sorov_matni(tz_matni, turlar) + "\n\n" + JSON_SKELET}],
        )
    return TzNatija.model_validate(json_ajrat(matn_yig(javob)))


async def bekor(baza, xabar, tg_id: int) -> bool:
    """Shakl bo'lsa bekor qiladi. `True` — bekor qilindi."""
    if not await faolmi(baza, tg_id):
        return False
    await baza.kp_shakli_ochir(tg_id)
    await xabar.reply_text("❌ KP tuzish to'xtatildi.")
    return True


async def javob(baza, xabar, tg_id: int, matn: str) -> bool:
    """Matnli javob. `True` — shakl bu xabarni O'ZI ishlatdi."""
    saqlangan = await baza.kp_shakli(tg_id)
    if saqlangan is None:
        return False

    javoblar = saqlangan["javoblar"]

    # Shakl allaqachon TO'LIQ, lekin aniqlashtiruv savoli kutilmoqda —
    # bu javob ODATIY savol emas, ambiguity yechimi. `Shakl.javob_ber`
    # bunday holatni bilmaydi (u faqat `savollar()` ro'yxatini ko'radi),
    # shuning uchun ALOHIDA tekshiramiz.
    if KUTILAYOTGAN_ANIQLIK in javoblar:
        await _aniqlikni_yop(baza, xabar, tg_id, javoblar, matn)
        return True

    shakl = Shakl(javoblar=javoblar)
    try:
        shakl.javob_ber(matn)
    except ShaklXatosi as xato:
        # Savol KUCHDA QOLADI — noto'g'ri javob bilan davom etmaymiz.
        await xabar.reply_text(f"⚠️ {xato}")
        await _savolni_yubor(xabar, shakl)
        return True

    await baza.kp_shakli_yoz(tg_id, shakl.javoblar)
    await _keyingisi(baza, xabar, tg_id, shakl)
    return True


# Menejer tugma o'rniga YOZISHI ham mumkin — ikkalasi ham ishlasin.
TARQOQ_SOZLARI = frozenset({
    "tarqoq", "тарқоқ", "тарокок", "tarqoq tizim", "тарқоқ тизим",
    "тарокок тизим", "razdelnaya", "раздельная",
})


async def _aniqlik_tugmasi(baza, xabar, tg_id: int, javoblar: dict,
                           qiymat: str) -> None:
    """Aniqlik savoliga TUGMA orqali javob."""
    from kp.shakldan import TARQOQQA_OT

    if qiymat != TARQOQQA_OT:
        return
    javoblar.pop(KUTILAYOTGAN_ANIQLIK, None)
    # Markaziy qurilmadan voz kechamiz — hisob QAYTA bajariladi va
    # ventilyator, isitgich, filtr alohida qatorlar bo'lib chiqadi.
    javoblar["markaziy"] = MARKAZIY_YOQ
    await baza.kp_shakli_yoz(tg_id, javoblar)
    await xabar.reply_text("🔀 Tarqoq tizimga o'tildi — qayta hisoblanmoqda…")
    await _yakunla(baza, xabar, tg_id, Shakl(javoblar=javoblar))


async def _aniqlikni_yop(baza, xabar, tg_id: int, javoblar: dict, matn: str) -> None:
    """Aniqlashtiruv javobini qabul qiladi va KP ni QAYTA yig'ishga urinadi.

    `index >= 0` — `mahsulotlar` ro'yxatidagi bitta qatorning modeli
    aniq quvvat bilan almashtiriladi, MIQDORI o'zgarmaydi (menejer
    odatda faqat model nomini yozadi, miqdorni emas).
    `index == -1` — obyekt yo'lida mos uskuna topilmagan edi; menejer
    aytgan model `qol_uskuna` ga yoziladi va OBYEKT YO'LI SAQLANADI.

    JONLI XATO (2026-08-21): ilgari bu yerda `yol` "model" ga
    o'tkazilardi. Natijada butun obyekt hisobi — havo sarfi, kanal
    diametri, panjara, qo'shimcha uskuna, yo'nalish — TASHLAB
    yuborilardi va KP da bitta qator qolardi. 350 m² oshxonaga
    (26 250 m³/soat) aynan shunday bo'lgan.
    """
    index = javoblar.pop(KUTILAYOTGAN_ANIQLIK)
    nom = matn.strip()

    # «tarqoq» deb YOZILGAN bo'lsa — tugma bosilgandek qabul qilamiz.
    #
    # JONLI XATO (2026-08-28): savol «tarqoq tizimga o'tamizmi?» deb
    # so'rardi, menejer «tarqoq» deb yozdi va o'sha savol qayta chiqdi.
    if nom.lower() in TARQOQ_SOZLARI:
        from kp.shakldan import TARQOQQA_OT

        await _aniqlik_tugmasi(baza, xabar, tg_id, javoblar, TARQOQQA_OT)
        return

    if not nom:
        javoblar[KUTILAYOTGAN_ANIQLIK] = index      # savol kuchda qoladi
        await xabar.reply_text("⚠️ Model nomini yozing.")
        return

    mahsulotlar = javoblar.get("mahsulotlar") or []
    if 0 <= index < len(mahsulotlar):
        mahsulotlar[index]["nomi"] = nom
    else:
        javoblar["qol_uskuna"] = nom

    shakl = Shakl(javoblar=javoblar)
    await baza.kp_shakli_yoz(tg_id, shakl.javoblar)
    await _yakunla(baza, xabar, tg_id, shakl)


async def tugma(baza, soro, tg_id: int) -> None:
    """Tanlov tugmasi bosildi."""
    xom = (soro.data or "")[len(TUGMA_OLDI):]
    kalit, _, qiymat = xom.partition(":")

    saqlangan = await baza.kp_shakli(tg_id)
    if saqlangan is None:
        await soro.edit_message_text("Bu shakl allaqachon yopilgan. /kp — yangisi.")
        return

    # ANIQLIK tugmasi joriy savolga bog'liq emas — shakl allaqachon
    # to'lgan, KP yig'ishda to'siq chiqqan.
    if kalit == "aniqlik":
        await soro.edit_message_text("✅ Tanlandi")
        await _aniqlik_tugmasi(baza, soro.message, tg_id,
                               saqlangan["javoblar"], qiymat)
        return

    shakl = Shakl(javoblar=saqlangan["javoblar"])
    joriy = shakl.joriy()
    if joriy is None or joriy.kalit != kalit:
        # Menejer eski xabardagi tugmani bosdi — jimgina e'tiborsiz qoldiramiz,
        # aks holda javob NOTO'G'RI savolga yozilardi.
        await soro.answer("Bu savol allaqachon o'tgan", show_alert=False)
        return

    if qiymat == ORQAGA:
        if not shakl.orqaga():
            await soro.answer("Orqaga qaytadigan joy yo'q", show_alert=False)
            return
        await baza.kp_shakli_yoz(tg_id, shakl.javoblar)
        # Savol O'SHA xabarda qayta chiziladi — ekran to'lib ketmasin.
        await _belgilarni_yangila(soro, shakl)
        return

    try:
        if qiymat == OTKAZ:
            shakl.otkaz()
        else:
            shakl.javob_ber(qiymat)
    except ShaklXatosi as xato:
        await soro.answer(str(xato)[:180], show_alert=True)
        return

    await baza.kp_shakli_yoz(tg_id, shakl.javoblar)

    # KO'P MARTA TANLANADIGAN SAVOL (uskuna ro'yxati) — savol O'SHA
    # xabarda qoladi, tanlangan tugmaga ✅ qo'yiladi.
    #
    # JONLI E'TIROZ (2026-08-26): har bosishda YANGI xabar chiqardi va
    # ekran "✅ Tizimga nima qo'shamiz? — rekuperator" qatorlari bilan
    # to'lib ketardi. Menejer nima tanlanganini yo'qotib qo'yardi.
    keyingi = shakl.joriy()
    if keyingi is not None and keyingi.kalit == joriy.kalit == "uskuna":
        await _belgilarni_yangila(soro, shakl)
        return

    # Tugmalarni olib tashlaymiz — ikki marta bosilmasin.
    tanlangan = qiymat if qiymat != OTKAZ else "o'tkazildi"
    await soro.edit_message_text(f"✅ {joriy.matn.splitlines()[0]} — *{tanlangan}*",
                                 parse_mode="Markdown")
    await _keyingisi(baza, soro.message, tg_id, shakl)


async def _belgilarni_yangila(soro, shakl: Shakl) -> None:
    """Xabar o'sha joyda qoladi, tanlanganlariga ✅ qo'yiladi."""
    try:
        await soro.edit_message_text(
            _savol_matni(shakl), reply_markup=_tugmalar(shakl),
            parse_mode="Markdown",
        )
    except Exception:                                  # noqa: BLE001
        # Telegram bir xil matnni qayta yozishga ruxsat bermaydi
        # («message is not modified»). Bu xato emas — foydalanuvchi
        # allaqachon tanlangan tugmani qayta bosgan.
        log.debug("tugmalarni yangilab bo'lmadi", exc_info=True)


async def _keyingisi(baza, xabar, tg_id: int, shakl: Shakl) -> None:
    if not shakl.tugadimi():
        await _savolni_yubor(xabar, shakl)
        return
    await _yakunla(baza, xabar, tg_id, shakl)


# --- yakun --------------------------------------------------------------------


async def _holatni_yangila(holat, matn: str) -> None:
    """Jarayon xabarini O'SHA joyda yangilaydi — ekran to'lib ketmasin.

    Xato YUTILADI: holat belgisi tufayli KP tuzish to'xtamasligi kerak.
    """
    if holat is None:
        return
    try:
        await holat.edit_text(matn)
    except Exception:                                # noqa: BLE001
        log.debug("holat yangilanmadi", exc_info=True)


async def _yakunla(baza, xabar, tg_id: int, shakl: Shakl) -> None:
    """Shakl to'ldi — KP yig'iladi.

    JARAYON BELGISI SHART. Menejer oxirgi javobni bergandan keyin
    hech narsa ko'rmasdi: katalog olinadi, ro'yxat katalog bilan
    solishtiriladi (AI), hujjat yasaladi — bularning hammasi jimgina
    ketardi va tashqaridan «qotib qoldi» bo'lib ko'rinardi.
    """
    s = sozlama()
    api = _mijoz()
    holat = await xabar.reply_text("⏳ Katalog olinmoqda…")
    try:
        katalog = await api.mahsulotlar()
        parametrlar = (await api.texnik_parametrlar()
                       if shakl.javoblar.get("yol") == "obyekt" else {})
    except Exception:
        log.exception("katalogni olib bo'lmadi")
        await xabar.reply_text(
            "⚠️ Katalogga ulanib bo'lmadi. Biroz kutib qayta urinib ko'ring: /kp")
        return

    # RO'YXATNI KATALOG BILAN SOLISHTIRISH — AI.
    #
    # Bu yo'lda ilgari AI umuman yo'q edi: faqat aniq moslik
    # qidirilardi va nom bir oz boshqacha yozilsa jimgina bo'sh
    # natija chiqardi. Endi kod nomzodlarni toraytiradi, AI esa
    # ulardan tanlaydi (`kp/royxat_ai.py`).
    qoshimcha_ogoh: list[str] = []
    if shakl.javoblar.get("yol") == "model":
        await _holatni_yangila(holat, "🔎 Ro'yxat katalog bilan solishtirilmoqda…")
        from kp.royxat_ai import moslashtir, qollash

        from app.llm import AnthropicLlm, tez_llm

        mahsulotlar = shakl.javoblar.get("mahsulotlar") or []
        try:
            llm = tez_llm(s.tez_modellar) if s.tez_modellar else AnthropicLlm()
            tanlovlar, qoshimcha_ogoh = await moslashtir(mahsulotlar, katalog, llm)
        except Exception:                            # noqa: BLE001
            log.warning("ro'yxat moslashtirilmadi", exc_info=True)
            tanlovlar = {}
        if tanlovlar:
            shakl.javoblar["mahsulotlar"] = qollash(mahsulotlar, tanlovlar)

    await _holatni_yangila(holat, "🧮 Hisob va hujjat tayyorlanmoqda…")
    menejer = await baza.menejer(tg_id)
    raqam = await baza.kp_raqam_ol(
        mijoz=str(shakl.javoblar.get("mijoz") or ""), iz_id=None
    )
    natija = yig(
        shakl.javoblar, katalog,
        raqam=raqam, kurs=kurs_joriy(), parametrlar=parametrlar,
        til=(await baza.foydalanuvchi_sozlamasi(tg_id) or {}).get("kp_tili") or "uz",
        menejer=menejer,
    )
    # AI moslashtirish ogohlantirishlari KP ga qo'shiladi — menejer
    # nima solishtirilmaganini ko'rsin.
    if qoshimcha_ogoh and natija.kp is not None:
        natija.kp.ogohlantirishlar.extend(qoshimcha_ogoh)

    if natija.aniqlik is not None:
        await _aniqlik_sorash(baza, xabar, tg_id, shakl, natija)
        return

    await baza.kp_shakli_ochir(tg_id)
    await _natijani_yubor(xabar, natija)


async def _aniqlik_sorash(baza, xabar, tg_id: int, shakl: Shakl, natija: Natija) -> None:
    """KP TUZILMAYDI — menejerdan aniqlik so'raladi.

    Eng arzon variantni jim tanlash mumkin edi, lekin `ВЦ 4-75 №2,5` da
    farq 156 dan 199 dollargacha — mijozga noto'g'ri narx ketardi.

    Kutilayotgan javob shaklga YOZILADI (`KUTILAYOTGAN_ANIQLIK`) — aks
    holda keyingi xabar "Shakl allaqachon to'ldirilgan" deb rad
    etilardi va menejer KP ni yakunlay olmasdi.
    """
    shakl.javoblar[KUTILAYOTGAN_ANIQLIK] = natija.aniqlik.index
    await baza.kp_shakli_yoz(tg_id, shakl.javoblar)

    qatorlar = [f"❓ {natija.aniqlik.savol}"]
    if natija.hisob:
        h = natija.hisob
        qatorlar.append(
            f"Hisob: *{h['sarf']:.0f} m³/soat*, kanal Ø{h['diametr']} mm")

    # OGOHLANTIRISHLAR SHU YERDA ko'rsatiladi, KP oxirida emas.
    #
    # JONLI E'TIROZ (2026-08-28): 120 000 m³/soat da hisobiy diametr
    # 2555 mm va tezlik 42 m/s edi — ya'ni tarmoq bir necha kanalga
    # bo'linishi kerak. Menejer esa faqat «kanal Ø1000 mm» ni ko'rib
    # qaror qabul qilardi: ogohlantirishlar KP TUZILGANDAN KEYIN
    # chiqardi, aniqlik savolida esa yo'q edi.
    #
    # Qaror shu yerda qabul qilinadi — ma'lumot ham shu yerda bo'lsin.
    if natija.ogohlantirishlar:
        qatorlar.append("")
        for ogoh in natija.ogohlantirishlar[:ANIQLIK_OGOH_SONI]:
            qatorlar.append(f"⚠️ {ogoh}")
        qolgan = len(natija.ogohlantirishlar) - ANIQLIK_OGOH_SONI
        if qolgan > 0:
            qatorlar.append(f"_…va yana {qolgan} ta ogohlantirish_")
    for variant in natija.aniqlik.variantlar:
        narx = variant.get("narx_som")
        narx_matni = (f"{narx:,.0f} so'm".replace(",", " ") if narx
                      else "narx kiritilmagan")
        quvvat = f" · {variant['quvvat']}" if variant.get("quvvat") else ""
        qatorlar.append(f"• `{variant['nomi']}`{quvvat} — {narx_matni}")
    tugmalar = None
    if natija.aniqlik.tanlovlar:
        # Savol ikkita yo'l taklif qilsa, IKKALASI HAM bosiladigan
        # bo'lishi kerak. Ilgari faqat model nomi qabul qilinardi va
        # ikkinchi yo'l YOPIQ HALQAGA olib borardi: menejer «tarqoq»
        # deb yozdi — o'sha savol qayta chiqdi.
        tugmalar = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                t["yorliq"],
                callback_data=f"{TUGMA_OLDI}aniqlik:" + t['qiymat'])]
            for t in natija.aniqlik.tanlovlar
        ])
        qatorlar.append("\nTugmani bosing yoki model nomini yozing. /bekor")
    else:
        qatorlar.append("\nModel nomini yozing yoki /bekor")
    await xabar.reply_text("\n".join(qatorlar), parse_mode="Markdown",
                           reply_markup=tugmalar)


def _qator_belgisi(qator) -> str:
    """Xulosa uchun nom — bir xil uskuna qaysi xonaga ketishi bilan.

    Spetsifikatsiyaning boshida "Xona nomi — " turadi (`kp/shakldan.py:
    _panjara_qatorlari`). Faqat shu qism olinadi: qolgani (jonli kesim,
    tezlik) xulosa uchun ortiqcha.
    """
    spek = (qator.spetsifikatsiya or "")
    bosh, ajratgich, _ = spek.partition(" — ")
    if ajratgich and bosh and len(bosh) < 60:
        return f"{qator.nomi} ({bosh})"
    return qator.nomi


async def _natijani_yubor(xabar, natija: Natija) -> None:
    kp = natija.kp
    qatorlar = [f"✅ *KP tayyor* — {kp.raqam}"]
    if natija.hisob:
        h = natija.hisob
        bolaklar = ["\n*Hisob*"]
        # Ko'p xonali obyektda har xona ALOHIDA ko'rsatiladi — menejer
        # qaysi raqam qayerdan chiqqanini ko'rsin.
        xonalar = h.get("xonalar") or []
        if len(xonalar) > 1:
            for x in xonalar:
                belgi = " (so'rish)" if x.get("sorish") else ""
                bolaklar.append(
                    f"• {x.get('nomi')}: {x.get('sarf', 0):.0f} m³/soat · "
                    f"Ø{x.get('diametr')} mm{belgi}"
                )
            bolaklar.append(
                f"*Magistral:* {h.get('kirish_sarfi', 0):.0f} m³/soat · "
                f"Ø{h['diametr']} mm"
            )
            if h.get("sorish_sarfi"):
                bolaklar.append(
                    f"*So'rish tizimi:* {h['sorish_sarfi']:.0f} m³/soat · "
                    f"Ø{h.get('sorish_diametri')} mm"
                )
        else:
            bolaklar.append(
                f"{h['sarf']:.0f} m³/soat · kanal Ø{h['diametr']} mm · "
                f"tezlik {h['tezlik']} m/s"
            )
        qatorlar.append("\n".join(bolaklar))
    qatorlar.append("")
    for qator in kp.qatorlar:
        narx = (f"{qator.birlik_narx:,.0f}".replace(",", " ")
                if qator.birlik_narx else "— narx yo'q")
        # XONA NOMI shu yerda ham kerak.
        #
        # JONLI E'TIROZ (2026-08-27): panjaralar har xona uchun alohida
        # hisoblanadi, shuning uchun xulosada bir xil nom ikki marta
        # chiqardi ("РВН 1000х1000 · 8 dona" va "РВН 1000х1000 · 3
        # dona"). Hujjatda farq ko'rinardi — xona nomi `spetsifikatsiya`
        # ustunida — lekin menejer avval SHU xulosani o'qiydi va uni
        # takror deb tushunardi.
        qatorlar.append(
            f"• {_qator_belgisi(qator)} · {qator.miqdor:g} {qator.birlik} · {narx}"
        )
    if kp.jami:
        qatorlar.append(f"\n*Jami (QQS bilan): {kp.jami:,.0f} so'm*".replace(",", " "))
    # Excel TZ dan 200 qatorlik KP chiqishi mumkin: bir xil ogohlantirish
    # takrorlanmasin va ro'yxat cheklansin — to'liq ro'yxat hujjatda.
    ogohlar = list(dict.fromkeys(kp.ogohlantirishlar))
    for ogoh in ogohlar[:OGOH_XABARDA]:
        qatorlar.append(f"\n⚠️ {ogoh}")
    if len(ogohlar) > OGOH_XABARDA:
        qatorlar.append(f"\n_…va yana {len(ogohlar) - OGOH_XABARDA} ta ogohlantirish_")
    # Telegram bitta xabarda 4096 belgidan ko'pini RAD ETADI — katta KP
    # xulosasi bo'laklab yuboriladi, aks holda hujjat ham yetib bormasdi.
    for bolak in _bolaklar(qatorlar):
        await xabar.reply_text(bolak, parse_mode="Markdown")

    papka = Path(sozlama().kp_yoli)
    papka.mkdir(parents=True, exist_ok=True)
    try:
        fayllar = hujjatlarni_yasa(kp, papka)
    except Exception:
        log.exception("KP hujjatini yasab bo'lmadi: %s", kp.raqam)
        await xabar.reply_text("⚠️ Hujjatni yasashda xato. Log tekshirilsin.")
        return
    for tur in ("pdf", "docx"):
        yol = fayllar.get(tur)
        if yol and Path(yol).is_file():
            with Path(yol).open("rb") as fayl:
                await xabar.reply_document(fayl, filename=Path(yol).name)

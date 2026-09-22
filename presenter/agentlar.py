"""Har agent natijasi uchun maxsus ko'rinish.

Umumiy qoidalar `matn.py` da; bu yerda faqat "shu agentning javobi qanday
o'qilishi kerak" degan bilim turadi.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .matn import MAKS_ROYXAT, natija_matni, qisqartir


def _qator(bolaklar: list[str]) -> str:
    return "\n".join(b for b in bolaklar if b)


# --- Sardor (product-spec) ---------------------------------------------------


def mahsulot_spetsifikatsiyasi(natija: dict[str, Any]) -> str:
    nomi = natija.get("mahsulot") or "Mahsulot"
    kategoriya = natija.get("kategoriya")

    bosh = f"{nomi} — texnik xususiyatlari"
    if kategoriya:
        bosh += f"\n({kategoriya})"

    qatorlar: list[str] = []
    for xususiyat in natija.get("xususiyatlar") or []:
        if not isinstance(xususiyat, dict):
            continue
        x_nomi = (xususiyat.get("nomi") or "").strip()
        qiymat = str(xususiyat.get("qiymat") or "").strip()
        if x_nomi and qiymat:
            qatorlar.append(f"{x_nomi}: {qiymat}")

    bolaklar = [bosh, ""]
    bolaklar.append("\n".join(qatorlar) if qatorlar else "Xususiyat topilmadi.")

    topilmagan = natija.get("topilmagan_maydonlar") or []
    if topilmagan:
        bolaklar.append("")
        bolaklar.append("Topilmadi: " + qisqartir(topilmagan))

    ziddiyatlar = natija.get("ziddiyatlar") or []
    if ziddiyatlar:
        bolaklar.append("")
        bolaklar.append("Manbalar zid: " + qisqartir(ziddiyatlar, 3))

    return _qator(bolaklar)


# --- Sardor: spetsifikatsiya bo'yicha tanlash --------------------------------


def mahsulot_tanlovi(natija: dict[str, Any]) -> str:
    bolaklar = ["Talabga mos mahsulotlar", ""]

    talablar = natija.get("talablar") or []
    if talablar:
        bolaklar.append("Talablar: " + qisqartir([_talab(t) for t in talablar], 8))
        bolaklar.append("")

    variantlar = natija.get("variantlar") or []
    if not variantlar:
        bolaklar.append("Katalogdan mos mahsulot topilmadi.")
    for i, variant in enumerate(variantlar[:5], 1):
        if not isinstance(variant, dict):
            continue
        bolaklar.append(f"{i}. {variant.get('mahsulot') or '—'}")
        moslik = variant.get("moslik_darajasi")
        if moslik:
            bolaklar.append(f"   Moslik: {moslik}")
        javob_beradi = variant.get("javob_beradi") or []
        if javob_beradi:
            bolaklar.append("   Javob beradi: " + qisqartir(javob_beradi, 5))
        bermaydi = variant.get("javob_bermaydi") or []
        if bermaydi:
            bolaklar.append("   Javob bermaydi: " + qisqartir(bermaydi, 5))
        izoh = variant.get("izoh")
        if izoh:
            bolaklar.append(f"   {izoh}")
        bolaklar.append("")

    if natija.get("qaror_izohi"):
        bolaklar.append(natija["qaror_izohi"])

    aniqlashtirish = natija.get("aniqlashtirish") or []
    if aniqlashtirish:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak: " + qisqartir(aniqlashtirish, 4))

    bolaklar.append("")
    bolaklar.append("Narx uchun KP so'rang — qaysi birini olish sizning qaroringiz.")
    return _qator(bolaklar)


def _talab(talab: Any) -> str:
    if isinstance(talab, dict):
        nomi = talab.get("nomi") or talab.get("parametr") or ""
        qiymat = talab.get("qiymat") or talab.get("talab") or ""
        return f"{nomi} {qiymat}".strip()
    return str(talab)


# --- Zara (price-monitor) ----------------------------------------------------


def narxlar(natija: dict[str, Any]) -> str:
    bolaklar = ["Narx ma'lumoti", ""]

    ichki = natija.get("ichki_narx_holati")
    if ichki:
        bolaklar.append(f"Ichki tizim: {ichki}")
        bolaklar.append("")

    yozuvlar = [y for y in (natija.get("yozuvlar") or []) if isinstance(y, dict)]
    topilgan = [y for y in yozuvlar if y.get("narx") is not None]
    if topilgan:
        for yozuv in topilgan[:MAKS_ROYXAT]:
            valyuta = yozuv.get("valyuta") or natija.get("valyuta") or ""
            qator = f"{yozuv.get('mahsulot')}: {yozuv.get('narx'):,.0f} {valyuta}".replace(",", " ")
            manba = yozuv.get("manba_nomi")
            if manba:
                qator += f" — {manba}"
            if yozuv.get("sana"):
                qator += f" ({yozuv['sana']})"
            if yozuv.get("tashqi_bozor"):
                qator += " [tashqi bozor narxi]"
            bolaklar.append(qator)
        if len(topilgan) > MAKS_ROYXAT:
            bolaklar.append(f"… yana {len(topilgan) - MAKS_ROYXAT} ta narx")
    else:
        bolaklar.append("Narx topilmadi.")

    topilmaganlar = natija.get("topilmaganlar") or []
    if topilmaganlar:
        bolaklar.append("")
        bolaklar.append("Topilmadi: " + qisqartir(topilmaganlar))

    diqqat = natija.get("diqqat") or []
    if diqqat:
        bolaklar.append("")
        bolaklar.extend(f"⚠️ {d}" for d in diqqat[:3])

    return _qator(bolaklar)


# --- Karim (competitor-watch) ------------------------------------------------


def raqobat(natija: dict[str, Any]) -> str:
    bolaklar = ["Raqobat tahlili", ""]

    topilmalar = [t for t in (natija.get("topilmalar") or []) if isinstance(t, dict)]
    boyicha: dict[str, list[str]] = {}
    for topilma in topilmalar:
        raqib = topilma.get("raqib") or "—"
        tafsilot = (topilma.get("tafsilot") or topilma.get("mavzu") or "").strip()
        if not tafsilot:
            continue
        sana = topilma.get("sana")
        if sana:
            tafsilot += f" ({sana})"
        boyicha.setdefault(raqib, []).append(tafsilot)

    for raqib, qatorlar in list(boyicha.items())[:MAKS_ROYXAT]:
        bolaklar.append(f"▸ {raqib}")
        for qator in qatorlar[:3]:
            bolaklar.append(f"   {qator}")
    if len(boyicha) > MAKS_ROYXAT:
        bolaklar.append(f"… yana {len(boyicha) - MAKS_ROYXAT} ta raqobatchi")

    trendlar = natija.get("trendlar") or []
    if trendlar:
        bolaklar.append("")
        bolaklar.append("Tendensiyalar:")
        bolaklar.extend(f"• {t}" for t in trendlar[:4])

    solishtirma = natija.get("solishtirma") or []
    if solishtirma:
        bolaklar.append("")
        bolaklar.append("Bizning mahsulot bilan solishtirma:")
        for s in solishtirma[:4]:
            bolaklar.append(f"• {_element(s)}")

    if natija.get("xulosa"):
        bolaklar.append("")
        bolaklar.append("Xulosa:")
        bolaklar.append(natija["xulosa"])

    topilmaganlar = natija.get("topilmaganlar") or []
    if topilmaganlar:
        bolaklar.append("")
        bolaklar.append("Topilmadi: " + qisqartir(topilmaganlar, 4))

    return _qator(bolaklar)


def _element(qiymat: Any) -> str:
    if isinstance(qiymat, dict):
        return " · ".join(f"{k}: {v}" for k, v in qiymat.items() if v)
    return str(qiymat)


# --- Malika (marketing) ------------------------------------------------------


def kampaniya(natija: dict[str, Any]) -> str:
    bolaklar = [natija.get("kampaniya_nomi") or "Kampaniya qoralamasi", ""]

    if natija.get("auditoriya"):
        bolaklar.append(f"Auditoriya: {natija['auditoriya']}")
    if natija.get("goya"):
        bolaklar.append(f"G'oya: {natija['goya']}")
    if natija.get("tavsiya_kanal"):
        vaqt = f", {natija['tavsiya_vaqt']}" if natija.get("tavsiya_vaqt") else ""
        bolaklar.append(f"Tavsiya: {natija['tavsiya_kanal']}{vaqt}")

    variantlar = [v for v in (natija.get("variantlar") or []) if isinstance(v, dict)]
    if variantlar:
        bolaklar.append("")
        for variant in variantlar[:4]:
            bolaklar.append(f"▸ {variant.get('kanal') or '—'} ({variant.get('ohang') or ''})")
            if variant.get("matn"):
                bolaklar.append(f"   {variant['matn']}")

    asos = natija.get("asos") or []
    if asos:
        bolaklar.append("")
        bolaklar.append("Nimaga asoslangan:")
        bolaklar.extend(f"• {a}" for a in asos[:4])

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak: " + qisqartir(sorash, 4))

    asossiz = natija.get("asossiz_dovolar") or []
    if asossiz:
        bolaklar.append("")
        bolaklar.append(f"Yozilmagan asossiz da'volar: {len(asossiz)} ta")

    return _qator(bolaklar)


# --- Doston (data-query) -----------------------------------------------------


def malumot(natija: dict[str, Any]) -> str:
    # Namunaviy ma'lumot ogohlantirishi ENG TEPADA turadi — pastda
    # qolsa, uzun javobda ko'rinmay ketadi.
    ogoh = natija.get("demo_ogohi")
    bosh = f"{ogoh}\n\n" if ogoh else ""

    # Katalogdan javob berilgan holat
    if natija.get("javob"):
        return bosh + str(natija["javob"])

    qatorlar = natija.get("qatorlar") or []
    if not qatorlar:
        return bosh + "So'rov bajarildi, lekin natija bo'sh — mos yozuv topilmadi."

    ustunlar = list(qatorlar[0].keys()) if isinstance(qatorlar[0], dict) else []
    bolaklar = [
        *([ogoh, ""] if ogoh else []),
        f"Natija: {natija.get('qatorlar_soni', len(qatorlar))} ta yozuv",
        "",
    ]

    for qator in qatorlar[:10]:
        if isinstance(qator, dict):
            bolaklar.append(" · ".join(f"{u}: {qator.get(u)}" for u in ustunlar))
    if len(qatorlar) > 10:
        bolaklar.append(f"… yana {len(qatorlar) - 10} ta yozuv")

    if natija.get("izoh"):
        bolaklar.append("")
        bolaklar.append(str(natija["izoh"]))
    return _qator(bolaklar)


# --- Hilola (hr-assist) ------------------------------------------------------


def hr(natija: dict[str, Any]) -> str:
    ogoh = natija.get("demo_ogohi")
    bolaklar = [
        *([ogoh, ""] if ogoh else []),
        f"{(natija.get('vazifa_turi') or 'HR').capitalize()} — qoralama",
        "",
    ]

    if natija.get("qoralama"):
        bolaklar.append(str(natija["qoralama"]))

    mezonlar = [m for m in (natija.get("mezonlar") or []) if isinstance(m, dict)]
    if mezonlar:
        bolaklar.append("")
        bolaklar.append("Mezonlar:")
        for mezon in mezonlar[:MAKS_ROYXAT]:
            izoh = f" — {mezon['izoh']}" if mezon.get("izoh") else ""
            bolaklar.append(f"• {mezon.get('nomi')}{izoh}")

    solishtirma = [s for s in (natija.get("solishtirma") or []) if isinstance(s, dict)]
    if solishtirma:
        bolaklar.append("")
        bolaklar.append("Nomzodlar:")
        for baho in solishtirma[:MAKS_ROYXAT]:
            bolaklar.append(
                f"• {baho.get('nomzod')} — moslik: {baho.get('moslik')}"
                + (f" ({baho['izoh']})" if baho.get("izoh") else "")
            )

    rad = natija.get("rad_etilgan_mezonlar") or []
    if rad:
        bolaklar.append("")
        bolaklar.append("Ishlatilmagan (kamsituvchi) mezonlar:")
        bolaklar.extend(f"• {r}" for r in rad[:3])

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak: " + qisqartir(sorash, 4))

    if natija.get("tavsiya"):
        bolaklar.append("")
        bolaklar.append(f"Kuzatuv: {natija['tavsiya']}")

    bolaklar.append("")
    bolaklar.append("Bu yakuniy qaror emas — qaror inson zimmasida.")
    return _qator(bolaklar)


# --- Laziz (legal-review) ----------------------------------------------------

XAVF_BELGISI = {"yuqori": "🔴", "orta": "🟡", "past": "🟢"}


def huquqiy(natija: dict[str, Any]) -> str:
    hujjat = natija.get("hujjat_turi") or "Hujjat"
    bolaklar = [f"{hujjat} — huquqiy tahlil"]
    if natija.get("yurisdiksiya"):
        bolaklar.append(f"Yurisdiksiya: {natija['yurisdiksiya']}")
    bolaklar.append("")

    qaydlar = [q for q in (natija.get("qaydlar") or []) if isinstance(q, dict)]
    tartib = {"yuqori": 0, "orta": 1, "past": 2}
    qaydlar.sort(key=lambda q: tartib.get(q.get("xavf"), 3))

    for qayd in qaydlar[:MAKS_ROYXAT]:
        belgi = XAVF_BELGISI.get(qayd.get("xavf"), "•")
        bolaklar.append(f"{belgi} {qayd.get('band') or '—'} — {qayd.get('izoh') or ''}")
        if qayd.get("tuzatish_taklifi"):
            bolaklar.append(f"   Taklif: {qayd['tuzatish_taklifi']}")
        # Qonun havolasi — huquqiy xulosada majburiy.
        if qayd.get("manba_nomi"):
            bolaklar.append(f"   Asos: {qayd['manba_nomi']}")
        bolaklar.append("")
    if len(qaydlar) > MAKS_ROYXAT:
        bolaklar.append(f"… yana {len(qaydlar) - MAKS_ROYXAT} ta qayd")

    if natija.get("xulosa"):
        bolaklar.append("Xulosa:")
        bolaklar.append(str(natija["xulosa"]))

    aniqlik = natija.get("aniqlik_kerak") or []
    if aniqlik:
        bolaklar.append("")
        bolaklar.append("Noaniq bandlar (taxmin qilinmadi):")
        bolaklar.extend(f"• {a}" for a in aniqlik[:4])

    yetishmagan = natija.get("yetishmagan_qismlar") or []
    if yetishmagan:
        bolaklar.append("")
        bolaklar.append("Hujjat to'liq emas: " + qisqartir(yetishmagan, 4))

    bolaklar.append("")
    bolaklar.append("Bu huquqiy kafolat emas — yakuniy qaror yurist zimmasida.")
    return _qator(bolaklar)


# --- Bekzod (sales-strategy) -------------------------------------------------


def savdo(natija: dict[str, Any]) -> str:
    turlar = {
        "savdo_rejasi": "Savdo rejasi",
        "kp": "Tijorat taklifi (KP)",
        "kanal_tahlili": "Kanal tahlili",
        "narx_siyosati": "Narx siyosati taklifi",
    }
    bosh = turlar.get(natija.get("vazifa_turi"), "Savdo strategiyasi")
    if natija.get("mahsulot"):
        bosh += f" — {natija['mahsulot']}"
    if natija.get("davr"):
        bosh += f" ({natija['davr']})"

    bolaklar = [bosh, ""]

    maqsadlar = [m for m in (natija.get("maqsadlar") or []) if isinstance(m, dict)]
    if maqsadlar:
        bolaklar.append("Maqsadlar:")
        for maqsad in maqsadlar[:MAKS_ROYXAT]:
            olchov = f" — {maqsad['olchov']}" if maqsad.get("olchov") else ""
            bolaklar.append(f"• {maqsad.get('nomi')}{olchov}")
        bolaklar.append("")

    bosqichlar = natija.get("bosqichlar") or []
    if bosqichlar:
        bolaklar.append("Bosqichlar:")
        bolaklar.extend(f"{i}. {b}" for i, b in enumerate(bosqichlar[:MAKS_ROYXAT], 1))
        bolaklar.append("")

    kanallar = [k for k in (natija.get("kanallar") or []) if isinstance(k, dict)]
    if kanallar:
        bolaklar.append("Kanallar:")
        for kanal in kanallar[:MAKS_ROYXAT]:
            ulush = f" ({kanal['ulush']})" if kanal.get("ulush") else ""
            bolaklar.append(f"▸ {kanal.get('nomi')}{ulush}")
            if kanal.get("yondashuv"):
                bolaklar.append(f"   {kanal['yondashuv']}")
        bolaklar.append("")

    segmentlar = [s for s in (natija.get("segmentlar") or []) if isinstance(s, dict)]
    if segmentlar:
        bolaklar.append("Segmentlar:")
        for segment in segmentlar[:MAKS_ROYXAT]:
            bolaklar.append(f"• {segment.get('nomi')} — {segment.get('yondashuv', '')}")
        bolaklar.append("")

    kpi = [k for k in (natija.get("kpi") or []) if isinstance(k, dict)]
    if kpi:
        bolaklar.append("KPI: " + qisqartir([f"{k.get('nomi')} ({k.get('olchov')})" for k in kpi]))
        bolaklar.append("")

    xavflar = natija.get("xavflar") or []
    if xavflar:
        bolaklar.append("Xavflar:")
        bolaklar.extend(f"⚠️ {x}" for x in xavflar[:4])
        bolaklar.append("")

    if natija.get("narx_taklifi"):
        bolaklar.append(f"Narx bo'yicha taklif (qaror emas): {natija['narx_taklifi']}")
        bolaklar.append("")

    if natija.get("kp_qoralamasi"):
        bolaklar.append("Tijorat taklifi qoralamasi:")
        bolaklar.append(str(natija["kp_qoralamasi"]))
        bolaklar.append("")

    malumot_yoq = natija.get("malumot_yoq") or []
    if malumot_yoq:
        bolaklar.append("Ma'lumot yetishmadi (taxmin qilinmadi): " + qisqartir(malumot_yoq))

    havola = natija.get("kimga_havola") or []
    if havola:
        bolaklar.append("Kimga murojaat qilish kerak: " + qisqartir(havola, 3))

    return _qator(bolaklar)


# --- Temur (proposal-builder) ------------------------------------------------


def tijorat_taklifi(natija: dict[str, Any]) -> str:
    bolaklar = [f"Tijorat taklifi № {natija.get('raqam', '—')}"]
    if natija.get("sana"):
        bolaklar.append(f"Sana: {natija['sana']}")

    mijoz = natija.get("mijoz") or {}
    if mijoz.get("nomi"):
        aloqa = " · ".join(x for x in (mijoz.get("aloqa"), mijoz.get("manzil")) if x)
        bolaklar.append(f"Mijoz: {mijoz['nomi']}" + (f" ({aloqa})" if aloqa else ""))
    bolaklar.append("")

    valyuta = natija.get("valyuta") or ""

    def pul(qiymat):
        if qiymat is None:
            return "—"
        return f"{qiymat:,.0f}".replace(",", " ") + (f" {valyuta}" if valyuta else "")

    for i, qator in enumerate(natija.get("qatorlar") or [], 1):
        if not isinstance(qator, dict):
            continue
        bolaklar.append(f"{i}. {qator.get('nomi')}")
        if qator.get("spetsifikatsiya"):
            bolaklar.append(f"   {qator['spetsifikatsiya']}")
        xom_miqdor = qator.get("miqdor")
        try:
            miqdor_matni = f"{float(xom_miqdor):g}"
        except (TypeError, ValueError):
            miqdor_matni = str(xom_miqdor or "")
        miqdor = f"{miqdor_matni} {qator.get('birlik', '')}".strip()
        if qator.get("birlik_narx") is None:
            bolaklar.append(f"   {miqdor} × [narx to'ldirilishi kerak]")
        else:
            bolaklar.append(
                f"   {miqdor} × {pul(qator['birlik_narx'])} = {pul(qator.get('jami'))}"
            )
    bolaklar.append("")

    if natija.get("summa") is not None:
        bolaklar.append(f"Jami (QQSsiz): {pul(natija['summa'])}")
        if natija.get("qqs") is not None:
            bolaklar.append(f"QQS: {pul(natija['qqs'])}")
        bolaklar.append(f"Umumiy summa: {pul(natija.get('jami'))}")

    ogohlantirishlar = natija.get("ogohlantirishlar") or []
    if ogohlantirishlar:
        bolaklar.append("")
        bolaklar.extend(f"⚠️ {o}" for o in ogohlantirishlar[:4])

    taklif = natija.get("taklif_qilingan") or []
    if taklif:
        bolaklar.append("")
        bolaklar.append("Katalogdagi o'xshash mahsulotlar: " + qisqartir(taklif, 4))

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak: " + qisqartir(sorash, 4))

    # KEYINGI QADAM. Narxsiz KP — boshi berk ko'cha: menejer nima
    # qilishni bilmaydi. Bitta qator uni amalga aylantiradi.
    narxsiz = [
        i for i, q in enumerate(natija.get("qatorlar") or [], 1)
        if isinstance(q, dict) and q.get("birlik_narx") is None
    ]
    if narxsiz:
        namuna = ", ".join(f"{i}-tovarga 5 mln" for i in narxsiz[:2])
        bolaklar.append("")
        bolaklar.append(f"💡 Narxni o'zingiz kiritishingiz mumkin: «{namuna}»")

    fayllar = natija.get("fayllar") or {}
    if fayllar:
        bolaklar.append("")
        bolaklar.append("Hujjat: " + ", ".join(f"{tur.upper()}" for tur in sorted(fayllar)))

    bolaklar.append("")
    bolaklar.append("Mijozga yuborilmadi — tasdiqdan keyin yuborishingiz mumkin.")
    return _qator(bolaklar)


# --- Nodira (catalog-admin) --------------------------------------------------


def _amal_qatori(amal: dict[str, Any]) -> str:
    """Bitta katalog o'zgarishini odam o'qiy oladigan qatorga aylantiradi."""
    tur = str(amal.get("tur") or "")
    belgi = "🗑" if tur.endswith("_ochir") else ("➕" if tur.endswith("_yarat") else "✏️")
    nishon = f" id={amal['nishon_id']}" if amal.get("nishon_id") else ""
    maydonlar = amal.get("maydonlar") or {}
    qiymatlar = ", ".join(f"{k}: {v}" for k, v in maydonlar.items())
    qator = f"{belgi} {tur}{nishon}"
    if qiymatlar:
        qator += f" — {qiymatlar}"
    if amal.get("izoh"):
        qator += f"\n   {amal['izoh']}"
    return qator


def katalog(natija: dict[str, Any]) -> str:
    bolaklar: list[str] = []

    # Bajarilgandan keyingi hisobot.
    if natija.get("bajarildi"):
        bolaklar.append(f"Katalogga {natija.get('bajarilgan_soni', 0)} ta o'zgarish yozildi:")
        bolaklar.append("")
        for yozuv in natija.get("bajarilgan") or []:
            if isinstance(yozuv, dict) and yozuv.get("tavsif"):
                bolaklar.append(f"✅ {yozuv['tavsif']}")
        xatolar = natija.get("xatolar") or []
        if xatolar:
            bolaklar.append("")
            bolaklar.extend(f"⚠️ {x}" for x in xatolar[:4])
        return _qator(bolaklar)

    # Tasdiq kutayotgan reja.
    if natija.get("niyat"):
        bolaklar.append(natija["niyat"])
        bolaklar.append("")

    amallar = natija.get("taklif_amal") or []
    bolaklar.append(f"Bajarilishi kutilayotgan o'zgarishlar ({len(amallar)} ta):")
    bolaklar.append("")
    for amal in amallar:
        if isinstance(amal, dict):
            bolaklar.append(_amal_qatori(amal))

    if natija.get("ochirish_soni"):
        bolaklar.append("")
        bolaklar.append(
            f"🗑 DIQQAT: {natija['ochirish_soni']} ta yozuv O'CHIRILADI — "
            "buni qaytarib bo'lmaydi."
        )
    if natija.get("xavf"):
        bolaklar.append(f"   {natija['xavf']}")

    topilmadi = natija.get("topilmadi") or []
    if topilmadi:
        bolaklar.append("")
        bolaklar.append("Katalogda topilmadi: " + qisqartir(topilmadi, 4))

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak: " + qisqartir(sorash, 4))

    ogohlantirishlar = natija.get("ogohlantirishlar") or []
    if ogohlantirishlar:
        bolaklar.append("")
        bolaklar.extend(f"⚠️ {o}" for o in ogohlantirishlar[:4])

    bolaklar.append("")
    bolaklar.append("Hech narsa hali yozilmadi — tasdiqlasangiz bajariladi.")
    return _qator(bolaklar)


# --- Anvar (montaj-guide) ----------------------------------------------------


def montaj(natija: dict[str, Any]) -> str:
    bolaklar: list[str] = []

    # Chegaradan tashqari savol — javob o'rniga kim qilishi aytiladi.
    if natija.get("chegaradan_tashqari"):
        return "⚠️ " + str(natija["chegaradan_tashqari"])

    if natija.get("vaziyat"):
        bolaklar.append(str(natija["vaziyat"]))
        bolaklar.append("")

    qadamlar = natija.get("qadamlar") or []
    if qadamlar:
        bolaklar.append("Nima qilinadi")
        for i, q in enumerate(qadamlar, 1):
            if not isinstance(q, dict):
                continue
            bolaklar.append(f"{i}. {q.get('nima') or '—'}")
            if q.get("nega"):
                bolaklar.append(f"   — {q['nega']}")
        bolaklar.append("")

    sabablar = natija.get("sabablar") or []
    if sabablar:
        bolaklar.append("Ehtimoliy sabablar (tekshirish tartibida)")
        for i, s in enumerate(sabablar, 1):
            if not isinstance(s, dict):
                continue
            bolaklar.append(f"{i}. {s.get('sabab') or '—'}")
            if s.get("qanday_tekshirish"):
                bolaklar.append(f"   Tekshirish: {s['qanday_tekshirish']}")
        bolaklar.append("")

    tekshiruv = natija.get("tekshiruv") or []
    if tekshiruv:
        bolaklar.append("Ishga tushirishdan oldin")
        bolaklar.extend(f"• {t}" for t in tekshiruv)
        bolaklar.append("")

    joyida = natija.get("joyida_aniqlanadi") or []
    if joyida:
        bolaklar.append("Joyida aniqlanadi (obyektni ko'rmasdan aytib bo'lmaydi)")
        bolaklar.extend(f"• {x}" for x in joyida)
        bolaklar.append("")

    bazada_yoq = natija.get("bazada_yoq") or []
    if bazada_yoq:
        bolaklar.append("⚠️ Bazamizda hujjat yo'q — muhandis tekshirsin")
        bolaklar.extend(f"• {x}" for x in bazada_yoq)
        bolaklar.append("")

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("Aniqlashtirish kerak")
        bolaklar.extend(f"• {x}" for x in sorash)

    return "\n".join(bolaklar).strip() or "Montaj bo'yicha ma'lumot yo'q."


# --- Jasur (tender-watch) ----------------------------------------------------


def _pul(qiymat: Any, valyuta: Any = "UZS") -> str:
    """Summa O'Z VALYUTASIDA: `12 500 000 so'm`, `81 205,70 dollar`.

    Ilgari bu yerda har doim " so'm" qo'shilardi. etender esa lotni
    dollarda va yevroda ham e'lon qiladi (2026-09-14: 866 lotdan 54 tasi
    USD, 10 tasi EUR) — ular ham so'm bo'lib ko'rinardi.
    """
    from integrations.valyuta import pul_matni

    return pul_matni(qiymat, str(valyuta or "UZS"))


def _som(qiymat: Any) -> str:
    """Summani so'mda ko'rsatadi: 12 500 000 so'm."""
    return _pul(qiymat, "UZS")


# E'lonlar orasidagi ajratgich — menejer ro'yxatni ko'z bilan bo'ladi.
AJRATGICH = "=" * 28

# NIMA QILISH KERAK — faqat TEKSHIRILGAN ma'lumot.
#
# Bu yerda ATAYLAB ro'yxatdan o'tish tartibi, to'lov yoki kafolat puli
# YOZILMAGAN: ular portal qoidalari va o'zgaradi. Xotiradan yozilgan
# tartib menejerni noto'g'ri yo'lga solardi.
#
# Yozilgani — o'z ma'lumotimizdan aniq bilinadigan narsa: lot raqami
# qidiruv kaliti, savdo aynan `maydoncha` da bo'ladi, havola esa
# DXMAP orqali lotning to'liq kartochkasiga olib boradi.
QADAM_IZOHI = (
    "NIMA QILISH KERAK\n"
    "1. Havolani ochib lot kartochkasini o'qing — texnik topshiriq,\n"
    "   miqdor va muddat shu yerda.\n"
    "2. Savdo yuqorida ko'rsatilgan MAYDONDA bo'ladi. O'sha maydonda\n"
    "   lot raqami bo'yicha qidirasiz.\n"
    "3. Ishtirok shartlari (ro'yxatdan o'tish, kafolat puli, hujjat)\n"
    "   har maydonda o'zining qoidasi bo'yicha — kartochkadagi\n"
    "   shartlarni o'qing.\n"
    "4. Texnik hisob kerak bo'lsa: /kp yoki obyektni tasvirlab yozing."
)

# Izoh sarlavhadan shuncha ulushdan ko'p yangi so'z keltirsa — foydali.
YANGILIK_ULUSHI = 0.4


# Muddatga shuncha kun qolganda ogohlantiriladi.
SHOSHILINCH_KUN = 2

MINTAQA = ZoneInfo("Asia/Tashkent")


def _muddat_ogohi(muddat: str) -> str:
    """Muddat yaqin bo'lsa ko'zga tashlanadigan belgi.

    Sana o'zi yetarli emas: menejer ro'yxatni tez o'qiydi va "2026-09-11"
    bugundan ikki kun keyinligini darrov hisoblamaydi. Shu sababdan
    ulgurish mumkin bo'lgan lot qo'ldan ketishi mumkin.
    """
    try:
        qolgan = (date.fromisoformat(str(muddat)[:10]) - _bugun()).days
    except (TypeError, ValueError):
        return ""
    if qolgan < 0:
        return "   ⚠️ MUDDAT O'TGAN"
    if qolgan == 0:
        return "   🔴 BUGUN TUGAYDI"
    if qolgan <= SHOSHILINCH_KUN:
        return f"   🟠 {qolgan} kun qoldi"
    return ""


def _bugun() -> date:
    """Mahalliy (Toshkent) sana — mashina sozlamasiga tayanmaydi."""
    return datetime.now(MINTAQA).date()


def _sozlar(matn: str) -> set[str]:
    """Solishtirish uchun so'zlar: kichik harf, faqat harf va raqam."""
    return {
        s for s in re.split(r"[^\w]+", (matn or "").lower())
        if len(s) > 3
    }


def _yangi_malumotmi(izoh: str, sarlavha: str) -> bool:
    """Izohda sarlavhada YO'Q ma'lumot bormi?

    Aynan taqqoslash yetarli emas: model sarlavhani boshqacha so'z
    tartibida yoki qo'shimcha bilan qaytaradi ("...xizmati",
    "...bo'yicha lot"). Shuning uchun SO'Z darajasida solishtiriladi.
    """
    izoh_sozlari = _sozlar(izoh)
    if not izoh_sozlari:
        return False
    yangi = izoh_sozlari - _sozlar(sarlavha)
    return len(yangi) / len(izoh_sozlari) >= YANGILIK_ULUSHI


def tenderlar(natija: dict[str, Any]) -> str:
    bolaklar: list[str] = []
    mos = natija.get("mos_elonlar") or []

    # IKKI TOIFA. `ishonch: past` — uskunasi bizniki EMAS (pretsizion
    # konditsioner, chet el brendi, maishiy split), lekin montaj yoki
    # servis qismi bizga tegishli bo'lishi mumkin.
    #
    # Ular ARALASHTIRILMAYDI: menejer "to'liq bizniki" deb o'ylab
    # tayyorgarlik ko'rib, keyin uskunani bera olmasligini bilib
    # qolmasligi kerak. Shuning uchun pastda, alohida sarlavha bilan.
    aniq = [e for e in mos if isinstance(e, dict) and e.get("ishonch") != "past"]
    ehtimol = [e for e in mos if isinstance(e, dict) and e.get("ishonch") == "past"]

    if not mos:
        bolaklar.append("Yangi mos e'lon yo'q.")
    elif aniq:
        bolaklar.append(f"BIZGA MOS ({len(aniq)} ta)")
        bolaklar.append("")

    for i, elon in enumerate(aniq + ehtimol, 1):
        if not isinstance(elon, dict):
            continue
        # Ikkinchi toifa boshlanishida sarlavha.
        if ehtimol and elon is ehtimol[0]:
            bolaklar.append(AJRATGICH)
            bolaklar.append(f"BIZGA TEGISHLI BO'LISHI MUMKIN ({len(ehtimol)} ta)")
            bolaklar.append("Uskunasi bizniki emas — montaj/servis qismi bo'lishi mumkin.")
            bolaklar.append("")
        bolaklar.append(AJRATGICH)
        sarlavha = (elon.get("sarlavha") or "—").strip()
        sana = f" · {elon['sana']}" if elon.get("sana") else ""
        bolaklar.append(f"{i}. {sarlavha}{sana}")
        bolaklar.append("")

        # LOT RAQAMI birinchi: menejer portalda aynan shu bilan qidiradi.
        if elon.get("lot_raqami"):
            bolaklar.append(f"Lot:     {elon['lot_raqami']}")
        # BUYURTMACHI NOMI EMAS, STIR. Nom uzun va tirnoqlar bilan
        # buzilgan holda keladi (`""TOSHKENT ... " MIL" DM`), ikki qator
        # egallaydi va hech narsa qo'shmaydi — tashkilot STIR bilan
        # bir qiymatli aniqlanadi. Jonli tekshiruv: 156 lotning
        # 156 tasida STIR bor.
        if elon.get("buyurtmachi_stir"):
            bolaklar.append(f"STIR:    {elon['buyurtmachi_stir']}")
        elif elon.get("buyurtmachi"):
            bolaklar.append(f"Buyurtmachi: {elon['buyurtmachi']}")
        if elon.get("hudud"):
            bolaklar.append(f"Hudud:   {elon['hudud']}")
        if elon.get("summa"):
            bolaklar.append(f"Narx:    {_pul(elon['summa'], elon.get('valyuta'))}")
        if elon.get("muddat"):
            bolaklar.append(f"Muddat:  {elon['muddat']}{_muddat_ogohi(elon['muddat'])}")
        if elon.get("maydoncha"):
            bolaklar.append(f"Maydon:  {elon['maydoncha']}")
        # BEGONA BREND — texnik topshiriqdan topilgan. Sarlavhada deyarli
        # yozilmaydi: 510351-lotda "VRF ta'miri" ko'rinardi, TZ da esa
        # AUX ARV6-H610 — bizning brend emas.
        if elon.get("begona_brend"):
            brendlar = ", ".join(str(b) for b in elon["begona_brend"])
            bolaklar.append(f"⚠ Brend:  {brendlar} — bizniki emas")

        # HUJJATDAN — sarlavhada yo'q narsa. "Aslida" sarlavhani tuzatadi
        # (287840: ta'mir emas, loyiha-smeta tuzish). "Shartlar": `·` —
        # kartochkadan kod ko'chirgani, `⚠` — hujjatdan model topgani.
        if elon.get("tz_aslida"):
            bolaklar.append(f"Aslida:  {elon['tz_aslida']}")
        shartlar = [str(s) for s in elon.get("shartlar") or []]
        talablar = [str(t) for t in elon.get("tz_talablar") or []]
        if shartlar or talablar:
            bolaklar.append("Shartlar:")
            bolaklar.extend(f"  · {s}" for s in shartlar)
            bolaklar.extend(f"  ⚠ {t}" for t in talablar)
        if elon.get("oqilmagan_fayllar"):
            bolaklar.append(
                "O'qilmadi: " + "; ".join(str(f) for f in elon["oqilmagan_fayllar"])
            )

        # TAKROR YOZILMAYDI. Model `nimaga_kerak` va `izoh` ni ko'pincha
        # sarlavhaning o'zi bilan to'ldiradi:
        #   sarlavha     "Ventilyatsiya tizimiga texnik xizmat ko'rsatish"
        #   nimaga_kerak "Ventilyatsiya tizimlariga texnik xizmat ..."
        #   izoh         "... texnik xizmat ko'rsatish bo'yicha lot."
        # Uchtasi bir xil gap — menejer uchun shovqin.
        #
        # "Aslida" bor bo'lsa sarlavha bo'yicha izoh KO'RSATILMAYDI: u
        # hujjat o'qilmasdan yozilgan va unga zid bo'lishi mumkin (287840:
        # "ta'mirlash profilimizga to'liq mos").
        for maydon in () if elon.get("tz_aslida") else ("nimaga_kerak", "izoh"):
            qiymat = (elon.get(maydon) or "").strip()
            if qiymat and _yangi_malumotmi(qiymat, sarlavha):
                bolaklar.append(f"Izoh:    {qiymat}")
                break

        if elon.get("havola"):
            bolaklar.append("")
            bolaklar.append(str(elon["havola"]))
        bolaklar.append("")

    if mos:
        bolaklar.append(AJRATGICH)
        bolaklar.append(QADAM_IZOHI)
        bolaklar.append("")

    otgan = natija.get("muddati_otgan") or 0
    if otgan:
        bolaklar.append(
            f"{otgan} ta lot muddati o'tgani uchun ko'rsatilmadi."
        )

    # TZ o'qilmagan lot — brendi va shartlari TEKSHIRILMAGAN. Jimgina
    # "brend yo'q" deb ko'rsatilmaydi.
    tekshirilmagan = natija.get("brend_tekshirilmadi") or 0
    if tekshirilmagan:
        bolaklar.append(
            f"{tekshirilmagan} ta lotning texnik topshirig'i o'qilmadi — "
            "brendi va shartlari tekshirilmadi."
        )
    chiqarilgan = [c for c in natija.get("hujjat_chiqargan") or [] if isinstance(c, dict)]
    if chiqarilgan:
        bolaklar.append(f"Hujjati o'qilgach {len(chiqarilgan)} ta lot chiqarildi:")
        for lot in chiqarilgan:
            bolaklar.append(
                f"  · {str(lot.get('sarlavha') or '—')[:80]} — {lot.get('sabab') or ''}"
            )
            if lot.get("havola"):
                bolaklar.append(f"    {lot['havola']}")
    if natija.get("hujjat_baholanmadi"):
        bolaklar.append(
            "⚠ Hujjatlar o'qildi, lekin model baholay olmadi "
            f"({str(natija['hujjat_baholanmadi'])[:150]}) — baho sarlavha bo'yicha."
        )

    korilgan = natija.get("yangi_korildi")
    if korilgan:
        mos_emas = natija.get("mos_emas_soni") or 0
        bolaklar.append(
            f"{korilgan} ta yangi e'lon ko'rildi, shundan {mos_emas} tasi mos emas."
        )
    if natija.get("xulosa"):
        bolaklar.append(natija["xulosa"])

    if natija.get("qamrov_izohi"):
        bolaklar.append("")
        bolaklar.append(f"ℹ️ {natija['qamrov_izohi']}")

    # `_qator` BO'SH QATORLARNI TASHLAYDI (`if b`) — bu yerda esa ular
    # ma'noli: e'lonlar orasidagi havo va ajratgich shu bilan ishlaydi.
    # Shuning uchun alohida birlashtiramiz, ketma-ket bo'shliqlar
    # bittaga qisqartiriladi.
    matn = "\n".join(bolaklar)
    return re.sub(r"\n{3,}", "\n\n", matn).strip()


# --- Nilufar (smm-analyst) ---------------------------------------------------


def _son(qiymat: Any) -> str:
    try:
        return f"{int(qiymat):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(qiymat or "—")


def smm(natija: dict[str, Any]) -> str:
    bolaklar = [f"Instagram tahlili — @{natija.get('profil', '—')}", ""]

    bolaklar.append(
        f"Obunachilar: {_son(natija.get('obunachilar'))} · "
        f"Postlar: {_son(natija.get('postlar_soni'))} · "
        f"Tahlilga olindi: {natija.get('korilgan_postlar', 0)} "
        f"({natija.get('video_soni', 0)} video)"
    )
    if natija.get("korishlar_medianasi"):
        bolaklar.append(
            f"Video ko'rishlar medianasi: {_son(natija['korishlar_medianasi'])}"
        )

    # Insights — faqat o'z akkauntimizda. Bular ko'rishlar sonidan
    # muhimroq: saqlash va ulashish kontent qiymatini, obuna esa biznes
    # natijasini ko'rsatadi.
    if natija.get("oz_akkaunt"):
        bolaklar.append("")
        bolaklar.append(
            f"Qamrov: {_son(natija.get('jami_qamrov'))} · "
            f"Saqlash: {_son(natija.get('jami_saqlash'))} · "
            f"Ulashish: {_son(natija.get('jami_ulashish'))} · "
            f"Yangi obuna: {_son(natija.get('jami_obuna'))}"
        )
        auditoriya = natija.get("auditoriya") or {}
        shaharlar = auditoriya.get("shaharlar") or {}
        if shaharlar:
            eng = list(shaharlar.items())[:4]
            bolaklar.append(
                "Auditoriya: " + ", ".join(f"{nom} {_son(soni)}" for nom, soni in eng)
            )

    if natija.get("umumiy_baho"):
        bolaklar.append("")
        bolaklar.append(natija["umumiy_baho"])

    turlar = natija.get("kontent_turlari") or []
    if turlar:
        bolaklar.append("")
        bolaklar.append("Kontent turlari: " + qisqartir(turlar, 6))

    ishlagan = natija.get("ishlagan_postlar") or []
    if ishlagan:
        bolaklar.append("")
        bolaklar.append("Eng yaxshi ishlagan postlar:")
        for i, post in enumerate(ishlagan[:5], 1):
            if not isinstance(post, dict):
                continue
            bolaklar.append(
                f"{i}. {_son(post.get('korishlar'))} ko'rish · "
                f"{_son(post.get('layklar'))} layk · {post.get('sana', '')}"
            )
            if post.get("hook"):
                bolaklar.append(f"   Hook: {post['hook']}")
            if post.get("nega_ishladi"):
                bolaklar.append(f"   {post['nega_ishladi']}")
            if post.get("havola"):
                bolaklar.append(f"   {post['havola']}")

    hooklar = natija.get("hook_naqshlari") or []
    if hooklar:
        bolaklar.append("")
        bolaklar.append("Hook naqshlari (sarlavha matni bo'yicha):")
        for h in hooklar[:5]:
            if not isinstance(h, dict):
                continue
            bolaklar.append(f"• {h.get('naqsh')}")
            if h.get("misol"):
                bolaklar.append(f"   misol: {h['misol'][:120]}")
            if h.get("izoh"):
                bolaklar.append(f"   {h['izoh']}")

    muammolar = natija.get("komment_muammolari") or []
    if muammolar:
        bolaklar.append("")
        bolaklar.append("Kommentlarda takrorlanadigan mavzular:")
        for m in muammolar[:6]:
            if not isinstance(m, dict):
                continue
            marta = f" ({m['necha_marta']} marta)" if m.get("necha_marta") else ""
            bolaklar.append(f"• {m.get('mavzu')}{marta}")
            if m.get("izoh"):
                bolaklar.append(f"   {m['izoh']}")

    tavsiyalar = natija.get("tavsiyalar") or []
    if tavsiyalar:
        bolaklar.append("")
        bolaklar.append("Tavsiyalar:")
        bolaklar.extend(f"{i}. {t}" for i, t in enumerate(tavsiyalar[:6], 1))

    cheklovlar = natija.get("cheklovlar") or []
    if cheklovlar:
        bolaklar.append("")
        bolaklar.extend(f"ℹ️ {c}" for c in cheklovlar[:3])

    return _qator(bolaklar)


# --- Aziza (kp-tracker) ------------------------------------------------------

_KP_HOLAT = {
    "yuborildi": "javob kutilmoqda",
    "javob_keldi": "javob keldi",
    "shartnoma": "shartnoma",
    "rad_etildi": "rad etildi",
}


def kp_kuzatuvi(natija: dict[str, Any]) -> str:
    # Holat o'zgartirilgan bo'lsa — qisqa tasdiq.
    ozgardi = natija.get("ozgardi") or {}
    if ozgardi:
        bolaklar = [
            f"{ozgardi.get('raqam')} — "
            f"{_KP_HOLAT.get(ozgardi.get('holat'), ozgardi.get('holat'))}"
        ]
        if ozgardi.get("izoh"):
            bolaklar.append(ozgardi["izoh"])
    else:
        bolaklar = ["KP kuzatuvi", ""]

    jami = natija.get("jami", 0)
    if not jami:
        return _qator(bolaklar + ["", "Hali birorta KP kuzatuvga tushmagan."])

    holatlar = natija.get("holatlar") or {}
    bolaklar.append("")
    bolaklar.append(
        f"Jami: {jami} ta · Konversiya: {natija.get('konversiya', 0)}%"
    )
    if holatlar:
        bolaklar.append(
            " · ".join(
                f"{_KP_HOLAT.get(h, h)}: {s}" for h, s in holatlar.items()
            )
        )
    if natija.get("shartnoma_summasi"):
        bolaklar.append(
            f"Shartnomalar summasi: {_son(natija['shartnoma_summasi'])} so'm"
        )

    etibor = natija.get("etibor_kerak") or []
    if etibor:
        bolaklar.append("")
        bolaklar.append("E'tibor kerak:")
        for e in etibor[:8]:
            if not isinstance(e, dict):
                continue
            mijoz = f" — {e['mijoz']}" if e.get("mijoz") else ""
            bolaklar.append(
                f"• {e.get('raqam')}{mijoz} · {e.get('kun', 0)} kun"
            )
            if e.get("nega"):
                bolaklar.append(f"  {e['nega']}")

    if natija.get("xulosa"):
        bolaklar.append("")
        bolaklar.append(natija["xulosa"])

    tavsiyalar = natija.get("tavsiyalar") or []
    if tavsiyalar:
        bolaklar.append("")
        bolaklar.append("Tavsiyalar:")
        bolaklar.extend(f"{i}. {t}" for i, t in enumerate(tavsiyalar[:5], 1))

    return _qator(bolaklar)


# --- Rustam (hvac-calc) ------------------------------------------------------


def ventilyatsiya_hisobi(natija: dict[str, Any]) -> str:
    bolaklar = ["Ventilyatsiya hisobi"]
    if natija.get("obyekt"):
        bolaklar.append(natija["obyekt"])
    bolaklar.append("")

    for xona in (natija.get("xonalar") or []):
        if not isinstance(xona, dict):
            continue
        bolaklar.append(f"▸ {xona.get('nomi')} ({xona.get('turi')})")
        bolaklar.append(
            f"   {xona.get('maydon')} m² × {xona.get('balandlik')} m "
            f"= {xona.get('hajm')} m³"
            + (f", {xona['odamlar']} kishi" if xona.get("odamlar") else "")
        )
        if xona.get("havo_sarfi"):
            bolaklar.append(
                f"   Havo sarfi: {_son(xona['havo_sarfi'])} m³/soat "
                f"({xona.get('usul')} bo'yicha)"
            )
            bolaklar.append(
                f"   Kanal: Ø{xona.get('diametr')} mm · "
                f"tezlik {xona.get('tezlik')} m/s"
            )
        else:
            bolaklar.append("   O'lcham yetishmaydi — hisoblanmadi")

    if natija.get("jami_sarf"):
        bolaklar.append("")
        bolaklar.append(
            f"Jami: {_son(natija['jami_sarf'])} m³/soat"
            + (f" · magistral Ø{natija['umumiy_diametr']} mm"
               if natija.get("umumiy_diametr") else "")
        )

    uskunalar = natija.get("uskunalar") or []
    if uskunalar:
        bolaklar.append("")
        bolaklar.append("Katalogdan mos o'lcham:")
        for u in uskunalar:
            if not isinstance(u, dict) or not u.get("modellar"):
                continue
            bolaklar.append(
                f"• Ø{u['diametr']}: " + qisqartir(u["modellar"], 6)
            )
        bolaklar.append(
            "  (moslik diametr bo'yicha — quvvatni pasportdan tekshiring)"
        )

    sorash = natija.get("sorash_kerak") or []
    if sorash:
        bolaklar.append("")
        bolaklar.append("Aniqlashtirish kerak:")
        bolaklar.extend(f"• {x}" for x in sorash[:5])

    ogoh = natija.get("ogohlantirishlar") or []
    if ogoh:
        bolaklar.append("")
        bolaklar.extend(f"⚠️ {x}" for x in ogoh[:5])

    eslatmalar = natija.get("eslatmalar") or []
    if eslatmalar:
        bolaklar.append("")
        bolaklar.extend(f"ℹ️ {x}" for x in eslatmalar[:3])

    return _qator(bolaklar)


# --- reyestr -----------------------------------------------------------------

KORINISHLAR: dict[str, Callable[[dict[str, Any]], str]] = {
    "product-spec": mahsulot_spetsifikatsiyasi,
    "price-monitor": narxlar,
    "competitor-watch": raqobat,
    "marketing": kampaniya,
    "sales-strategy": savdo,
    "proposal-builder": tijorat_taklifi,
    "data-query": malumot,
    "hr-assist": hr,
    "legal-review": huquqiy,
    "catalog-admin": katalog,
    "tender-watch": tenderlar,
    "smm-analyst": smm,
    "kp-tracker": kp_kuzatuvi,
    "hvac-calc": ventilyatsiya_hisobi,
    "montaj-guide": montaj,
}


def agent_matni(rol: str, natija: dict[str, Any]) -> str:
    """Agent natijasini o'qish uchun qulay matnga aylantiradi."""
    if not natija:
        return ""
    # Sardorning ikki rejimi bor. Bo'sh `variantlar` ham TANLOV natijasi —
    # "mos mahsulot topilmadi" javobi spesifikatsiya ko'rinishida chiqmasin.
    if rol == "product-spec" and natija.get("rejim") == "tanlov":
        return mahsulot_tanlovi(natija)
    korinish = KORINISHLAR.get(rol)
    return korinish(natija) if korinish else natija_matni(natija)

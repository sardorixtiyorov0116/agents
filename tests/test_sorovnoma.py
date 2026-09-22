"""So'rovnoma (oprosniy list) — mijozlar botidagi bo'limlar.

NEGA BU TESTLAR BOR
-------------------
Zavodning 12 ta oprosniy listi bor va ular mijozga TELEGRAM orqali
beriladi. Ikkita joyda xato qimmatga tushadi:

1. SHARTLI VARIANTLAR. F5-F9 tozalash klassi FAQAT ФЯК filtrida bor.
   ФЯГ tanlagan mijozga uni ko'rsatsak, u tanlab qo'yadi va menejerga
   ishlab chiqarib BO'LMAYDIGAN buyurtma tushadi — buni faqat zavodda
   sezishardi.

2. TA'RIF FAYLI. Savollar YAML da yozilgan va uni muhandis tahrirlaydi.
   Buzuq ta'rif jimgina o'tib ketmasligi kerak: noma'lum tekshiruv nomi
   yozilsa, so'rovnoma ishlamay qolgandan ko'ra darhol xato bergani
   yaxshi.
"""

from __future__ import annotations

import pytest

from kp.shakl import ShaklXatosi
from sorovnoma import SorovnomaShakli, bolim, bolimlar, fayl_yoli
from sorovnoma import oqim


# --- Ta'rif fayli -------------------------------------------------------------


def test_bolimlar_yuklanadi():
    kalitlar = [b.kalit for b in bolimlar()]

    assert "ventilyator" in kalitlar
    assert "panjara" in kalitlar
    assert "filtr" in kalitlar


def test_har_bolimda_savol_bor():
    for b in bolimlar():
        assert b.savollar, f"{b.kalit} bo'limida savol yo'q"


def test_har_bolimda_nom_va_belgi_bor():
    """Tugma yorlig'i shu ikkisidan yasaladi."""
    for b in bolimlar():
        assert b.nomi and b.belgi


def test_oprosniy_list_fayllari_JOYIDA():
    """Fayl yo'q bo'lsa «faylni yuborish» tugmasi ishlamaydi."""
    yoqlar = [b.kalit for b in bolimlar() if fayl_yoli(b) is None]

    assert yoqlar == [], f"fayl topilmadi: {yoqlar}"


def test_notanish_tekshiruv_DARHOL_xato_beradi():
    """Buzuq YAML jimgina o'tib ketmasin."""
    from sorovnoma.talab import _savol

    with pytest.raises(ValueError, match="noma'lum tekshiruv"):
        _savol({"kalit": "x", "matn": "?", "tekshir": "yoq_bunday"}, {})


def test_notanish_bolim_None_qaytaradi():
    assert bolim("yoq_bunday_bolim") is None


# --- Shartli savollar va variantlar -------------------------------------------


def test_FYAK_da_F_klasslari_BOR():
    s = SorovnomaShakli("filtr")
    s.javob_ber("ФЯК")

    klasslar = [t.qiymat for t in s.joriy().tanlovlar]

    assert klasslar == ["G3", "G4", "F5", "F6", "F7", "F8", "F9"]


def test_FYAG_da_F_klasslari_YOQ():
    """Zavod hujjatida F5-F9 «только для ФЯК» deb yozilgan."""
    s = SorovnomaShakli("filtr")
    s.javob_ber("ФЯГ")

    klasslar = [t.qiymat for t in s.joriy().tanlovlar]

    assert klasslar == ["G3", "G4"]


def test_FYAK_da_chontak_savollari_beriladi():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592"):
        s.javob_ber(javob)

    assert s.joriy().kalit == "chontak_uzunligi"


def test_FYAG_da_chontak_savollari_BERILMAYDI():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯГ", "G4", "400x400"):
        s.javob_ber(javob)

    assert s.joriy().kalit == "ramka"


def test_FYAK_da_ramka_savoli_BERILMAYDI():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592", "500", "6"):
        s.javob_ber(javob)

    assert s.joriy().kalit == "iqlim"


# --- Hisoblagich --------------------------------------------------------------


def test_hisoblagich_ORQAGA_sakramaydi():
    """«1/5» dan «2/7» ga o'tish mijozga savol ko'paygandek tuyuladi.

    Shart hal bo'lmaguncha UZUNROQ tarmoq uzunligi ko'rsatiladi.
    """
    s = SorovnomaShakli("filtr")
    jamilar = []
    for javob in ("ФЯК", "F7", "592x592", "500", "6", "У", "12"):
        jamilar.append(s.qadam()[1])
        s.javob_ber(javob)

    assert jamilar == sorted(jamilar, reverse=True) or len(set(jamilar)) == 1
    assert jamilar[0] == 7


def test_qisqa_tarmoqda_jami_KAMAYADI():
    s = SorovnomaShakli("filtr")
    boshlangich = s.qadam()[1]
    s.javob_ber("ФЯГ")

    assert boshlangich == 7
    assert s.qadam()[1] == 6


# --- Javob berish -------------------------------------------------------------


def test_tugmali_savolga_NOTOGRI_qiymat_rad_etiladi():
    s = SorovnomaShakli("filtr")

    with pytest.raises(ShaklXatosi):
        s.javob_ber("YOQ_BUNDAY")


def test_son_tekshiruvi_matnni_rad_etadi():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592"):
        s.javob_ber(javob)

    with pytest.raises(ShaklXatosi):
        s.javob_ber("uzun")


def test_manfiy_son_rad_etiladi():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592"):
        s.javob_ber(javob)

    with pytest.raises(ShaklXatosi):
        s.javob_ber("-5")


def test_otkazsa_boladigan_savol_otkaziladi():
    s = SorovnomaShakli("ventilyator")
    s.javob_ber("ichkarida")

    s.otkaz()                                  # turi — otkazsa_boladi: true

    assert s.javoblar["turi"] == ""


def test_MAJBURIY_savolni_otkazib_bolmaydi():
    s = SorovnomaShakli("filtr")

    with pytest.raises(ShaklXatosi):
        s.otkaz()                              # turi — majburiy


def test_orqaga_oxirgi_javobni_ochiradi():
    s = SorovnomaShakli("filtr")
    s.javob_ber("ФЯК")
    s.javob_ber("F7")

    assert s.orqaga() is True
    assert s.joriy().kalit == "klass"


def test_boshida_orqaga_qaytib_bolmaydi():
    assert SorovnomaShakli("filtr").orqaga() is False


def test_shart_ozgarsa_savollar_QAYTA_hisoblanadi():
    """ФЯК dan ФЯГ ga o'tilsa, cho'ntak savollari yo'qolishi kerak."""
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592", "500"):
        s.javob_ber(javob)

    # Boshiga qaytib turini almashtiramiz.
    while s.orqaga():
        pass
    s.javob_ber("ФЯГ")
    s.javob_ber("G4")
    s.javob_ber("400x400")

    assert s.joriy().kalit == "ramka"
    assert "chontak_uzunligi" not in [x.kalit for x in s._kerakli()]


# --- Ko'rinish ----------------------------------------------------------------


def test_hamma_bolim_TUGMADA_bor():
    """Nomlar tugmalarda — matnda takrorlanmaydi.

    Ilgari menyu matnida 12 ta bo'lim tavsifi bilan sanalardi va
    ostidan yana 12 ta tugma chiqardi: bir xil ro'yxat ikki marta,
    telefon ekranini to'ldirib.
    """
    yorliqlar = [t.text for qator in oqim.bolimlar_tugmalari().inline_keyboard
                 for t in qator]

    for b in bolimlar():
        assert any(b.nomi in y for y in yorliqlar), b.kalit


def test_menyu_matni_QISQA():
    """Telefon ekraniga sig'sin — tugmalar allaqachon uzun ro'yxat."""
    matn = oqim.bolimlar_matni()

    assert len(matn.splitlines()) <= 6
    assert "Qaysi uskuna kerak" in matn


def test_savol_matnida_variant_izohlari_bor():
    """Mijoz ФЯК nima ekanini bilmasligi mumkin."""
    matn = oqim.savol_matni(SorovnomaShakli("filtr"))

    assert "ФЯК" in matn
    assert "cho'ntakli" in matn


def test_natijada_son_ORTIQCHA_kasrsiz():
    """`son` tekshiruvi float qaytaradi — mijoz «500» yozgan edi."""
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592", "500", "6", "У", "12"):
        s.javob_ber(javob)

    matn = oqim.natija_matni(s)

    assert "500" in matn
    assert "500.0" not in matn


def test_menejer_xabarida_ALOQA_YOQLIGI_aytiladi():
    """Aloqasiz so'rovnoma — menejer bog'lana olmaydi va buni bilishi shart."""
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592", "500", "6", "У", "12"):
        s.javob_ber(javob)

    matn = oqim.menejer_matni(s, ism="Jasur", aloqa="", tg_id=1)

    assert "Aloqa qoldirilmagan" in matn


def test_menejer_xabarida_aloqa_bolsa_ogohlantirish_YOQ():
    s = SorovnomaShakli("filtr")
    for javob in ("ФЯК", "F7", "592x592", "500", "6", "У", "12"):
        s.javob_ber(javob)

    matn = oqim.menejer_matni(s, ism="Jasur", aloqa="+998901112233", tg_id=1)

    assert "Aloqa qoldirilmagan" not in matn
    assert "+998901112233" in matn


def test_tugmalarda_bekor_va_fayl_bor():
    shakl = SorovnomaShakli("filtr")

    tugmalar = oqim.tugmalar(shakl).inline_keyboard
    hamma = [t.callback_data for qator in tugmalar for t in qator]

    assert any(oqim.FAYL in d for d in hamma)
    assert any(oqim.BEKOR in d for d in hamma)


def test_birinchi_savolda_ORQAGA_tugmasi_YOQ():
    shakl = SorovnomaShakli("filtr")

    tugmalar = oqim.tugmalar(shakl).inline_keyboard
    hamma = [t.callback_data for qator in tugmalar for t in qator]

    assert not any(oqim.ORQAGA in d for d in hamma)


def test_ikkinchi_savolda_ORQAGA_tugmasi_BOR():
    shakl = SorovnomaShakli("filtr")
    shakl.javob_ber("ФЯК")

    tugmalar = oqim.tugmalar(shakl).inline_keyboard
    hamma = [t.callback_data for qator in tugmalar for t in qator]

    assert any(oqim.ORQAGA in d for d in hamma)


def test_tugma_yorliglari_TELEGRAM_chegarasiga_sigadi():
    """Telegram inline tugma yorlig'i 64 bayt; biz 32 belgi bilan cheklaymiz."""
    for b in bolimlar():
        shakl = SorovnomaShakli(b.kalit)
        for savol in b.savollar:
            for tanlov in savol.tanlovlar:
                assert len(tanlov.yorliq[:oqim.YORLIQ_UZUNLIGI]) <= 32


def test_callback_data_TELEGRAM_chegarasiga_sigadi():
    """`callback_data` 64 BAYT — kirilcha harf 2 bayt egallaydi."""
    for b in bolimlar():
        for savol in b.savollar:
            for tanlov in savol.tanlovlar:
                malumot = f"{oqim.TUGMA_OLDI}{savol.kalit}:{tanlov.qiymat}"
                assert len(malumot.encode("utf-8")) <= 64, malumot


# --- Fayl formati -------------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-27): fayllar zavoddan eski `.doc` formatida
# kelgan edi. Yuborish ishlardi, lekin mijoz to'ldirib QAYTARSA biz uni
# o'qiy olmasdik — `kp/tz.py` `.doc` ni bilmaydi. Hammasi `.docx` ga
# o'girildi.


def test_hamma_fayl_OQILADIGAN_formatda():
    from kp.tz import QOLLAB_QUVVATLANADI

    for b in bolimlar():
        yol = fayl_yoli(b)
        assert yol is not None, b.kalit
        assert yol.suffix.lower() in QOLLAB_QUVVATLANADI, (
            f"{b.kalit}: {yol.suffix} o'qilmaydi")


def test_fayllar_HAQIQATAN_ochiladi():
    """Format to'g'ri bo'lishi yetarli emas — fayl buzuq bo'lishi mumkin."""
    from kp.tz import matn_ol

    for b in bolimlar():
        matn = matn_ol(fayl_yoli(b))
        assert len(matn) > 200, f"{b.kalit}: matn juda qisqa"
        assert "ОПРОСНЫЙ" in matn.upper() or "ОПРОСНЫЙ ЛИСТ" in matn.upper()


def test_eski_doc_fayllari_QOLMAGAN():
    from sorovnoma.talab import SOROVNOMA_PAPKASI

    qolgan = list(SOROVNOMA_PAPKASI.glob("*.doc"))

    assert qolgan == [], f"o'girilmagan fayl: {qolgan}"


# --- Hamma bo'lim (12 ta) -----------------------------------------------------
#
# Bo'limlar YAML da yozilgani uchun xato TESTSIZ sezilmaydi: buzuq
# bo'lim mijoz uni TANLAGANDA yiqiladi, ya'ni jonli suhbat o'rtasida.
# Quyidagilar har bo'limni oxirigacha bosib chiqadi.

BOLIM_SONI = 12


def test_hamma_oprosniy_list_ulangan():
    """Zavodda 12 ta oprosniy list bor — hammasi bo'limga aylangan."""
    assert len(bolimlar()) == BOLIM_SONI


def _oxirigacha(kalit: str, maks: int = 40):
    """Bo'limni oxirigacha to'ldiradi. Tugamasa `None`."""
    s = SorovnomaShakli(kalit)
    for _ in range(maks):
        if s.tugadimi():
            return s
        savol = s.joriy()
        if savol.tanlovlar:
            s.javob_ber(savol.tanlovlar[0].qiymat)
        elif savol.otkazsa_boladi:
            s.otkaz()
        elif savol.tekshir:
            s.javob_ber("100")
        else:
            s.javob_ber("matn")
    return s if s.tugadimi() else None


@pytest.mark.parametrize("kalit", [b.kalit for b in bolimlar()])
def test_bolim_OXIRIGACHA_toldiriladi(kalit):
    """Halqaga tushib qolgan yoki javob qabul qilmaydigan savol bo'lmasin."""
    assert _oxirigacha(kalit) is not None, f"{kalit}: so'rovnoma tugamadi"


@pytest.mark.parametrize("kalit", [b.kalit for b in bolimlar()])
def test_har_bolimda_MIQDOR_soraladi(kalit):
    """Miqdorsiz KP tuzib bo'lmaydi — har oprosniy listda «Количество, шт» bor."""
    kalitlar = [s.kalit for s in bolim(kalit).savollar]

    assert "soni" in kalitlar, f"{kalit}: miqdor savoli yo'q"


@pytest.mark.parametrize("kalit", [b.kalit for b in bolimlar()])
def test_miqdor_OXIRGI_savol(kalit):
    """Miqdor oxirida turishi kerak — mijoz avval nima kerakligini aytadi."""
    assert bolim(kalit).savollar[-1].kalit == "soni"


def test_callback_data_HAMMA_bolimda_chegaraga_sigadi():
    """`callback_data` 64 BAYT — kirilcha harf 2 bayt egallaydi."""
    uzunlar = []
    for b in bolimlar():
        for savol in b.savollar:
            for tanlov in savol.tanlovlar:
                malumot = f"{oqim.TUGMA_OLDI}{savol.kalit}:{tanlov.qiymat}"
                if len(malumot.encode("utf-8")) > 64:
                    uzunlar.append(malumot)

    assert uzunlar == []


def test_tugma_yorliqlari_KESILMAYDI():
    """32 belgidan uzun yorliq so'z o'rtasidan kesilardi."""
    uzunlar = [t.yorliq for b in bolimlar() for s in b.savollar
               for t in s.tanlovlar if len(t.yorliq) > oqim.YORLIQ_UZUNLIGI]

    assert uzunlar == []


def test_bolim_kalitlari_TAKRORLANMAYDI():
    kalitlar = [b.kalit for b in bolimlar()]

    assert len(kalitlar) == len(set(kalitlar))


def test_savol_kalitlari_bolim_ICHIDA_takrorlanmaydi():
    """Takrorlangan kalit ikkinchi savolni jimgina yutib yuborardi."""
    for b in bolimlar():
        kalitlar = [s.kalit for s in b.savollar]
        assert len(kalitlar) == len(set(kalitlar)), b.kalit


def test_shart_HAQIQIY_kalitga_ishora_qiladi():
    """Xato yozilgan shart savolni MANGU yashirib qo'yardi."""
    import yaml
    from pathlib import Path

    from app.config import sozlama

    xom = yaml.safe_load(
        (Path(sozlama().bilim_yoli) / "product" / "sorovnoma.yaml")
        .read_text(encoding="utf-8"))

    for kalit, bolim_xom in xom["bolimlar"].items():
        savollar = bolim_xom.get("savollar") or []
        mavjud = {s["kalit"] for s in savollar}
        for s in savollar:
            shart = s.get("shart") or {}
            if shart:
                assert shart["kalit"] in mavjud, f"{kalit}.{s['kalit']}"
            shart_kalit = s.get("shart_kalit")
            if shart_kalit:
                assert shart_kalit in mavjud, f"{kalit}.{s['kalit']}"


def test_nom_qolipi_HAQIQIY_kalitlarga_ishora_qiladi():
    """Xato kalit yozilsa model nomi jimgina qisqarib ketardi."""
    from sorovnoma.kp_loyiha import _qolip_kalitlari

    for b in bolimlar():
        if not b.nom_qolipi:
            continue
        mavjud = {s.kalit for s in b.savollar}
        for kalit in _qolip_kalitlari(b.nom_qolipi):
            assert kalit in mavjud, f"{b.kalit}: nom_qolipi -> {kalit}"


# --- Bosma listdagi ASL atamalar ----------------------------------------------
#
# JONLI E'TIROZ (2026-08-28): atamalar o'zbekchaga tarjima qilingandi
# («Bino ichida», «Radial», «plastinali») va loyihachi ularni tanimay
# qoldi — u BOSMA oprosniy list bilan ishlaydi, u yerda «В помещении»,
# «Радиальный», «Пластинчатые» deb yozilgan.
#
# Endi mijoz ko'radigan yorliq — ASL rus atamasi, o'zbekchasi esa
# izohda. Savol yonida bosma listdagi nomi ham turadi.


def test_savollarda_ASL_nom_bor():
    """Muhandis bosma list bilan 1:1 solishtira olsin."""
    aslsiz = [(b.kalit, s.kalit) for b in bolimlar() for s in b.savollar
              if not s.asl]

    assert aslsiz == [], f"asl nomi yo'q: {aslsiz[:5]}"


def test_asl_nom_savol_matnida_KORINADI():
    from sorovnoma import SorovnomaShakli

    matn = oqim.savol_matni(SorovnomaShakli("ventilyator"))

    assert "Место установки вентилятора" in matn


@pytest.mark.parametrize("bolim_kaliti,kutilgan", [
    ("ventilyator", "В помещении"),
    ("ventilyator", "Радиальный"),
    ("panjara", "с КРВ"),
    ("kckp", "Приточная"),
    ("chiller", "Тепловой насос"),
])
def test_yorliq_ASL_atamada(bolim_kaliti, kutilgan):
    yorliqlar = [t.yorliq for s in bolim(bolim_kaliti).savollar
                 for t in s.tanlovlar]

    assert kutilgan in yorliqlar


def test_ichki_KALIT_qisqa_qoladi():
    """`callback_data` 64 BAYT — kirillcha harf 2 bayt egallaydi.

    Yorliq ruscha bo'lgani bilan kalit lotincha va qisqa bo'lishi
    kerak, aks holda uzun atamalar chegaradan oshib ketardi
    («Крышной осевой подпора воздуха» = 58 bayt).
    """
    uzunlar = []
    for b in bolimlar():
        for s in b.savollar:
            for t in s.tanlovlar:
                malumot = f"{oqim.TUGMA_OLDI}{s.kalit}:{t.qiymat}"
                if len(malumot.encode("utf-8")) > 64:
                    uzunlar.append(malumot)

    assert uzunlar == []


def test_ozbekcha_izoh_SAQLANADI():
    """Atama ruscha bo'lsa ham, bilmaydigan mijozga tushuntirish kerak."""
    tanlovlar = [t for s in bolim("ventilyator").savollar for t in s.tanlovlar]
    joy = [t for t in tanlovlar if t.yorliq == "В помещении"]

    assert joy and joy[0].izoh


def test_yorliqlarda_LOTINCHA_atama_qolmagan():
    """Texnik atama BOSMA LISTDAGIDEK bo'lishi kerak.

    «Radial», «plastinali», «Suvli (ВНВ)» — bular tarjima edi va
    loyihachi ularni tanimasdi. U bosma list bilan ishlaydi.

    Model kodlari (DVS, RSK) va o'lchov birliklari chetlab o'tiladi —
    ular asl holida lotincha.
    """
    import re

    CHETLAB = {"DVS / DVS-P", "КО / RSK", "РВР-1 / РВР-2", "4РВП"}
    lotinchalar = []
    for b in bolimlar():
        for s in b.savollar:
            for t in s.tanlovlar:
                if t.yorliq in CHETLAB:
                    continue
                # 3+ lotincha harfdan iborat so'z — tarjima qoldig'i.
                if re.search(r"[a-z]{3,}", t.yorliq):
                    lotinchalar.append(f"{b.kalit}.{s.kalit}: {t.yorliq}")

    assert lotinchalar == [], f"tarjima qolgan: {lotinchalar[:6]}"


def test_uzun_atama_izohga_KOCHADI():
    """Tugma 32 belgi — «клапан противопожарный универсальный» sig'maydi.

    Yorliqda qisqa belgi («КПУ»), izohda to'liq nomi qoladi.
    """
    tanlovlar = [t for s in bolim("yongin_klapani").savollar for t in s.tanlovlar]
    kpu = [t for t in tanlovlar if t.yorliq == "КПУ"]

    assert kpu, "КПУ topilmadi"
    assert "противопожарный" in kpu[0].izoh

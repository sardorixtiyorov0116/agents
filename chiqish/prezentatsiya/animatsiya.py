"""PowerPoint slaydiga animatsiya qo'shish.

NEGA QO'LDA XML
---------------
`python-pptx` animatsiyani qo'llab-quvvatlamaydi. Shuning uchun
slayd XML'iga `<p:timing>` bloki to'g'ridan-to'g'ri yoziladi — bu
PowerPoint'ning o'z formati, hech qanday qo'shimcha dastur kerak emas.

QANDAY ISHLAYDI
---------------
Har bir shakl uchun "paydo bo'lish" (entrance) effekti qo'shiladi:
avval ko'rinmas, keyin belgilangan vaqtda suzib chiqadi. Effektlar
ketma-ket, avtomatik ishlaydi — slayd ochilishi bilan rolik o'zi
o'ynaydi, sichqoncha bosish shart emas.

    presetID=10  -> Fade      (yumshoq paydo bo'lish)
    presetID=2   -> Fly In    (chetdan suzib kirish)
    presetID=53  -> Zoom      (kattalashib paydo bo'lish)
"""

from __future__ import annotations

from copy import deepcopy

from lxml import etree

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"p": P}


def _t(nom: str) -> str:
    return f"{{{P}}}{nom}"


# Effekt turlari: (presetID, presetClass, presetSubtype, filtr)
EFFEKTLAR = {
    "fade":  (10, "entr", 0, "fade"),
    "chap":  (2, "entr", 4, "wipe(right)"),     # chapdan suzib kiradi
    "past":  (2, "entr", 1, "wipe(up)"),        # pastdan ko'tariladi
    "kat":   (53, "entr", 16, "fade"),          # kattalashadi
}


class _Raqamlagich:
    """Timing daraxtidagi id'lar takrorlanmasligi kerak."""

    def __init__(self, boshlanish: int = 3):
        self.n = boshlanish

    def keyingi(self) -> int:
        self.n += 1
        return self.n


def _qadam(shakl_id: int, kechikish_ms: int, tur: str, davomiyligi: int,
           raqam: _Raqamlagich) -> etree._Element:
    """Bitta shakl uchun bitta effekt tugunini yasaydi."""
    preset, sinf, quyi, filtr = EFFEKTLAR[tur]

    tashqi = etree.SubElement(etree.Element(_t("bosh")), _t("par"))
    ct1 = etree.SubElement(tashqi, _t("cTn"))
    ct1.set("id", str(raqam.keyingi()))
    ct1.set("fill", "hold")
    st1 = etree.SubElement(ct1, _t("stCondLst"))
    etree.SubElement(st1, _t("cond")).set("delay", "0")
    ch1 = etree.SubElement(ct1, _t("childTnLst"))

    ichki = etree.SubElement(ch1, _t("par"))
    ct2 = etree.SubElement(ichki, _t("cTn"))
    ct2.set("id", str(raqam.keyingi()))
    ct2.set("fill", "hold")
    st2 = etree.SubElement(ct2, _t("stCondLst"))
    etree.SubElement(st2, _t("cond")).set("delay", "0")
    ch2 = etree.SubElement(ct2, _t("childTnLst"))

    effekt = etree.SubElement(ch2, _t("par"))
    ct3 = etree.SubElement(effekt, _t("cTn"))
    ct3.set("id", str(raqam.keyingi()))
    ct3.set("presetID", str(preset))
    ct3.set("presetClass", sinf)
    ct3.set("presetSubtype", str(quyi))
    ct3.set("fill", "hold")
    ct3.set("nodeType", "afterEffect")     # oldingisidan keyin — avtomatik
    st3 = etree.SubElement(ct3, _t("stCondLst"))
    etree.SubElement(st3, _t("cond")).set("delay", str(kechikish_ms))
    ch3 = etree.SubElement(ct3, _t("childTnLst"))

    # 1) shaklni ko'rinadigan qilamiz
    qoy = etree.SubElement(ch3, _t("set"))
    cb = etree.SubElement(qoy, _t("cBhvr"))
    ct4 = etree.SubElement(cb, _t("cTn"))
    ct4.set("id", str(raqam.keyingi()))
    ct4.set("dur", "1")
    ct4.set("fill", "hold")
    st4 = etree.SubElement(ct4, _t("stCondLst"))
    etree.SubElement(st4, _t("cond")).set("delay", "0")
    tgt = etree.SubElement(cb, _t("tgtEl"))
    etree.SubElement(tgt, _t("spTgt")).set("spid", str(shakl_id))
    anl = etree.SubElement(cb, _t("attrNameLst"))
    an = etree.SubElement(anl, _t("attrName"))
    an.text = "style.visibility"
    to = etree.SubElement(qoy, _t("to"))
    etree.SubElement(to, _t("strVal")).set("val", "visible")

    # 2) effektning o'zi
    ae = etree.SubElement(ch3, _t("animEffect"))
    ae.set("transition", "in")
    ae.set("filter", filtr)
    cb2 = etree.SubElement(ae, _t("cBhvr"))
    ct5 = etree.SubElement(cb2, _t("cTn"))
    ct5.set("id", str(raqam.keyingi()))
    ct5.set("dur", str(davomiyligi))
    tgt2 = etree.SubElement(cb2, _t("tgtEl"))
    etree.SubElement(tgt2, _t("spTgt")).set("spid", str(shakl_id))

    return tashqi


def animatsiya_qo_sh(slayd, qadamlar) -> None:
    """Slaydga avtomatik ishlaydigan animatsiya ketma-ketligini qo'shadi.

    `qadamlar` — (shakl, kechikish_ms, tur) uchliklari ro'yxati.
    `tur`: "fade" | "chap" | "past" | "kat".
    """
    if not qadamlar:
        return

    raqam = _Raqamlagich()
    timing = etree.SubElement(slayd._element, _t("timing"))
    tnLst = etree.SubElement(timing, _t("tnLst"))
    par = etree.SubElement(tnLst, _t("par"))

    ildiz = etree.SubElement(par, _t("cTn"))
    ildiz.set("id", "1")
    ildiz.set("dur", "indefinite")
    ildiz.set("restart", "never")
    ildiz.set("nodeType", "tmRoot")
    ildiz_ch = etree.SubElement(ildiz, _t("childTnLst"))

    seq = etree.SubElement(ildiz_ch, _t("seq"))
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")
    ct = etree.SubElement(seq, _t("cTn"))
    ct.set("id", "2")
    ct.set("dur", "indefinite")
    ct.set("nodeType", "mainSeq")
    ct_ch = etree.SubElement(ct, _t("childTnLst"))

    for shakl, kechikish, tur in qadamlar:
        ct_ch.append(_qadam(shakl.shape_id, kechikish, tur, 500, raqam))

    # Slaydni bosib o'tish shartlari — busiz PowerPoint animatsiyani
    # boshqarolmaydi va namoyishda oldinga o'tib bo'lmay qoladi.
    oldingi = etree.SubElement(seq, _t("prevCondLst"))
    c1 = etree.SubElement(oldingi, _t("cond"))
    c1.set("evt", "onPrev")
    c1.set("delay", "0")
    etree.SubElement(etree.SubElement(c1, _t("tgtEl")), _t("sldTgt"))

    keyingi = etree.SubElement(seq, _t("nextCondLst"))
    c2 = etree.SubElement(keyingi, _t("cond"))
    c2.set("evt", "onNext")
    c2.set("delay", "0")
    etree.SubElement(etree.SubElement(c2, _t("tgtEl")), _t("sldTgt"))

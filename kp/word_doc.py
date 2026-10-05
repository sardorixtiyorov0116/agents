"""Eski Word (.doc, Word 97–2003) — matn va jadvallar, sof Python.

NEGA KERAK
----------
Mijozlar TZ ni ko'pincha eski .doc da yuboradi; Jihozvent so'rovnoma
varaqalari ham .doc (opros listlar, 2026-10-03). Ilgari bot «.doc formati
o'qilmaydi» derdi. Serverda Word ham, LibreOffice ham yo'q — shuning uchun
format bevosita o'qiladi (`olefile` — OLE konteyner).

FORMAT (MS-DOC, qisqacha)
-------------------------
  * `WordDocument` oqimi boshida FIB: qaysi jadval oqimi (`0Table` /
    `1Table`) va undagi `Clx` (bo'laklar jadvali) qayerda.
  * `Clx` -> `PlcPcd`: matn BO'LAKLARGA bo'lingan; har bo'lak yo UTF-16,
    yo «siqilgan» 8-bitli (cp1252) matn.
  * Paragraf oxiri `\\r`, katak oxiri `\\x07`. Jadval qatori: har katak
    `\\x07` bilan tugaydi va qator oxirida yana bitta `\\x07` (qator belgisi).

QATOR CHEGARASI. Bo'sh katak ham «\\x07» beradi, shuning uchun «\\x07\\x07»
qator oxirimi yoki bo'sh katakmi — matnning o'zidan bilinmaydi. Ustunlar soni
TANLANADI: har (n+1)-belgi bo'sh bo'lgan eng kichik n. Word bilan
solishtirib sinaldi (tests/test_hujjat_turlari.py).
"""

from __future__ import annotations

import re
import struct
from pathlib import Path


class DocXatosi(ValueError):
    """.doc o'qilmadi — sababi menejerga aytiladi."""


def _bolaklar(yol: str | Path) -> tuple[str, set[int] | None]:
    """(matn, qator oxiri \\x07 larining CP lari yoki None)."""
    import olefile

    if not olefile.isOleFile(str(yol)):
        raise DocXatosi("Bu .doc fayl emas (yoki buzilgan)")
    with olefile.OleFileIO(str(yol)) as ole:
        if not ole.exists("WordDocument"):
            raise DocXatosi("Word hujjati topilmadi")
        wd = ole.openstream("WordDocument").read()
        bayroqlar = struct.unpack_from("<H", wd, 0x0A)[0]
        if bayroqlar & 0x0100:
            raise DocXatosi("Hujjat parol bilan himoyalangan")
        jadval_nomi = "1Table" if bayroqlar & 0x0200 else "0Table"
        if not ole.exists(jadval_nomi):
            raise DocXatosi("Word jadval oqimi topilmadi")
        tbl = ole.openstream(jadval_nomi).read()

    matn, bolaklar = _bolak_jadvali(wd, tbl)
    try:
        qator_oxirlari = _qator_oxirlari(wd, tbl, bolaklar)
    except Exception:          # noqa: BLE001 — xususiyatlar buzuq: taxminiy bo'linadi
        qator_oxirlari = None
    return matn, qator_oxirlari


def _bolak_jadvali(wd: bytes, tbl: bytes):
    """Matn va bo'laklar jadvali: [(cp_boshi, cp_oxiri, fc_boshi, belgi_hajmi)]."""
    fc_clx, lcb_clx = struct.unpack_from("<II", wd, 0x01A2)
    clx = tbl[fc_clx:fc_clx + lcb_clx]
    i = 0
    while i < len(clx) and clx[i] == 0x01:           # Prc — formatlash, o'tkazamiz
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if i >= len(clx) or clx[i] != 0x02:
        raise DocXatosi("Word bo'laklar jadvali (Pcdt) topilmadi")
    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (lcb - 4) // 12
    cp = struct.unpack_from(f"<{n + 1}I", plc, 0)
    matn = []
    bolaklar = []
    for k in range(n):
        pcd = plc[4 * (n + 1) + 8 * k:4 * (n + 1) + 8 * (k + 1)]
        fc = struct.unpack_from("<I", pcd, 2)[0]
        uzunlik = cp[k + 1] - cp[k]
        if fc & 0x40000000:                           # siqilgan: 8 bit, cp1252
            boshi = (fc & 0x3FFFFFFF) // 2
            matn.append(wd[boshi:boshi + uzunlik].decode("cp1252", errors="replace"))
            bolaklar.append((cp[k], cp[k + 1], boshi, 1))
        else:
            matn.append(wd[fc:fc + 2 * uzunlik].decode("utf-16-le", errors="replace"))
            bolaklar.append((cp[k], cp[k + 1], fc, 2))
    return "".join(matn), bolaklar


# Paragraf xususiyatlari: «jadval qatorini tugatuvchi paragraf» (TTP) belgisi.
_SPRM_TTP = (0x2417, 0x244C)      # sprmPFTtp, sprmPFInnerTtp


def _sprmlar(grpprl: bytes):
    """grpprl -> (sprm, operand) ketma-ketligi (MS-DOC 2.6)."""
    i = 0
    while i + 2 <= len(grpprl):
        sprm = struct.unpack_from("<H", grpprl, i)[0]
        i += 2
        spra = sprm >> 13
        if spra in (0, 1):
            hajm = 1
        elif spra in (2, 4, 5):
            hajm = 2
        elif spra == 3:
            hajm = 4
        elif spra == 7:
            hajm = 3
        else:                                       # 6 — o'zgaruvchan uzunlik
            if sprm == 0xD608:                      # sprmTDefTable: 2 baytli uzunlik
                hajm = struct.unpack_from("<H", grpprl, i)[0] + 1
                i += 1
            else:
                hajm = grpprl[i] + 1 if i < len(grpprl) else 1
        yield sprm, grpprl[i:i + hajm]
        i += hajm


def _qator_oxirlari(wd: bytes, tbl: bytes, bolaklar) -> set[int]:
    """Jadval qatori oxiri bo'lgan \\x07 larning CP lari — TTP paragraflari.

    Bo'sh katak ham «\\x07» beradi, shuning uchun qator chegarasini matndan
    bilib bo'lmaydi; Word uni paragraf xususiyatida (PAPX FKP) saqlaydi.
    """
    fc_bte, lcb_bte = struct.unpack_from("<II", wd, 0x0102)
    plc = tbl[fc_bte:fc_bte + lcb_bte]
    n = (lcb_bte - 4) // 8
    sahifalar = struct.unpack_from(f"<{n}I", plc, 4 * (n + 1))
    ttp_fclar: list[int] = []
    for pn in sahifalar:
        sahifa = wd[(pn & 0x3FFFFF) * 512:(pn & 0x3FFFFF) * 512 + 512]
        crun = sahifa[511]
        fclar = struct.unpack_from(f"<{crun + 1}I", sahifa, 0)
        for k in range(crun):
            b_offset = sahifa[4 * (crun + 1) + 13 * k]
            if not b_offset:
                continue
            j = b_offset * 2
            cb = sahifa[j]
            if cb == 0:
                hajm = 2 * sahifa[j + 1]
                boshi = j + 2
            else:
                hajm = 2 * cb - 1
                boshi = j + 1
            grpprl = sahifa[boshi + 2:boshi + hajm]          # istd (2 bayt) dan keyin
            if any(s in _SPRM_TTP and op[:1] == b"\x01" for s, op in _sprmlar(grpprl)):
                ttp_fclar.append(fclar[k + 1])             # paragraf oxiri (keyingi FC)
    natija: set[int] = set()
    for fc_oxir in ttp_fclar:
        for cp_boshi, cp_oxiri, fc_boshi, hajm in bolaklar:
            fc = fc_oxir - hajm                             # paragrafning OXIRGI belgisi
            if fc_boshi <= fc < fc_boshi + (cp_oxiri - cp_boshi) * hajm:
                natija.add(cp_boshi + (fc - fc_boshi) // hajm)
                break
    return natija


def _katak(matn: str) -> str:
    # Maydon kodlari (\x13 kod \x14 natija \x15) — natija qoladi; boshqaruv belgilari olib tashlanadi.
    matn = re.sub("\x13[^\x14\x15]*\x14", "", matn).replace("\x15", "")
    matn = re.sub("[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", matn.replace("\r", " "))
    return re.sub(r"\s+", " ", matn).strip()


def _yaroqli_qatorlar(tokenlar: list[str], i: int, n: int) -> int:
    """i dan boshlab n ustun bilan nechta qator KETMA-KET to'g'ri bo'linadi."""
    soni = 0
    while i + n < len(tokenlar) and tokenlar[i + n] == "":
        soni += 1
        i += n + 1
    return soni


def _jadvalga_bol(tokenlar: list[str]) -> list[list[str]]:
    """Jadval tokenlari (\\x07 bo'yicha bo'lingan) -> qatorlar.

    Har qator: n katak + bitta bo'sh token (qator belgisi). Bo'sh katak ham
    bo'sh token beradi, shuning uchun n TANLANADI: qaysi n bilan undan keyingi
    qatorlar eng ko'p ketma-ket to'g'ri bo'linsa — o'sha (teng bo'lsa oldingi
    n, keyin kichigi). Birlashtirilgan katakli qatorda n o'zgaradi.
    """
    qatorlar: list[list[str]] = []
    i, oldingi = 0, None

    def keyingisi_toliqmi(n: int) -> bool:
        # To'g'ri bo'lingan qatordan keyingi qator odatda TO'LA katak bilan
        # boshlanadi (tartib raqami, nom). Noto'g'ri bo'linsa — keyingi «qator»
        # bo'sh katakdan boshlanib, hamma narsa bir katakka suriladi
        # (решетки so'rovnomasi: «нет» qatori 4 katakli, 3 emas).
        j = i + n + 1
        return j >= len(tokenlar) or tokenlar[j].strip() != ""

    while i < len(tokenlar):
        nomzodlar = [n for n in range(1, min(64, len(tokenlar) - i))
                     if tokenlar[i + n] == ""]
        if not nomzodlar:
            qatorlar.append([_katak(t) for t in tokenlar[i:]])
            break
        n = max(nomzodlar, key=lambda n: (keyingisi_toliqmi(n),
                                          _yaroqli_qatorlar(tokenlar, i, n), n == oldingi, -n))
        qatorlar.append([_katak(t) for t in tokenlar[i:i + n]])
        oldingi = n
        i += n + 1
    return qatorlar


def doc_oqi(yol: str | Path) -> tuple[str, list[list[list[str]]]]:
    """.doc -> (to'liq matn, jadvallar). Matnda katak « | » bilan ajratiladi.

    JADVAL CHEGARASI: jadval birinchi katakdan oldingi paragraf belgisidan
    keyin boshlanadi. Qator oxiridan (bo'sh token) keyingi bo'lak YANGI
    PARAGRAF (\\r) bilan boshlansa — jadval tugagan: katak matni paragraf
    belgisi bilan boshlanmaydi, jadvaldan keyingi oddiy matn esa shunday.

    QATOR CHEGARASI — Word ning o'z belgisidan (TTP, `_qator_oxirlari`).
    Belgilar o'qilmasa — taxminiy bo'linadi (`_jadvalga_bol`).
    """
    xom, qator_oxirlari = _bolaklar(yol)
    jadvallar: list[list[list[str]]] = []
    matn_qismlar: list[str] = []
    pos = 0
    while True:
        birinchi = xom.find("\x07", pos)
        if birinchi < 0:
            matn_qismlar.append(xom[pos:])
            break
        bosh = xom.rfind("\r", pos, birinchi) + 1 or pos
        matn_qismlar.append(xom[pos:bosh])
        tokenlar: list[str] = []
        oxirlar: list[bool] = []          # token qator oxirimi (TTP)
        k = bosh
        while True:
            j = xom.find("\x07", k)
            if j < 0:
                break
            token = xom[k:j]
            oldingi_oxir = oxirlar[-1] if qator_oxirlari is not None and oxirlar else (
                bool(tokenlar) and tokenlar[-1] == "")
            if tokenlar and oldingi_oxir and token.startswith("\r"):
                break                       # qator oxiridan keyin yangi paragraf
            tokenlar.append(token)
            oxirlar.append(qator_oxirlari is not None and j in qator_oxirlari)
            k = j + 1
        if qator_oxirlari and any(oxirlar):
            jadval, qator = [], []
            for token, oxir in zip(tokenlar, oxirlar):
                if oxir:
                    jadval.append(qator)
                    qator = []
                else:
                    qator.append(_katak(token))
            if qator:
                jadval.append(qator)
        else:
            jadval = _jadvalga_bol(tokenlar)
        jadvallar.append(jadval)
        matn_qismlar.append("\n".join(" | ".join(q) for q in jadval) + "\n")
        pos = k
    matn = "".join(q.replace("\r", "\n") for q in matn_qismlar)
    matn = re.sub("[\x00-\x08\x0b\x0c\x0e-\x1f]", "", matn)
    return re.sub(r"\n{3,}", "\n\n", matn).strip(), jadvallar


# --- RTF ------------------------------------------------------------------------

# Matni chiqmaydigan guruhlar (shriftlar, ranglar, rasm, ma'lumot …).
_RTF_TASHLANADI = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
                   "header", "footer", "headerl", "headerr", "footerl", "footerr",
                   "listtable", "listoverridetable", "rsidtbl", "xmlnstbl", "datastore",
                   "themedata", "colorschememapping", "latentstyles", "generator"}
_RTF_TOKEN = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}\r\n]+)|[\r\n]+")


def rtf_oqi(baytlar: bytes) -> tuple[str, list[list[list[str]]]]:
    """RTF -> (matn, jadvallar). Jadval: `\\cell` katak, `\\row` qator, `\\intbl`."""
    matn_bayt = baytlar.decode("latin-1")
    m = re.search(r"\\ansicpg(\d+)", matn_bayt)
    kodlash = f"cp{m.group(1)}" if m else "cp1252"

    stek: list[tuple[bool, int]] = []
    tashla, uc, otkaz = False, 1, 0
    jadvallar: list[list[list[str]]] = []
    qator: list[str] = []
    katak: list[str] = []
    matn: list[str] = []
    jadvalda = False
    joriy_jadval: list[list[str]] = []
    bayt_bufer = bytearray()

    def bayt_yoz():
        if bayt_bufer:
            (katak if jadvalda else matn).append(bayt_bufer.decode(kodlash, errors="replace"))
            bayt_bufer.clear()

    def yoz(s: str):
        bayt_yoz()
        (katak if jadvalda else matn).append(s)

    def jadvalni_yop():
        nonlocal joriy_jadval
        if joriy_jadval:
            jadvallar.append(joriy_jadval)
            matn.append("\n" + "\n".join(" | ".join(q) for q in joriy_jadval) + "\n")
            joriy_jadval = []

    oldingi_guruh_boshi = False
    for t in _RTF_TOKEN.finditer(matn_bayt):
        soz, son, hex_, belgi, qavs, oddiy = t.groups()
        if qavs == "{":
            stek.append((tashla, uc))
            oldingi_guruh_boshi = True
            continue
        if qavs == "}":
            bayt_yoz()
            if stek:
                tashla, uc = stek.pop()
            oldingi_guruh_boshi = False
            continue
        guruh_boshi, oldingi_guruh_boshi = oldingi_guruh_boshi, False
        if belgi == "*" and guruh_boshi:
            tashla = True
            continue
        if soz and guruh_boshi and soz in _RTF_TASHLANADI:
            tashla = True
            continue
        if tashla:
            continue
        if soz:
            if soz == "uc" and son:
                uc = int(son)
            elif soz == "u" and son:
                kod = int(son)
                yoz(chr(kod + 65536 if kod < 0 else kod))
                otkaz = uc
            elif soz == "par" or soz == "line":
                yoz(" " if jadvalda else "\n")
            elif soz == "tab":
                yoz(" ")
            elif soz == "intbl":
                jadvalda = True
            elif soz == "pard":
                bayt_yoz()
                jadvalda = False
            elif soz == "cell":
                bayt_yoz()
                qator.append(_katak("".join(katak)))
                katak.clear()
            elif soz == "row":
                bayt_yoz()
                if qator:
                    joriy_jadval.append(qator)
                qator = []
                katak.clear()
            continue
        if hex_:
            if otkaz:
                otkaz -= 1
                continue
            bayt_bufer.append(int(hex_, 16))
            continue
        if belgi in ("\\", "{", "}"):
            yoz(belgi)
            continue
        if oddiy:
            if otkaz:
                oddiy = oddiy[otkaz:]
                otkaz = 0
            if oddiy and not jadvalda:
                jadvalni_yop()
            if oddiy:
                yoz(oddiy)
    bayt_yoz()
    if qator:
        joriy_jadval.append(qator)
    jadvalni_yop()
    natija = re.sub(r"[ \t]+", " ", "".join(matn))
    return re.sub(r"\n{3,}", "\n\n", natija).strip(), jadvallar


# --- HTML («Word -> veb-sahifa», kengaytmasi .doc) --------------------------------


def html_oqi(baytlar: bytes) -> tuple[str, list[list[list[str]]]]:
    from html.parser import HTMLParser

    m = re.search(rb"charset=[\"']?([\w-]+)", baytlar[:4000], re.I)
    kodlash = m.group(1).decode() if m else "utf-8"
    try:
        hujjat = baytlar.decode(kodlash)
    except (LookupError, UnicodeDecodeError):
        hujjat = baytlar.decode("cp1251", errors="replace")

    class Oquvchi(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.jadvallar: list[list[list[str]]] = []
            self.stek: list[list[list[str]]] = []
            self.katak: list[str] | None = None
            self.matn: list[str] = []
            self.tashla = 0

        def handle_starttag(self, teg, _a):
            if teg in ("style", "script", "head"):
                self.tashla += 1
            elif teg == "table":
                self.stek.append([])
            elif teg == "tr" and self.stek:
                self.stek[-1].append([])
            elif teg in ("td", "th") and self.stek:
                self.katak = []
            elif teg in ("br", "p", "div") and self.katak is None:
                self.matn.append("\n")

        def handle_endtag(self, teg):
            if teg in ("style", "script", "head"):
                self.tashla = max(0, self.tashla - 1)
            elif teg in ("td", "th") and self.stek and self.katak is not None:
                if not self.stek[-1]:
                    self.stek[-1].append([])
                self.stek[-1][-1].append(_katak("".join(self.katak)))
                self.katak = None
            elif teg == "table" and self.stek:
                jadval = [q for q in self.stek.pop() if q]
                if jadval:
                    self.jadvallar.append(jadval)
                    self.matn.append("\n" + "\n".join(" | ".join(q) for q in jadval) + "\n")

        def handle_data(self, data):
            if self.tashla:
                return
            if self.katak is not None:
                self.katak.append(data)
            elif not self.stek:
                self.matn.append(data)

    o = Oquvchi()
    o.feed(hujjat)
    matn = re.sub(r"[ \t\xa0]+", " ", "".join(o.matn))
    return re.sub(r"\n\s*\n+", "\n\n", matn).strip(), o.jadvallar


# --- DOCX --------------------------------------------------------------------------


def docx_oqi(yol: str | Path) -> tuple[str, list[list[list[str]]]]:
    from docx import Document

    hujjat = Document(str(yol))
    jadvallar = []
    for t in hujjat.tables:
        qatorlar = []
        for r in t.rows:
            kataklar, oldingi = [], None
            for c in r.cells:
                # Birlashtirilgan katak python-docx da TAKRORLANADI — bittasi olinadi.
                if c._tc is oldingi:
                    continue
                oldingi = c._tc
                kataklar.append(_katak(c.text))
            qatorlar.append(kataklar)
        jadvallar.append(qatorlar)
    matn = "\n".join(p.text for p in hujjat.paragraphs)
    matn += "\n" + "\n".join(" | ".join(q) for j in jadvallar for q in j)
    return matn.strip(), jadvallar


# --- umumiy -------------------------------------------------------------------------

WORD_KENGAYTMALARI = {".doc", ".docx", ".rtf", ".htm", ".html"}


def hujjat_oqi(yol: str | Path) -> tuple[str, list[list[list[str]]]]:
    """Word hujjati -> (matn, jadvallar). Tur KENGAYTMADAN emas, MAZMUNDAN.

    Haqiqiy hayotda «.doc» uch xil bo'ladi (2026-10-03 Telegram fayllari):
    Word 97 (D0CF11E0), RTF («{\\rtf») va HTML («Word -> veb-sahifa»).
    Word ularning hammasini ochadi — bot ham ochishi kerak.
    """
    yol = Path(yol)
    bosh = yol.read_bytes()[:8]
    if bosh.startswith(b"\xd0\xcf\x11\xe0"):
        return doc_oqi(yol)
    if bosh.startswith(b"PK"):
        return docx_oqi(yol)
    baytlar = yol.read_bytes()
    if baytlar.lstrip()[:5] == b"{\\rtf":
        return rtf_oqi(baytlar)
    if re.search(rb"<html|<!doctype html|<table", baytlar[:4000], re.I):
        return html_oqi(baytlar)
    raise DocXatosi("Hujjat turi tanilmadi (Word, RTF yoki HTML emas)")

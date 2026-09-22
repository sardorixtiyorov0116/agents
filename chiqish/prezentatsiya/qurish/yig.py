"""Prezentatsiyani bitta HTML faylga yig'adi.

Agent kartalari `contracts/*.yaml` dan, bo'limlar
`knowledge/product/sorovnoma.yaml` dan O'QIB olinadi — qo'lda
ko'chirilmaydi. Shartnoma o'zgarsa, prezentatsiya ham o'zgaradi.

Videolar base64 bo'lib ichiga kiradi: fayl bitta bo'lsin, hech
qanday tashqi manba talab qilmasin.

    .venv\\Scripts\\python chiqish\\prezentatsiya\\qurish\\yig.py
"""

from __future__ import annotations

import base64
import html
import pathlib
import re

import yaml

ILDIZ = pathlib.Path(__file__).resolve().parents[3]
QURISH = pathlib.Path(__file__).resolve().parent
MEDIA = ILDIZ / "chiqish" / "prezentatsiya" / "media2"
CHIQISH = ILDIZ / "chiqish" / "prezentatsiya" / "agentlar-tizimi.html"
ARTEFAKT = ILDIZ / "chiqish" / "prezentatsiya" / "artefakt.html"

# Mustaqil fayl uchun o'ram.
#
# NEGA KERAK: artefakt tizimi sahifani o'zi <head> ga o'raydi, shuning
# uchun u yerga doctype yozilmaydi. Lekin fayl brauzerda TO'G'RIDAN-TO'G'RI
# ochilsa, `meta charset` bo'lmasa brauzer Latin-1 deb o'qiydi va
# «·» belgisi «Â·» bo'lib chiqadi — bir marta shunday bo'ldi.
ORAM_BOSHI = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Jihozvent ventilyatsiya savdosi uchun 15 agentli tizim — jonli o'lchangan ko'rsatkichlar.">
"""
ORAM_OXIRI = "\n</body>\n</html>\n"

VIDEO_ATRIBUT = 'autoplay muted loop playsinline preload="auto" aria-hidden="true"'

# Shartnomadagi xavf darajasi -> nishon sinfi
NISHON = {"yuqori": "n-yuqori", "orta": "n-orta", "past": "n-past"}
NISHON_MATNI = {"yuqori": "yuqori xavf", "orta": "o‘rta", "past": "past"}


def q(matn: object) -> str:
    """HTML ga xavfsiz joylash."""
    return html.escape(str(matn or ""))


def agent_kartalari() -> str:
    """15 ta agent — contracts/ dan."""
    kartalar = []
    for fayl in sorted((ILDIZ / "contracts").glob("*.yaml")):
        d = yaml.safe_load(fayl.read_text(encoding="utf-8"))
        xavf = str(d.get("xavf") or "orta")
        chegara = len(d.get("chegaralar") or [])
        kartalar.append(
            '<div class="agent">'
            f'<span class="ism">{q(d.get("ism"))}</span>'
            f'<span class="lav">{q(d.get("lavozim"))}</span>'
            '<span class="kod">'
            f'<span>{q(d.get("rol"))}</span>'
            f'<span class="nishon {NISHON.get(xavf, "n-orta")}">'
            f'{q(NISHON_MATNI.get(xavf, xavf))}</span>'
            '</span>'
            '<span class="kod" style="margin-top:1px">'
            f'<span>{chegara} chegara</span></span>'
            '</div>'
        )
    if len(kartalar) != 15:
        raise SystemExit(f"XATO: {len(kartalar)} ta shartnoma topildi, 15 kutilgandi")
    return "\n".join(kartalar)


def bolim_kartalari() -> str:
    """12 ta so'rovnoma bo'limi — YAML dan."""
    manba = yaml.safe_load(
        (ILDIZ / "knowledge" / "product" / "sorovnoma.yaml").read_text(encoding="utf-8"))
    bolimlar = manba.get("bolimlar") or manba
    kartalar = []
    for kalit, v in bolimlar.items():
        nomi = v.get("nomi") or v.get("sarlavha") or kalit
        soni = len(v.get("savollar") or [])
        kartalar.append(
            '<div class="agent" style="border-left-color:var(--oqim)">'
            f'<span class="ism" style="font-size:14px">{q(nomi)}</span>'
            f'<span class="kod" style="margin-top:4px"><span>{soni} savol</span>'
            f'<span style="color:var(--sokin)">{q(kalit)}</span></span>'
            '</div>'
        )
    if len(kartalar) != 12:
        raise SystemExit(f"XATO: {len(kartalar)} ta bo‘lim topildi, 12 kutilgandi")
    return "\n".join(kartalar)


INGICHKA = " "   # ming ajratgichi — JS ham shuni ishlatadi


def raqamlarni_toldir(matn: str) -> str:
    """`data-qiymat` li elementga HAQIQIY raqamni matn qilib yozadi.

    NEGA KERAK: sanash animatsiyasi nolga tushirib qayta o'stiradi.
    Agar brauzer sahifani muzlatsa (fonda ochilsa, yoki JS to'xtasa),
    ekranda o'sha boshlang'ich matn qoladi. Avval u "0" edi va bir
    marta hamma ko'rsatkich NOL bo'lib qoldi — prezentatsiyada
    noto'g'ri raqam ko'rsatish eng yomon xato. Endi eng yomon holatda
    ham to'g'ri raqam turadi, faqat animatsiyasiz.
    """
    naqsh = re.compile(r'(<span[^>]*\bdata-qiymat="([0-9.]+)"[^>]*>)0(</span>)')

    def almashtir(mos: re.Match[str]) -> str:
        ochilish, xom = mos.group(1), mos.group(2)
        kasr_mos = re.search(r'data-kasr="(\d+)"', ochilish)
        kasr = int(kasr_mos.group(1)) if kasr_mos else 0
        qiymat = float(xom)
        matn_qiymat = f"{qiymat:,.{kasr}f}".replace(",", INGICHKA).replace(".", ",")
        return ochilish + matn_qiymat + mos.group(3)

    yangi, soni = naqsh.subn(almashtir, matn)
    print(f"   {soni} ta ko'rsatkichga haqiqiy qiymat yozildi")
    kutilgan = matn.count("data-qiymat")
    if soni != kutilgan:
        raise SystemExit(
            f"XATO: {kutilgan} ta data-qiymat bor, {soni} tasi to'ldirildi")
    return yangi


def videolar(matn: str) -> str:
    """`<video __V__ ></video>__VIDEO_NOM__` -> base64 joylangan teg."""
    naqsh = re.compile(r"<video __V__ ></video>__VIDEO_([A-Z]+)__")

    def almashtir(mos: re.Match[str]) -> str:
        nom = mos.group(1).lower()
        fayl = MEDIA / f"{nom}.mp4"
        if not fayl.exists():
            raise SystemExit(f"XATO: video topilmadi — {fayl}")
        b64 = base64.b64encode(fayl.read_bytes()).decode("ascii")
        print(f"   video {nom:8} {fayl.stat().st_size/1e6:5.2f} MB "
              f"-> base64 {len(b64)/1e6:5.2f} MB")
        return f'<video {VIDEO_ATRIBUT} src="data:video/mp4;base64,{b64}"></video>'

    yangi, soni = naqsh.subn(almashtir, matn)
    if soni != 5:
        raise SystemExit(f"XATO: {soni} ta video joylandi, 5 kutilgandi")
    return yangi


def main() -> None:
    shablon = (QURISH / "shablon.html").read_text(encoding="utf-8")
    uslub = (QURISH / "uslub.css").read_text(encoding="utf-8")
    skript = (QURISH / "skript.js").read_text(encoding="utf-8")

    sahifa = shablon
    sahifa = sahifa.replace("__AGENTLAR__", agent_kartalari())
    sahifa = sahifa.replace("__BOLIMLAR__", bolim_kartalari())
    sahifa = raqamlarni_toldir(sahifa)
    # Uslub va skript OXIRIDA — ichida `__` bo'lsa ham tegilmasin.
    print("Videolar joylanmoqda...")
    sahifa = videolar(sahifa)
    sahifa = sahifa.replace("__USLUB__", uslub)
    sahifa = sahifa.replace("__SKRIPT__", skript)

    qolgan = re.findall(r"__[A-Z_]+__", sahifa)
    if qolgan:
        raise SystemExit(f"XATO: to‘ldirilmagan joy qoldi: {set(qolgan)}")

    # 1) Artefakt uchun — doctype/head SIZ (tizim o'zi o'raydi).
    ARTEFAKT.write_text(sahifa, encoding="utf-8")

    # 2) Mustaqil fayl — to'liq hujjat, brauzerda ochsa bo'ladi.
    #    <title>, <link> va <style> sahifaning boshida turibdi — ular
    #    <head> ichiga tushadi; ko'rinadigan qismi <canvas> dan boshlanadi.
    ajratgich = '<canvas id="graf"'
    bosh, _, tana = sahifa.partition(ajratgich)
    tola = ORAM_BOSHI + bosh + "</head>\n<body>\n" + ajratgich + tana + ORAM_OXIRI
    CHIQISH.write_text(tola, encoding="utf-8")

    for nom, yol in (("Mustaqil HTML", CHIQISH), ("Artefakt", ARTEFAKT)):
        hajm = yol.stat().st_size / 1e6
        holat = "chegaradan OSHDI" if hajm > 16 else "16 MB ichida"
        print(f"\n{nom:14}: {yol}")
        print(f"{'Hajm':14}: {hajm:.2f} MB ({holat})")


if __name__ == "__main__":
    main()

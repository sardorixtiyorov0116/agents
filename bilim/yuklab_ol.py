"""lex.uz dan qonun hujjatlarini yuklab olib, matn holida saqlash.

Har fayl boshida metadata qoladi (manba havolasi, olingan sana) — javobda
manbani ko'rsatish va keyinchalik eskirganini bilish uchun.

Ishga tushirish:
    .venv\\Scripts\\python -m bilim.yuklab_ol            # ro'yxatdagilarni
    .venv\\Scripts\\python -m bilim.yuklab_ol 6257288 hr # bitta hujjat
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

import httpx

from app.config import sozlama

ASOS = "https://lex.uz/uz/docs/{}"
SARLAVHALAR = {"User-Agent": "Mozilla/5.0 (agentlar-tizimi bilim bazasi)"}

# Yuklanadigan hujjatlar: ID -> (fayl nomi, papkalar)
# Mehnat kodeksi ikkala papkada: Laziz huquqiy tahlil uchun, Hilola HR uchun.
HUJJATLAR = {
    "111189": ("fuqarolik-kodeksi-1-qism", ["legal"]),
    "6257288": ("mehnat-kodeksi", ["legal", "hr"]),
    "4674893": ("soliq-kodeksi", ["legal"]),
}


def matnga_aylantir(sahifa: str) -> str:
    """lex.uz sahifasidan toza matn ajratadi."""
    sahifa = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", sahifa, flags=re.S | re.I)
    sahifa = re.sub(r"<br\s*/?>", "\n", sahifa, flags=re.I)
    sahifa = re.sub(r"</(p|div|tr|h\d|li)>", "\n", sahifa, flags=re.I)
    matn = html.unescape(re.sub(r"<[^>]+>", "", sahifa))
    matn = re.sub(r"[ \t\xa0]+", " ", matn)
    matn = re.sub(r"\n\s*\n+", "\n\n", matn)
    return matn.strip()


def sarlavha(sahifa: str) -> str:
    mos = re.search(r"<title>(.*?)</title>", sahifa, re.S)
    return html.unescape(mos.group(1)).strip() if mos else ""


def boshdan_kes(matn: str) -> str:
    """Sahifa menyusi va navigatsiyani olib tashlaydi.

    Hujjat matni odatda katta bosh harfli sarlavhadan boshlanadi.
    """
    belgi = re.search(r"^\s*(ЎЗБЕКИСТОН|O‘ZBEKISTON|УЗБЕКИСТАН)", matn, re.M)
    return matn[belgi.start():].strip() if belgi else matn


def yukla(hujjat_id: str, mijoz: httpx.Client) -> tuple[str, str]:
    """Hujjatni yuklab, (sarlavha, matn) qaytaradi."""
    javob = mijoz.get(ASOS.format(hujjat_id), headers=SARLAVHALAR, timeout=60)
    javob.raise_for_status()
    sahifa = javob.text
    return sarlavha(sahifa), boshdan_kes(matnga_aylantir(sahifa))


def saqla(nomi: str, papka: str, hujjat_id: str, bosh: str, matn: str) -> Path:
    """Matnni metadata sarlavhasi bilan saqlaydi."""
    yol = sozlama().bilim_papkasi / papka / f"{nomi}.txt"
    yol.parent.mkdir(parents=True, exist_ok=True)

    metadata = (
        f"# {bosh}\n"
        f"# Manba: {ASOS.format(hujjat_id)}\n"
        f"# Olingan sana: {date.today().isoformat()}\n"
        f"# DIQQAT: qonun o'zgargan bo'lishi mumkin — manbadan tekshiring.\n\n"
    )
    yol.write_text(metadata + matn, encoding="utf-8")
    return yol


def main() -> None:
    ajratgich = argparse.ArgumentParser(description="lex.uz dan qonun yuklab olish")
    ajratgich.add_argument("hujjat_id", nargs="?", help="lex.uz hujjat ID (masalan 6257288)")
    ajratgich.add_argument("papka", nargs="?", default="legal", help="knowledge/<papka>")
    ajratgich.add_argument("--nom", help="fayl nomi (ixtiyoriy)")
    argumentlar = ajratgich.parse_args()

    if argumentlar.hujjat_id:
        vazifalar = {
            argumentlar.hujjat_id: (
                argumentlar.nom or f"hujjat-{argumentlar.hujjat_id}",
                [argumentlar.papka],
            )
        }
    else:
        vazifalar = HUJJATLAR

    with httpx.Client(follow_redirects=True) as mijoz:
        for hujjat_id, (nomi, papkalar) in vazifalar.items():
            try:
                bosh, matn = yukla(hujjat_id, mijoz)
            except httpx.HTTPError as xato:
                print(f"  XATO {hujjat_id}: {xato}", file=sys.stderr)
                continue

            if len(matn) < 5000:
                print(f"  XATO {hujjat_id}: matn juda qisqa ({len(matn)})", file=sys.stderr)
                continue

            moddalar = len(re.findall(r"\d+\s*[-–]\s*модда", matn, re.I))
            for papka in papkalar:
                yol = saqla(nomi, papka, hujjat_id, bosh, matn)
                print(f"  {yol.relative_to(sozlama().bilim_papkasi.parent)} "
                      f"— {len(matn):,} belgi, {moddalar} modda".replace(",", " "))

    print("\nEndi indekslang:  .venv\\Scripts\\python -m bilim.indeks")


if __name__ == "__main__":
    main()

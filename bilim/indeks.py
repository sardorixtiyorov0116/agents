"""Bilim bazasini indekslash.

Hujjatlar `knowledge/<papka>/` dan va sozlamadagi qo'shimcha yo'llardan
(masalan Obsidian vault) o'qiladi. Har bo'lak uchun vektor hisoblanadi va
SQLite'ga yoziladi — alohida vektor bazasi kerak emas, korpus kichik.

Ishga tushirish:
    .venv\\Scripts\\python -m bilim.indeks           # o'zgarganini indekslash
    .venv\\Scripts\\python -m bilim.indeks --hammasi  # qaytadan
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from app.config import sozlama

from .bolak import bol, qonunmi

# Indekslanadigan fayl turlari.
KENGAYTMALAR = {".md", ".txt", ".markdown"}

SXEMA = """
CREATE TABLE IF NOT EXISTS bilim_hujjat (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    papka      TEXT NOT NULL,
    yol        TEXT NOT NULL UNIQUE,
    nomi       TEXT NOT NULL,
    tur        TEXT,
    xesh       TEXT NOT NULL,
    sana       TEXT,
    eskirgan   INTEGER NOT NULL DEFAULT 0,
    yangilandi TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bilim_bolak (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    hujjat_id INTEGER NOT NULL REFERENCES bilim_hujjat(id) ON DELETE CASCADE,
    tartib    INTEGER NOT NULL,
    sarlavha  TEXT,
    matn      TEXT NOT NULL,
    vektor    BLOB
);

CREATE INDEX IF NOT EXISTS bilim_bolak_hujjat ON bilim_bolak (hujjat_id);
CREATE INDEX IF NOT EXISTS bilim_hujjat_papka ON bilim_hujjat (papka, eskirgan);
"""

_model = None


def model():
    """Embedding modeli (dangasa yuklanadi — import paytida emas)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(sozlama().bilim_model)
    return _model


# E5 oilasidagi modellar PREFIKS talab qiladi: hujjatga «passage: »,
# savolga «query: ». Ular shu bilan o'qitilgan va prefikssiz sifat
# sezilarli pasayadi.
#
# Boshqa modellarga prefiks QO'SHILMAYDI — ular buni oddiy matn deb
# qabul qiladi va vektor buziladi.
E5_PREFIKS = {"passage": "passage: ", "query": "query: "}


def _prefiksli(matnlar: list[str], tur: str) -> list[str]:
    if "e5" not in sozlama().bilim_model.lower():
        return matnlar
    oldi = E5_PREFIKS.get(tur, "")
    return [oldi + m for m in matnlar]


def vektorla(matnlar: list[str], tur: str = "passage") -> np.ndarray:
    """Matnlarni normallashtirilgan vektorlarga aylantiradi.

    `tur`: «passage» — indekslanadigan hujjat, «query» — qidiruv savoli.
    Ba'zi modellar (E5) ikkalasini boshqacha ko'radi.
    """
    if not matnlar:
        return np.zeros((0, 0), dtype=np.float32)
    vektorlar = np.array(
        list(model().embed(_prefiksli(matnlar, tur))), dtype=np.float32)
    normalar = np.linalg.norm(vektorlar, axis=1, keepdims=True)
    normalar[normalar == 0] = 1.0
    return vektorlar / normalar


def _hozir() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Obsidian vault papkalari qaysi bilim bo'limiga tushadi.
#
# Avval butun vault `umumiy` ga tushardi va bu ikki tomonlama zarar berardi:
#   - Rustamdan "ombor ventilyatsiyasi normasi" so'ralganda unga
#     RAQOBATCHILAR tahlili chiqardi — sof shovqin;
#   - Temur (proposal-builder) faqat `sales` ni ko'radi, shuning uchun
#     vaultdagi mijoz portretlarini UMUMAN ko'rmasdi.
#
# Endi har papka o'z joyiga tushadi va agent faqat o'ziga keraklisini oladi.
VAULT_XARITASI = {
    "00-MOC": "umumiy",
    "01-Kompaniya": "umumiy",
    "02-Mahsulotlar": "product",
    "03-Bozor": "market",
    "04-Raqobat": "market",
    "05-Mijozlar": "sales",
    "06-Strategiya": "marketing",
    # Montaj — uskunani QAYERGA va QANDAY o'rnatish. Bu hisobdan
    # ham, mahsulot tavsifidan ham alohida bilim: xato o'rnatish
    # ishlagan uskunani ham foydasiz qiladi.
    "07-Montaj": "montaj",
    # Normativ hujjatlar (SHNQ, QMQ) — loyihalash, hisob va montajda
    # tayaniladigan RASMIY talablar. `umumiy` ga tushsa marketing, SMM va
    # raqobat agentlariga ham chiqardi — ularga faqat shovqin.
    "08-Normativ": "normativ",
}


def papkalar() -> dict[str, list[Path]]:
    """Papka nomi -> qidiriladigan yo'llar.

    `knowledge/<papka>` doim; unga qo'shimcha ravishda tashqi vaultning
    tegishli qismi qo'shiladi (nusxa ko'chirilmaydi, joyida o'qiladi).

    Vaultda `VAULT_XARITASI` da yo'q yangi papka paydo bo'lsa, u `umumiy`
    ga tushadi — ya'ni ma'lumot YO'QOLMAYDI, faqat aniq manzili yo'q.
    """
    s = sozlama()
    natija: dict[str, list[Path]] = {}
    ildiz = s.bilim_papkasi
    vault = s.vault_papkasi

    qoshimcha: dict[str, list[Path]] = {}
    if vault and vault.is_dir():
        for ichki in sorted(vault.iterdir()):
            if not ichki.is_dir() or ichki.name.startswith("."):
                continue
            bolim = VAULT_XARITASI.get(ichki.name, "umumiy")
            qoshimcha.setdefault(bolim, []).append(ichki)
        # Ildizdagi yolg'iz fayllar (README va h.k.) — `umumiy` ga.
        # Butun vault yo'lini qo'shmaymiz: `rglob` ichki papkalarni qayta
        # o'qib, har hujjatni ikki marta indekslardi.
        qoshimcha.setdefault("umumiy", []).append(_IldizFaqat(vault))

    for papka in s.bilim_bolimlari:
        yollar = [ildiz / papka, *qoshimcha.get(papka, [])]
        natija[papka] = [y for y in yollar if y.is_dir()]
    return natija


class _IldizFaqat(Path):
    """Faqat shu papkaning O'ZIDAGI fayllar (ichki papkalarsiz).

    Vault ildizini oddiy yo'l sifatida qo'shsak, `rglob` ichki
    papkalarni ham qayta o'qiydi va hujjatlar ikki marta indekslanadi.
    """

    __slots__ = ()


def fayllar(yollar: Iterable[Path]) -> list[Path]:
    topilgan: list[Path] = []
    for yol in yollar:
        namuna = yol.glob("*") if isinstance(yol, _IldizFaqat) else yol.rglob("*")
        for fayl in sorted(namuna):
            if not fayl.is_file() or fayl.suffix.lower() not in KENGAYTMALAR:
                continue
            # Obsidian va tizim papkalari
            if any(qism.startswith(".") for qism in fayl.parts):
                continue
            topilgan.append(fayl)
    return topilgan


def _xesh(matn: str) -> str:
    return hashlib.sha256(matn.encode("utf-8")).hexdigest()[:32]


class Indeks:
    """Bilim bazasi indeksi (SQLite ustida)."""

    def __init__(self, yol: Path | None = None):
        self.yol = yol or sozlama().baza_fayli

    def _ulanish(self) -> sqlite3.Connection:
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        ulanish = sqlite3.connect(self.yol, timeout=30)
        ulanish.row_factory = sqlite3.Row
        ulanish.execute("PRAGMA foreign_keys = ON")
        return ulanish

    def tayyorla(self) -> None:
        with self._ulanish() as u:
            u.executescript(SXEMA)

    # --- indekslash ----------------------------------------------------------

    def hujjatni_indeksla(self, fayl: Path, papka: str, majburiy: bool = False) -> int:
        """Bitta hujjatni indekslaydi. Qaytaradi: yozilgan bo'lak soni."""
        try:
            matn = fayl.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return 0

        xesh = _xesh(matn)
        yol = str(fayl)

        with self._ulanish() as u:
            mavjud = u.execute(
                "SELECT id, xesh FROM bilim_hujjat WHERE yol = ?", (yol,)
            ).fetchone()
            if mavjud and mavjud["xesh"] == xesh and not majburiy:
                return 0  # o'zgarmagan

        qonun = qonunmi(matn)
        bolaklar = bol(matn, qonun=qonun)
        if not bolaklar:
            return 0

        # Vektorlashda parchaga hujjat nomi va bo'lim sarlavhasi qo'shiladi —
        # parcha o'z kontekstisiz ma'nosini yo'qotmasligi uchun. Saqlanadigan
        # matn esa toza qoladi.
        vektorlar = vektorla(
            [
                " | ".join(x for x in (fayl.stem, b.sarlavha, b.matn) if x)
                for b in bolaklar
            ]
        )

        with self._ulanish() as u:
            if mavjud:
                u.execute("DELETE FROM bilim_bolak WHERE hujjat_id = ?", (mavjud["id"],))
                u.execute(
                    "UPDATE bilim_hujjat SET xesh = ?, yangilandi = ?, tur = ?, papka = ?"
                    " WHERE id = ?",
                    (xesh, _hozir(), "qonun" if qonun else "matn", papka, mavjud["id"]),
                )
                hujjat_id = mavjud["id"]
            else:
                kursor = u.execute(
                    "INSERT INTO bilim_hujjat (papka, yol, nomi, tur, xesh, yangilandi)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (papka, yol, fayl.stem, "qonun" if qonun else "matn", xesh, _hozir()),
                )
                hujjat_id = int(kursor.lastrowid or 0)

            u.executemany(
                "INSERT INTO bilim_bolak (hujjat_id, tartib, sarlavha, matn, vektor)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (hujjat_id, b.tartib, b.sarlavha, b.matn, vektorlar[i].tobytes())
                    for i, b in enumerate(bolaklar)
                ],
            )
        return len(bolaklar)

    def hammasini_indeksla(self, majburiy: bool = False) -> dict[str, int]:
        """Barcha papkalarni indekslaydi. Qaytaradi: papka -> bo'lak soni."""
        self.tayyorla()
        natija: dict[str, int] = {}
        korilgan_yollar: set[str] = set()

        for papka, yollar in papkalar().items():
            soni = 0
            for fayl in fayllar(yollar):
                korilgan_yollar.add(str(fayl))
                soni += self.hujjatni_indeksla(fayl, papka, majburiy)
            natija[papka] = soni

        self._yoq_bolganlarni_ochir(korilgan_yollar)
        return natija

    def _yoq_bolganlarni_ochir(self, mavjud_yollar: set[str]) -> None:
        """O'chirilgan fayllarning yozuvlarini indeksdan olib tashlaydi."""
        with self._ulanish() as u:
            qatorlar = u.execute("SELECT id, yol FROM bilim_hujjat").fetchall()
            yoqolgan = [q["id"] for q in qatorlar if q["yol"] not in mavjud_yollar]
            if yoqolgan:
                belgilar = ",".join("?" * len(yoqolgan))
                u.execute(f"DELETE FROM bilim_hujjat WHERE id IN ({belgilar})", yoqolgan)

    # --- o'qish --------------------------------------------------------------

    def bolaklar(self, papkalar_royxati: list[str]) -> list[dict]:
        """Berilgan papkalardagi barcha bo'laklar (vektori bilan)."""
        if not papkalar_royxati:
            return []
        belgilar = ",".join("?" * len(papkalar_royxati))
        with self._ulanish() as u:
            qatorlar = u.execute(
                "SELECT b.id, b.matn, b.sarlavha, h.nomi, h.papka, h.tur, h.yol,"
                "       h.sana, h.eskirgan, b.vektor"
                " FROM bilim_bolak b JOIN bilim_hujjat h ON h.id = b.hujjat_id"
                f" WHERE h.papka IN ({belgilar}) AND h.eskirgan = 0"
                " ORDER BY b.id",
                papkalar_royxati,
            ).fetchall()
        return [dict(q) for q in qatorlar]

    def statistika(self) -> dict:
        with self._ulanish() as u:
            try:
                hujjatlar = u.execute(
                    "SELECT papka, count(*) AS n FROM bilim_hujjat GROUP BY papka"
                ).fetchall()
                bolaklar = u.execute("SELECT count(*) AS n FROM bilim_bolak").fetchone()
            except sqlite3.OperationalError:
                return {"hujjatlar": {}, "bolaklar": 0}
        return {
            "hujjatlar": {q["papka"]: q["n"] for q in hujjatlar},
            "bolaklar": bolaklar["n"] if bolaklar else 0,
        }

    def versiya(self) -> tuple:
        """Indeks o'zgarganini bilish uchun arzon belgi.

        Hujjat qo'shilsa/o'chirilsa (soni), yangilansa (`yangilandi`),
        eskirgan deb belgilansa (yig'indi) yoki bo'laklar soni o'zgarsa —
        qiymat boshqacha bo'ladi.
        """
        try:
            with self._ulanish() as u:
                h = u.execute(
                    "SELECT count(*), coalesce(max(yangilandi), ''),"
                    " coalesce(sum(eskirgan), 0) FROM bilim_hujjat"
                ).fetchone()
                b = u.execute("SELECT count(*) FROM bilim_bolak").fetchone()
        except sqlite3.OperationalError:
            return (0, "", 0, 0)
        return (h[0], h[1], h[2], b[0])

    def eskirgan_deb_belgila(self, yol_bolagi: str) -> int:
        """Eskirgan hujjatni belgilaydi (qonun yangilanganda)."""
        with self._ulanish() as u:
            kursor = u.execute(
                "UPDATE bilim_hujjat SET eskirgan = 1 WHERE yol LIKE ?",
                (f"%{yol_bolagi}%",),
            )
            return kursor.rowcount


def main() -> None:
    ajratgich = argparse.ArgumentParser(description="Bilim bazasini indekslash")
    ajratgich.add_argument(
        "--hammasi", action="store_true", help="o'zgarmaganlarni ham qaytadan indekslash"
    )
    argumentlar = ajratgich.parse_args()

    indeks = Indeks()
    print("Indekslanmoqda…")
    natija = indeks.hammasini_indeksla(majburiy=argumentlar.hammasi)

    for papka, soni in natija.items():
        holat = f"{soni} ta yangi bo'lak" if soni else "o'zgarmagan"
        print(f"  {papka:12} {holat}")

    stat = indeks.statistika()
    print(f"\nJami: {sum(stat['hujjatlar'].values())} hujjat, {stat['bolaklar']} bo'lak")
    for papka, soni in sorted(stat["hujjatlar"].items()):
        print(f"  {papka:12} {soni} hujjat")


if __name__ == "__main__":
    main()

"""Uchala jarayonni ishga tushiradi va yiqilsa qayta ko'taradi.

NEGA BITTA KONTEYNER
--------------------
Tizimda uchta jarayon bor:

  1. `app.main`   — veb panel va ofis ko'rinishi (FastAPI);
  2. `bot.asosiy` — ichki bot (menejerlar uchun) + tender va hisobot jadvali;
  3. `bot.mijoz`  — mijozlar boti (ochiq).

Uchalasi BITTA SQLite fayliga yozadi (`agentlar.db`). Bulut xizmatlarida
disk odatda bitta xizmatga biriktiriladi, ya'ni uch xizmatga bo'lib
yuborsak, ular bir xil bazani ko'rmaydi. Shuning uchun hammasi bitta
konteynerda turadi.

QAYTA KO'TARISH
---------------
Har bir jarayon alohida kuzatiladi. Biri yiqilsa (masalan Telegram
tarmog'i uzilib qolsa) — faqat o'sha qayta ishga tushadi, qolgani
ishlayveradi. Ketma-ket tez yiqilaverса kutish vaqti oshadi
(1s → 2s → 4s … 60s gacha), aks holda log yiqilish xabari bilan
to'lib ketadi.

To'xtatish: SIGTERM (Docker `stop`) — barcha bolalarga uzatiladi.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# Qayta ko'tarishdan oldin kutish (sekund).
ENG_KAM_KUTISH = 1.0
ENG_KOP_KUTISH = 60.0
# Log fayli shu hajmdan oshsa, eskisi `.eski` bo'lib saqlanadi.
# Windows'da Vazifa rejalashtiruvchisi (Task Scheduler) orqali
# ishga tushirilganda konsol bo'lmaydi — chiqish shu faylga tushadi,
# aks holda nima bo'lgani umuman ko'rinmaydi.
LOG_HAJMI = 5 * 1024 * 1024
# Jarayon shu vaqtdan uzoq ishlagan bo'lsa "barqaror" deb hisoblanadi va
# kutish hisoblagichi nolga tushadi.
BARQAROR = 60.0

toxtatilyapti = threading.Event()

# Windowsda bola jarayonni alohida guruhga qo'yamiz — shunda uni
# butun daraxti bilan birga o'ldirish mumkin.
_YANGI_GURUH: dict[str, int] = (
    {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    if os.name == "nt" else {}
)

# Bizga tegishli jarayonlarni tanish uchun belgilar. Boshqa Python
# jarayonlariga (masalan dasturchining o'z ishiga) tegmaymiz.
BIZNIKI = ("-m bot.asosiy", "-m bot.mijoz", "uvicorn app.main:app")


def _daraxtni_oldir(pid: int) -> bool:
    """Jarayonni BOLALARI BILAN birga o'ldiradi (Windows).

    `terminate()` faqat bevosita bolani o'ldiradi. Vazifa
    rejalashtiruvchisi orqali ishga tushirilganda esa zanjir
    uzun bo'ladi va nabiralar tirik qoladi.
    """
    if os.name != "nt":
        return False
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, timeout=20, check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError) as xato:
        log(f"daraxtni o'ldirib bo'lmadi (pid={pid}): {xato}")
        return False


def qoldiqlarni_tozala() -> int:
    """Oldingi ishga tushishdan qolgan jarayonlarni yopadi.

    NEGA KERAK: bitta bot tokeni bilan IKKI nusxa Telegramga ulansa,
    xabarlar ular orasida bo'linadi — javob bir keladi, bir kelmaydi.
    Bu jimgina buziladi, chunki ikkala nusxa ham "ishlayapman" deb
    turadi.

    Shuning uchun ishga tushishdan OLDIN eskilarini yopamiz. O'z
    jarayonimizga va o'z bolalarimizga tegmaydi.
    """
    if os.name != "nt":
        return 0
    ozim = os.getpid()
    buyruq = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or "
        "Name='python.exe'\" | Select-Object ProcessId,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        natija = subprocess.run(
            ["powershell", "-NoProfile", "-Command", buyruq],
            capture_output=True, text=True, timeout=30, check=False,
        )
        yozuvlar = json.loads(natija.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError) as xato:
        log(f"qoldiqlarni tekshirib bo'lmadi: {xato}")
        return 0
    if isinstance(yozuvlar, dict):
        yozuvlar = [yozuvlar]

    tozalandi = 0
    for yozuv in yozuvlar:
        pid = yozuv.get("ProcessId")
        satr = yozuv.get("CommandLine") or ""
        if pid in (None, ozim) or not any(b in satr for b in BIZNIKI):
            continue
        log(f"qoldiq jarayon yopilmoqda: pid={pid}")
        if _daraxtni_oldir(int(pid)):
            tozalandi += 1
    if tozalandi:
        log(f"{tozalandi} ta qoldiq jarayon yopildi")
        time.sleep(3)
    return tozalandi


@dataclass
class Jarayon:
    nomi: str
    buyruq: list[str]
    jarayon: subprocess.Popen | None = None
    kutish: float = ENG_KAM_KUTISH
    yiqilish: int = 0
    _qulf: threading.Lock = field(default_factory=threading.Lock)

    def boshla(self) -> None:
        with self._qulf:
            log(f"{self.nomi}: ishga tushmoqda")
            # Bolalarning chiqishi ham o'sha oqimga tushadi: konsolsiz
            # ishga tushirilganda hammasi log faylida bo'ladi.
            self.jarayon = subprocess.Popen(
                self.buyruq, stdout=_oqim(), stderr=subprocess.STDOUT,
                **_YANGI_GURUH,
            )

    def toxtat(self) -> None:
        with self._qulf:
            jarayon = self.jarayon
        if jarayon is None or jarayon.poll() is not None:
            return
        log(f"{self.nomi}: to'xtatilmoqda")
        # BUTUN DARAXTNI o'ldiramiz, faqat bolani emas.
        #
        # Jonli xato (2026-08-14): vazifa to'xtatilganda `bot.asosiy`
        # jarayonlari tirik qolib ketardi. Natijada uch avlod bir
        # vaqtda Telegramga ulanib, `Conflict: terminated by other
        # getUpdates request` xatosi 167 marta yozildi va xabarlar
        # nusxalar orasida bo'linib ketdi.
        if not _daraxtni_oldir(jarayon.pid):
            try:
                jarayon.terminate()
            except OSError:
                return
        try:
            jarayon.wait(timeout=15)
        except subprocess.TimeoutExpired:
            log(f"{self.nomi}: javob bermadi, majburan yopilmoqda")
            jarayon.kill()

    def kuzat(self) -> None:
        """Jarayon tugaguncha kutadi, keyin qayta ko'taradi."""
        while not toxtatilyapti.is_set():
            boshlandi = time.monotonic()
            self.boshla()
            kod = self.jarayon.wait()
            ishlagan = time.monotonic() - boshlandi

            if toxtatilyapti.is_set():
                return
            self.yiqilish += 1
            log(f"{self.nomi}: to'xtadi (kod={kod}, {ishlagan:.0f} s ishladi)")

            if ishlagan >= BARQAROR:
                # Uzoq ishlagandan keyingi yiqilish — tasodifiy. Kutishni
                # oshirish shart emas, darhol ko'taramiz.
                self.kutish = ENG_KAM_KUTISH
            else:
                self.kutish = min(self.kutish * 2, ENG_KOP_KUTISH)
            log(f"{self.nomi}: {self.kutish:.0f} s dan keyin qayta ko'tariladi")
            if toxtatilyapti.wait(self.kutish):
                return


_log_fayli = None


def _oqim():
    """Bolalarning chiqishi qayerga yozilsin.

    Konsol bo'lsa — konsolga (mahalliy ishlatishda shunday qulay).
    Bo'lmasa (`pythonw`, Vazifa rejalashtiruvchisi, Docker'siz xizmat)
    — log fayliga, aks holda hech narsa ko'rinmaydi.
    """
    global _log_fayli
    if sys.stdout is not None and sys.stdout.isatty():
        return None
    if _log_fayli is None:
        yol = Path(
            os.environ.get("BOSHQARUVCHI_LOG")
            or Path(__file__).resolve().parent / "chiqish" / "ishga_tushir.log"
        )
        yol.parent.mkdir(parents=True, exist_ok=True)
        # Oddiy aylanish: fayl kattalashsa eskisini almashtiramiz.
        # `logging.handlers` ishlatilmaydi — bola jarayonlarga FAYL
        # DASTAGI berilishi kerak, handler emas.
        try:
            if yol.exists() and yol.stat().st_size > LOG_HAJMI:
                yol.replace(yol.with_suffix(".log.eski"))
        except OSError:
            pass
        _log_fayli = open(yol, "a", encoding="utf-8", buffering=1)
    return _log_fayli


def log(matn: str) -> None:
    vaqt = time.strftime("%Y-%m-%d %H:%M:%S")
    qator = f"[{vaqt}] boshqaruvchi | {matn}"
    oqim = _oqim()
    if oqim is None:
        print(qator, flush=True)
    else:
        oqim.write(qator + "\n")


def jarayonlar() -> list[Jarayon]:
    """Ishga tushiriladigan jarayonlar ro'yxati.

    Botni o'chirib qo'yish uchun tokenni bo'sh qoldirish yetadi — bu
    yerda hech narsa o'zgartirilmaydi. Bot o'zi "token yo'q" deb
    yiqiladi va boshqaruvchi uni cheksiz ko'tarishga urinadi, shuning
    uchun token bor-yo'qligi SHU YERDA tekshiriladi.
    """
    port = os.environ.get("PORT", "8000")
    royxat = [
        Jarayon(
            "panel",
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", port],
        )
    ]
    # TOKENLAR `sozlama()` ORQALI O'QILADI, `os.environ` orqali emas.
    #
    # Jonli xato (2026-08-11): mahalliy kompyuterda tokenlar `.env`
    # faylida turadi, muhit o'zgaruvchisida emas. `os.environ` ni
    # tekshirganda ikkala bot ham "token yo'q" deb ishga tushmasdi va
    # faqat panel ko'tarilardi. `sozlama()` ikkalasini ham o'qiydi.
    for nomi, modul, token in (
        ("ichki-bot", "bot.asosiy", _token("bot_token")),
        ("mijoz-bot", "bot.mijoz", _token("mijoz_bot_token")),
    ):
        if token.strip():
            royxat.append(Jarayon(nomi, [sys.executable, "-m", modul]))
        else:
            log(f"{nomi}: token yo'q — ishga tushirilmadi")
    return royxat


def _token(maydon: str) -> str:
    """`.env` yoki muhit o'zgaruvchisidan token (topilmasa bo'sh)."""
    try:
        from app.config import sozlama

        return str(getattr(sozlama(), maydon, "") or "").strip()
    except Exception as xato:  # sozlama o'qilmasa — panel baribir ishlasin
        log(f"sozlama o'qilmadi ({maydon}): {xato}")
        return ""


def main() -> int:
    # Eski nusxalar tirik qolgan bo'lsa — avval ularni yopamiz.
    qoldiqlarni_tozala()

    royxat = jarayonlar()
    if not royxat:
        log("ishga tushiradigan hech narsa yo'q")
        return 1

    def toxtat(signal_raqami, _kadr) -> None:
        log(f"signal {signal_raqami} — to'xtatilmoqda")
        toxtatilyapti.set()
        for j in royxat:
            j.toxtat()

    for belgi in (signal.SIGTERM, signal.SIGINT):
        signal.signal(belgi, toxtat)

    oqimlar = [
        threading.Thread(target=j.kuzat, name=j.nomi, daemon=True) for j in royxat
    ]
    for oqim in oqimlar:
        oqim.start()

    log(f"{len(royxat)} ta jarayon kuzatilmoqda: "
        + ", ".join(j.nomi for j in royxat))
    try:
        while not toxtatilyapti.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        toxtat(signal.SIGINT, None)

    for oqim in oqimlar:
        oqim.join(timeout=20)
    log("hammasi to'xtadi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

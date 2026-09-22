"""Shouni yig'adi: videoni HTML ning ichiga joylaydi.

Nashr qilingan sahifada tashqi faylga murojaat bloklanadi, shuning uchun
video `data:` URI bo'lib matnning ichida turishi kerak. Bitta fayl — hech
qanday qo'shimcha papkasiz ishlaydi.
"""

import base64
import io
from pathlib import Path

BU = Path(__file__).parent
MANBA = BU / "_shou-manba.html"
CHIQISH = BU / "agentlar-shou.html"
VIDEOLAR = {
    "__VIDEO_OBSIDIAN__": BU / "media" / "obsidian-graf.mp4",
    "__VIDEO_OFIS__": BU / "media" / "ofis-3d.mp4",
}


def joyla(matn: str, belgi: str, fayl: Path, tur: str) -> str:
    if belgi not in matn:
        raise SystemExit(f"belgi topilmadi: {belgi}")
    b64 = base64.b64encode(fayl.read_bytes()).decode("ascii")
    return matn.replace(belgi, f"data:{tur};base64,{b64}")


matn = io.open(MANBA, encoding="utf-8").read()
for belgi, fayl in VIDEOLAR.items():
    matn = joyla(matn, belgi, fayl, "video/mp4")
io.open(CHIQISH, "w", encoding="utf-8").write(matn)

mb = CHIQISH.stat().st_size / 1024 / 1024
print(f"Yaratildi: {CHIQISH}")
print(f"Hajmi    : {mb:.2f} MB  (chegara 16 MB)")
if mb > 15:
    print("DIQQAT: chegaraga yaqin — videoni ko'proq siqish kerak.")

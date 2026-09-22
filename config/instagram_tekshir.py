"""`.env` dagi Instagram tokenini tekshiradi va USER_ID ni topib beradi.

Graph API Explorer'da qo'lda so'rov yozish shart emas: tokenni `.env` ga
qo'ysangiz, bu skript qolganini o'zi qiladi —

  1) token haqiqiymi va qachon tugaydi;
  2) qaysi ruxsatlar berilgan, qaysi biri YETISHMAYAPTI;
  3) ulangan Facebook sahifasi va uning Instagram akkaunti;
  4) `INSTAGRAM_USER_ID` — tayyor holda, nusxa olish uchun.

Token ekranga CHIQMAYDI — faqat uzunligi va oxirgi 4 belgisi.

    .venv\\Scripts\\python config/instagram_tekshir.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ILDIZ = Path(__file__).resolve().parent.parent
ASOS = "https://graph.facebook.com/v21.0"

# Nilufar uchun zarur ruxsatlar. `instagram_manage_insights` bo'lmasa,
# qamrov/saqlash/ulashish kelmaydi — faqat layk va komment qoladi.
KERAKLI = {
    "instagram_basic": "asosiy — profil va postlar",
    "pages_show_list": "Facebook sahifalar ro'yxati",
    "pages_read_engagement": "sahifa ma'lumotini o'qish",
    "instagram_manage_insights": "QAMROV, SAQLASH, ULASHISH — busiz statistika yo'q",
}


def _sorov(yol: str, token: str, **parametr) -> dict:
    parametr["access_token"] = token
    havola = f"{ASOS}/{yol}?{urllib.parse.urlencode(parametr)}"
    try:
        with urllib.request.urlopen(havola, timeout=30) as javob:
            return json.load(javob)
    except urllib.error.HTTPError as xato:
        tana = xato.read().decode("utf-8", "replace")
        try:
            return {"__xato__": json.loads(tana).get("error", {})}
        except ValueError:
            return {"__xato__": {"message": tana[:200]}}
    except Exception as xato:  # tarmoq
        return {"__xato__": {"message": str(xato)}}


def _xato_chiqar(javob: dict) -> bool:
    xato = javob.get("__xato__")
    if not xato:
        return False
    print("  ❌ " + str(xato.get("message") or "noma'lum xato"))
    if xato.get("code") == 190:
        print("     → Token eskirgan yoki bekor qilingan. Yangisini oling.")
    return True


def main() -> int:
    qiymatlar = dotenv_values(ILDIZ / ".env")
    token = (qiymatlar.get("INSTAGRAM_TOKEN") or "").strip()
    user_id = (qiymatlar.get("INSTAGRAM_USER_ID") or "").strip()

    if not token:
        print("❌ .env da INSTAGRAM_TOKEN yo'q.")
        print("   docs/instagram-token.md ga qarang.")
        return 1

    print(f"Token: {len(token)} belgi, oxiri …{token[-4:]}\n")

    # 1. Token haqiqiymi va qachon tugaydi
    print("1) Token tekshiruvi")
    tekshir = _sorov("debug_token", token, input_token=token)
    if _xato_chiqar(tekshir):
        return 1
    malumot = tekshir.get("data", {})
    if not malumot.get("is_valid"):
        print("  ❌ Token yaroqsiz.")
        return 1

    tugash = malumot.get("expires_at")
    if not tugash:
        print("  ✅ Token haqiqiy, muddati cheksiz (System User token)")
    else:
        from datetime import datetime, timezone

        sana = datetime.fromtimestamp(tugash, tz=timezone.utc)
        qolgan = (sana - datetime.now(timezone.utc)).days
        belgi = "✅" if qolgan > 7 else "⚠️"
        print(f"  {belgi} Token haqiqiy, {qolgan} kun qoldi ({sana:%Y-%m-%d})")
        if qolgan < 7:
            print("     → Uzaytiring: Access Token Debug Tool → Extend Access Token")

    # 2. Ruxsatlar
    print("\n2) Ruxsatlar")
    berilgan = set(malumot.get("scopes") or [])
    yetishmaydi = []
    for ruxsat, izoh in KERAKLI.items():
        if ruxsat in berilgan:
            print(f"  ✅ {ruxsat}")
        else:
            print(f"  ❌ {ruxsat} — {izoh}")
            yetishmaydi.append(ruxsat)

    # 3. Sahifa va Instagram akkaunti
    print("\n3) Ulangan akkauntlar")
    hisoblar = _sorov("me/accounts", token, fields="id,name,instagram_business_account")
    if _xato_chiqar(hisoblar):
        return 1

    topilgan: list[tuple[str, str]] = []
    for sahifa in hisoblar.get("data", []):
        ig = sahifa.get("instagram_business_account") or {}
        if ig.get("id"):
            print(f"  ✅ {sahifa.get('name')} → Instagram ID: {ig['id']}")
            topilgan.append((sahifa.get("name", ""), ig["id"]))
        else:
            print(f"  ⚠️ {sahifa.get('name')} — Instagram akkaunti ulanmagan")

    if not topilgan:
        print("\n  ❌ Instagram Business akkaunti topilmadi.")
        print("     Tekshiring: Instagram akkaunt Business/Creator turidami")
        print("     va Facebook sahifasiga ulanganmi.")
        return 1

    # 4. USER_ID
    print("\n4) INSTAGRAM_USER_ID")
    nom, topilgan_id = topilgan[0]
    if not user_id:
        print("  ⚠️ .env da yo'q. Quyidagini qo'shing:\n")
        print(f"     INSTAGRAM_USER_ID={topilgan_id}")
    elif user_id == topilgan_id:
        print(f"  ✅ To'g'ri: {user_id} ({nom})")
    else:
        print(f"  ⚠️ .env dagi: {user_id}")
        print(f"     Topilgani : {topilgan_id} ({nom})")

    # 5. Haqiqiy so'rov
    print("\n5) Jonli so'rov")
    profil = _sorov(
        topilgan_id, token, fields="username,followers_count,media_count"
    )
    if _xato_chiqar(profil):
        return 1
    print(
        f"  ✅ @{profil.get('username')} — "
        f"{profil.get('followers_count')} obunachi, "
        f"{profil.get('media_count')} post"
    )

    if yetishmaydi:
        print(f"\n⚠️ {len(yetishmaydi)} ta ruxsat yetishmayapti — statistika chala keladi.")
        return 1

    print("\n✅ Hammasi tayyor. Nilufar ishlashi mumkin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

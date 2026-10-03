"""Ilova tokenini tekshirish — yordamchiga faqat kirgan xaridor yozadi.

NEGA BACKEND ORQALI
-------------------
Token climavent-back'da imzolanadi va uning kaliti bizda YO'Q (va
bo'lmasligi kerak). Shuning uchun tokenni o'zimiz tekshirmaymiz —
uni backendning o'ziga ko'rsatamiz: `GET /api/users/one/{id}`. 200
qaytsa token tirik va profil (telefon, ism) shu javobdan olinadi.

ID ALMASHTIRISHGA QARSHI. Backend bu yo'lda boshqa foydalanuvchining
id'sini rad etadimi — bizga noma'lum. Shuning uchun token ichidagi id
(JWT `payload`) ham solishtiriladi: u yozilgan bo'lsa va so'rovdagi
id'ga mos kelmasa — rad. Imzoni tekshirmaymiz (kalit yo'q), lekin
imzoni backend allaqachon tekshirdi.

KESH. Har xabarda backendga borish shart emas: tasdiqlangan token
`KESH_SONIYA` davomida eslab qolinadi. Token o'zi bundan uzoqroq
yashaydi, ya'ni kesh chiqib ketgan tokenni ochiq qoldirmaydi.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from .yadro import Foydalanuvchi

log = logging.getLogger("yordamchi.kirish")

KESH_SONIYA = 600.0
VAQT_CHEGARASI = 10.0

# Token ichida id shu kalitlardan birida turadi (backend bir xil emas).
ID_KALITLARI = ("id", "userId", "user_id", "sub")


class KirishXatosi(Exception):
    """Token yaroqsiz yoki backend uni tasdiqlamadi."""


def token_yuki(token: str) -> dict[str, Any] | None:
    """JWT ichidagi ma'lumot (imzosiz o'qiladi). JWT bo'lmasa — None."""
    bolaklar = token.split(".")
    if len(bolaklar) != 3:
        return None
    yuk = bolaklar[1] + "=" * (-len(bolaklar[1]) % 4)
    try:
        malumot = json.loads(base64.urlsafe_b64decode(yuk))
    except (ValueError, json.JSONDecodeError):
        return None
    return malumot if isinstance(malumot, dict) else None


def token_idsi(token: str) -> str | None:
    """JWT ichidagi foydalanuvchi id'si. JWT bo'lmasa yoki id yo'q — None."""
    malumot = token_yuki(token)
    if malumot is None:
        return None
    for kalit in ID_KALITLARI:
        qiymat = malumot.get(kalit)
        if qiymat not in (None, ""):
            return str(qiymat)
    return None


def _profil(javob: Any) -> dict[str, Any]:
    """`client`/`user`/`data` ichida bo'lishi mumkin (ilova ham shunday o'qiydi)."""
    if not isinstance(javob, dict):
        return {}
    ichki = javob.get("client") or javob.get("user") or javob.get("data")
    return ichki if isinstance(ichki, dict) else javob


def _toza_ism(qiymat: Any) -> str:
    """Eski ro'yxatdan o'tish ism o'rniga telefon yozgan bo'lishi mumkin."""
    matn = str(qiymat or "").strip()
    if not matn or matn == "null" or matn.replace("+", "").replace(" ", "").isdigit():
        return ""
    return matn


class Kirish:
    def __init__(self, asos: str, transport: httpx.AsyncBaseTransport | None = None):
        self.asos = asos.rstrip("/")
        self._transport = transport
        self._kesh: dict[str, tuple[float, Foydalanuvchi]] = {}

    async def tekshir(self, token: str, foydalanuvchi_id: int) -> Foydalanuvchi:
        token = (token or "").strip()
        if not token:
            raise KirishXatosi("token yo'q")

        ichidagi = token_idsi(token)
        if ichidagi is not None and ichidagi != str(foydalanuvchi_id):
            raise KirishXatosi("token boshqa foydalanuvchiniki")
        # Muddati o'tgan token backendga yuborilmaydi: ilova 401 ni ko'rib
        # tokenni yangilaydi va qayta yuboradi.
        muddat = (token_yuki(token) or {}).get("exp")
        if isinstance(muddat, (int, float)) and muddat < time.time():
            raise KirishXatosi("token muddati o'tgan")

        kalit = hashlib.sha256(f"{foydalanuvchi_id}:{token}".encode()).hexdigest()
        hozir = time.monotonic()
        eslangan = self._kesh.get(kalit)
        if eslangan and hozir - eslangan[0] < KESH_SONIYA:
            return eslangan[1]

        try:
            async with httpx.AsyncClient(
                timeout=VAQT_CHEGARASI, transport=self._transport
            ) as mijoz:
                javob = await mijoz.get(
                    f"{self.asos}/api/users/one/{foydalanuvchi_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as xato:
            # Backend ishlamasa xaridor ham hech narsa qila olmaydi —
            # lekin bu «token yaroqsiz» EMAS, ilova chiqarib yubormasin.
            log.warning("backend javob bermadi: %s", xato)
            raise ConnectionError("backend javob bermadi") from xato

        if javob.status_code in (401, 403, 404):
            # Tashxis uchun: token QIYMATI yozilmaydi, faqat ichidagi
            # maydon nomlari va backend javobining boshi.
            log.info("backend rad etdi: %s %s; token maydonlari=%s",
                     javob.status_code, javob.text[:160],
                     sorted((token_yuki(token) or {}).keys()))
            raise KirishXatosi(f"backend rad etdi ({javob.status_code})")
        if javob.status_code >= 400:
            raise ConnectionError(f"backend xatosi ({javob.status_code})")

        try:
            profil = _profil(javob.json())
        except ValueError:
            profil = {}
        # Javobdagi id boshqa bo'lsa — backend so'ralganini emas, token
        # egasini qaytargan. Bunda ham rad: kim yozayotgani noaniq.
        javob_id = profil.get("id") or profil.get("userId")
        if javob_id not in (None, "") and str(javob_id) != str(foydalanuvchi_id):
            raise KirishXatosi("backend boshqa foydalanuvchini qaytardi")

        ism = " ".join(
            x for x in (_toza_ism(profil.get("name") or profil.get("first_name")),
                        _toza_ism(profil.get("surname") or profil.get("last_name")))
            if x
        )
        kim = Foydalanuvchi(
            id=foydalanuvchi_id,
            telefon=str(profil.get("phone_number") or profil.get("phone") or "").strip(),
            ism=ism,
        )
        self._kesh[kalit] = (hozir, kim)
        # Kesh cheksiz o'smasin: eskirganlar har safar tozalanadi.
        for k in [k for k, (vaqt, _) in self._kesh.items() if hozir - vaqt >= KESH_SONIYA]:
            self._kesh.pop(k, None)
        return kim

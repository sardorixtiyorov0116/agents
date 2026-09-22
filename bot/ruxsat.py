"""Bot uchun ruxsat tekshiruvi.

Ikki daraja:
  1) umumiy whitelist — ro'yxatda yo'q foydalanuvchi bilan bot umuman
     gaplashmaydi;
  2) agent darajasidagi ruxsat — masalan HR ma'lumoti hammaga emas. Bu
     tekshiruv router REJA tuzgandan KEYIN bo'ladi: foydalanuvchi qaysi agent
     kerakligini bilishi shart emas, lekin ruxsatsiz agent ishga tushmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Sozlama
from app.router import Reja

# Qo'shimcha ruxsat talab qiladigan agentlar: rol -> ruxsat ro'yxati nomi.
CHEKLANGAN_AGENTLAR = {"hr-assist": "hr", "catalog-admin": "katalog"}

RAD_SABABI = {
    "hr": "Bu so'rov HR ma'lumotiga tegadi, sizda esa HR ruxsati yo'q. "
          "So'rov bajarilmadi.",
    "katalog": "Bu so'rov katalogni o'zgartiradi, sizda esa katalog ruxsati yo'q. "
               "So'rov bajarilmadi.",
}


@dataclass(frozen=True)
class RuxsatQarori:
    """Ruxsat berildimi va berilmasa nima uchun."""

    ruxsat: bool
    sabab: str = ""


class Ruxsat:
    def __init__(self, sozlama: Sozlama):
        self.hammasi = sozlama.ruxsat_etilgan_idlar
        self.hr = sozlama.hr_idlar
        # Katalog ro'yxati bo'sh bo'lsa — umumiy ro'yxatdagi hamma. Aks holda
        # yangi sozlama qo'shilishi bilan katalog agenti hech kimga ishlamay
        # qolardi; yozish baribir tasdiqdan o'tadi.
        self.katalog = sozlama.katalog_idlar or self.hammasi

    def sozlanganmi(self) -> bool:
        """Whitelist bo'sh bo'lsa bot hech kimga javob bermaydi (xavfsiz standart)."""
        return bool(self.hammasi)

    def foydalanuvchi(self, tg_id: int | None) -> RuxsatQarori:
        if tg_id is None:
            return RuxsatQarori(False, "Foydalanuvchi aniqlanmadi.")
        if not self.hammasi:
            return RuxsatQarori(
                False,
                "Bot hali sozlanmagan: ruxsat etilgan foydalanuvchilar ro'yxati bo'sh "
                "(.env dagi BOT_RUXSAT_ETILGAN_ID).",
            )
        if tg_id not in self.hammasi:
            return RuxsatQarori(
                False, f"Sizda bu tizimga ruxsat yo'q. Sizning ID: {tg_id}"
            )
        return RuxsatQarori(True)

    def reja(self, tg_id: int, reja: Reja) -> RuxsatQarori:
        """Rejadagi agentlarning har biriga foydalanuvchi haqli ekanini tekshiradi."""
        for qadam in reja.qadamlar:
            royxat_nomi = CHEKLANGAN_AGENTLAR.get(qadam.agent)
            if royxat_nomi is None:
                continue
            if tg_id not in getattr(self, royxat_nomi, set()):
                return RuxsatQarori(False, RAD_SABABI[royxat_nomi])
        return RuxsatQarori(True)

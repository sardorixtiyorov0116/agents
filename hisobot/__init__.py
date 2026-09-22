"""Davriy hisobot — tizim qancha ish qilgani.

NEGA KERAK: hozir tizim foyda berayotganini hech kim o'lchamaydi. Busiz
u "qiziq o'yinchoq" bo'lib qoladi — ishlatilmasa ham, buzilsa ham hech
kim sezmaydi.

RAQAMLAR KODDAN. Bu yerda model umuman ishlatilmaydi: hammasi SQL
agregatsiyasi. Sabab oddiy — hisobot raqamlari har safar bir xil
chiqishi shart, va u tekin, bir zumda tayyorlanadi.

Eng qimmatli qismi — "javob berolmagan savollar". U bilim bazasiga
nima qo'shish kerakligini aytadi, ya'ni tizim o'zini yaxshilash yo'lini
ko'rsatadi.
"""

from .yigish import Hisobot, Davr, hisobot_matni, hisobot_yig

__all__ = ["Davr", "Hisobot", "hisobot_matni", "hisobot_yig"]

"""Javob tili — xaridor ilovasi qaysi tilda bo'lsa, javob ham o'sha tilda.

JONLI XATO (2026-10-03): ilova ruscha, savol ruscha — javob o'zbekcha
keldi. Sabab ikkita: ilova tilni yubormas edi, agentlar va presenter
shablonlari esa faqat o'zbekcha.

IKKI YO'L
---------
  1. DOIMIY matnlar (salom, chegara, «menejerga yubordim», narx javobi)
     — shu yerda uch tilda yozilgan. Model chaqirilmaydi.
  2. AGENT javobi (hisob, tanlov) — o'zbekcha yig'iladi va oxirida
     TARJIMA qilinadi. Agentlarning o'zini ko'p tilli qilish o'nlab
     shablon va promptni o'zgartirish degani; tarjima esa bitta arzon
     chaqiruv.

TARJIMA HECH NARSA QO'SHMAYDI. Model nomi, raqam, birlik, qator tartibi
o'zgarmaydi — buni prompt talab qiladi. Tarjima yiqilsa o'zbekcha matn
qaytadi: mijoz quruq qolgandan ko'ra o'zbekcha javob yaxshi.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from app.llm import matn_yig

log = logging.getLogger("yordamchi.til")

TILLAR = ("uz", "ru", "en")
ASOSIY = "uz"

Tarjimon = Callable[[str, str], Awaitable[str]]


def til(qiymat: Any) -> str:
    """Noma'lum til — o'zbekcha."""
    q = str(qiymat or "").strip().lower()[:2]
    return q if q in TILLAR else ASOSIY


MATNLAR: dict[str, dict[str, str]] = {
    "salom": {
        "uz": (
            "Assalomu alaykum! Men Climavent yordamchisiman.\n\n"
            "Ventilyatsiya yoki konditsioner bo'yicha yozing: xona maydoni, "
            "balandligi, necha kishi ishlashi — men hisoblab, katalogdan mos "
            "uskunani topaman."
        ),
        "ru": (
            "Здравствуйте! Я ассистент Climavent.\n\n"
            "Напишите про вентиляцию или кондиционирование: площадь, высоту "
            "помещения, сколько человек работает — я рассчитаю и подберу "
            "оборудование из каталога."
        ),
        "en": (
            "Hello! I'm the Climavent assistant.\n\n"
            "Tell me about your ventilation or air-conditioning needs: room "
            "area, ceiling height, how many people work there — I'll size it "
            "and pick matching equipment from the catalog."
        ),
    },
    "xayr": {
        "uz": "Arzimaydi! Yana savolingiz bo'lsa — yozavering.",
        "ru": "Пожалуйста! Если будут вопросы — пишите.",
        "en": "You're welcome! Write any time you have a question.",
    },
    # Javob oxiridagi eslatma: hisob TAXMINIY, va mijoz keyingi qadamni
    # bilishi kerak — ilovada KP ni o'zi darhol oladi.
    "izoh": {
        "uz": (
            "\n\nBu dastlabki hisob. Mahsulotni savatga qo'shib, KP ni darhol "
            "olishingiz mumkin. Savol qolsa — menejerimiz bog'lanadi."
        ),
        "ru": (
            "\n\nЭто предварительный расчёт. Добавьте товар в корзину — КП "
            "сформируется сразу. Если останутся вопросы — менеджер свяжется с вами."
        ),
        "en": (
            "\n\nThis is a preliminary estimate. Add the product to your cart to "
            "get the quote right away. If questions remain, a manager will contact you."
        ),
    },
    "menejerga": {
        "uz": (
            "Bu savolga menejerimiz aniqroq javob beradi. Savolingizni unga "
            "yubordim — ish vaqtida siz bilan bog'lanadi.\n\nShoshilinch bo'lsa: {telefon}"
        ),
        "ru": (
            "На этот вопрос точнее ответит менеджер. Я передал ему ваш вопрос — "
            "он свяжется с вами в рабочее время.\n\nЕсли срочно: {telefon}"
        ),
        "en": (
            "A manager can answer this more precisely. I've passed your question "
            "on — they'll contact you during business hours.\n\nIf urgent: {telefon}"
        ),
    },
    "kunlik": {
        "uz": (
            "Bugungi savollar chegarasiga yetdingiz.\n\nSavolingizni menejerimizga "
            "yubordim — u bog'lanadi. Katalog va savat esa cheklovsiz ishlaydi."
        ),
        "ru": (
            "Вы достигли лимита вопросов на сегодня.\n\nЯ передал ваш вопрос "
            "менеджеру — он свяжется с вами. Каталог и корзина работают без ограничений."
        ),
        "en": (
            "You've reached today's question limit.\n\nI've passed your question to "
            "a manager — they'll get in touch. The catalog and cart work without limits."
        ),
    },
    "sekinroq": {
        "uz": "Biroz sekinroq yozing — bir daqiqada bir necha savolga javob bera olaman.",
        "ru": "Пишите чуть медленнее — я отвечаю на несколько вопросов в минуту.",
        "en": "Please slow down a little — I can answer a few questions per minute.",
    },
    "xato": {
        "uz": (
            "Kechirasiz, hozir texnik nosozlik. Savolingizni menejerga yubordim.\n\n"
            "Shoshilinch bo'lsa: {telefon}"
        ),
        "ru": (
            "Извините, техническая неполадка. Я передал ваш вопрос менеджеру.\n\n"
            "Если срочно: {telefon}"
        ),
        "en": (
            "Sorry, there's a technical problem. I've passed your question to a "
            "manager.\n\nIf urgent: {telefon}"
        ),
    },
    "bosh": {"uz": "Savolingizni yozing.", "ru": "Напишите ваш вопрос.", "en": "Type your question."},
    # Narx javobi (`yadro.narx_matni`).
    "narxi": {"uz": "Narxi: {narx} so'm (QQS bilan)", "ru": "Цена: {narx} сум (с НДС)",
              "en": "Price: {narx} UZS (incl. VAT)"},
    "savatga": {
        "uz": "Savatga qo'shsangiz, KP darhol tayyor bo'ladi.",
        "ru": "Добавьте в корзину — КП будет готово сразу.",
        "en": "Add it to your cart and the quote is ready right away.",
    },
    "katalogda_bor": {"uz": "{model} — katalogimizda bor.", "ru": "{model} — есть в нашем каталоге.",
                      "en": "{model} is in our catalog."},
    "narx_menejerda": {
        "uz": (
            "Bu model narxi buyurtma parametrlariga bog'liq (o'lcham, ijro, "
            "miqdor). Savolingizni menejerga yubordim — u hisoblab beradi."
        ),
        "ru": (
            "Цена этой модели зависит от параметров заказа (размер, исполнение, "
            "количество). Я передал вопрос менеджеру — он рассчитает."
        ),
        "en": (
            "The price of this model depends on the order details (size, version, "
            "quantity). I've passed your question to a manager who will calculate it."
        ),
    },
    "topilmadi": {
        "uz": "«{model}» nomli modelni katalogimizdan topa olmadim.",
        "ru": "Модель «{model}» в нашем каталоге не нашёл.",
        "en": "I couldn't find a model called “{model}” in our catalog.",
    },
    "balki": {"uz": "Balki bulardan biri?", "ru": "Может, одна из этих?", "en": "Maybe one of these?"},
}


def matn(kalit: str, tili: str, **qiymatlar: Any) -> str:
    shablon = MATNLAR[kalit].get(tili) or MATNLAR[kalit][ASOSIY]
    return shablon.format(**qiymatlar) if qiymatlar else shablon


TIL_NOMI = {"ru": "Russian", "en": "English"}

# Birlik va so'zlar — tilga xos. JONLI XATO (2026-10-03): umumiy misolda
# «12 people» turgani uchun model RUSCHA matnga ham «12 people» yozdi.
BIRLIKLAR = {
    "ru": "m³/soat -> м³/ч, m² -> м², m -> м, mm -> мм, kVt -> кВт, Pa -> Па, "
          "12 kishi -> 12 человек, dona -> шт.",
    "en": "m³/soat -> m³/h, kVt -> kW, 12 kishi -> 12 people, dona -> pcs.",
}

TARJIMA_PROMPT = """You translate replies of an HVAC equipment shop assistant from Uzbek into {til}.

STRICT RULES:
- Output ONLY the {til} translation, nothing before or after it. Every word must be {til}.
- Keep EVERY model name, product code and number exactly as written (e.g. ВК-250С, Ø250, 1 080, 6.11).
- Units and common words: {birliklar}
- Keep the same line breaks, numbering, bullets and emoji.
- Do not add, remove, soften or explain anything. Do not answer the question yourself.
- Use the industry's usual {til} HVAC terminology."""


def tarjimon_yasa(llm: Any) -> Tarjimon:
    """`llm` — `AnthropicLlm` (tez va arzon model bilan)."""

    async def tarjima(matn_uz: str, tili: str) -> str:
        if tili == ASOSIY or not matn_uz.strip() or tili not in TIL_NOMI:
            return matn_uz
        try:
            javob = await llm.javob(
                system=TARJIMA_PROMPT.format(til=TIL_NOMI[tili], birliklar=BIRLIKLAR[tili]),
                messages=[{"role": "user", "content": matn_uz}],
                max_tokens=2000,
            )
            natija = matn_yig(javob)
            return natija or matn_uz
        except Exception:
            log.warning("tarjima bajarilmadi (%s) — o'zbekcha qaytadi", tili, exc_info=True)
            return matn_uz

    return tarjima


async def tarjimasiz(matn_uz: str, _tili: str) -> str:
    return matn_uz

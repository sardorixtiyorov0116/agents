"""`python -m yordamchi` — yordamchi serverini ishga tushiradi.

Port `PORT` muhit o'zgaruvchisidan (Railway shuni beradi), bo'lmasa 8000.
Docker'da: start buyrug'ini `python -m yordamchi` qilib qo'ying.
"""

from __future__ import annotations

import logging
import os

import uvicorn

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s", level=logging.INFO
)
# `httpx` URL ni to'liq yozadi, Telegram URL ichida esa BOT TOKENI turadi.
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    uvicorn.run(
        "yordamchi.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=True,
    )

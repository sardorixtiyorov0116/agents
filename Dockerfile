# Jihozvent agentlar tizimi.
#
# Uchala jarayon (panel + ikkita bot) bitta konteynerda ishlaydi —
# sababi `ishga_tushir.py` boshida yozilgan: hammasi bitta SQLite
# fayliga yozadi.

FROM python:3.13-slim

# VAQT MINTAQASI — shart. Tender har kuni 09:00 da, hisobot dushanba
# kuni yuboriladi. Konteyner standart holda UTC da turadi, ya'ni xabar
# Toshkent vaqti bilan 14:00 da kelardi.
ENV TZ=Asia/Tashkent \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata ca-certificates \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Avval faqat requirements — kod o'zgarganda paketlar qayta o'rnatilmasin.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# EMBEDDING MODELINI OLDINDAN YUKLAYMIZ (~120 MB).
#
# Aks holda birinchi savol modelni yuklab olishni kutadi: 30+ sekund va
# tarmoq uzilsa umuman ishlamaydi. Bu qatlam kod o'zgarganda qayta
# bajarilmaydi.
RUN python -c "from fastembed import TextEmbedding; \
TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

# Ma'lumot saqlanadigan papkalar. `agentlar.db` va tayyor KP hujjatlari
# shu yerda — docker-compose'da (yoki bulutda) DISK biriktiriladi,
# aks holda konteyner qayta ishga tushganda hamma narsa yo'qoladi.
ENV BAZA_YOLI=/data/agentlar.db \
    KP_YOLI=/data/kp \
    TEXNIK_KESH_YOLI=/data/texnik_parametrlar.json \
    VAULT_YOLI=/app/vault
RUN mkdir -p /data/kp

EXPOSE 8000

# Konteyner sog'ligini panel bilan tekshiramiz. `?tekshir=1` ATAYLAB
# ishlatilmaydi — u har safar Anthropic'ga so'rov yuboradi (pul).
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import httpx,sys; \
sys.exit(0 if httpx.get('http://127.0.0.1:8000/salomat', timeout=8).status_code==200 else 1)"

CMD ["python", "ishga_tushir.py"]

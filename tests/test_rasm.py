"""Katalogga rasm biriktirish.

XAVFSIZLIK MODELI shu yerda sinaladi. Qolgan hamma o'zgarishni model
rejalashtiradi, rasm bilan esa bunday qilib bo'lmaydi: model surat
yarata olmaydi, u faqat HAVOLA yozishi mumkin — va havolani o'ylab
topib qo'yadi. Shuning uchun zanjir teskari:

    rasm mazmuni ODAMDAN -> backend Cloudinary'ga qo'yib HAVOLA beradi
    -> aynan o'sha havola mahsulotga bog'lanadi.

Ya'ni havola hech qachon modeldan kelmaydi, va shuning uchun rasm
amallari `AMALLAR` jadvalida YO'Q.
"""

from __future__ import annotations

import json

import httpx
import pytest

from integrations import AMALLAR, ClimaventYozuvchi, YozishXatosi

pytestmark = pytest.mark.oz_transporti

RASM = b"\xff\xd8\xff\xe0sinov-surat"
HAVOLA = "https://res.cloudinary.com/dne7ddv2a/image/upload/v1/klapan.png"


class SoxtaJavob:
    def __init__(self, holat: int, tana):
        self.status_code = holat
        self._tana = tana
        self.text = tana if isinstance(tana, str) else json.dumps(tana)

    def json(self):
        if isinstance(self._tana, str):
            raise ValueError("JSON emas")
        return self._tana


class SoxtaHttp:
    """Yuklash va biriktirish so'rovlarini yozib boradi."""

    def __init__(self, yuklash=None, biriktirish=None, xato=None):
        self.yuklash = yuklash if yuklash is not None else SoxtaJavob(
            201, {"image_link": HAVOLA}
        )
        self.biriktirish = biriktirish if biriktirish is not None else SoxtaJavob(
            201, {"id": 5}
        )
        self.xato = xato
        self.sorovlar: list[dict] = []

    async def post(self, manzil, files=None, headers=None, timeout=None):
        self.sorovlar.append(
            {"metod": "POST", "manzil": manzil, "files": files, "sarlavha": headers}
        )
        if self.xato:
            raise self.xato
        return self.yuklash

    async def request(self, metod, manzil, json=None, headers=None, timeout=None):
        self.sorovlar.append(
            {"metod": metod, "manzil": manzil, "tana": json, "sarlavha": headers}
        )
        return self.biriktirish


def yozuvchi(http: SoxtaHttp | None = None, kalit: str = "sinov-kalit"):
    return ClimaventYozuvchi(
        asos="https://sinov.local", token="", xizmat_kaliti=kalit,
        mijoz=http or SoxtaHttp(),
    )


# --- xavfsizlik chegarasi ----------------------------------------------------


def test_rasm_amallari_model_jadvalida_yoq():
    """Model havola o'ylab topib biriktira olmasligi kerak."""
    assert not [n for n in AMALLAR if "rasm" in n]
    assert not [
        a for a in AMALLAR.values() if "image" in a.yol or "product-images" in a.yol
    ]


async def test_guvohnomasiz_rasm_yuklanmaydi():
    http = SoxtaHttp()

    with pytest.raises(YozishXatosi, match="SERVICE_API_KEY"):
        await yozuvchi(http, kalit="").rasm_yukla(RASM)

    assert http.sorovlar == []


async def test_bosh_rasm_yuborilmaydi():
    http = SoxtaHttp()

    with pytest.raises(YozishXatosi, match="bo'sh"):
        await yozuvchi(http).rasm_yukla(b"")

    assert http.sorovlar == []


# --- yuklash -----------------------------------------------------------------


async def test_rasm_multipart_bolib_ketadi():
    http = SoxtaHttp()

    havola = await yozuvchi(http).rasm_yukla(RASM, "klapan.png")

    assert havola == HAVOLA
    sorov = http.sorovlar[0]
    assert sorov["manzil"].endswith("/api/images/upload-image")
    assert sorov["files"]["file"] == ("klapan.png", RASM)
    # Multipart chegarasini `httpx` yozadi — biz `Content-Type` qo'ymaymiz.
    assert "Content-Type" not in sorov["sarlavha"]
    assert sorov["sarlavha"]["X-API-Key"] == "sinov-kalit"


@pytest.mark.parametrize(
    "tana",
    [
        {"image_link": HAVOLA},
        {"url": HAVOLA},
        {"secure_url": HAVOLA},
        {"data": {"image_link": HAVOLA}},
        HAVOLA,
    ],
)
async def test_turli_javob_shaklidan_havola_ajratiladi(tana):
    """Backend javob shaklini kafolatlamaydi."""
    http = SoxtaHttp(yuklash=SoxtaJavob(201, tana))

    assert await yozuvchi(http).rasm_yukla(RASM) == HAVOLA


async def test_havolasiz_javob_muvaffaqiyat_deb_qabul_qilinmaydi():
    """Jimgina 'yuklandi' deyish eng yomon holat — rasm yo'q, xato ham yo'q."""
    http = SoxtaHttp(yuklash=SoxtaJavob(201, {"holat": "ok"}))

    with pytest.raises(YozishXatosi, match="havola topilmadi"):
        await yozuvchi(http).rasm_yukla(RASM)


async def test_ruxsat_berilmasa_ochiq_aytiladi():
    http = SoxtaHttp(yuklash=SoxtaJavob(403, {"message": "yo'q"}))

    with pytest.raises(YozishXatosi, match="ruxsat bermadi"):
        await yozuvchi(http).rasm_yukla(RASM)


async def test_tarmoq_xatosi_yutilmaydi():
    http = SoxtaHttp(xato=httpx.ConnectError("ulanmadi"))

    with pytest.raises(YozishXatosi, match="tarmoq"):
        await yozuvchi(http).rasm_yukla(RASM)


# --- biriktirish -------------------------------------------------------------


async def test_biriktirish_havola_va_id_yuboradi():
    http = SoxtaHttp()

    await yozuvchi(http).rasmni_biriktir(158, HAVOLA)

    sorov = http.sorovlar[0]
    assert sorov["manzil"].endswith("/api/product-images/create")
    assert sorov["tana"] == {"image_link": HAVOLA, "product_id": 158}


async def test_bosh_havola_biriktirilmaydi():
    http = SoxtaHttp()

    with pytest.raises(YozishXatosi, match="havolasi bo'sh"):
        await yozuvchi(http).rasmni_biriktir(158, "")

    assert http.sorovlar == []


async def test_rasm_qoy_ikkala_bosqichni_bajaradi():
    http = SoxtaHttp()

    natija = await yozuvchi(http).rasm_qoy(158, RASM, "klapan.png")

    assert [s["metod"] for s in http.sorovlar] == ["POST", "POST"]
    assert http.sorovlar[0]["manzil"].endswith("/api/images/upload-image")
    assert http.sorovlar[1]["manzil"].endswith("/api/product-images/create")
    assert natija["havola"] == HAVOLA
    assert natija["mahsulot_id"] == 158


async def test_yarim_bajarilgan_yuklash_yashirilmaydi():
    """Rasm Cloudinary'da qolib, mahsulotga bog'lanmasa — ochiq aytilsin."""
    http = SoxtaHttp(biriktirish=SoxtaJavob(500, {"message": "ichki xato"}))

    with pytest.raises(YozishXatosi) as xato:
        await yozuvchi(http).rasm_qoy(158, RASM)

    assert HAVOLA in str(xato.value)
    assert "biriktirilmadi" in str(xato.value)

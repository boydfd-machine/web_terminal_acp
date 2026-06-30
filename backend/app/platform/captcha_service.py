from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from wheezy.captcha.image import background, captcha, curve, noise, offset, rotate, smooth, text, warp

from app.auth import sign_internal_message
from app.platform.security_store import get_security_store

CAPTCHA_TTL_SECONDS = 5 * 60
CAPTCHA_CODE_LENGTH = 5
CAPTCHA_WIDTH = 180
CAPTCHA_HEIGHT = 64
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass(frozen=True)
class CaptchaChallenge:
    captcha_id: str
    image_png: bytes
    ttl_seconds: int


async def create_captcha_challenge(identity: str) -> CaptchaChallenge:
    code = _random_code()
    captcha_id = secrets.token_urlsafe(24)
    await get_security_store().set_captcha(
        captcha_id,
        {
            "answer_hash": _answer_hash(captcha_id, identity, code),
            "identity": identity,
        },
        CAPTCHA_TTL_SECONDS,
    )
    await get_security_store().record_event(
        {
            "type": "captcha_created",
            "scope": "auth-login-captcha",
            "identity": identity,
            "captcha_id": captcha_id,
        }
    )
    return CaptchaChallenge(
        captcha_id=captcha_id,
        image_png=_render_png(code),
        ttl_seconds=CAPTCHA_TTL_SECONDS,
    )


async def verify_captcha(captcha_id: str | None, answer: str | None, identity: str) -> bool:
    if not captcha_id or not answer:
        return False
    value = await get_security_store().pop_captcha(captcha_id)
    if value is None or value.get("identity") != identity:
        return False
    expected = value.get("answer_hash")
    if not isinstance(expected, str):
        return False
    provided = _answer_hash(captcha_id, identity, answer)
    return hmac.compare_digest(expected, provided)


def _random_code() -> str:
    return "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_CODE_LENGTH))


def _answer_hash(captcha_id: str, identity: str, answer: str) -> str:
    normalized = answer.strip().upper()
    body = f"captcha.{captcha_id}.{identity}.{normalized}"
    return hashlib.sha256(sign_internal_message(body).encode("utf-8")).hexdigest()


def _render_png(code: str) -> bytes:
    font_paths = _captcha_font_paths()
    if font_paths:
        renderer = captcha(
            drawings=[
                background("#EEF2F7"),
                text(
                    fonts=font_paths,
                    font_sizes=(38, 42, 46),
                    drawings=[warp(), rotate(), offset()],
                    color="#1D4ED8",
                    squeeze_factor=0.82,
                ),
                curve(color="#0F766E", width=3, number=5),
                noise(number=42, color="#475569", level=2),
                smooth(),
            ],
            width=CAPTCHA_WIDTH,
            height=CAPTCHA_HEIGHT,
        )
        image = renderer(code)
    else:
        image = _fallback_image(code)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _captcha_font_paths() -> list[str]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
    ]
    return [path for path in candidates if Path(path).exists()]


def _fallback_image(code: str) -> Image.Image:
    image = Image.new("RGB", (CAPTCHA_WIDTH, CAPTCHA_HEIGHT), "#EEF2F7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    text_bbox = draw.textbbox((0, 0), code, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(
        ((CAPTCHA_WIDTH - text_width) // 2, (CAPTCHA_HEIGHT - text_height) // 2),
        code,
        fill="#1D4ED8",
        font=font,
    )
    for index in range(0, CAPTCHA_WIDTH, 18):
        draw.line((index, 0, CAPTCHA_WIDTH - index // 2, CAPTCHA_HEIGHT), fill="#94A3B8")
    return image

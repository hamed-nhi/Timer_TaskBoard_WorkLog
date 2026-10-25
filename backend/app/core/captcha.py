"""ARCaptcha verification: fixed HTTPS endpoint, bounded I/O, fail closed."""
import json

import httpx

from .config import settings
from .errors import ApiError

VERIFY_URL = "https://api.arcaptcha.co/arcaptcha/api/verify"


def verify_captcha(token: str):
    if settings.captcha_provider == "none":
        return
    if not settings.arcaptcha_site_key or not settings.arcaptcha_secret_key:
        raise ApiError("تنظیمات سرویس کپچا کامل نیست", 503)
    try:
        with httpx.Client(timeout=httpx.Timeout(5, connect=3), follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", VERIFY_URL, json={"challenge_id": token,
                    "site_key": settings.arcaptcha_site_key, "secret_key": settings.arcaptcha_secret_key}) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 16384:
                        raise ValueError("Oversized verification response")
        result = json.loads(body)
        if not isinstance(result, dict) or type(result.get("success")) is not bool:
            raise ValueError("Invalid verification response")
    except (httpx.HTTPError, ValueError, UnicodeError):
        raise ApiError("سرویس کپچا در دسترس نیست؛ دوباره تلاش کنید", 503) from None
    if result["success"] is not True:
        raise ApiError("کپچا معتبر نیست یا منقضی شده؛ دوباره حل کنید", 400)

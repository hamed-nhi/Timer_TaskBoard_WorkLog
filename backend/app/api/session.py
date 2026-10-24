"""Cookie serialization belongs to the HTTP boundary, not session business rules."""
from fastapi import Request, Response

from ..core.config import settings
from ..core.security import COOKIE_NAME


def set_session_cookie(response: Response, request: Request, token: str):
    lifetime = settings.session_days * 86400
    secure = settings.cookie_secure if settings.cookie_secure is not None else request.url.scheme == "https"
    response.set_cookie(COOKIE_NAME, token, max_age=lifetime, expires=lifetime, httponly=True,
                        secure=secure, samesite="lax", path="/")

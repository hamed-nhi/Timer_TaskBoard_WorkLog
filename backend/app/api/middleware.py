"""HTTP request protection and persistent-session response handling."""
from fastapi import Request
from fastapi.responses import JSONResponse

from ..core.constants import CSRF_HEADER, CSRF_VALUE
from .session import set_session_cookie


async def csrf_guard(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    response = await call_next(request)
    token = getattr(request.state, "renew_session_token", None)
    if token and response.status_code < 400:
        set_session_cookie(response, request, token)
    return response

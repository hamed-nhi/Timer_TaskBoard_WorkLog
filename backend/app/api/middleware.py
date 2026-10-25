"""HTTP request protection and persistent-session response handling."""
from fastapi import Request
from fastapi.responses import JSONResponse

from ..core.request_gate import request_gate
from ..core.constants import CSRF_HEADER, CSRF_VALUE
from .session import set_session_cookie


async def csrf_guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and not request_gate.admit(
            request.client.host if request.client else "unknown", request.url.path == "/api/auth/login"):
        return JSONResponse({"error": "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید"}, status_code=429,
                            headers={"Cache-Control": "no-store", "Retry-After": "1"})
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    token = getattr(request.state, "renew_session_token", None)
    if token and response.status_code < 400:
        set_session_cookie(response, request, token)
    return response

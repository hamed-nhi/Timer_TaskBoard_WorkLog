from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import set_session_cookie
from .common import CSRF_HEADER, CSRF_VALUE, ApiError
from .routers import admin, auth, catalog, fill, planned, presence, reports, settings_me, tags, tasks

app = FastAPI(title="TimeLog", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(ApiError)
async def api_error(_: Request, e: ApiError):
    return JSONResponse({"error": e.message}, status_code=e.status, headers=e.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, e: RequestValidationError):
    return JSONResponse({"error": "درخواست نامعتبر است"}, status_code=400)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, e: StarletteHTTPException):
    return JSONResponse({"error": "not found" if e.status_code == 404 else str(e.detail)}, status_code=e.status_code)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    """A page on another site cannot set this header on a cross-site request, so every
    state-changing call must carry it (together with SameSite=Lax cookies this stops CSRF)."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    response = await call_next(request)
    token = getattr(request.state, "renew_session_token", None)
    if token and response.status_code < 400:
        set_session_cookie(response, request, token)
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


for module in (auth, admin, catalog, tags, tasks, planned, presence, fill, reports, settings_me):
    app.include_router(module.router)

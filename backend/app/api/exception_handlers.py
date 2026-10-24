"""Central mapping from application errors to the existing JSON API contract."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.errors import ApiError


async def api_error(_: Request, error: ApiError):
    return JSONResponse({"error": error.message}, status_code=error.status, headers=error.headers)


async def validation_error(_: Request, error: RequestValidationError):
    return JSONResponse({"error": "درخواست نامعتبر است"}, status_code=400)


async def http_error(_: Request, error: StarletteHTTPException):
    return JSONResponse({"error": "not found" if error.status_code == 404 else str(error.detail)},
                        status_code=error.status_code)

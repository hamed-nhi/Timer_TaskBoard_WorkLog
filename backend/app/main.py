"""Application composition only. Run with uvicorn app.main:app."""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.exception_handlers import api_error, http_error, validation_error
from .api.middleware import csrf_guard
from .api.router import router
from .core.errors import ApiError


def create_app() -> FastAPI:
    application = FastAPI(title="TimeLog", docs_url=None, redoc_url=None, openapi_url=None)
    application.add_exception_handler(ApiError, api_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(StarletteHTTPException, http_error)
    application.middleware("http")(csrf_guard)
    application.include_router(router)
    return application


app = create_app()

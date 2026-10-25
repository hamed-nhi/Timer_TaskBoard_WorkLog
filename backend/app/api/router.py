"""The single API composition point; all public paths remain unchanged."""
from fastapi import APIRouter

from .routes import admin, auth, catalog, fill, imports, planned, presence, reports, settings, tags, tasks

router = APIRouter()


@router.get("/api/health")
def health():
    return {"ok": True}


for module in (auth, admin, catalog, imports, tags, tasks, planned, presence, fill, reports, settings):
    router.include_router(module.router)

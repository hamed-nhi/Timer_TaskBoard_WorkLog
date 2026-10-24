"""HTTP endpoints for fill; business rules live in services."""
from fastapi import APIRouter, Body, Query

from ..dependencies import DbDep, UserDep
from ...services import fill as service

router = APIRouter(prefix="/api")


@router.get("/fill-suggestion")
def fill_suggestion(db: DbDep, user: UserDep, date_: str | None = Query(None, alias='date'), percent: str | None = Query(None)):
    return service.fill_suggestion(db=db, user=user, date_=date_, percent=percent)


@router.post("/fill")
def apply_fill(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.apply_fill(db=db, user=user, data=data)


@router.post("/fill/rollback")
def rollback_fill(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.rollback_fill(db=db, user=user, data=data)

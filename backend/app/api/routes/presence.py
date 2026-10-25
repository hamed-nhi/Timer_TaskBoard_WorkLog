"""HTTP endpoints for presence; business rules live in services."""
from fastapi import APIRouter, Body, Query

from ..dependencies import DbDep, UserDep
from ...services import presence as service

router = APIRouter(prefix="/api")


@router.get("/presence")
def presence_get(db: DbDep, user: UserDep):
    return service.presence_get(db=db, user=user)


@router.get("/presence/history")
def presence_history(db: DbDep, user: UserDep, days: int = Query(31)):
    return service.presence_history(db=db, user=user, days=days)


@router.get("/presence/alerts")
def presence_alerts(db: DbDep, user: UserDep, date_: str | None = Query(None, alias="date")):
    return service.presence_alerts(db=db, user=user, date_=date_)


@router.post("/presence/start")
def presence_start(db: DbDep, user: UserDep):
    return service.presence_start(db=db, user=user)


@router.post("/presence/pause")
def presence_pause(db: DbDep, user: UserDep, data: dict | None = Body(None)):
    return service.presence_pause(db=db, user=user, data=data)


@router.post("/presence/finish")
def presence_finish(db: DbDep, user: UserDep):
    return service.presence_finish(db=db, user=user)


@router.post("/presence", status_code=201)
def presence_add(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.presence_add(db=db, user=user, data=data)


@router.put("/presence/{seg_id}")
def presence_update(seg_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.presence_update(seg_id=seg_id, db=db, user=user, data=data)


@router.delete("/presence/{seg_id}")
def presence_delete(seg_id: int, db: DbDep, user: UserDep):
    return service.presence_delete(seg_id=seg_id, db=db, user=user)

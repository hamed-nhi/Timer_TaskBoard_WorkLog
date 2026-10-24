"""HTTP endpoints for planned; business rules live in services."""
from fastapi import APIRouter, Body

from ..dependencies import DbDep, UserDep
from ...services import planned as service

router = APIRouter(prefix="/api")


@router.get("/planned")
def list_planned(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None, day: int | None = None):
    return service.list_planned(db=db, user=user, year=year, month=month, day=day)


@router.post("/planned", status_code=201)
def create_planned(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.create_planned(db=db, user=user, data=data)


@router.put("/planned/{planned_id}")
def update_planned(planned_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.update_planned(planned_id=planned_id, db=db, user=user, data=data)


@router.delete("/planned/{planned_id}")
def delete_planned(planned_id: int, db: DbDep, user: UserDep):
    return service.delete_planned(planned_id=planned_id, db=db, user=user)


@router.post("/planned/{planned_id}/start", status_code=201)
def start_planned(planned_id: int, db: DbDep, user: UserDep):
    return service.start_planned(planned_id=planned_id, db=db, user=user)

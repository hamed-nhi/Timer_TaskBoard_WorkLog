"""HTTP endpoints for tasks; business rules live in services."""
from fastapi import APIRouter, Body

from ..dependencies import DbDep, UserDep
from ...services import tasks as service

router = APIRouter(prefix="/api")


@router.get("/today")
def api_today(user: UserDep):
    return service.today_info(user=user)


@router.get("/month-days")
def api_month_days(user: UserDep, year: int | None = None, month: int | None = None):
    return service.month_days(user=user, year=year, month=month)


@router.get("/shift-date")
def api_shift_date(user: UserDep, year: int | None = None, month: int | None = None, day: int | None = None, delta: int = 0):
    return service.shift_date(user=user, year=year, month=month, day=day, delta=delta)


@router.get("/yesterday-titles")
def yesterday_titles(db: DbDep, user: UserDep):
    return service.yesterday_titles(db=db, user=user)


@router.get("/tasks")
def list_tasks(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None, day: int | None = None):
    return service.list_tasks(db=db, user=user, year=year, month=month, day=day)


@router.get("/tasks/paused")
def list_paused_tasks(db: DbDep, user: UserDep):
    return service.list_paused_tasks(db=db, user=user)


@router.post("/tasks", status_code=201)
def create_task(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.create_task(db=db, user=user, data=data)


@router.post("/tasks/{task_id}/pause")
def pause_task(task_id: int, db: DbDep, user: UserDep):
    return service.pause_task(task_id=task_id, db=db, user=user)


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: DbDep, user: UserDep):
    return service.resume_task(task_id=task_id, db=db, user=user)


@router.post("/tasks/{task_id}/stop")
def stop_task(task_id: int, db: DbDep, user: UserDep):
    return service.stop_task(task_id=task_id, db=db, user=user)


@router.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: int, db: DbDep, user: UserDep):
    return service.reopen_task(task_id=task_id, db=db, user=user)


@router.get("/tasks/{task_id}/segments")
def task_segments(task_id: int, db: DbDep, user: UserDep):
    return service.task_segments(task_id=task_id, db=db, user=user)


@router.post("/tasks/{task_id}/entered")
def set_entered(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.set_entered(task_id=task_id, db=db, user=user, data=data)


@router.post("/tasks/{task_id}/company")
def set_task_company(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.set_task_company(task_id=task_id, db=db, user=user, data=data)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.update_task(task_id=task_id, db=db, user=user, data=data)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: DbDep, user: UserDep):
    return service.delete_task(task_id=task_id, db=db, user=user)

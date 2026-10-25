"""HTTP endpoints for settings_me; business rules live in services."""
from fastapi import APIRouter, Body
from fastapi.responses import Response
import json

from ..dependencies import DbDep, UserDep
from ...services import settings as service
from ...core.backup import backup_revision

router = APIRouter(prefix="/api")


@router.get("/settings")
def api_get_settings(db: DbDep, user: UserDep):
    return service.get_settings(db=db, user=user)


@router.post("/settings")
def api_update_settings(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.update_settings(db=db, user=user, data=data)


@router.get("/goal-progress")
def goal_progress(db: DbDep, user: UserDep):
    return service.goal_progress(db=db, user=user)


@router.get("/me/backup")
def my_backup(db: DbDep, user: UserDep):
    data = service.my_backup(db=db, user=user)
    return Response(json.dumps(data, ensure_ascii=False, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="timelog_u{user["id"]}_{backup_revision(data)}.json"'})

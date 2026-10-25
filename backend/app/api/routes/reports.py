"""HTTP endpoints for reports; business rules live in services."""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..dependencies import DbDep, UserDep
from ...services import reports as service

router = APIRouter(prefix="/api")


@router.get("/timesheet")
def timesheet(db: DbDep, user: UserDep, date_: str | None = Query(None, alias='date')):
    return service.timesheet(db=db, user=user, date_=date_)


@router.get("/dashboard")
def dashboard(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None):
    return service.dashboard(db=db, user=user, year=year, month=month)


@router.get("/tag-summary")
def tag_summary(db: DbDep, user: UserDep, tag: str = '', year: int | None = None, month: int | None = None):
    return service.tag_summary(db=db, user=user, tag=tag, year=year, month=month)


@router.get("/calendar")
def api_calendar(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None):
    return service.calendar_month(db=db, user=user, year=year, month=month)


@router.get("/entry-report")
def entry_report(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None):
    return service.entry_report(db=db, user=user, year=year, month=month)


@router.get("/export")
def export_excel(db: DbDep, user: UserDep, year: int | None = None):
    content, filename = service.export_excel(db=db, user=user, year=year)
    return StreamingResponse(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})

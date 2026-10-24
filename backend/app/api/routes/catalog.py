"""HTTP endpoints for catalog; business rules live in services."""
from fastapi import APIRouter, Body

from ..dependencies import DbDep, UserDep
from ...services import catalog as service

router = APIRouter(prefix="/api/catalog")


@router.get("")
def full_catalog(db: DbDep, user: UserDep):
    return service.full_catalog(db=db, user=user)


@router.post("/import")
def catalog_import(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.catalog_import(db=db, user=user, data=data)


@router.post("/report-types", status_code=201)
def add_type(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.add_type(db=db, user=user, data=data)


@router.put("/report-types/{row_id}")
def rename_type(row_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.rename_type(row_id=row_id, db=db, user=user, data=data)


@router.delete("/report-types/{row_id}")
def delete_type(row_id: int, db: DbDep, user: UserDep):
    return service.delete_type(row_id=row_id, db=db, user=user)


@router.post("/projects", status_code=201)
def add_project(db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.add_project(db=db, user=user, data=data)


@router.put("/projects/{row_id}")
def rename_project(row_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.rename_project(row_id=row_id, db=db, user=user, data=data)


@router.delete("/projects/{row_id}")
def delete_project(row_id: int, db: DbDep, user: UserDep):
    return service.delete_project(row_id=row_id, db=db, user=user)


@router.post("/projects/{project_id}/stories", status_code=201)
def add_story(project_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.add_story(project_id=project_id, db=db, user=user, data=data)


@router.put("/stories/{row_id}")
def rename_story(row_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.rename_story(row_id=row_id, db=db, user=user, data=data)


@router.delete("/stories/{row_id}")
def delete_story(row_id: int, db: DbDep, user: UserDep):
    return service.delete_story(row_id=row_id, db=db, user=user)

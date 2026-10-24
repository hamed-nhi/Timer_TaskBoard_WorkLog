"""HTTP endpoints for tags; business rules live in services."""
from fastapi import APIRouter, Body, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..dependencies import DbDep, UserDep
from ...services import tags as service

router = APIRouter(prefix="/api")


@router.get("/tags")
def list_tags(db: DbDep, user: UserDep, usage: str | None = Query(None)):
    return service.list_tags(db=db, user=user, usage=usage)


@router.put("/tags/{tag_id}/budget")
def set_tag_budget(tag_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.set_tag_budget(tag_id=tag_id, db=db, user=user, data=data)


@router.put("/tags/{tag_id}")
def rename_tag(tag_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.rename_tag(tag_id=tag_id, db=db, user=user, data=data)


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: DbDep, user: UserDep):
    return service.delete_tag(tag_id=tag_id, db=db, user=user)


@router.post("/tags/{tag_id}/merge")
def merge_tag(tag_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.merge_tag(tag_id=tag_id, db=db, user=user, data=data)


@router.put("/tags/{tag_id}/company")
def set_tag_company(tag_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    return service.set_tag_company(tag_id=tag_id, db=db, user=user, data=data)


@router.get("/company-catalog")
def company_catalog(db: DbDep, user: UserDep):
    return service.company_catalog(db=db, user=user)


@router.post("/tags")
def create_tag(db: DbDep, user: UserDep, data: dict = Body(...)):
    payload, created = service.create_tag(db=db, user=user, data=data)
    return JSONResponse(jsonable_encoder(payload), status_code=201 if created else 200)

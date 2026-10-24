"""HTTP endpoints for admin; business rules live in services."""
from fastapi import APIRouter, Body

from ..dependencies import DbDep, AdminDep
from ...services import admin as service

router = APIRouter(prefix="/api/admin")


@router.get("/users")
def list_users(db: DbDep, admin: AdminDep):
    return service.list_users(db=db, admin=admin)


@router.post("/users", status_code=201)
def create_user(db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return service.create_user(db=db, admin=admin, data=data)


@router.put("/users/{user_id}")
def update_user(user_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return service.update_user(user_id=user_id, db=db, admin=admin, data=data)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: DbDep, admin: AdminDep):
    return service.reset_password(user_id=user_id, db=db, admin=admin)

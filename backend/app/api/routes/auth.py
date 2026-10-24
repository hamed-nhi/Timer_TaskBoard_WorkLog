"""Authentication HTTP adapter: inputs, cookies and application services."""
import ipaddress

from fastapi import APIRouter, Body, Depends, Request, Response

from ...core.security import COOKIE_NAME
from ...db.session import Db, get_db
from ...services import auth as service
from ..dependencies import current_user
from ..session import set_session_cookie

router = APIRouter(prefix="/api")


def client_ip(request: Request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


@router.post("/auth/login")
def login(request: Request, response: Response, data: dict = Body(...), db: Db = Depends(get_db)):
    user, token = service.login(db, str(data.get("username") or ""), str(data.get("password") or ""),
                                client_ip(request), request.headers.get("user-agent"))
    set_session_cookie(response, request, token)
    return user


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Db = Depends(get_db)):
    service.logout(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/me/password")
def change_password(request: Request, data: dict = Body(...), user: dict = Depends(current_user),
                    db: Db = Depends(get_db)):
    return service.change_password(db, user["id"], str(data.get("old") or ""), str(data.get("new") or ""),
                                   request.cookies.get(COOKIE_NAME))

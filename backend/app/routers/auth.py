import ipaddress

from fastapi import APIRouter, Body, Depends, Request, Response

from ..auth import (COOKIE_NAME, check_login_allowed, create_session, current_user, drop_sessions, hash_password,
                    record_login, token_digest, verify_password)
from ..common import ApiError
from ..config import settings
from ..db import Db, get_db

router = APIRouter(prefix="/api")


def client_ip(request: Request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


@router.post("/auth/login")
def login(request: Request, response: Response, data: dict = Body(...), db: Db = Depends(get_db)):
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")
    ip = client_ip(request)
    if not username or not password:
        raise ApiError("نام کاربری و رمز را وارد کنید")
    check_login_allowed(db, username, ip)
    user = db.execute("SELECT id, password_hash, is_active FROM users WHERE username = ?", (username,)).fetchone()
    ok = verify_password(user["password_hash"] if user else None, password)
    if not (ok and user["is_active"]):
        record_login(db, username, ip, False)
        raise ApiError("نام کاربری یا رمز اشتباه است", 401)
    record_login(db, username, ip, True)
    token = create_session(db, user["id"], request.headers.get("user-agent"))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=settings.session_days * 86400, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    return me_payload(db, user["id"])


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Db = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


def me_payload(db: Db, user_id: int):
    u = db.execute("SELECT id, username, display_name, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    return u


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/me/password")
def change_password(request: Request, data: dict = Body(...), user: dict = Depends(current_user),
                    db: Db = Depends(get_db)):
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not verify_password(row["password_hash"], str(data.get("old") or "")):
        raise ApiError("رمز فعلی اشتباه است", 400)
    new = str(data.get("new") or "")
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user["id"]))
    drop_sessions(db, user["id"], except_token=request.cookies.get(COOKIE_NAME))
    db.commit()
    return {"ok": True}

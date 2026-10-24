"""Passwords, sessions and the login rate limit."""
import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request

from .common import ApiError
from .config import settings
from .db import Db, get_db
from .timeutil import now_local

COOKIE_NAME = "tl_session"
MIN_PASSWORD_LEN = 8
_hasher = PasswordHasher()
# verifying against this keeps the response time of "no such user" equal to "wrong password"
_DUMMY_HASH = _hasher.hash("timelog-dummy-password")


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LEN:
        raise ApiError(f"رمز باید حداقل {MIN_PASSWORD_LEN} کاراکتر باشد")
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Db, user_id: int, user_agent: str | None) -> str:
    token = secrets.token_urlsafe(32)
    now = now_local()
    db.execute(
        "INSERT INTO sessions (user_id, token_hash, created_at, expires_at, last_seen_at, user_agent) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, token_digest(token), now, now + timedelta(days=settings.session_days), now,
         (user_agent or "")[:300]))
    return token


def drop_sessions(db: Db, user_id: int, except_token: str | None = None):
    if except_token:
        db.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?", (user_id, token_digest(except_token)))
    else:
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def current_user(request: Request, db: Db = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise ApiError("ابتدا وارد شوید", 401)
    now = now_local()
    row = db.execute(
        "SELECT s.id sid, s.last_seen_at, u.id, u.username, u.display_name, u.is_admin "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active", (token_digest(token), now)).fetchone()
    if not row:
        raise ApiError("ابتدا وارد شوید", 401)
    if now - row["last_seen_at"] > timedelta(hours=1):
        db.execute("UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now, row["sid"]))
        db.commit()
    return {k: row[k] for k in ("id", "username", "display_name", "is_admin")}


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise ApiError("دسترسی ندارید", 403)
    return user


# ---- login rate limit: 3 wrong passwords per username in 20 minutes, 10 per IP ----

def _locked_minutes(db: Db, where: str, value, limit: int) -> int:
    """Minutes left of the lock (0 = not locked). Only failures after the last success count."""
    now = now_local()
    since = now - timedelta(minutes=settings.login_window_minutes)
    rows = db.execute(
        f"SELECT at FROM login_attempts WHERE {where} = ? AND NOT success AND at > ? "
        f"AND at > COALESCE((SELECT MAX(at) FROM login_attempts WHERE {where} = ? AND success), ?) ORDER BY at",
        (value, since, value, since)).fetchall()
    if len(rows) < limit:
        return 0
    # the lock ends when enough old failures have left the window
    unlock_at = rows[len(rows) - limit]["at"] + timedelta(minutes=settings.login_window_minutes)
    return max(1, int((unlock_at - now).total_seconds() // 60) + 1)


def check_login_allowed(db: Db, username: str, ip: str | None):
    minutes = _locked_minutes(db, "username", username, settings.login_max_failures)
    if ip:
        minutes = max(minutes, _locked_minutes(db, "host(ip)", ip, settings.login_ip_max_failures))
    if minutes:
        raise ApiError(f"{settings.login_max_failures} بار رمز اشتباه وارد شد. {minutes} دقیقه‌ی دیگر دوباره امتحان کنید.",
                       429, headers={"Retry-After": str(minutes * 60)})


def record_login(db: Db, username: str, ip: str | None, success: bool):
    db.execute("INSERT INTO login_attempts (username, ip, success, at) VALUES (?, ?, ?, ?)",
               (username[:64], ip, success, now_local()))
    db.commit()

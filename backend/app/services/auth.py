"""Database sessions and login rate limiting; no HTTP dependencies."""
from datetime import timedelta
import secrets

from ..core.config import settings
from ..core.errors import ApiError
from ..core.security import hash_password, token_digest, verify_password
from ..core.time import now_local
from ..db.session import Db

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


def resolve_session(db: Db, token: str | None):
    if not token:
        raise ApiError("ابتدا وارد شوید", 401)
    now = now_local()
    row = db.execute(
        "SELECT s.id sid, s.last_seen_at, u.id, u.username, u.display_name, u.is_admin "
        "FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active", (token_digest(token), now)).fetchone()
    if not row:
        raise ApiError("ابتدا وارد شوید", 401)
    renewed = now - row["last_seen_at"] > timedelta(hours=1)
    if renewed:
        updated = db.execute("UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE id = ? AND expires_at > ?",
                             (now, now + timedelta(days=settings.session_days), row["sid"], now))
        if not updated.rowcount:
            raise ApiError("ابتدا وارد شوید", 401)
        db.commit()
    return {k: row[k] for k in ("id", "username", "display_name", "is_admin")}, renewed


def login(db: Db, username: str, password: str, ip: str | None, user_agent: str | None):
    username = username.strip().lower()
    if not username or not password:
        raise ApiError("نام کاربری و رمز را وارد کنید")
    check_login_allowed(db, username, ip)
    user = db.execute("SELECT id, password_hash, is_active FROM users WHERE username = ?", (username,)).fetchone()
    ok = verify_password(user["password_hash"] if user else None, password)
    if not (ok and user["is_active"]):
        record_login(db, username, ip, False)
        raise ApiError("نام کاربری یا رمز اشتباه است", 401)
    record_login(db, username, ip, True)
    token = create_session(db, user["id"], user_agent)
    db.commit()
    return db.execute("SELECT id, username, display_name, is_admin FROM users WHERE id = ?",
                      (user["id"],)).fetchone(), token


def logout(db: Db, token: str | None):
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))
        db.commit()


def change_password(db: Db, user_id: int, old: str, new: str, token: str | None):
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not verify_password(row["password_hash"], old):
        raise ApiError("رمز فعلی اشتباه است", 400)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))
    drop_sessions(db, user_id, except_token=token)
    db.commit()
    return {"ok": True}


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

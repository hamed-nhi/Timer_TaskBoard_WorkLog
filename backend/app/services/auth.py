"""Database sessions and login rate limiting; no HTTP dependencies."""
from datetime import timedelta
import secrets

from ..core.config import settings
from ..core.captcha import verify_captcha
from ..core.errors import ApiError
from ..core.security import hash_password, token_digest, verify_password, validate_password
from ..core.time import now_local
from ..db.session import Db
from . import login_protection as protection

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


def public_login_config():
    return {"captcha_provider": settings.captcha_provider,
            "site_key": settings.arcaptcha_site_key if settings.captcha_provider == "arcaptcha" else ""}


def login(db: Db, username: str, password: str, ip: str | None, user_agent: str | None,
          captcha_token=None):
    username = username.strip().lower()
    # Reserve an attempt BEFORE expensive hashing/network calls. This short PostgreSQL lock
    # serializes admission across processes; it never spans a password hash or provider I/O.
    db.execute("SELECT pg_advisory_xact_lock(731906, 1)")
    protection.check_bans(db, ip, username[:64])
    check_login_allowed(db, username[:64], ip)
    recent = db.execute("SELECT COUNT(*) n FROM login_attempts WHERE username = ? AND host(ip) IS NOT DISTINCT FROM ? "
                        "AND NOT success AND at > ? AND at > COALESCE((SELECT MAX(at) FROM login_attempts "
                        "WHERE username = ? AND host(ip) IS NOT DISTINCT FROM ? AND success), ?)",
                        (username[:64], ip, now_local() - timedelta(seconds=10), username[:64], ip,
                         now_local() - timedelta(seconds=10))).fetchone()
    if recent["n"] >= protection.policy(db)["attempts"]:
        raise ApiError("تلاش‌های هم‌زمان ورود بیش از حد مجاز است", 429, headers={"Retry-After": "10"})
    attempt = db.insert("INSERT INTO login_attempts (username, ip, success, at) VALUES (?, ?, false, ?)",
                        (username[:64], ip, now_local()))
    captcha_error = None
    if settings.captcha_provider == "arcaptcha":
        if not isinstance(captcha_token, str) or not 1 <= len(captcha_token) <= 4096:
            captcha_error = "ابتدا کپچا را حل کنید"
        else:
            reserved = db.execute("INSERT INTO captcha_redemptions (token_hash, expires_at) VALUES (?, ?) "
                                  "ON CONFLICT DO NOTHING", (token_digest(captcha_token), now_local() + timedelta(minutes=10)))
            if reserved.rowcount != 1:
                captcha_error = "کپچا قبلاً استفاده شده؛ دوباره حل کنید"
    # Keep bounded security history; no personal activity or recorded times are changed.
    db.execute("DELETE FROM login_attempts WHERE at < ?", (now_local() - timedelta(days=2),))
    db.execute("DELETE FROM captcha_redemptions WHERE expires_at < ?", (now_local(),))
    db.commit()
    if not username or not password or len(username) > 64 or len(password) > 1024:
        raise ApiError("نام کاربری یا رمز نامعتبر است", 400)
    if captcha_error:
        raise ApiError(captcha_error, 400)
    verify_captcha(captcha_token)
    user = db.execute("SELECT id, password_hash, is_active FROM users WHERE username = ?", (username,)).fetchone()
    ok = verify_password(user["password_hash"] if user else None, password)
    # Serialize completion too: admitted concurrent failures cannot race the escalation state.
    db.execute("SELECT pg_advisory_xact_lock(731906, 1)")
    config = protection.policy(db)
    if not (ok and user["is_active"]):
        protection.failed(db, ip, username, bool(user and user["is_active"]), config)
        db.commit()
        raise ApiError("نام کاربری یا رمز اشتباه است", 401)
    protection.succeeded(db, ip, username, config)
    db.execute("UPDATE login_attempts SET success = true WHERE id = ?", (attempt,))
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
    validate_password(new)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))
    drop_sessions(db, user_id, except_token=token)
    db.commit()
    return {"ok": True}


# Failed account attempts reset after its own success. IP failures never reset on success.
def _locked_minutes(db: Db, where: str, value, limit: int, reset_on_success=True, window_minutes=20) -> int:
    now = now_local()
    since = now - timedelta(minutes=window_minutes)
    reset = (f"AND at > COALESCE((SELECT MAX(at) FROM login_attempts WHERE {where} = ? AND success), ?)"
             if reset_on_success else "")
    params = (value, since, value, since) if reset_on_success else (value, since)
    rows = db.execute(f"SELECT at FROM login_attempts WHERE {where} IS NOT DISTINCT FROM ? AND NOT success "
                      f"AND at > ? {reset} ORDER BY at", params).fetchall()
    if len(rows) < limit:
        return 0
    unlock_at = rows[len(rows) - limit]["at"] + timedelta(minutes=window_minutes)
    return max(1, int((unlock_at - now).total_seconds() // 60) + 1)


def check_login_allowed(db: Db, username: str, ip: str | None):
    config = protection.policy(db)
    minutes = _locked_minutes(db, "host(ip)", ip, config["ip_max_failures"], False, config["ip_window_minutes"])
    if minutes:
        raise ApiError(f"تلاش‌های ورود بیش از حد مجاز است. {minutes} دقیقه‌ی دیگر دوباره امتحان کنید.",
                       429, headers={"Retry-After": str(minutes * 60)})
    now = now_local()
    for seconds, limit, per_ip in [(60, config["ip_burst"], True),
                                   (3600, config["ip_hourly"], True),
                                   (60, config["global_per_minute"], False)]:
        clause = "AND host(ip) IS NOT DISTINCT FROM ?" if per_ip else ""
        params = (now - timedelta(seconds=seconds), ip) if per_ip else (now - timedelta(seconds=seconds),)
        row = db.execute(f"SELECT COUNT(*) count, MIN(at) first FROM login_attempts WHERE at > ? {clause}", params).fetchone()
        if row["count"] >= limit:
            retry = max(1, int((row["first"] + timedelta(seconds=seconds) - now).total_seconds()) + 1)
            raise ApiError("تعداد درخواست‌های ورود زیاد است؛ کمی بعد دوباره تلاش کنید", 429,
                           headers={"Retry-After": str(retry)})

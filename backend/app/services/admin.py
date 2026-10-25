"""Admin-only account provisioning. Personal catalogs have their own router."""

from ..core.errors import ApiError
from ..core.security import hash_password, validate_password, generate_password
from ..db.session import Db
from .auth import drop_sessions
from . import login_protection as protection
from .validation import not_found


USERNAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def clean_username(value):
    name = str(value or "").strip().lower()
    if not 3 <= len(name) <= 64 or not set(name) <= USERNAME_CHARS:
        raise ApiError("نام کاربری باید ۳ تا ۶۴ حرف لاتین کوچک، عدد یا . _ - باشد")
    return name


def user_json(row):
    return {k: row[k] for k in ("id", "username", "display_name", "is_admin", "is_active", "created_at")}


# ---- users ----

def list_users(db: Db, admin: dict):
    return [user_json(r) for r in db.execute("SELECT * FROM users ORDER BY id").fetchall()]


def create_user(db: Db, admin: dict, data: dict):
    """Without a password a temporary one is generated and returned once."""
    username = clean_username(data.get("username"))
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise ApiError("این نام کاربری قبلاً ثبت شده", 409)
    password = str(data.get("password") or "") or generate_password()
    validate_password(password)
    uid = db.insert("INSERT INTO users (username, password_hash, display_name, is_admin) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), str(data.get("display_name") or "").strip()[:100],
                     bool(data.get("is_admin"))))
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return {**user_json(row), "temp_password": password}


def update_user(user_id: int, db: Db, admin: dict, data: dict):
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        not_found()
    if user_id == admin["id"] and ("is_active" in data and not data["is_active"] or
                                   "is_admin" in data and not data["is_admin"]):
        raise ApiError("نمی‌توانید خودتان را غیرفعال یا از ادمینی خارج کنید")
    db.execute("UPDATE users SET display_name = ?, is_active = ?, is_admin = ? WHERE id = ?",
               (str(data.get("display_name", row["display_name"]) or "").strip()[:100],
                bool(data.get("is_active", row["is_active"])), bool(data.get("is_admin", row["is_admin"])), user_id))
    if "is_active" in data and not data["is_active"]:
        drop_sessions(db, user_id)
    db.commit()
    return user_json(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def reset_password(user_id: int, db: Db, admin: dict):
    if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
        not_found()
    password = generate_password()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    drop_sessions(db, user_id)
    db.commit()
    return {"temp_password": password}


# These controls manage access only; they never expose another user's personal catalog/tasks.

def login_protection_overview(db: Db):
    return protection.overview(db)


def update_login_policy(db: Db, admin: dict, data: dict):
    return protection.update_policy(db, admin, data)


def unblock_login(db: Db, admin: dict, ban_id: int, data: dict):
    return protection.unblock(db, admin, ban_id, data.get("reset", False))


def update_credentials(db: Db, admin: dict, user_id: int, data: dict):
    import json
    from sqlalchemy.exc import IntegrityError
    if not data or set(data) - {"username", "password", "display_name", "is_admin"}:
        raise ApiError("نام کاربری یا رمز جدید را وارد کنید")
    db.lock_user(user_id)
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        not_found()
    username = clean_username(data["username"]) if "username" in data else row["username"]
    password = data.get("password")
    if "password" in data and (not isinstance(password, str) or not 8 <= len(password) <= 1024):
        raise ApiError("رمز باید ۸ تا ۱۰۲۴ کاراکتر باشد")
    if "is_admin" in data and type(data["is_admin"]) is not bool:
        raise ApiError("نقش نامعتبر است")
    if user_id == admin["id"] and data.get("is_admin") is False:
        raise ApiError("نمی‌توانید خودتان را از ادمینی خارج کنید")
    if "password" in data:
        validate_password(password)
    hashed = hash_password(password) if "password" in data else row["password_hash"]
    try:
        db.execute("UPDATE users SET username = ?, password_hash = ?, display_name = ?, is_admin = ? WHERE id = ?",
                   (username, hashed, str(data.get("display_name", row["display_name"]) or "").strip()[:100], data.get("is_admin", row["is_admin"]), user_id))
        if username != row["username"] or "password" in data or data.get("is_admin", row["is_admin"]) != row["is_admin"]:
            drop_sessions(db, user_id)
        db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'user_credentials_changed', ?::jsonb)",
                   (admin["id"], json.dumps({"user_id": user_id, "fields": sorted(data)})))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("این نام کاربری قبلاً ثبت شده", 409) from None
    return user_json(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

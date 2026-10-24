"""Admin-only account provisioning. Personal catalogs have their own router."""
import secrets

from ..core.errors import ApiError
from ..core.security import hash_password
from ..db.session import Db
from .auth import drop_sessions
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
    password = str(data.get("password") or "") or secrets.token_urlsafe(9)
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
    password = secrets.token_urlsafe(9)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    drop_sessions(db, user_id)
    db.commit()
    return {"temp_password": password}

"""Admin only: users and the shared company catalog."""
import secrets

from fastapi import APIRouter, Body
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..auth import drop_sessions, hash_password
from ..catalog import import_catalog
from ..common import ApiError, not_found
from ..deps import AdminDep, DbDep

router = APIRouter(prefix="/api/admin")

USERNAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def clean_username(value):
    name = str(value or "").strip().lower()
    if not 3 <= len(name) <= 64 or not set(name) <= USERNAME_CHARS:
        raise ApiError("نام کاربری باید ۳ تا ۶۴ حرف لاتین کوچک، عدد یا . _ - باشد")
    return name


def user_json(row):
    return {k: row[k] for k in ("id", "username", "display_name", "is_admin", "is_active", "created_at")}


# ---- users ----

@router.get("/users")
def list_users(db: DbDep, admin: AdminDep):
    return [user_json(r) for r in db.execute("SELECT * FROM users ORDER BY id").fetchall()]


@router.post("/users")
def create_user(db: DbDep, admin: AdminDep, data: dict = Body(...)):
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
    return JSONResponse(jsonable_encoder({**user_json(row), "temp_password": password}), status_code=201)


@router.put("/users/{user_id}")
def update_user(user_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
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


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: DbDep, admin: AdminDep):
    if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
        not_found()
    password = secrets.token_urlsafe(9)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    drop_sessions(db, user_id)
    db.commit()
    return {"temp_password": password}


# ---- catalog ----

def clean_name(value, label):
    name = str(value or "").strip()
    if not name or len(name) > 150:
        raise ApiError(f"{label} الزامی است و حداکثر ۱۵۰ کاراکتر")
    return name


def dup(e):
    raise ApiError("این مورد قبلاً ثبت شده", 409)


def add_named(db, table, name, extra_cols="", extra_vals=()):
    try:
        new_id = db.insert(f"INSERT INTO {table} (name, sort{extra_cols}) VALUES (?, "
                           f"(SELECT COALESCE(MAX(sort), 0) + 1 FROM {table}){', ?' * len(extra_vals)})",
                           (name, *extra_vals))
    except Exception as e:      # unique violation
        db.rollback()
        if "unique" in str(e).lower():
            dup(e)
        raise
    db.commit()
    return new_id


def rename(db, table, row_id, name):
    if not db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)).fetchone():
        not_found()
    try:
        db.execute(f"UPDATE {table} SET name = ? WHERE id = ?", (name, row_id))
    except Exception as e:
        db.rollback()
        if "unique" in str(e).lower():
            dup(e)
        raise
    db.commit()
    return {"ok": True}


@router.get("/catalog")
def full_catalog(db: DbDep, admin: AdminDep):
    types = db.execute("SELECT id, name FROM report_types ORDER BY sort, id").fetchall()
    projects = db.execute("SELECT id, name FROM projects ORDER BY sort, id").fetchall()
    stories = db.execute("SELECT id, project_id, name FROM stories ORDER BY sort, id").fetchall()
    for p in projects:
        p["stories"] = [s for s in stories if s["project_id"] == p["id"]]
    return {"types": types, "projects": projects}


@router.post("/catalog/import")
def catalog_import(db: DbDep, admin: AdminDep, data: dict = Body(...)):
    import_catalog(db, data)
    db.commit()
    return {"ok": True}


@router.post("/report-types", status_code=201)
def add_type(db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return {"id": add_named(db, "report_types", clean_name(data.get("name"), "نوع گزارش"))}


@router.put("/report-types/{row_id}")
def rename_type(row_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return rename(db, "report_types", row_id, clean_name(data.get("name"), "نوع گزارش"))


@router.delete("/report-types/{row_id}")
def delete_type(row_id: int, db: DbDep, admin: AdminDep):
    used = db.execute("SELECT (SELECT COUNT(*) FROM tags WHERE report_type_id = ?) + "
                      "(SELECT COUNT(*) FROM tasks WHERE report_type_id = ?) c", (row_id, row_id)).fetchone()["c"]
    if used:
        raise ApiError(f"این نوع گزارش روی {used} مورد استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM report_types WHERE id = ?", (row_id,))
    db.commit()
    return {"ok": True}


@router.post("/projects", status_code=201)
def add_project(db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return {"id": add_named(db, "projects", clean_name(data.get("name"), "نام پروژه"))}


@router.put("/projects/{row_id}")
def rename_project(row_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return rename(db, "projects", row_id, clean_name(data.get("name"), "نام پروژه"))


@router.delete("/projects/{row_id}")
def delete_project(row_id: int, db: DbDep, admin: AdminDep):
    used = db.execute("SELECT COUNT(*) c FROM tags WHERE story_id IN (SELECT id FROM stories WHERE project_id = ?)",
                      (row_id,)).fetchone()["c"]
    if used:
        raise ApiError(f"استوری‌های این پروژه روی {used} تگ استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM projects WHERE id = ?", (row_id,))
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/stories", status_code=201)
def add_story(project_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
    if not db.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        not_found()
    return {"id": add_named(db, "stories", clean_name(data.get("name"), "نام استوری"), ", project_id", (project_id,))}


@router.put("/stories/{row_id}")
def rename_story(row_id: int, db: DbDep, admin: AdminDep, data: dict = Body(...)):
    return rename(db, "stories", row_id, clean_name(data.get("name"), "نام استوری"))


@router.delete("/stories/{row_id}")
def delete_story(row_id: int, db: DbDep, admin: AdminDep):
    used = db.execute("SELECT COUNT(*) c FROM tags WHERE story_id = ?", (row_id,)).fetchone()["c"]
    if used:
        raise ApiError(f"این استوری روی {used} تگ استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM stories WHERE id = ?", (row_id,))
    db.commit()
    return {"ok": True}

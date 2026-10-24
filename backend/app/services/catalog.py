"""Every authenticated user manages only their own report types, projects and stories."""
from sqlalchemy.exc import IntegrityError

from ..core.errors import ApiError
from ..db.session import Db
from .catalog_helpers import catalog_payload, import_catalog
from .validation import not_found


def own(db, uid, table, row_id):
    row = db.execute(f"SELECT * FROM {table} WHERE id = ? AND user_id = ?", (row_id, uid)).fetchone()
    if not row:
        not_found()
    return row


def clean_name(value, label):
    name = value.strip() if isinstance(value, str) else ""
    if not name or len(name) > 150:
        raise ApiError(f"{label} الزامی است و حداکثر ۱۵۰ کاراکتر")
    return name


def add_named(db, uid, table, name, project_id=None):
    db.lock_user(uid)
    columns, values, params = "user_id, name", "?, ?", [uid, name]
    if project_id is not None:
        own(db, uid, "projects", project_id)
        columns += ", project_id"
        values += ", ?"
        params.append(project_id)
    try:
        new_id = db.insert(f"INSERT INTO {table} ({columns}, sort) VALUES ({values}, "
                           f"(SELECT COALESCE(MAX(sort), 0) + 1 FROM {table} WHERE user_id = ?))",
                           (*params, uid))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("این مورد قبلاً ثبت شده", 409)
    return {"id": new_id}


def rename(db, uid, table, row_id, name):
    db.lock_user(uid)
    own(db, uid, table, row_id)
    try:
        db.execute(f"UPDATE {table} SET name = ? WHERE id = ? AND user_id = ?", (name, row_id, uid))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("این مورد قبلاً ثبت شده", 409)
    return {"ok": True}


def full_catalog(db: Db, user: dict):
    return catalog_payload(db, user["id"])


def catalog_import(db: Db, user: dict, data: dict):
    types, projects = data.get("types", []), data.get("projects", {})
    if not isinstance(types, list) or not isinstance(projects, dict):
        raise ApiError("کاتالوگ نامعتبر است")
    cleaned = {"types": [clean_name(n, "نوع گزارش") for n in types], "projects": {}}
    for project, stories in projects.items():
        if not isinstance(stories, list):
            raise ApiError("فهرست استوری‌ها نامعتبر است")
        cleaned["projects"][clean_name(project, "نام پروژه")] = [clean_name(n, "نام استوری") for n in stories]
    import_catalog(db, user["id"], cleaned)
    db.commit()
    return {"ok": True}


def add_type(db: Db, user: dict, data: dict):
    return add_named(db, user["id"], "report_types", clean_name(data.get("name"), "نوع گزارش"))


def rename_type(row_id: int, db: Db, user: dict, data: dict):
    return rename(db, user["id"], "report_types", row_id, clean_name(data.get("name"), "نوع گزارش"))


def delete_type(row_id: int, db: Db, user: dict):
    uid = user["id"]
    db.lock_user(uid)
    own(db, uid, "report_types", row_id)
    used = db.execute("SELECT (SELECT COUNT(*) FROM tags WHERE report_type_id = ? AND user_id = ?) + "
                      "(SELECT COUNT(*) FROM tasks WHERE report_type_id = ? AND user_id = ?) c",
                      (row_id, uid, row_id, uid)).fetchone()["c"]
    if used:
        raise ApiError(f"این نوع گزارش روی {used} مورد استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM report_types WHERE id = ? AND user_id = ?", (row_id, uid))
    db.commit()
    return {"ok": True}


def add_project(db: Db, user: dict, data: dict):
    return add_named(db, user["id"], "projects", clean_name(data.get("name"), "نام پروژه"))


def rename_project(row_id: int, db: Db, user: dict, data: dict):
    return rename(db, user["id"], "projects", row_id, clean_name(data.get("name"), "نام پروژه"))


def delete_project(row_id: int, db: Db, user: dict):
    uid = user["id"]
    db.lock_user(uid)
    own(db, uid, "projects", row_id)
    used = db.execute("SELECT COUNT(*) c FROM tags WHERE user_id = ? AND story_id IN "
                      "(SELECT id FROM stories WHERE user_id = ? AND project_id = ?)",
                      (uid, uid, row_id)).fetchone()["c"]
    if used:
        raise ApiError(f"استوری‌های این پروژه روی {used} تگ استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (row_id, uid))
    db.commit()
    return {"ok": True}


def add_story(project_id: int, db: Db, user: dict, data: dict):
    return add_named(db, user["id"], "stories", clean_name(data.get("name"), "نام استوری"), project_id)


def rename_story(row_id: int, db: Db, user: dict, data: dict):
    return rename(db, user["id"], "stories", row_id, clean_name(data.get("name"), "نام استوری"))


def delete_story(row_id: int, db: Db, user: dict):
    uid = user["id"]
    db.lock_user(uid)
    own(db, uid, "stories", row_id)
    used = db.execute("SELECT COUNT(*) c FROM tags WHERE story_id = ? AND user_id = ?",
                      (row_id, uid)).fetchone()["c"]
    if used:
        raise ApiError(f"این استوری روی {used} تگ استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM stories WHERE id = ? AND user_id = ?", (row_id, uid))
    db.commit()
    return {"ok": True}

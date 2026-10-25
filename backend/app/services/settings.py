"""Per-user settings, goal progress and the user's own data download."""


from ..core.errors import ApiError
from ..core.config import settings as server_settings
from ..core.backup import sheet_id
from ..core.time import jalali_week_range, now_local, today_local
from ..db.session import Db
from .catalog_helpers import catalog_payload
from .timecalc import effective_minutes
from .user_settings import get_goals, get_setting, set_setting


def sheet_reserved(db, uid, sid):
    # A reservation lookup returns no other account's URL or personal data.
    return db.execute("SELECT 1 FROM user_settings WHERE key = ? AND user_id <> ? "
                      "AND split_part(split_part(split_part(value, '/', 6), ?, 1), '#', 1) = ? LIMIT 1",
                      ("google_sheet_url", uid, "?", sid)).fetchone() is not None


def settings_payload(db, uid):
    return {**get_goals(db, uid), "fill_target_percent": float(get_setting(db, uid, "fill_target_percent", 95)),
            "google_sheet_url": get_setting(db, uid, "google_sheet_url", ""),
            "backup_setup_done": get_setting(db, uid, "backup_setup_done", "0") == "1",
            "backup_service_email": server_settings.google_sheets_service_email}


def get_settings(db: Db, user: dict):
    return settings_payload(db, user["id"])


def update_settings(db: Db, user: dict, data: dict):
    uid = user["id"]
    limits = {"daily_goal_minutes": 24 * 60, "weekly_goal_minutes": 7 * 24 * 60}
    updates = {}
    for key, upper in limits.items():
        if key in data:
            try:
                value = float(data[key])
            except (TypeError, ValueError):
                raise ApiError("هدف باید یک عدد باشد")
            if not 0 < value <= upper:
                raise ApiError("هدف باید بیشتر از صفر و در حد منطقی باشد")
            updates[key] = value
    if "backup_setup_done" in data:
        if type(data["backup_setup_done"]) is not bool:
            raise ApiError("وضعیت راه‌اندازی پشتیبان نامعتبر است")
        updates["backup_setup_done"] = "1" if data["backup_setup_done"] else "0"
    if "google_sheet_url" in data:
        url = str(data["google_sheet_url"] or "").strip()
        if url:
            sid = sheet_id(url)
            # Serialize reservations across accounts, including different URL spellings.
            db.lock_user(-731905)
            if sheet_reserved(db, uid, sid):
                raise ApiError("این شیت قبلاً برای حساب دیگری ثبت شده؛ یک شیت جدا بسازید")
            url = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
        updates["google_sheet_url"] = url
    for key, value in updates.items():
        set_setting(db, uid, key, value)
    db.commit()
    return settings_payload(db, uid)


def goal_progress(db: Db, user: dict):
    uid = user["id"]
    goals = get_goals(db, uid)
    now = now_local()
    today_g = today_local()
    today_rows = db.execute("SELECT * FROM tasks WHERE user_id = ? AND gregorian_date = ?", (uid, today_g)).fetchall()
    week_start, week_end = jalali_week_range(today_g)
    week_rows = db.execute("SELECT * FROM tasks WHERE user_id = ? AND gregorian_date BETWEEN ? AND ?",
                           (uid, week_start, week_end)).fetchall()
    return {
        **goals,
        "today_minutes": round(sum(effective_minutes(r, now) for r in today_rows), 1),
        "week_minutes": round(sum(effective_minutes(r, now) for r in week_rows), 1),
    }


def my_backup(db: Db, user: dict):
    """Everything the user owns, as one JSON file."""
    uid = user["id"]
    q = lambda sql: db.execute(sql, (uid,)).fetchall()      # noqa: E731
    data = {
        "exported_at": now_local().isoformat(timespec="seconds"),
        "user": {"username": user["username"], "display_name": user["display_name"]},
        "catalog": catalog_payload(db, uid),
        "tags": q("SELECT * FROM tags WHERE user_id = ? ORDER BY id"),
        "tasks": q("SELECT * FROM tasks WHERE user_id = ? ORDER BY id"),
        "task_segments": q("SELECT s.* FROM task_segments s JOIN tasks t ON t.id = s.task_id "
                           "WHERE t.user_id = ? ORDER BY s.id"),
        "planned_tasks": q("SELECT * FROM planned_tasks WHERE user_id = ? ORDER BY id"),
        "presence_segments": q("SELECT * FROM presence_segments WHERE user_id = ? ORDER BY id"),
        "settings": q("SELECT key, value FROM user_settings WHERE user_id = ? ORDER BY key"),
        "audit_log": q("SELECT * FROM audit_log WHERE user_id = ? ORDER BY id"),
    }
    return data

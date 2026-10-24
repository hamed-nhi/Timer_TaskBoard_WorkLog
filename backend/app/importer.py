"""One-off import of a desktop TimeLog database (SQLite) into an empty user account.

Safety: the source is opened read-only and must be a COPY (a file called tasklog.db is refused),
everything goes in one transaction, and before it is committed the counts and the sums of minutes
are compared with the source - any difference rolls everything back."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .catalog import import_catalog
from .db import Db, SessionLocal


class ImportError_(Exception):
    pass


def ts(value):
    """Desktop timestamp text -> naive datetime (None stays None)."""
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace(" ", "T"))


def day(value):
    return datetime.fromisoformat(str(value)[:10]).date() if value else None


def import_desktop(db: Db, source_path, username, dry_run=False):
    path = Path(source_path)
    if path.name == "tasklog.db":
        raise ImportError_("این فایل خودِ دیتابیس اصلی است؛ اول از آن یک کپی بگیرید (مثلاً tasklog_copy.db) و آن را بدهید")
    if not path.exists():
        raise ImportError_(f"فایل پیدا نشد: {path}")
    src = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        return _import(db, src, username, dry_run)
    finally:
        src.close()


def _import(db, src, username, dry_run):
    user = db.execute("SELECT id FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if not user:
        raise ImportError_(f"کاربر «{username}» وجود ندارد؛ اول آن را بسازید (create-user)")
    uid = user["id"]
    db.lock_user(uid)
    for table in ("tasks", "tags", "planned_tasks", "presence_segments"):
        if db.execute(f"SELECT COUNT(*) c FROM {table} WHERE user_id = ?", (uid,)).fetchone()["c"]:
            raise ImportError_("حساب مقصد خالی نیست؛ انتقال فقط یک بار و روی حساب خالی انجام می‌شود")

    q = lambda sql: src.execute(sql).fetchall()      # noqa: E731
    warnings = []

    # ---- personal catalog: the saved list plus whatever the tags and tasks use ----
    settings = {r["key"]: r["value"] for r in q("SELECT key, value FROM settings")}
    try:
        saved = json.loads(settings.get("company_catalog") or "{}")
    except ValueError:
        saved = {}
    catalog = {"types": list(saved.get("types") or []),
               "projects": {p: list(s) for p, s in (saved.get("projects") or {}).items()}}
    for t in q("SELECT report_type, project, story FROM tags"):
        if t["report_type"] and t["report_type"] not in catalog["types"]:
            catalog["types"].append(t["report_type"])
        if t["project"] and t["story"]:
            stories = catalog["projects"].setdefault(t["project"], [])
            if t["story"] not in stories:
                stories.append(t["story"])
    for t in q("SELECT DISTINCT report_type FROM tasks WHERE report_type IS NOT NULL AND report_type <> ''"):
        if t["report_type"] not in catalog["types"]:
            catalog["types"].append(t["report_type"])
    import_catalog(db, uid, catalog)
    type_id = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM report_types WHERE user_id = ?", (uid,)).fetchall()}
    story_id = {(r["project"], r["name"]): r["id"] for r in db.execute(
        "SELECT s.id, s.name, p.name AS project FROM stories s JOIN projects p ON p.id = s.project_id "
        "WHERE s.user_id = ? AND p.user_id = ?", (uid, uid)).fetchall()}

    # ---- tags ----
    tag_map = {}
    for t in q("SELECT * FROM tags ORDER BY id"):
        if t["project"] and not t["story"]:
            warnings.append(f"تگ «{t['name']}» پروژه دارد ولی استوری ندارد؛ پروژه منتقل نشد")
        tag_map[t["id"]] = db.insert(
            "INSERT INTO tags (user_id, name, budget_minutes, budget_since, report_type_id, story_id, fill_weight, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, t["name"], t["budget_minutes"], day(t["budget_since"]), type_id.get(t["report_type"]),
             story_id.get((t["project"], t["story"])), t["fill_weight"], ts(t["created_at"])))

    # ---- tasks and their segments ----
    task_map = {}
    for t in q("SELECT * FROM tasks ORDER BY id"):
        task_map[t["id"]] = db.insert(
            "INSERT INTO tasks (user_id, jalali_year, jalali_month, jalali_day, gregorian_date, title, start_time, end_time, "
            "duration_minutes, status, accumulated_minutes, segment_started_at, tag_id, entered_main_system, meeting_with, "
            "meeting_minutes, adjust_minutes, report_type_id, outside_company, planned_flag, fill_minutes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, t["jalali_year"], t["jalali_month"], t["jalali_day"], day(t["gregorian_date"]), t["title"],
             t["start_time"], t["end_time"], t["duration_minutes"], t["status"], t["accumulated_minutes"],
             ts(t["segment_started_at"]), tag_map.get(t["tag_id"]), bool(t["entered_main_system"]), t["meeting_with"],
             t["meeting_minutes"], t["adjust_minutes"], type_id.get(t["report_type"]), bool(t["outside_company"]),
             bool(t["planned_flag"]), t["fill_minutes"], ts(t["created_at"])))
    for s in q("SELECT * FROM task_segments ORDER BY id"):
        db.execute("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (?, ?, ?)",
                   (task_map[s["task_id"]], ts(s["started_at"]), ts(s["ended_at"])))

    for p in q("SELECT * FROM planned_tasks ORDER BY id"):
        db.execute("INSERT INTO planned_tasks (user_id, jalali_year, jalali_month, jalali_day, title, tag_id, created_at) "
                   "VALUES (?,?,?,?,?,?,?)", (uid, p["jalali_year"], p["jalali_month"], p["jalali_day"], p["title"],
                                              tag_map.get(p["tag_id"]), ts(p["created_at"])))
    for s in q("SELECT * FROM presence_segments ORDER BY id"):
        db.execute("INSERT INTO presence_segments (user_id, started_at, ended_at, note, kind) VALUES (?,?,?,?,?)",
                   (uid, ts(s["started_at"]), ts(s["ended_at"]), s["note"], s["kind"]))

    # ---- settings and logs ----
    for key in ("daily_goal_minutes", "weekly_goal_minutes", "fill_target_percent"):
        if key in settings:
            db.execute("INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?)", (uid, key, settings[key]))
    for r in q("SELECT * FROM deleted_tasks ORDER BY id"):
        try:
            payload = json.loads(r["payload"])
        except ValueError:
            warnings.append(f"یک ردیف آرشیو تسک حذف‌شده (id {r['id']}) خوانده نشد")
            continue
        task = payload.get("task") if isinstance(payload, dict) else None
        if isinstance(task, dict):
            task["tag_id"] = tag_map.get(task.get("tag_id"))
        db.execute("INSERT INTO audit_log (user_id, kind, payload, at) VALUES (?, 'task_deleted', ?::jsonb, ?)",
                   (uid, json.dumps(payload, ensure_ascii=False), ts(r["deleted_at"])))
    for key, kind in (("tag_merge_log", "tag_merge"), ("fill_rollback_log", "fill_rollback")):
        try:
            entries = json.loads(settings.get(key) or "[]")
        except ValueError:
            entries = []
        for e in entries:
            db.execute("INSERT INTO audit_log (user_id, kind, payload, at) VALUES (?, ?, ?::jsonb, ?)",
                       (uid, kind, json.dumps(e, ensure_ascii=False), ts(e.get("at"))))

    # ---- verification: nothing may differ from the source ----
    report = {}
    checks = [
        ("tasks", "SELECT COUNT(*) FROM tasks", "SELECT COUNT(*) c FROM tasks WHERE user_id = ?"),
        ("duration_minutes", "SELECT ROUND(COALESCE(SUM(duration_minutes),0),2) FROM tasks",
         "SELECT ROUND(COALESCE(SUM(duration_minutes),0)::numeric,2)::float c FROM tasks WHERE user_id = ?"),
        ("accumulated_minutes", "SELECT ROUND(COALESCE(SUM(accumulated_minutes),0),2) FROM tasks",
         "SELECT ROUND(COALESCE(SUM(accumulated_minutes),0)::numeric,2)::float c FROM tasks WHERE user_id = ?"),
        ("fill_minutes", "SELECT ROUND(COALESCE(SUM(fill_minutes),0),2) FROM tasks",
         "SELECT ROUND(COALESCE(SUM(fill_minutes),0)::numeric,2)::float c FROM tasks WHERE user_id = ?"),
        ("adjust_minutes", "SELECT ROUND(COALESCE(SUM(adjust_minutes),0),2) FROM tasks",
         "SELECT ROUND(COALESCE(SUM(adjust_minutes),0)::numeric,2)::float c FROM tasks WHERE user_id = ?"),
        ("task_segments", "SELECT COUNT(*) FROM task_segments",
         "SELECT COUNT(*) c FROM task_segments s JOIN tasks t ON t.id = s.task_id WHERE t.user_id = ?"),
        ("presence_segments", "SELECT COUNT(*) FROM presence_segments",
         "SELECT COUNT(*) c FROM presence_segments WHERE user_id = ?"),
        ("planned_tasks", "SELECT COUNT(*) FROM planned_tasks", "SELECT COUNT(*) c FROM planned_tasks WHERE user_id = ?"),
        ("tags", "SELECT COUNT(*) FROM tags", "SELECT COUNT(*) c FROM tags WHERE user_id = ?"),
        ("deleted_tasks", "SELECT COUNT(*) FROM deleted_tasks",
         "SELECT COUNT(*) c FROM audit_log WHERE user_id = ? AND kind = 'task_deleted'"),
    ]
    for name, src_sql, dst_sql in checks:
        a = src.execute(src_sql).fetchone()[0]
        b = db.execute(dst_sql, (uid,)).fetchone()["c"]
        report[name] = {"source": a, "imported": b}
        if a != b:
            db.rollback()
            raise ImportError_(f"عدم تطابق در «{name}»: مبدأ {a} ولی منتقل‌شده {b}؛ هیچ چیزی ذخیره نشد")
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return {"report": report, "warnings": warnings, "dry_run": dry_run}


def run(source_path, username, dry_run=False):
    session = SessionLocal()
    try:
        return import_desktop(Db(session), source_path, username, dry_run)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

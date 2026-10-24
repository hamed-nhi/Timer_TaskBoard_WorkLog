"""Personal tags, budgets, company mappings and merge transactions."""
import json

from ..core.constants import MEETING_REPORT_TYPE
from ..core.errors import ApiError
from ..core.time import now_local, today_local
from ..db.session import Db
from .catalog_helpers import catalog_payload
from .timecalc import TASK_SELECT, effective_minutes
from .validation import clean_tag_name, not_found, tag_key


TAG_SELECT = (
    "SELECT tags.*, rt.name AS report_type, p.name AS project, s.name AS story "
    "FROM tags LEFT JOIN report_types rt ON tags.report_type_id = rt.id "
    "LEFT JOIN stories s ON tags.story_id = s.id LEFT JOIN projects p ON s.project_id = p.id"
)


def get_tag(db, uid, tag_id):
    row = db.execute(TAG_SELECT + " WHERE tags.id = ? AND tags.user_id = ?", (tag_id, uid)).fetchone()
    if not row:
        not_found()
    return row


def tag_usage(db, uid, tag_id):
    tasks = db.execute("SELECT COUNT(*) c FROM tasks WHERE tag_id = ? AND user_id = ?", (tag_id, uid)).fetchone()["c"]
    planned = db.execute("SELECT COUNT(*) c FROM planned_tasks WHERE tag_id = ? AND user_id = ?",
                         (tag_id, uid)).fetchone()["c"]
    # a task deleted by mistake can be restored from the archive - it must still find its tag
    archived = db.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE user_id = ? AND kind = 'task_deleted' "
        "AND payload->'task'->>'tag_id' = ?", (uid, str(tag_id))).fetchone()["c"]
    return {"task_count": tasks, "planned_count": planned, "archived_count": archived}


def parse_budget_hours(value):
    """None for 'no budget' (empty / 0 / missing), else hours as a float in (0, 100000]."""
    if value in (None, "", 0):
        return None
    try:
        hours = float(value)
    except (TypeError, ValueError):
        raise ApiError("ساعت بودجه نامعتبر است")
    if not 0 < hours <= 100000:
        raise ApiError("ساعت بودجه باید بین ۰ و ۱۰۰٬۰۰۰ باشد")
    return hours


def tag_spent_minutes(db, uid, tag_row, now=None):
    """Minutes worked on a tag that count against its budget: finished tasks plus the live
    time of running/paused ones, from `budget_since` on (whole history when it is NULL)."""
    now = now or now_local()
    query = TASK_SELECT + " WHERE tasks.tag_id = ? AND tasks.user_id = ?"
    params = [tag_row["id"], uid]
    if tag_row["budget_since"]:
        query += " AND tasks.gregorian_date >= ?"
        params.append(tag_row["budget_since"])
    return sum(effective_minutes(r, now) for r in db.execute(query, params))


def budget_info(db, uid, tag_row, now=None):
    budget = tag_row["budget_minutes"]
    if not budget:
        return {"budget_minutes": None, "budget_since": None, "spent_minutes": None, "budget_percent": None}
    spent = tag_spent_minutes(db, uid, tag_row, now)
    return {"budget_minutes": budget, "budget_since": tag_row["budget_since"],
            "spent_minutes": round(spent, 2), "budget_percent": round(spent / budget * 100, 1)}


def tag_json(db, uid, row):
    return {**row, **budget_info(db, uid, row)}


def list_tags(db: Db, user: dict, usage: str | None):
    uid = user["id"]
    rows = db.execute(TAG_SELECT + " WHERE tags.user_id = ? ORDER BY tags.id", (uid,)).fetchall()
    for row in rows:
        if usage:
            row.update(tag_usage(db, uid, row["id"]))
        row.update(budget_info(db, uid, row))
    return rows


def set_tag_budget(tag_id: int, db: Db, user: dict, data: dict):
    """Set ({"hours": 50, "from": "all"|"today"}) or clear ({"hours": null}) a tag's hour budget.
    Only the two budget columns of the tag change - tasks are never touched."""
    uid = user["id"]
    db.lock_user(uid)
    row = get_tag(db, uid, tag_id)
    hours = parse_budget_hours(data.get("hours"))
    if hours is None:
        db.execute("UPDATE tags SET budget_minutes = NULL, budget_since = NULL WHERE id = ?", (tag_id,))
    else:
        mode = data.get("from", "keep")
        if mode == "today":
            since = today_local()
        elif mode == "all":
            since = None
        else:  # keep the current start date when only the number changes
            since = row["budget_since"]
        db.execute("UPDATE tags SET budget_minutes = ?, budget_since = ? WHERE id = ?",
                   (round(hours * 60, 2), since, tag_id))
    db.commit()
    return tag_json(db, uid, get_tag(db, uid, tag_id))


def rename_tag(tag_id: int, db: Db, user: dict, data: dict):
    """Rename a tag. Tasks point at the tag by id, so every task that already has it
    (past, present and planned) shows the new name - nothing else is touched."""
    uid = user["id"]
    name = clean_tag_name(data.get("name"))
    db.lock_user(uid)
    get_tag(db, uid, tag_id)
    for other in db.execute("SELECT id, name FROM tags WHERE id <> ? AND user_id = ?", (tag_id, uid)):
        if tag_key(other["name"]) == tag_key(name):
            raise ApiError(f"تگ دیگری با نام «{other['name']}» وجود دارد", 409)
    db.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
    db.commit()
    return tag_json(db, uid, get_tag(db, uid, tag_id))


def delete_tag(tag_id: int, db: Db, user: dict):
    """Only a tag nothing refers to can be removed - deleting a used tag would silently
    strip it from the user's history."""
    uid = user["id"]
    db.lock_user(uid)
    get_tag(db, uid, tag_id)
    usage = tag_usage(db, uid, tag_id)
    if usage["task_count"] or usage["planned_count"] or usage["archived_count"]:
        used = usage["task_count"] + usage["planned_count"] + usage["archived_count"]
        raise ApiError(f"این تگ روی {used} مورد استفاده شده و حذف نمی‌شود", 409)
    db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    db.commit()
    return {"ok": True}


def merge_tags(db, uid, source_id, target_id):
    """Move everything that uses tag `source_id` onto `target_id`, then drop the now-unused
    source tag. The ids of every row that was moved go to the audit log so the merge can be
    undone by hand. Caller holds the user lock."""
    if source_id == target_id:
        raise ApiError("یک تگ را نمی‌شود با خودش ادغام کرد")
    try:
        source, target = get_tag(db, uid, source_id), get_tag(db, uid, target_id)
    except ApiError:
        raise ApiError("تگ پیدا نشد", 404)

    task_ids = [r["id"] for r in db.execute("SELECT id FROM tasks WHERE tag_id = ? AND user_id = ?", (source_id, uid))]
    planned_ids = [r["id"] for r in db.execute(
        "SELECT id FROM planned_tasks WHERE tag_id = ? AND user_id = ?", (source_id, uid))]
    db.execute("UPDATE tasks SET tag_id = ? WHERE tag_id = ? AND user_id = ?", (target_id, source_id, uid))
    db.execute("UPDATE planned_tasks SET tag_id = ? WHERE tag_id = ? AND user_id = ?", (target_id, source_id, uid))
    # tasks deleted by mistake can be restored from the archive: they must find the surviving tag
    archived_ids = [r["id"] for r in db.execute(
        "UPDATE audit_log SET payload = jsonb_set(payload, '{task,tag_id}', to_jsonb(?::bigint)) "
        "WHERE user_id = ? AND kind = 'task_deleted' AND payload->'task'->>'tag_id' = ? RETURNING id",
        (target_id, uid, str(source_id)))]
    db.execute("DELETE FROM tags WHERE id = ?", (source_id,))
    entry = {
        "at": now_local().isoformat(timespec="seconds"),
        "source": {"id": source_id, "name": source["name"]},
        "target": {"id": target_id, "name": target["name"]},
        "task_ids": task_ids, "planned_ids": planned_ids, "archived_ids": archived_ids,
    }
    db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'tag_merge', ?::jsonb)",
               (uid, json.dumps(entry, ensure_ascii=False)))
    return entry


def merge_tag(tag_id: int, db: Db, user: dict, data: dict):
    """Merge this tag into another one ({"into": id}); the other tag keeps its name."""
    try:
        target_id = int(data.get("into"))
    except (TypeError, ValueError):
        raise ApiError("تگ مقصد نامعتبر است")
    uid = user["id"]
    db.lock_user(uid)
    entry = merge_tags(db, uid, tag_id, target_id)
    db.commit()
    return {"ok": True, "moved_tasks": len(entry["task_ids"]), "moved_planned": len(entry["planned_ids"]),
            "target": entry["target"]}


def opt_id(db, uid, table, value, label):
    """Optional catalog id (None = cleared); it must exist."""
    if value in (None, "", 0):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{label} نامعتبر است")
    if not db.execute(f"SELECT 1 FROM {table} WHERE id = ? AND user_id = ?", (value, uid)).fetchone():
        not_found()
    return value


def set_tag_company(tag_id: int, db: Db, user: dict, data: dict):
    """Report type / story of the company's main system for a tag (from the user's private catalog), and its
    gap-fill weight. Only these tag columns change; tasks are never touched."""
    uid = user["id"]
    db.lock_user(uid)
    get_tag(db, uid, tag_id)
    weight = data.get("fill_weight")
    if weight in (None, ""):
        weight = None
    else:
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            raise ApiError("وزن نامعتبر است")
        if not 0 <= weight <= 10:
            raise ApiError("وزن باید بین ۰ و ۱۰ باشد")
    db.execute("UPDATE tags SET report_type_id = ?, story_id = ?, fill_weight = ? WHERE id = ?",
               (opt_id(db, uid, "report_types", data.get("report_type_id"), "نوع گزارش"),
                opt_id(db, uid, "stories", data.get("story_id"), "استوری"), weight, tag_id))
    db.commit()
    return tag_json(db, uid, get_tag(db, uid, tag_id))


def company_catalog(db: Db, user: dict):
    payload = catalog_payload(db, user["id"])
    if not any(t["name"] == MEETING_REPORT_TYPE for t in payload["types"]):
        payload["types"].append({"id": None, "name": MEETING_REPORT_TYPE})
    return payload


def create_tag(db: Db, user: dict, data: dict):
    uid = user["id"]
    name = clean_tag_name(data.get("name"))
    db.lock_user(uid)
    existing = db.execute(TAG_SELECT + " WHERE tags.user_id = ? AND tags.name = ?", (uid, name)).fetchone()
    if existing:
        return existing, False
    budget = parse_budget_hours(data.get("budget_hours"))     # optional: a new tag can start with an hour budget
    tag_id = db.insert("INSERT INTO tags (user_id, name, budget_minutes) VALUES (?, ?, ?)",
                       (uid, name, round(budget * 60, 2) if budget else None))
    story_id = opt_id(db, uid, "stories", data.get("story_id"), "استوری") if data.get("story_id") else None
    type_id = opt_id(db, uid, "report_types", data.get("report_type_id"), "نوع گزارش") if data.get("report_type_id") else None
    if story_id or type_id:
        db.execute("UPDATE tags SET story_id = ?, report_type_id = ? WHERE id = ?", (story_id, type_id, tag_id))
    db.commit()
    return tag_json(db, uid, get_tag(db, uid, tag_id)), True

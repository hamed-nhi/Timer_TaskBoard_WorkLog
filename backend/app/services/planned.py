"""Per-user planning and transitions into running tasks."""

from ..core.time import JALALI_MONTHS, g2j, j2g, now_local, today_jalali, today_local
from ..db.session import Db
from .timecalc import assert_no_overlap, get_task_row, open_segment, row_to_dict
from .validation import clean_jalali, clean_tag_id, clean_title, not_found


PLANNED_SELECT = (
    "SELECT planned_tasks.*, tags.name AS tag_name FROM planned_tasks "
    "LEFT JOIN tags ON planned_tasks.tag_id = tags.id"
)


def planned_row_to_dict(row):
    d = dict(row)
    d["jalali_date_str"] = f"{d['jalali_year']}/{d['jalali_month']:02d}/{d['jalali_day']:02d}"
    d["month_name"] = JALALI_MONTHS[d["jalali_month"] - 1]
    try:
        planned_g = j2g(d["jalali_year"], d["jalali_month"], d["jalali_day"])
    except (ValueError, OverflowError):
        # a legacy row with an impossible date must not break the whole list
        d["gregorian"] = None
        d["overdue"] = False
        return d
    d["gregorian"] = planned_g.isoformat()
    d["overdue"] = planned_g < today_local()
    return d


def get_planned(db, uid, planned_id):
    row = db.execute(PLANNED_SELECT + " WHERE planned_tasks.id = ? AND planned_tasks.user_id = ?",
                     (planned_id, uid)).fetchone()
    if not row:
        not_found()
    return row


def list_planned(db: Db, user: dict, year: int | None, month: int | None, day: int | None):
    query = PLANNED_SELECT + " WHERE planned_tasks.user_id = ?"
    params = [user["id"]]
    for column, value in (("jalali_year", year), ("jalali_month", month), ("jalali_day", day)):
        if value:
            query += f" AND planned_tasks.{column} = ?"
            params.append(value)
    query += " ORDER BY planned_tasks.jalali_year, planned_tasks.jalali_month, planned_tasks.jalali_day, planned_tasks.id"
    return [planned_row_to_dict(r) for r in db.execute(query, params).fetchall()]


def create_planned(db: Db, user: dict, data: dict):
    uid = user["id"]
    title = clean_title(data.get("title"))
    today_j = today_jalali()
    year, month, day = clean_jalali(
        data.get("jalali_year") or today_j.year,
        data.get("jalali_month") or today_j.month,
        data.get("jalali_day") or today_j.day,
    )
    tag_id = clean_tag_id(db, uid, data.get("tag_id"))
    new_id = db.insert(
        "INSERT INTO planned_tasks (user_id, jalali_year, jalali_month, jalali_day, title, tag_id) VALUES (?,?,?,?,?,?)",
        (uid, year, month, day, title, tag_id))
    db.commit()
    return planned_row_to_dict(get_planned(db, uid, new_id))


def update_planned(planned_id: int, db: Db, user: dict, data: dict):
    """Full edit of a planned item - also used to move it to another day (postpone) by changing the date."""
    uid = user["id"]
    db.lock_user(uid)
    row = get_planned(db, uid, planned_id)
    title = clean_title(data.get("title") or row["title"])
    year, month, day = clean_jalali(
        data.get("jalali_year", row["jalali_year"]),
        data.get("jalali_month", row["jalali_month"]),
        data.get("jalali_day", row["jalali_day"]),
    )
    tag_id = clean_tag_id(db, uid, data["tag_id"]) if "tag_id" in data else row["tag_id"]
    db.execute("UPDATE planned_tasks SET title=?, jalali_year=?, jalali_month=?, jalali_day=?, tag_id=? WHERE id=?",
               (title, year, month, day, tag_id, planned_id))
    db.commit()
    return planned_row_to_dict(get_planned(db, uid, planned_id))


def delete_planned(planned_id: int, db: Db, user: dict):
    db.execute("DELETE FROM planned_tasks WHERE id = ? AND user_id = ?", (planned_id, user["id"]))
    db.commit()
    return {"ok": True}


def start_planned(planned_id: int, db: Db, user: dict):
    """Turn a planned item into a real, running task starting right now (the planned date was only a
    target/reminder), then remove it from the plan."""
    uid = user["id"]
    db.lock_user(uid)
    planned = get_planned(db, uid, planned_id)
    now = now_local()
    today_j = g2j(now.date())
    assert_no_overlap(db, uid, now, now, live=True)
    new_id = db.insert(
        """INSERT INTO tasks (user_id, jalali_year, jalali_month, jalali_day, gregorian_date,
           title, start_time, end_time, duration_minutes, status,
           accumulated_minutes, segment_started_at, tag_id, planned_flag)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,true)""",
        (uid, today_j.year, today_j.month, today_j.day, now.date(), planned["title"],
         now.strftime("%H:%M"), None, None, "running", 0, now, planned["tag_id"]))
    open_segment(db, new_id, now)
    db.execute("DELETE FROM planned_tasks WHERE id = ?", (planned_id,))
    db.commit()
    return row_to_dict(get_task_row(db, uid, new_id))

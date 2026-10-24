"""Gap fill: spread the presence-minus-tasks gap over the day's tasks (report only - the recorded
time of a task is never touched)."""
import json
from datetime import date

from fastapi import APIRouter, Body, Query

from ..common import MEETING_REPORT_TYPE, ApiError
from ..deps import DbDep, UserDep
from ..routers.presence import day_segments, presence_minutes_on
from ..timecalc import TASK_SELECT, effective_minutes, row_to_dict
from ..timeutil import now_local, today_local
from ..usersettings import get_setting, set_setting

router = APIRouter(prefix="/api")

FILL_DEFAULT_PERCENT = 95       # fill the gap up to this share of the time at the company
FILL_MAX_PERCENT = 95           # the report may never go above this share of the presence time
FILL_CAP_RATIO = 0.5            # never add more than half of a task's own time to it
FILL_STEP = 5                   # suggestions are rounded to 5 minutes
FILL_MAX_PRESENCE = 11 * 60     # longer than this: "end of work" was probably never pressed
FILL_NO_LUNCH_AFTER = 6 * 60    # one unbroken stretch longer than this: lunch was probably not recorded
FILL_ASSUMED_LUNCH = 30
FILL_DAY_OFF = 4                # Friday (date.weekday)


def parse_day(value):
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        raise ApiError("تاریخ نامعتبر است")


def presence_sanity(db, uid, day, presence, real_total):
    """Is the day's presence trustworthy enough to fill the report up to it? Returns
    (presence to use, warnings, blocked). Blocked = suggest nothing; the tasks are reported
    with their recorded time only."""
    if day.weekday() == FILL_DAY_OFF:
        return presence, ["جمعه است؛ فقط زمان ثبت‌شده‌ی تسک‌ها گزارش می‌شود."], True
    if presence <= 0:
        return presence, ["برای این روز حضوری ثبت نشده؛ تسک‌ها با زمان ثبت‌شده‌ی خودشان گزارش می‌شوند."], True
    if presence + 5 < real_total:
        return presence, ["حضور ثبت‌شده از تسک‌ها کمتر است؛ احتمالاً ورود یا خروج درست زده نشده. "
                          "اول ساعت‌های حضور را در کارت حضور درست کنید."], True
    if presence > FILL_MAX_PRESENCE:
        return presence, ["حضور بیش از ۱۱ ساعت ثبت شده؛ احتمالاً «پایان کار» زده نشده. "
                          "اول ساعت‌های حضور را درست کنید."], True
    segs = day_segments(db, uid, day, order="started_at")
    warnings = []
    if len(segs) == 1 and presence > FILL_NO_LUNCH_AFTER:
        presence -= FILL_ASSUMED_LUNCH
        warnings.append("خروج ناهار ثبت نشده؛ ۳۰ دقیقه ناهار از حضور کم شد.")
    if day < today_local() and segs and segs[-1]["kind"] != "end":
        warnings.append("«پایان کار» برای این روز زده نشده است.")
    return presence, warnings, False


def fill_weight_of(row):
    w = row["tag_fill_weight"]
    return 1.0 if w is None else float(w)


def suggest_fill(items, needed):
    """Water-filling: share `needed` minutes by weight x own minutes, each task capped at
    FILL_CAP_RATIO of its own time; whatever a capped task cannot take goes to the others."""
    share = {i["id"]: 0.0 for i in items}
    active = [i for i in items if i["weight"] > 0 and i["minutes"] > 0]
    remaining = needed
    while remaining > 0.01 and active:
        total_w = sum(i["weight"] * i["minutes"] for i in active)
        capped = []
        given = 0.0
        for i in active:
            room = i["minutes"] * FILL_CAP_RATIO - share[i["id"]]
            part = remaining * i["weight"] * i["minutes"] / total_w
            if part >= room:
                part = room
                capped.append(i)
            share[i["id"]] += part
            given += part
        remaining -= given
        if not capped:
            break
        active = [i for i in active if i not in capped]
    return {k: int(round(v / FILL_STEP)) * FILL_STEP for k, v in share.items()}


def fill_target_percent(db, uid, value=None):
    if value is None:
        value = get_setting(db, uid, "fill_target_percent", FILL_DEFAULT_PERCENT)
    try:
        pct = float(value)
    except (TypeError, ValueError):
        raise ApiError("درصد هدف نامعتبر است")
    if not 50 <= pct <= FILL_MAX_PERCENT:
        raise ApiError("درصد هدف باید بین ۵۰ و ۹۵ باشد")
    return pct


@router.get("/fill-suggestion")
def fill_suggestion(db: DbDep, user: UserDep, date_: str | None = Query(None, alias="date"),
                    percent: str | None = Query(None)):
    uid = user["id"]
    day = parse_day(date_) if date_ else today_local()
    pct = fill_target_percent(db, uid, percent)
    now = now_local()
    rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? AND tasks.gregorian_date = ? "
                      "ORDER BY tasks.start_time, tasks.id", (uid, day)).fetchall()
    raw_presence = presence_minutes_on(db, uid, day)
    real_total = sum(effective_minutes(r, now) for r in rows)
    presence, warnings, blocked = presence_sanity(db, uid, day, raw_presence, real_total)
    target = presence * pct / 100
    needed = 0.0 if blocked else max(0.0, target - real_total)
    items = []
    for r in rows:
        d = row_to_dict(r)
        meeting = d["company_type"] == MEETING_REPORT_TYPE
        items.append({"id": r["id"], "title": r["title"], "tag_name": r["tag_name"],
                      "minutes": round(effective_minutes(r, now), 1),
                      "weight": 0.0 if meeting else fill_weight_of(r), "meeting": meeting,
                      "fill_minutes": r["fill_minutes"] or 0})
    suggested = suggest_fill(items, needed)
    for i in items:
        i["suggested"] = suggested[i["id"]]
        i["cap"] = int(i["minutes"] * FILL_CAP_RATIO)
    return {
        "date": day.isoformat(), "percent": pct, "presence_minutes": round(raw_presence, 1),
        "usable_presence_minutes": round(presence, 1), "warnings": warnings, "blocked": blocked,
        "task_minutes": round(real_total, 1), "target_minutes": round(target, 1),
        "needed_minutes": round(needed, 1),
        "allowed_minutes": round(max(0.0, target - real_total), 1), "suggested_total": sum(suggested.values()),
        "current_fill_total": round(sum(i["fill_minutes"] for i in items), 1), "items": items,
    }


@router.post("/fill")
def apply_fill(db: DbDep, user: UserDep, data: dict = Body(...)):
    """Save the report-only extra minutes of a day's tasks ({"date", "items": [{"id", "fill_minutes"}]},
    absolute values; 0 removes). The real time of a task is never touched."""
    uid = user["id"]
    day = parse_day(data.get("date"))
    items = data.get("items")
    if not isinstance(items, list):
        raise ApiError("فهرست نامعتبر است")
    db.lock_user(uid)
    for it in items:
        try:
            task_id = int(it.get("id"))
            minutes = float(it.get("fill_minutes") or 0)
        except (TypeError, ValueError, AttributeError):
            raise ApiError("مقدار نامعتبر است")
        if minutes != minutes or not 0 <= minutes <= 600:
            raise ApiError("زمان تکمیلی هر تسک باید بین ۰ و ۶۰۰ دقیقه باشد")
        if not db.execute("SELECT 1 FROM tasks WHERE id = ? AND user_id = ? AND gregorian_date = ?",
                          (task_id, uid, day)).fetchone():
            raise ApiError("تسک در این روز پیدا نشد", 404)
        db.execute("UPDATE tasks SET fill_minutes = ? WHERE id = ?", (round(minutes, 1), task_id))
    if data.get("percent") is not None:
        set_setting(db, uid, "fill_target_percent", fill_target_percent(db, uid, data.get("percent")))
    # the report (recorded + extra) may not go above the target share of the (trusted) presence
    pct = fill_target_percent(db, uid, data.get("percent"))
    now = now_local()
    rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? AND tasks.gregorian_date = ?", (uid, day)).fetchall()
    real_total = sum(effective_minutes(r, now) for r in rows)
    presence, _, _ = presence_sanity(db, uid, day, presence_minutes_on(db, uid, day), real_total)
    allowed = max(0.0, presence * pct / 100 - real_total)
    filled = sum((r["fill_minutes"] or 0) for r in rows)
    if filled > allowed + 1:
        db.rollback()
        raise ApiError(f"حداکثر {int(allowed)} دقیقه تکمیلی مجاز است (گزارش نباید از {int(pct)}٪ حضور بیشتر شود)")
    db.commit()
    return {"ok": True}


@router.post("/fill/rollback")
def rollback_fill(db: DbDep, user: UserDep, data: dict = Body(...)):
    """Take a day's report-only extra minutes off again, so the report is the recorded time.
    The removed values are kept in the audit log so nothing is lost."""
    uid = user["id"]
    day = parse_day(data.get("date")) if data.get("date") else today_local()
    db.lock_user(uid)
    rows = db.execute("SELECT id, fill_minutes FROM tasks WHERE user_id = ? AND gregorian_date = ? AND fill_minutes <> 0",
                      (uid, day)).fetchall()
    if rows:
        payload = {"date": day.isoformat(), "fills": {str(r["id"]): r["fill_minutes"] for r in rows}}
        db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'fill_rollback', ?::jsonb)",
                   (uid, json.dumps(payload)))
        db.execute("UPDATE tasks SET fill_minutes = 0 WHERE user_id = ? AND gregorian_date = ?", (uid, day))
    db.commit()
    return {"ok": True, "removed_minutes": round(sum(r["fill_minutes"] for r in rows), 1)}

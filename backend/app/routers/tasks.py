import json
from datetime import datetime, timedelta

import jdatetime
from fastapi import APIRouter, Body
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..common import ApiError, clean_jalali, clean_tag_id, clean_time, clean_title
from ..deps import DbDep, UserDep
from ..timecalc import (TASK_SELECT, assert_no_overlap, close_open_segment, compute_duration, duration_from_segments,
                        effective_minutes, get_own_task, get_task_row, open_segment, parse_adjust, row_to_dict,
                        window_dt)
from ..timeutil import JALALI_MONTHS, g2j, j2g, now_local, parse_time, today_jalali, today_local

router = APIRouter(prefix="/api")


@router.get("/today")
def api_today(user: UserDep):
    now = now_local()
    today_j = g2j(now.date())
    return {
        "gregorian": now.date().isoformat(),
        "jalali_year": today_j.year,
        "jalali_month": today_j.month,
        "jalali_day": today_j.day,
        "month_name": JALALI_MONTHS[today_j.month - 1],
        "time": now.strftime("%H:%M"),
        "server_time": now.isoformat(timespec="seconds"),    # lets a browser in another time zone tick correctly
    }


@router.get("/month-days")
def api_month_days(user: UserDep, year: int | None = None, month: int | None = None):
    if year is None or month is None or not 1 <= month <= 12 or not 1 <= year <= 9000:
        raise ApiError("سال یا ماه نامعتبر است")
    days_in_month = 29 if month == 12 and not jdatetime.date(year, 1, 1).isleap() else (31 if month <= 6 else 30)
    return {"days": days_in_month}


@router.get("/shift-date")
def api_shift_date(user: UserDep, year: int | None = None, month: int | None = None, day: int | None = None,
                   delta: int = 0):
    """Move a Jalali date forward/back by `delta` days - the daily-log prev/next-day navigation
    uses this instead of reimplementing Jalali calendar math in the browser."""
    year, month, day = clean_jalali(year, month, day)
    try:
        g_date = j2g(year, month, day) + timedelta(days=delta)
        j_date = g2j(g_date)
    except OverflowError:
        raise ApiError("تاریخ نامعتبر است")
    return {"jalali_year": j_date.year, "jalali_month": j_date.month, "jalali_day": j_date.day,
            "month_name": JALALI_MONTHS[j_date.month - 1], "gregorian": g_date.isoformat()}


@router.get("/yesterday-titles")
def yesterday_titles(db: DbDep, user: UserDep):
    """Distinct task titles from the previous calendar day, for autocomplete suggestions."""
    yesterday_j = g2j(today_local() - timedelta(days=1))
    rows = db.execute(
        """SELECT DISTINCT title FROM tasks
           WHERE user_id = ? AND jalali_year = ? AND jalali_month = ? AND jalali_day = ?
           ORDER BY title""",
        (user["id"], yesterday_j.year, yesterday_j.month, yesterday_j.day)).fetchall()
    return [r["title"] for r in rows]


@router.get("/tasks")
def list_tasks(db: DbDep, user: UserDep, year: int | None = None, month: int | None = None, day: int | None = None):
    query = TASK_SELECT + " WHERE tasks.user_id = ?"
    params = [user["id"]]
    for column, value in (("jalali_year", year), ("jalali_month", month), ("jalali_day", day)):
        if value:
            query += f" AND tasks.{column} = ?"
            params.append(value)
    query += " ORDER BY tasks.jalali_year, tasks.jalali_month, tasks.jalali_day, tasks.start_time"
    return [row_to_dict(r) for r in db.execute(query, params).fetchall()]


@router.get("/tasks/paused")
def list_paused_tasks(db: DbDep, user: UserDep):
    """Several tasks can be paused at once, so the page needs the full list to let the user pick."""
    rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? AND tasks.status='paused' ORDER BY tasks.id DESC",
                      (user["id"],)).fetchall()
    return [row_to_dict(r) for r in rows]


@router.post("/tasks")
def create_task(db: DbDep, user: UserDep, data: dict = Body(...)):
    uid = user["id"]
    title = clean_title(data.get("title"))

    today_j = today_jalali()
    now = now_local()
    year, month, day = clean_jalali(
        data.get("jalali_year") or today_j.year,
        data.get("jalali_month") or today_j.month,
        data.get("jalali_day") or today_j.day,
    )
    start_time = clean_time(data.get("start_time")) or now.strftime("%H:%M")
    end_time = clean_time(data.get("end_time"))
    gdate = j2g(year, month, day)

    if end_time:
        # a fully-specified backdated / manual entry: finished immediately
        status = "done"
        duration = compute_duration(start_time, end_time)
        accumulated = duration or 0
        segment_started_at = None
        seg_start_dt = datetime.combine(gdate, parse_time(start_time))
        seg_end_dt = seg_start_dt + timedelta(minutes=duration or 0)
    else:
        # live task: track a running segment starting from the given clock time (defaults to "now"), so
        # pause/resume elapsed time is measured correctly even when the task started earlier than logged
        status = "running"
        duration = None
        accumulated = 0
        start_dt = datetime.combine(gdate, parse_time(start_time))
        if start_dt > now:
            start_dt = now
        segment_started_at = start_dt

    db.lock_user(uid)
    if status == "running":
        assert_no_overlap(db, uid, start_dt, now, live=True)
    else:
        assert_no_overlap(db, uid, seg_start_dt, seg_end_dt)
    tag_id = clean_tag_id(db, uid, data.get("tag_id"))
    new_id = db.insert(
        """INSERT INTO tasks (user_id, jalali_year, jalali_month, jalali_day, gregorian_date,
           title, start_time, end_time, duration_minutes, status,
           accumulated_minutes, segment_started_at, tag_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, year, month, day, gdate, title, start_time, end_time, duration, status,
         accumulated, segment_started_at, tag_id))
    if status == "running":
        open_segment(db, new_id, segment_started_at)
    else:
        open_segment(db, new_id, seg_start_dt)
        close_open_segment(db, new_id, seg_end_dt)
    db.commit()
    return JSONResponse(jsonable_encoder(row_to_dict(get_task_row(db, uid, new_id))), status_code=201)


@router.post("/tasks/{task_id}/pause")
def pause_task(task_id: int, db: DbDep, user: UserDep):
    uid = user["id"]
    db.lock_user(uid)
    row = get_own_task(db, uid, task_id)
    if row["status"] != "running":
        return row_to_dict(get_task_row(db, uid, task_id))

    now = now_local()
    accumulated = row["accumulated_minutes"] or 0
    if row["segment_started_at"]:
        accumulated += max(0, (now - row["segment_started_at"]).total_seconds() / 60)

    db.execute("UPDATE tasks SET status='paused', accumulated_minutes=?, segment_started_at=NULL WHERE id=?",
               (round(accumulated, 2), task_id))
    close_open_segment(db, task_id, now)
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: DbDep, user: UserDep):
    uid = user["id"]
    db.lock_user(uid)
    row = get_own_task(db, uid, task_id)
    if row["status"] != "paused":
        return row_to_dict(get_task_row(db, uid, task_id))

    now = now_local()
    assert_no_overlap(db, uid, now, now, exclude_id=task_id, live=True)
    db.execute("UPDATE tasks SET status='running', segment_started_at=? WHERE id=?", (now, task_id))
    open_segment(db, task_id, now)
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.post("/tasks/{task_id}/stop")
def stop_task(task_id: int, db: DbDep, user: UserDep):
    uid = user["id"]
    db.lock_user(uid)
    row = get_own_task(db, uid, task_id)
    if row["status"] == "done":
        # already finished (double-click / stale screen): must not touch the recorded end time
        return row_to_dict(get_task_row(db, uid, task_id))

    now = now_local()
    accumulated = row["accumulated_minutes"] or 0
    if row["status"] == "running" and row["segment_started_at"]:
        accumulated += max(0, (now - row["segment_started_at"]).total_seconds() / 60)

    db.execute(
        """UPDATE tasks SET end_time=?, duration_minutes=?, status='done',
           accumulated_minutes=?, segment_started_at=NULL WHERE id=?""",
        (now.strftime("%H:%M"), round(accumulated, 1), round(accumulated, 2), task_id))
    if row["status"] == "running":
        close_open_segment(db, task_id, now)
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: int, db: DbDep, user: UserDep):
    """Start another work session on a task that was already stopped today (e.g. finished the
    morning part, continuing after lunch). The time already recorded is kept and the new session is
    added on top when it is stopped."""
    uid = user["id"]
    db.lock_user(uid)
    row = get_own_task(db, uid, task_id)
    if row["status"] != "done":
        return row_to_dict(get_task_row(db, uid, task_id))
    if row["gregorian_date"] != today_local():
        raise ApiError("فقط تسک‌های امروز را می‌توان دوباره ادامه داد")

    now = now_local()
    assert_no_overlap(db, uid, now, now, exclude_id=task_id, live=True)
    previous = row["duration_minutes"] if row["duration_minutes"] is not None else (row["accumulated_minutes"] or 0)
    # duration_minutes is left untouched on purpose: nothing recorded is erased, it is simply replaced by
    # the new total when the task is stopped again. entered_main_system is cleared because the minutes change.
    db.execute(
        """UPDATE tasks SET status='running', end_time=NULL, accumulated_minutes=?,
           segment_started_at=?, entered_main_system=false WHERE id=?""",
        (round(previous, 2), now, task_id))
    open_segment(db, task_id, now)
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.get("/tasks/{task_id}/segments")
def task_segments(task_id: int, db: DbDep, user: UserDep):
    """Full pause/resume history for one task: every work segment with its start/end clock time."""
    get_own_task(db, user["id"], task_id)
    rows = db.execute("SELECT * FROM task_segments WHERE task_id = ? ORDER BY id", (task_id,)).fetchall()
    now = now_local()
    result = []
    for r in rows:
        started, ended = r["started_at"], r["ended_at"]
        minutes = ((ended or now) - started).total_seconds() / 60
        result.append({
            "started_at": started, "ended_at": ended,
            "started_label": started.strftime("%H:%M"),
            "ended_label": ended.strftime("%H:%M") if ended else None,
            "minutes": round(minutes, 1),
            "ongoing": ended is None,
        })
    return result


@router.post("/tasks/{task_id}/entered")
def set_entered(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    """Toggle the 'entered into the main system' checkbox of the daily log - a manual bookkeeping
    flag, it doesn't touch timing data."""
    uid = user["id"]
    get_own_task(db, uid, task_id)
    db.execute("UPDATE tasks SET entered_main_system=? WHERE id=?", (bool(data.get("entered")), task_id))
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.post("/tasks/{task_id}/company")
def set_task_company(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    """Report type (override), "planned" and "outside the company" ticks of a task for the company's
    main system. Only these columns change - never the task's time."""
    uid = user["id"]
    db.lock_user(uid)
    get_own_task(db, uid, task_id)
    if "report_type_id" in data:
        value = data.get("report_type_id")
        if value in (None, "", 0):
            value = None
        else:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ApiError("نوع گزارش نامعتبر است")
            if not db.execute("SELECT 1 FROM report_types WHERE id = ? AND user_id = ?", (value, uid)).fetchone():
                raise ApiError("not found", 404)
        db.execute("UPDATE tasks SET report_type_id = ? WHERE id = ?", (value, task_id))
    for key in ("outside_company", "planned_flag"):
        if key in data:
            db.execute(f"UPDATE tasks SET {key} = ? WHERE id = ?", (bool(data.get(key)), task_id))
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.put("/tasks/{task_id}")
def update_task(task_id: int, db: DbDep, user: UserDep, data: dict = Body(...)):
    uid = user["id"]
    db.lock_user(uid)
    row = get_own_task(db, uid, task_id)

    year, month, day = clean_jalali(
        data.get("jalali_year", row["jalali_year"]),
        data.get("jalali_month", row["jalali_month"]),
        data.get("jalali_day", row["jalali_day"]),
    )
    title = clean_title(data["title"]) if "title" in data else row["title"]
    tag_id = clean_tag_id(db, uid, data["tag_id"]) if "tag_id" in data else row["tag_id"]
    start_time = clean_time(data.get("start_time")) or row["start_time"]
    end_time = clean_time(data["end_time"]) if "end_time" in data else row["end_time"]
    gdate = j2g(year, month, day)
    now = now_local()

    # title/tag/date edits must never touch the timer; only an explicit
    # start/end time change affects the tracked minutes
    status = row["status"]
    duration = row["duration_minutes"]
    accumulated = row["accumulated_minutes"] or 0
    segment_started_at = row["segment_started_at"]
    start_changed = start_time != row["start_time"]
    end_changed = end_time != row["end_time"]
    adjust = parse_adjust(data.get("adjust_minutes"))
    adjust_total = row["adjust_minutes"] or 0

    if status == "done":
        if not end_time:
            raise ApiError("برای تسک تمام‌شده، ساعت پایان را خالی نگذارید")
        repair = False
        if not (start_changed or end_changed) and row["duration_minutes"] is not None:
            # saving a never-paused task whose recorded total disagrees with its own start/end repairs it
            span = compute_duration(start_time, end_time)
            # work can never exceed the clock span, and a task that lasted minutes is never 0:
            # only those two impossible cases are repaired (a smaller total may be a real pause)
            repair = span is not None and (row["duration_minutes"] > span + max(adjust_total, 0) + 0.5
                                           or (row["duration_minutes"] < 0.5 and span >= 1))
        if start_changed or end_changed or gdate != row["gregorian_date"]:
            new_s, new_e = window_dt(gdate, start_time, end_time)
            n_segs = db.execute("SELECT COUNT(*) c FROM task_segments WHERE task_id = ?", (task_id,)).fetchone()["c"]
            if n_segs <= 1 or gdate != row["gregorian_date"]:
                assert_no_overlap(db, uid, new_s, new_e, exclude_id=task_id)
            else:
                # a task with pauses: its gaps may hold other work, so only the parts added around it count
                old_s, old_e = window_dt(row["gregorian_date"], row["start_time"], row["end_time"])
                if new_s < old_s:
                    assert_no_overlap(db, uid, new_s, min(old_s, new_e), exclude_id=task_id)
                if new_e > old_e:
                    assert_no_overlap(db, uid, max(old_e, new_s), new_e, exclude_id=task_id)
        if start_changed or end_changed or repair:
            new_span = compute_duration(start_time, end_time)
            old_span = compute_duration(row["start_time"], row["end_time"])
            recorded = row["duration_minutes"]
            segs = db.execute("SELECT id FROM task_segments WHERE task_id = ?", (task_id,)).fetchall()
            if len(segs) == 1:
                # never paused: the typed times ARE the work, whatever the old (possibly wrong) total was
                duration = round((new_span or 0) + adjust_total, 1) if new_span is not None else new_span
                seg_start = datetime.combine(gdate, parse_time(start_time))
                db.execute("UPDATE task_segments SET started_at = ?, ended_at = ? WHERE id = ?",
                           (seg_start, seg_start + timedelta(minutes=new_span or 0), segs[0]["id"]))
            elif recorded is None or old_span is None or repair:
                duration = round((new_span or 0) + adjust_total, 1) if new_span is not None else new_span
            elif len(segs) > 1:
                duration = duration_from_segments(db, task_id, gdate, start_time, end_time, recorded, old_span,
                                                  new_span, row["adjust_minutes"] or 0)
            else:
                # apply only the difference the user typed: minutes the task was paused stay
                # out of the total (with no pauses recorded == old duration, this equals the new span)
                duration = round(recorded + new_span - old_span, 1)
                if duration <= 0:
                    # the implied pause is longer than the new window (e.g. a task re-opened hours
                    # later, then its end time corrected): the typed times are what the user means
                    duration = new_span
            accumulated = duration or 0
        if adjust and duration is not None:
            if duration + adjust < 0:
                raise ApiError("با این کاهش، مدت تسک منفی می‌شود")
            duration = round(duration + adjust, 1)
            accumulated = duration
            adjust_total = round(adjust_total + adjust, 1)
    else:
        segs = db.execute("SELECT id, started_at FROM task_segments WHERE task_id = ?", (task_id,)).fetchall()
        if row["start_time"] and start_changed and status == "running" and segment_started_at \
                and len(segs) == 1 and not accumulated:
            # never paused: the running segment itself starts at the corrected time (not in the future)
            new_start = datetime.combine(segment_started_at.date(), parse_time(start_time))
            new_start = min(new_start, now)
            if new_start < segment_started_at:
                assert_no_overlap(db, uid, new_start, segment_started_at, exclude_id=task_id)
            segment_started_at = new_start
            db.execute("UPDATE task_segments SET started_at = ? WHERE id = ?", (segment_started_at, segs[0]["id"]))
        elif row["start_time"] and start_changed:
            # corrected start of a live task: keep pauses intact, add/remove the difference
            shift = compute_duration(start_time, row["start_time"]) or 0
            if shift > 12 * 60:
                shift -= 24 * 60
            accumulated = max(0, accumulated + shift)

        if adjust:
            now_total = effective_minutes(row, now) + adjust
            if now_total < 0:
                raise ApiError("با این کاهش، مدت تسک منفی می‌شود")
            accumulated = round(accumulated + adjust, 2)
            adjust_total = round(adjust_total + adjust, 1)

        if end_time:
            # finishing by typing the end time: count real work only (never the
            # pauses or the idle gap between sessions), up to the typed time
            extra = 0.0
            if status == "running" and segment_started_at:
                end_dt = datetime.combine(segment_started_at.date(), parse_time(end_time))
                if end_dt < segment_started_at:
                    next_day = end_dt + timedelta(days=1)
                    end_dt = next_day if next_day <= now else segment_started_at
                extra = (end_dt - segment_started_at).total_seconds() / 60
                close_open_segment(db, task_id, end_dt)
            total = accumulated + extra
            status = "done"
            duration = round(total, 1)
            accumulated = total
            segment_started_at = None

    db.execute(
        """UPDATE tasks SET jalali_year=?, jalali_month=?, jalali_day=?, gregorian_date=?,
           title=?, start_time=?, end_time=?, duration_minutes=?, status=?,
           accumulated_minutes=?, segment_started_at=?, tag_id=?, adjust_minutes=? WHERE id=?""",
        (year, month, day, gdate, title, start_time, end_time, duration, status,
         round(accumulated, 2), segment_started_at, tag_id, adjust_total, task_id))
    db.commit()
    return row_to_dict(get_task_row(db, uid, task_id))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: DbDep, user: UserDep):
    uid = user["id"]
    db.lock_user(uid)
    row = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, uid)).fetchone()
    if row:
        segments = db.execute("SELECT * FROM task_segments WHERE task_id = ? ORDER BY id", (task_id,)).fetchall()
        payload = json.dumps({"task": row, "segments": segments}, ensure_ascii=False, default=str)
        db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'task_deleted', ?::jsonb)", (uid, payload))
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return {"ok": True}

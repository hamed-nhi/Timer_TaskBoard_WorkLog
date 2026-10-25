"""Presence at the company. Check-in/out is manual only on the web; the page reminds the user when a
task is running without a check-in (`needs_checkin`)."""
from datetime import date, datetime, timedelta

from ..core.errors import ApiError
from ..core.time import g2j, now_local, parse_time, to_date, today_local
from ..db.session import Db
from .timecalc import TASK_SELECT, effective_minutes
from .validation import not_found


def day_bounds(gdate):
    start = datetime.combine(to_date(gdate), datetime.min.time())
    return start, start + timedelta(days=1)


def day_segments(db, uid, gdate, order="started_at, id"):
    lo, hi = day_bounds(gdate)
    return db.execute(
        f"SELECT * FROM presence_segments WHERE user_id = ? AND started_at >= ? AND started_at < ? ORDER BY {order}",
        (uid, lo, hi)).fetchall()


def first_task_start(db, uid, gdate):
    return db.execute(
        """SELECT MIN(s.started_at) m FROM task_segments s JOIN tasks t ON t.id = s.task_id
           WHERE t.user_id = ? AND t.gregorian_date = ?""", (uid, gdate)).fetchone()["m"]


def presence_state(db, uid):
    """Today's presence: stretches at the company, total time there, and how much of it has tasks."""
    now = now_local()
    gdate = now.date()
    rows = day_segments(db, uid, gdate)
    segments, total, open_id, since = [], 0.0, None, None
    for r in rows:
        start = r["started_at"]
        end = r["ended_at"] or now
        minutes = max(0.0, (end - start).total_seconds() / 60)
        total += minutes
        if not r["ended_at"]:
            open_id, since = r["id"], start
        segments.append({"id": r["id"], "start": start.strftime("%H:%M"),
                         "end": end.strftime("%H:%M") if r["ended_at"] else None,
                         "minutes": round(minutes, 1), "open": not r["ended_at"],
                         "kind": r["kind"], "note": r["note"]})
    task_rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? AND tasks.gregorian_date = ?", (uid, gdate)).fetchall()
    task_minutes = sum(effective_minutes(t, now) for t in task_rows)
    fill_minutes = sum((t["fill_minutes"] or 0) for t in task_rows)
    running = next((t for t in task_rows if t["status"] == "running"), None)
    paused = [t for t in task_rows if t["status"] == "paused"]
    first_task = first_task_start(db, uid, gdate)
    return {
        "first_task_start": first_task.strftime("%H:%M") if first_task and first_task.date() == gdate else None,
        "status": "in" if open_id else ("done" if rows and rows[-1]["kind"] == "end" else ("break" if rows else "none")),
        "segments": segments,
        "total_minutes": round(total, 1),
        "since": since,
        "task_minutes": round(task_minutes, 1),
        "fill_minutes": round(fill_minutes, 1),
        "running_task": running["title"] if running else None,
        "running_task_id": running["id"] if running else None,
        "paused_task": paused[-1]["title"] if paused else None,
        "needs_checkin": bool(running) and not open_id,
        "server_time": now,
    }


def presence_check_in(db, uid):
    """Open a stretch now unless one is already open. An open stretch left over from an earlier
    day (forgot to check out) is closed at the end of that day first."""
    now = now_local()
    for r in db.execute("SELECT id, started_at FROM presence_segments WHERE user_id = ? AND ended_at IS NULL",
                        (uid,)).fetchall():
        if r["started_at"].date() < now.date():
            end_of_day = datetime.combine(r["started_at"].date(), datetime.max.time()).replace(microsecond=0)
            db.execute("UPDATE presence_segments SET ended_at = ? WHERE id = ?", (end_of_day, r["id"]))
    if not db.execute("SELECT 1 FROM presence_segments WHERE user_id = ? AND ended_at IS NULL", (uid,)).fetchone():
        db.execute("INSERT INTO presence_segments (user_id, started_at, ended_at) VALUES (?, ?, NULL)",
                   (uid, now.replace(microsecond=0)))


def presence_minutes_on(db, uid, gdate):
    now = now_local()
    total = 0.0
    for r in day_segments(db, uid, gdate):
        start = r["started_at"]
        end = r["ended_at"] or max(now, start)
        total += max(0.0, (end - start).total_seconds() / 60)
    return total


def presence_get(db: Db, user: dict):
    return presence_state(db, user["id"])


def presence_history(db: Db, user: dict, days: int):
    """Presence per day (newest first) next to the task total of that day. Only days that have a
    recorded presence appear."""
    uid = user["id"]
    now = now_local()
    days = min(days or 31, 400)
    since = datetime.combine(now.date() - timedelta(days=days), datetime.min.time())
    per_day = {}
    for r in db.execute("SELECT * FROM presence_segments WHERE user_id = ? AND started_at >= ? ORDER BY started_at",
                        (uid, since)).fetchall():
        d = r["started_at"].date()
        start = r["started_at"]
        end = r["ended_at"] or (now if d == now.date() else None)
        item = per_day.setdefault(d, {"minutes": 0.0, "first": start.strftime("%H:%M"), "last": None, "unclosed": False})
        if end is None:
            item["unclosed"] = True
        else:
            item["minutes"] += max(0.0, (end - start).total_seconds() / 60)
            item["last"] = end.strftime("%H:%M")
    out = []
    for d in sorted(per_day, reverse=True):
        task_rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? AND tasks.gregorian_date = ?", (uid, d)).fetchall()
        tasks = sum(effective_minutes(t, now) for t in task_rows)
        j = g2j(d)
        item = per_day[d]
        out.append({"date": d.isoformat(), "jalali": f"{j.year}/{j.month:02d}/{j.day:02d}", "first": item["first"],
                    "last": item["last"], "unclosed": item["unclosed"],
                    "presence_minutes": round(item["minutes"], 1), "task_minutes": round(tasks, 1),
                    "gap_minutes": round(max(0.0, item["minutes"] - tasks), 1)})
    return out


def requested_day(value):
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError()
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError("تاریخ نامعتبر است")


def presence_alerts(db: Db, user: dict, date_: str | None = None):
    """Compare past days only; include fill and days with tasks but no attendance.

    Forgotten open spans stop at their own midnight, so the discrepancy cannot
    grow just because the job ran on a later day. No recorded time is changed.
    """
    uid, today = user["id"], now_local().date()
    target = requested_day(date_) if date_ is not None else None
    extra = " AND gregorian_date = ?" if target else ""
    params = [uid, today] + ([target] if target else []) + [uid, datetime.combine(today, datetime.min.time())]
    rows = db.execute("""
        WITH task_totals AS (
          SELECT gregorian_date AS day,
            SUM(CASE WHEN status = 'done' THEN COALESCE(duration_minutes, 0)
                ELSE COALESCE(accumulated_minutes, 0) + CASE
                  WHEN status = 'running' AND segment_started_at IS NOT NULL THEN
                    GREATEST(0, EXTRACT(EPOCH FROM (gregorian_date + INTERVAL '1 day' - segment_started_at)) / 60)
                  ELSE 0 END END) AS actual,
            SUM(COALESCE(fill_minutes, 0)) AS fill
          FROM tasks WHERE user_id = ? AND gregorian_date < ?""" + extra + """
          GROUP BY gregorian_date
        ), presence_totals AS (
          SELECT started_at::date AS day,
            SUM(GREATEST(0, EXTRACT(EPOCH FROM (
              LEAST(COALESCE(ended_at, started_at::date + INTERVAL '1 day'),
                    started_at::date + INTERVAL '1 day') - started_at)) / 60)) AS minutes,
            BOOL_OR(ended_at IS NULL) AS unclosed
          FROM presence_segments WHERE user_id = ? AND started_at < ?
          GROUP BY started_at::date
        )
        SELECT t.day, t.actual, t.fill, COALESCE(p.minutes, 0) AS presence,
               COALESCE(p.unclosed, false) AS unclosed
        FROM task_totals t LEFT JOIN presence_totals p ON t.day = p.day
        WHERE t.actual + t.fill > COALESCE(p.minutes, 0) + 0.05
        ORDER BY t.day DESC
        """, params).fetchall()
    out = []
    for row in rows[:50]:
        j = g2j(row["day"])
        actual, fill, presence = (float(row[key]) for key in ("actual", "fill", "presence"))
        out.append({"date": row["day"].isoformat(), "jalali": f"{j.year}/{j.month:02d}/{j.day:02d}",
                    "year": j.year, "month": j.month, "day": j.day,
                    "task_minutes": round(actual, 1), "fill_minutes": round(fill, 1),
                    "reported_minutes": round(actual + fill, 1), "presence_minutes": round(presence, 1),
                    "excess_minutes": round(actual + fill - presence, 1), "unclosed": row["unclosed"], "segments": []})
    if out:
        by_date = {r["date"]: r for r in out}
        segments = db.execute("SELECT id, started_at, ended_at FROM presence_segments "
                              "WHERE user_id = ? AND started_at::date = ANY(?) ORDER BY started_at, id",
                              (uid, [date.fromisoformat(d) for d in by_date])).fetchall()
        for segment in segments:
            key = segment["started_at"].date().isoformat()
            by_date[key]["segments"].append({"id": segment["id"], "start": segment["started_at"].strftime("%H:%M"),
                                            "end": segment["ended_at"].strftime("%H:%M") if segment["ended_at"] else None})
    return {"days": out, "count": len(rows)}


def presence_start(db: Db, user: dict):
    uid = user["id"]
    db.lock_user(uid)
    presence_check_in(db, uid)
    db.commit()
    return presence_state(db, uid)


def presence_leave(db, uid, kind, note=None):
    db.lock_user(uid)
    db.execute("UPDATE presence_segments SET ended_at = ?, kind = ?, note = ? WHERE user_id = ? AND ended_at IS NULL",
               (now_local().replace(microsecond=0), kind, note, uid))
    db.commit()
    return presence_state(db, uid)


def presence_pause(db: Db, user: dict, data: dict | None):
    """Leave for lunch / a break (come back later today)."""
    note = data.get("note") if isinstance(data, dict) else None
    return presence_leave(db, user["id"], "break", (note or "").strip()[:60] or None)


def presence_finish(db: Db, user: dict):
    """Leave for good: the working day is over."""
    return presence_leave(db, user["id"], "end")


def presence_window(db, uid, data, gdate, current_id=None):
    """Validated (start, end) datetimes for a stretch on `gdate`; end None = still at the company."""
    gdate = to_date(gdate)
    try:
        start = datetime.combine(gdate, parse_time(data.get("start_time")))
    except (TypeError, ValueError):
        raise ApiError("ساعت ورود نامعتبر است")
    end = None
    if data.get("end_time"):
        try:
            end = datetime.combine(gdate, parse_time(data["end_time"]))
        except (TypeError, ValueError):
            raise ApiError("ساعت خروج نامعتبر است")
        if end <= start:
            raise ApiError("ساعت خروج باید بعد از ساعت ورود باشد")
    elif gdate != today_local():
        raise ApiError("برای روزهای گذشته ساعت خروج لازم است")
    far = end or datetime.combine(gdate, datetime.max.time())
    for r in day_segments(db, uid, gdate):
        if r["id"] == current_id:
            continue
        r_end = r["ended_at"] or datetime.max
        if start < r_end and r["started_at"] < far:
            raise ApiError("این بازه با یک بازه‌ی دیگر حضور هم‌پوشانی دارد")
        if end is None and r["ended_at"] is None:
            raise ApiError("هم‌اکنون یک ورود بدون خروج دارید")
    return start, end


def presence_add(db: Db, user: dict, data: dict):
    uid = user["id"]
    db.lock_user(uid)
    gdate = requested_day(data["date"]) if "date" in data else today_local()
    if gdate > today_local():
        raise ApiError("ثبت حضور برای روز آینده مجاز نیست")
    start, end = presence_window(db, uid, data, gdate)
    db.execute("INSERT INTO presence_segments (user_id, started_at, ended_at) VALUES (?, ?, ?)", (uid, start, end))
    db.commit()
    return presence_state(db, uid)


def presence_update(seg_id: int, db: Db, user: dict, data: dict):
    uid = user["id"]
    db.lock_user(uid)
    row = db.execute("SELECT * FROM presence_segments WHERE id = ? AND user_id = ?", (seg_id, uid)).fetchone()
    if not row:
        not_found()
    start, end = presence_window(db, uid, data, row["started_at"].date(), current_id=seg_id)
    db.execute("UPDATE presence_segments SET started_at = ?, ended_at = ? WHERE id = ?", (start, end, seg_id))
    db.commit()
    return presence_state(db, uid)


def presence_delete(seg_id: int, db: Db, user: dict):
    uid = user["id"]
    db.lock_user(uid)
    db.execute("DELETE FROM presence_segments WHERE id = ? AND user_id = ?", (seg_id, uid))
    db.commit()
    return presence_state(db, uid)

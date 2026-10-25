"""Task time arithmetic, ported from the desktop app. Segments are naive Tehran wall-clock datetimes."""
from datetime import date, datetime, timedelta

from ..core.constants import MEETING_REPORT_TYPE
from ..core.errors import ApiError
from ..core.backup import fingerprint
from ..core.time import JALALI_MONTHS, now_local, parse_time, to_date, to_dt

# tasks joined with everything the UI shows: tag, the tag's company fields and the task's own report type
TASK_SELECT = (
    "SELECT tasks.*, tags.name AS tag_name, trt.name AS tag_report_type, tp.name AS tag_project, "
    "ts.name AS tag_story, tags.fill_weight AS tag_fill_weight, rt.name AS report_type "
    "FROM tasks LEFT JOIN tags ON tasks.tag_id = tags.id "
    "LEFT JOIN report_types trt ON tags.report_type_id = trt.id "
    "LEFT JOIN stories ts ON tags.story_id = ts.id LEFT JOIN projects tp ON ts.project_id = tp.id "
    "LEFT JOIN report_types rt ON tasks.report_type_id = rt.id"
)


def company_type(d):
    """Report type for the company's main system: chosen on the task, else meeting, else the tag's."""
    if d.get("report_type"):
        return d["report_type"]
    if d.get("meeting_with"):
        return MEETING_REPORT_TYPE
    return d.get("tag_report_type")


def task_revision(row):
    fields = ("id", "title", "jalali_year", "jalali_month", "jalali_day", "start_time", "end_time",
              "duration_minutes", "accumulated_minutes", "segment_started_at", "status", "tag_id",
              "adjust_minutes", "fill_minutes", "report_type_id", "planned_flag", "outside_company", "entered_main_system")
    return fingerprint({key: row.get(key) for key in fields})


def row_to_dict(row):
    d = dict(row)
    d["revision"] = task_revision(row)
    d["jalali_date_str"] = f"{d['jalali_year']}/{d['jalali_month']:02d}/{d['jalali_day']:02d}"
    d["month_name"] = JALALI_MONTHS[d["jalali_month"] - 1]
    d["company_type"] = company_type(d)
    d["company_project"] = d.get("tag_project")
    d["company_story"] = d.get("tag_story")
    return d


def get_task_row(db, uid, task_id):
    return db.execute(TASK_SELECT + " WHERE tasks.id = ? AND tasks.user_id = ?", (task_id, uid)).fetchone()


def get_own_task(db, uid, task_id):
    row = db.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, uid)).fetchone()
    if not row:
        raise ApiError("not found", 404)
    return row


def effective_minutes(row, now):
    """Minutes worked so far on this task: the final duration once done, or the
    accumulated pause time plus whatever has elapsed on the currently running segment."""
    if row["status"] == "done":
        return row["duration_minutes"] or 0
    minutes = row["accumulated_minutes"] or 0
    if row["status"] == "running" and row["segment_started_at"]:
        started = to_dt(row["segment_started_at"])
        minutes += max(0, (now - started).total_seconds() / 60)
    return minutes


def compute_duration(start_s, end_s):
    """Best-effort duration for manually edited start/end HH:MM pairs (assumes same-day,
    wrapping past midnight once)."""
    if not start_s or not end_s:
        return None
    today = date.today()
    diff = (datetime.combine(today, parse_time(end_s)) - datetime.combine(today, parse_time(start_s))
            ).total_seconds() / 60
    if diff < 0:
        diff += 24 * 60
    return round(diff, 1)


def open_segment(db, task_id, started_at):
    db.execute("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (?, ?, NULL)", (task_id, started_at))


def close_open_segment(db, task_id, ended_at):
    db.execute(
        """UPDATE task_segments SET ended_at = ? WHERE id = (
               SELECT id FROM task_segments WHERE task_id = ? AND ended_at IS NULL
               ORDER BY id DESC LIMIT 1
           )""",
        (ended_at, task_id),
    )


def window_dt(gdate, start_time, end_time):
    """Clock window of a task on a day as datetimes (an end before the start means the next day)."""
    day = to_date(gdate)
    a = datetime.combine(day, parse_time(start_time))
    b = datetime.combine(day, parse_time(end_time))
    if b < a:
        b += timedelta(days=1)
    return a, b


def parse_adjust(value):
    """Signed minutes the user wants to add (+) or remove (-) from a task's total. None = no change."""
    if value in (None, "", 0):
        return None
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        raise ApiError("مقدار تعدیل نامعتبر است")
    if minutes != minutes or abs(minutes) > 24 * 60 * 7:
        raise ApiError("مقدار تعدیل نامعتبر است")
    return round(minutes, 1) or None


def duration_from_segments(db, task_id, gdate, start_time, end_time, recorded, old_span, new_span, adjust=0):
    """Worked minutes of a task with pauses after its start/end were edited: the real work segments
    inside the new window, plus any stretch the window was widened beyond the first/last segment.
    Moving the end back to the real last stop therefore never removes work, and widening adds it."""
    segs = db.execute("SELECT started_at, ended_at FROM task_segments WHERE task_id = ? ORDER BY id", (task_id,)).fetchall()
    if any(r["ended_at"] is None for r in segs):
        return round(max(recorded + new_span - old_span, 0) or new_span, 1)
    win_s, win_e = window_dt(gdate, start_time, end_time)
    spans = [(r["started_at"], r["ended_at"]) for r in segs]
    if abs(sum((b - a).total_seconds() for a, b in spans) / 60 + adjust - recorded) > 1.5:
        # the segment history does not add up to the recorded total: fall back to adding the difference
        total = round(recorded + new_span - old_span, 1)
        return total if total > 0 else new_span
    inside = sum(max(0.0, (min(b, win_e) - max(a, win_s)).total_seconds()) for a, b in spans) / 60
    env_s, env_e = min(a for a, _ in spans), max(b for _, b in spans)
    extra = max(0.0, (env_s - win_s).total_seconds()) + max(0.0, (win_e - env_e).total_seconds())
    total = round(inside + extra / 60 + adjust, 1)
    return total if total > 0 else new_span


def assert_no_overlap(db, uid, start_dt, end_dt, exclude_id=None, live=False):
    """Two tasks of one user may not be worked on at the same time. Looks at the real work segments
    of every other task (pauses are free time). `live` = the new work is open-ended, so any task that
    is running right now is a conflict. Overlaps shorter than a minute are rounding noise
    (a task stopped at 10:30:40 and the next one started at "10:30")."""
    now = now_local()
    rows = db.execute(
        """SELECT s.started_at, s.ended_at, t.title FROM task_segments s
           JOIN tasks t ON t.id = s.task_id
           WHERE t.user_id = ? AND (?::bigint IS NULL OR t.id != ?::bigint)
             AND s.started_at <= ? AND (s.ended_at IS NULL OR s.ended_at >= ?)""",
        (uid, exclude_id, exclude_id, max(end_dt, now), start_dt),
    ).fetchall()
    for r in rows:
        if r["ended_at"] is None:
            if live:
                raise ApiError(f"تسک «{r['title']}» هنوز در حال اجراست؛ اول آن را مکث یا پایان بدهید")
            seg_end = now
        else:
            seg_end = r["ended_at"]
        seg_start = r["started_at"]
        overlap = (min(seg_end, end_dt) - max(seg_start, start_dt)).total_seconds()
        if overlap > 60:
            raise ApiError(
                f"این بازه با تسک «{r['title']}» ({seg_start.strftime('%H:%M')} تا {seg_end.strftime('%H:%M')}) "
                "هم‌زمان می‌شود؛ دو کار را نمی‌شود هم‌زمان انجام داد")

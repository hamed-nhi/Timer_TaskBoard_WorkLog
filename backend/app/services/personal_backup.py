"""Immutable per-user snapshots and source-change-only Google Sheets synchronization.

The checkpoint is local, not a user-editable sheet hash. Editing a sheet without
editing the source never causes the next run to overwrite that row.
"""
import json
import os
import tempfile
import uuid
from pathlib import Path

from ..core.backup import backup_revision, canonical_json, fingerprint, sheet_id
from ..core.errors import ApiError
from .settings import my_backup, sheet_reserved
from .timecalc import TASK_SELECT, row_to_dict
from .reports import build_workbook

HEADERS = ["شناسه تسک", "نسخه منبع", "تاریخ شمسی", "شرح فعالیت", "وضعیت", "شروع", "پایان",
           "دقیقه ثبت‌شده", "دقیقه تکمیلی", "تگ", "نوع گزارش", "پروژه", "استوری", "پلن شده", "خارج از شرکت"]


def atomic_file(path, content, *, immutable=False):
    """Publish complete files only. Immutable destinations are never replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temp, path)
            except FileExistsError:
                pass
        else:
            os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def snapshot(root, uid, data, rows):
    revision = backup_revision(data)
    folder = Path(root) / f"user-{int(uid)}" / "versions"
    target = folder / f"{revision}.json"
    created = not target.exists()
    if created:
        atomic_file(target, canonical_json(data).encode("utf-8"), immutable=True)
    else:
        if backup_revision(json.loads(target.read_text(encoding="utf-8"))) != revision:
            raise ApiError("نسخه پشتیبان آسیب دیده؛ فایل موجود بازنویسی نشد")
    excel = folder / f"{revision}.xlsx"
    if not excel.exists():
        atomic_file(excel, build_workbook(rows).getvalue(), immutable=True)
    return {"revision": revision, "created": created}


def task_values(row):
    d = row_to_dict(row)
    return [str(row["id"]), fingerprint(row), d["jalali_date_str"], row["title"], row["status"],
            row["start_time"] or "", row["end_time"] or "",
            row["duration_minutes"] if row["duration_minutes"] is not None else "",
            row["fill_minutes"] or 0, row["tag_name"] or "", d["company_type"] or "",
            d["company_project"] or "", d["company_story"] or "",
            bool(row["planned_flag"]), bool(row["outside_company"])]


def sync_sheet(gateway, rows, owner, checkpoint):
    """One account owns one workbook. Updates are driven by persisted source values."""
    checkpoint = Path(checkpoint)
    state = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else None
    if state is not None and state.get("owner") != owner:
        raise ApiError("مالک checkpoint متفاوت است؛ همگام‌سازی متوقف شد")
    created = gateway.ensure_owner(owner, HEADERS)
    if not created and state is None:
        raise ApiError("checkpoint این شیت موجود نیست؛ برای حفظ داده‌ها همگام‌سازی متوقف شد")
    if state is None:
        state = {"owner": owner, "tasks": {}}
        atomic_file(checkpoint, canonical_json(state).encode("utf-8"))
    existing = gateway.read_rows()
    if not existing or existing[0] != HEADERS:
        raise ApiError("ستون‌های شیت تغییر کرده؛ همگام‌سازی متوقف شد")
    positions = {}
    for pos, values in enumerate(existing[1:], start=2):
        if not values or not str(values[0]):
            continue
        key = str(values[0])
        if key in positions:
            raise ApiError("شناسه تکراری در شیت؛ همگام‌سازی متوقف شد")
        positions[key] = (pos, values)
    current = {str(row["id"]): task_values(row) for row in rows}
    previous = state["tasks"]
    updates = []
    next_row = len(existing) + 1
    new_state = dict(previous)
    for key, values in current.items():
        revision = values[1]
        if previous.get(key) == revision:
            continue  # Never repair or overwrite sheet edits when the source is unchanged.
        found = positions.get(key)
        if found:
            pos, remote = found
            if key not in previous and (len(remote) < 2 or remote[1] != revision):
                raise ApiError("ردیف ناشناخته در شیت؛ بازنویسی نشد")
            if len(remote) < 2 or remote[1] != revision:
                updates.append({"range": f"'TimeLog'!A{pos}:O{pos}", "values": [values]})
        elif key in previous:
            raise ApiError("ردیف قبلی از شیت حذف شده؛ بازنویسی نشد")
        else:
            updates.append({"range": f"'TimeLog'!A{next_row}:O{next_row}", "values": [values]})
            next_row += 1
        new_state[key] = revision
    # Source deletions retain the old backup row; only mark it deleted once.
    for key in previous.keys() - current.keys():
        revision = fingerprint({"id": key, "deleted": True})
        if previous[key] == revision:
            continue
        if key not in positions:
            raise ApiError("ردیف قبلی از شیت حذف شده؛ بازنویسی نشد")
        pos, _ = positions[key]
        updates.extend([{"range": f"'TimeLog'!B{pos}", "values": [[revision]]},
                        {"range": f"'TimeLog'!E{pos}", "values": [["deleted"]]}])
        new_state[key] = revision
    if updates:
        gateway.write(updates, max(next_row - 1, len(existing)))
    if new_state != previous:
        atomic_file(checkpoint, canonical_json({"owner": owner, "tasks": new_state}).encode("utf-8"))
    return len(updates)


def backup_user(db, user, root, gateway_factory=None):
    uid = user["id"]
    data = my_backup(db, user)
    rows = db.execute(TASK_SELECT + " WHERE tasks.user_id = ? ORDER BY tasks.id", (uid,)).fetchall()
    result = snapshot(root, uid, data, rows)
    result["sheet_updates"] = None
    link = next((r["value"] for r in data["settings"] if r["key"] == "google_sheet_url"), "")
    if link and gateway_factory:
        sid = sheet_id(link)
        # Reject legacy duplicates too, before sending any data externally.
        if sheet_reserved(db, uid, sid):
            raise ApiError("شیت مشترک بین چند حساب مجاز نیست")
        instance = Path(root) / ".instance-id"
        atomic_file(instance, str(uuid.uuid4()).encode("ascii"), immutable=True)
        owner = f"timelog:{instance.read_text(encoding='ascii')}:{uid}"
        result["sheet_updates"] = sync_sheet(gateway_factory(sid), rows, owner,
                                               Path(root) / f"user-{uid}" / f"sheet-{sid}.json")
    return result

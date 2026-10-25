"""Backup invariants against real files and a stateful fake Sheets transport."""
import copy
import json
import re

import pytest

from app.core.backup import backup_revision, fingerprint, sheet_id
from app.core.errors import ApiError
from app.services.personal_backup import HEADERS, snapshot, sync_sheet


def row(id=1, title="source"):
    return dict(id=id, title=title, jalali_year=1405, jalali_month=8, jalali_day=3, status="done",
                start_time="09:00", end_time="10:00", duration_minutes=60, fill_minutes=0,
                tag_name="tag", planned_flag=False, outside_company=False)


class Sheet:
    def __init__(self):
        self.owner = None
        self.rows = []
        self.writes = []
        self.fail = False

    def ensure_owner(self, owner, headers):
        if self.owner and owner != self.owner:
            raise ApiError("wrong owner")
        if self.owner:
            return False
        self.owner = owner
        self.rows = [list(headers)]
        return True

    def read_rows(self):
        return copy.deepcopy(self.rows)

    def write(self, updates, last_row):
        if self.fail:
            raise RuntimeError("network down")
        self.writes.extend(copy.deepcopy(updates))
        for update in updates:
            match = re.search(r"!([A-Z]+)([0-9]+)", update["range"])
            col = ord(match[1]) - ord("A")
            pos = int(match[2]) - 1
            while len(self.rows) <= pos:
                self.rows.append([])
            while len(self.rows[pos]) < col + len(update["values"][0]):
                self.rows[pos].append("")
            self.rows[pos][col:col + len(update["values"][0])] = update["values"][0]


def test_files_are_immutable_and_clock_is_not_a_source_change(tmp_path):
    payload = {"exported_at": "first", "tasks": [row()]}
    first = snapshot(tmp_path, 1, payload, [row()])
    paths = list(tmp_path.rglob("*.json")) + list(tmp_path.rglob("*.xlsx"))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    payload["exported_at"] = "tomorrow"
    assert snapshot(tmp_path, 1, payload, [row()]) == {"revision": first["revision"], "created": False}
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    payload["tasks"][0]["title"] = "edited"
    assert snapshot(tmp_path, 1, payload, [row(title="edited")])["created"]
    assert len(list(tmp_path.rglob("*.json"))) == 2
    assert len(list(tmp_path.rglob("*.xlsx"))) == 2
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    snapshot(tmp_path, 2, payload, [row(title="edited")])
    assert (tmp_path / "user-2" / "versions").exists()


def test_corrupt_existing_snapshot_is_not_silently_replaced(tmp_path):
    data = {"tasks": [row()]}
    snapshot(tmp_path, 1, data, [row()])
    path = next(tmp_path.rglob("*.json"))
    path.write_text('{"tasks": []}')
    with pytest.raises(ApiError):
        snapshot(tmp_path, 1, data, [row()])
    assert json.loads(path.read_text()) == {"tasks": []}


def test_sync_updates_only_changed_source_and_preserves_sheet_edits(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    assert sync_sheet(sheet, [row(), row(2, "other")], "alice", checkpoint) == 2
    sheet.writes.clear()
    sheet.rows[1][3] = "manually edited sheet title"
    sheet.rows[1][1] = "manually edited hash"
    assert sync_sheet(sheet, [row(), row(2, "other")], "alice", checkpoint) == 0
    assert sheet.rows[1][3] == "manually edited sheet title"
    assert not sheet.writes
    assert sync_sheet(sheet, [row(title="source edited"), row(2, "other")], "alice", checkpoint) == 1
    assert sheet.rows[1][3] == "source edited"
    assert sheet.writes[0]["range"] == "'TimeLog'!A2:O2"
    sheet.writes.clear()
    assert sync_sheet(sheet, [row(title="source edited"), row(2, "other"), row(3, "new")], "alice", checkpoint) == 1
    assert sheet.writes[0]["range"] == "'TimeLog'!A4:O4"


def test_source_deletion_keeps_history_and_marks_once(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    sync_sheet(sheet, [row()], "alice", checkpoint)
    assert sync_sheet(sheet, [], "alice", checkpoint) == 2
    assert sheet.rows[1][3] == "source" and sheet.rows[1][4] == "deleted"
    assert sync_sheet(sheet, [], "alice", checkpoint) == 0


def test_failure_never_advances_checkpoint(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    sync_sheet(sheet, [row()], "alice", checkpoint)
    previous = checkpoint.read_bytes()
    sheet.fail = True
    with pytest.raises(RuntimeError):
        sync_sheet(sheet, [row(title="edited")], "alice", checkpoint)
    assert checkpoint.read_bytes() == previous
    sheet.fail = False
    assert sync_sheet(sheet, [row(title="edited")], "alice", checkpoint) == 1
    assert sync_sheet(sheet, [row(title="edited")], "alice", checkpoint) == 0


def test_foreign_owner_or_lost_checkpoint_never_overwrites(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    sync_sheet(sheet, [row()], "alice", checkpoint)
    before = copy.deepcopy(sheet.rows)
    with pytest.raises(ApiError):
        sync_sheet(sheet, [row(title="bob")], "bob", tmp_path / "bob.json")
    checkpoint.unlink()
    with pytest.raises(ApiError):
        sync_sheet(sheet, [row(title="new")], "alice", checkpoint)
    assert sheet.rows == before


def test_moved_rows_follow_id_not_position_and_extra_notes_survive(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    sync_sheet(sheet, [row(), row(2, "second")], "alice", checkpoint)
    sheet.rows[1], sheet.rows[2] = sheet.rows[2], sheet.rows[1]
    sheet.rows[2].append("personal note outside managed columns")
    sync_sheet(sheet, [row(title="changed"), row(2, "second")], "alice", checkpoint)
    assert sheet.rows[2][3] == "changed"
    assert sheet.rows[2][15] == "personal note outside managed columns"
    assert sheet.rows[1][3] == "second"


def test_duplicate_ids_and_missing_rows_fail_closed(tmp_path):
    sheet, checkpoint = Sheet(), tmp_path / "state.json"
    sync_sheet(sheet, [row()], "alice", checkpoint)
    sheet.rows.append(copy.deepcopy(sheet.rows[1]))
    with pytest.raises(ApiError):
        sync_sheet(sheet, [row(title="edited")], "alice", checkpoint)
    sheet.rows = [HEADERS]
    with pytest.raises(ApiError):
        sync_sheet(sheet, [row(title="edited")], "alice", checkpoint)


@pytest.mark.parametrize("url", ["https://docs.google.com.evil/spreadsheets/d/abc", "http://docs.google.com/spreadsheets/d/abc",
                                 "https://docs.google.com@evil/spreadsheets/d/abc", "https://docs.google.com/spreadsheets/",
                                 "https://docs.google.com/spreadsheets/d/../edit"])
def test_sheet_url_rejects_invalid_or_foreign_hosts(url):
    with pytest.raises(ApiError):
        sheet_id(url)


def test_sheet_ids_and_source_hashes_are_stable():
    assert sheet_id("https://docs.google.com/spreadsheets/d/abc_123/edit?gid=0#gid=1") == "abc_123"
    assert backup_revision({"exported_at": "a", "tasks": []}) == backup_revision({"exported_at": "b", "tasks": []})
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})

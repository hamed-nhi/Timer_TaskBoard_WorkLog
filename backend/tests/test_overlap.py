"""Two tasks of one user can never be worked on at the same time (new work only; old data is not touched)."""
from datetime import datetime

import pytest

from conftest import sql

pytestmark = pytest.mark.strict
DAY = {"jalali_year": 1405, "jalali_month": 7, "jalali_day": 3}       # 2026-09-25


def manual(client, start, end, title="کار"):
    return client.post("/api/tasks", json={"title": title, "start_time": start, "end_time": end, **DAY})


def test_overlapping_manual_entry_is_refused(client):
    assert manual(client, "09:00", "10:00", "الف").status_code == 201
    res = manual(client, "09:50", "10:30", "ب")
    assert res.status_code == 400 and "الف" in res.get_json()["error"]
    assert len(client.get("/api/tasks?year=1405&month=7&day=3").get_json()) == 1


def test_back_to_back_tasks_are_fine(client):
    assert manual(client, "09:00", "10:00").status_code == 201
    assert manual(client, "10:00", "11:00").status_code == 201
    assert manual(client, "08:00", "09:00").status_code == 201


def test_starting_a_task_while_another_runs_is_refused(client):
    assert client.post("/api/tasks", json={"title": "اول"}).status_code == 201
    second = client.post("/api/tasks", json={"title": "دوم"})
    assert second.status_code == 400 and "اول" in second.get_json()["error"]
    assert client.post("/api/tasks", json={"title": "سوم"}).status_code == 400


def test_after_pause_or_stop_a_new_task_can_start(client):
    a = client.post("/api/tasks", json={"title": "اول"}).get_json()
    client.post(f"/api/tasks/{a['id']}/pause")
    b = client.post("/api/tasks", json={"title": "دوم"})
    assert b.status_code == 201                         # a paused task does not block
    res = client.post(f"/api/tasks/{a['id']}/resume")   # but two running at once would
    assert res.status_code == 400 and "دوم" in res.get_json()["error"]
    client.post(f"/api/tasks/{b.get_json()['id']}/stop")
    assert client.post(f"/api/tasks/{a['id']}/resume").status_code == 200


def test_reopen_and_planned_start_are_blocked_while_something_runs(client):
    a = client.post("/api/tasks", json={"title": "اول"}).get_json()
    client.post(f"/api/tasks/{a['id']}/stop")
    assert client.post("/api/tasks", json={"title": "دوم"}).status_code == 201
    assert client.post(f"/api/tasks/{a['id']}/reopen").status_code == 400
    p = client.post("/api/planned", json={"title": "برنامه"}).get_json()
    assert client.post(f"/api/planned/{p['id']}/start").status_code == 400
    assert any(x["id"] == p["id"] for x in client.get("/api/planned").get_json())      # not lost


def test_editing_times_into_another_task_is_refused_but_title_edits_are_not(client):
    a = manual(client, "09:00", "10:00", "الف").get_json()
    b = manual(client, "10:00", "11:00", "ب").get_json()
    assert client.put(f"/api/tasks/{b['id']}", json={"start_time": "09:30"}).status_code == 400
    ok = client.put(f"/api/tasks/{b['id']}", json={"title": "ب۲"})
    assert ok.status_code == 200 and ok.get_json()["start_time"] == "10:00"
    assert client.put(f"/api/tasks/{a['id']}", json={"end_time": "10:40"}).status_code == 400
    assert client.put(f"/api/tasks/{a['id']}", json={"end_time": "10:00"}).status_code == 200


def test_old_overlapping_data_still_opens_and_saves_a_title(client):
    manual(client, "09:00", "10:00", "الف")
    b = manual(client, "10:00", "11:00", "ب").get_json()
    sql("UPDATE tasks SET start_time='09:30' WHERE id=:i", i=b["id"])
    sql("UPDATE task_segments SET started_at = started_at - interval '30 minutes' WHERE task_id=:i", i=b["id"])
    res = client.put(f"/api/tasks/{b['id']}", json={"title": "تغییر نام"})
    assert res.status_code == 200 and res.get_json()["start_time"] == "09:30"


def test_pauses_leave_room_for_other_work(client):
    a = manual(client, "09:00", "12:00", "الف").get_json()
    sql("UPDATE task_segments SET ended_at = :e WHERE task_id=:i", e=datetime(2026, 9, 25, 10, 0), i=a["id"])
    sql("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (:i, :a, :b)", i=a["id"],
        a=datetime(2026, 9, 25, 11, 0), b=datetime(2026, 9, 25, 12, 0))
    assert manual(client, "10:10", "10:50", "وسط").status_code == 201

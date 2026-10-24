"""Presence at the company: manual check-in, lunch out/back, leaving; independent of tasks."""
from datetime import datetime

from conftest import sql
from app.timeutil import today_local


def add_presence(start, end, day=None):
    day = day or today_local()
    sql("INSERT INTO presence_segments (user_id, started_at, ended_at) VALUES "
        "((SELECT id FROM users ORDER BY id LIMIT 1), :s, :e)",
        s=datetime.fromisoformat(f"{day}T{start}:00"), e=datetime.fromisoformat(f"{day}T{end}:00") if end else None)


def test_starts_empty(client):
    p = client.get("/api/presence").get_json()
    assert p["status"] == "none" and p["segments"] == [] and p["total_minutes"] == 0 and p["needs_checkin"] is False


def test_check_in_out_back(client):
    assert client.post("/api/presence/start").get_json()["status"] == "in"
    assert len(client.post("/api/presence/start").get_json()["segments"]) == 1       # no second open stretch
    assert client.post("/api/presence/pause").get_json()["status"] == "break"
    p = client.post("/api/presence/start").get_json()
    assert p["status"] == "in" and len(p["segments"]) == 2


def test_finish_day_is_final_until_the_button_is_pressed(client):
    client.post("/api/presence/start")
    assert client.post("/api/presence/finish").get_json()["status"] == "done"
    assert client.get("/api/presence").get_json()["status"] == "done"
    assert client.post("/api/presence/start").get_json()["status"] == "in"


def test_there_is_no_automatic_check_in(client):
    """Starting a task or opening the page never checks you in on the web."""
    client.post("/api/tasks", json={"title": "کار"})
    assert client.get("/api/presence").get_json()["status"] == "none"
    assert client.post("/api/presence/auto").status_code in (404, 405)


def test_needs_checkin_reminder(client):
    assert client.get("/api/presence").get_json()["needs_checkin"] is False
    t = client.post("/api/tasks", json={"title": "کار"}).get_json()
    assert client.get("/api/presence").get_json()["needs_checkin"] is True        # task running, not checked in
    client.post("/api/presence/start")
    assert client.get("/api/presence").get_json()["needs_checkin"] is False
    client.post("/api/presence/pause")
    assert client.get("/api/presence").get_json()["needs_checkin"] is True        # left for lunch, task still running
    client.post(f"/api/tasks/{t['id']}/stop")
    assert client.get("/api/presence").get_json()["needs_checkin"] is False


def test_edit_add_delete_and_validation(client):
    client.post("/api/presence/start")
    client.post("/api/presence/pause")
    seg = client.get("/api/presence").get_json()["segments"][0]
    ok = client.put(f"/api/presence/{seg['id']}", json={"start_time": "08:00", "end_time": "12:00"})
    assert ok.status_code == 200 and ok.get_json()["total_minutes"] == 240
    assert client.put(f"/api/presence/{seg['id']}", json={"start_time": "12:00", "end_time": "08:00"}).status_code == 400
    assert client.post("/api/presence", json={"start_time": "11:00", "end_time": "13:00"}).status_code == 400   # overlaps
    assert client.post("/api/presence", json={"start_time": "12:30", "end_time": "17:00"}).status_code == 201
    assert client.get("/api/presence").get_json()["total_minutes"] == 240 + 270
    assert client.delete(f"/api/presence/{seg['id']}").get_json()["total_minutes"] == 270


def test_task_minutes_are_reported_and_tasks_untouched(client):
    client.post("/api/presence/start")
    client.post("/api/tasks", json={"title": "کار", "start_time": "09:00", "end_time": "10:30"})
    assert client.get("/api/presence").get_json()["task_minutes"] >= 90
    t = client.get("/api/tasks").get_json()[0]
    client.post("/api/presence/pause")
    assert client.get("/api/tasks").get_json()[0]["duration_minutes"] == t["duration_minutes"]


def test_running_and_paused_task_names_are_exposed(client):
    t = client.post("/api/tasks", json={"title": "در حال اجرا"}).get_json()
    p = client.get("/api/presence").get_json()
    assert p["running_task"] == "در حال اجرا" and p["running_task_id"] == t["id"]
    client.post(f"/api/tasks/{t['id']}/pause")
    p = client.get("/api/presence").get_json()
    assert p["running_task"] is None and p["paused_task"] == "در حال اجرا"


def test_forgotten_checkout_from_an_earlier_day_is_closed_at_midnight(client):
    sql("INSERT INTO presence_segments (user_id, started_at, ended_at) VALUES ((SELECT id FROM users), '2020-01-01 08:00', NULL)")
    assert client.get("/api/presence").get_json()["status"] == "none"       # not today's
    assert client.post("/api/presence/start").get_json()["status"] == "in"
    assert str(sql("SELECT ended_at FROM presence_segments WHERE started_at < '2021-01-01'")[0]["ended_at"]).startswith(
        "2020-01-01 23:59")


def test_first_task_start_is_reported(client):
    client.post("/api/tasks", json={"title": "کار", "start_time": "00:05", "end_time": "00:25"})
    assert client.get("/api/presence").get_json()["first_task_start"] == "00:05"


def test_history_lists_only_days_with_presence(client):
    assert client.get("/api/presence/history").get_json() == []
    add_presence("08:00", "12:00", "2026-10-10")
    add_presence("13:00", "17:00", "2026-10-10")
    h = client.get("/api/presence/history?days=4000").get_json()
    assert len(h) == 1 and h[0]["presence_minutes"] == 480 and h[0]["first"] == "08:00" and h[0]["last"] == "17:00"
    assert h[0]["gap_minutes"] == 480


def test_leave_reason_is_stored(client):
    client.post("/api/presence/start")
    p = client.post("/api/presence/pause", json={"note": "کار بیرون از شرکت"}).get_json()
    assert p["segments"][0]["note"] == "کار بیرون از شرکت" and p["status"] == "break"
    client.post("/api/presence/start")
    assert client.post("/api/presence/pause").status_code == 200            # no body is fine


def test_past_day_segment_needs_an_end(client):
    seg_day = "2026-10-10"
    add_presence("08:00", "12:00", seg_day)
    sid = sql("SELECT id FROM presence_segments")[0]["id"]
    assert client.put(f"/api/presence/{sid}", json={"start_time": "08:00"}).status_code == 400

"""Past-day warnings, missing attendance, source fixes, midnight and account isolation."""
from datetime import datetime, timedelta

import pytest

from app.core.time import g2j, today_local
from app.services import presence
from tests.support import Client, sql


def task(client, day, start="09:00", end="11:00"):
    j = g2j(day)
    result = client.post("/api/tasks", json={"title": "alert source", "jalali_year": j.year,
                         "jalali_month": j.month, "jalali_day": j.day, "start_time": start, "end_time": end})
    assert result.status_code == 201, result.text
    return result.get_json()


def attend(client, day, start="09:00", end="10:00"):
    return client.post("/api/presence", json={"date": day.isoformat(), "start_time": start, "end_time": end})


def alerts(client, day=None):
    return client.get("/api/presence/alerts" + (f"?date={day}" if day else "")).get_json()


def test_today_does_not_warn_until_tehran_midnight(alice, monkeypatch):
    day = today_local()
    task(alice, day)
    monkeypatch.setattr(presence, "now_local", lambda: datetime.combine(day, datetime.max.time()))
    assert alerts(alice) == {"days": [], "count": 0}
    monkeypatch.setattr(presence, "now_local", lambda: datetime.combine(day + timedelta(days=1), datetime.min.time()))
    result = alerts(alice)
    assert result["count"] == 1
    assert result["days"][0]["excess_minutes"] == 120
    assert result["days"][0]["presence_minutes"] == 0


def test_alerts_and_segment_ids_are_private_even_for_admin(alice, bob, admin):
    day = today_local() - timedelta(days=1)
    task(alice, day)
    assert attend(alice, day).status_code == 201
    result = alerts(alice)["days"][0]
    assert result["excess_minutes"] == 60 and len(result["segments"]) == 1
    assert alerts(bob) == alerts(admin) == {"days": [], "count": 0}
    before = sql("SELECT duration_minutes FROM tasks")
    assert alerts(alice)["days"][0] == result
    assert sql("SELECT duration_minutes FROM tasks") == before


def test_no_warning_when_equal_or_below_attendance(alice):
    day = today_local() - timedelta(days=1)
    task(alice, day, end="10:00")
    assert attend(alice, day).status_code == 201
    assert alerts(alice)["count"] == 0
    task(alice, day - timedelta(days=1), end="09:30")
    assert attend(alice, day - timedelta(days=1)).status_code == 201
    assert alerts(alice)["count"] == 0


def test_fill_is_included_and_original_time_is_untouched(alice):
    day = today_local() - timedelta(days=1)
    t = task(alice, day, end="10:30")
    sql("UPDATE tasks SET fill_minutes = 30 WHERE id = :id", id=t["id"])
    assert attend(alice, day, end="10:40").status_code == 201
    warning = alerts(alice)["days"][0]
    assert warning["task_minutes"] == 90 and warning["reported_minutes"] == 120
    assert warning["presence_minutes"] == 100 and warning["excess_minutes"] == 20
    assert sql("SELECT duration_minutes, fill_minutes FROM tasks")[0] == {"duration_minutes": 90, "fill_minutes": 30}


def test_past_day_can_be_fixed_by_adding_or_editing_real_attendance(alice):
    day = today_local() - timedelta(days=1)
    task(alice, day)
    assert alerts(alice)["count"] == 1
    assert attend(alice, day).status_code == 201
    warning = alerts(alice)["days"][0]
    assert warning["excess_minutes"] == 60
    segment = warning["segments"][0]
    assert alice.put(f"/api/presence/{segment['id']}", json={"start_time": "09:00", "end_time": "11:00"}).status_code == 200
    assert alerts(alice)["count"] == 0


def test_stale_running_task_is_capped_at_its_own_midnight(alice, monkeypatch):
    day = today_local() - timedelta(days=1)
    t = task(alice, day, start="23:00", end="23:30")
    sql("UPDATE tasks SET status = 'running', duration_minutes = NULL, accumulated_minutes = 30, "
        "segment_started_at = :start WHERE id = :id", start=datetime.combine(day, datetime.min.time()) + timedelta(hours=23), id=t["id"])
    first = alerts(alice)["days"][0]
    assert first["reported_minutes"] == 90
    monkeypatch.setattr(presence, "now_local", lambda: datetime.combine(day + timedelta(days=10), datetime.min.time()))
    assert alerts(alice)["days"][0]["reported_minutes"] == 90


def test_forgotten_old_attendance_is_capped_without_changing_source(alice):
    day = today_local() - timedelta(days=2)
    task(alice, day)
    uid = sql("SELECT id FROM users")[0]["id"]
    sql("INSERT INTO presence_segments (user_id, started_at) VALUES (:uid, :start)",
        uid=uid, start=datetime.combine(day, datetime.min.time()) + timedelta(hours=8))
    assert alerts(alice)["count"] == 0
    assert sql("SELECT ended_at FROM presence_segments")[0]["ended_at"] is None


@pytest.mark.parametrize("value", [123, [], {}, None, "bad", "2026-99-99"])
def test_invalid_backdated_attendance_is_rejected(alice, value):
    assert alice.post("/api/presence", json={"date": value, "start_time": "09:00", "end_time": "10:00"}).status_code == 400


def test_future_attendance_and_past_open_span_are_rejected(alice):
    day = today_local()
    assert attend(alice, day + timedelta(days=1)).status_code == 400
    assert attend(alice, day - timedelta(days=1), end=None).status_code == 400
    assert alice.get("/api/presence/alerts?date=bad").status_code == 400
    assert Client().get("/api/presence/alerts").status_code == 401

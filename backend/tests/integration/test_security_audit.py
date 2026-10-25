"""Active malformed-input, privilege, CSRF and private-export regression tests."""
import io
import json

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import fill
from app.core.time import today_local
from tests.support import Client, sql


@pytest.mark.parametrize("path,body", [
    ("/api/tasks", {"title": []}), ("/api/tasks", {"title": "x", "tag_id": {"id": 1}}),
    ("/api/tags", {"name": {"x": 1}}), ("/api/planned", {"title": "x", "jalali_year": []}),
    ("/api/catalog/projects", {"name": []}), ("/api/settings", {"daily_goal_minutes": "nan"}),
    ("/api/settings", {"weekly_goal_minutes": "inf"}), ("/api/presence", {"start_time": {}}),
    ("/api/fill", {"date": today_local().isoformat(), "items": [None]}),
    ("/api/fill", {"date": today_local().isoformat(), "items": [{"id": 1, "fill_minutes": "nan"}]}),
])
def test_bad_input_never_causes_500_or_creates_partial_data(alice, path, body):
    probe = TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 52000),
                       headers={"X-Requested-With": "timelog"})
    probe.cookies.set("tl_session", alice.http.cookies.get("tl_session"))
    response = probe.post(path, json=body)
    assert response.status_code in (400, 404, 409, 422), (path, response.status_code, response.text)
    assert sql("SELECT count(*) c FROM tasks")[0]["c"] == 0
    assert sql("SELECT count(*) c FROM planned_tasks")[0]["c"] == 0


def test_cross_origin_preflight_has_no_cors_permission_and_simple_writes_fail(alice):
    raw = TestClient(app, headers={"Origin": "https://attacker.example"})
    raw.cookies.set("tl_session", alice.http.cookies.get("tl_session"))
    response = raw.options("/api/tasks", headers={"Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "X-Requested-With"})
    assert "access-control-allow-origin" not in response.headers
    assert raw.post("/api/tasks", json={"title": "forged"}).status_code == 403


def test_self_supplied_admin_flag_cannot_elevate_role(alice):
    response = alice.post("/api/settings", json={"is_admin": True, "user_id": 999})
    assert response.status_code in (200, 400)
    assert alice.get("/api/me").get_json()["is_admin"] is False
    assert alice.get("/api/admin/users").status_code == 403


def test_administrator_cannot_read_or_edit_another_accounts_personal_records(alice, admin):
    t = alice.post("/api/tasks", json={"title": "PRIVATE-ALICE", "start_time": "03:00", "end_time": "04:00"}).get_json()
    for path in ("/api/tasks", "/api/me/backup", "/api/company-catalog", "/api/presence/alerts"):
        assert "PRIVATE-ALICE" not in admin.get(path).text
    assert admin.put(f"/api/tasks/{t['id']}", json={"title": "stolen"}).status_code == 404
    assert sql("SELECT title FROM tasks")[0]["title"] == "PRIVATE-ALICE"


def test_blocked_fill_cannot_be_saved_by_bypassing_ui(alice, monkeypatch):
    day = today_local()
    task = alice.post("/api/tasks", json={"title": "x", "start_time": "09:00", "end_time": "10:00"}).get_json()
    assert alice.post("/api/presence", json={"start_time": "08:00", "end_time": "11:00"}).status_code == 201
    monkeypatch.setattr(fill, "FILL_DAY_OFF", day.weekday())
    assert alice.get("/api/fill-suggestion").get_json()["blocked"]
    response = alice.post("/api/fill", json={"date": day.isoformat(), "items": [{"id": task["id"], "fill_minutes": 10}]})
    assert response.status_code == 400
    assert sql("SELECT fill_minutes, duration_minutes FROM tasks")[0] == {"fill_minutes": 0, "duration_minutes": 60}


def test_excel_user_text_is_never_executed_as_a_formula(alice):
    alice.post("/api/tasks", json={"title": '=HYPERLINK("https://attacker.example", "x")',
                                  "start_time": "03:00", "end_time": "04:00"})
    book = openpyxl.load_workbook(io.BytesIO(alice.get("/api/export").content))
    cell = next(iter(book))["B2"]
    assert cell.data_type == "s" and cell.value.startswith("=HYPERLINK")


def test_fill_limit_has_no_extra_one_minute_bypass(alice):
    day = today_local().isoformat()
    task = alice.post("/api/tasks", json={"title": "x", "start_time": "09:00", "end_time": "10:30"}).get_json()
    assert alice.post("/api/presence", json={"start_time": "08:00", "end_time": "09:40"}).status_code == 201
    response = alice.post("/api/fill", json={"date": day, "items": [{"id": task["id"], "fill_minutes": 5.1}]})
    assert response.status_code == 400
    assert sql("SELECT fill_minutes FROM tasks")[0]["fill_minutes"] == 0


def test_private_api_responses_are_not_cacheable(alice):
    for path in ("/api/me", "/api/tasks", "/api/me/backup", "/api/export"):
        assert "no-store" in alice.get(path).headers.get("cache-control", "")

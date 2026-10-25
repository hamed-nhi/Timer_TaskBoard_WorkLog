"""Cross-feature user journeys and transaction/concurrency acceptance."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io

import openpyxl
import pytest

from app.core.time import today_local
from tests.support import Client, sql

pytestmark = pytest.mark.strict


def task(client, title, start="09:00", end="10:00", **fields):
    response = client.post("/api/tasks", json={"title": title, "start_time": start, "end_time": end, **fields})
    assert response.status_code == 201, response.text
    return response.get_json()


def clone_client(client):
    result = Client()
    result.http.cookies.set("tl_session", client.http.cookies.get("tl_session"))
    return result


def test_daily_work_report_fill_export_and_rollback(alice, bob):
    kind = alice.post("/api/catalog/report-types", json={"name": "گزارش روزانه"}).get_json()["id"]
    project = alice.post("/api/catalog/projects", json={"name": "پروژه روزانه"}).get_json()["id"]
    story = alice.post(f"/api/catalog/projects/{project}/stories", json={"name": "تحویل"}).get_json()["id"]
    tag = alice.post("/api/tags", json={"name": "تحویل", "report_type_id": kind, "story_id": story}).get_json()["id"]
    first = task(alice, "کار اول", "09:00", "11:00", tag_id=tag)
    second = task(alice, "کار دوم", "11:00", "13:00", tag_id=tag)
    sql("INSERT INTO presence_segments (user_id,started_at,ended_at,kind) "
        "VALUES ((SELECT id FROM users WHERE username='alice'), :s, :e, 'end')",
        s=f"{today_local()} 08:00:00", e=f"{today_local()} 14:00:00")
    day = today_local().isoformat()
    suggestion = alice.get(f"/api/fill-suggestion?date={day}").get_json()
    assert not suggestion["blocked"] and suggestion["suggested_total"] > 0
    assert alice.post("/api/fill", json={"date": day, "items": [
        {"id": item["id"], "fill_minutes": item["suggested"]} for item in suggestion["items"]]}).status_code == 200
    rows = alice.get("/api/tasks").get_json()
    assert sum(row["duration_minutes"] for row in rows) == 240
    assert sum(row["fill_minutes"] for row in rows) > 0
    assert alice.post(f"/api/tasks/{first['id']}/entered", json={"entered": True}).status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(alice.get("/api/export").content))
    assert sum(sheet.max_row - 1 for sheet in workbook) == 2
    backup = alice.get("/api/me/backup").get_json()
    assert len(backup["tasks"]) == 2 and backup["catalog"]["projects"][0]["name"] == "پروژه روزانه"
    assert bob.get("/api/tasks").get_json() == []
    assert bob.get("/api/catalog").get_json() == {"types": [], "projects": []}
    result = alice.post("/api/fill/rollback", json={"date": day}).get_json()
    assert result["removed_minutes"] > 0
    assert [(r["id"], r["duration_minutes"], r["fill_minutes"]) for r in alice.get("/api/tasks").get_json()] == [
        (first["id"], 120, 0), (second["id"], 120, 0)]
    assert sql("SELECT kind FROM audit_log")[0]["kind"] == "fill_rollback"


def test_fill_batch_is_atomic_when_later_task_is_invalid(alice):
    current = task(alice, "اصل زمان")
    result = alice.post("/api/fill", json={"date": today_local().isoformat(), "items": [
        {"id": current["id"], "fill_minutes": 15}, {"id": 9999999, "fill_minutes": 10}]})
    assert result.status_code == 404
    row = sql("SELECT duration_minutes, fill_minutes FROM tasks")[0]
    assert row == {"duration_minutes": 60, "fill_minutes": 0}


def test_invalid_settings_change_is_atomic(alice):
    before = deepcopy(alice.get("/api/settings").get_json())
    result = alice.post("/api/settings", json={"daily_goal_minutes": 300, "google_sheet_url": "https://example.com"})
    assert result.status_code == 400
    assert alice.get("/api/settings").get_json() == before


def test_sql_and_html_looking_titles_are_stored_as_data(alice):
    title = """<img src=x onerror=alert(1)> '; DROP TABLE tasks; --"""
    created = task(alice, title)
    assert created["title"] == title
    assert alice.get("/api/tasks").get_json()[0]["title"] == title
    assert sql("SELECT count(*) c FROM users")[0]["c"] == 1


def test_parallel_start_allows_exactly_one_running_task(alice):
    clients = [clone_client(alice) for _ in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda c: c.post("/api/tasks", json={"title": "هم‌زمان"}), clients))
    assert sorted(r.status_code for r in responses) == [201, 400, 400, 400, 400, 400]
    assert sql("SELECT count(*) c FROM tasks WHERE status='running'")[0]["c"] == 1
    assert sql("SELECT count(*) c FROM task_segments WHERE ended_at IS NULL")[0]["c"] == 1


def test_parallel_stop_is_idempotent(alice):
    running = alice.post("/api/tasks", json={"title": "پایان هم‌زمان"}).get_json()
    clients = [clone_client(alice) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda c: c.post(f"/api/tasks/{running['id']}/stop"), clients))
    assert all(r.status_code == 200 for r in responses)
    assert len({(r.get_json()["end_time"], r.get_json()["duration_minutes"]) for r in responses}) == 1
    assert sql("SELECT count(*) c FROM task_segments WHERE ended_at IS NOT NULL")[0]["c"] == 1


def test_parallel_catalog_creation_has_one_winner(alice):
    clients = [clone_client(alice) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda c: c.post("/api/catalog/projects", json={"name": "یک نام"}), clients))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    assert len(alice.get("/api/catalog").get_json()["projects"]) == 1


def test_parallel_users_do_not_block_each_others_work(alice, bob):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda c: c.post("/api/tasks", json={"title": c.username}), [alice, bob]))
    assert [r.status_code for r in responses] == [201, 201]
    assert [t["title"] for t in alice.get("/api/tasks").get_json()] == ["alice"]
    assert [t["title"] for t in bob.get("/api/tasks").get_json()] == ["bob"]


@pytest.mark.parametrize("value", [123, [1], {"invalid": "date"}])
def test_fill_rejects_invalid_date_types_without_server_error(alice, value):
    from fastapi.testclient import TestClient
    from app.main import app
    probe = TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 51000),
                       headers={"X-Requested-With": "timelog"})
    probe.cookies.set("tl_session", alice.http.cookies.get("tl_session"))
    response = probe.post("/api/fill", json={"date": value, "items": []})
    assert response.status_code == 400

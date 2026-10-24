"""One user must never see or change the data of another user."""
import io
import json
from datetime import date

import openpyxl
import pytest

from tests.support import sql


@pytest.fixture()
def world(alice, bob):
    """alice owns one of everything."""
    tag = alice.post("/api/tags", json={"name": "تگ آلیس"}).get_json()
    task = alice.post("/api/tasks", json={"title": "کار آلیس", "tag_id": tag["id"], "start_time": "09:00",
                                          "end_time": "10:00"}).get_json()
    planned = alice.post("/api/planned", json={"title": "برنامه آلیس"}).get_json()
    alice.post("/api/presence/start")
    seg = alice.get("/api/presence").get_json()["segments"][0]
    return {"tag": tag["id"], "task": task["id"], "planned": planned["id"], "seg": seg["id"]}


def test_lists_are_empty_for_bob(world, bob):
    assert bob.get("/api/tasks").get_json() == []
    assert bob.get("/api/tags").get_json() == []
    assert bob.get("/api/planned").get_json() == []
    assert bob.get("/api/presence").get_json()["segments"] == []
    assert bob.get("/api/tasks/paused").get_json() == []
    d = bob.get("/api/dashboard").get_json()
    assert d["task_count"] == 0 and d["total_minutes"] == 0
    assert bob.get("/api/goal-progress").get_json()["today_minutes"] == 0
    assert bob.get("/api/entry-report").get_json() == []
    assert bob.get("/api/yesterday-titles").get_json() == []
    assert bob.get("/api/presence/history").get_json() == []


def test_bob_gets_404_for_alices_ids(world, bob):
    t, tag, p, seg = world["task"], world["tag"], world["planned"], world["seg"]
    for method, url, body in [
        ("put", f"/api/tasks/{t}", {"title": "x"}),
        ("post", f"/api/tasks/{t}/pause", None), ("post", f"/api/tasks/{t}/resume", None),
        ("post", f"/api/tasks/{t}/stop", None), ("post", f"/api/tasks/{t}/reopen", None),
        ("get", f"/api/tasks/{t}/segments", None), ("post", f"/api/tasks/{t}/entered", {"entered": True}),
        ("post", f"/api/tasks/{t}/company", {"outside_company": True}),
        ("put", f"/api/tags/{tag}", {"name": "x"}), ("delete", f"/api/tags/{tag}", None),
        ("put", f"/api/tags/{tag}/budget", {"hours": 5}), ("put", f"/api/tags/{tag}/company", {}),
        ("post", f"/api/tags/{tag}/merge", {"into": tag + 1000}),
        ("put", f"/api/planned/{p}", {"title": "x"}), ("post", f"/api/planned/{p}/start", None),
        ("put", f"/api/presence/{seg}", {"start_time": "08:00", "end_time": "09:00"}),
    ]:
        r = getattr(bob, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, url, r.status_code)
    # deleting somebody else's task is a silent no-op (like the desktop) and changes nothing
    bob.delete(f"/api/tasks/{t}")
    assert sql("SELECT title FROM tasks")[0]["title"] == "کار آلیس"
    assert sql("SELECT count(*) c FROM audit_log")[0]["c"] == 0
    assert sql("SELECT count(*) c FROM tags")[0]["c"] == 1


def test_bob_cannot_delete_alices_planned_or_presence(world, bob):
    bob.delete(f"/api/planned/{world['planned']}")
    bob.delete(f"/api/presence/{world['seg']}")
    assert sql("SELECT count(*) c FROM planned_tasks")[0]["c"] == 1
    assert sql("SELECT count(*) c FROM presence_segments")[0]["c"] == 1


def test_bob_cannot_attach_alices_tag(world, bob):
    assert bob.post("/api/tasks", json={"title": "x", "tag_id": world["tag"]}).status_code == 400
    assert bob.post("/api/planned", json={"title": "x", "tag_id": world["tag"]}).status_code == 400
    mine = bob.post("/api/tags", json={"name": "تگ بوب"}).get_json()
    assert bob.post(f"/api/tags/{mine['id']}/merge", json={"into": world["tag"]}).status_code == 404


def test_same_tag_name_for_two_users_is_two_tags(world, bob):
    b = bob.post("/api/tags", json={"name": "تگ آلیس"}).get_json()
    assert b["id"] != world["tag"]
    assert sql("SELECT count(*) c FROM tags")[0]["c"] == 2


def test_fill_cannot_touch_other_users_tasks(world, bob):
    r = bob.post("/api/fill", json={"date": date.today().isoformat(),
                                    "items": [{"id": world["task"], "fill_minutes": 5}]})
    assert r.status_code == 404
    assert sql("SELECT fill_minutes FROM tasks")[0]["fill_minutes"] == 0


def test_two_users_can_work_at_the_same_time(alice, bob):
    assert alice.post("/api/tasks", json={"title": "a"}).status_code == 201
    assert bob.post("/api/tasks", json={"title": "b"}).status_code == 201


def test_export_and_backup_hold_only_own_data(world, bob):
    bob.post("/api/tasks", json={"title": "کار بوب", "start_time": "09:00", "end_time": "09:30"})
    data = json.loads(bob.get("/api/me/backup").content)
    assert [t["title"] for t in data["tasks"]] == ["کار بوب"] and data["tags"] == []
    wb = openpyxl.load_workbook(io.BytesIO(bob.get("/api/export").content))
    titles = [row[1] for ws in wb for row in ws.iter_rows(min_row=2, values_only=True)]
    assert titles == ["کار بوب"]


def test_settings_are_per_user(alice, bob):
    alice.post("/api/settings", json={"daily_goal_minutes": 300})
    assert bob.get("/api/settings").get_json()["daily_goal_minutes"] == 480
    assert alice.get("/api/settings").get_json()["daily_goal_minutes"] == 300


def test_catalog_is_private(alice, bob, admin):
    assert alice.post("/api/catalog/report-types", json={"name": "گزارش فنی"}).get_json()["id"]
    assert [x["name"] for x in alice.get("/api/company-catalog").get_json()["types"] if x["id"]] == ["گزارش فنی"]
    for c in (bob, admin):
        assert [x["name"] for x in c.get("/api/company-catalog").get_json()["types"] if x["id"]] == []

"""Tags (budget, rename, delete, merge) and the planned-items backlog."""
import pytest

from tests.support import sql


def done(client, minutes, y, m, d, tag_id=None, title="کار"):
    """A finished task of exactly `minutes` minutes on a given Jalali day."""
    end_total = 8 * 60 + minutes
    payload = {"title": title, "start_time": "08:00", "end_time": f"{end_total // 60:02d}:{end_total % 60:02d}",
               "jalali_year": y, "jalali_month": m, "jalali_day": d}
    if tag_id:
        payload["tag_id"] = tag_id
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201, res.text
    return res.get_json()


def make_tag(client, name="پروژه"):
    return client.post("/api/tags", json={"name": name}).get_json()["id"]


def tag(client, tag_id):
    return next(t for t in client.get("/api/tags").get_json() if t["id"] == tag_id)


# ---- budget ----

def test_tags_without_budget_report_none(client):
    t = tag(client, make_tag(client))
    assert t["budget_minutes"] is None and t["spent_minutes"] is None and t["budget_percent"] is None


def test_budget_counts_all_history_by_default(client):
    tid = make_tag(client)
    done(client, 90, 1405, 6, 2, tag_id=tid)
    done(client, 30, 1405, 7, 3, tag_id=tid)
    assert client.put(f"/api/tags/{tid}/budget", json={"hours": 4, "from": "all"}).status_code == 200
    t = tag(client, tid)
    assert (t["budget_minutes"], t["spent_minutes"], t["budget_percent"]) == (240, 120, 50.0)


def test_other_tags_and_untagged_work_do_not_count(client):
    a, b = make_tag(client, "الف"), make_tag(client, "ب")
    done(client, 60, 1405, 7, 3, tag_id=a)
    done(client, 599, 1405, 7, 3, tag_id=b)
    done(client, 100, 1405, 7, 4)
    client.put(f"/api/tags/{a}/budget", json={"hours": 2})
    assert tag(client, a)["spent_minutes"] == 60


def test_from_today_ignores_older_work(client):
    tid = make_tag(client)
    done(client, 120, 1380, 1, 1, tag_id=tid)
    client.put(f"/api/tags/{tid}/budget", json={"hours": 5, "from": "today"})
    t = tag(client, tid)
    assert t["budget_since"] and t["spent_minutes"] == 0
    client.put(f"/api/tags/{tid}/budget", json={"hours": 6})
    assert tag(client, tid)["budget_since"] == t["budget_since"]          # only the number changed
    client.put(f"/api/tags/{tid}/budget", json={"hours": 6, "from": "all"})
    assert tag(client, tid)["spent_minutes"] == 120


def test_over_budget_percent_exceeds_100(client):
    tid = make_tag(client)
    done(client, 180, 1405, 7, 3, tag_id=tid)
    client.put(f"/api/tags/{tid}/budget", json={"hours": 2})
    assert tag(client, tid)["budget_percent"] == 150.0


def test_running_task_counts_live(client):
    tid = make_tag(client)
    assert client.post("/api/tasks", json={"title": "در حال انجام", "tag_id": tid}).status_code == 201
    client.put(f"/api/tags/{tid}/budget", json={"hours": 1})
    assert tag(client, tid)["spent_minutes"] >= 0


def test_clear_budget(client):
    tid = make_tag(client)
    client.put(f"/api/tags/{tid}/budget", json={"hours": 3})
    client.put(f"/api/tags/{tid}/budget", json={"hours": None})
    assert tag(client, tid)["budget_minutes"] is None


def test_invalid_budget_is_rejected_and_nothing_changes(client):
    tid = make_tag(client)
    client.put(f"/api/tags/{tid}/budget", json={"hours": 3})
    for bad in ("abc", -2, 10 ** 7):
        assert client.put(f"/api/tags/{tid}/budget", json={"hours": bad}).status_code == 400
    assert tag(client, tid)["budget_minutes"] == 180
    assert client.put("/api/tags/9999/budget", json={"hours": 3}).status_code == 404


def test_setting_a_budget_never_touches_tasks(client):
    tid = make_tag(client)
    done(client, 75, 1405, 7, 3, tag_id=tid)
    before = sql("SELECT * FROM tasks ORDER BY id")
    client.put(f"/api/tags/{tid}/budget", json={"hours": 9, "from": "today"})
    client.put(f"/api/tags/{tid}/budget", json={"hours": None})
    assert sql("SELECT * FROM tasks ORDER BY id") == before


def test_new_tag_can_start_with_a_budget(client):
    res = client.post("/api/tags", json={"name": "پروژه ۲۰۰", "budget_hours": 200})
    assert res.status_code == 201
    t = res.get_json()
    assert t["budget_minutes"] == 12000 and t["spent_minutes"] == 0 and t["budget_percent"] == 0


def test_new_tag_without_budget_and_invalid_budget(client):
    assert client.post("/api/tags", json={"name": "ساده"}).get_json()["budget_minutes"] is None
    assert client.post("/api/tags", json={"name": "ساده2", "budget_hours": ""}).get_json()["budget_minutes"] is None
    assert client.post("/api/tags", json={"name": "بد", "budget_hours": "x"}).status_code == 400
    assert client.post("/api/tags", json={"name": "بد", "budget_hours": -5}).status_code == 400
    assert not [t for t in client.get("/api/tags").get_json() if t["name"] == "بد"]


def test_creating_an_existing_tag_does_not_overwrite_its_budget(client):
    client.post("/api/tags", json={"name": "ثابت", "budget_hours": 10})
    assert client.post("/api/tags", json={"name": "ثابت", "budget_hours": 99}).get_json()["budget_minutes"] == 600


def test_progress_and_tag_summary(client):
    tid = client.post("/api/tags", json={"name": "طرح", "budget_hours": 10}).get_json()["id"]
    done(client, 60, 1405, 7, 3, tag_id=tid, title="طراحی")
    done(client, 120, 1405, 7, 4, tag_id=tid, title="پیاده‌سازی")
    s = client.get(f"/api/tag-summary?tag={tid}").get_json()
    assert s["budget"]["spent_minutes"] == 180 and s["budget"]["budget_percent"] == 30.0
    assert [r["title"] for r in s["recent"]] == ["پیاده‌سازی", "طراحی"]
    assert s["total_minutes"] == 180 and s["day_count"] == 2 and s["top_titles"][0]["title"] == "پیاده‌سازی"
    assert client.get("/api/tag-summary?tag=none").get_json()["budget"] is None
    assert client.get("/api/tag-summary?tag=999").status_code == 404
    assert client.get("/api/tag-summary?tag=abc").status_code == 400


# ---- rename / delete ----

def test_rename_and_duplicate_names(client):
    a, b = make_tag(client, "ي ك"), make_tag(client, "دیگر")
    assert client.put(f"/api/tags/{b}", json={"name": "ی ک"}).status_code == 409        # same after Arabic/Persian letters
    assert client.put(f"/api/tags/{b}", json={"name": "   "}).status_code == 400
    assert client.put(f"/api/tags/{b}", json={"name": "جدید"}).get_json()["name"] == "جدید"


def test_used_tag_cannot_be_deleted_unused_can(client):
    used, free = make_tag(client, "پرکاربرد"), make_tag(client, "آزاد")
    t = done(client, 10, 1405, 7, 1, used)
    assert client.delete(f"/api/tags/{used}").status_code == 409
    client.delete(f"/api/tasks/{t['id']}")
    assert client.delete(f"/api/tags/{used}").status_code == 409          # still referenced by the archive
    assert client.delete(f"/api/tags/{free}").status_code == 200


# ---- merge ----

def test_merge_moves_tasks_planned_and_archive_and_removes_the_source(client):
    a, b = make_tag(client, "ایران"), make_tag(client, "نامبر")
    t1 = done(client, 60, 1405, 7, 1, a)
    t2 = done(client, 30, 1405, 7, 2, b)
    t3 = done(client, 15, 1405, 7, 3, b)
    client.post("/api/planned", json={"title": "برنامه", "tag_id": b})
    client.delete(f"/api/tasks/{t3['id']}")
    res = client.post(f"/api/tags/{b}/merge", json={"into": a})
    assert res.status_code == 200 and res.get_json()["moved_tasks"] == 1 and res.get_json()["moved_planned"] == 1
    client.put(f"/api/tags/{a}", json={"name": "خرید و پشتیبانی اکانت"})
    names = [t["name"] for t in client.get("/api/tags").get_json()]
    assert "نامبر" not in names and "خرید و پشتیبانی اکانت" in names
    tasks = {t["id"]: t for t in client.get("/api/tasks").get_json()}
    assert tasks[t1["id"]]["tag_name"] == tasks[t2["id"]]["tag_name"] == "خرید و پشتیبانی اکانت"
    assert client.get("/api/planned").get_json()[0]["tag_name"] == "خرید و پشتیبانی اکانت"
    assert client.get("/api/dashboard?year=1405&month=7").get_json()["total_minutes"] == 90
    archived = sql("SELECT payload FROM audit_log WHERE kind='task_deleted'")[0]["payload"]
    assert archived["task"]["tag_id"] == a
    log = sql("SELECT payload FROM audit_log WHERE kind='tag_merge'")[0]["payload"]
    assert log["source"]["name"] == "نامبر" and log["task_ids"] == [t2["id"]]


def test_merge_never_loses_a_minute_or_a_task(client):
    a, b = make_tag(client, "الف"), make_tag(client, "ب")
    for i in range(1, 6):
        done(client, 10 * i, 1405, 7, i, a if i % 2 else b)
    before = client.get("/api/dashboard?year=1405").get_json()
    client.post(f"/api/tags/{b}/merge", json={"into": a})
    after = client.get("/api/dashboard?year=1405").get_json()
    assert (after["total_minutes"], after["task_count"]) == (before["total_minutes"], before["task_count"])
    assert len(after["by_tag"]) == 1 and after["by_tag"][0]["minutes"] == 150


def test_merge_validation_and_failed_merge_changes_nothing(client):
    a = make_tag(client, "الف")
    done(client, 10, 1405, 7, 1, a)
    assert client.post(f"/api/tags/{a}/merge", json={"into": a}).status_code == 400
    assert client.post(f"/api/tags/{a}/merge", json={"into": 99999}).status_code == 404
    assert client.post("/api/tags/99999/merge", json={"into": a}).status_code == 404
    assert client.post(f"/api/tags/{a}/merge", json={}).status_code == 400
    assert client.post(f"/api/tags/{a}/merge", json={"into": "x"}).status_code == 400
    assert client.get("/api/tasks").get_json()[0]["tag_name"] == "الف"


# ---- planned items ----

def create_planned(client, **overrides):
    return client.post("/api/planned", json={"title": "تحویل گزارش", **overrides})


def test_create_and_list_planned(client):
    data = create_planned(client, jalali_year=1405, jalali_month=8, jalali_day=10).get_json()
    assert data["title"] == "تحویل گزارش" and data["jalali_date_str"] == "1405/08/10"
    assert client.post("/api/planned", json={"title": "  "}).status_code == 400
    create_planned(client, title="دیرتر", jalali_year=1405, jalali_month=9, jalali_day=1)
    create_planned(client, title="زودتر", jalali_year=1405, jalali_month=7, jalali_day=5)
    assert [p["title"] for p in client.get("/api/planned").get_json()] == ["زودتر", "تحویل گزارش", "دیرتر"]


def test_delete_planned(client):
    pid = create_planned(client).get_json()["id"]
    assert client.delete(f"/api/planned/{pid}").get_json()["ok"] is True
    assert client.get("/api/planned").get_json() == []


def test_start_planned_creates_running_task_today_and_removes_it(client):
    pid = create_planned(client, title="کار برنامه‌ریزی‌شده", jalali_year=1405, jalali_month=9, jalali_day=15).get_json()["id"]
    today = client.get("/api/today").get_json()
    res = client.post(f"/api/planned/{pid}/start")
    assert res.status_code == 201
    task = res.get_json()
    assert task["title"] == "کار برنامه‌ریزی‌شده" and task["status"] == "running" and task["planned_flag"] is True
    assert (task["jalali_year"], task["jalali_month"], task["jalali_day"]) == (
        today["jalali_year"], today["jalali_month"], today["jalali_day"])
    assert client.get("/api/planned").get_json() == []
    assert client.post(f"/api/tasks/{task['id']}/stop").get_json()["status"] == "done"
    assert client.post("/api/planned/9999/start").status_code == 404


def test_update_planned(client):
    tid = make_tag(client)
    pid = create_planned(client, jalali_year=1405, jalali_month=7, jalali_day=5).get_json()["id"]
    data = client.put(f"/api/planned/{pid}", json={"title": "عنوان جدید", "jalali_year": 1405, "jalali_month": 7,
                                                   "jalali_day": 20, "tag_id": tid}).get_json()
    assert data["title"] == "عنوان جدید" and data["jalali_date_str"] == "1405/07/20" and data["tag_id"] == tid
    moved = client.put(f"/api/planned/{pid}", json={"jalali_year": 1405, "jalali_month": 7, "jalali_day": 6}).get_json()
    assert moved["title"] == "عنوان جدید" and moved["jalali_date_str"] == "1405/07/06"
    assert client.put("/api/planned/9999", json={"title": "x"}).status_code == 404


def test_planned_overdue_flag(client):
    assert create_planned(client, jalali_year=1300, jalali_month=1, jalali_day=1).get_json()["overdue"] is True
    assert create_planned(client, jalali_year=1450, jalali_month=1, jalali_day=1).get_json()["overdue"] is False

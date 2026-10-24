"""Company fields (report type / project / story) and the presence gap fill (report only)."""
from datetime import date, datetime

from conftest import sql
from app.routers import fill
from app.timeutil import today_jalali, today_local


def today_task(client, title, start, end, **extra):
    j = today_jalali()
    payload = {"title": title, "jalali_year": j.year, "jalali_month": j.month, "jalali_day": j.day,
               "start_time": start, "end_time": end}
    payload.update(extra)
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def add_presence(start, end):
    d = today_local()
    sql("INSERT INTO presence_segments (user_id, started_at, ended_at) VALUES ((SELECT id FROM users ORDER BY id LIMIT 1), :s, :e)",
        s=datetime.fromisoformat(f"{d}T{start}:00"), e=datetime.fromisoformat(f"{d}T{end}:00"))


def catalog(admin, types=("گزارش فنی", "جلسات"), project="پروژه‌ی هوش مصنوعی", stories=("اکانت‌ها", "تحقیق")):
    ids = {"types": {}, "stories": {}}
    for t in types:
        ids["types"][t] = admin.post("/api/admin/report-types", json={"name": t}).get_json()["id"]
    pid = admin.post("/api/admin/projects", json={"name": project}).get_json()["id"]
    for s in stories:
        ids["stories"][s] = admin.post(f"/api/admin/projects/{pid}/stories", json={"name": s}).get_json()["id"]
    return ids


def new_tag(client, name, **company):
    tag = client.post("/api/tags", json={"name": name}).get_json()
    if company:
        res = client.put(f"/api/tags/{tag['id']}/company", json=company)
        assert res.status_code == 200, res.get_json()
    return tag


def fill_for(client):
    return client.get(f"/api/fill-suggestion?date={date.today().isoformat()}").get_json()


def test_tag_carries_type_project_story_to_its_tasks(client, admin):
    ids = catalog(admin)
    tag = new_tag(client, "اکانت", report_type_id=ids["types"]["گزارش فنی"], story_id=ids["stories"]["اکانت‌ها"])
    t = today_task(client, "خرید اکانت", "09:00", "10:00", tag_id=tag["id"])
    assert (t["company_type"], t["company_project"], t["company_story"]) == ("گزارش فنی", "پروژه‌ی هوش مصنوعی", "اکانت‌ها")
    cat = client.get("/api/company-catalog").get_json()
    assert [x["name"] for x in cat["types"]] == ["گزارش فنی", "جلسات"]
    assert cat["projects"][0]["stories"][0]["name"] == "اکانت‌ها"
    assert client.get("/api/tags").get_json()[0]["story"] == "اکانت‌ها"


def test_unknown_catalog_ids_are_refused(client):
    tag = new_tag(client, "تگ")
    assert client.put(f"/api/tags/{tag['id']}/company", json={"report_type_id": 999}).status_code == 400
    assert client.put(f"/api/tags/{tag['id']}/company", json={"story_id": 999}).status_code == 400
    assert client.put(f"/api/tags/{tag['id']}/company", json={"fill_weight": 11}).status_code == 400


def test_task_type_override_and_ticks_never_touch_time(client, admin):
    ids = catalog(admin)
    tag = new_tag(client, "تیکتینگ", report_type_id=ids["types"]["گزارش فنی"])
    t = today_task(client, "تیکت", "09:00", "10:30", tag_id=tag["id"])
    d = client.post(f"/api/tasks/{t['id']}/company", json={"report_type_id": ids["types"]["جلسات"],
                                                           "outside_company": True, "planned_flag": True}).get_json()
    assert d["company_type"] == "جلسات" and d["outside_company"] is True and d["planned_flag"] is True
    assert d["duration_minutes"] == t["duration_minutes"] == 90
    assert client.post(f"/api/tasks/{t['id']}/company", json={"report_type_id": None}).get_json()["company_type"] == "گزارش فنی"


def test_task_marked_as_meeting_gets_no_fill(client, admin):
    ids = catalog(admin)
    add_presence("08:00", "12:00")
    tag = new_tag(client, "چت بات", report_type_id=ids["types"]["گزارش فنی"])
    t = today_task(client, "جلسه پیشرفت", "08:00", "10:00", tag_id=tag["id"])
    client.post(f"/api/tasks/{t['id']}/company", json={"report_type_id": ids["types"]["جلسات"]})
    item = fill_for(client)["items"][0]
    assert item["meeting"] and item["suggested"] == 0


def test_catalog_in_use_cannot_be_deleted(client, admin):
    ids = catalog(admin)
    new_tag(client, "تگ", report_type_id=ids["types"]["گزارش فنی"], story_id=ids["stories"]["تحقیق"])
    assert admin.delete(f"/api/admin/report-types/{ids['types']['گزارش فنی']}").status_code == 409
    assert admin.delete(f"/api/admin/stories/{ids['stories']['تحقیق']}").status_code == 409
    assert admin.delete(f"/api/admin/stories/{ids['stories']['اکانت‌ها']}").status_code == 200
    assert admin.post("/api/admin/report-types", json={"name": "گزارش فنی"}).status_code == 409      # duplicate


def test_catalog_import_is_idempotent(admin):
    data = {"types": ["الف", "ب"], "projects": {"پ۱": ["س۱", "س۲"]}}
    for _ in range(2):
        assert admin.post("/api/admin/catalog/import", json=data).status_code == 200
    cat = admin.get("/api/admin/catalog").get_json()
    assert [t["name"] for t in cat["types"]] == ["الف", "ب"]
    assert [s["name"] for s in cat["projects"][0]["stories"]] == ["س۱", "س۲"]


def test_started_planned_item_is_marked_planned(client):
    j = client.get("/api/today").get_json()
    p = client.post("/api/planned", json={"title": "برنامه", "jalali_year": j["jalali_year"],
                                          "jalali_month": j["jalali_month"], "jalali_day": j["jalali_day"]}).get_json()
    assert client.post(f"/api/planned/{p['id']}/start").get_json()["planned_flag"] is True


def test_fill_suggestion_reaches_target_by_weight_and_keeps_real_time(client):
    add_presence("08:00", "12:00")
    add_presence("12:30", "16:30")                              # 480 min at the company, lunch recorded
    heavy = new_tag(client, "سنگین", fill_weight=2)
    light = new_tag(client, "سبک")
    a = today_task(client, "الف", "08:00", "11:00", tag_id=heavy["id"])      # 180
    b = today_task(client, "ب", "11:00", "14:00", tag_id=light["id"])        # 180
    s = fill_for(client)
    assert s["percent"] == 95 and s["presence_minutes"] == 480 and s["task_minutes"] == 360
    assert s["needed_minutes"] == 96                            # 480 * 0.95 - 360
    by_id = {i["id"]: i for i in s["items"]}
    assert by_id[a["id"]]["suggested"] > by_id[b["id"]]["suggested"]
    assert all(i["suggested"] % 5 == 0 for i in s["items"]) and abs(s["suggested_total"] - 96) <= 5

    items = [{"id": i["id"], "fill_minutes": i["suggested"]} for i in s["items"]]
    assert client.post("/api/fill", json={"date": s["date"], "items": items}).status_code == 200
    rows = client.get("/api/tasks").get_json()
    assert {r["id"]: r["duration_minutes"] for r in rows} == {a["id"]: 180, b["id"]: 180}    # real time untouched
    assert sum(r["fill_minutes"] for r in rows) == s["suggested_total"]
    assert client.get("/api/presence").get_json()["fill_minutes"] == s["suggested_total"]
    client.post("/api/fill", json={"date": s["date"], "items": [{"id": i["id"], "fill_minutes": 0} for i in s["items"]]})
    assert sum(r["fill_minutes"] for r in client.get("/api/tasks").get_json()) == 0


def test_fill_caps_each_task_and_skips_meetings_and_zero_weight(client, admin):
    ids = catalog(admin)
    add_presence("08:00", "17:00")
    never = new_tag(client, "هرگز", fill_weight=0)
    meet = new_tag(client, "جلسه‌ها", report_type_id=ids["types"]["جلسات"])
    today_task(client, "صفر", "08:00", "09:00", tag_id=never["id"])
    today_task(client, "جلسه", "09:00", "10:00", tag_id=meet["id"])
    today_task(client, "کار", "10:00", "11:00")
    s = fill_for(client)
    by_title = {i["title"]: i for i in s["items"]}
    assert by_title["صفر"]["suggested"] == 0 and by_title["جلسه"]["suggested"] == 0
    assert by_title["کار"]["suggested"] == 30                   # capped at half of its own 60 minutes
    assert s["suggested_total"] < s["needed_minutes"]


def test_fill_percent_is_remembered_and_validated(client):
    add_presence("08:00", "16:00")
    t = today_task(client, "کار", "08:00", "14:00")
    d = date.today().isoformat()
    assert client.get(f"/api/fill-suggestion?date={d}&percent=30").status_code == 400
    client.post("/api/fill", json={"date": d, "items": [], "percent": 90})
    assert client.get(f"/api/fill-suggestion?date={d}").get_json()["percent"] == 90
    assert client.post("/api/fill", json={"date": d, "items": [{"id": t["id"], "fill_minutes": -5}]}).status_code == 400
    assert client.post("/api/fill", json={"date": "2000-01-01", "items": [{"id": t["id"], "fill_minutes": 5}]}).status_code == 404
    assert client.post("/api/fill", json={"date": "nope", "items": []}).status_code == 400


def test_no_presence_means_no_suggestion(client):
    today_task(client, "کار", "08:00", "10:00")
    s = fill_for(client)
    assert s["blocked"] and s["needed_minutes"] == 0 and s["items"][0]["suggested"] == 0


def test_presence_shorter_than_tasks_is_not_trusted(client):
    add_presence("09:00", "10:00")
    today_task(client, "کار", "08:00", "12:00")
    s = fill_for(client)
    assert s["blocked"] and s["suggested_total"] == 0 and s["warnings"]


def test_presence_over_eleven_hours_is_not_trusted(client):
    add_presence("06:00", "12:00")
    add_presence("12:30", "18:00")
    today_task(client, "کار", "08:00", "12:00")
    assert fill_for(client)["blocked"]


def test_unrecorded_lunch_is_taken_off(client):
    add_presence("08:00", "16:00")                              # one 8h stretch, no lunch out
    today_task(client, "کار", "08:00", "14:00")                 # 360
    s = fill_for(client)
    assert not s["blocked"] and s["usable_presence_minutes"] == 450
    assert s["needed_minutes"] == 450 * 0.95 - 360 and s["warnings"]


def test_friday_is_never_filled(client, monkeypatch):
    monkeypatch.setattr(fill, "FILL_DAY_OFF", date.today().weekday())
    add_presence("08:00", "12:00")
    today_task(client, "کار", "08:00", "10:00")
    assert fill_for(client)["blocked"]


def test_rollback_removes_fill_and_keeps_recorded_time(client):
    add_presence("08:00", "12:00")
    a = today_task(client, "کار", "08:00", "10:00")
    d = date.today().isoformat()
    client.post("/api/fill", json={"date": d, "items": [{"id": a["id"], "fill_minutes": 30}]})
    assert client.post("/api/fill/rollback", json={"date": d}).get_json()["removed_minutes"] == 30
    row = client.get("/api/tasks").get_json()[0]
    assert row["fill_minutes"] == 0 and row["duration_minutes"] == 120
    log = sql("SELECT payload FROM audit_log WHERE kind='fill_rollback'")[0]["payload"]
    assert log["fills"] == {str(a["id"]): 30.0}


def test_report_can_never_go_above_95_percent(client):
    add_presence("08:00", "12:00")                              # 240 min
    a = today_task(client, "کار", "08:00", "11:00")             # 180 -> at most 228 - 180 = 48
    d = date.today().isoformat()
    assert client.post("/api/fill", json={"date": d, "items": [{"id": a["id"], "fill_minutes": 60}]}).status_code == 400
    assert client.get("/api/tasks").get_json()[0]["fill_minutes"] == 0          # nothing saved
    assert client.post("/api/fill", json={"date": d, "items": [{"id": a["id"], "fill_minutes": 45}]}).status_code == 200
    assert client.get(f"/api/fill-suggestion?date={d}&percent=99").status_code == 400


def test_suggestion_is_fresh_even_after_an_earlier_fill(client):
    add_presence("08:00", "12:00")
    add_presence("12:30", "16:30")
    a = today_task(client, "الف", "08:00", "10:00")
    d = date.today().isoformat()
    client.post("/api/fill", json={"date": d, "items": [{"id": a["id"], "fill_minutes": 20}]})
    today_task(client, "ب", "10:00", "13:00")
    s = client.get(f"/api/fill-suggestion?date={d}").get_json()
    assert s["current_fill_total"] == 20 and all(i["suggested"] > 0 for i in s["items"])

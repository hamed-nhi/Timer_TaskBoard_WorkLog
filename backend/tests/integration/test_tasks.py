"""Task CRUD, the pause/resume lifecycle and the minute arithmetic (ported from the desktop suite)."""
from datetime import date, datetime, timedelta

from tests.support import sql
from app.core.time import g2j, now_local


def create_task(client, **overrides):
    payload = {"title": "کار روی گزارش"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


def make_tag(client, name="تگ"):
    return client.post("/api/tags", json={"name": name}).get_json()["id"]


def test_create_task_defaults_to_running(client):
    res = create_task(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "running" and data["end_time"] is None and data["start_time"] is not None


def test_create_task_requires_title(client):
    assert client.post("/api/tasks", json={"title": "   "}).status_code == 400
    assert client.post("/api/tasks", json={"title": "x" * 501}).status_code == 400
    assert create_task(client, start_time="9:00").status_code == 400
    assert create_task(client, jalali_month=13).status_code == 400


def test_create_task_with_end_time_is_done_immediately(client):
    data = create_task(client, start_time="09:00", end_time="10:15").get_json()
    assert data["status"] == "done" and data["duration_minutes"] == 75.0


def test_backdated_running_task_counts_from_custom_start(client):
    custom_start = (now_local() - timedelta(hours=1)).strftime("%H:%M")
    task_id = create_task(client, start_time=custom_start).get_json()["id"]
    paused = client.post(f"/api/tasks/{task_id}/pause").get_json()
    assert paused["status"] == "paused" and 58 <= paused["accumulated_minutes"] <= 62


def test_pause_resume_stop_lifecycle(client):
    task_id = create_task(client).get_json()["id"]
    sql("UPDATE tasks SET segment_started_at = :s WHERE id = :i", s=now_local() - timedelta(minutes=10), i=task_id)
    paused = client.post(f"/api/tasks/{task_id}/pause").get_json()
    assert paused["status"] == "paused" and 9 <= paused["accumulated_minutes"] <= 11
    resumed = client.post(f"/api/tasks/{task_id}/resume").get_json()
    assert resumed["status"] == "running" and resumed["segment_started_at"] is not None
    stopped = client.post(f"/api/tasks/{task_id}/stop").get_json()
    assert stopped["status"] == "done" and stopped["duration_minutes"] >= 9.9 and stopped["end_time"]
    assert [s["ended_at"] is not None for s in sql("SELECT ended_at FROM task_segments ORDER BY id")] == [True, True]


def test_double_stop_does_not_change_the_end_time(client):
    t = create_task(client, start_time="09:00", end_time="10:00").get_json()
    again = client.post(f"/api/tasks/{t['id']}/stop").get_json()
    assert again["end_time"] == "10:00" and again["duration_minutes"] == 60


def test_pause_is_noop_when_not_running(client):
    task_id = create_task(client, start_time="09:00", end_time="10:00").get_json()["id"]
    assert client.post(f"/api/tasks/{task_id}/pause").get_json()["status"] == "done"


def test_reopen_adds_a_session_on_top(client):
    old = create_task(client, jalali_year=1405, jalali_month=7, jalali_day=1, start_time="09:00", end_time="10:00").get_json()
    assert client.post(f"/api/tasks/{old['id']}/reopen").status_code == 400    # not a task of today
    today = g2j(date.today())
    t = create_task(client, title="امروز", jalali_year=today.year, jalali_month=today.month, jalali_day=today.day,
                    start_time="00:00", end_time="00:30").get_json()
    r = client.post(f"/api/tasks/{t['id']}/reopen").get_json()
    assert r["status"] == "running" and r["accumulated_minutes"] == 30 and r["entered_main_system"] is False
    assert sql("SELECT count(*) c FROM task_segments WHERE task_id=:i", i=t["id"])[0]["c"] == 2


def test_update_task_changes_fields(client):
    task_id = create_task(client, start_time="09:00", end_time="10:00").get_json()["id"]
    data = client.put(f"/api/tasks/{task_id}", json={"title": "عنوان جدید", "start_time": "08:00",
                                                     "end_time": "09:30"}).get_json()
    assert data["title"] == "عنوان جدید" and data["duration_minutes"] == 90.0


def test_editing_title_of_paused_task_keeps_its_time(client):
    task = create_task(client).get_json()
    client.post(f"/api/tasks/{task['id']}/pause")
    sql("UPDATE tasks SET accumulated_minutes = 95 WHERE id = :i", i=task["id"])
    data = client.put(f"/api/tasks/{task['id']}", json={"title": "عنوان تازه"}).get_json()
    assert data["title"] == "عنوان تازه" and data["status"] == "paused" and data["accumulated_minutes"] == 95


def test_editing_title_of_running_task_keeps_its_segment(client):
    tag = make_tag(client)
    task = create_task(client, start_time="00:00").get_json()
    data = client.put(f"/api/tasks/{task['id']}", json={"title": "عنوان تازه", "tag_id": tag}).get_json()
    assert data["status"] == "running" and data["segment_started_at"] == task["segment_started_at"]
    assert data["end_time"] is None and data["tag_name"] == "تگ"


def test_finishing_running_task_via_edit_uses_typed_end_time(client):
    task = create_task(client, start_time="00:00").get_json()
    data = client.put(f"/api/tasks/{task['id']}", json={"start_time": "00:00", "end_time": "00:45"}).get_json()
    assert data["status"] == "done" and data["end_time"] == "00:45" and data["duration_minutes"] == 45.0


def test_editing_title_of_done_task_keeps_paused_duration(client):
    task = create_task(client, start_time="09:00", end_time="11:00").get_json()
    sql("UPDATE tasks SET duration_minutes = 100 WHERE id = :i", i=task["id"])
    sql("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (:i, now(), now())", i=task["id"])
    assert client.put(f"/api/tasks/{task['id']}", json={"title": "x"}).get_json()["duration_minutes"] == 100


def test_update_missing_task_404(client):
    assert client.put("/api/tasks/9999", json={"title": "x"}).status_code == 404


def test_delete_task_archives_it(client):
    t = create_task(client, start_time="09:00", end_time="10:00").get_json()
    assert client.delete(f"/api/tasks/{t['id']}").get_json()["ok"] is True
    assert all(x["id"] != t["id"] for x in client.get("/api/tasks").get_json())
    archived = sql("SELECT payload FROM audit_log WHERE kind='task_deleted'")[0]["payload"]
    assert archived["task"]["title"] == "کار روی گزارش" and len(archived["segments"]) == 1
    assert sql("SELECT count(*) c FROM task_segments")[0]["c"] == 0
    assert client.delete(f"/api/tasks/{t['id']}").get_json()["ok"] is True      # deleting twice is harmless


def test_list_tasks_filters_by_year_month(client):
    create_task(client, jalali_year=1405, jalali_month=7, jalali_day=1, start_time="09:00", end_time="10:00")
    create_task(client, jalali_year=1404, jalali_month=1, jalali_day=1, start_time="09:00", end_time="10:00")
    res = client.get("/api/tasks?year=1405&month=7").get_json()
    assert len(res) == 1 and res[0]["jalali_year"] == 1405


def test_yesterday_titles(client):
    y = g2j(date.today() - timedelta(days=1))
    create_task(client, title="جلسه دیروز", jalali_year=y.year, jalali_month=y.month, jalali_day=y.day,
                start_time="09:00", end_time="10:00")
    assert "جلسه دیروز" in client.get("/api/yesterday-titles").get_json()


def test_month_days_and_shift_date(client):
    assert client.get("/api/month-days?year=1404&month=1").get_json()["days"] == 31
    assert client.get("/api/month-days?year=1404&month=7").get_json()["days"] == 30
    assert client.get("/api/month-days?year=1404&month=13").status_code == 400
    r = client.get("/api/shift-date?year=1405&month=1&day=1&delta=-1").get_json()
    assert (r["jalali_year"], r["jalali_month"], r["jalali_day"]) == (1404, 12, 29)


def test_entered_flag_and_company_ticks(client):
    t = create_task(client, start_time="09:00", end_time="10:00").get_json()
    assert client.post(f"/api/tasks/{t['id']}/entered", json={"entered": True}).get_json()["entered_main_system"] is True
    r = client.post(f"/api/tasks/{t['id']}/company", json={"outside_company": True, "planned_flag": True}).get_json()
    assert r["outside_company"] is True and r["planned_flag"] is True and r["duration_minutes"] == 60


def test_segments_endpoint(client):
    t = create_task(client, start_time="09:00", end_time="10:00").get_json()
    segs = client.get(f"/api/tasks/{t['id']}/segments").get_json()
    assert segs[0]["started_label"] == "09:00" and segs[0]["ended_label"] == "10:00" and segs[0]["minutes"] == 60


# ---- manual +/- correction of the total ----

def done_task(client, start="09:00", end="10:30"):
    return client.post("/api/tasks", json={"title": "کار", "start_time": start, "end_time": end}).get_json()


def put(client, tid, **body):
    return client.put(f"/api/tasks/{tid}", json=body)


def set_segments(task, spans, duration):
    day = sql("SELECT gregorian_date d FROM tasks WHERE id=:i", i=task["id"])[0]["d"]
    sql("DELETE FROM task_segments WHERE task_id=:i", i=task["id"])
    for a, b in spans:
        sql("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (:i, :a, :b)", i=task["id"],
            a=datetime.fromisoformat(f"{day}T{a}:00"), b=datetime.fromisoformat(f"{day}T{b}:00"))
    sql("UPDATE tasks SET duration_minutes=:d, accumulated_minutes=:d WHERE id=:i", d=duration, i=task["id"])


def test_add_and_remove_minutes_on_a_finished_task(client):
    t = done_task(client)
    assert put(client, t["id"], adjust_minutes=15).get_json()["duration_minutes"] == 105
    r = put(client, t["id"], adjust_minutes=-40).get_json()
    assert r["duration_minutes"] == 65 and r["accumulated_minutes"] == 65
    assert r["start_time"] == "09:00" and r["end_time"] == "10:30"


def test_manual_addition_survives_resave_and_clock_edit(client):
    t = done_task(client)
    assert put(client, t["id"], adjust_minutes=150).get_json()["duration_minutes"] == 240
    assert put(client, t["id"], title="عنوان").get_json()["duration_minutes"] == 240
    assert put(client, t["id"], end_time="10:40").get_json()["duration_minutes"] == 250


def test_cannot_go_negative_and_nothing_changes(client):
    t = done_task(client)
    assert put(client, t["id"], adjust_minutes=-91).status_code == 400
    assert client.get("/api/tasks").get_json()[0]["duration_minutes"] == 90


def test_invalid_adjust_values_are_rejected(client):
    t = done_task(client)
    assert put(client, t["id"], adjust_minutes="abc").status_code == 400
    assert put(client, t["id"], adjust_minutes=10 ** 7).status_code == 400
    assert put(client, t["id"], adjust_minutes=0).get_json()["duration_minutes"] == 90


def test_adjusting_a_task_with_pauses_keeps_the_pauses_out(client):
    t = done_task(client, "08:00", "12:00")
    set_segments(t, [("08:00", "09:00"), ("11:00", "12:00")], 120)
    assert put(client, t["id"], adjust_minutes=-20).get_json()["duration_minutes"] == 100
    assert put(client, t["id"], end_time="12:30").get_json()["duration_minutes"] == 130


def test_running_and_paused_tasks_can_be_adjusted(client):
    r = client.post("/api/tasks", json={"title": "زنده"}).get_json()
    client.post(f"/api/tasks/{r['id']}/pause")
    up = put(client, r["id"], adjust_minutes=30).get_json()
    assert up["status"] == "paused" and up["accumulated_minutes"] >= 30
    assert put(client, r["id"], adjust_minutes=-31).status_code == 400
    assert client.post(f"/api/tasks/{r['id']}/stop").get_json()["duration_minutes"] >= 30


# ---- editing clock times of finished tasks ----

def make_done(client, start="09:00", end="11:00", recorded=None):
    task = done_task(client, start, end)
    if recorded is not None:      # as if a pause had been recorded: a task with two work segments
        sql("UPDATE tasks SET duration_minutes=:r, accumulated_minutes=:r WHERE id=:i", r=recorded, i=task["id"])
        sql("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (:i, '2020-01-01 00:00:00', '2020-01-01 00:01:00')",
            i=task["id"])
    return task


def test_earlier_start_adds_exactly_the_difference(client):
    task = make_done(client, recorded=100)
    edited = put(client, task["id"], start_time="08:50").get_json()
    assert edited["duration_minutes"] == 110.0 and edited["accumulated_minutes"] == 110.0


def test_later_end_adds_exactly_the_difference(client):
    assert put(client, make_done(client, recorded=100)["id"], end_time="11:30").get_json()["duration_minutes"] == 130.0


def test_changing_both_ends_at_once(client):
    edited = put(client, make_done(client, recorded=100)["id"], start_time="09:30", end_time="11:00").get_json()
    assert edited["duration_minutes"] == 70.0


def test_without_pauses_the_new_duration_is_simply_the_new_span(client):
    edited = put(client, make_done(client)["id"], start_time="08:00", end_time="09:30").get_json()
    assert edited["duration_minutes"] == 90.0


def test_duration_never_goes_negative_nor_zero_for_a_real_window(client):
    task = make_done(client, "09:00", "10:00", recorded=10)
    assert put(client, task["id"], start_time="09:50", end_time="10:00").get_json()["duration_minutes"] == 10.0


def test_reopened_task_whose_end_is_corrected_earlier_keeps_the_typed_window(client):
    task = make_done(client, "09:04", "10:36", recorded=1.3)
    assert put(client, task["id"], end_time="10:30").get_json()["duration_minutes"] == 86.0


def test_title_edit_alone_does_not_touch_duration(client):
    task = make_done(client, recorded=100)
    assert put(client, task["id"], title="عنوان جدید").get_json()["duration_minutes"] == 100


def test_a_never_paused_task_always_lasts_exactly_end_minus_start(client):
    task = make_done(client, "10:23", "12:21")
    sql("UPDATE tasks SET duration_minutes = 0, accumulated_minutes = 0 WHERE id = :i", i=task["id"])
    edited = put(client, task["id"], start_time="12:22", end_time="12:35").get_json()
    assert edited["duration_minutes"] == 13.0
    segs = client.get(f"/api/tasks/{task['id']}/segments").get_json()
    assert segs[0]["started_label"] == "12:22" and segs[0]["ended_label"] == "12:35"


def test_saving_without_changes_repairs_a_wrong_total_of_a_never_paused_task(client):
    task = make_done(client, "12:22", "12:35")
    sql("UPDATE tasks SET duration_minutes = 0, accumulated_minutes = 0 WHERE id = :i", i=task["id"])
    assert put(client, task["id"], title="کار").get_json()["duration_minutes"] == 13.0


def test_moving_the_start_of_a_running_task_moves_its_running_segment(client):
    two_hours_ago = (now_local() - timedelta(hours=2)).strftime("%H:%M")
    task = client.post("/api/tasks", json={"title": "کار", "start_time": two_hours_ago}).get_json()
    put(client, task["id"], start_time=now_local().strftime("%H:%M"))
    end_hm = (now_local() + timedelta(minutes=13)).strftime("%H:%M")
    done = put(client, task["id"], end_time=end_hm).get_json()
    assert 12.5 <= done["duration_minutes"] <= 14.5


def test_moving_the_end_back_to_the_real_last_stop_keeps_the_work(client):
    task = make_done(client, "08:04", "12:54")
    set_segments(task, [("08:04", "08:20"), ("09:40", "09:50"), ("11:13", "12:15")], 88)
    edited = put(client, task["id"], end_time="12:15").get_json()
    assert edited["end_time"] == "12:15" and edited["duration_minutes"] == 88.0
    assert put(client, task["id"], end_time="12:45").get_json()["duration_minutes"] == 118.0

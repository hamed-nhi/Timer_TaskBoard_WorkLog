"""Import of a desktop database copy: nothing lost, nothing changed, never on the real file."""
import json
import sqlite3

import pytest

from conftest import make_user, sql, login_as
from app.importer import ImportError_, run

DESKTOP_DDL = """
CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, jalali_year INTEGER NOT NULL, jalali_month INTEGER NOT NULL,
 jalali_day INTEGER NOT NULL, gregorian_date TEXT NOT NULL, title TEXT NOT NULL, start_time TEXT, end_time TEXT,
 duration_minutes REAL, status TEXT NOT NULL DEFAULT 'running', accumulated_minutes REAL NOT NULL DEFAULT 0,
 segment_started_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), tag_id INTEGER,
 entered_main_system INTEGER NOT NULL DEFAULT 0, meeting_with TEXT, meeting_minutes REAL,
 adjust_minutes REAL NOT NULL DEFAULT 0, report_type TEXT, outside_company INTEGER NOT NULL DEFAULT 0,
 planned_flag INTEGER NOT NULL DEFAULT 0, fill_minutes REAL NOT NULL DEFAULT 0);
CREATE TABLE planned_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, jalali_year INTEGER NOT NULL,
 jalali_month INTEGER NOT NULL, jalali_day INTEGER NOT NULL, title TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), tag_id INTEGER);
CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), budget_minutes REAL, budget_since TEXT,
 report_type TEXT, project TEXT, story TEXT, fill_weight REAL);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE task_segments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, started_at TEXT NOT NULL,
 ended_at TEXT);
CREATE TABLE deleted_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
 deleted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), payload TEXT NOT NULL);
CREATE TABLE presence_segments (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, ended_at TEXT,
 note TEXT, kind TEXT);
"""


@pytest.fixture()
def desktop_copy(tmp_path):
    path = tmp_path / "copy.db"
    con = sqlite3.connect(path)
    con.executescript(DESKTOP_DDL)
    con.execute("INSERT INTO tags (id, name, budget_minutes, budget_since, report_type, project, story, fill_weight) "
                "VALUES (5, 'استوری الف', 600, '2026-10-01', 'گزارش فنی', 'پروژه', 'استوری الف', 2)")
    con.execute("INSERT INTO tags (id, name, report_type) VALUES (6, 'جلسه', 'جلسات')")
    con.execute("INSERT INTO tags (id, name, project) VALUES (7, 'ناقص', 'فقط پروژه')")
    con.execute("INSERT INTO tasks (id, jalali_year, jalali_month, jalali_day, gregorian_date, title, start_time, end_time, "
                "duration_minutes, status, accumulated_minutes, tag_id, entered_main_system, adjust_minutes, "
                "report_type, outside_company, planned_flag, fill_minutes, created_at) VALUES "
                "(10, 1405, 7, 3, '2026-09-25', 'کار یک', '09:00', '10:30', 90.5, 'done', 90.5, 5, 1, 5, 'جلسات', 1, 1, 15, "
                "'2026-09-25 10:31:00')")
    con.execute("INSERT INTO tasks (id, jalali_year, jalali_month, jalali_day, gregorian_date, title, start_time, "
                "status, accumulated_minutes, segment_started_at, tag_id) VALUES "
                "(11, 1405, 7, 3, '2026-09-25', 'در حال اجرا', '11:00', 'running', 0, '2026-09-25T11:00:00.123456', 6)")
    con.execute("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (10, '2026-09-25T09:00:00', '2026-09-25T10:30:30')")
    con.execute("INSERT INTO task_segments (task_id, started_at, ended_at) VALUES (11, '2026-09-25T11:00:00.123456', NULL)")
    con.execute("INSERT INTO planned_tasks (jalali_year, jalali_month, jalali_day, title, tag_id) VALUES (1405, 7, 9, 'برنامه', 5)")
    con.execute("INSERT INTO presence_segments (started_at, ended_at, note, kind) VALUES "
                "('2026-09-25T08:30:00', '2026-09-25T12:00:00', 'ناهار', 'break')")
    con.execute("INSERT INTO deleted_tasks (task_id, deleted_at, payload) VALUES (99, '2026-09-26 08:00:00', ?)",
                (json.dumps({"task": {"id": 99, "title": "حذف‌شده", "tag_id": 5}, "segments": []}),))
    for key, value in {"daily_goal_minutes": "420", "fill_target_percent": "90", "presence_last_seen": "x",
                       "company_catalog": json.dumps({"types": ["گزارش فنی", "جلسات", "ماموریت"],
                                                      "projects": {"پروژه": ["استوری الف", "استوری ب"]}}),
                       "tag_merge_log": json.dumps([{"at": "2026-09-20T10:00:00", "source": {"id": 1}}]),
                       "fill_rollback_log": json.dumps([{"at": "2026-09-21T10:00:00", "date": "2026-09-21", "fills": {"1": 5}}])
                       }.items():
        con.execute("INSERT INTO settings VALUES (?, ?)", (key, value))
    con.commit()
    con.close()
    return path


def test_full_import_keeps_every_number(desktop_copy):
    uid = make_user("hamed")
    result = run(desktop_copy, "hamed")
    assert result["report"]["tasks"] == {"source": 2, "imported": 2}
    assert any("ناقص" in w for w in result["warnings"])
    t = sql("SELECT * FROM tasks WHERE title='کار یک'")[0]
    assert (t["duration_minutes"], t["accumulated_minutes"], t["fill_minutes"], t["adjust_minutes"]) == (90.5, 90.5, 15, 5)
    assert t["entered_main_system"] and t["outside_company"] and t["planned_flag"] and t["start_time"] == "09:00"
    assert str(t["gregorian_date"]) == "2026-09-25" and t["user_id"] == uid
    running = sql("SELECT * FROM tasks WHERE title='در حال اجرا'")[0]
    assert running["status"] == "running" and running["segment_started_at"].microsecond == 123456
    # the report type of a task and the tag's company fields became catalog links
    names = sql("SELECT rt.name tt, s.name sn, p.name pn, tg.fill_weight w, tg.budget_since b FROM tags tg "
                "LEFT JOIN report_types rt ON rt.id=tg.report_type_id LEFT JOIN stories s ON s.id=tg.story_id "
                "LEFT JOIN projects p ON p.id=s.project_id WHERE tg.name='استوری الف'")[0]
    assert (names["tt"], names["sn"], names["pn"], names["w"], str(names["b"])) == ("گزارش فنی", "استوری الف", "پروژه", 2, "2026-10-01")
    assert sql("SELECT rt.name n FROM tasks t JOIN report_types rt ON rt.id=t.report_type_id WHERE t.title='کار یک'")[0]["n"] == "جلسات"
    assert {r["name"] for r in sql("SELECT name FROM report_types")} == {"گزارش فنی", "جلسات", "ماموریت"}
    assert sql("SELECT count(*) c FROM stories")[0]["c"] == 2
    # settings, presence, archive and logs
    assert {r["key"]: r["value"] for r in sql("SELECT key, value FROM user_settings")} == {
        "daily_goal_minutes": "420", "fill_target_percent": "90"}
    assert sql("SELECT note FROM presence_segments")[0]["note"] == "ناهار"
    kinds = sorted(r["kind"] for r in sql("SELECT kind FROM audit_log"))
    assert kinds == ["fill_rollback", "tag_merge", "task_deleted"]
    archived = sql("SELECT payload FROM audit_log WHERE kind='task_deleted'")[0]["payload"]
    new_tag = sql("SELECT id FROM tags WHERE name='استوری الف'")[0]["id"]
    assert archived["task"]["tag_id"] == new_tag
    assert sql("SELECT tag_id FROM planned_tasks")[0]["tag_id"] == new_tag
    assert sql("SELECT count(*) c FROM task_segments")[0]["c"] == 2


def test_imported_data_shows_up_in_the_app(desktop_copy):
    make_user("hamed")
    run(desktop_copy, "hamed")
    c = login_as("hamed")
    tasks = {t["title"]: t for t in c.get("/api/tasks").get_json()}
    assert tasks["کار یک"]["company_type"] == "جلسات" and tasks["کار یک"]["company_story"] == "استوری الف"
    assert c.get("/api/dashboard?year=1405").get_json()["total_minutes"] == 90.5
    assert c.get("/api/tags").get_json()[0]["budget_minutes"] == 600


def test_dry_run_saves_nothing(desktop_copy):
    make_user("hamed")
    assert run(desktop_copy, "hamed", dry_run=True)["dry_run"] is True
    assert sql("SELECT count(*) c FROM tasks")[0]["c"] == 0 and sql("SELECT count(*) c FROM report_types")[0]["c"] == 0


def test_source_file_is_not_modified(desktop_copy):
    make_user("hamed")
    before = desktop_copy.read_bytes()
    run(desktop_copy, "hamed")
    assert desktop_copy.read_bytes() == before


def test_refuses_the_real_database_name(desktop_copy, tmp_path):
    real = tmp_path / "tasklog.db"
    real.write_bytes(desktop_copy.read_bytes())
    make_user("hamed")
    with pytest.raises(ImportError_, match="کپی"):
        run(real, "hamed")


def test_refuses_a_non_empty_account_and_unknown_user(desktop_copy):
    make_user("hamed")
    run(desktop_copy, "hamed")
    with pytest.raises(ImportError_, match="خالی نیست"):
        run(desktop_copy, "hamed")
    with pytest.raises(ImportError_, match="وجود ندارد"):
        run(desktop_copy, "nobody")


def test_other_users_data_untouched(desktop_copy):
    make_user("friend")
    make_user("hamed")
    c = login_as("friend")
    c.post("/api/tasks", json={"title": "کار دوست", "start_time": "09:00", "end_time": "09:30"})
    run(desktop_copy, "hamed")
    assert [t["title"] for t in c.get("/api/tasks").get_json()] == ["کار دوست"]


def test_a_mismatch_rolls_everything_back(desktop_copy, monkeypatch):
    """If the imported numbers ever differ from the source, nothing stays."""
    from app import importer
    make_user("hamed")
    original_execute = importer.Db.execute

    def skip_segment_rows(self, sql_text, params=()):
        if sql_text.startswith("INSERT INTO task_segments"):
            return original_execute(self, "SELECT 1", ())
        return original_execute(self, sql_text, params)

    monkeypatch.setattr(importer.Db, "execute", skip_segment_rows)
    with pytest.raises(ImportError_, match="عدم تطابق"):
        run(desktop_copy, "hamed")
    monkeypatch.undo()
    assert sql("SELECT count(*) c FROM tasks")[0]["c"] == 0 and sql("SELECT count(*) c FROM tags")[0]["c"] == 0

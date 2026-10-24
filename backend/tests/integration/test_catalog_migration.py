"""Upgrade real legacy rows in a disposable schema, preserving times and ownership."""
import json
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.session import engine


def test_private_catalog_migration_preserves_legacy_data():
    schema = "catalog_migration_" + uuid.uuid4().hex
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "0001")
            conn.execute(text("INSERT INTO users (id, username, password_hash) VALUES "
                              "(1,'alice','hash'),(2,'bob','hash'),(3,'empty','hash')"))
            conn.execute(text("INSERT INTO report_types (id,name,sort) VALUES "
                              "(1,'shared type',0),(2,'unused private legacy',1)"))
            conn.execute(text("INSERT INTO projects (id,name,sort) VALUES (1,'shared project',0)"))
            conn.execute(text("INSERT INTO stories (id,project_id,name,sort) VALUES "
                              "(1,1,'alice story',0),(2,1,'bob story',1)"))
            # Explicit fixture IDs need their sequences advanced before migration creates copies.
            for table in ("report_types", "projects", "stories"):
                conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                                  f"(SELECT MAX(id) FROM {table}))"))
            conn.execute(text("INSERT INTO tags (id,user_id,name,report_type_id,story_id) VALUES "
                              "(1,1,'alice tag',1,1),(2,2,'bob tag',1,2)"))
            conn.execute(text("INSERT INTO tasks (id,user_id,jalali_year,jalali_month,jalali_day,gregorian_date,"
                              "title,status,start_time,end_time,duration_minutes,accumulated_minutes,"
                              "fill_minutes,adjust_minutes,tag_id,report_type_id) VALUES "
                              "(1,1,1405,7,3,'2026-09-25','alice work','done','09:00','10:00',60,60,10,5,1,1),"
                              "(2,2,1405,7,3,'2026-09-25','bob work','done','10:00','11:30',90,90,20,0,2,1)"))
            conn.execute(text("INSERT INTO task_segments (task_id,started_at,ended_at) VALUES "
                              "(1,'2026-09-25 09:00','2026-09-25 10:00'),"
                              "(2,'2026-09-25 10:00','2026-09-25 11:30')"))
            conn.execute(text("INSERT INTO planned_tasks (user_id,jalali_year,jalali_month,jalali_day,title,tag_id) "
                              "VALUES (1,1405,7,4,'plan',1)"))
            conn.execute(text("INSERT INTO presence_segments (user_id,started_at,ended_at) "
                              "VALUES (1,'2026-09-25 08:00','2026-09-25 12:00')"))
            payload = {"task": {"id": 99, "title": "deleted", "report_type_id": 2, "tag_id": 1}, "segments": []}
            conn.execute(text("INSERT INTO audit_log (user_id,kind,payload) VALUES "
                              "(1,'task_deleted',CAST(:payload AS jsonb))"), {"payload": json.dumps(payload)})
            before = conn.execute(text("SELECT id,user_id,title,duration_minutes,accumulated_minutes,"
                                       "fill_minutes,adjust_minutes,start_time,end_time FROM tasks ORDER BY id")).all()
            segments = conn.execute(text("SELECT * FROM task_segments ORDER BY id")).all()
            presence = conn.execute(text("SELECT * FROM presence_segments ORDER BY id")).all()
            command.upgrade(cfg, "head")
            assert conn.execute(text("SELECT id,user_id,title,duration_minutes,accumulated_minutes,"
                                     "fill_minutes,adjust_minutes,start_time,end_time FROM tasks ORDER BY id")).all() == before
            assert conn.execute(text("SELECT * FROM task_segments ORDER BY id")).all() == segments
            assert conn.execute(text("SELECT * FROM presence_segments ORDER BY id")).all() == presence
            rows = conn.execute(text("SELECT t.user_id,t.report_type_id,tg.report_type_id tag_type,s.name,"
                                     "s.user_id story_owner,p.user_id project_owner "
                                     "FROM tasks t JOIN tags tg ON tg.id=t.tag_id "
                                     "JOIN stories s ON s.id=tg.story_id JOIN projects p ON p.id=s.project_id "
                                     "ORDER BY t.user_id")).mappings().all()
            assert rows[0]["report_type_id"] != rows[1]["report_type_id"]
            for row in rows:
                assert row["report_type_id"] == row["tag_type"]
                assert row["user_id"] == row["story_owner"] == row["project_owner"]
            assert [r["name"] for r in rows] == ["alice story", "bob story"]
            assert conn.execute(text("SELECT count(*) FROM stories WHERE user_id=3")).scalar_one() == 0
            assert conn.execute(text("SELECT count(*) FROM report_types WHERE user_id IS NULL")).scalar_one() == 2
            archive = conn.execute(text("SELECT payload FROM audit_log WHERE user_id=1")).scalar_one()
            owner = conn.execute(text("SELECT user_id FROM report_types WHERE id=:id"),
                                 {"id": archive["task"]["report_type_id"]}).scalar_one()
            assert owner == 1 and archive["task"]["title"] == "deleted"
            assert conn.execute(text("SELECT count(*) FROM planned_tasks WHERE user_id=1 AND tag_id=1")).scalar_one() == 1
            # Ownerless originals survive but none is referenced by current users' data.
            assert conn.execute(text("SELECT count(*) FROM tags tg JOIN stories s ON s.id=tg.story_id "
                                     "WHERE s.user_id IS NULL")).scalar_one() == 0
        finally:
            transaction.rollback()

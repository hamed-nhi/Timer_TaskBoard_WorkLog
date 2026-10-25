"""Seed synthetic users/history only in the isolated system-test database."""
import argparse
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
url = os.environ.get("QA_DATABASE_URL", "")
parsed = make_url(url) if url else None
if not parsed or (parsed.database, parsed.port) not in {("timelog_audit_test", 5544)} or parsed.host not in {"127.0.0.1", "localhost"}:
    raise SystemExit("QA_DATABASE_URL must target a verified local QA database/port pair")
os.environ["DATABASE_URL"] = url

from app.core.security import hash_password
from app.core.time import g2j, today_local
from app.db.session import Db, SessionLocal

PASSWORD = "qa-system-password-1"


def seed(load=False, reset_ui=False):
    with SessionLocal() as session:
        db = Db(session)
        if reset_ui and parsed.database != "timelog_audit_test":
            raise SystemExit("Refusing to reset existing demo accounts; use the isolated audit database")
        if reset_ui:
            db.execute("DELETE FROM login_attempts WHERE username IN (?,?,?,?,?)",
                       ("qa_alice", "qa_bob", "qa_admin", "qa_invited", "qa_inactive"))
            db.execute("DELETE FROM users WHERE username IN (?,?,?,?)",
                       ("qa_alice", "qa_bob", "qa_admin", "qa_invited"))
        names = ["qa_alice", "qa_bob", "qa_admin"]
        if load:
            names += [f"qa_load_{i}" for i in range(10)]
        for name in names:
            db.execute("INSERT INTO users (username,password_hash,display_name,is_admin) VALUES (?,?,?,?) "
                       "ON CONFLICT (username) DO NOTHING",
                       (name, hash_password(PASSWORD), name, name == "qa_admin"))
        if load:
            for name in names[3:]:
                uid = db.execute("SELECT id FROM users WHERE username=?", (name,)).fetchone()["id"]
                if db.execute("SELECT count(*) c FROM tasks WHERE user_id=?", (uid,)).fetchone()["c"]:
                    continue
                tag = db.insert("INSERT INTO tags (user_id,name) VALUES (?,?)", (uid, "QA history"))
                for offset in range(28):
                    day = today_local() - timedelta(days=offset)
                    j = g2j(day)
                    db.execute(
                        "INSERT INTO tasks (user_id,jalali_year,jalali_month,jalali_day,gregorian_date,title,"
                        "start_time,end_time,duration_minutes,status,accumulated_minutes,tag_id) "
                        "SELECT ?,?,?,?,?, 'QA work ' || n, "
                        "to_char(time '09:00' + n * interval '20 minutes','HH24:MI'),"
                        "to_char(time '09:00' + (n+1) * interval '20 minutes','HH24:MI'),20,'done',20,? "
                        "FROM generate_series(0,9) n", (uid,j.year,j.month,j.day,day,tag))
                    db.execute("INSERT INTO presence_segments (user_id,started_at,ended_at,kind) VALUES (?,?,?,'end')",
                               (uid,datetime.combine(day,time(8)),datetime.combine(day,time(16))))
                db.execute("INSERT INTO task_segments (task_id,started_at,ended_at) "
                           "SELECT id,gregorian_date + start_time::time,gregorian_date + end_time::time "
                           "FROM tasks WHERE user_id=?", (uid,))
        if parsed.database == "timelog_audit_test":
            db.execute("INSERT INTO users (username,password_hash,display_name,is_active) VALUES (?,?,?,false) "
                       "ON CONFLICT (username) DO NOTHING", ("qa_inactive", hash_password(PASSWORD), "Inactive audit fixture"))
        db.commit()
        print(f"Seeded {len(names)} synthetic QA accounts" + (" and 2800 history tasks" if load else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--reset-ui", action="store_true")
    args = parser.parse_args()
    seed(args.load, args.reset_ui)

"""Prove an actual QA pg_dump/restore and API restart preserve synthetic data."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/testing"
CMD = ["docker", "compose", "-p", "timelog-qa", "-f", str(ROOT / "docker-compose.test.yml")]
SOURCE = "timelog_system_test"
TARGET = "timelog_recovery_test"
TABLES = ["users", "tasks", "task_segments", "tags", "planned_tasks", "presence_segments",
          "report_types", "projects", "stories", "user_settings", "audit_log", "sessions"]


def snapshot(database):
    assert database in {SOURCE, TARGET} and database.endswith("_test")
    with psycopg.connect(host="127.0.0.1", port=5543, user="timelog", password="qa-password-only", dbname=database) as conn:
        result = {}
        for table in TABLES:
            columns = "user_id, key" if table == "user_settings" else "id"
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY {columns}").fetchall()
            result[table] = {"rows": len(rows), "sha256": hashlib.sha256(
                json.dumps(rows, ensure_ascii=False, default=str).encode()).hexdigest()}
        return result


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    original = snapshot(SOURCE)
    dump = OUT / "qa-only.dump"
    with dump.open("wb") as file:
        subprocess.run(CMD + ["exec", "-T", "db", "pg_dump", "-U", "timelog", "-Fc", SOURCE], stdout=file, check=True)
    subprocess.run(CMD + ["exec", "-T", "db", "createdb", "-U", "timelog", TARGET], check=True)
    try:
        with dump.open("rb") as file:
            subprocess.run(CMD + ["exec", "-T", "db", "pg_restore", "--exit-on-error", "--no-owner",
                                 "-U", "timelog", "-d", TARGET], stdin=file, check=True)
        restored = snapshot(TARGET)
        assert restored == original, "Restored data differs from source"
    finally:
        subprocess.run(CMD + ["exec", "-T", "db", "dropdb", "-U", "timelog", TARGET], check=True)
    with httpx.Client(base_url="http://127.0.0.1:18081", timeout=5) as client:
        login = client.post("/api/auth/login", json={"username": "qa_alice", "password": "qa-system-password-1"},
                            headers={"X-Requested-With": "timelog"})
        login.raise_for_status()
        before = client.get("/api/tasks").json()
        started = time.monotonic()
        subprocess.run(CMD + ["restart", "api"], check=True)
        while time.monotonic() - started < 35:
            try:
                response = client.get("/api/me")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.5)
        else:
            raise AssertionError("API did not recover within 35 seconds")
        assert response.json()["username"] == "qa_alice"
        assert client.get("/api/tasks").json() == before
        restart = round(time.monotonic() - started, 2)
    report = {"dump_restore": "passed", "all_table_fingerprints_equal": True, "tables": original,
              "dump_bytes": dump.stat().st_size, "api_restart": "passed", "session_survived_restart": True,
              "api_recovery_seconds": restart}
    (OUT / "recovery.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))

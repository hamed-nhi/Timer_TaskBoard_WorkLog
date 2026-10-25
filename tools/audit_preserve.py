"""Read-only preservation of the existing demo DB using one exported PG snapshot."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/audit"
CMD = ["docker", "compose", "-p", "timelog-qa", "-f", str(ROOT / "docker-compose.test.yml"), "exec", "-T", "db"]


def fingerprint(connection):
    tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    result = {}
    for (name,) in tables:
        cursor = connection.execute(sql.SQL("SELECT * FROM public.{}").format(sql.Identifier(name)))
        columns = [c.name for c in cursor.description]
        rows = sorted(json.dumps(row, default=str, sort_keys=True, ensure_ascii=False) for row in cursor.fetchall())
        result[name] = {"rows": len(rows), "sha256": hashlib.sha256(json.dumps([columns, rows], ensure_ascii=False).encode()).hexdigest()}
    return result


if __name__ == "__main__":
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = f"timelog_preserve_{stamp.lower()}_test"
    private = ROOT / "backups/pre-audit" / stamp
    private.mkdir(parents=True, mode=0o700)
    OUT.mkdir(parents=True, exist_ok=True)
    dump = private / "current-demo.dump"
    connect = dict(host="127.0.0.1", port=5543, user="timelog", password="qa-password-only")
    with psycopg.connect(**connect, dbname="timelog_system_test") as conn:
        conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        assert conn.execute("SELECT current_database()").fetchone()[0] == "timelog_system_test"
        snap = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        before = fingerprint(conn)
        with dump.open("xb") as stream:
            subprocess.run(CMD + ["pg_dump", "-U", "timelog", "-Fc", "--snapshot", snap, "timelog_system_test"], stdout=stream, check=True)
        dump.chmod(0o600)
    subprocess.run(CMD + ["createdb", "-U", "timelog", target], check=True)
    with dump.open("rb") as stream:
        subprocess.run(CMD + ["pg_restore", "--exit-on-error", "--no-owner", "-U", "timelog", "-d", target], stdin=stream, check=True)
    with psycopg.connect(**connect, dbname=target) as conn:
        after = fingerprint(conn)
    assert before == after, "Preservation restore differs; stop audit"
    report = {"source": "timelog_system_test", "restored_database": target,
              "snapshot_consistent": True, "all_tables_equal": True, "tables": before,
              "private_backup": str(dump.relative_to(ROOT)), "dump_sha256": hashlib.sha256(dump.read_bytes()).hexdigest()}
    (OUT / "preservation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"preserved": True, "tables": len(before), "rows": sum(r["rows"] for r in before.values()), "restore_equal": True}))

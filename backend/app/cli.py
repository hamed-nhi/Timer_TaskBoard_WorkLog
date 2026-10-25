"""Admin command line:  python -m app.cli <command>

  create-user USERNAME [--admin] [--display-name NAME]   password is asked (not passed as an argument)
  reset-password USERNAME
  import-catalog FILE.json --user USERNAME                personal company catalog (desktop format)
  import-desktop COPY.db --user USERNAME [--dry-run]      one-off import of a desktop database copy
"""
import argparse
import getpass
import json
import os
import sys

from .core.security import hash_password
from .services.catalog_helpers import import_catalog
from .core.errors import ApiError
from .db.session import Db, SessionLocal
from .services.importer import ImportError_, run as run_import


def ask_password():
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat: "):
        sys.exit("The two passwords differ")
    return first


def cmd_create_user(args):
    password = ask_password()
    with SessionLocal() as session:
        db = Db(session)
        username = args.username.strip().lower()
        if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            sys.exit("This username already exists")
        db.execute("INSERT INTO users (username, password_hash, display_name, is_admin) VALUES (?, ?, ?, ?)",
                   (username, hash_password(password), args.display_name or "", args.admin))
        db.commit()
    print(f"User {username} created" + (" (admin)" if args.admin else ""))


def cmd_reset_password(args):
    password = ask_password()
    with SessionLocal() as session:
        db = Db(session)
        row = db.execute("SELECT id FROM users WHERE username = ?", (args.username.strip().lower(),)).fetchone()
        if not row:
            sys.exit("No such user")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
        db.commit()
    print("Password changed; the user is logged out everywhere")


def cmd_import_catalog(args):
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    with SessionLocal() as session:
        db = Db(session)
        user = db.execute("SELECT id FROM users WHERE username = ?", (args.user.strip().lower(),)).fetchone()
        if not user:
            sys.exit("No such user")
        import_catalog(db, user["id"], data)
        db.commit()
    print("Catalog imported")


def cmd_import_desktop(args):
    result = run_import(args.db, args.user, dry_run=args.dry_run)
    print("DRY RUN - nothing was saved" if result["dry_run"] else "Import committed")
    for name, c in result["report"].items():
        print(f"  {name:20} source={c['source']}  imported={c['imported']}")
    for w in result["warnings"]:
        print("  warning:", w)


def cmd_backup_users(args):
    from sqlalchemy.orm import Session
    from .db.session import engine
    from .services.personal_backup import backup_user
    from .services.google_sheets import GoogleSheet

    with SessionLocal() as session:
        db = Db(session)
        if args.user:
            users = db.execute("SELECT id FROM users WHERE username = ? AND is_active = true",
                               (args.user.strip().lower(),)).fetchall()
            if not users:
                sys.exit("No active user")
        else:
            users = db.execute("SELECT id FROM users WHERE is_active = true ORDER BY id").fetchall()
    failed = False
    for item in users:
        uid = item["id"]
        # Keep a dedicated connection while holding this session-level job lock.
        # Acquire BEFORE the repeatable-read snapshot; API writes are not blocked.
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_lock(%s, %s)", (731905, uid))
            connection.commit()
            try:
                with Session(bind=connection) as session:
                    db = Db(session)
                    db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                    user = db.execute("SELECT id, username, display_name FROM users WHERE id = ? AND is_active = true",
                                      (uid,)).fetchone()
                    if user:
                        factory = (lambda sid: GoogleSheet(sid, args.sheets_credentials)) if args.sheets_credentials else None
                        result = backup_user(db, user, args.output, factory)
                        print(f"user={uid} revision={result['revision']} new={result['created']} sheet_updates={result['sheet_updates']}")
            except Exception as exc:
                failed = True
                # No private payload, credential path or Google response body in logs.
                print(f"Backup failed for user={uid}: {type(exc).__name__}", file=sys.stderr)
            finally:
                connection.rollback()
                connection.exec_driver_sql("SELECT pg_advisory_unlock(%s, %s)", (731905, uid))
                connection.commit()
    if failed:
        sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-user")
    p.add_argument("username")
    p.add_argument("--admin", action="store_true")
    p.add_argument("--display-name")
    p.set_defaults(func=cmd_create_user)
    p = sub.add_parser("reset-password")
    p.add_argument("username")
    p.set_defaults(func=cmd_reset_password)
    p = sub.add_parser("import-catalog")
    p.add_argument("file")
    p.add_argument("--user", required=True)
    p.set_defaults(func=cmd_import_catalog)
    p = sub.add_parser("import-desktop")
    p.add_argument("db")
    p.add_argument("--user", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_import_desktop)
    p = sub.add_parser("backup-users", help="Versioned personal JSON/Excel and optional source-change-only Sheets sync")
    p.add_argument("--output", required=True)
    p.add_argument("--user")
    p.add_argument("--sheets-credentials", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or None)
    p.set_defaults(func=cmd_backup_users)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ImportError_, ApiError) as e:
        sys.exit(f"Error: {getattr(e, 'message', e)}")


if __name__ == "__main__":
    main()

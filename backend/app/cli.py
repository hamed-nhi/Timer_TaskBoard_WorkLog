"""Admin command line:  python -m app.cli <command>

  create-user USERNAME [--admin] [--display-name NAME]   password is asked (not passed as an argument)
  reset-password USERNAME
  import-catalog FILE.json --user USERNAME                personal company catalog (desktop format)
  import-desktop COPY.db --user USERNAME [--dry-run]      one-off import of a desktop database copy
"""
import argparse
import getpass
import json
import sys

from .auth import hash_password
from .catalog import import_catalog
from .common import ApiError
from .db import Db, SessionLocal
from .importer import ImportError_, run as run_import


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
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ImportError_, ApiError) as e:
        sys.exit(f"Error: {getattr(e, 'message', e)}")


if __name__ == "__main__":
    main()

"""Per-account company catalog helpers, shared by the API and import commands."""


def catalog_payload(db, uid):
    types = db.execute("SELECT id, name FROM report_types WHERE user_id = ? ORDER BY sort, id", (uid,)).fetchall()
    projects = db.execute("SELECT id, name FROM projects WHERE user_id = ? ORDER BY sort, id", (uid,)).fetchall()
    stories = db.execute("SELECT id, project_id, name FROM stories WHERE user_id = ? ORDER BY sort, id",
                         (uid,)).fetchall()
    for project in projects:
        project["stories"] = [s for s in stories if s["project_id"] == project["id"]]
    return {"types": types, "projects": projects}


def import_catalog(db, uid, data):
    """Idempotent import into one account; never reads another account's catalog."""
    db.lock_user(uid)
    for name in data.get("types") or []:
        db.execute("INSERT INTO report_types (user_id, name, sort) VALUES (?, ?, "
                   "(SELECT COALESCE(MAX(sort), 0) + 1 FROM report_types WHERE user_id = ?)) "
                   "ON CONFLICT (user_id, name) DO NOTHING", (uid, name, uid))
    for project, stories in (data.get("projects") or {}).items():
        db.execute("INSERT INTO projects (user_id, name, sort) VALUES (?, ?, "
                   "(SELECT COALESCE(MAX(sort), 0) + 1 FROM projects WHERE user_id = ?)) "
                   "ON CONFLICT (user_id, name) DO NOTHING", (uid, project, uid))
        pid = db.execute("SELECT id FROM projects WHERE user_id = ? AND name = ?", (uid, project)).fetchone()["id"]
        for story in stories or []:
            db.execute("INSERT INTO stories (user_id, project_id, name, sort) VALUES (?, ?, ?, "
                       "(SELECT COALESCE(MAX(sort), 0) + 1 FROM stories WHERE user_id = ? AND project_id = ?)) "
                       "ON CONFLICT (project_id, name) DO NOTHING", (uid, pid, story, uid, pid))

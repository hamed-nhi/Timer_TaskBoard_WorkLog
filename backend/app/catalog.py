"""Shared company catalog helpers (used by the admin API and the CLI)."""


def import_catalog(db, data):
    """Idempotent import of the desktop format: {"types": [...], "projects": {project: [stories]}}.
    Existing entries are kept, missing ones are added."""
    for name in data.get("types") or []:
        db.execute("INSERT INTO report_types (name, sort) VALUES (?, "
                   "(SELECT COALESCE(MAX(sort), 0) + 1 FROM report_types)) ON CONFLICT (name) DO NOTHING", (name,))
    for project, stories in (data.get("projects") or {}).items():
        db.execute("INSERT INTO projects (name, sort) VALUES (?, "
                   "(SELECT COALESCE(MAX(sort), 0) + 1 FROM projects)) ON CONFLICT (name) DO NOTHING", (project,))
        pid = db.execute("SELECT id FROM projects WHERE name = ?", (project,)).fetchone()["id"]
        for story in stories or []:
            db.execute("INSERT INTO stories (project_id, name, sort) VALUES (?, ?, "
                       "(SELECT COALESCE(MAX(sort), 0) + 1 FROM stories WHERE project_id = ?)) "
                       "ON CONFLICT (project_id, name) DO NOTHING", (pid, story, pid))

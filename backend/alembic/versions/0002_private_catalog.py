"""Private catalogs with lossless retention of ownerless legacy catalog rows.

Revision ID: 0002
Revises: 0001
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("report_types", "projects", "stories"):
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_user", table, "users", ["user_id"], ["id"], ondelete="CASCADE")
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_unique_constraint(f"uq_{table}_id_user", table, ["id", "user_id"])
    for table in ("report_types", "projects"):
        # Replace the global name uniqueness without deleting any catalog records.
        op.drop_constraint(f"{table}_name_key", table, type_="unique")
        op.create_unique_constraint(f"uq_{table}_user_name", table, ["user_id", "name"])

    conn = op.get_bind()
    types = {r["id"]: r for r in conn.execute(sa.text("SELECT * FROM report_types")).mappings()}
    projects = {r["id"]: r for r in conn.execute(sa.text("SELECT * FROM projects")).mappings()}
    stories = {r["id"]: r for r in conn.execute(sa.text("SELECT * FROM stories")).mappings()}

    def rows(sql, uid):
        return list(conn.execute(sa.text(sql), {"uid": uid}).mappings())

    def clone(table, row, uid, project_id=None):
        values = {"uid": uid, "name": row["name"], "sort": row["sort"]}
        columns, placeholders = "user_id, name, sort", ":uid, :name, :sort"
        if project_id is not None:
            columns += ", project_id"
            placeholders += ", :pid"
            values["pid"] = project_id
        return conn.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"),
                            values).scalar_one()

    for uid in conn.execute(sa.text("SELECT id FROM users ORDER BY id")).scalars():
        tags = rows("SELECT id, report_type_id, story_id FROM tags WHERE user_id = :uid", uid)
        tasks = rows("SELECT id, report_type_id FROM tasks WHERE user_id = :uid", uid)
        archived = rows("SELECT id, payload FROM audit_log WHERE user_id = :uid AND kind = 'task_deleted'", uid)
        type_ids = {r["report_type_id"] for r in [*tags, *tasks] if r["report_type_id"] is not None}
        for entry in archived:
            task = entry["payload"].get("task") if isinstance(entry["payload"], dict) else None
            if isinstance(task, dict) and isinstance(task.get("report_type_id"), int):
                if task["report_type_id"] in types:
                    type_ids.add(task["report_type_id"])
        story_ids = {r["story_id"] for r in tags if r["story_id"] is not None}
        project_ids = {stories[sid]["project_id"] for sid in story_ids}
        type_map = {old: clone("report_types", types[old], uid) for old in sorted(type_ids)}
        project_map = {old: clone("projects", projects[old], uid) for old in sorted(project_ids)}
        story_map = {old: clone("stories", stories[old], uid, project_map[stories[old]["project_id"]])
                     for old in sorted(story_ids)}
        for tag in tags:
            conn.execute(sa.text("UPDATE tags SET report_type_id=:rt, story_id=:sid WHERE id=:id AND user_id=:uid"),
                         {"rt": type_map.get(tag["report_type_id"]), "sid": story_map.get(tag["story_id"]),
                          "id": tag["id"], "uid": uid})
        for task in tasks:
            conn.execute(sa.text("UPDATE tasks SET report_type_id=:rt WHERE id=:id AND user_id=:uid"),
                         {"rt": type_map.get(task["report_type_id"]), "id": task["id"], "uid": uid})
        for entry in archived:
            payload = entry["payload"]
            task = payload.get("task") if isinstance(payload, dict) else None
            if isinstance(task, dict) and isinstance(task.get("report_type_id"), int) and task["report_type_id"] in type_map:
                task["report_type_id"] = type_map[task["report_type_id"]]
                conn.execute(sa.text("UPDATE audit_log SET payload=CAST(:payload AS jsonb) WHERE id=:id AND user_id=:uid"),
                             {"payload": json.dumps(payload, ensure_ascii=False), "id": entry["id"], "uid": uid})

    op.create_unique_constraint("uq_tags_id_user", "tags", ["id", "user_id"])
    for name, source, columns, target, refs in (
        ("fk_stories_project_owner", "stories", ["project_id", "user_id"], "projects", ["id", "user_id"]),
        ("fk_tags_report_type_owner", "tags", ["report_type_id", "user_id"], "report_types", ["id", "user_id"]),
        ("fk_tags_story_owner", "tags", ["story_id", "user_id"], "stories", ["id", "user_id"]),
        ("fk_tasks_report_type_owner", "tasks", ["report_type_id", "user_id"], "report_types", ["id", "user_id"]),
        ("fk_tasks_tag_owner", "tasks", ["tag_id", "user_id"], "tags", ["id", "user_id"]),
        ("fk_planned_tag_owner", "planned_tasks", ["tag_id", "user_id"], "tags", ["id", "user_id"]),
    ):
        op.create_foreign_key(name, source, target, columns, refs)


def downgrade():
    raise RuntimeError("Private catalogs cannot be merged back automatically without risking user data.")

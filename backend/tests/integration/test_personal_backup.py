"""Account isolation and repeat-run behavior on disposable PostgreSQL."""
import json

from app.db.session import Db, SessionLocal
from app.services.personal_backup import backup_user
from tests.support import sql


def test_sheet_reservation_is_private_and_matches_url_variants(alice, bob, admin):
    url = "https://docs.google.com/spreadsheets/d/personal_sheet/edit#gid=0"
    assert alice.post("/api/settings", json={"google_sheet_url": url}).status_code == 200
    assert bob.get("/api/settings").get_json()["google_sheet_url"] == ""
    for client in (bob, admin):
        assert client.post("/api/settings", json={"google_sheet_url": url.replace("/edit#gid=0", "?gid=5")}).status_code == 400
    assert bob.post("/api/settings", json={"google_sheet_url": url.replace("personal_sheet", "bob_sheet")}).status_code == 200
    assert alice.post("/api/settings", json={"google_sheet_url": ""}).status_code == 200
    assert admin.post("/api/settings", json={"google_sheet_url": url}).status_code == 200


def test_personal_snapshots_keep_prior_versions_and_other_accounts_out(alice, bob, tmp_path):
    task = alice.post("/api/tasks", json={"title": "private Alice", "start_time": "09:00", "end_time": "10:00"}).get_json()
    bob.post("/api/tasks", json={"title": "private Bob", "start_time": "11:00", "end_time": "12:00"})
    users = sql("SELECT id, username, display_name FROM users ORDER BY id")
    def run(user):
        with SessionLocal() as session:
            return backup_user(Db(session), user, tmp_path)
    first = run(users[0])
    assert first["created"] and not run(users[0])["created"]
    run(users[1])
    for user, title in zip(users, ("private Alice", "private Bob")):
        payload = json.loads(next((tmp_path / f"user-{user['id']}").rglob("*.json")).read_text(encoding="utf-8"))
        assert [r["title"] for r in payload["tasks"]] == [title]
    assert alice.put(f"/api/tasks/{task['id']}", json={"title": "edited Alice"}).status_code == 200
    second = run(users[0])
    assert second["created"] and second["revision"] != first["revision"]
    assert len(list((tmp_path / f"user-{users[0]['id']}").rglob("*.json"))) == 2
    assert len(list((tmp_path / f"user-{users[1]['id']}").rglob("*.json"))) == 1


def test_download_filenames_are_personal_stable_and_change_with_source(alice, bob):
    for path in ("/api/me/backup", "/api/export"):
        first = alice.get(path).headers["content-disposition"]
        assert alice.get(path).headers["content-disposition"] == first
        assert bob.get(path).headers["content-disposition"] != first
    before = {p: alice.get(p).headers["content-disposition"] for p in ("/api/me/backup", "/api/export")}
    alice.post("/api/tasks", json={"title": "new source", "start_time": "09:00", "end_time": "10:00"})
    for path, filename in before.items():
        assert alice.get(path).headers["content-disposition"] != filename

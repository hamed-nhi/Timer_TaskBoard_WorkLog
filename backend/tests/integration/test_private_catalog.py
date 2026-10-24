"""Personal catalog CRUD, API/DB isolation and private export coverage."""
import json

import pytest
from sqlalchemy.exc import IntegrityError

from tests.support import sql


def catalog(client):
    r = client.post("/api/catalog/report-types", json={"name": "گزارش خصوصی"})
    assert r.status_code == 201
    rt = r.get_json()["id"]
    r = client.post("/api/catalog/projects", json={"name": "پروژه خصوصی"})
    assert r.status_code == 201
    project = r.get_json()["id"]
    r = client.post(f"/api/catalog/projects/{project}/stories", json={"name": "استوری خصوصی"})
    assert r.status_code == 201
    return rt, project, r.get_json()["id"]


def test_each_account_manages_its_own_catalog(alice, bob, admin):
    rt, project, story = catalog(alice)
    for other in (bob, admin):
        assert other.get("/api/catalog").get_json() == {"types": [], "projects": []}
        visible = other.get("/api/company-catalog").get_json()
        assert visible["projects"] == [] and [t for t in visible["types"] if t["id"]] == []
    assert alice.put(f"/api/catalog/report-types/{rt}", json={"name": "ویرایش"}).status_code == 200
    assert alice.put(f"/api/catalog/projects/{project}", json={"name": "ویرایش"}).status_code == 200
    assert alice.put(f"/api/catalog/stories/{story}", json={"name": "ویرایش"}).status_code == 200
    assert alice.delete(f"/api/catalog/projects/{project}").status_code == 200
    assert alice.delete(f"/api/catalog/report-types/{rt}").status_code == 200
    assert alice.get("/api/catalog").get_json() == {"types": [], "projects": []}


def test_foreign_ids_are_404_even_for_admin(alice, bob, admin):
    rt, project, story = catalog(alice)
    for other in (bob, admin):
        for kind, row_id in (("report-types", rt), ("projects", project), ("stories", story)):
            assert other.put(f"/api/catalog/{kind}/{row_id}", json={"name": "هک"}).status_code == 404
            assert other.delete(f"/api/catalog/{kind}/{row_id}").status_code == 404
        assert other.post(f"/api/catalog/projects/{project}/stories", json={"name": "هک"}).status_code == 404
    assert alice.get("/api/catalog").get_json()["projects"][0]["stories"][0]["name"] == "استوری خصوصی"


def test_duplicate_names_are_private_and_import_is_idempotent(alice, bob):
    a = catalog(alice)
    b = catalog(bob)
    assert all(x != y for x, y in zip(a, b))
    assert alice.post("/api/catalog/report-types", json={"name": "گزارش خصوصی"}).status_code == 409
    data = {"types": ["جدید"], "projects": {"جدید": ["استوری جدید"]}}
    for c in (alice, bob):
        for _ in range(2):
            assert c.post("/api/catalog/import", json=data).status_code == 200
        assert len(c.get("/api/catalog").get_json()["projects"]) == 2


def test_foreign_catalog_cannot_be_attached_to_owned_data(alice, bob):
    rt, _, story = catalog(alice)
    own = bob.post("/api/tags", json={"name": "مال من"}).get_json()["id"]
    for fields in ({"report_type_id": rt}, {"story_id": story}):
        assert bob.post("/api/tags", json={"name": "نامعتبر", **fields}).status_code == 404
        assert bob.put(f"/api/tags/{own}/company", json=fields).status_code == 404
    task = bob.post("/api/tasks", json={"title": "مال من"}).get_json()["id"]
    assert bob.post(f"/api/tasks/{task}/company", json={"report_type_id": rt}).status_code == 404
    assert len(bob.get("/api/tags").get_json()) == 1


def test_catalog_is_in_personal_backup_only(alice, bob):
    catalog(alice)
    mine = json.loads(alice.get("/api/me/backup").content)
    other = json.loads(bob.get("/api/me/backup").content)
    assert mine["catalog"]["types"][0]["name"] == "گزارش خصوصی"
    assert other["catalog"] == {"types": [], "projects": []}


def test_used_catalog_items_cannot_be_removed(alice):
    rt, project, story = catalog(alice)
    tag = alice.post("/api/tags", json={"name": "تگ", "report_type_id": rt, "story_id": story})
    assert tag.status_code == 201
    for kind, row_id in (("report-types", rt), ("projects", project), ("stories", story)):
        assert alice.delete(f"/api/catalog/{kind}/{row_id}").status_code == 409


def test_database_rejects_cross_account_catalog_and_tag_links(alice, bob):
    rt, project, story = catalog(alice)
    uid = sql("SELECT id FROM users WHERE username='bob'")[0]["id"]
    tag = bob.post("/api/tags", json={"name": "بوب"}).get_json()["id"]
    foreign_tag = alice.post("/api/tags", json={"name": "آلیس"}).get_json()["id"]
    task = bob.post("/api/tasks", json={"title": "بوب"}).get_json()["id"]
    planned = bob.post("/api/planned", json={"title": "بوب"}).get_json()["id"]
    statements = [
        ("UPDATE tags SET report_type_id=:value WHERE id=:id", rt, tag),
        ("UPDATE tags SET story_id=:value WHERE id=:id", story, tag),
        ("UPDATE tasks SET report_type_id=:value WHERE id=:id", rt, task),
        ("UPDATE tasks SET tag_id=:value WHERE id=:id", foreign_tag, task),
        ("UPDATE planned_tasks SET tag_id=:value WHERE id=:id", foreign_tag, planned),
    ]
    for statement, value, row_id in statements:
        with pytest.raises(IntegrityError):
            sql(statement, value=value, id=row_id)
    with pytest.raises(IntegrityError):
        sql("INSERT INTO stories (user_id, project_id, name) VALUES (:uid, :pid, 'wrong')", uid=uid, pid=project)


def test_catalog_validation_and_anonymous_access(alice):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/catalog").status_code == 401
        assert anonymous.post("/api/catalog/projects", json={"name": "x"},
                              headers={"X-Requested-With": "timelog"}).status_code == 401
    for payload in ({"name": ""}, {"name": 12}, {"name": "x" * 151}):
        assert alice.post("/api/catalog/projects", json=payload).status_code == 400
    assert alice.post("/api/catalog/import", json={"projects": {"x": "bad"}}).status_code == 400

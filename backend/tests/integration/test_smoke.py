from tests.support import sql


def test_health_and_login_required(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/me").get_json()["username"] == "alice"


def test_task_roundtrip(client):
    t = client.post("/api/tasks", json={"title": "کار اول"}).get_json()
    assert t["status"] == "running"
    t = client.post(f"/api/tasks/{t['id']}/stop").get_json()
    assert t["status"] == "done" and t["duration_minutes"] is not None
    assert sql("SELECT count(*) c FROM task_segments")[0]["c"] == 1

from datetime import timedelta

from conftest import Client, login_as, make_user, sql
from app import auth
from app.timeutil import now_local


def test_login_logout_and_cookie_flags(alice):
    assert alice.get("/api/me").status_code == 200
    r = Client().post("/api/auth/login", json={"username": "alice", "password": "password123"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert alice.post("/api/auth/logout").status_code == 200
    assert alice.get("/api/me").status_code == 401


def test_anonymous_cannot_use_the_api():
    c = Client()
    for url in ("/api/tasks", "/api/tags", "/api/presence", "/api/settings", "/api/export"):
        assert c.get(url).status_code == 401, url


def test_wrong_password_and_unknown_user_look_the_same():
    make_user("alice")
    a = Client().post("/api/auth/login", json={"username": "alice", "password": "wrong-pass"})
    b = Client().post("/api/auth/login", json={"username": "nobody", "password": "wrong-pass"})
    assert a.status_code == b.status_code == 401
    assert a.get_json() == b.get_json()


def test_username_is_case_insensitive():
    make_user("alice")
    assert Client().post("/api/auth/login", json={"username": " Alice ", "password": "password123"}).status_code == 200


def test_lockout_after_three_failures_even_with_the_right_password(monkeypatch):
    make_user("alice")
    c = Client()
    for _ in range(3):
        assert c.post("/api/auth/login", json={"username": "alice", "password": "bad-password"}).status_code == 401
    r = c.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert "دقیقه" in r.get_json()["error"]
    # 21 minutes later it works again
    later = now_local() + timedelta(minutes=21)
    monkeypatch.setattr(auth, "now_local", lambda: later)
    assert c.post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 200


def test_two_failures_then_success_resets_the_counter():
    make_user("alice")
    c = Client()
    for _ in range(2):
        c.post("/api/auth/login", json={"username": "alice", "password": "bad-password"})
    assert c.post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 200
    for _ in range(2):
        assert c.post("/api/auth/login", json={"username": "alice", "password": "bad-password"}).status_code == 401


def test_lockout_is_per_username():
    make_user("alice")
    make_user("bob")
    c = Client()
    for _ in range(3):
        c.post("/api/auth/login", json={"username": "alice", "password": "bad-password"})
    assert c.post("/api/auth/login", json={"username": "bob", "password": "password123"}).status_code == 200


def test_ip_lockout_after_ten_failures():
    make_user("alice")
    c = Client()
    for i in range(10):
        c.post("/api/auth/login", json={"username": f"user{i}", "password": "bad-password"})
    r = c.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert r.status_code == 429


def test_expired_session_is_rejected(alice):
    sql("UPDATE sessions SET expires_at = now() - interval '1 minute'")
    assert alice.get("/api/me").status_code == 401


def test_inactive_user_cannot_log_in_or_keep_a_session(alice):
    sql("UPDATE users SET is_active = false WHERE username = 'alice'")
    assert alice.get("/api/me").status_code == 401
    assert Client().post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 401


def test_change_password_drops_other_sessions(alice):
    other = login_as("alice")
    r = alice.post("/api/me/password", json={"old": "password123", "new": "another-pass-1"})
    assert r.status_code == 200
    assert other.get("/api/me").status_code == 401           # other device logged out
    assert alice.get("/api/me").status_code == 200           # this one stays
    assert Client().post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 401
    assert login_as("alice", "another-pass-1")


def test_change_password_checks_old_and_length(alice):
    assert alice.post("/api/me/password", json={"old": "nope-nope-1", "new": "another-pass-1"}).status_code == 400
    assert alice.post("/api/me/password", json={"old": "password123", "new": "short"}).status_code == 400


def test_password_is_hashed_and_token_not_stored_plain(alice):
    assert sql("SELECT password_hash FROM users")[0]["password_hash"].startswith("$argon2")
    token = alice.http.cookies.get("tl_session")
    assert token != sql("SELECT token_hash FROM sessions")[0]["token_hash"]


def test_csrf_header_required_for_writes(alice):
    from fastapi.testclient import TestClient
    from app.main import app
    raw = TestClient(app, client=("127.0.0.1", 1))
    raw.cookies.set("tl_session", alice.http.cookies.get("tl_session"))
    assert raw.post("/api/tasks", json={"title": "x"}).status_code == 403
    assert raw.get("/api/tasks").status_code == 200       # reads need no header
    assert raw.post("/api/tasks", json={"title": "x"}, headers={"X-Requested-With": "timelog"}).status_code == 201


def test_admin_only_routes(alice, admin):
    assert alice.get("/api/admin/users").status_code == 403
    assert alice.post("/api/admin/users", json={"username": "friend"}).status_code == 403
    assert admin.get("/api/admin/users").status_code == 200


def test_admin_creates_user_who_can_log_in(admin):
    r = admin.post("/api/admin/users", json={"username": "Friend1", "display_name": "دوست"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["username"] == "friend1" and body["temp_password"]
    assert login_as("friend1", body["temp_password"]).get("/api/me").get_json()["is_admin"] is False
    assert admin.post("/api/admin/users", json={"username": "friend1"}).status_code == 409
    assert admin.post("/api/admin/users", json={"username": "bad name"}).status_code == 400


def test_admin_deactivate_and_reset_password(admin, bob):
    uid = sql("SELECT id FROM users WHERE username='bob'")[0]["id"]
    assert admin.put(f"/api/admin/users/{uid}", json={"is_active": False}).status_code == 200
    assert bob.get("/api/me").status_code == 401
    admin.put(f"/api/admin/users/{uid}", json={"is_active": True})
    temp = admin.post(f"/api/admin/users/{uid}/reset-password").get_json()["temp_password"]
    assert login_as("bob", temp)


def test_admin_cannot_lock_themselves_out(admin):
    me = admin.get("/api/me").get_json()["id"]
    assert admin.put(f"/api/admin/users/{me}", json={"is_active": False}).status_code == 400
    assert admin.put(f"/api/admin/users/{me}", json={"is_admin": False}).status_code == 400

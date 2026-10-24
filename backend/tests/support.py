"""Shared integration clients, account setup and SQL assertions."""
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import engine
from app.main import app

HEADERS = {"X-Requested-With": "timelog"}

class Resp:
    """Response with the Flask-style helpers the ported tests use."""

    def __init__(self, r):
        self._r = r

    def get_json(self):
        return self._r.json()

    @property
    def data(self):
        return self._r.content

    def __getattr__(self, name):
        return getattr(self._r, name)

class Client:
    """Logged-in test client: same-origin header always sent, `json=` bodies, `get_json()` on responses."""

    def __init__(self, username=None):
        self.http = TestClient(app, headers=HEADERS, client=("127.0.0.1", 50000))
        self.username = username

    def _call(self, method, url, **kw):
        qs = kw.pop("query_string", None)
        if qs is not None:
            kw["params"] = qs
        return Resp(self.http.request(method, url, **kw))

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)

    def put(self, url, **kw):
        return self._call("PUT", url, **kw)

    def delete(self, url, **kw):
        return self._call("DELETE", url, **kw)

def sql(query, **params):
    """Run SQL against the test database (setup and assertions)."""
    with engine.begin() as conn:
        result = conn.execute(text(query), params)
        return [dict(r) for r in result.mappings().all()] if result.returns_rows else None

def make_user(username, password="password123", admin=False):
    uid = sql("INSERT INTO users (username, password_hash, display_name, is_admin) "
              "VALUES (:u, :h, :u, :a) RETURNING id", u=username, h=hash_password(password), a=admin)[0]["id"]
    return uid

def login_as(username, password="password123"):
    c = Client(username)
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c

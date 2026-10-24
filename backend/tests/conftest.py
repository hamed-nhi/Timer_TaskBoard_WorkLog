import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
# the test database: never the dev or production one
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://timelog:timelog@localhost:5442/timelog_test")
os.environ["COOKIE_SECURE"] = "false"

import pytest                                    # noqa: E402
from alembic import command                      # noqa: E402
from alembic.config import Config                # noqa: E402
from fastapi.testclient import TestClient        # noqa: E402
from sqlalchemy.engine import make_url
from sqlalchemy import text                      # noqa: E402

from app.auth import hash_password               # noqa: E402
from app.config import settings                  # noqa: E402
from app.db import engine                       # noqa: E402
from app.main import app                         # noqa: E402

HEADERS = {"X-Requested-With": "timelog"}


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Build the schema with the real migrations, so they are what gets tested."""
    database = make_url(settings.database_url).database or ""
    if not database.endswith("_test"):
        raise RuntimeError("Refusing destructive test setup: database name must end with _test")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["url"] = settings.database_url
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, report_types, projects, login_attempts RESTART IDENTITY CASCADE"))


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


@pytest.fixture()
def alice():
    make_user("alice")
    return login_as("alice")


@pytest.fixture()
def bob():
    make_user("bob")
    return login_as("bob")


@pytest.fixture()
def admin():
    make_user("boss", admin=True)
    return login_as("boss")


@pytest.fixture()
def client(alice):
    """The default single user of most tests."""
    return alice


@pytest.fixture(autouse=True)
def overlap_check_off(request, monkeypatch):
    """Most tests stack many tasks at the same clock time on purpose; the no-overlap rule has its own
    tests, which mark themselves `strict` to keep the real check."""
    if "strict" in request.keywords:
        return
    from app.routers import planned, tasks
    for module in (tasks, planned):
        monkeypatch.setattr(module, "assert_no_overlap", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def no_day_off(monkeypatch):
    """Fill tests must not depend on the weekday they run on (Friday blocks suggestions)."""
    from app.routers import fill
    monkeypatch.setattr(fill, "FILL_DAY_OFF", None)

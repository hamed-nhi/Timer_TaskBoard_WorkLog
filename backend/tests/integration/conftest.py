"""Real PostgreSQL fixtures, scoped to integration tests only."""
from pathlib import Path
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from tests.support import Client, login_as, make_user
from tests.database_safety import disposable_database

BACKEND = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="session", autouse=True)
def schema():
    """Build the schema with the real migrations, so they are what gets tested."""
    disposable_database(os.environ.get("TEST_DATABASE_URL"))
    if settings.database_url != os.environ["TEST_DATABASE_URL"]:
        raise RuntimeError("Application/test database configuration differs; refusing schema reset")
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
    from app.services import planned, tasks
    for module in (tasks, planned):
        monkeypatch.setattr(module, "assert_no_overlap", lambda *a, **k: None)

@pytest.fixture(autouse=True)
def no_day_off(monkeypatch):
    """Fill tests must not depend on the weekday they run on (Friday blocks suggestions)."""
    from app.services import fill
    monkeypatch.setattr(fill, "FILL_DAY_OFF", None)

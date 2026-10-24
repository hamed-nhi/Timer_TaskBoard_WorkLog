"""Configure test environment before importing application modules."""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://timelog:timelog@localhost:5442/timelog_test")
os.environ["COOKIE_SECURE"] = "false"

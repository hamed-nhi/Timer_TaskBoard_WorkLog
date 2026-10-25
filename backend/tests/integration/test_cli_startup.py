"""Exercise the migration CLI without the test runner's injected import path."""
import os
from pathlib import Path
import subprocess
import sys


def test_alembic_cli_resolves_app_from_an_unrelated_directory(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(backend / "alembic.ini"), "current"],
        cwd=tmp_path, env=os.environ.copy(), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "0002" in result.stdout

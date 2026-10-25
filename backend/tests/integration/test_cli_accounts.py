"""CLI account provisioning and targeted catalog import acceptance."""
import json

import pytest

from app import cli
from tests.support import Client, login_as, sql


def test_cli_create_and_reset_account(monkeypatch):
    monkeypatch.setattr(cli, "ask_password", lambda: "qa-cli-password-1")
    cli.main(["create-user", "qa_cli", "--admin", "--display-name", "کاربر CLI"])
    user = login_as("qa_cli", "qa-cli-password-1")
    assert user.get("/api/me").get_json()["is_admin"] is True
    monkeypatch.setattr(cli, "ask_password", lambda: "qa-cli-password-2")
    cli.main(["reset-password", "qa_cli"])
    assert user.get("/api/me").status_code == 401
    assert login_as("qa_cli", "qa-cli-password-2").get("/api/me").status_code == 200


def test_cli_duplicate_user_does_not_overwrite_account(alice, monkeypatch):
    before = sql("SELECT password_hash FROM users WHERE username='alice'")[0]["password_hash"]
    monkeypatch.setattr(cli, "ask_password", lambda: "qa-duplicate-password")
    with pytest.raises(SystemExit):
        cli.main(["create-user", "alice"])
    assert sql("SELECT password_hash FROM users WHERE username='alice'")[0]["password_hash"] == before
    assert alice.get("/api/me").status_code == 200


def test_cli_catalog_import_is_private_and_repeatable(alice, bob, tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"types": ["CLI خصوصی"], "projects": {"پروژه CLI": ["استوری CLI"]}}), encoding="utf-8")
    for _ in range(2):
        cli.main(["import-catalog", str(path), "--user", "alice"])
    assert len(alice.get("/api/catalog").get_json()["projects"]) == 1
    assert bob.get("/api/catalog").get_json() == {"types": [], "projects": []}

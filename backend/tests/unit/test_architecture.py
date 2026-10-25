"""Guard dependency direction and HTTP contracts during future refactors."""
import ast
import importlib.util
import json
from pathlib import Path

from app.main import app, create_app

APP = Path(__file__).resolve().parents[2] / "app"


def imported_modules(path):
    relative = path.relative_to(APP).with_suffix("").parts
    package = ".".join(("app", *relative[:-1]))
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            yield importlib.util.resolve_name(name, package) if node.level else name


def test_dependency_direction_keeps_business_rules_independent_of_http():
    forbidden = {
        "core": ("app.api", "app.db", "app.services", "fastapi", "starlette", "sqlalchemy"),
        "db": ("app.api", "app.services", "fastapi", "starlette"),
        "services": ("app.api", "app.main", "fastapi", "starlette"),
    }
    for layer, prefixes in forbidden.items():
        for path in (APP / layer).rglob("*.py"):
            for module in imported_modules(path):
                assert not any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes), (
                    path.relative_to(APP), module)


def test_http_routes_do_not_execute_database_operations():
    for path in (APP / "api" / "routes").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"execute", "insert", "commit", "rollback", "lock_user"}, path.name


def test_public_paths_parameters_and_bodies_match_pre_refactor_contract():
    baseline = Path(__file__).resolve().parents[1] / "fixtures" / "api_contract.json"
    expected = json.loads(baseline.read_text(encoding="utf-8"))
    actual = {
        path: {method: {key: operation[key] for key in ("parameters", "requestBody") if key in operation}
               for method, operation in methods.items()}
        for path, methods in app.openapi()["paths"].items()
    }
    extension = json.loads(baseline.with_name("import_contract.json").read_text(encoding="utf-8"))
    additions = extension["paths"]
    assert {name: app.openapi()["components"]["schemas"][name] for name in extension["schemas"]} == extension["schemas"]
    assert set(actual) == set(expected) | set(additions)
    assert {path: actual[path] for path in expected} == expected
    assert {path: actual[path] for path in additions} == additions


def test_application_factory_builds_independent_equivalent_apps():
    other = create_app()
    assert other is not app
    assert other.openapi() == app.openapi()
    assert len(other.user_middleware) == len(app.user_middleware) == 1

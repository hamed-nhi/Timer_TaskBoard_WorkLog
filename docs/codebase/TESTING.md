# Testing Patterns

## Stack and commands
pytest 9.1.1, FastAPI TestClient/httpx and real PostgreSQL integration tests.
From backend:
- python -m pytest -q tests/unit: architecture, API request contract and application factory; no DB needed.
- python -m pytest -q tests/integration: API behavior, sessions, ownership, time logic, exports and migrations.
- python -m pytest -q: both suites.
From frontend: npm.cmd run lint; npm.cmd run build.

## Layout and isolation
Root conftest configures environment before application imports, but does not connect/drop schema.
integration/conftest owns schema/reset/account fixtures. TEST_DATABASE_URL must point to a disposable DB ending in _test; setup recreates public schema and cleanup truncates test records.
tests/support.py owns clients and SQL/setup helpers. Unit tests were verified with an unavailable database endpoint to prove they do not need PostgreSQL.
Integration overlap checks are patched off by default except strict tests; Friday behavior has a dedicated case.

## Regression guards
fixtures/api_contract.json records the pre-refactor 57 public paths and their parameter/body definitions. Unit tests compare the current OpenAPI request contract against it, guard import direction and prevent SQL/commit in routes.
Factory tests verify a new app has equivalent schema and one middleware registration.
Existing integration tests cover private catalogs, cross-owner foreign keys, lossless migration, import isolation, 90-day session renewal and logout revocation.

## CI and gaps
CI runs unit/architecture and DB integration tests in separate steps; frontend CI runs npm ci/lint/build.
[TODO] No coverage percentage/threshold, browser E2E suite or load benchmark is configured. Lint/build do not prove mobile interaction acceptance.
See HANDOFF for the latest completed command results.

## Evidence
- backend/requirements-dev.txt
- backend/pytest.ini
- backend/tests/conftest.py
- backend/tests/integration/conftest.py
- backend/tests/unit/test_architecture.py
- backend/tests/fixtures/api_contract.json
- .github/workflows/ci.yml
- frontend/package.json

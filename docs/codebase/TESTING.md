# Testing Patterns

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


## Core Sections (Required)

### 1) Test Stack and Commands
pytest==9.1.1, httpx==0.28.1 and FastAPI TestClient. Assertions are plain pytest/Python; monkeypatch controls clock and selected business checks.
From backend/: python -m pytest -q. Frontend: npm.cmd run lint; npm.cmd run build.
No separate unit/E2E/coverage scripts are declared. [TODO] Coverage tooling and measured percentage.
Do not run tests until TEST_DATABASE_URL is explicitly checked: session setup drops and recreates public schema.

### 2) Test Layout
Ten backend/tests/test_*.py modules contain 157 test_ function definitions (static rg count on 2026-10-24). conftest.py supplies schema, cleanup, users and login helpers; pytest.ini defines testpaths and strict marker.
This count is not a fresh passing-test result. HANDOFF reports 157 passing tests from earlier work; this session did not rerun them.

### 3) Test Scope Matrix
| Scope | Present | Targets / evidence |
|---|---|---|
| Helper logic through API | Yes | time edits, budget, fill arithmetic; test_tasks.py/test_fill.py |
| Integration | Yes, real PostgreSQL | auth, tenant isolation, reports, imports |
| Browser E2E | No checked-in suite found | PLAN explicitly asks only build/lint |
| UI visual/manual | Prior evidence in HANDOFF only | Mobile 360px claimed; no new browser verification |
| Deployment/recovery | Scripts available | Full compose/restoration not executed in this review |

### 4) Mocking and Isolation Strategy
conftest overwrites DATABASE_URL from TEST_DATABASE_URL or local timelog_test and disables secure cookies for tests. Schema fixture runs real Alembic migrations after DROP SCHEMA; cleanup truncates users/catalog/login_attempts with cascade and identity reset.
alice/bob/admin fixtures support access-control assertions. Default tests bypass assert_no_overlap; test_overlap.py is strict and checks the real path. Friday handling is disabled by default and explicitly exercised in a dedicated test.
Import tests create synthetic SQLite data; mismatch tests monkeypatch insertion to prove rollback.
A wrongly configured TEST_DATABASE_URL could target a non-test database: the fixture has no database-name safety assertion.

### 5) Coverage and Quality Signals
CI selects Python 3.13/Postgres 18 and Node 22, running pytest and npm ci/lint/build. No deployment step is defined.
Coverage threshold/report: [TODO]. Concurrency load, full server deployment and browser/mobile acceptance are not established by static review.
PLAN's 95% aggregate fill rule has tests; blocked-day/manual-fill consistency warrants additional targeted cases before any fix.

### 6) Evidence
- backend/requirements-dev.txt
- backend/pytest.ini
- backend/tests/conftest.py
- backend/tests/test_auth.py
- backend/tests/test_isolation.py
- backend/tests/test_overlap.py
- backend/tests/test_import.py
- backend/tests/test_fill.py
- frontend/package.json
- .github/workflows/ci.yml

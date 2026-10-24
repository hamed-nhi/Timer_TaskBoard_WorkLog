# Codebase Structure

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


## Core Sections (Required)

### 1) Top-Level Map
| Path | Purpose | Evidence |
|---|---|---|
| backend/app/ | FastAPI, SQL business logic, auth, CLI/importer | backend/app/main.py |
| backend/alembic/ | Initial schema and migration runner | backend/alembic/versions/0001_initial_schema.py |
| backend/tests/ | 157 test_ function definitions across ten test modules | backend/tests/test_tasks.py; backend/tests/conftest.py |
| frontend/app/ | RTL root, login and nine app pages | frontend/app/layout.tsx |
| frontend/components/ | Shell, forms, task/tag/presence/fill dialogs | frontend/components/shell.tsx |
| frontend/lib/ | API, SWR, types, clock and Persian formatting | frontend/lib/data.tsx |
| deploy/ | Encrypted dump, restoration trial, Windows pull | deploy/backup.sh |
| tools/ | Icon generation | tools/make_icons.py |
| docs/ | Original plan and handoff; this source-backed map | docs/PLAN.md; docs/HANDOFF.md |
| .github/ | Backend tests and frontend lint/build CI | .github/workflows/ci.yml |

venv/, .next/, out/ and tsconfig.tsbuildinfo are environment/generated artifacts, not architecture sources.

### 2) Entry Points
FastAPI: backend/app/main.py:app. CLI: python -m app.cli. Alembic: backend/alembic/env.py.
Frontend root: frontend/app/layout.tsx; protected shell via frontend/app/(app)/layout.tsx.
User routes: /, /planned/, /dashboard/, /calendar/, /timesheet/, /tasks/, /daylog/, /settings/, /admin/; /login/ sits outside the app group.
Dockerfiles and compose select production processes; backup scripts require host scheduling.

### 3) Module Boundaries
| Boundary | Owns | Constraints from current design |
|---|---|---|
| routers/ | Feature API operations and commits | User data queries scope to authenticated user |
| timecalc.py, timeutil.py | Time/segment and Jalali arithmetic | Preserve desktop-compatible naive Tehran times |
| db.py, models.py | SQL access/session and schema metadata | Db is a small SQL adapter, not a repository layer |
| components/ | Shared interaction and dialogs | Backend remains authoritative for validation |
| deploy/ | Server backup/recovery | Real data must remain protected |

### 4) Naming and Organization Rules
Python uses snake_case modules and functions, PascalCase model classes. Frontend exports PascalCase components, camelCase helpers; file names are lowercase feature names. App Router uses page.tsx/layout.tsx and a route group. Alias @/* resolves to frontend/*.
PLAN's proposed schemas.py, jalali.py, jobs/sheets_sync.py and deploy/Caddyfile do not match the current tree: validation is mostly helper-based, date helpers live in timeutil.py, Sheets job is absent and Caddyfile is in frontend/.

### 5) Evidence
- backend/app/main.py
- backend/app/deps.py
- backend/app/cli.py
- frontend/app/(app)/layout.tsx
- frontend/tsconfig.json
- frontend/components/shell.tsx
- docs/PLAN.md

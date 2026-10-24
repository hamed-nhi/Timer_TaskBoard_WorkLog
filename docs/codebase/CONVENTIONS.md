# Coding Conventions

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


## Core Sections (Required)

### 1) Naming Rules
| Item | Observed rule/example | Evidence |
|---|---|---|
| Python files/functions | snake_case: get_own_task, settings_me.py | backend/app/timecalc.py |
| Classes | PascalCase: User, ApiError, Db | backend/app/models.py; backend/app/common.py |
| React | PascalCase components, camelCase helpers | frontend/components/tasks.tsx |
| Constants/env | UPPER_SNAKE_CASE: FILL_MAX_PERCENT, DATABASE_URL | backend/app/routers/fill.py; backend/app/config.py |

### 2) Formatting and Linting
ESLint extends next/core-web-vitals and next/typescript. no-explicit-any and react-hooks/exhaustive-deps are disabled. TypeScript strict=true, noEmit=true, skipLibCheck=true. npm.cmd run lint invokes next lint.
[TODO] Verify the lint command against the installed Next CLI; no dependency install or lint execution was performed.
No standalone formatter or Python lint configuration was found in the inspected project configs.
Observed formatting: four-space Python, two-space TS, comparatively compact JSX/CSS.

### 3) Import and Module Conventions
Backend uses package-relative imports, with stdlib/external/local groups visible in auth.py and routers. Frontend uses @/ aliases plus sibling-relative component imports. There is no observed mandated import-order tool or general barrel-export policy.

### 4) Error and Logging Conventions
ApiError carries message/status/headers and is rendered as {"error": "..."}; request validation maps to 400. Input helpers validate strings and IDs; most router bodies are dicts rather than dedicated schemas.
UI generally shows Persian errors through api.ts, toast or form state. Some backend errors remain English: not found/forbidden.
No centralized structured logging/redaction implementation was found in inspected app modules. Passwords are Argon2 hashes, session tokens SHA256 digests; do not log raw credentials.
get_db rolls back uncommitted work on exit; write routers generally commit explicitly.

### 5) Testing Conventions
backend/tests/test_*.py with pytest assertions, shared Client wrapper, SQL setup/assertions and monkeypatch. Non-strict tests disable overlap checks. strict-marked overlap tests retain them. Tests normally override Friday behavior.
Coverage target is [TODO]; no configured threshold found.
Preserve actual task time during fill, use additive future migrations, never push on the user's behalf, and keep desktop/live data untouched (HANDOFF).

### 6) Evidence
- frontend/eslint.config.mjs
- frontend/tsconfig.json
- frontend/package.json
- backend/app/common.py
- backend/app/main.py
- backend/app/db.py
- backend/tests/conftest.py
- docs/HANDOFF.md

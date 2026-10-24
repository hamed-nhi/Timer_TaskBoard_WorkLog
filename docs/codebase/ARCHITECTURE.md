# Architecture

## Style and flow
A modular monolith: static Next frontend -> same-origin Caddy /api proxy -> FastAPI HTTP adapters -> application services -> PostgreSQL.
app/main.py is the composition root. api/router.py includes feature routes. API dependencies resolve authenticated users, roles and request database sessions. Services receive explicit database/user inputs and return plain data or file content.
HTTP status codes, cookies, JSON encoding and streaming headers are owned by API adapters. Services do not import FastAPI or route modules.

## Domain responsibilities
tasks/timecalc own running/paused/done lifecycles, segments, overlap and adjustments. presence owns manual check-in/out. fill owns suggestions/report-only minutes and audit rollback. tags owns budgets and merges. catalog/catalog_helpers own private catalog CRUD/import. reports owns report queries/workbook generation. settings owns goals and private JSON-export data. auth owns session persistence/rate limiting.
core/security owns password hashing and token digests; api/session serializes cookies. db/session retains the small parameterized SQL wrapper and per-user transaction locks.

## Data contracts
Time remains naive Tehran wall time. HH:MM fields remain strings. Private catalogs and composite owner foreign keys remain unchanged. Only one running task per user is allowed; a second is rejected. Fill extras remain separate from recorded minutes.
No schema migration was added for this restructuring.

## Frontend
Routes re-export feature views. AppShell composes providers and navigation; features own behavior; shared/lib remain independent of routes/features, enforced by ESLint.
Existing styling, URLs, mobile navigation and static export remain intact.

## Risks and growth
Direct SQL stays in services intentionally; there is no extra repository abstraction. Long feature modules may be split when responsibilities diverge. Scaling throughput still requires load/DB query measurement.
Existing backup and manual-fill policy concerns are described in CONCERNS.md.

## Evidence
- backend/app/main.py
- backend/app/api/dependencies.py
- backend/app/api/routes/tasks.py
- backend/app/services/tasks.py
- backend/app/services/auth.py
- backend/app/db/session.py
- backend/tests/unit/test_architecture.py
- frontend/eslint.config.mjs

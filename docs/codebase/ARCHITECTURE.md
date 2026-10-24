# Architecture

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


## Core Sections (Required)

### 1) Architectural Style
One synchronous FastAPI backend and one statically exported Next frontend, backed by PostgreSQL. Feature routers call shared helpers and parameterized SQL through Db; SQLAlchemy provides connections, sessions and schema metadata.
Constraints: private per-user data, shared admin-owned company catalog, preserving recorded time separately from report extras. Desktop source and live databases remain untouched (docs/HANDOFF.md).

### 2) System Flow
Browser -> SWR/api.ts -> same-origin /api -> Caddy -> FastAPI middleware/dependencies -> feature router -> Db/SQLAlchemy -> PostgreSQL -> JSON -> SWR refresh.
1. AppShell fetches /api/me; the API wrapper redirects on 401.
2. Writes include X-Requested-With: timelog; middleware rejects missing headers.
3. current_user hashes the session cookie and checks active user plus expiry.
4. Creating a task validates title/date/time, acquires a per-user advisory transaction lock and checks overlap.
5. The router inserts task and segment, commits, and returns the joined task representation.
6. refreshAll revalidates API cache entries except /me and /today.

### 3) Layer/Module Responsibilities
| Module | Owns | Does not own | Evidence |
|---|---|---|---|
| auth.py/deps.py | Password hashes, session lookup, roles | UI state | backend/app/auth.py |
| tasks.py/timecalc.py | running/paused/done lifecycle, segments, overlap and adjustments | Presence clock | backend/app/routers/tasks.py |
| presence.py | Manual check-in/out and needs_checkin | Implicit task start | backend/app/routers/presence.py |
| fill.py | Suggestions, report extras, rollback audit | Editing original duration | backend/app/routers/fill.py |
| reports.py | Dashboard, calendar, weekly sheets and Excel | Remote company submission | backend/app/routers/reports.py |
| importer.py | Read-only SQLite copy -> verified transaction | Desktop writes | backend/app/importer.py |

### 4) Reused Patterns
FastAPI Depends supplies shared request dependencies; Db.lock_user uses pg_advisory_xact_lock for many mutations. TASK_SELECT centralizes joins. Context providers share dialogs and a one-second clock. SWR owns remote state. audit_log stores deleted task snapshots, merges and removed fills.
No worker/queue is present. Sheets sync is described in documents but no jobs implementation exists.

### 5) Known Architectural Risks
Time is naive Tehran wall time, not PLAN's timestamptz. start/end are HH:MM strings and IDs are Integer, not the planned time/bigint schema.
Only one running task is allowed: creating/resuming/reopening while another runs raises an error. PLAN's auto-pause statement is contradicted by code and test_overlap.py.
Fill suggestion blocks Fridays and suspect presence; apply_fill ignores the returned blocked flag and enforces aggregate allowance instead. Per-task 50% caps and meeting exclusion are suggestion rules, not enforced identically for manual submissions.
Unpaginated lists and Python aggregation may become costly with long history.

### 6) Evidence
- backend/app/main.py
- backend/app/db.py
- backend/app/models.py
- backend/app/timecalc.py
- backend/app/routers/tasks.py
- backend/app/routers/fill.py
- backend/tests/test_overlap.py
- frontend/lib/api.ts
- frontend/lib/data.tsx

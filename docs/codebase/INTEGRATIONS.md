# External Integrations

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


## Core Sections (Required)

### 1) Integration Inventory
| System | Type / purpose | Auth / criticality | Evidence |
|---|---|---|---|
| PostgreSQL 18 | Persistent application data | DATABASE_URL; critical | backend/app/db.py; docker-compose.yml |
| Caddy 2 | Same-origin proxy, static site, domain HTTPS | Site configuration; critical | frontend/Caddyfile |
| SQLite desktop copy | One-time migration input | Local read-only file; optional | backend/app/importer.py |
| gpg + pg_dump | Encrypted server backups | BACKUP_PASSPHRASE; recovery-critical | deploy/backup.sh |
| SSH/scp and local Drive folder | Copies server backups to Windows | SSH configuration outside script | deploy/pull_backup.ps1 |
| Google Sheets | URL storage only, sync absent | No implemented service-account flow | backend/app/routers/settings_me.py |
| Package registries | Image/npm/pip acquisition | Mirror settings | Dockerfiles; .env.example |

No implemented company-story scraper was found; HANDOFF marks it pending. calendar_events.py contains local event data and approximate fallback logic, not a runtime calendar web call.

### 2) Data Stores
PostgreSQL holds users, sessions, login attempts, report_types/projects/stories, tags, tasks, task_segments, planned_tasks, presence_segments, user_settings and audit_log.
task_segments belongs to a user through its parent task. Shared catalog has no user_id. User JSON export includes owned records but not a shared-catalog snapshot.
SQLite importer refuses the exact filename tasklog.db, opens URI mode=ro, verifies counts and minute sums, then commits or rolls back. It does not itself create the source copy.

### 3) Secrets and Credentials Handling
Root env template contains placeholders. .gitignore excludes .env, database files, dumps and backups. Settings read environment; .env.example is configuration documentation, not a secret store.
Backup passphrase is passed as a gpg command argument rather than PLAN's passphrase-file approach.
[TODO] Actual secret provisioning/rotation and SSH key setup are outside the inspected repository.

### 4) Reliability and Failure Behavior
Database uses pool_pre_ping. Compose gates API start on database health and uses unless-stopped restarts. Startup applies Alembic before uvicorn.
No explicit fetch timeout/circuit breaker exists in api.ts; SWR refresh intervals are defined in data.tsx.
Backup pipeline uses sh set -eu without pipefail; a failed dump can be hidden by successful encryption of its empty input. Restore script also pipes without full upstream error propagation.
Current weekly backup is Sunday (date +%u = 7), while PLAN says Friday. No latest symlink or Windows 30-copy retention is implemented.

### 5) Observability for Integrations
Scripts emit basic success/error/count text; no metrics/tracing integration was found in inspected configs. /api/health returns a static ok without testing the DB.
[TODO] Real server access to registries/Google and successful full backup restoration remain unverified in this review.

### 6) Evidence
- docker-compose.yml
- frontend/Caddyfile
- backend/app/db.py
- backend/app/importer.py
- backend/app/routers/settings_me.py
- backend/app/routers/settings_me.py (my_backup)
- deploy/backup.sh
- deploy/restore_test.sh
- deploy/pull_backup.ps1
- .gitignore

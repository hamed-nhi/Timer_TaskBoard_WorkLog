# External Integrations

## Inventory
PostgreSQL 18 is the persistent store via app/db/session.py. Caddy provides static files, HTTPS for configured domains and /api proxying. The importer reads a SQLite copy in mode=ro and writes one verified PostgreSQL transaction.
pg_dump/gpg create encrypted backups; scp copies server backups to the user's Windows folder. Google Sheets is URL storage only; a synchronization job and company-story scraper are still absent.

## Ownership and secrets
Catalogs, tasks, tags, plans, presence, settings and exports are account-private. Personal JSON export includes the account's catalog.
Configuration comes from environment/.env; .gitignore excludes credentials/dumps/backups. Backup passphrase is currently passed as a gpg argument.
[TODO] Server secret rotation, Google connectivity, SSH configuration and real deployment verification remain external operational work.

## Reliability
SQLAlchemy uses pool_pre_ping, Compose waits for DB health, API startup applies Alembic, and restart policy is unless-stopped. Session renewal remains in PostgreSQL and cookies.
The API wrapper has no explicit request timeout/circuit breaker. /api/health is a static process liveness response, not a DB readiness check.
Backup pipelines have the existing status-propagation limitation recorded in CONCERNS.md. No backup scripts were changed during restructuring.

## Observability
Scripts emit basic success/error text; no metrics/tracing platform is configured in the inspected sources. No production load benchmark was run.

## Evidence
- backend/app/db/session.py
- backend/app/services/importer.py
- backend/app/services/settings.py
- backend/app/api/routes/reports.py
- docker-compose.yml
- frontend/Caddyfile
- deploy/backup.sh
- deploy/restore_test.sh
- deploy/pull_backup.ps1

# TIME LOG

A self-hosted, multi-user work-time tracker with a Persian RTL interface and Jalali calendar. Track tasks, attendance, plans and reports from a desktop browser or phone.

**Stack:** FastAPI · PostgreSQL 18 · Next.js 15 / React 19 · Caddy · Docker Compose.

## Features

- Start, pause, resume and finish tasks; edit recorded times and view work segments.
- Record attendance separately from task time, with warnings for past days whose task totals exceed attendance.
- Keep personal tags, report types, projects and stories. Administrators manage accounts; personal records and catalogs remain private to their owners.
- View daily, monthly and weekly reports, a Jalali calendar and Excel exports.
- Use a responsive interface with light, dark and device-based themes.
- Stay signed in across browser restarts using renewable, HttpOnly sessions. Use the same account on multiple devices.
- Preview and import completed task history from Excel (`.xlsx`) or CSV. Download templates and conversion instructions from **Settings**.
- Download personal JSON backups. Optional backup jobs retain immutable versions and synchronize source changes to a private Google Sheet.

TIME LOG requires a network connection. Its installable web manifest does not provide offline storage or background synchronization.

## Quick start with Docker

Install Docker Engine or Docker Desktop with Docker Compose v2. Then:

```sh
git clone https://github.com/hamed-nhi/workload.git
cd workload
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.

Edit `.env` before starting:

| Variable | Purpose |
| --- | --- |
| `DB_PASSWORD` | A strong, unique PostgreSQL password. Use a URL-safe value. |
| `BACKUP_PASSPHRASE` | A separate encryption passphrase. Keep a recovery copy securely outside the server. |
| `SITE_ADDRESS` | `:80` for local HTTP, or your domain name for automatic HTTPS. |
| `HTTP_PORT` | Local HTTP port; defaults to `80`. |
| `COOKIE_SECURE` | Leave empty to follow the request scheme; use `true` when HTTPS terminates upstream. |

Start the services and create the first administrator:

```sh
docker compose up -d --build
docker compose exec api python -m app.cli create-user admin --admin
```

The command prompts for a password; there is **no default administrator password**. Open `http://localhost` for local use, or your configured HTTPS domain. For automatic HTTPS, point the domain at the server and make ports 80 and 443 reachable.

The administrator can create accounts in **Management**. Every signed-in user has a separate Management section for their own report types, projects and stories.

PostgreSQL data persists in the `pgdata` named volume. Caddy certificate state persists in `caddy_data`. Do not remove those volumes when upgrading.

## Import existing task history

Open **Settings → Import history from Excel or CSV**.

1. Download the Excel/CSV template. A separate text guide can be given to a model or used to convert another application's export.
2. Replace the example row with your actual records. Keep the source file unchanged as a reference.
3. Select the file and preview it. For different column names, adjust the column mapping and preview again.
4. Resolve every row error, review the totals and confirm the import.

Dates accept full Jalali `1405/08/03` or Gregorian `2026-10-25` values. Persian digits are supported. Times use `HH:MM`; durations are **minutes**, including fractional minutes. A duration may differ from the start/end interval, for example when the original task included pauses; the recorded duration is preserved.

Native TIME LOG workbooks are recognized automatically, including their year-bearing worksheet names. For month/day-only dates in another file, supply the Jalali year explicitly. Files may contain up to 5 MB and 5,000 data rows. Convert legacy `.xls` files to `.xlsx`, and replace formulas with their values first.

Imports are private to the signed-in account and transactional: a file with row errors imports nothing. Exact duplicates are skipped, and existing records are never overwritten. Uploading a changed record adds a separate record; it does not replace the original. The preview must still match the file and account state when confirmed.

This format transfers **completed tasks**, their recorded durations, separate report-only extra minutes, tags and catalog labels. It does not reconstruct attendance, pause segments or future plans that are absent from a task export. Do not treat a task spreadsheet as a full database backup.

### Full desktop database migration

The administrator can also migrate a **copy** of the original desktop SQLite database into an empty account. The original desktop source and live database must remain untouched.

```sh
# Create desktop_copy.db outside the live desktop application first.
docker compose cp desktop_copy.db api:/tmp/desktop_copy.db
docker compose exec api python -m app.cli import-desktop /tmp/desktop_copy.db --user alice --dry-run
# Review record counts and minute totals; then run again without --dry-run.
```

The importer reads the copy in read-only mode and verifies counts and sums before committing. The destination account must be empty. No desktop database is included in this repository.

## Multiple devices and sessions

Sign in to the same server URL on your phone and computer. Each browser has its own server-side session; signing in on one device does not sign out another. Active pages periodically refresh server data, and refocus/reconnection triggers refreshes. An open page is not an offline copy.

A session cookie lasts 90 days and renews with activity, at most once an hour. Passwords are not saved by the application in browser storage. Logout revokes the current session; changing a password revokes the other sessions. Clearing cookies, expiry or administrator revocation requires signing in again.

A phone's `localhost` refers to the phone itself. Use the server's reachable domain or LAN address on both devices, with HTTPS for deployment.

## Backups and recovery

### Encrypted database backups

Run `deploy/backup.sh` from a scheduled job on the Linux host. It validates `pg_dump`, encrypts it with GPG/AES256 and only then publishes the archive. It retains 14 daily and 8 weekly copies. GPG must be installed on that host.

```sh
./deploy/backup.sh
./deploy/restore_test.sh
```

The restore check decrypts the latest archive, restores it into a newly created temporary database, verifies it and removes that temporary database. A failed dump, decryption or restore returns a nonzero exit status. Regularly test recovery and keep an encrypted copy outside the server. `deploy/pull_backup.ps1` can retrieve backups to a Windows backup location.

### Versioned personal backups and optional Sheets sync

```sh
docker compose --profile backup build personal-backup
docker compose --profile backup run --rm personal-backup
```

Schedule this job externally if daily runs are required; Compose does not install a scheduler. It writes private per-user JSON/Excel snapshots under `backups/personal`. Unchanged source data creates no new snapshot; changed source data creates a new version and preserves the previous one.

Google Sheets sync is optional. Create a separate sheet for each account, share it with the service account as an editor, mount its credentials read-only under `secrets/`, set `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sheets.json`, and save the personal sheet URL in Settings. The job updates only source-changed tasks; unchanged source records do not overwrite manual sheet edits. Source deletions are marked while retaining the old backup row. Do not share one destination between accounts.

Never commit `.env`, credentials, backup files or database dumps.

## Local development

Requirements: Python 3.13+, Node.js 22+, Docker and PostgreSQL 18.

```sh
docker compose -f docker-compose.dev.yml up -d
python -m venv venv
# Activate venv: source venv/bin/activate (POSIX), or .\venv\Scripts\Activate.ps1 (PowerShell)
python -m pip install -r backend/requirements-dev.txt
```

Set the backend environment for the development database:

```sh
# POSIX shell
export DATABASE_URL='postgresql+psycopg://timelog:timelog@127.0.0.1:5442/timelog'
export COOKIE_SECURE=false
```

```powershell
# PowerShell
$env:DATABASE_URL='postgresql+psycopg://timelog:timelog@127.0.0.1:5442/timelog'
$env:COOKIE_SECURE='false'
```

```sh
cd backend
alembic upgrade head
python -m app.cli create-user admin --admin
uvicorn app.main:app --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. Next.js proxies `/api` to the local backend during development; production serves the static export through Caddy. On PowerShell use `npm.cmd` if script execution policy blocks `npm.ps1`.

The PostgreSQL base-image mirror, npm registry and Python index can be configured through `DOCKER_REGISTRY`, `NPM_REGISTRY` and `PIP_INDEX_URL` when required. Other pinned build images must remain reachable through your Docker registry configuration. Use trusted mirrors; the default build uses the public upstream registries.

## Tests

Fast tests require no database:

```sh
cd backend
python -m pytest -q tests/unit
```

Integration tests **recreate the public schema**. Create and explicitly select a disposable database whose name ends in `_test`; never use a development, audit-browser or production database.

```sh
docker compose -f docker-compose.dev.yml exec db createdb -U timelog timelog_test
```

Set `TEST_DATABASE_URL=postgresql+psycopg://timelog:timelog@127.0.0.1:5442/timelog_test` in your shell, then:

```sh
cd backend
python -m pytest -q tests/integration
python -m pytest -q tests/operational  # Requires Docker for fault-injected backup-script tests.
```

Frontend checks:

```sh
cd frontend
npm run lint
npm run build
```

The isolated browser/recovery/load environment uses the `audit` profile in `docker-compose.test.yml`, web port **18082**, database port **5544**, and its own persistent volume. Its seed/reset tools refuse to reset the existing demo on port 18081. See [the QA runbook](docs/testing/AUDIT_RUNBOOK.md) for exact commands, role fixtures, evidence locations and limitations. Failed, skipped and unexecuted checks are reported separately.

## Architecture and upgrades

- `backend/app/api`: HTTP contracts, authentication dependencies and serialization.
- `backend/app/services`: business rules, ownership checks and transactions.
- `backend/app/db`: schema and PostgreSQL adapter.
- `backend/app/core`: configuration, security and time primitives.
- `frontend/src/features`: feature views and dialogs; `shared` and `lib` hold independent reusable code.
- `deploy`, `tools`, `docs`: operations, QA utilities and documentation.

See [Architecture](docs/ARCHITECTURE.md), [operational handoff](docs/HANDOFF.md) and [contribution rules](AGENTS.md). Existing detailed design documents are primarily in Persian.

Before upgrading a real database, create and verify a backup. Add migrations instead of rewriting existing migrations. Docker applies migrations when starting the API. Migration `0002` separates previously shared catalogs by owner while preserving recorded times and legacy rows.

Security and performance test results describe the tested environment; they are not a production capacity or security certification. Real Google Sheets, HTTPS deployment and physical-device compatibility require their own configured environments.

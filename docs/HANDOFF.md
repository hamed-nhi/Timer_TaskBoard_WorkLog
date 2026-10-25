# HANDOFF — TIME LOG web

Project context as of 2026-10-25. Read [ARCHITECTURE.md](ARCHITECTURE.md) for the layout. PLAN.md records the original design; newer decisions in this handoff take precedence. Local contributor instructions may supplement these documents but are not required to deploy the application.

## Product and decisions

TIME LOG tracks time, tasks, plans, manual attendance and Jalali reports through a responsive Persian RTL interface. It uses FastAPI and PostgreSQL 18, Next.js 15 and React 19 with a static export, and Caddy.

Report types, projects and stories are private to each account. Every user has a Management page for their own catalog; only administrators manage accounts. Administrators cannot read other users' catalogs or activities through the API.

Authentication uses usernames/passwords, PostgreSQL sessions and an HttpOnly cookie. Sessions default to 90 days and renew with activity at most once an hour. Empty COOKIE_SECURE follows the request scheme; an explicit value takes precedence. Opening login with a valid session redirects to the application.

Backend login bans apply to an IP/account pair: three failures trigger 15 minutes, then 10 hours, then 30 days. Three unknown usernames trigger a 24-hour IP ban. Administrators configure and release bans through the UI; see [DEPLOY.md](../DEPLOY.md). Changing a password invalidates other sessions.

Attendance is manual. There is no offline mode or service worker. The PWA manifest only supports adding the application to a home screen.

## Work and data rules

- Keep user-facing communication concise and in Persian, and state material verification/deployment limits.
- The desktop source at `C:\Users\hnahali\Documents\Folder\Hamed-stuff\time-sys` is read-only and must remain untouched.
- Never open the live tasklog.db for writes or tests. The importer reads a copy with `mode=ro`.
- Report fill must not change original task times; `fill_minutes` is separate. Preserve real data.
- Test only on dedicated databases or copies. Verify a backup before intentional real-data migrations. A previous desktop backup location was `C:\TimeLogBackups\before_<what>_<ts>.db`.
- Add migrations rather than rewriting existing ones.
- Never commit .env, secrets, databases or dumps.
- Commit complete, tested changes locally without automatic model attribution. Publishing requires the owner's authorization; this handoff does not grant it by itself.

## Current structure

- app/main.py only composes create_app and the application; app.main:app stays stable.
- app/api/routes owns Body/Query input, dependencies and HTTP responses; SQL and commits are forbidden there.
- app/api/dependencies resolves request users, roles and database access. Middleware, exception_handlers and session handle response/cookie behavior.
- app/services owns business rules and transactions; it must not import FastAPI or app/api. Reuse plain functions without unnecessary Repository/Interface layers.
- app/db/session.py provides Db and Session; app/db/models.py defines models.
- app/core owns configuration, errors, password/token hashing and time; it does not depend on API/services/DB.
- frontend/src/app owns routes/layouts; page.tsx files export feature views.
- frontend/src/features owns feature code; components/app-shell.tsx composes providers and navigation. shared and lib are independent of features.
- Database-independent tests live in tests/unit; API/PostgreSQL tests in tests/integration. Shared helpers live in tests/support.py; do not import conftest.
- tests is a package. The old restriction against tests/__init__.py no longer applies; direct imports from conftest were removed.
- The structural refactor preserved public API/page URLs and changed neither migrations nor real data.

## Important contracts

Times are naive Tehran wall-clock values: timestamps have no timezone and start/end are HH:MM strings. now_local uses Asia/Tehran.

Filter all personal data by user_id. task_segments inherit ownership from the task. Other users' identifiers generally return 404; deleting their task/plan/attendance remains a no-op.

Manage the personal catalog through /api/catalog and read its selection list through /api/company-catalog. Composite constraints reject tags/types/stories from another account.

Starting a second task while one is running is rejected; no automatic pause occurs. Multiple paused tasks are allowed. Db.lock_user uses pg_advisory_xact_lock.

Fill rules: maximum target 95%, each task capped at 50% of its own time, five-minute steps, trusted attendance capped at 660 minutes, assumed 30-minute lunch after six uninterrupted hours, and no Friday suggestion. Positive fill in a blocked state is rejected; original time is unchanged.

Audit events include task_deleted, fill_rollback and tag_merge.

## Migrations and data import

0001 is the initial schema. 0002 copies each user's related catalog records and redirects task/tag/archive references without changing time or attendance.

Legacy shared records are retained without an owner and hidden from the API. Unrelated records with no identifiable owner are not assigned automatically.

At the catalog-refactor stage, 0002 had only been tested on disposable databases. Any real upgrade requires a verified backup followed by alembic upgrade head. Later authorized local upgrades are recorded below.

CLI:

- `python -m app.cli create-user <username> --admin`
- `python -m app.cli reset-password <username>`
- `python -m app.cli import-catalog catalog.json --user <username>`
- `python -m app.cli import-desktop <copy.db> --user <username> --dry-run`

## Running and validating

Development PostgreSQL: `docker compose -f docker-compose.dev.yml up -d`, port 5442.
Backend from backend: `..\venv\Scripts\python -m uvicorn app.main:app --port 8000`.
Frontend from frontend: `npm.cmd run dev`; use npm.cmd if npm.ps1 is blocked.
Fast tests: `python -m pytest -q tests/unit`, without a database.
For full tests, set TEST_DATABASE_URL explicitly to a dedicated `_test` database, then run `python -m pytest -q`. Integration fixtures recreate public schema.
A historical disposable database was timelog_catalog_20261024_b68d_test; never point tests at real/development timelog.
Frontend validation: `npm.cmd run lint` and `npm.cmd run build`.

CI separates unit/architecture checks from integration. Architecture tests enforce layer boundaries, no SQL in routes, original HTTP input contracts, the separate three-route import contract, and equivalent create_app composition. New login contracts are tracked separately.

Historical refactor results: all 173 pre-existing functional tests passed; adding four architecture tests produced 177 passes. Frontend lint/build passed after moving to src. The final import-cleanup run passed 177 tests in 48 seconds; alembic check found no schema drift.

## Initial audit results and limits — 2026-10-25

The initial audit is documented in docs/testing/AUDIT_RUNBOOK.md and AUDIT_RESULTS.fa.md; older reports are historical. It passed 325 backend/operational tests at 91.23% combined coverage. Previous xfails were replaced by fixes and regression tests. Frontend units, admin/user journeys, file import/two-device checks and accessibility/viewport/theme matrices were reported separately.

Audit uses port 18082 and PostgreSQL 5544 with a persistent volume. Integration uses only timelog_audit_integration_test; fixtures require an explicit TEST_DATABASE_URL and reject browser/preserved databases. That audit did not change the old 18081 stack or desktop data. The old demo DB uses tmpfs; it is not permanent storage and must not be stopped without backup/migration.

Verified checks included 14-table restore fingerprints, session persistence through restart/recreation, actual encryption of the preserved copy, and explicit rejection of wrong keys/truncated archives. backup.sh and restore_test.sh no longer mistake consumer pipeline success for producer success. Mixed load and a 15-minute soak verified every saved write; see the audit for interpretation limits.

A compatible override fixed nested PostCSS. Caddy and gosu are rebuilt with patched Go/dependencies while preserving PostgreSQL engine/data layout. Unused pip/ensurepip are removed from API/job images. Static CSP hashes authorize exported scripts; private API responses use no-store. Some Debian packages have no stable fix. Image security is not clean. govulncheck failed with a public-database HTTP 403 and is not counted as successful.

Live Google Sheets, real-domain HTTPS, Safari/iOS, physical phones, a full penetration test and production capacity remain unverified. Writing GitHub CI is not equivalent to running it. Story scraping from the original upstream system is outside this change. The audit itself did not deploy production; subsequent owner-authorized GitHub publication is separate.

## History import and multiple devices

The public name is TIME LOG and README is English. Settings supports XLSX/CSV history import, templates for both formats and a downloadable model-conversion guide. tabular_parser.py bounds file reading and validates input; tabular_import.py owns preview, ownership, repeat detection and transactions. Rows commit together or not at all. Recorded time, separate fill, fractional values and counts of genuine identical rows are preserved. Re-importing an old file cannot undo later edits/deletions. A changed file adds records instead of overwriting existing records, as preview and README explain.

The format transfers completed tasks only; it does not invent missing attendance, pause logs or future plans. Full SQLite migration remains a CLI operation on a copy and an empty account. Import required no new migration. Files above 5 MB, 5,000 rows, 50 MB expanded ZIP size, or containing formula cells are rejected. Runtime includes defusedxml.

SWR refreshes active pages periodically. Two browsers have separate sessions. Task edit forms send a revision; stale edits return 409 and retain the draft. Editing an imported task's title/metadata does not repair or round its time. Unknown start/end times do not prevent editing a duration-bearing task's title.

## Personal backups — 2026-10-25

JSON/Excel downloads have account-specific versioned names. `python -m app.cli backup-users --output ...` creates immutable account files; elapsed runtime alone does not create a revision. Optional Google Sheet sync writes only source-new/source-changed records and preserves deletion history. Accounts cannot share a sheet. Dockerfile.backup and the backup profile provide the job. Server credentials/scheduling require deployment configuration; see docs/PERSONAL_BACKUPS.fa.md. Preserve checkpoints and .instance-id with versions. Live Google connectivity was not tested locally.

## Responsive UI and attendance warnings — 2026-10-25

The fluid web shell extends to 1920 pixels, uses a sidebar from 1100 pixels, and switches features to multiple columns using container queries at 900 pixels of content width. shared/theme.tsx stores system/light/dark under timelog-theme; root layout applies the theme before paint. Modal and MoreMenu portal into body. A catalog story without a tag appears in the selector and can be linked through a prefilled confirmation dialog.

/api/presence/alerts returns private warnings for past days, comparing actual plus fill time against attendance. Today/future dates are excluded; data is never corrected automatically. POST /api/presence accepts an optional ISO date for past corrections, requires an end time for past days and rejects future attendance. Old open intervals are capped at that day's midnight. Tests and limits are in docs/testing/UI_REVIEW.fa.md.

## Deployment handoff and login security — 2026-10-25

DEPLOY.md is the server guide. Additive migrations 0003/0004 create login-security state without changing recorded work times. Accounts are only activated/deactivated, not deleted. Administrators edit usernames, passwords, display names and roles; credential changes invalidate sessions. Other users' personal records remain inaccessible.

ARCaptcha is optional and disabled by default because no real keys were supplied. Public config comes from the backend; Secret remains server-only. Tokens are verified server-side and reserved for one use in PostgreSQL. Provider failures cannot bypass captcha. Live-provider behavior without keys is unverified.

A bounded in-memory gate runs before routing/SQL; durable bans live in PostgreSQL. The per-process gate does not replace CDN/WAF or volumetric DDoS protection. No actual CDN or production server was configured here.

Console recovery: `python -m app.cli login-security` and `python -m app.cli unblock-login --ip <IP> --reset`. Local account credentials are private under secrets, excluded from Git/reports. Fresh servers create independent accounts using DEPLOY.

First-use setup now explains backups, retains per-user completion and offers Excel download. The backup-scheduler Compose service runs initially and daily at 03:00 Tehran, retries failures after 15 minutes and keeps a persistent success marker. Actual Sheets delivery still requires service-account credentials and Editor permission; saving a URL is not proof of delivery.

With the owner's later explicit approval, the 18081 API/UI were upgraded after a verified backup/restore. Its DB container was not recreated; personal tables remained equal. Three accounts were renamed/recredentialed in both environments while retaining IDs. Credentials remain local secrets. See docs/testing/RELEASE_RESULTS.fa.md for current release results; AUDIT_RESULTS predates these additions.

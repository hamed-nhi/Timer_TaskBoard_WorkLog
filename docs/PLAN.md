# TimeLog Web — original implementation plan

> Historical design, not the current deployment guide. Use [ARCHITECTURE.md](ARCHITECTURE.md), [HANDOFF.md](HANDOFF.md) and [DEPLOY.md](../DEPLOY.md) for current behavior. Original shared catalogs, session lifetime, timestamps, login limits, worker counts and backup policies were subsequently superseded.

> Update 2026-10-24: each account now owns its report types, projects and stories. All users manage their own catalog; only account administration requires an administrator. The change uses /api/catalog, 0002_private_catalog.py and import-catalog FILE --user USERNAME. Related legacy records are copied per owner and references redirected; originals remain ownerless and hidden from the API. At that stage this migration had run only on test databases; real upgrades require a backup.

> The refactored layout is backend/app/{api,services,core,db} and frontend/src/{app,features,components,shared,lib}. The tree below is historical.

Complete each implementation phase separately, test and commit before proceeding. Desktop business rules come from `C:\Users\hnahali\Documents\Folder\Hamed-stuff\time-sys`: app.py, static/app.js, calendar_events.py and tests/.

## 0. Non-negotiable rules

1. Desktop time-sys is read-only: no changed files or commits.
2. Never open live tasklog.db for writes. First create a SQLite backup at `C:\TimeLogBackups\before_web_migration_<ts>.db`; read that copy only with mode=ro.
3. Every personal query filters user_id; foreign task/tag IDs return 404, not 403.
4. No .env, passwords, Google keys or dumps in Git.
5. No Redis, Celery, Kubernetes, microservices, GraphQL, JWT or Repository wrapper around SQLAlchemy; database sessions suffice.
6. For ambiguous endpoints, read desktop code/tests first; ask the owner if still unclear.
7. UI/errors are Persian for the Persian-speaking user; comments are brief and English.

## 1. Original decisions

| Topic | Planning decision |
| --- | --- |
| Repository | Private timelog-web at `C:\Users\hnahali\Documents\Folder\Hamed-stuff\timelog-web`; owner creates remote/pushes. |
| Backend | Python 3.12, FastAPI, sync SQLAlchemy 2, psycopg 3, Alembic, pydantic-settings, argon2-cffi, jdatetime, openpyxl. |
| Database | PostgreSQL 18. |
| Frontend | Next.js 15 App Router, React 19, TypeScript, Tailwind CSS 4; output: 'export', no production Node server. |
| Fetching | lib/api.ts wrapper and SWR. |
| Font | Self-hosted Vazirmatn from @fontsource/vazirmatn, no Google Fonts. |
| Dates | Backend Jalali conversion; frontend Intl.DateTimeFormat('fa-IR-u-ca-persian') and Persian digits, no date library. |
| Login | Username/password, cookie session, three failures within 20 minutes lock access. |
| Signup | Administrator creates accounts; no open registration. |
| Catalog | Originally shared/admin-only, later scraped upstream, initially JSON import. Superseded by private catalogs. |
| Attendance | Manual only; remove auto-entry, ping and shutdown detection; remind when running work has no company check-in. |
| Offline | Unsupported. |
| Mobile | Responsive section 7; home-screen manifest without service worker/offline cache. |
| Server | Linux VPS in Iran, Docker Compose, Caddy automatic HTTPS. |
| Timezone | Asia/Tehran. Original proposal used timestamptz; implemented contracts are in HANDOFF. |
| Backup | Nightly pg_dump; daily retrieval to `D:\My Drive\TimeLogBackups\web` for local/Google Drive copies; optional personal Sheets after phase 7. |

Iran connectivity: Docker Hub/npm/Google may be inaccessible. Support Docker registry-mirrors in /etc/docker/daemon.json, for example https://docker.arvancloud.ir, and build arguments NPM_REGISTRY/PIP_INDEX_URL. Never assume Google access.

## 2. Proposed repository structure

~~~text
timelog-web/
├─ README.md                 # Local setup/deployment, originally planned in Persian
├─ .gitignore                # .env, *.db, backups/, node_modules, .next, out, __pycache__
├─ .env.example
├─ docker-compose.yml        # db, api, web (Caddy)
├─ docker-compose.dev.yml    # Development PostgreSQL only
├─ .github/workflows/ci.yml
├─ backend/
│  ├─ pyproject.toml         # Or requirements.txt plus requirements-dev.txt
│  ├─ Dockerfile
│  ├─ alembic.ini
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py             # FastAPI, routers, exception handlers
│  │  ├─ config.py           # pydantic-settings
│  │  ├─ db.py               # engine, SessionLocal, get_db
│  │  ├─ models.py           # All SQLAlchemy models in one file
│  │  ├─ schemas.py          # Pydantic requests/responses
│  │  ├─ auth.py             # Hashing, sessions, current_user, require_admin, rate limits
│  │  ├─ jalali.py           # g2j, j2g, months/weekdays from app.py
│  │  ├─ calendar_events.py  # Unchanged desktop copy
│  │  ├─ timecalc.py         # Effective time, segments, overlap, duration from app.py
│  │  ├─ fill.py             # presence_sanity, suggest_fill, constants from app.py
│  │  ├─ routers/
│  │  │  ├─ auth.py  tasks.py  planned.py  tags.py  presence.py
│  │  │  ├─ reports.py       # Timesheet, dashboard, tag summary, entry report, export, daylog
│  │  │  ├─ fill.py  calendar.py  settings.py  catalog.py  admin.py  me.py
│  │  ├─ cli.py              # create-user, reset-password, import-desktop, import-catalog
│  │  └─ jobs/sheets_sync.py # Phase 7
│  └─ tests/
│     ├─ conftest.py         # Test PostgreSQL, client/login helper, two users
│     └─ test_*.py
├─ frontend/
│  ├─ package.json  next.config.ts  tsconfig.json  postcss.config.mjs
│  ├─ public/ manifest.webmanifest, icons/
│  ├─ app/
│  │  ├─ layout.tsx          # lang=fa, dir=rtl, font, shell
│  │  ├─ login/page.tsx
│  │  ├─ (app)/layout.tsx    # Auth guard and desktop/mobile navigation
│  │  ├─ (app)/page.tsx      # Today
│  │  ├─ (app)/planned/page.tsx  dashboard/  calendar/  timesheet/  tasks/  daylog/  settings/  admin/
│  ├─ components/            # TaskTimer, TaskCard, PresenceCard, FillDialog, StoryPicker, Modal/Sheet
│  └─ lib/ api.ts, fa.ts (faDigits, fmtDuration), types.ts
└─ deploy/
   ├─ Caddyfile
   ├─ backup.sh              # pg_dump, GPG, retention
   ├─ restore_test.sh
   └─ pull_backup.ps1        # User's computer
~~~

## 3. Proposed PostgreSQL schema

Originally all tables used bigint identity primary keys, created_at timestamptz default now(), and user references as foreign keys. Actual migrations/models supersede this proposal.

~~~text
users(id, username citext unique, password_hash, display_name, is_admin bool, is_active bool, created_at)
sessions(id, user_id, token_hash text unique, created_at, expires_at, last_seen_at, user_agent)
login_attempts(id, username, ip inet, success bool, at timestamptz) -- indexes: (username, at), (ip, at)
-- Originally shared administrator catalog:
report_types(id, name unique, sort)
projects(id, name unique, sort)
stories(id, project_id FK, name, sort, unique(project_id, name))
-- Personal records:
tags(id, user_id, name, budget_minutes real null, budget_since date null,
     report_type_id FK null, story_id FK null, fill_weight real null, created_at,
     unique(user_id, lower(name)))
tasks(id, user_id, jalali_year, jalali_month, jalali_day, gregorian_date date,
      title, start_time time null, end_time time null, duration_minutes real null,
      status text check in ('running','paused','done'), accumulated_minutes real default 0,
      segment_started_at timestamptz null, tag_id FK null, entered_main_system bool,
      meeting_with text null, meeting_minutes real null, adjust_minutes real default 0,
      report_type_id FK null, outside_company bool, planned_flag bool, fill_minutes real default 0,
      created_at)
      -- indexes: (user_id, gregorian_date), (user_id, status)
task_segments(id, task_id FK on delete cascade, started_at timestamptz, ended_at timestamptz null)
planned_tasks(id, user_id, jalali_year, jalali_month, jalali_day, title, tag_id FK null, created_at)
presence_segments(id, user_id, started_at timestamptz, ended_at timestamptz null, note text, kind text)
user_settings(user_id, key, value text, PK(user_id, key))
   -- daily_goal_minutes, weekly_goal_minutes, fill_target_percent, google_sheet_url
audit_log(id, user_id, kind text, payload jsonb, at)
   -- task_deleted | fill_rollback | tag_merge
   -- replaces deleted_tasks, fill_rollback_log and tag_merge_log
~~~

Inspect desktop status values using grep "status" app.py; preserve additional values if found. Map text tags.report_type and tags.project/tags.story to report_type_id/story_id by catalog names; map tasks.report_type to report_type_id. Start with one initial migration; later changes are new/additive. Task company_type/company_project/company_story uses desktop precedence: task override, meeting_with, then tag report type. Project/story come from the tag's story.

## 4. Original authentication/security requirements

- argon2id through argon2-cffi; originally minimum eight characters.
- POST /api/auth/login {username, password}: three username failures in 20 minutes return 429, a Persian remaining-time message and Retry-After; also ten failures/IP/20 minutes to stop username spraying. Wrong password, absent and inactive users get identical 401 messages. Record attempts in login_attempts.
- Success generates secrets.token_urlsafe(32), storing SHA256 only. Set tl_session with HttpOnly, Secure, SameSite=Lax, Path=/ and originally 30-day Max-Age; current lifetime is in HANDOFF.
- POST /api/auth/logout deletes the DB session.
- current_user resolves the cookie's valid session, updates last_seen_at at most hourly, and returns 401 when absent.
- require_admin returns 403 to non-admins.
- POST/PUT/DELETE require X-Requested-With: timelog or return 403. Combine with SameSite=Lax and same-origin frontend/API. No CORS: / and /api share one origin.
- POST /api/me/password {old,new} invalidates other sessions.
- Original admin API: GET/POST /api/admin/users, PUT /api/admin/users/{id} for activation/display name, POST /api/admin/users/{id}/reset-password for a temporary password, catalog CRUD under /api/admin/catalog/... (later superseded).
- CLI: `python -m app.cli create-user <username> --admin`; prompt with getpass, never password arguments. Never log passwords/tokens.

## 5. API

All routes start with /api. The original plan required authentication except for login. Preserve desktop request/response shapes for static/app.js; corresponding app.py functions define behavior.

| Web endpoint | Desktop function | Notes |
| --- | --- | --- |
| GET /api/me | — | {id, username, display_name, is_admin} |
| GET /api/today, /api/month-days, /api/shift-date, /api/yesterday-titles | api_today, api_month_days, api_shift_date, yesterday_titles | |
| GET/POST /api/tags, PUT/DELETE /api/tags/{id}, PUT /api/tags/{id}/budget, POST /api/tags/{id}/merge, PUT /api/tags/{id}/company | Corresponding handlers | company: {report_type_id, story_id, fill_weight} |
| GET /api/company-catalog | company_catalog | Originally shared tables. |
| GET/POST /api/presence, GET /api/presence/history, POST /api/presence/start\|pause\|finish, PUT/DELETE /api/presence/{id} | Corresponding handlers | Remove /ping, /auto, /auto-setting, presence_last_seen, presence_close_dead_session. needs_checkin=true for today's running task without open attendance. |
| GET/POST /api/settings | api_get_settings, api_update_settings | user_settings. |
| GET /api/goal-progress | goal_progress | |
| GET/POST /api/planned, PUT/DELETE /api/planned/{id}, POST /api/planned/{id}/start | Corresponding handlers | Set planned_flag on start. |
| GET/POST /api/tasks, GET /api/tasks/paused, POST /api/tasks/{id}/pause\|resume\|stop\|reopen, GET /api/tasks/{id}/segments, POST /api/tasks/{id}/entered, POST /api/tasks/{id}/company, PUT/DELETE /api/tasks/{id} | Corresponding handlers | Delete archives full payload/segments under task_deleted. |
| GET /api/fill-suggestion, POST /api/fill, POST /api/fill/rollback | Corresponding handlers | Rollback uses audit_log. |
| GET /api/timesheet, /api/dashboard, /api/tag-summary, /api/calendar, /api/entry-report | Corresponding handlers | |
| GET /api/export | export_excel | Own data, same columns. |
| GET /api/me/backup | — | Full personal JSON download. |
| /api/backup, /api/drive-backup | — | Remove: server owns database backup. |

Port desktop tests with these rules:

- Duration: effective_minutes, duration_from_segments, compute_duration, parse_adjust, adjust_minutes; pause/resume segments and accumulated_minutes; reopen; update_task start/end edits.
- assert_no_overlap applies only within the same account.
- Original one-running-task proposal expected a new task to pause the old one; inspect create_task. Actual rejection behavior is in HANDOFF.
- Fill: presence_sanity covers Friday, no attendance, attendance below tasks, over 11 hours, 30-minute lunch deduction and missing end-of-day status. suggest_fill uses 50%, five-minute rounding and FILL_MAX_PERCENT=95; apply_fill enforces server caps. Replace shutdown-inference warnings with missing end-of-day feedback.
- Budgets: budget_info/tag_spent_minutes. Merge: merge_tags. Dashboard: build_comparison/aligned_minutes.
- Copy calendar_events.py unchanged.
- Validate clean_title (500 characters), clean_tag_name (60), TIME_RE, clean_jalali and Arabic/Persian letters through tag_key; use Pydantic or those helpers.
- Errors have an error property with a Persian message and statuses 400/401/403/404/409/429, as handle_api_error.

## 6. Frontend

layout.tsx uses lang=fa/dir=rtl and CSS variables; initial dark design follows prefers-color-scheme. /api/me 401 redirects to /login. lib/api.ts adds the CSRF header, credentials: same-origin, redirects 401 and throws response errors. Match desktop tab ordering/content in templates/index.html/static/app.js.

| Route | Content |
| --- | --- |
| /login | Username/password and 429 feedback. |
| / (Today) | Attendance lifecycle/report/fill; needs_checkin; task/story form; live timer; paused/daily lists; goals. |
| /planned | Daily plans and starting work. |
| /dashboard | Comparisons, tags, budgets. |
| /calendar | Jalali month/events. |
| /timesheet | Weekly timesheet. |
| /tasks | All tasks/editing. |
| /daylog | Daily columns/totals, rollback, copy-all in desktop order, entered-in-main-system checkbox. |
| /settings | Goals/fill target, password, Sheet URL, Excel/JSON, tag/story management. |
| /admin | Originally admin-only users/catalog; later private-catalog access superseded this. |

Fill dialog: suggestion/warnings, manual edit, preview/final confirmation. Fetch fresh suggestions; over-cap totals show errors and disable Next. Group stories by project/optgroup as populateTagSelect, including no-story/add-new choices. Calculate timers each second from segment_started_at/accumulated_minutes and revalidate SWR on tab focus.

## 7. Responsive/mobile requirements

Initial widths: 360, 768, 1280px, without page-wide horizontal scrolling.

- Below 768: five labeled bottom icons, Today/Plans/Daylog/Dashboard/More; More opens a sheet. Above 768 originally uses top navigation. Bottom padding uses env(safe-area-inset-bottom).
- Running task: sticky bar above mobile tabs, title/timer/pause/finish, available on every page.
- Below 640: report/task rows become cards with title/times/recorded/fill/type/project/story. Controls below, totals after list. Weekly timesheet scrolls inside itself or uses day accordions.
- Dialogs: full-width mobile bottom sheets, maximum 90vh, internal scroll, pinned primary actions.
- Touch targets at least 44×44px; input font at least 16px to avoid iOS zoom. Originally input type=time for clocks and inputMode=numeric for numbers.
- Calendar: compact seven-column grid; details sheet below.
- Manifest: localized product name (current name TIME LOG), dir=rtl, lang=fa, display=standalone, theme_color, 192/512 icons from tools/generate_icon.py or existing desktop assets, plus apple-touch-icon.

Acceptance: all pages at Chrome DevTools 360×740 without horizontal page scroll; task lifecycle, check-in and fill work by touch; capture screenshots.

## 8. Original deployment proposal

Current commands: DEPLOY.md.

- db: postgres:18, pgdata, healthcheck, no public port.
- api: backend/Dockerfile, originally python:3.12-slim/two Uvicorn workers; alembic upgrade head at startup; .env; private Compose access.
- web: Caddy 2 multi-stage image; node:22 runs npm ci/build with NPM_REGISTRY; serve out/ on 80/443.

Proposed deploy/Caddyfile:

~~~text
{$DOMAIN} {
  encode gzip
  handle /api/* { reverse_proxy api:8000 }
  handle { root * /srv/www; try_files {path} {path}.html {path}/index.html /index.html; file_server }
  header { Strict-Transport-Security "max-age=31536000"; X-Content-Type-Options nosniff; Referrer-Policy same-origin }
}
~~~

Originally DOMAIN=:443/tls internal without a domain. Proposed .env fields: DOMAIN, POSTGRES_PASSWORD, DATABASE_URL, APP_TZ=Asia/Tehran, BACKUP_PASSPHRASE_FILE, optional GOOGLE_SA_JSON.
Original update: git pull && docker compose up -d --build.
CI: PostgreSQL 18/pip install/pytest; frontend npm ci/lint/build; no automatic deployment.

## 9. Original backup plan

Host cron runs backup.sh nightly at 02:30:

1. Encrypt docker compose exec -T db pg_dump -Fc -U timelog timelog through gpg --symmetric --batch --passphrase-file into `/srv/timelog/backups/daily/timelog_<date>.dump.gpg`.
2. Friday copies to weekly/.
3. Keep 14 daily/eight weekly copies.
4. Empty output/pg_dump failure exits nonzero and logs the error.
5. Update latest.dump.gpg symlink.

restore_test.sh restores latest dump to temporary timelog_restore_test, prints task/user counts, drops it, and runs monthly.

pull_backup.ps1 on the user's computer retrieves latest.dump.gpg through scp/Windows OpenSSH and a user-created SSH key to `D:\My Drive\TimeLogBackups\web\timelog_<date>.dump.gpg`, keeps 30 copies, and documents daily/at-logon Task Scheduler registration. No passwords in scripts.

Settings provides personal Excel/JSON downloads.

## 10. Desktop migration

Command: `python -m app.cli import-desktop <path-to-copy.db> --user <username>`.

1. Copy only; reject live tasklog.db.
2. Open sqlite3.connect('file:...?mode=ro', uri=True).
3. Refuse destination tasks; import once into an empty account.
4. Originally import settings.company_catalog idempotently into shared tables; private ownership later superseded this.
5. One transaction: tags resolve story_id/report_type_id by name; planned_tasks; tasks with mapped IDs (originally local text-to-Tehran timestamptz conversion); task_segments; presence_segments; settings to user_settings excluding presence_last_seen/default_tags_seeded; deleted_tasks/tag_merge_log/fill_rollback_log to audit_log.
6. Before commit compare tasks, SUM(duration_minutes), SUM(fill_minutes), SUM(adjust_minutes), segment/attendance counts; mismatch rolls back. Planning snapshot: 77 tasks, 9561.1 minutes.
7. Use a small synthetic SQLite fixture in tests/fixtures, never real test data.

## 11. Planned tests

pytest/fastapi.testclient, real PostgreSQL through TEST_DATABASE_URL, development Compose, truncate tables between tests, alice/bob/login helper in conftest.py. Port desktop time/overlap/pause/planned/fill/budget/Excel/timesheet tests, not pywebview/drive/ping.

Required checks: Bob cannot read/change Alice's tasks/tags/plans/attendance/settings/exports through lists or direct get/put/delete (planned 404); three wrong passwords make fourth attempt 429 even with correct credentials, mocked 20-minute expiry; logout/session expiry 401; password invalidates other sessions; missing POST CSRF 403; ordinary admin routes 403; needs_checkin; section 10 import/nonempty-account refusal. Initial frontend scope was build/lint only, without E2E; later QA expanded it.

## 12. Phases and acceptance

Commit per phase; tests pass; brief Persian status for the owner.

| Phase | Work | Acceptance |
| --- | --- | --- |
| 1. Skeleton | Repo/PLAN/.gitignore/dev Compose, /api/health, Alembic/models/initial migration, blank RTL Next/font/CI. | pytest/build pass; migration works on PostgreSQL 18. |
| 2. Login | Users/sessions/attempts, login/logout/me, CSRF, create-user CLI, login page. | Section 11 security passes. |
| 3. Task core | Jalali/time/tags/all task actions/planned/settings/goals/catalog reading, ported/isolation tests. | Desktop-equivalent, passing tests. |
| 4. Attendance/fill | Manual attendance/needs_checkin, suggestions/apply/rollback, audit. | Ported fill tests pass. |
| 5. Reports | Timesheet/dashboard/tag summary/calendar/entry report/Excel/personal JSON. | Desktop-equivalent Excel columns. |
| 6. Frontend | Section 6 pages/section 7 responsiveness/admin/manifest. | Mobile acceptance; 360/1280 screenshots. |
| 7. Import/deploy/backup | Desktop import, Dockerfiles/Caddy, backup/restore/pull scripts, README; Sheets only after owner confirms Google access. | Full local Compose; real-copy import with equal checks; successful dump restore. |

Original optional Sheets after phase 7: app/jobs/sheets_sync.py/service account; users save/share their sheet; nightly Tasks-tab overwrite with Excel columns; log one failure and continue others; host cron invokes docker compose exec api python -m app.jobs.sheets_sync. Later source-change-only synchronization superseded overwriting.

## 13. Questions open at planning time

1. Domain available? Affects DOMAIN; phases 1–6 proceed without it.
2. Destination-server result for curl -sS -o /dev/null -w "%{http_code}\n" https://sheets.googleapis.com?
3. Server OS/RAM and Docker installed?
4. Approximate user count?

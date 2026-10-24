# Technology Stack

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


Reviewed 2026-10-24 at commit 2707511. Static source inspection; no services or tests were started.

## Core Sections (Required)

### 1) Runtime Summary
| Area | Value | Evidence |
|---|---|---|
| Backend | Python; Docker and CI select 3.13 | backend/Dockerfile; .github/workflows/ci.yml |
| Frontend | TypeScript, React, Next App Router; Node 22 at build time | frontend/package.json; frontend/Dockerfile |
| Packages | pip requirements; npm with package-lock | backend/requirements.txt; frontend/package-lock.json |
| Build | Next static export in production; Caddy serves out/ | frontend/next.config.ts; frontend/Dockerfile |

### 2) Production Frameworks and Dependencies
Backend pins: FastAPI 0.162.0, uvicorn[standard] 0.54.0, SQLAlchemy 2.1.6, psycopg[binary] 3.3.6, Alembic 1.20.1, pydantic-settings 2.16.1, argon2-cffi 25.1.0, jdatetime 6.1.1, openpyxl 3.1.5, tzdata 2026.5 (backend/requirements.txt).
Frontend declared ranges: Next ^15.5.28, React/react-dom ^19.3.1, SWR ^2.5.1, Vazirmatn ^5.3.0 (frontend/package.json). These are manifest ranges, not a report of installed versions.
PostgreSQL 18 and Caddy 2 are image tags (docker-compose.yml; frontend/Dockerfile).

### 3) Development Toolchain
pytest 9.1.1 and httpx 0.28.1; ESLint ^9.39.5, TypeScript ^6.0.3, Tailwind/PostCSS 4 tooling. See requirements-dev.txt and package.json. CSS imports Tailwind plus local Vazirmatn weights; most product styles are in globals.css.

### 4) Key Commands
Run backend commands from backend/, frontend commands from frontend/:
- pip install -r requirements-dev.txt
- alembic upgrade head; uvicorn app.main:app --port 8000
- python -m pytest -q (only with an explicitly verified disposable test database)
- npm.cmd ci; npm.cmd run dev; npm.cmd run lint; npm.cmd run build
Root deployment: docker compose up -d --build. Commands were inspected, not executed.

### 5) Environment and Config
backend/app/config.py reads environment and a working-directory .env. Defaults include APP_TZ=Asia/Tehran, 90-day rolling sessions, 3 username failures / 20 minutes and 10 IP failures.
Root .env.example configures DB_PASSWORD, SITE_ADDRESS, COOKIE_SECURE, HTTP_PORT, registry mirrors and BACKUP_PASSPHRASE.
COOKIE_SECURE defaults to automatic request-scheme detection; a blank Compose/environment value is ignored. Explicit true/false overrides automatic handling.
Production has no Node server. PLAN.md says Python 3.12; current Docker/CI select 3.13.

### 6) Evidence
- backend/requirements.txt
- backend/requirements-dev.txt
- backend/app/config.py
- frontend/package.json
- frontend/next.config.ts
- frontend/Dockerfile
- .env.example
- .github/workflows/ci.yml

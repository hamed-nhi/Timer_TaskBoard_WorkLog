# Technology Stack

## Runtime and dependencies
Backend runs Python 3.13 in Docker/CI, FastAPI, synchronous SQLAlchemy/psycopg and PostgreSQL 18. Exact pins remain in backend/requirements.txt: FastAPI 0.162.0, uvicorn 0.54.0, SQLAlchemy 2.1.6, psycopg 3.3.6, Alembic 1.20.1, pydantic-settings 2.16.1, argon2-cffi 25.1.0, jdatetime 6.1.1, openpyxl 3.1.5 and tzdata 2026.5.
Frontend declares Next ^15.5.28, React ^19.3.1, SWR ^2.5.1 and Vazirmatn ^5.3.0. TypeScript and ESLint are development tools; Tailwind/PostCSS are build tools. See package.json and package-lock.json for versions.

## Build and commands
Node 22 builds a static Next export; Caddy 2 serves it. There is no production Node application server.
Backend commands from backend: pip install -r requirements-dev.txt; uvicorn app.main:app --port 8000; python -m app.cli; alembic upgrade head.
Tests: python -m pytest -q tests/unit; python -m pytest -q tests/integration.
Frontend commands from frontend: npm.cmd ci; npm.cmd run dev; npm.cmd run lint; npm.cmd run build.

## Configuration
app/core/config.py reads environment and working-directory .env. Cookie lifetime defaults to 90 days with activity renewal; blank COOKIE_SECURE selects request-scheme detection. APP_TZ defaults to Asia/Tehran.
Root .env.example documents DB_PASSWORD, SITE_ADDRESS, ports, mirrors and backup passphrase. Credentials and deployment state were not changed during restructuring.
No new runtime dependency was added for the architecture refactor.

## Evidence
- backend/app/core/config.py
- backend/requirements.txt
- backend/requirements-dev.txt
- backend/Dockerfile
- frontend/package.json
- frontend/next.config.ts
- frontend/Dockerfile
- .github/workflows/ci.yml

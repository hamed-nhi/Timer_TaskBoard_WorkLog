# Working on TimeLog

Read docs/ARCHITECTURE.md for the current layout and docs/HANDOFF.md for operational context.

## Backend boundaries
- app/main.py composes the application; keep the app.main:app and app.cli entrypoints stable.
- app/api/routes owns HTTP input, auth dependencies and response serialization. Do not execute SQL or commit transactions in routes.
- app/services owns business rules, ownership checks and transactions. Do not import app.api, FastAPI or Starlette here.
- app/db owns models and the session/SQL adapter. It must not depend on services or API.
- app/core owns configuration, errors, security primitives and time helpers. It must not depend on the other layers.
- Reuse plain service functions. Add abstractions only when there are concrete independent implementations or responsibilities.
- Every personal-data query must scope by user. Catalogs are private even for administrators.

## Frontend boundaries
- Sources live under frontend/src; @/* resolves there.
- app/**/page.tsx delegates to a feature view; layouts compose the application.
- features owns views, dialogs and feature behavior.
- shared and lib must not import features, routes or the app shell.
- Preserve Persian RTL, mobile behavior and the static-export build.

## Validation
- backend: python -m pytest -q tests/unit (no database needed).
- backend: python -m pytest -q tests/integration on an explicitly verified disposable PostgreSQL database.
- Set TEST_DATABASE_URL to a dedicated database whose name ends in _test. Integration setup recreates its public schema.
- Never run integration tests against development or production databases.
- frontend: npm.cmd run test:unit, npm.cmd run lint and npm.cmd run build.
- System QA: use only docker-compose.test.yml with project timelog-qa; frontend npm.cmd run test:e2e targets its local port 18081.
- backend/tests/operational uses disposable Docker containers to inject backup failures. Strict xfails are known open defects, not passing behavior.
- See docs/testing/TEST_PLAN.fa.md and RESULTS.fa.md for the executable QA matrix and limits.
- Keep the HTTP request contract fixture and architecture tests meaningful; do not update snapshots simply to conceal accidental changes.

## Data and Git
- Desktop TimeLog source and live SQLite data must remain untouched.
- Never commit .env, credentials, database copies, dumps or generated build output.
- Back up real data before any intentional data migration; preserve existing recorded times.
- Add new migrations instead of rewriting existing migrations.
- Commit a complete tested feature locally; do not push on the user's behalf.
- Speak Persian and state material verification/deployment limitations clearly.

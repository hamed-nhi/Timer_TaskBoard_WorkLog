# Codebase Structure

## Top-level map
backend/app contains api, services, core and db packages plus main.py and cli.py. backend/alembic retains versioned schema migrations. backend/tests separates unit, integration, fixtures and shared support.
frontend/src contains app, features, components, shared and lib. frontend/public holds public assets. deploy holds backup/recovery/pull scripts, tools holds icon tooling, docs holds architecture/handoff/design notes, and .github/workflows holds CI.

## Entrypoints
app/main.py provides create_app() and app. app/cli.py retains python -m app.cli. Alembic imports core config and db models.
frontend/src/app/layout.tsx defines RTL root metadata. The (app) route-group layout loads components/app-shell.tsx. Page files re-export feature views.
Public routes remain /, /login/, /planned/, /dashboard/, /calendar/, /timesheet/, /tasks/, /daylog/, /settings/ and /admin/.

## Module ownership
API routes handle Body/Query/auth dependencies and serialization. Services own rules/queries/transactions. Core owns errors/settings/security/time. DB owns schema/session execution.
Features own their UI; shared owns generic widgets; lib owns cross-feature API contracts, fetch, SWR and formatting. Daylog navigation and task time previews live with their features.
No placeholder repository/interface/worker packages were introduced. Models remain one cohesive file; global CSS remains intact.

## Organization conventions
Python packages and functions use snake_case. React exports PascalCase components, with lowercase feature filenames. @/* resolves to frontend/src/*.
venv, node_modules, .next, out and tsconfig.tsbuildinfo are generated/environment artifacts.

## Evidence
- docs/ARCHITECTURE.md
- backend/app/main.py
- backend/app/api/router.py
- backend/app/db/models.py
- backend/tests/integration/conftest.py
- frontend/src/components/app-shell.tsx
- frontend/tsconfig.json

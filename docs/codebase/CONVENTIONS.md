# Coding Conventions

## Naming and imports
Python uses snake_case files/functions and PascalCase classes. API adapters are grouped by feature; services have matching names where appropriate. Helpers have explicit purposes such as timecalc, catalog_helpers and user_settings.
Frontend uses PascalCase components with feature-owned view.tsx/components.tsx. @/* resolves to src/*. Cross-feature composition belongs in components/app-shell.tsx.

## Enforced boundaries
core cannot import API/services/db. db cannot import API/services. services cannot import API/FastAPI/Starlette. Route adapters cannot execute database operations.
Shared frontend UI/utilities cannot import features/app/composition; features cannot import routes or AppShell. Backend architecture tests and ESLint enforce these boundaries.

## Formatting and lint
TypeScript strict=true and noEmit=true. ESLint extends Next core-web-vitals/typescript; existing explicit-any/exhaustive-deps exceptions remain. npm.cmd run lint and npm.cmd run build are the current checks.
[TODO] A dedicated Python formatter/linter is not yet configured; the refactor did not add a new dependency for one.

## Errors and transactions
core/errors.ApiError contains message/status/headers without HTTP imports. api/exception_handlers maps it to the existing error JSON. Services validate inputs and commit explicitly; db/get_db rolls back uncommitted work on cleanup.
Credentials are never logged or saved to browser storage; passwords are hashed and session tokens digested.

## Tests and safe changes
Pure/architecture tests live in tests/unit; real DB/API/migration tests in tests/integration. Helpers are imported from tests.support, not conftest. Only integration fixtures recreate/truncate DB schema.
Preserve private ownership and recorded times, add migrations for schema changes, and never push automatically.

## Evidence
- AGENTS.md
- backend/app/core/errors.py
- backend/app/api/exception_handlers.py
- backend/app/db/session.py
- backend/tests/unit/test_architecture.py
- backend/tests/support.py
- frontend/eslint.config.mjs
- frontend/tsconfig.json

# Project architecture and layout

This document describes the current layout. The application is a single deployable system with clear boundaries: a feature can be developed and tested without adding several intermediary layers for every small change. There is no artificial file-count target; each file needs a defined responsibility and a predictable location.

## Directory map

```text
workload/
├── backend/
│   ├── app/
│   │   ├── main.py                 # Compose the FastAPI application
│   │   ├── api/
│   │   │   ├── router.py           # Register all routes
│   │   │   ├── routes/             # HTTP input and response adapters
│   │   │   ├── dependencies.py     # Request user, role and database dependencies
│   │   │   ├── middleware.py       # CSRF protection and cookie renewal
│   │   │   ├── session.py          # Session cookie configuration
│   │   │   └── exception_handlers.py
│   │   ├── services/              # Task, tag, attendance, fill, reporting and catalog rules
│   │   ├── core/                  # Configuration, errors, security and time helpers
│   │   └── db/                    # Session/Db adapter and SQLAlchemy models
│   ├── alembic/                   # Versioned migrations
│   ├── tests/
│   │   ├── unit/                  # Fast tests without a database
│   │   ├── integration/           # API, ownership and migrations on test PostgreSQL
│   │   ├── fixtures/              # HTTP request contract captured before the refactor
│   │   └── support.py             # Shared test clients and helpers
│   └── requirements*.txt
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js routes and layouts
│   │   ├── features/              # Feature implementation
│   │   │   ├── auth/
│   │   │   ├── today/
│   │   │   ├── tasks/
│   │   │   ├── tags/
│   │   │   ├── presence/
│   │   │   ├── fill/
│   │   │   ├── planned/
│   │   │   ├── daylog/
│   │   │   ├── dashboard/
│   │   │   ├── calendar/
│   │   │   ├── timesheet/
│   │   │   ├── settings/
│   │   │   └── admin/
│   │   ├── components/            # Feature composition, including the app shell
│   │   ├── shared/                # Reusable UI independent of features
│   │   └── lib/                   # Fetch, SWR, API contracts and Persian formatting
│   └── public/                    # Icons and manifest
├── deploy/                        # Backup, restore checks and retrieval scripts
├── tools/                         # Development and QA tools
├── docs/                          # Design, setup and handoff
└── .github/workflows/             # CI checks
```

Within each frontend feature, `view.tsx` implements the page. Its `app/**/page.tsx` only exports that view. Features such as tasks and attendance keep their interactive components alongside the view. Do not create empty directories for hypothetical future features.

## Responsibilities and dependency direction

```text
main → api → services → db
         ↓       ↓      ↓
                core
```

- **API:** Body/query input, authentication and role dependencies, status codes, headers, cookies and downloadable responses. Routes do not execute queries or commit transactions.
- **Services:** Business rules, ownership checks, transactions and queries. Services do not import FastAPI, Request or Response; they return plain data or file content.
- **DB:** Table models, Session creation, parameterized SQL execution and per-user transaction locks. Models and the database adapter do not import API or services.
- **Core:** Configuration, application errors, time utilities and password hashing. This layer is independent of API, services and DB.

Shared feature logic is called through its service. Attendance or reporting services must not import a tag route. An HTTP route is only one entry point to a service; the CLI can use the same rules.

Queries currently live in services. There is no separate Repository and Interface for every table; the small Db wrapper is sufficient at this scale. Introduce a storage boundary when it has multiple concrete implementations.

## Frontend boundaries

`app` defines routes, `components/app-shell.tsx` composes features and providers, and `features` owns page behavior. `shared` and `lib` must not import a page or specific feature. ESLint enforces these boundaries.

Shared API contracts live in `lib/types.ts`. SWR holds server state; `lib/data.tsx` supplies the shared clock. The original structural refactor preserved the CSS and did not redesign the interface.

## Adding a feature

1. Put new backend rules in the feature's service. A new route only resolves input and calls that service.
2. Scope every personal-data query by user. AdminDep is for account administration; an administrator's catalog is private too.
3. Change tables through a new migration and test the upgrade. The structural refactor itself required no new migration.
4. Implement new frontend pages in features and export them from the route. Keep feature-specific components there too.
5. Put database-independent tests in unit and API/storage tests in integration.
6. Split a file when it has a separate responsibility or becomes difficult to change and test; do not create a tiny file for every function.

## Scalability and reliability

The layout separates feature development and testing. PostgreSQL locks, account isolation, persistent cookies and API contracts were preserved. PostgreSQL stores data and sessions; production frontend output is static.

Unit tests enforce layer boundaries, prohibit SQL in routes and compare the original 57-path request contract. Later feature contracts are tracked separately. Unit tests need no PostgreSQL; destructive schema fixtures are confined to integration tests, whose database name must end in `_test`.

Actual capacity depends on user count, workload, response time, query count, memory and connection-pool usage. Directory organization alone does not guarantee capacity or availability. The structural refactor did not include load testing or a real production deployment; later results are in [the current release report](testing/RELEASE_RESULTS.fa.md). Historical backup concerns are recorded in [codebase/CONCERNS.md](codebase/CONCERNS.md).

## Stable commands

- Backend: `uvicorn app.main:app --port 8000`
- CLI: `python -m app.cli ...`
- Migrations: `alembic upgrade head`
- Fast tests: `python -m pytest -q tests/unit`
- Database tests: `python -m pytest -q tests/integration` on a dedicated disposable test database
- Frontend: `npm.cmd run dev`, `npm.cmd run lint`, `npm.cmd run build`

Run Python commands from backend and npm commands from frontend. Existing public API URLs and page routes remain stable.

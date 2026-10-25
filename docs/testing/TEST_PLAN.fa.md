# TIME LOG system test plan

> Historical initial QA plan. Do not run its original 18081/tmpfs reset/teardown against the current environment. Use [AUDIT_RUNBOOK.md](AUDIT_RUNBOOK.md), [RELEASE_RESULTS.fa.md](RELEASE_RESULTS.fa.md) and [DEPLOY.md](../../DEPLOY.md).

Design/execution: 2026-10-25. Test realistic usage, boundaries, isolation and errors alongside unit tests.

## Environment and protection

Separate timelog-qa Docker project: initial PostgreSQL 5543, web 18081, timelog_system_test and timelog_integration_test separate from real data. Browser/load records were synthetic; real DB and desktop were unused. The initial tmpfs database lost data when stopped and is not a production template. Later audit uses persistent 18082/5544.

## Roles and usage

- New user: admin-created account, first login/catalog/task.
- Daily user: manual attendance, start/pause/resume/finish, plans/report.
- Reporting user: manual times, tags/budgets/fill, Excel/JSON.
- Colleagues: concurrent use, duplicate names, foreign identifiers.
- Mobile: narrow viewport, bottom navigation, taps.
- Cross-timezone: London browser/Tehran server.
- Unstable network: disconnect during submission, reconnect/retry.
- Operator: CLI, Docker, migrations, backup/restore/encryption/restart.

## Test types

| Type | Scope/tool | Criterion |
| --- | --- | --- |
| Unit | pytest/Node; time/Jalali/Persian digits/rounding | Boundaries correct, input unchanged. |
| Integration | FastAPI TestClient/real PostgreSQL | HTTP, transaction, ownership and data correctness. |
| E2E | Chrome/Playwright | Correct UI and server result. |
| Contract/architecture | OpenAPI/AST/ESLint | Original 57-route inputs and layer boundaries. |
| Functional security | Login/CSRF/ID guessing/XSS/SQL-looking text | Unauthorized requests rejected; others' data intact. |
| Concurrency | ThreadPoolExecutor/clients | One live task; idempotent finish; no catalog duplication. |
| Responsive/touch | Nine pages, three widths, touch | RTL; no page-wide horizontal scroll; taps succeed. |
| Exploratory load | Ten users, 2,800 tasks, 400 requests/run | Record errors/percentiles; local p95 below 2 seconds. |
| Backup fault injection | Real scripts/fake Docker-GPG commands in containers | Any failed stage exits nonzero. |
| Actual restore | pg_dump/pg_restore, 12-table fingerprints | Exact source/destination equality. |
| Actual encryption | GPG AES256/temporary keyring | Decrypted hash matches; wrong password fails. |
| Resilience | API restart/existing cookie | API/session/tasks recover. |
| Dependency audit | npm audit | Record findings, no forced major upgrade. |

Local exploratory latency budget is not a production SLO/capacity guarantee; specify hardware, history, users and peak periods first.

## Results and expected failures

scenarios.json provides prerequisites/steps/expectations/evidence, linked to JUnit/JSON. xfail means reproduced open defect, not success; strict=True exposes unexpected changes. Unregistered failures fail CI.

Alembic startup was fixed through config-path resolution and a CLI test from another directory. Fill/backup pipeline defects were initially reproduced only; later reports record fixes.

## Original commands — historical only

~~~powershell
docker compose -p timelog-qa -f docker-compose.test.yml up -d --build
docker compose -p timelog-qa -f docker-compose.test.yml exec -T db createdb -U timelog timelog_integration_test
$env:QA_DATABASE_URL="postgresql+psycopg://timelog:qa-password-only@127.0.0.1:5543/timelog_system_test"
.\venv\Scripts\python tools/qa_seed.py --load --reset-ui
~~~

These seed commands no longer apply to the protected demo. Health had to return 200 first; integration DB creation was once only.

Original backend run:

~~~powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://timelog:qa-password-only@127.0.0.1:5543/timelog_integration_test"
$env:COVERAGE_CORE="ctrace"
python -m coverage run --branch --source=app -m pytest -q -rx
python -m coverage report
~~~

Default tracing stalled on Python 3.14; the final initial run used ctrace. Frontend: npm ci, test:unit, lint, test:e2e; Chrome or Playwright Chromium/QA_BROWSER_CHANNEL=chromium. Root tools: python tools/qa_load.py, tools/qa_recovery.py, tools/qa_crypto.py. Docker comparison originally used QA_BASE_URL=http://web:80 and QA_IN_DOCKER=1.

Original teardown was docker compose -p timelog-qa -f docker-compose.test.yml down --volumes. **Do not run it now:** this project also contains preserved accounts/environments. Current runbook removes only designated disposable containers, retaining volumes.

## CI and exclusions

Regular CI runs unit/integration, backup fault injection and frontend units. Manual system-qa builds Docker and runs browser/load/restore, retaining evidence without dumps. GitHub workflows were not run during the initial local QA.

Not tested then: Safari/Firefox, physical phones, full WCAG, independent penetration testing, full Python/OS audit, real HTTPS/domain, multi-day persistence and production failure/restore. Sheets/story scraping were not implemented at that stage; later docs describe current Sheets functionality.

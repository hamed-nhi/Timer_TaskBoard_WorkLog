# TIME LOG QA runbook

This runbook uses synthetic accounts and a separate Docker profile. Do not point these tools at a real application database.

## Environments and safety boundaries

| Environment | HTTP | PostgreSQL | Purpose |
| --- | --- | --- | --- |
| Existing demo | `127.0.0.1:18081` | `127.0.0.1:5543/timelog_system_test` | Preserved; never reset by the audit tools. |
| Audit browser environment | `localhost:18082` | `127.0.0.1:5544/timelog_audit_test` | Persistent synthetic E2E, UI, load and recovery data. |
| Integration database | none | `127.0.0.1:5544/timelog_audit_integration_test` | Disposable schema, recreated by pytest. |

Use `localhost:18082` for manual audit review if your existing demo uses `127.0.0.1:18081`; different hostnames keep their browser cookies separate. Automated tests always use fresh browser contexts.

The audit database uses the `audit_pgdata` named volume. Neither `docker compose down --volumes` nor `--reset-ui` against the existing demo is part of this workflow. The integration fixture requires an explicit `TEST_DATABASE_URL`, checks the `_test` suffix and rejects the browser and preservation databases.

## Install QA dependencies

From the repository root, with the Python virtual environment active:

```sh
python -m pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
npm ci --prefix tools/qa-browser
cd frontend
npx playwright install chromium
```

Use `npm.cmd` on PowerShell when required. Set `QA_BROWSER_CHANNEL=chromium` to use Playwright's browser; local tests otherwise use installed Chrome. On Linux CI, install browser OS dependencies with `npx playwright install --with-deps chromium`.

## Start only the audit services

```sh
docker compose -p timelog-qa -f docker-compose.test.yml --profile audit up -d --build audit-db audit-api audit-web
```

Set `QA_DATABASE_URL` to this **synthetic audit-only** URL:

```powershell
$env:QA_DATABASE_URL='postgresql+psycopg://auditor:audit-password-only@127.0.0.1:5544/timelog_audit_test'
$env:QA_BROWSER_CHANNEL='chromium'
python tools/qa_seed.py --load --reset-ui
```

On POSIX shells, use `export QA_DATABASE_URL='...'`. The seed creates an administrator, two normal users, an inactive user and ten load-test users with 2,800 history tasks. Its sample credentials are for loopback QA only: `qa_admin`, `qa_alice`, `qa_bob` / `qa-system-password-1`. Production never runs this seed and has no default account.

`--reset-ui` replaces only the named UI fixtures and their login-attempt history. It preserves the load accounts and their saved writes. Do not reset those accounts during a load run.

## Backend and frontend checks

Create the integration database once and verify its name:

```sh
docker compose -p timelog-qa -f docker-compose.test.yml --profile audit exec -T audit-db createdb -U auditor timelog_audit_integration_test
docker compose -p timelog-qa -f docker-compose.test.yml --profile audit exec -T audit-db psql -U auditor -d timelog_audit_integration_test -tAc 'SELECT current_database()'
```

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://auditor:audit-password-only@127.0.0.1:5544/timelog_audit_integration_test'
cd backend
python -m coverage run -m pytest -q tests/unit tests/integration tests/operational --junitxml=../artifacts/audit/backend.xml
python -m coverage report
python -m coverage xml -o ../artifacts/audit/coverage.xml
```

Create `artifacts/audit` first. Coverage includes branches and must remain at least 90%. Unit tests alone require no database. Operational tests need Docker and use command fault injection in containers with no network.

```sh
cd frontend
npm run test:unit
npm run lint
npm run build
npm run test:e2e
node tests/e2e/import-devices.cjs
node tests/e2e/audit-ui.cjs
```

The import/device journey creates a fresh account, downloads templates, maps custom CSV columns, rejects invalid rows, simulates a lost commit response and tests two independent same-account sessions. It verifies refresh between devices, an edit conflict that preserves the draft, and independent logout.

The UI matrix covers nine routes, widths 320–1920, three theme choices, normal/admin roles, dialogs, keyboard focus, mobile touch and failed-network drafts. The accessibility runner uses axe-core with CSP bypass **only to inject its analysis library**. Normal E2E contexts keep CSP enforced and separately verify that injected scripts are blocked. Automated checks do not replace a human usability study or physical screen-reader/device testing.

## Mixed load and uninterrupted soak

```sh
python tools/audit_load.py --name load-windows-direct
python tools/audit_load.py --seconds 900 --name soak-release-15min
```

Ten users mix reads with task creation; every successful write is checked afterward by ID, title, duration and total count. Each run uses a separate historical date range. The gate is zero unexpected errors, all saved records present and p95 below 2 seconds. The soak also checks worker duration and activity gaps; a suspended host must not be mistaken for continuous activity. On Windows, the tool temporarily prevents automatic system sleep while it runs and restores that state on exit.

The loopback clients bypass system proxies (`trust_env=False`). Docker-network comparison uses the same script with `QA_BASE_URL=http://audit-web:80` in an ephemeral runner on `timelog-qa_audit`; mount the script read-only and keep reports in `artifacts/audit`. Never use the application's runtime image to install extra test packages; its package installer is deliberately removed.

This is a local baseline, not a production capacity guarantee.

## Data preservation and recovery

Before auditing an existing demo, run the preservation tools once:

```sh
python tools/audit_preserve.py
python tools/audit_preservation_crypto.py
```

They export a read-only, consistent PostgreSQL snapshot, verify every public table after restore, and verify an actual encrypted restore. Real dumps and the generated recovery key stay privately under `backups/pre-audit/<timestamp>/`; move an escrow copy of that key to a separate secure location. Neither keys nor dumps belong in reports, CI artifacts or Git. The crypto step refuses to overwrite an existing preservation key/archive.

For the synthetic audit environment:

```sh
python tools/audit_personal_pipeline.py
python tools/audit_recovery.py
python tools/qa_crypto.py
python tools/audit_backup_scripts.py
python tools/audit_verify_demo.py
```

Do not run restarts/recreation during a load test or browser journey. Recovery compares all public tables, restarts and recreates **only audit containers**, checks the persistent volume and verifies the same session after recovery. The personal pipeline uses a dedicated reference account containing finished/paused tasks, work segments, presence, plans, catalog, settings and separate extra minutes. It checks unchanged-source no-ops and preservation of prior backup versions after a source edit.

The deployment-script harness runs the real `backup.sh` and `restore_test.sh` with PostgreSQL and GPG. Its adapter points their Docker transport at `audit-db`; it does not mock dumping, encryption or restoration. Wrong keys and corrupt envelopes must fail.

## Security evidence

```sh
python tools/audit_dependencies.py
python -m pip_audit -r backend/requirements-sheets.txt --format json --output artifacts/audit/python-audit-final.json
python tools/audit_http_security.py
python tools/audit_zap.py
```

Install `pip-audit` separately in the QA environment when needed. The JavaScript check submits locked package names/versions to the official npm advisory endpoint and exits nonzero for findings. It includes application and accessibility-tool lockfiles.

The ZAP tool uses a pinned image and bundled rules (`-silent`, preventing a surprise rule update during startup). It creates a fresh normal user, restricts authentication to `audit-web`, runs the API policy with a bounded active-scan budget, revokes the session and redacts its token from published evidence. Account administration and login/logout/password mutation endpoints are tested by the functional security suite instead of active fuzzing.

Use Trivy to scan the final API, web, PostgreSQL and optional personal-backup images; scan only a staged copy of tracked source for secrets. Record image IDs, the scanner/database version, severity, fix availability and triage. Do not add blanket ignore rules to obtain a green result. Runtime images remove unused pip/ensurepip bundles; Caddy and the PostgreSQL privilege-drop helper are rebuilt with pinned patched Go dependencies. The PostgreSQL engine/data layout is preserved.

A completed scan is not a clean scan. Unfixed distribution findings, external-service failures and unexecuted tools must remain visible. In particular, a network error from `govulncheck` is not a zero-vulnerability result.

## Reports and limitations

Raw sanitized evidence belongs under ignored `artifacts/audit/`; private backups remain under ignored `backups/`. The report generator produces a Persian Markdown summary and a standalone HTML report with selected synthetic screenshots. Never include cookies, generated passwords, keys or private dumps.

Live Google Sheets needs a service account and a dedicated test sheet. Without them, only transport/contract simulations are verified. Real HTTPS, Safari/iOS and a physical phone remain unverified unless those environments are explicitly available.

CI runs the fast/backend checks in `ci.yml`; `system-tests.yml` provides a manually dispatched audit stack. Local commits do not publish changes or rewrite remote history.

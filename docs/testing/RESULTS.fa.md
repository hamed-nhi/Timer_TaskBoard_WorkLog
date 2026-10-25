> Historical initial report. See [current release results](RELEASE_RESULTS.fa.md), [the later audit](AUDIT_RESULTS.fa.md) and [the runbook](AUDIT_RUNBOOK.md).

# TIME LOG system test report

Timestamp: 2026-10-25T09:36:47+03:30

## Main result

Core journeys, isolation and browser checks passed. This does not mean defect-free or fully production-ready; backup and boundary defects were open at this stage.

- Backend/operations: 209 passed; seven expected failures representing five open defects.
- Frontend units: 12 passed. Browser: 44/44 executable scenarios passed.
- Coverage: lines 94.82%, branches 87.22%, combined 93.40%.
- Seventy designed scenarios with prerequisites, steps and evidence.
- Docker-network load: 400 requests, zero errors, p95 317.98 ms.
- Windows route: five transport errors in 1,200 recorded requests; root cause not yet confirmed.
- Restore: all 12 table fingerprints matched; session survived restart; API recovered in 5.36 seconds.
- Real AES256 encryption/decryption matched SHA256 and rejected the wrong password.
- Real API/Next/Caddy builds and lint passed. Alembic startup was fixed and retested.

## Findings and actions

### QA-001 — Rounding exceeds a short task's 50% cap

Severity: medium. Historical status: open.
Reproduction: suggest_fill for a six-minute task with a 100-minute deficit suggests five minutes.
Expected: this task's fill cap is three minutes.
Location: backend/app/services/fill.py:suggest_fill.
Action: round below each task's cap and distribute the remainder without breaking caps.

### QA-002 — Rounded aggregate exceeds the allowed gap

Severity: medium. Historical status: open.
Reproduction: two 60-minute tasks, weight one, eight-minute gap receive ten minutes total.
Expected: do not exceed the server cap; the application's own suggestion must be saveable.
Location: backend/app/services/fill.py:suggest_fill.
Action: aggregate-aware rounding and suggestion-to-save roundtrip tests.

### QA-003 — Invalid date type produces 500

Severity: medium. Historical status: open.
Reproduction: POST /api/fill with date 123, [1] or an object, and empty items.
Expected: controlled 400, no internal error.
Location: backend/app/services/fill.py:parse_day.
Action: validate type and convert TypeError into ApiError too.

### QA-004 — Failed pg_dump can produce false backup success

Severity: high. Historical status: open.
Reproduction: pg_dump exits 17, but encryption consumer exits zero with nonempty output; script exits zero.
Expected: dump-producer failure immediately fails the backup.
Location: deploy/backup.sh.
Action: independently verify dump production; publish valid output only; retest with real GPG after fixing.

### QA-005 — Pipeline does not independently check decryption failure

Severity: medium. Historical status: open.
Reproduction: injected gpg failure with successful fake pg_restore still reports script success.
Expected: preserve failure from every stage even when the consumer succeeds.
Location: deploy/restore_test.sh.
Action: check decryption separately. This finding does not claim that actual restore succeeds with arbitrary wrong passwords.

### QA-006 — Docker startup stopped at Alembic

Severity: high. Status: fixed.
Reproduction: Python 3.13 image failed alembic upgrade head with ModuleNotFoundError: app.
Expected: resolve the application independently of cwd/executable location.
Location: backend/alembic.ini.
Action: anchor script_location/prepend_sys_path to %(here)s. CLI and Docker-stack checks passed.

### QA-007 — Windows-to-Docker connections reset under load

Severity: requires investigation. Historical status: observed.
Reproduction: five WinError 10054 disconnects among 1,200 requests across three host runs; zero among 400 Docker-network requests.
Expected: no transport errors on the intended usage path.
Evidence: artifacts/testing/load-run1.json through load-run3.json; load-linux.json.
Action: investigate forwarding/keep-alive and actual server environment. Comparing routes alone does not establish root cause.

### QA-008 — npm findings in PostCSS/Next chain

Severity: high/moderate. Historical status: audit finding.
Reproduction: full audit reported two affected packages, one high/one moderate, mainly transitive PostCSS.
Expected: fixed versions or a documented assessment of build-path impact.
Evidence: artifacts/testing/npm-audit.json.
Action: assess a compatible upgrade and retest. npm audit fix --force was not run; production-only audit failed due to network issues.

## Evidence and limits

JUnit, coverage JSON, browser results/screenshots, load and restore evidence are in artifacts/testing. report.html is the searchable report. Load figures apply only to the local synthetic dataset.

Seven xfails are not passes: defects were executed/reproduced. New CI was written but not run on GitHub. This initial QA did not deploy a real server or change real data.

Not tested then: Safari/Firefox/physical phones, full WCAG/independent penetration testing, real HTTPS/domain/server, long soak/failover/production PostgreSQL failure, full Python/OS audit, definitive Windows disconnect cause, and GitHub workflow execution.

# TIME LOG audit report — 2026-10-25

> Initial audit history. Later login, administration, backup onboarding and deployment features are covered in [current release results](RELEASE_RESULTS.fa.md).

**Functional acceptance: passed. Release security: open/conditional; images are not fully clean.**

Local checks used an isolated audit environment. Failures, skips, xfails and unexecuted checks are not counted as success.

## Results

| Area | Count/criterion | Failures | Evidence/scope |
| --- | --- | --- | --- |
| Backend Unit / Integration / Operational | 325 | 0 | Real PostgreSQL; protected DBs rejected; no xfail/skip. |
| Combined line/branch coverage | 91.23% | Minimum 90% | coverage.xml / coverage.txt |
| Frontend units | 15 | 0 | Time/date formatting and display calculations. |
| Browser E2E and roles | 46 | 0 | Admin, two ordinary users, inactive user; touch, sessions, logout. |
| UI/UX/accessibility | 341 | 0 | Nine pages, 320–1920, light/dark/system, axe/keyboard. |
| Import and two devices | 10 | 0 | Templates, mapping, lost response, refresh/conflict. |
| Final direct load | 400 | 0 | p95=573.62 ms; saved writes verified. |
| Final continuous soak | 9000 | 0 | Ten users, 2250 writes; p95=295.13 ms. |
| Internal Docker comparison | 400 | 0 | p95=454.87 ms. |

Backend breakdown: unit 79, integration 241, operational 5. Skips: zero. Lint, static-export build and migration-drift checks also passed. Security tests are part of the backend count, not counted twice.

## Data preservation and real usage

- At this audit stage, 18081, its accounts and desktop data were unchanged. New code was available only at localhost:18082.
- Before testing, a consistent snapshot of existing data was encrypted and restored separately; all 14 table fingerprints matched. Dump/key were excluded from reports/Git.
- Previous business data remained equal to baseline; normal active-session expires_at/last_seen_at renewals were recorded separately.
- A complete reference account included finished/paused tasks, segments, attendance, tags, catalog, plans, settings and fill. Actual time was never converted into fill.
- The real backup job created no new files/mtime changes for unchanged source. Source editing created a second version while retaining original bytes.
- Audit restart/recreation with its persistent volume preserved every table and the session. Actual dump/restore, wrong passwords and truncated archives were tested.
- Final uninterrupted load: each worker active at least 900.42 seconds, maximum idle gap 1.02 seconds, 2250 verified writes. Local p95 threshold was two seconds; this is not a production capacity guarantee.
- A host-monitoring pause affected an intermediate run, which did not qualify as a continuous 15-minute soak. Final evidence explicitly records worker activity/gaps.
- Desktop/phone browsers had independent sessions. Edits refreshed across devices without reload; logging out on one did not log out the other.

## Confirmed fixes

| ID | Problem | Fix/result | Regression |
| --- | --- | --- | --- |
| QA-001/002 | Rounded fill suggestion exceeds caps | Floor five-minute steps; per-task/aggregate caps checked across 2000 randomized inputs. | test_time_boundaries |
| QA-003/009 | Invalid or explicitly empty invalid date | Explicit 400; no 500 or unintended default date. | test_journeys / test_security_audit |
| QA-004/005 | False pipeline success in backup/restore | Independently check dump, archive validity, encryption, decryption and restore. | test_backup_failures / backup-scripts.json |
| QA-006 | Pause/resume/finish race | Disable controls while pending; tests await actual responses. | E2E-04 / E2E-53 |
| QA-007 | Loopback load traverses Windows proxy | Direct local clients; initial disconnect retained as an environment failure. | load-proxy-baseline / load-release-direct |
| QA-008 | Vulnerable nested PostCSS in Next | Compatible 8.5.31 override, npm ci/lint/build; no forced major upgrade. | npm-advisories-before / npm-advisories |
| QA-010/011 | Bypass blocked state/fill cap through API | Reject/rollback positive blocked-day fill or values beyond contract precision. | test_security_audit |
| QA-012 | User text becomes an Excel formula | Export text explicitly as strings; HYPERLINK title never executes. | test_excel_user_text_is_never_executed_as_a_formula |
| QA-013 | Private caching/missing CSP | API no-store; only hashed static inline scripts; injected script blocked. | http-security / E2E-57 |
| QA-014 | Imported task lacks clocks or duration differs | Metadata edits never repair/round duration; 60.12345 preserved. | test_tabular_import / import-precision-red |
| QA-015 | Stale edit from a second device | Revision/409 preserves newer server data and local draft. | test_stale_device / import-devices |
| QA-016 | Repeated import or lost post-commit response | Repeat is no-op; genuine identical rows retained; old file cannot undo later edits. | test_tabular_import / import-devices |
| QA-017 | Wrong row number after blank lines | Report physical file row numbers. | test_errors_keep_physical_row_numbers |
| UI-01 | Chart/calendar accessible roles/names | Separate day button from auxiliary dates; correct chart focus/name. | axe route matrix |
| UI-02 | Contrast/control labels | Correct light/dark buttons and Daylog checkbox. | axe light/dark and dialogs |
| UI-03 | Lost focus after task menu | Return focus to trigger/main after deletion; test Escape/focus trap. | keyboard-focus-red / keyboard menu scenarios |
| UI-04 | Long import form with optional mappings | Automatic detection/short preview; expand mapping only when needed. | import-devices screenshots |
| IMG-01 | Vulnerable installers/binaries | Remove pip/ensurepip; rebuild Caddy/gosu with Go 1.27.3/patched dependencies. | Trivy before/after |

## Final image scans

| Image | Critical | High | Medium | Low | Unknown | Fixed version available |
| --- | --- | --- | --- | --- | --- | --- |
| API | 0 | 44 | 58 | 61 | 1 | 0 |
| Web / Caddy | 0 | 0 | 0 | 0 | 1 | 0 |
| PostgreSQL | 1 | 61 | 109 | 138 | 4 | 0 |
| Personal backup | 0 | 44 | 58 | 61 | 1 | 0 |

npm: zero advisories among 394 locked packages. Python app/Sheets dependencies: zero known vulnerabilities. Source secrets: zero detected; private files were never in source-scan/Git scope.

## Open findings and limits

- Debian findings remain in API/job/PostgreSQL. No final finding had an available fixed version, which does not make unfixed findings harmless.
- PostgreSQL libxml2 CVE-2026-6653 remains CRITICAL in scanner output. Debian trixie lists it vulnerable with a Minor issue/no-dsa vendor note. The application does not feed XML to DB XML functions; this observation is not a library fix or proof of unreachability.
- Caddy crypto-module GO-2026-5932 concerning legacy openpgp remains UNKNOWN. Independent govulncheck failed with public-database HTTP 403, not a clean result.
- Authenticated ZAP scanned 55 API paths under the API policy. Low warning for root HTML was expected; malformed-input 4xx responses were informational. No 5xx/high finding appeared in this bounded run; this is not a full penetration test.
- JavaScript auditing used npm's official advisory endpoint. The initial npm audit transport failed; that attempt was not counted as success.
- Live Sheets requires a service account/dedicated sheet; simulations/contracts covered ownership, destination edits, deletions and network failure.
- Real HTTPS, Safari/iOS, Firefox and physical phones were unverified. Mobile tests used Chrome viewport/touch emulation.
- GitHub Actions did not run remotely and production was not deployed. Writing a workflow does not execute it.
- The old 18081 DB uses tmpfs; do not treat it as permanent or stop it without migration/backup. Main Compose/audit use persistent volumes.

## Delivery and reproduction

- [Runbook](AUDIT_RUNBOOK.md); tests in backend/tests and frontend/tests/e2e; operational tools in tools/audit_*.py.
- Ignored local evidence/HTML under artifacts/audit; package artifacts/TIME-LOG-QA-2026-10-25.zip.
- JUnit, coverage, load/security JSON, synthetic screenshots and restore fingerprints retained; no dumps, keys, cookies or generated passwords in delivery.
- English README, TIME LOG branding and Excel/CSV templates updated; layer boundaries/entrypoints preserved; import needed no migration.
- Owner explicitly authorized publishing the version/rewritten history to GitHub. Actual production deployment/GitHub Actions execution are outside this result.

Primary triage sources: [Debian libxml2](https://security-tracker.debian.org/tracker/CVE-2026-6653), [Go openpgp advisory](https://pkg.go.dev/vuln/GO-2026-5932), [ZAP API Scan scope](https://www.zaproxy.org/docs/docker/api-scan/).

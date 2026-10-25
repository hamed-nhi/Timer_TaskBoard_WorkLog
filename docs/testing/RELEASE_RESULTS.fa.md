# TIME LOG release test results — 2026-10-25

**Functional acceptance: passed. Security is not declared unconditionally clean.**

| Check | Count/criterion | Result/failures |
| --- | --- | --- |
| Backend Unit / Integration / Operational | 402 | 0 |
| Combined coverage | 90.94% | Minimum 90% |
| Frontend units | 15 | 0 |
| Main E2E | 46 | 0 |
| UI/UX, nine pages at 320–1920 | 341 | 0 |
| Import/two devices | 10 | 0 |
| Browser security, admin, onboarding, own password | 14 | 0 |
| Mobile onboarding/axe | 390px/touch | Passed |
| Fresh production Compose/real scheduler | Empty DB/persistent volume | Passed |
| Ordinary ten-user load after flood gate | 300 requests | Zero unexpected errors |
| API request burst | 1000 | 798 HTTP 429; zero unexpected errors |

## Behavior and evidence

- Report date: 2026-10-25. This describes the release after login-security/backup additions. AUDIT_RESULTS covers the earlier audit/15-minute soak; that long test is not presented as a repeat against this release.
- PostgreSQL bans an IP/account pair after three wrong passwords: 15 minutes, then 10 hours, then 30 days for this and later stages. Three unknown names ban the entire IP for 24 hours. Banned requests do not extend the deadline. Successful login clears that pair's escalation by default; the administrator can change this.
- Admins configure attempts, durations and complementary IP/global budgets, release bans or reset stages. A real defect left short admission counters after release; it was fixed and regression-tested for immediate login. Console recovery was tested on a clean installation.
- Tested chosen/generated passwords, account creation, username/display-name/role/password edits and activation/deactivation. No account-delete API exists. Deactivate/reactivate left complete task rows identical. Credential changes revoke account sessions.
- New passwords at every web/CLI setter require at least eight characters, uppercase/lowercase, a digit and symbol. Existing passwords are not silently changed on login. Self-service changes preserve the current session and revoke the others.
- Public captcha config comes from backend; Secret never reaches browser. Missing/rejected/malformed tokens, network failures, oversized responses, redirects and concurrent replay cannot create sessions. Provider remains disabled because real keys were not supplied.
- A bounded memory gate rejects excess traffic before JSON/routing/SQL. Logical tests used 10,000 IP identifiers; an actual burst sent 1,000 API requests. Memory bounds/thread races were checked. This is not a full botnet or volumetric attack simulation.
- First use explains private sheet creation, Editor permission for the service account, URL saving and private Excel download. Completion is per-user/persistent. Invalid URL cannot mark setup complete. Users can continue without a sheet and reopen setup in Settings.
- Docker scheduler runs initially/daily at 03:00 Tehran, retries after 15 minutes and stores its marker on a volume. A real job passed on a fresh installation; unchanged input created no new/overwritten snapshot. Controlled clocks tested schedules; no real full-day wait was claimed.
- Main production Compose ran separately on an empty DB. Migration 0004, CLI admin creation, health, backup-scheduler and force-recreation were tested. Data/session persisted.
- Owner separately approved the 18081 upgrade. Beforehand, a dump restored elsewhere with every table fingerprint equal. Only API/web were upgraded; its DB container was not recreated. Pre-existing personal tables remained equal.
- Three requested accounts in both environments retained IDs/roles; all six logins passed. Setup completion was reset for first human use and test sessions revoked. Real names/passwords are absent from Git/delivery.
- Initial load setup hit login limits while browser work was active; that 429 result was not passed. Ordinary load staggered session starts according to admission policy while ten users' actual workloads remained concurrent.
- Two test expectations were corrected: old create-user button wording and expecting a Persian word in the Google Sheet error. Assertions were retained; complete journeys reran successfully. xfail/skip are not success.

## Limits

- Live Sheets was not tested without a real service account, sheet and permissions. A saved URL is not proof of delivery; DEPLOY specifies setup/access.
- Live ARCaptcha lacks Site/Secret keys. Server/widget contracts used controlled responses. When enabled, an outage blocks new login rather than bypassing captcha.
- Volumetric DDoS/CDN/WAF, destination DNS/real HTTPS, Safari/iOS and physical phones remain unverified. The bounded memory gate is per-process, resets on restart and multiplies with replicas; PostgreSQL bans persist.
- Images are not fully clean. Debian findings lack available fixes. Earlier PostgreSQL libxml2 CVE-2026-6653 was CRITICAL and remains vendor-open; Caddy GO-2026-5932 remains UNKNOWN. Independent govulncheck failed with HTTP 403, not a clean result.
- Current Python audit found no known dependency vulnerability; source scan detected zero secrets. This does not prove absence of all weaknesses. Private files were outside source/Git scope.
- The old local DB uses tmpfs, not production storage. Main server Compose/fresh-install smoke use persistent volumes. Encrypted DB/off-server backups remain necessary.

## Reproduction and delivery

- [Server guide](../../DEPLOY.md); [test commands](AUDIT_RUNBOOK.md).
- Sanitized local evidence: artifacts/audit/release-summary.json, JUnit, coverage, browser/smoke/scans.
- HTML/ZIP exclude dumps, keys, cookies and real account names/passwords. The private credentials file is ignored/untracked.
- Primary references: [ARCaptcha Verify](https://github.com/arcaptcha/arcaptcha-docs/blob/main/versioned_docs/version-4.0.0/API/Verify.md), [Caddy header rules](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers).

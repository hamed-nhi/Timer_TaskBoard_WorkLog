# Codebase Concerns

> Current feature update (2026-10-24): catalogs are now PRIVATE per account. The original snapshot below describes the pre-change architecture where it mentions a shared catalog. See backend/app/routers/catalog.py, backend/alembic/versions/0002_private_catalog.py, and backend/tests/test_private_catalog.py. All users can manage their own catalog at /api/catalog; only account administration is admin-only. Personal JSON backups include catalogs. CLI catalog import requires --user. Database composite foreign keys reject cross-owner catalog/tag links. Legacy catalog originals remain ownerless and hidden; referenced records are copied per owner. Test setup now refuses database names without the _test suffix.


Source review at 2707511 on 2026-10-24. Findings below are static observations; no fixes, runtime exploit tests or deployment trials were performed.

## Core Sections (Required)

### 1) Top Risks (Prioritized)
| Severity | Concern / impact | Evidence | Suggested action |
|---|---|---|---|
| High | Backup pipeline can mask pg_dump failure; encrypted output can still be nonempty | deploy/backup.sh | Check producer status and publish backup only after success; verify recovery |
| High | Test setup drops public schema for whichever TEST_DATABASE_URL is supplied | backend/tests/conftest.py | Assert disposable target before running tests |
| Medium | Manual fill ignores presence_sanity blocked result, although suggestions respect it | backend/app/routers/fill.py | Clarify manual exception and test Friday/suspect-presence submissions |
| Medium | UI promises nightly Sheets sync, implementation only saves URL | frontend/app/(app)/settings/page.tsx; backend/app/routers/settings_me.py | Align wording with implemented behavior |
| Medium | Full compose, recovery and current mobile acceptance not verified here | docs/HANDOFF.md | Validate in disposable environments before deployment |

### 2) Technical Debt
| Item | Evidence / gap | Suggested action |
|---|---|---|
| Diverging plan and reality | docs/PLAN.md vs models.py/timeutil.py: timestamptz -> naive DateTime; time -> String(5); bigint -> Integer; citext -> lowercase String | Document current contracts before schema work |
| Task-start behavior divergence | PLAN says auto-pause; tasks.py rejects second running task; test_overlap.py agrees with code | Preserve tested behavior unless explicitly changed |
| Runtime/deployment differences | Python 3.12/two workers in PLAN; Docker selects 3.13 and default uvicorn worker count | Use current configs for operating instructions |
| Backup contract incomplete | Sunday weekly vs Friday; 03:00 cron vs 02:30 plan; no latest symlink or Windows 30-copy retention | Align intended recovery policy and scripts |
| Theme/responsive differences | PLAN dark mode and 768 breakpoint; globals.css light styles and main 760 breakpoint | Treat HANDOFF/current CSS as current implementation |
| Sheets and scraper pending | docs/HANDOFF.md; no jobs module in tree | Keep these listed as unimplemented |

### 3) Security Concerns
| Risk | Evidence | Existing mitigation / remaining gap |
|---|---|---|
| Wrong DB in test environment | conftest.py reads arbitrary TEST_DATABASE_URL | Dedicated default exists, explicit target guard absent |
| Passphrase visibility | backup.sh/restore_test.sh use --passphrase argument | Encrypted output, but passphrase-file approach from PLAN absent |
| HTTP cookie setup mismatch | .env.example defaults :80 and secure=true | Comment explains required override; setup must apply it |
| Concurrent login attempts | auth.py checks and records failures in separate steps | DB-based lockout exists; concurrent threshold behavior unverified |

Tenant isolation uses user filters and ownership validation; no claim of a complete security audit is made. Existing CSRF header, SameSite cookie, password hashing, token digests and admin dependencies are visible in source.

### 4) Performance and Scaling Concerns
| Concern | Evidence | Observed / potential impact |
|---|---|---|
| Unpaginated history | routers/tasks.py, reports.py | Fetches and aggregates rows in Python; no measured slowdown |
| Per-tag and per-day queries | tags.py budget_info loop; presence.py presence_history | Query count grows with tags/days; no load measurement |
| Broad revalidation | frontend/lib/data.tsx refreshAll | Mutations refresh many cached API entries |
| Per-user write serialization | backend/app/db.py lock_user | Correctness-oriented; throughput under contention unmeasured |

### 5) Fragile/High-Churn Areas
Last 90-day git scan: tasks.py appears in two commits; most other listed files once. Only five commits exist in inspected recent history, so this is a limited churn signal.
tasks.py combines lifecycle, time edits and ownership handling; reports.py combines several report formats. Preserve segment/adjust/fill distinctions and run targeted regression tests for changes.
No production TODO/FIXME/HACK marker was reported by the scan; this is not evidence of no debt.
Raw scan was removed after its verified findings were incorporated into these seven files.

### 6) [ASK USER] Questions
No new question is required for this read-only onboarding. Existing deployment unknowns from PLAN/HANDOFF remain recorded as [TODO]: domain, server OS/RAM/Docker readiness, expected user count and access to Google Sheets. They do not block understanding the repository.

### 7) Evidence
- docs/PLAN.md
- docs/HANDOFF.md
- backend/app/models.py
- backend/app/timeutil.py
- backend/app/routers/tasks.py
- backend/app/routers/fill.py
- backend/tests/conftest.py
- backend/tests/test_overlap.py
- frontend/app/(app)/settings/page.tsx
- deploy/backup.sh
- deploy/restore_test.sh
- deploy/pull_backup.ps1
- git log -5 and git log --name-only --since=90.days (scan)

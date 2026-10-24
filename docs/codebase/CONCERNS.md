# Codebase Concerns

## Prioritized operational risks
| Priority | Concern | Evidence / next action |
|---|---|---|
| High | sh backup pipeline can mask pg_dump failure | deploy/backup.sh; check producer status and verify recovery before relying on it |
| Medium | Manual fill ignores the presence-sanity blocked flag while suggestions respect it | app/services/fill.py; clarify/test manual policy before changing behavior |
| Medium | Settings UI promises Sheets sync but service only stores a URL | frontend/src/features/settings/view.tsx; app/services/settings.py |
| Medium | Full compose deployment, recovery and real load unverified | docs/HANDOFF.md; run disposable deployment/recovery/load acceptance |
| Low | Dedicated Python formatting/lint not configured | requirements-dev.txt; add consistently when adopted |

## Structural work completed
HTTP adapters now delegate to services; cross-router business imports are removed. Config/security/errors/time have explicit core ownership, and schema/session have a db package.
Frontend route files are thin, features own UI and shared/lib imports are guarded. Integration fixtures no longer run for unit tests.
No ORM repository abstraction, distributed service, queue or placeholder directory was added.

## Security and data
Private catalog ownership is enforced at API and database levels, including administrator requests. Persistent sessions retain logout/expiry/revocation behavior. Integration DB setup rejects names without the _test suffix.
Backup passphrases still use process arguments. Login failure check/record steps remain separate; concurrent threshold behavior is not load-tested.

## Performance
Task lists are unpaginated; reports aggregate rows in Python. Per-tag budget and per-day presence queries can grow with history. refreshAll revalidates many API entries, and writes are serialized per user.
These are source observations, not measured production slowdowns. New folder boundaries do not remove the need for query/load measurements.

## History and safe changes
Before restructuring, tasks.py was the only file with two changes in the limited five-commit onboarding history; this is not a long-term churn metric. Now time edits remain a sensitive area in services/tasks.py/timecalc.py.
Schema migrations and actual user data were not changed by the structural refactor.
No new user decision is required for this layout. [TODO] Existing deployment unknowns remain: domain, server OS/RAM, expected user count and Google access.

## Evidence
- backend/app/services/tasks.py
- backend/app/services/timecalc.py
- backend/app/services/fill.py
- backend/app/services/tags.py
- backend/app/services/presence.py
- backend/app/services/auth.py
- backend/tests/unit/test_architecture.py
- deploy/backup.sh
- frontend/src/lib/data.tsx

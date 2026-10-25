# Web UI review — 2026-10-25

> Historical responsive-redesign review. Counts/open defects describe that stage, not the current release; see [RELEASE_RESULTS.fa.md](RELEASE_RESULTS.fa.md).

## Changes

- Removed the 920px cap: shell grows to 1920px, with approximately 1570px main content at Full HD and separate sidebar space.
- Primary routes appear in a sidebar from 1100px; tablets use top and phones bottom navigation.
- Quick task entry comes first on Today. Attendance/goals occupy a side column when possible. Attendance help collapses; check-in is beside the form.
- Calendar/plans/settings respond to content width; wide tables scroll internally.
- Light/dark/system themes persist in-browser, apply before first paint, and cover forms/menus/calendar/dialogs.
- New catalog stories appear in the task selector and link through a prefilled confirmation, without searching tag management.
- Dialogs/row menus portal into body to avoid clipping/displacement from columns/container queries. Dialogs trap focus, close on Escape and restore prior focus.
- Gregorian month values in calendar titles/date descriptions are numeric.

## Attendance warnings

GET /api/presence/alerts compares dates before today in Tehran; optional date=YYYY-MM-DD selects one day. Report time is stored actual plus fill. All tasks, including outside-company work, participate. Missing attendance means zero.

Today/Daylog warnings show attendance/task totals/difference. Correct attendance adds/edits historical intervals; View tasks opens that report. Past attendance requires an end time. Current-day time is not capped or auto-corrected.

Old open tasks/attendance are capped at that day's midnight in this read-only comparison, avoiding inflation over later days without rewriting original time. Show the latest 50 mismatched days; older dates remain checkable through their reports. Preserve existing API contracts, adding only the new route's fixture.

## Verification and limits at that stage

- 241 backend unit/integration tests passed; five earlier xfails remained, not accepted as correct behavior. Separate timelog_personal_backup_test was used; demo/real data were not cleared.
- Fifteen frontend tests, lint, static export and API/web Docker builds passed in timelog-qa.
- The in-app browser checked Today, Plans, Daylog, Dashboard, Calendar, Timesheet, All tasks, Settings and Management in two themes at 320/360/390/768/1024/1366/1920: 126 combinations. No off-screen controls or page-wide horizontal scroll; wide charts/tables scroll inside themselves.
- A two-hour historical task produced a zero-attendance warning. Missing end time was rejected; actual 09:00–11:00 attendance removed it without changing task time.
- Direct story selection/linking, dialog focus cycling, theme persistence and mobile navigation were interactively checked.
- Evidence: artifacts/testing/ui-redesign. Viewports emulate dimensions, not physical phones, Safari/iOS or every zoom level.
- Live Sheets/server cron required credentials/deployment; see [personal backups](../PERSONAL_BACKUPS.fa.md).

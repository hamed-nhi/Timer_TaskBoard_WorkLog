# Usage scenarios and recorded results

> Historical initial QA matrix. Recorded open defects describe that run; subsequent fixes/current acceptance are in [RELEASE_RESULTS.fa.md](RELEASE_RESULTS.fa.md).

| ID | Area | Scenario | Result |
| --- | --- | --- | --- |
| AUTH-01 | Authentication | Successful login and secure cookie | Passed |
| AUTH-02 | Authentication | Username case and whitespace | Passed |
| AUTH-03 | Security | Unknown user and wrong password | Passed |
| AUTH-04 | Security | Three-attempt lock and expiry | Passed |
| AUTH-05 | Security | Per-IP failure cap | Passed |
| AUTH-06 | Security | Anonymous requests and CSRF | Passed |
| AUTH-07 | Sessions | Reopen the browser | Passed |
| AUTH-08 | Sessions | Active-session renewal | Passed |
| AUTH-09 | Sessions | Expiry and revocation | Passed |
| AUTH-10 | Sessions | Password change and deactivation | Passed |
| CAT-01 | Catalog | Private management through UI | Passed |
| CAT-02 | Administration | Administrator creates an account | Passed |
| CAT-03 | Catalog | Identical names in two accounts | Passed |
| CAT-04 | Isolation | Guess another user's catalog ID | Passed |
| CAT-05 | Isolation | Attach foreign tag/type/story | Passed |
| CAT-06 | Catalog | Delete a referenced item | Passed |
| CAT-07 | Catalog | Repeated JSON import | Passed |
| TASK-01 | Tasks | Live lifecycle | Passed |
| TASK-02 | Tasks | Manual entry across midnight | Passed |
| TASK-03 | Tasks | Repeated finish and reopen | Passed |
| TASK-04 | Tasks | Edit title without changing time | Passed |
| TASK-05 | Tasks | Edit clocks with pauses/adjustments | Passed |
| TASK-06 | Tasks | Actual overlap and pause gaps | Passed |
| TASK-07 | Tasks | Auditable deletion | Passed |
| PLAN-01 | Planning | Start planned work | Passed |
| TAG-01 | Tags and budgets | Budget and date scope | Passed |
| TAG-02 | Tags and budgets | Merge and rename | Passed |
| PRES-01 | Attendance | Check-in, temporary exit and finish | Passed |
| PRES-02 | Attendance | Missing check-in reminder | Passed |
| PRES-03 | Attendance | Edit intervals and overlap | Passed |
| FILL-01 | Report fill | Complete daily-report journey | Passed |
| FILL-02 | Report fill | Touch/form preview and confirmation | Passed |
| FILL-03 | Report fill | Weights, meetings and target | Passed |
| FILL-04 | Report fill | Invalid attendance and Friday | Passed |
| FILL-05 | Transactions | Failure during multi-task save | Passed |
| FILL-06 | Boundaries | Six-minute task cap | Open defect |
| FILL-07 | Boundaries | Rounding and aggregate cap | Open defect |
| FILL-08 | Validation | Invalid date type | Open defect |
| REPORT-01 | Reports | Saturday–Friday timesheet | Passed |
| REPORT-02 | Reports | Compare equal-length periods | Passed |
| REPORT-03 | Reports | Jalali calendar/events | Passed |
| REPORT-04 | Reports | Empty Excel and year filter | Passed |
| REPORT-05 | Isolation | Private exports | Passed |
| IMPORT-01 | Migration | Read desktop copy safely | Passed |
| IMPORT-02 | Migration | Mismatch/nonempty account | Passed |
| IMPORT-03 | Schema migration | Upgrade 0001 to 0002 | Passed |
| CONC-01 | Concurrency | Parallel starts for one user | Passed |
| CONC-02 | Concurrency | Parallel stops | Passed |
| CONC-03 | Concurrency | Parallel same-name creation | Passed |
| CONC-04 | Concurrency | Two users work concurrently | Passed |
| UI-01 | Frontend | Persian digits and clocks | Passed |
| UI-02 | Browser security | SQL/HTML-looking title | Passed |
| UI-03 | Resilience | Disconnect during submission | Passed |
| UI-04 | Responsive | All pages at three widths | Passed |
| UI-05 | Touch | Task lifecycle by touch | Passed |
| UI-06 | Time | London browser and Tehran server | Passed |
| UI-07 | Navigation | Mobile More and reports | Passed |
| OPS-01 | Docker | Real stack startup | Passed |
| OPS-02 | Recovery | Actual dump/restore | Passed |
| OPS-03 | Resilience | API restart | Passed |
| OPS-04 | Backup fault injection | Dump producer fails | Open defect |
| OPS-05 | Backup fault injection | Decryption fails | Open defect |
| OPS-06 | Backup fault injection | Encryption/pg_restore fails | Passed |
| PERF-01 | Performance | Multi-user load | Needs investigation |
| SEC-01 | Dependencies | npm package audit | Audit finding |
| ARCH-01 | Architecture | Stable boundaries and contracts | Passed |
| SET-01 | Transactions | Invalid/valid settings in one request | Passed |
| CLI-01 | CLI | Create account/reset password | Passed |
| CLI-02 | CLI | Import catalog for one account | Passed |
| OPS-07 | Encryption | AES256 and wrong password | Passed |

## AUTH-01 — Successful login and secure cookie

- Prerequisite: Active account created by an administrator
- Steps: Submit the correct username/password
- Expected: Today opens; expiring HttpOnly cookie
- Result: Passed
- Evidence: E2E-01, test_login_logout_and_cookie_flags

## AUTH-02 — Username case and whitespace

- Prerequisite: Active account
- Steps: Log in with uppercase letters and surrounding spaces
- Expected: Same account is authenticated
- Result: Passed
- Evidence: test_username_is_case_insensitive

## AUTH-03 — Unknown user and wrong password

- Prerequisite: Signed out
- Steps: Submit wrong password, then nonexistent username
- Expected: Identical 401 messages
- Result: Passed
- Evidence: test_wrong_password_and_unknown_user

## AUTH-04 — Three-attempt lock and expiry

- Prerequisite: Active account
- Steps: Three wrong passwords, correct password, then advance time
- Expected: 429 with Retry-After, then successful login
- Result: Passed
- Evidence: test_lockout_after_three_failures

## AUTH-05 — Per-IP failure cap

- Prerequisite: Several usernames from one IP
- Steps: Ten failures, then another attempt
- Expected: 429
- Result: Passed
- Evidence: test_ip_lockout_after_ten_failures

## AUTH-06 — Anonymous requests and CSRF

- Prerequisite: No session or missing header
- Steps: Read private data and write without the required header
- Expected: 401 and 403
- Result: Passed
- Evidence: test_anonymous_cannot_use_the_api, test_csrf_header_required

## AUTH-07 — Reopen the browser

- Prerequisite: Valid cookie
- Steps: Close test Chrome and reopen the same profile
- Expected: Authentication persists
- Result: Passed
- Evidence: E2E-11

## AUTH-08 — Active-session renewal

- Prerequisite: Old but valid session
- Steps: Use after 20 days and beyond original expiry
- Expected: Renew for 90 days
- Result: Passed
- Evidence: test_session_is_renewed_after_activity

## AUTH-09 — Expiry and revocation

- Prerequisite: Old token
- Steps: Logout, replay token, and test expiration
- Expected: 401 without session resurrection
- Result: Passed
- Evidence: E2E-51, test_expired_session_is_rejected

## AUTH-10 — Password change and deactivation

- Prerequisite: Two sessions for one account
- Steps: Change password or deactivate account
- Expected: Affected sessions revoked
- Result: Passed
- Evidence: test_change_password_drops_other_sessions, test_inactive_user_cannot_log_in

## CAT-01 — Private management through UI

- Prerequisite: Ordinary user
- Steps: Create report type, project and story
- Expected: Owned by that account; no account-management access
- Result: Passed
- Evidence: E2E-02

## CAT-02 — Administrator creates an account

- Prerequisite: Administrator account
- Steps: Create an account in Management
- Expected: Account created; others' catalogs remain hidden
- Result: Passed
- Evidence: E2E-10, test_admin_only_routes

## CAT-03 — Identical names in two accounts

- Prerequisite: Two users
- Steps: Create same-named records, then duplicate within one account
- Expected: Independent IDs; own duplicate returns 409
- Result: Passed
- Evidence: test_duplicate_names_are_private

## CAT-04 — Guess another user's catalog ID

- Prerequisite: Foreign account identifier
- Steps: Edit/delete, including as administrator
- Expected: 404; owner's data preserved
- Result: Passed
- Evidence: test_foreign_ids_are_404_even_for_admin

## CAT-05 — Attach foreign tag/type/story

- Prerequisite: User-owned data
- Steps: Submit a foreign ID through API and test SQL
- Expected: API rejection and database constraint enforcement
- Result: Passed
- Evidence: test_foreign_catalog_cannot_be_attached, test_database_rejects_cross_account

## CAT-06 — Delete a referenced item

- Prerequisite: Catalog linked to a tag
- Steps: Delete report type, story or project
- Expected: 409; references retained
- Result: Passed
- Evidence: test_used_catalog_items_cannot_be_removed

## CAT-07 — Repeated JSON import

- Prerequisite: Private catalog
- Steps: Import the same JSON twice
- Expected: No duplicates or effects on others
- Result: Passed
- Evidence: test_catalog_import_is_idempotent

## TASK-01 — Live lifecycle

- Prerequisite: Ordinary user
- Steps: Start, pause, resume and finish
- Expected: Done task with correct duration
- Result: Passed
- Evidence: E2E-04, test_pause_resume_stop_lifecycle

## TASK-02 — Manual entry across midnight

- Prerequisite: Nonoverlapping interval
- Steps: Enter 23:50 to 00:20 and clock boundaries
- Expected: 30 minutes; correct boundary behavior
- Result: Passed
- Evidence: test_clock_boundaries, test_create_task_with_end_time

## TASK-03 — Repeated finish and reopen

- Prerequisite: Today's completed task
- Steps: Finish again, reopen, then finish
- Expected: Preserve earlier time and add the new session
- Result: Passed
- Evidence: test_double_stop_does_not_change, test_reopen_adds_a_session

## TASK-04 — Edit title without changing time

- Prerequisite: Running or paused task
- Steps: Change title and save
- Expected: Duration and segments preserved
- Result: Passed
- Evidence: test_editing_title_of_running_task, test_editing_title_of_paused_task

## TASK-05 — Edit clocks with pauses/adjustments

- Prerequisite: Multiple segments
- Steps: Edit clocks and positive/negative adjustment
- Expected: Paused time excluded; negative duration rejected
- Result: Passed
- Evidence: test_adjusting_a_task_with_pauses, test_cannot_go_negative

## TASK-06 — Actual overlap and pause gaps

- Prerequisite: Two tasks for one user
- Steps: Submit overlapping interval and interval inside pause
- Expected: Reject overlap; accept free gap
- Result: Passed
- Evidence: test_overlapping_manual_entry_is_refused, test_pauses_leave_room

## TASK-07 — Auditable deletion

- Prerequisite: Task with segments
- Steps: Delete task
- Expected: Snapshot archived in audit; active task removed
- Result: Passed
- Evidence: test_delete_task_archives_it

## PLAN-01 — Start planned work

- Prerequisite: Saved plan
- Steps: Start through UI, then finish
- Expected: Plan removed; planned_flag set
- Result: Passed
- Evidence: E2E-06, test_start_planned_creates_running_task

## TAG-01 — Budget and date scope

- Prerequisite: Tag with history
- Steps: Budget all history or from today
- Expected: Spent time follows selected scope
- Result: Passed
- Evidence: test_budget_counts_all_history, test_from_today_ignores

## TAG-02 — Merge and rename

- Prerequisite: Linked tasks, plans and archive
- Steps: Rename and merge tags
- Expected: Every task/minute preserved
- Result: Passed
- Evidence: test_merge_never_loses_a_minute, test_merge_moves_tasks

## PRES-01 — Check-in, temporary exit and finish

- Prerequisite: Workday
- Steps: Check in, pause, return and finish
- Expected: Attendance independent of tasks; correct state
- Result: Passed
- Evidence: E2E-05, test_check_in_out_back

## PRES-02 — Missing check-in reminder

- Prerequisite: Running task without attendance
- Steps: Read attendance state
- Expected: needs_checkin true; no automatic check-in
- Result: Passed
- Evidence: test_needs_checkin_reminder, test_there_is_no_automatic

## PRES-03 — Edit intervals and overlap

- Prerequisite: Saved attendance
- Steps: Edit/add/delete and submit overlap
- Expected: Intervals remain valid
- Result: Passed
- Evidence: test_edit_add_delete_and_validation

## FILL-01 — Complete daily-report journey

- Prerequisite: Attendance and two real tasks
- Steps: Suggest, save, export Excel/JSON, rollback
- Expected: Separate fill; original time unchanged
- Result: Passed
- Evidence: test_daily_work_report_fill_export_and_rollback

## FILL-02 — Touch/form preview and confirmation

- Prerequisite: Valid suggestion inputs
- Steps: Open dialog, preview, apply and rollback
- Expected: Fill saved/reverted without duration changes
- Result: Passed
- Evidence: E2E-56

## FILL-03 — Weights, meetings and target

- Prerequisite: Tags with different weights
- Steps: Request suggestion including meetings/zero weight
- Expected: Weight rules and aggregate cap enforced
- Result: Passed
- Evidence: test_fill_caps_each_task, test_report_can_never_go_above

## FILL-04 — Invalid attendance and Friday

- Prerequisite: No/suspicious attendance
- Steps: Request suggestion
- Expected: No suggestion; warning present
- Result: Passed
- Evidence: test_no_presence_means_no_suggestion, test_presence_over_eleven_hours, test_friday_is_never

## FILL-05 — Failure during multi-task save

- Prerequisite: Valid task and invalid ID
- Steps: Submit fill batch
- Expected: Full rollback; no partial save
- Result: Passed
- Evidence: test_fill_batch_is_atomic

## FILL-06 — Six-minute task cap

- Prerequisite: Six-minute task and large deficit
- Steps: Request fill suggestion
- Expected: At most three minutes; historical result was five
- Result: Open defect
- Evidence: test_fill_suggestion_respects_cap_for_short_tasks

## FILL-07 — Rounding and aggregate cap

- Prerequisite: Two 60-minute tasks, eight-minute gap
- Steps: Request fill suggestion
- Expected: Total at most nine minutes; historical result was ten
- Result: Open defect
- Evidence: test_fill_suggestion_does_not_exceed_total

## FILL-08 — Invalid date type

- Prerequisite: Numeric/array/object date
- Steps: POST fill
- Expected: 400 instead of 500
- Result: Open defect
- Evidence: test_fill_rejects_invalid_date_types

## REPORT-01 — Saturday–Friday timesheet

- Prerequisite: Several weeks of history
- Steps: Select days and navigate weeks
- Expected: Rows/totals follow Iranian week
- Result: Passed
- Evidence: test_week_runs_saturday_to_friday, test_cells_rows_and_totals

## REPORT-02 — Compare equal-length periods

- Prerequisite: Two months/years of data
- Steps: View current-month/current-year dashboard
- Expected: Compare through the corresponding prior-period day
- Result: Passed
- Evidence: test_running_month_is_compared, test_running_and_finished_year

## REPORT-03 — Jalali calendar/events

- Prerequisite: Valid and invalid months
- Steps: Display month and select day
- Expected: Correct days/events/task counts
- Result: Passed
- Evidence: test_calendar_month

## REPORT-04 — Empty Excel and year filter

- Prerequisite: Several years and an empty account
- Steps: Download Excel
- Expected: Valid file/columns/filter
- Result: Passed
- Evidence: test_export_empty_still_returns, test_export_sheets_headers

## REPORT-05 — Private exports

- Prerequisite: Two populated accounts
- Steps: Second user downloads Excel/JSON
- Expected: Only own records and catalog
- Result: Passed
- Evidence: test_export_and_backup_hold_only_own_data, test_catalog_is_in_personal_backup

## IMPORT-01 — Read desktop copy safely

- Prerequisite: Synthetic SQLite, empty account
- Steps: Import normally and dry-run
- Expected: Every value preserved; source unchanged
- Result: Passed
- Evidence: test_full_import_keeps_every_number, test_source_file_is_not_modified, test_dry_run_saves

## IMPORT-02 — Mismatch/nonempty account

- Prerequisite: Invalid source or populated destination
- Steps: Attempt import and inject mismatch
- Expected: Rollback; migration refused
- Result: Passed
- Evidence: test_a_mismatch_rolls_everything_back, test_refuses_a_non_empty_account

## IMPORT-03 — Upgrade 0001 to 0002

- Prerequisite: Synthetic shared legacy data
- Steps: Migrate in separate schema
- Expected: Duration, attendance, archive and ownership preserved
- Result: Passed
- Evidence: test_private_catalog_migration_preserves

## CONC-01 — Parallel starts for one user

- Prerequisite: Six clients sharing a session
- Steps: Six simultaneous starts
- Expected: Exactly one running task
- Result: Passed
- Evidence: test_parallel_start_allows_exactly_one

## CONC-02 — Parallel stops

- Prerequisite: Running task
- Steps: Five finish requests
- Expected: All succeed; identical time; one closed segment
- Result: Passed
- Evidence: test_parallel_stop_is_idempotent

## CONC-03 — Parallel same-name creation

- Prerequisite: Five clients for one account
- Steps: Five same-name project creates
- Expected: One 201, four 409 responses
- Result: Passed
- Evidence: test_parallel_catalog_creation

## CONC-04 — Two users work concurrently

- Prerequisite: Independent accounts
- Steps: Start both simultaneously
- Expected: Both succeed; data isolated
- Result: Passed
- Evidence: test_parallel_users_do_not_block

## UI-01 — Persian digits and clocks

- Prerequisite: Latin/Persian/Arabic input
- Steps: Convert/parse clocks and durations
- Expected: Correct output; invalid clocks rejected
- Result: Passed
- Evidence: FRONTEND-UNIT

## UI-02 — SQL/HTML-looking title

- Prerequisite: Authenticated user
- Steps: Save SQL and img/onerror text
- Expected: Literal text; no code execution
- Result: Passed
- Evidence: E2E-07, test_sql_and_html_looking_titles

## UI-03 — Disconnect during submission

- Prerequisite: Filled form
- Steps: Disconnect, submit, reconnect, retry
- Expected: Error shown; draft retained; one record
- Result: Passed
- Evidence: E2E-09

## UI-04 — All pages at three widths

- Prerequisite: User with data
- Steps: Open nine pages at 360/768/1280
- Expected: RTL; no page-wide horizontal scroll
- Result: Passed
- Evidence: RESPONSIVE

## UI-05 — Task lifecycle by touch

- Prerequisite: Mobile hasTouch context
- Steps: Tap start/pause/resume/finish
- Expected: Actions succeed
- Result: Passed
- Evidence: E2E-53

## UI-06 — London browser and Tehran server

- Prerequisite: Different browser timezone
- Steps: View today's clock
- Expected: UI matches Tehran server
- Result: Passed
- Evidence: E2E-54

## UI-07 — Mobile More and reports

- Prerequisite: 360px viewport
- Steps: Tap report, then Management under More
- Expected: Correct routes
- Result: Passed
- Evidence: E2E-50

## OPS-01 — Real stack startup

- Prerequisite: Isolated QA Compose
- Steps: Build, migrate at startup, request through Caddy
- Expected: Web/API/PostgreSQL available
- Result: Passed
- Evidence: DOCKER, test_alembic_cli_resolves

## OPS-02 — Actual dump/restore

- Prerequisite: Synthetic multi-table data
- Steps: pg_dump, restore into fresh DB, fingerprint
- Expected: All 12 tables equal
- Result: Passed
- Evidence: RECOVERY

## OPS-03 — API restart

- Prerequisite: Existing session/tasks
- Steps: Restart container; reuse cookie
- Expected: Session/tasks preserved
- Result: Passed
- Evidence: RESTART

## OPS-04 — Dump producer fails

- Prerequisite: Fake docker exits 17
- Steps: Run backup.sh in isolated container
- Expected: Nonzero exit; historical false success reproduced
- Result: Open defect
- Evidence: test_backup_fails_when_database_dump_fails

## OPS-05 — Decryption fails

- Prerequisite: Fake gpg exits 19
- Steps: Run restore_test.sh
- Expected: Nonzero exit; historical false success reproduced
- Result: Open defect
- Evidence: test_restore_fails_when_decryption_fails

## OPS-06 — Encryption/pg_restore fails

- Prerequisite: Injected pipeline consumer failure
- Steps: Run scripts
- Expected: Nonzero exit
- Result: Passed
- Evidence: test_backup_fails_when_encryption_fails, test_restore_fails_when_database_restore_fails

## PERF-01 — Multi-user load

- Prerequisite: Ten users, 2,800 tasks, 28 days
- Steps: 400 requests with ten workers
- Expected: Zero errors; p50/p95/p99; local budget only
- Result: Needs investigation
- Evidence: LOAD

## SEC-01 — npm package audit

- Prerequisite: Current package-lock
- Steps: npm audit without automatic upgrades
- Expected: Record findings and impact limits
- Result: Audit finding
- Evidence: AUDIT

## ARCH-01 — Stable boundaries and contracts

- Prerequisite: Complete source
- Steps: Test imports, SQL-free routes, OpenAPI
- Expected: Original 57-route contract and dependency direction preserved
- Result: Passed
- Evidence: test_dependency_direction, test_http_routes_do_not_execute, test_public_paths_parameters

## SET-01 — Invalid/valid settings in one request

- Prerequisite: Existing settings
- Steps: Send new goal and invalid Sheet URL together
- Expected: 400; all earlier settings preserved
- Result: Passed
- Evidence: test_invalid_settings_change_is_atomic

## CLI-01 — Create account/reset password

- Prerequisite: Test database
- Steps: Create with CLI; Login with first password; Reset password and login with new one
- Expected: Correct account/role; old session revoked
- Result: Passed
- Evidence: test_cli_create_and_reset_account, test_cli_duplicate_user_does_not_overwrite

## CLI-02 — Import catalog for one account

- Prerequisite: Two accounts, synthetic JSON
- Steps: Run import-catalog twice with --user alice
- Expected: No duplicates; hidden from Bob
- Result: Passed
- Evidence: test_cli_catalog_import_is_private

## OPS-07 — AES256 and wrong password

- Prerequisite: Synthetic QA dump, temporary keyring
- Steps: Encrypt; Decrypt and compare SHA256; Attempt wrong password
- Expected: Identical file; wrong password rejected
- Result: Passed
- Evidence: CRYPTO

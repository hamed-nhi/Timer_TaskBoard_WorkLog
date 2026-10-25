# Personal backups and Google Sheets synchronization

## Behavior

- Excel and JSON exports are scoped to the signed-in user. Administrators export only their own account too.
- Download filenames include account ID and a source-content hash. Identical source data produces the same name; changed source produces a new name. Browser/device handling of downloaded filenames remains under the user's control.
- The backup command creates `user-ID/versions` for each account. It adds JSON/Excel files only when source content changes. Runtime alone does not create a revision. Existing files are never replaced; earlier versions remain, including when source data returns to a previous revision.
- Full personal JSON includes that account's tasks, tags, catalog, work/attendance segments, plans, settings and audit log. It excludes passwords and sessions. Excel is the task view.
- Server files have restricted permissions, but personal JSON/Excel copies are not encrypted. Never web-serve backups. The encrypted full-database backup in deploy/backup.sh is separate and does not replace personal exports.

## Sheets

Each Google spreadsheet is reserved for one account, including alternate URLs for the same file. The API does not disclose another account's URL; reservation checks only test destination identity. Ownership includes installation and account IDs, preventing another account or installation from taking over managed tabs.

Only the `TimeLog` and `_TimeLog_owner` tabs are created; other tabs are preserved. Each task has a stable identifier in TimeLog:

1. New task: append a row.
2. Unchanged source: write no cells in its row, even if the user edited sheet text or its hash column.
3. Actual task/related-source change: update that row from source. The application manages columns A–O; put personal notes from P onward or in a separate tab.
4. Source deletion: keep the old row, changing only status to `deleted` and its source revision. Earlier backup files remain too.

Running-task duration uses stored fields; elapsed time alone does not trigger nightly rewrites. Stop/pause/edit operations count as source changes. Sorting complete rows is supported. Missing/duplicate IDs, changed column headers or a missing ownership marker stop synchronization safely.

Preserve the account checkpoint and root `.instance-id` with backup versions. If a checkpoint is deleted, the application does not automatically overwrite the existing sheet; restore a healthy checkpoint or assign a new spreadsheet. Network failures do not advance the checkpoint, so the next run is repeatable. Only one sync job per account runs at once; its job lock is separate from normal user-operation locks.

## Server setup

Saving a URL alone does not enable scheduling or Google access. Configure the server:

1. Create a service account dedicated to this installation and enable Sheets API. Store its key only on the server as `secrets/google-sheets.json` with restricted access; Git ignores this directory. Each user shares only their own sheet with the service-account email as Editor.
2. Set `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sheets.json` in .env for delivery. Empty credentials create local personal files only and send nothing to Google. The current first-use guide also displays GOOGLE_SHEETS_SERVICE_EMAIL; see [DEPLOY.md](../DEPLOY.md).
3. Build and run once:

```sh
docker compose --profile backup build personal-backup
docker compose --profile backup run --rm personal-backup
```

4. The original deployment used this nightly cron entry:

```cron
15 3 * * * /opt/timelog/deploy/personal_backup.sh >> /var/log/timelog-personal-backup.log 2>&1
```

The current release alternatively provides `docker compose --profile backup up -d --build backup-scheduler`, documented in DEPLOY.md. Choose a scheduling method rather than adding duplicate schedules.

All active accounts are processed. For one account: `docker compose --profile backup run --rm personal-backup --user USERNAME`. A failed account does not prevent backups for the others; the final exit status is nonzero for monitoring. Logs contain account IDs, revision hashes and write counts only.

Without Docker, install backend/requirements-sheets.txt, set DATABASE_URL for the intended environment, and run from backend:

```sh
python -m app.cli backup-users --output /private/backups/personal --user USERNAME
```

The server operator owns backup-directory permissions, credentials, scheduling and job monitoring. The personal-backup feature itself required no database migration or modification of real source data.

## Verification

Real-file tests cover repeat-run revision stability, preservation of earlier files after edits, account isolation and corrupted JSON detection. A stateful fake Sheets gateway tests add/edit/delete, manual destination edits, row movement, network failures and ownership. HTTP contract tests cover atomic ownership creation, capacity growth and RAW values. No real Google credentials were present, so actual Google delivery and server cron were not verified in that feature's tests. Later local scheduler smoke results are recorded in the release report.

Official references: [Write values](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdate), [batchUpdate](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate), [Service-account authentication](https://google-auth.readthedocs.io/en/latest/user-guide.html#service-account-private-key-files).

# Deploy TIME LOG on a Linux server

This guide starts a fresh production database. Existing local QA databases and test passwords are **not** shipped. The application uses Docker Compose, PostgreSQL 18, FastAPI and Caddy with a static Next.js export.

## 1. Prepare the server

Install Git, GnuPG and Docker Engine with the Compose v2 plugin. Follow [Docker's official installation guide](https://docs.docker.com/engine/install/ubuntu/) for your distribution. Verify:

```sh
docker version
docker compose version
gpg --version
```

Point your domain's DNS records to this server. Allow inbound TCP 80 and 443, and restrict SSH appropriately. Only Caddy is published; do not expose PostgreSQL or the API port. No Kubernetes, host Python or host Node.js is needed.

## 2. Configure and start

```sh
git clone https://github.com/hamed-nhi/workload.git /opt/timelog
cd /opt/timelog
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```dotenv
DB_PASSWORD=REPLACE_WITH_UNIQUE_RANDOM_URL_SAFE_PASSWORD
BACKUP_PASSPHRASE=REPLACE_WITH_SEPARATE_RANDOM_BACKUP_PASSPHRASE
SITE_ADDRESS=timelog.example.com
COOKIE_SECURE=true
HTTP_PORT=80
CAPTCHA_PROVIDER=none
```

Generate each password separately, for example with `openssl rand -hex 32`. Keep the backup passphrase outside this server too. Do not put spaces, shell substitutions or unescaped shell metacharacters in these values: the backup scripts source `.env` as shell configuration. Never commit or share this file.

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=60 api web
curl --fail https://timelog.example.com/api/health
```

The first build downloads dependencies and compiles Caddy/gosu; allow time for it. Automatic additive migrations run before the API starts. Caddy obtains the HTTPS certificate; ports 80/443 and DNS must be correct. Open `https://timelog.example.com` from both phone and computer.

For a temporary local-only HTTP test, use `SITE_ADDRESS=:80`, `COOKIE_SECURE=false` and an unused `HTTP_PORT`. Do not deploy public login over plain HTTP.

## 3. Create user accounts

Replace these example usernames with your own. Run each command interactively; each asks twice for its own password:

```sh
docker compose exec api python -m app.cli create-user user_one
docker compose exec api python -m app.cli create-user user_two
docker compose exec api python -m app.cli create-user admin --admin
```

New passwords must contain at least 8 characters, including an ASCII uppercase letter, lowercase letter, digit and punctuation symbol; the backend enforces this for CLI/admin/self-service setters. Legacy stored passwords remain usable until changed. Every user can change their own password in Settings.

There are no built-in passwords, seed accounts or backdoor administrator names. `admin` is an ordinary administrator role, not a special bypass. The local credentials supplied separately are not production credentials. If a username already exists the command refuses to overwrite it.

Sign in as `admin` and open **Management**. Administrators can create accounts with chosen or generated passwords, edit usernames/display names/roles, reset passwords and deactivate accounts. Changing credentials invalidates that account's sessions. Users' tasks and catalogs stay private even from administrators. There is no destructive account deletion control.

## 4. Login protection and recovery

Ban/credential enforcement runs in the backend with persistent PostgreSQL state, including direct API calls and parallel requests. Defaults:

| Event | Default action |
| --- | --- |
| 3 wrong passwords for one IP/account | 15-minute ban |
| Next 3 after that ban expires | 10-hour ban |
| Next 3 after that ban expires | 30-day ban; subsequent stages remain 30 days |
| 3 unknown/inactive username attempts from an IP | 24-hour IP ban |
| IP-wide failures | 10 in 20 minutes, regardless of successful logins on other accounts |
| All login requests | 30/IP/minute, 120/IP/hour, 300 globally/minute |

Banned requests do not extend their ban. Partial mistake counts expire after 20 quiet minutes. Successful login clears escalation for the same IP/account by default; it does not clear the IP's aggregate security budget. Existing valid sessions remain usable. A mistyped **existing** name is treated like that account; an unregistered name contributes to the unknown-name count.

In **Management → Login security**, change attempt limits, the three stage durations, unknown-name duration and success reset behavior. Settings apply to future decisions; existing ban end times are preserved until explicitly released. Release a ban while keeping its stage, or clear the entire stage history. Changes and releases are audited. Only administrators can read or modify this state.

If the administrator is locked out, use the server console:

```sh
docker compose exec api python -m app.cli login-security
docker compose exec api python -m app.cli unblock-login --ip 203.0.113.10 --reset
# Optional: add --username admin to limit the release to that account/IP pair.
docker compose exec api python -m app.cli reset-password admin
```

The example IP must be replaced with the IP shown by `login-security`. Resetting a password alone does not silently remove a ban. Console recovery requires server access; no public unlock/bypass endpoint exists.

Caddy is the public edge and overwrites untrusted forwarding headers. The API trusts forwarded headers only because it is unreachable publicly on the private Compose network. Do not publish its port or attach untrusted containers. If adding a CDN/load balancer, explicitly configure only its trusted proxy ranges in Caddy and retest real client IPs; otherwise many users may appear as one IP. See [Caddy's header rules](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers). Rate limits reduce guessing; they are not upstream DDoS protection or MFA.

### Flood admission and upstream DDoS protection

Before JSON parsing, routing, password hashing or SQL, a bounded in-memory token bucket rejects excess API traffic. Per process: API 60/IP/second and 200 globally/second; login 5/IP/second and 20 globally/second, each with a burst of twice that rate. The IP map is capped at 4,096 entries; saturated maps reject new keys instead of evicting existing limits. Memory budgets are local to one API process, reset on restart and multiply with replicas; durable database bans do not. Keep the default single process unless you add a shared edge limiter.

The login request body is capped at 16 KB in Caddy; other API uploads retain their 8 MB cap. Forged browser forwarding headers do not select an arbitrary client IP through the default public Caddy edge.

A botnet can still saturate network bandwidth, TLS handshakes, connection queues or the proxy before application code runs. Put the production domain behind a trusted CDN/WAF with bot/DDoS protection when exposed publicly, restrict origin access to that provider, and configure only its published IP ranges as trusted proxies. Do not trust every incoming forwarding header. Provider setup requires the actual domain/account; it is not activated by this repository. Test legitimate shared-IP traffic before tightening thresholds. This local gate is not a volumetric DDoS shield.

## 5. Optional Iranian ARCaptcha

The default `CAPTCHA_PROVIDER=none` keeps strict backend limits active without external credentials. To enable [ARCaptcha](https://github.com/arcaptcha/arcaptcha-docs/blob/main/versioned_docs/version-4.0.0/API/Verify.md):

1. Register the actual domain in its dashboard and obtain both keys.
2. Set these only in the server `.env`:

```dotenv
CAPTCHA_PROVIDER=arcaptcha
ARCAPTCHA_SITE_KEY=YOUR_PUBLIC_SITE_KEY
ARCAPTCHA_SECRET_KEY=YOUR_PRIVATE_SECRET_KEY
```

```sh
docker compose up -d --force-recreate api
```

The login UI gets the public configuration from the backend; no frontend key rebuild is needed. The secret never reaches the browser. Each token is checked through the fixed HTTPS verification endpoint and locally reserved against replay. Missing/rejected tokens and provider outages cannot create sessions. A provider outage blocks new login when enabled; it does not turn verification off. Do a real challenge test with your domain/keys before enabling for users. Contract tests with a fake provider do not certify external availability.

## 6. Backup before inviting users

```sh
chmod +x deploy/backup.sh deploy/restore_test.sh
./deploy/backup.sh
./deploy/restore_test.sh
```

Both commands must succeed. Enable the built-in daily personal-backup scheduler (persistent output, retries after failure):

```sh
docker compose --profile backup up -d --build backup-scheduler
docker compose --profile backup logs --tail=40 backup-scheduler
```

It performs an initial backup, then runs once per day at 03:00 Asia/Tehran, retaining an on-volume success marker. A failed run retries after 15 minutes. No cron is needed for this personal job. Keep the separate encrypted full-database backup too.

Every user's first visit displays private backup setup: create a private blank Google Sheet, share it as Editor with the configured service account and save its URL. Users may continue without a sheet and reopen the guide in Settings; personal Excel download remains available. Do not make the sheet public. To configure Sheets, enable Google Sheets API in the service-account project, save its JSON key as `secrets/google-sheets.json`, and set:

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sheets.json
GOOGLE_SHEETS_SERVICE_EMAIL=YOUR_SERVICE_ACCOUNT_EMAIL
```

Restart API and scheduler after changing these values. The email is public configuration for sharing; the private JSON key must never reach users or Git. Saving a URL does not prove delivery. Until credentials, permissions and the scheduler work on the destination server, the UI does not claim synchronization is active. Test a real source edit and inspect its destination row. A new JSON/Excel version is written only when source data changes.

Schedule the full encrypted database backup, for example with the deployment user's crontab:

```cron
0 3 * * * cd /opt/timelog && ./deploy/backup.sh >> /opt/timelog/backups/backup.log 2>&1
```

Keep encrypted archives and a recovery copy of the passphrase off-server. Run the restore check regularly. Personal JSON/Excel snapshots are optional (`docker compose --profile backup run --rm personal-backup`); they supplement the full encrypted database backup.

The `pgdata` volume holds data; `caddy_data` holds certificates. Never use `docker compose down --volumes` on this installation. Keep the Compose project name/path stable so Docker reuses the same volume. This guide does not restore the local test databases or desktop files.

## 7. Upgrade safely

```sh
cd /opt/timelog
./deploy/backup.sh
./deploy/restore_test.sh
git pull --ff-only
docker compose up -d --build
curl --fail https://timelog.example.com/api/health
docker compose logs --tail=60 api
```

Check login, a user's existing task times and admin controls after upgrading. Do not downgrade database schemas just to roll back application code. Restore an encrypted dump to a **separate** PostgreSQL instance first; validate it before any production cutover. Backup scripts perform a temporary restore test, not automatic replacement of production data.

## Verification limits

Local automated tests, deployment configuration and a disposable Linux-container smoke test can be verified here. Actual server DNS/HTTPS, external ARCaptcha with real keys, physical phones and live Google Sheets require the destination environment. Remaining base-image findings are documented in [the audit report](docs/testing/AUDIT_RESULTS.fa.md); production security is not declared universally clean.

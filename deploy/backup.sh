#!/bin/sh
# Nightly: encrypted pg_dump, keep 14 daily + 8 weekly. Cron: 0 3 * * * /opt/timelog/deploy/backup.sh
set -eu
cd "$(dirname "$0")/.."
. ./.env
OUT=${BACKUP_DIR:-./backups}
mkdir -p "$OUT/daily" "$OUT/weekly"
ts=$(date +%Y%m%d_%H%M%S)
f="$OUT/daily/timelog_$ts.dump.gpg"
docker compose exec -T db pg_dump -U timelog -Fc timelog \
  | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$BACKUP_PASSPHRASE" -o "$f"
[ -s "$f" ] || { echo "empty backup" >&2; rm -f "$f"; exit 1; }
[ "$(date +%u)" = 7 ] && cp "$f" "$OUT/weekly/"
ls -1t "$OUT"/daily/*.gpg | tail -n +15 | xargs -r rm --
ls -1t "$OUT"/weekly/*.gpg | tail -n +9 | xargs -r rm --
echo "ok $f"

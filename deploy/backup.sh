#!/bin/sh
# Nightly encrypted backup. Each producer must succeed before publishing anything.
set -eu
umask 077
cd "$(dirname "$0")/.."
. ./.env
OUT=${BACKUP_DIR:-./backups}
mkdir -p "$OUT/daily" "$OUT/weekly"
tmp=$(mktemp -d "$OUT/.backup.XXXXXX")
cleanup() {
  rm -f -- "$tmp/source.dump" "$tmp/encrypted.gpg" "$tmp/passphrase"
  rmdir "$tmp"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
printf '%s' "$BACKUP_PASSPHRASE" > "$tmp/passphrase"
docker compose exec -T db pg_dump -U timelog -Fc timelog > "$tmp/source.dump"
[ -s "$tmp/source.dump" ]
docker compose exec -T db pg_restore --list < "$tmp/source.dump" > /dev/null
gpg --batch --pinentry-mode loopback --symmetric --cipher-algo AES256   --passphrase-file "$tmp/passphrase" -o "$tmp/encrypted.gpg" "$tmp/source.dump"
[ -s "$tmp/encrypted.gpg" ]
ts=$(date -u +%Y%m%dT%H%M%SZ)
f="$OUT/daily/timelog_${ts}_$(basename "$tmp").dump.gpg"
# Exclusive publication; never overwrite an older backup even in the same second.
ln "$tmp/encrypted.gpg" "$f"
if [ "$(date +%u)" = 7 ]; then ln "$f" "$OUT/weekly/$(basename "$f")"; fi
ls -1t "$OUT"/daily/*.gpg | tail -n +15 | while IFS= read -r old; do rm -f -- "$old"; done
if ls "$OUT"/weekly/*.gpg >/dev/null 2>&1; then
  ls -1t "$OUT"/weekly/*.gpg | tail -n +9 | while IFS= read -r old; do rm -f -- "$old"; done
fi
echo "ok $f"

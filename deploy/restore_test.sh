#!/bin/sh
# Restore into a new, uniquely named test DB; never drop an existing database.
set -eu
umask 077
cd "$(dirname "$0")/.."
. ./.env
f=$(ls -1t "${BACKUP_DIR:-./backups}"/daily/*.gpg | head -1)
[ -n "$f" ] && [ -s "$f" ]
tmp=$(mktemp -d "${TMPDIR:-/tmp}/timelog-restore.XXXXXX")
target="restore_$(date -u +%Y%m%d%H%M%S)_$(basename "$tmp" | tr -cd 'a-z0-9')_test"
created=0
cleanup() {
  status=$?
  if [ "$created" = 1 ]; then
    docker compose exec -T db dropdb -U timelog "$target" || status=1
  fi
  rm -f -- "$tmp/decrypted.dump" "$tmp/passphrase"
  rmdir "$tmp" || status=1
  exit "$status"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
printf '%s' "$BACKUP_PASSPHRASE" > "$tmp/passphrase"
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$tmp/passphrase"   -o "$tmp/decrypted.dump" --decrypt "$f"
[ -s "$tmp/decrypted.dump" ]
docker compose exec -T db pg_restore --list < "$tmp/decrypted.dump" > /dev/null
docker compose exec -T db createdb -U timelog "$target"
created=1
docker compose exec -T db pg_restore --exit-on-error -U timelog -d "$target" --no-owner < "$tmp/decrypted.dump"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U timelog -d "$target" -tc 'SELECT count(*) AS tasks FROM tasks'
echo "restore verified"

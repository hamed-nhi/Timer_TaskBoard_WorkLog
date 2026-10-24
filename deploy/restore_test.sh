#!/bin/sh
# Proves the newest backup restores: loads it into a throwaway database and counts tasks. Never touches the live db.
set -eu
cd "$(dirname "$0")/.."
. ./.env
f=$(ls -1t "${BACKUP_DIR:-./backups}"/daily/*.gpg | head -1)
echo "testing $f"
docker compose exec -T db psql -U timelog -d postgres -c "DROP DATABASE IF EXISTS restore_test" -c "CREATE DATABASE restore_test"
gpg --batch --quiet --decrypt --passphrase "$BACKUP_PASSPHRASE" "$f" \
  | docker compose exec -T db pg_restore -U timelog -d restore_test --no-owner
docker compose exec -T db psql -U timelog -d restore_test -tc "SELECT count(*) AS tasks FROM tasks"
docker compose exec -T db psql -U timelog -d postgres -c "DROP DATABASE restore_test"

#!/bin/sh
# Cron example: 15 3 * * * /opt/timelog/deploy/personal_backup.sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile backup run --rm personal-backup

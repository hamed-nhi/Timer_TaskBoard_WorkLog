"""Run actual backup scripts with fault-injected commands inside a disposable container."""
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.operational
ROOT = Path(__file__).resolve().parents[3]


def run_script(script, docker_fail, gpg_fail):
    if not shutil.which("docker"):
        pytest.skip("Docker is required for the operational fault-injection tests")
    harness = r"""
set -eu
mkdir -p /tmp/qa/deploy /tmp/qa/bin /tmp/qa/backups/daily /tmp/qa/backups/weekly
sed 's/\r$//' /source/script.sh > /tmp/qa/deploy/check.sh
printf 'BACKUP_PASSPHRASE=qa-not-a-real-secret\n' > /tmp/qa/.env
printf 'sample dump' > /tmp/qa/backups/daily/input.gpg
cat > /tmp/qa/bin/docker <<'SH'
#!/bin/sh
case "$*" in
  *pg_dump*) [ "$DOCKER_FAIL" = dump ] && exit 17; printf 'dump data';;
  *pg_restore*) cat >/dev/null; [ "$DOCKER_FAIL" = restore ] && exit 18;;
  *) printf '1\n';;
esac
exit 0
SH
cat > /tmp/qa/bin/gpg <<'SH'
#!/bin/sh
[ "$GPG_FAIL" = yes ] && exit 19
out=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '-o' ]; then shift; out="$1"; fi
  shift
done
if [ -n "$out" ]; then
  cat >/dev/null
  printf 'nonempty encrypted envelope' > "$out"
else
  printf 'decrypted bytes'
fi
SH
chmod +x /tmp/qa/bin/docker /tmp/qa/bin/gpg
export PATH="/tmp/qa/bin:$PATH"
sh /tmp/qa/deploy/check.sh
"""
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "-i",
         "--mount", f"type=bind,source={ROOT / 'deploy' / script},target=/source/script.sh,readonly",
         "-e", f"DOCKER_FAIL={docker_fail}", "-e", f"GPG_FAIL={gpg_fail}", "postgres:18", "sh", "-s"],
        input=harness.encode("utf-8"), capture_output=True, timeout=45)
    result.stdout = result.stdout.decode("utf-8", errors="replace")
    result.stderr = result.stderr.decode("utf-8", errors="replace")
    assert "Illegal option" not in result.stderr, result.stderr
    return result


@pytest.mark.xfail(strict=True, reason="QA-004: pg_dump failure is masked by a successful gpg pipeline")
def test_backup_fails_when_database_dump_fails():
    result = run_script("backup.sh", "dump", "no")
    assert result.returncode != 0, result.stdout


def test_backup_fails_when_encryption_fails():
    assert run_script("backup.sh", "none", "yes").returncode != 0


@pytest.mark.xfail(strict=True, reason="QA-005: decryption failure is masked by successful pg_restore")
def test_restore_fails_when_decryption_fails():
    result = run_script("restore_test.sh", "none", "yes")
    assert result.returncode != 0, result.stdout


def test_restore_fails_when_database_restore_fails():
    assert run_script("restore_test.sh", "restore", "no").returncode != 0

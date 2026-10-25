"""One daily personal backup job, with retry and a durable success marker."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from .core.config import settings


def seconds_until_due(now, last_date):
    if not last_date:
        return 0
    today = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if last_date == now.date().isoformat():
        today += timedelta(days=1)
    return max(0, (today - now).total_seconds())


def run_once(output, runner=subprocess.run):
    result = runner([sys.executable, "-m", "app.cli", "backup-users", "--output", str(output)], check=False)
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--output", default="/backups/personal")
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    marker = output / ".scheduler-success.json"
    last_date = None
    if marker.exists():
        try:
            last_date = json.loads(marker.read_text(encoding="utf-8"))["date"]
        except (ValueError, KeyError):
            pass
    while True:
        now = datetime.now(ZoneInfo(settings.app_tz))
        wait = seconds_until_due(now, last_date)
        if wait and not args.once:
            time.sleep(min(wait, 60))
            continue
        ok = run_once(output)
        if ok:
            last_date = now.date().isoformat()
            temporary = marker.with_suffix(".tmp")
            temporary.write_text(json.dumps({"date": last_date}), encoding="utf-8")
            temporary.replace(marker)
        if args.once:
            return 0 if ok else 1
        if not ok:
            print("Daily backup failed; retrying in 15 minutes", flush=True)
            time.sleep(900)


if __name__ == "__main__":
    raise SystemExit(main())

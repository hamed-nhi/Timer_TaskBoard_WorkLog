from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json
import pytest
from app import backup_scheduler as scheduler


@pytest.mark.parametrize("hour,last,expected", [(1,None,0),(1,"2026-10-24",7200),(4,"2026-10-24",0),(4,"2026-10-25",82800)])
def test_daily_tehran_schedule_and_restart_marker(hour,last,expected):
    now=datetime(2026,10,25,hour,tzinfo=ZoneInfo("Asia/Tehran"))
    assert scheduler.seconds_until_due(now,last)==expected


def test_job_uses_argument_list_and_propagates_failure(tmp_path):
    seen=[]
    def runner(command,check):seen.append(command);return SimpleNamespace(returncode=1)
    assert scheduler.run_once(tmp_path,runner) is False
    assert seen[0][-2:]==["--output",str(tmp_path)]
    assert "app.cli" in seen[0]


@pytest.mark.parametrize("ok",[True,False])
def test_once_records_only_successful_job(tmp_path,monkeypatch,ok):
    monkeypatch.setattr(scheduler,"run_once",lambda output:ok)
    assert scheduler.main(["--once","--output",str(tmp_path)])==(0 if ok else 1)
    assert (tmp_path/".scheduler-success.json").exists()==ok


def test_corrupt_marker_is_not_reported_as_success(tmp_path,monkeypatch):
    marker=tmp_path/".scheduler-success.json";marker.write_text("broken")
    monkeypatch.setattr(scheduler,"run_once",lambda output:False)
    assert scheduler.main(["--once","--output",str(tmp_path)])==1
    assert marker.read_text()=="broken"

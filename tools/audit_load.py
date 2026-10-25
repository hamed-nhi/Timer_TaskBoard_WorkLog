"""Bounded mixed read/write load. Only the isolated audit service is accepted."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, timedelta
import json
import os
from pathlib import Path
import time
import uuid

import httpx
import jdatetime

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:18082")
if BASE not in {"http://127.0.0.1:18082", "http://audit-web:80"}:
    raise SystemExit("Only the isolated audit target is permitted")
OUT = Path(os.environ["QA_ARTIFACT_DIR"]) if "QA_ARTIFACT_DIR" in os.environ else Path(__file__).resolve().parents[1] / "artifacts/audit"
HEADERS = {"X-Requested-With": "timelog"}


@contextmanager
def keep_awake():
    """Prevent automatic Windows sleep only while this foreground test process runs."""
    if os.name != "nt":
        yield
        return
    import ctypes
    set_state = ctypes.windll.kernel32.SetThreadExecutionState
    set_state.argtypes = [ctypes.c_uint]
    set_state.restype = ctypes.c_uint
    active = bool(set_state(0x80000001))
    try:
        yield
    finally:
        if active:
            set_state(0x80000000)


def worker(index, duration, count, run):
    timings, errors, created = [], [], []
    with httpx.Client(base_url=BASE, timeout=15, headers=HEADERS, trust_env=False) as client:
        login = client.post("/api/auth/login", json={"username": f"qa_load_{index}", "password": "qa-system-password-1"})
        login.raise_for_status()
        initial = client.get("/api/tasks").json()
        assert len(initial) >= 280
        anchor = min(date.fromisoformat(r["gregorian_date"]) for r in initial) - timedelta(days=20)
        load_start = time.monotonic()
        last_finish = load_start
        max_idle = 0.0
        until, n = load_start + duration, 0
        while (time.monotonic() < until) if duration else (n < count):
            started = time.monotonic()
            max_idle = max(max_idle, started - last_finish)
            route = ["/api/tasks", "/api/dashboard", "/api/presence/history", "/api/settings"][n % 4]
            try:
                if n % 4 == 0:
                    day = anchor + timedelta(days=n // 400)
                    j = jdatetime.date.fromgregorian(date=day)
                    minute = (n // 4 % 100) * 5
                    title = f"AUDIT-{run}-{index}-{n}"
                    payload = {"title": title, "jalali_year": j.year, "jalali_month": j.month, "jalali_day": j.day,
                               "start_time": f"{8 + minute // 60:02d}:{minute % 60:02d}",
                               "end_time": f"{8 + (minute + 5) // 60:02d}:{(minute + 5) % 60:02d}"}
                    response = client.post(route, json=payload)
                    if response.status_code == 201:
                        created.append((response.json()["id"], title))
                else:
                    response = client.get(route)
                if response.status_code not in (200, 201):
                    errors.append({"path": route, "status": response.status_code})
            except httpx.HTTPError as exc:
                errors.append({"path": route, "error": type(exc).__name__})
            last_finish = time.monotonic()
            timings.append((last_finish - started) * 1000)
            n += 1
            if duration:
                time.sleep(max(0, 1 - (time.monotonic() - started)))
        load_seconds = time.monotonic() - load_start
        rows = client.get("/api/tasks").json()
        saved = {r["id"]: r for r in rows}
        valid = len(rows) == len(initial) + len(created) and all(
            saved.get(id, {}).get("title") == title and saved[id]["duration_minutes"] == 5 for id, title in created)
    return {"timings": timings, "errors": errors, "created": len(created), "data_integrity": valid, "load_seconds": load_seconds, "max_idle_seconds": max_idle}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--name", default="load")
    args = parser.parse_args()
    assert 0 <= args.seconds <= 900 and 1 <= args.requests <= 1000
    OUT.mkdir(parents=True, exist_ok=True)
    run = uuid.uuid4().hex[:8]
    started = time.monotonic()
    with keep_awake(), ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(worker, n, args.seconds, args.requests, run) for n in range(10)]
        while not all(f.done() for f in futures):
            time.sleep(10)
            elapsed = int(time.monotonic() - started)
            if elapsed % 60 < 10:
                print(f"audit load elapsed={elapsed}s", flush=True)
        values = [f.result() for f in futures]
    timings = sorted(t for result in values for t in result["timings"])
    result = {"target": BASE, "users": 10, "seconds": round(time.monotonic() - started, 2),
              "requests": len(timings), "writes": sum(r["created"] for r in values),
              "errors": [e for r in values for e in r["errors"]],
              "all_saved_data_verified": all(r["data_integrity"] for r in values),
              "p95_ms": round(timings[int((len(timings)-1)*.95)], 2),
              "p99_ms": round(timings[int((len(timings)-1)*.99)], 2)}
    result["load_seconds_min"] = round(min(r["load_seconds"] for r in values), 2)
    result["load_seconds_max"] = round(max(r["load_seconds"] for r in values), 2)
    result["max_idle_seconds"] = round(max(r["max_idle_seconds"] for r in values), 2)
    result["max_request_ms"] = round(max(timings), 2)
    result["uninterrupted"] = not args.seconds or (result["max_idle_seconds"] < 5 and result["max_request_ms"] < 30000 and result["load_seconds_min"] >= args.seconds)
    result["passed"] = result["uninterrupted"] and not result["errors"] and result["all_saved_data_verified"] and result["p95_ms"] < 2000
    (OUT / f"{args.name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result["passed"] else 1)

"""Small authenticated load/reliability probe against the local QA stack only."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import time
from urllib.parse import urlparse

import httpx

BASE = os.environ.get("QA_BASE_URL", "http://127.0.0.1:18082")
parsed = urlparse(BASE)
local_target = parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == 18082
docker_target = os.environ.get("QA_IN_DOCKER") == "1" and parsed.hostname == "audit-web" and parsed.port == 80
if not (local_target or docker_target):
    raise SystemExit("Refusing non-QA target")
OUT = Path(os.environ["QA_ARTIFACT_DIR"]) if "QA_ARTIFACT_DIR" in os.environ else Path(__file__).resolve().parents[1] / "artifacts/audit"
OUT.mkdir(parents=True, exist_ok=True)
PATHS = ["/api/tasks", "/api/dashboard", "/api/timesheet", "/api/presence/history", "/api/settings", "/api/company-catalog"]


def worker(index):
    timings, errors = [], []
    with httpx.Client(base_url=BASE, timeout=15, trust_env=False) as client:
        response = client.post("/api/auth/login",
                               json={"username": f"qa_load_{index}", "password": "qa-system-password-1"},
                               headers={"X-Requested-With": "timelog"})
        response.raise_for_status()
        assert len(client.get("/api/tasks").json()) >= 280
        for n in range(40):
            route = PATHS[n % len(PATHS)]
            started = time.perf_counter()
            try:
                response = client.get(route)
                timings.append((time.perf_counter() - started) * 1000)
                if response.status_code != 200:
                    errors.append({"path": route, "status": response.status_code})
            except httpx.HTTPError as exc:
                timings.append((time.perf_counter() - started) * 1000)
                errors.append({"path": route, "error": type(exc).__name__, "message": str(exc), "cause": str(exc.__cause__)})
    return timings, errors


if __name__ == "__main__":
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:
        values = list(pool.map(worker, range(10)))
    timings = sorted(t for batch, _ in values for t in batch)
    errors = [e for _, batch in values for e in batch]
    def percentile(p):
        return round(timings[min(len(timings) - 1, int((len(timings) - 1) * p))], 2)
    elapsed = time.perf_counter() - started
    result = {"requests": len(timings), "users": 10, "concurrency": 10, "history_tasks": 2800, "target": BASE,
              "seconds": round(elapsed, 2), "requests_per_second": round(len(timings) / elapsed, 2),
              "p50_ms": percentile(.5), "p95_ms": percentile(.95), "p99_ms": percentile(.99),
              "max_ms": round(max(timings), 2), "errors": errors,
              "local_exploratory_budget_ms": 2000, "local_budget_met": percentile(.95) < 2000,
              "note": "Local QA smoke load; not a production capacity or availability certification"}
    (OUT / "load.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if errors:
        raise SystemExit(1)

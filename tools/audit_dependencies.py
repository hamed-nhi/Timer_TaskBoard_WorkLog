"""Query npm's public advisory API without npm transport-specific failures."""
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
packages = {}
lockfiles = ["frontend/package-lock.json", "tools/qa-browser/package-lock.json"]
for filename in lockfiles:
    lock = json.loads((ROOT / filename).read_text(encoding="utf-8"))
    for path, data in lock["packages"].items():
        if path and data.get("version"):
            name = data.get("name") or path.rsplit("node_modules/", 1)[-1]
            packages.setdefault(name, set()).add(data["version"])
with httpx.Client(timeout=90, follow_redirects=False) as client:
    response = client.post("https://registry.npmjs.org/-/npm/v1/security/advisories/bulk",
                           json={name: sorted(versions) for name, versions in packages.items()})
    response.raise_for_status()
    advisories = response.json()
result = {"source": "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk", "packages": len(packages), "lockfiles": lockfiles,
          "advisories": advisories}
(ROOT / "artifacts/audit/npm-advisories.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"packages": len(packages), "affected_packages": len(advisories)}))

raise SystemExit(1 if advisories else 0)

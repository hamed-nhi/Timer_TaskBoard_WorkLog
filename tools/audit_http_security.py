"""Read-only HTTP hardening check against the audit frontend only."""
import json
from pathlib import Path
import httpx
out=Path(__file__).resolve().parents[1]/'artifacts/audit/http-security.json'
results=[]
with httpx.Client(base_url='http://127.0.0.1:18082',trust_env=False,timeout=15) as client:
 for route in ('/','/login/','/api/health'):
  response=client.get(route)
  policy=response.headers.get('content-security-policy','')
  results.append({'route':route,'nosniff':response.headers.get('x-content-type-options')=='nosniff','frame_denied':response.headers.get('x-frame-options')=='DENY','script_policy_uses_hashes':"script-src 'self' 'sha256-" in policy and "'unsafe-eval'" not in policy and "script-src 'self' 'unsafe-inline'" not in policy,'api_not_cached':not route.startswith('/api/') or 'no-store' in response.headers.get('cache-control','')})
report={'passed':all(all(v for k,v in row.items() if k!='route') for row in results),'results':results}
out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)

"""Bounded authenticated ZAP scan, isolated Docker network and a fresh synthetic account."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/audit'
private=ROOT/'backups/audit-zap'/uuid.uuid4().hex
private.mkdir(parents=True,mode=0o700)
os.environ['DATABASE_URL']='postgresql+psycopg://auditor:audit-password-only@127.0.0.1:5544/timelog_audit_test'
sys.path.insert(0,str(ROOT/'backend'))
from app.main import app
spec=app.openapi();spec['servers']=[{'url':'http://audit-web:80'}]
excluded=('/api/auth/','/api/admin/','/api/me/password')
spec['paths']={p:v for p,v in spec['paths'].items() if not any(p.startswith(x) for x in excluded)}
(private/'openapi.json').write_text(json.dumps(spec),encoding='utf-8')
headers={'X-Requested-With':'timelog'}
with httpx.Client(base_url='http://127.0.0.1:18082',trust_env=False,timeout=20,headers=headers) as admin:
 admin.post('/api/auth/login',json={'username':'qa_admin','password':'qa-system-password-1'}).raise_for_status()
 account=admin.post('/api/admin/users',json={'username':'qa_zap_'+uuid.uuid4().hex[:10],'display_name':'Synthetic ZAP audit'})
 account.raise_for_status();account=account.json()
with httpx.Client(base_url='http://127.0.0.1:18082',trust_env=False,timeout=20,headers=headers) as user:
 login=user.post('/api/auth/login',json={'username':account['username'],'password':account['temp_password']});login.raise_for_status()
 token=user.cookies.get('tl_session');assert token
 user.post('/api/tasks',json={'title':'Synthetic security sample','start_time':'09:00','end_time':'10:00'}).raise_for_status()
 assert user.get('/api/me').json()['username']==account['username']
 env=dict(os.environ,ZAP_AUTH_HEADER='Cookie',ZAP_AUTH_HEADER_VALUE='tl_session='+token,ZAP_AUTH_HEADER_SITE='audit-web')
 options='-silent -config ascan.maxScanDurationInMins=4 -config ascan.maxRuleDurationInMins=1 -config replacer.full_list(0).description=timelog-csrf -config replacer.full_list(0).enabled=true -config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=X-Requested-With -config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement=timelog'
 command=['docker','run','--rm','--network','timelog-qa_audit','--mount',f'type=bind,source={private},target=/zap/wrk',
          '-e','ZAP_AUTH_HEADER','-e','ZAP_AUTH_HEADER_VALUE','-e','ZAP_AUTH_HEADER_SITE',
          'ghcr.io/zaproxy/zaproxy@sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6',
          'zap-api-scan.py','-t','/zap/wrk/openapi.json','-f','openapi','-J','raw.json','-T','3','-z',options]
 started=time.monotonic()
 result=subprocess.run(command,env=env,capture_output=True,timeout=720)
 raw=private/'raw.json'
 if not raw.exists():
  log=(result.stdout+result.stderr).decode(errors='replace').replace(token,'[REDACTED]')
  (OUT/'zap.log').write_text(log,encoding='utf-8')
  raise SystemExit(f'ZAP failed before producing evidence (exit {result.returncode}); see sanitized log')
 data=json.loads(raw.read_text(encoding='utf-8'))
 text=json.dumps(data).replace(token,'[REDACTED]').replace(account['temp_password'],'[REDACTED]')
 (OUT/'zap.json').write_text(text,encoding='utf-8')
 alerts=[a for site in data.get('site',[]) for a in site.get('alerts',[])]
 report={'completed':result.returncode in (0,1,2),'exit_code':result.returncode,'seconds':round(time.monotonic()-started,2),
         'target':'http://audit-web:80','role':'fresh normal user','active_scan_budget_minutes':4,'paths':len(spec['paths']),
         'excluded':['login/logout/password changes/admin account endpoints'],
         'alerts':[{'id':a.get('pluginid'),'name':a.get('name'),'risk':a.get('riskdesc'),'count':a.get('count')} for a in alerts]}
 (OUT/'zap-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 log=(result.stdout+result.stderr).decode(errors='replace').replace(token,'[REDACTED]').replace(account['temp_password'],'[REDACTED]')
 (OUT/'zap.log').write_text(log,encoding='utf-8')
 user.post('/api/auth/logout')
 print(json.dumps(report))

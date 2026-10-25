"""Exercise the actual personal-backup container with a complete synthetic reference account."""
import hashlib
import json
from datetime import date,timedelta
from pathlib import Path
import subprocess
import time
import uuid
import httpx
import jdatetime

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/audit'
folder=ROOT/'backups/audit-personal'/uuid.uuid4().hex;folder.mkdir(parents=True,mode=0o700)
HEADERS={'X-Requested-With':'timelog'}

def post(client,path,body):
 response=client.post(path,json=body);response.raise_for_status();return response.json()

def files():
 return {str(p.relative_to(folder)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime':p.stat().st_mtime_ns} for p in folder.rglob('*') if p.is_file()}

with httpx.Client(base_url='http://127.0.0.1:18082',trust_env=False,timeout=30,headers=HEADERS) as admin:
 post(admin,'/api/auth/login',{'username':'qa_admin','password':'qa-system-password-1'})
 account=post(admin,'/api/admin/users',{'username':'qa_reference_'+uuid.uuid4().hex[:8],'display_name':'Recovery reference'})
with httpx.Client(base_url='http://127.0.0.1:18082',trust_env=False,timeout=30,headers=HEADERS) as client:
 post(client,'/api/auth/login',{'username':account['username'],'password':account['temp_password']})
 today=client.get('/api/today').json();day=date.fromisoformat(today['gregorian'])-timedelta(days=1)
 while day.weekday()==4:day-=timedelta(days=1)
 j=jdatetime.date.fromgregorian(date=day)
 report_type=post(client,'/api/catalog/report-types',{'name':'Reference type'})
 project=post(client,'/api/catalog/projects',{'name':'Reference project'})
 story=post(client,f"/api/catalog/projects/{project['id']}/stories",{'name':'Reference story'})
 tag=post(client,'/api/tags',{'name':'Reference tag','story_id':story['id'],'report_type_id':report_type['id']})
 finished=post(client,'/api/tasks',{'title':'Reference finished','start_time':'09:00','end_time':'10:00','tag_id':tag['id'],'jalali_year':j.year,'jalali_month':j.month,'jalali_day':j.day})
 post(client,'/api/presence',{'date':day.isoformat(),'start_time':'08:00','end_time':'11:00'})
 post(client,'/api/fill',{'date':day.isoformat(),'items':[{'id':finished['id'],'fill_minutes':10}]})
 paused=post(client,'/api/tasks',{'title':'Reference paused','tag_id':tag['id']});post(client,f"/api/tasks/{paused['id']}/pause",{})
 post(client,'/api/planned',{'title':'Reference future plan','tag_id':tag['id']})
 post(client,'/api/settings',{'daily_goal_minutes':420,'weekly_goal_minutes':2000})
 def run():
  started=time.monotonic()
  subprocess.run(['docker','run','--rm','--network','timelog-qa_audit','--mount',f'type=bind,source={folder},target=/backups',
      '-e','DATABASE_URL=postgresql+psycopg://auditor:audit-password-only@audit-db:5432/timelog_audit_test',
      'timelog-qa-personal-backup:latest','--user',account['username']],capture_output=True,check=True,timeout=120)
  return round(time.monotonic()-started,2)
 first_seconds=run();first=files();assert len([p for p in first if p.endswith('.json')])==1
 second_seconds=run();assert files()==first,'Unchanged source rewrote or created a backup'
 response=client.put(f"/api/tasks/{finished['id']}",json={'title':'Reference edited by owner'});response.raise_for_status()
 assert response.json()['duration_minutes']==60
 third_seconds=run();third=files();assert len([p for p in third if p.endswith('.json')])==2
 assert all(third.get(p)==value for p,value in first.items()),'Prior backup changed'
 newest=[p for p in third if p.endswith('.json') and p not in first];payload=json.loads((folder/newest[0]).read_text(encoding='utf-8'))
 assert len(payload['tasks'])==2 and any(t['status']=='paused' for t in payload['tasks'])
 assert any(t['duration_minutes']==60 and t['fill_minutes']==10 for t in payload['tasks'])
 assert payload['planned_tasks'] and payload['presence_segments'] and payload['task_segments'] and payload['settings']
 assert payload['catalog']['projects'] and payload['tags']
 report={'passed':True,'unchanged_source_no_write':True,'source_edit_created_version':True,'prior_version_preserved':True,
         'complete_reference_account':True,'reference_user_id':payload['tasks'][0]['user_id'],'job_seconds':[first_seconds,second_seconds,third_seconds],
         'versions_before':1,'versions_after':2,'source_task_minutes_preserved':True}
 (OUT/'personal-pipeline.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

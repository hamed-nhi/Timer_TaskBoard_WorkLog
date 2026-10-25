"""Read-only final verification of the existing demo, using the preservation baseline."""
import json
from pathlib import Path
import psycopg
from audit_preserve import fingerprint
root=Path(__file__).resolve().parents[1]
baseline=json.loads((root/'artifacts/audit/preservation.json').read_text())['tables']
with psycopg.connect(host='127.0.0.1',port=5543,user='timelog',password='qa-password-only',dbname='timelog_system_test') as conn:
 conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
 current=fingerprint(conn)
changed=[name for name in baseline if baseline[name]!=current.get(name)]
baseline_report=json.loads((root/'artifacts/audit/preservation.json').read_text())
renewal_only=False
columns_changed=[]
if changed==['sessions']:
 connection=dict(host='127.0.0.1',port=5543,user='timelog',password='qa-password-only')
 def sessions(database):
  with psycopg.connect(**connection,dbname=database) as conn:
   conn.execute('BEGIN READ ONLY');cursor=conn.execute('SELECT * FROM sessions ORDER BY token_hash')
   return [c.name for c in cursor.description],cursor.fetchall()
 columns,old=sessions(baseline_report['restored_database']);_,new=sessions('timelog_system_test')
 columns_changed=sorted({col for a,b in zip(old,new) for col,x,y in zip(columns,a,b) if x!=y})
 renewal_only=len(old)==len(new) and set(columns_changed)<= {'expires_at','last_seen_at'} and all(y>=x for a,b in zip(old,new) for col,x,y in zip(columns,a,b) if col in columns_changed)
passed=not changed or renewal_only
report={'passed':passed,'business_data_unchanged':passed,'all_tables_unchanged':not changed,'changed_tables':changed,'only_normal_session_renewal':renewal_only,'changed_session_columns':columns_changed,'before':baseline,'after':current}
(root/'artifacts/audit/demo-final.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'before','after'}}))
if not passed:raise SystemExit(1)

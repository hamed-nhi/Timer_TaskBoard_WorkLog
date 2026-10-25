"""Audit-only recovery, persistent volume and session proof; never touches port 18081."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
import httpx
import psycopg
from audit_preserve import fingerprint

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/audit'
CMD=['docker','compose','-p','timelog-qa','-f',str(ROOT/'docker-compose.test.yml'),'--profile','audit']
EXEC=CMD+['exec','-T','audit-db']
SOURCE='timelog_audit_test'
CONN=dict(host='127.0.0.1',port=5544,user='auditor',password='audit-password-only')

def snapshot(database):
    assert database==SOURCE or (database.startswith('timelog_audit_restore_') and database.endswith('_test'))
    with psycopg.connect(**CONN,dbname=database) as conn:
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return fingerprint(conn)

def wait(client):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        try:
            response=client.get('/api/me')
            if response.status_code==200:return response.json()
        except httpx.HTTPError:pass
        time.sleep(.5)
    raise AssertionError('Audit did not recover or session was lost')

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    target='timelog_audit_restore_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'_test'
    with httpx.Client(base_url='http://127.0.0.1:18082',timeout=15,trust_env=False,headers={'X-Requested-With':'timelog'}) as client:
        client.post('/api/auth/login',json={'username':'qa_alice','password':'qa-system-password-1'}).raise_for_status()
        before=snapshot(SOURCE)
        dump=OUT/'audit-only.dump'
        with psycopg.connect(**CONN,dbname=SOURCE) as conn:
            conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            exported=conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
            before=fingerprint(conn)
            with dump.open('wb') as stream:subprocess.run(EXEC+['pg_dump','-U','auditor','-Fc','--snapshot',exported,SOURCE],stdout=stream,check=True)
        subprocess.run(EXEC+['createdb','-U','auditor',target],check=True)
        try:
            with dump.open('rb') as stream:subprocess.run(EXEC+['pg_restore','--exit-on-error','--no-owner','-U','auditor','-d',target],stdin=stream,check=True)
            assert snapshot(target)==before,'Restore content differs'
        finally:subprocess.run(EXEC+['dropdb','-U','auditor',target],check=True)
        stages=[]
        for command in [('restart','audit-api','audit-web'),('up','-d','--force-recreate','audit-db','audit-api','audit-web')]:
            started=time.monotonic()
            subprocess.run(CMD+list(command),check=True,capture_output=True)
            identity=wait(client)
            assert identity['username']=='qa_alice'
            after=snapshot(SOURCE)
            assert before==after,'Persistent data changed across restart/recreate'
            stages.append({'operation':' '.join(command),'seconds':round(time.monotonic()-started,2),'all_tables_equal':True,'session_preserved':True})
    result={'passed':True,'dump_restore_equal':True,'tables':before,'stages':stages,'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest()}
    (OUT/'recovery.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'tables':len(before),'stages':stages}))

"""Run the actual deployment scripts with real PostgreSQL/GPG in a private QA harness.
Only the Docker transport/QA role are adapted; producers and archive validation are real.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone
import psycopg
from audit_preserve import fingerprint

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/audit'
private=ROOT/'backups/audit-script-harness'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
private.mkdir(parents=True,exist_ok=False)
(private/'deploy').mkdir();(private/'bin').mkdir();(private/'keyring').mkdir()
for name in ('backup.sh','restore_test.sh'):
 (private/'deploy'/name).write_text((ROOT/'deploy'/name).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')

def unix(path):
 value=Path(path).resolve().as_posix()
 return '/'+value[0].lower()+value[2:] if os.name=='nt' else value

bash=shutil.which('bash') if os.name!='nt' else r'C:\Program Files\Git\bin\bash.exe'
real_docker=shutil.which('docker')
assert bash and real_docker,'Bash and Docker required'
wrapper='''#!/bin/bash
set -eu
[ "$1" = compose ] && [ "$2" = exec ] && [ "$3" = -T ] && [ "$4" = db ] || exit 98
shift 4
case "$1" in pg_dump|pg_restore|createdb|dropdb|psql) ;; *) exit 99;; esac
args=(); previous=''
for value in "$@"; do
 if [ "$value" = timelog ]; then
  if [ "$previous" = -U ]; then value=auditor; else value=timelog_audit_test; fi
 fi
 args+=("$value"); previous="$value"
done
exec "$QA_REAL_DOCKER" exec -i timelog-qa-audit-db-1 "${args[@]}"
'''
# The transport is fixed to this audit container and never delegates to compose defaults.
(private/'bin/docker').write_text(wrapper,encoding='utf-8',newline='\n');(private/'bin/docker').chmod(0o700)
env=dict(os.environ,QA_REAL_DOCKER=unix(real_docker),GNUPGHOME=unix(private/'keyring'),MSYS_NO_PATHCONV='1')
env['PATH']=str(private/'bin')+os.pathsep+env['PATH']
# Bash converts Windows PATH at startup; add an explicit POSIX path as well.
command_prefix='export PATH="'+unix(private/'bin')+':$PATH"; '

def key(value):
 (private/'.env').write_text('BACKUP_PASSPHRASE='+value+'\n',encoding='utf-8')

def run(name):
 return subprocess.run([bash,'-c',command_prefix+'sh deploy/'+name],cwd=private,env=env,capture_output=True,timeout=120)

def snap():
 with psycopg.connect(host='127.0.0.1',port=5544,user='auditor',password='audit-password-only',dbname='timelog_audit_test') as c:
  c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');return fingerprint(c)

try:
 key('synthetic-script-audit-passphrase')
 before=snap()
 first=run('backup.sh');assert first.returncode==0,first.stderr.decode(errors='replace')
 files=list((private/'backups/daily').glob('*.gpg'));assert len(files)==1
 digest=hashlib.sha256(files[0].read_bytes()).hexdigest()
 second=run('backup.sh');assert second.returncode==0,second.stderr.decode(errors='replace')
 assert len(list((private/'backups/daily').glob('*.gpg')))==2
 assert hashlib.sha256(files[0].read_bytes()).hexdigest()==digest
 valid=run('restore_test.sh');assert valid.returncode==0,valid.stderr.decode(errors='replace')
 key('wrong-script-audit-passphrase')
 wrong=run('restore_test.sh');assert wrong.returncode!=0,'Wrong key accepted'
 key('synthetic-script-audit-passphrase')
 newest=max((private/'backups/daily').glob('*.gpg'),key=lambda p:p.stat().st_mtime_ns)
 newest.write_bytes(newest.read_bytes()[:32])
 corrupt=run('restore_test.sh');assert corrupt.returncode!=0,'Corrupt envelope accepted'
 assert snap()==before,'Audit source changed during backup/restore'
 report={'passed':True,'actual_deploy_scripts':True,'real_pg_dump_gpg_restore':True,'wrong_key_rejected':True,'corrupt_file_rejected':True,'prior_backup_preserved':True,'source_unchanged':True}
 (OUT/'backup-scripts.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:
 gpgconf=Path(r'C:\Program Files\Git\usr\bin\gpgconf.exe') if os.name=='nt' else Path(shutil.which('gpgconf') or '/usr/bin/gpgconf')
 if gpgconf.exists():subprocess.run([str(gpgconf),'--homedir',unix(private/'keyring'),'--kill','gpg-agent'],capture_output=True)

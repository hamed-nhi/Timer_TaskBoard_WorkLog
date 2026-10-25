"""Encrypt and verify the preserved real snapshot without printing its key or contents."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime,timezone
import psycopg
from audit_preserve import fingerprint
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/audit'
proof=json.loads((OUT/'preservation.json').read_text());source=ROOT/proof['private_backup'];private=source.parent
key=private/'recovery.key';encrypted=private/'current-demo.dump.gpg'
if key.exists() or encrypted.exists():raise SystemExit('Existing encrypted preservation must be reviewed rather than overwritten')
key.write_text(secrets.token_urlsafe(48),encoding='ascii');key.chmod(0o600)
gpg=shutil.which('gpg') or r'C:\Program Files\Git\usr\bin\gpg.exe'
def arg(path):
 s=Path(path).resolve().as_posix();return '/'+s[0].lower()+s[2:] if os.name=='nt' and '/Git/' in str(gpg).replace('\\','/') else s
cmd=['docker','compose','-p','timelog-qa','-f',str(ROOT/'docker-compose.test.yml'),'exec','-T','db']
target='timelog_preserve_crypto_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'_test'
with tempfile.TemporaryDirectory(prefix='crypto-verify-',dir=private) as home:
 common=[gpg,'--homedir',arg(home),'--batch','--yes','--no-symkey-cache','--pinentry-mode','loopback','--passphrase-file',arg(key)]
 subprocess.run(common+['--symmetric','--cipher-algo','AES256','--output',arg(encrypted),arg(source)],capture_output=True,check=True)
 restored=Path(home)/'verified.dump'
 subprocess.run(common+['--output',arg(restored),'--decrypt',arg(encrypted)],capture_output=True,check=True)
 assert hashlib.sha256(restored.read_bytes()).hexdigest()==proof['dump_sha256']
 subprocess.run(cmd+['createdb','-U','timelog',target],capture_output=True,check=True)
 try:
  with restored.open('rb') as stream:subprocess.run(cmd+['pg_restore','--exit-on-error','--no-owner','-U','timelog','-d',target],stdin=stream,capture_output=True,check=True)
  with psycopg.connect(host='127.0.0.1',port=5543,user='timelog',password='qa-password-only',dbname=target) as conn:
   conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');assert fingerprint(conn)==proof['tables']
 finally:subprocess.run(cmd+['dropdb','-U','timelog',target],capture_output=True,check=True)
 gpgconf=Path(gpg).with_name('gpgconf.exe' if os.name=='nt' else 'gpgconf')
 if gpgconf.exists():subprocess.run([str(gpgconf),'--homedir',arg(home),'--kill','gpg-agent'],capture_output=True)
result={'passed':True,'real_preserved_snapshot_encrypted':True,'encrypted_restore_equal':True,'all_tables':len(proof['tables']),'sha256_equal':True,'encrypted_sha256':hashlib.sha256(encrypted.read_bytes()).hexdigest(),'key_stored_privately':True}
(OUT/'real-backup-crypto.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

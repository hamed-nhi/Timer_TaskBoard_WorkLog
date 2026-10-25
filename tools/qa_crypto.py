"""Actual AES256 GPG roundtrip of the synthetic QA dump, with an isolated keyring."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/audit"
gpg = os.environ.get("QA_GPG") or shutil.which("gpg")
if not gpg:
    candidate = Path(r"C:\Program Files\Git\usr\bin\gpg.exe")
    gpg = str(candidate) if candidate.exists() else None
if not gpg:
    raise SystemExit("GPG is not installed; record this test as unexecuted, not passed")
source = OUT / "audit-only.dump"
if not source.exists():
    raise SystemExit("Run audit_recovery.py first")
encrypted = OUT / "audit-only.dump.gpg"
def argument(value):
    value = Path(value).resolve().as_posix()
    if os.name == "nt" and "/Git/" in str(gpg).replace("\\", "/"):
        return "/" + value[0].lower() + value[2:]
    return value


with tempfile.TemporaryDirectory(prefix="timelog-qa-gpg-") as home:
    common = [gpg, "--homedir", argument(home), "--batch", "--yes", "--pinentry-mode", "loopback", "--no-symkey-cache"]
    try:
        result = subprocess.run(common + ["--passphrase-fd", "0", "--symmetric", "--cipher-algo", "AES256",
                                         "--output", argument(encrypted), argument(source)],
                                input=b"synthetic-qa-key-only\n", capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        decrypted = Path(home) / "roundtrip.dump"
        result = subprocess.run(common + ["--passphrase-fd", "0", "--output", argument(decrypted),
                                         "--decrypt", argument(encrypted)],
                                input=b"synthetic-qa-key-only\n", capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest(source) == digest(decrypted)
        wrong = subprocess.run(common + ["--passphrase-fd", "0", "--output", argument(Path(home) / "wrong.dump"),
                                        "--decrypt", argument(encrypted)],
                               input=b"wrong-qa-key\n", capture_output=True)
        assert wrong.returncode != 0
        corrupt = Path(home) / "truncated.gpg"
        corrupt.write_bytes(encrypted.read_bytes()[:max(1, encrypted.stat().st_size // 2)])
        damaged = subprocess.run(common + ["--passphrase-fd", "0", "--output", argument(Path(home) / "damaged.dump"),
                                          "--decrypt", argument(corrupt)], input=b"synthetic-qa-key-only\n", capture_output=True)
        assert damaged.returncode != 0
        report = {"truncated_ciphertext_rejected": True,"aes256_roundtrip": "passed", "sha256_equal": True,
                  "wrong_passphrase_rejected": True, "encrypted_bytes": encrypted.stat().st_size}
        (OUT / "crypto.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    finally:
        executable = Path(gpg).with_name("gpgconf.exe" if os.name == "nt" else "gpgconf")
        if executable.exists():
            subprocess.run([str(executable), "--homedir", argument(home), "--kill", "gpg-agent"],
                           capture_output=True, timeout=10)

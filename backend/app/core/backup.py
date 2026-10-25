"""Stable source revisions; clock time and workbook ZIP metadata are not revisions."""
import hashlib
import json
import re
from urllib.parse import urlparse

from .errors import ApiError


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def backup_revision(data):
    return fingerprint({k: v for k, v in data.items() if k != "exported_at"})


def sheet_id(url):
    parsed = urlparse(url)
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "docs.google.com" or not match:
        raise ApiError("لینک باید آدرس معتبر Google Sheet باشد")
    return match.group(1)

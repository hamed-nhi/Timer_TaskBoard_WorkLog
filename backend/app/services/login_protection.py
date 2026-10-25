"""Persistent ban policy and admission state. Caller holds the login admission lock."""
import ipaddress
import json
from datetime import timedelta

from ..core.errors import ApiError
from ..core.config import settings
from ..core.time import now_local
from ..db.session import Db

DEFAULT_POLICY = {"attempts": 3, "durations_minutes": [15, 600, 43200],
                  "unknown_attempts": 3, "unknown_minutes": 1440, "reset_on_success": True}

RATE_FIELDS = {"ip_max_failures": ("login_ip_max_failures", 1000), "ip_window_minutes": ("login_window_minutes", 1440),
               "ip_burst": ("login_ip_burst", 10000), "ip_hourly": ("login_ip_hourly", 100000),
               "global_per_minute": ("login_global_per_minute", 100000)}


def policy(db: Db):
    row = db.execute("SELECT policy FROM login_protection_settings WHERE id = 1").fetchone()
    return {**DEFAULT_POLICY, **{key: getattr(settings, field) for key, (field, _) in RATE_FIELDS.items()}, **(row["policy"] if row else {})}


def identity(ip):
    return str(ipaddress.ip_address(ip or "0.0.0.0"))


def check_bans(db: Db, ip, username):
    row = db.execute("SELECT banned_until FROM login_bans WHERE ip = ? AND username IN ('', ?) "
                     "AND banned_until > ? ORDER BY banned_until DESC LIMIT 1",
                     (identity(ip), username, now_local())).fetchone()
    if row:
        retry = max(1, int((row["banned_until"] - now_local()).total_seconds()) + 1)
        raise ApiError(f"ورود از این نشانی موقتاً مسدود است؛ {(retry + 59) // 60} دقیقهٔ دیگر دوباره تلاش کنید", 429,
                       headers={"Retry-After": str(retry)})


def failed(db: Db, ip, username, known: bool, config: dict):
    name = username if known else ""
    now = now_local()
    row = db.execute("SELECT * FROM login_bans WHERE ip = ? AND username = ?", (identity(ip), name)).fetchone()
    if not row:
        uid = db.insert("INSERT INTO login_bans (ip, username, failures, stage, updated_at, reason) "
                        "VALUES (?, ?, 0, 0, ?, ?)", (identity(ip), name, now, "password" if known else "unknown_username"))
        row = {"id": uid, "failures": 0, "stage": 0, "updated_at": now, "banned_until": None}
    # Requests already admitted concurrently cannot lengthen an existing ban.
    if row["banned_until"] and row["banned_until"] > now:
        return
    failures = row["failures"] if now - row["updated_at"] <= timedelta(minutes=20) else 0
    failures += 1
    stage = row["stage"]
    until = None
    if failures >= config["attempts" if known else "unknown_attempts"]:
        minutes = config["durations_minutes"][min(stage, 2)] if known else config["unknown_minutes"]
        until = now + timedelta(minutes=minutes)
        stage = min(stage + 1, 3)
        failures = 0
    db.execute("UPDATE login_bans SET failures = ?, stage = ?, banned_until = ?, updated_at = ? WHERE id = ?",
               (failures, stage, until, now, row["id"]))


def succeeded(db: Db, ip, username, config):
    if config["reset_on_success"]:
        db.execute("DELETE FROM login_bans WHERE ip = ? AND (username = ? OR (username = '' AND banned_until IS NULL))",
                   (identity(ip), username))


def overview(db: Db):
    rows = db.execute("SELECT id, host(ip) ip, username, failures, stage, banned_until, updated_at, reason "
                      "FROM login_bans ORDER BY updated_at DESC LIMIT 200").fetchall()
    now = now_local()
    return {"policy": policy(db), "bans": [{**r, "active": bool(r["banned_until"] and r["banned_until"] > now)} for r in rows]}


def update_policy(db: Db, admin: dict, data: dict):
    if set(data) != set(DEFAULT_POLICY) | set(RATE_FIELDS):
        raise ApiError("همهٔ تنظیمات سیاست ورود را وارد کنید")
    for key, maximum in [("attempts", 20), ("unknown_attempts", 20), ("unknown_minutes", 525600), *[(key, maximum) for key, (_, maximum) in RATE_FIELDS.items()]]:
        if type(data[key]) is not int or not 1 <= data[key] <= maximum:
            raise ApiError("تعداد تلاش یا مدت مسدودی نامعتبر است")
    durations = data["durations_minutes"]
    if not isinstance(durations, list) or len(durations) != 3 or any(type(v) is not int or not 1 <= v <= 525600 for v in durations) or durations != sorted(durations):
        raise ApiError("سه مدت مسدودی باید مثبت و به‌ترتیب افزایشی باشند")
    if type(data["reset_on_success"]) is not bool:
        raise ApiError("تنظیم بازنشانی نامعتبر است")
    db.execute("SELECT pg_advisory_xact_lock(731906, 1)")
    db.execute("INSERT INTO login_protection_settings (id, policy) VALUES (1, ?::jsonb) "
               "ON CONFLICT (id) DO UPDATE SET policy = EXCLUDED.policy", (json.dumps(data),))
    db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'login_policy_changed', ?::jsonb)",
               (admin["id"], json.dumps(data)))
    db.commit()
    return overview(db)


def unblock(db: Db, admin: dict | None, ban_id: int, reset: bool):
    if type(reset) is not bool:
        raise ApiError("تنظیم بازنشانی نامعتبر است")
    db.execute("SELECT pg_advisory_xact_lock(731906, 1)")
    row = db.execute("SELECT id, host(ip) ip, username FROM login_bans WHERE id = ?", (ban_id,)).fetchone()
    if not row:
        raise ApiError("رکورد مسدودی پیدا نشد", 404)
    # Releasing a ban must also remove its short admission reservations; otherwise a
    # freshly released user still receives 429 until that separate window expires.
    db.execute("DELETE FROM login_attempts WHERE host(ip) = ? AND (? = '' OR username = ?)",
               (row["ip"], row["username"], row["username"]))
    if reset:
        db.execute("DELETE FROM login_bans WHERE id = ?", (ban_id,))
    else:
        db.execute("UPDATE login_bans SET banned_until = NULL, failures = 0, updated_at = ? WHERE id = ?", (now_local(), ban_id))
    if admin:
        db.execute("INSERT INTO audit_log (user_id, kind, payload) VALUES (?, 'login_ban_released', ?::jsonb)",
                   (admin["id"], json.dumps({"ban_id": ban_id, "reset": reset})))
    db.commit()
    return {"ok": True}

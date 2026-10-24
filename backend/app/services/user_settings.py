"""Per-user key/value settings."""
DEFAULT_SETTINGS = {"daily_goal_minutes": "480", "weekly_goal_minutes": "2400"}


def get_setting(db, uid, key, default=None):
    row = db.execute("SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (uid, key)).fetchone()
    return row["value"] if row else default


def set_setting(db, uid, key, value):
    db.execute("INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
               "ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value", (uid, key, str(value)))


def get_goals(db, uid):
    rows = db.execute("SELECT key, value FROM user_settings WHERE user_id = ?", (uid,)).fetchall()
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: r["value"] for r in rows})
    return {
        "daily_goal_minutes": float(settings["daily_goal_minutes"]),
        "weekly_goal_minutes": float(settings["weekly_goal_minutes"]),
    }

"""All times are naive wall-clock times in the app time zone (Tehran), like the desktop app."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from .config import settings

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]  # Saturday first
_TZ = ZoneInfo(settings.app_tz)


def now_local() -> datetime:
    return datetime.now(_TZ).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


def g2j(g_date: date) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=g_date)


def today_jalali() -> jdatetime.date:
    return g2j(today_local())


def j2g(y: int, m: int, d: int) -> date:
    return jdatetime.date(y, m, d).togregorian()


def parse_time(s):
    if not s:
        return None
    return datetime.strptime(s, "%H:%M").time()


def to_dt(value):
    """Datetime from a DB value or an ISO string."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def jalali_week_range(today_g):
    """Persian week: Saturday through Friday, as Gregorian dates."""
    days_since_saturday = (today_g.weekday() - 5) % 7
    week_start = today_g - timedelta(days=days_since_saturday)
    return week_start, week_start + timedelta(days=6)


def jalali_month_length(year, month):
    if month <= 6:
        return 31
    if month < 12:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def week_start_of(d):
    """The Saturday that starts the Iranian week containing `d`."""
    return d - timedelta(days=(d.weekday() + 2) % 7)

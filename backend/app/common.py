"""Shared constants, errors and input validation (ported from the desktop app)."""
import re

from .timeutil import j2g


class ApiError(Exception):
    def __init__(self, message, status=400, headers=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.headers = headers


MAX_TITLE_LEN = 500
MAX_TAG_LEN = 60
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "timelog"

# the company's main system asks for a report type; a task with "meeting with ..." is a meeting
MEETING_REPORT_TYPE = "جلسات"


def clean_title(value):
    title = (value or "").strip() if isinstance(value, str) or value is None else ""
    if not title:
        raise ApiError("شرح فعالیت الزامی است")
    if len(title) > MAX_TITLE_LEN:
        raise ApiError(f"شرح فعالیت نباید بیشتر از {MAX_TITLE_LEN} کاراکتر باشد")
    return title


def clean_time(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not TIME_RE.match(value):
        raise ApiError("ساعت نامعتبر است (فرمت درست مثل 09:30)")
    return value


def clean_jalali(year, month, day):
    try:
        y, m, d = int(year), int(month), int(day)
        j2g(y, m, d)
    except (TypeError, ValueError, OverflowError):
        raise ApiError("تاریخ نامعتبر است")
    return y, m, d


def clean_tag_id(db, uid, value):
    if value in (None, "", 0):
        return None
    try:
        tag_id = int(value)
    except (TypeError, ValueError):
        raise ApiError("تگ نامعتبر است")
    if not db.execute("SELECT 1 FROM tags WHERE id = ? AND user_id = ?", (tag_id, uid)).fetchone():
        raise ApiError("تگ نامعتبر است")
    return tag_id


def clean_tag_name(value):
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        raise ApiError("نام تگ الزامی است")
    if len(name) > MAX_TAG_LEN:
        raise ApiError(f"نام تگ نباید بیشتر از {MAX_TAG_LEN} کاراکتر باشد")
    return name


_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی"})


def tag_key(name):
    """Two names that only differ in case or in Arabic/Persian letter shapes are the same tag to a reader."""
    return name.translate(_ARABIC_TO_PERSIAN).casefold()


def not_found():
    raise ApiError("not found", 404)

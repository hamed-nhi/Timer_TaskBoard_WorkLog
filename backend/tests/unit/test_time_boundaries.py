"""Deterministic boundary tests for date/time and report-only arithmetic."""
from datetime import date, timedelta
from copy import deepcopy

import pytest

from app.core.errors import ApiError
from app.core.time import g2j, j2g
from app.services.fill import suggest_fill
from app.services.timecalc import compute_duration, parse_adjust
from app.services.validation import clean_title


@pytest.mark.parametrize("start,end,expected", [
    ("00:00", "00:00", 0), ("23:59", "00:00", 1), ("23:50", "00:20", 30),
    ("09:00", "17:00", 480), ("00:00", "23:59", 1439), ("12:30", "12:31", 1)])
def test_clock_boundaries(start, end, expected):
    assert compute_duration(start, end) == expected


def test_jalali_roundtrip_across_year_and_leap_boundaries():
    anchor = date(2020, 1, 1)
    for offset in range(0, 365 * 8, 7):
        value = anchor + timedelta(days=offset)
        jalali = g2j(value)
        assert j2g(jalali.year, jalali.month, jalali.day) == value


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "not a number", 10081, -10081])
def test_invalid_adjustments_are_rejected(value):
    with pytest.raises(ApiError):
        parse_adjust(value)


@pytest.mark.parametrize("length", [1, 499, 500])
def test_persian_title_length_boundaries(length):
    assert clean_title("ی" * length) == "ی" * length


def test_overlong_title_is_rejected():
    with pytest.raises(ApiError):
        clean_title("ی" * 501)


def test_fill_never_mutates_recorded_items_and_skips_zero_weight():
    items = [{"id": 1, "minutes": 120, "weight": 0}, {"id": 2, "minutes": 120, "weight": 1}]
    before = deepcopy(items)
    assert suggest_fill(items, 60) == {1: 0, 2: 60}
    assert items == before


@pytest.mark.xfail(strict=True, reason="QA-001: rounding a 50% cap to 5 minutes can exceed the cap")
def test_fill_suggestion_respects_cap_for_short_tasks():
    assert suggest_fill([{"id": 1, "minutes": 6, "weight": 1}], 100)[1] <= 3


@pytest.mark.xfail(strict=True, reason="QA-002: independent rounding can exceed the total allowed gap")
def test_fill_suggestion_does_not_exceed_total_allowance():
    values = suggest_fill([{"id": 1, "minutes": 60, "weight": 1},
                           {"id": 2, "minutes": 60, "weight": 1}], 8)
    assert sum(values.values()) <= 9

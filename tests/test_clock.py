"""时间基元：解析、归属日、日界线校验。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from orbit.core.clock import (
    circular_span,
    day_key,
    format_time,
    from_minutes,
    line_in_sleep_gap,
    minutes,
    parse_time,
    suggest_day_line,
)

LINE = time(6, 0)


def test_parse_and_format_roundtrip():
    assert parse_time("09:00") == time(9, 0)
    assert parse_time("9:05") == time(9, 5)
    assert parse_time(" 23:59:30 ") == time(23, 59, 30)
    assert format_time(time(7, 3)) == "07:03"


@pytest.mark.parametrize("bad", ["", "9点", "25:00", "09:00:00:00"])
def test_parse_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


def test_minutes_and_from_minutes():
    assert minutes(time(6, 30)) == 390
    assert from_minutes(390) == time(6, 30)
    assert from_minutes(1500) == time(1, 0)  # 越过 24 小时折回


def test_circular_span_wraps_over_midnight():
    assert circular_span(time(23, 0), time(9, 0)) == 10 * 60
    assert circular_span(time(9, 0), time(23, 0)) == 14 * 60
    assert circular_span(time(6, 0), time(6, 0)) == 0


# --- 归属日 ---------------------------------------------------------------


def test_day_key_before_line_belongs_to_previous_day():
    assert day_key(datetime(2026, 11, 14, 3, 0), LINE) == date(2026, 11, 13)


def test_day_key_boundary_is_inclusive_for_today():
    assert day_key(datetime(2026, 11, 14, 5, 59), LINE) == date(2026, 11, 13)
    assert day_key(datetime(2026, 11, 14, 6, 0), LINE) == date(2026, 11, 14)


# --- 日界线校验 -----------------------------------------------------------


def test_line_inside_sleep_gap_is_ok():
    assert line_in_sleep_gap(time(9, 0), time(23, 0), time(6, 0))
    assert line_in_sleep_gap(time(9, 0), time(23, 0), time(9, 0))  # 正好等于起床
    assert line_in_sleep_gap(time(9, 0), time(1, 0), time(6, 0))  # 跨零点睡


def test_line_after_wake_is_rejected():
    """起床 05:00、日界线 06:00 —— 05:30 已经起床半小时，却还在算昨天。"""
    assert not line_in_sleep_gap(time(5, 0), time(23, 0), time(6, 0))


def test_line_before_sleep_is_rejected_when_sleeping_after_midnight():
    """09:00 起、01:00 睡、日界线 00:30 —— 凌晨 00:10 还在活动，却被算成前天。"""
    assert not line_in_sleep_gap(time(9, 0), time(1, 0), time(0, 30))


def test_line_equal_to_sleep_is_rejected():
    """睡觉那一刻就切新的一天，会让刚结束的那段直接变成「新一天 0%」。"""
    assert not line_in_sleep_gap(time(9, 0), time(23, 0), time(23, 0))


def test_24_hour_window_has_no_gap_so_line_is_irrelevant():
    assert line_in_sleep_gap(time(8, 0), time(8, 0), time(6, 0))


def test_suggest_day_line_lands_in_the_middle_of_sleep():
    assert suggest_day_line(time(5, 0), time(23, 0)) == time(2, 0)
    assert suggest_day_line(time(9, 0), time(23, 0)) == time(4, 0)
    assert suggest_day_line(time(9, 0), time(1, 0)) == time(5, 0)


@pytest.mark.parametrize(
    "wake,sleep",
    [(time(5, 0), time(23, 0)), (time(9, 0), time(1, 0)), (time(6, 0), time(22, 30))],
)
def test_suggestion_always_satisfies_the_check(wake, sleep):
    suggested = suggest_day_line(wake, sleep)
    assert line_in_sleep_gap(wake, sleep, suggested)

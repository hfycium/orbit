"""进度纯函数。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from orbit.core import STATE_BEFORE, STATE_OVER, STATE_RUNNING, build_window, compute


def window():
    return build_window(date(2026, 11, 14), time(9, 0), time(23, 0), "fixed")


def test_progress_half_way():
    progress = compute(window(), datetime(2026, 11, 14, 16, 0))
    assert progress.state == STATE_RUNNING
    assert progress.ratio == pytest.approx(0.5)
    assert progress.remaining == timedelta(hours=7)
    assert progress.over == timedelta(0)


def test_progress_over_sleep_time():
    progress = compute(window(), datetime(2026, 11, 14, 23, 30))
    assert progress.state == STATE_OVER
    assert progress.ratio == 1.0
    assert progress.over == timedelta(minutes=30)


def test_progress_before_wake_time():
    progress = compute(window(), datetime(2026, 11, 14, 8, 0))
    assert progress.state == STATE_BEFORE
    assert progress.ratio == 0.0
    assert progress.remaining == timedelta(hours=14)


def test_progress_ratio_is_clamped_to_window():
    """进度上限锁在 1.0，超时靠 over 表达，不把环画过一整圈。"""
    progress = compute(window(), datetime(2026, 11, 15, 6, 0))
    assert progress.ratio == 1.0
    assert progress.over == timedelta(hours=7)


def test_progress_on_crossing_window():
    crossing = build_window(date(2026, 11, 14), time(9, 0), time(1, 0), "fixed")
    progress = compute(crossing, datetime(2026, 11, 15, 0, 30))
    assert progress.state == STATE_RUNNING
    assert progress.remaining == timedelta(minutes=30)
    assert progress.ratio == pytest.approx(15.5 / 16)


def test_zero_length_window_is_empty_not_a_crash():
    broken = build_window(date(2026, 11, 14), time(9, 0), time(9, 0), "t")
    broken = broken.__class__(
        day=broken.day, start=broken.start, end=broken.start, source="t"
    )
    assert compute(broken, datetime(2026, 11, 14, 9, 0)).state == "empty"

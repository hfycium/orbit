"""作息窗口：三种模式、临时调整、继承、归属日纠正、日界线巡检。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from orbit.config import Config, DatedSchedule, Schedule, Weekly
from orbit.core import (
    SOURCE_DAILY_BASELINE,
    STATE_OVER,
    STATE_RUNNING,
    build_window,
    compute,
    daily_source,
    fallback_window,
    inspect_day_line,
    resolve,
    window_for_day,
)


def fixed_config(wake="09:00", sleep="23:00") -> Config:
    return Config(mode="fixed", fixed=Schedule(wake, sleep))


# --- 窗口构造 -------------------------------------------------------------


def test_window_crosses_midnight_when_sleep_is_earlier_than_wake():
    window = build_window(date(2026, 11, 14), time(9, 0), time(1, 0), "test")
    assert window.start == datetime(2026, 11, 14, 9, 0)
    assert window.end == datetime(2026, 11, 15, 1, 0)
    assert window.total == timedelta(hours=16)


def test_equal_wake_and_sleep_means_24_hours():
    window = build_window(date(2026, 11, 14), time(23, 0), time(23, 0), "test")
    assert window.total == timedelta(hours=24)


def test_fallback_is_a_whole_calendar_day():
    window = fallback_window(date(2026, 11, 14))
    assert window.start == datetime(2026, 11, 14, 0, 0)
    assert window.end == datetime(2026, 11, 15, 0, 0)
    assert window.is_fallback


def test_window_contains_is_left_closed_right_open():
    window = build_window(date(2026, 11, 14), time(9, 0), time(23, 0), "test")
    assert window.contains(datetime(2026, 11, 14, 9, 0))
    assert window.contains(datetime(2026, 11, 14, 22, 59))
    assert not window.contains(datetime(2026, 11, 14, 23, 0))


# --- 三种模式 -------------------------------------------------------------


def test_fixed_mode_applies_every_day():
    window = resolve(fixed_config(), datetime(2026, 11, 14, 16, 0))
    assert window.source == "fixed"
    assert window.start == datetime(2026, 11, 14, 9, 0)
    assert window.end == datetime(2026, 11, 14, 23, 0)


def test_weekly_friday_night_uses_weekday_schedule():
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("08:00", "23:30"), Schedule("10:00", "01:00")),
    )
    window = resolve(config, datetime(2026, 11, 13, 23, 0))
    assert window.source == "weekly.weekday"
    assert window.start == datetime(2026, 11, 13, 8, 0)


def test_weekly_saturday_1am_still_belongs_to_friday():
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("08:00", "23:30"), Schedule("10:00", "01:00")),
    )
    window = resolve(config, datetime(2026, 11, 14, 1, 0))
    assert window.day == date(2026, 11, 13)
    assert window.source == "weekly.weekday"
    assert window.end == datetime(2026, 11, 13, 23, 30)


def test_weekly_saturday_morning_switches_to_weekend():
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("08:00", "23:30"), Schedule("10:00", "01:00")),
    )
    window = resolve(config, datetime(2026, 11, 14, 10, 0))
    assert window.source == "weekly.weekend"
    assert window.start == datetime(2026, 11, 14, 10, 0)


# --- 归属日纠正（起床早于日界线）-----------------------------------------


def test_early_wake_wins_over_day_line():
    """05:00 起床、日界线 06:00：05:30 属于今天，而不是昨天的超时。"""
    config = fixed_config("05:00", "23:00")
    window = resolve(config, datetime(2026, 11, 14, 5, 30))
    assert window.day == date(2026, 11, 14)
    assert window.start == datetime(2026, 11, 14, 5, 0)


def test_early_wake_progress_is_tiny_not_over():
    config = fixed_config("05:00", "23:00")
    progress = compute(resolve(config, datetime(2026, 11, 14, 5, 30)), datetime(2026, 11, 14, 5, 30))
    assert progress.state == STATE_RUNNING
    assert progress.ratio == pytest.approx(0.5 / 18)


def test_before_wake_still_belongs_to_previous_day():
    """04:00 还没起床，仍算昨天 —— 这条不能被上面的纠正规则吃掉。"""
    config = fixed_config("05:00", "23:00")
    window = resolve(config, datetime(2026, 11, 14, 4, 0))
    assert window.day == date(2026, 11, 13)
    assert compute(window, datetime(2026, 11, 14, 4, 0)).state == STATE_OVER


def test_flat_mode_after_wake_does_not_flip_to_next_day():
    """普通作息：16:00 属于今天，纠正规则不该把日子往后推。"""
    window = resolve(fixed_config(), datetime(2026, 11, 14, 16, 0))
    assert window.day == date(2026, 11, 14)


# --- 每日模式 -------------------------------------------------------------


def test_daily_mode_inherits_from_previous_day():
    config = Config(mode="daily", daily={"2026-11-13": Schedule("09:00", "23:00")})
    window = resolve(config, datetime(2026, 11, 14, 16, 0))
    assert window.source == "daily:2026-11-13"
    assert window.start == datetime(2026, 11, 14, 9, 0)  # 时刻继承，日期是今天


def test_daily_today_record_beats_history():
    config = Config(
        mode="daily",
        daily={"2026-11-13": Schedule("09:00", "23:00"), "2026-11-14": Schedule("07:00", "22:00")},
    )
    window = resolve(config, datetime(2026, 11, 14, 16, 0))
    assert window.source == "daily:2026-11-14"
    assert window.start == datetime(2026, 11, 14, 7, 0)


def test_daily_ignores_future_records():
    config = Config(mode="daily", daily={"2026-11-20": Schedule("07:00", "22:00")})
    window = resolve(config, datetime(2026, 11, 14, 16, 0))
    assert window.is_fallback


def test_daily_mode_without_history_falls_back():
    config = Config(mode="daily")
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).is_fallback


def test_daily_baseline_keeps_inheritance_alive_without_history():
    """历史被裁空 / 误删之后，永久基准仍然给得出作息。"""
    config = Config(
        mode="daily",
        daily={},
        daily_latest=DatedSchedule("2026-11-14", "09:00", "23:00"),
    )
    window = resolve(config, datetime(2026, 12, 24, 16, 0))
    assert window.source == SOURCE_DAILY_BASELINE
    assert window.start == datetime(2026, 12, 24, 9, 0)
    assert config.configured


def test_daily_baseline_from_the_future_is_ignored():
    config = Config(
        mode="daily",
        daily_latest=DatedSchedule("2026-11-20", "09:00", "23:00"),
    )
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).is_fallback


def test_daily_source_prefers_history_over_baseline():
    config = Config(
        mode="daily",
        daily={"2026-11-13": Schedule("06:30", "22:00")},
        daily_latest=DatedSchedule("2026-10-01", "09:00", "23:00"),
    )
    source, schedule = daily_source(config, date(2026, 11, 14))
    assert source == "daily:2026-11-13"
    assert schedule.wake == "06:30"


# --- 临时调整 -------------------------------------------------------------


def test_override_wins_for_its_own_day():
    config = Config(
        mode="fixed",
        fixed=Schedule("09:00", "23:00"),
        override=DatedSchedule("2026-11-14", "08:30", "22:30"),
    )
    window = resolve(config, datetime(2026, 11, 14, 16, 0))
    assert window.source == "override"
    assert window.start == datetime(2026, 11, 14, 8, 30)


def test_override_expires_after_day_line():
    config = Config(
        mode="fixed",
        fixed=Schedule("09:00", "23:00"),
        override=DatedSchedule("2026-11-14", "08:30", "22:30"),
    )
    window = resolve(config, datetime(2026, 11, 15, 16, 0))
    assert window.source == "fixed"


def test_override_with_half_config_is_ignored():
    config = Config(
        mode="fixed",
        fixed=Schedule("09:00", "23:00"),
        override=DatedSchedule("2026-11-14", "08:30"),
    )
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).source == "fixed"


def test_override_is_not_applied_in_daily_mode():
    """每日模式本身就是逐日填，残留的临时调整不该盖住今天那条。"""
    config = Config(
        mode="daily",
        daily={"2026-11-14": Schedule("09:00", "23:00")},
        override=DatedSchedule("2026-11-14", "05:00", "20:00"),
    )
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).source == "daily:2026-11-14"


def test_stale_override_from_a_previous_mode_does_not_leak():
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("08:00", "23:00"), Schedule("09:00", "00:30")),
        override=DatedSchedule("2026-11-01", "05:00", "20:00"),
    )
    window = resolve(config, datetime(2026, 11, 14, 16, 0))
    assert window.source == "weekly.weekend"


# --- 未完成配置 -----------------------------------------------------------


def test_half_filled_fixed_config_is_not_configured():
    config = Config(mode="fixed", fixed=Schedule("09:00", None))
    assert config.configured is False
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).is_fallback


def test_unparsable_time_falls_back_instead_of_crashing():
    config = Config(mode="fixed", fixed=Schedule("9点", "23:00"))
    assert resolve(config, datetime(2026, 11, 14, 16, 0)).is_fallback


def test_unparsable_day_line_falls_back_to_six():
    config = fixed_config()
    config.day_line = "六点"
    assert resolve(config, datetime(2026, 11, 14, 3, 0)).day == date(2026, 11, 13)


# --- 日界线巡检 -----------------------------------------------------------


def test_day_line_ok_for_normal_schedule():
    assert inspect_day_line(fixed_config("09:00", "23:00")) is None


def test_day_line_flagged_when_wake_is_before_it():
    issue = inspect_day_line(fixed_config("05:00", "23:00"))
    assert issue is not None
    assert issue.source == "fixed"
    assert issue.suggested == time(2, 0)
    assert "02:00" in issue.message()


def test_day_line_checked_against_weekend_group():
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("07:30", "23:00"), Schedule("05:30", "23:30")),
    )
    issue = inspect_day_line(config)
    assert issue is not None
    assert issue.source == "weekly.weekend"


def test_day_line_flags_sleep_after_midnight_case():
    """01:00 睡、日界线 00:30：凌晨 00:40 还在活动，却被算成前天。"""
    config = fixed_config("09:00", "01:00")
    config.day_line = "00:30"
    issue = inspect_day_line(config)
    assert issue is not None
    assert issue.suggested == time(5, 0)


def test_window_for_day_is_pure():
    config = fixed_config()
    first = window_for_day(config, date(2026, 11, 14))
    second = window_for_day(config, date(2026, 11, 14))
    assert first == second

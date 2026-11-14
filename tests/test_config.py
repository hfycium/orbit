"""配置持久化：往返、容错、每日记录的裁剪与永久基准。"""

from __future__ import annotations

from datetime import date, datetime

from orbit.config import (
    DAILY_KEEP_DAYS,
    Config,
    DatedSchedule,
    Schedule,
    Weekly,
    load_config,
    save_config,
)
from orbit.core import resolve


def test_config_roundtrip(tmp_path):
    config = Config(
        mode="weekly",
        weekly=Weekly(Schedule("08:00", "23:30"), Schedule("10:00", "01:00")),
        daily={"2026-11-13": Schedule("09:00", "22:00")},
    )
    path = tmp_path / "config.json"
    save_config(config, path)

    loaded = load_config(path)
    assert loaded.mode == "weekly"
    assert loaded.weekly.weekend.sleep == "01:00"
    assert loaded.daily["2026-11-13"].wake == "09:00"


def test_daily_latest_survives_roundtrip(tmp_path):
    config = Config(
        mode="daily",
        daily_latest=DatedSchedule("2026-11-14", "09:00", "23:00"),
    )
    path = tmp_path / "config.json"
    save_config(config, path)
    assert load_config(path).daily_latest.day == "2026-11-14"


def test_missing_config_file_returns_defaults(tmp_path):
    loaded = load_config(tmp_path / "nope.json")
    assert loaded.mode is None
    assert loaded.configured is False


def test_daily_history_is_trimmed_but_baseline_kept():
    daily = {f"2026-01-{day:02d}": Schedule("09:00", "23:00") for day in range(1, 32)}
    trimmed = Config(mode="daily", daily=daily).trimmed(DAILY_KEEP_DAYS)
    assert len(trimmed.daily) == DAILY_KEEP_DAYS
    assert "2026-01-01" not in trimmed.daily
    assert trimmed.daily_latest is not None
    assert trimmed.daily_latest.day == "2026-01-31"


def test_trimmed_does_not_mutate_the_original():
    daily = {f"2026-01-{day:02d}": Schedule("09:00", "23:00") for day in range(1, 32)}
    original = Config(mode="daily", daily=daily)
    original.trimmed(30)
    assert len(original.daily) == 31
    assert original.daily_latest is None


def test_baseline_never_moves_backwards():
    config = Config(
        mode="daily",
        daily={"2026-01-01": Schedule("06:00", "22:00")},
        daily_latest=DatedSchedule("2026-05-01", "09:00", "23:00"),
    )
    assert config.fold_daily_latest().day == "2026-05-01"


def test_incomplete_record_does_not_become_baseline():
    config = Config(mode="daily", daily={"2026-05-02": Schedule("09:00", None)})
    assert config.fold_daily_latest() is None


def test_newest_record_becomes_baseline():
    config = Config(
        mode="daily",
        daily={
            "2026-11-01": Schedule("08:00", "22:00"),
            "2026-11-14": Schedule("07:00", "23:30"),
        },
    )
    baseline = config.fold_daily_latest()
    assert baseline.day == "2026-11-14"
    assert baseline.sleep == "23:30"


def test_long_absence_still_resolves_after_trim():
    """填过一次、时隔 40 天再打开，进度仍是那条作息，不是兜底。"""
    daily = {f"2026-01-{day:02d}": Schedule("07:00", "23:00") for day in range(1, 32)}
    config = Config(mode="daily", daily=daily).trimmed()
    window = resolve(config, datetime(2026, 3, 10, 16, 0))
    assert not window.is_fallback
    assert window.start == datetime(2026, 3, 10, 7, 0)
    assert config.configured


def test_broken_json_shapes_do_not_crash():
    config = Config.from_dict(
        {
            "mode": "bogus",
            "fixed": {"wake": 123},
            "daily": "nope",
            "override": {"wake": "09:00"},
            "daily_latest": [],
        }
    )
    assert config.mode is None
    assert config.fixed.wake is None
    assert config.daily == {}
    assert config.override is None
    assert config.daily_latest is None


def test_override_roundtrip():
    config = Config(mode="fixed", override=DatedSchedule("2026-11-14", "08:30", "22:30"))
    restored = Config.from_dict(config.to_dict())
    assert restored.override.day == "2026-11-14"
    assert restored.override.matches(date(2026, 11, 14))

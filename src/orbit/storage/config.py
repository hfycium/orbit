"""配置模型与持久化。

三种模式互斥，各自的数据都留着，切换模式不会丢。
临时调整（override）自带 day 字段，读到时不等于当前 day_key 就当它失效——
不靠定时器清理，因为关机一整晚回来定时器根本没跑过。

每日模式另存一份 **daily_latest（永久基准）**：逐日记录只留最近 30 天，
但「上一次的作息」必须一直在，否则隔 40 天没开程序就会突然掉进兜底。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from .jsonio import load_json, save_json

MODES = ("fixed", "daily", "weekly")
DAILY_KEEP_DAYS = 30
DEFAULT_DAY_LINE = "06:00"


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


@dataclass
class Schedule:
    """一组起床 / 睡觉时间，两者都填齐才算完整。"""

    wake: str | None = None
    sleep: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.wake and self.sleep)

    def to_dict(self) -> dict:
        return {"wake": self.wake, "sleep": self.sleep}

    @classmethod
    def from_dict(cls, data: object) -> "Schedule":
        if not isinstance(data, dict):
            return cls()
        return cls(wake=_opt_str(data.get("wake")), sleep=_opt_str(data.get("sleep")))


@dataclass
class Weekly:
    weekday: Schedule = field(default_factory=Schedule)
    weekend: Schedule = field(default_factory=Schedule)

    def to_dict(self) -> dict:
        return {
            "weekday": self.weekday.to_dict(),
            "weekend": self.weekend.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: object) -> "Weekly":
        if not isinstance(data, dict):
            return cls()
        return cls(
            weekday=Schedule.from_dict(data.get("weekday")),
            weekend=Schedule.from_dict(data.get("weekend")),
        )


@dataclass
class DatedSchedule:
    """带归属日的一组作息。临时调整和每日基准共用这个形状。

    `day` 是归属日（day_key），不是自然日。
    """

    day: str
    wake: str | None = None
    sleep: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.wake and self.sleep)

    def matches(self, day_key: date) -> bool:
        return self.day == day_key.isoformat()

    def to_dict(self) -> dict:
        return {"day": self.day, "wake": self.wake, "sleep": self.sleep}

    @classmethod
    def from_dict(cls, data: object) -> "DatedSchedule | None":
        if not isinstance(data, dict):
            return None
        day = _opt_str(data.get("day"))
        if not day:
            return None
        return cls(day=day, wake=_opt_str(data.get("wake")), sleep=_opt_str(data.get("sleep")))


@dataclass
class Config:
    mode: str | None = None
    day_line: str = DEFAULT_DAY_LINE
    fixed: Schedule = field(default_factory=Schedule)
    weekly: Weekly = field(default_factory=Weekly)
    daily: dict[str, Schedule] = field(default_factory=dict)
    override: DatedSchedule | None = None
    daily_latest: DatedSchedule | None = None

    @property
    def configured(self) -> bool:
        """引导是否走完：选了模式且对应数据完整。"""
        if self.mode not in MODES:
            return False
        if self.mode == "fixed":
            return self.fixed.complete
        if self.mode == "weekly":
            return self.weekly.weekday.complete and self.weekly.weekend.complete
        return bool(self.daily) or bool(self.daily_latest and self.daily_latest.complete)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "day_line": self.day_line,
            "fixed": self.fixed.to_dict(),
            "weekly": self.weekly.to_dict(),
            "daily": {key: item.to_dict() for key, item in self.daily.items()},
            "override": self.override.to_dict() if self.override else None,
            "daily_latest": self.daily_latest.to_dict() if self.daily_latest else None,
        }

    @classmethod
    def from_dict(cls, data: object) -> "Config":
        if not isinstance(data, dict):
            return cls()
        daily_raw = data.get("daily")
        daily: dict[str, Schedule] = {}
        if isinstance(daily_raw, dict):
            for key, item in daily_raw.items():
                if isinstance(key, str):
                    daily[key] = Schedule.from_dict(item)
        mode = data.get("mode")
        return cls(
            mode=mode if mode in MODES else None,
            day_line=_opt_str(data.get("day_line")) or DEFAULT_DAY_LINE,
            fixed=Schedule.from_dict(data.get("fixed")),
            weekly=Weekly.from_dict(data.get("weekly")),
            daily=daily,
            override=DatedSchedule.from_dict(data.get("override")),
            daily_latest=DatedSchedule.from_dict(data.get("daily_latest")),
        )

    def fold_daily_latest(self) -> "DatedSchedule | None":
        """最近一条完整记录 → 永久基准（不修改自身）。"""
        if not self.daily:
            return self.daily_latest
        newest = max(self.daily)
        entry = self.daily[newest]
        if not entry.complete:
            return self.daily_latest
        if self.daily_latest is None or newest > self.daily_latest.day:
            return DatedSchedule(newest, entry.wake, entry.sleep)
        return self.daily_latest

    def trimmed(self, keep: int = DAILY_KEEP_DAYS) -> "Config":
        """逐日记录只留最近 keep 天；永久基准先固化，裁不到它。"""
        baseline = self.fold_daily_latest()
        daily = self.daily
        if len(daily) > keep:
            daily = dict(sorted(daily.items())[-keep:])
        return replace(self, daily=daily, daily_latest=baseline)


def config_path() -> Path:
    home = os.environ.get("ORBIT_HOME")
    if home:
        return Path(home).expanduser() / "config.json"
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Orbit" / "config.json"


def load_config(path: Path | None = None) -> Config:
    """读配置。文件缺失、损坏、内容不是对象，都按「未配置」处理。

    损坏时会先试 `.bak`（上一次的完整内容），所以手改坏一个逗号不会连作息一起丢。
    """
    data = load_json(path or config_path())
    return Config() if data is None else Config.from_dict(data)


def save_config(config: Config, path: Path | None = None) -> Path:
    """原子写：先写临时文件再替换，并把上一版留成 `.bak`。"""
    return save_json(path or config_path(), config.trimmed().to_dict())

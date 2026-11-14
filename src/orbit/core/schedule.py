"""作息窗口：由归属日 + 配置解出这一段起床 ~ 睡觉区间。

三件事在这里定死：
1. 模式互斥，没有跨模式优先级——override（临时调整）是模式内的修饰，不是第四种模式。
2. 临时调整只对自己那个归属日有效，跨日界线自动失效（靠比对 day 字段，不靠定时器）。
3. 起床早于日界线时，以「现在落在今天自己的窗口里」为准，纠正归属日。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .clock import (
    day_key,
    format_time,
    line_in_sleep_gap,
    local_naive,
    parse_time,
    suggest_day_line,
)

WEEKEND_WEEKDAYS = (5, 6)  # 周六、周日
SOURCE_OVERRIDE = "override"
SOURCE_FALLBACK = "fallback"
SOURCE_DAILY_BASELINE = "daily:baseline"


@dataclass(frozen=True)
class DayWindow:
    """归属到某个起床日的一段作息区间。

    start 是起床时刻，end 是睡觉时刻；end 可能落在 day 的次日（跨零点）。
    source 说明这段时间是谁给的，用于判断「未完成配置」与调试。
    """

    day: date
    start: datetime
    end: datetime
    source: str

    @property
    def total(self) -> timedelta:
        return self.end - self.start

    @property
    def is_fallback(self) -> bool:
        return self.source == SOURCE_FALLBACK

    def contains(self, moment: datetime) -> bool:
        """左闭右开：正好到睡觉时刻算已结束，属于 over。"""
        return self.start <= moment < self.end


def build_window(day: date, wake: time, sleep: time, source: str) -> DayWindow:
    """由起床日与两个时刻构造区间。

    sleep 不晚于 wake 视为跨零点，end 顺延到次日（wake == sleep 得到 24 小时窗口）。
    """
    start = datetime.combine(day, wake)
    end = datetime.combine(day, sleep)
    if end <= start:
        end += timedelta(days=1)
    return DayWindow(day=day, start=start, end=end, source=source)


FALLBACK_WAKE = time(0, 0)
FALLBACK_SLEEP = time(0, 0)


def fallback_window(day: date) -> DayWindow:
    """配置未完成时的兜底：00:00 → 次日 00:00，整整一个自然日。"""
    return build_window(day, FALLBACK_WAKE, FALLBACK_SLEEP, source=SOURCE_FALLBACK)


def _window_from(day: date, schedule, source: str) -> DayWindow | None:
    """一组时间齐全且可解析才建得出窗口；否则 None，交给下一层。"""
    if schedule is None or not getattr(schedule, "complete", False):
        return None
    try:
        wake = parse_time(schedule.wake)
        sleep = parse_time(schedule.sleep)
    except (ValueError, TypeError):
        return None
    return build_window(day, wake, sleep, source)


def latest_daily(daily: dict, day: date) -> tuple[str, object] | None:
    """历史里不晚于 day 的最近一条完整记录。

    不按「往前 30 天」数格子——记录被裁过、日期有空洞时都会漏。直接取
    `key <= day` 里最大的那条，语义就是「上一次填的作息」。
    """
    limit = day.isoformat()
    candidates = [
        key
        for key, item in daily.items()
        if key <= limit and getattr(item, "complete", False)
    ]
    if not candidates:
        return None
    newest = max(candidates)
    return newest, daily[newest]


def daily_source(config, day: date) -> tuple[str, object] | None:
    """每日模式的作息从哪来：今天的记录 → 历史最近一条 → 永久基准。"""
    own = config.daily.get(day.isoformat())
    if own is not None and getattr(own, "complete", False):
        return f"daily:{day.isoformat()}", own
    found = latest_daily(config.daily, day)
    if found is not None:
        return f"daily:{found[0]}", found[1]
    baseline = config.daily_latest
    if (
        baseline is not None
        and getattr(baseline, "complete", False)
        and baseline.day <= day.isoformat()
    ):
        return SOURCE_DAILY_BASELINE, baseline
    return None


def window_for_day(config, day: date) -> DayWindow:
    """解出归属日 day 这一天的作息区间（不含「现在」的判断）。"""
    mode = config.mode

    # 临时调整只属于固定 / 周制；每日模式本身就是逐日填，再叠一层没有意义。
    if mode in ("fixed", "weekly"):
        override = config.override
        if override is not None and override.matches(day):
            window = _window_from(day, override, SOURCE_OVERRIDE)
            if window is not None:
                return window

    if mode == "fixed":
        window = _window_from(day, config.fixed, "fixed")
        if window is not None:
            return window
    elif mode == "weekly":
        is_weekend = day.weekday() in WEEKEND_WEEKDAYS
        group = config.weekly.weekend if is_weekend else config.weekly.weekday
        source = "weekly.weekend" if is_weekend else "weekly.weekday"
        window = _window_from(day, group, source)
        if window is not None:
            return window
    elif mode == "daily":
        found = daily_source(config, day)
        if found is not None:
            window = _window_from(day, found[1], found[0])
            if window is not None:
                return window

    return fallback_window(day)


def _day_line(config) -> time:
    try:
        return parse_time(config.day_line)
    except (ValueError, TypeError):
        return parse_time("06:00")


def resolve(config, now: datetime) -> DayWindow:
    """解出 now 这一刻应该显示的作息区间。

    名义归属日由日界线给出，但它会被「已经起床」这条事实纠正：起床 05:00、
    日界线 06:00 时，05:30 名义上属于昨天，实际已经在今天的窗口里了。
    所以两个候选日都算一遍，先看名义日、再看自然日，谁装得下 now 就是谁。
    """
    moment = local_naive(now)
    nominal = day_key(moment, _day_line(config))
    today = moment.date()

    for candidate in (nominal,) if nominal == today else (nominal, today):
        window = window_for_day(config, candidate)
        if window.contains(moment):
            return window

    # 处在两个窗口之间的空档（比如 03:00 还没起床、或早已过了睡觉时间），
    # 按名义归属日返回，进度会落在 before / over 上。
    return window_for_day(config, nominal)


@dataclass(frozen=True)
class DayLineIssue:
    """日界线和某一组作息打架。设置界面拿它提示并给建议值。"""

    source: str
    wake: time
    sleep: time
    line: time
    suggested: time

    def message(self) -> str:
        return (
            f"日界线 {format_time(self.line)} 不在睡觉时段里"
            f"（{format_time(self.sleep)} 睡、{format_time(self.wake)} 起），"
            f"建议改成 {format_time(self.suggested)}"
        )


def inspect_day_line(config) -> DayLineIssue | None:
    """检查日界线是否落在每一组已配置作息的睡觉时段内，返回第一条冲突。

    只检查已填齐的组；配置没填完的组本来就跑兜底，不存在冲突。
    """
    line = _day_line(config)
    groups = [
        ("fixed", config.fixed),
        ("weekly.weekday", config.weekly.weekday),
        ("weekly.weekend", config.weekly.weekend),
        ("daily_latest", config.daily_latest),
    ]
    own = getattr(config, "daily", {})
    if own:
        groups.append(("daily", own[max(own)]))

    for source, schedule in groups:
        if schedule is None or not getattr(schedule, "complete", False):
            continue
        try:
            wake = parse_time(schedule.wake)
            sleep = parse_time(schedule.sleep)
        except (ValueError, TypeError):
            continue
        if not line_in_sleep_gap(wake, sleep, line):
            return DayLineIssue(
                source=source,
                wake=wake,
                sleep=sleep,
                line=line,
                suggested=suggest_day_line(wake, sleep),
            )
    return None

"""时间基元：时刻解析、归属日、日界线校验。

这一层只回答两个问题：现在几点、这个时刻属于哪一天。
不读系统时钟、不碰 UI——`now` 一律由调用方传入，所以能逐条单测。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

MINUTES_PER_DAY = 24 * 60


def local_naive(dt: datetime) -> datetime:
    """统一切成本地朴素时间。带时区的输入先转本地再去掉 tzinfo。"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def parse_time(text: str) -> time:
    """解析 "09:00" / "9:00" / "09:00:30"。"""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"无法解析时间: {text!r}")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    return time(hour, minute, second)


def format_time(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def minutes(value: time) -> int:
    """当天第几分钟，只取时分。"""
    return value.hour * 60 + value.minute


def from_minutes(total: int) -> time:
    total %= MINUTES_PER_DAY
    return time(total // 60, total % 60)


def circular_span(start: time, end: time) -> int:
    """从 start 顺时针走到 end 的分钟数（0..1439）。

    作息窗口一律按这个方向量：睡觉 → 次日起床、起床 → 睡觉，跨零点都成立。
    """
    return (minutes(end) - minutes(start)) % MINUTES_PER_DAY


def day_key(now: datetime, day_line: time) -> date:
    """now 早于日界线时归属前一天。

    日界线默认 06:00：凌晨 03:00 看球，归属日仍是昨天，进度不是 12%。
    这只是名义口径；起床早于日界线的情况由 `schedule.resolve` 里
    「已经落在自己今天的窗口里」那条规则纠正，见 `line_in_sleep_gap`。
    """
    moment = local_naive(now)
    if moment.time() < day_line:
        return moment.date() - timedelta(days=1)
    return moment.date()


def line_in_sleep_gap(wake: time, sleep: time, line: time) -> bool:
    """日界线是否落在「睡着」的那段空档里。

    空档 = 从睡觉时刻顺时针走到起床时刻。日界线必须严格晚于睡觉、且不晚于起床：

        睡觉 ──(日界线只能在这段)──▶ 起床 ──清醒──▶ 睡觉

    落在外面就会误判，两头的例子都是真的：
    - 早于睡觉（09:00 起、01:00 睡、日界线 00:30）→ 凌晨 00:10 还在活动，却被算成前天
    - 晚于起床（05:00 起、日界线 06:00）→ 05:30 已经起床半小时，却被算成昨天

    起床时刻等于睡觉时刻是 24 小时窗口，没有空档，日界线不起作用，返回 True。
    """
    gap = circular_span(sleep, wake)
    if gap == 0:
        return True
    offset = circular_span(sleep, line)
    return 0 < offset <= gap


def suggest_day_line(wake: time, sleep: time) -> time:
    """取睡觉时段的中点，作为日界线的建议值。

    05:00 起、23:00 睡 → 空档 6 小时，建议 02:00。
    """
    gap = circular_span(sleep, wake)
    if gap == 0:
        return sleep
    return from_minutes(minutes(sleep) + gap // 2)

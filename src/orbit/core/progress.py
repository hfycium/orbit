"""进度计算：只做纯函数，不碰 UI，不读时钟。

球上那一圈、面板里的剩余时长、超时提示，全部从这里取数。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .clock import local_naive
from .schedule import DayWindow

STATE_BEFORE = "before"
STATE_RUNNING = "running"
STATE_OVER = "over"
STATE_EMPTY = "empty"


@dataclass(frozen=True)
class Progress:
    ratio: float  # 0..1，直接用于环形弧长
    remaining: timedelta  # 距离睡觉还剩多久；已超时为 0
    over: timedelta  # 超过睡觉多久；未超时为 0
    state: str
    total: timedelta


def compute(window: DayWindow, now: datetime) -> Progress:
    moment = local_naive(now)
    total = window.total

    if total.total_seconds() <= 0:
        return Progress(0.0, timedelta(0), timedelta(0), STATE_EMPTY, total)

    if moment < window.start:
        return Progress(0.0, total, timedelta(0), STATE_BEFORE, total)

    if moment >= window.end:
        return Progress(1.0, timedelta(0), moment - window.end, STATE_OVER, total)

    elapsed = moment - window.start
    return Progress(
        ratio=elapsed / total,
        remaining=window.end - moment,
        over=timedelta(0),
        state=STATE_RUNNING,
        total=total,
    )

"""核心层：纯逻辑，不依赖 Qt、不读系统时钟。

对外只暴露这些名字，上层（UI / 服务）不要越过它去碰内部模块。
"""

from .clock import (
    circular_span,
    day_key,
    format_time,
    from_minutes,
    line_in_sleep_gap,
    local_naive,
    minutes,
    parse_time,
    suggest_day_line,
)
from .interaction import CLICK, CLICK_MAX_MOVE, DRAG, NONE, PointerTracker
from .layout import (
    DEFAULT_GAP,
    MIN_PANEL_HEIGHT,
    PanelPlacement,
    Rect,
    clamp_into_work,
    place_panel,
)
from .progress import (
    STATE_BEFORE,
    STATE_EMPTY,
    STATE_OVER,
    STATE_RUNNING,
    Progress,
    compute,
)
from .schedule import (
    SOURCE_DAILY_BASELINE,
    SOURCE_FALLBACK,
    SOURCE_OVERRIDE,
    DayLineIssue,
    DayWindow,
    build_window,
    daily_source,
    fallback_window,
    inspect_day_line,
    latest_daily,
    resolve,
    window_for_day,
)

__all__ = [
    "CLICK",
    "CLICK_MAX_MOVE",
    "DEFAULT_GAP",
    "DRAG",
    "MIN_PANEL_HEIGHT",
    "NONE",
    "PointerTracker",
    "SOURCE_DAILY_BASELINE",
    "SOURCE_FALLBACK",
    "SOURCE_OVERRIDE",
    "STATE_BEFORE",
    "STATE_EMPTY",
    "STATE_OVER",
    "STATE_RUNNING",
    "DayLineIssue",
    "DayWindow",
    "PanelPlacement",
    "Progress",
    "Rect",
    "build_window",
    "circular_span",
    "clamp_into_work",
    "compute",
    "daily_source",
    "day_key",
    "fallback_window",
    "format_time",
    "from_minutes",
    "inspect_day_line",
    "latest_daily",
    "line_in_sleep_gap",
    "local_naive",
    "minutes",
    "parse_time",
    "place_panel",
    "resolve",
    "suggest_day_line",
    "window_for_day",
]

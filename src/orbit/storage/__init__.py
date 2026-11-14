"""存储层：所有落盘动作都在这里，`ui/` 不碰文件。

一个仓库里最容易长歪的地方是「这个模块顺手存一下」。所有写盘集中在一处，
才能保证每条写都走原子替换，也才能回答「删掉哪个文件会丢什么」。
"""

from .config import (
    DAILY_KEEP_DAYS,
    DEFAULT_DAY_LINE,
    MODES,
    Config,
    DatedSchedule,
    Schedule,
    Weekly,
    config_path,
    load_config,
    save_config,
)
from .window_state import WindowState, load_state, save_state, state_path

__all__ = [
    "DAILY_KEEP_DAYS",
    "DEFAULT_DAY_LINE",
    "MODES",
    "Config",
    "DatedSchedule",
    "Schedule",
    "Weekly",
    "WindowState",
    "config_path",
    "load_config",
    "load_state",
    "save_config",
    "save_state",
    "state_path",
]

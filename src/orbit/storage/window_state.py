"""球的位置：单独一个文件，和作息配置分开。

分开的理由不是洁癖——作息是用户手填、可能被手改的东西，位置是程序自己写的。
两者混在一个文件里，一次位置写入就会把用户手改的注释和缩进重排掉，还多一次
「配置写坏了导致位置丢失」的耦合。

坐标允许为负：副屏在主屏左侧时 x 就是负数，不能拿 `> 0` 当校验。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .jsonio import load_json, save_json


@dataclass(frozen=True)
class WindowState:
    x: int | None = None
    y: int | None = None

    @property
    def known(self) -> bool:
        return self.x is not None and self.y is not None

    def as_point(self) -> tuple[int, int] | None:
        if self.x is None or self.y is None:
            return None
        return self.x, self.y

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


def state_path() -> Path:
    home = os.environ.get("ORBIT_HOME")
    if home:
        return Path(home).expanduser() / "window.json"
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Orbit" / "window.json"


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def load_state(path: Path | None = None) -> WindowState:
    data = load_json(path or state_path())
    if data is None:
        return WindowState()
    return WindowState(x=_as_int(data.get("x")), y=_as_int(data.get("y")))


def save_state(state: WindowState, path: Path | None = None) -> Path:
    return save_json(path or state_path(), state.to_dict())

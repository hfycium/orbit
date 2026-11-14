"""按下 → 移动 → 松开，判断这一次算「点击」还是「拖拽」。

为什么要单独一层：这个判断错了，用户会觉得「球点不开」，而且很难复现——
毕竟全看手抖不抖。放进纯函数里，边界就能逐条测。

判据用**累计位移**（离按下点的最远曼哈顿距离），不是路径长度：
按下后左右各晃 3px，路径累计 6px 但人根本没想拖，按路径算会误判成拖拽。
曼哈顿距离（|dx|+|dy|）与现成实现一致，也符合规格里的「4 px」。

**不加时间阈值。** 按住 0.4 秒再松手是「一个慢一点的点击」，不是拖拽——
desktop_calendar 加了 `耗时 < 0.25s` 的条件，结果慢点就点不开，这个坑不抄。
"""

from __future__ import annotations

CLICK_MAX_MOVE = 4

CLICK = "click"
DRAG = "drag"
NONE = "none"


class PointerTracker:
    """一次按下的生命周期。同一时刻只跟踪一个指针。"""

    def __init__(self, threshold: int = CLICK_MAX_MOVE) -> None:
        self.threshold = threshold
        self._origin: tuple[float, float] | None = None
        self._farthest = 0.0

    @property
    def active(self) -> bool:
        return self._origin is not None

    @property
    def farthest(self) -> float:
        return self._farthest

    @property
    def dragging(self) -> bool:
        return self._origin is not None and self._farthest >= self.threshold

    def press(self, x: float, y: float) -> None:
        self._origin = (x, y)
        self._farthest = 0.0

    def move(self, x: float, y: float) -> bool:
        """返回「现在算不算拖拽」。没按下时移动一律不算。"""
        if self._origin is None:
            return False
        ox, oy = self._origin
        distance = abs(x - ox) + abs(y - oy)
        if distance > self._farthest:
            self._farthest = distance
        return self.dragging

    def release(self, x: float, y: float) -> str:
        """返回 CLICK / DRAG / NONE，并重置。"""
        if self._origin is None:
            return NONE
        self.move(x, y)
        verdict = DRAG if self.dragging else CLICK
        self.cancel()
        return verdict

    def cancel(self) -> None:
        self._origin = None
        self._farthest = 0.0

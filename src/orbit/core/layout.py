"""面板落位：纯几何，不依赖 Qt。

M2 的展开动画要按屏幕位置决定方向与高度，这部分算错了只会看到「面板出界」
或「莫名其妙被压扁」，很难反推。所以把它拎出来单独算、单独测。

坐标约定：全部用「左上角 + 宽高」，右/下边界为 `x + w` / `y + h`（不含）。
不使用 QRect.bottom()（它含端点、减一），避免 1px 级别的错位混进来。
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_GAP = 8.0
MIN_PANEL_HEIGHT = 64.0


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def center_x(self) -> float:
        return self.x + self.w / 2

    @property
    def center_y(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True)
class PanelPlacement:
    x: float
    y: float
    w: float
    h: float
    down: bool
    room: float  # 该侧可用高度：从球的外缘量到工作区边（去掉 gap）
    gap: float = DEFAULT_GAP

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.w, self.h)

    @property
    def near_y(self) -> float:
        """进度线所在的边，也就是球原来那一侧。"""
        return self.y if self.down else self.y + self.h

    @property
    def far_y(self) -> float:
        return self.y + self.h if self.down else self.y

    @property
    def degenerate(self) -> bool:
        """球贴在极边位置时可能一点空间都没有，此时不该展开。"""
        return self.h <= 0 or self.w <= 0

    def height_limited(self, want_h: float) -> bool:
        """高度被空间压缩过（面板内需要滚动）。"""
        return self.h + 0.5 < want_h


def place_panel(
    work: Rect,
    cx: float,
    cy: float,
    radius: float,
    want_w: float,
    want_h: float,
    gap: float = DEFAULT_GAP,
) -> PanelPlacement:
    """算出面板矩形。

    方向只看球在哪半屏：上半屏向下、下半屏向上，**不换边**。面板就是球摊开
    成的，换边会让球落在面板中间而不是端头，方向感就断了。

    高度从球的**外缘**量起：向下展开时面板顶边 = 球顶（cy - r），所以可用
    高度是「工作区底 − gap − 球顶」，而不是从球底算——后者会白丢一个直径，
    表现为面板莫名被压扁。
    """
    down = cy <= work.center_y

    anchor = (cy - radius) if down else (cy + radius)
    room = (work.bottom - gap - anchor) if down else (anchor - (work.y + gap))
    room = max(room, 0.0)

    w = max(min(want_w, work.w - 2 * gap), 0.0)
    h = max(min(want_h, room), 0.0)

    low_x = work.x + gap
    high_x = max(work.right - gap - w, low_x)
    x = min(max(cx - w / 2, low_x), high_x)

    y = anchor if down else anchor - h
    # 球被拖到工作区之外（多显示器交界、改分辨率后位置越界）时兜底钳回，
    # 此时近端不再对着球，但总比面板半个身子在屏幕外好。
    y = min(max(y, work.y), max(work.bottom - h, work.y))
    return PanelPlacement(x=x, y=y, w=w, h=h, down=down, room=room, gap=gap)


def clamp_into_work(
    x: float, y: float, w: float, h: float, work: Rect, margin: float = 0.0
) -> tuple[int, int]:
    """把窗口左上角钳进工作区，保证整窗可见。

    用于「重启后恢复位置」：上次的坐标可能来自一块已经拔掉的副屏、
    或者分辨率变小了，直接用会把球丢到屏幕外，用户以为程序没启动。
    窗口比工作区还大时贴左上角，不做无意义的负数推送。
    """
    left = work.x + margin
    top = work.y + margin
    right = work.right - margin - w
    bottom = work.bottom - margin - h
    return (
        int(round(min(max(x, left), max(right, left)))),
        int(round(min(max(y, top), max(bottom, top)))),
    )

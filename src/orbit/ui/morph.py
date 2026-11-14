"""球的形变几何：闭合环 → 摊平的横条 → 面板。

纯函数：给定 t ∈ [0,1] 返回一组点，不 import Qt、不读时钟、不改状态。
这一层是 M2 的全部风险，所以先单独做出来验证，不接面板内容和存储。

三条几何约定（对应规格里最容易做错的地方）：

1. **展开起点固定在 u=0，也就是环的 12 点方向（进度起点）**，不是剪口。
   于是 u 就是时间轴：u=0 是起床，u=比例 是此刻，u=1 是睡觉。
   剪口只是 u=比例 处的一段「不画」的缺口。
   这样摊平出来天然是「已过在左、未过在右」，不需要在动画中途重排颜色。

2. **「圆变线」不是缩放，是按弧长弯折。** 每个 u 对应的材料点始终在曲线的同一
   个弧长位置上，曲率从 1/r 连续降到 0，所以颜色在形变全程连续，不会中途跳色。

3. **厚度只在企直之后才长。** 弯折阶段厚度恒为环宽，撑开阶段才从环宽长到面板高，
   长向远离球的那一侧——面板的近端那条线就是进度线，长度由它守住。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.layout import Rect

TAU = math.tau


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


@dataclass(frozen=True)
class StripSpec:
    """一次形变需要的全部参数。"""

    cx: float
    cy: float
    radius: float
    panel: Rect
    down: bool = True
    ratio: float = 0.6
    ring_width: float = 4.0
    inset: float = 2.0
    gap_deg: float = 9.0
    t_gap: float = 0.20
    t_bend: float = 0.55
    samples: int = 160

    @property
    def neutral_radius(self) -> float:
        """环的中线半径。环宽 4、向内缩 2，中线再让半个环宽。"""
        return max(self.radius - self.inset - self.ring_width / 2, 1.0)

    @property
    def length(self) -> float:
        """环的中线周长，也是摊平后条带的长度（未经拉伸）。"""
        return TAU * self.neutral_radius

    @property
    def near_dir(self) -> float:
        """从近端（进度线）指向远端的方向：向下展开 +1，向上展开 -1。"""
        return 1.0 if self.down else -1.0

    @property
    def near_y(self) -> float:
        """面板近端那条线该在的位置（环宽的中心线）。"""
        if self.down:
            return self.panel.y + self.ring_width / 2
        return self.panel.y + self.panel.h - self.ring_width / 2


def gap_phase(t: float, spec: StripSpec) -> float:
    """0→1：剪口张开。"""
    return _clamp01(t / spec.t_gap) if spec.t_gap > 0 else 1.0


def bend_phase(t: float, spec: StripSpec) -> float:
    """0→1：环被拉直。"""
    span = max(spec.t_bend - spec.t_gap, 1e-6)
    return _clamp01((t - spec.t_gap) / span)


def grow_phase(t: float, spec: StripSpec) -> float:
    """0→1：横条撑成面板。"""
    span = max(1.0 - spec.t_bend, 1e-6)
    return _clamp01((t - spec.t_bend) / span)


def near_point(u: float, t: float, spec: StripSpec) -> tuple[float, float]:
    """时间轴位置 u 处的进度线点，屏幕坐标。

    u=0 是起床（环的 12 点），u=1 是睡觉（回到 12 点前一点）。
    """
    bend = bend_phase(t, spec)
    curvature = (1.0 - bend) / spec.neutral_radius
    d = u * spec.length

    if curvature > 1e-9:
        x = math.sin(curvature * d) / curvature
        y = (1.0 - math.cos(curvature * d)) / curvature
    else:
        x, y = d, 0.0

    if spec.down:
        sx, sy = spec.cx + x, spec.cy - spec.neutral_radius + y
    else:
        # 向上展开 = 整个形变关于球心水平轴镜像：近端变成球的底边，进度方向不变
        sx, sy = spec.cx + x, spec.cy + spec.neutral_radius - y

    grow = grow_phase(t, spec)
    if grow > 0.0:
        tx = spec.panel.x + u * spec.panel.w
        sx += (tx - sx) * grow
        sy += (spec.near_y - sy) * grow
    return sx, sy


@dataclass(frozen=True)
class MorphFrame:
    """某一时刻的绘制数据。全部是屏幕坐标，绘制层只管画。"""

    t: float
    red: tuple[tuple[float, float], ...]
    track: tuple[tuple[float, float], ...]
    body: tuple[tuple[float, float], ...]
    body_rect: Rect
    thickness: float
    corner: float
    grow: float
    bend: float
    straight: bool
    ball_alpha: float


def frame_at(t: float, spec: StripSpec) -> MorphFrame:
    t = _clamp01(t)
    grow = grow_phase(t, spec)
    bend = bend_phase(t, spec)

    # 剪口：只有一个，开在条带的两端（也就是 u=0 / u=1 那条接缝）。
    # 为什么不在 u=比例 处开：条带要成为一条「左→右 = 早→晚」的时间轴，
    # 它的左端就必须是 u=0；而闭合的环摊平后，u=0 和 u=1 本来就是同一个点，
    # 所以环只可能在这个接缝上裂开。在 u=比例 处再开一个口会变成两个断口。
    gap = math.radians(spec.gap_deg) * gap_phase(t, spec) * (1.0 - grow)
    half_gap = gap / TAU / 2.0

    p = _clamp01(spec.ratio)
    red = _polyline(min(half_gap, p), p, t, spec)
    track = _polyline(p, max(1.0 - half_gap, p), t, spec)

    thickness = spec.ring_width + (spec.panel.h - spec.ring_width) * grow
    corner = 2.0 + 10.0 * grow
    straight = bend >= 1.0 - 1e-9

    # 直立之后面板体的矩形：长度从环周长长到面板宽，高度从环宽长到面板高，
    # 近端那条边始终钉在 near_y 上。所以它是「从一根线长成一张卡」，
    # 不是「线画完之后凭空出现一张卡」。
    length = spec.length + (spec.panel.w - spec.length) * grow
    left = spec.cx + (spec.panel.x - spec.cx) * grow
    top = spec.near_y - spec.ring_width / 2 if spec.down else spec.near_y + spec.ring_width / 2 - thickness
    body_rect = Rect(left, top, length, thickness)

    body = () if straight else _body_polygon(t, spec, thickness)
    return MorphFrame(
        t=t,
        red=red,
        track=track,
        body=body,
        body_rect=body_rect,
        thickness=thickness,
        corner=corner,
        grow=grow,
        bend=bend,
        straight=straight,
        ball_alpha=1.0 - bend,
    )


def _polyline(u0: float, u1: float, t: float, spec: StripSpec) -> tuple[tuple[float, float], ...]:
    if u1 <= u0:
        return ()
    count = max(int(spec.samples * (u1 - u0)) + 2, 3)
    return tuple(near_point(u0 + (u1 - u0) * i / (count - 1), t, spec) for i in range(count))


def _body_polygon(t: float, spec: StripSpec, thickness: float) -> tuple[tuple[float, float], ...]:
    """弯折阶段的带体轮廓。沿法线偏移，所以贴着圆时是真正的圆环带。"""
    count = spec.samples
    points = [near_point(i / (count - 1), t, spec) for i in range(count)]
    far_sign = spec.near_dir

    outer: list[tuple[float, float]] = []
    inner: list[tuple[float, float]] = []
    for i, (x, y) in enumerate(points):
        if i == 0:
            nx, ny = points[1][0] - x, points[1][1] - y
        elif i == count - 1:
            nx, ny = x - points[-2][0], y - points[-2][1]
        else:
            nx, ny = points[i + 1][0] - points[i - 1][0], points[i + 1][1] - points[i - 1][1]
        norm = math.hypot(nx, ny) or 1.0
        # 法线取 (-ty, tx)：顺时针描圆时它指向圆心，对向下展开就是「向远端」
        fx = (-ny / norm) * far_sign
        fy = (nx / norm) * far_sign
        outer.append((x - fx * spec.ring_width / 2, y - fy * spec.ring_width / 2))
        inner.append((x + fx * (thickness - spec.ring_width / 2), y + fy * (thickness - spec.ring_width / 2)))
    return tuple(outer) + tuple(reversed(inner))


def end_anchors(spec: StripSpec) -> tuple[tuple[float, float], tuple[float, float]]:
    """条带两端在完全摊平后应落在哪里，供测试与调试使用。"""
    return (
        (spec.panel.x, spec.near_y),
        (spec.panel.x + spec.panel.w, spec.near_y),
    )


def motion_bounds(spec: StripSpec, steps: int = 24) -> tuple[float, float, float, float]:
    """整个形变过程扫过的范围（左, 上, 右, 下）。

    窗口必须比「球 ∪ 面板」更大：环摊平的中途会甩到两者之外，按两者取并集
    会把弧线裁掉。但窗口又不能一直这么大——透明区域照样吃鼠标点击，
    所以动画结束后要收回到面板本身。
    """
    xs: list[float] = []
    ys: list[float] = []
    for i in range(steps + 1):
        t = i / steps
        for j in range(25):
            x, y = near_point(j / 24, t, spec)
            xs.append(x)
            ys.append(y)
    pad = spec.ring_width + 4
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

"""形变几何的关键不变量。

这些断言就是「展开动画对不对」的形式化版本：环在 t=0 必须真的闭合在球上、
t=1 必须真的是一条贴着面板近端的直线、颜色在全程不跳、路径没有突跳。
"""

from __future__ import annotations

import math

import pytest

from orbit.core.layout import Rect, place_panel
from orbit.ui.morph import (
    StripSpec,
    bend_phase,
    frame_at,
    grow_phase,
    near_point,
)

R = 28.0
WORK = Rect(0, 0, 1920, 1040)
PANEL = place_panel(WORK, 960, 300, R, 320, 96).rect


def spec(down=True, ratio=0.25, panel=PANEL, cx=960, cy=300):
    return StripSpec(cx=cx, cy=cy, radius=R, panel=panel, down=down, ratio=ratio)


# --- 阶段 -----------------------------------------------------------------


def test_phases_cover_the_unit_interval_in_order():
    s = spec()
    assert (bend_phase(0, s), grow_phase(0, s)) == (0.0, 0.0)
    assert bend_phase(0.2, s) == pytest.approx(0.0)
    assert bend_phase(0.55, s) == pytest.approx(1.0)
    assert grow_phase(0.55, s) == pytest.approx(0.0)
    assert grow_phase(1.0, s) == pytest.approx(1.0)


# --- t=0：必须就是那个球 --------------------------------------------------


def test_at_rest_the_strip_is_the_ring():
    s = spec()
    for i in range(50):
        x, y = near_point(i / 49, 0.0, s)
        assert math.hypot(x - s.cx, y - s.cy) == pytest.approx(s.neutral_radius, abs=0.4)


def test_at_rest_the_ring_is_closed():
    s = spec()
    head = near_point(0.0, 0.0, s)
    tail = near_point(1.0, 0.0, s)
    assert math.dist(head, tail) < 1.0


def test_at_rest_red_starts_at_twelve_oclock():
    s = spec(ratio=0.25)
    x, y = near_point(0.0, 0.0, s)
    assert x == pytest.approx(s.cx, abs=0.5)
    assert y < s.cy  # 12 点方向在球心上方


def test_red_covers_exactly_the_ratio_at_rest():
    """25% 的进度对应环上 90°，也就是 3 点方向。"""
    s = spec(ratio=0.25)
    x, y = near_point(0.25, 0.0, s)
    assert x == pytest.approx(s.cx + s.neutral_radius, abs=0.6)
    assert y == pytest.approx(s.cy, abs=0.6)


# --- t=1：必须就是那条进度条 ----------------------------------------------


def test_fully_open_strip_is_a_straight_line_on_the_near_edge():
    s = spec()
    ys = [near_point(i / 40, 1.0, s)[1] for i in range(41)]
    assert max(ys) - min(ys) < 0.5
    assert abs(ys[0] - s.near_y) < 0.5


def test_fully_open_strip_spans_the_panel_width():
    s = spec()
    left = near_point(0.0, 1.0, s)
    right = near_point(1.0, 1.0, s)
    assert left[0] == pytest.approx(s.panel.x, abs=0.5)
    assert right[0] == pytest.approx(s.panel.x + s.panel.w, abs=0.5)


def test_colour_order_is_elapsed_then_remaining():
    """这就是「剪口剪错位置」那件事的验收：摊平后已过必须在左。"""
    s = spec(ratio=0.25)
    frame = frame_at(1.0, s)
    assert frame.red[0][0] == pytest.approx(s.panel.x, abs=0.5)
    assert frame.track[-1][0] == pytest.approx(s.panel.x + s.panel.w, abs=0.5)
    # 已过 / 未过的交界落在面板宽度的 25% 处
    boundary = frame.red[-1][0]
    assert boundary == pytest.approx(s.panel.x + 0.25 * s.panel.w, abs=1.0)


def test_once_straight_red_stays_left_of_track():
    """摊平之后已过段必须在左、未过段在右，任何一帧都不能反过来。

    弯折阶段不能用 x 判断：环上的 x 不随 u 单调（过了 3 点就往回走），
    两段在屏幕上左右互换是正常的，那不是错。
    """
    s = spec(ratio=0.4)
    for step in range(11, 21):
        frame = frame_at(step / 20, s)
        assert frame.red and frame.track
        assert frame.red[0][0] <= frame.track[-1][0]
        assert frame.red[-1][0] <= frame.track[0][0] + 0.01


# --- 方向 -----------------------------------------------------------------


def test_upward_expansion_mirrors_to_the_ball_bottom():
    panel = place_panel(WORK, 960, 900, R, 320, 96).rect
    s = spec(down=False, panel=panel, cy=900)
    assert panel.y + panel.h == pytest.approx(900 + R)
    assert near_point(0.5, 1.0, s)[1] == pytest.approx(s.near_y, abs=0.5)
    assert s.near_y == pytest.approx(panel.y + panel.h - s.ring_width / 2)


def test_upward_expansion_ring_sits_on_the_ball():
    panel = place_panel(WORK, 960, 900, R, 320, 96).rect
    s = spec(down=False, panel=panel, cy=900)
    for i in range(30):
        x, y = near_point(i / 29, 0.0, s)
        assert math.hypot(x - s.cx, y - s.cy) == pytest.approx(s.neutral_radius, abs=0.6)


# --- 连续性 ---------------------------------------------------------------


def _peak_step(step_count: int) -> float:
    s = spec(ratio=0.25)
    samples = 60
    previous = [near_point(i / (samples - 1), 0.0, s) for i in range(samples)]
    peak = 0.0
    for step in range(1, step_count + 1):
        t = step / step_count
        current = [near_point(i / (samples - 1), t, s) for i in range(samples)]
        peak = max(peak, max(math.dist(a, b) for a, b in zip(previous, current)))
        previous = current
    return peak


def test_motion_is_continuous_not_jumpy():
    """步长减半、峰值位移也该跟着减半 —— 有突跳时它不会变小。

    环摊平本来就是一端甩出去，速度峰值出现在拉直的最后（t≈0.55），
    这是几何必然，不是 bug；要证明的是它连续、没有跳变。
    """
    coarse = _peak_step(100)
    fine = _peak_step(200)
    assert coarse < 20.0
    assert fine < coarse * 0.6


def test_thickness_only_grows_after_the_band_is_straight():
    s = spec()
    for step in range(0, 11):
        t = step / 20  # 0 .. 0.55
        frame = frame_at(t, s)
        assert frame.thickness == pytest.approx(s.ring_width)
    assert frame_at(0.55, s).straight is True
    assert frame_at(1.0, s).thickness == pytest.approx(s.panel.h)


def test_gap_closes_at_the_end_so_the_bar_has_no_notch():
    s = spec(ratio=0.25)
    frame = frame_at(1.0, s)
    assert frame.red[-1][0] == pytest.approx(frame.track[0][0], abs=0.6)


def test_ball_face_fades_out_before_the_panel_opens():
    s = spec()
    assert frame_at(0.0, s).ball_alpha == pytest.approx(1.0)
    assert frame_at(0.55, s).ball_alpha == pytest.approx(0.0)


def test_body_polygon_encloses_the_near_edge():
    s = spec()
    frame = frame_at(0.4, s)
    assert frame.straight is False
    assert len(frame.body) > 100
    ys = [p[1] for p in frame.body]
    near_ys = [p[1] for p in frame.red + frame.track]
    assert max(ys) >= max(near_ys) - s.ring_width

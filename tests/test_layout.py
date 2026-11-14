"""面板落位：方向、可用高度、水平钳制。

数字都是「左上角 + 宽高」的浮点，右/下边界不含端点。四个角和屏幕中线的
位置都要覆盖——这一层算错，表现是面板出界或莫名被压扁，很难反推。
"""

from __future__ import annotations

import pytest

from orbit.core.layout import DEFAULT_GAP, Rect, place_panel

WORK = Rect(0, 0, 1920, 1040)
R = 28.0
WANT_W = 320.0
WANT_H = 96.0


def place(cx, cy, work=WORK, want_w=WANT_W, want_h=WANT_H):
    return place_panel(work, cx, cy, R, want_w, want_h)


def assert_inside(panel, work=WORK, gap=DEFAULT_GAP):
    assert panel.x >= work.x + gap - 0.01
    assert panel.y >= work.y - 0.01
    assert panel.x + panel.w <= work.right - gap + 0.01
    assert panel.y + panel.h <= work.bottom + 0.01
    assert panel.h > 0 and panel.w > 0


# --- 方向 -----------------------------------------------------------------


@pytest.mark.parametrize(
    "cx,cy",
    [
        (28, 28),  # 左上
        (960, 100),  # 上中
        (1892, 28),  # 右上
    ],
)
def test_upper_half_expands_downward(cx, cy):
    panel = place(cx, cy)
    assert panel.down is True
    assert panel.near_y == pytest.approx(cy - R)  # 近端 = 球顶
    assert_inside(panel)


@pytest.mark.parametrize(
    "cx,cy",
    [
        (28, 1012),  # 左下
        (960, 940),  # 下中
        (1892, 1012),  # 右下
    ],
)
def test_lower_half_expands_upward(cx, cy):
    panel = place(cx, cy)
    assert panel.down is False
    assert panel.near_y == pytest.approx(cy + R)  # 近端 = 球底
    assert_inside(panel)


def test_exact_center_expands_downward():
    assert place(960, WORK.center_y).down is True


# --- 水平钳制 -------------------------------------------------------------


def test_left_edge_shifts_right_without_overflow():
    panel = place(28, 100)
    assert panel.x == pytest.approx(DEFAULT_GAP)


def test_right_edge_shifts_left_without_overflow():
    panel = place(1892, 100)
    assert panel.x + panel.w == pytest.approx(WORK.right - DEFAULT_GAP)


def test_centered_when_there_is_room():
    panel = place(960, 100)
    assert panel.x == pytest.approx(960 - WANT_W / 2)


# --- 可用高度（这次修正的地方）-------------------------------------------


def test_room_measured_from_ball_edge_not_ball_bottom():
    """向下展开时面板顶边 = 球顶，可用高度要把球整个算进去。"""
    panel = place(960, 100)
    assert panel.room == pytest.approx(WORK.bottom - DEFAULT_GAP - (100 - R))
    assert panel.h == pytest.approx(WANT_H)


def test_room_under_ball_leaves_no_gap_waste():
    """球贴屏幕底部时向上展开，可用高度到球底为止，不该再扣一个直径。"""
    panel = place(960, 980)
    assert panel.room == pytest.approx((980 + R) - (WORK.y + DEFAULT_GAP))
    assert panel.h == pytest.approx(WANT_H)


def test_short_space_compresses_instead_of_flipping():
    """空间不够时压高度、不换边——换边会让球落在面板中间。"""
    work = Rect(0, 0, 1920, 120)
    panel = place(960, 70, work=work)
    assert panel.down is False
    assert panel.h == pytest.approx(90)
    assert panel.h < WANT_H
    assert panel.height_limited(WANT_H) is True
    assert_inside(panel, work)


def test_narrow_screen_shrinks_width():
    work = Rect(0, 0, 300, 800)
    panel = place(150, 100, work=work)
    assert panel.w == pytest.approx(300 - 2 * DEFAULT_GAP)
    assert_inside(panel, work)


def test_secondary_monitor_with_offset_is_respected():
    """多显示器：工作区原点不是 (0,0) 也要贴着算。"""
    work = Rect(-1920, 120, 1920, 960)
    panel = place(-1920 + 28, 200, work=work)
    assert panel.x == pytest.approx(work.x + DEFAULT_GAP)
    assert panel.y == pytest.approx(200 - R)
    assert_inside(panel, work)


def test_ball_dragged_outside_work_area_still_keeps_panel_inside():
    work = Rect(0, 0, 400, 100)
    panel = place(200, 90, work=work)
    assert panel.y + panel.h <= work.bottom + 0.01
    assert panel.h > 0

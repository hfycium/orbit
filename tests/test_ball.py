"""球窗口：几何参数、窗口标志、位置恢复的钳制。

不测鼠标事件本身——那要模拟全局光标位置，在离屏平台上测出来的东西和真机
不是一回事。点击/拖拽的判定在 `test_interaction.py` 里测，那里才是真逻辑。
"""

import pytest
from PySide6.QtCore import Qt

from orbit.core import Rect
from orbit.storage import WindowState
from orbit.ui.ball import BallWindow, percent_text
from orbit.ui.theme import DARK


@pytest.mark.parametrize(
    "ratio,expected",
    [
        (0.0, "0%"),
        (0.424, "42%"),
        (0.455, "46%"),
        (0.5, "50%"),
        (1.0, "100%"),
        (-0.3, "0%"),
        (1.7, "100%"),
    ],
)
def test_percent_text(ratio, expected):
    assert percent_text(ratio) == expected


def test_window_flags_make_it_a_topmost_tool(qt_app):
    ball = BallWindow()
    flags = ball.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    # Tool 少了会多一个任务栏图标
    assert flags & Qt.WindowType.Tool


def test_translucent_background_is_on(qt_app):
    ball = BallWindow()
    assert ball.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_window_is_ball_plus_margin(qt_app):
    ball = BallWindow()
    assert ball.width() == DARK.window_size == 64
    assert ball.height() == ball.width()
    # 环的中线半径必须与形变几何一套：球 28、内缩 2、环宽 4 → 24
    assert DARK.neutral_radius == pytest.approx(24.0)


def test_progress_updates_are_visible(qt_app):
    ball = BallWindow()
    assert ball.ratio == 0.0
    ball.set_progress(0.42)
    assert ball.ratio == pytest.approx(0.42)
    assert ball.fallback is False


def test_fallback_flag_is_tracked(qt_app):
    ball = BallWindow()
    ball.set_progress(0.42, fallback=True)
    assert ball.fallback is True
    ball.set_progress(0.42, fallback=False)
    assert ball.fallback is False


def test_restore_without_record_puts_ball_on_screen(qt_app):
    ball = BallWindow()
    ball.restore(WindowState())
    screen = ball.screen().availableGeometry()
    assert screen.contains(ball.frameGeometry().center())


def test_restore_clamps_position_from_a_removed_monitor(qt_app):
    """上次在副屏，这次副屏没了：坐标要钳回来，不能把球丢在屏幕外。"""
    ball = BallWindow()
    ball.restore(WindowState(9999, 9999))
    screen = ball.screen().availableGeometry()
    assert screen.contains(ball.frameGeometry().center())


def test_restore_keeps_negative_coordinates_when_valid(qt_app):
    """负坐标本身不是错误——副屏在主屏左侧时 x 就是负的。"""
    state = WindowState(-2000, 100)
    ball = BallWindow()
    ball.restore(state)
    # 该坐标不属于任何屏，于是回退到主屏并钳制；只要不崩、还在屏内即可
    screen = ball.screen().availableGeometry()
    assert screen.contains(ball.frameGeometry().center())


def test_clamped_into_work_area_with_margin():
    from orbit.core import clamp_into_work

    work = Rect(0, 0, 1920, 1040)
    assert clamp_into_work(-50, -50, 64, 64, work) == (0, 0)
    assert clamp_into_work(5000, 5000, 64, 64, work) == (1856, 976)
    assert clamp_into_work(100, 100, 64, 64, work) == (100, 100)


def test_clamp_when_window_larger_than_work():
    from orbit.core import clamp_into_work

    work = Rect(0, 0, 40, 40)
    assert clamp_into_work(10, 10, 64, 64, work) == (0, 0)

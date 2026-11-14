"""点击与拖拽的判定。这一层错了，症状是「球点不开」，且极难复现。"""

from orbit.core import CLICK, CLICK_MAX_MOVE, DRAG, NONE, PointerTracker


def test_still_press_is_a_click():
    t = PointerTracker()
    t.press(100, 100)
    assert t.release(100, 100) == CLICK


def test_small_shake_is_still_a_click():
    t = PointerTracker()
    t.press(100, 100)
    t.move(101, 100)
    t.move(99, 101)
    assert t.release(100, 100) == CLICK


def test_jitter_back_and_forth_is_not_a_drag():
    """左右各晃 3px：路径累计 6px，但离按下点的最远距离只有 3px。"""
    t = PointerTracker()
    t.press(100, 100)
    for x in (103, 97, 103, 97):
        t.move(x, 100)
    assert t.release(100, 100) == CLICK


def test_exactly_four_pixels_is_a_drag():
    """规格是「位移 < 4 才算点击」，所以 4 本身已经是拖拽。"""
    t = PointerTracker()
    t.press(100, 100)
    assert t.move(104, 100) is True
    assert t.release(104, 100) == DRAG


def test_one_pixel_short_of_threshold_is_a_click():
    t = PointerTracker()
    t.press(100, 100)
    assert t.move(103, 100) is False
    assert t.release(103, 100) == CLICK


def test_manhattan_means_diagonal_counts_both_axes():
    """走对角线 3+3：欧氏距离只有 4.2，但曼哈顿是 6，算拖拽。

    这是有意的：与现成实现一致，且「斜着甩 3px」在手上确实已经是移动了。
    """
    t = PointerTracker()
    t.press(100, 100)
    assert t.move(103, 103) is True
    assert t.release(103, 103) == DRAG


def test_release_without_press_is_none():
    t = PointerTracker()
    assert t.release(100, 100) == NONE


def test_move_without_press_is_not_dragging():
    t = PointerTracker()
    assert t.move(500, 500) is False
    assert t.release(500, 500) == NONE


def test_no_time_threshold_deliberate():
    """按住多久都只影响「有没有移」，不影响判定。

    这里没有时间参数可传，就是规格本身：慢一点的点击仍是点击。
    """
    t = PointerTracker()
    t.press(10, 10)
    t.move(10, 11)
    assert t.release(10, 11) == CLICK


def test_tracker_resets_between_gestures():
    t = PointerTracker()
    t.press(0, 0)
    assert t.release(50, 0) == DRAG
    assert t.active is False
    t.press(0, 0)
    assert t.release(0, 0) == CLICK


def test_threshold_is_configurable():
    t = PointerTracker(threshold=10)
    t.press(0, 0)
    assert t.move(9, 0) is False
    assert t.release(9, 0) == CLICK
    assert CLICK_MAX_MOVE == 4

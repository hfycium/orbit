"""总装：引导 → 球 → 托盘这一层的接线是否正确。

不真的 exec() 事件循环，也不弹引导窗：把时间点注入 refresh，直接看推给球的比例。
"""

import pytest

from orbit.app import OrbitApp
from orbit.storage import Config, Schedule, WindowState, load_config, load_state, save_config
from orbit.ui.ball import BallWindow


def _configured() -> Config:
    return Config(mode="fixed", fixed=Schedule("09:00", "23:00"))


def test_refresh_pushes_configured_progress(qt_app, orbit_home):
    save_config(_configured())
    orbit = OrbitApp(qt_app)
    orbit.ball = BallWindow()

    orbit.refresh(_dt(16, 0))
    assert orbit.ball.ratio == pytest.approx(0.5)  # 09:00–23:00 的 16:00
    assert orbit.ball.fallback is False


def test_refresh_before_wake_is_zero(qt_app, orbit_home):
    save_config(_configured())
    orbit = OrbitApp(qt_app)
    orbit.ball = BallWindow()

    orbit.refresh(_dt(7, 0))
    assert orbit.ball.ratio == pytest.approx(0.0)


def test_refresh_after_sleep_is_full(qt_app, orbit_home):
    save_config(_configured())
    orbit = OrbitApp(qt_app)
    orbit.ball = BallWindow()

    orbit.refresh(_dt(23, 30))
    assert orbit.ball.ratio == pytest.approx(1.0)


def test_unconfigured_config_falls_back_and_flags_it(qt_app, orbit_home):
    """没有配置时球要跑兜底并打上标记，不能伪装成正常进度。"""
    save_config(Config())
    orbit = OrbitApp(qt_app)
    orbit.ball = BallWindow()

    orbit.refresh(_dt(12, 0))
    assert orbit.ball.fallback is True
    assert orbit.ball.ratio == pytest.approx(0.5)  # 兜底是 00:00–24:00


def test_refresh_without_ball_is_a_noop(qt_app, orbit_home):
    orbit = OrbitApp(qt_app)
    orbit.refresh(_dt(12, 0))  # 不该抛异常


def test_drag_saves_position(qt_app, orbit_home):
    orbit = OrbitApp(qt_app)
    orbit._on_moved(300, 200)
    assert load_state().as_point() == (300, 200)


def test_start_declines_when_onboarding_cancelled(qt_app, orbit_home, monkeypatch):
    """用户取消引导 → 这次不显示球，下次启动再来。"""
    save_config(Config())
    orbit = OrbitApp(qt_app)

    monkeypatch.setattr(
        "orbit.ui.onboarding.OnboardingDialog.exec", lambda self: 0
    )
    assert orbit.start() is False
    assert orbit.ball is None


def test_start_accepts_onboarding_and_persists(qt_app, orbit_home, monkeypatch):
    save_config(Config())
    orbit = OrbitApp(qt_app)

    def fake_exec(self):
        self._mode_buttons["fixed"].setChecked(True)
        return 1

    monkeypatch.setattr("orbit.ui.onboarding.OnboardingDialog.exec", fake_exec)
    assert orbit.start() is True
    assert orbit.ball is not None
    assert load_config().configured is True

    orbit.ball.hide()
    orbit.ball.deleteLater()


def test_window_state_roundtrip_through_app(qt_app, orbit_home):
    orbit = OrbitApp(qt_app)
    orbit._on_moved(-120, 40)
    assert load_state() == WindowState(-120, 40)


def _dt(hour: int, minute: int):
    from datetime import datetime

    return datetime(2026, 11, 14, hour, minute)  # 周六，用固定模式不受周制影响

"""测试共用的两台「假机器」：一个离屏 Qt、一个临时 ORBIT_HOME。

离屏平台没有数字字形（`62%` 会渲染成豆腐块），但那只影响看，不影响断言——
断言看的是比例数值，不看像素。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

import pytest


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def orbit_home(tmp_path, monkeypatch):
    """把配置与位置都指到临时目录，测试之间互不干扰。"""
    monkeypatch.setenv("ORBIT_HOME", str(tmp_path))
    return tmp_path

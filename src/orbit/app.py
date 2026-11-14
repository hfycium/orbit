"""总装：引导 → 球 → 托盘。

启动顺序是有讲究的：**先引导、后建球**。没有配置的球只会一直跑兜底状态，
那等于没装；先出球再补引导，还会让「引导没做完」这段时间的进度逻辑跑错数据。

托盘是唯一的「确定入口」：球可以拖到任何地方、也可能被别的窗口盖住，
所以退出、重新设置、显示/隐藏都必须能在托盘里找到。
"""

from __future__ import annotations

import sys
from datetime import datetime

from pathlib import Path

from PySide6.QtCore import QLockFile, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .core import compute, resolve
from .storage import Config, WindowState, config_path, load_config, load_state, save_config, save_state
from .ui.ball import BallWindow
from .ui.onboarding import OnboardingDialog
from .ui.theme import DARK

REFRESH_MS = 1000
TRAY_ICON_SIZE = 32
INSTANCE_SERVER_NAME = "orbit-desktop-instance-v1"


class SingleInstance:
    """已有实例时转发唤醒请求，不再创建第二个球。"""

    def __init__(
        self,
        app: QApplication,
        activate,
        name: str = INSTANCE_SERVER_NAME,
        lock_path: Path | None = None,
    ):
        self.name = name
        self.activate = activate
        path = lock_path or config_path().parent / "orbit.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(path))
        self.primary = self.lock.tryLock(0)
        self.server = QLocalServer(app)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept_connection)

        if self.primary:
            if not self.server.listen(name):
                QLocalServer.removeServer(name)
                self.server.listen(name)
            return

        socket = QLocalSocket()
        socket.connectToServer(name)
        if socket.waitForConnected(500):
            socket.write(b"activate")
            socket.waitForBytesWritten(500)

    def _accept_connection(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda client=socket: self._received(client))
            if socket.bytesAvailable():
                self._received(socket)

    def _received(self, socket: QLocalSocket) -> None:
        socket.readAll()
        self.activate()


def _tray_icon() -> QIcon:
    """托盘图标现画，不依赖资源文件——省一条「忘记带 icon 就变空白」的坑。"""
    pixmap = QPixmap(TRAY_ICON_SIZE, TRAY_ICON_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(DARK.accent_mid, 3.0)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = 4.0
    painter.drawEllipse(inset, inset, TRAY_ICON_SIZE - 2 * inset, TRAY_ICON_SIZE - 2 * inset)
    painter.end()
    return QIcon(pixmap)


class OrbitApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.config = Config()
        self.ball: BallWindow | None = None
        self.tray: QSystemTrayIcon | None = None
        self._timer = QTimer()
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)

        self.app.setQuitOnLastWindowClosed(False)
        self.config = load_config()

    # ------------------------------------------------------------------ 启动

    def start(self) -> bool:
        """返回 False 表示用户没走完引导，这次不显示球。"""
        if not self.config.configured and not self._onboard():
            return False

        self.ball = BallWindow(DARK)
        self.ball.activated.connect(self._on_activated)
        self.ball.moved.connect(self._on_moved)
        self.ball.context_requested.connect(self._show_menu)
        self.ball.restore(load_state())
        self.ball.show()
        self.ball.raise_()

        self._install_tray()
        self.refresh()
        self._timer.start()
        return True

    def _onboard(self) -> bool:
        dialog = OnboardingDialog(self.config)
        if not dialog.exec():
            return False
        self.config = dialog.result_config()
        save_config(self.config)
        return True

    def _install_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(_tray_icon(), self.app)
        self.tray.setToolTip("Orbit · 今天还剩多少")
        self.tray.setContextMenu(self._build_menu(None))
        self.tray.show()

    # ------------------------------------------------------------------ 刷新

    def refresh(self, now: datetime | None = None) -> None:
        """算一次进度并推给球。`now` 可注入，方便单测不靠真实时钟。"""
        if self.ball is None:
            return
        moment = now or datetime.now()
        window = resolve(self.config, moment)
        progress = compute(window, moment)
        self.ball.set_progress(progress.ratio, fallback=window.is_fallback)

    def _on_moved(self, x: int, y: int) -> None:
        save_state(WindowState(x, y))

    def _on_activated(self) -> None:
        if self.ball is not None:
            self.ball.toggle_expanded()

    # ------------------------------------------------------------------ 菜单

    def _build_menu(self, parent) -> QMenu:
        menu = QMenu(parent)

        toggle = QAction("显示 / 隐藏", menu)
        toggle.triggered.connect(self._toggle_visible)
        menu.addAction(toggle)

        settings = QAction("重新设置作息…", menu)
        settings.triggered.connect(self._reconfigure)
        menu.addAction(settings)

        menu.addSeparator()
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)
        return menu

    def _show_menu(self, position: QPoint) -> None:
        menu = self._build_menu(self.ball)
        menu.exec(position)

    def _toggle_visible(self) -> None:
        if self.ball is None:
            return
        if self.ball.isVisible():
            self.ball.hide()
        else:
            self.ball.show()

    def _reconfigure(self) -> None:
        if not self._onboard():
            return
        self.refresh()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Orbit")
    app.setApplicationDisplayName("Orbit")

    orbit = OrbitApp(app)

    def activate_existing() -> None:
        target = app.activeModalWidget() or orbit.ball
        if target is None:
            return
        if target is orbit.ball and not target.isVisible():
            target.show()
        target.raise_()
        target.activateWindow()

    instance = SingleInstance(app, activate_existing)
    if not instance.primary:
        return 0
    if not orbit.start():
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""桌面上的那个球：无边框、置顶、不进任务栏、可拖。

M1 只做「能看、能拖、能记住位置」。点击目前只发信号，展开留给 M2——
形变几何已经在 `morph.py` 里验完了，但把它接到真实窗口上要改窗口尺寸与
透明区域的策略，混在一起做会让「球对不对」和「动画对不对」互相掩盖。

两个 Windows 上的硬要求，写在最前面免得以后被“优化”掉：
1. `WA_TranslucentBackground` 必须在 `show()` 之前设，之后再设无效。
2. `Tool` 不能省。少了它任务栏会多一个图标，而这是个不该占任务栏的东西。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QGuiApplication,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ..core import PointerTracker, Rect, clamp_into_work
from ..core.interaction import CLICK, DRAG
from ..storage import WindowState
from .theme import DARK, Theme

DEFAULT_EDGE_MARGIN = 16


def percent_text(ratio: float) -> str:
    """球心只放这一行字，不放中文（44px 的内径塞不下整句）。"""
    clamped = min(max(ratio, 0.0), 1.0)
    return f"{round(clamped * 100)}%"


class BallWindow(QWidget):
    """一个 64×64 的透明窗口，里面画一个 56px 的球和一圈进度环。"""

    activated = Signal()
    moved = Signal(int, int)
    context_requested = Signal(QPoint)

    def __init__(self, theme: Theme = DARK, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self._ratio = 0.0
        self._fallback = False
        self._tracker = PointerTracker()
        self._press_offset = QPointF()

        self.setWindowTitle("Orbit")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(theme.window_size, theme.window_size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    # ------------------------------------------------------------------ 状态

    def set_progress(self, ratio: float, fallback: bool = False) -> None:
        """比例变化才重绘。一秒钟重画 60 次和一分钟重画 1 次，用户看不出区别。"""
        if abs(ratio - self._ratio) < 1e-4 and fallback == self._fallback:
            return
        self._ratio = ratio
        self._fallback = fallback
        self.update()

    @property
    def ratio(self) -> float:
        return self._ratio

    @property
    def fallback(self) -> bool:
        """当前是否在「未设作息」的兜底口径上（球上会画虚线环）。"""
        return self._fallback

    # ------------------------------------------------------------------ 落位

    def _work_area(self, near: QPoint | None = None) -> Rect:
        """`near` 所在那块屏的工作区（已排除任务栏）；查不到就退回窗口所在屏。"""
        screen = QGuiApplication.screenAt(near) if near is not None else None
        if screen is None:
            screen = self.screen() or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        return Rect(geo.x(), geo.y(), geo.width(), geo.height())

    def restore(self, state: WindowState) -> None:
        """按上次的位置放回去；没有记录就放右侧三分之一高处。

        坐标来自哪块屏要多查一步：副屏被拔掉后，旧坐标会把球丢在屏幕外，
        用户只会以为程序没启动。所以用 `screenAt` 反查，查不到就回主屏再钳。
        """
        size = self.width()
        point = state.as_point()
        if point is None:
            work = self._work_area()
            self.move(
                int(work.right - size - DEFAULT_EDGE_MARGIN),
                int(work.y + work.h / 3),
            )
            return
        x, y = point
        work = self._work_area(QPoint(x + size // 2, y + size // 2))
        self.move(*clamp_into_work(x, y, size, size, work))

    def position(self) -> tuple[int, int]:
        return self.x(), self.y()

    # ------------------------------------------------------------------ 交互

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.globalPosition()
        self._tracker.press(point.x(), point.y())
        self._press_offset = point.toPoint() - self.frameGeometry().topLeft()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self._tracker.active:
            return
        point = event.globalPosition()
        if not self._tracker.move(point.x(), point.y()):
            return  # 还没越过阈值，窗口不动，免得“点一下就抖一下”
        target = point.toPoint() - self._press_offset
        self.move(target)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.globalPosition()
        verdict = self._tracker.release(point.x(), point.y())
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        if verdict == DRAG:
            # 松手时钳回工作区：拖到屏幕边缘外面就再也点不回来了
            work = self._work_area(point.toPoint())
            x, y = clamp_into_work(self.x(), self.y(), self.width(), self.height(), work)
            if (x, y) != (self.x(), self.y()):
                self.move(x, y)
            self.moved.emit(self.x(), self.y())
        elif verdict == CLICK:
            self.activated.emit()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        # 双击的第二下会先触发一次 click，这里吞掉，避免展开又收起
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self._tracker.cancel()
        self.context_requested.emit(event.globalPos())
        event.accept()

    # ------------------------------------------------------------------ 绘制

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        theme = self.theme
        center = QRectF(self.rect()).center()
        radius = theme.ball_radius

        self._paint_body(painter, center, radius)
        self._paint_ring(painter, center)
        self._paint_text(painter, center)

    def _paint_body(self, painter: QPainter, center: QPointF, radius: float) -> None:
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.0, self.theme.body_inner)
        gradient.setColorAt(1.0, self.theme.body_outer)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def _ring_rect(self, center: QPointF) -> QRectF:
        r = self.theme.neutral_radius
        return QRectF(center.x() - r, center.y() - r, r * 2, r * 2)

    def _paint_ring(self, painter: QPainter, center: QPointF) -> None:
        theme = self.theme
        rect = self._ring_rect(center)

        track = QPen(theme.track, theme.ring_width)
        track.setCapStyle(Qt.PenCapStyle.FlatCap)
        if self._fallback:
            # 兜底口径（还没设作息）画虚线：不伪装成正常进度
            track.setStyle(Qt.PenStyle.DashLine)
            track.setDashPattern([1.4, 2.0])
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(track)
        painter.drawEllipse(rect)

        ratio = min(max(self._ratio, 0.0), 1.0)
        if ratio <= 0.0:
            return

        pen = QPen(self._arc_brush(center), theme.ring_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        if ratio >= 0.999:
            # 画满圈时不要画 360° 弧：起点和终点会叠出一个可见的接缝
            painter.drawEllipse(rect)
        else:
            painter.drawArc(rect, 90 * 16, int(round(-360 * 16 * ratio)))

    def _arc_brush(self, center: QPointF):
        theme = self.theme
        if self._fallback:
            return QColor(theme.text_muted)
        gradient = QConicalGradient(center, 90.0)
        gradient.setColorAt(0.0, theme.accent_start)
        gradient.setColorAt(0.55, theme.accent_mid)
        gradient.setColorAt(1.0, theme.accent_end)
        return gradient

    def _paint_text(self, painter: QPainter, center: QPointF) -> None:
        theme = self.theme
        font = QFont()
        font.setFamilies(["Segoe UI", "Microsoft YaHei"])
        font.setPixelSize(max(9, int(theme.ball_radius * 0.5)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(theme.text_muted if self._fallback else theme.text)
        box = QRectF(
            center.x() - theme.ball_radius,
            center.y() - theme.ball_radius,
            theme.ball_radius * 2,
            theme.ball_radius * 2,
        )
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, percent_text(self._ratio))

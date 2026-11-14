"""桌面上的那个球：无边框、置顶、不进任务栏、可拖。

M1 只做「能看、能拖、能记住位置」。点击目前只发信号，展开留给 M2——
形变几何已经在 `morph.py` 里验完了，但把它接到真实窗口上要改窗口尺寸与
透明区域的策略，混在一起做会让「球对不对」和「动画对不对」互相掩盖。

两个 Windows 上的硬要求，写在最前面免得以后被“优化”掉：
1. `WA_TranslucentBackground` 必须在 `show()` 之前设，之后再设无效。
2. `Tool` 不能省。少了它任务栏会多一个图标，而这是个不该占任务栏的东西。
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRectF, QSize, Qt, Signal, QVariantAnimation, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QCursor,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import QWidget

from ..core import PointerTracker, Rect, clamp_into_work
from ..core.layout import place_panel
from ..core.interaction import CLICK, DRAG
from ..storage import WindowState
from .theme import DARK, Theme
from .morph import StripSpec, frame_at, motion_bounds

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
        self._morph: StripSpec | None = None
        self._morph_t = 0.0
        self._origin = QPointF()
        self._motion_origin = QPointF()
        self._expanded = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(theme.expand_ms)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_morph_value)
        self._anim.finished.connect(self._on_morph_finished)
        self._panel_rect = Rect(0, 0, 0, 0)
        self._motion_size = QSize(self.theme.window_size, self.theme.window_size)
        self._hover_opened = False
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(theme.hover_open_ms)
        self._hover_timer.timeout.connect(self._expand_from_hover)
        self._outside_timer = QTimer(self)
        self._outside_timer.setInterval(50)
        self._outside_timer.timeout.connect(self._poll_outside_click)
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(theme.hover_close_ms)
        self._leave_timer.timeout.connect(self._collapse_if_pointer_left)
        self._escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._escape.activated.connect(self._begin_collapse)

        self.setWindowTitle("Orbit")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(theme.window_size, theme.window_size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # 球心数字：等宽数字（tnum）让「8%」与「100%」的数字位对齐，
        # 刷新时不会因为字形宽度变化而左右抖。字体只建一次，别在 paintEvent 里造。
        self._percent_font = QFont()
        self._percent_font.setFamilies(list(theme.font_families))
        self._percent_font.setPixelSize(theme.percent_px)
        self._percent_font.setWeight(theme.percent_weight)
        self._percent_font.setFeature(QFont.Tag("tnum"), 1)

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
            center_x = work.x + work.w / 2
            center_y = work.y + work.h / 2
            self.move(
                round(center_x - size / 2),
                round(center_y - size / 2),
            )
            return
        x, y = point
        work = self._work_area(QPoint(x + size // 2, y + size // 2))
        self.move(*clamp_into_work(x, y, size, size, work))

    def position(self) -> tuple[int, int]:
        return self.x(), self.y()

    def toggle_expanded(self) -> None:
        if self._morph is None:
            self._begin_expand()
        else:
            self._begin_collapse()

    def _begin_expand(self) -> None:
        self._hover_opened = False
        center = QPointF(self.x() + self.width() / 2, self.y() + self.height() / 2)
        work = self._work_area(center.toPoint())
        down = center.y() <= work.y + work.h / 2
        placement = place_panel(
            work, center.x(), center.y(), self.theme.ball_radius,
            self.theme.panel_width, self.theme.panel_height,
        )
        self._morph = StripSpec(
            center.x(), center.y(), self.theme.ball_radius, placement.rect,
            down=down, ratio=self._ratio, ring_width=self.theme.ring_width,
            inset=self.theme.ring_inset, corner=self.theme.panel_radius,
        )
        left, top, right, bottom = motion_bounds(self._morph)
        ball = (center.x() - self.theme.ball_radius - self.theme.window_margin,
                center.y() - self.theme.ball_radius - self.theme.window_margin,
                center.x() + self.theme.ball_radius + self.theme.window_margin,
                center.y() + self.theme.ball_radius + self.theme.window_margin)
        panel = placement.rect
        bounds = (min(left, ball[0], panel.x), min(top, ball[1], panel.y),
                  max(right, ball[2], panel.right), max(bottom, ball[3], panel.bottom))
        self._origin = QPointF(bounds[0], bounds[1])
        self._motion_origin = QPointF(bounds[0], bounds[1])
        self._motion_size = QSize(max(1, round(bounds[2] - bounds[0])), max(1, round(bounds[3] - bounds[1])))
        self._panel_rect = placement.rect
        self._expanded = True
        self._set_canvas(self._origin, self._motion_size)
        self._animate(0.0, 1.0, self.theme.expand_ms)

    def _begin_collapse(self) -> None:
        if self._morph is None:
            return
        self._set_canvas(self._motion_origin, self._motion_size)
        self._expanded = False
        self._animate(self._morph_t, 0.0, self.theme.collapse_ms)

    def _animate(self, start: float, end: float, duration: int) -> None:
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic if end > start else QEasingCurve.Type.InCubic)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def _set_canvas(self, origin: QPointF, size: QSize) -> None:
        self._origin = origin
        self.setFixedSize(size)
        self.move(round(origin.x()), round(origin.y()))

    def _on_morph_value(self, value) -> None:
        self._morph_t = float(value)
        self.update()

    def _on_morph_finished(self) -> None:
        if self._morph is None:
            return
        if self._expanded:
            rect = self._panel_rect
            self._set_canvas(QPointF(rect.x, rect.y), QSize(round(rect.w), round(rect.h)))
            self._origin = QPointF(rect.x, rect.y)
            self._outside_timer.start()
        else:
            spec = self._morph
            size = self.theme.window_size
            self._set_canvas(QPointF(spec.cx - size / 2, spec.cy - size / 2), QSize(size, size))
            self._morph = None
            self._morph_t = 0.0
            self._outside_timer.stop()
            self._leave_timer.stop()
        self.update()

    # ------------------------------------------------------------------ 交互

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._morph is not None and self._anim.state() != QVariantAnimation.State.Running:
            self._tracker.press(event.globalPosition().x(), event.globalPosition().y())
            self._press_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
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
        old_x, old_y = self.x(), self.y()
        self.move(target)
        if self._morph is not None:
            self._translate_morph(self.x() - old_x, self.y() - old_y)
        event.accept()

    def _translate_morph(self, dx: int, dy: int) -> None:
        spec = self._morph
        if spec is None:
            return
        self._morph = StripSpec(
            cx=spec.cx + dx, cy=spec.cy + dy, radius=spec.radius,
            panel=Rect(spec.panel.x + dx, spec.panel.y + dy, spec.panel.w, spec.panel.h),
            down=spec.down, ratio=spec.ratio, ring_width=spec.ring_width,
            inset=spec.inset, corner=spec.corner, gap_deg=spec.gap_deg, t_gap=spec.t_gap,
            t_bend=spec.t_bend, samples=spec.samples,
        )
        self._panel_rect = self._morph.panel
        self._origin += QPointF(dx, dy)
        self._motion_origin += QPointF(dx, dy)

    def enterEvent(self, event) -> None:
        self._leave_timer.stop()
        if self._morph is None:
            self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_timer.stop()
        if self._morph is not None and self._hover_opened:
            self._leave_timer.start()
        super().leaveEvent(event)

    def _expand_from_hover(self) -> None:
        if self._morph is None:
            self._hover_opened = True
            self._begin_expand()
            self._hover_opened = True

    def _collapse_if_pointer_left(self) -> None:
        if self._morph is not None and self._hover_opened:
            point = QCursor.pos()
            if not self.frameGeometry().contains(point):
                self._begin_collapse()

    def _poll_outside_click(self) -> None:
        if self._morph is None or self._anim.state() == QVariantAnimation.State.Running:
            return
        if sys.platform == "win32":
            pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 1)
        else:
            pressed = bool(QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if pressed and not self.frameGeometry().contains(QCursor.pos()):
            self._begin_collapse()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.globalPosition()
        verdict = self._tracker.release(point.x(), point.y())
        if self._morph is not None:
            if verdict == DRAG:
                work = self._work_area(point.toPoint())
                x, y = clamp_into_work(self.x(), self.y(), self.width(), self.height(), work)
                dx, dy = x - self.x(), y - self.y()
                if dx or dy:
                    self.move(x, y)
                    self._translate_morph(dx, dy)
                spec = self._morph
                size = self.theme.window_size
                self.moved.emit(round(spec.cx - size / 2), round(spec.cy - size / 2))
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
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

        if self._morph is not None:
            self._paint_morph(painter)
            return

        theme = self.theme
        center = QRectF(self.rect()).center()
        radius = theme.ball_radius

        self._paint_body(painter, center, radius)
        self._paint_ring(painter, center)
        self._paint_text(painter, center)

    def _paint_morph(self, painter: QPainter) -> None:
        spec = self._morph
        if spec is None:
            return
        frame = frame_at(self._morph_t, spec)

        def at(point: tuple[float, float]) -> QPointF:
            return QPointF(point[0] - self._origin.x(), point[1] - self._origin.y())

        if frame.straight:
            rect = frame.body_rect
            body = QRectF(rect.x - self._origin.x(), rect.y - self._origin.y(), rect.w, rect.h)
            path = QPainterPath()
            radius = min(frame.corner, rect.h / 2)
            path.addRoundedRect(body, radius, radius)
            painter.setPen(QPen(self.theme.outline, self.theme.outline_width))
            painter.setBrush(self.theme.body_outer)
            painter.drawPath(path)
            painter.setClipPath(path)
        elif frame.body:
            # 弯折阶段球盘必须还在。只画环带的话，点下去的瞬间中间会突然空掉
            # ——球「啪」地变成一圈细环再摊开，看起来像坏了。
            if frame.ball_alpha > 0.01:
                center = QPointF(spec.cx - self._origin.x(), spec.cy - self._origin.y())
                painter.setOpacity(frame.ball_alpha)
                self._paint_disc(painter, center, spec.radius)
                painter.setOpacity(1.0)

            path = QPainterPath(at(frame.body[0]))
            for point in frame.body[1:]:
                path.lineTo(at(point))
            path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.theme.body_outer)
            painter.drawPath(path)

        for points, color, alpha in (
            (frame.track, self.theme.track, 1.0),
            (frame.red, self.theme.text_muted if self._fallback else self.theme.accent, 1.0),
        ):
            if len(points) < 2:
                continue
            path = QPainterPath(at(points[0]))
            for point in points[1:]:
                path.lineTo(at(point))
            pen = QPen(color, spec.ring_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setOpacity(alpha)
            painter.drawPath(path)
        painter.setOpacity(1.0)
        painter.setClipping(False)

        if frame.ball_alpha > 0.01:
            painter.setOpacity(frame.ball_alpha)
            painter.setFont(self._percent_font)
            painter.setPen(self.theme.text)
            box = QRectF(
                spec.cx - spec.radius - self._origin.x(),
                spec.cy - spec.radius - self._origin.y(),
                spec.radius * 2,
                spec.radius * 2,
            )
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, percent_text(self._ratio))
            painter.setOpacity(1.0)

    def _paint_body(self, painter: QPainter, center: QPointF, radius: float) -> None:
        theme = self.theme

        # 阴影先画，球体盖在上面：三层同心圆由外到内加深，读起来像一层柔光。
        painter.setPen(Qt.PenStyle.NoPen)
        for spread, alpha in theme.shadow_layers:
            color = QColor(theme.shadow)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.drawEllipse(
                QPointF(center.x(), center.y() + theme.shadow_offset),
                radius + spread,
                radius + spread,
            )

        self._paint_disc(painter, center, radius)

    def _paint_disc(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """盘面本身：径向渐变 + 内沿描边。阴影不在这里，形变中途不跟着跑。"""
        theme = self.theme
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.0, theme.body_inner)
        gradient.setColorAt(1.0, theme.body_outer)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

        # 描边画在球内沿（半径减半个线宽），画在中心会向外多出半像素，
        # 125%/150% 缩放下更容易糊成两像素灰边。
        painter.setPen(QPen(theme.outline, theme.outline_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = radius - theme.outline_width / 2
        painter.drawEllipse(center, inset, inset)

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

        pen = QPen(theme.text_muted if self._fallback else theme.accent, theme.ring_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        if ratio >= 0.999:
            # 画满圈时不要画 360° 弧：起点和终点会叠出一个可见的接缝
            painter.drawEllipse(rect)
        else:
            painter.drawArc(rect, 90 * 16, int(round(-360 * 16 * ratio)))

    def _paint_text(self, painter: QPainter, center: QPointF) -> None:
        theme = self.theme
        painter.setFont(self._percent_font)
        painter.setPen(theme.text_muted if self._fallback else theme.text)
        box = QRectF(
            center.x() - theme.ball_radius,
            center.y() - theme.ball_radius,
            theme.ball_radius * 2,
            theme.ball_radius * 2,
        )
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, percent_text(self._ratio))

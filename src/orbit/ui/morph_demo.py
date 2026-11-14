"""形变原型：只验证「球能不能真的摊开成面板」。

故意不接配置、不接存储、不接待办，只管一个 t 推所有几何。
跑起来：

    .venv\\Scripts\\python.exe -m orbit.ui.morph_demo

点击球展开、再点收起、拖动移动、ESC 收起。屏幕上球在哪半屏就往哪边摊，
面板不出工作区。也可以离屏出图核对几何：

    .venv\\Scripts\\python.exe -m orbit.ui.morph_demo --render out/
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from ..core.layout import Rect, place_panel
from .morph import MorphFrame, StripSpec, frame_at, motion_bounds

BALL_RADIUS = 28
BALL_MARGIN = 4
PANEL_W = 320
PANEL_H = 96
EXPAND_MS = 260
COLLAPSE_MS = 200
CLICK_SLOP = 4

ELAPSED = "#6E8BF5"
TRACK = "#FFFFFF"
BODY = "#16181D"
TEXT = "#EEF1F7"


def window_rect(spec: StripSpec) -> Rect:
    """动画期间窗口必须同时装得下球、面板和中间的甩动，否则会被裁。"""
    ball = Rect(
        spec.cx - spec.radius - BALL_MARGIN,
        spec.cy - spec.radius - BALL_MARGIN,
        (spec.radius + BALL_MARGIN) * 2,
        (spec.radius + BALL_MARGIN) * 2,
    )
    panel = spec.panel
    left, top, right, bottom = motion_bounds(spec)
    left = min(left, ball.x, panel.x)
    top = min(top, ball.y, panel.y)
    right = max(right, ball.right, panel.right)
    bottom = max(bottom, ball.bottom, panel.bottom)
    return Rect(left, top, right - left, bottom - top)


def paint_morph(
    painter: QPainter,
    spec: StripSpec,
    frame: MorphFrame,
    origin: QPointF,
    ratio_text: str,
) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def at(point: tuple[float, float]) -> QPointF:
        return QPointF(point[0] - origin.x(), point[1] - origin.y())

    if frame.straight:
        rect = frame.body_rect
        body = QRectF(
            rect.x - origin.x(),
            rect.y - origin.y(),
            rect.w,
            rect.h,
        )
        path = QPainterPath()
        radius = min(frame.corner, rect.h / 2)
        path.addRoundedRect(body, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BODY))
        painter.setOpacity(0.94)
        painter.drawPath(path)
        painter.setOpacity(1.0)
        painter.setClipPath(path)

    # 近端那条线：已过段 + 未过段。弯折阶段它就是整个球。
    for points, color, alpha in (
        (frame.track, QColor(TRACK), 0.22),
        (frame.red, QColor(ELAPSED), 1.0),
    ):
        if len(points) < 2:
            continue
        pen = QPen(color, spec.ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setOpacity(alpha)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(at(points[0]))
        for point in points[1:]:
            path.lineTo(at(point))
        painter.drawPath(path)
    painter.setOpacity(1.0)

    if frame.straight:
        painter.setClipping(False)

    # 球心的百分比：只活到环被拉直为止
    if frame.ball_alpha > 0.01:
        painter.setOpacity(frame.ball_alpha * 0.92)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        box = QRectF(
            spec.cx - spec.radius - origin.x(),
            spec.cy - spec.radius - origin.y(),
            spec.radius * 2,
            spec.radius * 2,
        )
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, ratio_text)
        painter.setOpacity(1.0)


class MorphWindow(QWidget):
    def __init__(self, ratio: float = 0.62) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self.ratio = ratio
        self._t = 0.0
        self._origin = QPointF(0, 0)
        self._spec: StripSpec | None = None
        self._ball_center = QPointF(0, 0)
        self._press: QPoint | None = None
        self._dragging = False

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.finished.connect(self._on_anim_done)

        self._place_ball(QPointF(120, 120))

    # --- 位置与尺寸 -------------------------------------------------------

    def _set_window(self, rect: Rect) -> None:
        """换一块画布：窗口原点变了，所有屏幕坐标由 _origin 平移过去。"""
        self._origin = QPointF(rect.x, rect.y)
        self.setFixedSize(QSize(int(rect.w), int(rect.h)))
        self.move(int(rect.x), int(rect.y))

    def _place_ball(self, center: QPointF) -> None:
        self._ball_center = center
        self._t = 0.0
        self._spec = None
        size = BALL_RADIUS * 2 + BALL_MARGIN * 2
        self._set_window(Rect(center.x() - size / 2, center.y() - size / 2, size, size))

    def _build_spec(self) -> StripSpec:
        screen = self.screen() or QGuiApplication.primaryScreen()
        work = screen.availableGeometry()
        placement = place_panel(
            Rect(work.x(), work.y(), work.width(), work.height()),
            self._ball_center.x(),
            self._ball_center.y(),
            BALL_RADIUS,
            PANEL_W,
            PANEL_H,
        )
        return StripSpec(
            cx=self._ball_center.x(),
            cy=self._ball_center.y(),
            radius=BALL_RADIUS,
            panel=placement.rect,
            down=placement.down,
            ratio=self.ratio,
        )

    def _enter_expanded(self) -> None:
        self._spec = self._build_spec()
        self._set_window(window_rect(self._spec))
        self._animate(1.0, EXPAND_MS, QEasingCurve.Type.OutCubic)

    def _enter_collapsed(self) -> None:
        size = BALL_RADIUS * 2 + BALL_MARGIN * 2
        self._spec = None
        self._set_window(
            Rect(self._ball_center.x() - size / 2, self._ball_center.y() - size / 2, size, size)
        )
        self.update()

    def _begin_collapse(self) -> None:
        if self._spec is not None:
            # 先把窗口撑回运动范围，否则反向动画会被裁掉
            self._set_window(window_rect(self._spec))
        self._animate(0.0, COLLAPSE_MS, QEasingCurve.Type.InCubic)

    def _animate(self, target: float, duration: int, curve: QEasingCurve.Type) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(curve)
        self._anim.start()

    def _on_anim(self, value) -> None:
        self._t = float(value)
        self.update()

    def _on_anim_done(self) -> None:
        if self._t >= 0.999 and self._spec is not None:
            # 展开完只留面板那一块：窗口的透明区域照样吃鼠标点击，
            # 留着整个运动范围等于在桌面上挖了一块死区。
            panel = self._spec.panel
            self._set_window(Rect(panel.x, panel.y, panel.w, panel.h))
            self.update()
        elif self._t <= 0.001:
            self._enter_collapsed()

    # --- 交互 -------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return
        now = event.globalPosition().toPoint()
        delta = now - self._press
        if not self._dragging and (abs(delta.x()) >= CLICK_SLOP or abs(delta.y()) >= CLICK_SLOP):
            self._dragging = True
        if self._dragging:
            self.move(self.pos() + delta)
            self._press = now
            if self._spec is not None:
                self._ball_center = QPointF(
                    self._ball_center.x() + delta.x(), self._ball_center.y() + delta.y()
                )
                self._spec = StripSpec(
                    cx=self._ball_center.x(),
                    cy=self._ball_center.y(),
                    radius=self._spec.radius,
                    panel=Rect(
                        self._spec.panel.x + delta.x(),
                        self._spec.panel.y + delta.y(),
                        self._spec.panel.w,
                        self._spec.panel.h,
                    ),
                    down=self._spec.down,
                    ratio=self._spec.ratio,
                )
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._press = None
        if self._dragging:
            self._dragging = False
            return
        if self._t >= 0.999:
            self._begin_collapse()
        elif self._t <= 0.001:
            self._enter_expanded()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._t >= 0.999:
            self._begin_collapse()

    # --- 绘制 -------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._spec is None:
            spec = StripSpec(
                cx=BALL_RADIUS + BALL_MARGIN,
                cy=BALL_RADIUS + BALL_MARGIN,
                radius=BALL_RADIUS,
                panel=Rect(0, 0, PANEL_W, PANEL_H),
                down=True,
                ratio=self.ratio,
            )
            paint_morph(painter, spec, frame_at(0.0, spec), QPointF(0, 0), f"{self.ratio:.0%}")
            return
        paint_morph(
            painter,
            self._spec,
            frame_at(self._t, self._spec),
            self._origin,
            f"{self.ratio:.0%}",
        )


def render_frames(out_dir: str, times: list[float], ratio: float, top_left: bool) -> list[str]:
    """离屏出图：不依赖真实桌面，用来核对几何。"""
    os.makedirs(out_dir, exist_ok=True)
    spec = StripSpec(
        cx=200.0,
        cy=160.0 if top_left else 700.0,
        radius=BALL_RADIUS,
        panel=place_panel(
            Rect(0, 0, 1280, 800),
            200.0,
            160.0 if top_left else 700.0,
            BALL_RADIUS,
            PANEL_W,
            PANEL_H,
        ).rect,
        down=top_left,
        ratio=ratio,
    )
    box = window_rect(spec)
    written = []
    for t in times:
        image = QImage(int(box.w), int(box.h), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#2B2F3A"))
        painter = QPainter(image)
        paint_morph(painter, spec, frame_at(t, spec), QPointF(box.x, box.y), f"{ratio:.0%}")
        painter.end()
        name = os.path.join(out_dir, f"t{int(round(t * 100)):03d}.png")
        image.save(name)
        written.append(name)
    return written


def main(argv: list[str]) -> int:
    if "--render" in argv:
        index = argv.index("--render")
        out_dir = argv[index + 1] if len(argv) > index + 1 else "out"
        ratio = 0.62
        if "--ratio" in argv:
            ratio = float(argv[argv.index("--ratio") + 1])
        times = [0.0, 0.1, 0.2, 0.35, 0.5, 0.55, 0.7, 0.85, 1.0]
        QGuiApplication(sys.argv[:1])
        for name in render_frames(out_dir, times, ratio, top_left=True):
            print(name)
        return 0

    app = QApplication(sys.argv)
    window = MorphWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

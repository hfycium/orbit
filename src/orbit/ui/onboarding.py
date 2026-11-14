"""Orbit 首次设置：深色时间仪表与滚轮作息输入。"""

from __future__ import annotations

from datetime import date
from time import monotonic

from PySide6.QtCore import (
    QEasingCurve,
    QTime,
    QTimer,
    Qt,
    Signal,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.schedule import daily_source, inspect_day_line
from ..storage import Config, Schedule, Weekly

MODE_ORDER = ("fixed", "daily", "weekly")
MODE_LABELS = {"fixed": "固定作息", "daily": "每日调整", "weekly": "周制"}

COLORS = {
    "background": "#171a1f",
    "rail": "#14171b",
    "surface": "#1c2026",
    "surface_hover": "#252b38",
    "border": "#30353e",
    "text": "#f3f4f5",
    "muted": "#a6abb4",
    "quiet": "#858d99",
    "accent": "#a6b8ff",
    "accent_text": "#111a2b",
    "warning": "#e8bd72",
}


def _parse_time(value: str | None, fallback: str) -> QTime:
    parsed = QTime.fromString(value or fallback, "HH:mm")
    return parsed if parsed.isValid() else QTime.fromString(fallback, "HH:mm")


def _time_value(hour: "WheelColumn", minute: "WheelColumn") -> str:
    return f"{hour.value():02d}:{minute.value():02d}"


class WheelColumn(QWidget):
    """循环数字滚轮：数字跟手移动，松手后惯性滑动并吸附到整格。"""

    valueChanged = Signal(int)

    def __init__(self, maximum: int, value: int, suffix: str = "", parent=None):
        super().__init__(parent)
        self._maximum = maximum
        self._row_height = 38
        self._value = value % (maximum + 1)
        self._position = float(50 * (maximum + 1) + self._value)
        self._entry_buffer = ""
        self._press_y = 0.0
        self._press_position = self._position
        self._last_y = 0.0
        self._last_time = 0.0
        self._velocity = 0.0
        self._drag_active = False
        self._dragging = False
        self.setObjectName("wheelColumn")
        self.setFixedSize(70, self._row_height * 3)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_position)
        self._entry_timer = QTimer(self)
        self._entry_timer.setSingleShot(True)
        self._entry_timer.setInterval(900)
        self._entry_timer.timeout.connect(self._clear_entry_buffer)
        self.setToolTip(f"拖动或滚动选择{suffix}；聚焦后可用 ↑ ↓ 或键入数字")

    def _set_position(self, position: float) -> None:
        self._position = float(position)
        value = int(self._position + 0.5) % (self._maximum + 1)
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)
        self.update()

    def _animate_to(self, target: float, duration: int = 150) -> None:
        self._animation.stop()
        self._animation.setDuration(duration)
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(float(target))
        self._animation.start()

    def _settle_drag(self) -> None:
        fling = max(-18.0, min(18.0, self._velocity * 0.18))
        target = round(self._position + fling)
        duration = min(520, max(150, 130 + int(abs(target - self._position) * 18)))
        self._animate_to(target, duration)

    def set_value(self, value: int, animated: bool = True) -> None:
        period = self._maximum + 1
        value %= period
        delta = (value - self._value + period // 2) % period - period // 2
        if delta:
            target = round(self._position) + delta
            if animated:
                self._animate_to(target)
            else:
                self._animation.stop()
                self._set_position(target)

    def _clear_entry_buffer(self) -> None:
        self._entry_buffer = ""

    def _type_digit(self, digit: str) -> None:
        candidate = (self._entry_buffer + digit)[-2:]
        parsed = int(candidate)
        if parsed <= self._maximum:
            self._entry_buffer = candidate
        else:
            self._entry_buffer = digit
            parsed = int(digit)
        self.set_value(parsed, animated=False)
        self._entry_timer.start()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._animation.stop()
            self._drag_active = True
            self._dragging = False
            self._press_y = event.position().y()
            self._press_position = self._position
            self._last_y = self._press_y
            self._last_time = monotonic()
            self._velocity = 0.0
            self.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_active:
            y = event.position().y()
            distance = y - self._press_y
            if not self._dragging and abs(distance) >= 4:
                self._dragging = True
            if self._dragging:
                self._set_position(self._press_position - distance / self._row_height)
                now = monotonic()
                elapsed = max(now - self._last_time, 0.001)
                instant_velocity = -(y - self._last_y) / elapsed / self._row_height
                self._velocity = self._velocity * 0.35 + instant_velocity * 0.65
                self._last_y = y
                self._last_time = now
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_active and event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._drag_active = False
            self._dragging = False
            if was_dragging:
                self._settle_drag()
            else:
                offset = (event.position().y() - self.height() / 2) / self._row_height
                self._animate_to(round(self._position + offset))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta:
            self.set_value(self._value + (1 if delta > 0 else -1), animated=True)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up:
            self.set_value(self._value + 1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.set_value(self._value - 1)
            event.accept()
            return
        if event.text().isdigit():
            self._type_digit(event.text())
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._clear_entry_buffer()
            self._entry_timer.stop()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        center_y = self.height() / 2

        band = self.rect().adjusted(5, round(center_y - self._row_height / 2 + 2), -5,
                                    round(center_y - self._row_height / 2 + 2) + self._row_height - self.height())
        painter.setPen(QColor(166, 184, 255, 48))
        painter.setBrush(QColor(166, 184, 255, 18))
        painter.drawRoundedRect(band, 8, 8)

        first = int(self._position) - 2
        last = int(self._position) + 3
        for row in range(first, last + 1):
            y = center_y + (row - self._position) * self._row_height
            distance = abs(y - center_y)
            fade = min(distance / (self._row_height * 1.45), 1.0)
            font = QFont("Segoe UI", round(24 - fade * 9))
            font.setWeight(
                QFont.Weight.DemiBold
                if int(self._position + 0.5) == row
                else QFont.Weight.Normal
            )
            color = QColor(COLORS["text"])
            color.setAlpha(round(255 - fade * 150))
            painter.setFont(font)
            painter.setPen(color)
            text_rect = self.rect().adjusted(0, round(y - self._row_height / 2), 0,
                                             round(y + self._row_height / 2) - self.height())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter,
                             f"{row % (self._maximum + 1):02d}")

    def closeEvent(self, event) -> None:
        self._animation.stop()
        self._entry_timer.stop()
        super().closeEvent(event)

    def value(self) -> int:
        return self._value

class TimeWheel(QWidget):
    """小时 / 分钟两列及其所属字段标题。"""

    timeChanged = Signal()

    def __init__(self, label: str, value: str | None, default: str, parent=None):
        super().__init__(parent)
        time = _parse_time(value, default)
        self.hour = WheelColumn(23, time.hour(), "小时")
        self.minute = WheelColumn(59, time.minute(), "分钟")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(9)
        self.heading = QLabel(label)
        self.heading.setObjectName("timeLabel")
        root.addWidget(self.heading)

        wheel_row = QHBoxLayout()
        wheel_row.setContentsMargins(0, 0, 0, 0)
        wheel_row.setSpacing(5)
        wheel_row.addWidget(self.hour)
        colon = QLabel(":")
        colon.setObjectName("timeColon")
        colon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wheel_row.addWidget(colon)
        wheel_row.addWidget(self.minute)
        root.addLayout(wheel_row)

        self.hour.valueChanged.connect(self.timeChanged)
        self.minute.valueChanged.connect(self.timeChanged)

    def value(self) -> str:
        return _time_value(self.hour, self.minute)


class ScheduleRing(QWidget):
    """左侧的 24 小时刻度预览。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wake = 8 * 60
        self._sleep = 23 * 60
        self._center_time = "08:00"
        self.setFixedSize(236, 236)

    def set_times(self, wake: str, sleep: str) -> None:
        wake_time = QTime.fromString(wake, "HH:mm")
        sleep_time = QTime.fromString(sleep, "HH:mm")
        if wake_time.isValid() and sleep_time.isValid():
            self._wake = wake_time.hour() * 60 + wake_time.minute()
            self._sleep = sleep_time.hour() * 60 + sleep_time.minute()
            self._center_time = wake
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(13, 13, -13, -13)
        pen = QPen(QColor(COLORS["border"]), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        duration = (self._sleep - self._wake) % (24 * 60)
        if duration == 0:
            duration = 24 * 60
        start = 90 * 16 - round(self._wake / (24 * 60) * 360 * 16)
        span = -round(duration / (24 * 60) * 360 * 16)
        pen.setColor(QColor(COLORS["accent"]))
        painter.setPen(pen)
        painter.drawArc(rect, start, span)

        center = self.rect().center()
        painter.setPen(QColor(COLORS["text"]))
        time_font = QFont("Segoe UI", 27, QFont.Weight.DemiBold)
        painter.setFont(time_font)
        painter.drawText(center.x() - 92, center.y() - 16, 184, 40, Qt.AlignmentFlag.AlignCenter, self._center_time)
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.drawText(center.x() - 80, center.y() + 26, 160, 22, Qt.AlignmentFlag.AlignCenter, "作息起点")


class OnboardingDialog(QDialog):
    """初始作息引导，沿用现有配置模型并按选中模式显示滚轮。"""

    def __init__(self, config: Config | None = None, today: date | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Orbit · 作息设置")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumSize(920, 620)
        self.resize(1000, 680)
        self.setModal(True)
        self._config = config or Config()
        self._today = today or date.today()
        self._time_wheels: list[TimeWheel] = []
        self._mode_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}

        self.setStyleSheet(self._style_sheet())
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_preview(), 0)
        root.addWidget(self._build_editor(), 1)

        self._install_drag_regions()
        self._apply_mode(self._config.mode if self._config.mode in MODE_ORDER else "fixed")
        self._refresh_line_hint()

    def _install_drag_regions(self) -> None:
        """让无系统标题栏的窗口可从非交互区域拖动。"""
        for name in (
            "previewRail",
            "brand",
            "scheduleRing",
            "summary",
            "railDescription",
            "editor",
            "eyebrow",
            "title",
            "subtitle",
            "windowBar",
        ):
            widget = self.findChild(QWidget, name)
            if widget is not None:
                widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == event.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                return True
        return super().eventFilter(watched, event)

    def _build_preview(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("previewRail")
        rail.setFixedWidth(320)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(30, 32, 30, 30)
        layout.setSpacing(0)

        brand = QLabel("Orbit  <span style='color:#818999'>/</span> 作息")
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(brand)
        layout.addSpacing(24)

        self.ring = ScheduleRing()
        self.ring.setObjectName("scheduleRing")
        layout.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.wake_summary = QLabel()
        self.wake_summary.setObjectName("summary")
        self.wake_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.wake_summary)
        layout.addStretch(1)

        description = QLabel("这段时间会成为 Orbit 今天的刻度。睡觉时间跨过午夜时，仍按起床日归属。")
        description.setObjectName("railDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        return rail

    def _build_editor(self) -> QWidget:
        editor = QWidget()
        editor.setObjectName("editor")
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(42, 34, 42, 30)
        layout.setSpacing(0)

        window_bar = QWidget()
        window_bar.setObjectName("windowBar")
        bar_layout = QHBoxLayout(window_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        eyebrow = QLabel("欢迎使用 Orbit")
        eyebrow.setObjectName("eyebrow")
        bar_layout.addWidget(eyebrow)
        bar_layout.addStretch(1)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("windowCloseButton")
        self.close_button.setFixedSize(32, 32)
        self.close_button.setToolTip("关闭设置窗口")
        self.close_button.clicked.connect(self.reject)
        bar_layout.addWidget(self.close_button)
        layout.addWidget(window_bar)
        title = QLabel("先定下你的日常节奏")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("滚动选择起床与睡觉时间，也可以聚焦数字后键入精确值。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        for mode in MODE_ORDER:
            button = QPushButton(MODE_LABELS[mode])
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected=mode: self._apply_mode(selected))
            self._mode_buttons[mode] = button
            tabs.addWidget(button)
        tabs.addStretch(1)
        layout.addLayout(tabs)
        layout.addSpacing(18)

        self.stack_area = QScrollArea()
        self.stack_area.setWidgetResizable(True)
        self.stack_area.setFrameShape(QFrame.Shape.NoFrame)
        self.stack_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack_area.setObjectName("pageScroll")
        self.stack_host = QWidget()
        self.stack_host.setObjectName("pageContent")
        self.stack_layout = QVBoxLayout(self.stack_host)
        self.stack_layout.setContentsMargins(0, 0, 4, 0)
        self.stack_layout.setSpacing(0)
        self.stack_area.setWidget(self.stack_host)
        layout.addWidget(self.stack_area, 1)

        self.line_hint = QLabel()
        self.line_hint.setObjectName("lineHint")
        self.line_hint.setWordWrap(True)
        layout.addWidget(self.line_hint)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 18, 0, 0)
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        self.accept_button = QPushButton("开始使用")
        self.accept_button.setObjectName("primaryButton")
        self.accept_button.clicked.connect(self.accept)
        footer.addWidget(cancel)
        footer.addWidget(self.accept_button)
        layout.addLayout(footer)
        return editor

    def _make_schedule_page(self, title: str, schedules: list[tuple[str, Schedule, str, str]]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)

        for label, schedule, wake_default, sleep_default in schedules:
            card = QFrame()
            card.setObjectName("scheduleCard")
            row = QHBoxLayout(card)
            row.setContentsMargins(17, 13, 17, 13)
            row.setSpacing(12)
            caption = QLabel(label)
            caption.setObjectName("scheduleCaption")
            caption.setFixedWidth(78)
            row.addWidget(caption)
            wake = self._new_wheel("起床", schedule.wake, wake_default)
            sleep = self._new_wheel("睡觉", schedule.sleep, sleep_default)
            row.addWidget(wake, 1)
            row.addWidget(sleep, 1)
            layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _new_wheel(self, label: str, value: str | None, default: str) -> TimeWheel:
        wheel = TimeWheel(label, value, default)
        wheel.timeChanged.connect(self._refresh_preview)
        wheel.timeChanged.connect(self._refresh_line_hint)
        self._time_wheels.append(wheel)
        return wheel

    def _build_pages(self) -> None:
        inherited_found = daily_source(self._config, self._today)
        inherited = inherited_found[1] if inherited_found else Schedule()
        self._pages = {
            "fixed": self._make_schedule_page(
                "每天使用的时间",
                [("每天", self._config.fixed, "08:00", "23:00")],
            ),
            "daily": self._make_schedule_page(
                f"今天的作息 · {self._today.isoformat()}",
                [("今天", inherited, "08:00", "23:00")],
            ),
            "weekly": self._make_schedule_page(
                "工作日与周末",
                [
                    ("工作日", self._config.weekly.weekday, "07:30", "23:00"),
                    ("周末", self._config.weekly.weekend, "09:00", "00:30"),
                ],
            ),
        }

    def _apply_mode(self, mode: str) -> None:
        if not self._pages:
            self._build_pages()
        for key, button in self._mode_buttons.items():
            button.setChecked(key == mode)
        while self.stack_layout.count():
            item = self.stack_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.stack_layout.addWidget(self._pages[mode])
        self._selected_mode = mode
        self._refresh_preview()
        self._refresh_line_hint()

    def _selected_wheels(self) -> list[TimeWheel]:
        page = self._pages.get(getattr(self, "_selected_mode", "fixed"))
        return page.findChildren(TimeWheel) if page is not None else []

    def selected_mode(self) -> str:
        return getattr(self, "_selected_mode", "fixed")

    def _refresh_preview(self) -> None:
        wheels = self._selected_wheels()
        if not wheels:
            return
        wake, sleep = wheels[0].value(), wheels[1].value()
        self.ring.set_times(wake, sleep)
        self.wake_summary.setText(f"起床 {wake}　·　睡觉 {sleep}")

    def _refresh_line_hint(self) -> None:
        if not hasattr(self, "line_hint"):
            return
        issue = inspect_day_line(self.active_config())
        if issue is None:
            self.line_hint.clear()
            self.line_hint.setVisible(False)
            return
        self.line_hint.setText("日界线提示：" + issue.message())
        self.line_hint.setVisible(True)

    def active_config(self) -> Config:
        wheels = self._selected_wheels()
        config = Config(day_line=self._config.day_line, mode=self.selected_mode())
        if config.mode == "fixed":
            config.fixed = Schedule(wheels[0].value(), wheels[1].value())
        elif config.mode == "weekly":
            config.weekly = Weekly(
                weekday=Schedule(wheels[0].value(), wheels[1].value()),
                weekend=Schedule(wheels[2].value(), wheels[3].value()),
            )
        else:
            config.daily = {self._today.isoformat(): Schedule(wheels[0].value(), wheels[1].value())}
        return config

    def result_config(self) -> Config:
        active = self.active_config()
        daily = dict(self._config.daily) | active.daily
        daily_latest = self._config.daily_latest
        if active.mode == "daily":
            schedule = active.daily[self._today.isoformat()]
            from ..storage import DatedSchedule

            daily_latest = DatedSchedule(self._today.isoformat(), schedule.wake, schedule.sleep)
        return Config(
            mode=active.mode,
            day_line=self._config.day_line,
            fixed=active.fixed if active.mode == "fixed" else self._config.fixed,
            weekly=active.weekly if active.mode == "weekly" else self._config.weekly,
            daily=daily,
            override=self._config.override,
            daily_latest=daily_latest,
        )

    @staticmethod
    def _style_sheet() -> str:
        return f"""
            QDialog {{ background: {COLORS['background']}; color: {COLORS['text']}; border: 1px solid rgba(255, 255, 255, 28); border-radius: 14px; }}
            QWidget#previewRail {{ background: {COLORS['rail']}; border-right: 1px solid {COLORS['border']}; }}
            QLabel#brand {{ color: {COLORS['text']}; font-size: 20px; font-weight: 600; }}
            QLabel#eyebrow {{ color: {COLORS['quiet']}; font-size: 13px; }}
            QPushButton#windowCloseButton {{ color: {COLORS['muted']}; background: transparent; border: 1px solid transparent; border-radius: 9px; font-size: 22px; padding: 0; }}
            QPushButton#windowCloseButton:hover {{ color: #ffffff; background: #8f3d4a; border-color: #a94a58; }}
            QPushButton#windowCloseButton:pressed {{ background: #74303c; }}
            QLabel#title {{ color: {COLORS['text']}; font-size: 27px; font-weight: 600; margin-top: 6px; }}
            QLabel#subtitle {{ color: {COLORS['muted']}; font-size: 14px; margin-top: 8px; }}
            QLabel#summary {{ color: {COLORS['muted']}; font-size: 12px; margin-top: 16px; }}
            QLabel#railDescription {{ color: {COLORS['muted']}; font-size: 14px; line-height: 1.5; }}
            QPushButton {{ color: {COLORS['muted']}; background: transparent; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 10px 14px; min-height: 20px; }}
            QPushButton:hover {{ background: {COLORS['surface_hover']}; color: {COLORS['text']}; }}
            QPushButton:checked {{ color: #e8edff; background: {COLORS['surface_hover']}; border-color: #6e7fa4; }}
            QPushButton#primaryButton {{ color: {COLORS['accent_text']}; background: {COLORS['accent']}; border: 0; font-weight: 650; }}
            QPushButton#secondaryButton {{ background: {COLORS['surface']}; color: {COLORS['text']}; }}
            QLabel#sectionTitle {{ color: {COLORS['text']}; font-size: 16px; font-weight: 600; padding: 4px 0; }}
            QFrame#scheduleCard {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}
            QLabel#scheduleCaption {{ color: {COLORS['muted']}; font-size: 13px; font-weight: 600; }}
            QLabel#timeLabel {{ color: {COLORS['muted']}; font-size: 12px; }}
            QLabel#timeColon {{ color: {COLORS['quiet']}; font-size: 20px; padding-top: 23px; }}
            QWidget#wheelColumn {{ background: transparent; }}
            QScrollArea#pageScroll {{ background: transparent; }}
            QWidget#pageContent, QScrollArea#pageScroll QWidget#qt_scrollarea_viewport {{ background: {COLORS['background']}; }}
            QLabel#lineHint {{ color: {COLORS['warning']}; font-size: 12px; padding-top: 7px; }}
            QScrollBar:vertical {{ width: 8px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: #3a414c; border-radius: 4px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = OnboardingDialog()
    if dialog.exec():
        result = dialog.result_config()
        print(f"模式: {result.mode} | 已配置: {result.configured}")
        print(result.to_dict())

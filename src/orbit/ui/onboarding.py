"""Orbit 首次设置：深色时间仪表与滚轮作息输入。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
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


def _time_value(hour: QSpinBox, minute: QSpinBox) -> str:
    return f"{hour.value():02d}:{minute.value():02d}"


class WheelColumn(QWidget):
    """一列可滚动、可键盘微调、可直接键入的数字滚轮。"""

    valueChanged = Signal(int)

    def __init__(self, maximum: int, value: int, suffix: str = "", parent=None):
        super().__init__(parent)
        self._maximum = maximum
        self._suffix = suffix
        self.setObjectName("wheelColumn")
        self.setFixedWidth(66)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)

        self.previous = QLabel()
        self.previous.setObjectName("wheelNeighbor")
        self.current = _PaddedSpinBox()
        self.current.setObjectName("wheelValue")
        self.current.setRange(0, maximum)
        self.current.setWrapping(True)
        # NoButtons on the Windows style collapses QSpinBox's internal line edit to 1px.
        # Keep the native spin subcontrols enabled and hide their hit areas in QSS instead.
        self.current.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self.current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current.setKeyboardTracking(True)
        self.current.setAccelerated(True)
        self.current.setFixedHeight(48)
        self.current.setValue(value)
        self.next = QLabel()
        self.next.setObjectName("wheelNeighbor")

        for label in (self.previous, self.next):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(30)
            label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            label.installEventFilter(self)

        layout.addWidget(self.previous)
        layout.addWidget(self.current)
        layout.addWidget(self.next)
        self.current.valueChanged.connect(self._sync)
        self.current.valueChanged.connect(self.valueChanged)
        self._sync(self.current.value())
        self.setToolTip(f"滚动或使用 ↑ ↓ 调整{suffix}；也可以直接输入数字")

    def _sync(self, value: int) -> None:
        self.previous.setText(f"{(value - 1) % (self._maximum + 1):02d}")
        self.next.setText(f"{(value + 1) % (self._maximum + 1):02d}")

    def eventFilter(self, watched, event) -> bool:
        if event.type() == event.Type.Wheel:
            delta = event.angleDelta().y()
            if delta:
                self.current.stepBy(1 if delta > 0 else -1)
                return True
        if event.type() == event.Type.MouseButtonPress:
            self.current.setFocus()
        return super().eventFilter(watched, event)

    def value(self) -> int:
        return self.current.value()


class _PaddedSpinBox(QSpinBox):
    def textFromValue(self, value: int) -> str:
        return f"{value:02d}"

    def valueFromText(self, text: str) -> int:
        try:
            return int(text)
        except ValueError:
            return 0


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
        painter.drawText(center.x() - 80, center.y() + 26, 160, 22, Qt.AlignmentFlag.AlignCenter, "作息起点")


class OnboardingDialog(QDialog):
    """初始作息引导，沿用现有配置模型并按选中模式显示滚轮。"""

    def __init__(self, config: Config | None = None, today: date | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Orbit · 作息设置")
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

        self._apply_mode(self._config.mode if self._config.mode in MODE_ORDER else "fixed")
        self._refresh_line_hint()

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

        eyebrow = QLabel("欢迎使用 Orbit")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
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
            QDialog {{ background: {COLORS['background']}; color: {COLORS['text']}; }}
            QWidget#previewRail {{ background: {COLORS['rail']}; border-right: 1px solid {COLORS['border']}; }}
            QLabel#brand {{ color: {COLORS['text']}; font-size: 20px; font-weight: 600; }}
            QLabel#eyebrow {{ color: {COLORS['quiet']}; font-size: 13px; }}
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
            QLabel#wheelNeighbor {{ color: {COLORS['quiet']}; font-size: 14px; background: transparent; }}
            QSpinBox#wheelValue {{ color: {COLORS['text']}; background: #252a32; border: 1px solid #525f78; border-radius: 7px; font-size: 24px; font-weight: 600; selection-background-color: #687da7; padding: 0; }}
            QSpinBox#wheelValue::up-button, QSpinBox#wheelValue::down-button {{ width: 0; border: 0; }}
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

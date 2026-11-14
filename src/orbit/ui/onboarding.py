"""首启引导：选一种模式并填完时间。

模式互斥，所以这里只有一个选择维度；填完才允许进入球。
不做「跳过」按钮——没有配置的球只会一直跑兜底状态，等于没装。

日界线在这里只做提示：起床早于 06:00 时，默认日界线会把「已经起床」算成
昨天。运行时会按「现在落在今天的窗口里」自动纠正，所以不拦着用户保存，
但要把建议值说出来（日界线本身在设置窗口里改，见 M3）。
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QTimeEdit,
    QVBoxLayout,
)

from ..storage import Config, Schedule, Weekly
from ..core.schedule import daily_source, inspect_day_line

MODE_TEXT = {
    "fixed": ("固定", "设置一次起床、睡觉时间，每天自动使用"),
    "daily": ("每日", "设置当天的起床、睡觉时间，默认继承前一天"),
    "weekly": ("周制", "分别设置工作日、周末作息，按起床日期自动切换"),
}

MODE_ORDER = ("fixed", "daily", "weekly")


def _time_edit(default: str) -> QTimeEdit:
    edit = QTimeEdit()
    edit.setDisplayFormat("HH:mm")
    hour, minute = default.split(":")[:2]
    edit.setTime(QTime(int(hour), int(minute)))
    return edit


def _value(edit: QTimeEdit) -> str:
    return edit.time().toString("HH:mm")


class OnboardingDialog(QDialog):
    """一屏填完的引导。模式切换只影响下方时间区显示哪几行。"""

    def __init__(self, config: Config | None = None, today: date | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Orbit · 初始设置")
        self.setMinimumWidth(480)
        self._config = config or Config()
        self._today = today or date.today()
        self._edits: list[QTimeEdit] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("选择一种作息方式。之后基本不用再设置，需要时可随时切换。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addWidget(self._build_mode_box())
        layout.addWidget(self._build_fixed_box())
        layout.addWidget(self._build_weekly_box())
        layout.addWidget(self._build_daily_box())

        self.line_hint = QLabel()
        self.line_hint.setWordWrap(True)
        self.line_hint.setStyleSheet("color: #b26a00;")
        layout.addWidget(self.line_hint)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("开始使用")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        for edit in self._edits:
            edit.timeChanged.connect(self._refresh_line_hint)

        self._apply_mode()

    def _build_mode_box(self) -> QGroupBox:
        box = QGroupBox("作息模式")
        inner = QVBoxLayout(box)
        self._mode_buttons: dict[str, QRadioButton] = {}
        current = self._config.mode if self._config.mode in MODE_ORDER else "fixed"
        for mode in MODE_ORDER:
            name, desc = MODE_TEXT[mode]
            button = QRadioButton(f"{name}　{desc}")
            button.setChecked(mode == current)
            button.toggled.connect(self._apply_mode)
            self._mode_buttons[mode] = button
            inner.addWidget(button)
        return box

    def _build_fixed_box(self) -> QGroupBox:
        box = QGroupBox("作息时间")
        form = QFormLayout(box)
        self.fixed_wake = _time_edit(self._config.fixed.wake or "08:00")
        self.fixed_sleep = _time_edit(self._config.fixed.sleep or "23:00")
        form.addRow("起床", self.fixed_wake)
        form.addRow("睡觉", self.fixed_sleep)
        self.fixed_box = box
        self._edits += [self.fixed_wake, self.fixed_sleep]
        return box

    def _build_weekly_box(self) -> QGroupBox:
        box = QGroupBox("工作日 / 周末")
        form = QFormLayout(box)
        weekday = self._config.weekly.weekday
        weekend = self._config.weekly.weekend
        self.weekday_wake = _time_edit(weekday.wake or "07:30")
        self.weekday_sleep = _time_edit(weekday.sleep or "23:00")
        self.weekend_wake = _time_edit(weekend.wake or "09:00")
        self.weekend_sleep = _time_edit(weekend.sleep or "00:30")
        form.addRow("工作日 起床", self.weekday_wake)
        form.addRow("工作日 睡觉", self.weekday_sleep)
        form.addRow("周末 起床", self.weekend_wake)
        form.addRow("周末 睡觉", self.weekend_sleep)
        self.weekly_box = box
        self._edits += [self.weekday_wake, self.weekday_sleep, self.weekend_wake, self.weekend_sleep]
        return box

    def _build_daily_box(self) -> QGroupBox:
        box = QGroupBox(f"今天的作息（{self._today.isoformat()}）")
        form = QFormLayout(box)
        inherited = self._inherited_schedule()
        self.daily_wake = _time_edit(inherited.wake if inherited else "08:00")
        self.daily_sleep = _time_edit(inherited.sleep if inherited else "23:00")
        form.addRow("起床", self.daily_wake)
        form.addRow("睡觉", self.daily_sleep)
        self.daily_hint = QLabel(
            "已沿用上一次的作息" if inherited else "还没有历史记录，先填今天这一组"
        )
        self.daily_hint.setWordWrap(True)
        form.addRow(self.daily_hint)
        self.daily_box = box
        self._edits += [self.daily_wake, self.daily_sleep]
        return box

    def _inherited_schedule(self) -> Schedule | None:
        found = daily_source(self._config, self._today)
        if found is None:
            return None
        return found[1]

    def selected_mode(self) -> str:
        for mode, button in self._mode_buttons.items():
            if button.isChecked():
                return mode
        return "fixed"

    def _apply_mode(self) -> None:
        mode = self.selected_mode()
        self.fixed_box.setVisible(mode == "fixed")
        self.weekly_box.setVisible(mode == "weekly")
        self.daily_box.setVisible(mode == "daily")
        self._refresh_line_hint()

    def _refresh_line_hint(self) -> None:
        issue = inspect_day_line(self.active_config())
        if issue is None:
            self.line_hint.clear()
            self.line_hint.setVisible(False)
            return
        self.line_hint.setText("提示：" + issue.message() + "。")
        self.line_hint.setVisible(True)

    def active_config(self) -> Config:
        """只带当前模式那一组的配置，用于校验与提示。"""
        config = Config(day_line=self._config.day_line, mode=self.selected_mode())
        if config.mode == "fixed":
            config.fixed = Schedule(_value(self.fixed_wake), _value(self.fixed_sleep))
        elif config.mode == "weekly":
            config.weekly = Weekly(
                weekday=Schedule(_value(self.weekday_wake), _value(self.weekday_sleep)),
                weekend=Schedule(_value(self.weekend_wake), _value(self.weekend_sleep)),
            )
        else:
            config.daily = {
                self._today.isoformat(): Schedule(
                    _value(self.daily_wake), _value(self.daily_sleep)
                )
            }
        return config

    def result_config(self) -> Config:
        """把界面上的选择写回完整配置（保留其它模式已填的数据）。"""
        active = self.active_config()
        return Config(
            mode=active.mode,
            day_line=self._config.day_line,
            fixed=active.fixed if active.mode == "fixed" else self._config.fixed,
            weekly=active.weekly if active.mode == "weekly" else self._config.weekly,
            daily=dict(self._config.daily) | active.daily,
            override=self._config.override,
            daily_latest=self._config.daily_latest,
        )


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = OnboardingDialog()
    if dialog.exec():
        result = dialog.result_config()
        print(f"模式: {result.mode} | 已配置: {result.configured}")
        print(result.to_dict())

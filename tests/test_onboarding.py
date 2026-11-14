from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from orbit.storage import Config, Schedule, Weekly, load_config, save_config
from orbit.ui.onboarding import OnboardingDialog, WheelColumn


def test_onboarding_dialog_has_no_system_frame(qt_app):
    dialog = OnboardingDialog(Config())
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    dialog.close()


def test_time_wheel_changes_value_when_dragged(qt_app):
    column = WheelColumn(23, 10, "小时")
    column.show()
    qt_app.processEvents()
    start = QPoint(30, 22)
    global_start = QPointF(column.current.mapToGlobal(start))

    def send(event_type, local_y, button, buttons):
        local = QPointF(30, local_y)
        global_pos = QPointF(global_start.x(), global_start.y() + local_y - start.y())
        event = QMouseEvent(
            event_type,
            local,
            global_pos,
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(column.current, event)

    send(QEvent.Type.MouseButtonPress, 22, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    send(QEvent.Type.MouseMove, 0, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
    send(QEvent.Type.MouseButtonRelease, 0, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)

    assert column.value() == 11
    column.close()


def test_onboarding_restores_last_selected_mode(qt_app, orbit_home):
    original = Config(
        mode="weekly",
        weekly=Weekly(Schedule("07:30", "23:00"), Schedule("09:00", "00:30")),
    )
    dialog = OnboardingDialog(original)
    assert dialog.selected_mode() == "weekly"

    dialog._apply_mode("daily")
    save_config(dialog.result_config())
    reopened = OnboardingDialog(load_config())

    assert reopened.selected_mode() == "daily"
    assert reopened._mode_buttons["daily"].isChecked()
    dialog.close()
    reopened.close()

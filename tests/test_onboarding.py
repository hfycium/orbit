from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from orbit.storage import Config, Schedule, Weekly, load_config, save_config
from orbit.ui.onboarding import OnboardingDialog, WheelColumn


def test_onboarding_dialog_has_no_system_frame(qt_app):
    dialog = OnboardingDialog(Config())
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    dialog.close()


def test_onboarding_close_button_closes_borderless_window(qt_app):
    dialog = OnboardingDialog(Config())
    dialog.close_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_time_wheel_tracks_mouse_drag_and_snaps_to_row(qt_app):
    column = WheelColumn(23, 10, "小时")
    column.show()
    qt_app.processEvents()
    QTest.mousePress(column, Qt.MouseButton.LeftButton, pos=QPoint(34, 56))
    QTest.mouseMove(column, QPoint(34, 30), 80)
    QTest.mouseMove(column, QPoint(34, 8), 80)
    assert column.value() != 10
    QTest.mouseRelease(column, Qt.MouseButton.LeftButton, pos=QPoint(34, 8))
    QTest.qWait(700)
    assert abs(column._position - round(column._position)) < 0.01

    column._type_digit("2")
    column._type_digit("0")
    assert column.value() == 20
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

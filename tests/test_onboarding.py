from PySide6.QtCore import Qt

from orbit.storage import Config
from orbit.ui.onboarding import OnboardingDialog


def test_onboarding_dialog_has_no_system_frame(qt_app):
    dialog = OnboardingDialog(Config())
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    dialog.close()

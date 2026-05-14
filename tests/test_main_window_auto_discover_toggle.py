"""Test that the auto-discover toggle in the View menu controls widget state."""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_auto_discover_toggle_exists_and_starts_checked(qapp):
    """Auto-discover toggle exists and is checked by default."""
    from analyzer.main_window import MainWindow

    window = MainWindow()

    assert hasattr(window, "auto_discover_action")
    assert window.auto_discover_action.isCheckable()
    assert window.auto_discover_action.isChecked()


def test_auto_discover_toggle_propagates_to_widget(qapp):
    """Auto-discover toggle state propagates to Phase 2 widget."""
    from analyzer.main_window import MainWindow

    window = MainWindow()

    assert window.phase2_results._auto_discover_enabled is True

    window.auto_discover_action.setChecked(False)
    assert window.phase2_results._auto_discover_enabled is False

    window.auto_discover_action.setChecked(True)
    assert window.phase2_results._auto_discover_enabled is True


def test_auto_discover_action_in_view_menu(qapp):
    """Auto-discover action is in the View menu."""
    from analyzer.main_window import MainWindow

    window = MainWindow()

    view_menu = None
    for action in window.menuBar().actions():
        if action.text() == "&View":
            view_menu = action.menu()
            break

    assert view_menu is not None

    action_texts = [a.text() for a in view_menu.actions()]
    assert "Auto-discover &build context" in action_texts

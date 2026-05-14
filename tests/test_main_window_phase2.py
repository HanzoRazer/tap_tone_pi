"""
Tests for Phase 2 session integration in MainWindow.

DO-005 Stage D acceptance tests:
- Menu action exists
- Loading Phase 2 session populates widget
- Tab switches to Phase 2 results
- Error handling for invalid sessions
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if PyQt6 is not available (CI environment)
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from analyzer.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(qapp) -> MainWindow:
    """Create a MainWindow instance."""
    return MainWindow()


@pytest.fixture
def valid_session_dir(tmp_path: Path) -> Path:
    """Create a valid synthetic session directory."""
    session_dir = tmp_path / "session_test"
    session_dir.mkdir()
    (session_dir / "derived").mkdir()

    grid = {
        "schema_version": "phase2_grid_v1",
        "units": "mm",
        "origin": {"x": 0.0, "y": 0.0},
        "spacing": 10.0,
    }
    (session_dir / "grid.json").write_text(json.dumps(grid), encoding="utf-8")

    meta = {
        "schema_version": "phase2_session_meta_v1",
        "session_id": "test_session_001",
        "build_id": "TEST_BUILD_001",
        "created_at": "2026-05-02T12:00:00Z",
    }
    (session_dir / "session_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    freqs = [100.0, 200.0, 300.0, 400.0, 500.0]
    points = [
        {
            "point_id": f"P{i:02d}",
            "x_mm": float(i * 10),
            "y_mm": 0.0,
            "H_mag": [1.0, 2.0, 3.0, 2.0, 1.0],
            "H_phase_deg": [0.0] * 5,
        }
        for i in range(4)
    ]
    snapshot = {
        "schema_version": "phase2_ods_snapshot_v2",
        "freqs_hz": freqs,
        "points": points,
    }
    (session_dir / "derived" / "ods_snapshot.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )

    return session_dir


class TestMainWindowPhase2Integration:
    """Tests for Phase 2 session integration."""

    def test_has_phase2_results_tab(self, main_window: MainWindow):
        """MainWindow has Phase 2 ODS tab."""
        tab_names = [
            main_window.chart_tabs.tabText(i)
            for i in range(main_window.chart_tabs.count())
        ]
        assert "Phase 2 ODS" in tab_names

    def test_has_phase2_results_widget(self, main_window: MainWindow):
        """MainWindow has Phase2ResultsWidget attribute."""
        assert hasattr(main_window, "phase2_results")
        assert main_window.phase2_results is not None

    def test_load_phase2_session_success(
        self, main_window: MainWindow, valid_session_dir: Path
    ):
        """Loading valid Phase 2 session populates widget."""
        main_window._load_phase2_session(str(valid_session_dir))

        assert main_window.current_phase2_session is not None
        assert main_window.current_phase2_session.n_points == 4
        assert main_window.phase2_results.has_session()

    def test_load_phase2_session_switches_tab(
        self, main_window: MainWindow, valid_session_dir: Path
    ):
        """Loading Phase 2 session switches to Phase 2 tab."""
        main_window._load_phase2_session(str(valid_session_dir))

        current_widget = main_window.chart_tabs.currentWidget()
        assert current_widget is main_window.phase2_results

    def test_load_phase2_session_updates_statusbar(
        self, main_window: MainWindow, valid_session_dir: Path
    ):
        """Loading Phase 2 session updates status bar."""
        main_window._load_phase2_session(str(valid_session_dir))

        status_text = main_window.statusbar.currentMessage()
        assert "Phase 2" in status_text
        assert "4 points" in status_text

    def test_load_invalid_session_shows_error(
        self, main_window: MainWindow, tmp_path: Path
    ):
        """Loading invalid session shows error message."""
        invalid_dir = tmp_path / "invalid_session"
        invalid_dir.mkdir()

        with patch.object(main_window, "statusbar") as mock_statusbar:
            # Should not raise, but should show error dialog
            # We patch QMessageBox to prevent blocking
            with patch(
                "analyzer.main_window.QMessageBox.critical"
            ) as mock_critical:
                main_window._load_phase2_session(str(invalid_dir))
                mock_critical.assert_called_once()

    def test_frequency_changed_updates_statusbar(
        self, main_window: MainWindow, valid_session_dir: Path
    ):
        """Frequency change updates status bar."""
        main_window._load_phase2_session(str(valid_session_dir))

        main_window._on_phase2_frequency_changed(300.0)

        status_text = main_window.statusbar.currentMessage()
        assert "300.0 Hz" in status_text


class TestMainWindowPhase2Menu:
    """Tests for Phase 2 menu item."""

    def test_open_phase2_action_exists(self, main_window: MainWindow):
        """File menu has Open Phase 2 Session action."""
        file_menu = main_window.menuBar().actions()[0].menu()
        action_texts = [action.text() for action in file_menu.actions()]

        # Should contain Open Phase 2 Session (with & for accelerator)
        assert any("Phase" in text and "2" in text for text in action_texts)

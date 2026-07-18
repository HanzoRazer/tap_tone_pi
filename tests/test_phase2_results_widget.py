"""
Tests for Phase2ResultsWidget.

DO-005 Stage C acceptance tests:
- Widget initialization
- Session loading and display
- Frequency slider interaction
- Peak list population and click handling
- Metadata display
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# Skip all tests if PyQt6 is not available (CI environment)
pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from analyzer.loaders.phase2_session import Phase2Session, load_phase2_session
from analyzer.loaders.prediction_loader import BuildComparison, ModeComparison
from analyzer.widgets.phase2_results import Phase2ResultsWidget
from tap_tone_pi.materials import (
    BuildDatabase,
    BuildRecord,
    MeasuredSummary,
    PredictedValues,
    Residuals,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


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

    # 4 points, 10 frequencies with clear peaks at 300 Hz and 500 Hz
    freqs = list(np.linspace(100, 600, 10))
    points = []
    for i, (x, y) in enumerate([(0, 0), (10, 0), (0, 10), (10, 10)]):
        # Create magnitude with peaks at index 4 (300 Hz) and 8 (500 Hz)
        H_mag = [1.0] * 10
        H_mag[4] = 5.0  # Peak at ~300 Hz
        H_mag[8] = 3.0  # Peak at ~500 Hz
        points.append(
            {
                "point_id": f"P{i:02d}",
                "x_mm": float(x),
                "y_mm": float(y),
                "H_mag": H_mag,
                "H_phase_deg": [0.0] * 10,
            }
        )

    snapshot = {
        "schema_version": "phase2_ods_snapshot_v2",
        "freqs_hz": freqs,
        "points": points,
    }
    (session_dir / "derived" / "ods_snapshot.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )

    return session_dir


@pytest.fixture
def session(valid_session_dir: Path) -> Phase2Session:
    """Load the test session."""
    return load_phase2_session(valid_session_dir)


@pytest.fixture
def widget(qapp) -> Phase2ResultsWidget:
    """Create a Phase2ResultsWidget instance."""
    return Phase2ResultsWidget()


class TestPhase2ResultsWidgetInit:
    """Tests for widget initialization."""

    def test_creates_widget(self, widget: Phase2ResultsWidget):
        """Widget initializes without error."""
        assert widget is not None

    def test_initial_state_no_session(self, widget: Phase2ResultsWidget):
        """Widget starts with no session."""
        assert not widget.has_session()
        assert widget.session is None
        assert widget.current_frequency == 0.0


class TestPhase2ResultsWidgetSetSession:
    """Tests for set_session method."""

    def test_loads_session(self, widget: Phase2ResultsWidget, session: Phase2Session):
        """set_session loads session correctly."""
        widget.set_session(session)

        assert widget.has_session()
        assert widget.session is session
        assert widget._heatmap.n_points == 4

    def test_updates_slider_range(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """set_session updates slider range to match frequencies."""
        widget.set_session(session)

        assert widget._freq_slider.maximum() == session.n_freqs - 1

    def test_updates_metadata_labels(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """set_session updates metadata labels."""
        widget.set_session(session)

        assert "test_session_001" in widget._session_label.text()
        assert "4 points" in widget._grid_label.text()
        assert "TEST_BUILD_001" in widget._build_label.text()

    def test_populates_peaks_list(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """set_session populates peaks list."""
        widget.set_session(session)

        assert widget._peaks_list.count() > 0


class TestPhase2ResultsWidgetFrequencyControl:
    """Tests for frequency selection."""

    def test_slider_updates_heatmap(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Slider value change updates heatmap."""
        widget.set_session(session)
        initial_freq = widget.current_frequency

        widget._freq_slider.setValue(5)

        assert widget.current_frequency != initial_freq
        assert widget._current_freq_idx == 5

    def test_slider_updates_freq_label(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Slider value change updates frequency label."""
        widget.set_session(session)

        widget._freq_slider.setValue(5)

        assert "Hz" in widget._freq_label.text()
        freq_text = widget._freq_label.text().replace(" Hz", "")
        assert float(freq_text) > 0

    def test_set_frequency_by_value(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """set_frequency finds nearest index."""
        widget.set_session(session)

        # Set to a frequency that should snap to nearest bin
        widget.set_frequency(350.0)

        # Should snap to nearest frequency index
        assert widget._freq_slider.value() > 0

    def test_frequency_changed_signal(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """frequency_changed signal is emitted."""
        widget.set_session(session)

        signal_received = []
        widget.frequency_changed.connect(lambda f: signal_received.append(f))

        widget._freq_slider.setValue(3)

        assert len(signal_received) == 1
        assert signal_received[0] > 0


class TestPhase2ResultsWidgetPeaksInteraction:
    """Tests for peaks list interaction."""

    def test_peak_click_updates_slider(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Clicking a peak updates the slider."""
        widget.set_session(session)

        if widget._peaks_list.count() > 0:
            initial_value = widget._freq_slider.value()
            item = widget._peaks_list.item(0)
            peak_idx = item.data(Qt.ItemDataRole.UserRole)

            widget._on_peak_clicked(item)

            assert widget._freq_slider.value() == peak_idx


class TestPhase2ResultsWidgetWsiPlot:
    """Tests for WSI curve plotting."""

    def test_plots_mean_magnitude_without_wsi(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Without WSI data, plots mean magnitude."""
        widget.set_session(session)

        # Should have plotted something (mean magnitude fallback)
        assert len(widget._wsi_ax.lines) > 0

    def test_plots_wsi_when_available(
        self, widget: Phase2ResultsWidget, valid_session_dir: Path
    ):
        """With WSI data, plots WSI curve."""
        # Add WSI data
        wsi_curve = {
            "schema_version": "wsi_curve_v1",
            "freqs_hz": [100, 200, 300],
            "wsi_values": [0.5, 0.8, 0.6],
        }
        (valid_session_dir / "derived" / "wsi_curve.json").write_text(
            json.dumps(wsi_curve), encoding="utf-8"
        )

        session = load_phase2_session(valid_session_dir)
        widget.set_session(session)

        # Should have plotted WSI curve
        assert len(widget._wsi_ax.lines) >= 1


class TestPhase2ResultsWidgetHeatmap:
    """Tests for heatmap display."""

    def test_heatmap_has_points(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Heatmap receives points from session."""
        widget.set_session(session)

        assert widget._heatmap.n_points == 4

    def test_heatmap_values_updated(
        self, widget: Phase2ResultsWidget, session: Phase2Session
    ):
        """Heatmap values are updated when frequency changes."""
        widget.set_session(session)

        initial_range = widget._heatmap.value_range

        # Change to a different frequency
        widget._freq_slider.setValue(4)  # Peak frequency

        # Values should change (peak has higher magnitude)
        new_range = widget._heatmap.value_range
        assert new_range[1] > initial_range[1]  # Max should be higher at peak


class TestPhase2ResultsWidgetComparison:
    """Tests for comparison mode (DO-006)."""

    @pytest.fixture
    def build_db(self, tmp_path: Path, monkeypatch) -> BuildDatabase:
        """Create a temporary database with test builds."""
        db_path = tmp_path / "test_builds_db.json"
        monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(db_path))

        db = BuildDatabase(db_path)
        db.load()
        db.add_build(
            BuildRecord(
                build_id="TEST_BUILD_001",
                design_name="Test Jumbo",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
                predicted=PredictedValues(T1_hz=180.0, A0_hz=100.0),
                measured_summary=MeasuredSummary(T1_hz=175.0, A0_hz=102.0),
                residuals=Residuals(
                    T1_residual_hz=-5.0,
                    T1_residual_pct=-2.78,
                    A0_residual_hz=2.0,
                    A0_residual_pct=2.0,
                ),
            )
        )
        db.save()
        return db

    def test_initial_no_comparison(self, widget: Phase2ResultsWidget):
        """Widget starts with no comparison data."""
        assert not widget.has_comparison()
        assert widget.comparison is None

    def test_load_comparison_success(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """load_comparison loads data from build database."""
        widget.set_session(session)
        widget.load_comparison("TEST_BUILD_001")

        assert widget.has_comparison()
        assert widget.comparison is not None
        assert widget.comparison.build_id == "TEST_BUILD_001"

    def test_auto_loads_comparison_on_set_session(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """set_session auto-loads comparison for session.build_id."""
        widget.set_session(session)

        # Session has build_id=TEST_BUILD_001, should auto-load
        assert widget.has_comparison()
        assert widget.comparison.build_id == "TEST_BUILD_001"

    def test_comparison_display_updated(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """Comparison panel shows mode data."""
        widget.set_session(session)

        # Check comparison label was updated
        assert "TEST_BUILD_001" in widget._comparison_label.text()

        # Check comparison list has entries
        assert widget._comparison_list.count() >= 2  # T1 and A0

    def test_load_comparison_missing_build(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """load_comparison handles missing build gracefully."""
        widget.set_session(session)
        widget.load_comparison("NONEXISTENT_BUILD")

        assert not widget.has_comparison()
        assert "No comparison data" in widget._comparison_label.text()

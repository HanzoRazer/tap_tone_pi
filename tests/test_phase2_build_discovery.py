"""
Tests for build record auto-discovery in Phase2ResultsWidget.

DO-008 Stage C and D acceptance tests:
- Auto-discovery logic
- Build record loading
- Status label updates
- Discovery toggle
- Prediction auto-load
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from analyzer.loaders.phase2_session import Phase2Session, load_phase2_session
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

    freqs = list(np.linspace(100, 600, 10))
    points = []
    for i, (x, y) in enumerate([(0, 0), (10, 0), (0, 10), (10, 10)]):
        H_mag = [1.0] * 10
        H_mag[4] = 5.0
        H_mag[8] = 3.0
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
def session_no_build_id(tmp_path: Path) -> Path:
    """Create a session directory without build_id."""
    session_dir = tmp_path / "session_no_build"
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
        "session_id": "session_no_build",
        "created_at": "2026-05-02T12:00:00Z",
    }
    (session_dir / "session_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    freqs = list(np.linspace(100, 600, 10))
    points = [
        {
            "point_id": "P00",
            "x_mm": 0.0,
            "y_mm": 0.0,
            "H_mag": [1.0] * 10,
            "H_phase_deg": [0.0] * 10,
        }
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


@pytest.fixture
def build_db(tmp_path: Path, monkeypatch) -> BuildDatabase:
    """Create a temporary database with test builds."""
    db_path = tmp_path / "test_builds_db.json"
    monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(db_path))

    db = BuildDatabase(db_path)
    db.load()
    db.add_build(
        BuildRecord(
            build_id="TEST_BUILD_001",
            design_name="Carlos Jumbo",
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


@pytest.fixture
def session(valid_session_dir: Path) -> Phase2Session:
    """Load the test session."""
    return load_phase2_session(valid_session_dir)


@pytest.fixture
def widget(qapp) -> Phase2ResultsWidget:
    """Create a Phase2ResultsWidget instance."""
    return Phase2ResultsWidget()


class TestDiscoverySilentWhenDisabled:
    """Tests for discovery opt-out."""

    def test_discovery_silent_when_disabled(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """When auto-discover is disabled, no build is discovered."""
        widget.set_auto_discover(False)
        widget.set_session(session)

        assert widget._discovered_build is None


class TestDiscoverySilentWhenNoBuildId:
    """Tests for sessions without build_id."""

    def test_discovery_silent_when_no_build_id(
        self, widget: Phase2ResultsWidget, session_no_build_id: Path, qapp
    ):
        """When session has no build_id, discovery is silent."""
        session = load_phase2_session(session_no_build_id)
        widget.set_session(session)

        assert widget._discovered_build is None
        assert widget._build_label.text() == ""


class TestDiscoverySilentWhenNoBuildFile:
    """Tests for missing build records."""

    def test_discovery_silent_when_no_build_file(
        self, widget: Phase2ResultsWidget, session: Phase2Session, tmp_path: Path, monkeypatch
    ):
        """When build file doesn't exist, discovery is silent."""
        monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(tmp_path / "missing.json"))
        widget.set_session(session)

        assert widget._discovered_build is None
        assert "TEST_BUILD_001" in widget._build_label.text()


class TestDiscoverySuccess:
    """Tests for successful build discovery."""

    def test_discovery_success(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """Discovery populates _discovered_build on success."""
        widget.set_session(session)

        assert widget._discovered_build is not None
        assert widget._discovered_build.build_id == "TEST_BUILD_001"
        assert widget._discovered_build.design_name == "Carlos Jumbo"

    def test_discovery_updates_status_label(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """Discovery updates build label with build info."""
        widget.set_session(session)

        label_text = widget._build_label.text()
        assert "TEST_BUILD_001" in label_text
        assert "Carlos Jumbo" in label_text


class TestDiscoveryHandlesCorruptBuildFile:
    """Tests for corrupt build records."""

    def test_discovery_handles_corrupt_build_file(
        self, widget: Phase2ResultsWidget, session: Phase2Session, tmp_path: Path, monkeypatch
    ):
        """Corrupt build file doesn't crash the widget."""
        db_path = tmp_path / "corrupt_builds.json"
        db_path.write_text("{ invalid json }", encoding="utf-8")
        monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(db_path))

        widget.set_session(session)

        assert widget._discovered_build is None
        assert widget.has_session()


class TestDiscoveryResetsOnNewSessionLoad:
    """Tests for state reset between sessions."""

    def test_discovery_resets_on_new_session_load(
        self,
        widget: Phase2ResultsWidget,
        session: Phase2Session,
        session_no_build_id: Path,
        build_db: BuildDatabase,
    ):
        """Loading a new session resets discovered build."""
        widget.set_session(session)
        assert widget._discovered_build is not None

        session_b = load_phase2_session(session_no_build_id)
        widget.set_session(session_b)

        assert widget._discovered_build is None


class TestSetAutoDiscoverTogglesState:
    """Tests for auto-discover toggle."""

    def test_set_auto_discover_toggles_state(self, widget: Phase2ResultsWidget):
        """set_auto_discover updates internal flag."""
        assert widget._auto_discover_enabled is True

        widget.set_auto_discover(False)
        assert widget._auto_discover_enabled is False

        widget.set_auto_discover(True)
        assert widget._auto_discover_enabled is True


class TestExistingBehaviorUnchanged:
    """Regression tests for existing behavior."""

    def test_existing_load_session_behavior_unchanged(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """Widget still loads session and comparison correctly."""
        widget.set_session(session)

        assert widget.has_session()
        assert widget.session is session
        assert widget._heatmap.n_points == 4
        assert widget.has_comparison()
        assert widget.comparison.build_id == "TEST_BUILD_001"


class TestHasDiscoveredBuild:
    """Tests for has_discovered_build method."""

    def test_has_discovered_build_true(
        self, widget: Phase2ResultsWidget, session: Phase2Session, build_db: BuildDatabase
    ):
        """has_discovered_build returns True when build is found."""
        widget.set_session(session)
        assert widget.has_discovered_build() is True

    def test_has_discovered_build_false(
        self, widget: Phase2ResultsWidget, session_no_build_id: Path
    ):
        """has_discovered_build returns False when no build."""
        session = load_phase2_session(session_no_build_id)
        widget.set_session(session)
        assert widget.has_discovered_build() is False

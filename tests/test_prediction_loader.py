"""
Tests for prediction loader.

DO-006 Stage E acceptance tests:
- ModeComparison dataclass
- BuildComparison dataclass
- load_build_comparison from database
- get_predicted_mode_frequencies helper
- get_measured_mode_frequencies helper
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer.loaders.prediction_loader import (
    BuildComparison,
    ModeComparison,
    get_measured_mode_frequencies,
    get_predicted_mode_frequencies,
    load_build_comparison,
)
from tap_tone_pi.materials import (
    BuildDatabase,
    BuildRecord,
    MeasuredSummary,
    PredictedValues,
    Residuals,
    WoodSelection,
)


@pytest.fixture
def temp_db_path(tmp_path: Path, monkeypatch) -> Path:
    """Create a temporary database path and set environment."""
    db_path = tmp_path / "test_builds_db.json"
    monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(db_path))
    return db_path


@pytest.fixture
def populated_db(temp_db_path: Path) -> BuildDatabase:
    """A database with builds containing predictions/measurements."""
    db = BuildDatabase(temp_db_path)
    db.load()

    # Build with full predictions and measurements
    db.add_build(
        BuildRecord(
            build_id="BUILD_FULL",
            design_name="Carlos Jumbo",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            predicted=PredictedValues(
                T1_hz=180.0,
                A0_hz=100.0,
                T2_hz=280.0,
                T3_hz=350.0,
            ),
            measured_summary=MeasuredSummary(
                T1_hz=175.0,
                A0_hz=102.0,
                T2_hz=275.0,
                T3_hz=345.0,
            ),
            residuals=Residuals(
                T1_residual_hz=-5.0,
                T1_residual_pct=-2.78,
                A0_residual_hz=2.0,
                A0_residual_pct=2.0,
                T2_residual_hz=-5.0,
                T2_residual_pct=-1.79,
                T3_residual_hz=-5.0,
                T3_residual_pct=-1.43,
                computed_at_utc="2026-05-02T12:00:00Z",
            ),
        )
    )

    # Build with only predictions (no measurements yet)
    db.add_build(
        BuildRecord(
            build_id="BUILD_PRED_ONLY",
            design_name="Standard Dread",
            build_started="2026-05-15",
            created_at_utc="2026-05-15T10:00:00Z",
            predicted=PredictedValues(
                T1_hz=160.0,
                A0_hz=95.0,
            ),
        )
    )

    # Build with no predictions or measurements
    db.add_build(
        BuildRecord(
            build_id="BUILD_EMPTY",
            design_name="Empty Build",
            build_started="2026-06-01",
            created_at_utc="2026-06-01T10:00:00Z",
        )
    )

    db.save()
    return db


class TestModeComparison:
    """Tests for ModeComparison dataclass."""

    def test_has_both_true(self):
        """has_both is True when both values present."""
        mode = ModeComparison(
            mode_name="T1",
            predicted_hz=180.0,
            measured_hz=175.0,
            residual_hz=-5.0,
            residual_pct=-2.78,
        )
        assert mode.has_both is True

    def test_has_both_false_no_predicted(self):
        """has_both is False when predicted missing."""
        mode = ModeComparison(
            mode_name="T1",
            predicted_hz=None,
            measured_hz=175.0,
            residual_hz=None,
            residual_pct=None,
        )
        assert mode.has_both is False

    def test_has_both_false_no_measured(self):
        """has_both is False when measured missing."""
        mode = ModeComparison(
            mode_name="T1",
            predicted_hz=180.0,
            measured_hz=None,
            residual_hz=None,
            residual_pct=None,
        )
        assert mode.has_both is False


class TestBuildComparison:
    """Tests for BuildComparison dataclass."""

    def test_n_modes_with_comparison(self):
        """n_modes_with_comparison counts modes with both values."""
        comp = BuildComparison(
            build_id="TEST",
            design_name="Test",
            modes=[
                ModeComparison("T1", 180.0, 175.0, -5.0, -2.78),
                ModeComparison("A0", 100.0, None, None, None),
                ModeComparison("T2", 280.0, 275.0, -5.0, -1.79),
                ModeComparison("T3", None, None, None, None),
            ],
        )
        assert comp.n_modes_with_comparison == 2

    def test_has_predictions(self):
        """has_predictions detects any predicted values."""
        comp = BuildComparison(
            build_id="TEST",
            design_name="Test",
            modes=[
                ModeComparison("T1", 180.0, None, None, None),
                ModeComparison("A0", None, None, None, None),
            ],
        )
        assert comp.has_predictions is True

    def test_has_measurements(self):
        """has_measurements detects any measured values."""
        comp = BuildComparison(
            build_id="TEST",
            design_name="Test",
            modes=[
                ModeComparison("T1", None, 175.0, None, None),
                ModeComparison("A0", None, None, None, None),
            ],
        )
        assert comp.has_measurements is True


class TestLoadBuildComparison:
    """Tests for load_build_comparison."""

    def test_loads_full_build(self, populated_db: BuildDatabase):
        """Loads comparison with all data."""
        comp = load_build_comparison("BUILD_FULL")

        assert comp is not None
        assert comp.build_id == "BUILD_FULL"
        assert comp.design_name == "Carlos Jumbo"
        assert len(comp.modes) == 4

        t1 = next(m for m in comp.modes if m.mode_name == "T1")
        assert t1.predicted_hz == 180.0
        assert t1.measured_hz == 175.0
        assert t1.residual_hz == -5.0

    def test_loads_predictions_only(self, populated_db: BuildDatabase):
        """Loads build with only predictions."""
        comp = load_build_comparison("BUILD_PRED_ONLY")

        assert comp is not None
        assert comp.has_predictions is True
        assert comp.has_measurements is False

        t1 = next(m for m in comp.modes if m.mode_name == "T1")
        assert t1.predicted_hz == 160.0
        assert t1.measured_hz is None

    def test_returns_none_for_missing_build(self, populated_db: BuildDatabase):
        """Returns None for nonexistent build."""
        comp = load_build_comparison("NONEXISTENT")
        assert comp is None

    def test_returns_none_when_no_db(self, tmp_path: Path, monkeypatch):
        """Returns None when database doesn't exist."""
        monkeypatch.setenv("TTP_BUILDS_DB_PATH", str(tmp_path / "missing.json"))
        comp = load_build_comparison("ANY_BUILD")
        assert comp is None


class TestGetPredictedModeFrequencies:
    """Tests for get_predicted_mode_frequencies."""

    def test_returns_dict(self, populated_db: BuildDatabase):
        """Returns dict of mode -> predicted Hz."""
        result = get_predicted_mode_frequencies("BUILD_FULL")

        assert result["T1"] == 180.0
        assert result["A0"] == 100.0
        assert result["T2"] == 280.0
        assert result["T3"] == 350.0

    def test_excludes_none_values(self, populated_db: BuildDatabase):
        """Excludes modes with None predicted values."""
        result = get_predicted_mode_frequencies("BUILD_PRED_ONLY")

        assert "T1" in result
        assert "A0" in result
        assert "T2" not in result
        assert "T3" not in result

    def test_empty_dict_for_missing_build(self, populated_db: BuildDatabase):
        """Returns empty dict for missing build."""
        result = get_predicted_mode_frequencies("NONEXISTENT")
        assert result == {}


class TestGetMeasuredModeFrequencies:
    """Tests for get_measured_mode_frequencies."""

    def test_returns_dict(self, populated_db: BuildDatabase):
        """Returns dict of mode -> measured Hz."""
        result = get_measured_mode_frequencies("BUILD_FULL")

        assert result["T1"] == 175.0
        assert result["A0"] == 102.0
        assert result["T2"] == 275.0
        assert result["T3"] == 345.0

    def test_empty_dict_for_no_measurements(self, populated_db: BuildDatabase):
        """Returns empty dict when no measurements."""
        result = get_measured_mode_frequencies("BUILD_PRED_ONLY")
        assert result == {}

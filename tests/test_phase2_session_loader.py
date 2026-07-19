"""
Tests for Phase 2 session loader.

DO-005 Stage A acceptance tests:
- Load synthetic session directory
- Handle missing required files
- Handle invalid/malformed JSON
- Handle schema version mismatch
- Handle empty or mismatched arrays
- Optional fields (coherence, wsi_curve)
- Query methods (peak_response_freq, amplitude_at_freq, etc.)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analyzer.loaders.phase2_session import (
    Phase2Session,
    Phase2SessionLoadError,
    load_phase2_session,
    try_discover_build_record,
)


@pytest.fixture
def valid_session_dir(tmp_path: Path) -> Path:
    """Create a valid synthetic session directory."""
    session_dir = tmp_path / "session_test"
    session_dir.mkdir()
    (session_dir / "derived").mkdir()

    # grid.json
    grid = {
        "schema_version": "phase2_grid_v1",
        "units": "mm",
        "origin": {"x": 0.0, "y": 0.0},
        "spacing": 10.0,
    }
    (session_dir / "grid.json").write_text(json.dumps(grid), encoding="utf-8")

    # session_meta.json
    meta = {
        "schema_version": "phase2_session_meta_v1",
        "session_id": "test_session_001",
        "build_id": "TEST_BUILD_001",
        "created_at": "2026-05-02T12:00:00Z",
    }
    (session_dir / "session_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # derived/ods_snapshot.json with 4 points, 5 frequencies
    freqs = [100.0, 200.0, 300.0, 400.0, 500.0]
    points = [
        {
            "point_id": "P00",
            "x_mm": 0.0,
            "y_mm": 0.0,
            "H_mag": [1.0, 2.0, 3.0, 2.0, 1.0],
            "H_phase_deg": [0.0, 10.0, 20.0, 30.0, 40.0],
            "coherence": [0.9, 0.95, 0.98, 0.95, 0.9],
        },
        {
            "point_id": "P01",
            "x_mm": 10.0,
            "y_mm": 0.0,
            "H_mag": [1.5, 2.5, 4.0, 2.5, 1.5],
            "H_phase_deg": [5.0, 15.0, 25.0, 35.0, 45.0],
            "coherence": [0.85, 0.9, 0.95, 0.9, 0.85],
        },
        {
            "point_id": "P10",
            "x_mm": 0.0,
            "y_mm": 10.0,
            "H_mag": [0.8, 1.8, 2.8, 1.8, 0.8],
            "H_phase_deg": [-5.0, 5.0, 15.0, 25.0, 35.0],
            "coherence": [0.88, 0.92, 0.96, 0.92, 0.88],
        },
        {
            "point_id": "P11",
            "x_mm": 10.0,
            "y_mm": 10.0,
            "H_mag": [1.2, 2.2, 3.5, 2.2, 1.2],
            "H_phase_deg": [2.0, 12.0, 22.0, 32.0, 42.0],
            "coherence": [0.87, 0.93, 0.97, 0.93, 0.87],
        },
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


class TestLoadPhase2SessionSuccess:
    """Tests for successful loading of Phase 2 sessions."""

    def test_loads_valid_session(self, valid_session_dir: Path):
        """Loading a valid synthetic session succeeds."""
        session = load_phase2_session(valid_session_dir)

        assert session.session_dir == valid_session_dir
        assert session.n_points == 4
        assert session.n_freqs == 5
        assert session.build_id == "TEST_BUILD_001"
        assert len(session.freqs_hz) == 5
        assert session.freqs_hz[0] == 100.0
        assert session.freqs_hz[-1] == 500.0

    def test_loads_point_data(self, valid_session_dir: Path):
        """Point data is correctly loaded."""
        session = load_phase2_session(valid_session_dir)

        p00 = next(p for p in session.points if p.point_id == "P00")
        assert p00.x_mm == 0.0
        assert p00.y_mm == 0.0
        assert len(p00.H_mag) == 5
        assert p00.H_mag[2] == 3.0  # peak at 300 Hz
        assert p00.coherence is not None
        assert len(p00.coherence) == 5

    def test_loads_grid_meta(self, valid_session_dir: Path):
        """Grid metadata is loaded."""
        session = load_phase2_session(valid_session_dir)

        assert session.grid_meta["units"] == "mm"
        assert session.grid_meta["spacing"] == 10.0

    def test_loads_session_meta(self, valid_session_dir: Path):
        """Session metadata is loaded."""
        session = load_phase2_session(valid_session_dir)

        assert session.session_meta["session_id"] == "test_session_001"


class TestLoadPhase2SessionMissingFiles:
    """Tests for missing required files."""

    def test_missing_grid_json(self, valid_session_dir: Path):
        """Missing grid.json raises Phase2SessionLoadError."""
        (valid_session_dir / "grid.json").unlink()

        with pytest.raises(Phase2SessionLoadError, match="grid.json"):
            load_phase2_session(valid_session_dir)

    def test_missing_session_meta(self, valid_session_dir: Path):
        """Missing session_meta.json raises Phase2SessionLoadError."""
        (valid_session_dir / "session_meta.json").unlink()

        with pytest.raises(Phase2SessionLoadError, match="session_meta.json"):
            load_phase2_session(valid_session_dir)

    def test_missing_ods_snapshot(self, valid_session_dir: Path):
        """Missing derived/ods_snapshot.json raises Phase2SessionLoadError."""
        (valid_session_dir / "derived" / "ods_snapshot.json").unlink()

        with pytest.raises(Phase2SessionLoadError, match="ods_snapshot.json"):
            load_phase2_session(valid_session_dir)

    def test_not_a_directory(self, tmp_path: Path):
        """Non-directory path raises Phase2SessionLoadError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")

        with pytest.raises(Phase2SessionLoadError, match="Not a directory"):
            load_phase2_session(file_path)


class TestLoadPhase2SessionInvalidData:
    """Tests for invalid or malformed data."""

    def test_invalid_json(self, valid_session_dir: Path):
        """Invalid JSON raises Phase2SessionLoadError."""
        (valid_session_dir / "grid.json").write_text("{invalid json", encoding="utf-8")

        with pytest.raises(Phase2SessionLoadError, match="Invalid JSON"):
            load_phase2_session(valid_session_dir)

    def test_wrong_schema_version(self, valid_session_dir: Path):
        """Wrong ods_snapshot schema_version raises Phase2SessionLoadError."""
        snapshot_path = valid_session_dir / "derived" / "ods_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["schema_version"] = "wrong_schema_v1"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        with pytest.raises(Phase2SessionLoadError, match="schema_version"):
            load_phase2_session(valid_session_dir)

    def test_empty_freqs_hz(self, valid_session_dir: Path):
        """Empty freqs_hz raises Phase2SessionLoadError."""
        snapshot_path = valid_session_dir / "derived" / "ods_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["freqs_hz"] = []
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        with pytest.raises(Phase2SessionLoadError, match="empty freqs_hz"):
            load_phase2_session(valid_session_dir)

    def test_mismatched_array_lengths(self, valid_session_dir: Path):
        """Mismatched H_mag length raises Phase2SessionLoadError."""
        snapshot_path = valid_session_dir / "derived" / "ods_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["points"][0]["H_mag"] = [1.0, 2.0, 3.0]  # 3 instead of 5
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        with pytest.raises(Phase2SessionLoadError, match="H_mag length"):
            load_phase2_session(valid_session_dir)

    def test_no_points(self, valid_session_dir: Path):
        """Empty points list raises Phase2SessionLoadError."""
        snapshot_path = valid_session_dir / "derived" / "ods_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["points"] = []
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        with pytest.raises(Phase2SessionLoadError, match="no points"):
            load_phase2_session(valid_session_dir)


class TestLoadPhase2SessionOptionalFields:
    """Tests for optional fields."""

    def test_missing_coherence_loads_ok(self, valid_session_dir: Path):
        """Missing coherence field loads with coherence=None."""
        snapshot_path = valid_session_dir / "derived" / "ods_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        for pt in snapshot["points"]:
            del pt["coherence"]
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        session = load_phase2_session(valid_session_dir)

        for point in session.points:
            assert point.coherence is None

    def test_wsi_curve_loaded_when_present(self, valid_session_dir: Path):
        """Optional wsi_curve.json is loaded when present."""
        wsi_curve = {
            "schema_version": "wsi_curve_v1",
            "freqs_hz": [100.0, 200.0, 300.0],
            "wsi_values": [0.5, 0.8, 0.6],
        }
        (valid_session_dir / "derived" / "wsi_curve.json").write_text(
            json.dumps(wsi_curve), encoding="utf-8"
        )

        session = load_phase2_session(valid_session_dir)

        assert session.wsi_curve is not None
        assert session.wsi_curve["freqs_hz"] == [100.0, 200.0, 300.0]

    def test_wsi_curve_none_when_missing(self, valid_session_dir: Path):
        """wsi_curve is None when file not present."""
        session = load_phase2_session(valid_session_dir)
        assert session.wsi_curve is None

    def test_build_id_from_instrument_id(self, valid_session_dir: Path):
        """build_id falls back to instrument_id if build_id not present."""
        meta_path = valid_session_dir / "session_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        del meta["build_id"]
        meta["instrument_id"] = "FALLBACK_INSTRUMENT_001"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        session = load_phase2_session(valid_session_dir)

        assert session.build_id == "FALLBACK_INSTRUMENT_001"


class TestPhase2SessionQueryMethods:
    """Tests for Phase2Session query methods."""

    def test_peak_response_freq(self, valid_session_dir: Path):
        """peak_response_freq returns frequency of maximum mean amplitude."""
        session = load_phase2_session(valid_session_dir)

        # All points have peak at 300 Hz (index 2)
        peak_freq = session.peak_response_freq()
        assert peak_freq == 300.0

    def test_amplitude_at_freq_interpolates(self, valid_session_dir: Path):
        """amplitude_at_freq interpolates between frequency bins."""
        session = load_phase2_session(valid_session_dir)

        # 250 Hz is between 200 Hz and 300 Hz
        result = session.amplitude_at_freq(250.0)

        # P00: H_mag at 200 Hz is 2.0, at 300 Hz is 3.0 -> interpolate to 2.5
        assert result["P00"] == pytest.approx(2.5, rel=1e-6)

    def test_amplitude_at_freq_exact(self, valid_session_dir: Path):
        """amplitude_at_freq returns exact value at frequency bin."""
        session = load_phase2_session(valid_session_dir)

        result = session.amplitude_at_freq(300.0)

        assert result["P00"] == 3.0
        assert result["P01"] == 4.0

    def test_amplitude_at_freq_index(self, valid_session_dir: Path):
        """amplitude_at_freq_index returns exact value at index."""
        session = load_phase2_session(valid_session_dir)

        result = session.amplitude_at_freq_index(2)  # 300 Hz

        assert result["P00"] == 3.0
        assert result["P01"] == 4.0
        assert result["P10"] == 2.8
        assert result["P11"] == 3.5

    def test_phase_at_freq_index(self, valid_session_dir: Path):
        """phase_at_freq_index returns phase values at index."""
        session = load_phase2_session(valid_session_dir)

        result = session.phase_at_freq_index(2)  # 300 Hz

        assert result["P00"] == 20.0
        assert result["P01"] == 25.0

    def test_get_point_coords(self, valid_session_dir: Path):
        """get_point_coords returns list of (point_id, x, y) tuples."""
        session = load_phase2_session(valid_session_dir)

        coords = session.get_point_coords()

        assert len(coords) == 4
        assert ("P00", 0.0, 0.0) in coords
        assert ("P11", 10.0, 10.0) in coords

    def test_peak_response_freq_empty_session(self, tmp_path: Path):
        """peak_response_freq returns 0.0 for edge case of no data."""
        # Create minimal valid session that passes loading
        session = Phase2Session(
            session_dir=tmp_path,
            session_meta={},
            grid_meta={},
            freqs_hz=np.array([]),
            points=[],
        )

        assert session.peak_response_freq() == 0.0


class TestTryDiscoverBuildRecord:
    """Tests for try_discover_build_record."""

    def test_returns_none_when_no_build_id(self, valid_session_dir: Path):
        """Returns None when session has no build_id."""
        meta_path = valid_session_dir / "session_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        del meta["build_id"]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        session = load_phase2_session(valid_session_dir)
        session.build_id = None

        result = try_discover_build_record(session)
        assert result is None

    def test_returns_none_when_db_missing(self, valid_session_dir: Path, monkeypatch):
        """Returns None when builds_db.json doesn't exist."""
        # Point to a nonexistent path
        monkeypatch.setenv("TTP_BUILDS_DB_PATH", "/nonexistent/builds_db.json")

        session = load_phase2_session(valid_session_dir)

        result = try_discover_build_record(session)
        assert result is None

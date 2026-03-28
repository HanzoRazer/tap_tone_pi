"""
Tests for tap_tone_pi.server.app module.

Tests cover:
- App creation
- Health endpoint
- Device listing
- Calibration status
- Grid listing
- Session listing
- CLI integration
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Check if FastAPI is available
try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import create_app, app, HAS_FASTAPI, add_server_subcommand
    SKIP_REASON = "FastAPI not installed"  # placeholder, tests won't skip
except ImportError:
    SKIP_REASON = "FastAPI not installed"
    HAS_FASTAPI = False
    app = None
    create_app = None


# --- Fixtures ---

@pytest.fixture
def client():
    """Create test client."""
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed")

    return TestClient(app)


@pytest.fixture
def sample_grid_dir(tmp_path):
    """Create sample grid directory."""
    grids_dir = tmp_path / "grids"
    grids_dir.mkdir()

    # Create sample grid
    grid_data = {
        "name": "Test Grid",
        "units": "mm",
        "origin": "center",
        "points": [
            {"id": "A1", "x": 0, "y": 0},
            {"id": "A2", "x": 50, "y": 0},
        ],
    }

    with open(grids_dir / "test_grid.json", "w") as f:
        json.dump(grid_data, f)

    return grids_dir


@pytest.fixture
def sample_session_dir(tmp_path):
    """Create sample session directory."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    # Create sample session
    session_dir = sessions_dir / "session_20260328T100000Z"
    session_dir.mkdir()

    state_data = {
        "schema_version": "session_state_v1",
        "grid_path": "test_grid.json",
        "started_at_utc": "2026-03-28T10:00:00Z",
        "last_updated_utc": "2026-03-28T10:30:00Z",
        "is_complete": False,
        "points": {
            "A1": {"status": "captured", "coherence": 0.95},
            "A2": {"status": "pending"},
        },
    }

    with open(session_dir / "session_state.json", "w") as f:
        json.dump(state_data, f)

    return sessions_dir


# --- App Creation Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestAppCreation:
    """Tests for app creation."""

    def test_create_app_returns_fastapi(self):
        """create_app should return FastAPI instance."""
        from fastapi import FastAPI

        test_app = create_app()

        assert isinstance(test_app, FastAPI)

    def test_app_has_docs(self, client):
        """App should have OpenAPI docs."""
        response = client.get("/docs")

        # Docs redirect or return HTML
        assert response.status_code in (200, 307)

    def test_app_has_openapi_json(self, client):
        """App should have OpenAPI JSON schema."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


# --- Health Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return ok status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_includes_version(self, client):
        """Health endpoint should include version."""
        response = client.get("/health")

        data = response.json()
        assert "version" in data

    def test_health_includes_timestamp(self, client):
        """Health endpoint should include timestamp."""
        response = client.get("/health")

        data = response.json()
        assert "timestamp" in data


# --- Info Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestInfoEndpoint:
    """Tests for /info endpoint."""

    def test_info_returns_system_info(self, client):
        """Info endpoint should return system info."""
        response = client.get("/info")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "tap_tone_pi"

    def test_info_includes_dsp_provenance(self, client):
        """Info endpoint should include DSP provenance."""
        response = client.get("/info")

        data = response.json()
        assert "dsp" in data
        assert "algo_id" in data["dsp"]


# --- Devices Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestDevicesEndpoint:
    """Tests for /devices endpoint."""

    def test_devices_returns_list(self, client):
        """Devices endpoint should return list."""
        response = client.get("/devices")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_devices_have_required_fields(self, client):
        """Device objects should have required fields."""
        response = client.get("/devices")

        data = response.json()
        if len(data) > 0:
            device = data[0]
            assert "index" in device
            assert "name" in device
            assert "sample_rate" in device


# --- Calibration Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestCalibrationEndpoint:
    """Tests for /calibration/{device_index} endpoint."""

    @patch("tap_tone_pi.server.app.load_calibration")
    @patch("tap_tone_pi.server.app.get_calibration_status")
    def test_calibration_uncalibrated(self, mock_status, mock_load, client):
        """Should return uncalibrated status."""
        from tap_tone_pi.calibration.storage import CalibrationStatus

        mock_load.return_value = None
        mock_status.return_value = CalibrationStatus.UNCALIBRATED

        response = client.get("/calibration/0")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "uncalibrated"
        assert data["device_index"] == 0

    @patch("tap_tone_pi.server.app.load_calibration")
    @patch("tap_tone_pi.server.app.get_calibration_status")
    @patch("tap_tone_pi.server.app.is_calibration_stale")
    def test_calibration_valid(self, mock_stale, mock_status, mock_load, client):
        """Should return valid calibration status."""
        from tap_tone_pi.calibration.storage import CalibrationStatus, CalibrationData

        mock_status.return_value = CalibrationStatus.VALID
        mock_stale.return_value = False
        mock_load.return_value = CalibrationData(
            device_index=1,
            device_name="Test Device",
            calibrated_at="2026-03-15T10:00:00Z",
            loopback_latency_ms=15.5,
            amplitude_error_db=-0.3,
            loopback_completed=True,
            reference_tone_completed=True,
        )

        response = client.get("/calibration/1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "valid"
        assert data["latency_ms"] == 15.5


# --- Grids Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestGridsEndpoint:
    """Tests for /grids endpoint."""

    def test_grids_empty_directory(self, client, tmp_path):
        """Should return empty list for nonexistent directory."""
        response = client.get(f"/grids?directory={tmp_path / 'nonexistent'}")

        assert response.status_code == 200
        assert response.json() == []

    def test_grids_with_files(self, client, sample_grid_dir):
        """Should return grid info for valid grids."""
        response = client.get(f"/grids?directory={sample_grid_dir}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Grid"
        assert data[0]["point_count"] == 2


# --- Sessions Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestSessionsEndpoint:
    """Tests for /sessions endpoint."""

    def test_sessions_empty_directory(self, client, tmp_path):
        """Should return empty list for nonexistent directory."""
        response = client.get(f"/sessions?directory={tmp_path / 'nonexistent'}")

        assert response.status_code == 200
        assert response.json() == []

    def test_sessions_with_data(self, client, sample_session_dir):
        """Should return session info."""
        response = client.get(f"/sessions?directory={sample_session_dir}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["session_id"] == "session_20260328T100000Z"
        assert data[0]["captured"] == 1
        assert data[0]["pending"] == 1

    def test_session_detail(self, client, sample_session_dir):
        """Should return detailed session info."""
        response = client.get(
            f"/sessions/session_20260328T100000Z?directory={sample_session_dir}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "points" in data

    def test_session_not_found(self, client, sample_session_dir):
        """Should return 404 for nonexistent session."""
        response = client.get(
            f"/sessions/nonexistent?directory={sample_session_dir}"
        )

        assert response.status_code == 404


# --- Analysis Endpoint Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestAnalysisEndpoint:
    """Tests for /analyze endpoint."""

    def test_analyze_missing_input(self, client):
        """Should require wav_path or wav_base64."""
        response = client.post("/analyze", json={})

        assert response.status_code == 400

    def test_analyze_file_not_found(self, client, tmp_path):
        """Should return 404 for nonexistent file."""
        response = client.post("/analyze", json={
            "wav_path": str(tmp_path / "nonexistent.wav"),
        })

        assert response.status_code == 404


# --- CLI Tests ---

@pytest.mark.skipif(not HAS_FASTAPI, reason=SKIP_REASON)
class TestCLIIntegration:
    """Tests for CLI integration."""

    def test_add_server_subcommand(self):
        """Should add server subcommand."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()

        add_server_subcommand(subparsers)

        args = parser.parse_args(["server", "--port", "9000"])

        assert args.port == 9000

    def test_server_default_args(self):
        """Should have sensible defaults."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_server_subcommand(subparsers)

        args = parser.parse_args(["server"])

        assert args.host == "0.0.0.0"
        assert args.port == 8000
        assert args.reload is False

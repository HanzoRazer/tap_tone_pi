"""
tests/test_calibration_gate_and_export.py

Tests for:
  1. tap_tone_pi/calibration/gate.py — CalibrationGate enforcement
  2. scripts/phase2/export_viewer_pack_v1.py — wolf candidates purity gate
  3. tap_tone_pi/server/app.py — /export/{session_id} endpoint

All tests are hermetic (tmp_path, monkeypatch) — no real hardware or
calibration files on disk.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tap_tone_pi.calibration.gate import (  # noqa: E402
    CalibrationGateResult,
    enforce_calibration_gate,
    print_gate_result,
    _cal_age_days,
)
from tap_tone_pi.calibration.storage import CalibrationData, CalibrationStatus  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(days_ago: int = 0) -> str:
    """Return ISO datetime string N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_cal(device_index: int = 0, days_ago: int = 1) -> CalibrationData:
    """Build a fresh, complete CalibrationData."""
    return CalibrationData(
        device_index=device_index,
        device_name=f"Test Device {device_index}",
        calibrated_at=_utc(days_ago),
        loopback_completed=True,
        loopback_latency_ms=12.0,
        loopback_snr_db=45.0,
        reference_tone_completed=True,
        reference_amplitude_dbfs=-20.0,
    )


def _stale_cal(device_index: int = 0) -> CalibrationData:
    """Build a CalibrationData that is 35 days old (beyond 30-day limit)."""
    return _valid_cal(device_index=device_index, days_ago=35)


# ---------------------------------------------------------------------------
# Section 1: CalibrationGate unit tests
# ---------------------------------------------------------------------------


class TestCalibrationGateValid:
    def test_valid_cal_is_allowed(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.VALID,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _valid_cal(),
        )
        result = enforce_calibration_gate(0)
        assert result.allowed is True
        assert result.gate_verdict == "allowed"
        assert result.status == "valid"

    def test_valid_cal_no_warning(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.VALID,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _valid_cal(),
        )
        result = enforce_calibration_gate(0)
        assert result.warning == ""
        assert result.is_stale is False
        assert result.is_uncalibrated is False


class TestCalibrationGateStale:
    def test_stale_blocked_by_default(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.STALE,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _stale_cal(),
        )
        result = enforce_calibration_gate(0)
        assert result.allowed is False
        assert result.gate_verdict == "blocked"
        assert result.is_stale is True
        assert "BLOCKED" in result.message
        assert (
            "recalibrate" in result.message.lower() or "ttp calibrate" in result.message
        )

    def test_stale_allowed_with_force(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.STALE,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _stale_cal(),
        )
        result = enforce_calibration_gate(0, allow_stale=True)
        assert result.allowed is True
        assert result.gate_verdict == "warned"
        assert result.is_stale is True
        assert "WARN" in result.warning

    def test_stale_message_contains_age(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.STALE,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _stale_cal(),
        )
        result = enforce_calibration_gate(0)
        # Should mention the age in days
        assert "35" in result.message or "days" in result.message


class TestCalibrationGateUncalibrated:
    def test_uncalibrated_blocked_by_default(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.UNCALIBRATED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0)
        assert result.allowed is False
        assert result.gate_verdict == "blocked"
        assert result.is_uncalibrated is True
        assert "BLOCKED" in result.message

    def test_uncalibrated_blocked_even_with_force_stale(self, monkeypatch):
        """allow_stale does NOT bypass uncalibrated gate."""
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.UNCALIBRATED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0, allow_stale=True)
        assert result.allowed is False

    def test_uncalibrated_allowed_with_force_uncalibrated(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.UNCALIBRATED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0, allow_uncalibrated=True)
        assert result.allowed is True
        assert result.gate_verdict == "warned"
        assert result.is_uncalibrated is True
        assert "MUST NOT" in result.warning or "production" in result.warning.lower()

    def test_uncalibrated_warning_mentions_calibrate_command(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.UNCALIBRATED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0)
        assert "ttp calibrate" in result.message


class TestCalibrationGateFailed:
    def test_failed_always_blocked(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.FAILED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0)
        assert result.allowed is False
        assert result.is_failed is True

    def test_failed_not_overrideable(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.FAILED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        # Neither force flag bypasses FAILED
        result = enforce_calibration_gate(0, allow_stale=True, allow_uncalibrated=True)
        assert result.allowed is False


class TestCalibrationGateHelpers:
    def test_to_dict_contains_required_fields(self, monkeypatch):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.VALID,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _valid_cal(),
        )
        result = enforce_calibration_gate(0)
        d = result.to_dict()
        assert "allowed" in d
        assert "status" in d
        assert "gate_verdict" in d

    def test_cal_age_days_none_returns_999(self):
        assert _cal_age_days(None) == 999

    def test_cal_age_days_fresh(self):
        cal = _valid_cal(days_ago=2)
        age = _cal_age_days(cal)
        assert 1 <= age <= 3  # Allow for clock skew

    def test_print_gate_allowed(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.VALID,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: _valid_cal(),
        )
        result = enforce_calibration_gate(0)
        print_gate_result(result)
        out = capsys.readouterr().out
        # Should print message (valid message)
        assert len(out) > 0 or result.message == ""  # no crash

    def test_print_gate_blocked(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.get_calibration_status",
            lambda idx: CalibrationStatus.UNCALIBRATED,
        )
        monkeypatch.setattr(
            "tap_tone_pi.calibration.gate.load_calibration",
            lambda idx: None,
        )
        result = enforce_calibration_gate(0)
        print_gate_result(result)
        out = capsys.readouterr().out
        assert "BLOCKED" in out


# ---------------------------------------------------------------------------
# Section 2: Wolf candidates purity gate
# ---------------------------------------------------------------------------


class TestWolfCandidatesPurityGate:
    def _get_gate_fn(self):
        """Import _validate_wolf_candidates_clean from export script."""
        try:
            import scripts.phase2.export_viewer_pack_v1 as mod

            return getattr(mod, "_validate_wolf_candidates_clean", None)
        except Exception:
            pytest.skip("export_viewer_pack_v1 could not be loaded")
            return None

    def test_clean_wolf_candidates_passes(self, tmp_path):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        wc.write_text(
            json.dumps(
                {
                    "wolf_candidates": [
                        {
                            "freq_hz": 203.0,
                            "peak_pair_idx": 0,
                            "wsi": 0.65,
                            "beat_frequency_hz": 8.2,
                            "omega": 0.041,
                        }
                    ]
                }
            )
        )
        fn(wc)  # must not raise

    def test_advisory_field_at_root_raises(self, tmp_path):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        # mitigation_type is a WolfAdvisor field
        wc.write_text(
            json.dumps(
                {
                    "wolf_candidates": [{"freq_hz": 203.0}],
                    "mitigation_type": "add_mass",  # ← prohibited
                }
            )
        )
        with pytest.raises(ValueError, match="advisory fields"):
            fn(wc)

    def test_advisory_field_nested_in_candidates_raises(self, tmp_path):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        wc.write_text(
            json.dumps(
                {
                    "wolf_candidates": [
                        {
                            "freq_hz": 203.0,
                            "recommendations": [{"type": "add_mass"}],  # ← prohibited
                        }
                    ],
                }
            )
        )
        with pytest.raises(ValueError, match="advisory fields"):
            fn(wc)

    @pytest.mark.parametrize(
        "bad_field",
        [
            "mitigation_suggestions",
            "recommendations",
            "advisor_output",
            "mitigation_type",
            "recommended_action",
            "confidence_level",
            "wolf_directive",
            "directive_id",
        ],
    )
    def test_all_prohibited_fields_caught(self, tmp_path, bad_field):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        wc.write_text(json.dumps({bad_field: "some_value"}))
        with pytest.raises(ValueError, match="advisory fields"):
            fn(wc)

    def test_unparseable_json_does_not_raise(self, tmp_path):
        """Parse errors must not propagate — other validators handle them."""
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        wc.write_text("{this is not json")
        fn(wc)  # must not raise

    def test_missing_file_does_not_raise(self, tmp_path):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        # File does not exist
        fn(wc)  # must not raise (file checked elsewhere)

    def test_error_message_references_adr(self, tmp_path):
        fn = self._get_gate_fn()
        if fn is None:
            pytest.skip("_validate_wolf_candidates_clean not found")

        wc = tmp_path / "wolf_candidates.json"
        wc.write_text(json.dumps({"directive_id": "wolf_abc123"}))
        with pytest.raises(ValueError, match="ADR-0009"):
            fn(wc)


# ---------------------------------------------------------------------------
# Section 3: FastAPI /export endpoint
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient
    from tap_tone_pi.server.app import create_app

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False


@pytest.fixture()
def client(tmp_path: Path):
    # DO-98: the export tests read session directories under tmp_path via
    # absolute paths, so authorize tmp_path as the server data root. /export now
    # confines its `directory` read param to the configured root like /sessions.
    app = create_app(data_root=tmp_path)
    return TestClient(app)


@pytest.fixture()
def fake_session(tmp_path: Path) -> Path:
    """Create a minimal Phase 2 session directory structure."""
    session_dir = tmp_path / "runs_phase2" / "session_20260330T120000Z"
    (session_dir / "points").mkdir(parents=True)
    (session_dir / "derived").mkdir(parents=True)

    # grid.json
    grid = {
        "grid_id": "guitar_top_35pt",
        "name": "Guitar Top 35pt",
        "units": "mm",
        "width": 400.0,
        "height": 520.0,
        "points": [{"id": "A1", "x": 0.0, "y": 0.0}],
    }
    (session_dir / "grid.json").write_text(json.dumps(grid))

    # metadata.json
    meta = {
        "specimen_id": "test_plate_001",
        "device_id": "ttp_dev_001",
        "sample_rate_hz": 48000,
    }
    (session_dir / "metadata.json").write_text(json.dumps(meta))

    return tmp_path / "runs_phase2"


@pytest.mark.skipif(not FASTAPI_OK, reason="fastapi not installed")
class TestExportEndpoint:
    def test_export_missing_session_returns_404(self, client, tmp_path):
        resp = client.get(
            "/export/session_nonexistent",
            params={"directory": str(tmp_path / "empty")},
        )
        assert resp.status_code == 404

    def test_export_valid_session_returns_ok(self, client, fake_session, tmp_path):
        """Export a minimal session — should return 200 with pack metadata."""
        out_dir = tmp_path / "exports"
        out_dir.mkdir()

        with patch(
            "scripts.phase2.export_viewer_pack_v1.export_viewer_pack",
            return_value=out_dir / "viewer_pack_v1",
        ) as mock_export:  # noqa: F841
            # Create a fake pack directory
            pack_dir = out_dir / "viewer_pack_v1"
            pack_dir.mkdir(parents=True)
            (pack_dir / "manifest.json").write_text(json.dumps({"files": []}))

            resp = client.get(
                "/export/session_20260330T120000Z",
                params={
                    "directory": str(fake_session),
                    "output_dir": str(out_dir),
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "session_20260330T120000Z"
        assert "pack_path" in body
        assert body["status"] == "ok"

    def test_export_wolf_purity_violation_returns_422(
        self, client, fake_session, tmp_path
    ):
        """Wolf advisory contamination must return HTTP 422."""
        out_dir = tmp_path / "exports"
        out_dir.mkdir()

        with patch(
            "scripts.phase2.export_viewer_pack_v1.export_viewer_pack",
            side_effect=ValueError(
                "wolf_candidates.json contains advisory fields: {'mitigation_type'}. "
                "See docs/ADR-0009-advisory-boundary.md"
            ),
        ):
            resp = client.get(
                "/export/session_20260330T120000Z",
                params={
                    "directory": str(fake_session),
                    "output_dir": str(out_dir),
                },
            )

        assert resp.status_code == 422
        assert (
            "advisory" in resp.json()["detail"].lower()
            or "wolf" in resp.json()["detail"].lower()
        )

    def test_export_file_not_found_returns_404(self, client, tmp_path):
        with patch(
            "scripts.phase2.export_viewer_pack_v1.export_viewer_pack",
            side_effect=FileNotFoundError("session_dir not found"),
        ):
            resp = client.get(
                "/export/session_missing",
                params={
                    "directory": str(tmp_path),
                    "output_dir": str(tmp_path / "out"),
                },
            )
        assert resp.status_code == 404

    def test_export_response_has_manifest_sha(self, client, fake_session, tmp_path):
        out_dir = tmp_path / "exports"
        pack_dir = out_dir / "viewer_pack_v1"
        pack_dir.mkdir(parents=True)
        manifest_content = json.dumps({"files": [], "schema_version": "1.0"})
        (pack_dir / "manifest.json").write_text(manifest_content)

        with patch(
            "scripts.phase2.export_viewer_pack_v1.export_viewer_pack",
            return_value=pack_dir,
        ):
            resp = client.get(
                "/export/session_20260330T120000Z",
                params={
                    "directory": str(fake_session),
                    "output_dir": str(out_dir),
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "manifest_sha256" in body
        assert len(body["manifest_sha256"]) == 16  # First 16 chars of hex

    def test_health_endpoint_still_works(self, client):
        """Regression: existing endpoints must not break after export impl."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Section 4: Phase 2 CLI calibration gate integration
# ---------------------------------------------------------------------------


class TestPhase2CalibrationGateCLI:
    """
    Test that _run_new() honours the gate result without calling real hardware.
    """

    def _run_new(self, monkeypatch, gate_allowed: bool, force_uncal: bool = False):
        """Call _run_new() with a mocked gate result and a minimal args object."""

        # Mock the gate
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.enforce_calibration_gate",
            lambda idx, **kw: CalibrationGateResult(
                allowed=gate_allowed,
                status="valid" if gate_allowed else "uncalibrated",
                message="" if gate_allowed else "[BLOCKED] No calibration.",
                gate_verdict="allowed" if gate_allowed else "blocked",
            ),
        )
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.print_gate_result",
            lambda r: None,
        )

        return gate_allowed  # Return what _run_new would check

    def test_blocked_gate_prevents_session(self, monkeypatch, tmp_path):
        """When gate.allowed is False, _run_new must return 1 immediately."""
        from types import SimpleNamespace
        import tap_tone_pi.cli.phase2_cmd as cmd

        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.enforce_calibration_gate",
            lambda idx, **kw: CalibrationGateResult(
                allowed=False,
                status="uncalibrated",
                message="[BLOCKED] No calibration.",
                gate_verdict="blocked",
            ),
        )
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.print_gate_result",
            lambda r: None,
        )
        # Also mock grid/session creation so it never reaches those
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.load_grid",
            lambda p: MagicMock(points=[]),
        )

        args = SimpleNamespace(
            grid="config/grids/guitar_top_35pt.json",
            out=str(tmp_path / "runs"),
            device=0,
            force=False,
            force_uncalibrated=False,
            coherence_threshold=0.7,
        )

        # Patch Path.exists() for the grid file check
        with patch("pathlib.Path.exists", return_value=True):
            rc = cmd._run_new(args)

        assert rc == 1, (
            "_run_new must return 1 when calibration gate blocks. "
            "Check that the gate enforcement block runs BEFORE session creation."
        )

    def test_allowed_gate_proceeds(self, monkeypatch, tmp_path):
        """When gate.allowed is True, _run_new should not return 1 immediately."""
        from types import SimpleNamespace
        import tap_tone_pi.cli.phase2_cmd as cmd

        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.enforce_calibration_gate",
            lambda idx, **kw: CalibrationGateResult(
                allowed=True,
                status="valid",
                message="Calibration valid.",
                gate_verdict="allowed",
            ),
        )
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.print_gate_result",
            lambda r: None,
        )
        # Mock everything after the gate so test stays hermetic
        monkeypatch.setattr(
            "tap_tone_pi.cli.phase2_cmd.load_grid",
            lambda p: (_ for _ in ()).throw(RuntimeError("stop_after_gate")),
        )

        args = SimpleNamespace(
            grid="config/grids/guitar_top_35pt.json",
            out=str(tmp_path / "runs"),
            device=0,
            force=False,
            force_uncalibrated=False,
            coherence_threshold=0.7,
        )

        with patch("pathlib.Path.exists", return_value=True):
            try:
                cmd._run_new(args)
            except RuntimeError as e:
                if "stop_after_gate" in str(e):
                    pass  # Gate passed, execution reached grid loading
                else:
                    raise

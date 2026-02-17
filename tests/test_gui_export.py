"""Tests for GUI session viewer pack export (Phase 11)."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile


class TestExportResult:
    """ExportResult dataclass tests."""

    def test_export_result_defaults(self):
        """ExportResult has sensible defaults."""
        from tap_tone_pi.gui.export import ExportResult

        result = ExportResult(success=True)
        assert result.success is True
        assert result.output_path is None
        assert result.error is None
        assert result.point_count == 0
        assert result.warnings == []

    def test_export_result_with_warnings(self):
        """ExportResult can hold warnings."""
        from tap_tone_pi.gui.export import ExportResult

        result = ExportResult(
            success=True,
            point_count=3,
            warnings=["Missing audio for point_002"],
        )
        assert result.warnings == ["Missing audio for point_002"]


class TestFindBestAttempt:
    """Tests for _find_best_attempt helper."""

    def test_prefers_pass_over_warn(self, tmp_path: Path):
        """PASS verdict is preferred over WARN."""
        from tap_tone_pi.gui.export import _find_best_attempt

        point_dir = tmp_path / "point_001"
        point_dir.mkdir()

        # Create attempt_001 with WARN
        att1 = point_dir / "attempt_001"
        att1.mkdir()
        (att1 / "quality_check.json").write_text(json.dumps({"verdict": "WARN"}))

        # Create attempt_002 with PASS
        att2 = point_dir / "attempt_002"
        att2.mkdir()
        (att2 / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))

        best = _find_best_attempt(point_dir)
        assert best == att2

    def test_prefers_warn_over_fail(self, tmp_path: Path):
        """WARN verdict is preferred over FAIL."""
        from tap_tone_pi.gui.export import _find_best_attempt

        point_dir = tmp_path / "point_001"
        point_dir.mkdir()

        # Create attempt_001 with FAIL
        att1 = point_dir / "attempt_001"
        att1.mkdir()
        (att1 / "quality_check.json").write_text(json.dumps({"verdict": "FAIL"}))

        # Create attempt_002 with WARN
        att2 = point_dir / "attempt_002"
        att2.mkdir()
        (att2 / "quality_check.json").write_text(json.dumps({"verdict": "WARN"}))

        best = _find_best_attempt(point_dir)
        assert best == att2

    def test_uses_latest_when_same_verdict(self, tmp_path: Path):
        """When verdicts are equal, prefer latest attempt."""
        from tap_tone_pi.gui.export import _find_best_attempt

        point_dir = tmp_path / "point_001"
        point_dir.mkdir()

        # Create two PASS attempts
        att1 = point_dir / "attempt_001"
        att1.mkdir()
        (att1 / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))

        att2 = point_dir / "attempt_002"
        att2.mkdir()
        (att2 / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))

        best = _find_best_attempt(point_dir)
        assert best == att2

    def test_returns_none_when_no_attempts(self, tmp_path: Path):
        """Returns None when no attempts exist."""
        from tap_tone_pi.gui.export import _find_best_attempt

        point_dir = tmp_path / "point_001"
        point_dir.mkdir()

        best = _find_best_attempt(point_dir)
        assert best is None


class TestExportGuiSession:
    """Tests for export_gui_session function."""

    def test_session_not_found(self, tmp_path: Path):
        """Returns error when session directory doesn't exist."""
        from tap_tone_pi.gui.export import export_gui_session

        result = export_gui_session(tmp_path / "nonexistent")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_no_measurement_points(self, tmp_path: Path):
        """Returns error when no measurement points found."""
        from tap_tone_pi.gui.export import export_gui_session

        session_dir = tmp_path / "session_001"
        session_dir.mkdir()

        result = export_gui_session(session_dir)
        assert result.success is False
        assert "no measurement points" in result.error.lower()

    def test_creates_zip_with_manifest(self, tmp_path: Path):
        """Creates ZIP file with viewer_pack.json manifest."""
        from tap_tone_pi.gui.export import export_gui_session

        # Create session with one point
        session_dir = tmp_path / "session_001"
        session_dir.mkdir()

        point_dir = session_dir / "point_001"
        point_dir.mkdir()

        attempt_dir = point_dir / "attempt_001"
        attempt_dir.mkdir()

        # Create minimal files
        (attempt_dir / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))
        (attempt_dir / "analysis.json").write_text(json.dumps({"dominant_hz": 440.0}))

        # Create a minimal WAV file (44 bytes header + some silence)
        import struct

        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
        wav_data += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16)
        wav_data += b"data" + struct.pack("<I", 0)
        (attempt_dir / "audio.wav").write_bytes(wav_data)

        result = export_gui_session(session_dir)

        assert result.success is True
        assert result.output_path is not None
        assert result.output_path.suffix == ".zip"
        assert result.point_count == 1

        # Check ZIP contents
        with ZipFile(result.output_path) as zf:
            names = zf.namelist()
            assert "viewer_pack.json" in names
            assert "audio/points/point_001.wav" in names

            # Parse manifest
            manifest = json.loads(zf.read("viewer_pack.json"))
            assert manifest["schema_id"] == "viewer_pack_v1"
            assert "point_001" in manifest["points"]

    def test_skips_hidden_directories(self, tmp_path: Path):
        """Skips directories starting with _ or ."""
        from tap_tone_pi.gui.export import export_gui_session

        session_dir = tmp_path / "session_001"
        session_dir.mkdir()

        # Create hidden dirs (should be skipped)
        (session_dir / "_internal").mkdir()
        (session_dir / ".hidden").mkdir()

        # Create one valid point
        point_dir = session_dir / "point_001"
        point_dir.mkdir()
        attempt_dir = point_dir / "attempt_001"
        attempt_dir.mkdir()
        (attempt_dir / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))
        (attempt_dir / "analysis.json").write_text(json.dumps({"dominant_hz": 440.0}))

        # Minimal WAV
        import struct

        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
        wav_data += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16)
        wav_data += b"data" + struct.pack("<I", 0)
        (attempt_dir / "audio.wav").write_bytes(wav_data)

        result = export_gui_session(session_dir)

        assert result.success is True
        assert result.point_count == 1

    def test_can_export_as_directory(self, tmp_path: Path):
        """Can export as directory instead of ZIP."""
        from tap_tone_pi.gui.export import export_gui_session

        session_dir = tmp_path / "session_001"
        session_dir.mkdir()

        point_dir = session_dir / "point_001"
        point_dir.mkdir()
        attempt_dir = point_dir / "attempt_001"
        attempt_dir.mkdir()
        (attempt_dir / "quality_check.json").write_text(json.dumps({"verdict": "PASS"}))
        (attempt_dir / "analysis.json").write_text(json.dumps({"dominant_hz": 440.0}))

        # Minimal WAV
        import struct

        wav_data = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
        wav_data += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16)
        wav_data += b"data" + struct.pack("<I", 0)
        (attempt_dir / "audio.wav").write_bytes(wav_data)

        result = export_gui_session(session_dir, as_zip=False)

        assert result.success is True
        assert result.output_path.is_dir()
        assert (result.output_path / "viewer_pack.json").exists()

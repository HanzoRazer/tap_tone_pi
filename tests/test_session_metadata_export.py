"""
Tests for session metadata export functionality (Release A.1 follow-on).

Tests the SessionMetaV1 dataclass and extract_session_metadata() helper.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone.export_metadata import SessionMetaV1, write_session_meta


class TestSessionMetaV1:
    """Test SessionMetaV1 dataclass."""

    def test_default_values(self):
        """SessionMetaV1 has sensible defaults."""
        meta = SessionMetaV1()
        assert meta.schema_id == "tap_tone_session_meta_v1"
        assert meta.specimen_id == ""
        assert meta.run_id == ""
        assert meta.mic_gain_db is None
        assert meta.sample_rate_hz is None

    def test_with_values(self):
        """SessionMetaV1 accepts all fields."""
        meta = SessionMetaV1(
            specimen_id="S-0001",
            run_id="2026-02-07T1200Z_A1",
            device_id="tap-tone-pi-01",
            fixture_id="fixture_v3",
            mic_id="mic_sm57_01",
            mic_gain_db=28.0,
            preamp_model="scarlett_solo",
            sample_rate_hz=48000,
            tap_count=5,
            tap_protocol="center_tap_light",
            ambient_notes="quiet room",
            created_at_utc="2026-02-07T12:00:00Z",
        )
        assert meta.specimen_id == "S-0001"
        assert meta.mic_gain_db == 28.0
        assert meta.tap_count == 5

    def test_is_frozen(self):
        """SessionMetaV1 is immutable (frozen dataclass)."""
        meta = SessionMetaV1(specimen_id="S-0001")
        with pytest.raises(Exception):  # FrozenInstanceError
            meta.specimen_id = "S-0002"


class TestWriteSessionMeta:
    """Test write_session_meta() function."""

    def test_writes_to_meta_dir(self, tmp_path):
        """write_session_meta creates meta/session_meta.json."""
        meta = SessionMetaV1(specimen_id="S-0001", run_id="test_run")
        result = write_session_meta(tmp_path, meta)

        assert result == tmp_path / "meta" / "session_meta.json"
        assert result.exists()

    def test_output_is_valid_json(self, tmp_path):
        """Output file is valid JSON."""
        meta = SessionMetaV1(specimen_id="S-0001")
        result = write_session_meta(tmp_path, meta)

        data = json.loads(result.read_text())
        assert data["schema_id"] == "tap_tone_session_meta_v1"
        assert data["specimen_id"] == "S-0001"

    def test_auto_populates_created_at(self, tmp_path):
        """If created_at_utc is empty, it's auto-populated."""
        meta = SessionMetaV1(specimen_id="S-0001")
        assert meta.created_at_utc == ""

        result = write_session_meta(tmp_path, meta)
        data = json.loads(result.read_text())

        assert data["created_at_utc"] != ""
        assert data["created_at_utc"].endswith("Z")

    def test_preserves_created_at_if_set(self, tmp_path):
        """If created_at_utc is set, it's preserved."""
        meta = SessionMetaV1(
            specimen_id="S-0001",
            created_at_utc="2026-01-01T00:00:00Z",
        )
        result = write_session_meta(tmp_path, meta)
        data = json.loads(result.read_text())

        assert data["created_at_utc"] == "2026-01-01T00:00:00Z"


class TestExtractSessionMetadata:
    """Test extract_session_metadata() helper."""

    def test_extracts_from_metadata_json(self, tmp_path):
        """Extracts fields from metadata.json."""
        # Import here to avoid import errors if export script has missing deps
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        # Create metadata.json
        (tmp_path / "metadata.json").write_text(
            json.dumps(
                {
                    "specimen_id": "S-0001",
                    "device_id": "tap-pi-01",
                    "fixture_id": "fixture_v3",
                    "mic_id": "sm57_01",
                    "mic_gain_db": 28.0,
                    "sample_rate_hz": 48000,
                    "tap_protocol": "center_tap",
                }
            )
        )

        result = extract_session_metadata(tmp_path)

        assert result["specimen_id"] == "S-0001"
        assert result["device_id"] == "tap-pi-01"
        assert result["mic_gain_db"] == 28.0
        assert result["sample_rate_hz"] == 48000

    def test_extracts_tap_count_from_grid(self, tmp_path):
        """Extracts tap_count from grid.json."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        # Create grid.json with 5 points
        (tmp_path / "grid.json").write_text(
            json.dumps(
                {
                    "points": [
                        {"id": "A1", "x": 0, "y": 0},
                        {"id": "A2", "x": 1, "y": 0},
                        {"id": "B1", "x": 0, "y": 1},
                        {"id": "B2", "x": 1, "y": 1},
                        {"id": "C1", "x": 0.5, "y": 0.5},
                    ]
                }
            )
        )

        result = extract_session_metadata(tmp_path)
        assert result["tap_count"] == 5

    def test_counts_point_folders_if_no_grid(self, tmp_path):
        """Falls back to counting point_* folders."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        # Create point folders
        points_dir = tmp_path / "points"
        points_dir.mkdir()
        (points_dir / "point_A1").mkdir()
        (points_dir / "point_A2").mkdir()
        (points_dir / "point_B1").mkdir()

        result = extract_session_metadata(tmp_path)
        assert result["tap_count"] == 3

    def test_extracts_sample_rate_from_capture_meta(self, tmp_path):
        """Extracts sample_rate_hz from first capture_meta.json."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        # Create point with capture_meta
        point_dir = tmp_path / "points" / "point_A1"
        point_dir.mkdir(parents=True)
        (point_dir / "capture_meta.json").write_text(
            json.dumps(
                {
                    "sample_rate_hz": 96000,
                    "channels": 2,
                }
            )
        )

        result = extract_session_metadata(tmp_path)
        assert result["sample_rate_hz"] == 96000

    def test_uses_folder_name_as_run_id(self, tmp_path):
        """Uses session folder name as run_id."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        result = extract_session_metadata(tmp_path)
        assert result["run_id"] == tmp_path.name

    def test_handles_missing_files_gracefully(self, tmp_path):
        """Returns empty dict fields for missing files."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        result = extract_session_metadata(tmp_path)

        # Should not raise, should return run_id at minimum
        assert "run_id" in result
        assert result.get("specimen_id", "") == ""

    def test_handles_malformed_json(self, tmp_path):
        """Handles malformed JSON gracefully."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "phase2"))
        from export_viewer_pack_v1 import extract_session_metadata

        (tmp_path / "metadata.json").write_text("{ invalid json }")

        # Should not raise
        result = extract_session_metadata(tmp_path)
        assert "run_id" in result

"""
Tests for tap_tone_pi.calibration.session_context module.

Tests cover:
- Calibration context generation
- Context injection into session metadata
- Offset extraction
- Format display
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from tap_tone_pi.calibration.session_context import (
    CalibrationContext,
    get_calibration_context,
    format_calibration_summary,
    inject_calibration_into_meta,
    extract_calibration_offsets,
)


# --- CalibrationContext Tests ---

class TestCalibrationContext:
    """Tests for CalibrationContext dataclass."""
    
    def test_default_values(self):
        """Default values should be set correctly."""
        ctx = CalibrationContext(
            status="uncalibrated",
            device_index=0,
        )
        
        assert ctx.status == "uncalibrated"
        assert ctx.device_index == 0
        assert ctx.device_name is None
        assert ctx.warnings == []
        assert ctx.captured_at != ""  # Should auto-set
    
    def test_to_dict_removes_none(self):
        """to_dict should remove None values."""
        ctx = CalibrationContext(
            status="valid",
            device_index=1,
            device_name="Test Device",
            amplitude_offset_db=None,  # Should be removed
        )
        
        d = ctx.to_dict()
        
        assert "amplitude_offset_db" not in d
        assert d["status"] == "valid"
        assert d["device_name"] == "Test Device"
    
    def test_from_dict(self):
        """Should reconstruct from dict."""
        original = CalibrationContext(
            status="valid",
            device_index=2,
            device_name="My Device",
            amplitude_offset_db=-0.5,
            latency_ms=15.0,
        )
        
        d = original.to_dict()
        reconstructed = CalibrationContext.from_dict(d)
        
        assert reconstructed.status == original.status
        assert reconstructed.device_index == original.device_index
        assert reconstructed.amplitude_offset_db == original.amplitude_offset_db
    
    def test_warnings_list(self):
        """Warnings should be a mutable list."""
        ctx = CalibrationContext(
            status="stale",
            device_index=0,
            warnings=["Calibration expired"],
        )
        
        assert len(ctx.warnings) == 1
        assert "expired" in ctx.warnings[0]


# --- Context Generation Tests ---

class TestGetCalibrationContext:
    """Tests for get_calibration_context function."""
    
    @patch("tap_tone_pi.calibration.session_context.load_calibration")
    @patch("tap_tone_pi.calibration.session_context.get_calibration_status")
    def test_uncalibrated_device(self, mock_status, mock_load):
        """Uncalibrated device should return appropriate context."""
        mock_load.return_value = None
        
        ctx = get_calibration_context(device_index=5)
        
        assert ctx.status == "uncalibrated"
        assert ctx.device_index == 5
        assert len(ctx.warnings) > 0
        assert "not calibrated" in ctx.warnings[0].lower()
    
    @patch("tap_tone_pi.calibration.session_context.load_calibration")
    @patch("tap_tone_pi.calibration.session_context.get_calibration_status")
    @patch("tap_tone_pi.calibration.session_context.is_calibration_stale")
    def test_valid_calibration(self, mock_stale, mock_status, mock_load):
        """Valid calibration should populate all fields."""
        from tap_tone_pi.calibration.storage import CalibrationStatus, CalibrationData
        
        mock_status.return_value = CalibrationStatus.VALID
        mock_stale.return_value = False
        mock_load.return_value = CalibrationData(
            device_index=1,
            device_name="Scarlett Solo",
            calibrated_at="2026-03-01T10:00:00Z",
            loopback_completed=True,
            loopback_latency_ms=12.5,
            reference_tone_completed=True,
            amplitude_error_db=-0.3,
        )
        
        ctx = get_calibration_context(device_index=1)
        
        assert ctx.status == "valid"
        assert ctx.device_name == "Scarlett Solo"
        assert ctx.latency_ms == 12.5
        assert ctx.amplitude_offset_db == -0.3
        assert ctx.is_stale is False
        assert len(ctx.warnings) == 0
    
    @patch("tap_tone_pi.calibration.session_context.load_calibration")
    @patch("tap_tone_pi.calibration.session_context.get_calibration_status")
    @patch("tap_tone_pi.calibration.session_context.is_calibration_stale")
    def test_stale_calibration(self, mock_stale, mock_status, mock_load):
        """Stale calibration should include warning."""
        from tap_tone_pi.calibration.storage import CalibrationStatus, CalibrationData
        
        mock_status.return_value = CalibrationStatus.STALE
        mock_stale.return_value = True
        mock_load.return_value = CalibrationData(
            device_index=1,
            device_name="Old Device",
            calibrated_at="2025-01-01T10:00:00Z",  # Very old
            loopback_completed=True,
            reference_tone_completed=True,
        )
        
        ctx = get_calibration_context(device_index=1)
        
        assert ctx.status == "stale"
        assert ctx.is_stale is True
        assert len(ctx.warnings) > 0
        assert "stale" in ctx.warnings[0].lower()


# --- Format Summary Tests ---

class TestFormatCalibrationSummary:
    """Tests for format_calibration_summary function."""
    
    def test_valid_calibration_format(self):
        """Valid calibration should format cleanly."""
        ctx = CalibrationContext(
            status="valid",
            device_index=1,
            device_name="Test Device",
            calibrated_at="2026-03-15T10:00:00Z",
            amplitude_offset_db=-0.25,
            latency_ms=15.5,
        )
        
        summary = format_calibration_summary(ctx)
        
        assert "VALID" in summary
        assert "Test Device" in summary
        assert "-0.25" in summary
        assert "15.5" in summary
    
    def test_uncalibrated_format(self):
        """Uncalibrated status should be clear."""
        ctx = CalibrationContext(
            status="uncalibrated",
            device_index=0,
            warnings=["Device is not calibrated."],
        )
        
        summary = format_calibration_summary(ctx)
        
        assert "UNCALIBRATED" in summary
        assert "⚠" in summary
    
    def test_stale_with_warnings(self):
        """Stale calibration should show warnings."""
        ctx = CalibrationContext(
            status="stale",
            device_index=2,
            device_name="Old Device",
            warnings=["Calibration is stale.", "Consider recalibrating."],
        )
        
        summary = format_calibration_summary(ctx)
        
        assert "STALE" in summary
        assert summary.count("⚠") >= 2


# --- Injection Tests ---

class TestInjectCalibrationIntoMeta:
    """Tests for inject_calibration_into_meta function."""
    
    @patch("tap_tone_pi.calibration.session_context.get_calibration_context")
    def test_injects_calibration_section(self, mock_get_ctx):
        """Should add calibration section to metadata."""
        mock_get_ctx.return_value = CalibrationContext(
            status="valid",
            device_index=1,
            amplitude_offset_db=-0.5,
        )
        
        meta = {"session_id": "test123", "grid": "35pt"}
        
        result = inject_calibration_into_meta(meta, device_index=1)
        
        assert "calibration" in result
        assert result["calibration"]["status"] == "valid"
        assert result["calibration"]["amplitude_offset_db"] == -0.5
    
    @patch("tap_tone_pi.calibration.session_context.get_calibration_context")
    def test_preserves_existing_meta(self, mock_get_ctx):
        """Should preserve existing metadata."""
        mock_get_ctx.return_value = CalibrationContext(
            status="valid",
            device_index=1,
        )
        
        meta = {
            "session_id": "test123",
            "grid": "35pt",
            "custom_field": "preserve_me",
        }
        
        result = inject_calibration_into_meta(meta, device_index=1)
        
        assert result["session_id"] == "test123"
        assert result["custom_field"] == "preserve_me"
        assert "calibration" in result


# --- Offset Extraction Tests ---

class TestExtractCalibrationOffsets:
    """Tests for extract_calibration_offsets function."""
    
    def test_extracts_both_offsets(self):
        """Should extract both amplitude and frequency offsets."""
        meta = {
            "calibration": {
                "amplitude_offset_db": -0.3,
                "frequency_offset_hz": 0.5,
            }
        }
        
        amp, freq = extract_calibration_offsets(meta)
        
        assert amp == -0.3
        assert freq == 0.5
    
    def test_missing_calibration_returns_none(self):
        """Missing calibration section should return None."""
        meta = {"session_id": "test"}
        
        amp, freq = extract_calibration_offsets(meta)
        
        assert amp is None
        assert freq is None
    
    def test_partial_offsets(self):
        """Should handle partial offset availability."""
        meta = {
            "calibration": {
                "amplitude_offset_db": -0.2,
                # No frequency_offset_hz
            }
        }
        
        amp, freq = extract_calibration_offsets(meta)
        
        assert amp == -0.2
        assert freq is None
    
    def test_empty_calibration_section(self):
        """Empty calibration section should return None."""
        meta = {"calibration": {}}
        
        amp, freq = extract_calibration_offsets(meta)
        
        assert amp is None
        assert freq is None

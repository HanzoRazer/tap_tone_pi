# INSTRUMENT CLASS: MEASUREMENT
"""Tests for calibration trust attachment to measurement attempts.

Validates:
- Calibration fields added to Attempt
- attach_calibration method behavior
- Calibration status values match existing enum
- Measurement facts remain unchanged by calibration attachment
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from tap_tone_pi.workflow.attempt import Attempt, AttemptStatus
from tap_tone_pi.calibration.storage import CalibrationStatus


class TestAttemptCalibrationFields:
    """Tests for calibration fields in Attempt dataclass."""

    def test_attempt_has_calibration_fields(self):
        """Attempt should have calibration trust fields."""
        attempt = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        # All calibration fields should exist and default to None
        assert hasattr(attempt, "calibration_status")
        assert hasattr(attempt, "calibration_id")
        assert hasattr(attempt, "calibration_checked_at")
        assert hasattr(attempt, "calibration_age_days")

        assert attempt.calibration_status is None
        assert attempt.calibration_id is None
        assert attempt.calibration_checked_at is None
        assert attempt.calibration_age_days is None

    def test_attach_calibration_valid(self):
        """attach_calibration should set all calibration fields."""
        attempt = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.attach_calibration(
            status="valid",
            calibration_id="cal_0_2026-01-01T00:00:00Z",
            age_days=5.0,
        )

        assert attempt.calibration_status == "valid"
        assert attempt.calibration_id == "cal_0_2026-01-01T00:00:00Z"
        assert attempt.calibration_age_days == 5.0
        assert attempt.calibration_checked_at is not None
        # Timestamp should be ISO format with Z suffix
        assert attempt.calibration_checked_at.endswith("Z")

    def test_attach_calibration_uncalibrated(self):
        """attach_calibration should handle uncalibrated status."""
        attempt = Attempt(
            attempt_id="test_002",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.attach_calibration(status="uncalibrated")

        assert attempt.calibration_status == "uncalibrated"
        assert attempt.calibration_id is None
        assert attempt.calibration_age_days is None
        assert attempt.calibration_checked_at is not None

    def test_attach_calibration_stale(self):
        """attach_calibration should handle stale status."""
        attempt = Attempt(
            attempt_id="test_003",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.attach_calibration(
            status="stale",
            calibration_id="cal_0_2025-11-01T00:00:00Z",
            age_days=45.0,
        )

        assert attempt.calibration_status == "stale"
        assert attempt.calibration_age_days == 45.0

    def test_attach_calibration_failed(self):
        """attach_calibration should handle failed status."""
        attempt = Attempt(
            attempt_id="test_004",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.attach_calibration(status="failed")

        assert attempt.calibration_status == "failed"


class TestCalibrationStatusValues:
    """Tests for calibration status value consistency."""

    def test_status_values_match_enum(self):
        """Calibration status values should match CalibrationStatus enum."""
        valid_statuses = {s.value for s in CalibrationStatus}
        expected = {"uncalibrated", "valid", "stale", "failed"}

        assert valid_statuses == expected

    def test_attempt_accepts_all_enum_values(self):
        """Attempt should accept all CalibrationStatus enum values."""
        for status in CalibrationStatus:
            attempt = Attempt(
                attempt_id=f"test_{status.value}",
                point_id="point_A1",
                attempt_number=1,
            )
            attempt.attach_calibration(status=status.value)
            assert attempt.calibration_status == status.value


class TestMeasurementFactsUnchanged:
    """Tests that calibration attachment does not change measurement facts."""

    def test_calibration_does_not_change_analysis_results(self):
        """Attaching calibration should not change analysis results."""
        attempt = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        # Set analysis results
        attempt.mark_analyzed(
            dominant_hz=220.0,
            rms=0.05,
            confidence=0.85,
            peak_count=5,
            clipped=False,
        )
        original_hz = attempt.dominant_hz
        original_rms = attempt.rms
        original_confidence = attempt.confidence

        # Attach calibration
        attempt.attach_calibration(
            status="valid",
            calibration_id="cal_0_2026-01-01T00:00:00Z",
            age_days=5.0,
        )

        # Measurement facts must remain unchanged
        assert attempt.dominant_hz == original_hz
        assert attempt.rms == original_rms
        assert attempt.confidence == original_confidence
        assert attempt.peak_count == 5
        assert attempt.clipped is False

    def test_calibration_does_not_change_verdict(self):
        """Attaching calibration should not change quality verdict."""
        attempt = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.verdict = "pass"
        attempt.triggered_rules = []

        attempt.attach_calibration(status="stale", age_days=45.0)

        # Verdict unchanged
        assert attempt.verdict == "pass"
        assert attempt.triggered_rules == []


class TestAttemptSerialization:
    """Tests for Attempt serialization with calibration fields."""

    def test_to_dict_includes_calibration(self):
        """to_dict should include calibration fields."""
        attempt = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        attempt.attach_calibration(
            status="valid",
            calibration_id="cal_0_2026-01-01",
            age_days=10.0,
        )

        d = attempt.to_dict()

        assert d["calibration_status"] == "valid"
        assert d["calibration_id"] == "cal_0_2026-01-01"
        assert d["calibration_age_days"] == 10.0
        assert "calibration_checked_at" in d

    def test_from_dict_restores_calibration(self):
        """from_dict should restore calibration fields."""
        original = Attempt(
            attempt_id="test_001",
            point_id="point_A1",
            attempt_number=1,
        )
        original.attach_calibration(
            status="stale",
            calibration_id="cal_0_old",
            age_days=60.0,
        )

        d = original.to_dict()
        restored = Attempt.from_dict(d)

        assert restored.calibration_status == original.calibration_status
        assert restored.calibration_id == original.calibration_id
        assert restored.calibration_age_days == original.calibration_age_days
        assert restored.calibration_checked_at == original.calibration_checked_at


class TestCalibrationGateAttachment:
    """Tests for get_calibration_attachment helper."""

    def test_get_calibration_attachment_returns_dict(self):
        """get_calibration_attachment should return a dict with required keys."""
        from tap_tone_pi.calibration.gate import get_calibration_attachment

        result = get_calibration_attachment(device_index=0)

        assert isinstance(result, dict)
        assert "status" in result
        assert "calibration_id" in result
        assert "age_days" in result
        # Status should be one of the valid values
        assert result["status"] in {"uncalibrated", "valid", "stale", "failed"}

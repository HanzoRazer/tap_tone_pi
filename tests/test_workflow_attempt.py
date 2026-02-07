"""Tests for the attempt tracking module.

Tests Attempt dataclass and AttemptStore persistence.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.workflow.attempt import (
    Attempt,
    AttemptStatus,
    AttemptStore,
)
from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict, TriggeredRule


# =============================================================================
# Attempt Dataclass Tests
# =============================================================================

class TestAttempt:
    """Test the Attempt dataclass."""

    def test_create_attempt_with_defaults(self):
        """Attempt has sensible defaults."""
        attempt = Attempt(
            attempt_id="point_001_attempt_001",
            point_id="point_001",
            attempt_number=1,
        )

        assert attempt.status == AttemptStatus.PENDING
        assert attempt.created_at is not None
        assert attempt.captured_at is None
        assert attempt.succeeded is False

    def test_mark_captured(self):
        """mark_captured updates status and timestamps."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )

        attempt.mark_captured(
            device_index=1,
            device_name="USB Mic",
            sample_rate=48000,
            duration_seconds=2.5,
        )

        assert attempt.status == AttemptStatus.CAPTURED
        assert attempt.captured_at is not None
        assert attempt.device_index == 1
        assert attempt.device_name == "USB Mic"
        assert attempt.sample_rate == 48000
        assert attempt.duration_seconds == 2.5

    def test_mark_analyzed(self):
        """mark_analyzed updates status and analysis summary."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.CAPTURED

        attempt.mark_analyzed(
            dominant_hz=440.0,
            rms=0.05,
            confidence=0.85,
            peak_count=5,
            clipped=False,
        )

        assert attempt.status == AttemptStatus.ANALYZED
        assert attempt.analyzed_at is not None
        assert attempt.dominant_hz == 440.0
        assert attempt.rms == 0.05
        assert attempt.confidence == 0.85
        assert attempt.peak_count == 5
        assert attempt.clipped is False

    def test_mark_gated_pass(self):
        """mark_gated with PASS verdict sets status correctly."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.ANALYZED

        verdict = QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])

        attempt.mark_gated(verdict)

        assert attempt.status == AttemptStatus.PASSED
        assert attempt.verdict == "pass"
        assert attempt.triggered_rules == []
        assert attempt.completed_at is not None
        assert attempt.succeeded is True

    def test_mark_gated_warn(self):
        """mark_gated with WARN verdict sets status correctly."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.ANALYZED

        verdict = QualityVerdict(verdict=Verdict.WARN, triggered_rules=[])

        attempt.mark_gated(verdict)

        assert attempt.status == AttemptStatus.WARNED
        assert attempt.verdict == "warn"
        assert attempt.succeeded is True  # WARNED counts as succeeded

    def test_mark_gated_fail(self):
        """mark_gated with FAIL verdict sets status correctly."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.ANALYZED

        verdict = QualityVerdict(verdict=Verdict.FAIL, triggered_rules=[])

        attempt.mark_gated(verdict)

        assert attempt.status == AttemptStatus.FAILED
        assert attempt.verdict == "fail"
        assert attempt.succeeded is False

    def test_mark_overridden(self):
        """mark_overridden changes failed to overridden."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.FAILED

        attempt.mark_overridden("Operator judgment: acceptable")

        assert attempt.status == AttemptStatus.OVERRIDDEN
        assert attempt.override_reason == "Operator judgment: acceptable"
        assert attempt.overridden_at is not None
        assert attempt.succeeded is True  # OVERRIDDEN counts as succeeded

    def test_mark_overridden_rejects_non_failed(self):
        """mark_overridden raises if attempt is not failed."""
        attempt = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        attempt.status = AttemptStatus.PASSED

        with pytest.raises(ValueError, match="only override failed"):
            attempt.mark_overridden("Should not work")

    def test_to_dict_and_from_dict_roundtrip(self):
        """Attempt survives JSON roundtrip."""
        original = Attempt(
            attempt_id="p1_a1",
            point_id="p1",
            attempt_number=1,
        )
        original.mark_captured(
            device_index=2,
            device_name="Mic 2",
            sample_rate=44100,
            duration_seconds=3.0,
        )
        original.mark_analyzed(
            dominant_hz=220.0,
            rms=0.03,
            confidence=0.7,
            peak_count=3,
            clipped=False,
        )

        d = original.to_dict()
        restored = Attempt.from_dict(d)

        assert restored.attempt_id == original.attempt_id
        assert restored.status == original.status
        assert restored.device_name == original.device_name
        assert restored.dominant_hz == original.dominant_hz


# =============================================================================
# AttemptStore Tests
# =============================================================================

class TestAttemptStore:
    """Test AttemptStore persistence."""

    def test_create_attempt_first(self, tmp_path):
        """First attempt for a point is number 1."""
        store = AttemptStore(tmp_path)

        attempt = store.create_attempt("point_A")

        assert attempt.point_id == "point_A"
        assert attempt.attempt_number == 1
        assert attempt.attempt_id == "point_A_attempt_001"

    def test_create_attempt_increments(self, tmp_path):
        """Subsequent attempts increment the number."""
        store = AttemptStore(tmp_path)

        a1 = store.create_attempt("point_A")
        store.save_attempt(a1)

        a2 = store.create_attempt("point_A")

        assert a2.attempt_number == 2
        assert a2.attempt_id == "point_A_attempt_002"

    def test_save_and_load_attempt(self, tmp_path):
        """Attempt can be saved and loaded."""
        store = AttemptStore(tmp_path)

        attempt = store.create_attempt("point_B")
        attempt.mark_captured(
            device_index=0,
            device_name="Default",
            sample_rate=48000,
            duration_seconds=2.5,
        )
        store.save_attempt(attempt)

        loaded = store.load_attempt("point_B", 1)

        assert loaded is not None
        assert loaded.attempt_id == attempt.attempt_id
        assert loaded.status == AttemptStatus.CAPTURED
        assert loaded.device_name == "Default"

    def test_load_nonexistent_returns_none(self, tmp_path):
        """Loading non-existent attempt returns None."""
        store = AttemptStore(tmp_path)

        loaded = store.load_attempt("nonexistent", 1)

        assert loaded is None

    def test_get_attempt_dir(self, tmp_path):
        """get_attempt_dir returns correct path."""
        store = AttemptStore(tmp_path)

        attempt = store.create_attempt("point_C")

        attempt_dir = store.get_attempt_dir(attempt)

        assert attempt_dir == tmp_path / "point_C" / "attempt_001"
        assert attempt_dir.exists()

    def test_list_attempts_empty(self, tmp_path):
        """list_attempts returns empty list for new point."""
        store = AttemptStore(tmp_path)

        attempts = store.list_attempts("nonexistent")

        assert attempts == []

    def test_list_attempts_multiple(self, tmp_path):
        """list_attempts returns all attempts in order."""
        store = AttemptStore(tmp_path)

        a1 = store.create_attempt("point_D")
        a1.status = AttemptStatus.FAILED
        store.save_attempt(a1)

        a2 = store.create_attempt("point_D")
        a2.status = AttemptStatus.PASSED
        store.save_attempt(a2)

        attempts = store.list_attempts("point_D")

        assert len(attempts) == 2
        assert attempts[0].attempt_number == 1
        assert attempts[1].attempt_number == 2
        assert attempts[0].status == AttemptStatus.FAILED
        assert attempts[1].status == AttemptStatus.PASSED

    def test_get_latest_attempt(self, tmp_path):
        """get_latest_attempt returns most recent."""
        store = AttemptStore(tmp_path)

        a1 = store.create_attempt("point_E")
        store.save_attempt(a1)

        a2 = store.create_attempt("point_E")
        a2.status = AttemptStatus.PASSED
        store.save_attempt(a2)

        latest = store.get_latest_attempt("point_E")

        assert latest is not None
        assert latest.attempt_number == 2
        assert latest.status == AttemptStatus.PASSED

    def test_get_latest_attempt_none(self, tmp_path):
        """get_latest_attempt returns None for nonexistent point."""
        store = AttemptStore(tmp_path)

        latest = store.get_latest_attempt("nonexistent")

        assert latest is None

    def test_count_attempts(self, tmp_path):
        """count_attempts returns correct count."""
        store = AttemptStore(tmp_path)

        assert store.count_attempts("point_F") == 0

        a1 = store.create_attempt("point_F")
        store.save_attempt(a1)
        assert store.count_attempts("point_F") == 1

        a2 = store.create_attempt("point_F")
        store.save_attempt(a2)
        assert store.count_attempts("point_F") == 2

    def test_separate_points_independent(self, tmp_path):
        """Attempts for different points are independent."""
        store = AttemptStore(tmp_path)

        a1 = store.create_attempt("point_X")
        store.save_attempt(a1)

        a2 = store.create_attempt("point_Y")
        store.save_attempt(a2)

        assert store.count_attempts("point_X") == 1
        assert store.count_attempts("point_Y") == 1
        assert a1.attempt_number == 1
        assert a2.attempt_number == 1

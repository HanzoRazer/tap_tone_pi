# INSTRUMENT CLASS: MEASUREMENT
"""Tests for repeatability evidence computation.

Validates:
- Variance math correctness
- Repeatability gate logic
- Edge cases (empty, single value)
- Serialization
"""

from __future__ import annotations

import math
import pytest

from tap_tone_pi.core.repeatability import (
    RepeatabilityEvidenceV1,
    compute_repeatability_evidence,
)


class TestRepeatabilityEvidenceV1:
    """Tests for RepeatabilityEvidenceV1 dataclass."""

    def test_default_values(self):
        """Default evidence should have sensible defaults."""
        ev = RepeatabilityEvidenceV1()

        assert ev.schema_version == "repeatability_evidence_v1"
        assert ev.repetitions_required == 1
        assert ev.repetitions_completed == 0
        assert ev.passed_repeatability_gate is False

    def test_to_dict_omits_none(self):
        """to_dict should omit None values."""
        ev = RepeatabilityEvidenceV1(
            repetitions_required=5,
            repetitions_completed=5,
            dominant_frequency_mean_hz=220.0,
            passed_repeatability_gate=True,
        )
        d = ev.to_dict()

        assert "repetitions_required" in d
        assert "dominant_frequency_mean_hz" in d
        # None values should be omitted
        assert "snr_mean_db" not in d
        assert "gate_failure_reason" not in d


class TestComputeRepeatabilityEvidence:
    """Tests for compute_repeatability_evidence function."""

    def test_empty_input(self):
        """Empty input should fail with appropriate message."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[],
            rms_values=[],
            repetitions_required=5,
        )

        assert ev.repetitions_completed == 0
        assert ev.passed_repeatability_gate is False
        assert "No measurements" in (ev.gate_failure_reason or "")

    def test_single_measurement(self):
        """Single measurement should have zero variance."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0],
            rms_values=[0.05],
            repetitions_required=1,
        )

        assert ev.repetitions_completed == 1
        assert ev.dominant_frequency_mean_hz == 220.0
        assert ev.dominant_frequency_std_hz == 0.0
        assert ev.dominant_frequency_variance_pct == 0.0
        assert ev.passed_repeatability_gate is True

    def test_consistent_measurements_pass(self):
        """Consistent measurements should pass repeatability gate."""
        # 5 measurements with very low variance (within 1%)
        freqs = [220.0, 220.2, 219.8, 220.1, 219.9]
        rms = [0.05, 0.051, 0.049, 0.050, 0.050]

        ev = compute_repeatability_evidence(
            frequencies_hz=freqs,
            rms_values=rms,
            repetitions_required=5,
            max_frequency_variance_pct=3.0,
        )

        assert ev.repetitions_completed == 5
        assert ev.passed_repeatability_gate is True
        assert ev.dominant_frequency_variance_pct is not None
        assert ev.dominant_frequency_variance_pct < 1.0  # Very consistent

    def test_inconsistent_measurements_fail(self):
        """Inconsistent measurements should fail repeatability gate."""
        # High variance in frequency
        freqs = [220.0, 235.0, 210.0, 250.0, 200.0]
        rms = [0.05, 0.05, 0.05, 0.05, 0.05]

        ev = compute_repeatability_evidence(
            frequencies_hz=freqs,
            rms_values=rms,
            repetitions_required=5,
            max_frequency_variance_pct=3.0,
        )

        assert ev.passed_repeatability_gate is False
        assert "Frequency variance too high" in (ev.gate_failure_reason or "")
        assert ev.dominant_frequency_variance_pct is not None
        assert ev.dominant_frequency_variance_pct > 3.0

    def test_insufficient_repetitions_fail(self):
        """Insufficient repetitions should fail repeatability gate."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.1, 220.0],  # Only 3
            rms_values=[0.05, 0.05, 0.05],
            repetitions_required=5,  # Need 5
        )

        assert ev.repetitions_completed == 3
        assert ev.passed_repeatability_gate is False
        assert "Insufficient repetitions" in (ev.gate_failure_reason or "")

    def test_variance_math_correctness(self):
        """Verify variance computation is mathematically correct."""
        # Use known values where we can verify math
        freqs = [100.0, 102.0, 98.0, 101.0, 99.0]  # mean = 100, easy to verify
        rms = [0.1, 0.1, 0.1, 0.1, 0.1]

        ev = compute_repeatability_evidence(
            frequencies_hz=freqs,
            rms_values=rms,
            repetitions_required=5,
        )

        # Mean should be 100.0
        assert ev.dominant_frequency_mean_hz == 100.0

        # Manually compute expected std
        # variance = ((0)^2 + (2)^2 + (-2)^2 + (1)^2 + (-1)^2) / 4 = 10/4 = 2.5
        # std = sqrt(2.5) ≈ 1.581
        expected_std = math.sqrt(2.5)
        assert ev.dominant_frequency_std_hz is not None
        assert abs(ev.dominant_frequency_std_hz - expected_std) < 0.001

        # Variance pct = std/mean * 100 = 1.581%
        expected_var_pct = expected_std / 100.0 * 100
        assert ev.dominant_frequency_variance_pct is not None
        assert abs(ev.dominant_frequency_variance_pct - expected_var_pct) < 0.001

    def test_confidence_stability_computation(self):
        """Verify confidence stability is computed correctly."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.0, 220.0, 220.0, 220.0],
            rms_values=[0.05, 0.05, 0.05, 0.05, 0.05],
            confidence_values=[0.9, 0.9, 0.9, 0.9, 0.9],  # Perfect stability
            repetitions_required=5,
        )

        assert ev.confidence_mean == 0.9
        assert ev.confidence_std == 0.0
        assert ev.confidence_stability == 1.0  # Perfect stability

    def test_confidence_stability_with_variance(self):
        """Confidence stability should decrease with variance."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.0, 220.0, 220.0, 220.0],
            rms_values=[0.05, 0.05, 0.05, 0.05, 0.05],
            confidence_values=[0.5, 0.6, 0.7, 0.8, 0.9],  # Varying confidence
            repetitions_required=5,
        )

        assert ev.confidence_stability is not None
        assert ev.confidence_stability < 1.0  # Not perfect stability
        assert ev.confidence_stability > 0.0  # Not completely unstable

    def test_snr_variance_computation(self):
        """Verify SNR variance is computed."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.0, 220.0, 220.0, 220.0],
            rms_values=[0.05, 0.05, 0.05, 0.05, 0.05],
            snr_values_db=[30.0, 32.0, 28.0, 31.0, 29.0],
            repetitions_required=5,
        )

        assert ev.snr_mean_db is not None
        assert ev.snr_std_db is not None
        assert abs(ev.snr_mean_db - 30.0) < 0.01

    def test_rms_variance_computation(self):
        """Verify RMS variance is computed."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.0, 220.0, 220.0, 220.0],
            rms_values=[0.05, 0.055, 0.045, 0.052, 0.048],
            repetitions_required=5,
        )

        assert ev.rms_mean is not None
        assert ev.rms_std is not None
        assert ev.rms_variance_pct is not None
        assert abs(ev.rms_mean - 0.05) < 0.001


class TestEdgeCases:
    """Tests for edge cases."""

    def test_two_measurements(self):
        """Two measurements should compute valid variance."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 224.0],  # 4 Hz difference
            rms_values=[0.05, 0.05],
            repetitions_required=2,
        )

        assert ev.repetitions_completed == 2
        assert ev.dominant_frequency_mean_hz == 222.0
        # With 2 samples, std uses n-1 denominator
        # std = sqrt(((-2)^2 + (2)^2) / 1) = sqrt(8) = 2.828
        assert ev.dominant_frequency_std_hz is not None
        assert abs(ev.dominant_frequency_std_hz - math.sqrt(8)) < 0.001

    def test_zero_mean_frequency(self):
        """Zero frequency should not cause division by zero."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[0.0, 0.0, 0.0],
            rms_values=[0.05, 0.05, 0.05],
            repetitions_required=3,
        )

        assert ev.dominant_frequency_mean_hz == 0.0
        # Variance pct should be 0 when mean is 0 (not inf)
        assert ev.dominant_frequency_variance_pct == 0.0

    def test_missing_optional_values(self):
        """Missing optional values should not cause errors."""
        ev = compute_repeatability_evidence(
            frequencies_hz=[220.0, 220.0, 220.0],
            rms_values=[0.05, 0.05, 0.05],
            snr_values_db=None,  # Optional
            confidence_values=None,  # Optional
            repetitions_required=3,
        )

        assert ev.snr_mean_db is None
        assert ev.confidence_mean is None
        assert ev.passed_repeatability_gate is True

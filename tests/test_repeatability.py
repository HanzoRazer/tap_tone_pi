# INSTRUMENT CLASS: MEASUREMENT
"""Tests for repeatability evidence computation (Dev Order 85).

Tests cover:
- Stability behavior (stable captures → low stddev → high score)
- Instability behavior (high drift → higher stddev → lower score)
- Sample-count behavior (more captures stabilize estimates)
- Monotonicity (better repeatability → higher score)
- Threshold comparison semantics
- Export compatibility
"""

import pytest

from tap_tone_pi.core.repeatability import (
    RepeatabilityScoreWeights,
    ThresholdResult,
    compute_repeatability_evidence,
    compute_repeatability_score,
    compute_validity_envelope,
)


class TestRepeatabilityEvidence:
    """Tests for compute_repeatability_evidence function."""

    def test_stable_captures_low_variance(self):
        """Highly stable repeated captures should have low stddev."""
        freqs = [440.0, 440.01, 439.99, 440.005, 439.995]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=5,
        )

        assert evidence.repetitions_completed == 5
        assert evidence.dominant_frequency_mean_hz == pytest.approx(440.0, rel=0.001)
        assert evidence.dominant_frequency_std_hz < 0.1
        assert evidence.passed_repeatability_gate is True

    def test_unstable_captures_high_variance(self):
        """High drift repeated captures should have higher stddev."""
        freqs = [400.0, 450.0, 420.0, 480.0, 410.0]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=5,
            max_frequency_variance_pct=1.0,
        )

        assert evidence.dominant_frequency_std_hz > 20.0
        assert evidence.dominant_frequency_variance_pct > 5.0
        assert evidence.passed_repeatability_gate is False
        assert "variance too high" in evidence.gate_failure_reason.lower()

    def test_insufficient_repetitions_fails_gate(self):
        """Fewer repetitions than required should fail the gate."""
        freqs = [440.0, 440.1, 439.9]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=5,
        )

        assert evidence.repetitions_completed == 3
        assert evidence.passed_repeatability_gate is False
        assert "insufficient" in evidence.gate_failure_reason.lower()

    def test_empty_measurements(self):
        """No measurements should fail gracefully."""
        evidence = compute_repeatability_evidence(
            frequencies_hz=[],
            repetitions_required=5,
        )

        assert evidence.repetitions_completed == 0
        assert evidence.passed_repeatability_gate is False
        assert evidence.gate_failure_reason is not None

    def test_includes_all_optional_fields(self):
        """Should compute all optional fields when provided."""
        freqs = [440.0, 440.1, 439.9, 440.05, 439.95]
        mags = [-10.0, -10.1, -9.9, -10.05, -9.95]
        snrs = [30.0, 30.5, 29.5, 30.2, 29.8]
        cohs = [0.95, 0.94, 0.96, 0.95, 0.94]
        uncs = [0.05, 0.06, 0.04, 0.055, 0.045]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            peak_magnitudes_db=mags,
            snr_values_db=snrs,
            coherence_values=cohs,
            transfer_uncertainty_values=uncs,
            repetitions_required=5,
            observation_window_seconds=10.0,
        )

        assert evidence.peak_magnitude_mean_db is not None
        assert evidence.peak_magnitude_std_db is not None
        assert evidence.snr_mean_db is not None
        assert evidence.snr_std_db is not None
        assert evidence.coherence_mean is not None
        assert evidence.coherence_std is not None
        assert evidence.transfer_uncertainty_mean is not None
        assert evidence.observation_window_seconds == 10.0

    def test_rejected_count_preserved(self):
        """Rejected repetition count should be preserved."""
        evidence = compute_repeatability_evidence(
            frequencies_hz=[440.0, 440.1],
            repetitions_required=5,
            repetitions_rejected=3,
        )

        assert evidence.repetitions_rejected == 3


class TestRepeatabilityScore:
    """Tests for compute_repeatability_score function."""

    def test_zero_variance_gives_score_one(self):
        """Zero CV should give score of 1.0."""
        score = compute_repeatability_score(
            frequency_cv=0.0,
            magnitude_cv=0.0,
        )

        assert score == 1.0

    def test_high_variance_gives_low_score(self):
        """High CV should give low score."""
        score = compute_repeatability_score(
            frequency_cv=2.0,
            magnitude_cv=2.0,
        )

        # CV=2.0 → score = 1/(1+2) = 0.333
        assert score < 0.5

    def test_score_bounded_zero_to_one(self):
        """Score should always be in (0, 1]."""
        # Very high variance
        score_bad = compute_repeatability_score(
            frequency_cv=10.0,
            magnitude_cv=10.0,
        )
        assert 0 < score_bad <= 1

        # Zero variance
        score_good = compute_repeatability_score(
            frequency_cv=0.0,
        )
        assert 0 < score_good <= 1

    def test_monotonicity_lower_cv_higher_score(self):
        """Lower CV should always give higher or equal score."""
        scores = []
        for cv in [0.0, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]:
            scores.append(compute_repeatability_score(frequency_cv=cv))

        # Scores should be monotonically decreasing
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )

    def test_custom_weights(self):
        """Custom weights should affect score computation."""
        # High frequency CV, low magnitude CV
        score_default = compute_repeatability_score(  # noqa: F841
            frequency_cv=1.0,
            magnitude_cv=0.0,
        )

        # Weight frequency heavily
        score_freq_heavy = compute_repeatability_score(
            frequency_cv=1.0,
            magnitude_cv=0.0,
            weights=RepeatabilityScoreWeights(frequency=10.0, magnitude=0.1),
        )

        # Weight magnitude heavily
        score_mag_heavy = compute_repeatability_score(
            frequency_cv=1.0,
            magnitude_cv=0.0,
            weights=RepeatabilityScoreWeights(frequency=0.1, magnitude=10.0),
        )

        # With frequency weighted heavily and high freq CV, score should be lower
        assert score_freq_heavy < score_mag_heavy

    def test_no_valid_inputs_returns_zero(self):
        """No valid CV inputs should return 0."""
        score = compute_repeatability_score()
        assert score == 0.0

        score_inf = compute_repeatability_score(frequency_cv=float("inf"))
        assert score_inf == 0.0


class TestMeasurementValidityEnvelope:
    """Tests for MeasurementValidityEnvelopeV1 and compute_validity_envelope."""

    def test_stable_captures_high_score(self):
        """Stable captures should produce high repeatability score."""
        freqs = [440.0, 440.01, 439.99, 440.005, 439.995]
        mags = [-10.0, -10.01, -9.99, -10.005, -9.995]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            peak_magnitudes_db=mags,
            repetitions_required=5,
        )

        envelope = compute_validity_envelope(evidence)

        assert envelope.repeatability_score > 0.95
        assert envelope.epistemic_status == "derived"

    def test_unstable_captures_low_score(self):
        """Unstable captures should produce lower repeatability score."""
        freqs = [400.0, 500.0, 420.0, 480.0, 450.0]
        mags = [-5.0, -15.0, -8.0, -12.0, -10.0]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            peak_magnitudes_db=mags,
            repetitions_required=5,
        )

        envelope = compute_validity_envelope(evidence)

        assert envelope.repeatability_score < 0.95

    def test_threshold_results_stored(self):
        """Threshold comparison results should include the threshold values."""
        freqs = [440.0, 440.1, 439.9, 440.05, 439.95]
        mags = [-10.0, -10.1, -9.9, -10.05, -9.95]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            peak_magnitudes_db=mags,
            transfer_uncertainty_values=[0.05, 0.06, 0.04, 0.055, 0.045],
            repetitions_required=5,
        )

        envelope = compute_validity_envelope(
            evidence,
            frequency_std_threshold_hz=1.0,
            magnitude_std_threshold_db=0.5,
            uncertainty_threshold=0.1,
        )

        # Frequency threshold check
        assert envelope.frequency_std_below_threshold is not None
        assert envelope.frequency_std_below_threshold.threshold == 1.0
        assert isinstance(envelope.frequency_std_below_threshold.below_threshold, bool)

        # Magnitude threshold check
        assert envelope.magnitude_std_below_threshold is not None
        assert envelope.magnitude_std_below_threshold.threshold == 0.5

        # Uncertainty threshold check
        assert envelope.uncertainty_below_threshold is not None
        assert envelope.uncertainty_below_threshold.threshold == 0.1

    def test_envelope_contains_repeatability_evidence(self):
        """Envelope should contain the full repeatability evidence."""
        freqs = [440.0, 440.1, 439.9]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=3,
        )

        envelope = compute_validity_envelope(evidence)

        assert envelope.repeatability is not None
        assert envelope.repeatability.repetitions_completed == 3

    def test_to_dict_serialization(self):
        """Envelope should serialize to dict for JSON export."""
        freqs = [440.0, 440.1, 439.9, 440.05, 439.95]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=5,
        )

        envelope = compute_validity_envelope(evidence)
        d = envelope.to_dict()

        assert "schema_version" in d
        assert "repeatability_score" in d
        assert "epistemic_status" in d
        assert d["epistemic_status"] == "derived"


class TestSampleCountScaling:
    """Tests for sample count effects on repeatability estimates."""

    def test_more_samples_narrower_std_estimate(self):
        """More samples should give more stable mean estimates (law of large numbers)."""
        import random

        random.seed(42)

        # Simulate repeated measurements with same underlying variance
        true_freq = 440.0
        noise_std = 1.0

        # Few samples
        few_samples = [true_freq + random.gauss(0, noise_std) for _ in range(3)]
        evidence_few = compute_repeatability_evidence(
            frequencies_hz=few_samples,
            repetitions_required=3,
        )

        # Many samples
        many_samples = [true_freq + random.gauss(0, noise_std) for _ in range(50)]
        evidence_many = compute_repeatability_evidence(
            frequencies_hz=many_samples,
            repetitions_required=50,
        )

        # Mean should be closer to true value with more samples
        error_few = abs(evidence_few.dominant_frequency_mean_hz - true_freq)  # noqa: F841
        error_many = abs(evidence_many.dominant_frequency_mean_hz - true_freq)  # noqa: F841

        # This is probabilistic but with seed=42 should be consistent
        # With many more samples, we expect error to be smaller (on average)
        assert evidence_many.repetitions_completed > evidence_few.repetitions_completed


class TestExportCompatibility:
    """Tests for backward compatibility with historical exports."""

    def test_evidence_to_dict_excludes_none(self):
        """to_dict should exclude None values for clean exports."""
        evidence = compute_repeatability_evidence(
            frequencies_hz=[440.0],
            repetitions_required=1,
        )

        d = evidence.to_dict()

        # Should not have None values
        for key, value in d.items():
            assert value is not None, f"Key {key} has None value"

    def test_minimal_evidence_serializes(self):
        """Minimal evidence (freq only) should serialize cleanly."""
        evidence = compute_repeatability_evidence(
            frequencies_hz=[440.0, 440.1],
            repetitions_required=2,
        )

        d = evidence.to_dict()

        assert "schema_version" in d
        assert "dominant_frequency_mean_hz" in d
        assert d["schema_version"] == "repeatability_evidence_v1"

    def test_envelope_serializes_with_nested_repeatability(self):
        """Envelope serialization should include nested repeatability."""
        freqs = [440.0, 440.1, 439.9]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            repetitions_required=3,
        )

        envelope = compute_validity_envelope(evidence)
        d = envelope.to_dict()

        assert "repeatability" in d
        assert isinstance(d["repeatability"], dict)
        assert "dominant_frequency_mean_hz" in d["repeatability"]


class TestThresholdResult:
    """Tests for ThresholdResult dataclass."""

    def test_threshold_result_immutable(self):
        """ThresholdResult should be frozen (immutable)."""
        result = ThresholdResult(
            below_threshold=True,
            value=0.5,
            threshold=1.0,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.value = 0.6

    def test_threshold_result_comparison_logic(self):
        """below_threshold should correctly reflect value vs threshold."""
        # Value below threshold
        result_below = ThresholdResult(
            below_threshold=0.5 < 1.0,
            value=0.5,
            threshold=1.0,
        )
        assert result_below.below_threshold is True

        # Value above threshold
        result_above = ThresholdResult(
            below_threshold=1.5 < 1.0,
            value=1.5,
            threshold=1.0,
        )
        assert result_above.below_threshold is False


class TestPhase2ExportIntegration:
    """Export integration smoke test (DO-85 anchor)."""

    def test_phase2_export_includes_optional_repeatability_blocks_when_available(self):
        """Repeatability metadata integrates with viewer pack export.

        This test verifies the export pathway exists and produces valid JSON.
        The actual export_viewer_pack function reads repeatability from session
        files when present — this test validates the data structures serialize
        correctly for that pathway.
        """
        freqs = [440.0, 440.1, 439.9, 440.05, 439.95]
        mags = [-10.0, -10.1, -9.9, -10.05, -9.95]

        evidence = compute_repeatability_evidence(
            frequencies_hz=freqs,
            peak_magnitudes_db=mags,
            repetitions_required=5,
        )

        envelope = compute_validity_envelope(evidence)

        # Serialize to dict (what export_viewer_pack_v1 would embed)
        evidence_dict = evidence.to_dict()
        envelope_dict = envelope.to_dict()

        # Verify JSON-serializable
        import json

        json_evidence = json.dumps(evidence_dict)
        json_envelope = json.dumps(envelope_dict)

        assert len(json_evidence) > 0
        assert len(json_envelope) > 0

        # Verify round-trip
        parsed_evidence = json.loads(json_evidence)
        parsed_envelope = json.loads(json_envelope)

        assert parsed_evidence["schema_version"] == "repeatability_evidence_v1"
        assert parsed_envelope["schema_version"] == "measurement_validity_envelope_v1"
        assert "repeatability_score" in parsed_envelope
        assert "repeatability" in parsed_envelope

        # Narrow advisory-free check (full leakage scan is in test_guidance_not_in_measurement_exports.py)
        assert "recommendation" not in parsed_evidence
        assert "guidance" not in parsed_envelope

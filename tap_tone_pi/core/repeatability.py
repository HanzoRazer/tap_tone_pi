# INSTRUMENT CLASS: MEASUREMENT
"""Repeatability evidence computation (Dev Order 85).

Computes variance and consistency metrics across repeated captures
to establish measurement legitimacy. This is first-class evidence,
not convenience data.

Repeatability evidence answers: "Were the repeated captures consistent
enough to trust this measurement?"

Metrics computed:
- Frequency variance across repetitions
- Peak magnitude variance (dB)
- RMS variance
- SNR variance
- Coherence variance (for transfer function measurements)
- Transfer uncertainty statistics
- Confidence stability
- Repeatability score (bounded [0,1], CV-based)

This module is MEASUREMENT class — it quantifies capture consistency,
not instrument merit or operator correctness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Any, Sequence


@dataclass(frozen=True)
class RepeatabilityEvidenceV1:
    """Repeatability evidence for a measurement point.

    This is a governance artifact that records whether repeated
    captures were consistent enough to trust the measurement.
    """

    # Schema version
    schema_version: str = "repeatability_evidence_v1"

    # Repetition counts
    repetitions_required: int = 1
    repetitions_completed: int = 0
    repetitions_rejected: int = 0

    # Frequency variance (dominant peak)
    dominant_frequency_mean_hz: float | None = None
    dominant_frequency_std_hz: float | None = None
    dominant_frequency_variance_pct: float | None = None

    # Peak magnitude variance (dB scale)
    peak_magnitude_mean_db: float | None = None
    peak_magnitude_std_db: float | None = None

    # RMS variance
    rms_mean: float | None = None
    rms_std: float | None = None
    rms_variance_pct: float | None = None

    # SNR variance
    snr_mean_db: float | None = None
    snr_std_db: float | None = None
    snr_variance_db: float | None = None

    # Coherence variance (transfer function measurements)
    coherence_mean: float | None = None
    coherence_std: float | None = None

    # Transfer uncertainty statistics
    transfer_uncertainty_mean: float | None = None

    # Confidence stability
    confidence_mean: float | None = None
    confidence_std: float | None = None
    confidence_stability: float | None = None  # 1 - (std / mean), clamped to [0, 1]

    # Observation window
    observation_window_seconds: float | None = None

    # Gate result
    passed_repeatability_gate: bool = False
    gate_failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def compute_repeatability_evidence(
    frequencies_hz: Sequence[float],
    rms_values: Sequence[float] | None = None,
    snr_values_db: Sequence[float] | None = None,
    confidence_values: Sequence[float] | None = None,
    peak_magnitudes_db: Sequence[float] | None = None,
    coherence_values: Sequence[float] | None = None,
    transfer_uncertainty_values: Sequence[float] | None = None,
    repetitions_required: int = 5,
    repetitions_rejected: int = 0,
    max_frequency_variance_pct: float = 3.0,
    observation_window_seconds: float | None = None,
) -> RepeatabilityEvidenceV1:
    """Compute repeatability evidence from repeated measurements.

    Source-agnostic: accepts normalized records from any measurement context
    (multitap sessions, repeated Phase 2 point captures, etc.).

    Args:
        frequencies_hz: Dominant frequencies from each repetition
        rms_values: Optional RMS values from each repetition
        snr_values_db: Optional SNR values from each repetition
        confidence_values: Optional confidence values from each repetition
        peak_magnitudes_db: Optional peak magnitudes in dB from each repetition
        coherence_values: Optional coherence values from each repetition
        transfer_uncertainty_values: Optional transfer uncertainty from each repetition
        repetitions_required: Number of repetitions required by workflow
        repetitions_rejected: Number of rejected attempts
        max_frequency_variance_pct: Maximum allowed frequency variance (%)
        observation_window_seconds: Total observation time window

    Returns:
        RepeatabilityEvidenceV1 with computed metrics and gate result
    """
    n = len(frequencies_hz)

    if n == 0:
        return RepeatabilityEvidenceV1(
            repetitions_required=repetitions_required,
            repetitions_completed=0,
            repetitions_rejected=repetitions_rejected,
            passed_repeatability_gate=False,
            gate_failure_reason="No measurements provided",
            observation_window_seconds=observation_window_seconds,
        )

    # Frequency stats
    freq_mean = sum(frequencies_hz) / n
    freq_std = _std(frequencies_hz, freq_mean)
    freq_var_pct = (freq_std / freq_mean * 100) if freq_mean > 0 else 0.0

    # RMS stats
    rms_mean = None
    rms_std = None
    rms_var_pct = None
    if rms_values and len(rms_values) == n:
        rms_mean = sum(rms_values) / n
        rms_std = _std(rms_values, rms_mean)
        rms_var_pct = (rms_std / rms_mean * 100) if rms_mean and rms_std and rms_mean > 0 else None

    # Peak magnitude stats (dB)
    mag_mean_db = None
    mag_std_db = None
    if peak_magnitudes_db and len(peak_magnitudes_db) == n:
        mag_mean_db = sum(peak_magnitudes_db) / n
        mag_std_db = _std(peak_magnitudes_db, mag_mean_db)

    # SNR stats
    snr_mean = None
    snr_std = None
    if snr_values_db and len(snr_values_db) == n:
        snr_mean = sum(snr_values_db) / n
        snr_std = _std(snr_values_db, snr_mean)

    # Coherence stats
    coh_mean = None
    coh_std = None
    if coherence_values and len(coherence_values) == n:
        coh_mean = sum(coherence_values) / n
        coh_std = _std(coherence_values, coh_mean)

    # Transfer uncertainty stats
    tf_unc_mean = None
    if transfer_uncertainty_values and len(transfer_uncertainty_values) == n:
        tf_unc_mean = sum(transfer_uncertainty_values) / n

    # Confidence stats
    conf_mean = None
    conf_std = None
    conf_stability = None
    if confidence_values and len(confidence_values) == n:
        conf_mean = sum(confidence_values) / n
        conf_std = _std(confidence_values, conf_mean)
        if conf_mean > 0:
            conf_stability = max(0.0, min(1.0, 1.0 - (conf_std / conf_mean)))

    # Gate check
    passed = True
    failure_reason = None

    if n < repetitions_required:
        passed = False
        failure_reason = f"Insufficient repetitions: {n} < {repetitions_required}"
    elif freq_var_pct > max_frequency_variance_pct:
        passed = False
        failure_reason = f"Frequency variance too high: {freq_var_pct:.2f}% > {max_frequency_variance_pct}%"

    return RepeatabilityEvidenceV1(
        repetitions_required=repetitions_required,
        repetitions_completed=n,
        repetitions_rejected=repetitions_rejected,
        dominant_frequency_mean_hz=round(freq_mean, 3),
        dominant_frequency_std_hz=round(freq_std, 3),
        dominant_frequency_variance_pct=round(freq_var_pct, 3),
        peak_magnitude_mean_db=round(mag_mean_db, 2) if mag_mean_db is not None else None,
        peak_magnitude_std_db=round(mag_std_db, 2) if mag_std_db is not None else None,
        rms_mean=round(rms_mean, 6) if rms_mean is not None else None,
        rms_std=round(rms_std, 6) if rms_std is not None else None,
        rms_variance_pct=round(rms_var_pct, 3) if rms_var_pct is not None else None,
        snr_mean_db=round(snr_mean, 2) if snr_mean is not None else None,
        snr_std_db=round(snr_std, 2) if snr_std is not None else None,
        snr_variance_db=round(snr_std, 2) if snr_std is not None else None,
        coherence_mean=round(coh_mean, 4) if coh_mean is not None else None,
        coherence_std=round(coh_std, 4) if coh_std is not None else None,
        transfer_uncertainty_mean=round(tf_unc_mean, 4) if tf_unc_mean is not None else None,
        confidence_mean=round(conf_mean, 4) if conf_mean is not None else None,
        confidence_std=round(conf_std, 4) if conf_std is not None else None,
        confidence_stability=round(conf_stability, 4) if conf_stability is not None else None,
        observation_window_seconds=observation_window_seconds,
        passed_repeatability_gate=passed,
        gate_failure_reason=failure_reason,
    )


def _std(values: Sequence[float], mean: float | None) -> float:
    """Compute sample standard deviation."""
    if mean is None or len(values) < 2:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _cv(std: float, mean: float) -> float:
    """Compute coefficient of variation (CV = std/mean)."""
    if mean == 0 or mean is None:
        return float("inf") if std > 0 else 0.0
    return abs(std / mean)


@dataclass(frozen=True)
class RepeatabilityScoreWeights:
    """Configurable weights for repeatability score computation.

    All weights should be non-negative. They are normalized internally.
    """

    frequency: float = 1.0
    magnitude: float = 1.0
    snr: float = 0.5
    coherence: float = 0.5


def compute_repeatability_score(
    frequency_cv: float | None = None,
    magnitude_cv: float | None = None,
    snr_cv: float | None = None,
    coherence_cv: float | None = None,
    weights: RepeatabilityScoreWeights | None = None,
) -> float:
    """Compute bounded repeatability score from coefficient of variation terms.

    Formula: score = 1 / (1 + weighted_cv)

    This produces a score in (0, 1] where:
    - 1.0 = perfectly repeatable (zero variance)
    - approaching 0.0 = highly variable

    Args:
        frequency_cv: CV of dominant frequency (std/mean)
        magnitude_cv: CV of peak magnitude
        snr_cv: CV of SNR values
        coherence_cv: CV of coherence values
        weights: Optional weight configuration

    Returns:
        Repeatability score in (0, 1]
    """
    if weights is None:
        weights = RepeatabilityScoreWeights()

    cv_terms = []
    weight_values = []

    if frequency_cv is not None and math.isfinite(frequency_cv):
        cv_terms.append(frequency_cv)
        weight_values.append(weights.frequency)

    if magnitude_cv is not None and math.isfinite(magnitude_cv):
        cv_terms.append(magnitude_cv)
        weight_values.append(weights.magnitude)

    if snr_cv is not None and math.isfinite(snr_cv):
        cv_terms.append(snr_cv)
        weight_values.append(weights.snr)

    if coherence_cv is not None and math.isfinite(coherence_cv):
        cv_terms.append(coherence_cv)
        weight_values.append(weights.coherence)

    if not cv_terms:
        return 0.0

    total_weight = sum(weight_values)
    if total_weight == 0:
        return 0.0

    weighted_cv = sum(cv * w for cv, w in zip(cv_terms, weight_values)) / total_weight

    return 1.0 / (1.0 + weighted_cv)


@dataclass(frozen=True)
class ThresholdResult:
    """Result of a threshold comparison with the threshold value stored."""

    below_threshold: bool
    value: float
    threshold: float


@dataclass(frozen=True)
class MeasurementValidityEnvelopeV1:
    """Measurement validity envelope expressing repeatability state.

    This is a MEASUREMENT class structure — it quantifies capture consistency
    with explicit thresholds, not advisory judgment.

    The boolean fields store threshold comparison results along with
    the actual threshold values used, keeping this measurement-only.
    """

    # Schema version
    schema_version: str = "measurement_validity_envelope_v1"

    # Bounded repeatability score (0, 1]
    repeatability_score: float = 0.0

    # Threshold comparison results (with thresholds stored)
    frequency_std_below_threshold: ThresholdResult | None = None
    magnitude_std_below_threshold: ThresholdResult | None = None
    uncertainty_below_threshold: ThresholdResult | None = None

    # Full repeatability evidence
    repeatability: RepeatabilityEvidenceV1 | None = None

    # Epistemic status per ADR-0012
    epistemic_status: str = "derived"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result = {
            "schema_version": self.schema_version,
            "repeatability_score": self.repeatability_score,
            "epistemic_status": self.epistemic_status,
        }

        if self.frequency_std_below_threshold is not None:
            result["frequency_std_below_threshold"] = asdict(
                self.frequency_std_below_threshold
            )

        if self.magnitude_std_below_threshold is not None:
            result["magnitude_std_below_threshold"] = asdict(
                self.magnitude_std_below_threshold
            )

        if self.uncertainty_below_threshold is not None:
            result["uncertainty_below_threshold"] = asdict(
                self.uncertainty_below_threshold
            )

        if self.repeatability is not None:
            result["repeatability"] = self.repeatability.to_dict()

        return result


def compute_validity_envelope(
    repeatability: RepeatabilityEvidenceV1,
    *,
    frequency_std_threshold_hz: float = 5.0,
    magnitude_std_threshold_db: float = 3.0,
    uncertainty_threshold: float = 0.2,
    weights: RepeatabilityScoreWeights | None = None,
) -> MeasurementValidityEnvelopeV1:
    """Compute measurement validity envelope from repeatability evidence.

    Args:
        repeatability: Computed repeatability evidence
        frequency_std_threshold_hz: Threshold for frequency std (Hz)
        magnitude_std_threshold_db: Threshold for magnitude std (dB)
        uncertainty_threshold: Threshold for transfer uncertainty
        weights: Optional weights for repeatability score

    Returns:
        MeasurementValidityEnvelopeV1 with score and threshold comparisons
    """
    # Compute CVs for score
    freq_cv = None
    mag_cv = None
    snr_cv = None
    coh_cv = None

    if (
        repeatability.dominant_frequency_std_hz is not None
        and repeatability.dominant_frequency_mean_hz is not None
        and repeatability.dominant_frequency_mean_hz > 0
    ):
        freq_cv = _cv(
            repeatability.dominant_frequency_std_hz,
            repeatability.dominant_frequency_mean_hz,
        )

    if (
        repeatability.peak_magnitude_std_db is not None
        and repeatability.peak_magnitude_mean_db is not None
        and repeatability.peak_magnitude_mean_db != 0
    ):
        mag_cv = _cv(
            repeatability.peak_magnitude_std_db,
            abs(repeatability.peak_magnitude_mean_db),
        )

    if (
        repeatability.snr_std_db is not None
        and repeatability.snr_mean_db is not None
        and repeatability.snr_mean_db != 0
    ):
        snr_cv = _cv(repeatability.snr_std_db, abs(repeatability.snr_mean_db))

    if (
        repeatability.coherence_std is not None
        and repeatability.coherence_mean is not None
        and repeatability.coherence_mean > 0
    ):
        coh_cv = _cv(repeatability.coherence_std, repeatability.coherence_mean)

    score = compute_repeatability_score(
        frequency_cv=freq_cv,
        magnitude_cv=mag_cv,
        snr_cv=snr_cv,
        coherence_cv=coh_cv,
        weights=weights,
    )

    # Threshold comparisons
    freq_threshold_result = None
    if repeatability.dominant_frequency_std_hz is not None:
        freq_threshold_result = ThresholdResult(
            below_threshold=repeatability.dominant_frequency_std_hz
            < frequency_std_threshold_hz,
            value=repeatability.dominant_frequency_std_hz,
            threshold=frequency_std_threshold_hz,
        )

    mag_threshold_result = None
    if repeatability.peak_magnitude_std_db is not None:
        mag_threshold_result = ThresholdResult(
            below_threshold=repeatability.peak_magnitude_std_db
            < magnitude_std_threshold_db,
            value=repeatability.peak_magnitude_std_db,
            threshold=magnitude_std_threshold_db,
        )

    unc_threshold_result = None
    if repeatability.transfer_uncertainty_mean is not None:
        unc_threshold_result = ThresholdResult(
            below_threshold=repeatability.transfer_uncertainty_mean
            < uncertainty_threshold,
            value=repeatability.transfer_uncertainty_mean,
            threshold=uncertainty_threshold,
        )

    return MeasurementValidityEnvelopeV1(
        repeatability_score=round(score, 4),
        frequency_std_below_threshold=freq_threshold_result,
        magnitude_std_below_threshold=mag_threshold_result,
        uncertainty_below_threshold=unc_threshold_result,
        repeatability=repeatability,
    )


__all__ = [
    "RepeatabilityEvidenceV1",
    "RepeatabilityScoreWeights",
    "MeasurementValidityEnvelopeV1",
    "ThresholdResult",
    "compute_repeatability_evidence",
    "compute_repeatability_score",
    "compute_validity_envelope",
]

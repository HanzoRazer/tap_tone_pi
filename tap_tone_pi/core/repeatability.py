# INSTRUMENT CLASS: MEASUREMENT
"""Repeatability evidence computation.

Computes variance and consistency metrics across repeated captures
to establish measurement legitimacy. This is first-class evidence,
not convenience data.

Repeatability evidence answers: "Were the repeated captures consistent
enough to trust this measurement?"

Metrics computed:
- Frequency variance across repetitions
- RMS variance
- SNR variance
- Confidence stability
- Rejected attempt count
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
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

    # RMS variance
    rms_mean: float | None = None
    rms_std: float | None = None
    rms_variance_pct: float | None = None

    # SNR variance
    snr_mean_db: float | None = None
    snr_std_db: float | None = None
    snr_variance_db: float | None = None

    # Confidence stability
    confidence_mean: float | None = None
    confidence_std: float | None = None
    confidence_stability: float | None = None  # 1 - (std / mean), clamped to [0, 1]

    # Gate result
    passed_repeatability_gate: bool = False
    gate_failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def compute_repeatability_evidence(
    frequencies_hz: Sequence[float],
    rms_values: Sequence[float],
    snr_values_db: Sequence[float] | None = None,
    confidence_values: Sequence[float] | None = None,
    repetitions_required: int = 5,
    max_frequency_variance_pct: float = 3.0,
) -> RepeatabilityEvidenceV1:
    """Compute repeatability evidence from repeated measurements.

    Args:
        frequencies_hz: Dominant frequencies from each repetition
        rms_values: RMS values from each repetition
        snr_values_db: Optional SNR values from each repetition
        confidence_values: Optional confidence values from each repetition
        repetitions_required: Number of repetitions required by workflow
        max_frequency_variance_pct: Maximum allowed frequency variance (%)

    Returns:
        RepeatabilityEvidenceV1 with computed metrics and gate result
    """
    n = len(frequencies_hz)

    if n == 0:
        return RepeatabilityEvidenceV1(
            repetitions_required=repetitions_required,
            repetitions_completed=0,
            passed_repeatability_gate=False,
            gate_failure_reason="No measurements provided",
        )

    # Frequency stats
    freq_mean = sum(frequencies_hz) / n
    freq_std = _std(frequencies_hz, freq_mean)
    freq_var_pct = (freq_std / freq_mean * 100) if freq_mean > 0 else 0.0

    # RMS stats
    rms_mean = sum(rms_values) / n if rms_values else None
    rms_std = _std(rms_values, rms_mean) if rms_values and rms_mean else None
    rms_var_pct = (rms_std / rms_mean * 100) if rms_mean and rms_std and rms_mean > 0 else None

    # SNR stats
    snr_mean = None
    snr_std = None
    if snr_values_db and len(snr_values_db) == n:
        snr_mean = sum(snr_values_db) / n
        snr_std = _std(snr_values_db, snr_mean)

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
        dominant_frequency_mean_hz=round(freq_mean, 3),
        dominant_frequency_std_hz=round(freq_std, 3),
        dominant_frequency_variance_pct=round(freq_var_pct, 3),
        rms_mean=round(rms_mean, 6) if rms_mean is not None else None,
        rms_std=round(rms_std, 6) if rms_std is not None else None,
        rms_variance_pct=round(rms_var_pct, 3) if rms_var_pct is not None else None,
        snr_mean_db=round(snr_mean, 2) if snr_mean is not None else None,
        snr_std_db=round(snr_std, 2) if snr_std is not None else None,
        snr_variance_db=round(snr_std, 2) if snr_std is not None else None,
        confidence_mean=round(conf_mean, 4) if conf_mean is not None else None,
        confidence_std=round(conf_std, 4) if conf_std is not None else None,
        confidence_stability=round(conf_stability, 4) if conf_stability is not None else None,
        passed_repeatability_gate=passed,
        gate_failure_reason=failure_reason,
    )


def _std(values: Sequence[float], mean: float | None) -> float:
    """Compute sample standard deviation."""
    if mean is None or len(values) < 2:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


__all__ = [
    "RepeatabilityEvidenceV1",
    "compute_repeatability_evidence",
]

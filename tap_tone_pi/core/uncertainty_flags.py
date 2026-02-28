"""
Uncertainty flags for measurement quality assessment.

Phase 3.2: Measurement Uncertainty Reporting

This module provides a system for flagging measurements that have
high uncertainty or quality concerns. Flags help operators understand
when measurements need additional verification.

Flag Categories:
    - HIGH_UNCERTAINTY: Expanded uncertainty exceeds threshold
    - LOW_CONFIDENCE: Physics-based confidence below threshold
    - HIGH_VARIATION: Repeatability CV exceeds threshold
    - OUTLIER: Measurement deviates significantly from reference
    - CLIPPED: Audio signal was clipped
    - LOW_SIGNAL: RMS below detection threshold
    - LOW_SNR: Signal-to-noise ratio below threshold
    - POOR_COHERENCE: Two-channel coherence below threshold

Example:
    >>> from tap_tone_pi.core.uncertainty_flags import (
    ...     assess_measurement_quality,
    ...     QualityAssessment,
    ... )
    >>> assessment = assess_measurement_quality(
    ...     dominant_hz=185.2,
    ...     freq_uncertainty_hz=2.5,
    ...     confidence=0.45,
    ...     snr_db=12.0,
    ... )
    >>> print(f"Flags: {assessment.flag_ids}")
    Flags: ['LOW_CONFIDENCE', 'LOW_SNR']
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class UncertaintyFlag(Enum):
    """Enumeration of measurement quality flags."""

    HIGH_UNCERTAINTY = auto()  # U exceeds threshold
    LOW_CONFIDENCE = auto()  # Confidence score below threshold
    HIGH_VARIATION = auto()  # Repeatability CV exceeds threshold
    OUTLIER = auto()  # Measurement is statistical outlier
    CLIPPED = auto()  # Audio signal was clipped
    LOW_SIGNAL = auto()  # RMS below detection threshold
    LOW_SNR = auto()  # Signal-to-noise below threshold
    POOR_COHERENCE = auto()  # Two-channel coherence below threshold
    WIDE_BANDWIDTH = auto()  # Q-factor too low (broad peak)
    FREQUENCY_DRIFT = auto()  # Frequency changed during measurement
    MISSING_REFERENCE = auto()  # No reference for comparison


# Human-readable descriptions for each flag
FLAG_DESCRIPTIONS: dict[UncertaintyFlag, str] = {
    UncertaintyFlag.HIGH_UNCERTAINTY: "Measurement uncertainty exceeds acceptable threshold",
    UncertaintyFlag.LOW_CONFIDENCE: "Physics-based confidence score is below threshold",
    UncertaintyFlag.HIGH_VARIATION: "Repeatability coefficient of variation is high",
    UncertaintyFlag.OUTLIER: "Measurement deviates significantly from expected value",
    UncertaintyFlag.CLIPPED: "Audio signal was clipped during capture",
    UncertaintyFlag.LOW_SIGNAL: "Signal level too low for reliable detection",
    UncertaintyFlag.LOW_SNR: "Signal-to-noise ratio is below threshold",
    UncertaintyFlag.POOR_COHERENCE: "Two-channel coherence is below threshold",
    UncertaintyFlag.WIDE_BANDWIDTH: "Peak is too broad to be a clear resonance",
    UncertaintyFlag.FREQUENCY_DRIFT: "Frequency changed during measurement window",
    UncertaintyFlag.MISSING_REFERENCE: "No reference value available for comparison",
}

# Severity levels: 0=info, 1=warning, 2=error
FLAG_SEVERITY: dict[UncertaintyFlag, int] = {
    UncertaintyFlag.HIGH_UNCERTAINTY: 1,
    UncertaintyFlag.LOW_CONFIDENCE: 1,
    UncertaintyFlag.HIGH_VARIATION: 1,
    UncertaintyFlag.OUTLIER: 2,
    UncertaintyFlag.CLIPPED: 2,
    UncertaintyFlag.LOW_SIGNAL: 2,
    UncertaintyFlag.LOW_SNR: 1,
    UncertaintyFlag.POOR_COHERENCE: 1,
    UncertaintyFlag.WIDE_BANDWIDTH: 0,
    UncertaintyFlag.FREQUENCY_DRIFT: 1,
    UncertaintyFlag.MISSING_REFERENCE: 0,
}


@dataclass(frozen=True)
class QualityThresholds:
    """Configurable thresholds for measurement quality assessment.

    All thresholds are tuned for tap tone analysis of tonewoods.
    Override for different applications.
    """

    # Uncertainty thresholds
    max_relative_uncertainty: float = 0.02  # 2% of frequency
    max_absolute_uncertainty_hz: float = 2.0  # 2 Hz absolute

    # Confidence thresholds
    min_confidence: float = 0.5  # 50% confidence minimum

    # Repeatability thresholds
    max_cv_pct: float = 1.0  # 1% coefficient of variation

    # Signal quality thresholds
    min_rms: float = 0.01  # Minimum RMS level
    min_snr_db: float = 15.0  # Minimum SNR in dB
    min_coherence: float = 0.7  # Minimum coherence (0-1)
    min_q_factor: float = 5.0  # Minimum Q-factor for resonance

    # Outlier detection
    outlier_sigma: float = 3.0  # Standard deviations for outlier

    # Drift detection
    max_drift_hz: float = 1.0  # Maximum frequency drift


# Default thresholds
DEFAULT_THRESHOLDS = QualityThresholds()


@dataclass
class FlagDetail:
    """Detailed information about a triggered flag."""

    flag: UncertaintyFlag
    severity: int
    description: str
    value: float | None = None
    threshold: float | None = None
    message: str | None = None

    @property
    def flag_id(self) -> str:
        """Return flag ID as string."""
        return self.flag.name

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "flag_id": self.flag_id,
            "severity": self.severity,
            "description": self.description,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class QualityAssessment:
    """Complete quality assessment of a measurement.

    Attributes:
        is_acceptable: True if no error-level flags
        has_warnings: True if any warning-level flags
        flags: List of triggered flags with details
        overall_quality: Numeric quality score (0-1)
    """

    flags: list[FlagDetail] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        """True if no error-level (severity=2) flags."""
        return not any(f.severity >= 2 for f in self.flags)

    @property
    def has_warnings(self) -> bool:
        """True if any warning-level (severity>=1) flags."""
        return any(f.severity >= 1 for f in self.flags)

    @property
    def flag_ids(self) -> list[str]:
        """List of flag IDs that were triggered."""
        return [f.flag_id for f in self.flags]

    @property
    def max_severity(self) -> int:
        """Maximum severity of all flags (0 if none)."""
        if not self.flags:
            return 0
        return max(f.severity for f in self.flags)

    @property
    def overall_quality(self) -> float:
        """
        Numeric quality score (0-1).

        Based on flag severities:
        - No flags: 1.0
        - Info flags only: 0.9
        - Warning flags: 0.7
        - Error flags: 0.3
        """
        if not self.flags:
            return 1.0

        max_sev = self.max_severity
        if max_sev == 0:
            return 0.9
        elif max_sev == 1:
            return 0.7
        else:
            return 0.3

    def add_flag(
        self,
        flag: UncertaintyFlag,
        *,
        value: float | None = None,
        threshold: float | None = None,
        message: str | None = None,
    ) -> None:
        """Add a flag to the assessment."""
        self.flags.append(FlagDetail(
            flag=flag,
            severity=FLAG_SEVERITY[flag],
            description=FLAG_DESCRIPTIONS[flag],
            value=value,
            threshold=threshold,
            message=message,
        ))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_acceptable": self.is_acceptable,
            "has_warnings": self.has_warnings,
            "overall_quality": self.overall_quality,
            "max_severity": self.max_severity,
            "flag_count": len(self.flags),
            "flags": [f.to_dict() for f in self.flags],
        }

    def format_summary(self) -> str:
        """Format a one-line summary."""
        if not self.flags:
            return "OK"

        flag_strs = []
        for f in self.flags:
            if f.severity >= 2:
                flag_strs.append(f"[ERROR] {f.flag_id}")
            elif f.severity >= 1:
                flag_strs.append(f"[WARN] {f.flag_id}")
            else:
                flag_strs.append(f"[INFO] {f.flag_id}")

        return " | ".join(flag_strs)


def _check_signal_flags(
    assessment: QualityAssessment,
    th: QualityThresholds,
    *,
    clipped: bool,
    rms: float | None,
    snr_db: float | None,
) -> None:
    """Check signal-level quality flags (clipping, RMS, SNR)."""
    if clipped:
        assessment.add_flag(
            UncertaintyFlag.CLIPPED,
            message="Audio signal was clipped - retake measurement"
        )
    if rms is not None and rms < th.min_rms:
        assessment.add_flag(
            UncertaintyFlag.LOW_SIGNAL,
            value=rms,
            threshold=th.min_rms,
            message=f"RMS {rms:.4f} below minimum {th.min_rms}"
        )
    if snr_db is not None and snr_db < th.min_snr_db:
        assessment.add_flag(
            UncertaintyFlag.LOW_SNR,
            value=snr_db,
            threshold=th.min_snr_db,
            message=f"SNR {snr_db:.1f} dB below minimum {th.min_snr_db} dB"
        )


def _check_analysis_flags(
    assessment: QualityAssessment,
    th: QualityThresholds,
    *,
    confidence: float | None,
    coherence: float | None,
    q_factor: float | None,
) -> None:
    """Check analysis-metric quality flags (confidence, coherence, Q-factor)."""
    if confidence is not None and confidence < th.min_confidence:
        assessment.add_flag(
            UncertaintyFlag.LOW_CONFIDENCE,
            value=confidence,
            threshold=th.min_confidence,
            message=f"Confidence {confidence:.2%} below minimum {th.min_confidence:.0%}"
        )
    if coherence is not None and coherence < th.min_coherence:
        assessment.add_flag(
            UncertaintyFlag.POOR_COHERENCE,
            value=coherence,
            threshold=th.min_coherence,
            message=f"Coherence {coherence:.2f} below minimum {th.min_coherence}"
        )
    if q_factor is not None and q_factor < th.min_q_factor:
        assessment.add_flag(
            UncertaintyFlag.WIDE_BANDWIDTH,
            value=q_factor,
            threshold=th.min_q_factor,
            message=f"Q-factor {q_factor:.1f} below minimum {th.min_q_factor}"
        )


def _check_precision_flags(
    assessment: QualityAssessment,
    th: QualityThresholds,
    *,
    dominant_hz: float | None,
    freq_uncertainty_hz: float | None,
    cv_pct: float | None,
    reference_hz: float | None,
    reference_uncertainty_hz: float | None,
) -> None:
    """Check measurement-precision quality flags (uncertainty, CV, outlier)."""
    if dominant_hz is not None and freq_uncertainty_hz is not None:
        relative_uncertainty = freq_uncertainty_hz / dominant_hz if dominant_hz > 0 else 0
        if (relative_uncertainty > th.max_relative_uncertainty or
                freq_uncertainty_hz > th.max_absolute_uncertainty_hz):
            assessment.add_flag(
                UncertaintyFlag.HIGH_UNCERTAINTY,
                value=freq_uncertainty_hz,
                threshold=max(
                    th.max_absolute_uncertainty_hz,
                    dominant_hz * th.max_relative_uncertainty
                ),
                message=f"Uncertainty {freq_uncertainty_hz:.2f} Hz ({relative_uncertainty:.1%}) exceeds threshold"
            )

    if cv_pct is not None and cv_pct > th.max_cv_pct:
        assessment.add_flag(
            UncertaintyFlag.HIGH_VARIATION,
            value=cv_pct,
            threshold=th.max_cv_pct,
            message=f"CV {cv_pct:.2f}% exceeds maximum {th.max_cv_pct}%"
        )

    if (dominant_hz is not None and reference_hz is not None
            and freq_uncertainty_hz is not None):
        if reference_uncertainty_hz is not None:
            combined_u = (freq_uncertainty_hz**2 + reference_uncertainty_hz**2)**0.5
        else:
            combined_u = freq_uncertainty_hz

        deviation = abs(dominant_hz - reference_hz)
        threshold = th.outlier_sigma * combined_u

        if combined_u > 0 and deviation > threshold:
            assessment.add_flag(
                UncertaintyFlag.OUTLIER,
                value=deviation,
                threshold=threshold,
                message=f"Deviation {deviation:.2f} Hz exceeds {th.outlier_sigma}\u03c3 threshold"
            )


def assess_measurement_quality(
    *,
    dominant_hz: float | None = None,
    freq_uncertainty_hz: float | None = None,
    confidence: float | None = None,
    snr_db: float | None = None,
    coherence: float | None = None,
    q_factor: float | None = None,
    rms: float | None = None,
    clipped: bool = False,
    cv_pct: float | None = None,
    reference_hz: float | None = None,
    reference_uncertainty_hz: float | None = None,
    thresholds: QualityThresholds | None = None,
) -> QualityAssessment:
    """
    Assess measurement quality and generate flags.

    Args:
        dominant_hz: Detected dominant frequency
        freq_uncertainty_hz: Frequency uncertainty (standard uncertainty)
        confidence: Physics-based confidence score (0-1)
        snr_db: Signal-to-noise ratio in dB
        coherence: Two-channel coherence (0-1)
        q_factor: Estimated Q-factor of dominant peak
        rms: RMS signal level
        clipped: Whether audio was clipped
        cv_pct: Coefficient of variation from repeatability (%)
        reference_hz: Reference frequency for comparison
        reference_uncertainty_hz: Uncertainty of reference
        thresholds: Custom thresholds (uses DEFAULT_THRESHOLDS if None)

    Returns:
        QualityAssessment with all triggered flags

    Example:
        >>> assessment = assess_measurement_quality(
        ...     dominant_hz=185.2,
        ...     freq_uncertainty_hz=2.5,
        ...     confidence=0.45,
        ...     snr_db=12.0,
        ... )
        >>> if not assessment.is_acceptable:
        ...     print(f"Issues: {assessment.format_summary()}")
    """
    th = thresholds or DEFAULT_THRESHOLDS
    assessment = QualityAssessment()

    _check_signal_flags(assessment, th, clipped=clipped, rms=rms, snr_db=snr_db)
    _check_analysis_flags(
        assessment, th,
        confidence=confidence, coherence=coherence, q_factor=q_factor,
    )
    _check_precision_flags(
        assessment, th,
        dominant_hz=dominant_hz,
        freq_uncertainty_hz=freq_uncertainty_hz,
        cv_pct=cv_pct,
        reference_hz=reference_hz,
        reference_uncertainty_hz=reference_uncertainty_hz,
    )

    return assessment


def format_flags_for_display(
    assessment: QualityAssessment,
    *,
    show_details: bool = True,
    use_color: bool = False,
) -> str:
    """
    Format quality assessment for terminal display.

    Args:
        assessment: Quality assessment to format
        show_details: Include detailed messages
        use_color: Use ANSI color codes

    Returns:
        Formatted string for display
    """
    if not assessment.flags:
        if use_color:
            return "\033[32m✓ No quality flags\033[0m"
        return "OK - No quality flags"

    lines = []

    # Header based on severity
    if assessment.max_severity >= 2:
        header = "QUALITY ISSUES DETECTED"
        if use_color:
            header = f"\033[31m{header}\033[0m"
    elif assessment.max_severity >= 1:
        header = "QUALITY WARNINGS"
        if use_color:
            header = f"\033[33m{header}\033[0m"
    else:
        header = "QUALITY NOTES"

    lines.append(header)
    lines.append("-" * len(header.replace("\033[31m", "").replace("\033[33m", "").replace("\033[0m", "")))

    for flag_detail in assessment.flags:
        # Severity indicator
        if flag_detail.severity >= 2:
            indicator = "[ERROR]"
            if use_color:
                indicator = f"\033[31m{indicator}\033[0m"
        elif flag_detail.severity >= 1:
            indicator = "[WARN] "
            if use_color:
                indicator = f"\033[33m{indicator}\033[0m"
        else:
            indicator = "[INFO] "

        line = f"  {indicator} {flag_detail.flag_id}"

        if show_details and flag_detail.message:
            line += f": {flag_detail.message}"

        lines.append(line)

    return "\n".join(lines)


__all__ = [
    # Enums
    "UncertaintyFlag",
    # Classes
    "QualityThresholds",
    "FlagDetail",
    "QualityAssessment",
    # Functions
    "assess_measurement_quality",
    "format_flags_for_display",
    # Constants
    "DEFAULT_THRESHOLDS",
    "FLAG_DESCRIPTIONS",
    "FLAG_SEVERITY",
]

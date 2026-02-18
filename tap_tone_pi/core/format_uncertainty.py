"""
CLI formatting utilities for uncertainty display.

Phase 3.2: Measurement Uncertainty Reporting

This module provides formatting functions for displaying measurements
with their uncertainty in CLI output.

Example:
    >>> from tap_tone_pi.core.format_uncertainty import (
    ...     format_frequency_with_uncertainty,
    ...     format_analysis_with_uncertainty,
    ... )
    >>> print(format_frequency_with_uncertainty(185.2, 0.3, unit="Hz"))
    185.2 ± 0.3 Hz
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FormattedMeasurement:
    """A formatted measurement value with uncertainty."""

    value: float
    uncertainty: float | None
    unit: str
    precision: int

    def __str__(self) -> str:
        """Format as 'value ± uncertainty unit' string."""
        if self.uncertainty is not None and self.uncertainty > 0:
            return f"{self.value:.{self.precision}f} ± {self.uncertainty:.{self.precision}f} {self.unit}".strip()
        return f"{self.value:.{self.precision}f} {self.unit}".strip()

    @property
    def value_str(self) -> str:
        """Just the value with precision."""
        return f"{self.value:.{self.precision}f}"

    @property
    def uncertainty_str(self) -> str:
        """Just the uncertainty with ± prefix, or empty if none."""
        if self.uncertainty is not None and self.uncertainty > 0:
            return f"± {self.uncertainty:.{self.precision}f}"
        return ""


def format_frequency_with_uncertainty(
    freq_hz: float,
    uncertainty_hz: float | None = None,
    *,
    unit: str = "Hz",
    precision: int = 1,
) -> str:
    """
    Format a frequency measurement with its uncertainty.

    Args:
        freq_hz: Frequency value in Hz
        uncertainty_hz: Standard or expanded uncertainty in Hz
        unit: Unit label (default "Hz")
        precision: Decimal places (default 1)

    Returns:
        Formatted string like "185.2 ± 0.3 Hz"

    Example:
        >>> format_frequency_with_uncertainty(185.2, 0.3)
        '185.2 ± 0.3 Hz'
        >>> format_frequency_with_uncertainty(185.2)
        '185.2 Hz'
    """
    return str(FormattedMeasurement(freq_hz, uncertainty_hz, unit, precision))


def format_value_with_uncertainty(
    value: float,
    uncertainty: float | None = None,
    *,
    unit: str = "",
    precision: int = 2,
) -> str:
    """
    Format a generic measurement with its uncertainty.

    Args:
        value: Measurement value
        uncertainty: Standard or expanded uncertainty
        unit: Unit label
        precision: Decimal places

    Returns:
        Formatted string like "0.85 ± 0.02"
    """
    return str(FormattedMeasurement(value, uncertainty, unit, precision))


def format_analysis_summary(
    dominant_hz: float | None,
    rms: float,
    confidence: float,
    clipped: bool,
    *,
    freq_uncertainty_hz: float | None = None,
    snr_db: float | None = None,
    coherence: float | None = None,
    show_uncertainty: bool = True,
) -> str:
    """
    Format analysis summary with optional uncertainty info.

    Args:
        dominant_hz: Dominant frequency in Hz
        rms: RMS signal level
        confidence: Confidence score (0-1)
        clipped: Whether signal was clipped
        freq_uncertainty_hz: Frequency uncertainty
        snr_db: Signal-to-noise ratio
        coherence: Two-channel coherence
        show_uncertainty: Whether to display uncertainty

    Returns:
        Multi-line summary string

    Example:
        >>> summary = format_analysis_summary(
        ...     dominant_hz=185.2,
        ...     rms=0.08,
        ...     confidence=0.85,
        ...     clipped=False,
        ...     freq_uncertainty_hz=0.3,
        ... )
        >>> print(summary)
        Dominant: 185.2 ± 0.3 Hz
        RMS: 0.0800   Confidence: 85.0%   Clipped: No
    """
    lines = []

    # Dominant frequency with uncertainty
    if dominant_hz is not None:
        if show_uncertainty and freq_uncertainty_hz is not None:
            freq_str = format_frequency_with_uncertainty(dominant_hz, freq_uncertainty_hz)
        else:
            freq_str = f"{dominant_hz:.1f} Hz"
        lines.append(f"Dominant: {freq_str}")
    else:
        lines.append("Dominant: n/a")

    # RMS, Confidence, Clipped
    clip_str = "Yes" if clipped else "No"
    conf_pct = confidence * 100
    lines.append(f"RMS: {rms:.4f}   Confidence: {conf_pct:.1f}%   Clipped: {clip_str}")

    # Additional metrics if available
    extra = []
    if snr_db is not None:
        extra.append(f"SNR: {snr_db:.1f} dB")
    if coherence is not None:
        extra.append(f"Coherence: {coherence:.2f}")
    if extra:
        lines.append("  ".join(extra))

    return "\n".join(lines)


def format_peak_table(
    peaks: list[dict[str, Any]],
    *,
    max_peaks: int = 8,
    show_uncertainty: bool = True,
) -> str:
    """
    Format a table of frequency peaks.

    Args:
        peaks: List of peak dicts with keys:
               - freq_hz (required)
               - magnitude (required)
               - uncertainty_hz (optional)
               - confidence (optional)
        max_peaks: Maximum peaks to display
        show_uncertainty: Whether to show uncertainty column

    Returns:
        Formatted table string

    Example:
        >>> peaks = [
        ...     {"freq_hz": 185.2, "magnitude": 0.95, "uncertainty_hz": 0.3},
        ...     {"freq_hz": 312.5, "magnitude": 0.45, "uncertainty_hz": 0.5},
        ... ]
        >>> print(format_peak_table(peaks))
        Top peaks:
          - 185.2 ± 0.3 Hz   mag=0.950
          - 312.5 ± 0.5 Hz   mag=0.450
    """
    if not peaks:
        return "No peaks detected."

    lines = ["Top peaks:"]

    for p in peaks[:max_peaks]:
        freq = p.get("freq_hz", 0.0)
        mag = p.get("magnitude", 0.0)
        unc = p.get("uncertainty_hz") or p.get("freq_uncertainty_hz")

        if show_uncertainty and unc is not None:
            freq_str = format_frequency_with_uncertainty(freq, unc)
        else:
            freq_str = f"{freq:.1f} Hz"

        # Add confidence if available
        conf = p.get("confidence")
        if conf is not None:
            lines.append(f"  - {freq_str:>20}   mag={mag:.3f}   conf={conf:.2f}")
        else:
            lines.append(f"  - {freq_str:>20}   mag={mag:.3f}")

    return "\n".join(lines)


def format_repeatability_summary(
    mean: float,
    std_dev: float,
    n_measurements: int,
    cv_pct: float,
    *,
    unit: str = "Hz",
    threshold_cv_pct: float = 1.0,
) -> str:
    """
    Format repeatability statistics summary.

    Args:
        mean: Mean value
        std_dev: Standard deviation
        n_measurements: Number of measurements
        cv_pct: Coefficient of variation (%)
        unit: Unit label
        threshold_cv_pct: Acceptable CV threshold

    Returns:
        Formatted repeatability summary

    Example:
        >>> print(format_repeatability_summary(
        ...     mean=185.2,
        ...     std_dev=0.3,
        ...     n_measurements=5,
        ...     cv_pct=0.16,
        ... ))
        Repeatability (n=5):
          Mean: 185.2 Hz
          Std dev: 0.3 Hz
          CV: 0.16% ✓
    """
    status = "✓" if cv_pct <= threshold_cv_pct else "⚠"
    lines = [
        f"Repeatability (n={n_measurements}):",
        f"  Mean: {mean:.1f} {unit}",
        f"  Std dev: {std_dev:.2f} {unit}",
        f"  CV: {cv_pct:.2f}% {status}",
    ]
    return "\n".join(lines)


def format_quality_summary(
    is_acceptable: bool,
    has_warnings: bool,
    flag_ids: list[str],
    overall_quality: float,
) -> str:
    """
    Format quality assessment summary.

    Args:
        is_acceptable: Whether measurement is acceptable
        has_warnings: Whether there are warnings
        flag_ids: List of triggered flag IDs
        overall_quality: Quality score (0-1)

    Returns:
        Formatted quality summary

    Example:
        >>> print(format_quality_summary(
        ...     is_acceptable=True,
        ...     has_warnings=True,
        ...     flag_ids=["LOW_SNR"],
        ...     overall_quality=0.7,
        ... ))
        Quality: 70% (ACCEPTABLE with warnings)
          Flags: LOW_SNR
    """
    quality_pct = overall_quality * 100

    if not has_warnings:
        status = "OK"
    elif is_acceptable:
        status = "ACCEPTABLE with warnings"
    else:
        status = "NEEDS ATTENTION"

    lines = [f"Quality: {quality_pct:.0f}% ({status})"]

    if flag_ids:
        lines.append(f"  Flags: {', '.join(flag_ids)}")

    return "\n".join(lines)


__all__ = [
    "FormattedMeasurement",
    "format_frequency_with_uncertainty",
    "format_value_with_uncertainty",
    "format_analysis_summary",
    "format_peak_table",
    "format_repeatability_summary",
    "format_quality_summary",
]

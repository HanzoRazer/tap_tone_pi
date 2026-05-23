# INSTRUMENT CLASS: MEASUREMENT
"""
Session diff service for comparing acoustic measurements.

Compares two measurement sessions (before/after wood removal) and
produces a structured diff showing changes in frequency, amplitude,
and quality metrics.

M7 Fix: Uncertainty-Based Comparison Threshold
----------------------------------------------
Problem: Hardcoded threshold (e.g., 1 Hz) for "significant difference" without:
  - Scaling by frequency
  - Accounting for measurement uncertainty
  - User configurability

Solution: Use uncertainty-based thresholds following GUM (Guide to Uncertainty
in Measurement) principles:

  Significant if: |Δf| > k × √(u_a² + u_b²)

  where:
    Δf = frequency difference (B - A)
    u_a = standard uncertainty of measurement A
    u_b = standard uncertainty of measurement B
    k = coverage factor (default 2 for ~95% confidence)

If uncertainties are not available, fall back to relative threshold:
  Significant if: |Δf| > threshold_pct × f_mean

Default fallback: 0.5% of mean frequency (reasonable for tap tone measurements).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# M7 fix: Configurable significance parameters
DEFAULT_COVERAGE_FACTOR = 2.0  # k=2 for ~95% confidence interval
DEFAULT_FALLBACK_THRESHOLD_PCT = 0.5  # 0.5% of frequency when no uncertainty


@dataclass
class SignificanceConfig:
    """Configuration for uncertainty-based significance testing.

    M7 fix: Replaces hardcoded 1 Hz threshold with physics-based approach.
    """

    coverage_factor: float = DEFAULT_COVERAGE_FACTOR
    fallback_threshold_pct: float = DEFAULT_FALLBACK_THRESHOLD_PCT
    min_absolute_hz: float = 0.5  # Minimum detectable change (FFT resolution limit)

    def is_significant(
        self,
        delta: float,
        freq_mean: float,
        uncertainty_a: float | None = None,
        uncertainty_b: float | None = None,
    ) -> tuple[bool, float, str]:
        """
        Test if a frequency difference is statistically significant.

        Args:
            delta: Frequency difference (B - A) in Hz
            freq_mean: Mean frequency of the two measurements
            uncertainty_a: Standard uncertainty of measurement A (Hz)
            uncertainty_b: Standard uncertainty of measurement B (Hz)

        Returns:
            (is_significant, threshold_used, method) tuple

        Physics:
        - If uncertainties available: |Δf| > k × √(u_a² + u_b²)
        - Otherwise: |Δf| > fallback_pct × f_mean
        - Always: |Δf| > min_absolute_hz (FFT resolution floor)
        """
        abs_delta = abs(delta)

        # Method 1: Uncertainty-based (preferred)
        if uncertainty_a is not None and uncertainty_b is not None:
            # Combined standard uncertainty
            u_combined = math.sqrt(uncertainty_a**2 + uncertainty_b**2)
            # Expanded uncertainty with coverage factor
            threshold = self.coverage_factor * u_combined
            threshold = max(threshold, self.min_absolute_hz)
            return abs_delta > threshold, threshold, "uncertainty"

        # Method 2: Relative threshold fallback
        if freq_mean > 0:
            threshold = freq_mean * (self.fallback_threshold_pct / 100.0)
            threshold = max(threshold, self.min_absolute_hz)
            return abs_delta > threshold, threshold, "relative"

        # Method 3: Absolute minimum fallback
        return abs_delta > self.min_absolute_hz, self.min_absolute_hz, "absolute"


# Global default config
SIGNIFICANCE_CONFIG = SignificanceConfig()


@dataclass
class PeakDiff:
    """Difference in a single peak between two measurements.

    M7 fix: Now includes uncertainty fields and uses uncertainty-based
    significance testing instead of hardcoded 1 Hz threshold.
    """

    label: str
    freq_a: float | None = None
    freq_b: float | None = None
    amp_a: float | None = None
    amp_b: float | None = None
    # M7 fix: Uncertainty fields for proper significance testing
    freq_uncertainty_a: float | None = None  # Standard uncertainty of freq_a (Hz)
    freq_uncertainty_b: float | None = None  # Standard uncertainty of freq_b (Hz)
    # M7 fix: Cached significance result
    _significance_threshold: float | None = None
    _significance_method: str | None = None

    @property
    def freq_delta(self) -> float | None:
        """Frequency change (B - A). Positive = frequency increased."""
        if self.freq_a is not None and self.freq_b is not None:
            return self.freq_b - self.freq_a
        return None

    @property
    def freq_delta_pct(self) -> float | None:
        """Frequency change as percentage."""
        if self.freq_a and self.freq_delta is not None:
            return (self.freq_delta / self.freq_a) * 100
        return None

    @property
    def amp_delta(self) -> float | None:
        """Amplitude change (B - A). Positive = louder."""
        if self.amp_a is not None and self.amp_b is not None:
            return self.amp_b - self.amp_a
        return None

    @property
    def amp_delta_pct(self) -> float | None:
        """Amplitude change as percentage."""
        if self.amp_a and self.amp_delta is not None:
            return (self.amp_delta / self.amp_a) * 100
        return None

    @property
    def combined_uncertainty(self) -> float | None:
        """Combined standard uncertainty of the frequency difference.

        u_combined = √(u_a² + u_b²)
        """
        if self.freq_uncertainty_a is not None and self.freq_uncertainty_b is not None:
            return math.sqrt(self.freq_uncertainty_a**2 + self.freq_uncertainty_b**2)
        return None

    def is_significant(self, config: SignificanceConfig | None = None) -> bool:
        """
        Test if the frequency change is statistically significant.

        M7 fix: Uses uncertainty-based testing instead of hardcoded threshold.
        """
        config = config or SIGNIFICANCE_CONFIG

        if self.freq_a is None or self.freq_b is None:
            return False

        delta = self.freq_delta
        if delta is None:
            return False

        freq_mean = (self.freq_a + self.freq_b) / 2.0
        is_sig, threshold, method = config.is_significant(
            delta,
            freq_mean,
            self.freq_uncertainty_a,
            self.freq_uncertainty_b,
        )

        # Cache for reporting
        self._significance_threshold = threshold
        self._significance_method = method

        return is_sig

    @property
    def status(self) -> str:
        """Status indicator: added, removed, changed, unchanged.

        M7 fix: Uses uncertainty-based significance testing.
        """
        if self.freq_a is None and self.freq_b is not None:
            return "added"
        if self.freq_a is not None and self.freq_b is None:
            return "removed"
        if self.is_significant():
            return "changed"
        return "unchanged"

    @property
    def significance_info(self) -> dict[str, Any]:
        """Return significance test details for debugging."""
        return {
            "is_significant": self.status == "changed",
            "threshold_hz": self._significance_threshold,
            "method": self._significance_method,
            "combined_uncertainty_hz": self.combined_uncertainty,
            "freq_uncertainty_a": self.freq_uncertainty_a,
            "freq_uncertainty_b": self.freq_uncertainty_b,
        }


@dataclass
class MetricDiff:
    """Difference in a single metric between two measurements."""

    name: str
    value_a: float | None = None
    value_b: float | None = None
    unit: str = ""

    @property
    def delta(self) -> float | None:
        """Change (B - A)."""
        if self.value_a is not None and self.value_b is not None:
            return self.value_b - self.value_a
        return None

    @property
    def delta_pct(self) -> float | None:
        """Change as percentage."""
        if self.value_a and self.delta is not None:
            return (self.delta / self.value_a) * 100
        return None


@dataclass
class SessionDiff:
    """Complete diff between two measurement sessions."""

    session_a: str  # Name/path of session A (before)
    session_b: str  # Name/path of session B (after)
    peaks: list[PeakDiff] = field(default_factory=list)
    metrics: list[MetricDiff] = field(default_factory=list)
    point_id: str | None = None  # For multi-point sessions
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, Any]:
        """Summary statistics of the diff."""
        peaks_added = sum(1 for p in self.peaks if p.status == "added")
        peaks_removed = sum(1 for p in self.peaks if p.status == "removed")
        peaks_changed = sum(1 for p in self.peaks if p.status == "changed")

        freq_deltas = [p.freq_delta for p in self.peaks if p.freq_delta is not None]
        avg_freq_delta = sum(freq_deltas) / len(freq_deltas) if freq_deltas else 0

        return {
            "peaks_added": peaks_added,
            "peaks_removed": peaks_removed,
            "peaks_changed": peaks_changed,
            "peaks_unchanged": len(self.peaks)
            - peaks_added
            - peaks_removed
            - peaks_changed,
            "avg_freq_delta_hz": avg_freq_delta,
            "total_peaks_a": sum(1 for p in self.peaks if p.freq_a is not None),
            "total_peaks_b": sum(1 for p in self.peaks if p.freq_b is not None),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        M7 fix: Now includes uncertainty and significance information.
        """
        return {
            "session_a": self.session_a,
            "session_b": self.session_b,
            "point_id": self.point_id,
            "summary": self.summary,
            "peaks": [
                {
                    "label": p.label,
                    "freq_a": p.freq_a,
                    "freq_b": p.freq_b,
                    "freq_delta": p.freq_delta,
                    "freq_delta_pct": p.freq_delta_pct,
                    "amp_a": p.amp_a,
                    "amp_b": p.amp_b,
                    "amp_delta_pct": p.amp_delta_pct,
                    "status": p.status,
                    # M7 fix: Include uncertainty and significance info
                    "freq_uncertainty_a": p.freq_uncertainty_a,
                    "freq_uncertainty_b": p.freq_uncertainty_b,
                    "combined_uncertainty": p.combined_uncertainty,
                    "significance": p.significance_info,
                }
                for p in self.peaks
            ],
            "metrics": [
                {
                    "name": m.name,
                    "value_a": m.value_a,
                    "value_b": m.value_b,
                    "delta": m.delta,
                    "delta_pct": m.delta_pct,
                    "unit": m.unit,
                }
                for m in self.metrics
            ],
            "errors": self.errors,
        }


def _load_analysis(path: Path) -> dict[str, Any] | None:
    """Load analysis.json from a path."""
    analysis_file = None

    # Try different locations
    candidates = [
        path / "analysis.json",
        path / "tap_tone.json",
        path / "tap_tone_offline.json",
    ]

    # Also check for attempt directories
    for attempt_dir in sorted(path.glob("*/attempt_*"), reverse=True):
        candidates.insert(0, attempt_dir / "analysis.json")

    for candidate in candidates:
        if candidate.exists():
            analysis_file = candidate
            break

    if not analysis_file:
        return None

    try:
        with open(analysis_file) as f:
            return json.load(f)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return None


@dataclass
class ExtractedPeak:
    """Peak data extracted from analysis JSON.

    M7 fix: Now includes uncertainty information for significance testing.
    """

    label: str
    freq_hz: float
    amplitude: float
    uncertainty_hz: float | None = None  # Standard uncertainty of frequency


def _extract_peaks(data: dict[str, Any]) -> list[ExtractedPeak]:
    """Extract peaks with optional uncertainty information.

    M7 fix: Now extracts uncertainty fields for proper significance testing.

    Supported uncertainty field names:
    - freq_uncertainty, freq_uncertainty_hz
    - uncertainty, uncertainty_hz
    - std_error, std_error_hz
    - From confidence_components.snr_db: estimate uncertainty from SNR
    """
    peaks = []

    def _get_uncertainty(info: dict) -> float | None:
        """Extract uncertainty from various field names."""
        # Direct uncertainty fields
        for key in [
            "freq_uncertainty",
            "freq_uncertainty_hz",
            "uncertainty",
            "uncertainty_hz",
            "std_error",
            "std_error_hz",
        ]:
            if key in info:
                return float(info[key])

        # M7: Estimate from SNR if confidence_components available
        # Rule of thumb: σ_f ≈ f / (2 × 10^(SNR_dB/20))
        # This is the Cramer-Rao lower bound for frequency estimation
        if "confidence_components" in info:
            cc = info["confidence_components"]
            snr_db = cc.get("snr_db")
            freq = info.get("freq_hz") or info.get("frequency")
            if snr_db is not None and freq is not None:
                snr_linear = 10 ** (snr_db / 20.0)
                return freq / (2.0 * snr_linear) if snr_linear > 0 else None

        return None

    # Format 1: {"peaks": {"A4": {"freq_hz": 440, "amp": 1000}}}
    if "peaks" in data and isinstance(data["peaks"], dict):
        for label, info in data["peaks"].items():
            if isinstance(info, dict):
                freq = info.get("freq_hz") or info.get("frequency")
                amp = (
                    info.get("amp")
                    or info.get("magnitude")
                    or info.get("amplitude", 1.0)
                )
                if freq:
                    peaks.append(
                        ExtractedPeak(
                            label=label,
                            freq_hz=float(freq),
                            amplitude=float(amp),
                            uncertainty_hz=_get_uncertainty(info),
                        )
                    )

    # Format 2: {"peaks": [{"freq_hz": 440, "magnitude": 0.5}]}
    elif "peaks" in data and isinstance(data["peaks"], list):
        for i, p in enumerate(data["peaks"]):
            freq = p.get("freq_hz") or p.get("frequency")
            amp = p.get("magnitude") or p.get("amp") or p.get("amplitude", 1.0)
            label = p.get("label", f"P{i + 1}")
            if freq:
                peaks.append(
                    ExtractedPeak(
                        label=label,
                        freq_hz=float(freq),
                        amplitude=float(amp),
                        uncertainty_hz=_get_uncertainty(p),
                    )
                )

    # Format 3: {"dominant_hz": 440}
    if "dominant_hz" in data:
        # M7: Try to get uncertainty from confidence_components
        uncertainty = None
        if "confidence_components" in data:
            cc = data["confidence_components"]
            snr_db = cc.get("snr_db")
            if snr_db is not None:
                snr_linear = 10 ** (snr_db / 20.0)
                uncertainty = (
                    data["dominant_hz"] / (2.0 * snr_linear) if snr_linear > 0 else None
                )

        peaks.append(
            ExtractedPeak(
                label="dominant",
                freq_hz=float(data["dominant_hz"]),
                amplitude=data.get("rms", 1.0),
                uncertainty_hz=uncertainty,
            )
        )

    return peaks


def _extract_metrics(data: dict[str, Any]) -> list[tuple[str, float, str]]:
    """Extract metrics as (name, value, unit) tuples."""
    metrics = []

    if "rms" in data:
        metrics.append(("RMS", float(data["rms"]), ""))

    if "confidence" in data:
        metrics.append(("Confidence", float(data["confidence"]), ""))

    if "dominant_hz" in data:
        metrics.append(("Dominant Frequency", float(data["dominant_hz"]), "Hz"))

    if "summary" in data:
        summary = data["summary"]
        if "coherence_mean" in summary:
            metrics.append(("Coherence (mean)", float(summary["coherence_mean"]), ""))
        if "H_mag_max" in summary:
            metrics.append(("H magnitude (max)", float(summary["H_mag_max"]), ""))

    return metrics


def compare_sessions(
    session_a: Path | str,
    session_b: Path | str,
    point_id: str | None = None,
) -> SessionDiff:
    """
    Compare two measurement sessions.

    Args:
        session_a: Path to session A (before)
        session_b: Path to session B (after)
        point_id: Optional point ID for multi-point sessions

    Returns:
        SessionDiff with peak and metric comparisons
    """
    path_a = Path(session_a)
    path_b = Path(session_b)

    diff = SessionDiff(
        session_a=path_a.name,
        session_b=path_b.name,
        point_id=point_id,
    )

    # Load analysis data
    data_a = _load_analysis(path_a)
    data_b = _load_analysis(path_b)

    if data_a is None:
        diff.errors.append(f"Could not load analysis from {path_a.name}")
    if data_b is None:
        diff.errors.append(f"Could not load analysis from {path_b.name}")

    if data_a is None or data_b is None:
        return diff

    # Extract and compare peaks (M7 fix: now includes uncertainty)
    peaks_a = {p.label: p for p in _extract_peaks(data_a)}
    peaks_b = {p.label: p for p in _extract_peaks(data_b)}

    all_labels = set(peaks_a.keys()) | set(peaks_b.keys())

    for label in sorted(all_labels):
        peak_a = peaks_a.get(label)
        peak_b = peaks_b.get(label)

        diff.peaks.append(
            PeakDiff(
                label=label,
                freq_a=peak_a.freq_hz if peak_a else None,
                freq_b=peak_b.freq_hz if peak_b else None,
                amp_a=peak_a.amplitude if peak_a else None,
                amp_b=peak_b.amplitude if peak_b else None,
                # M7 fix: Include uncertainty for proper significance testing
                freq_uncertainty_a=peak_a.uncertainty_hz if peak_a else None,
                freq_uncertainty_b=peak_b.uncertainty_hz if peak_b else None,
            )
        )

    # Extract and compare metrics
    metrics_a = {name: (val, unit) for name, val, unit in _extract_metrics(data_a)}
    metrics_b = {name: (val, unit) for name, val, unit in _extract_metrics(data_b)}

    all_metrics = set(metrics_a.keys()) | set(metrics_b.keys())

    for name in sorted(all_metrics):
        val_a, unit_a = metrics_a.get(name, (None, ""))
        val_b, unit_b = metrics_b.get(name, (None, ""))

        diff.metrics.append(
            MetricDiff(
                name=name,
                value_a=val_a,
                value_b=val_b,
                unit=unit_a or unit_b,
            )
        )

    return diff


def format_diff_report(diff: SessionDiff) -> str:
    """Format a diff as a human-readable text report."""
    lines = []

    lines.append("Session Comparison Report")
    lines.append("=" * 50)
    lines.append(f"Before: {diff.session_a}")
    lines.append(f"After:  {diff.session_b}")
    if diff.point_id:
        lines.append(f"Point:  {diff.point_id}")
    lines.append("")

    if diff.errors:
        lines.append("Errors:")
        for err in diff.errors:
            lines.append(f"  - {err}")
        lines.append("")

    # Summary
    summary = diff.summary
    lines.append("Summary:")
    lines.append(f"  Peaks in A: {summary['total_peaks_a']}")
    lines.append(f"  Peaks in B: {summary['total_peaks_b']}")
    lines.append(f"  Added:      {summary['peaks_added']}")
    lines.append(f"  Removed:    {summary['peaks_removed']}")
    lines.append(f"  Changed:    {summary['peaks_changed']}")
    lines.append(f"  Avg Δf:     {summary['avg_freq_delta_hz']:+.1f} Hz")
    lines.append("")

    # Peaks table (M7 fix: now shows uncertainty-based significance)
    if diff.peaks:
        lines.append("Peak Changes:")
        lines.append(
            f"  {'Label':<10} {'Freq A':>10} {'Freq B':>10} {'Δ Hz':>10} {'±u':>8} {'Status':<10}"
        )
        lines.append(
            f"  {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 10}"
        )

        for p in diff.peaks:
            freq_a_str = f"{p.freq_a:.1f}" if p.freq_a else "-"
            freq_b_str = f"{p.freq_b:.1f}" if p.freq_b else "-"
            delta_str = f"{p.freq_delta:+.1f}" if p.freq_delta else "-"
            # M7 fix: Show combined uncertainty if available
            u_str = f"±{p.combined_uncertainty:.2f}" if p.combined_uncertainty else "-"
            lines.append(
                f"  {p.label:<10} {freq_a_str:>10} {freq_b_str:>10} {delta_str:>10} {u_str:>8} {p.status:<10}"
            )
        lines.append("")

        # M7 fix: Add significance method note
        methods_used = set()
        for p in diff.peaks:
            if p._significance_method:
                methods_used.add(p._significance_method)
        if methods_used:
            lines.append(f"  Significance method(s): {', '.join(sorted(methods_used))}")
            lines.append("")

    # Metrics table
    if diff.metrics:
        lines.append("Metric Changes:")
        lines.append(f"  {'Metric':<20} {'Before':>12} {'After':>12} {'Δ%':>10}")
        lines.append(f"  {'-' * 20} {'-' * 12} {'-' * 12} {'-' * 10}")

        for m in diff.metrics:
            val_a_str = f"{m.value_a:.4f}" if m.value_a else "-"
            val_b_str = f"{m.value_b:.4f}" if m.value_b else "-"
            delta_pct_str = f"{m.delta_pct:+.1f}%" if m.delta_pct else "-"
            lines.append(
                f"  {m.name:<20} {val_a_str:>12} {val_b_str:>12} {delta_pct_str:>10}"
            )

    return "\n".join(lines)


__all__ = [
    "PeakDiff",
    "MetricDiff",
    "SessionDiff",
    "ExtractedPeak",
    "SignificanceConfig",
    "SIGNIFICANCE_CONFIG",
    "compare_sessions",
    "format_diff_report",
]

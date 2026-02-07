"""
Session diff service for comparing acoustic measurements.

Compares two measurement sessions (before/after wood removal) and
produces a structured diff showing changes in frequency, amplitude,
and quality metrics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PeakDiff:
    """Difference in a single peak between two measurements."""
    label: str
    freq_a: float | None = None
    freq_b: float | None = None
    amp_a: float | None = None
    amp_b: float | None = None

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
    def status(self) -> str:
        """Status indicator: added, removed, changed, unchanged."""
        if self.freq_a is None and self.freq_b is not None:
            return "added"
        if self.freq_a is not None and self.freq_b is None:
            return "removed"
        if self.freq_delta and abs(self.freq_delta) > 1.0:  # > 1 Hz change
            return "changed"
        return "unchanged"


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
            "peaks_unchanged": len(self.peaks) - peaks_added - peaks_removed - peaks_changed,
            "avg_freq_delta_hz": avg_freq_delta,
            "total_peaks_a": sum(1 for p in self.peaks if p.freq_a is not None),
            "total_peaks_b": sum(1 for p in self.peaks if p.freq_b is not None),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    except Exception:
        return None


def _extract_peaks(data: dict[str, Any]) -> list[tuple[str, float, float]]:
    """Extract peaks as (label, freq_hz, amplitude) tuples."""
    peaks = []

    # Format 1: {"peaks": {"A4": {"freq_hz": 440, "amp": 1000}}}
    if "peaks" in data and isinstance(data["peaks"], dict):
        for label, info in data["peaks"].items():
            if isinstance(info, dict):
                freq = info.get("freq_hz") or info.get("frequency")
                amp = info.get("amp") or info.get("magnitude") or info.get("amplitude", 1.0)
                if freq:
                    peaks.append((label, float(freq), float(amp)))

    # Format 2: {"peaks": [{"freq_hz": 440, "magnitude": 0.5}]}
    elif "peaks" in data and isinstance(data["peaks"], list):
        for i, p in enumerate(data["peaks"]):
            freq = p.get("freq_hz") or p.get("frequency")
            amp = p.get("magnitude") or p.get("amp") or p.get("amplitude", 1.0)
            label = p.get("label", f"P{i+1}")
            if freq:
                peaks.append((label, float(freq), float(amp)))

    # Format 3: {"dominant_hz": 440}
    if "dominant_hz" in data:
        peaks.append(("dominant", float(data["dominant_hz"]), data.get("rms", 1.0)))

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

    # Extract and compare peaks
    peaks_a = {label: (freq, amp) for label, freq, amp in _extract_peaks(data_a)}
    peaks_b = {label: (freq, amp) for label, freq, amp in _extract_peaks(data_b)}

    all_labels = set(peaks_a.keys()) | set(peaks_b.keys())

    for label in sorted(all_labels):
        freq_a, amp_a = peaks_a.get(label, (None, None))
        freq_b, amp_b = peaks_b.get(label, (None, None))

        diff.peaks.append(PeakDiff(
            label=label,
            freq_a=freq_a,
            freq_b=freq_b,
            amp_a=amp_a,
            amp_b=amp_b,
        ))

    # Extract and compare metrics
    metrics_a = {name: (val, unit) for name, val, unit in _extract_metrics(data_a)}
    metrics_b = {name: (val, unit) for name, val, unit in _extract_metrics(data_b)}

    all_metrics = set(metrics_a.keys()) | set(metrics_b.keys())

    for name in sorted(all_metrics):
        val_a, unit_a = metrics_a.get(name, (None, ""))
        val_b, unit_b = metrics_b.get(name, (None, ""))

        diff.metrics.append(MetricDiff(
            name=name,
            value_a=val_a,
            value_b=val_b,
            unit=unit_a or unit_b,
        ))

    return diff


def format_diff_report(diff: SessionDiff) -> str:
    """Format a diff as a human-readable text report."""
    lines = []

    lines.append(f"Session Comparison Report")
    lines.append(f"=" * 50)
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

    # Peaks table
    if diff.peaks:
        lines.append("Peak Changes:")
        lines.append(f"  {'Label':<10} {'Freq A':>10} {'Freq B':>10} {'Δ Hz':>10} {'Status':<10}")
        lines.append(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

        for p in diff.peaks:
            freq_a_str = f"{p.freq_a:.1f}" if p.freq_a else "-"
            freq_b_str = f"{p.freq_b:.1f}" if p.freq_b else "-"
            delta_str = f"{p.freq_delta:+.1f}" if p.freq_delta else "-"
            lines.append(f"  {p.label:<10} {freq_a_str:>10} {freq_b_str:>10} {delta_str:>10} {p.status:<10}")
        lines.append("")

    # Metrics table
    if diff.metrics:
        lines.append("Metric Changes:")
        lines.append(f"  {'Metric':<20} {'Before':>12} {'After':>12} {'Δ%':>10}")
        lines.append(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}")

        for m in diff.metrics:
            val_a_str = f"{m.value_a:.4f}" if m.value_a else "-"
            val_b_str = f"{m.value_b:.4f}" if m.value_b else "-"
            delta_pct_str = f"{m.delta_pct:+.1f}%" if m.delta_pct else "-"
            lines.append(f"  {m.name:<20} {val_a_str:>12} {val_b_str:>12} {delta_pct_str:>10}")

    return "\n".join(lines)


__all__ = [
    "PeakDiff",
    "MetricDiff",
    "SessionDiff",
    "compare_sessions",
    "format_diff_report",
]

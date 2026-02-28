"""
Phase 1/2 Cross-Validation Module.

Correlates Phase 1 (single-channel FFT) peaks with Phase 2 (dual-channel ODS)
mode shapes to ensure measurement consistency.

M5 Audit Fix: Phase 1 and Phase 2 can report different frequencies for the same
mode without consistency checks. This module adds mode-linking with tolerance-based
matching and flags inconsistencies.

Physics basis:
- Phase 1 detects resonant frequencies from single-point tap response
- Phase 2 maps spatial mode shapes using transfer functions across a grid
- Same physical modes should appear at matching frequencies (within tolerance)

See: docs/CODEBASE_AUDIT_2026.md (M5)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any



class MatchStatus(Enum):
    """Status of mode matching between phases."""

    MATCHED = "matched"  # Phase 1 peak found corresponding Phase 2 ODS mode
    P1_ONLY = "phase1_only"  # Peak only in Phase 1 (possible spurious)
    P2_ONLY = "phase2_only"  # Mode only in Phase 2 (missing from Phase 1)
    WEAK_MATCH = "weak_match"  # Matched but with low confidence


class ConfidenceLevel(Enum):
    """Confidence level for cross-phase matching."""

    HIGH = "high"  # Clear match, both phases agree
    MEDIUM = "medium"  # Match with some uncertainty
    LOW = "low"  # Questionable match


@dataclass
class Phase1Peak:
    """A Phase 1 (single-channel) frequency peak."""

    freq_hz: float
    magnitude: float  # Normalized 0..1
    confidence: float = 1.0  # Analysis confidence
    label: str | None = None  # Optional mode label (e.g., "1,0")


@dataclass
class Phase2Mode:
    """A Phase 2 (ODS) mode shape at a specific frequency."""

    freq_hz: float
    n_points: int  # Number of grid points
    max_magnitude: float  # Peak magnitude in mode shape
    coherence_mean: float = 1.0  # Mean coherence across grid (if available)
    pattern_label: str | None = None  # Identified mode pattern (e.g., "1,0")


@dataclass
class ModeMatch:
    """Result of matching a single mode across phases."""

    p1_freq_hz: float | None
    p2_freq_hz: float | None
    freq_delta_hz: float | None  # Signed difference (P2 - P1)
    freq_delta_pct: float | None  # Percent difference
    status: MatchStatus
    confidence: ConfidenceLevel
    notes: list[str] = field(default_factory=list)


@dataclass
class CrossValidationResult:
    """Complete cross-validation result between Phase 1 and Phase 2."""

    n_p1_peaks: int
    n_p2_modes: int
    n_matched: int
    n_p1_only: int
    n_p2_only: int
    n_weak_match: int

    matches: list[ModeMatch]

    # Overall assessment
    agreement_ratio: float  # n_matched / max(n_p1, n_p2)
    is_consistent: bool  # True if no red flags
    warnings: list[str] = field(default_factory=list)

    # Configuration used
    tolerance_pct: float = 2.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "n_p1_peaks": self.n_p1_peaks,
            "n_p2_modes": self.n_p2_modes,
            "n_matched": self.n_matched,
            "n_p1_only": self.n_p1_only,
            "n_p2_only": self.n_p2_only,
            "n_weak_match": self.n_weak_match,
            "agreement_ratio": round(self.agreement_ratio, 3),
            "is_consistent": self.is_consistent,
            "tolerance_pct": self.tolerance_pct,
            "warnings": self.warnings,
            "matches": [
                {
                    "p1_freq_hz": m.p1_freq_hz,
                    "p2_freq_hz": m.p2_freq_hz,
                    "freq_delta_hz": round(m.freq_delta_hz, 2) if m.freq_delta_hz else None,
                    "freq_delta_pct": round(m.freq_delta_pct, 3) if m.freq_delta_pct else None,
                    "status": m.status.value,
                    "confidence": m.confidence.value,
                    "notes": m.notes,
                }
                for m in self.matches
            ],
        }


def compute_tolerance_hz(freq_hz: float, tolerance_pct: float = 2.0) -> float:
    """
    Compute frequency-relative tolerance.

    Uses percentage of frequency (default 2%) with a minimum floor
    to account for FFT bin width at low frequencies.

    Args:
        freq_hz: Center frequency
        tolerance_pct: Tolerance as percentage (default 2%)

    Returns:
        Tolerance in Hz
    """
    # Minimum tolerance: 1 Hz (accounts for typical FFT resolution)
    min_tol_hz = 1.0
    return max(min_tol_hz, freq_hz * tolerance_pct / 100.0)


def _assess_match_quality(
    p1: Phase1Peak,
    p2: Phase2Mode,
    delta_pct: float,
    tolerance_pct: float,
    weak_match_threshold: float,
) -> tuple[MatchStatus, ConfidenceLevel, list[str]]:
    """Assess quality of a single P1-P2 frequency match."""
    if p1.confidence < weak_match_threshold:
        status = MatchStatus.WEAK_MATCH
        confidence = ConfidenceLevel.LOW
        notes = [f"P1 confidence low ({p1.confidence:.2f})"]
    elif abs(delta_pct) > tolerance_pct * 0.5:
        status = MatchStatus.MATCHED
        confidence = ConfidenceLevel.MEDIUM
        notes = ["Near tolerance boundary"]
    else:
        status = MatchStatus.MATCHED
        confidence = ConfidenceLevel.HIGH
        notes = []

    if p2.coherence_mean < 0.7:
        confidence = (
            ConfidenceLevel.MEDIUM
            if confidence == ConfidenceLevel.HIGH
            else ConfidenceLevel.LOW
        )
        notes.append(f"P2 coherence low ({p2.coherence_mean:.2f})")

    return status, confidence, notes


def _collect_unmatched_p2(
    p2_sorted: list[Phase2Mode],
    p2_matched: set[int],
) -> tuple[list[ModeMatch], list[str]]:
    """Build ModeMatch entries and warnings for unmatched P2 modes."""
    matches: list[ModeMatch] = []
    warnings: list[str] = []
    for j, p2 in enumerate(p2_sorted):
        if j not in p2_matched:
            matches.append(ModeMatch(
                p1_freq_hz=None,
                p2_freq_hz=p2.freq_hz,
                freq_delta_hz=None,
                freq_delta_pct=None,
                status=MatchStatus.P2_ONLY,
                confidence=ConfidenceLevel.LOW,
                notes=["No corresponding P1 peak found"],
            ))
            warnings.append(f"P2 mode at {p2.freq_hz:.1f} Hz not detected in P1")
    return matches, warnings


def match_phases(
    p1_peaks: list[Phase1Peak],
    p2_modes: list[Phase2Mode],
    *,
    tolerance_pct: float = 2.0,
    weak_match_threshold: float = 0.3,
    min_confidence_for_match: float = 0.5,
) -> CrossValidationResult:
    """
    Cross-validate Phase 1 peaks against Phase 2 ODS modes.

    Algorithm:
    1. Sort both lists by frequency
    2. For each P1 peak, find nearest P2 mode within tolerance
    3. Flag unmatched entries from both phases
    4. Assess match quality based on:
       - Frequency agreement
       - Confidence levels
       - Coherence (P2)

    Args:
        p1_peaks: Phase 1 frequency peaks
        p2_modes: Phase 2 ODS mode frequencies
        tolerance_pct: Frequency tolerance as percentage (default 2%)
        weak_match_threshold: P1 confidence below this = weak match
        min_confidence_for_match: Minimum P1 confidence to attempt matching

    Returns:
        CrossValidationResult with all matches and diagnostics
    """
    if not p1_peaks and not p2_modes:
        return CrossValidationResult(
            n_p1_peaks=0,
            n_p2_modes=0,
            n_matched=0,
            n_p1_only=0,
            n_p2_only=0,
            n_weak_match=0,
            matches=[],
            agreement_ratio=1.0,  # Vacuously true
            is_consistent=True,
            tolerance_pct=tolerance_pct,
        )

    # Sort by frequency
    p1_sorted = sorted(p1_peaks, key=lambda p: p.freq_hz)
    p2_sorted = sorted(p2_modes, key=lambda m: m.freq_hz)

    matches: list[ModeMatch] = []
    p1_matched: set[int] = set()
    p2_matched: set[int] = set()
    warnings: list[str] = []

    # Match P1 peaks to P2 modes
    for i, p1 in enumerate(p1_sorted):
        tol_hz = compute_tolerance_hz(p1.freq_hz, tolerance_pct)

        # Find closest P2 mode
        best_j: int | None = None
        best_delta: float = float("inf")

        for j, p2 in enumerate(p2_sorted):
            if j in p2_matched:
                continue  # Already matched

            delta = abs(p2.freq_hz - p1.freq_hz)
            if delta < tol_hz and delta < best_delta:
                best_j = j
                best_delta = delta

        if best_j is not None:
            p2 = p2_sorted[best_j]
            delta_hz = p2.freq_hz - p1.freq_hz
            delta_pct = (delta_hz / p1.freq_hz) * 100.0 if p1.freq_hz > 0 else 0.0

            status, confidence, notes = _assess_match_quality(
                p1, p2, delta_pct, tolerance_pct, weak_match_threshold,
            )

            matches.append(ModeMatch(
                p1_freq_hz=p1.freq_hz,
                p2_freq_hz=p2.freq_hz,
                freq_delta_hz=delta_hz,
                freq_delta_pct=delta_pct,
                status=status,
                confidence=confidence,
                notes=notes,
            ))

            p1_matched.add(i)
            p2_matched.add(best_j)

        elif p1.confidence >= min_confidence_for_match:
            # P1 peak with no P2 match - possibly spurious
            matches.append(ModeMatch(
                p1_freq_hz=p1.freq_hz,
                p2_freq_hz=None,
                freq_delta_hz=None,
                freq_delta_pct=None,
                status=MatchStatus.P1_ONLY,
                confidence=ConfidenceLevel.LOW,
                notes=["No corresponding P2 mode found"],
            ))
            warnings.append(f"P1 peak at {p1.freq_hz:.1f} Hz not confirmed by P2 ODS")

    # Unmatched P2 modes
    p2_unmatched, p2_warns = _collect_unmatched_p2(p2_sorted, p2_matched)
    matches.extend(p2_unmatched)
    warnings.extend(p2_warns)

    # Compute statistics
    n_matched = sum(1 for m in matches if m.status == MatchStatus.MATCHED)
    n_weak = sum(1 for m in matches if m.status == MatchStatus.WEAK_MATCH)
    n_p1_only = sum(1 for m in matches if m.status == MatchStatus.P1_ONLY)
    n_p2_only = sum(1 for m in matches if m.status == MatchStatus.P2_ONLY)

    max_modes = max(len(p1_peaks), len(p2_modes))
    agreement_ratio = (n_matched + n_weak) / max_modes if max_modes > 0 else 1.0

    # Consistency check: flag if too many unmatched
    is_consistent = (
        n_p1_only <= len(p1_peaks) * 0.3 and  # <30% P1 unmatched
        n_p2_only <= len(p2_modes) * 0.3  # <30% P2 unmatched
    )

    if not is_consistent:
        warnings.insert(0, "Phase 1/2 inconsistency: >30% modes unmatched")

    return CrossValidationResult(
        n_p1_peaks=len(p1_peaks),
        n_p2_modes=len(p2_modes),
        n_matched=n_matched,
        n_p1_only=n_p1_only,
        n_p2_only=n_p2_only,
        n_weak_match=n_weak,
        matches=matches,
        agreement_ratio=agreement_ratio,
        is_consistent=is_consistent,
        warnings=warnings,
        tolerance_pct=tolerance_pct,
    )


def load_p1_peaks_from_json(data: dict[str, Any]) -> list[Phase1Peak]:
    """
    Load Phase 1 peaks from analysis JSON.

    Handles both formats:
    - Direct peak list: {"peaks": [{"freq_hz": ..., "magnitude": ...}, ...]}
    - Analysis result: {"dominant_hz": ..., "peaks": [...], "confidence": ...}

    Args:
        data: JSON-loaded analysis data

    Returns:
        List of Phase1Peak objects
    """
    peaks: list[Phase1Peak] = []

    if "peaks" not in data:
        return peaks

    confidence = data.get("confidence", 1.0)

    for p in data["peaks"]:
        peaks.append(Phase1Peak(
            freq_hz=float(p["freq_hz"]),
            magnitude=float(p.get("magnitude", 0.0)),
            confidence=confidence,
            label=p.get("label"),
        ))

    return peaks


def load_p2_modes_from_json(data: dict[str, Any]) -> list[Phase2Mode]:
    """
    Load Phase 2 modes from ODS summary JSON.

    Expected format (from ods_compute.py):
    {
        "target_frequencies_hz": [100, 150, ...],
        "ods_files": ["ods_f_100.0Hz.json", ...],
        "n_points": 25,
        ...
    }

    Args:
        data: JSON-loaded ODS summary data

    Returns:
        List of Phase2Mode objects
    """
    modes: list[Phase2Mode] = []

    target_freqs = data.get("target_frequencies_hz", [])
    n_points = data.get("n_points", 0)

    for freq in target_freqs:
        modes.append(Phase2Mode(
            freq_hz=float(freq),
            n_points=n_points,
            max_magnitude=1.0,  # Placeholder, actual value from individual ODS file
            coherence_mean=1.0,  # Placeholder
        ))

    return modes


def crossval_from_json(
    p1_json: dict[str, Any],
    p2_json: dict[str, Any],
    tolerance_pct: float = 2.0,
) -> CrossValidationResult:
    """
    Convenience function: cross-validate from JSON data.

    Args:
        p1_json: Phase 1 analysis JSON
        p2_json: Phase 2 ODS summary JSON
        tolerance_pct: Frequency tolerance percentage

    Returns:
        CrossValidationResult
    """
    p1_peaks = load_p1_peaks_from_json(p1_json)
    p2_modes = load_p2_modes_from_json(p2_json)
    return match_phases(p1_peaks, p2_modes, tolerance_pct=tolerance_pct)

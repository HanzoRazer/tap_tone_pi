"""
Tap Tone Analysis Module.

Provides physics-based analysis tools for tap tone measurements.
"""

from .wolf_beat import (
    # Data structures
    PeakInfo,
    PeakPair,
    WolfBeatResult,
    # Core functions
    find_peaks_in_frf,
    extract_linewidth,
    extract_linewidth_lorentzian,
    find_peak_pairs,
    analyze_wolf_beat,
    # Utilities
    estimate_coupling_from_split,
    predict_wolf_severity_change,
)

__all__ = [
    # Data structures
    "PeakInfo",
    "PeakPair",
    "WolfBeatResult",
    # Core functions
    "find_peaks_in_frf",
    "extract_linewidth",
    "extract_linewidth_lorentzian",
    "find_peak_pairs",
    "analyze_wolf_beat",
    # Utilities
    "estimate_coupling_from_split",
    "predict_wolf_severity_change",
]

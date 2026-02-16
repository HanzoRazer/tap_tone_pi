"""
Analysis modules for tap tone data processing.
"""

from analyzer.analysis.peaks import find_spectrum_peaks, PeakDetector
from analyzer.analysis.fft import compute_fft, compute_transfer_function
from analyzer.analysis.coherence import compute_coherence, analyze_coherence_quality
from analyzer.analysis.wood_properties import (
    estimate_wood_properties,
    WoodDimensions,
    WoodProperties,
    identify_wood_species,
    TONEWOOD_REFERENCES
)

__all__ = [
    "find_spectrum_peaks",
    "PeakDetector",
    "compute_fft",
    "compute_transfer_function",
    "compute_coherence",
    "analyze_coherence_quality",
    "estimate_wood_properties",
    "WoodDimensions",
    "WoodProperties",
    "identify_wood_species",
    "TONEWOOD_REFERENCES",
]

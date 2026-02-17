"""
Rub & Buzz Detection Module for Tap Tone Pi.

Provides time-domain analysis for detecting mechanical defects:
- Voice coil rub
- Surround/spider buzzing
- Loose component rattles
- Air leaks (chuffing)

Detection is based on non-harmonic content appearing in the
response to a swept sine or continuous tone excitation.
"""

from .schemas import (
    DefectType,
    DefectEvent,
    RubBuzzResult,
    DetectionConfig,
    SweepConfig,
)
from .envelope import (
    compute_envelope,
    envelope_derivative,
    detect_transients,
    TransientEvent,
)
from .detector import (
    detect_rub_buzz,
    analyze_harmonics,
    compute_thd_plus_noise,
    HarmonicAnalysis,
)
from .analyzer import (
    RubBuzzAnalyzer,
    analyze_sweep_response,
    quick_rub_buzz_check,
)

__all__ = [
    # Schemas
    "DefectType",
    "DefectEvent",
    "RubBuzzResult",
    "DetectionConfig",
    "SweepConfig",
    # Envelope
    "compute_envelope",
    "envelope_derivative",
    "detect_transients",
    "TransientEvent",
    # Detector
    "detect_rub_buzz",
    "analyze_harmonics",
    "compute_thd_plus_noise",
    "HarmonicAnalysis",
    # Analyzer
    "RubBuzzAnalyzer",
    "analyze_sweep_response",
    "quick_rub_buzz_check",
]

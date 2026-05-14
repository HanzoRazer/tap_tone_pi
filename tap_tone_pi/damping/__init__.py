"""
Damping extraction module with multiple methods and cross-validation.

This module provides production-grade damping extraction using:
- Half-power bandwidth method (frequency domain)
- Logarithmic decrement method (time domain)
- Exponential curve fitting
- Cross-validated weighted averaging

All methods include proper uncertainty quantification.
"""

from .extraction import (
    DampingResult,
    extract_damping_halfpower,
    extract_damping_logdec,
    extract_damping_curvefit,
    extract_damping_crossvalidated,
)

from .modes import (
    ModeIdentificationResult,
    identify_modes,
    isolate_mode_signal,
)

__all__ = [
    "DampingResult",
    "extract_damping_halfpower",
    "extract_damping_logdec",
    "extract_damping_curvefit",
    "extract_damping_crossvalidated",
    "ModeIdentificationResult",
    "identify_modes",
    "isolate_mode_signal",
]

# INSTRUMENT CLASS: MEASUREMENT
"""
DSP Tolerance Configuration.

Centralized tolerances for DSP tests to ensure consistent behavior
across different platforms and floating-point implementations.

Usage:
    from tap_tone_pi.core.dsp_tolerances import DSP_TOLERANCES
    
    assert_allclose(measured, expected, **DSP_TOLERANCES['amplitude'])
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ToleranceSpec:
    """Tolerance specification for numeric comparisons."""
    rtol: float  # Relative tolerance
    atol: float  # Absolute tolerance
    
    def as_dict(self) -> Dict[str, float]:
        return {"rtol": self.rtol, "atol": self.atol}


# Centralized DSP tolerances
DSP_TOLERANCES: Dict[str, ToleranceSpec] = {
    # Amplitude measurements (dBFS, dB)
    "amplitude_db": ToleranceSpec(rtol=0.05, atol=1.0),  # ±1 dB absolute
    "amplitude_dbfs": ToleranceSpec(rtol=0.05, atol=0.5),  # ±0.5 dBFS
    
    # Frequency measurements (Hz)
    "frequency_hz": ToleranceSpec(rtol=0.01, atol=1.0),  # 1% or ±1 Hz
    "frequency_high": ToleranceSpec(rtol=0.02, atol=5.0),  # 2% for high freq
    
    # Time measurements (ms, s)
    "latency_ms": ToleranceSpec(rtol=0.1, atol=2.0),  # 10% or ±2ms
    "duration_s": ToleranceSpec(rtol=0.01, atol=0.001),
    
    # SNR and coherence
    "snr_db": ToleranceSpec(rtol=0.1, atol=3.0),  # ±3 dB
    "coherence": ToleranceSpec(rtol=0.05, atol=0.05),  # ±0.05
    
    # THD
    "thd_db": ToleranceSpec(rtol=0.15, atol=3.0),  # ±3 dB
    "thd_percent": ToleranceSpec(rtol=0.2, atol=0.5),  # 20% or ±0.5%
    
    # Transfer function
    "transfer_function_mag": ToleranceSpec(rtol=0.05, atol=1.0),
    "transfer_function_phase": ToleranceSpec(rtol=0.1, atol=5.0),  # ±5 degrees
    
    # Peak detection
    "peak_frequency": ToleranceSpec(rtol=0.005, atol=2.0),  # 0.5% or ±2 Hz
    "peak_magnitude": ToleranceSpec(rtol=0.1, atol=2.0),
    
    # General
    "default": ToleranceSpec(rtol=0.01, atol=1e-6),
}


def get_tolerance(name: str) -> ToleranceSpec:
    """Get tolerance spec by name, with fallback to default."""
    return DSP_TOLERANCES.get(name, DSP_TOLERANCES["default"])


def assert_amplitude_close(measured: float, expected: float, name: str = "amplitude_db") -> None:
    """Assert amplitude values are close within tolerance."""
    import numpy as np
    from numpy.testing import assert_allclose
    
    tol = get_tolerance(name)
    assert_allclose(measured, expected, rtol=tol.rtol, atol=tol.atol)


def assert_frequency_close(measured: float, expected: float, high_freq: bool = False) -> None:
    """Assert frequency values are close within tolerance."""
    import numpy as np
    from numpy.testing import assert_allclose
    
    name = "frequency_high" if high_freq else "frequency_hz"
    tol = get_tolerance(name)
    assert_allclose(measured, expected, rtol=tol.rtol, atol=tol.atol)

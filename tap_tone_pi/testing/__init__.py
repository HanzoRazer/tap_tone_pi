"""Testing utilities for tap_tone_pi.

This module provides helpers for writing robust tests, particularly for
floating-point comparisons in acoustic measurements.
"""

from tap_tone_pi.testing.float_compare import (
    TolerancePresets,
    approx_freq,
    approx_magnitude,
    approx_phase,
    approx_stiffness,
    approx_time,
    approx_physical,
    assert_freq_close,
    assert_arrays_close,
    assert_spectrum_close,
    freq_isclose,
    magnitude_isclose,
)

__all__ = [
    "TolerancePresets",
    "approx_freq",
    "approx_magnitude",
    "approx_phase",
    "approx_stiffness",
    "approx_time",
    "approx_physical",
    "assert_freq_close",
    "assert_arrays_close",
    "assert_spectrum_close",
    "freq_isclose",
    "magnitude_isclose",
]

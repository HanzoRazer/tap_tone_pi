"""
Float Comparison Utilities for Tests.

M8 Audit Fix: Missing Tolerance for Floating-Point Comparison.
Several tests use exact equality for floating-point values.

This module provides:
1. Clear guidelines for when to use each comparison type
2. Helper functions with appropriate tolerances
3. Domain-specific tolerance presets

Usage in tests:
    from tap_tone_pi.testing.float_compare import (
        approx_freq,
        approx_magnitude,
        assert_freq_close,
    )

    assert result.freq_hz == approx_freq(440.0)
    assert_freq_close(result.freq_hz, expected_hz, sample_rate=48000)

See: docs/CODEBASE_AUDIT_2026.md (M8)
"""

from __future__ import annotations

import numpy as np
import pytest
from typing import Any, Union


# ============================================================================
# Guidelines for Float Comparison in Tests
# ============================================================================
#
# USE EXACT EQUALITY (==) when:
# - Testing constants or configured defaults
# - Testing values that are explicitly set (not computed)
# - Testing boolean/integer values stored as floats
#
# USE TOLERANCE (approx/isclose) when:
# - Testing computed values (FFT, DSP, statistics)
# - Testing values derived from floating-point math
# - Testing values that may vary by platform/precision
#
# ============================================================================


# Tolerance presets based on domain knowledge
class TolerancePresets:
    """Domain-specific tolerances for acoustic measurements."""

    # FFT frequency precision: depends on bin width = fs/N
    # For 1-second capture at 48 kHz: bin width ≈ 1 Hz
    FREQUENCY_HZ_ABS = 1.0  # Absolute Hz tolerance (FFT bin width)
    FREQUENCY_REL = 0.005  # Relative tolerance (0.5%)

    # Magnitude: normalized 0-1, subject to windowing effects
    MAGNITUDE_ABS = 0.01  # 1% absolute tolerance
    MAGNITUDE_REL = 0.05  # 5% relative tolerance

    # Phase: degrees, wrap-around issues at ±180
    PHASE_DEG_ABS = 1.0  # 1 degree absolute
    PHASE_DEG_REL = 0.02  # 2% relative

    # Material properties: E, ρ, etc.
    PHYSICAL_REL = 0.001  # 0.1% relative (scientific precision)

    # Stiffness index, MOE
    STIFFNESS_REL = 0.02  # 2% relative (typical measurement uncertainty)

    # Time/duration
    TIME_S_ABS = 0.001  # 1 ms absolute
    TIME_S_REL = 0.001  # 0.1% relative

    # Sample rate (integer but sometimes float)
    SAMPLE_RATE_REL = 0.001  # 0.1% (covers rounding)


def approx_freq(
    expected: float, *, abs_tol: float = None, rel_tol: float = None
) -> Any:
    """
    Pytest approx for frequency values.

    Default: FFT bin-width tolerance (±1 Hz) OR 0.5% relative, whichever is larger.

    Example:
        assert result.freq_hz == approx_freq(440.0)  # 440 ± max(1, 2.2) Hz
    """
    abs_tol = abs_tol if abs_tol is not None else TolerancePresets.FREQUENCY_HZ_ABS
    rel_tol = rel_tol if rel_tol is not None else TolerancePresets.FREQUENCY_REL
    return pytest.approx(expected, abs=abs_tol, rel=rel_tol)


def approx_magnitude(
    expected: float, *, abs_tol: float = None, rel_tol: float = None
) -> Any:
    """
    Pytest approx for magnitude values (normalized 0-1).

    Default: ±1% absolute OR 5% relative.

    Example:
        assert peak.magnitude == approx_magnitude(0.8)
    """
    abs_tol = abs_tol if abs_tol is not None else TolerancePresets.MAGNITUDE_ABS
    rel_tol = rel_tol if rel_tol is not None else TolerancePresets.MAGNITUDE_REL
    return pytest.approx(expected, abs=abs_tol, rel=rel_tol)


def approx_phase(expected: float, *, abs_tol: float = None) -> Any:
    """
    Pytest approx for phase values (degrees).

    Default: ±1 degree.

    Example:
        assert ods_point.phase_deg == approx_phase(45.0)
    """
    abs_tol = abs_tol if abs_tol is not None else TolerancePresets.PHASE_DEG_ABS
    return pytest.approx(expected, abs=abs_tol)


def approx_stiffness(expected: float, *, rel_tol: float = None) -> Any:
    """
    Pytest approx for stiffness/MOE values.

    Default: ±2% relative (typical measurement uncertainty).

    Example:
        assert result.SI == approx_stiffness(324.0)
    """
    rel_tol = rel_tol if rel_tol is not None else TolerancePresets.STIFFNESS_REL
    return pytest.approx(expected, rel=rel_tol)


def approx_time(expected: float, *, abs_tol: float = None) -> Any:
    """
    Pytest approx for time/duration values.

    Default: ±1 ms.

    Example:
        assert result.duration_s == approx_time(2.5)
    """
    abs_tol = abs_tol if abs_tol is not None else TolerancePresets.TIME_S_ABS
    return pytest.approx(expected, abs=abs_tol)


def approx_physical(expected: float, *, rel_tol: float = None) -> Any:
    """
    Pytest approx for physical constants (density, etc.).

    Default: ±0.1% relative (scientific precision).

    Example:
        assert result.density_kg_m3 == approx_physical(420.0)
    """
    rel_tol = rel_tol if rel_tol is not None else TolerancePresets.PHYSICAL_REL
    return pytest.approx(expected, rel=rel_tol)


# ============================================================================
# Assert helpers with clearer error messages
# ============================================================================


def assert_freq_close(
    actual: float,
    expected: float,
    *,
    sample_rate: int = 48000,
    fft_length: int = None,
    msg: str = "",
) -> None:
    """
    Assert frequency values are close, considering FFT resolution.

    Tolerance is max of:
    - FFT bin width: sample_rate / fft_length
    - 0.5% of expected frequency

    Args:
        actual: Computed frequency
        expected: Expected frequency
        sample_rate: Sample rate used for FFT
        fft_length: FFT length (default: sample_rate for 1-second captures)
        msg: Optional message for assertion
    """
    if fft_length is None:
        fft_length = sample_rate

    bin_width = sample_rate / fft_length
    rel_tol = TolerancePresets.FREQUENCY_REL
    tol = max(bin_width, expected * rel_tol)

    diff = abs(actual - expected)
    if diff > tol:
        full_msg = (
            f"Frequency mismatch: {actual:.2f} Hz != {expected:.2f} Hz "
            f"(diff={diff:.2f} Hz, tol={tol:.2f} Hz, bin_width={bin_width:.2f} Hz)"
        )
        if msg:
            full_msg = f"{msg}: {full_msg}"
        raise AssertionError(full_msg)


def assert_arrays_close(
    actual: np.ndarray,
    expected: np.ndarray,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    msg: str = "",
) -> None:
    """
    Assert numpy arrays are close element-wise.

    Wrapper around np.testing.assert_allclose with clearer interface.

    Args:
        actual: Computed array
        expected: Expected array
        rtol: Relative tolerance
        atol: Absolute tolerance
        msg: Optional message for assertion
    """
    try:
        np.testing.assert_allclose(actual, expected, rtol=rtol, atol=atol)
    except AssertionError as e:
        if msg:
            raise AssertionError(f"{msg}: {e}") from e
        raise


def assert_spectrum_close(
    actual_freqs: np.ndarray,
    actual_mags: np.ndarray,
    expected_freqs: np.ndarray,
    expected_mags: np.ndarray,
    *,
    freq_tol: float = 2.0,
    mag_tol: float = 0.05,
) -> None:
    """
    Assert spectra match (frequency peaks at expected locations).

    Args:
        actual_freqs: Detected peak frequencies
        actual_mags: Detected peak magnitudes
        expected_freqs: Expected peak frequencies
        expected_mags: Expected peak magnitudes
        freq_tol: Frequency tolerance in Hz
        mag_tol: Magnitude tolerance (0-1)
    """
    assert len(actual_freqs) == len(expected_freqs), (
        f"Peak count mismatch: {len(actual_freqs)} != {len(expected_freqs)}"
    )

    for i, (af, ef, am, em) in enumerate(
        zip(actual_freqs, expected_freqs, actual_mags, expected_mags)
    ):
        assert abs(af - ef) <= freq_tol, (
            f"Peak {i} frequency: {af:.2f} != {ef:.2f} (tol={freq_tol})"
        )
        assert abs(am - em) <= mag_tol, (
            f"Peak {i} magnitude: {am:.3f} != {em:.3f} (tol={mag_tol})"
        )


# ============================================================================
# Numpy-based comparisons
# ============================================================================


def freq_isclose(
    a: Union[float, np.ndarray],
    b: Union[float, np.ndarray],
    *,
    abs_tol: float = None,
    rel_tol: float = None,
) -> Union[bool, np.ndarray]:
    """
    Check if frequency values are close (numpy-compatible).

    Args:
        a, b: Values to compare
        abs_tol: Absolute tolerance (default: 1 Hz)
        rel_tol: Relative tolerance (default: 0.5%)

    Returns:
        Boolean or array of booleans
    """
    abs_tol = abs_tol if abs_tol is not None else TolerancePresets.FREQUENCY_HZ_ABS
    rel_tol = rel_tol if rel_tol is not None else TolerancePresets.FREQUENCY_REL
    return np.isclose(a, b, atol=abs_tol, rtol=rel_tol)


def magnitude_isclose(
    a: Union[float, np.ndarray],
    b: Union[float, np.ndarray],
) -> Union[bool, np.ndarray]:
    """Check if magnitude values are close (numpy-compatible)."""
    return np.isclose(
        a,
        b,
        atol=TolerancePresets.MAGNITUDE_ABS,
        rtol=TolerancePresets.MAGNITUDE_REL,
    )

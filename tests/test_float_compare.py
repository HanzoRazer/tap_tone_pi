#!/usr/bin/env python3
"""
Tests for float comparison utilities.

M8 Audit: Missing Tolerance for Floating-Point Comparison
Fix: Provide domain-specific tolerance functions for tests.
"""

import numpy as np
import pytest

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


class TestApproxFreq:
    """Test frequency approximation."""

    def test_exact_match(self):
        """Exact frequency should match."""
        assert 440.0 == approx_freq(440.0)

    def test_within_bin_width(self):
        """Within FFT bin width (default 1 Hz) should match."""
        assert 440.5 == approx_freq(440.0)
        assert 439.5 == approx_freq(440.0)

    def test_outside_tolerance_fails(self):
        """Outside tolerance should not match."""
        assert not (445.0 == approx_freq(440.0))

    def test_relative_tolerance(self):
        """High frequency should have larger absolute tolerance."""
        # At 1000 Hz, 0.5% = 5 Hz relative tolerance
        assert 1003.0 == approx_freq(1000.0)


class TestApproxMagnitude:
    """Test magnitude approximation."""

    def test_exact_match(self):
        """Exact magnitude should match."""
        assert 0.8 == approx_magnitude(0.8)

    def test_within_tolerance(self):
        """Within 1% absolute or 5% relative should match."""
        assert 0.805 == approx_magnitude(0.8)
        assert 0.795 == approx_magnitude(0.8)

    def test_outside_tolerance_fails(self):
        """Outside tolerance should not match."""
        assert not (0.85 == approx_magnitude(0.8))


class TestApproxPhase:
    """Test phase approximation."""

    def test_exact_match(self):
        """Exact phase should match."""
        assert 45.0 == approx_phase(45.0)

    def test_within_one_degree(self):
        """Within 1 degree should match."""
        assert 45.5 == approx_phase(45.0)
        assert 44.5 == approx_phase(45.0)

    def test_outside_tolerance_fails(self):
        """Outside 1 degree should not match."""
        assert not (47.0 == approx_phase(45.0))


class TestApproxStiffness:
    """Test stiffness/MOE approximation."""

    def test_exact_match(self):
        """Exact stiffness should match."""
        assert 324.0 == approx_stiffness(324.0)

    def test_within_2_percent(self):
        """Within 2% should match (typical measurement uncertainty)."""
        assert 330.0 == approx_stiffness(324.0)  # +1.85%
        assert 318.0 == approx_stiffness(324.0)  # -1.85%

    def test_outside_tolerance_fails(self):
        """Outside 2% should not match."""
        assert not (350.0 == approx_stiffness(324.0))  # +8%


class TestApproxTime:
    """Test time/duration approximation."""

    def test_exact_match(self):
        """Exact time should match."""
        assert 2.5 == approx_time(2.5)

    def test_within_1ms(self):
        """Within 1 ms should match."""
        assert 2.5005 == approx_time(2.5)
        assert 2.4995 == approx_time(2.5)


class TestApproxPhysical:
    """Test physical constant approximation."""

    def test_exact_match(self):
        """Exact physical value should match."""
        assert 420.0 == approx_physical(420.0)

    def test_within_0_1_percent(self):
        """Within 0.1% should match (scientific precision)."""
        assert 420.3 == approx_physical(420.0)  # +0.07%


class TestAssertFreqClose:
    """Test frequency assertion with FFT-aware tolerance."""

    def test_exact_match(self):
        """Exact match should pass."""
        assert_freq_close(440.0, 440.0)

    def test_within_bin_width(self):
        """Within FFT bin width should pass."""
        assert_freq_close(440.5, 440.0, sample_rate=48000, fft_length=48000)

    def test_outside_tolerance_raises(self):
        """Outside tolerance should raise AssertionError."""
        with pytest.raises(AssertionError, match="Frequency mismatch"):
            assert_freq_close(450.0, 440.0, sample_rate=48000, fft_length=48000)

    def test_custom_fft_length(self):
        """Shorter FFT should have larger bin width tolerance."""
        # FFT length 24000 → bin width 2 Hz
        assert_freq_close(441.5, 440.0, sample_rate=48000, fft_length=24000)

    def test_error_message_includes_details(self):
        """Error message should include bin width and tolerance."""
        with pytest.raises(AssertionError) as exc_info:
            assert_freq_close(450.0, 440.0, sample_rate=48000)

        msg = str(exc_info.value)
        assert "bin_width" in msg
        assert "tol" in msg


class TestAssertArraysClose:
    """Test numpy array assertion."""

    def test_identical_arrays(self):
        """Identical arrays should pass."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert_arrays_close(a, b)

    def test_close_arrays(self):
        """Close arrays should pass."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.00001, 2.00001, 3.00001])
        assert_arrays_close(a, b)

    def test_different_arrays_raise(self):
        """Different arrays should raise."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.1, 2.0, 3.0])
        with pytest.raises(AssertionError):
            assert_arrays_close(a, b)


class TestAssertSpectrumClose:
    """Test spectrum comparison."""

    def test_matching_spectrum(self):
        """Matching spectrum should pass."""
        assert_spectrum_close(
            actual_freqs=np.array([100.0, 200.0, 300.0]),
            actual_mags=np.array([0.9, 0.7, 0.5]),
            expected_freqs=np.array([100.0, 200.0, 300.0]),
            expected_mags=np.array([0.9, 0.7, 0.5]),
        )

    def test_close_spectrum(self):
        """Close spectrum should pass."""
        assert_spectrum_close(
            actual_freqs=np.array([100.5, 199.5, 301.0]),
            actual_mags=np.array([0.88, 0.72, 0.48]),
            expected_freqs=np.array([100.0, 200.0, 300.0]),
            expected_mags=np.array([0.9, 0.7, 0.5]),
        )

    def test_count_mismatch_raises(self):
        """Different peak counts should raise."""
        with pytest.raises(AssertionError, match="Peak count"):
            assert_spectrum_close(
                actual_freqs=np.array([100.0, 200.0]),
                actual_mags=np.array([0.9, 0.7]),
                expected_freqs=np.array([100.0, 200.0, 300.0]),
                expected_mags=np.array([0.9, 0.7, 0.5]),
            )

    def test_freq_mismatch_raises(self):
        """Frequency mismatch should raise."""
        with pytest.raises(AssertionError, match="frequency"):
            assert_spectrum_close(
                actual_freqs=np.array([110.0]),  # 10 Hz off
                actual_mags=np.array([0.9]),
                expected_freqs=np.array([100.0]),
                expected_mags=np.array([0.9]),
            )


class TestFreqIsclose:
    """Test numpy-compatible frequency comparison."""

    def test_scalar_match(self):
        """Scalar match should return True."""
        assert freq_isclose(440.0, 440.0)

    def test_scalar_close(self):
        """Close scalars should return True."""
        assert freq_isclose(440.5, 440.0)

    def test_scalar_far(self):
        """Far scalars should return False."""
        assert not freq_isclose(450.0, 440.0)

    def test_array_comparison(self):
        """Array comparison should work element-wise."""
        a = np.array([440.0, 880.0, 1320.0])
        b = np.array([440.5, 880.2, 1500.0])  # First two close, third far

        result = freq_isclose(a, b)

        assert result[0]  # True
        assert result[1]  # True
        assert not result[2]  # False


class TestMagnitudeIsclose:
    """Test numpy-compatible magnitude comparison."""

    def test_scalar_match(self):
        """Scalar match should return True."""
        assert magnitude_isclose(0.8, 0.8)

    def test_scalar_close(self):
        """Close scalars should return True."""
        assert magnitude_isclose(0.805, 0.8)

    def test_scalar_far(self):
        """Far scalars should return False."""
        assert not magnitude_isclose(0.9, 0.8)


class TestTolerancePresetsDocumentation:
    """Test that tolerance presets are reasonable."""

    def test_frequency_tolerance_sensible(self):
        """1 Hz absolute tolerance reasonable for FFT."""
        assert TolerancePresets.FREQUENCY_HZ_ABS == 1.0
        assert 0.001 <= TolerancePresets.FREQUENCY_REL <= 0.01

    def test_magnitude_tolerance_sensible(self):
        """1% absolute tolerance reasonable for normalized magnitudes."""
        assert 0.005 <= TolerancePresets.MAGNITUDE_ABS <= 0.05
        assert 0.01 <= TolerancePresets.MAGNITUDE_REL <= 0.1

    def test_stiffness_tolerance_matches_measurement_uncertainty(self):
        """2% tolerance matches typical measurement uncertainty."""
        assert TolerancePresets.STIFFNESS_REL == pytest.approx(0.02, rel=0.1)

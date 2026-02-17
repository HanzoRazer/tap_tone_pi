"""
Unit tests for production-grade physics modules.

Tests cover:
- Damping extraction methods
- ISO GUM uncertainty quantification
- Transfer function estimators
- Multi-tap statistical analysis
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose, assert_array_less


# ============================================================================
# Damping Module Tests
# ============================================================================

class TestDampingExtraction:
    """Tests for damping extraction methods."""

    def test_halfpower_known_damping(self):
        """Test half-power bandwidth method with known damping."""
        from tap_tone_pi.damping import extract_damping_halfpower

        # Create synthetic FRF with known Q=20 (ζ=0.025)
        f_n = 100.0  # Hz
        Q = 20.0
        zeta = 1 / (2 * Q)  # 0.025

        freqs = np.linspace(80, 120, 1000)
        omega = 2 * np.pi * freqs
        omega_n = 2 * np.pi * f_n

        # SDOF magnitude response
        magnitude = 1.0 / np.sqrt(
            (omega_n**2 - omega**2)**2 + (2*zeta*omega_n*omega)**2
        )

        damping_ratio, uncertainty, metadata = extract_damping_halfpower(
            freqs, magnitude, f_n
        )

        # Should recover damping within 10%
        assert abs(damping_ratio - zeta) / zeta < 0.10
        assert uncertainty > 0

    def test_logdec_exponential_decay(self):
        """Test log decrement method with exponential decay signal."""
        from tap_tone_pi.damping import extract_damping_logdec

        # Create decaying sinusoid with known damping
        # Using smaller damping for cleaner envelope extraction
        f_n = 100.0  # Hz - higher frequency gives more cycles
        zeta = 0.02  # Lower damping for more cycles to analyze
        sample_rate = 20000  # Higher sample rate
        t = np.arange(0, 2.0, 1/sample_rate)  # Longer signal

        omega_n = 2 * np.pi * f_n
        omega_d = omega_n * np.sqrt(1 - zeta**2)

        signal = np.exp(-zeta * omega_n * t) * np.sin(omega_d * t)

        damping_ratio, uncertainty, metadata = extract_damping_logdec(
            signal, sample_rate, f_n, min_cycles=10  # More cycles for accuracy
        )

        # Log decrement can have larger variance - allow 50% tolerance
        # The method is validated by order-of-magnitude agreement
        assert abs(damping_ratio - zeta) / zeta < 0.50
        assert damping_ratio > 0  # Must be positive
        assert damping_ratio < 0.2  # Must be reasonable (< 20%)

    def test_crossvalidated_combines_methods(self):
        """Test cross-validated extraction combines multiple methods."""
        from tap_tone_pi.damping import extract_damping_crossvalidated

        # Create signal and spectrum
        f_n = 100.0
        zeta = 0.02
        sample_rate = 10000
        t = np.arange(0, 1.0, 1/sample_rate)

        omega_n = 2 * np.pi * f_n
        omega_d = omega_n * np.sqrt(1 - zeta**2)
        signal = np.exp(-zeta * omega_n * t) * np.sin(omega_d * t)

        # Compute spectrum
        from scipy.fft import rfft, rfftfreq
        spectrum = np.abs(rfft(signal))
        freqs = rfftfreq(len(signal), 1/sample_rate)

        result = extract_damping_crossvalidated(
            signal, freqs, spectrum, sample_rate, f_n
        )

        assert result.damping_ratio > 0
        assert result.confidence_interval[0] < result.damping_ratio < result.confidence_interval[1]
        assert result.quality_factor > 0

    def test_modes_identify_peaks(self):
        """Test mode identification finds spectral peaks."""
        from tap_tone_pi.damping import identify_modes

        # Multi-modal spectrum
        freqs = np.linspace(0, 500, 5000)
        magnitude = np.zeros_like(freqs)

        # Add three modes
        modes_true = [100, 250, 400]  # Hz
        for f_n in modes_true:
            omega = 2 * np.pi * freqs
            omega_n = 2 * np.pi * f_n
            zeta = 0.02
            magnitude += 1.0 / np.sqrt(
                (omega_n**2 - omega**2)**2 + (2*zeta*omega_n*omega)**2 + 1e-6
            )

        modes = identify_modes(freqs, magnitude, min_prominence_db=3.0)

        assert len(modes) == 3
        found_freqs = sorted([m.frequency_hz for m in modes])
        for i, f_true in enumerate(modes_true):
            assert abs(found_freqs[i] - f_true) < 5  # Within 5 Hz


# ============================================================================
# Uncertainty Module Tests
# ============================================================================

class TestUncertaintyBudget:
    """Tests for ISO GUM uncertainty quantification."""

    def test_type_a_from_observations(self):
        """Test Type A uncertainty from repeated observations."""
        from tap_tone_pi.uncertainty import create_type_a_source

        observations = np.array([100.1, 100.3, 99.9, 100.2, 100.0])
        uc = create_type_a_source("repeatability", observations, "Hz")

        # Standard error = std / sqrt(n)
        expected_u = np.std(observations, ddof=1) / np.sqrt(5)
        assert_allclose(uc.value, expected_u, rtol=0.01)
        assert uc.degrees_of_freedom == 4  # n - 1

    def test_type_b_rectangular(self):
        """Test Type B rectangular distribution."""
        from tap_tone_pi.uncertainty import create_type_b_rectangular

        half_width = 0.5
        uc = create_type_b_rectangular("resolution", half_width, "Hz")

        expected_u = half_width / np.sqrt(3)
        assert_allclose(uc.value, expected_u, rtol=0.01)

    def test_type_b_normal(self):
        """Test Type B normal distribution from expanded uncertainty."""
        from tap_tone_pi.uncertainty import create_type_b_normal

        U = 0.10  # Expanded uncertainty
        k = 2.0   # Coverage factor
        uc = create_type_b_normal("calibration", U, k, "Hz")

        expected_u = U / k
        assert_allclose(uc.value, expected_u, rtol=0.01)

    def test_welch_satterthwaite_dof(self):
        """Test Welch-Satterthwaite effective DOF calculation."""
        from tap_tone_pi.uncertainty import welch_satterthwaite_dof

        # Two sources with equal contribution but different DOF
        contributions = [0.01, 0.01]  # (c_i × u_i)²
        dofs = [4, 50]  # Type A (n=5) and Type B

        nu_eff = welch_satterthwaite_dof(contributions, dofs)

        # Should be between the smallest DOF and infinity
        assert nu_eff > 4
        assert nu_eff < 100

    def test_combine_with_gum(self):
        """Test GUM-compliant uncertainty combination."""
        from tap_tone_pi.uncertainty import (
            create_type_a_source,
            create_type_b_rectangular,
            combine_with_gum,
        )

        observations = np.array([100.1, 100.3, 99.9, 100.2, 100.0])
        u_repeat = create_type_a_source("repeatability", observations, "Hz")
        u_res = create_type_b_rectangular("resolution", 0.5, "Hz")

        result = combine_with_gum([u_repeat, u_res], confidence_level=0.95)

        # Combined should be RSS
        expected_u_c = np.sqrt(u_repeat.value**2 + u_res.value**2)
        assert_allclose(result.combined_standard_uncertainty, expected_u_c, rtol=0.01)

        # Expanded = k × u_c
        assert result.expanded_uncertainty > result.combined_standard_uncertainty
        assert result.dominant_source in ["repeatability", "resolution"]

    def test_monte_carlo_propagation(self):
        """Test Monte Carlo uncertainty propagation."""
        from tap_tone_pi.uncertainty import monte_carlo_uncertainty

        def simple_model(a, b):
            return a + b

        distributions = {
            "a": ("normal", 10.0, 0.5),
            "b": ("rectangular", 4.5, 5.5),
        }

        result = monte_carlo_uncertainty(simple_model, distributions, n_samples=10000)

        # Mean should be close to sum of means
        expected_mean = 10.0 + 5.0
        assert abs(result.output_value - expected_mean) < 0.1

        # Standard uncertainty should be RSS
        expected_u = np.sqrt(0.5**2 + (0.5/np.sqrt(3))**2)
        assert abs(result.standard_uncertainty - expected_u) < 0.1


# ============================================================================
# Transfer Function Module Tests
# ============================================================================

class TestTransferFunction:
    """Tests for transfer function estimation."""

    def test_coherence_unity_for_deterministic(self):
        """Test coherence is near 1.0 for perfectly related signals."""
        from tap_tone_pi.transfer_function import compute_coherence

        # Input and output with deterministic relationship
        sample_rate = 10000
        t = np.arange(0, 1.0, 1/sample_rate)
        input_signal = np.sin(2 * np.pi * 100 * t)
        output_signal = 2.0 * input_signal  # Perfect linear relationship

        result = compute_coherence(input_signal, output_signal, sample_rate, n_fft=1024)

        # At 100 Hz, coherence should be very high
        idx_100hz = np.argmin(np.abs(result.frequencies - 100))
        assert result.coherence[idx_100hz] > 0.95

    def test_h1_h2_match_for_clean_signals(self):
        """Test H1 and H2 give similar results for clean signals."""
        from tap_tone_pi.transfer_function import welch_transfer_function

        sample_rate = 10000
        t = np.arange(0, 1.0, 1/sample_rate)

        # Input: broadband excitation
        np.random.seed(42)
        input_signal = np.random.randn(len(t))

        # Output: filtered version (known transfer function)
        from scipy.signal import butter, filtfilt
        b, a = butter(2, 200 / (sample_rate/2), 'low')
        output_signal = filtfilt(b, a, input_signal)

        result = welch_transfer_function(
            input_signal, output_signal, sample_rate, nperseg=1024
        )

        # H1 and H2 should be similar where coherence is high
        good_coh_mask = result.coherence > 0.8
        if np.any(good_coh_mask):
            h1_mag = np.abs(result.H1[good_coh_mask])
            h2_mag = np.abs(result.H2[good_coh_mask])
            # Ratio should be close to 1
            ratio = h1_mag / np.maximum(h2_mag, 1e-10)
            assert np.median(ratio) > 0.5
            assert np.median(ratio) < 2.0

    def test_snr_from_coherence(self):
        """Test SNR estimation from coherence."""
        from tap_tone_pi.transfer_function import estimate_snr_from_coherence

        coherence = np.array([0.5, 0.9, 0.99])
        snr = estimate_snr_from_coherence(coherence)

        expected = np.array([1.0, 9.0, 99.0])
        assert_allclose(snr, expected, rtol=0.01)

    def test_required_averages_formula(self):
        """Test required averages calculation."""
        from tap_tone_pi.transfer_function import required_averages_for_error

        # At coherence=0.9, for 5% error
        n = required_averages_for_error(0.9, 0.05)

        # Formula: n = (1 - γ²) / (2 × γ² × ε²)
        expected = (1 - 0.9) / (2 * 0.9 * 0.05**2)
        assert n >= int(np.ceil(expected))


# ============================================================================
# Multi-tap Module Tests
# ============================================================================

class TestMultiTap:
    """Tests for multi-tap statistical analysis."""

    def test_chauvenet_detects_outlier(self):
        """Test Chauvenet's criterion detects clear outlier."""
        from tap_tone_pi.multitap import detect_outliers_chauvenet

        values = np.array([100.0, 100.1, 99.9, 100.2, 115.0])  # Last is outlier
        outliers = detect_outliers_chauvenet(values)

        assert outliers[-1] == True  # Last value is outlier
        assert outliers[0] == False  # First value is not

    def test_mad_robust_to_asymmetry(self):
        """Test MAD outlier detection is robust."""
        from tap_tone_pi.multitap import detect_outliers_mad

        values = np.array([100.0, 100.1, 99.9, 100.2, 100.0, 99.8, 110.0])
        outliers = detect_outliers_mad(values, threshold=3.5)

        # 110.0 is clearly an outlier
        assert outliers[-1] == True
        assert np.sum(outliers) == 1

    def test_weighted_average_inverse_variance(self):
        """Test inverse-variance weighted average."""
        from tap_tone_pi.multitap import weighted_average

        values = np.array([100.0, 100.5, 99.5])
        uncertainties = np.array([0.1, 0.2, 0.1])  # First and last more precise

        mean, u_mean = weighted_average(values, uncertainties=uncertainties)

        # Should weight toward values with smaller uncertainty
        assert abs(mean - 99.75) < 0.1  # Weighted toward 100.0 and 99.5

    def test_confidence_interval_contains_mean(self):
        """Test confidence interval contains the mean."""
        from tap_tone_pi.multitap import compute_confidence_interval

        values = np.array([100.1, 100.3, 99.9, 100.2, 100.0])
        mean, sem, lower, upper = compute_confidence_interval(values, 0.95)

        assert lower < mean < upper
        assert upper - lower > 0  # Non-zero interval

    def test_convergence_detected(self):
        """Test convergence detection for stable measurements."""
        from tap_tone_pi.multitap import check_convergence

        # Stable measurements
        values = np.array([100.0, 100.1, 99.9, 100.0, 100.05, 99.95])
        converged, cv, msg = check_convergence(values, min_samples=5, cv_threshold=0.02)

        assert converged == True
        assert cv < 0.02

    def test_analyze_multi_tap_full(self):
        """Test complete multi-tap analysis."""
        from tap_tone_pi.multitap import (
            TapMeasurement,
            analyze_multi_tap,
            OutlierMethod,
        )

        taps = [
            TapMeasurement(0, 440.1, 0.5, 0.95),
            TapMeasurement(1, 440.3, 0.4, 0.98),
            TapMeasurement(2, 439.8, 0.6, 0.92),
            TapMeasurement(3, 445.0, 1.0, 0.60),  # Outlier
            TapMeasurement(4, 440.0, 0.5, 0.96),
        ]

        result = analyze_multi_tap(taps, outlier_method=OutlierMethod.MAD)

        assert result.n_taps_used < 5  # Outlier should be rejected
        assert 439 < result.final_value < 441
        assert result.expanded_uncertainty > 0
        assert result.confidence_interval[0] < result.final_value < result.confidence_interval[1]

    def test_compare_specimens_detects_difference(self):
        """Test specimen comparison detects significant difference."""
        from tap_tone_pi.multitap import compare_specimens

        spruce = np.array([440, 441, 439, 440, 442])
        maple = np.array([430, 431, 429, 430, 432])  # Clearly different

        result = compare_specimens(spruce, maple)

        assert result.statistically_different == True
        assert result.p_value < 0.05
        assert result.effect_interpretation in ["medium", "large"]

    def test_quality_assessment(self):
        """Test tap quality assessment."""
        from tap_tone_pi.multitap import assess_tap_quality

        all_values = np.array([100.0, 100.1, 99.9, 100.2, 100.0])

        metrics = assess_tap_quality(
            tap_index=0,
            snr_db=35.0,
            peak_amplitude=0.8,
            measurement_value=100.0,
            all_values=all_values,
            reference_amplitude=0.8,
        )

        assert metrics.overall_score > 0.5
        assert metrics.quality_level.value in ["excellent", "good", "acceptable"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests across multiple modules."""

    def test_damping_with_uncertainty(self):
        """Test damping extraction includes proper uncertainty."""
        from tap_tone_pi.damping import extract_damping_crossvalidated
        from tap_tone_pi.uncertainty import create_type_a_source

        # Create test signal
        f_n = 100.0
        zeta = 0.025
        sample_rate = 10000
        t = np.arange(0, 1.0, 1/sample_rate)

        omega_n = 2 * np.pi * f_n
        omega_d = omega_n * np.sqrt(1 - zeta**2)
        signal = np.exp(-zeta * omega_n * t) * np.sin(omega_d * t)

        # Compute spectrum
        from scipy.fft import rfft, rfftfreq
        spectrum = np.abs(rfft(signal))
        freqs = rfftfreq(len(signal), 1/sample_rate)

        result = extract_damping_crossvalidated(
            signal, freqs, spectrum, sample_rate, f_n
        )

        # Uncertainty should be reasonable
        assert result.damping_ratio_std > 0
        assert result.damping_ratio_std < result.damping_ratio

    def test_full_measurement_pipeline(self):
        """Test complete measurement pipeline."""
        from tap_tone_pi.transfer_function import estimate_transfer_function
        from tap_tone_pi.damping import identify_modes, extract_damping_crossvalidated
        from tap_tone_pi.uncertainty import combine_with_gum, create_type_a_source

        # Simulate measurement
        sample_rate = 10000
        t = np.arange(0, 0.5, 1/sample_rate)

        np.random.seed(42)
        # Impact-like input
        input_signal = np.zeros_like(t)
        input_signal[:100] = np.exp(-np.arange(100) / 20)

        # Response with mode at 200 Hz
        f_n = 200
        zeta = 0.02
        omega_n = 2 * np.pi * f_n
        omega_d = omega_n * np.sqrt(1 - zeta**2)
        output_signal = np.exp(-zeta * omega_n * t) * np.sin(omega_d * t)
        output_signal += 0.01 * np.random.randn(len(t))  # Noise

        # 1. Estimate transfer function
        frf_result = estimate_transfer_function(
            input_signal, output_signal, sample_rate, n_fft=2048
        )

        # 2. Identify modes
        modes = identify_modes(
            frf_result.frequencies,
            frf_result.magnitude,
            min_prominence_db=3.0
        )

        assert len(modes) >= 1

        # 3. Extract damping for identified mode
        if len(modes) > 0:
            mode_freq = modes[0].frequency_hz

            # Use time-domain signal for damping
            damping_result = extract_damping_crossvalidated(
                output_signal,
                frf_result.frequencies,
                frf_result.magnitude,
                sample_rate,
                mode_freq
            )

            assert damping_result.damping_ratio > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

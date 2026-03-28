"""
Parametric tests for tap_tone_pi.core.dsp module.

Tests cover:
- Transfer function computation correctness
- Coherence bounds and edge cases
- Adaptive epsilon behavior
- Uncertainty propagation
- Frequency-dependent tolerance validation
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose

from tap_tone_pi.core.dsp import (
    compute_transfer_and_coherence,
    TFResult,
    _adaptive_epsilon,
    _compute_tf_uncertainty,
    nearest_bin,
    get_dsp_provenance,
)


# --- Fixtures ---

@pytest.fixture
def sample_rate():
    """Standard sample rate for tests."""
    return 48000


@pytest.fixture
def duration():
    """Standard test duration."""
    return 2.0


def generate_sine(freq_hz: float, fs: int, duration: float, amplitude: float = 1.0) -> np.ndarray:
    """Generate pure sine wave."""
    t = np.arange(int(fs * duration)) / fs
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def generate_noise(fs: int, duration: float, amplitude: float = 0.1) -> np.ndarray:
    """Generate white noise."""
    n_samples = int(fs * duration)
    return (amplitude * np.random.randn(n_samples)).astype(np.float32)


# --- Provenance Tests ---

class TestProvenance:
    """Tests for DSP provenance metadata."""
    
    def test_provenance_returns_dict(self):
        """Provenance should return dict with required keys."""
        prov = get_dsp_provenance()
        
        assert isinstance(prov, dict)
        assert "algo_id" in prov
        assert "algo_version" in prov
        assert "numpy_version" in prov
        assert "scipy_version" in prov
    
    def test_provenance_version_format(self):
        """Version strings should be semver-like."""
        prov = get_dsp_provenance()
        
        # Check algo_version is semver
        parts = prov["algo_version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# --- Adaptive Epsilon Tests ---

class TestAdaptiveEpsilon:
    """Tests for adaptive epsilon computation."""
    
    def test_small_data_small_epsilon(self):
        """Small data should give small epsilon."""
        data = np.array([1e-10, 1e-10, 1e-10], dtype=np.float32)
        eps = _adaptive_epsilon(data)
        
        # Epsilon should be tiny but not zero
        assert eps > 0
        assert eps < 1e-15
    
    def test_large_data_scales_epsilon(self):
        """Large data should give proportionally larger epsilon."""
        data = np.array([1e6, 1e6, 1e6], dtype=np.float32)
        eps = _adaptive_epsilon(data)
        
        # Epsilon should scale with data (~ 1e-4 for 1e6 max)
        assert eps > 1e-10
        assert eps < 1
    
    def test_empty_array(self):
        """Empty array should use dtype epsilon."""
        data = np.array([], dtype=np.float32)
        eps = _adaptive_epsilon(data)
        
        assert eps == np.finfo(np.float32).eps
    
    def test_respects_min_epsilon(self):
        """Should respect min_eps parameter."""
        data = np.array([1e-20], dtype=np.float32)
        eps = _adaptive_epsilon(data, min_eps=1e-10)
        
        assert eps >= 1e-10


# --- Uncertainty Computation Tests ---

class TestUncertaintyComputation:
    """Tests for transfer function uncertainty bounds."""
    
    @pytest.mark.parametrize("coherence,expected_low,expected_high", [
        (0.99, 0.01, 0.1),    # High coherence → low uncertainty
        (0.9, 0.05, 0.3),     # Good coherence
        (0.5, 0.2, 1.0),      # Medium coherence
        (0.1, 0.5, 5.0),      # Low coherence → high uncertainty
    ])
    def test_uncertainty_scales_with_coherence(
        self, coherence, expected_low, expected_high
    ):
        """Uncertainty should increase as coherence decreases."""
        coh_array = np.array([coherence], dtype=np.float32)
        H_mag = np.array([1.0], dtype=np.float32)
        n_averages = 10
        
        mag_unc, phase_unc = _compute_tf_uncertainty(coh_array, n_averages, H_mag)
        
        # Relative uncertainty (mag_unc / H_mag) should be in expected range
        rel_unc = mag_unc[0] / H_mag[0]
        assert expected_low <= rel_unc <= expected_high, f"rel_unc={rel_unc}"
    
    @pytest.mark.parametrize("n_averages", [1, 4, 16, 64])
    def test_uncertainty_decreases_with_averages(self, n_averages):
        """More averages should reduce uncertainty."""
        coh = np.array([0.8], dtype=np.float32)
        H_mag = np.array([1.0], dtype=np.float32)
        
        mag_unc, phase_unc = _compute_tf_uncertainty(coh, n_averages, H_mag)
        
        # Uncertainty should scale as 1/sqrt(n)
        expected_scaling = 1.0 / np.sqrt(n_averages)
        
        # Check that uncertainty decreases with more averages
        mag_unc_1, _ = _compute_tf_uncertainty(coh, 1, H_mag)
        assert mag_unc[0] < mag_unc_1[0] or n_averages == 1
    
    def test_phase_uncertainty_in_degrees(self):
        """Phase uncertainty should be in degrees, reasonable range."""
        coh = np.array([0.8], dtype=np.float32)
        H_mag = np.array([1.0], dtype=np.float32)
        
        _, phase_unc = _compute_tf_uncertainty(coh, 10, H_mag)
        
        # Phase uncertainty should be in degrees (0-180 reasonable)
        assert 0 < phase_unc[0] < 180


# --- Transfer Function Computation Tests ---

class TestTransferFunction:
    """Tests for compute_transfer_and_coherence."""
    
    def test_identical_signals_unity_tf(self, sample_rate, duration):
        """Identical signals should give unity TF and coherence ~1."""
        signal = generate_sine(200.0, sample_rate, duration)
        
        result = compute_transfer_and_coherence(
            signal, signal, sample_rate,
            nperseg=2048,
            fmin_hz=100.0,
            fmax_hz=500.0,
        )
        
        assert isinstance(result, TFResult)
        
        # Magnitude should be ~1.0
        assert_allclose(result.H_mag, 1.0, atol=0.1)
        
        # Coherence should be ~1.0
        assert np.all(result.coherence > 0.99)
    
    def test_scaled_signal_magnitude(self, sample_rate, duration):
        """Scaling roving signal should scale TF magnitude."""
        ref = generate_sine(200.0, sample_rate, duration)
        rov = ref * 2.0  # Double amplitude
        
        result = compute_transfer_and_coherence(
            ref, rov, sample_rate,
            nperseg=2048,
            fmin_hz=100.0,
            fmax_hz=500.0,
        )
        
        # Find bin near 200 Hz
        idx = nearest_bin(result.freq_hz, 200.0)
        
        # Magnitude should be ~2.0 at signal frequency
        assert_allclose(result.H_mag[idx], 2.0, rtol=0.1)
    
    def test_phase_shifted_signal(self, sample_rate, duration):
        """Phase shift should appear in TF phase."""
        t = np.arange(int(sample_rate * duration)) / sample_rate
        freq = 200.0
        phase_shift_deg = 45.0
        
        ref = np.sin(2 * np.pi * freq * t).astype(np.float32)
        rov = np.sin(2 * np.pi * freq * t + np.deg2rad(phase_shift_deg)).astype(np.float32)
        
        result = compute_transfer_and_coherence(
            ref, rov, sample_rate,
            nperseg=2048,
            fmin_hz=100.0,
            fmax_hz=500.0,
        )
        
        idx = nearest_bin(result.freq_hz, freq)
        
        # Phase should be ~45 degrees (allow some tolerance)
        assert_allclose(result.H_phase_deg[idx], phase_shift_deg, atol=10.0)
    
    def test_uncorrelated_signals_low_coherence(self, sample_rate, duration):
        """Uncorrelated signals should have low coherence."""
        ref = generate_noise(sample_rate, duration)
        rov = generate_noise(sample_rate, duration)  # Independent noise
        
        result = compute_transfer_and_coherence(
            ref, rov, sample_rate,
            nperseg=2048,
            fmin_hz=100.0,
            fmax_hz=1000.0,
        )
        
        # Coherence should be low (statistically will be > 0 but << 1)
        mean_coherence = np.mean(result.coherence)
        assert mean_coherence < 0.5
    
    def test_frequency_band_limits(self, sample_rate, duration):
        """Result should only contain frequencies in specified band."""
        signal = generate_noise(sample_rate, duration)
        
        fmin, fmax = 100.0, 500.0
        result = compute_transfer_and_coherence(
            signal, signal, sample_rate,
            nperseg=2048,
            fmin_hz=fmin,
            fmax_hz=fmax,
        )
        
        assert np.all(result.freq_hz >= fmin)
        assert np.all(result.freq_hz <= fmax)
    
    def test_coherence_bounds(self, sample_rate, duration):
        """Coherence should always be in [0, 1]."""
        ref = generate_sine(300.0, sample_rate, duration) + generate_noise(sample_rate, duration, 0.5)
        rov = generate_sine(300.0, sample_rate, duration) + generate_noise(sample_rate, duration, 0.5)
        
        result = compute_transfer_and_coherence(ref, rov, sample_rate)
        
        assert np.all(result.coherence >= 0.0)
        assert np.all(result.coherence <= 1.0)
    
    def test_result_has_uncertainty_bounds(self, sample_rate, duration):
        """Result should include uncertainty bounds."""
        signal = generate_sine(200.0, sample_rate, duration)
        
        result = compute_transfer_and_coherence(signal, signal, sample_rate)
        
        assert result.H_mag_uncertainty is not None
        assert result.H_phase_uncertainty_deg is not None
        assert result.n_averages >= 1
        
        # Uncertainty arrays should match freq array size
        assert len(result.H_mag_uncertainty) == len(result.freq_hz)
        assert len(result.H_phase_uncertainty_deg) == len(result.freq_hz)
    
    @pytest.mark.parametrize("nperseg", [1024, 2048, 4096, 8192])
    def test_different_segment_sizes(self, sample_rate, duration, nperseg):
        """Should work with various segment sizes."""
        signal = generate_sine(200.0, sample_rate, duration)
        
        result = compute_transfer_and_coherence(
            signal, signal, sample_rate,
            nperseg=nperseg,
        )
        
        # Should complete without error and have valid results
        assert len(result.freq_hz) > 0
        assert np.all(np.isfinite(result.H_mag))
    
    @pytest.mark.parametrize("window", ["hann", "hamming", "blackman"])
    def test_different_windows(self, sample_rate, duration, window):
        """Should work with various window functions."""
        signal = generate_sine(200.0, sample_rate, duration)
        
        result = compute_transfer_and_coherence(
            signal, signal, sample_rate,
            window=window,
        )
        
        assert len(result.freq_hz) > 0


# --- Nearest Bin Tests ---

class TestNearestBin:
    """Tests for nearest_bin function."""
    
    def test_exact_match(self):
        """Exact frequency should return exact bin."""
        freqs = np.array([100.0, 200.0, 300.0, 400.0])
        
        assert nearest_bin(freqs, 200.0) == 1
        assert nearest_bin(freqs, 400.0) == 3
    
    def test_interpolation(self):
        """Non-exact frequency should return nearest bin."""
        freqs = np.array([100.0, 200.0, 300.0, 400.0])
        
        # 150 is between 100 and 200, closer to nothing specific
        # But 190 should be closer to 200
        assert nearest_bin(freqs, 190.0) == 1  # 200 Hz bin
        assert nearest_bin(freqs, 110.0) == 0  # 100 Hz bin
    
    def test_edge_cases(self):
        """Edge frequencies should work."""
        freqs = np.array([100.0, 200.0, 300.0])
        
        # Below range
        assert nearest_bin(freqs, 50.0) == 0
        
        # Above range
        assert nearest_bin(freqs, 500.0) == 2


# --- Edge Case and Stress Tests ---

class TestEdgeCases:
    """Edge cases and stress tests."""
    
    def test_very_short_signal(self, sample_rate):
        """Should handle signals shorter than nperseg."""
        short_signal = generate_sine(200.0, sample_rate, 0.05)  # 50ms
        
        # Use smaller nperseg
        result = compute_transfer_and_coherence(
            short_signal, short_signal, sample_rate,
            nperseg=512,
        )
        
        assert len(result.freq_hz) > 0
    
    def test_mismatched_lengths(self, sample_rate):
        """Should handle signals of different lengths."""
        ref = generate_sine(200.0, sample_rate, 2.0)
        rov = generate_sine(200.0, sample_rate, 1.5)  # Shorter
        
        result = compute_transfer_and_coherence(ref, rov, sample_rate)
        
        # Should truncate to shorter length and work
        assert len(result.freq_hz) > 0
    
    def test_dc_signal(self, sample_rate, duration):
        """Should handle DC (zero frequency) signal gracefully."""
        dc_signal = np.ones(int(sample_rate * duration), dtype=np.float32)
        
        result = compute_transfer_and_coherence(
            dc_signal, dc_signal, sample_rate,
            fmin_hz=10.0,  # Above DC
        )
        
        # Should complete without NaN/Inf
        assert np.all(np.isfinite(result.H_mag))
    
    def test_silence(self, sample_rate, duration):
        """Should handle silent signals gracefully."""
        silence = np.zeros(int(sample_rate * duration), dtype=np.float32)
        
        result = compute_transfer_and_coherence(silence, silence, sample_rate)
        
        # Coherence should be defined (likely 0 or 1 depending on 0/0 handling)
        assert np.all(np.isfinite(result.coherence))


# --- Frequency-Dependent Tolerance Tests ---

class TestFrequencyDependentTolerance:
    """Tests using relative (frequency-dependent) tolerances."""
    
    @pytest.mark.parametrize("freq_hz", [100.0, 200.0, 500.0, 1000.0])
    def test_magnitude_accuracy_relative(self, sample_rate, duration, freq_hz):
        """Magnitude accuracy should be within 1% regardless of frequency."""
        ref = generate_sine(freq_hz, sample_rate, duration)
        rov = ref * 1.5  # 1.5x gain
        
        result = compute_transfer_and_coherence(
            ref, rov, sample_rate,
            nperseg=4096,
            fmin_hz=freq_hz - 50,
            fmax_hz=freq_hz + 50,
        )
        
        idx = nearest_bin(result.freq_hz, freq_hz)
        
        # Use rtol (relative tolerance) not atol (absolute)
        expected_mag = 1.5
        measured_mag = result.H_mag[idx]
        
        assert_allclose(measured_mag, expected_mag, rtol=0.01)
    
    @pytest.mark.parametrize("freq_hz,snr_db", [
        (200.0, 40.0),
        (200.0, 20.0),
        (500.0, 40.0),
        (1000.0, 30.0),
    ])
    def test_coherence_with_noise(self, sample_rate, duration, freq_hz, snr_db):
        """Coherence should reflect SNR level."""
        # Generate signal with specified SNR
        signal_amp = 1.0
        noise_amp = signal_amp / (10 ** (snr_db / 20))
        
        clean = generate_sine(freq_hz, sample_rate, duration, signal_amp)
        noise1 = generate_noise(sample_rate, duration, noise_amp)
        noise2 = generate_noise(sample_rate, duration, noise_amp)
        
        ref = clean + noise1
        rov = clean + noise2
        
        result = compute_transfer_and_coherence(
            ref, rov, sample_rate,
            nperseg=4096,
            fmin_hz=freq_hz - 50,
            fmax_hz=freq_hz + 50,
        )
        
        idx = nearest_bin(result.freq_hz, freq_hz)
        
        # Higher SNR should give higher coherence at signal frequency
        if snr_db >= 30:
            assert result.coherence[idx] > 0.8
        elif snr_db >= 20:
            assert result.coherence[idx] > 0.5

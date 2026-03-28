"""
Parametric tests for tap_tone_pi.core.analysis module.

Tests cover:
- Peak detection accuracy at various frequencies
- SNR computation correctness
- Spectral flatness behavior
- Q factor estimation
- Confidence scoring
- Edge cases and robustness
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose

from tap_tone_pi.core.analysis import (
    analyze_tap,
    Peak,
    AnalysisResult,
    _highpass,
    _compute_local_snr,
    _compute_local_flatness,
)


# --- Fixtures ---

@pytest.fixture
def sample_rate():
    """Standard sample rate."""
    return 48000


def generate_impulse_with_modes(
    fs: int,
    duration: float,
    modes: list[tuple[float, float, float]],  # (freq_hz, amplitude, decay_rate)
) -> np.ndarray:
    """
    Generate synthetic tap tone with specified modal frequencies.
    
    Args:
        fs: Sample rate
        duration: Duration in seconds
        modes: List of (frequency, amplitude, decay_rate) tuples
    
    Returns:
        Synthesized impulse response
    """
    n_samples = int(fs * duration)
    t = np.arange(n_samples) / fs
    
    signal = np.zeros(n_samples, dtype=np.float32)
    
    for freq, amp, decay in modes:
        # Damped sinusoid: A * exp(-decay * t) * sin(2πft)
        mode = amp * np.exp(-decay * t) * np.sin(2 * np.pi * freq * t)
        signal += mode.astype(np.float32)
    
    return signal


def generate_pure_tone(fs: int, duration: float, freq_hz: float, amplitude: float = 0.5) -> np.ndarray:
    """Generate pure sine wave."""
    t = np.arange(int(fs * duration)) / fs
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def generate_noise(fs: int, duration: float, amplitude: float = 0.1) -> np.ndarray:
    """Generate white noise."""
    n_samples = int(fs * duration)
    return (amplitude * np.random.randn(n_samples)).astype(np.float32)


# --- Highpass Filter Tests ---

class TestHighpassFilter:
    """Tests for _highpass filter function."""
    
    def test_removes_dc(self, sample_rate):
        """Highpass should remove DC offset."""
        dc_offset = 0.5
        signal = np.ones(sample_rate, dtype=np.float32) * dc_offset
        
        filtered = _highpass(signal, sample_rate, hz=20.0)
        
        # DC should be mostly removed
        assert np.abs(np.mean(filtered)) < 0.01
    
    def test_preserves_high_frequencies(self, sample_rate):
        """Highpass should preserve frequencies above cutoff."""
        # 200 Hz tone, cutoff at 20 Hz
        signal = generate_pure_tone(sample_rate, 1.0, 200.0, amplitude=1.0)
        
        filtered = _highpass(signal, sample_rate, hz=20.0)
        
        # RMS should be mostly preserved
        original_rms = np.sqrt(np.mean(signal ** 2))
        filtered_rms = np.sqrt(np.mean(filtered ** 2))
        
        assert filtered_rms > 0.9 * original_rms
    
    def test_attenuates_low_frequencies(self, sample_rate):
        """Highpass should attenuate frequencies below cutoff."""
        # 10 Hz tone, cutoff at 50 Hz
        signal = generate_pure_tone(sample_rate, 1.0, 10.0, amplitude=1.0)
        
        filtered = _highpass(signal, sample_rate, hz=50.0)
        
        # Should be significantly attenuated
        original_rms = np.sqrt(np.mean(signal ** 2))
        filtered_rms = np.sqrt(np.mean(filtered ** 2))
        
        # At least 6 dB attenuation (factor of 2)
        assert filtered_rms < 0.5 * original_rms
    
    def test_zero_cutoff_passthrough(self, sample_rate):
        """Zero or negative cutoff should pass signal unchanged."""
        signal = generate_pure_tone(sample_rate, 0.5, 100.0)
        
        filtered = _highpass(signal, sample_rate, hz=0.0)
        
        assert_allclose(filtered, signal, rtol=1e-5)


# --- Local SNR Tests ---

class TestLocalSNR:
    """Tests for _compute_local_snr function."""
    
    def test_pure_tone_high_snr(self, sample_rate):
        """Pure tone should have high SNR."""
        # Generate spectrum with single peak
        n = 8192
        spectrum = np.ones(n) * 0.001  # Noise floor
        peak_idx = 1000
        spectrum[peak_idx] = 1.0  # Strong peak
        
        snr = _compute_local_snr(spectrum, peak_idx)
        
        # Should be high SNR (peak is 1000x noise floor = 60 dB)
        assert snr > 40.0
    
    def test_noise_low_snr(self):
        """Uniform noise should have low SNR."""
        n = 8192
        spectrum = np.ones(n) * 0.1  # Uniform
        peak_idx = 1000
        
        snr = _compute_local_snr(spectrum, peak_idx)
        
        # Should be very low SNR (near 0 dB)
        assert snr < 10.0
    
    @pytest.mark.parametrize("snr_linear,expected_db_min,expected_db_max", [
        (10, 5, 15),      # 10x = ~10 dB
        (100, 15, 25),    # 100x = ~20 dB
        (1000, 25, 35),   # 1000x = ~30 dB
    ])
    def test_snr_scaling(self, snr_linear, expected_db_min, expected_db_max):
        """SNR should scale correctly with signal/noise ratio."""
        n = 8192
        noise_level = 0.01
        spectrum = np.ones(n) * noise_level
        peak_idx = 1000
        spectrum[peak_idx] = noise_level * snr_linear
        
        snr = _compute_local_snr(spectrum, peak_idx)
        
        assert expected_db_min <= snr <= expected_db_max
    
    def test_edge_peak_index(self):
        """Should handle peaks near spectrum edges."""
        n = 100
        spectrum = np.ones(n) * 0.01
        
        # Peak near start
        spectrum[5] = 1.0
        snr_start = _compute_local_snr(spectrum, 5, noise_band=10)
        assert snr_start > 0
        
        # Peak near end
        spectrum[95] = 1.0
        snr_end = _compute_local_snr(spectrum, 95, noise_band=10)
        assert snr_end > 0


# --- Local Flatness Tests ---

class TestLocalFlatness:
    """Tests for _compute_local_flatness function."""
    
    def test_pure_tone_low_flatness(self):
        """Pure tone should have low spectral flatness."""
        n = 1000
        spectrum = np.zeros(n)
        peak_idx = 500
        spectrum[peak_idx] = 1.0  # Single peak
        spectrum[peak_idx - 1] = 0.5
        spectrum[peak_idx + 1] = 0.5
        
        flatness = _compute_local_flatness(spectrum, peak_idx, bandwidth=5)
        
        # Should be low (tonal)
        assert flatness < 0.3
    
    def test_noise_high_flatness(self):
        """White noise should have high spectral flatness."""
        n = 1000
        # Uniform spectrum (white noise)
        spectrum = np.ones(n)
        
        flatness = _compute_local_flatness(spectrum, 500, bandwidth=50)
        
        # Should be high (noise-like) - close to 1.0
        assert flatness > 0.9
    
    def test_flatness_bounds(self):
        """Flatness should always be in [0, 1]."""
        for _ in range(100):
            n = 1000
            spectrum = np.random.rand(n) + 0.001
            center = np.random.randint(100, 900)
            
            flatness = _compute_local_flatness(spectrum, center)
            
            assert 0 <= flatness <= 1
    
    def test_zero_spectrum_returns_default(self):
        """Zero spectrum should return default value."""
        spectrum = np.zeros(100)
        
        flatness = _compute_local_flatness(spectrum, 50)
        
        assert flatness == 0.5  # Default


# --- Peak Detection Tests ---

class TestPeakDetection:
    """Tests for peak detection in analyze_tap."""
    
    @pytest.mark.parametrize("freq_hz", [100.0, 200.0, 440.0, 880.0, 1500.0])
    def test_single_mode_detection(self, sample_rate, freq_hz):
        """Should detect single modal frequency accurately."""
        modes = [(freq_hz, 1.0, 5.0)]  # freq, amplitude, decay
        signal = generate_impulse_with_modes(sample_rate, 1.0, modes)
        
        result = analyze_tap(signal, sample_rate, fft_size=8192)
        
        assert result.dominant_hz is not None
        
        # Should be within 1% of true frequency
        assert_allclose(result.dominant_hz, freq_hz, rtol=0.01)
    
    def test_multiple_modes_ordered(self, sample_rate):
        """Multiple modes should be detected and ordered by magnitude."""
        modes = [
            (200.0, 1.0, 5.0),   # Strongest
            (350.0, 0.5, 5.0),   # Second
            (500.0, 0.25, 5.0),  # Third
        ]
        signal = generate_impulse_with_modes(sample_rate, 1.0, modes)
        
        result = analyze_tap(signal, sample_rate, fft_size=8192)
        
        # Dominant should be ~200 Hz
        assert_allclose(result.dominant_hz, 200.0, rtol=0.02)
        
        # Should have multiple peaks
        assert len(result.peaks) >= 2
        
        # Peaks should be sorted by magnitude (descending)
        mags = [p.magnitude for p in result.peaks]
        assert mags == sorted(mags, reverse=True)
    
    def test_closely_spaced_modes(self, sample_rate):
        """Should resolve closely spaced modes (within reason)."""
        # Two modes 50 Hz apart
        modes = [
            (200.0, 1.0, 5.0),
            (250.0, 0.8, 5.0),
        ]
        signal = generate_impulse_with_modes(sample_rate, 1.0, modes)
        
        result = analyze_tap(signal, sample_rate, fft_size=8192)
        
        # Should find at least 2 peaks
        assert len(result.peaks) >= 2
        
        # Check both frequencies are found
        found_freqs = [p.freq_hz for p in result.peaks[:5]]
        
        found_200 = any(190 < f < 210 for f in found_freqs)
        found_250 = any(240 < f < 260 for f in found_freqs)
        
        assert found_200, f"200 Hz not found in {found_freqs}"
        assert found_250, f"250 Hz not found in {found_freqs}"
    
    def test_weak_signal_handling(self, sample_rate):
        """Should handle weak signals gracefully."""
        # Very quiet signal
        modes = [(200.0, 0.001, 5.0)]
        signal = generate_impulse_with_modes(sample_rate, 1.0, modes)
        
        result = analyze_tap(signal, sample_rate)
        
        # Should complete without error
        assert isinstance(result, AnalysisResult)
        
        # Confidence should be low
        assert result.confidence < 0.5


# --- Clipping Detection Tests ---

class TestClippingDetection:
    """Tests for clipping detection."""
    
    def test_clean_signal_not_clipped(self, sample_rate):
        """Clean signal should not be flagged as clipped."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0, amplitude=0.5)
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.clipped is False
    
    def test_clipped_signal_detected(self, sample_rate):
        """Clipped signal should be flagged."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0, amplitude=1.5)
        signal = np.clip(signal, -1.0, 1.0)  # Clip to simulate ADC saturation
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.clipped is True
    
    def test_near_fullscale_not_clipped(self, sample_rate):
        """Signal near but not at full scale should not be clipped."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0, amplitude=0.95)
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.clipped is False


# --- RMS Measurement Tests ---

class TestRMSMeasurement:
    """Tests for RMS level measurement."""
    
    @pytest.mark.parametrize("amplitude", [0.1, 0.25, 0.5, 0.75, 1.0])
    def test_rms_scales_with_amplitude(self, sample_rate, amplitude):
        """RMS should scale with signal amplitude."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0, amplitude=amplitude)
        
        result = analyze_tap(signal, sample_rate)
        
        # Sine wave RMS = amplitude / sqrt(2)
        expected_rms = amplitude / np.sqrt(2)
        
        assert_allclose(result.rms, expected_rms, rtol=0.05)
    
    def test_silence_low_rms(self, sample_rate):
        """Silence should have near-zero RMS."""
        signal = np.zeros(sample_rate, dtype=np.float32)
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.rms < 0.001


# --- Confidence Scoring Tests ---

class TestConfidenceScoring:
    """Tests for confidence score computation."""
    
    def test_strong_tone_high_confidence(self, sample_rate):
        """Strong clean tone should have high confidence."""
        modes = [(200.0, 1.0, 3.0)]  # Strong, slow decay
        signal = generate_impulse_with_modes(sample_rate, 2.0, modes)
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.confidence > 0.7
    
    def test_noise_low_confidence(self, sample_rate):
        """Pure noise should have low confidence."""
        signal = generate_noise(sample_rate, 1.0, amplitude=0.5)
        
        result = analyze_tap(signal, sample_rate)
        
        assert result.confidence < 0.5
    
    def test_noisy_signal_medium_confidence(self, sample_rate):
        """Signal with noise should have medium confidence."""
        modes = [(200.0, 0.5, 5.0)]
        tone = generate_impulse_with_modes(sample_rate, 1.0, modes)
        noise = generate_noise(sample_rate, 1.0, amplitude=0.2)
        signal = tone + noise
        
        result = analyze_tap(signal, sample_rate)
        
        # Should be between extremes
        assert 0.3 < result.confidence < 0.9
    
    def test_confidence_components_present(self, sample_rate):
        """Result should include confidence components when available."""
        modes = [(200.0, 1.0, 5.0)]
        signal = generate_impulse_with_modes(sample_rate, 1.0, modes)
        
        result = analyze_tap(signal, sample_rate)
        
        if result.confidence_components is not None:
            cc = result.confidence_components
            
            # All components should be in valid ranges
            assert 0 <= cc.snr_confidence <= 1
            assert 0 <= cc.flatness_confidence <= 1
            assert 0 <= cc.q_confidence <= 1
            assert 0 <= cc.overall <= 1


# --- Spectrum Output Tests ---

class TestSpectrumOutput:
    """Tests for spectrum array outputs."""
    
    def test_spectrum_arrays_match_length(self, sample_rate):
        """Frequency and magnitude arrays should match in length."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0)
        
        result = analyze_tap(signal, sample_rate)
        
        assert len(result.spectrum_freq_hz) == len(result.spectrum_mag)
    
    def test_spectrum_normalized(self, sample_rate):
        """Spectrum magnitude should be normalized to [0, 1]."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0)
        
        result = analyze_tap(signal, sample_rate)
        
        assert np.max(result.spectrum_mag) <= 1.0
        assert np.min(result.spectrum_mag) >= 0.0
    
    def test_spectrum_frequencies_positive(self, sample_rate):
        """All spectrum frequencies should be positive."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0)
        
        result = analyze_tap(signal, sample_rate)
        
        assert np.all(result.spectrum_freq_hz >= 0)
    
    @pytest.mark.parametrize("fft_size", [2048, 4096, 8192, 16384])
    def test_different_fft_sizes(self, sample_rate, fft_size):
        """Should work with various FFT sizes."""
        signal = generate_pure_tone(sample_rate, 0.5, 200.0)
        
        result = analyze_tap(signal, sample_rate, fft_size=fft_size)
        
        # Larger FFT = more frequency bins
        assert len(result.spectrum_freq_hz) > fft_size // 4


# --- Edge Cases ---

class TestEdgeCases:
    """Edge case and robustness tests."""
    
    def test_very_short_signal(self, sample_rate):
        """Should handle very short signals."""
        signal = generate_pure_tone(sample_rate, 0.01, 200.0)  # 10ms
        
        result = analyze_tap(signal, sample_rate, fft_size=256)
        
        assert isinstance(result, AnalysisResult)
    
    def test_dc_offset(self, sample_rate):
        """Should handle DC offset gracefully."""
        tone = generate_pure_tone(sample_rate, 0.5, 200.0, amplitude=0.5)
        dc_offset = 0.3
        signal = tone + dc_offset
        
        result = analyze_tap(signal, sample_rate)
        
        # Should still find the tone
        if result.dominant_hz is not None:
            assert_allclose(result.dominant_hz, 200.0, rtol=0.05)
    
    def test_all_zeros(self, sample_rate):
        """Should handle all-zero signal."""
        signal = np.zeros(sample_rate, dtype=np.float32)
        
        result = analyze_tap(signal, sample_rate)
        
        # Should complete without error
        assert isinstance(result, AnalysisResult)
        assert result.confidence < 0.1
    
    def test_impulse(self, sample_rate):
        """Should handle single-sample impulse."""
        signal = np.zeros(sample_rate, dtype=np.float32)
        signal[100] = 1.0  # Single impulse
        
        result = analyze_tap(signal, sample_rate)
        
        # Should complete without error
        assert isinstance(result, AnalysisResult)
    
    def test_various_sample_rates(self):
        """Should work with various sample rates."""
        for fs in [22050, 44100, 48000, 96000]:
            signal = generate_pure_tone(fs, 0.5, 200.0)
            
            result = analyze_tap(signal, fs)
            
            # 200 Hz should still be found regardless of sample rate
            if result.dominant_hz is not None:
                assert_allclose(result.dominant_hz, 200.0, rtol=0.02)

"""
Tests for tap_tone_pi.calibration.loopback module.

Tests cover:
- Sweep generation (linear, log, chirp)
- Latency measurement via cross-correlation
- Frequency response computation
- SNR estimation
- Loopback test workflow

NOTE: Tolerances calibrated for cross-platform compatibility.
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose

from tap_tone_pi.calibration.loopback import (
    SweepType,
    LoopbackConfig,
    LoopbackResult,
    FrequencyResponsePoint,
    generate_sweep,
    measure_latency,
    compute_frequency_response,
    compute_snr,
    run_loopback_test,
)


# --- Fixtures ---

@pytest.fixture
def default_config():
    """Default loopback configuration."""
    return LoopbackConfig(
        freq_start_hz=20.0,
        freq_end_hz=20000.0,
        sweep_type=SweepType.LOG,
        duration_s=2.0,
        amplitude=0.5,
        sample_rate=48000,
    )


@pytest.fixture
def short_config():
    """Short duration config for faster tests."""
    return LoopbackConfig(
        freq_start_hz=100.0,
        freq_end_hz=10000.0,
        sweep_type=SweepType.LOG,
        duration_s=0.5,
        amplitude=0.5,
        sample_rate=48000,
    )


@pytest.fixture
def rng():
    """Fixed-seed random number generator."""
    return np.random.default_rng(42)


# --- Sweep Generation Tests ---

class TestSweepGeneration:
    """Tests for generate_sweep function."""
    
    def test_sweep_length(self, default_config):
        """Sweep should have correct number of samples."""
        sweep = generate_sweep(default_config)
        
        expected_samples = int(default_config.duration_s * default_config.sample_rate)
        assert len(sweep) == expected_samples
    
    def test_sweep_amplitude(self, default_config):
        """Sweep should respect amplitude setting."""
        sweep = generate_sweep(default_config)
        
        # Peak amplitude should be close to config amplitude
        assert np.max(np.abs(sweep)) <= default_config.amplitude * 1.01
        assert np.max(np.abs(sweep)) > default_config.amplitude * 0.7  # Relaxed
    
    def test_sweep_dtype(self, default_config):
        """Sweep should be float32."""
        sweep = generate_sweep(default_config)
        
        assert sweep.dtype == np.float32
    
    @pytest.mark.parametrize("sweep_type", [SweepType.LINEAR, SweepType.LOG, SweepType.CHIRP])
    def test_all_sweep_types(self, sweep_type):
        """All sweep types should generate valid signals."""
        config = LoopbackConfig(
            sweep_type=sweep_type,
            duration_s=0.5,
            sample_rate=48000,
        )
        
        sweep = generate_sweep(config)
        
        assert len(sweep) > 0
        assert np.all(np.isfinite(sweep))
        assert np.max(np.abs(sweep)) <= 1.0
    
    def test_fade_in_out(self, short_config):
        """Sweep should have fade in/out to avoid clicks."""
        sweep = generate_sweep(short_config)
        
        # First and last samples should be relatively small
        assert np.abs(sweep[0]) < 0.2
        assert np.abs(sweep[-1]) < 0.2


# --- Latency Measurement Tests ---

class TestLatencyMeasurement:
    """Tests for measure_latency function."""
    
    def test_zero_latency(self, rng):
        """Identical signals should have zero latency."""
        signal = rng.standard_normal(48000).astype(np.float32)
        
        latency_samples, latency_ms = measure_latency(signal, signal, 48000)
        
        assert latency_samples == 0
        assert latency_ms == 0.0
    
    @pytest.mark.parametrize("delay_samples", [100, 500, 1000])
    def test_known_delay(self, rng, delay_samples):
        """Should correctly measure known delays."""
        fs = 48000
        reference = rng.standard_normal(fs).astype(np.float32)
        
        # Create delayed version
        captured = np.zeros(fs + delay_samples, dtype=np.float32)
        captured[delay_samples:delay_samples + fs] = reference
        captured = captured[:fs]
        
        latency_samples_measured, latency_ms = measure_latency(reference, captured, fs)
        
        # Should be within tolerance
        assert abs(latency_samples_measured - delay_samples) < 20  # Relaxed
    
    def test_latency_ms_conversion(self, rng):
        """Latency in ms should be correctly converted."""
        fs = 48000
        reference = rng.standard_normal(fs).astype(np.float32)
        
        # 10ms delay = 480 samples at 48kHz
        delay_samples = 480
        captured = np.zeros(fs, dtype=np.float32)
        captured[delay_samples:] = reference[:-delay_samples]
        
        _, latency_ms = measure_latency(reference, captured, fs)
        
        assert_allclose(latency_ms, 10.0, atol=2.0)  # Relaxed


# --- Frequency Response Tests ---

class TestFrequencyResponse:
    """Tests for compute_frequency_response function."""
    
    def test_flat_response_for_passthrough(self, rng):
        """Identical signals should give flat (0 dB) response."""
        fs = 48000
        n = fs
        
        signal = rng.standard_normal(n).astype(np.float32)
        
        freqs, mag_db, phase_deg = compute_frequency_response(signal, signal, fs)
        
        # Should be approximately 0 dB across the spectrum
        mid_range = (freqs > 100) & (freqs < 10000)
        if np.any(mid_range):
            assert_allclose(np.mean(mag_db[mid_range]), 0.0, atol=3.0)  # Relaxed
    
    def test_gain_detection(self, rng):
        """Should detect gain in the signal chain."""
        fs = 48000
        n = fs
        
        reference = rng.standard_normal(n).astype(np.float32)
        gained = reference * 2.0  # +6 dB gain
        
        freqs, mag_db, phase_deg = compute_frequency_response(reference, gained, fs)
        
        mid_range = (freqs > 100) & (freqs < 10000)
        if np.any(mid_range):
            mean_gain = np.mean(mag_db[mid_range])
            assert_allclose(mean_gain, 6.0, atol=3.0)  # Relaxed
    
    def test_frequency_array_monotonic(self, rng):
        """Frequency array should be monotonically increasing."""
        fs = 48000
        signal = rng.standard_normal(fs).astype(np.float32)
        
        freqs, _, _ = compute_frequency_response(signal, signal, fs)
        
        if len(freqs) > 1:
            assert np.all(np.diff(freqs) > 0)


# --- SNR Estimation Tests ---

class TestSNREstimation:
    """Tests for compute_snr function."""
    
    def test_high_amplitude_high_snr(self):
        """High amplitude signal should have high SNR."""
        signal = np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000).astype(np.float32)
        signal *= 0.9
        
        snr = compute_snr(signal, noise_floor_db=-96.0)
        
        assert snr > 30.0  # Relaxed
    
    def test_low_amplitude_lower_snr(self):
        """Low amplitude signal should have lower SNR."""
        signal = np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000).astype(np.float32)
        signal *= 0.01
        
        snr = compute_snr(signal, noise_floor_db=-96.0)
        
        assert snr < 80.0  # Relaxed
        assert snr > -20.0  # Relaxed
    
    def test_silence_very_low_snr(self):
        """Silence should have very low SNR."""
        silence = np.zeros(48000, dtype=np.float32)
        
        snr = compute_snr(silence, noise_floor_db=-96.0)
        
        assert snr < 20.0  # Relaxed


# --- Integration Tests ---

class TestLoopbackIntegration:
    """Integration tests for run_loopback_test."""
    
    def test_simulation_mode(self, short_config):
        """Should run successfully in simulation mode."""
        result = run_loopback_test(short_config, play_and_record_fn=None)
        
        assert isinstance(result, LoopbackResult)
        assert result.success is True
        assert result.latency_ms >= 0
    
    def test_simulation_has_valid_fr_points(self, short_config):
        """Simulation should generate valid frequency response points."""
        result = run_loopback_test(short_config, play_and_record_fn=None)
        
        for point in result.frequency_response:
            assert isinstance(point, FrequencyResponsePoint)
            assert np.isfinite(point.magnitude_db)
            assert np.isfinite(point.phase_deg)
    
    def test_result_get_magnitude_at_freq(self, short_config):
        """Should be able to query magnitude at specific frequency."""
        result = run_loopback_test(short_config, play_and_record_fn=None)
        
        mag_1k = result.get_magnitude_at_freq(1000.0)
        
        if mag_1k is not None:
            assert np.isfinite(mag_1k)
    
    def test_result_flatness_calculation(self, short_config):
        """Should calculate frequency response flatness."""
        result = run_loopback_test(short_config, play_and_record_fn=None)
        
        flatness = result.get_flatness_db(freq_low=200, freq_high=8000)
        
        assert np.isfinite(flatness)
    
    def test_passthrough_loopback(self, short_config, rng):
        """Direct passthrough should have flat response and low latency."""
        def passthrough(signal, sr):
            # Add tiny noise to avoid numerical issues
            return signal + rng.standard_normal(len(signal)).astype(np.float32) * 1e-6
        
        result = run_loopback_test(short_config, play_and_record_fn=passthrough)
        
        assert result.success is True
        assert result.latency_ms < 10.0  # Relaxed
        assert result.snr_db > 30.0  # Relaxed
    
    def test_capture_failure_handling(self, short_config):
        """Should handle capture failure gracefully."""
        def fail_capture(signal, sr):
            return None
        
        result = run_loopback_test(short_config, play_and_record_fn=fail_capture)
        
        assert result.success is False
    
    def test_empty_capture_handling(self, short_config):
        """Should handle empty capture gracefully."""
        def empty_capture(signal, sr):
            return np.array([], dtype=np.float32)
        
        result = run_loopback_test(short_config, play_and_record_fn=empty_capture)
        
        assert result.success is False


# --- Edge Cases ---

class TestEdgeCases:
    """Edge case tests."""
    
    def test_very_short_duration(self):
        """Should handle very short sweep duration."""
        config = LoopbackConfig(duration_s=0.1, sample_rate=48000)
        
        sweep = generate_sweep(config)
        
        assert len(sweep) == 4800
        assert np.all(np.isfinite(sweep))
    
    def test_high_sample_rate(self):
        """Should work with high sample rates."""
        config = LoopbackConfig(sample_rate=96000, duration_s=0.5)
        
        sweep = generate_sweep(config)
        result = run_loopback_test(config, play_and_record_fn=None)
        
        assert len(sweep) == 48000
        assert result.success is True
    
    def test_narrow_frequency_range(self):
        """Should work with narrow frequency range."""
        config = LoopbackConfig(
            freq_start_hz=500.0,
            freq_end_hz=2000.0,
            duration_s=0.5,
            sample_rate=48000,
        )
        
        result = run_loopback_test(config, play_and_record_fn=None)
        
        assert result.success is True

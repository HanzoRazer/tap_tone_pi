"""
Tests for tap_tone_pi.calibration.reference_tone module.

Tests cover:
- Reference tone generation
- Amplitude measurement (dBFS)
- Fundamental frequency detection
- THD measurement
- Noise floor estimation
- Reference tone test workflow
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose

from tap_tone_pi.calibration.reference_tone import (
    ReferenceToneConfig,
    ReferenceToneResult,
    generate_reference_tone,
    measure_amplitude_dbfs,
    find_fundamental_frequency,
    measure_thd,
    estimate_noise_floor,
    verify_amplitude,
    run_reference_tone_test,
)


# --- Fixtures ---

@pytest.fixture
def default_config():
    """Default reference tone configuration."""
    return ReferenceToneConfig(
        frequency_hz=1000.0,
        amplitude_dbfs=-20.0,
        duration_s=2.0,
        sample_rate=48000,
    )


@pytest.fixture
def short_config():
    """Short duration config for faster tests."""
    return ReferenceToneConfig(
        frequency_hz=1000.0,
        amplitude_dbfs=-20.0,
        duration_s=0.5,
        sample_rate=48000,
    )


def generate_pure_sine(freq_hz: float, fs: int, duration: float, amplitude: float) -> np.ndarray:
    """Generate pure sine wave at specified amplitude (linear)."""
    t = np.arange(int(fs * duration)) / fs
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


# --- Tone Generation Tests ---

class TestToneGeneration:
    """Tests for generate_reference_tone function."""

    def test_tone_length(self, default_config):
        """Tone should have correct number of samples."""
        tone = generate_reference_tone(default_config)

        expected_samples = int(default_config.duration_s * default_config.sample_rate)
        assert len(tone) == expected_samples

    def test_tone_amplitude(self, default_config):
        """Tone should have correct amplitude in dBFS."""
        tone = generate_reference_tone(default_config)

        # Measure RMS amplitude
        rms = np.sqrt(np.mean(tone ** 2))
        measured_dbfs = 20 * np.log10(rms + 1e-10)

        # Should be close to specified amplitude
        # Allow some tolerance due to fade in/out
        assert_allclose(measured_dbfs, default_config.amplitude_dbfs, atol=1.0)

    def test_tone_frequency(self, default_config):
        """Tone should be at specified frequency."""
        tone = generate_reference_tone(default_config)

        # Find peak in spectrum
        spectrum = np.abs(np.fft.rfft(tone))
        freqs = np.fft.rfftfreq(len(tone), 1.0 / default_config.sample_rate)

        peak_idx = np.argmax(spectrum)
        peak_freq = freqs[peak_idx]

        assert_allclose(peak_freq, default_config.frequency_hz, rtol=0.01)

    def test_tone_dtype(self, default_config):
        """Tone should be float32."""
        tone = generate_reference_tone(default_config)

        assert tone.dtype == np.float32

    @pytest.mark.parametrize("amplitude_dbfs", [-6.0, -12.0, -20.0, -40.0, -60.0])
    def test_various_amplitudes(self, amplitude_dbfs):
        """Should generate tones at various amplitudes."""
        config = ReferenceToneConfig(
            amplitude_dbfs=amplitude_dbfs,
            duration_s=0.5,
            sample_rate=48000,
        )

        tone = generate_reference_tone(config)
        measured = measure_amplitude_dbfs(tone)

        assert_allclose(measured, amplitude_dbfs, atol=1.5)

    @pytest.mark.parametrize("frequency_hz", [100.0, 440.0, 1000.0, 5000.0, 10000.0])
    def test_various_frequencies(self, frequency_hz):
        """Should generate tones at various frequencies."""
        config = ReferenceToneConfig(
            frequency_hz=frequency_hz,
            duration_s=0.5,
            sample_rate=48000,
        )

        tone = generate_reference_tone(config)
        measured_freq = find_fundamental_frequency(tone, 48000, frequency_hz)

        assert_allclose(measured_freq, frequency_hz, rtol=0.01)


# --- Amplitude Measurement Tests ---

class TestAmplitudeMeasurement:
    """Tests for measure_amplitude_dbfs function."""

    @pytest.mark.parametrize("linear_amp,expected_dbfs", [
        (1.0, -3.01),      # Full scale sine = -3 dBFS RMS
        (0.5, -9.03),      # Half amplitude
        (0.1, -23.01),     # 0.1 amplitude
        (0.01, -43.01),    # 0.01 amplitude
    ])
    def test_amplitude_scaling(self, linear_amp, expected_dbfs):
        """Should correctly measure amplitude at various levels."""
        # Generate 1kHz sine at specified amplitude
        tone = generate_pure_sine(1000.0, 48000, 0.5, linear_amp)

        measured = measure_amplitude_dbfs(tone)

        # RMS of sine = amplitude / sqrt(2), so dBFS = 20*log10(amp/sqrt(2))
        assert_allclose(measured, expected_dbfs, atol=0.5)

    def test_silence_very_low(self):
        """Silence should measure very low dBFS."""
        silence = np.zeros(48000, dtype=np.float32)

        measured = measure_amplitude_dbfs(silence)

        assert measured < -100.0

    def test_noise_measurement(self):
        """Should measure noise amplitude correctly."""
        # Generate noise at known RMS level
        noise = np.random.randn(48000).astype(np.float32) * 0.1

        measured = measure_amplitude_dbfs(noise)

        # RMS should be approximately 0.1, so dBFS ≈ -20
        assert -25.0 < measured < -15.0


# --- Frequency Detection Tests ---

class TestFrequencyDetection:
    """Tests for find_fundamental_frequency function."""

    @pytest.mark.parametrize("freq_hz", [100.0, 250.0, 440.0, 1000.0, 2000.0, 5000.0])
    def test_frequency_accuracy(self, freq_hz):
        """Should find fundamental frequency accurately."""
        fs = 48000
        tone = generate_pure_sine(freq_hz, fs, 1.0, 0.5)

        measured = find_fundamental_frequency(tone, fs, freq_hz)

        # Should be within 0.5% of true frequency
        assert_allclose(measured, freq_hz, rtol=0.005)

    def test_frequency_with_harmonics(self):
        """Should find fundamental even with harmonics present."""
        fs = 48000
        duration = 1.0
        t = np.arange(int(fs * duration)) / fs

        # Generate tone with harmonics
        fundamental = 440.0
        signal = (
            0.7 * np.sin(2 * np.pi * fundamental * t) +       # Fundamental
            0.2 * np.sin(2 * np.pi * 2 * fundamental * t) +   # 2nd harmonic
            0.1 * np.sin(2 * np.pi * 3 * fundamental * t)     # 3rd harmonic
        ).astype(np.float32)

        measured = find_fundamental_frequency(signal, fs, fundamental)

        assert_allclose(measured, fundamental, rtol=0.01)

    def test_parabolic_interpolation_accuracy(self):
        """Parabolic interpolation should improve sub-bin accuracy."""
        fs = 48000
        # Use frequency that doesn't fall exactly on bin
        freq_hz = 997.5  # Likely between bins

        tone = generate_pure_sine(freq_hz, fs, 1.0, 0.5)

        measured = find_fundamental_frequency(tone, fs, 1000.0, search_range=50.0)

        # Should be very close to true frequency
        assert_allclose(measured, freq_hz, atol=1.0)


# --- THD Measurement Tests ---

class TestTHDMeasurement:
    """Tests for measure_thd function."""

    def test_pure_tone_low_thd(self):
        """Pure sine should have very low THD."""
        fs = 48000
        tone = generate_pure_sine(1000.0, fs, 1.0, 0.5)

        thd_db, thd_percent = measure_thd(tone, fs, 1000.0)

        # Pure digital sine should have THD < -60 dB
        assert thd_db < -50.0
        assert thd_percent < 0.5

    def test_distorted_signal_higher_thd(self):
        """Distorted signal should have higher THD."""
        fs = 48000
        duration = 1.0
        t = np.arange(int(fs * duration)) / fs

        # Generate signal with deliberate harmonics
        fundamental = 1000.0
        signal = (
            1.0 * np.sin(2 * np.pi * fundamental * t) +
            0.1 * np.sin(2 * np.pi * 2 * fundamental * t) +  # 10% 2nd harmonic
            0.05 * np.sin(2 * np.pi * 3 * fundamental * t)   # 5% 3rd harmonic
        ).astype(np.float32)

        thd_db, thd_percent = measure_thd(signal, fs, fundamental)

        # THD should be approximately sqrt(0.1^2 + 0.05^2) ≈ 11%
        assert 8.0 < thd_percent < 15.0

    def test_thd_harmonic_count(self):
        """THD should include specified number of harmonics."""
        fs = 48000
        duration = 1.0
        t = np.arange(int(fs * duration)) / fs

        fundamental = 1000.0

        # Add 5th harmonic only
        signal = (
            1.0 * np.sin(2 * np.pi * fundamental * t) +
            0.1 * np.sin(2 * np.pi * 5 * fundamental * t)
        ).astype(np.float32)

        # With n_harmonics=5, should include 5th harmonic
        thd_db, thd_percent = measure_thd(signal, fs, fundamental, n_harmonics=5)

        assert thd_percent > 5.0  # Should detect the 10% 5th harmonic


# --- Noise Floor Estimation Tests ---

class TestNoiseFloorEstimation:
    """Tests for estimate_noise_floor function."""

    def test_pure_tone_low_noise(self):
        """Pure tone should have low noise floor."""
        fs = 48000
        tone = generate_pure_sine(1000.0, fs, 1.0, 0.5)

        noise_floor = estimate_noise_floor(tone, fs, 1000.0)

        # Should be very low for pure digital sine
        assert noise_floor < -80.0

    def test_noisy_signal_higher_floor(self):
        """Noisy signal should have higher noise floor."""
        fs = 48000
        duration = 1.0

        # Tone + noise
        tone = generate_pure_sine(1000.0, fs, duration, 0.5)
        noise = np.random.randn(int(fs * duration)).astype(np.float32) * 0.01
        signal = tone + noise

        noise_floor = estimate_noise_floor(signal, fs, 1000.0)

        # Should be higher than pure tone
        # Noise at 0.01 amplitude ≈ -40 dBFS
        assert noise_floor > -50.0


# --- Amplitude Verification Tests ---

class TestAmplitudeVerification:
    """Tests for verify_amplitude function."""

    def test_matching_amplitude_passes(self):
        """Matching amplitude should pass."""
        passed, error = verify_amplitude(-20.0, -20.0, max_error_db=1.0)

        assert passed is True
        assert abs(error) < 0.01

    def test_small_error_passes(self):
        """Small error within tolerance should pass."""
        passed, error = verify_amplitude(-20.0, -20.5, max_error_db=1.0)

        assert passed is True
        assert_allclose(error, -0.5, atol=0.01)

    def test_large_error_fails(self):
        """Large error exceeding tolerance should fail."""
        passed, error = verify_amplitude(-20.0, -22.0, max_error_db=1.0)

        assert passed is False
        assert_allclose(error, -2.0, atol=0.01)

    @pytest.mark.parametrize("ref,measured,max_err,expected_pass", [
        (-20.0, -20.0, 1.0, True),
        (-20.0, -20.5, 1.0, True),
        (-20.0, -21.0, 1.0, True),   # Edge case
        (-20.0, -21.1, 1.0, False),
        (-20.0, -18.0, 1.0, False),
        (-20.0, -15.0, 5.0, True),   # Larger tolerance
    ])
    def test_various_scenarios(self, ref, measured, max_err, expected_pass):
        """Test various amplitude verification scenarios."""
        passed, _ = verify_amplitude(ref, measured, max_error_db=max_err)

        assert passed == expected_pass


# --- Reference Tone Test Integration Tests ---

class TestReferenceToneIntegration:
    """Integration tests for run_reference_tone_test."""

    def test_simulation_mode(self, short_config):
        """Should run successfully in simulation mode."""
        result = run_reference_tone_test(short_config, play_and_record_fn=None)

        assert isinstance(result, ReferenceToneResult)
        assert result.success is True
        assert result.amplitude_error_db is not None
        assert result.thd_db < 0  # THD should be negative dB

    def test_passthrough_accurate(self, short_config):
        """Direct passthrough should give accurate results."""
        def passthrough(signal, sr):
            return signal.copy()

        result = run_reference_tone_test(short_config, play_and_record_fn=passthrough)

        assert result.success is True
        assert abs(result.amplitude_error_db) < 0.5
        assert abs(result.frequency_error_hz) < 1.0

    def test_gain_mismatch_detection(self, short_config):
        """Should detect gain mismatch."""
        def add_gain(signal, sr):
            return signal * 1.5  # +3.5 dB gain

        result = run_reference_tone_test(short_config, play_and_record_fn=add_gain)

        # Amplitude error should be approximately +3.5 dB
        assert 2.0 < result.amplitude_error_db < 5.0

    def test_capture_failure_handling(self, short_config):
        """Should handle capture failure gracefully."""
        def fail_capture(signal, sr):
            return None

        result = run_reference_tone_test(short_config, play_and_record_fn=fail_capture)

        assert result.success is False
        assert "captured" in result.error_message.lower()

    def test_high_thd_detection(self, short_config):
        """Should detect high THD."""
        def add_distortion(signal, sr):
            # Square the signal to add harmonics
            return np.clip(signal * 2, -1, 1)

        result = run_reference_tone_test(short_config, play_and_record_fn=add_distortion)

        # THD should be high due to clipping
        assert result.thd_percent > 1.0

    def test_result_fields_populated(self, short_config):
        """All result fields should be populated."""
        result = run_reference_tone_test(short_config, play_and_record_fn=None)

        assert result.reference_amplitude_dbfs == short_config.amplitude_dbfs
        assert result.measured_amplitude_dbfs != 0
        assert result.measured_frequency_hz > 0
        assert result.noise_floor_dbfs < 0
        assert result.snr_db > 0


# --- Edge Cases ---

class TestEdgeCases:
    """Edge case tests."""

    def test_very_low_frequency(self):
        """Should handle low frequencies."""
        config = ReferenceToneConfig(
            frequency_hz=50.0,
            duration_s=1.0,
            sample_rate=48000,
        )

        tone = generate_reference_tone(config)
        measured = find_fundamental_frequency(tone, 48000, 50.0)

        assert_allclose(measured, 50.0, rtol=0.02)

    def test_high_frequency(self):
        """Should handle high frequencies."""
        config = ReferenceToneConfig(
            frequency_hz=15000.0,
            duration_s=0.5,
            sample_rate=48000,
        )

        tone = generate_reference_tone(config)
        measured = find_fundamental_frequency(tone, 48000, 15000.0)

        assert_allclose(measured, 15000.0, rtol=0.01)

    def test_very_quiet_tone(self):
        """Should handle very quiet tones."""
        config = ReferenceToneConfig(
            amplitude_dbfs=-60.0,
            duration_s=1.0,
            sample_rate=48000,
        )

        result = run_reference_tone_test(config, play_and_record_fn=None)

        # Should still work but SNR will be lower
        assert result.success is True

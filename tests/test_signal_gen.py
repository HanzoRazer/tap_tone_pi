"""
Tests for the signal generator module.
"""

import math

import numpy as np
import pytest

from tap_tone_pi.signal_gen import (
    generate_sine,
    generate_sweep,
    generate_chirp,
    generate_noise,
    generate_impulse,
    generate_multitone,
    generate_comb,
    write_wav,
    read_wav,
    signal_to_int16,
    normalize_signal,
    SignalConfig,
    SweepConfig,
    NoiseConfig,
    WaveformType,
    SweepType,
    NoiseType,
)


class TestGenerateSine:
    """Tests for sine wave generation."""

    def test_basic_sine(self):
        """Test basic sine wave generation."""
        signal = generate_sine(frequency_hz=440.0, duration_s=0.5, sample_rate=48000)

        assert len(signal) == 24000
        assert signal.dtype == np.float64
        assert np.max(np.abs(signal)) <= 1.0

    def test_amplitude(self):
        """Test amplitude is correct."""
        signal = generate_sine(
            frequency_hz=1000.0,
            duration_s=0.1,
            sample_rate=48000,
            amplitude=0.5,
            fade_in_ms=0,
            fade_out_ms=0,
        )

        # Peak should be close to amplitude
        assert np.max(np.abs(signal)) == pytest.approx(0.5, rel=0.01)

    def test_frequency_accuracy(self):
        """Test frequency is correct."""
        freq = 1000.0
        duration = 1.0
        sample_rate = 48000

        signal = generate_sine(
            frequency_hz=freq,
            duration_s=duration,
            sample_rate=sample_rate,
        )

        # Count zero crossings
        zero_crossings = np.sum(np.diff(np.sign(signal)) != 0)
        expected_crossings = 2 * freq * duration  # 2 per cycle

        assert zero_crossings == pytest.approx(expected_crossings, rel=0.02)

    def test_config_object(self):
        """Test using SignalConfig object."""
        config = SignalConfig(
            sample_rate=44100,
            duration_s=0.5,
            amplitude=0.7,
            frequency_hz=880.0,
        )

        signal = generate_sine(config)

        assert len(signal) == int(44100 * 0.5)

    def test_fade_applied(self):
        """Test fade in/out is applied."""
        signal = generate_sine(
            frequency_hz=1000.0,
            duration_s=0.1,
            sample_rate=48000,
            fade_in_ms=10,
            fade_out_ms=10,
        )

        # First sample should be near zero (faded in)
        assert abs(signal[0]) < 0.01

        # Last sample should be near zero (faded out)
        assert abs(signal[-1]) < 0.01


class TestGenerateSweep:
    """Tests for sweep generation."""

    def test_basic_sweep(self):
        """Test basic sweep generation."""
        signal = generate_sweep(
            start_freq_hz=100.0,
            end_freq_hz=1000.0,
            duration_s=1.0,
            sample_rate=48000,
        )

        # Should include silence padding
        expected_samples = int(48000 * 1.0) + int(48000 * 0.2)  # sweep + padding
        assert len(signal) == pytest.approx(expected_samples, rel=0.1)

    def test_linear_sweep(self):
        """Test linear sweep type."""
        signal = generate_sweep(
            start_freq_hz=100.0,
            end_freq_hz=1000.0,
            duration_s=0.5,
            sample_rate=48000,
            sweep_type=SweepType.LINEAR,
        )

        assert len(signal) > 0
        assert np.max(np.abs(signal)) <= 1.0

    def test_logarithmic_sweep(self):
        """Test logarithmic sweep type."""
        signal = generate_sweep(
            start_freq_hz=20.0,
            end_freq_hz=20000.0,
            duration_s=1.0,
            sample_rate=48000,
            sweep_type=SweepType.LOGARITHMIC,
        )

        assert len(signal) > 0

    def test_chirp_convenience(self):
        """Test chirp convenience function."""
        signal = generate_chirp(
            start_freq_hz=20.0,
            end_freq_hz=20000.0,
            duration_s=1.0,
        )

        assert len(signal) > 0


class TestGenerateNoise:
    """Tests for noise generation."""

    def test_white_noise(self):
        """Test white noise generation."""
        signal = generate_noise(
            noise_type=NoiseType.WHITE,
            duration_s=0.5,
            sample_rate=48000,
            amplitude=0.3,
            seed=42,
        )

        assert len(signal) == 24000

    def test_pink_noise(self):
        """Test pink noise generation."""
        signal = generate_noise(
            noise_type=NoiseType.PINK,
            duration_s=0.5,
            sample_rate=48000,
            seed=42,
        )

        assert len(signal) == 24000

    def test_brown_noise(self):
        """Test brown noise generation."""
        signal = generate_noise(
            noise_type=NoiseType.BROWN,
            duration_s=0.5,
            sample_rate=48000,
            seed=42,
        )

        assert len(signal) == 24000
        assert np.max(np.abs(signal)) <= 1.0

    def test_reproducible_with_seed(self):
        """Test noise is reproducible with same seed."""
        signal1 = generate_noise(noise_type="white", duration_s=0.1, seed=123)
        signal2 = generate_noise(noise_type="white", duration_s=0.1, seed=123)

        np.testing.assert_array_almost_equal(signal1, signal2)

    def test_different_with_different_seed(self):
        """Test noise is different with different seeds."""
        signal1 = generate_noise(noise_type="white", duration_s=0.1, seed=123)
        signal2 = generate_noise(noise_type="white", duration_s=0.1, seed=456)

        assert not np.allclose(signal1, signal2)


class TestGenerateImpulse:
    """Tests for impulse generation."""

    def test_basic_impulse(self):
        """Test basic impulse generation."""
        signal = generate_impulse(
            duration_s=0.1,
            sample_rate=48000,
            amplitude=1.0,
            impulse_time_ms=50.0,
        )

        assert len(signal) == 4800

        # Find impulse position
        impulse_idx = np.argmax(np.abs(signal))
        expected_idx = int(50.0 * 48000 / 1000)

        assert impulse_idx == expected_idx
        assert signal[impulse_idx] == 1.0

    def test_impulse_is_single_sample(self):
        """Test impulse is a single sample."""
        signal = generate_impulse(
            duration_s=0.5,  # Longer than default impulse_time_ms (100ms)
            sample_rate=48000,
            impulse_time_ms=100.0,
        )

        non_zero = np.sum(signal != 0)
        assert non_zero == 1


class TestGenerateMultitone:
    """Tests for multitone generation."""

    def test_basic_multitone(self):
        """Test basic multitone generation."""
        signal = generate_multitone(
            frequencies_hz=[100.0, 500.0, 1000.0],
            duration_s=0.5,
            sample_rate=48000,
        )

        assert len(signal) == 24000
        assert np.max(np.abs(signal)) <= 1.0

    def test_frequencies_present(self):
        """Test all frequencies are present in spectrum."""
        frequencies = [200.0, 400.0, 800.0]
        signal = generate_multitone(
            frequencies_hz=frequencies,
            duration_s=1.0,
            sample_rate=48000,
            fade_in_ms=0,
            fade_out_ms=0,
        )

        # Compute FFT
        fft = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1 / 48000)

        # Check each frequency has a peak
        for freq in frequencies:
            # Find nearest bin
            idx = np.argmin(np.abs(freqs - freq))
            # Should be a local maximum
            assert fft[idx] > fft[idx - 5]
            assert fft[idx] > fft[idx + 5]


class TestGenerateComb:
    """Tests for comb signal generation."""

    def test_basic_comb(self):
        """Test basic comb generation."""
        signal = generate_comb(
            fundamental_hz=100.0,
            n_harmonics=10,
            duration_s=0.5,
            sample_rate=48000,
        )

        assert len(signal) == 24000

    def test_harmonics_present(self):
        """Test harmonics are present."""
        fundamental = 100.0
        n_harmonics = 5

        signal = generate_comb(
            fundamental_hz=fundamental,
            n_harmonics=n_harmonics,
            duration_s=1.0,
            sample_rate=48000,
        )

        # Compute FFT
        fft = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1 / 48000)

        # Check each harmonic
        for h in range(1, n_harmonics + 1):
            freq = fundamental * h
            idx = np.argmin(np.abs(freqs - freq))
            # Should have significant energy
            assert fft[idx] > np.mean(fft)


class TestWavIO:
    """Tests for WAV file I/O."""

    def test_write_read_roundtrip(self, tmp_path):
        """Test write and read produces same signal."""
        original = generate_sine(frequency_hz=440.0, duration_s=0.1, amplitude=0.5)

        # Write
        filepath = tmp_path / "test.wav"
        write_wav(original, filepath, sample_rate=48000)

        # Read back
        loaded, rate = read_wav(filepath)

        # Should be close (within quantization error)
        assert rate == 48000
        assert len(loaded) == len(original)

        # 16-bit quantization error ~= 1/32768
        np.testing.assert_array_almost_equal(
            loaded.flatten(),
            original,
            decimal=4,
        )

    def test_signal_to_int16(self):
        """Test int16 conversion."""
        signal = np.array([0.0, 0.5, 1.0, -1.0, -0.5])
        converted = signal_to_int16(signal)

        assert converted.dtype == np.int16
        assert converted[0] == 0
        assert converted[2] == 32767
        assert converted[3] == -32767

    def test_normalize_signal_peak(self):
        """Test peak normalization."""
        signal = np.array([0.1, 0.2, 0.3, -0.2])
        normalized = normalize_signal(signal, target_peak=0.9)

        assert np.max(np.abs(normalized)) == pytest.approx(0.9, rel=0.001)

    def test_normalize_signal_rms(self):
        """Test RMS normalization."""
        signal = generate_sine(frequency_hz=1000, duration_s=0.1, amplitude=0.5)
        target_rms = 0.3
        normalized = normalize_signal(signal, target_rms=target_rms)

        actual_rms = np.sqrt(np.mean(normalized**2))
        assert actual_rms == pytest.approx(target_rms, rel=0.01)

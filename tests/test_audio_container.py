#!/usr/bin/env python3
"""
Tests for AudioContainer with sample rate validation.

M6 Audit: Sample Rate Consistency Not Enforced
Fix: Embed sample rate in audio container, validate on load.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tap_tone_pi.io.audio_container import (
    AudioContainer,
    AudioContainer2Ch,
    SampleRateMismatchError,
    validate_sample_rate,
    load_wav_validated,
    load_wav_2ch_validated,
    is_standard_sample_rate,
    get_sample_rate_warning,
)


class TestAudioContainer:
    """Test AudioContainer creation and validation."""

    def test_create_container_basic(self):
        """Basic container creation should work."""
        signal = np.zeros(1000, dtype=np.float32)
        container = AudioContainer(signal=signal, sample_rate=48000)

        assert container.sample_rate == 48000
        assert container.num_samples == 1000
        assert container.num_channels == 1

    def test_container_duration(self):
        """Duration should be calculated correctly."""
        signal = np.zeros(48000, dtype=np.float32)  # 1 second at 48 kHz
        container = AudioContainer(signal=signal, sample_rate=48000)

        assert container.duration_s == pytest.approx(1.0, rel=1e-6)

    def test_container_immutable(self):
        """Container should be immutable (frozen dataclass)."""
        signal = np.zeros(1000, dtype=np.float32)
        container = AudioContainer(signal=signal, sample_rate=48000)

        with pytest.raises(AttributeError):
            container.sample_rate = 44100  # type: ignore

    def test_container_rejects_zero_sample_rate(self):
        """Zero sample rate should raise ValueError."""
        signal = np.zeros(1000, dtype=np.float32)
        with pytest.raises(ValueError, match="must be positive"):
            AudioContainer(signal=signal, sample_rate=0)

    def test_container_rejects_negative_sample_rate(self):
        """Negative sample rate should raise ValueError."""
        signal = np.zeros(1000, dtype=np.float32)
        with pytest.raises(ValueError, match="must be positive"):
            AudioContainer(signal=signal, sample_rate=-48000)

    def test_container_validate_matching(self):
        """Validation should pass for matching sample rate."""
        signal = np.zeros(1000, dtype=np.float32)
        container = AudioContainer(signal=signal, sample_rate=48000)

        container.validate_sample_rate(48000)  # Should not raise

    def test_container_validate_mismatch(self):
        """Validation should fail for mismatched sample rate."""
        signal = np.zeros(1000, dtype=np.float32)
        container = AudioContainer(signal=signal, sample_rate=48000)

        with pytest.raises(SampleRateMismatchError) as exc_info:
            container.validate_sample_rate(44100)

        assert exc_info.value.expected_fs == 44100
        assert exc_info.value.actual_fs == 48000

    def test_container_to_dict(self):
        """to_dict should serialize metadata correctly."""
        signal = np.zeros(48000, dtype=np.float32)
        container = AudioContainer(
            signal=signal, sample_rate=48000, source="test.wav"
        )

        d = container.to_dict()

        assert d["sample_rate"] == 48000
        assert d["num_samples"] == 48000
        assert d["duration_s"] == pytest.approx(1.0, rel=1e-4)
        assert d["source"] == "test.wav"


class TestAudioContainer2Ch:
    """Test two-channel container."""

    def test_create_2ch_container(self):
        """2-channel container creation should work."""
        ref = np.zeros(1000, dtype=np.float32)
        rov = np.zeros(1000, dtype=np.float32)
        container = AudioContainer2Ch(
            reference=ref, roving=rov, sample_rate=48000
        )

        assert container.sample_rate == 48000
        assert container.num_samples == 1000

    def test_2ch_length_mismatch_raises(self):
        """Mismatched channel lengths should raise."""
        ref = np.zeros(1000, dtype=np.float32)
        rov = np.zeros(500, dtype=np.float32)

        with pytest.raises(ValueError, match="length mismatch"):
            AudioContainer2Ch(reference=ref, roving=rov, sample_rate=48000)


class TestValidateSampleRate:
    """Test sample rate validation function."""

    def test_exact_match(self):
        """Exact match should pass."""
        validate_sample_rate(48000, 48000)  # Should not raise

    def test_mismatch_raises(self):
        """Mismatch should raise SampleRateMismatchError."""
        with pytest.raises(SampleRateMismatchError):
            validate_sample_rate(48000, 44100)

    def test_small_tolerance(self):
        """Small deviations within tolerance should pass."""
        # 0.1% of 48000 = 48 Hz tolerance
        validate_sample_rate(48000, 48040, tolerance_pct=0.1)  # Within 0.1%

    def test_tolerance_exceeded(self):
        """Deviations exceeding tolerance should fail."""
        with pytest.raises(SampleRateMismatchError):
            validate_sample_rate(48000, 48100, tolerance_pct=0.1)  # Exceeds 0.1%

    def test_zero_tolerance_strict(self):
        """Zero tolerance should require exact match."""
        validate_sample_rate(48000, 48000, tolerance_pct=0.0)

        with pytest.raises(SampleRateMismatchError):
            validate_sample_rate(48000, 48001, tolerance_pct=0.0)

    def test_error_message_includes_percentages(self):
        """Error message should include percentage error."""
        with pytest.raises(SampleRateMismatchError) as exc_info:
            validate_sample_rate(48000, 44100)

        # ~8.1% error
        assert "8.1%" in str(exc_info.value) or "8%" in str(exc_info.value)

    def test_error_message_includes_source(self):
        """Error message should include source if provided."""
        with pytest.raises(SampleRateMismatchError) as exc_info:
            validate_sample_rate(48000, 44100, source="test_audio.wav")

        assert "test_audio.wav" in str(exc_info.value)

    def test_invalid_expected_fs(self):
        """Invalid expected_fs should raise ValueError."""
        with pytest.raises(ValueError, match="expected_fs"):
            validate_sample_rate(0, 48000)

    def test_invalid_actual_fs(self):
        """Invalid actual_fs should raise ValueError."""
        with pytest.raises(ValueError, match="actual_fs"):
            validate_sample_rate(48000, 0)


class TestLoadWavValidated:
    """Test validated WAV loading."""

    @pytest.fixture
    def temp_wav_48k(self, tmp_path: Path) -> Path:
        """Create a temporary 48 kHz WAV file."""
        wav_path = tmp_path / "test_48k.wav"
        signal = (np.random.rand(48000) * 0.5 - 0.25).astype(np.float32)
        signal_int16 = (signal * 32767).astype(np.int16)
        wavfile.write(str(wav_path), 48000, signal_int16)
        return wav_path

    @pytest.fixture
    def temp_wav_44k(self, tmp_path: Path) -> Path:
        """Create a temporary 44.1 kHz WAV file."""
        wav_path = tmp_path / "test_44k.wav"
        signal = (np.random.rand(44100) * 0.5 - 0.25).astype(np.float32)
        signal_int16 = (signal * 32767).astype(np.int16)
        wavfile.write(str(wav_path), 44100, signal_int16)
        return wav_path

    def test_load_without_validation(self, temp_wav_48k: Path):
        """Loading without expected_fs should not validate."""
        container = load_wav_validated(temp_wav_48k)

        assert container.sample_rate == 48000
        assert container.num_samples == 48000

    def test_load_with_matching_validation(self, temp_wav_48k: Path):
        """Loading with matching expected_fs should pass."""
        container = load_wav_validated(temp_wav_48k, expected_fs=48000)

        assert container.sample_rate == 48000

    def test_load_with_mismatch_raises(self, temp_wav_48k: Path):
        """Loading with mismatched expected_fs should raise."""
        with pytest.raises(SampleRateMismatchError):
            load_wav_validated(temp_wav_48k, expected_fs=44100)

    def test_load_includes_source(self, temp_wav_48k: Path):
        """Loaded container should include source path."""
        container = load_wav_validated(temp_wav_48k)

        assert container.source is not None
        assert "test_48k.wav" in container.source

    def test_load_2ch_validated(self, tmp_path: Path):
        """2-channel loading should work with validation."""
        wav_path = tmp_path / "test_stereo.wav"
        signal = (np.random.rand(48000, 2) * 0.5 - 0.25).astype(np.float32)
        signal_int16 = (signal * 32767).astype(np.int16)
        wavfile.write(str(wav_path), 48000, signal_int16)

        container = load_wav_2ch_validated(wav_path, expected_fs=48000)

        assert container.sample_rate == 48000
        assert container.num_samples == 48000


class TestStandardSampleRates:
    """Test sample rate utilities."""

    @pytest.mark.parametrize(
        "fs,expected",
        [
            (44100, True),
            (48000, True),
            (96000, True),
            (22050, True),
            (47999, False),  # Off by 1
            (12345, False),  # Random
        ],
    )
    def test_is_standard_sample_rate(self, fs: int, expected: bool):
        """Standard sample rates should be recognized."""
        assert is_standard_sample_rate(fs) == expected

    def test_warning_for_low_sample_rate(self):
        """Very low sample rate should generate warning."""
        warning = get_sample_rate_warning(4000)

        assert warning is not None
        assert "low" in warning.lower() or "Nyquist" in warning

    def test_warning_for_high_sample_rate(self):
        """Very high sample rate should generate warning."""
        warning = get_sample_rate_warning(500000)

        assert warning is not None
        assert "high" in warning.lower()

    def test_warning_for_nonstandard(self):
        """Non-standard sample rate should generate warning."""
        warning = get_sample_rate_warning(47999)

        assert warning is not None
        assert "non-standard" in warning.lower()

    def test_no_warning_for_standard(self):
        """Standard sample rates should not generate warnings."""
        warning = get_sample_rate_warning(48000)

        assert warning is None


class TestPhysicalRealism:
    """Test real-world scenarios."""

    def test_cd_vs_dvd_mismatch_detected(self):
        """CD quality (44.1 kHz) vs DVD quality (48 kHz) mismatch should be caught."""
        signal = np.zeros(44100, dtype=np.float32)
        container = AudioContainer(signal=signal, sample_rate=44100)

        with pytest.raises(SampleRateMismatchError) as exc_info:
            container.validate_sample_rate(48000)

        # ~8.8% error
        assert exc_info.value.actual_fs == 44100
        assert exc_info.value.expected_fs == 48000

    def test_frequency_error_implication(self):
        """Demonstrate frequency error from sample rate mismatch.

        If 44.1 kHz audio is analyzed as 48 kHz:
        - Reported freq = actual_freq × (48000 / 44100) = actual_freq × 1.088
        - A 440 Hz note would appear as 478.5 Hz
        - This is a 38.5 Hz (8.8%) systematic error!
        """
        actual_fs = 44100
        assumed_fs = 48000

        actual_freq = 440.0  # A4 note
        reported_freq = actual_freq * (assumed_fs / actual_fs)

        error_hz = reported_freq - actual_freq
        error_pct = (error_hz / actual_freq) * 100

        # This demonstrates why validation matters
        assert error_pct == pytest.approx(8.8, abs=0.1)
        assert error_hz == pytest.approx(38.5, abs=0.5)

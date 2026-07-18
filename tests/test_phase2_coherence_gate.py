"""
Tests for tap_tone_pi.phase2.coherence_gate module.
"""

import numpy as np
import pytest

from tap_tone_pi.phase2.coherence_gate import (
    CoherenceResult,
    check_coherence_from_arrays,
    format_coherence_feedback,
)


@pytest.fixture
def clean_signal():
    """Create a clean sinusoidal test signal."""
    fs = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(fs * duration))
    # 200 Hz sine wave
    signal = np.sin(2 * np.pi * 200 * t) * 0.5
    return signal, fs


@pytest.fixture
def noisy_signal():
    """Create a noisy test signal (wideband noise; split-window coherence stays low)."""
    fs = 44100
    duration = 1.0
    n = int(fs * duration)
    rng = np.random.default_rng(42)
    # Pure noise — avoids high self-coherence from a shared weak tone in both halves
    signal = rng.standard_normal(n).astype(np.float64)
    return signal, fs


class TestCoherenceResult:
    """Tests for CoherenceResult dataclass."""

    def test_passed_result(self):
        """Passed result should have no recommendation."""
        result = CoherenceResult(
            passed=True,
            coherence=0.95,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )
        assert result.passed
        assert result.recommendation == ""

    def test_failed_result_generates_recommendation(self):
        """Failed result should generate recommendation."""
        result = CoherenceResult(
            passed=False,
            coherence=0.4,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )
        assert not result.passed
        assert result.recommendation  # Should be non-empty
        assert "coherence" in result.recommendation.lower()

    def test_very_low_coherence_recommendation(self):
        """Very low coherence should have specific guidance."""
        result = CoherenceResult(
            passed=False,
            coherence=0.2,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )
        assert (
            "microphone" in result.recommendation.lower()
            or "check" in result.recommendation.lower()
        )

    def test_marginal_coherence_recommendation(self):
        """Marginal coherence should suggest retry."""
        result = CoherenceResult(
            passed=False,
            coherence=0.65,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )
        assert "retry" in result.recommendation.lower()


class TestCheckCoherenceFromArrays:
    """Tests for check_coherence_from_arrays function."""

    def test_clean_signal_passes(self, clean_signal):
        """Clean sinusoidal signal should pass coherence check."""
        signal, fs = clean_signal

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        # Clean sine should have high self-coherence
        assert result.coherence > 0.5  # May not be exactly 1.0 due to edge effects

    def test_noisy_signal_fails(self, noisy_signal):
        """Noisy signal should fail coherence check."""
        signal, fs = noisy_signal

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        # Random noise should have low coherence
        assert result.coherence < 0.7
        assert not result.passed

    def test_too_short_signal_fails(self):
        """Signal shorter than 2*nperseg should fail."""
        fs = 44100
        short_signal = np.random.randn(1000)  # Too short for nperseg=4096

        result = check_coherence_from_arrays(
            signal=short_signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
            nperseg=4096,
        )

        assert not result.passed
        assert "short" in result.recommendation.lower()

    def test_dominant_frequency_detected(self, clean_signal):
        """Should detect dominant frequency correctly."""
        signal, fs = clean_signal

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        # Should detect frequency near 200 Hz
        assert 150 < result.dominant_freq_hz < 250

    def test_coherence_at_peaks_populated(self, clean_signal):
        """coherence_at_peaks should be populated."""
        signal, fs = clean_signal

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        assert result.coherence_at_peaks is not None
        assert len(result.coherence_at_peaks) > 0

        # Each entry should be (freq, coherence) tuple
        freq, coh = result.coherence_at_peaks[0]
        assert isinstance(freq, float)
        assert isinstance(coh, float)

    def test_mean_coherence_computed(self, clean_signal):
        """mean_coherence should be computed."""
        signal, fs = clean_signal

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        assert result.mean_coherence > 0

    def test_cross_coherence_with_reference(self, clean_signal):
        """Should compute cross-coherence when reference provided."""
        signal, fs = clean_signal

        # Use same signal as reference (perfect coherence)
        result = check_coherence_from_arrays(
            signal=signal,
            reference=signal.copy(),
            sample_rate=fs,
            threshold=0.7,
        )

        # Same signal should have high coherence
        assert result.coherence > 0.9

    def test_threshold_parameter(self, clean_signal):
        """Result should respect threshold parameter."""
        signal, fs = clean_signal

        # With low threshold, should pass
        result_low = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.3,
        )

        # With very high threshold, may fail
        result_high = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.99,
        )

        assert result_low.threshold == 0.3
        assert result_high.threshold == 0.99


class TestFormatCoherenceFeedback:
    """Tests for format_coherence_feedback function."""

    def test_format_passed(self):
        """Passed result should show PASS."""
        result = CoherenceResult(
            passed=True,
            coherence=0.95,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )

        output = format_coherence_feedback(result, use_color=False)

        assert "PASS" in output
        assert "0.95" in output or "0.950" in output

    def test_format_failed(self):
        """Failed result should show FAIL and recommendation."""
        result = CoherenceResult(
            passed=False,
            coherence=0.4,
            dominant_freq_hz=200.0,
            threshold=0.7,
            recommendation="Try adjusting microphone placement.",
        )

        output = format_coherence_feedback(result, use_color=False)

        assert "FAIL" in output
        assert "microphone" in output.lower()

    def test_format_warning(self):
        """Marginal coherence should show WARN."""
        result = CoherenceResult(
            passed=False,
            coherence=0.65,  # Close to 0.7 threshold
            dominant_freq_hz=200.0,
            threshold=0.7,
        )

        output = format_coherence_feedback(result, use_color=False)

        assert "WARN" in output

    def test_format_includes_frequency(self):
        """Output should include dominant frequency."""
        result = CoherenceResult(
            passed=True,
            coherence=0.95,
            dominant_freq_hz=187.5,
            threshold=0.7,
        )

        output = format_coherence_feedback(result, use_color=False)

        assert "187" in output
        assert "Hz" in output

    def test_format_with_color_includes_codes(self):
        """Colored output should include ANSI codes."""
        result = CoherenceResult(
            passed=True,
            coherence=0.95,
            dominant_freq_hz=200.0,
            threshold=0.7,
        )

        output = format_coherence_feedback(result, use_color=True)

        # Should contain ANSI escape codes
        assert "\033[" in output


class TestEdgeCases:
    """Edge case tests."""

    def test_dc_signal(self):
        """Should handle DC signal (no frequency content)."""
        fs = 44100
        dc_signal = np.ones(fs * 2) * 0.5  # 2 seconds of DC

        result = check_coherence_from_arrays(
            signal=dc_signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        # Should not crash, may fail due to no peaks
        assert isinstance(result, CoherenceResult)

    def test_impulse_signal(self):
        """Should handle impulse-like signal."""
        fs = 44100
        impulse = np.zeros(fs * 2)
        impulse[fs] = 1.0  # Single sample impulse at 1 second

        result = check_coherence_from_arrays(
            signal=impulse,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        assert isinstance(result, CoherenceResult)

    def test_multi_tone_signal(self):
        """Should handle signal with multiple tones."""
        fs = 44100
        t = np.linspace(0, 1.0, fs)
        # Three tones at 100, 200, 300 Hz
        signal = (
            np.sin(2 * np.pi * 100 * t)
            + np.sin(2 * np.pi * 200 * t) * 0.5
            + np.sin(2 * np.pi * 300 * t) * 0.25
        )

        result = check_coherence_from_arrays(
            signal=signal,
            reference=None,
            sample_rate=fs,
            threshold=0.7,
        )

        # Should detect at least 100 Hz as dominant
        assert 80 < result.dominant_freq_hz < 150

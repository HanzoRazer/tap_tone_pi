"""
test_dsp_cross_validation.py — Dual-DSP stack regression guard.

Verifies that analyzer/analysis/fft.py and tap_tone_pi/core/analysis.py
produce consistent peak frequencies for the same input signal.

WHY THIS TEST EXISTS (see design review, Mar 30 2026):
  v9 of the repo contains two independent FFT/peak-detection implementations:
    - tap_tone_pi/core/analysis.py   (capture engine, runs on Pi)
    - analyzer/analysis/fft.py       (desktop viewer, runs on PC)

  If these drift, the same WAV file will produce different dominant frequencies
  in the capture report vs the desktop analyzer. This is a silent wrong-answer
  failure mode — no crash, just inconsistent numbers.

  This test catches drift early by running both implementations on identical
  synthetic signals with known exact frequencies and asserting agreement within
  a physical tolerance (1.5 Hz, approximately one FFT bin at 44100 Hz / 4096 pts).

TOLERANCE RATIONALE:
  FFT bin width = sample_rate / N_samples = 44100 / 4096 ≈ 10.8 Hz
  Peak detection interpolates between bins; 1.5 Hz is ~14% of one bin.
  This is tight enough to catch algorithm divergence but loose enough to
  accommodate minor windowing/normalization differences.

  If this test fails, the two implementations have diverged in a way that would
  produce materially different results for real luthier measurements.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root without install
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Import both DSP stacks
# ---------------------------------------------------------------------------

try:
    from tap_tone_pi.core.analysis import analyze_tap, Peak

    CAPTURE_ENGINE_AVAILABLE = True
except ImportError:
    CAPTURE_ENGINE_AVAILABLE = False

try:
    from analyzer.analysis.fft import compute_fft, find_resonance_frequency
    from analyzer.analysis.peaks import find_spectrum_peaks

    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not (CAPTURE_ENGINE_AVAILABLE and ANALYZER_AVAILABLE),
    reason="Both tap_tone_pi.core.analysis and analyzer.analysis must be importable",
)

# ---------------------------------------------------------------------------
# Signal synthesis helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100
DURATION_S = 0.5  # 0.5s gives ~4096 samples at the default FFT size


def _make_synthetic_tap(
    fundamental_hz: float,
    harmonics: list[float],
    sample_rate: int = SAMPLE_RATE,
    duration_s: float = DURATION_S,
    snr_db: float = 40.0,
    decay_tau: float = 0.15,
    seed: int = 42,
) -> np.ndarray:
    """
    Synthesize a tap-tone impulse response with known frequencies.

    Each frequency gets a decaying sinusoid component. Noise is added
    at the specified SNR. The result is normalized to [-1, 1].

    Args:
        fundamental_hz: Fundamental frequency in Hz
        harmonics: List of additional frequencies to include
        sample_rate: Sample rate in Hz
        duration_s: Signal duration in seconds
        snr_db: Signal-to-noise ratio in dB (relative to peak)
        decay_tau: Exponential decay time constant in seconds
        seed: RNG seed for reproducible noise

    Returns:
        float32 numpy array normalized to [-1, 1]
    """
    rng = np.random.default_rng(seed)
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    freqs = [fundamental_hz] + harmonics

    signal = np.zeros_like(t)
    for i, f in enumerate(freqs):
        amplitude = 1.0 / (i + 1)  # Fundamental loudest
        phase = rng.uniform(0, 2 * np.pi)
        decay = np.exp(-t / decay_tau)
        signal += amplitude * decay * np.sin(2 * np.pi * f * t + phase)

    # Add white noise at specified SNR
    signal_rms = float(np.sqrt(np.mean(signal**2)))
    noise_rms = signal_rms / (10 ** (snr_db / 20.0))
    noise = rng.normal(0, noise_rms, size=len(t))
    signal = (signal + noise).astype(np.float32)

    # Normalize
    peak = float(np.max(np.abs(signal)))
    if peak > 0:
        signal = signal / peak * 0.9  # 90% of full scale, avoids clipping

    return signal


def _capture_engine_dominant(
    signal: np.ndarray, sample_rate: int = SAMPLE_RATE
) -> float | None:
    """Run tap_tone_pi.core.analysis.analyze_tap and return dominant_hz."""
    result = analyze_tap(
        signal,
        sample_rate,
        highpass_hz=20.0,
        peak_min_hz=40.0,
        peak_max_hz=2000.0,
        peak_min_prominence=0.03,
        peak_min_spacing_hz=5.0,
        max_peaks=12,
    )
    return result.dominant_hz


def _capture_engine_peaks(
    signal: np.ndarray, sample_rate: int = SAMPLE_RATE
) -> list[float]:
    """Return all peak frequencies from capture engine."""
    result = analyze_tap(
        signal,
        sample_rate,
        highpass_hz=20.0,
        peak_min_hz=40.0,
        peak_max_hz=2000.0,
        peak_min_prominence=0.03,
        peak_min_spacing_hz=5.0,
        max_peaks=12,
    )
    return [p.freq_hz for p in result.peaks]


def _analyzer_dominant(
    signal: np.ndarray, sample_rate: int = SAMPLE_RATE
) -> float | None:
    """Run analyzer.analysis.fft and return dominant frequency via find_resonance_frequency."""
    freqs, mags = compute_fft(signal, float(sample_rate), window="hann")
    dominant = find_resonance_frequency(freqs, mags, freq_range=(40.0, 2000.0))
    return dominant if dominant > 0 else None


def _analyzer_peaks(signal: np.ndarray, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Return top peaks from analyzer.analysis.peaks."""
    freqs, mags = compute_fft(signal, float(sample_rate), window="hann")

    # Normalize for find_spectrum_peaks (expects 0..1 range roughly)
    mag_max = float(mags.max()) if mags.size > 0 else 1.0
    if mag_max > 0:
        mags_n = mags / mag_max
    else:
        mags_n = mags

    peaks = find_spectrum_peaks(
        freqs,
        mags_n,
        min_prominence=0.03,
        min_distance=5,
        max_peaks=12,
    )
    return [p["freq_hz"] for p in peaks]


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------

# Maximum allowed difference between the two implementations for the same signal.
# 1.5 Hz ≈ 14% of one FFT bin at 44100 Hz / 4096 samples.
# This catches meaningful algorithmic divergence while tolerating minor
# floating-point or windowing normalization differences.
DOMINANT_FREQ_TOLERANCE_HZ = 1.5

# For peak-by-peak comparison: how close must matched peaks be?
PEAK_MATCH_TOLERANCE_HZ = 2.5

# Minimum fraction of peaks that must be present in both implementations
# (some peaks near the noise floor may be detected by one and not the other)
PEAK_OVERLAP_FRACTION = 0.6


# ---------------------------------------------------------------------------
# Test cases — each is a synthetic signal with known frequencies
# ---------------------------------------------------------------------------

SINGLE_TONE_CASES = [
    pytest.param(180.0, [], id="180Hz_sitka_fundamental"),
    pytest.param(220.0, [], id="220Hz_A3_reference"),
    pytest.param(310.0, [], id="310Hz_typical_mode2"),
    pytest.param(640.0, [], id="640Hz_higher_mode"),
    pytest.param(95.0, [], id="95Hz_low_fundamental"),
]

MULTI_TONE_CASES = [
    pytest.param(
        180.0,
        [360.0, 540.0],
        id="180Hz_with_harmonics",
    ),
    pytest.param(
        203.0,
        [380.0, 635.0, 757.0],
        id="sitka_spruce_sample_frequencies",
    ),
    pytest.param(
        165.0,
        [330.0, 495.0, 660.0],
        id="cedar_top_harmonic_series",
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDominantFrequencyAgreement:
    """
    Both implementations must agree on the dominant (loudest) peak frequency
    for synthetic single-tone signals.
    """

    @pytest.mark.parametrize("fundamental_hz,harmonics", SINGLE_TONE_CASES)
    def test_single_tone_dominant_agrees(
        self, fundamental_hz: float, harmonics: list[float]
    ) -> None:
        signal = _make_synthetic_tap(fundamental_hz, harmonics)

        capture_dom = _capture_engine_dominant(signal)
        analyzer_dom = _analyzer_dominant(signal)

        assert capture_dom is not None, (
            f"Capture engine returned no dominant frequency for {fundamental_hz} Hz signal"
        )
        assert analyzer_dom is not None, (
            f"Analyzer returned no dominant frequency for {fundamental_hz} Hz signal"
        )

        diff = abs(capture_dom - analyzer_dom)
        assert diff <= DOMINANT_FREQ_TOLERANCE_HZ, (
            f"Dominant frequency disagreement for {fundamental_hz} Hz signal:\n"
            f"  Capture engine: {capture_dom:.3f} Hz\n"
            f"  Analyzer:       {analyzer_dom:.3f} Hz\n"
            f"  Difference:     {diff:.3f} Hz  (limit: {DOMINANT_FREQ_TOLERANCE_HZ} Hz)\n\n"
            f"This indicates the two DSP implementations have diverged. "
            f"A luthier measuring the same plate with the Pi and the desktop viewer "
            f"would see different numbers. Fix: align windowing and normalization "
            f"in analyzer/analysis/fft.py to match tap_tone_pi/core/analysis.py."
        )

    @pytest.mark.parametrize("fundamental_hz,harmonics", SINGLE_TONE_CASES)
    def test_single_tone_both_near_truth(
        self, fundamental_hz: float, harmonics: list[float]
    ) -> None:
        """Each implementation should be within 1 FFT bin of the true frequency."""
        signal = _make_synthetic_tap(fundamental_hz, harmonics)
        bin_width_hz = float(SAMPLE_RATE) / len(signal)
        tolerance = bin_width_hz * 1.5  # 1.5 bins

        capture_dom = _capture_engine_dominant(signal)
        analyzer_dom = _analyzer_dominant(signal)

        if capture_dom is not None:
            assert abs(capture_dom - fundamental_hz) <= tolerance, (
                f"Capture engine is far from truth: "
                f"got {capture_dom:.2f} Hz, expected ~{fundamental_hz:.1f} Hz "
                f"(tolerance: {tolerance:.2f} Hz)"
            )
        if analyzer_dom is not None:
            assert abs(analyzer_dom - fundamental_hz) <= tolerance, (
                f"Analyzer is far from truth: "
                f"got {analyzer_dom:.2f} Hz, expected ~{fundamental_hz:.1f} Hz "
                f"(tolerance: {tolerance:.2f} Hz)"
            )


class TestMultiPeakAgreement:
    """
    For multi-tone signals, both implementations must detect overlapping sets
    of peaks within the match tolerance.
    """

    @pytest.mark.parametrize("fundamental_hz,harmonics", MULTI_TONE_CASES)
    def test_peak_overlap_fraction(
        self, fundamental_hz: float, harmonics: list[float]
    ) -> None:
        """
        At least PEAK_OVERLAP_FRACTION of peaks detected by the capture engine
        must have a matching peak (within PEAK_MATCH_TOLERANCE_HZ) in the analyzer.
        """
        signal = _make_synthetic_tap(fundamental_hz, harmonics, snr_db=35.0)

        capture_peaks = _capture_engine_peaks(signal)
        analyzer_peaks = _analyzer_peaks(signal)

        if not capture_peaks:
            pytest.skip(f"Capture engine found no peaks for {fundamental_hz} Hz signal")
        if not analyzer_peaks:
            pytest.skip(f"Analyzer found no peaks for {fundamental_hz} Hz signal")

        # For each capture peak, check if analyzer found something close
        matched = 0
        for cp in capture_peaks:
            for ap in analyzer_peaks:
                if abs(cp - ap) <= PEAK_MATCH_TOLERANCE_HZ:
                    matched += 1
                    break

        overlap = matched / len(capture_peaks)
        assert overlap >= PEAK_OVERLAP_FRACTION, (
            f"Too few peaks overlap between implementations for {fundamental_hz} Hz signal:\n"
            f"  Capture engine peaks: {[f'{f:.1f}' for f in capture_peaks]}\n"
            f"  Analyzer peaks:       {[f'{f:.1f}' for f in analyzer_peaks]}\n"
            f"  Match fraction:       {overlap:.2f}  (minimum: {PEAK_OVERLAP_FRACTION})\n\n"
            f"This means the two implementations disagree on which resonances exist. "
            f"Aligned peak detection logic is required."
        )

    @pytest.mark.parametrize("fundamental_hz,harmonics", MULTI_TONE_CASES)
    def test_dominant_agrees_on_multi_tone(
        self, fundamental_hz: float, harmonics: list[float]
    ) -> None:
        """Both implementations must agree on the loudest peak (the fundamental)."""
        signal = _make_synthetic_tap(fundamental_hz, harmonics)

        capture_dom = _capture_engine_dominant(signal)
        analyzer_dom = _analyzer_dominant(signal)

        if capture_dom is None or analyzer_dom is None:
            pytest.skip("One implementation returned no dominant frequency")

        diff = abs(capture_dom - analyzer_dom)
        assert diff <= DOMINANT_FREQ_TOLERANCE_HZ, (
            f"Dominant frequency disagreement on multi-tone signal "
            f"(fundamental={fundamental_hz} Hz):\n"
            f"  Capture engine: {capture_dom:.3f} Hz\n"
            f"  Analyzer:       {analyzer_dom:.3f} Hz\n"
            f"  Difference:     {diff:.3f} Hz  (limit: {DOMINANT_FREQ_TOLERANCE_HZ} Hz)"
        )


class TestNormalizationConsistency:
    """
    Spectrum normalization between the two implementations must be consistent.
    Both normalize to 0..1 range (or similar). The dominant peak should map
    to magnitude ~1.0 in both.
    """

    def test_capture_engine_normalizes_to_unit(self) -> None:
        """tap_tone_pi.core returns peaks with magnitude in [0, 1]."""
        signal = _make_synthetic_tap(220.0, [440.0])
        result = analyze_tap(signal, SAMPLE_RATE)
        if result.peaks:
            max_mag = max(p.magnitude for p in result.peaks)
            assert 0.0 <= max_mag <= 1.0, (
                f"Capture engine peak magnitude out of [0, 1] range: {max_mag}"
            )
            assert max_mag > 0.5, (
                f"Capture engine dominant peak magnitude unexpectedly low: {max_mag}"
            )

    def test_spectrum_array_normalized(self) -> None:
        """Both spectrum arrays should have a maximum of 1.0."""
        signal = _make_synthetic_tap(220.0, [])

        result = analyze_tap(signal, SAMPLE_RATE)
        if result.spectrum_mag.size > 0:
            assert float(result.spectrum_mag.max()) <= 1.01, (
                "tap_tone_pi spectrum_mag exceeds 1.0"
            )

        freqs, mags = compute_fft(signal, float(SAMPLE_RATE), window="hann")
        # Analyzer does NOT normalize to 0..1 — it returns amplitude.
        # Just verify it's finite and non-negative.
        assert np.all(np.isfinite(mags)), "Analyzer FFT produced non-finite magnitudes"
        assert np.all(mags >= 0), "Analyzer FFT produced negative magnitudes"


class TestEdgeCases:
    """Ensure neither implementation crashes on boundary inputs."""

    def test_silence(self) -> None:
        """Both should handle silence gracefully (no peaks, no crash)."""
        silence = np.zeros(int(SAMPLE_RATE * DURATION_S), dtype=np.float32)

        result = analyze_tap(silence, SAMPLE_RATE)
        assert result.dominant_hz is None or result.dominant_hz == 0.0

        freqs, mags = compute_fft(silence, float(SAMPLE_RATE), window="hann")
        assert np.all(np.isfinite(mags))

    def test_clipping_detected_by_capture_engine(self) -> None:
        """Clipped signal should be flagged by the capture engine."""
        clipped = np.ones(int(SAMPLE_RATE * DURATION_S), dtype=np.float32)
        result = analyze_tap(clipped, SAMPLE_RATE)
        assert result.clipped is True

    def test_very_short_signal(self) -> None:
        """Very short signals should not raise exceptions."""
        short = np.zeros(128, dtype=np.float32)
        # Should return gracefully
        result = analyze_tap(short, SAMPLE_RATE)
        assert result is not None

        freqs, mags = compute_fft(short, float(SAMPLE_RATE), window="hann")
        assert np.all(np.isfinite(mags))

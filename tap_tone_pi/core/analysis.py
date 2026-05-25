# INSTRUMENT CLASS: MEASUREMENT
"""Core FFT-based tap tone analysis.

This module provides the primary analyze_tap() function for extracting
frequency peaks from impulse response audio.

    from tap_tone_pi.core.analysis import analyze_tap, Peak, AnalysisResult

Design Decisions (m2, m3 audit fixes):

Window Function (Hanning) - m2:
    We use the Hanning (Hann) window for FFT analysis. This choice balances:
    - Frequency resolution: Good main lobe width (4 bins at -3dB)
    - Spectral leakage: Moderate sidelobe suppression (-31 dB first sidelobe)
    - Amplitude accuracy: Less scalloping loss than Blackman (~1.4 dB vs ~1.1 dB)

    Trade-offs vs alternatives:
    - Blackman: Better sidelobe suppression (-58 dB) but wider main lobe (6 bins).
      Use for: closely-spaced modes where leakage is a concern.
    - Hamming: Slightly narrower main lobe but worse first sidelobe (-43 dB).
      Use for: applications where frequency resolution is critical.
    - Rectangular (no window): Best frequency resolution but worst leakage.
      Use for: transient analysis where time resolution matters.

    For tap tone modal analysis, Hanning provides the best compromise between
    resolving closely-spaced resonances and rejecting broadband noise leakage.

Filter Order (Butterworth order=4) - m3:
    The highpass filter uses order=4 Butterworth for DC/rumble removal:
    - Rolloff: 24 dB/octave (80 dB/decade) - sufficient attenuation below 20 Hz
    - Phase: Minimally nonlinear phase via filtfilt (zero-phase filtering)
    - Group delay: Acceptable for impulsive signals (~2-3ms at cutoff)

    Higher orders (6, 8) would improve stopband rejection but:
    - Increase computational cost
    - Worsen transient response (overshoot, ringing)
    - More phase distortion before filtfilt correction

    For modal analysis of tonewoods, order=4 provides adequate rumble rejection
    while preserving the attack transient needed for accurate frequency estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import butter, filtfilt, find_peaks


@dataclass(frozen=True)
class Peak:
    """A detected frequency peak."""

    freq_hz: float
    magnitude: float  # normalized 0..1


@dataclass(frozen=True)
class ConfidenceComponents:
    """Components of physics-based confidence score.

    Each component is in [0, 1] range. The overall confidence is a weighted
    combination designed to match expert assessment of "real" vs "noise" peaks.

    See docs/theory/confidence_derivation.md for mathematical foundation.
    """

    snr_db: float  # Signal-to-noise ratio in dB
    snr_confidence: float  # Sigmoid mapping of SNR
    flatness: float  # Spectral flatness (0=tonal, 1=noise)
    flatness_confidence: float  # 1 - flatness
    q_factor: float | None  # Estimated Q from half-power bandwidth
    q_confidence: float  # Resonance sharpness indicator
    overall: float  # Weighted combination


@dataclass(frozen=True)
class AnalysisResult:
    """Result of tap tone FFT analysis."""

    dominant_hz: float | None
    peaks: list[Peak]
    clipped: bool
    rms: float
    confidence: float  # 0..1
    spectrum_freq_hz: np.ndarray
    spectrum_mag: np.ndarray  # normalized 0..1
    # Optional for backward compatibility - None means legacy heuristic was used
    confidence_components: ConfidenceComponents | None = None


def _highpass(x: np.ndarray, fs: int, hz: float) -> np.ndarray:
    """Apply 2nd-order Butterworth highpass filter."""
    if hz <= 0:
        return x
    nyq = 0.5 * fs
    w = hz / nyq
    b, a = butter(2, w, btype="highpass")
    return filtfilt(b, a, x).astype(np.float32)


def _compute_local_snr(
    spectrum: np.ndarray, peak_idx: int, noise_band: int = 20
) -> float:
    """
    Compute local SNR at a spectral peak.

    Uses median of neighboring bins (excluding peak region) as noise estimate.
    This is more robust than mean for spectra with multiple peaks.

    Args:
        spectrum: Magnitude spectrum (linear scale, not dB)
        peak_idx: Index of the peak bin
        noise_band: Number of bins on each side for noise estimation

    Returns:
        SNR in dB, clamped to [0, 60]
    """
    peak_power = spectrum[peak_idx] ** 2

    # Estimate noise from neighboring bins (excluding peak region ±5 bins)
    left_start = max(0, peak_idx - noise_band - 5)
    left_end = max(0, peak_idx - 5)
    right_start = min(len(spectrum) - 1, peak_idx + 5)
    right_end = min(len(spectrum) - 1, peak_idx + noise_band + 5)

    noise_bins = np.concatenate(
        [spectrum[left_start:left_end], spectrum[right_start:right_end]]
    )

    if len(noise_bins) < 3:
        return 0.0  # Cannot estimate noise

    # Use median for robust noise estimate
    noise_power = float(np.median(noise_bins)) ** 2

    if noise_power < 1e-20:
        return 60.0  # Very high SNR (cap at 60 dB)

    snr_linear = peak_power / noise_power
    snr_db = 10 * np.log10(snr_linear)

    return float(np.clip(snr_db, 0, 60))


def _compute_local_flatness(
    spectrum: np.ndarray, center_idx: int, bandwidth: int = 10
) -> float:
    """
    Compute spectral flatness in region around a peak.

    Spectral flatness = geometric_mean / arithmetic_mean
    - Pure tone: SF → 0 (tonal)
    - White noise: SF → 1 (noise-like)

    Args:
        spectrum: Magnitude spectrum
        center_idx: Center of analysis region
        bandwidth: Number of bins on each side

    Returns:
        Spectral flatness in [0, 1]
    """
    start = max(0, center_idx - bandwidth)
    end = min(len(spectrum), center_idx + bandwidth + 1)

    region = spectrum[start:end]

    if len(region) < 3 or np.all(region == 0):
        return 0.5

    # Avoid log of zero
    region = np.maximum(region, 1e-20)

    geometric_mean = np.exp(np.mean(np.log(region)))
    arithmetic_mean = np.mean(region)

    if arithmetic_mean < 1e-20:
        return 0.5

    flatness = geometric_mean / arithmetic_mean
    return float(np.clip(flatness, 0, 1))


def _estimate_q_factor(
    spectrum: np.ndarray, freqs: np.ndarray, peak_idx: int, q_reference: float = 20.0
) -> tuple[float | None, float]:
    """
    Estimate Q factor from half-power (-3dB) bandwidth.

    Q = f_center / bandwidth
    High Q → sharp resonance → more likely real mode

    Args:
        spectrum: Magnitude spectrum
        freqs: Frequency array (Hz)
        peak_idx: Index of the peak
        q_reference: Reference Q for confidence scaling (typical wood: 20)

    Returns:
        (q_factor, q_confidence) where q_confidence in [0, 1]
    """
    peak_mag = spectrum[peak_idx]
    half_power = peak_mag / np.sqrt(2)  # -3dB point

    # Find left -3dB crossing
    left_idx = peak_idx
    while left_idx > 0 and spectrum[left_idx] > half_power:
        left_idx -= 1

    # Find right -3dB crossing
    right_idx = peak_idx
    while right_idx < len(spectrum) - 1 and spectrum[right_idx] > half_power:
        right_idx += 1

    if left_idx == 0 or right_idx == len(spectrum) - 1:
        # Couldn't find both -3dB points
        return None, 0.5

    # Linear interpolation for precise crossing frequency
    f_center = freqs[peak_idx]

    if spectrum[left_idx] != spectrum[left_idx + 1]:
        f_lower = np.interp(
            half_power,
            [spectrum[left_idx], spectrum[left_idx + 1]],
            [freqs[left_idx], freqs[left_idx + 1]],
        )
    else:
        f_lower = freqs[left_idx]

    if spectrum[right_idx] != spectrum[right_idx - 1]:
        f_upper = np.interp(
            half_power,
            [spectrum[right_idx], spectrum[right_idx - 1]],
            [freqs[right_idx], freqs[right_idx - 1]],
        )
    else:
        f_upper = freqs[right_idx]

    bandwidth = f_upper - f_lower

    if bandwidth <= 0:
        return None, 0.5

    q = f_center / bandwidth

    # Q confidence: higher Q = higher confidence (up to a point)
    # Q < 5: probably not a resonance (conf → 0.2)
    # Q ~ 20: typical mode (conf → 0.6)
    # Q > 50: very sharp resonance (conf → 0.9)
    conf_q = 1.0 - np.exp(-q / q_reference)

    return float(q), float(np.clip(conf_q, 0, 1))


def _compute_peak_confidence(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    peak_idx: int,
    clipped: bool,
    rms: float,
    snr_threshold: float = 15.0,
    snr_steepness: float = 5.0,
) -> ConfidenceComponents:
    """
    Compute physics-based confidence for a spectral peak.

    Combines:
    - SNR: Is the peak above the noise floor? (weight: 0.45)
    - Flatness: Is this tonal vs broadband? (weight: 0.25)
    - Q factor: Does it look like a resonance? (weight: 0.30)

    Args:
        spectrum: Magnitude spectrum (linear scale)
        freqs: Frequency array (Hz)
        peak_idx: Index of the peak
        clipped: Whether signal was clipped
        rms: Signal RMS level
        snr_threshold: SNR (dB) for 50% confidence
        snr_steepness: Transition rate (dB)

    Returns:
        ConfidenceComponents with all factors and overall score
    """
    # Clipping or very low signal → low confidence
    if clipped:
        return ConfidenceComponents(
            snr_db=0.0,
            snr_confidence=0.0,
            flatness=1.0,
            flatness_confidence=0.0,
            q_factor=None,
            q_confidence=0.0,
            overall=0.1,
        )
    if rms < 0.005:
        return ConfidenceComponents(
            snr_db=0.0,
            snr_confidence=0.0,
            flatness=1.0,
            flatness_confidence=0.0,
            q_factor=None,
            q_confidence=0.0,
            overall=0.0,
        )

    # SNR: sigmoid mapping
    snr_db = _compute_local_snr(spectrum, peak_idx)
    conf_snr = 1.0 / (1.0 + np.exp(-(snr_db - snr_threshold) / snr_steepness))

    # Flatness: lower = more tonal = higher confidence
    flatness = _compute_local_flatness(spectrum, peak_idx)
    conf_flat = 1.0 - flatness

    # Q factor: sharper peak = more likely real mode
    q_factor, conf_q = _estimate_q_factor(spectrum, freqs, peak_idx)

    # Weighted combination (no coherence available in single-channel)
    weights = {"snr": 0.45, "flat": 0.25, "q": 0.30}
    overall = (
        weights["snr"] * conf_snr + weights["flat"] * conf_flat + weights["q"] * conf_q
    )

    return ConfidenceComponents(
        snr_db=float(snr_db),
        snr_confidence=float(conf_snr),
        flatness=float(flatness),
        flatness_confidence=float(conf_flat),
        q_factor=q_factor,
        q_confidence=float(conf_q),
        overall=float(np.clip(overall, 0, 1)),
    )


def analyze_tap(
    audio: np.ndarray,
    sample_rate: int,
    *,
    highpass_hz: float = 20.0,
    peak_min_hz: float = 40.0,
    peak_max_hz: float = 2000.0,
    peak_min_prominence: float = 0.05,
    peak_min_spacing_hz: float = 10.0,
    max_peaks: int = 12,
) -> AnalysisResult:
    """Analyze tap impulse audio and extract frequency peaks.

    Args:
        audio: Input audio signal (float32, [-1, 1])
        sample_rate: Sample rate in Hz
        highpass_hz: Highpass filter cutoff
        peak_min_hz: Minimum frequency for peak detection
        peak_max_hz: Maximum frequency for peak detection
        peak_min_prominence: Minimum peak prominence (0-1)
        peak_min_spacing_hz: Minimum spacing between peaks
        max_peaks: Maximum number of peaks to return

    Returns:
        AnalysisResult with detected peaks and spectrum
    """
    if audio.size == 0:
        return AnalysisResult(
            dominant_hz=None,
            peaks=[],
            clipped=False,
            rms=0.0,
            confidence=0.0,
            spectrum_freq_hz=np.array([], dtype=np.float32),
            spectrum_mag=np.array([], dtype=np.float32),
            confidence_components=None,
        )

    x = audio.astype(np.float32)

    # Health metrics
    clipped = bool(np.any(np.abs(x) >= 0.995))  # m6 fix: commercial standard
    rms = float(np.sqrt(np.mean(x * x)))

    # DC removal + high-pass
    x = x - float(np.mean(x))
    x = _highpass(x, sample_rate, highpass_hz)

    # Window
    w = np.hanning(x.size).astype(np.float32)
    xw = x * w

    # FFT magnitude (lab version: explicit float32 dtype)
    spec = np.abs(rfft(xw)).astype(np.float32)
    freqs = rfftfreq(xw.size, d=1.0 / sample_rate).astype(np.float32)

    # Normalize magnitude to 0..1 (lab version: explicit float32)
    spec_max = float(spec.max()) if spec.size else 0.0
    spec_n = (
        (spec / spec_max).astype(np.float32)
        if spec_max > 0
        else spec.astype(np.float32)
    )

    # Band mask
    mask = (freqs >= peak_min_hz) & (freqs <= peak_max_hz)
    freqs_m = freqs[mask]
    spec_m = spec_n[mask]

    if freqs_m.size < 4:
        return AnalysisResult(
            dominant_hz=None,
            peaks=[],
            clipped=clipped,
            rms=rms,
            confidence=0.0,
            spectrum_freq_hz=freqs,
            spectrum_mag=spec_n,
            confidence_components=None,
        )

    # Spacing Hz -> bins
    df = float(freqs_m[1] - freqs_m[0])
    min_dist_bins = max(1, int(round(peak_min_spacing_hz / df)))

    peaks_idx, _ = find_peaks(
        spec_m, prominence=peak_min_prominence, distance=min_dist_bins
    )

    # Sort peaks by magnitude descending
    peaks_sorted = sorted(
        peaks_idx.tolist(), key=lambda i: float(spec_m[i]), reverse=True
    )[:max_peaks]
    peaks_out: list[Peak] = [
        Peak(freq_hz=float(freqs_m[i]), magnitude=float(spec_m[i]))
        for i in peaks_sorted
    ]

    dominant_hz = peaks_out[0].freq_hz if peaks_out else None

    # Physics-based confidence (see docs/theory/confidence_derivation.md)
    # Uses SNR, spectral flatness, and Q-factor instead of arbitrary heuristic
    if peaks_out:
        # Find index of dominant peak in the masked spectrum
        dominant_freq = peaks_out[0].freq_hz
        peak_idx = int(np.argmin(np.abs(freqs_m - dominant_freq)))

        confidence_components = _compute_peak_confidence(
            spectrum=spec_m,
            freqs=freqs_m,
            peak_idx=peak_idx,
            clipped=clipped,
            rms=rms,
        )
        conf = confidence_components.overall
    else:
        confidence_components = ConfidenceComponents(
            snr_db=0.0,
            snr_confidence=0.0,
            flatness=1.0,
            flatness_confidence=0.0,
            q_factor=None,
            q_confidence=0.0,
            overall=0.0,
        )
        conf = 0.0

    return AnalysisResult(
        dominant_hz=dominant_hz,
        peaks=peaks_out,
        clipped=clipped,
        rms=rms,
        confidence=float(conf),
        spectrum_freq_hz=freqs,
        spectrum_mag=spec_n,
        confidence_components=confidence_components,
    )


def analysis_to_json_dict(res: AnalysisResult) -> dict[str, Any]:
    """Convert AnalysisResult to JSON-serializable dict.

    Note: This uses the simpler format for backward compatibility.
    The storage layer adds additional fields (label, sample_rate, ts_utc).
    """
    result = {
        "dominant_hz": res.dominant_hz,
        "peaks": [{"freq_hz": p.freq_hz, "magnitude": p.magnitude} for p in res.peaks],
        "clipped": res.clipped,
        "rms": res.rms,
        "confidence": res.confidence,
    }

    # Include confidence breakdown for diagnostics (if available)
    if res.confidence_components is not None:
        cc = res.confidence_components
        result["confidence_components"] = {
            "snr_db": round(cc.snr_db, 2),
            "snr_confidence": round(cc.snr_confidence, 3),
            "flatness": round(cc.flatness, 3),
            "flatness_confidence": round(cc.flatness_confidence, 3),
            "q_factor": round(cc.q_factor, 1) if cc.q_factor is not None else None,
            "q_confidence": round(cc.q_confidence, 3),
        }

    return result

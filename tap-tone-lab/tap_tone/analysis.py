from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import butter, filtfilt, find_peaks


@dataclass(frozen=True)
class Peak:
    freq_hz: float
    magnitude: float  # normalized 0..1


@dataclass(frozen=True)
class AnalysisResult:
    dominant_hz: float | None
    peaks: list[Peak]
    clipped: bool
    rms: float
    confidence: float  # 0..1
    spectrum_freq_hz: np.ndarray
    spectrum_mag: np.ndarray  # normalized 0..1


def _highpass(x: np.ndarray, fs: int, hz: float) -> np.ndarray:
    if hz <= 0:
        return x
    nyq = 0.5 * fs
    w = hz / nyq
    b, a = butter(2, w, btype="highpass")
    return filtfilt(b, a, x).astype(np.float32)


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
    if audio.size == 0:
        return AnalysisResult(
            dominant_hz=None,
            peaks=[],
            clipped=False,
            rms=0.0,
            confidence=0.0,
            spectrum_freq_hz=np.array([], dtype=np.float32),
            spectrum_mag=np.array([], dtype=np.float32),
        )

    x = audio.astype(np.float32)

    clipped = bool(np.any(np.abs(x) >= 0.999))
    rms = float(np.sqrt(np.mean(x * x)))

    # DC removal + high-pass
    x = x - float(np.mean(x))
    x = _highpass(x, sample_rate, highpass_hz)

    # Window
    w = np.hanning(x.size).astype(np.float32)
    xw = x * w

    # FFT magnitude
    spec = np.abs(rfft(xw)).astype(np.float32)
    freqs = rfftfreq(xw.size, d=1.0 / sample_rate).astype(np.float32)

    # Normalize magnitude to 0..1
    spec_max = float(spec.max()) if spec.size else 0.0
    spec_n = (spec / spec_max).astype(np.float32) if spec_max > 0 else spec.astype(np.float32)

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
        )

    # spacing Hz -> bins
    df = float(freqs_m[1] - freqs_m[0])
    min_dist_bins = max(1, int(round(peak_min_spacing_hz / df)))

    peaks_idx, props = find_peaks(spec_m, prominence=peak_min_prominence, distance=min_dist_bins)

    peaks_sorted = sorted(peaks_idx.tolist(), key=lambda i: float(spec_m[i]), reverse=True)[:max_peaks]
    peaks_out: list[Peak] = [Peak(freq_hz=float(freqs_m[i]), magnitude=float(spec_m[i])) for i in peaks_sorted]

    dominant_hz = peaks_out[0].freq_hz if peaks_out else None

    # Confidence heuristic (validity only, not "tone")
    conf = 0.0
    if not clipped and rms > 0.005 and peaks_out:
        conf = min(1.0, 0.5 + 0.5 * float(peaks_out[0].magnitude))
    elif not clipped and rms > 0.01:
        conf = 0.3

    return AnalysisResult(
        dominant_hz=dominant_hz,
        peaks=peaks_out,
        clipped=clipped,
        rms=rms,
        confidence=float(conf),
        spectrum_freq_hz=freqs,
        spectrum_mag=spec_n,
    )


def analysis_to_json_dict(res: AnalysisResult, *, sample_rate: int, label: str | None) -> dict[str, Any]:
    return {
        "ts_utc": None,  # storage layer fills this
        "label": label,
        "sample_rate": int(sample_rate),
        "channels": 1,
        "dominant_hz": res.dominant_hz,
        "rms": [res.rms],
        "clipped": [res.clipped],
        "confidence": res.confidence,
        "peaks": {
            "ch0": [{"freq_hz": p.freq_hz, "magnitude": p.magnitude} for p in res.peaks]
        },
        "algo": {
            "version": "0.3.0-phase1",
            "window": "hann",
            "highpass_hz": None,
            "peak_min_hz": None,
            "peak_max_hz": None,
            "peak_min_prominence": None,
            "coherence_nperseg": None,
        },
    }

"""
Envelope tracking for transient defect detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from scipy import signal as scipy_signal


@dataclass
class TransientEvent:
    """A detected transient in the envelope."""

    start_sample: int
    end_sample: int
    peak_sample: int
    peak_amplitude: float
    rise_rate: float  # Amplitude units per sample
    duration_samples: int

    @property
    def duration_s(self) -> float:
        """Duration in seconds (requires sample_rate)."""
        # This is set externally
        return getattr(self, "_duration_s", self.duration_samples / 48000)

    def with_sample_rate(self, sample_rate: int) -> "TransientEvent":
        """Return copy with sample rate for time calculations."""
        event = TransientEvent(
            start_sample=self.start_sample,
            end_sample=self.end_sample,
            peak_sample=self.peak_sample,
            peak_amplitude=self.peak_amplitude,
            rise_rate=self.rise_rate,
            duration_samples=self.duration_samples,
        )
        event._duration_s = self.duration_samples / sample_rate
        event._sample_rate = sample_rate
        return event

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "start_sample": self.start_sample,
            "end_sample": self.end_sample,
            "peak_sample": self.peak_sample,
            "peak_amplitude": self.peak_amplitude,
            "rise_rate": self.rise_rate,
            "duration_samples": self.duration_samples,
        }


def compute_envelope(
    signal: np.ndarray,
    sample_rate: int = 48000,
    method: str = "hilbert",
    smoothing_ms: float = 2.0,
) -> np.ndarray:
    """
    Compute the envelope of a signal.

    Args:
        signal: Input signal array
        sample_rate: Sample rate in Hz
        method: "hilbert" (analytic) or "rectify" (rectified + LPF)
        smoothing_ms: Smoothing time constant in milliseconds

    Returns:
        Envelope array (same length as input)
    """
    if method == "hilbert":
        # Hilbert transform for analytic signal envelope
        analytic = scipy_signal.hilbert(signal)
        envelope = np.abs(analytic)
    else:
        # Full-wave rectification + lowpass filter
        rectified = np.abs(signal)

        # Design lowpass filter
        cutoff_hz = 1000.0 / smoothing_ms  # Approximate
        nyquist = sample_rate / 2
        if cutoff_hz >= nyquist:
            cutoff_hz = nyquist * 0.9

        b, a = scipy_signal.butter(2, cutoff_hz / nyquist, btype="low")
        envelope = scipy_signal.filtfilt(b, a, rectified)

    # Apply smoothing if specified
    if smoothing_ms > 0:
        smoothing_samples = int(smoothing_ms * sample_rate / 1000)
        if smoothing_samples > 1:
            kernel = np.ones(smoothing_samples) / smoothing_samples
            envelope = np.convolve(envelope, kernel, mode="same")

    return envelope


def envelope_derivative(
    envelope: np.ndarray,
    sample_rate: int = 48000,
    smoothing_ms: float = 1.0,
) -> np.ndarray:
    """
    Compute derivative of envelope for transient detection.

    Args:
        envelope: Envelope array
        sample_rate: Sample rate in Hz
        smoothing_ms: Pre-derivative smoothing

    Returns:
        Derivative array
    """
    # Apply smoothing first
    if smoothing_ms > 0:
        smoothing_samples = max(1, int(smoothing_ms * sample_rate / 1000))
        kernel = np.ones(smoothing_samples) / smoothing_samples
        envelope = np.convolve(envelope, kernel, mode="same")

    # Compute derivative
    derivative = np.diff(envelope, prepend=envelope[0])

    return derivative


def detect_transients(
    signal: np.ndarray,
    sample_rate: int = 48000,
    threshold_factor: float = 3.0,
    min_duration_ms: float = 0.5,
    max_duration_ms: float = 50.0,
    merge_gap_ms: float = 2.0,
) -> List[TransientEvent]:
    """
    Detect transient events in a signal.

    Transients are detected as rapid increases in envelope amplitude
    that exceed the local noise floor by threshold_factor.

    Args:
        signal: Input signal array
        sample_rate: Sample rate in Hz
        threshold_factor: Detection threshold as multiple of local noise
        min_duration_ms: Minimum transient duration
        max_duration_ms: Maximum transient duration
        merge_gap_ms: Merge transients closer than this

    Returns:
        List of TransientEvent objects
    """
    # Compute envelope
    envelope = compute_envelope(signal, sample_rate, smoothing_ms=1.0)

    # Compute derivative
    derivative = envelope_derivative(envelope, sample_rate)

    # Estimate noise floor using median
    noise_floor = np.median(envelope) * threshold_factor

    # Find regions where envelope exceeds threshold
    above_threshold = envelope > noise_floor

    # Find rapid rises (positive derivative above threshold)
    rise_threshold = np.std(derivative) * threshold_factor
    rapid_rise = derivative > rise_threshold

    # Combine: transient = above threshold AND rapid rise recently
    # Use a small lookahead window
    lookahead_samples = int(5.0 * sample_rate / 1000)  # 5ms

    transient_regions = []
    in_transient = False
    start_idx = 0

    for i in range(len(signal)):
        # Check if rapid rise occurred recently
        window_start = max(0, i - lookahead_samples)
        had_rise = np.any(rapid_rise[window_start:i + 1])

        if above_threshold[i] and had_rise and not in_transient:
            # Start of transient
            in_transient = True
            start_idx = i
        elif not above_threshold[i] and in_transient:
            # End of transient
            in_transient = False
            transient_regions.append((start_idx, i))

    # Handle transient at end of signal
    if in_transient:
        transient_regions.append((start_idx, len(signal) - 1))

    # Convert to TransientEvent objects with filtering
    min_samples = int(min_duration_ms * sample_rate / 1000)
    max_samples = int(max_duration_ms * sample_rate / 1000)
    merge_samples = int(merge_gap_ms * sample_rate / 1000)

    # Merge close transients
    merged_regions = []
    for start, end in transient_regions:
        if merged_regions and start - merged_regions[-1][1] < merge_samples:
            # Merge with previous
            merged_regions[-1] = (merged_regions[-1][0], end)
        else:
            merged_regions.append((start, end))

    # Filter by duration and create events
    events = []
    for start, end in merged_regions:
        duration = end - start
        if min_samples <= duration <= max_samples:
            # Find peak within region
            region_env = envelope[start:end]
            peak_idx = start + np.argmax(region_env)
            peak_amp = envelope[peak_idx]

            # Calculate rise rate
            rise_samples = peak_idx - start
            if rise_samples > 0:
                rise_rate = (peak_amp - envelope[start]) / rise_samples
            else:
                rise_rate = 0.0

            event = TransientEvent(
                start_sample=start,
                end_sample=end,
                peak_sample=peak_idx,
                peak_amplitude=peak_amp,
                rise_rate=rise_rate,
                duration_samples=duration,
            ).with_sample_rate(sample_rate)

            events.append(event)

    return events


def compute_crest_factor(signal: np.ndarray) -> float:
    """
    Compute crest factor (peak to RMS ratio).

    High crest factor indicates impulsive/transient content.

    Args:
        signal: Input signal array

    Returns:
        Crest factor in dB
    """
    peak = np.max(np.abs(signal))
    rms = np.sqrt(np.mean(signal ** 2))

    if rms < 1e-10:
        return 0.0

    return 20 * np.log10(peak / rms)


def compute_envelope_modulation(
    envelope: np.ndarray,
    sample_rate: int = 48000,
    freq_range: Tuple[float, float] = (1.0, 100.0),
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Analyze modulation frequencies in the envelope.

    Useful for detecting periodic defects (e.g., once-per-revolution).

    Args:
        envelope: Envelope array
        sample_rate: Sample rate in Hz
        freq_range: Frequency range of interest (Hz)

    Returns:
        Tuple of (frequencies, magnitudes)
    """
    # FFT of envelope
    n = len(envelope)
    fft = np.fft.rfft(envelope)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

    # Filter to frequency range of interest
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    freqs_filtered = freqs[mask]
    mags_filtered = np.abs(fft[mask])

    return freqs_filtered, mags_filtered

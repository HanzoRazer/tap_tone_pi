"""
FFT and transfer function computation.
"""

from typing import Tuple, Optional
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import welch, csd


def compute_fft(
    signal: np.ndarray,
    sample_rate: float,
    window: str = "hann"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute FFT of a signal.

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate in Hz
        window: Window function ('hann', 'hamming', 'blackman', 'none')

    Returns:
        Tuple of (frequencies, magnitudes)
    """
    signal = np.asarray(signal)
    n = len(signal)

    # Apply window
    if window == "hann":
        win = np.hanning(n)
    elif window == "hamming":
        win = np.hamming(n)
    elif window == "blackman":
        win = np.blackman(n)
    else:
        win = np.ones(n)

    windowed = signal * win

    # Compute FFT
    fft_result = rfft(windowed)
    frequencies = rfftfreq(n, 1.0 / sample_rate)
    magnitudes = np.abs(fft_result) * 2.0 / n  # Normalize

    return frequencies, magnitudes


def compute_transfer_function(
    input_signal: np.ndarray,
    output_signal: np.ndarray,
    sample_rate: float,
    nperseg: int = 2048,
    noverlap: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute transfer function H(f) = Y(f) / X(f) using Welch's method.

    Also computes coherence to assess measurement quality.

    Args:
        input_signal: Input (excitation) signal
        output_signal: Output (response) signal
        sample_rate: Sample rate in Hz
        nperseg: Segment length for Welch's method
        noverlap: Overlap between segments (default: nperseg // 2)

    Returns:
        Tuple of (frequencies, H_magnitude, coherence, phase_degrees)
    """
    input_signal = np.asarray(input_signal)
    output_signal = np.asarray(output_signal)

    if noverlap is None:
        noverlap = nperseg // 2

    # Compute auto-spectral densities
    f, Pxx = welch(input_signal, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)
    _, Pyy = welch(output_signal, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)

    # Compute cross-spectral density
    _, Pxy = csd(input_signal, output_signal, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)

    # Transfer function H(f) = Pxy / Pxx
    H = Pxy / (Pxx + 1e-10)  # Add small value to avoid division by zero
    H_mag = np.abs(H)
    H_phase = np.angle(H, deg=True)

    # Coherence = |Pxy|^2 / (Pxx * Pyy)
    coherence = np.abs(Pxy) ** 2 / ((Pxx * Pyy) + 1e-10)
    coherence = np.clip(coherence, 0, 1)

    return f, H_mag, coherence, H_phase


def compute_power_spectrum(
    signal: np.ndarray,
    sample_rate: float,
    nperseg: int = 2048
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute power spectral density using Welch's method.

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate in Hz
        nperseg: Segment length

    Returns:
        Tuple of (frequencies, PSD)
    """
    return welch(signal, fs=sample_rate, nperseg=nperseg)


def frequency_response_smoothing(
    frequencies: np.ndarray,
    magnitudes: np.ndarray,
    octave_fraction: float = 1/3
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Smooth frequency response using fractional-octave averaging.

    Args:
        frequencies: Frequency array
        magnitudes: Magnitude array
        octave_fraction: Fraction of octave for smoothing (1/3, 1/6, 1/12, etc.)

    Returns:
        Tuple of (smoothed frequencies, smoothed magnitudes)
    """
    frequencies = np.asarray(frequencies)
    magnitudes = np.asarray(magnitudes)

    # Generate center frequencies for smoothing bands
    f_min = frequencies[frequencies > 0].min()
    f_max = frequencies.max()

    # Logarithmic frequency spacing
    n_bands = int(np.log2(f_max / f_min) / octave_fraction) + 1
    center_freqs = f_min * (2 ** (octave_fraction * np.arange(n_bands)))

    smoothed_mags = np.zeros(n_bands)

    for i, fc in enumerate(center_freqs):
        # Band edges
        f_low = fc / (2 ** (octave_fraction / 2))
        f_high = fc * (2 ** (octave_fraction / 2))

        # Find points in band
        mask = (frequencies >= f_low) & (frequencies < f_high)
        if np.any(mask):
            # RMS average
            smoothed_mags[i] = np.sqrt(np.mean(magnitudes[mask] ** 2))
        else:
            smoothed_mags[i] = 0

    return center_freqs, smoothed_mags


def find_resonance_frequency(
    frequencies: np.ndarray,
    magnitudes: np.ndarray,
    freq_range: Tuple[float, float] = (50, 500)
) -> float:
    """
    Find the dominant resonance frequency in a range.

    Args:
        frequencies: Frequency array
        magnitudes: Magnitude array
        freq_range: (min_freq, max_freq) to search

    Returns:
        Resonance frequency in Hz
    """
    frequencies = np.asarray(frequencies)
    magnitudes = np.asarray(magnitudes)

    # Filter to range
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    if not np.any(mask):
        return 0.0

    freq_in_range = frequencies[mask]
    mag_in_range = magnitudes[mask]

    # Find peak
    peak_idx = np.argmax(mag_in_range)

    return float(freq_in_range[peak_idx])

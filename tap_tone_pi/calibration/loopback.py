"""
Loopback calibration test for measuring system frequency response.

Plays a sweep or chirp through the output, captures through the input,
and computes the system's frequency response for compensation.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum


class SweepType(Enum):
    """Type of test signal for loopback."""

    LINEAR = "linear"  # Linear frequency sweep
    LOG = "log"  # Logarithmic frequency sweep
    CHIRP = "chirp"  # Exponential chirp


@dataclass
class LoopbackConfig:
    """Configuration for loopback test."""

    # Frequency range
    freq_start_hz: float = 20.0
    freq_end_hz: float = 20000.0

    # Signal parameters
    sweep_type: SweepType = SweepType.LOG
    duration_s: float = 2.0
    amplitude: float = 0.5  # 0-1 range

    # Analysis parameters
    sample_rate: int = 48000
    fft_size: int = 8192
    overlap: float = 0.5

    # Quality thresholds
    min_snr_db: float = 20.0  # Minimum acceptable SNR
    max_latency_ms: float = 50.0  # Maximum acceptable latency


@dataclass
class FrequencyResponsePoint:
    """Single point in frequency response measurement."""

    freq_hz: float
    magnitude_db: float
    phase_deg: float


@dataclass
class LoopbackResult:
    """Results from loopback calibration test."""

    # Test metadata
    success: bool
    error_message: str = ""

    # Latency measurement
    latency_samples: int = 0
    latency_ms: float = 0.0

    # Signal quality
    snr_db: float = 0.0
    noise_floor_db: float = -96.0

    # Frequency response
    frequency_response: List[FrequencyResponsePoint] = field(default_factory=list)

    # Raw data for advanced analysis
    frequencies_hz: np.ndarray = field(default_factory=lambda: np.array([]))
    magnitude_db: np.ndarray = field(default_factory=lambda: np.array([]))
    phase_deg: np.ndarray = field(default_factory=lambda: np.array([]))

    def get_magnitude_at_freq(self, freq_hz: float) -> Optional[float]:
        """Get magnitude at specific frequency (interpolated)."""
        if len(self.frequencies_hz) == 0:
            return None
        return float(np.interp(freq_hz, self.frequencies_hz, self.magnitude_db))

    def get_flatness_db(self, freq_low: float = 100, freq_high: float = 10000) -> float:
        """Get peak-to-peak variation in frequency range."""
        if len(self.frequencies_hz) == 0:
            return float("inf")

        mask = (self.frequencies_hz >= freq_low) & (self.frequencies_hz <= freq_high)
        if not np.any(mask):
            return float("inf")

        magnitudes = self.magnitude_db[mask]
        return float(np.max(magnitudes) - np.min(magnitudes))


def generate_sweep(config: LoopbackConfig) -> np.ndarray:
    """
    Generate test sweep signal.

    Args:
        config: Loopback configuration

    Returns:
        numpy array of samples
    """
    n_samples = int(config.duration_s * config.sample_rate)
    t = np.linspace(0, config.duration_s, n_samples, dtype=np.float32)

    if config.sweep_type == SweepType.LINEAR:
        # Linear frequency sweep
        freq = np.linspace(config.freq_start_hz, config.freq_end_hz, n_samples)
        phase = 2 * np.pi * np.cumsum(freq) / config.sample_rate
        signal = np.sin(phase)

    elif config.sweep_type == SweepType.LOG:
        # Logarithmic frequency sweep (more energy at low frequencies)
        k = (config.freq_end_hz / config.freq_start_hz) ** (1.0 / config.duration_s)
        phase = (
            2
            * np.pi
            * config.freq_start_hz
            * (k**t - 1)
            / np.log(k)
        )
        signal = np.sin(phase)

    else:  # CHIRP
        # Exponential chirp
        from scipy.signal import chirp as scipy_chirp

        signal = scipy_chirp(
            t,
            config.freq_start_hz,
            config.duration_s,
            config.freq_end_hz,
            method="logarithmic",
        )

    # Apply amplitude and fade in/out to avoid clicks
    fade_samples = int(0.01 * config.sample_rate)  # 10ms fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)

    signal[:fade_samples] *= fade_in
    signal[-fade_samples:] *= fade_out
    signal *= config.amplitude

    return signal.astype(np.float32)


def measure_latency(
    reference: np.ndarray, captured: np.ndarray, sample_rate: int
) -> Tuple[int, float]:
    """
    Measure latency using cross-correlation.

    Args:
        reference: Original signal
        captured: Captured signal
        sample_rate: Sample rate in Hz

    Returns:
        Tuple of (latency_samples, latency_ms)
    """
    # Use cross-correlation to find delay
    correlation = np.correlate(captured, reference, mode="full")

    # Find peak
    peak_idx = np.argmax(np.abs(correlation))

    # Convert to latency
    latency_samples = peak_idx - len(reference) + 1
    latency_ms = (latency_samples / sample_rate) * 1000.0

    return int(latency_samples), float(latency_ms)


def compute_frequency_response(
    reference: np.ndarray,
    captured: np.ndarray,
    sample_rate: int,
    fft_size: int = 8192,
    overlap: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute frequency response from reference and captured signals.

    Uses Welch's method for averaged spectral estimation.

    Args:
        reference: Original signal sent
        captured: Signal captured through system
        sample_rate: Sample rate in Hz
        fft_size: FFT window size
        overlap: Overlap ratio (0-1)

    Returns:
        Tuple of (frequencies_hz, magnitude_db, phase_deg)
    """
    from scipy.signal import welch, csd

    # Compute power spectral densities
    nperseg = min(fft_size, len(reference))
    noverlap = int(nperseg * overlap)

    # Reference spectrum
    f_ref, psd_ref = welch(
        reference, fs=sample_rate, nperseg=nperseg, noverlap=noverlap
    )

    # Captured spectrum
    _, _psd_cap = welch(captured, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)

    # Cross spectral density for phase
    _, csd_result = csd(
        reference, captured, fs=sample_rate, nperseg=nperseg, noverlap=noverlap
    )

    # Compute transfer function
    # H(f) = Pxy(f) / Pxx(f)
    eps = 1e-10  # Avoid division by zero
    transfer_function = csd_result / (psd_ref + eps)

    # Magnitude in dB (relative)
    magnitude_db = 20 * np.log10(np.abs(transfer_function) + eps)

    # Phase in degrees
    phase_deg = np.angle(transfer_function, deg=True)

    return f_ref, magnitude_db.astype(np.float64), phase_deg.astype(np.float64)


def compute_snr(signal: np.ndarray, noise_floor_db: float = -96.0) -> float:
    """
    Estimate SNR from captured signal.

    Args:
        signal: Captured signal
        noise_floor_db: Assumed noise floor in dB

    Returns:
        Estimated SNR in dB
    """
    # RMS of signal
    rms = np.sqrt(np.mean(signal**2))
    signal_db = 20 * np.log10(rms + 1e-10)

    return float(signal_db - noise_floor_db)


def run_loopback_test(
    config: LoopbackConfig,
    play_and_record_fn=None,
) -> LoopbackResult:
    """
    Run loopback calibration test.

    This function generates a test signal, plays it through the output,
    captures through the input, and analyzes the system response.

    Args:
        config: Test configuration
        play_and_record_fn: Function that takes (signal, sample_rate) and returns
                           captured audio. If None, returns simulated result.

    Returns:
        LoopbackResult with test results
    """
    # Generate test signal
    reference = generate_sweep(config)

    if play_and_record_fn is None:
        # Simulation mode - return ideal response with some realistic imperfections
        return _simulate_loopback_result(config, reference)

    try:
        # Play and record
        captured = play_and_record_fn(reference, config.sample_rate)

        if captured is None or len(captured) == 0:
            return LoopbackResult(
                success=False, error_message="No audio captured"
            )

        # Ensure same length for analysis
        min_len = min(len(reference), len(captured))
        reference = reference[:min_len]
        captured = captured[:min_len]

        # Measure latency
        latency_samples, latency_ms = measure_latency(
            reference, captured, config.sample_rate
        )

        # Check latency threshold
        if latency_ms > config.max_latency_ms:
            return LoopbackResult(
                success=False,
                error_message=f"Latency {latency_ms:.1f}ms exceeds maximum {config.max_latency_ms}ms",
                latency_samples=latency_samples,
                latency_ms=latency_ms,
            )

        # Compute frequency response
        frequencies, magnitude_db, phase_deg = compute_frequency_response(
            reference, captured, config.sample_rate, config.fft_size, config.overlap
        )

        # Estimate SNR
        snr_db = compute_snr(captured)

        if snr_db < config.min_snr_db:
            return LoopbackResult(
                success=False,
                error_message=f"SNR {snr_db:.1f}dB below minimum {config.min_snr_db}dB",
                latency_samples=latency_samples,
                latency_ms=latency_ms,
                snr_db=snr_db,
            )

        # Build frequency response points
        fr_points = [
            FrequencyResponsePoint(
                freq_hz=float(f), magnitude_db=float(m), phase_deg=float(p)
            )
            for f, m, p in zip(frequencies, magnitude_db, phase_deg)
            if config.freq_start_hz <= f <= config.freq_end_hz
        ]

        return LoopbackResult(
            success=True,
            latency_samples=latency_samples,
            latency_ms=latency_ms,
            snr_db=snr_db,
            frequency_response=fr_points,
            frequencies_hz=frequencies,
            magnitude_db=magnitude_db,
            phase_deg=phase_deg,
        )

    except Exception as e:
        return LoopbackResult(success=False, error_message=str(e))


def _simulate_loopback_result(
    config: LoopbackConfig, reference: np.ndarray
) -> LoopbackResult:
    """Generate simulated loopback result for testing without hardware."""
    # Generate frequency axis
    n_points = config.fft_size // 2 + 1
    frequencies = np.linspace(0, config.sample_rate / 2, n_points)

    # Simulate typical USB audio response
    # - Roll-off at low frequencies
    # - Slight boost around 2-5kHz
    # - Roll-off above 15kHz
    magnitude_db = np.zeros(n_points)

    for i, f in enumerate(frequencies):
        if f < 50:
            magnitude_db[i] = -6 * (1 - f / 50)  # Low frequency roll-off
        elif f < 2000:
            magnitude_db[i] = 0
        elif f < 5000:
            magnitude_db[i] = 1.5 * ((f - 2000) / 3000)  # Slight presence boost
        elif f < 15000:
            magnitude_db[i] = 1.5 - 1.5 * ((f - 5000) / 10000)
        else:
            magnitude_db[i] = -3 * ((f - 15000) / 5000)  # High frequency roll-off

    # Add some realistic noise
    magnitude_db += np.random.normal(0, 0.2, n_points)

    # Phase (approximately linear for typical latency)
    latency_ms = 15.0  # Typical USB audio latency
    latency_samples = int(latency_ms * config.sample_rate / 1000)
    phase_deg = -360 * frequencies * latency_ms / 1000

    # Build response points
    fr_points = [
        FrequencyResponsePoint(
            freq_hz=float(f), magnitude_db=float(m), phase_deg=float(p)
        )
        for f, m, p in zip(frequencies, magnitude_db, phase_deg)
        if config.freq_start_hz <= f <= config.freq_end_hz
    ]

    return LoopbackResult(
        success=True,
        latency_samples=latency_samples,
        latency_ms=latency_ms,
        snr_db=45.0,  # Typical for decent USB audio
        noise_floor_db=-90.0,
        frequency_response=fr_points,
        frequencies_hz=frequencies,
        magnitude_db=magnitude_db,
        phase_deg=phase_deg,
    )

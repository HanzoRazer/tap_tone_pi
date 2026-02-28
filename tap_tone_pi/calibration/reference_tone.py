"""
Reference tone calibration for amplitude verification.

Uses a known frequency (typically 1 kHz) at known amplitude to verify
the measurement chain's amplitude accuracy.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class ReferenceToneConfig:
    """Configuration for reference tone test."""

    # Reference signal parameters
    frequency_hz: float = 1000.0  # Standard calibration frequency
    amplitude_dbfs: float = -20.0  # Reference amplitude in dBFS
    duration_s: float = 2.0

    # Analysis parameters
    sample_rate: int = 48000
    fft_size: int = 8192

    # Acceptance thresholds
    max_amplitude_error_db: float = 1.0  # Maximum acceptable error
    min_thd_db: float = -40.0  # Minimum THD (should be lower = better)


@dataclass
class ReferenceToneResult:
    """Results from reference tone calibration test."""

    # Test metadata
    success: bool
    error_message: str = ""

    # Amplitude measurements
    reference_amplitude_dbfs: float = 0.0  # What we sent
    measured_amplitude_dbfs: float = 0.0  # What we measured
    amplitude_error_db: float = 0.0  # Difference

    # Frequency accuracy
    measured_frequency_hz: float = 0.0
    frequency_error_hz: float = 0.0

    # Distortion analysis
    thd_db: float = 0.0  # Total harmonic distortion
    thd_percent: float = 0.0

    # Noise measurements
    noise_floor_dbfs: float = -96.0
    snr_db: float = 0.0


def generate_reference_tone(config: ReferenceToneConfig) -> np.ndarray:
    """
    Generate reference tone signal.

    Args:
        config: Reference tone configuration

    Returns:
        numpy array of samples
    """
    n_samples = int(config.duration_s * config.sample_rate)
    t = np.linspace(0, config.duration_s, n_samples, dtype=np.float64)

    # Generate pure sine wave
    signal = np.sin(2 * np.pi * config.frequency_hz * t)

    # Convert dBFS to linear amplitude
    amplitude = 10 ** (config.amplitude_dbfs / 20.0)
    signal *= amplitude

    # Apply fade in/out to avoid clicks
    fade_samples = int(0.01 * config.sample_rate)  # 10ms fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)

    signal[:fade_samples] *= fade_in
    signal[-fade_samples:] *= fade_out

    return signal.astype(np.float32)


def measure_amplitude_dbfs(signal: np.ndarray) -> float:
    """
    Measure RMS amplitude in dBFS.

    Args:
        signal: Audio signal (-1 to 1 range)

    Returns:
        Amplitude in dBFS
    """
    rms = np.sqrt(np.mean(signal**2))
    # dBFS where 0 dBFS = full scale (1.0)
    dbfs = 20 * np.log10(rms + 1e-10)
    return float(dbfs)


def find_fundamental_frequency(
    signal: np.ndarray,
    sample_rate: int,
    expected_freq: float,
    search_range: float = 50.0,
) -> float:
    """
    Find the fundamental frequency using FFT.

    Args:
        signal: Audio signal
        sample_rate: Sample rate in Hz
        expected_freq: Expected frequency (for search window)
        search_range: Search range around expected frequency

    Returns:
        Measured frequency in Hz
    """
    # Compute FFT
    n = len(signal)
    fft_result = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

    # Find peak in search range
    mask = (freqs >= expected_freq - search_range) & (
        freqs <= expected_freq + search_range
    )
    masked_magnitude = np.abs(fft_result)
    masked_magnitude[~mask] = 0

    peak_idx = np.argmax(masked_magnitude)

    # Parabolic interpolation for sub-bin accuracy
    if 0 < peak_idx < len(fft_result) - 1:
        alpha = np.abs(fft_result[peak_idx - 1])
        beta = np.abs(fft_result[peak_idx])
        gamma = np.abs(fft_result[peak_idx + 1])

        if beta > 0:
            p = 0.5 * (alpha - gamma) / (alpha - 2 * beta + gamma)
            freq_correction = p * (freqs[1] - freqs[0])
            return float(freqs[peak_idx] + freq_correction)

    return float(freqs[peak_idx])


def measure_thd(
    signal: np.ndarray, sample_rate: int, fundamental_freq: float, n_harmonics: int = 5
) -> tuple[float, float]:
    """
    Measure Total Harmonic Distortion.

    Args:
        signal: Audio signal
        sample_rate: Sample rate in Hz
        fundamental_freq: Fundamental frequency in Hz
        n_harmonics: Number of harmonics to include

    Returns:
        Tuple of (THD in dB, THD in percent)
    """
    # Compute FFT
    n = len(signal)
    fft_result = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    magnitudes = np.abs(fft_result)

    # Find fundamental power
    fundamental_idx = np.argmin(np.abs(freqs - fundamental_freq))
    fundamental_power = magnitudes[fundamental_idx] ** 2

    # Sum harmonic powers
    harmonic_power = 0.0
    for h in range(2, n_harmonics + 2):  # 2nd through (n_harmonics+1)th harmonic
        harmonic_freq = fundamental_freq * h
        if harmonic_freq > sample_rate / 2:
            break
        harmonic_idx = np.argmin(np.abs(freqs - harmonic_freq))
        harmonic_power += magnitudes[harmonic_idx] ** 2

    # Calculate THD
    if fundamental_power > 0:
        thd_ratio = np.sqrt(harmonic_power / fundamental_power)
        thd_percent = thd_ratio * 100.0
        thd_db = 20 * np.log10(thd_ratio + 1e-10)
    else:
        thd_percent = 100.0
        thd_db = 0.0

    return float(thd_db), float(thd_percent)


def estimate_noise_floor(
    signal: np.ndarray,
    sample_rate: int,
    exclude_freq: float,
    exclude_width: float = 100.0,
) -> float:
    """
    Estimate noise floor excluding signal frequency.

    Args:
        signal: Audio signal
        sample_rate: Sample rate in Hz
        exclude_freq: Frequency to exclude (and harmonics)
        exclude_width: Width of exclusion band in Hz

    Returns:
        Noise floor in dBFS
    """
    # Compute FFT
    n = len(signal)
    fft_result = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    magnitudes = np.abs(fft_result)

    # Create mask excluding fundamental and harmonics
    mask = np.ones(len(freqs), dtype=bool)
    for h in range(1, 10):  # Exclude first 9 harmonics
        harmonic_freq = exclude_freq * h
        mask &= ~(
            (freqs >= harmonic_freq - exclude_width)
            & (freqs <= harmonic_freq + exclude_width)
        )

    # Calculate noise floor from remaining bins
    if np.any(mask):
        noise_power = np.mean(magnitudes[mask] ** 2)
        noise_rms = np.sqrt(noise_power)
        # Scale to dBFS
        noise_dbfs = 20 * np.log10(noise_rms * np.sqrt(2) / n + 1e-10)
    else:
        noise_dbfs = -96.0

    return float(noise_dbfs)


def verify_amplitude(
    reference_dbfs: float, measured_dbfs: float, max_error_db: float = 1.0
) -> tuple[bool, float]:
    """
    Verify amplitude accuracy.

    Args:
        reference_dbfs: Reference amplitude in dBFS
        measured_dbfs: Measured amplitude in dBFS
        max_error_db: Maximum acceptable error

    Returns:
        Tuple of (passed, error_db)
    """
    error_db = measured_dbfs - reference_dbfs
    passed = abs(error_db) <= max_error_db
    return passed, float(error_db)


def run_reference_tone_test(
    config: ReferenceToneConfig,
    play_and_record_fn=None,
) -> ReferenceToneResult:
    """
    Run reference tone calibration test.

    This function generates a reference tone, plays it through the output,
    captures through the input, and verifies amplitude accuracy.

    Args:
        config: Test configuration
        play_and_record_fn: Function that takes (signal, sample_rate) and returns
                           captured audio. If None, returns simulated result.

    Returns:
        ReferenceToneResult with test results
    """
    # Generate reference tone
    reference = generate_reference_tone(config)

    if play_and_record_fn is None:
        # Simulation mode
        return _simulate_reference_tone_result(config)

    try:
        # Play and record
        captured = play_and_record_fn(reference, config.sample_rate)

        if captured is None or len(captured) == 0:
            return ReferenceToneResult(success=False, error_message="No audio captured")

        # Trim to analysis region (skip fade in/out)
        trim_samples = int(0.1 * config.sample_rate)  # 100ms
        if len(captured) > 2 * trim_samples:
            captured = captured[trim_samples:-trim_samples]

        # Measure amplitude
        measured_dbfs = measure_amplitude_dbfs(captured)
        amplitude_passed, amplitude_error = verify_amplitude(
            config.amplitude_dbfs, measured_dbfs, config.max_amplitude_error_db
        )

        # Find actual frequency
        measured_freq = find_fundamental_frequency(
            captured, config.sample_rate, config.frequency_hz
        )
        frequency_error = measured_freq - config.frequency_hz

        # Measure THD
        thd_db, thd_percent = measure_thd(captured, config.sample_rate, measured_freq)

        # Estimate noise floor
        noise_floor = estimate_noise_floor(captured, config.sample_rate, measured_freq)

        # Calculate SNR
        snr_db = measured_dbfs - noise_floor

        # Check if THD is acceptable
        thd_passed = thd_db <= config.min_thd_db

        # Overall success
        success = amplitude_passed and thd_passed

        error_messages = []
        if not amplitude_passed:
            error_messages.append(
                f"Amplitude error {amplitude_error:.2f}dB exceeds {config.max_amplitude_error_db}dB"
            )
        if not thd_passed:
            error_messages.append(
                f"THD {thd_db:.1f}dB exceeds {config.min_thd_db}dB threshold"
            )

        return ReferenceToneResult(
            success=success,
            error_message="; ".join(error_messages),
            reference_amplitude_dbfs=config.amplitude_dbfs,
            measured_amplitude_dbfs=measured_dbfs,
            amplitude_error_db=amplitude_error,
            measured_frequency_hz=measured_freq,
            frequency_error_hz=frequency_error,
            thd_db=thd_db,
            thd_percent=thd_percent,
            noise_floor_dbfs=noise_floor,
            snr_db=snr_db,
        )

    except Exception as e:
        return ReferenceToneResult(success=False, error_message=str(e))


def _simulate_reference_tone_result(config: ReferenceToneConfig) -> ReferenceToneResult:
    """Generate simulated reference tone result for testing without hardware."""
    # Simulate typical USB audio characteristics
    # Small amplitude error (typical gain mismatch)
    amplitude_error = np.random.uniform(-0.3, 0.3)
    measured_dbfs = config.amplitude_dbfs + amplitude_error

    # Small frequency error (clock drift)
    frequency_error = np.random.uniform(-0.5, 0.5)
    measured_freq = config.frequency_hz + frequency_error

    # Typical THD for decent audio interface
    thd_db = np.random.uniform(-55, -45)
    thd_percent = 10 ** (thd_db / 20.0) * 100

    # Typical noise floor
    noise_floor = np.random.uniform(-92, -88)
    snr_db = measured_dbfs - noise_floor

    return ReferenceToneResult(
        success=True,
        reference_amplitude_dbfs=config.amplitude_dbfs,
        measured_amplitude_dbfs=float(measured_dbfs),
        amplitude_error_db=float(amplitude_error),
        measured_frequency_hz=float(measured_freq),
        frequency_error_hz=float(frequency_error),
        thd_db=float(thd_db),
        thd_percent=float(thd_percent),
        noise_floor_dbfs=float(noise_floor),
        snr_db=float(snr_db),
    )

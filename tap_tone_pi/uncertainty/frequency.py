# INSTRUMENT CLASS: MEASUREMENT
"""
Frequency measurement uncertainty calculations.
"""

from __future__ import annotations

import math
from typing import Optional

from .budget import (
    UncertaintyBudget,
    UncertaintyType,
    get_snr_uncertainty_factor,
    UNCERTAINTY_FACTORS,
)


def compute_frequency_resolution(sample_rate: int, fft_size: int) -> float:
    """
    Compute FFT frequency resolution (bin width).

    Args:
        sample_rate: Sample rate in Hz
        fft_size: FFT window size

    Returns:
        Frequency resolution in Hz
    """
    return sample_rate / fft_size


def compute_frequency_uncertainty(
    freq_hz: float,
    sample_rate: int = 48000,
    fft_size: int = 8192,
    snr_db: float = 40.0,
    is_calibrated: bool = False,
    uses_parabolic_interpolation: bool = True,
    duration_s: Optional[float] = None,
) -> UncertaintyBudget:
    """
    Compute uncertainty budget for frequency measurement.

    Main uncertainty sources:
    1. FFT frequency resolution (bin width)
    2. Peak interpolation accuracy
    3. Signal quality (SNR-dependent)
    4. Spectral leakage (windowing effects)

    Args:
        freq_hz: Measured frequency in Hz
        sample_rate: Sample rate in Hz
        fft_size: FFT window size
        snr_db: Signal-to-noise ratio in dB
        is_calibrated: Whether system is calibrated
        uses_parabolic_interpolation: Whether parabolic peak interpolation is used
        duration_s: Signal duration (affects frequency resolution)

    Returns:
        UncertaintyBudget for the frequency measurement
    """
    budget = UncertaintyBudget(
        measurement_value=freq_hz,
        measurement_unit="Hz",
    )

    # 1. FFT bin width (fundamental resolution limit)
    bin_width = compute_frequency_resolution(sample_rate, fft_size)

    # With parabolic interpolation, uncertainty is fraction of bin width
    if uses_parabolic_interpolation:
        interp_factor = UNCERTAINTY_FACTORS["peak_interpolation"]
    else:
        interp_factor = 0.5  # Without interpolation, ±0.5 bins

    resolution_uncertainty = bin_width * interp_factor

    budget.add_component(
        name="FFT resolution",
        value=resolution_uncertainty,
        unit="Hz",
        uncertainty_type=UncertaintyType.TYPE_B,
        description=f"FFT bin width {bin_width:.2f} Hz × {interp_factor}",
    )

    # 2. SNR-dependent uncertainty
    # Higher SNR → cleaner peaks → lower uncertainty
    snr_factor = get_snr_uncertainty_factor(snr_db)
    # Convert dB uncertainty to Hz (approximate via relative error)
    snr_relative = 10 ** (snr_factor / 20) - 1
    snr_uncertainty = freq_hz * snr_relative * 0.1  # Scale down

    budget.add_component(
        name="Signal quality (SNR)",
        value=snr_uncertainty,
        unit="Hz",
        uncertainty_type=UncertaintyType.TYPE_A,
        description=f"Based on SNR = {snr_db:.1f} dB",
    )

    # 3. Spectral leakage (windowing effects)
    # Hann window has ±1.5 bin width main lobe
    leakage_uncertainty = bin_width * 0.1  # Small contribution with Hann

    budget.add_component(
        name="Spectral leakage",
        value=leakage_uncertainty,
        unit="Hz",
        uncertainty_type=UncertaintyType.TYPE_B,
        description="Windowing effects (Hann window assumed)",
    )

    # 4. Duration-dependent (if signal is short)
    if duration_s is not None and duration_s < 1.0:
        # Heisenberg uncertainty: Δf × Δt ≥ 1/(4π)
        # For practical measurements, use empirical factor
        duration_uncertainty = 1.0 / duration_s * 0.2

        budget.add_component(
            name="Duration limit",
            value=duration_uncertainty,
            unit="Hz",
            uncertainty_type=UncertaintyType.TYPE_B,
            description=f"Short duration ({duration_s:.2f}s) increases uncertainty",
        )

    return budget


def compute_frequency_uncertainty_simple(
    freq_hz: float,
    snr_db: float = 40.0,
    sample_rate: int = 48000,
    fft_size: int = 8192,
) -> float:
    """
    Compute simple expanded frequency uncertainty (±Hz).

    This is a convenience function that returns a single number
    rather than a full uncertainty budget.

    Args:
        freq_hz: Measured frequency in Hz
        snr_db: Signal-to-noise ratio in dB
        sample_rate: Sample rate in Hz
        fft_size: FFT window size

    Returns:
        Expanded uncertainty in Hz (k=2, ~95%)
    """
    budget = compute_frequency_uncertainty(
        freq_hz=freq_hz,
        sample_rate=sample_rate,
        fft_size=fft_size,
        snr_db=snr_db,
    )
    return budget.expanded_uncertainty


def estimate_frequency_repeatability(
    measurements: list[float],
) -> float:
    """
    Estimate frequency repeatability from repeated measurements (Type A).

    Args:
        measurements: List of frequency measurements in Hz

    Returns:
        Standard deviation of the mean (standard uncertainty)
    """
    if len(measurements) < 2:
        return float("inf")

    n = len(measurements)
    mean = sum(measurements) / n
    variance = sum((x - mean) ** 2 for x in measurements) / (n - 1)
    std_dev = math.sqrt(variance)

    # Standard uncertainty of the mean
    return std_dev / math.sqrt(n)

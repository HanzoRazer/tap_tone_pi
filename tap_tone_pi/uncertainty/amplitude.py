# INSTRUMENT CLASS: MEASUREMENT
"""
Amplitude measurement uncertainty calculations.
"""

from __future__ import annotations

import math
from typing import Optional

from .budget import (
    UncertaintyBudget,
    UncertaintyType,
    get_calibration_uncertainty_factor,
)


def compute_snr_uncertainty(snr_db: float) -> float:
    """
    Compute amplitude uncertainty component from SNR.

    Lower SNR means more noise contamination of the signal,
    leading to higher amplitude uncertainty.

    Args:
        snr_db: Signal-to-noise ratio in dB

    Returns:
        Standard uncertainty in dB
    """
    # Theoretical relationship: amplitude uncertainty ≈ 1/SNR (linear)
    # In dB: uncertainty ≈ 20*log10(1 + 1/10^(SNR/20))
    snr_linear = 10 ** (snr_db / 20)
    uncertainty_linear = 1 / snr_linear
    uncertainty_db = 20 * math.log10(1 + uncertainty_linear)

    return uncertainty_db


def compute_amplitude_uncertainty(
    magnitude_db: float,
    snr_db: float = 40.0,
    is_calibrated: bool = False,
    coherence: Optional[float] = None,
    averaging_count: int = 1,
) -> UncertaintyBudget:
    """
    Compute uncertainty budget for amplitude measurement.

    Main uncertainty sources:
    1. Calibration state (calibrated vs uncalibrated)
    2. Signal quality (SNR)
    3. Coherence (for two-channel measurements)
    4. Averaging (reduces random uncertainty)
    5. Quantization (ADC resolution)

    Args:
        magnitude_db: Measured magnitude in dB
        snr_db: Signal-to-noise ratio in dB
        is_calibrated: Whether system is calibrated
        coherence: Coherence value 0-1 (for two-channel, None if single-channel)
        averaging_count: Number of averages in measurement

    Returns:
        UncertaintyBudget for the amplitude measurement
    """
    budget = UncertaintyBudget(
        measurement_value=magnitude_db,
        measurement_unit="dB",
    )

    # 1. Calibration uncertainty
    cal_uncertainty = get_calibration_uncertainty_factor(is_calibrated)
    budget.add_component(
        name="Calibration",
        value=cal_uncertainty,
        unit="dB",
        uncertainty_type=UncertaintyType.TYPE_B,
        description="Calibrated" if is_calibrated else "Uncalibrated system",
    )

    # 2. SNR-dependent uncertainty
    snr_uncertainty = compute_snr_uncertainty(snr_db)
    budget.add_component(
        name="Signal quality (SNR)",
        value=snr_uncertainty,
        unit="dB",
        uncertainty_type=UncertaintyType.TYPE_A,
        description=f"SNR = {snr_db:.1f} dB",
    )

    # 3. Coherence-based uncertainty (two-channel measurements)
    if coherence is not None:
        # Lower coherence = higher uncertainty
        # Uncertainty scales inversely with coherence
        if coherence > 0.1:
            coherence_uncertainty = 10 * math.log10(1 / coherence)
        else:
            coherence_uncertainty = 10.0  # Very low coherence

        budget.add_component(
            name="Coherence",
            value=coherence_uncertainty,
            unit="dB",
            uncertainty_type=UncertaintyType.TYPE_A,
            description=f"Coherence = {coherence:.2f}",
        )

    # 4. Averaging reduction
    if averaging_count > 1:
        # Random uncertainty reduces by sqrt(N)
        averaging_factor = math.sqrt(averaging_count)
        averaging_reduction = 20 * math.log10(averaging_factor)

        # This is a reduction, so we note it but don't add as component
        # Instead, we could scale other Type A components
        budget.add_component(
            name="Averaging benefit",
            value=-averaging_reduction / 10,  # Small net benefit
            unit="dB",
            uncertainty_type=UncertaintyType.TYPE_A,
            description=f"{averaging_count} averages (√N improvement)",
            sensitivity_coefficient=0.5,  # Partial benefit
        )

    # 5. ADC quantization (typically 24-bit audio = negligible)
    # 24-bit → ~144 dB dynamic range, quantization error << 0.01 dB
    quantization_uncertainty = 0.01
    budget.add_component(
        name="Quantization",
        value=quantization_uncertainty,
        unit="dB",
        uncertainty_type=UncertaintyType.TYPE_B,
        description="24-bit ADC quantization",
    )

    return budget


def compute_amplitude_uncertainty_simple(
    snr_db: float = 40.0,
    is_calibrated: bool = False,
) -> float:
    """
    Compute simple expanded amplitude uncertainty (±dB).

    This is a convenience function that returns a single number.

    Args:
        snr_db: Signal-to-noise ratio in dB
        is_calibrated: Whether system is calibrated

    Returns:
        Expanded uncertainty in dB (k=2, ~95%)
    """
    budget = compute_amplitude_uncertainty(
        magnitude_db=0,  # Doesn't affect uncertainty
        snr_db=snr_db,
        is_calibrated=is_calibrated,
    )
    return budget.expanded_uncertainty


def estimate_amplitude_repeatability(
    measurements_db: list[float],
) -> float:
    """
    Estimate amplitude repeatability from repeated measurements (Type A).

    Args:
        measurements_db: List of amplitude measurements in dB

    Returns:
        Standard deviation of the mean (standard uncertainty)
    """
    if len(measurements_db) < 2:
        return float("inf")

    n = len(measurements_db)
    mean = sum(measurements_db) / n
    variance = sum((x - mean) ** 2 for x in measurements_db) / (n - 1)
    std_dev = math.sqrt(variance)

    return std_dev / math.sqrt(n)


def rms_to_dbfs(rms: float) -> float:
    """Convert RMS amplitude to dBFS."""
    return 20 * math.log10(rms + 1e-10)


def dbfs_to_rms(dbfs: float) -> float:
    """Convert dBFS to RMS amplitude."""
    return 10 ** (dbfs / 20)

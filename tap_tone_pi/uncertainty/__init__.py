"""
tap_tone_pi.uncertainty — Measurement uncertainty quantification.

Phase 3 P0: Provides uncertainty estimates for all measurements.

This module computes and reports measurement uncertainty based on:
- Device calibration state (calibrated vs uncalibrated)
- Signal quality metrics (SNR, coherence)
- Methodology factors (tap tone vs deflection)
- Environmental factors (when available)

Key exports:
- UncertaintyBudget: Structured uncertainty breakdown
- compute_frequency_uncertainty: Hz uncertainty for frequency measurements
- compute_amplitude_uncertainty: dB uncertainty for magnitude measurements
- compute_stiffness_uncertainty: GPa uncertainty for MOE calculations
- format_with_uncertainty: String formatting helpers

Usage:
    from tap_tone_pi.uncertainty import (
        compute_frequency_uncertainty,
        format_with_uncertainty,
    )

    freq_hz = 440.0
    uncertainty = compute_frequency_uncertainty(
        freq_hz=freq_hz,
        snr_db=45.0,
        is_calibrated=True,
    )

    print(format_with_uncertainty(freq_hz, uncertainty, "Hz"))
    # Output: "440.0 ± 1.2 Hz"
"""

from .budget import (
    UncertaintyBudget,
    UncertaintyComponent,
    combine_uncertainties,
    expand_uncertainty,
)
from .frequency import (
    compute_frequency_uncertainty,
    compute_frequency_resolution,
)
from .amplitude import (
    compute_amplitude_uncertainty,
    compute_snr_uncertainty,
)
from .stiffness import (
    compute_stiffness_uncertainty,
    compute_deflection_moe_uncertainty,
    compute_tap_tone_moe_uncertainty,
)
from .formatters import (
    format_with_uncertainty,
    format_uncertainty_budget,
    uncertainty_to_dict,
)

__all__ = [
    # Budget
    "UncertaintyBudget",
    "UncertaintyComponent",
    "combine_uncertainties",
    "expand_uncertainty",
    # Frequency
    "compute_frequency_uncertainty",
    "compute_frequency_resolution",
    # Amplitude
    "compute_amplitude_uncertainty",
    "compute_snr_uncertainty",
    # Stiffness
    "compute_stiffness_uncertainty",
    "compute_deflection_moe_uncertainty",
    "compute_tap_tone_moe_uncertainty",
    # Formatters
    "format_with_uncertainty",
    "format_uncertainty_budget",
    "uncertainty_to_dict",
]

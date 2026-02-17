"""
Transfer function estimation module.

This module provides production-grade transfer function (frequency response)
estimation with multiple estimators and quality metrics.

Estimators:
- H1: Gxy/Gxx - minimizes noise in output, standard choice
- H2: Gyy/Gyx - minimizes noise in input
- Hv: sqrt(H1×H2) - geometric mean, unbiased when SNR known

Quality Metrics:
- Coherence γ²: measure of linear relationship between input and output
- SNR estimation from coherence: SNR = γ²/(1-γ²)
- Uncertainty bounds from coherence and averaging

Mathematical Background:
------------------------
For input x(t) and output y(t) related by transfer function H(f):

    Y(f) = H(f) × X(f) + N(f)

where N(f) is uncorrelated noise.

The cross-spectral density:
    Gxy = E[X*(f) × Y(f)]

The auto-spectral densities:
    Gxx = E[X*(f) × X(f)]
    Gyy = E[Y*(f) × Y(f)]

Coherence:
    γ²(f) = |Gxy(f)|² / (Gxx(f) × Gyy(f))

γ² = 1.0 means perfect linear relationship (no noise).
γ² = 0.0 means no linear relationship.
"""

from .estimators import (
    TransferFunctionResult,
    CoherenceResult,
    estimate_h1,
    estimate_h2,
    estimate_hv,
    estimate_transfer_function,
    compute_coherence,
    compute_cross_spectrum,
    compute_auto_spectrum,
)

from .welch import (
    welch_spectrum,
    welch_cross_spectrum,
    welch_transfer_function,
)

from .quality import (
    estimate_snr_from_coherence,
    uncertainty_from_coherence,
    required_averages_for_error,
    validate_measurement_quality,
)

__all__ = [
    # Core classes
    "TransferFunctionResult",
    "CoherenceResult",
    # Estimators
    "estimate_h1",
    "estimate_h2",
    "estimate_hv",
    "estimate_transfer_function",
    # Spectral calculations
    "compute_coherence",
    "compute_cross_spectrum",
    "compute_auto_spectrum",
    # Welch method
    "welch_spectrum",
    "welch_cross_spectrum",
    "welch_transfer_function",
    # Quality metrics
    "estimate_snr_from_coherence",
    "uncertainty_from_coherence",
    "required_averages_for_error",
    "validate_measurement_quality",
]

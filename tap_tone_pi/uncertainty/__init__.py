"""
tap_tone_pi.uncertainty — ISO GUM-compliant uncertainty quantification.

Phase 3 P0: Provides uncertainty estimates for all measurements.

This module implements uncertainty analysis following:
- ISO/IEC Guide 98-3:2008 (GUM)
- ISO/IEC Guide 98-3:2008/Suppl 1:2008 (Monte Carlo methods)

Key Capabilities:
- Type A evaluation (statistical analysis of repeated observations)
- Type B evaluation (specifications, calibration certificates, prior knowledge)
- Combined standard uncertainty with sensitivity coefficients
- Welch-Satterthwaite effective degrees of freedom
- Coverage factor from t-distribution
- Monte Carlo uncertainty propagation
- Correlation handling

Key exports:
- UncertaintyBudget: Structured uncertainty breakdown
- compute_frequency_uncertainty: Hz uncertainty for frequency measurements
- compute_amplitude_uncertainty: dB uncertainty for magnitude measurements
- compute_stiffness_uncertainty: GPa uncertainty for MOE calculations
- format_with_uncertainty: String formatting helpers
- create_type_a_source: Create Type A from observations
- create_type_b_rectangular: Create Type B with rectangular distribution
- create_type_b_normal: Create Type B with normal distribution
- propagate_uncertainty: GUM law of propagation
- monte_carlo_uncertainty: GUM Supplement 1 method

Usage:
    from tap_tone_pi.uncertainty import (
        compute_frequency_uncertainty,
        format_with_uncertainty,
        create_type_a_source,
        create_type_b_rectangular,
        combine_with_gum,
    )

    # Type A from repeated measurements
    readings = np.array([440.1, 439.9, 440.0, 440.2, 439.8])
    u_repeat = create_type_a_source("repeatability", readings, "Hz")

    # Type B from resolution (±0.5 Hz uniform)
    u_res = create_type_b_rectangular("resolution", 0.5, "Hz")

    # Combine per GUM
    result = combine_with_gum([u_repeat, u_res], confidence_level=0.95)
    print(f"U = {result.expanded_uncertainty:.2f} Hz (k={result.coverage_factor:.2f})")
"""

from .budget import (
    UncertaintyBudget,
    UncertaintyComponent,
    UncertaintyType,
    DistributionType,
    CombinedUncertainty,
    combine_uncertainties,
    combine_with_gum,
    expand_uncertainty,
    welch_satterthwaite_dof,
    coverage_factor,
    create_type_a_source,
    create_type_b_rectangular,
    create_type_b_normal,
    create_type_b_triangular,
    create_type_b_uform,
)

from .propagation import (
    PropagationResult,
    MonteCarloResult,
    propagate_uncertainty,
    monte_carlo_uncertainty,
    sensitivity_coefficients,
    correlation_matrix,
    validate_gum_assumptions,
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
    # Budget - core classes
    "UncertaintyBudget",
    "UncertaintyComponent",
    "UncertaintyType",
    "DistributionType",
    "CombinedUncertainty",
    # Budget - combination functions
    "combine_uncertainties",
    "combine_with_gum",
    "expand_uncertainty",
    "welch_satterthwaite_dof",
    "coverage_factor",
    # Budget - Type A/B constructors
    "create_type_a_source",
    "create_type_b_rectangular",
    "create_type_b_normal",
    "create_type_b_triangular",
    "create_type_b_uform",
    # Propagation
    "PropagationResult",
    "MonteCarloResult",
    "propagate_uncertainty",
    "monte_carlo_uncertainty",
    "sensitivity_coefficients",
    "correlation_matrix",
    "validate_gum_assumptions",
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

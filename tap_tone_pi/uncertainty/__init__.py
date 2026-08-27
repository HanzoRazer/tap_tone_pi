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

# ---------------------------------------------------------------------------
# Lazy re-export (PEP 562)
# ---------------------------------------------------------------------------
#
# These names were eagerly imported here. That made ``import
# tap_tone_pi.uncertainty`` — and therefore *any* import beneath it, including
# the stdlib-only acquisition package — pull in NumPy through ``budget`` and
# ``propagation``.
#
# DO-107A requires the instrument-side acquisition core to load without NumPy
# transitively, and a subpackage cannot escape its parent's ``__init__``. So the
# heavy modules are resolved on first attribute access instead of at import.
#
# The public API is unchanged: every name in ``__all__`` still resolves through
# ``from tap_tone_pi.uncertainty import X``, ``import tap_tone_pi.uncertainty``
# followed by attribute access, and ``import *``. Only the *timing* of the
# underlying module import moves.

from typing import TYPE_CHECKING, Any

_LAZY_EXPORTS: dict[str, str] = {
    # Budget - core classes
    "UncertaintyBudget": "budget",
    "UncertaintyComponent": "budget",
    "UncertaintyType": "budget",
    "DistributionType": "budget",
    "CombinedUncertainty": "budget",
    # Budget - combination functions
    "combine_uncertainties": "budget",
    "combine_with_gum": "budget",
    "expand_uncertainty": "budget",
    "welch_satterthwaite_dof": "budget",
    "coverage_factor": "budget",
    # Budget - Type A/B constructors
    "create_type_a_source": "budget",
    "create_type_b_rectangular": "budget",
    "create_type_b_normal": "budget",
    "create_type_b_triangular": "budget",
    "create_type_b_uform": "budget",
    # Propagation
    "PropagationResult": "propagation",
    "MonteCarloResult": "propagation",
    "propagate_uncertainty": "propagation",
    "monte_carlo_uncertainty": "propagation",
    "sensitivity_coefficients": "propagation",
    "correlation_matrix": "propagation",
    "validate_gum_assumptions": "propagation",
    # Frequency
    "compute_frequency_uncertainty": "frequency",
    "compute_frequency_resolution": "frequency",
    # Amplitude
    "compute_amplitude_uncertainty": "amplitude",
    "compute_snr_uncertainty": "amplitude",
    # Stiffness
    "compute_stiffness_uncertainty": "stiffness",
    "compute_deflection_moe_uncertainty": "stiffness",
    "compute_tap_tone_moe_uncertainty": "stiffness",
    # Formatters
    "format_with_uncertainty": "formatters",
    "format_uncertainty_budget": "formatters",
    "uncertainty_to_dict": "formatters",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value  # resolve once, then it is a plain global
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


if TYPE_CHECKING:  # pragma: no cover - import-time cost is the whole point
    from .amplitude import compute_amplitude_uncertainty, compute_snr_uncertainty
    from .budget import (
        CombinedUncertainty,
        DistributionType,
        UncertaintyBudget,
        UncertaintyComponent,
        UncertaintyType,
        combine_uncertainties,
        combine_with_gum,
        coverage_factor,
        create_type_a_source,
        create_type_b_normal,
        create_type_b_rectangular,
        create_type_b_triangular,
        create_type_b_uform,
        expand_uncertainty,
        welch_satterthwaite_dof,
    )
    from .formatters import (
        format_uncertainty_budget,
        format_with_uncertainty,
        uncertainty_to_dict,
    )
    from .frequency import (
        compute_frequency_resolution,
        compute_frequency_uncertainty,
    )
    from .propagation import (
        MonteCarloResult,
        PropagationResult,
        correlation_matrix,
        monte_carlo_uncertainty,
        propagate_uncertainty,
        sensitivity_coefficients,
        validate_gum_assumptions,
    )
    from .stiffness import (
        compute_deflection_moe_uncertainty,
        compute_stiffness_uncertainty,
        compute_tap_tone_moe_uncertainty,
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

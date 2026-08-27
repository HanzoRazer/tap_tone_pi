# INSTRUMENT CLASS: MEASUREMENT
"""Acquisition Budget Authority (DO-107A).

Answers, for one measurement configuration: what limits this measurement, what
uncertainty follows from those limits, and how large a physical difference must
exist before the Analyzer can distinguish it.

**Standard library only, transitively.** Everything importable from this package
must load on the instrument without NumPy. That rules out importing
:mod:`tap_tone_pi.uncertainty.budget` or :mod:`~tap_tone_pi.uncertainty.frequency`
from here, both of which reach NumPy — adaptation to those canonical authorities
happens at an integration boundary outside this package.

See ``docs/ACQUISITION_BUDGET_AUTHORITY.md`` for the ownership boundaries,
including which calculations delegate rather than being reimplemented here.
"""

from __future__ import annotations

from .quantities import (
    AcquisitionQuantityError,
    FormulaStatus,
    Provenance,
    Quantity,
    ResultAvailability,
    as_quantity,
)
from .frequency_budget import (
    AggregateContributor,
    FrequencyBudget,
    clock_scale_error_hz,
    estimator_floor_candidate_hz,
    frequency_budget,
)
from .modulus import (
    ModulusBudget,
    ModulusUnavailable,
    UnavailableSection,
    modulus_budget,
    modulus_budget_or_unavailable,
)
from .noise import (
    NoiseBudget,
    clock_topology_note,
    combine_snr_db,
    front_end_output_noise_vrms,
    front_end_snr_db,
    jitter_budget_s,
    jitter_snr_db,
    noise_budget,
    quantization_snr_db,
    rss,
)
from .sweep import SweepLimits, compute_sweep_limits
from .specs import (
    CLOCK_TOPOLOGIES,
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    FrontEndSpec,
    SpecimenSpec,
    SweepSpec,
    spec_quantities,
)

__all__ = [
    "AcquisitionQuantityError",
    "Provenance",
    "Quantity",
    "ResultAvailability",
    "FormulaStatus",
    "as_quantity",
    "CLOCK_TOPOLOGIES",
    "CaptureSpec",
    "ClockSpec",
    "ConverterSpec",
    "FrontEndSpec",
    "SpecimenSpec",
    "SweepSpec",
    "spec_quantities",
    # noise
    "NoiseBudget",
    "noise_budget",
    "jitter_snr_db",
    "jitter_budget_s",
    "quantization_snr_db",
    "combine_snr_db",
    "rss",
    "front_end_output_noise_vrms",
    "front_end_snr_db",
    "clock_topology_note",
    # frequency
    "FrequencyBudget",
    "frequency_budget",
    "clock_scale_error_hz",
    "estimator_floor_candidate_hz",
    # sweep
    "SweepLimits",
    "compute_sweep_limits",
    # modulus (delegating adapter)
    "AggregateContributor",
    "ModulusBudget",
    "ModulusUnavailable",
    "UnavailableSection",
    "modulus_budget",
    "modulus_budget_or_unavailable",
]

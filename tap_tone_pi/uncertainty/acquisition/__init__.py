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
from .budget import (
    ACQUISITION_BUDGET_SCHEMA_VERSION,
    AcquisitionBudgetV1,
    EvidenceAssessment,
    EvidenceCondition,
    EvidenceReason,
)
from .contract import SCHEMA_FILE, SCHEMA_VERSION, validate_acquisition_budget
from .e0_adapter import (
    E0_MAPPINGS,
    E0_UNMAPPED_GROUPS,
    E0Adaptation,
    E0AdapterError,
    E0InformedBudget,
    E0Mapping,
    E0MappingOutcome,
    E0MappingStatus,
    E0OperatingPoint,
    E0UnmappedGroup,
    adapt_e0_characterization,
    build_acquisition_budget_from_e0,
    compare_budget_inputs,
    e0_informed_converter,
    e0_source_locator,
    parse_e0_source_locator,
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
from .self_test import (
    DEFAULT_MARGIN_DB,
    SelfTestThresholdPolicy,
    SelfTestThresholds,
    self_test_thresholds,
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
    # self-test
    "DEFAULT_MARGIN_DB",
    "SelfTestThresholdPolicy",
    "SelfTestThresholds",
    "self_test_thresholds",
    # composition
    "ACQUISITION_BUDGET_SCHEMA_VERSION",
    "AcquisitionBudgetV1",
    "EvidenceAssessment",
    "EvidenceCondition",
    "EvidenceReason",
    # contract
    "SCHEMA_VERSION",
    "SCHEMA_FILE",
    "validate_acquisition_budget",
    # E0 integration (DO-107B)
    "E0_MAPPINGS",
    "E0_UNMAPPED_GROUPS",
    "E0Adaptation",
    "E0AdapterError",
    "E0InformedBudget",
    "E0Mapping",
    "E0MappingOutcome",
    "E0MappingStatus",
    "E0OperatingPoint",
    "E0UnmappedGroup",
    "adapt_e0_characterization",
    "build_acquisition_budget_from_e0",
    "compare_budget_inputs",
    "e0_informed_converter",
    "e0_source_locator",
    "parse_e0_source_locator",
]

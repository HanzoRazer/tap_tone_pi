"""Empirical model framework — metadata around scientific equations (DO-101A).

Generalizes the empirical capabilities proven in ``tap_tone_pi.luthiery`` into
a domain-agnostic home. Mathematical implementations, measurements, laboratory
workflows, and advisory logic remain outside this package.

Public surface is deliberately narrow. ``__all__`` is the supported vocabulary
plus the behaviour modules ``validation``, ``serialization``,
``formula_validation``, ``luthiery_compat``, and ``util``.
"""

from __future__ import annotations

from tap_tone_pi.empirical import (
    formula_validation,
    luthiery_compat,
    serialization,
    util,
    validation,
)
from tap_tone_pi.empirical.contracts import (
    EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION,
    FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION,
    CalibrationRecord,
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    FormulaValidationEnvelopeV1,
    MeasurementLink,
    ModelInputDefinition,
    ModelOutputDefinition,
    UncertaintyReference,
    ValidityDomain,
)
from tap_tone_pi.empirical.errors import (
    EmpiricalErrorCode,
    EmpiricalModelError,
    RegistryError,
    ValidationError,
    raise_for_findings,
)

__all__ = [
    # Behaviour modules
    "formula_validation",
    "luthiery_compat",
    "serialization",
    "util",
    "validation",
    # Vocabulary — contracts
    "EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION",
    "FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION",
    "CalibrationRecord",
    "EmpiricalModelDefinitionV1",
    "EvidenceReference",
    "FormulaValidationEnvelopeV1",
    "MeasurementLink",
    "ModelInputDefinition",
    "ModelOutputDefinition",
    "UncertaintyReference",
    "ValidityDomain",
    # Vocabulary — errors
    "EmpiricalErrorCode",
    "EmpiricalModelError",
    "RegistryError",
    "ValidationError",
    "raise_for_findings",
]

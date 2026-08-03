# INSTRUMENT CLASS: MEASUREMENT
"""Small pure helpers for constructing empirical model records (DO-101A).

No mathematical helpers. No registry builders (those belong to DO-101B).

Dataclass constructors are dumb containers. Prefer :func:`build_model` /
:func:`clone_model` (with ``validate=True``) when you need a validated record.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from tap_tone_pi.empirical.contracts import (
    CalibrationRecord,
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    MeasurementLink,
    ModelInputDefinition,
    ModelOutputDefinition,
    UncertaintyReference,
    ValidityDomain,
)
from tap_tone_pi.empirical.validation import validate_model


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_reference(ref: EvidenceReference) -> EvidenceReference:
    """Return a copy with stripped identifiers; blank optionals become None."""
    return EvidenceReference(
        reference_id=ref.reference_id.strip(),
        kind=ref.kind.strip(),
        citation=_empty_to_none(ref.citation),
        uri=_empty_to_none(ref.uri),
        formula_id=_empty_to_none(ref.formula_id),
        regression_evidence_id=_empty_to_none(ref.regression_evidence_id),
        notes=_empty_to_none(ref.notes),
    )


def normalize_uncertainty(
    uncertainty: UncertaintyReference | None,
) -> UncertaintyReference | None:
    """Strip whitespace; collapse an all-empty reference to None."""
    if uncertainty is None:
        return None
    cleaned = UncertaintyReference(
        uncertainty_model_id=_empty_to_none(uncertainty.uncertainty_model_id),
        uncertainty_record_id=_empty_to_none(uncertainty.uncertainty_record_id),
        uncertainty_summary=_empty_to_none(uncertainty.uncertainty_summary),
    )
    if (
        cleaned.uncertainty_model_id is None
        and cleaned.uncertainty_record_id is None
        and cleaned.uncertainty_summary is None
    ):
        return None
    return cleaned


def build_model(
    *,
    model_id: str,
    version: int,
    title: str,
    description: str = "",
    assumptions: Sequence[str] = (),
    inputs: Sequence[ModelInputDefinition] = (),
    outputs: Sequence[ModelOutputDefinition] = (),
    validity_domain: ValidityDomain | None = None,
    measurement_links: Sequence[MeasurementLink] = (),
    evidence_references: Sequence[EvidenceReference] = (),
    calibration_history: Sequence[CalibrationRecord] = (),
    uncertainty: UncertaintyReference | None = None,
    equation_module: str | None = None,
    equation_symbol: str | None = None,
    domain: str | None = None,
    notes: str | None = None,
    validate: bool = True,
) -> EmpiricalModelDefinitionV1:
    """Construct an empirical model, optionally validating immediately."""
    model = EmpiricalModelDefinitionV1(
        model_id=model_id.strip(),
        version=version,
        title=title.strip(),
        description=description,
        assumptions=tuple(a.strip() for a in assumptions),
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        validity_domain=validity_domain or ValidityDomain(),
        measurement_links=tuple(measurement_links),
        evidence_references=tuple(
            normalize_reference(ref) for ref in evidence_references
        ),
        calibration_history=tuple(calibration_history),
        uncertainty=normalize_uncertainty(uncertainty),
        equation_module=_empty_to_none(equation_module),
        equation_symbol=_empty_to_none(equation_symbol),
        domain=_empty_to_none(domain),
        notes=_empty_to_none(notes),
    )
    if validate:
        validate_model(model, raise_on_error=True)
    return model


def clone_model(
    model: EmpiricalModelDefinitionV1,
    *,
    validate: bool = True,
    **overrides: object,
) -> EmpiricalModelDefinitionV1:
    """Return a copy with selected field overrides.

    Overriding ``model_id`` or ``version`` authors a *new* published identity —
    it does not mutate an already-published ``(model_id, version)`` pair. The
    caller is responsible for treating the result as a new definition.

    By default the clone is re-validated. Pass ``validate=False`` only when
    intentionally constructing an intermediate invalid object.
    """
    cloned = replace(model, **overrides)  # type: ignore[arg-type]
    if validate:
        validate_model(cloned, raise_on_error=True)
    return cloned

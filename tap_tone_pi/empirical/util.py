# INSTRUMENT CLASS: MEASUREMENT
"""Small pure helpers for constructing empirical model records (DO-101A).

No mathematical helpers. No registry builders (those belong to DO-101B).

Dataclass constructors are dumb containers. Prefer :func:`build_model` /
:func:`clone_model` (with ``validate=True``) when you need a validated record.
"""

from __future__ import annotations

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


def normalize_measurement_link(link: MeasurementLink) -> MeasurementLink:
    """Strip identifiers; collapse blank optionals to None."""
    return MeasurementLink(
        link_id=link.link_id.strip(),
        role=link.role.strip(),
        experiment_design_id=_empty_to_none(link.experiment_design_id),
        campaign_id=_empty_to_none(link.campaign_id),
        session_id=_empty_to_none(link.session_id),
        notes=_empty_to_none(link.notes),
    )


def normalize_calibration_record(record: CalibrationRecord) -> CalibrationRecord:
    """Strip identifiers; collapse blank optionals to None."""
    return CalibrationRecord(
        record_id=record.record_id.strip(),
        calibrated_at_utc=_empty_to_none(record.calibrated_at_utc),
        method=_empty_to_none(record.method),
        evidence_reference_id=_empty_to_none(record.evidence_reference_id),
        notes=_empty_to_none(record.notes),
    )


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
        measurement_links=tuple(
            normalize_measurement_link(link) for link in measurement_links
        ),
        evidence_references=tuple(
            normalize_reference(ref) for ref in evidence_references
        ),
        calibration_history=tuple(
            normalize_calibration_record(record) for record in calibration_history
        ),
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
    """Return a normalized copy with selected field overrides.

    Overriding ``model_id`` or ``version`` authors a *new* published identity —
    it does not mutate an already-published ``(model_id, version)`` pair. The
    caller is responsible for treating the result as a new definition.

    Overrides are re-normalized through the same pipeline as
    :func:`build_model` (strip / blank→None / reference normalization), then
    optionally re-validated. Pass ``validate=False`` only when intentionally
    constructing an intermediate invalid object.
    """
    fields: dict[str, object] = {
        "model_id": model.model_id,
        "version": model.version,
        "title": model.title,
        "description": model.description,
        "assumptions": model.assumptions,
        "inputs": model.inputs,
        "outputs": model.outputs,
        "validity_domain": model.validity_domain,
        "measurement_links": model.measurement_links,
        "evidence_references": model.evidence_references,
        "calibration_history": model.calibration_history,
        "uncertainty": model.uncertainty,
        "equation_module": model.equation_module,
        "equation_symbol": model.equation_symbol,
        "domain": model.domain,
        "notes": model.notes,
    }
    fields.update(overrides)
    return build_model(validate=validate, **fields)  # type: ignore[arg-type]

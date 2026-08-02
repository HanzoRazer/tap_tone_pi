# INSTRUMENT CLASS: MEASUREMENT
"""Pure validation for empirical model definitions (DO-101A).

Independent of CLI and registry state. Returns findings; raises only when a
caller asks via :func:`raise_for_findings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tap_tone_pi.empirical.contracts import (
    FORBIDDEN_ADVISORY_TERMS,
    CalibrationRecord,
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    MeasurementLink,
    UncertaintyReference,
    ValidityDomain,
)
from tap_tone_pi.empirical.errors import (
    EmpiricalErrorCode,
    raise_for_findings,
)


@dataclass(frozen=True)
class EmpiricalValidationFindingV1:
    """One structural problem found while validating a model definition."""

    code: EmpiricalErrorCode
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.path:
            d["path"] = self.path
        return d


def _scan_advisory(text: str, *, path: str) -> list[EmpiricalValidationFindingV1]:
    lowered = text.lower()
    findings: list[EmpiricalValidationFindingV1] = []
    for term in sorted(FORBIDDEN_ADVISORY_TERMS):
        # Word-boundary-ish check: reject whole-word matches only.
        padded = f" {lowered} "
        if f" {term} " in padded or lowered == term:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.ADVISORY_LANGUAGE_FORBIDDEN,
                    message=f"advisory term {term!r} is forbidden",
                    path=path,
                )
            )
    return findings


def _validate_range_pair(
    observed: tuple[float, float] | None,
    declared: tuple[float, float] | None,
    *,
    path: str,
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    for label, pair in (("observed_range", observed), ("declared_range", declared)):
        if pair is None:
            continue
        lo, hi = pair
        if lo > hi:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_VALIDITY_DOMAIN,
                    message=f"{label} lower bound exceeds upper bound",
                    path=f"{path}.{label}",
                )
            )
    return findings


def validate_validity_domain(
    domain: ValidityDomain, *, path: str = "validity_domain"
) -> list[EmpiricalValidationFindingV1]:
    findings = _validate_range_pair(
        domain.observed_range, domain.declared_range, path=path
    )
    for i, note in enumerate(domain.notes):
        findings.extend(_scan_advisory(note, path=f"{path}.notes[{i}]"))
    return findings


def validate_uncertainty(
    uncertainty: UncertaintyReference | None, *, path: str = "uncertainty"
) -> list[EmpiricalValidationFindingV1]:
    if uncertainty is None:
        return []
    if (
        uncertainty.uncertainty_model_id is None
        and uncertainty.uncertainty_record_id is None
        and uncertainty.uncertainty_summary is None
    ):
        return [
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.INVALID_UNCERTAINTY_REFERENCE,
                message="uncertainty reference has no identifying fields",
                path=path,
            )
        ]
    findings: list[EmpiricalValidationFindingV1] = []
    if uncertainty.uncertainty_summary:
        findings.extend(
            _scan_advisory(
                uncertainty.uncertainty_summary, path=f"{path}.uncertainty_summary"
            )
        )
    return findings


def validate_measurement_links(
    links: tuple[MeasurementLink, ...], *, path: str = "measurement_links"
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    seen: set[str] = set()
    for i, link in enumerate(links):
        item_path = f"{path}[{i}]"
        if not link.link_id:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_MEASUREMENT_LINK,
                    message="measurement link_id must be non-empty",
                    path=f"{item_path}.link_id",
                )
            )
        elif link.link_id in seen:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_MEASUREMENT_LINK,
                    message=f"duplicate measurement link_id {link.link_id!r}",
                    path=f"{item_path}.link_id",
                )
            )
        else:
            seen.add(link.link_id)
        if not link.role:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_MEASUREMENT_LINK,
                    message="measurement link role must be non-empty",
                    path=f"{item_path}.role",
                )
            )
        if link.notes:
            findings.extend(_scan_advisory(link.notes, path=f"{item_path}.notes"))
    return findings


def validate_evidence_references(
    refs: tuple[EvidenceReference, ...], *, path: str = "evidence_references"
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    seen: set[str] = set()
    for i, ref in enumerate(refs):
        item_path = f"{path}[{i}]"
        if not ref.reference_id:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_EVIDENCE_REFERENCE,
                    message="evidence reference_id must be non-empty",
                    path=f"{item_path}.reference_id",
                )
            )
        elif ref.reference_id in seen:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_EVIDENCE_REFERENCE,
                    message=f"duplicate evidence reference_id {ref.reference_id!r}",
                    path=f"{item_path}.reference_id",
                )
            )
        else:
            seen.add(ref.reference_id)
        if not ref.kind:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_EVIDENCE_REFERENCE,
                    message="evidence kind must be non-empty",
                    path=f"{item_path}.kind",
                )
            )
        for field_name, text in (
            ("citation", ref.citation),
            ("notes", ref.notes),
        ):
            if text:
                findings.extend(
                    _scan_advisory(text, path=f"{item_path}.{field_name}")
                )
    return findings


def validate_calibration_history(
    records: tuple[CalibrationRecord, ...], *, path: str = "calibration_history"
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    seen: set[str] = set()
    for i, record in enumerate(records):
        item_path = f"{path}[{i}]"
        if not record.record_id:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_CALIBRATION_RECORD,
                    message="calibration record_id must be non-empty",
                    path=f"{item_path}.record_id",
                )
            )
        elif record.record_id in seen:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_CALIBRATION_RECORD,
                    message=f"duplicate calibration record_id {record.record_id!r}",
                    path=f"{item_path}.record_id",
                )
            )
        else:
            seen.add(record.record_id)
        if record.notes:
            findings.extend(_scan_advisory(record.notes, path=f"{item_path}.notes"))
    return findings


def validate_inputs(
    model: EmpiricalModelDefinitionV1,
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    if not model.inputs:
        findings.append(
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.MISSING_INPUTS,
                message="model must declare at least one input",
                path="inputs",
            )
        )
    seen: set[str] = set()
    for i, item in enumerate(model.inputs):
        if not item.name:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
                    message="input name must be non-empty",
                    path=f"inputs[{i}].name",
                )
            )
            continue
        if item.name in seen:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.DUPLICATE_INPUT_NAME,
                    message=f"duplicate input name {item.name!r}",
                    path=f"inputs[{i}].name",
                )
            )
        else:
            seen.add(item.name)
        if item.description:
            findings.extend(
                _scan_advisory(item.description, path=f"inputs[{i}].description")
            )
    return findings


def validate_outputs(
    model: EmpiricalModelDefinitionV1,
) -> list[EmpiricalValidationFindingV1]:
    findings: list[EmpiricalValidationFindingV1] = []
    if not model.outputs:
        findings.append(
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.MISSING_OUTPUTS,
                message="model must declare at least one output",
                path="outputs",
            )
        )
    seen: set[str] = set()
    for i, item in enumerate(model.outputs):
        if not item.name:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
                    message="output name must be non-empty",
                    path=f"outputs[{i}].name",
                )
            )
            continue
        if item.name in seen:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.DUPLICATE_OUTPUT_NAME,
                    message=f"duplicate output name {item.name!r}",
                    path=f"outputs[{i}].name",
                )
            )
        else:
            seen.add(item.name)
        if item.description:
            findings.extend(
                _scan_advisory(item.description, path=f"outputs[{i}].description")
            )
    return findings


def validate_model(
    model: EmpiricalModelDefinitionV1, *, raise_on_error: bool = False
) -> list[EmpiricalValidationFindingV1]:
    """Validate a model definition. Pure — no I/O, no registry."""
    findings: list[EmpiricalValidationFindingV1] = []

    if not model.model_id:
        findings.append(
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.INVALID_MODEL_IDENTITY,
                message="model_id must be a non-empty string",
                path="model_id",
            )
        )
    if model.version < 1:
        findings.append(
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.INVALID_VERSION,
                message="version must be an integer >= 1",
                path="version",
            )
        )
    if not model.title:
        findings.append(
            EmpiricalValidationFindingV1(
                code=EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
                message="title must be a non-empty string",
                path="title",
            )
        )

    findings.extend(_scan_advisory(model.title, path="title"))
    findings.extend(_scan_advisory(model.description, path="description"))
    if model.notes:
        findings.extend(_scan_advisory(model.notes, path="notes"))

    for i, assumption in enumerate(model.assumptions):
        if not assumption:
            findings.append(
                EmpiricalValidationFindingV1(
                    code=EmpiricalErrorCode.INVALID_ASSUMPTION,
                    message="assumption entries must be non-empty",
                    path=f"assumptions[{i}]",
                )
            )
        else:
            findings.extend(_scan_advisory(assumption, path=f"assumptions[{i}]"))

    findings.extend(validate_inputs(model))
    findings.extend(validate_outputs(model))
    findings.extend(validate_validity_domain(model.validity_domain))
    findings.extend(validate_measurement_links(model.measurement_links))
    findings.extend(validate_evidence_references(model.evidence_references))
    findings.extend(validate_calibration_history(model.calibration_history))
    findings.extend(validate_uncertainty(model.uncertainty))

    if raise_on_error:
        raise_for_findings(findings)
    return findings

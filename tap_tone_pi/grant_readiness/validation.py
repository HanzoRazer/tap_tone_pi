# INSTRUMENT CLASS: MEASUREMENT
"""Pure validation for grant-readiness evidence (DO-102).

Every function here is pure: it reads records and, where asked, the repository
tree. Nothing in this module touches capture hardware, runs an analysis, or
mutates a measurement result.

Validation returns findings rather than raising, so a caller can report every
problem with an inventory or a study at once instead of only the first. Use
:func:`raise_for_findings` where a single failure should stop the caller.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    CapabilityEvidenceV1,
    CapabilityStatus,
    EvidenceOrigin,
    HardwareVerification,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    ReferenceValidationPlanV1,
    RepeatabilityStudyV1,
    TechnicalRiskV1,
)
from tap_tone_pi.grant_readiness.errors import (
    CapabilityAuditError,
    EvidenceLinkageError,
    ExperimentRecordError,
    GrantReadinessError,
    GrantReadinessErrorCode,
)

# A bounded experiment needs at least two observations before "spread" means
# anything. This is a floor on what can be computed, not a target repeat count:
# DO-102 §4.11 forbids inventing one.
MINIMUM_REPEAT_COUNT = 2

# Patterns that mark a string as an absolute host path rather than a
# repository-relative reference. Evidence records carry the latter only.
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_ABSOLUTE = re.compile(r"^\\\\")


@dataclass(frozen=True)
class ValidationFinding:
    """One problem found in a record. Findings never carry a host path."""

    code: GrantReadinessErrorCode
    message: str
    context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.context:
            payload["context"] = {k: self.context[k] for k in sorted(self.context)}
        return payload


def raise_for_findings(
    findings: Iterable[ValidationFinding],
    *,
    error_cls: type[GrantReadinessError] = GrantReadinessError,
) -> None:
    """Raise for the first finding, carrying the full list in context."""
    ordered = list(findings)
    if not ordered:
        return
    first = ordered[0]
    raise error_cls(
        first.code,
        first.message,
        {"findings": [finding.to_dict() for finding in ordered]},
    )


# ---------------------------------------------------------------------------
# Deterministic evidence helpers
# ---------------------------------------------------------------------------


def evidence_digest(payload: Any) -> str:
    """Return the SHA-256 of a payload's canonical JSON form.

    Canonical means sorted keys, no incidental whitespace, and ``allow_nan``
    off, so the digest depends on the evidence and not on how it was written.
    """
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_run_ids(run_ids: Iterable[str]) -> tuple[str, ...]:
    """Return run identifiers deduplicated and sorted, for stable linkage."""
    return tuple(sorted(set(run_ids)))


def is_host_path(value: str) -> bool:
    """True if ``value`` looks like an absolute path on the machine that ran."""
    return bool(
        value.startswith("/")
        or _WINDOWS_ABSOLUTE.match(value)
        or _UNC_ABSOLUTE.match(value)
    )


def validate_source_artifact_refs(
    refs: Sequence[str], *, record: str
) -> list[ValidationFinding]:
    """Check artifact references are present and repository-relative."""
    findings: list[ValidationFinding] = []
    if not refs:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.SOURCE_ARTIFACT_MISSING,
                f"{record} names no source artifact",
                {"record": record},
            )
        )
    for ref in refs:
        if is_host_path(ref):
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_REFERENCE,
                    f"{record} artifact reference is an absolute host path",
                    {"record": record},
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Capability audit
# ---------------------------------------------------------------------------


def validate_capability_evidence(
    evidence: CapabilityEvidenceV1, *, repo_root: Path | None = None
) -> list[ValidationFinding]:
    """Validate one capability claim, optionally against the repository tree."""
    findings: list[ValidationFinding] = []
    context = {"capability_id": evidence.capability_id}

    if evidence.status is CapabilityStatus.IMPLEMENTED:
        if not evidence.implementation_paths:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.MISSING_IMPLEMENTATION_EVIDENCE,
                    f"{evidence.capability_id} is IMPLEMENTED but names no code",
                    context,
                )
            )
        if not evidence.test_paths:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM,
                    f"{evidence.capability_id} is IMPLEMENTED but names no test",
                    context,
                )
            )

    if evidence.status is CapabilityStatus.PLANNED and evidence.implementation_paths:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM,
                f"{evidence.capability_id} is PLANNED but names implementation code",
                context,
            )
        )

    if not evidence.notes.strip():
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM,
                f"{evidence.capability_id} carries a status with no explanation",
                context,
            )
        )

    for declared in (*evidence.implementation_paths, *evidence.test_paths):
        if is_host_path(declared):
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_PATH,
                    f"{evidence.capability_id} declares an absolute host path",
                    context,
                )
            )
        elif repo_root is not None and not (repo_root / declared).exists():
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_PATH,
                    (
                        f"{evidence.capability_id} declares evidence that does not "
                        f"resolve: {declared}"
                    ),
                    {**context, "path": declared},
                )
            )

    return findings


def validate_capability_inventory(
    inventory: Sequence[CapabilityEvidenceV1], *, repo_root: Path | None = None
) -> list[ValidationFinding]:
    """Validate a whole inventory, including cross-entry identity rules."""
    findings: list[ValidationFinding] = []

    seen: set[str] = set()
    for evidence in inventory:
        if evidence.capability_id in seen:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.DUPLICATE_CAPABILITY_ID,
                    f"capability {evidence.capability_id} is declared more than once",
                    {"capability_id": evidence.capability_id},
                )
            )
        seen.add(evidence.capability_id)

    for evidence in inventory:
        findings.extend(validate_capability_evidence(evidence, repo_root=repo_root))
    return findings


def validate_no_unwitnessed_hardware_claim(
    inventory: Sequence[CapabilityEvidenceV1],
) -> list[ValidationFinding]:
    """Refuse any VERIFIED_ON_HARDWARE claim while the campaign is deferred.

    DO-102 executes no hardware campaign. Until the deferred execution gate has
    run and been witnessed, nothing in this repository may claim it did.
    """
    return [
        ValidationFinding(
            GrantReadinessErrorCode.INVALID_HARDWARE_VERIFICATION,
            (
                f"{evidence.capability_id} claims VERIFIED_ON_HARDWARE, but no "
                "witnessed hardware campaign is recorded"
            ),
            {"capability_id": evidence.capability_id},
        )
        for evidence in inventory
        if evidence.hardware_verified is HardwareVerification.VERIFIED_ON_HARDWARE
    ]


# ---------------------------------------------------------------------------
# Experiment definition and runs
# ---------------------------------------------------------------------------


def validate_experiment_definition(
    definition: PreliminaryExperimentDefinitionV1,
) -> list[ValidationFinding]:
    """Validate one bounded experiment definition."""
    findings: list[ValidationFinding] = []
    context = {"experiment_id": definition.experiment_id}

    required = {
        "experiment_id": definition.experiment_id,
        "instrument_id": definition.instrument_id,
        "measurement_point_id": definition.measurement_point_id,
        "operator_id": definition.operator_id,
        "analysis_profile": definition.analysis_profile,
    }
    for name, value in required.items():
        if not value or not value.strip():
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
                    f"experiment definition is missing {name}",
                    {**context, "field": name},
                )
            )

    if definition.planned_repeat_count < MINIMUM_REPEAT_COUNT:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.INSUFFICIENT_REPEAT_COUNT,
                (
                    "a repeatability experiment needs at least "
                    f"{MINIMUM_REPEAT_COUNT} planned repeats, got "
                    f"{definition.planned_repeat_count}"
                ),
                context,
            )
        )

    return findings


def validate_experiment_runs(
    runs: Sequence[PreliminaryExperimentRunV1],
    *,
    definition: PreliminaryExperimentDefinitionV1 | None = None,
) -> list[ValidationFinding]:
    """Validate a run collection: identity, accounting, and artifact linkage."""
    findings: list[ValidationFinding] = []

    seen: set[str] = set()
    for run in runs:
        context = {"run_id": run.run_id}

        if run.run_id in seen:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.DUPLICATE_RUN_ID,
                    f"run {run.run_id} appears more than once",
                    context,
                )
            )
        seen.add(run.run_id)

        if definition is not None and run.experiment_id != definition.experiment_id:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.EXPERIMENT_ID_MISMATCH,
                    (
                        f"run {run.run_id} belongs to experiment "
                        f"{run.experiment_id}, not {definition.experiment_id}"
                    ),
                    context,
                )
            )

        if run.valid and run.rejection_reason is not None:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_REJECTION_REASON,
                    f"run {run.run_id} is valid but carries a rejection reason",
                    context,
                )
            )
        if not run.valid and run.rejection_reason is None:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_REJECTION_REASON,
                    f"run {run.run_id} is rejected but names no reason",
                    context,
                )
            )

        # A rejected run may legitimately have lost its artifact — that is one
        # of the rejection reasons — so only valid runs must name their source.
        if run.valid:
            findings.extend(
                validate_source_artifact_refs(
                    run.source_artifact_ids, record=f"run {run.run_id}"
                )
            )
            if not run.observed_features:
                findings.append(
                    ValidationFinding(
                        GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                        f"run {run.run_id} is valid but observed nothing",
                        context,
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Study
# ---------------------------------------------------------------------------


def validate_repeatability_study(
    study: RepeatabilityStudyV1,
) -> list[ValidationFinding]:
    """Validate a whole study: definition, runs, metrics, and their linkage."""
    findings: list[ValidationFinding] = []
    findings.extend(validate_experiment_definition(study.experiment_definition))
    findings.extend(
        validate_experiment_runs(study.runs, definition=study.experiment_definition)
    )

    valid_ids = {run.run_id for run in study.runs if run.valid}
    rejected_ids = {run.run_id for run in study.runs if not run.valid}

    for metric in study.metrics:
        context = {"metric_id": metric.metric_id, "quantity": metric.quantity}

        unknown = sorted(set(metric.source_run_ids) - valid_ids - rejected_ids)
        if unknown:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_REFERENCE,
                    (
                        f"metric {metric.metric_id} cites runs that are not in the "
                        f"study: {', '.join(unknown)}"
                    ),
                    {**context, "unknown_run_ids": unknown},
                )
            )

        # A rejected run must never contribute to a number, only to the count.
        contaminated = sorted(set(metric.source_run_ids) & rejected_ids)
        if contaminated:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_REJECTION_REASON,
                    (
                        f"metric {metric.metric_id} draws on rejected runs: "
                        f"{', '.join(contaminated)}"
                    ),
                    {**context, "rejected_run_ids": contaminated},
                )
            )

        if metric.sample_count != len(set(metric.source_run_ids)):
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_REFERENCE,
                    (
                        f"metric {metric.metric_id} reports {metric.sample_count} "
                        f"samples but cites {len(set(metric.source_run_ids))} runs"
                    ),
                    context,
                )
            )

    findings.extend(validate_study_evidence_origin(study))

    if study.metrics and not study.limitations:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                "a study reporting metrics must state its limitations",
                {"study_id": study.study_id},
            )
        )

    return findings


def validate_study_evidence_origin(
    study: RepeatabilityStudyV1,
) -> list[ValidationFinding]:
    """A study may not claim an origin its runs do not support.

    This is the check behind DO-102's rule that no generated report may
    represent fixture or synthetic data as hardware evidence: a study is
    hardware evidence only if every run in it is.
    """
    findings: list[ValidationFinding] = []
    if not study.runs:
        return findings

    origins = {run.evidence_origin for run in study.runs}
    if study.evidence_origin is EvidenceOrigin.HARDWARE and origins != {
        EvidenceOrigin.HARDWARE
    }:
        non_hardware = sorted(
            run.run_id
            for run in study.runs
            if run.evidence_origin is not EvidenceOrigin.HARDWARE
        )
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                (
                    "study claims HARDWARE origin but contains non-hardware runs: "
                    f"{', '.join(non_hardware)}"
                ),
                {"study_id": study.study_id, "non_hardware_run_ids": non_hardware},
            )
        )

    if study.evidence_origin is not EvidenceOrigin.HARDWARE and (
        EvidenceOrigin.HARDWARE in origins
    ):
        # The reverse direction understates rather than overstates, but it still
        # means the study's own label does not describe its contents.
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                (
                    f"study claims {study.evidence_origin.value} origin but "
                    "contains hardware runs"
                ),
                {"study_id": study.study_id},
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Risks and reference plan
# ---------------------------------------------------------------------------


def validate_technical_risk(risk: TechnicalRiskV1) -> list[ValidationFinding]:
    """A risk must say what is known, what is not, and how to settle it."""
    findings: list[ValidationFinding] = []
    required = {
        "current_evidence": risk.current_evidence,
        "unresolved_question": risk.unresolved_question,
        "proposed_validation_method": risk.proposed_validation_method,
    }
    for name, value in required.items():
        if not value.strip():
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
                    f"risk {risk.risk_id} is missing {name}",
                    {"risk_id": risk.risk_id, "field": name},
                )
            )
    return findings


def validate_reference_validation_plan(
    plan: ReferenceValidationPlanV1,
) -> list[ValidationFinding]:
    """A plan must name at least one prospective comparison method."""
    if not plan.methods:
        return [
            ValidationFinding(
                GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION,
                "reference validation plan names no comparison method",
                {"plan_id": plan.plan_id},
            )
        ]
    return []


__all__ = [
    "MINIMUM_REPEAT_COUNT",
    "ValidationFinding",
    "raise_for_findings",
    "evidence_digest",
    "normalize_run_ids",
    "is_host_path",
    "validate_source_artifact_refs",
    "validate_capability_evidence",
    "validate_capability_inventory",
    "validate_no_unwitnessed_hardware_claim",
    "validate_experiment_definition",
    "validate_experiment_runs",
    "validate_repeatability_study",
    "validate_study_evidence_origin",
    "validate_technical_risk",
    "validate_reference_validation_plan",
    "CapabilityAuditError",
    "EvidenceLinkageError",
    "ExperimentRecordError",
]

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
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from tap_tone_pi.grant_readiness.contracts import (
    MECHANICAL_FRF_NAMES,
    AcquisitionChannelV1,
    ExcitationContextV1,
    AcquisitionRole,
    CampaignExecutionStatus,
    CapabilityEvidenceV1,
    CapabilityStatus,
    EvidenceOrigin,
    ExperimentKind,
    ExperimentOutcomeStatus,
    ExternalArtifactV1,
    HardwareCampaignConfigV1,
    HardwareCampaignRecordV1,
    HardwareVerification,
    MassLoadingObservationV1,
    PreliminaryExperimentDefinitionV1,
    PreliminaryExperimentRunV1,
    ReciprocityObservationV1,
    ReferenceValidationPlanV1,
    RejectionReason,
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


def validate_contact_assembly_masses(
    excitation: ExcitationContextV1, *, record: str
) -> list[ValidationFinding]:
    """A recorded mass must be a mass.

    DO-103 §4.9 replaced an inherited approximate mass-loading figure with the
    instruction to *measure* the stinger and contact assembly, and DO-104 makes
    those measurements part of E1. This checks only that a recorded value could
    be one: it is finite (already enforced on read) and not negative. Nothing
    here compares a mass against a limit, because no evidence for one exists —
    that is what E5 is for.

    It also, deliberately, does **not** check the combined mass against the sum
    of the components. They are different physical ideas: the components are
    hardware masses, the combined figure is the effective mass participating at
    the specimen interface, and it may legitimately be lower than the sum. A
    validator enforcing the arithmetic would reject a correct measurement.
    """
    findings: list[ValidationFinding] = []
    for name, value in excitation.contact_assembly_masses_g.items():
        if value is not None and value < 0:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_CONTACT_ASSEMBLY_MASS,
                    f"{record} records a negative {name.replace('_', ' ')}",
                    {"record": record, "field": name},
                )
            )
    return findings


def validate_experiment_definition(
    definition: PreliminaryExperimentDefinitionV1,
) -> list[ValidationFinding]:
    """Validate one bounded experiment definition."""
    findings: list[ValidationFinding] = []
    context = {"experiment_id": definition.experiment_id}
    findings.extend(
        validate_contact_assembly_masses(
            definition.excitation, record=f"experiment {definition.experiment_id}"
        )
    )

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

        findings.extend(validate_run_acquisition_provenance(run))
        findings.extend(validate_transfer_quantity_naming(run))
        findings.extend(validate_run_campaign_condition(run))
        if run.acquisition is not None:
            for channel in run.acquisition.channels:
                findings.extend(
                    validate_channel_calibration(channel, record=f"run {run.run_id}")
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

    findings.extend(validate_run_sequence(runs))

    return findings


# ---------------------------------------------------------------------------
# Acquisition provenance (DO-103 §5.4)
# ---------------------------------------------------------------------------


def validate_run_acquisition_provenance(
    run: PreliminaryExperimentRunV1,
) -> list[ValidationFinding]:
    """A ``HARDWARE`` claim must be backed by acquisition provenance.

    DO-102 guarded this claim two ways: it refused ``HARDWARE`` for a result
    marked ``demo: true``, and it required a study's runs to agree with its
    label. Both are necessary and neither is sufficient — nothing stopped a
    caller asserting ``HARDWARE`` over data that simply lacked a demo flag.

    DO-103 §5.4 closes that by deriving the claim from the evidence: a run is
    hardware-origin only if it carries what a physical session can attest and a
    fixture or a generator cannot. The tightening is additive. A ``FIXTURE`` or
    ``SYNTHETIC`` run is unaffected and means exactly what it meant before.

    Every condition below is *presence*, not quality. Nothing here judges
    whether a rate was high enough or a sensor good enough; DO-103 §5.5 forbids
    inventing a threshold this campaign exists to produce the evidence for.
    """
    if run.evidence_origin is not EvidenceOrigin.HARDWARE:
        return []

    context = {"run_id": run.run_id}
    acquisition = run.acquisition
    if acquisition is None:
        return [
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE,
                (
                    f"run {run.run_id} claims HARDWARE origin but records no "
                    "acquisition provenance"
                ),
                context,
            )
        ]

    findings: list[ValidationFinding] = []
    missing = [
        name
        for name, value in (
            ("session_id", acquisition.session_id),
            ("acquisition_id", acquisition.acquisition_id),
            ("interface_id", acquisition.interface_id),
        )
        if not str(value).strip()
    ]
    if missing:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE,
                (
                    f"run {run.run_id} claims HARDWARE origin but its acquisition "
                    f"provenance is missing: {', '.join(missing)}"
                ),
                {**context, "missing_fields": missing},
            )
        )

    if acquisition.sample_rate_hz <= 0:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE,
                (
                    f"run {run.run_id} claims HARDWARE origin but records no "
                    "acquisition sample rate"
                ),
                context,
            )
        )

    for role in (AcquisitionRole.EXCITATION, AcquisitionRole.RESPONSE):
        if not acquisition.channels_for(role):
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE,
                    (
                        f"run {run.run_id} claims HARDWARE origin but identifies no "
                        f"{role.value.lower()} channel"
                    ),
                    {**context, "role": role.value},
                )
            )

    # Raw measurements are retained for rejected runs too (DO-103 §6.7). The one
    # exception is the run whose artifact never arrived: MISSING_ARTIFACT is the
    # reason for exactly that, and demanding an artifact here would make an
    # honest rejection unrecordable and reward dropping the run instead.
    retained = acquisition.raw_artifact_ids or run.source_artifact_ids
    if not retained and run.rejection_reason is not RejectionReason.MISSING_ARTIFACT:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_PROVENANCE_INCOMPLETE,
                (
                    f"run {run.run_id} claims HARDWARE origin but retains no raw "
                    "measurement"
                ),
                context,
            )
        )

    return findings


def validate_transfer_quantity_naming(
    run: PreliminaryExperimentRunV1,
) -> list[ValidationFinding]:
    """An acoustic response over a measured force is not a mechanical FRF.

    DO-103 §6.6: with a microphone response and a measured force input the
    transfer function is acoustic pressure per unit force, ``Pa/N``. Mobility,
    accelerance, and receptance all require the response to be a mechanical
    motion of the structure. Carrying the distinction in the record — not only
    in the prose — is what stops a later reader losing it by reading the data.
    """
    acquisition = run.acquisition
    if acquisition is None:
        return []
    response = acquisition.response_channel
    if response is None or response.quantity != "acoustic_pressure":
        return []

    findings: list[ValidationFinding] = []
    for feature in run.observed_features:
        lowered = feature.quantity.lower()
        named = sorted(name for name in MECHANICAL_FRF_NAMES if name in lowered)
        if named:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.MECHANICAL_FRF_MISNAMED,
                    (
                        f"run {run.run_id} names {feature.quantity!r} over an "
                        "acoustic pressure response; a mechanical frequency "
                        "response requires a mechanical response quantity"
                    ),
                    {
                        "run_id": run.run_id,
                        "quantity": feature.quantity,
                        "mechanical_names": named,
                    },
                )
            )
    return findings


def validate_witnessed_hardware_session(
    study: RepeatabilityStudyV1,
) -> list[ValidationFinding]:
    """The stricter of DO-103 §5.4's two standards, used by §10 promotion.

    Hardware origin is an acquisition classification: this data came off
    physical instruments. A witnessed session is a governance condition: the
    provenance is recorded, retained, and *attributable*. Every witnessed run is
    hardware-origin; the reverse does not hold.

    This is deliberately not part of :func:`validate_repeatability_study`. A
    hardware study with unattributed runs is valid evidence of what it observed;
    it is simply not enough to promote a capability off
    ``NOT_VERIFIED_ON_HARDWARE``, which is a separate decision that calls this.
    """
    if study.evidence_origin is not EvidenceOrigin.HARDWARE:
        return [
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_SESSION_NOT_WITNESSED,
                (
                    f"study {study.study_id} is {study.evidence_origin.value} data "
                    "and cannot be a witnessed hardware session"
                ),
                {"study_id": study.study_id},
            )
        ]

    unwitnessed = sorted(
        run.run_id for run in study.runs if not run.is_witnessed_hardware
    )
    if unwitnessed:
        return [
            ValidationFinding(
                GrantReadinessErrorCode.HARDWARE_SESSION_NOT_WITNESSED,
                (
                    f"study {study.study_id} contains runs with no attributable "
                    f"acquisition: {', '.join(unwitnessed)}"
                ),
                {"study_id": study.study_id, "unwitnessed_run_ids": unwitnessed},
            )
        ]
    return []


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
# Hardware campaign (DO-103 §7, §9)
# ---------------------------------------------------------------------------

# Coherence is defined on [0, 1] by construction. Refusing a value outside that
# interval is a check that a record is a record, not an acceptance threshold:
# DO-103 §4.6 forbids comparing an observed coherence against a limit, and
# nothing here does.
COHERENCE_BOUNDS = (0.0, 1.0)

# What each experiment kind must record before its runs can be grouped at all.
# These are structural requirements of the comparison, not quality bars.
_CONDITION_REQUIREMENTS: dict[ExperimentKind, tuple[str, ...]] = {
    ExperimentKind.DETACH_REATTACH: ("contact_configuration_id",),
    ExperimentKind.RECIPROCITY: ("drive_point_id", "response_point_id"),
    ExperimentKind.MASS_LOADING: ("mass_challenge_id", "added_mass_g"),
}

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_channel_calibration(
    channel: AcquisitionChannelV1, *, record: str = "channel"
) -> list[ValidationFinding]:
    """A calibration claim must carry what would let someone check it.

    DO-103 §4.2 separates measured from traceable. A channel may say its
    scaling is traceable, and if it does it must name the reference that makes
    the claim checkable; otherwise the strongest thing the record supports is
    that a number was recorded. This is a check on the claim, never on the
    sensor: an ``UNKNOWN`` calibration is a perfectly valid state and produces
    no finding.
    """
    findings: list[ValidationFinding] = []
    context = {"record": record, "sensor_id": channel.sensor_id}

    if channel.claims_traceability and not channel.calibration_reference:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CALIBRATION_TRACEABILITY_UNSUPPORTED,
                (
                    f"channel {channel.sensor_id} claims traceable calibration but "
                    "names no calibration reference"
                ),
                context,
            )
        )

    if (channel.sensitivity_value is None) != (channel.sensitivity_unit is None):
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                (
                    f"channel {channel.sensor_id} records a sensitivity without "
                    "both a value and its unit; neither is meaningful alone"
                ),
                context,
            )
        )

    return findings


def validate_run_campaign_condition(
    run: PreliminaryExperimentRunV1,
) -> list[ValidationFinding]:
    """A campaign run must record what its own experiment needs to be grouped.

    E3 cannot separate within-attachment from between-attachment variation
    unless every run says which attachment it belongs to; E4 cannot pair a
    direction with its transpose unless both points are named; E5 cannot compare
    against a baseline unless the mass is measured. Each missing field would not
    produce a wrong number — it would produce a comparison that silently drops
    the run, which is worse.

    A run with no campaign condition is a DO-102 run and is not judged here.
    """
    condition = run.campaign_condition
    if condition is None:
        return []

    findings: list[ValidationFinding] = []
    context = {"run_id": run.run_id, "experiment_kind": condition.experiment_kind.value}

    missing = [
        name
        for name in _CONDITION_REQUIREMENTS.get(condition.experiment_kind, ())
        if getattr(condition, name) is None
    ]
    if missing:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONDITION_INCOMPLETE,
                (
                    f"run {run.run_id} is a "
                    f"{condition.experiment_kind.value} run but records no "
                    f"{', '.join(missing)}"
                ),
                {**context, "missing_fields": missing},
            )
        )

    if condition.nominal_added_mass_g is not None and condition.added_mass_g is None:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.MASS_CHALLENGE_UNMEASURED,
                (
                    f"run {run.run_id} records an intended added mass with no "
                    "measured mass; the nominal value may not stand in for it"
                ),
                context,
            )
        )

    if condition.added_mass_g is not None and condition.added_mass_g < 0:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.MASS_CHALLENGE_UNMEASURED,
                f"run {run.run_id} records a negative added mass",
                context,
            )
        )

    pair = condition.point_pair
    if pair is not None and pair[0] == pair[1]:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.RECIPROCITY_POINTS_MISMATCHED,
                (
                    f"run {run.run_id} drives and measures at the same point "
                    f"{pair[0]!r}, which has no transpose"
                ),
                context,
            )
        )

    return findings


def _parsed_utc(value: str) -> datetime | None:
    """Parse a recorded UTC timestamp, or ``None`` if it will not parse.

    Deserialization already refuses a non-UTC timestamp, so this is a guard for
    records assembled in memory rather than read from disk.
    """
    text = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def validate_run_sequence(
    runs: Sequence[PreliminaryExperimentRunV1],
) -> list[ValidationFinding]:
    """The recorded acquisition order must be able to order the runs.

    Warm-up, contact creep, and transducer drift are only visible in sequence,
    so the order is recorded at acquisition rather than reconstructed later by
    sorting timestamps. Two failures make that record useless: an index used
    twice orders nothing, and an index that contradicts the clock means one of
    the two is wrong and a reader cannot tell which.

    The DO-104 invariant: **acquisition order is authoritative as explicitly
    recorded by ``sequence_index``; timestamps remain separately preserved
    evidence, and a disagreement is reported, not silently repaired.** The two
    are independent evidence about the same acquisition, so neither is sorted
    into agreement with the other and neither is treated as the truth the other
    must match. A disagreement may itself be the finding — a capture, clock,
    import, or operator problem — and resolving it here would destroy it.

    Runs without a sequence index are not judged: the field is optional, and a
    DO-102 study that never had one is unaffected.
    """
    findings: list[ValidationFinding] = []
    indexed = [run for run in runs if run.sequence_index is not None]

    seen: dict[int, str] = {}
    for run in indexed:
        first = seen.get(run.sequence_index)
        if first is not None:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_RUN_SEQUENCE,
                    (
                        f"runs {first} and {run.run_id} share sequence index "
                        f"{run.sequence_index}"
                    ),
                    {
                        "sequence_index": run.sequence_index,
                        "run_ids": [first, run.run_id],
                    },
                )
            )
        else:
            seen[run.sequence_index] = run.run_id

    ordered = sorted(indexed, key=lambda run: run.sequence_index)
    previous = None
    for run in ordered:
        stamp = _parsed_utc(run.captured_at)
        if stamp is None:
            continue
        if previous is not None and stamp < previous[1]:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INVALID_RUN_SEQUENCE,
                    (
                        f"run {run.run_id} follows {previous[0]} in acquisition "
                        "order but was captured before it"
                    ),
                    {"run_ids": [previous[0], run.run_id]},
                )
            )
        previous = (run.run_id, stamp)

    return findings


def validate_external_artifact(
    artifact: ExternalArtifactV1,
) -> list[ValidationFinding]:
    """An artifact reference must identify bytes, not a location.

    Raw audio is not committed to this repository, so the reference has to
    survive the file moving. The digest is therefore the identity and is
    required to look like one; the locator says where a copy may currently be
    found, and an absolute path from the acquiring workstation is refused as an
    identity because it stops meaning anything on any other machine.
    """
    findings: list[ValidationFinding] = []
    context = {"artifact_id": artifact.artifact_id}

    if not _SHA256_PATTERN.match(artifact.sha256):
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.ARTIFACT_IDENTITY_INCOMPLETE,
                (
                    f"artifact {artifact.artifact_id} does not carry a SHA-256 "
                    "digest as its identity"
                ),
                context,
            )
        )

    if artifact.byte_count < 0:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.ARTIFACT_IDENTITY_INCOMPLETE,
                f"artifact {artifact.artifact_id} reports a negative size",
                context,
            )
        )

    if is_host_path(artifact.storage_locator):
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.ARTIFACT_IDENTITY_NOT_PORTABLE,
                (
                    f"artifact {artifact.artifact_id} uses an absolute host path as "
                    "its storage locator; a path on the acquiring machine is not a "
                    "durable identity"
                ),
                context,
            )
        )

    return findings


def validate_artifact_manifest(
    artifacts: Sequence[ExternalArtifactV1],
    *,
    runs: Sequence[PreliminaryExperimentRunV1] = (),
) -> list[ValidationFinding]:
    """Check an artifact manifest and, where runs are given, its coverage.

    A run that names a raw artifact the manifest does not carry has an evidence
    reference nobody can resolve, which is the failure DO-103 §12 criterion 12
    is written against: every number must lead back to the bytes it came from.
    """
    findings: list[ValidationFinding] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.artifact_id in seen:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.ARTIFACT_IDENTITY_INCOMPLETE,
                    f"artifact {artifact.artifact_id} appears more than once",
                    {"artifact_id": artifact.artifact_id},
                )
            )
        seen.add(artifact.artifact_id)
        findings.extend(validate_external_artifact(artifact))

    for run in runs:
        if run.acquisition is None:
            continue
        unresolved = sorted(set(run.acquisition.raw_artifact_ids) - seen)
        if unresolved:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_REFERENCE,
                    (
                        f"run {run.run_id} retains raw artifacts the manifest does "
                        f"not carry: {', '.join(unresolved)}"
                    ),
                    {"run_id": run.run_id, "artifact_ids": unresolved},
                )
            )

    return findings


def validate_campaign_config(
    config: HardwareCampaignConfigV1,
) -> list[ValidationFinding]:
    """Check a campaign's stated configuration before anything is captured.

    Two of these are worth stating. The rig must be identified, because DO-103
    §4.8 makes it part of the measurement instrument and a campaign that cannot
    say which rig it used cannot be repeated. And exactly one excitation and one
    response channel must be named, because the transfer function's own units
    are derived from that pair — an ambiguous pair makes the recorded unit
    unknowable rather than merely unrecorded.
    """
    findings: list[ValidationFinding] = []
    context = {"campaign_id": config.campaign_id}

    findings.extend(
        validate_contact_assembly_masses(
            config.excitation, record=f"campaign {config.campaign_id}"
        )
    )

    if not config.excitation.rig_configuration_id:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                "campaign identifies no rig configuration",
                context,
            )
        )

    for role in (AcquisitionRole.EXCITATION, AcquisitionRole.RESPONSE):
        found = config.channels_for(role)
        if len(found) != 1:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"campaign names {len(found)} {role.value.lower()} channels; "
                        "the transfer quantity is derived from exactly one of each"
                    ),
                    {**context, "role": role.value},
                )
            )

    indices: set[int] = set()
    for channel in config.channels:
        if channel.channel_index in indices:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    f"campaign reuses channel index {channel.channel_index}",
                    context,
                )
            )
        indices.add(channel.channel_index)
        findings.extend(
            validate_channel_calibration(
                channel, record=f"campaign {config.campaign_id}"
            )
        )

    if config.force_channel is None:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                (
                    "campaign records no measured force channel; DO-103 requires "
                    "the excitation to be measured rather than commanded"
                ),
                context,
            )
        )

    seen_experiments: set[str] = set()
    for plan in config.experiments:
        plan_context = {**context, "experiment_id": plan.experiment_id}
        if plan.experiment_id in seen_experiments:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    f"campaign plans experiment {plan.experiment_id} twice",
                    plan_context,
                )
            )
        seen_experiments.add(plan.experiment_id)

        if plan.planned_repeat_count < MINIMUM_REPEAT_COUNT:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INSUFFICIENT_REPEAT_COUNT,
                    (
                        f"experiment {plan.experiment_id} plans "
                        f"{plan.planned_repeat_count} repeats, fewer than the "
                        f"{MINIMUM_REPEAT_COUNT} a spread can be described from"
                    ),
                    plan_context,
                )
            )

        is_rig_experiment = plan.kind is ExperimentKind.RIG_CHARACTERIZATION
        if is_rig_experiment and not plan.subject_is_rig:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"experiment {plan.experiment_id} characterizes the rig but "
                        "does not declare the rig as its subject; recording the rig "
                        "in instrument_id is permitted only where the record says so"
                    ),
                    plan_context,
                )
            )
        if plan.subject_is_rig and not is_rig_experiment:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"experiment {plan.experiment_id} declares the rig as its "
                        f"subject but is a {plan.kind.value} experiment"
                    ),
                    plan_context,
                )
            )

    return findings


def validate_reciprocity_observation(
    observation: ReciprocityObservationV1,
) -> list[ValidationFinding]:
    """Check a reciprocity observation describes a transpose of two directions.

    There is no residual limit here and there will not be one in this order: a
    large residual is what E4 exists to detect. What is checked is that the
    record is coherent as a record — two distinct runs, two distinct points, a
    residual that is a magnitude, and coherences inside the interval coherence
    is defined on.
    """
    findings: list[ValidationFinding] = []
    context = {"observation_id": observation.observation_id}

    if observation.forward_run_id == observation.reverse_run_id:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.RECIPROCITY_PAIR_INCOMPLETE,
                (
                    f"observation {observation.observation_id} pairs run "
                    f"{observation.forward_run_id} with itself"
                ),
                context,
            )
        )

    if observation.forward_drive_point_id == observation.forward_response_point_id:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.RECIPROCITY_POINTS_MISMATCHED,
                (
                    f"observation {observation.observation_id} drives and measures "
                    "at the same point"
                ),
                context,
            )
        )

    if observation.absolute_residual < 0:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.NON_FINITE_STATISTIC,
                (
                    f"observation {observation.observation_id} reports a negative "
                    "absolute residual"
                ),
                context,
            )
        )

    low, high = COHERENCE_BOUNDS
    for name, value in (
        ("forward_coherence", observation.forward_coherence),
        ("reverse_coherence", observation.reverse_coherence),
    ):
        if value is not None and not low <= value <= high:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.NON_FINITE_STATISTIC,
                    (
                        f"observation {observation.observation_id} reports "
                        f"{name} of {value}, outside the interval coherence is "
                        "defined on"
                    ),
                    {**context, "field": name},
                )
            )

    return findings


def validate_mass_loading_observation(
    observation: MassLoadingObservationV1,
) -> list[ValidationFinding]:
    """Check a mass-loading observation compares a load against a baseline.

    No response size is judged. A challenge that moved nothing is a finding
    about the measurement architecture, and DO-103 §4.7 forbids this order from
    deciding how much movement would have been enough.
    """
    findings: list[ValidationFinding] = []
    context = {"observation_id": observation.observation_id}

    if observation.added_mass_g <= 0:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.MASS_CHALLENGE_UNMEASURED,
                (
                    f"observation {observation.observation_id} compares a challenge "
                    f"of {observation.added_mass_g} g, which adds no mass"
                ),
                context,
            )
        )

    for name, metric in (
        ("baseline_metric", observation.baseline_metric),
        ("loaded_metric", observation.loaded_metric),
    ):
        if metric.sample_count < MINIMUM_REPEAT_COUNT:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                    (
                        f"observation {observation.observation_id} summarizes "
                        f"{name} from {metric.sample_count} run(s); a delta cannot "
                        "be read against a spread that was never observed"
                    ),
                    {**context, "field": name},
                )
            )
        if metric.unit != observation.unit:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
                    (
                        f"observation {observation.observation_id} reports "
                        f"{observation.unit} but its {name} is in {metric.unit}"
                    ),
                    {**context, "field": name},
                )
            )

    return findings


def validate_campaign_record(
    record: HardwareCampaignRecordV1,
) -> list[ValidationFinding]:
    """Validate a whole campaign: configuration, accounting, and observations.

    The accounting rules exist because DO-103 §12 criterion 11 requires an
    experiment that did not run to say why. An executed experiment names the
    study it produced; one stopped by an earlier gate names the gate; and a
    campaign that claims execution has to have executed something.
    """
    findings: list[ValidationFinding] = list(validate_campaign_config(record.config))
    findings.extend(validate_artifact_manifest(record.artifacts))

    planned = {plan.experiment_id for plan in record.config.experiments}
    accounted: set[str] = set()
    for outcome in record.outcomes:
        context = {
            "campaign_id": record.campaign_id,
            "experiment_id": outcome.experiment_id,
        }
        if outcome.experiment_id not in planned:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"campaign records an outcome for {outcome.experiment_id}, "
                        "which it never planned"
                    ),
                    context,
                )
            )
        if outcome.experiment_id in accounted:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    f"campaign accounts for {outcome.experiment_id} twice",
                    context,
                )
            )
        accounted.add(outcome.experiment_id)

        if outcome.status is ExperimentOutcomeStatus.EXECUTED and not outcome.study_id:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"experiment {outcome.experiment_id} is recorded as executed "
                        "but names no study"
                    ),
                    context,
                )
            )
        if (
            outcome.status is ExperimentOutcomeStatus.EXECUTED
            and outcome.evidence_origin is None
        ):
            # Without it the campaign cannot say what kind of evidence it holds,
            # and a reader would have to open every study to find out.
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                    (
                        f"experiment {outcome.experiment_id} is recorded as executed "
                        "but its outcome names no evidence origin"
                    ),
                    context,
                )
            )
        if outcome.witnessed and not outcome.is_hardware_evidence:
            # Witnessed is the stricter of DO-103 §5.4's two standards and is a
            # property of hardware acquisition. Fixture data cannot carry it,
            # whatever the summary says.
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.HARDWARE_SESSION_NOT_WITNESSED,
                    (
                        f"experiment {outcome.experiment_id} is recorded as witnessed "
                        f"over {outcome.evidence_origin.value if outcome.evidence_origin else 'unstated'} "
                        "evidence"
                    ),
                    context,
                )
            )
        if (
            outcome.status is ExperimentOutcomeStatus.BLOCKED_BY_GATE
            and not outcome.blocked_by_experiment_id
        ):
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    (
                        f"experiment {outcome.experiment_id} is recorded as blocked "
                        "but names no gate that blocked it"
                    ),
                    context,
                )
            )

    unaccounted = sorted(planned - accounted)
    if unaccounted:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                (
                    "campaign plans experiments it does not account for: "
                    f"{', '.join(unaccounted)}"
                ),
                {"campaign_id": record.campaign_id, "experiment_ids": unaccounted},
            )
        )

    findings.extend(validate_campaign_execution_status(record))

    for observation in record.reciprocity:
        findings.extend(validate_reciprocity_observation(observation))
    for loading in record.mass_loading:
        findings.extend(validate_mass_loading_observation(loading))

    return findings


def validate_campaign_execution_status(
    record: HardwareCampaignRecordV1,
) -> list[ValidationFinding]:
    """A campaign may not claim an execution its own outcomes do not support.

    The status is what a reader sees first and often alone, so it is the field
    most worth protecting from a hopeful choice of word. ``HARDWARE_EXECUTED``
    requires an executed outcome carrying hardware-origin evidence;
    ``FIXTURE_EXECUTED`` requires that none of them does; ``PREPARED`` requires
    that nothing ran at all. A rehearsal against fixture data is a real result
    and is not a hardware campaign, and no arrangement of these fields lets it
    be recorded as one.

    ``ABORTED`` is deliberately unconstrained beyond the accounting: a campaign
    can be abandoned at any point, and the reason is not a state machine.
    """
    findings: list[ValidationFinding] = []
    context = {"campaign_id": record.campaign_id}
    executed = record.executed_experiment_ids
    hardware = record.hardware_experiment_ids
    status = record.execution_status

    if status is CampaignExecutionStatus.PREPARED and executed:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                (
                    "campaign is recorded as prepared but accounts for executed "
                    f"experiments: {', '.join(executed)}"
                ),
                context,
            )
        )

    if status is CampaignExecutionStatus.HARDWARE_EXECUTED and not hardware:
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                (
                    "campaign is recorded as hardware-executed but no experiment "
                    "produced hardware-origin evidence"
                ),
                context,
            )
        )

    if status is CampaignExecutionStatus.FIXTURE_EXECUTED:
        if not executed:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                    "campaign is recorded as fixture-executed but nothing executed",
                    context,
                )
            )
        if hardware:
            findings.append(
                ValidationFinding(
                    GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                    (
                        "campaign is recorded as fixture-executed but contains "
                        f"hardware-origin experiments: {', '.join(hardware)}"
                    ),
                    context,
                )
            )

    if status is CampaignExecutionStatus.HALTED_AT_GATE and not any(
        outcome.status is ExperimentOutcomeStatus.HALTED_AT_GATE
        for outcome in record.outcomes
    ):
        findings.append(
            ValidationFinding(
                GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID,
                (
                    "campaign is recorded as halted at a gate but no experiment is "
                    "recorded as the gate that halted it"
                ),
                context,
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
    "COHERENCE_BOUNDS",
    "validate_channel_calibration",
    "validate_contact_assembly_masses",
    "validate_run_campaign_condition",
    "validate_run_sequence",
    "validate_external_artifact",
    "validate_artifact_manifest",
    "validate_campaign_config",
    "validate_campaign_execution_status",
    "validate_reciprocity_observation",
    "validate_mass_loading_observation",
    "validate_campaign_record",
    "validate_technical_risk",
    "validate_reference_validation_plan",
    "CapabilityAuditError",
    "EvidenceLinkageError",
    "ExperimentRecordError",
]

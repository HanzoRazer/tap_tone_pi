# INSTRUMENT CLASS: MEASUREMENT
"""Grant-readiness evidence contracts (DO-102).

Frozen records describing what the instrument currently does, what a bounded
preliminary repeatability experiment observed, and which technical questions
remain unresolved. These are evidence contracts: they carry measurements and
their conditions, never an interpretation of them.

Three rules shape every record here.

**Repeatability is not accuracy.** :class:`RepeatabilityMetricV1` reports the
spread of repeated observations under recorded conditions. It carries no
acceptance flag, no threshold, and no pass/fail field, because agreement with a
reference has not been established and cannot be inferred from spread alone.
The DO-085 acceptance gate in :mod:`tap_tone_pi.core.repeatability` stays where
it lives; a study may cross-reference that evidence by identity, but it does not
inherit from it and does not need it to serialize or validate.

**Evidence origin travels with the evidence.** Every run and every study carries
an :class:`EvidenceOrigin`. Fixture and synthetic data are legitimate ways to
prove a contract and an analysis path; they are not hardware evidence, and
nothing downstream may present them as such.

**Excitation is recorded generically.** :class:`ExcitationContextV1` describes
the mechanical arrangement — method, device, drive point, contact condition,
fixture — and treats ``manual_tap`` as one value among several rather than as
the canonical method. A driven source links back to the existing
``ExcitationContractV1`` through ``excitation_contract_id``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from tap_tone_pi.grant_readiness.errors import (
    CapabilityAuditError,
    ExperimentRecordError,
    GrantReadinessErrorCode,
)

AUDIT_SCHEMA_VERSION = "nsf_grant_readiness_audit_v1"
STUDY_SCHEMA_VERSION = "ttp_preliminary_repeatability_study_v1"
CAMPAIGN_SCHEMA_VERSION = "ttp_hardware_campaign_v1"


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


class CapabilityStatus(str, Enum):
    """The four-state capability vocabulary (DO-102 §4.2).

    A ``str`` enum so the serialized value is exactly the declared state while an
    unknown state stays unconstructable. There is deliberately no "mostly done".
    """

    IMPLEMENTED = "IMPLEMENTED"
    EXPERIMENTAL = "EXPERIMENTAL"
    PARTIAL = "PARTIAL"
    PLANNED = "PLANNED"


class HardwareVerification(str, Enum):
    """Whether execution on the intended hardware has been witnessed.

    ``NOT_VERIFIED_ON_HARDWARE`` is the DO-102 secondary state: code exists, but
    nobody has watched it run on the intended Pi/microphone configuration.
    ``NOT_APPLICABLE`` marks a capability with no hardware dependency to witness.
    """

    VERIFIED_ON_HARDWARE = "VERIFIED_ON_HARDWARE"
    NOT_VERIFIED_ON_HARDWARE = "NOT_VERIFIED_ON_HARDWARE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceOrigin(str, Enum):
    """Where a run's underlying data came from.

    ``HARDWARE`` means a witnessed physical capture. ``FIXTURE`` means a
    deterministic recorded input used to prove the analysis path. ``SYNTHETIC``
    means generated audio. Only ``HARDWARE`` may be described as hardware
    evidence, and DO-102 produces none of it.
    """

    HARDWARE = "HARDWARE"
    FIXTURE = "FIXTURE"
    SYNTHETIC = "SYNTHETIC"

    @property
    def is_hardware_evidence(self) -> bool:
        return self is EvidenceOrigin.HARDWARE


class AcquisitionRole(str, Enum):
    """What one recorded channel carries (DO-103 §5.4).

    ``EXCITATION`` is the input the structure is driven with; ``RESPONSE`` is
    what the structure is observed by. A transfer function is response over
    excitation, so the pair is what gives the ratio its units — see
    :attr:`AcquisitionProvenanceV1.transfer_unit`.
    """

    EXCITATION = "EXCITATION"
    RESPONSE = "RESPONSE"


class CalibrationTraceability(str, Enum):
    """How far a channel's scaling to engineering units can be defended.

    DO-103 §4.2 separates *measured* from *traceable*: recording a force channel
    makes the excitation observable, and it does not make the newton it is
    scaled to defensible against a standard. ``NOMINAL`` is a manufacturer or
    datasheet sensitivity taken on trust; ``TRACEABLE`` is an unbroken chain to
    a reference and requires a calibration reference to say so. The default is
    ``UNKNOWN``, because a sensor whose calibration nobody recorded has none
    this repository can attest to.
    """

    TRACEABLE = "TRACEABLE"
    NOMINAL = "NOMINAL"
    UNKNOWN = "UNKNOWN"


class ExperimentKind(str, Enum):
    """Which of the DO-103 §7 characterization experiments a record belongs to.

    The kinds are not interchangeable and are not a severity ordering. Each asks
    a different question of the same rig and needs a different grouping of the
    same run records — which is why a run says which one it belongs to rather
    than leaving a reader to infer it from an experiment's name.
    """

    RIG_CHARACTERIZATION = "RIG_CHARACTERIZATION"
    FIXED_POINT = "FIXED_POINT"
    DETACH_REATTACH = "DETACH_REATTACH"
    RECIPROCITY = "RECIPROCITY"
    MASS_LOADING = "MASS_LOADING"


class CampaignExecutionStatus(str, Enum):
    """What a campaign as a whole is, read cold and without its contents.

    The distinction a reader is most likely to lose is between running the
    analysis path and running the rig, and a bare ``EXECUTED`` loses it: a
    campaign rehearsed end to end against fixture data and a campaign driven by
    a physical shaker would carry the same word. The status therefore names
    which of the two happened, so nobody has to open the studies to find out.

    ``PREPARED`` is a configuration with nothing run against it, which is the
    expected state of this repository's own campaign until a rig exists.
    ``HALTED_AT_GATE`` is DO-103 §13's E1 gate firing — a real and reportable
    result. ``ABORTED`` is a campaign stopped for a reason that is not a gate.
    """

    PREPARED = "PREPARED"
    FIXTURE_EXECUTED = "FIXTURE_EXECUTED"
    HARDWARE_EXECUTED = "HARDWARE_EXECUTED"
    HALTED_AT_GATE = "HALTED_AT_GATE"
    ABORTED = "ABORTED"

    @property
    def is_hardware_execution(self) -> bool:
        return self is CampaignExecutionStatus.HARDWARE_EXECUTED


class ExperimentOutcomeStatus(str, Enum):
    """What became of one planned experiment within a campaign.

    Separate from :class:`CampaignExecutionStatus` because they answer different
    questions. This one says whether an experiment ran; the campaign's own
    status says what kind of campaign it was. An outcome that ran names both the
    study it produced and that study's evidence origin, so ``EXECUTED`` here is
    never read in isolation either.

    ``HALTED_AT_GATE`` and ``BLOCKED_BY_GATE`` exist because DO-103 §13 makes E1
    a real gate: a rig that cannot produce usable evidence stops the downstream
    campaign, and §12 criterion 11 requires that outcome to be *recorded* rather
    than left as an absence. A missing experiment and a deliberately abandoned
    one are different findings, and a reader must not have to guess which one a
    gap represents.
    """

    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTED = "EXECUTED"
    HALTED_AT_GATE = "HALTED_AT_GATE"
    BLOCKED_BY_GATE = "BLOCKED_BY_GATE"


class RejectionReason(str, Enum):
    """Why a run was excluded from the numerical summary.

    A rejected run stays in the study. It is accounted for, reported, and
    counted; it is only withheld from the statistics.

    ``QUALITY_GATE_REJECTED`` is not in the DO-102 list. It exists because the
    Phase 1 contract emits a ``fail`` verdict that need not name clipping or a
    low signal, and inferring one of those from a bare verdict would invent a
    cause the evidence does not support.
    """

    CLIPPING = "CLIPPING"
    INSUFFICIENT_SIGNAL = "INSUFFICIENT_SIGNAL"
    ANALYSIS_FAILURE = "ANALYSIS_FAILURE"
    MISSING_ARTIFACT = "MISSING_ARTIFACT"
    INVALID_METADATA = "INVALID_METADATA"
    QUALITY_GATE_REJECTED = "QUALITY_GATE_REJECTED"


class RiskStatus(str, Enum):
    """Lifecycle of a technical risk."""

    OPEN = "OPEN"
    PARTIALLY_CHARACTERIZED = "PARTIALLY_CHARACTERIZED"
    CLOSED = "CLOSED"


# Excitation methods this contract knows how to name. The tuple is open by
# intent: an unlisted method is recorded verbatim rather than rejected, because
# the excitation architecture is expected to change and a contract that refuses
# to record what happened is worse than one that records an unfamiliar name.
KNOWN_EXCITATION_METHODS: tuple[str, ...] = (
    "manual_tap",
    "instrumented_hammer",
    "shaker_stinger",
    "acoustic_drive",
    "unspecified",
)

# Physical quantities a recorded channel may carry. Like
# ``KNOWN_EXCITATION_METHODS`` this is a known-values list, not a closed one: an
# unlisted quantity is recorded and flagged as unrecognised rather than refused,
# because refusing it would lose the record of what was actually measured.
KNOWN_ACQUISITION_QUANTITIES: tuple[str, ...] = (
    "force",
    "acoustic_pressure",
    "velocity",
    "acceleration",
    "displacement",
    "voltage",
    "unspecified",
)

# Names of mechanical frequency-response functions. DO-103 §6.6 forbids every one
# of them for an acoustic pressure response over a measured force: p/F is an
# acoustic-response transfer function relative to measured force, and calling it
# mobility would make a future comparison against a laboratory modal method a
# category error rather than a disagreement.
MECHANICAL_FRF_NAMES: frozenset[str] = frozenset(
    {
        "mobility",
        "accelerance",
        "inertance",
        "receptance",
        "compliance",
    }
)


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _reject_unknown_keys(
    payload: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> None:
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise error(
            code,
            f"{record} payload carries unknown field(s): {', '.join(unknown)}",
            {"record": record, "unknown_fields": unknown},
        )


def _require_text(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise error(
            code,
            f"{record}.{key} must be a non-empty string",
            {"field": key, "record": record},
        )
    return value


def _optional_text(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise error(
            code,
            f"{record}.{key} must be a non-empty string when present",
            {"field": key, "record": record},
        )
    return value


def _text_tuple(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> tuple[str, ...]:
    value = payload.get(key, ())
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise error(
            code,
            f"{record}.{key} must be an array of strings",
            {"field": key, "record": record},
        )
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise error(
                code,
                f"{record}.{key} entries must be non-empty strings",
                {"field": key, "record": record},
            )
        out.append(item)
    return tuple(out)


def _optional_number(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error(
            code,
            f"{record}.{key} must be a number when present",
            {"field": key, "record": record},
        )
    if not math.isfinite(float(value)):
        raise error(
            GrantReadinessErrorCode.NON_FINITE_STATISTIC,
            f"{record}.{key} must be finite",
            {"field": key, "record": record},
        )
    return float(value)


def _require_enum(
    payload: Mapping[str, Any],
    key: str,
    enum_cls: type[Enum],
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> Any:
    raw = payload.get(key)
    try:
        return enum_cls(raw)
    except ValueError as exc:
        raise error(
            code,
            f"{record}.{key} is not a known {enum_cls.__name__}: {raw!r}",
            {
                "field": key,
                "record": record,
                "permitted": [member.value for member in enum_cls],
            },
        ) from exc


def _sequence(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> Sequence[Any]:
    """Read an array field, refusing a string that would iterate per character."""
    value = payload.get(key, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise error(
            code,
            f"{record}.{key} must be an array",
            {"field": key, "record": record},
        )
    return value


def _number_tuple(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> tuple[float, ...]:
    values = _sequence(payload, key, record=record, error=error, code=code)
    out: list[float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise error(
                code,
                f"{record}.{key} entries must be numbers",
                {"field": key, "record": record},
            )
        if not math.isfinite(float(item)):
            raise error(
                GrantReadinessErrorCode.NON_FINITE_STATISTIC,
                f"{record}.{key} entries must be finite",
                {"field": key, "record": record},
            )
        out.append(float(item))
    return tuple(out)


def _required_numbers(
    payload: Mapping[str, Any],
    keys: Iterable[str],
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> dict[str, float]:
    """Read several required finite numbers, naming the first that is absent."""
    numbers: dict[str, float] = {}
    for name in keys:
        value = _optional_number(payload, name, record=record, error=error, code=code)
        if value is None:
            raise error(
                code,
                f"{record}.{name} is required",
                {"record": record, "field": name},
            )
        numbers[name] = value
    return numbers


def _reject_derived_disagreement(
    payload: Mapping[str, Any],
    derived: Mapping[str, Any],
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> None:
    """Refuse a payload whose emitted-for-readers fields contradict its contents.

    A derived field round-trips trivially, so a disagreement means the document
    is internally inconsistent. Deserializing it silently would produce an
    object whose counts differ from the source it was read from.
    """
    for name, value in derived.items():
        if name in payload and payload[name] != value:
            raise error(
                code,
                (
                    f"{record}.{name} {payload[name]!r} disagrees with the record "
                    f"(derived {value!r})"
                ),
                {"record": record, "field": name},
            )


def _enum_with_default(
    payload: Mapping[str, Any],
    key: str,
    enum_cls: type[Enum],
    default: Any,
    *,
    record: str,
    error: type[ExperimentRecordError] | type[CapabilityAuditError],
    code: GrantReadinessErrorCode,
) -> Any:
    """Read an optional enum field, falling back to ``default`` when absent.

    An *absent* value takes the default; a *present* but unrecognised one is
    refused. Coercing an unknown state to the default would silently rewrite
    what a record claimed about itself.
    """
    if payload.get(key) is None:
        return default
    return _require_enum(payload, key, enum_cls, record=record, error=error, code=code)


def require_utc_timestamp(value: Any, *, record: str, field_name: str) -> str:
    """Return ``value`` if it is an ISO-8601 UTC instant, else raise NSF-207.

    Conditions are only evidence if the time they were recorded at is
    unambiguous, so a naive or offset local timestamp is refused rather than
    silently reinterpreted.
    """
    if not isinstance(value, str) or not value.strip():
        raise ExperimentRecordError(
            GrantReadinessErrorCode.TIMESTAMP_NOT_UTC,
            f"{record}.{field_name} must be an ISO-8601 UTC timestamp",
            {"field": field_name, "record": record},
        )
    text = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ExperimentRecordError(
            GrantReadinessErrorCode.TIMESTAMP_NOT_UTC,
            f"{record}.{field_name} is not a parseable ISO-8601 timestamp",
            {"field": field_name, "record": record},
        ) from exc
    offset = parsed.utcoffset()
    if offset is None or offset != timedelta(0):
        # A naive timestamp, or one carrying a local offset, is refused rather
        # than reinterpreted — guessing the zone would fabricate provenance.
        raise ExperimentRecordError(
            GrantReadinessErrorCode.TIMESTAMP_NOT_UTC,
            f"{record}.{field_name} must carry a UTC offset of zero",
            {"field": field_name, "record": record},
        )
    return value


# ---------------------------------------------------------------------------
# Capability audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityEvidenceV1:
    """One audited capability and the repository evidence behind its status."""

    capability_id: str
    name: str
    status: CapabilityStatus
    implementation_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    hardware_verified: HardwareVerification = (
        HardwareVerification.NOT_VERIFIED_ON_HARDWARE
    )
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "status": self.status.value,
            "implementation_paths": list(self.implementation_paths),
            "test_paths": list(self.test_paths),
            "evidence_refs": list(self.evidence_refs),
            "hardware_verified": self.hardware_verified.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CapabilityEvidenceV1:
        record = "CapabilityEvidenceV1"
        err = CapabilityAuditError
        code = GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM
        _reject_unknown_keys(
            payload,
            (
                "capability_id",
                "name",
                "status",
                "implementation_paths",
                "test_paths",
                "evidence_refs",
                "hardware_verified",
                "notes",
            ),
            record=record,
            error=err,
            code=code,
        )
        return cls(
            capability_id=_require_text(
                payload, "capability_id", record=record, error=err, code=code
            ),
            name=_require_text(payload, "name", record=record, error=err, code=code),
            status=_require_enum(
                payload,
                "status",
                CapabilityStatus,
                record=record,
                error=err,
                code=GrantReadinessErrorCode.INVALID_CAPABILITY_STATUS,
            ),
            implementation_paths=_text_tuple(
                payload, "implementation_paths", record=record, error=err, code=code
            ),
            test_paths=_text_tuple(
                payload, "test_paths", record=record, error=err, code=code
            ),
            evidence_refs=_text_tuple(
                payload, "evidence_refs", record=record, error=err, code=code
            ),
            hardware_verified=_require_enum(
                payload,
                "hardware_verified",
                HardwareVerification,
                record=record,
                error=err,
                code=GrantReadinessErrorCode.INVALID_HARDWARE_VERIFICATION,
            ),
            notes=_require_text(payload, "notes", record=record, error=err, code=code),
        )


@dataclass(frozen=True)
class GrantReadinessAuditV1:
    """A capability audit produced from a declared inventory plus repo state."""

    audit_id: str
    generated_at: str
    capabilities: tuple[CapabilityEvidenceV1, ...] = ()
    repository_commit: str | None = None
    limitations: tuple[str, ...] = ()
    schema_version: str = field(default=AUDIT_SCHEMA_VERSION, init=False)

    @property
    def status_counts(self) -> dict[str, int]:
        """Capability count per status, with every status present as a key."""
        counts = {member.value: 0 for member in CapabilityStatus}
        for capability in self.capabilities:
            counts[capability.status.value] += 1
        return counts

    @property
    def hardware_verified_count(self) -> int:
        return sum(
            1
            for capability in self.capabilities
            if capability.hardware_verified is HardwareVerification.VERIFIED_ON_HARDWARE
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "audit_id": self.audit_id,
            "generated_at": self.generated_at,
            "repository_commit": self.repository_commit,
            "capability_count": len(self.capabilities),
            "status_counts": self.status_counts,
            "hardware_verified_count": self.hardware_verified_count,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GrantReadinessAuditV1:
        record = "GrantReadinessAuditV1"
        err = CapabilityAuditError
        code = GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM
        _reject_unknown_keys(
            payload,
            (
                "schema_version",
                "audit_id",
                "generated_at",
                "repository_commit",
                "capability_count",
                "status_counts",
                "hardware_verified_count",
                "capabilities",
                "limitations",
            ),
            record=record,
            error=err,
            code=code,
        )
        declared = payload.get("schema_version", AUDIT_SCHEMA_VERSION)
        if declared != AUDIT_SCHEMA_VERSION:
            raise err(
                code,
                f"{record}.schema_version must be {AUDIT_SCHEMA_VERSION!r}",
                {"record": record, "schema_version": declared},
            )
        raw_caps = payload.get("capabilities", ())
        if isinstance(raw_caps, (str, bytes)) or not isinstance(raw_caps, Sequence):
            raise err(
                code,
                f"{record}.capabilities must be an array",
                {"record": record},
            )
        return cls(
            audit_id=_require_text(
                payload, "audit_id", record=record, error=err, code=code
            ),
            generated_at=require_utc_timestamp(
                payload.get("generated_at"), record=record, field_name="generated_at"
            ),
            capabilities=tuple(
                CapabilityEvidenceV1.from_dict(item) for item in raw_caps
            ),
            repository_commit=_optional_text(
                payload, "repository_commit", record=record, error=err, code=code
            ),
            limitations=_text_tuple(
                payload, "limitations", record=record, error=err, code=code
            ),
        )


# ---------------------------------------------------------------------------
# Experiment definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentalContextV1:
    """Recorded conditions. ``None`` means unknown and stays unknown.

    DO-102 §4.6: environment is recorded, never corrected. Nothing in this
    package normalizes a measurement for temperature or humidity.
    """

    temp_c: float | None = None
    rh_pct: float | None = None
    specimen_moisture_pct: float | None = None
    ambient_noise_note: str | None = None

    @property
    def is_fully_unknown(self) -> bool:
        return all(
            value is None
            for value in (
                self.temp_c,
                self.rh_pct,
                self.specimen_moisture_pct,
                self.ambient_noise_note,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "temp_c": self.temp_c,
            "rh_pct": self.rh_pct,
            "specimen_moisture_pct": self.specimen_moisture_pct,
            "ambient_noise_note": self.ambient_noise_note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> EnvironmentalContextV1:
        if payload is None:
            return cls()
        record = "EnvironmentalContextV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            ("temp_c", "rh_pct", "specimen_moisture_pct", "ambient_noise_note"),
            record=record,
            error=err,
            code=code,
        )
        return cls(
            temp_c=_optional_number(
                payload, "temp_c", record=record, error=err, code=code
            ),
            rh_pct=_optional_number(
                payload, "rh_pct", record=record, error=err, code=code
            ),
            specimen_moisture_pct=_optional_number(
                payload, "specimen_moisture_pct", record=record, error=err, code=code
            ),
            ambient_noise_note=_optional_text(
                payload, "ambient_noise_note", record=record, error=err, code=code
            ),
        )


@dataclass(frozen=True)
class ExcitationContextV1:
    """The mechanical excitation arrangement, recorded generically.

    ``manual_tap`` is one permitted ``excitation_method`` among several and is
    deliberately not privileged as the canonical method. A driven source records
    its signal specification in the existing ``ExcitationContractV1`` and links
    to it here through ``excitation_contract_id``; this record describes the
    physical arrangement that contract says nothing about.
    """

    excitation_method: str = "unspecified"
    excitation_device_id: str | None = None
    excitation_point: str | None = None
    contact_condition: str | None = None
    fixture_id: str | None = None
    excitation_contract_id: str | None = None
    stinger_id: str | None = None
    contact_tip_id: str | None = None
    rig_configuration_id: str | None = None

    @property
    def is_known_method(self) -> bool:
        return self.excitation_method in KNOWN_EXCITATION_METHODS

    @property
    def rig_identity(self) -> dict[str, str | None]:
        """The DO-103 §4.8 rig parts, for reporting which are identified.

        The rig is part of the measurement instrument, so the parts that can be
        swapped without touching the shaker are named separately: the stinger
        and the contact tip change the mechanical path into the specimen, and
        ``rig_configuration_id`` names the assembled combination. Changing any
        of them is a configuration change, not a repeat.
        """
        return {
            "rig_configuration_id": self.rig_configuration_id,
            "excitation_device_id": self.excitation_device_id,
            "stinger_id": self.stinger_id,
            "contact_tip_id": self.contact_tip_id,
            "fixture_id": self.fixture_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "excitation_method": self.excitation_method,
            "excitation_device_id": self.excitation_device_id,
            "excitation_point": self.excitation_point,
            "contact_condition": self.contact_condition,
            "fixture_id": self.fixture_id,
            "excitation_contract_id": self.excitation_contract_id,
            "stinger_id": self.stinger_id,
            "contact_tip_id": self.contact_tip_id,
            "rig_configuration_id": self.rig_configuration_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> ExcitationContextV1:
        if payload is None:
            return cls()
        record = "ExcitationContextV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "excitation_method",
                "excitation_device_id",
                "excitation_point",
                "contact_condition",
                "fixture_id",
                "excitation_contract_id",
                "stinger_id",
                "contact_tip_id",
                "rig_configuration_id",
            ),
            record=record,
            error=err,
            code=code,
        )
        return cls(
            excitation_method=_require_text(
                payload, "excitation_method", record=record, error=err, code=code
            ),
            excitation_device_id=_optional_text(
                payload, "excitation_device_id", record=record, error=err, code=code
            ),
            excitation_point=_optional_text(
                payload, "excitation_point", record=record, error=err, code=code
            ),
            contact_condition=_optional_text(
                payload, "contact_condition", record=record, error=err, code=code
            ),
            fixture_id=_optional_text(
                payload, "fixture_id", record=record, error=err, code=code
            ),
            excitation_contract_id=_optional_text(
                payload, "excitation_contract_id", record=record, error=err, code=code
            ),
            stinger_id=_optional_text(
                payload, "stinger_id", record=record, error=err, code=code
            ),
            contact_tip_id=_optional_text(
                payload, "contact_tip_id", record=record, error=err, code=code
            ),
            rig_configuration_id=_optional_text(
                payload, "rig_configuration_id", record=record, error=err, code=code
            ),
        )


@dataclass(frozen=True)
class PreliminaryExperimentDefinitionV1:
    """One bounded repeatability experiment: one instrument, one point."""

    experiment_id: str
    instrument_id: str
    measurement_point_id: str
    operator_id: str
    planned_repeat_count: int
    created_at: str
    analysis_profile: str = "phase1_tap_analysis_v1"
    excitation: ExcitationContextV1 = field(default_factory=ExcitationContextV1)
    sensor_position: str | None = None
    support_condition: str | None = None
    environmental_context: EnvironmentalContextV1 = field(
        default_factory=EnvironmentalContextV1
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "instrument_id": self.instrument_id,
            "measurement_point_id": self.measurement_point_id,
            "operator_id": self.operator_id,
            "planned_repeat_count": self.planned_repeat_count,
            "created_at": self.created_at,
            "analysis_profile": self.analysis_profile,
            "excitation": self.excitation.to_dict(),
            "sensor_position": self.sensor_position,
            "support_condition": self.support_condition,
            "environmental_context": self.environmental_context.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PreliminaryExperimentDefinitionV1:
        record = "PreliminaryExperimentDefinitionV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "experiment_id",
                "instrument_id",
                "measurement_point_id",
                "operator_id",
                "planned_repeat_count",
                "created_at",
                "analysis_profile",
                "excitation",
                "sensor_position",
                "support_condition",
                "environmental_context",
            ),
            record=record,
            error=err,
            code=code,
        )
        repeats = payload.get("planned_repeat_count")
        if isinstance(repeats, bool) or not isinstance(repeats, int):
            raise err(
                code,
                f"{record}.planned_repeat_count must be an integer",
                {"record": record},
            )
        return cls(
            experiment_id=_require_text(
                payload, "experiment_id", record=record, error=err, code=code
            ),
            instrument_id=_require_text(
                payload, "instrument_id", record=record, error=err, code=code
            ),
            measurement_point_id=_require_text(
                payload, "measurement_point_id", record=record, error=err, code=code
            ),
            operator_id=_require_text(
                payload, "operator_id", record=record, error=err, code=code
            ),
            planned_repeat_count=repeats,
            created_at=require_utc_timestamp(
                payload.get("created_at"), record=record, field_name="created_at"
            ),
            analysis_profile=_require_text(
                payload, "analysis_profile", record=record, error=err, code=code
            ),
            excitation=ExcitationContextV1.from_dict(payload.get("excitation")),
            sensor_position=_optional_text(
                payload, "sensor_position", record=record, error=err, code=code
            ),
            support_condition=_optional_text(
                payload, "support_condition", record=record, error=err, code=code
            ),
            environmental_context=EnvironmentalContextV1.from_dict(
                payload.get("environmental_context")
            ),
        )


# ---------------------------------------------------------------------------
# Acquisition provenance (DO-103 §5.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionChannelV1:
    """One recorded channel: what it carried, and what sensed it.

    The channel's ``quantity`` and ``unit`` are what make a transfer function's
    own units derivable rather than assumed. A microphone response over a
    measured force is ``Pa/N``; the same arithmetic over two microphones is a
    ratio and nothing more. Recording the pair keeps that difference in the data
    instead of only in the prose (DO-103 §6.6).
    """

    channel_index: int
    role: AcquisitionRole
    quantity: str
    unit: str
    sensor_id: str
    gain_setting: str | None = None
    sensitivity_value: float | None = None
    sensitivity_unit: str | None = None
    calibration_traceability: CalibrationTraceability = CalibrationTraceability.UNKNOWN
    calibration_reference: str | None = None

    @property
    def is_known_quantity(self) -> bool:
        return self.quantity in KNOWN_ACQUISITION_QUANTITIES

    @property
    def sensitivity_is_recorded(self) -> bool:
        """Whether both the sensitivity number and its unit were supplied.

        The unit travels with the number and is never assumed. DO-103 §4.2 does
        not fix a sensor or its units in advance, so a force transducer's
        sensitivity is recorded in whatever the chosen device states it in
        rather than coerced into a unit this repository picked first.
        """
        return self.sensitivity_value is not None and bool(self.sensitivity_unit)

    @property
    def claims_traceability(self) -> bool:
        return self.calibration_traceability is CalibrationTraceability.TRACEABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_index": self.channel_index,
            "role": self.role.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "sensor_id": self.sensor_id,
            "gain_setting": self.gain_setting,
            "sensitivity_value": self.sensitivity_value,
            "sensitivity_unit": self.sensitivity_unit,
            "calibration_traceability": self.calibration_traceability.value,
            "calibration_reference": self.calibration_reference,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AcquisitionChannelV1:
        record = "AcquisitionChannelV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "channel_index",
                "role",
                "quantity",
                "unit",
                "sensor_id",
                "gain_setting",
                "sensitivity_value",
                "sensitivity_unit",
                "calibration_traceability",
                "calibration_reference",
            ),
            record=record,
            error=err,
            code=code,
        )
        index = payload.get("channel_index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise err(
                code,
                f"{record}.channel_index must be a non-negative integer",
                {"record": record},
            )
        return cls(
            channel_index=index,
            role=_require_enum(
                payload,
                "role",
                AcquisitionRole,
                record=record,
                error=err,
                code=code,
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            sensor_id=_require_text(
                payload, "sensor_id", record=record, error=err, code=code
            ),
            gain_setting=_optional_text(
                payload, "gain_setting", record=record, error=err, code=code
            ),
            sensitivity_value=_optional_number(
                payload, "sensitivity_value", record=record, error=err, code=code
            ),
            sensitivity_unit=_optional_text(
                payload, "sensitivity_unit", record=record, error=err, code=code
            ),
            calibration_traceability=_enum_with_default(
                payload,
                "calibration_traceability",
                CalibrationTraceability,
                CalibrationTraceability.UNKNOWN,
                record=record,
                error=err,
                code=code,
            ),
            calibration_reference=_optional_text(
                payload, "calibration_reference", record=record, error=err, code=code
            ),
        )


@dataclass(frozen=True)
class AcquisitionProvenanceV1:
    """What a physical acquisition session recorded about itself.

    DO-103 §5.4 makes the ``HARDWARE`` claim *derived* rather than declared: a
    run may not become hardware evidence because a caller chose the label. This
    record carries what a physical session can attest that a fixture or a
    generator cannot — the instruments, the acquisition configuration, the
    session identity, and the channel roles — and
    :func:`~.validation.validate_run_acquisition_provenance` refuses a
    ``HARDWARE`` origin that is not backed by it.

    ``witnessed_by`` is the stricter of the two standards DO-103 §5.4 defines.
    Hardware origin says the data came off physical instruments. A witnessed
    session says the provenance is recorded, retained, and attributable to
    someone. Every witnessed run is hardware-origin; the reverse does not hold,
    and §10 promotes a capability only on the stricter one.
    """

    session_id: str
    acquisition_id: str
    interface_id: str
    sample_rate_hz: int
    channels: tuple[AcquisitionChannelV1, ...] = ()
    excitation_device_id: str | None = None
    drive_parameters: str | None = None
    raw_artifact_ids: tuple[str, ...] = ()
    witnessed_by: str | None = None

    def channels_for(self, role: AcquisitionRole) -> tuple[AcquisitionChannelV1, ...]:
        return tuple(channel for channel in self.channels if channel.role is role)

    @property
    def excitation_channel(self) -> AcquisitionChannelV1 | None:
        """The single excitation channel, or ``None`` if there is not exactly one."""
        found = self.channels_for(AcquisitionRole.EXCITATION)
        return found[0] if len(found) == 1 else None

    @property
    def response_channel(self) -> AcquisitionChannelV1 | None:
        """The single response channel, or ``None`` if there is not exactly one."""
        found = self.channels_for(AcquisitionRole.RESPONSE)
        return found[0] if len(found) == 1 else None

    @property
    def transfer_unit(self) -> str | None:
        """Units of response over excitation, derived from the channels.

        ``None`` when the pair is not unambiguous. The unit is never assumed: a
        microphone over a force transducer yields ``Pa/N`` because that is what
        the two channels say they carried, not because this campaign expects it.
        """
        excitation = self.excitation_channel
        response = self.response_channel
        if excitation is None or response is None:
            return None
        return f"{response.unit}/{excitation.unit}"

    @property
    def is_witnessed(self) -> bool:
        """Whether this acquisition is attributable to a witness."""
        return bool(self.witnessed_by)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "acquisition_id": self.acquisition_id,
            "interface_id": self.interface_id,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": [channel.to_dict() for channel in self.channels],
            "excitation_device_id": self.excitation_device_id,
            "drive_parameters": self.drive_parameters,
            "raw_artifact_ids": list(self.raw_artifact_ids),
            "witnessed_by": self.witnessed_by,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any] | None
    ) -> AcquisitionProvenanceV1 | None:
        if payload is None:
            return None
        record = "AcquisitionProvenanceV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "session_id",
                "acquisition_id",
                "interface_id",
                "sample_rate_hz",
                "channels",
                "excitation_device_id",
                "drive_parameters",
                "raw_artifact_ids",
                "witnessed_by",
            ),
            record=record,
            error=err,
            code=code,
        )
        rate = payload.get("sample_rate_hz")
        if isinstance(rate, bool) or not isinstance(rate, int) or rate <= 0:
            raise err(
                code,
                f"{record}.sample_rate_hz must be a positive integer",
                {"record": record},
            )
        raw_channels = payload.get("channels", ())
        if isinstance(raw_channels, (str, bytes)) or not isinstance(
            raw_channels, Sequence
        ):
            raise err(code, f"{record}.channels must be an array", {"record": record})
        return cls(
            session_id=_require_text(
                payload, "session_id", record=record, error=err, code=code
            ),
            acquisition_id=_require_text(
                payload, "acquisition_id", record=record, error=err, code=code
            ),
            interface_id=_require_text(
                payload, "interface_id", record=record, error=err, code=code
            ),
            sample_rate_hz=rate,
            channels=tuple(
                AcquisitionChannelV1.from_dict(item) for item in raw_channels
            ),
            excitation_device_id=_optional_text(
                payload, "excitation_device_id", record=record, error=err, code=code
            ),
            drive_parameters=_optional_text(
                payload, "drive_parameters", record=record, error=err, code=code
            ),
            raw_artifact_ids=_text_tuple(
                payload, "raw_artifact_ids", record=record, error=err, code=code
            ),
            witnessed_by=_optional_text(
                payload, "witnessed_by", record=record, error=err, code=code
            ),
        )


# ---------------------------------------------------------------------------
# Campaign condition (DO-103 §7, §9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignConditionV1:
    """The physical state one campaign run was captured under.

    DO-103 §9 says plainly that the DO-102 evidence container was shaped for one
    experiment design — one instrument, one point, repeated captures — and that
    E1, E4, and E5 strain that shape. The ruling there is to keep the container
    and add fields where one genuinely cannot carry the meaning, never to
    overload an existing field into meaning something new. This record is that
    addition, and it is the whole of it.

    What it carries is *state*, not measurement and not judgement: which of the
    five experiments a run belongs to, whether the stinger was detached between
    two runs, which pair of points a reciprocity direction used, and what mass
    was actually on the specimen. Everything a reader needs to group runs
    correctly, and nothing that grades them.

    Three fields exist for reasons worth stating.

    ``contact_configuration_id`` identifies one uninterrupted attachment. Two
    runs sharing it were captured without breaking contact; two runs with
    different values were not. E3 is exactly the question of how much that
    difference costs, and it cannot be asked of runs that do not record it.

    ``drive_point_id`` and ``response_point_id`` exist because
    ``measurement_point_id`` is singular and a reciprocity run is
    drive-at-A/measure-at-B (§9). Recording the pair here leaves the singular
    field meaning what it always meant.

    ``added_mass_g`` is the *measured* mass. ``nominal_added_mass_g`` is what was
    intended. DO-103 §4.7 forbids the nominal value standing in for the measured
    one, so they are separate fields and every comparison is computed from the
    measured one.
    """

    experiment_kind: ExperimentKind
    contact_configuration_id: str | None = None
    drive_point_id: str | None = None
    response_point_id: str | None = None
    mass_challenge_id: str | None = None
    added_mass_g: float | None = None
    nominal_added_mass_g: float | None = None
    mass_location_id: str | None = None
    note: str | None = None

    @property
    def is_mass_baseline(self) -> bool:
        """Whether this run carried no added mass, as measured.

        ``None`` is not zero: an unrecorded mass is unknown, and treating it as
        a baseline would let an unmeasured run anchor every comparison drawn
        against it.
        """
        return self.added_mass_g == 0.0

    @property
    def point_pair(self) -> tuple[str, str] | None:
        """The ordered drive/response pair, or ``None`` if either is unrecorded."""
        if self.drive_point_id is None or self.response_point_id is None:
            return None
        return (self.drive_point_id, self.response_point_id)

    def is_transpose_of(self, other: CampaignConditionV1) -> bool:
        """Whether ``other`` drives where this measures, and measures where it drives.

        A reciprocity pair is a transpose and nothing looser. Two runs at the
        same pair in the same direction are repeats, and a pair sharing only one
        point is a different measurement altogether.
        """
        mine = self.point_pair
        theirs = other.point_pair
        if mine is None or theirs is None:
            return False
        return mine == (theirs[1], theirs[0]) and mine[0] != mine[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_kind": self.experiment_kind.value,
            "contact_configuration_id": self.contact_configuration_id,
            "drive_point_id": self.drive_point_id,
            "response_point_id": self.response_point_id,
            "mass_challenge_id": self.mass_challenge_id,
            "added_mass_g": self.added_mass_g,
            "nominal_added_mass_g": self.nominal_added_mass_g,
            "mass_location_id": self.mass_location_id,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> CampaignConditionV1 | None:
        if payload is None:
            return None
        record = "CampaignConditionV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "experiment_kind",
                "contact_configuration_id",
                "drive_point_id",
                "response_point_id",
                "mass_challenge_id",
                "added_mass_g",
                "nominal_added_mass_g",
                "mass_location_id",
                "note",
            ),
            record=record,
            error=err,
            code=code,
        )
        return cls(
            experiment_kind=_require_enum(
                payload,
                "experiment_kind",
                ExperimentKind,
                record=record,
                error=err,
                code=code,
            ),
            contact_configuration_id=_optional_text(
                payload, "contact_configuration_id", record=record, error=err, code=code
            ),
            drive_point_id=_optional_text(
                payload, "drive_point_id", record=record, error=err, code=code
            ),
            response_point_id=_optional_text(
                payload, "response_point_id", record=record, error=err, code=code
            ),
            mass_challenge_id=_optional_text(
                payload, "mass_challenge_id", record=record, error=err, code=code
            ),
            added_mass_g=_optional_number(
                payload, "added_mass_g", record=record, error=err, code=code
            ),
            nominal_added_mass_g=_optional_number(
                payload, "nominal_added_mass_g", record=record, error=err, code=code
            ),
            mass_location_id=_optional_text(
                payload, "mass_location_id", record=record, error=err, code=code
            ),
            note=_optional_text(payload, "note", record=record, error=err, code=code),
        )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservedFeatureV1:
    """One quantity read out of one run.

    Named a *feature*, not a mode: DO-102 §4.8 treats extracted peaks as
    spectral feature candidates unless a stronger validated semantic contract
    exists, and none does.
    """

    quantity: str
    unit: str
    value: float

    def to_dict(self) -> dict[str, Any]:
        return {"quantity": self.quantity, "unit": self.unit, "value": self.value}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ObservedFeatureV1:
        record = "ObservedFeatureV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload, ("quantity", "unit", "value"), record=record, error=err, code=code
        )
        value = _optional_number(payload, "value", record=record, error=err, code=code)
        if value is None:
            raise err(
                code,
                f"{record}.value is required",
                {"record": record, "field": "value"},
            )
        return cls(
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            value=value,
        )


@dataclass(frozen=True)
class PreliminaryExperimentRunV1:
    """One capture attempt, valid or rejected.

    A rejected run keeps its identity, its source artifacts, and its conditions.
    It is excluded from the numerical summary and included in the accounting.
    """

    run_id: str
    experiment_id: str
    captured_at: str
    evidence_origin: EvidenceOrigin
    valid: bool = True
    source_artifact_ids: tuple[str, ...] = ()
    measurement_result_id: str | None = None
    rejection_reason: RejectionReason | None = None
    observed_features: tuple[ObservedFeatureV1, ...] = ()
    conditions: EnvironmentalContextV1 = field(default_factory=EnvironmentalContextV1)
    acquisition: AcquisitionProvenanceV1 | None = None
    campaign_condition: CampaignConditionV1 | None = None

    @property
    def experiment_kind(self) -> ExperimentKind | None:
        """Which characterization experiment this run belongs to, if it says."""
        if self.campaign_condition is None:
            return None
        return self.campaign_condition.experiment_kind

    @property
    def is_witnessed_hardware(self) -> bool:
        """Hardware origin *and* an attributable acquisition (DO-103 §5.4).

        The two standards are deliberately separate. This property answers the
        stricter one, which is what §10 requires before a capability may be
        promoted off ``NOT_VERIFIED_ON_HARDWARE``.
        """
        return (
            self.evidence_origin is EvidenceOrigin.HARDWARE
            and self.acquisition is not None
            and self.acquisition.is_witnessed
        )

    def feature(self, quantity: str) -> ObservedFeatureV1 | None:
        """Return the observed feature for ``quantity``, or ``None``."""
        for observed in self.observed_features:
            if observed.quantity == quantity:
                return observed
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "captured_at": self.captured_at,
            "evidence_origin": self.evidence_origin.value,
            "valid": self.valid,
            "source_artifact_ids": list(self.source_artifact_ids),
            "measurement_result_id": self.measurement_result_id,
            "rejection_reason": (
                self.rejection_reason.value if self.rejection_reason else None
            ),
            "observed_features": [f.to_dict() for f in self.observed_features],
            "conditions": self.conditions.to_dict(),
            "acquisition": (
                self.acquisition.to_dict() if self.acquisition is not None else None
            ),
            "campaign_condition": (
                self.campaign_condition.to_dict()
                if self.campaign_condition is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PreliminaryExperimentRunV1:
        record = "PreliminaryExperimentRunV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "run_id",
                "experiment_id",
                "captured_at",
                "evidence_origin",
                "valid",
                "source_artifact_ids",
                "measurement_result_id",
                "rejection_reason",
                "observed_features",
                "conditions",
                "acquisition",
                "campaign_condition",
            ),
            record=record,
            error=err,
            code=code,
        )
        valid = payload.get("valid", True)
        if not isinstance(valid, bool):
            raise err(code, f"{record}.valid must be a boolean", {"record": record})

        raw_reason = payload.get("rejection_reason")
        reason: RejectionReason | None = None
        if raw_reason is not None:
            try:
                reason = RejectionReason(raw_reason)
            except ValueError as exc:
                raise err(
                    GrantReadinessErrorCode.INVALID_REJECTION_REASON,
                    f"{record}.rejection_reason is not a known reason: {raw_reason!r}",
                    {
                        "record": record,
                        "permitted": [m.value for m in RejectionReason],
                    },
                ) from exc

        raw_features = payload.get("observed_features", ())
        if isinstance(raw_features, (str, bytes)) or not isinstance(
            raw_features, Sequence
        ):
            raise err(
                code, f"{record}.observed_features must be an array", {"record": record}
            )

        return cls(
            run_id=_require_text(
                payload, "run_id", record=record, error=err, code=code
            ),
            experiment_id=_require_text(
                payload, "experiment_id", record=record, error=err, code=code
            ),
            captured_at=require_utc_timestamp(
                payload.get("captured_at"), record=record, field_name="captured_at"
            ),
            evidence_origin=_require_enum(
                payload,
                "evidence_origin",
                EvidenceOrigin,
                record=record,
                error=err,
                code=GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
            ),
            valid=valid,
            source_artifact_ids=_text_tuple(
                payload, "source_artifact_ids", record=record, error=err, code=code
            ),
            measurement_result_id=_optional_text(
                payload, "measurement_result_id", record=record, error=err, code=code
            ),
            rejection_reason=reason,
            observed_features=tuple(
                ObservedFeatureV1.from_dict(item) for item in raw_features
            ),
            conditions=EnvironmentalContextV1.from_dict(payload.get("conditions")),
            acquisition=AcquisitionProvenanceV1.from_dict(payload.get("acquisition")),
            campaign_condition=CampaignConditionV1.from_dict(
                payload.get("campaign_condition")
            ),
        )


# ---------------------------------------------------------------------------
# Metrics and study
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepeatabilityMetricV1:
    """Descriptive spread of one quantity across the valid runs of one study.

    There is deliberately no acceptance flag and no threshold. This record says
    how much repeated observations varied under the recorded conditions; it says
    nothing about agreement with a reference, which has not been established.

    ``range_value`` carries what DO-102 §5 calls ``range``. The repository's own
    :class:`tap_tone_pi.core.statistics.RepeatabilityMetrics` already uses
    ``range_value``, and matching the neighbour beats matching the handoff's
    prose while shadowing a builtin.
    """

    metric_id: str
    quantity: str
    unit: str
    sample_count: int
    mean: float
    median: float
    standard_deviation: float
    coefficient_of_variation_pct: float
    minimum: float
    maximum: float
    range_value: float
    median_absolute_deviation: float
    source_run_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "sample_count": self.sample_count,
            "mean": self.mean,
            "median": self.median,
            "standard_deviation": self.standard_deviation,
            "coefficient_of_variation_pct": self.coefficient_of_variation_pct,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "range_value": self.range_value,
            "median_absolute_deviation": self.median_absolute_deviation,
            "source_run_ids": list(self.source_run_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepeatabilityMetricV1:
        record = "RepeatabilityMetricV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.NON_FINITE_STATISTIC
        numeric_fields = (
            "mean",
            "median",
            "standard_deviation",
            "coefficient_of_variation_pct",
            "minimum",
            "maximum",
            "range_value",
            "median_absolute_deviation",
        )
        _reject_unknown_keys(
            payload,
            ("metric_id", "quantity", "unit", "sample_count", "source_run_ids")
            + numeric_fields,
            record=record,
            error=err,
            code=code,
        )
        sample_count = payload.get("sample_count")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int):
            raise err(
                GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                f"{record}.sample_count must be an integer",
                {"record": record},
            )
        numbers: dict[str, float] = {}
        for name in numeric_fields:
            value = _optional_number(payload, name, record=record, error=err, code=code)
            if value is None:
                raise err(
                    code,
                    f"{record}.{name} is required",
                    {"record": record, "field": name},
                )
            numbers[name] = value
        return cls(
            metric_id=_require_text(
                payload, "metric_id", record=record, error=err, code=code
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            sample_count=sample_count,
            source_run_ids=_text_tuple(
                payload, "source_run_ids", record=record, error=err, code=code
            ),
            **numbers,
        )


@dataclass(frozen=True)
class RepeatabilityStudyV1:
    """One preliminary repeatability study: definition, runs, metrics, limits.

    ``referenced_repeatability_evidence_ids`` cross-references any DO-085
    :class:`~tap_tone_pi.core.repeatability.RepeatabilityEvidenceV1` covering the
    same runs. The reference is informational — this record serializes and
    validates without it, and never inherits that record's acceptance gate.
    """

    study_id: str
    experiment_definition: PreliminaryExperimentDefinitionV1
    generated_at: str
    evidence_origin: EvidenceOrigin
    runs: tuple[PreliminaryExperimentRunV1, ...] = ()
    metrics: tuple[RepeatabilityMetricV1, ...] = ()
    limitations: tuple[str, ...] = ()
    referenced_repeatability_evidence_ids: tuple[str, ...] = ()
    schema_version: str = field(default=STUDY_SCHEMA_VERSION, init=False)

    @property
    def valid_run_count(self) -> int:
        return sum(1 for run in self.runs if run.valid)

    @property
    def rejected_run_count(self) -> int:
        return sum(1 for run in self.runs if not run.valid)

    @property
    def rejection_counts(self) -> dict[str, int]:
        """Rejected-run count per reason, with every reason present as a key."""
        counts = {member.value: 0 for member in RejectionReason}
        for run in self.runs:
            if not run.valid and run.rejection_reason is not None:
                counts[run.rejection_reason.value] += 1
        return counts

    @property
    def is_hardware_evidence(self) -> bool:
        return self.evidence_origin.is_hardware_evidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "generated_at": self.generated_at,
            "evidence_origin": self.evidence_origin.value,
            "experiment_definition": self.experiment_definition.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "valid_run_count": self.valid_run_count,
            "rejected_run_count": self.rejected_run_count,
            "rejection_counts": self.rejection_counts,
            "limitations": list(self.limitations),
            "referenced_repeatability_evidence_ids": list(
                self.referenced_repeatability_evidence_ids
            ),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepeatabilityStudyV1:
        record = "RepeatabilityStudyV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "schema_version",
                "study_id",
                "generated_at",
                "evidence_origin",
                "experiment_definition",
                "runs",
                "metrics",
                "valid_run_count",
                "rejected_run_count",
                "rejection_counts",
                "limitations",
                "referenced_repeatability_evidence_ids",
            ),
            record=record,
            error=err,
            code=code,
        )
        declared = payload.get("schema_version", STUDY_SCHEMA_VERSION)
        if declared != STUDY_SCHEMA_VERSION:
            raise err(
                code,
                f"{record}.schema_version must be {STUDY_SCHEMA_VERSION!r}",
                {"record": record, "schema_version": declared},
            )
        definition = payload.get("experiment_definition")
        if not isinstance(definition, Mapping):
            raise err(
                code,
                f"{record}.experiment_definition must be an object",
                {"record": record},
            )
        raw_runs = payload.get("runs", ())
        raw_metrics = payload.get("metrics", ())
        for name, raw in (("runs", raw_runs), ("metrics", raw_metrics)):
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
                raise err(code, f"{record}.{name} must be an array", {"record": record})
        study = cls(
            study_id=_require_text(
                payload, "study_id", record=record, error=err, code=code
            ),
            experiment_definition=PreliminaryExperimentDefinitionV1.from_dict(
                definition
            ),
            generated_at=require_utc_timestamp(
                payload.get("generated_at"), record=record, field_name="generated_at"
            ),
            evidence_origin=_require_enum(
                payload,
                "evidence_origin",
                EvidenceOrigin,
                record=record,
                error=err,
                code=GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
            ),
            runs=tuple(PreliminaryExperimentRunV1.from_dict(r) for r in raw_runs),
            metrics=tuple(RepeatabilityMetricV1.from_dict(m) for m in raw_metrics),
            limitations=_text_tuple(
                payload, "limitations", record=record, error=err, code=code
            ),
            referenced_repeatability_evidence_ids=_text_tuple(
                payload,
                "referenced_repeatability_evidence_ids",
                record=record,
                error=err,
                code=code,
            ),
        )
        # The run counts are derived from ``runs`` and emitted by ``to_dict`` for
        # readers. They round-trip trivially, but if a persisted payload carries
        # values that contradict its own runs the document is internally
        # inconsistent and must not deserialize silently into an object whose
        # counts disagree with the source it was read from.
        for name, derived in (
            ("valid_run_count", study.valid_run_count),
            ("rejected_run_count", study.rejected_run_count),
            ("rejection_counts", study.rejection_counts),
        ):
            if name in payload and payload[name] != derived:
                raise err(
                    code,
                    (
                        f"{record}.{name} {payload[name]!r} disagrees with the "
                        f"runs (derived {derived!r})"
                    ),
                    {"record": record, "field": name},
                )
        return study


# ---------------------------------------------------------------------------
# Risks and reference validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TechnicalRiskV1:
    """One unresolved technical question and how Phase I would settle it."""

    risk_id: str
    title: str
    current_evidence: str
    unresolved_question: str
    phase_i_relevance: str
    proposed_validation_method: str
    status: RiskStatus = RiskStatus.OPEN

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "title": self.title,
            "current_evidence": self.current_evidence,
            "unresolved_question": self.unresolved_question,
            "phase_i_relevance": self.phase_i_relevance,
            "proposed_validation_method": self.proposed_validation_method,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TechnicalRiskV1:
        record = "TechnicalRiskV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        text_fields = (
            "risk_id",
            "title",
            "current_evidence",
            "unresolved_question",
            "phase_i_relevance",
            "proposed_validation_method",
        )
        _reject_unknown_keys(
            payload, text_fields + ("status",), record=record, error=err, code=code
        )
        values = {
            name: _require_text(payload, name, record=record, error=err, code=code)
            for name in text_fields
        }
        return cls(
            status=_require_enum(
                payload, "status", RiskStatus, record=record, error=err, code=code
            ),
            **values,
        )


@dataclass(frozen=True)
class ReferenceMethodV1:
    """One prospective comparison method. Unknown partners stay ``TBD``."""

    method: str
    measurement_compared: str
    access_status: str
    potential_partner: str = "TBD"
    required_preparation: str = "TBD"
    phase_i_role: str = "TBD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "measurement_compared": self.measurement_compared,
            "access_status": self.access_status,
            "potential_partner": self.potential_partner,
            "required_preparation": self.required_preparation,
            "phase_i_role": self.phase_i_role,
        }


@dataclass(frozen=True)
class ReferenceValidationPlanV1:
    """Prospective comparison pathways. No comparison has been performed."""

    plan_id: str
    generated_at: str
    methods: tuple[ReferenceMethodV1, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "generated_at": self.generated_at,
            "methods": [m.to_dict() for m in self.methods],
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Hardware campaign (DO-103 §7, §9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupSpreadV1:
    """Descriptive spread of one quantity across *groups* rather than runs.

    :class:`RepeatabilityMetricV1` summarizes repeated observations, and each of
    its samples is a run. Between-attachment variation is a different question:
    each sample is one attachment, represented by that attachment's own mean.
    Reusing the run-level record for it would make ``source_run_ids`` name
    things that are not runs, which is exactly the overloading DO-103 §9
    forbids — so the group-level summary gets its own record and says what its
    samples are.

    Like its neighbour it carries no acceptance flag and no threshold. It
    reports how much the group means differed, and nothing about whether that
    difference is acceptable.
    """

    group_kind: str
    quantity: str
    unit: str
    group_count: int
    group_ids: tuple[str, ...]
    group_values: tuple[float, ...]
    mean: float
    median: float
    standard_deviation: float
    coefficient_of_variation_pct: float
    minimum: float
    maximum: float
    range_value: float
    median_absolute_deviation: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_kind": self.group_kind,
            "quantity": self.quantity,
            "unit": self.unit,
            "group_count": self.group_count,
            "group_ids": list(self.group_ids),
            "group_values": list(self.group_values),
            "mean": self.mean,
            "median": self.median,
            "standard_deviation": self.standard_deviation,
            "coefficient_of_variation_pct": self.coefficient_of_variation_pct,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "range_value": self.range_value,
            "median_absolute_deviation": self.median_absolute_deviation,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GroupSpreadV1:
        record = "GroupSpreadV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.NON_FINITE_STATISTIC
        numeric_fields = (
            "mean",
            "median",
            "standard_deviation",
            "coefficient_of_variation_pct",
            "minimum",
            "maximum",
            "range_value",
            "median_absolute_deviation",
        )
        _reject_unknown_keys(
            payload,
            (
                "group_kind",
                "quantity",
                "unit",
                "group_count",
                "group_ids",
                "group_values",
            )
            + numeric_fields,
            record=record,
            error=err,
            code=code,
        )
        count = payload.get("group_count")
        if isinstance(count, bool) or not isinstance(count, int):
            raise err(
                GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                f"{record}.group_count must be an integer",
                {"record": record},
            )
        numbers = _required_numbers(
            payload, numeric_fields, record=record, error=err, code=code
        )
        return cls(
            group_kind=_require_text(
                payload, "group_kind", record=record, error=err, code=code
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            group_count=count,
            group_ids=_text_tuple(
                payload, "group_ids", record=record, error=err, code=code
            ),
            group_values=_number_tuple(
                payload, "group_values", record=record, error=err, code=code
            ),
            **numbers,
        )


@dataclass(frozen=True)
class AttachmentVariationV1:
    """How much one quantity moved within an attachment versus between them.

    DO-103 E3 detaches and re-attaches the stinger deliberately, because contact
    variability is a candidate for the largest error term in the whole
    architecture and nothing else in the campaign would expose it. The two
    numbers are kept separate and are never combined into one figure: the
    within-attachment metrics describe repeats that never broke contact, and the
    between-attachment spread describes what remaking the contact did.

    An attachment with fewer than two valid runs is named in
    ``unsummarized_attachment_ids`` rather than dropped. It contributed no
    within-attachment statistic, and saying so is part of the accounting.
    """

    variation_id: str
    quantity: str
    unit: str
    attachment_ids: tuple[str, ...]
    within_attachment_metrics: tuple[RepeatabilityMetricV1, ...] = ()
    between_attachment_spread: GroupSpreadV1 | None = None
    unsummarized_attachment_ids: tuple[str, ...] = ()

    @property
    def attachment_count(self) -> int:
        return len(self.attachment_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variation_id": self.variation_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "attachment_ids": list(self.attachment_ids),
            "attachment_count": self.attachment_count,
            "within_attachment_metrics": [
                metric.to_dict() for metric in self.within_attachment_metrics
            ],
            "between_attachment_spread": (
                self.between_attachment_spread.to_dict()
                if self.between_attachment_spread is not None
                else None
            ),
            "unsummarized_attachment_ids": list(self.unsummarized_attachment_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AttachmentVariationV1:
        record = "AttachmentVariationV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.INVALID_EXPERIMENT_DEFINITION
        _reject_unknown_keys(
            payload,
            (
                "variation_id",
                "quantity",
                "unit",
                "attachment_ids",
                "attachment_count",
                "within_attachment_metrics",
                "between_attachment_spread",
                "unsummarized_attachment_ids",
            ),
            record=record,
            error=err,
            code=code,
        )
        raw_metrics = _sequence(
            payload, "within_attachment_metrics", record=record, error=err, code=code
        )
        spread = payload.get("between_attachment_spread")
        variation = cls(
            variation_id=_require_text(
                payload, "variation_id", record=record, error=err, code=code
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            attachment_ids=_text_tuple(
                payload, "attachment_ids", record=record, error=err, code=code
            ),
            within_attachment_metrics=tuple(
                RepeatabilityMetricV1.from_dict(item) for item in raw_metrics
            ),
            between_attachment_spread=(
                GroupSpreadV1.from_dict(spread) if spread is not None else None
            ),
            unsummarized_attachment_ids=_text_tuple(
                payload,
                "unsummarized_attachment_ids",
                record=record,
                error=err,
                code=code,
            ),
        )
        _reject_derived_disagreement(
            payload,
            {"attachment_count": variation.attachment_count},
            record=record,
            error=err,
            code=code,
        )
        return variation


@dataclass(frozen=True)
class ReciprocityObservationV1:
    """One forward/reverse pair and the residual between them.

    Reciprocity asks whether driving at A and measuring at B agrees with driving
    at B and measuring at A. DO-103 §5.5 and §4.6 make this deliberately
    threshold-free: this record reports the two values, their residual, and the
    coherence each direction was observed with, and it has no pass field, no
    verdict, and no tolerance. A poor result is a finding about the measurement
    architecture, which is the entire reason the experiment exists.

    Both coherences are retained separately. A residual observed where one
    direction had poor coherence means something different from the same
    residual where both were high, and collapsing them into one number would
    destroy exactly that distinction.

    Both evaluation frequencies are retained for the same reason. Each direction
    is its own capture and lands on its own frequency bin, so a residual can span
    two slightly different frequencies. ``frequency_mismatch_hz`` makes that
    visible in the pair record itself rather than leaving a reviewer to open both
    runs and compare. It is a magnitude and carries no limit: DO-103 §4.6 forbids
    this order from deciding how far apart is too far.
    """

    observation_id: str
    quantity: str
    unit: str
    forward_run_id: str
    reverse_run_id: str
    forward_drive_point_id: str
    forward_response_point_id: str
    forward_value: float
    reverse_value: float
    absolute_residual: float
    relative_residual: float | None = None
    forward_evaluation_frequency_hz: float | None = None
    reverse_evaluation_frequency_hz: float | None = None
    forward_coherence: float | None = None
    reverse_coherence: float | None = None

    @property
    def frequency_mismatch_hz(self) -> float | None:
        """How far apart the two directions' bins fell, or ``None`` if unknown.

        Derived, so it cannot disagree with the frequencies it is taken over.
        """
        forward = self.forward_evaluation_frequency_hz
        reverse = self.reverse_evaluation_frequency_hz
        if forward is None or reverse is None:
            return None
        return abs(forward - reverse)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "forward_run_id": self.forward_run_id,
            "reverse_run_id": self.reverse_run_id,
            "forward_drive_point_id": self.forward_drive_point_id,
            "forward_response_point_id": self.forward_response_point_id,
            "forward_value": self.forward_value,
            "reverse_value": self.reverse_value,
            "absolute_residual": self.absolute_residual,
            "relative_residual": self.relative_residual,
            "forward_evaluation_frequency_hz": self.forward_evaluation_frequency_hz,
            "reverse_evaluation_frequency_hz": self.reverse_evaluation_frequency_hz,
            "frequency_mismatch_hz": self.frequency_mismatch_hz,
            "forward_coherence": self.forward_coherence,
            "reverse_coherence": self.reverse_coherence,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReciprocityObservationV1:
        record = "ReciprocityObservationV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.NON_FINITE_STATISTIC
        _reject_unknown_keys(
            payload,
            (
                "observation_id",
                "quantity",
                "unit",
                "forward_run_id",
                "reverse_run_id",
                "forward_drive_point_id",
                "forward_response_point_id",
                "forward_value",
                "reverse_value",
                "absolute_residual",
                "relative_residual",
                "forward_evaluation_frequency_hz",
                "reverse_evaluation_frequency_hz",
                "frequency_mismatch_hz",
                "forward_coherence",
                "reverse_coherence",
            ),
            record=record,
            error=err,
            code=code,
        )
        numbers = _required_numbers(
            payload,
            ("forward_value", "reverse_value", "absolute_residual"),
            record=record,
            error=err,
            code=code,
        )
        observation = cls(
            observation_id=_require_text(
                payload, "observation_id", record=record, error=err, code=code
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            forward_run_id=_require_text(
                payload, "forward_run_id", record=record, error=err, code=code
            ),
            reverse_run_id=_require_text(
                payload, "reverse_run_id", record=record, error=err, code=code
            ),
            forward_drive_point_id=_require_text(
                payload, "forward_drive_point_id", record=record, error=err, code=code
            ),
            forward_response_point_id=_require_text(
                payload,
                "forward_response_point_id",
                record=record,
                error=err,
                code=code,
            ),
            relative_residual=_optional_number(
                payload, "relative_residual", record=record, error=err, code=code
            ),
            forward_evaluation_frequency_hz=_optional_number(
                payload,
                "forward_evaluation_frequency_hz",
                record=record,
                error=err,
                code=code,
            ),
            reverse_evaluation_frequency_hz=_optional_number(
                payload,
                "reverse_evaluation_frequency_hz",
                record=record,
                error=err,
                code=code,
            ),
            forward_coherence=_optional_number(
                payload, "forward_coherence", record=record, error=err, code=code
            ),
            reverse_coherence=_optional_number(
                payload, "reverse_coherence", record=record, error=err, code=code
            ),
            forward_value=numbers["forward_value"],
            reverse_value=numbers["reverse_value"],
            absolute_residual=numbers["absolute_residual"],
        )
        _reject_derived_disagreement(
            payload,
            {"frequency_mismatch_hz": observation.frequency_mismatch_hz},
            record=record,
            error=err,
            code=code,
        )
        return observation


@dataclass(frozen=True)
class MassLoadingObservationV1:
    """How one quantity responded to a known mass deliberately added.

    E5 asks whether the architecture notices a configuration change it was told
    about in advance. The comparison is between summarized groups of runs, not
    between two single captures, so the spread of each group travels with its
    mean and a reader can see whether the difference is larger than the noise
    it sits in.

    ``added_mass_g`` is the measured mass. DO-103 §4.7 forbids a nominal value
    standing in for it, so the nominal figure is recorded beside it and is never
    what the delta is computed from.

    The delta is *signed* on purpose. Which way a quantity moved under added
    mass is physical information, and an absolute value would discard it. It
    remains a description: there is no threshold here, and nothing in this
    record says whether a response of any size is acceptable.
    """

    observation_id: str
    quantity: str
    unit: str
    mass_challenge_id: str
    added_mass_g: float
    baseline_metric: RepeatabilityMetricV1
    loaded_metric: RepeatabilityMetricV1
    absolute_delta: float
    relative_delta_pct: float | None = None
    nominal_added_mass_g: float | None = None
    mass_location_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "mass_challenge_id": self.mass_challenge_id,
            "added_mass_g": self.added_mass_g,
            "nominal_added_mass_g": self.nominal_added_mass_g,
            "mass_location_id": self.mass_location_id,
            "baseline_metric": self.baseline_metric.to_dict(),
            "loaded_metric": self.loaded_metric.to_dict(),
            "absolute_delta": self.absolute_delta,
            "relative_delta_pct": self.relative_delta_pct,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MassLoadingObservationV1:
        record = "MassLoadingObservationV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.NON_FINITE_STATISTIC
        _reject_unknown_keys(
            payload,
            (
                "observation_id",
                "quantity",
                "unit",
                "mass_challenge_id",
                "added_mass_g",
                "nominal_added_mass_g",
                "mass_location_id",
                "baseline_metric",
                "loaded_metric",
                "absolute_delta",
                "relative_delta_pct",
            ),
            record=record,
            error=err,
            code=code,
        )
        numbers = _required_numbers(
            payload,
            ("added_mass_g", "absolute_delta"),
            record=record,
            error=err,
            code=code,
        )

        def group_metric(name: str) -> RepeatabilityMetricV1:
            block = payload.get(name)
            if not isinstance(block, Mapping):
                raise err(
                    GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
                    f"{record}.{name} must be an object",
                    {"record": record, "field": name},
                )
            return RepeatabilityMetricV1.from_dict(block)

        return cls(
            observation_id=_require_text(
                payload, "observation_id", record=record, error=err, code=code
            ),
            quantity=_require_text(
                payload, "quantity", record=record, error=err, code=code
            ),
            unit=_require_text(payload, "unit", record=record, error=err, code=code),
            mass_challenge_id=_require_text(
                payload, "mass_challenge_id", record=record, error=err, code=code
            ),
            relative_delta_pct=_optional_number(
                payload, "relative_delta_pct", record=record, error=err, code=code
            ),
            nominal_added_mass_g=_optional_number(
                payload, "nominal_added_mass_g", record=record, error=err, code=code
            ),
            mass_location_id=_optional_text(
                payload, "mass_location_id", record=record, error=err, code=code
            ),
            baseline_metric=group_metric("baseline_metric"),
            loaded_metric=group_metric("loaded_metric"),
            added_mass_g=numbers["added_mass_g"],
            absolute_delta=numbers["absolute_delta"],
        )


@dataclass(frozen=True)
class ExternalArtifactV1:
    """One raw measurement file that lives outside the repository.

    Raw audio is not committed here, so an evidence reference to it has to
    survive the file moving. The durable identity is therefore the digest: a
    campaign says what the bytes were, what produced them, and where a reader
    may currently find them, in that order of authority. ``local_path_hint``
    records where the file sat on the acquiring workstation and is explicitly
    ephemeral — it is a convenience for the operator, never the identity.

    ``repository_tracked`` is present and defaults to false so a reader never
    has to infer whether a `git checkout` would produce the file.
    """

    artifact_id: str
    kind: str
    sha256: str
    byte_count: int
    media_type: str
    storage_locator: str
    capture_run_id: str | None = None
    repository_tracked: bool = False
    local_path_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "media_type": self.media_type,
            "storage_locator": self.storage_locator,
            "capture_run_id": self.capture_run_id,
            "repository_tracked": self.repository_tracked,
            "local_path_hint": self.local_path_hint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExternalArtifactV1:
        record = "ExternalArtifactV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.ARTIFACT_IDENTITY_INCOMPLETE
        _reject_unknown_keys(
            payload,
            (
                "artifact_id",
                "kind",
                "sha256",
                "byte_count",
                "media_type",
                "storage_locator",
                "capture_run_id",
                "repository_tracked",
                "local_path_hint",
            ),
            record=record,
            error=err,
            code=code,
        )
        byte_count = payload.get("byte_count")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int):
            raise err(
                code,
                f"{record}.byte_count must be an integer",
                {"record": record, "field": "byte_count"},
            )
        tracked = payload.get("repository_tracked", False)
        if not isinstance(tracked, bool):
            raise err(
                code,
                f"{record}.repository_tracked must be a boolean",
                {"record": record, "field": "repository_tracked"},
            )
        return cls(
            artifact_id=_require_text(
                payload, "artifact_id", record=record, error=err, code=code
            ),
            kind=_require_text(payload, "kind", record=record, error=err, code=code),
            sha256=_require_text(
                payload, "sha256", record=record, error=err, code=code
            ),
            byte_count=byte_count,
            media_type=_require_text(
                payload, "media_type", record=record, error=err, code=code
            ),
            storage_locator=_require_text(
                payload, "storage_locator", record=record, error=err, code=code
            ),
            capture_run_id=_optional_text(
                payload, "capture_run_id", record=record, error=err, code=code
            ),
            repository_tracked=tracked,
            local_path_hint=_optional_text(
                payload, "local_path_hint", record=record, error=err, code=code
            ),
        )


@dataclass(frozen=True)
class CampaignExperimentPlanV1:
    """One planned experiment in a campaign, before it is executed.

    ``subject_is_rig`` is how DO-103 §9's E1 ruling is kept honest. E1
    characterizes the rig, not an instrument, and the DO-102 definition requires
    a non-empty ``instrument_id``. Recording the rig there is defensible — it is
    literally what is under test — but only if the record *says* that is what
    happened, which is this flag. A silent substitution is the thing §9 rules
    out.
    """

    experiment_id: str
    kind: ExperimentKind
    instrument_id: str
    measurement_point_id: str
    planned_repeat_count: int
    evaluation_frequency_hz: float | None = None
    subject_is_rig: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "kind": self.kind.value,
            "instrument_id": self.instrument_id,
            "measurement_point_id": self.measurement_point_id,
            "planned_repeat_count": self.planned_repeat_count,
            "evaluation_frequency_hz": self.evaluation_frequency_hz,
            "subject_is_rig": self.subject_is_rig,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CampaignExperimentPlanV1:
        record = "CampaignExperimentPlanV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID
        _reject_unknown_keys(
            payload,
            (
                "experiment_id",
                "kind",
                "instrument_id",
                "measurement_point_id",
                "planned_repeat_count",
                "evaluation_frequency_hz",
                "subject_is_rig",
                "note",
            ),
            record=record,
            error=err,
            code=code,
        )
        repeats = payload.get("planned_repeat_count")
        if isinstance(repeats, bool) or not isinstance(repeats, int):
            raise err(
                code,
                f"{record}.planned_repeat_count must be an integer",
                {"record": record},
            )
        subject_is_rig = payload.get("subject_is_rig", False)
        if not isinstance(subject_is_rig, bool):
            raise err(
                code, f"{record}.subject_is_rig must be a boolean", {"record": record}
            )
        return cls(
            experiment_id=_require_text(
                payload, "experiment_id", record=record, error=err, code=code
            ),
            kind=_require_enum(
                payload, "kind", ExperimentKind, record=record, error=err, code=code
            ),
            instrument_id=_require_text(
                payload, "instrument_id", record=record, error=err, code=code
            ),
            measurement_point_id=_require_text(
                payload, "measurement_point_id", record=record, error=err, code=code
            ),
            planned_repeat_count=repeats,
            evaluation_frequency_hz=_optional_number(
                payload, "evaluation_frequency_hz", record=record, error=err, code=code
            ),
            subject_is_rig=subject_is_rig,
            note=_optional_text(payload, "note", record=record, error=err, code=code),
        )


@dataclass(frozen=True)
class HardwareCampaignConfigV1:
    """The stated configuration a campaign is to be executed under.

    This is an *input* specification, not evidence. It exists so that every
    acquisition command names its rig, its channels, and its experiments
    explicitly: DO-103 §5 forbids an undocumented default acquisition, and a
    campaign whose configuration was implied by a script's defaults could not be
    reproduced or audited afterwards.

    The rig and channel vocabularies are the DO-102 records, unchanged. Nothing
    here introduces a second way to describe an excitation arrangement or an
    acquisition channel.
    """

    campaign_id: str
    created_at: str
    operator_id: str
    interface_id: str
    sample_rate_hz: int
    excitation: ExcitationContextV1 = field(default_factory=ExcitationContextV1)
    support_condition: str | None = None
    channels: tuple[AcquisitionChannelV1, ...] = ()
    environmental_context: EnvironmentalContextV1 = field(
        default_factory=EnvironmentalContextV1
    )
    experiments: tuple[CampaignExperimentPlanV1, ...] = ()
    notes: tuple[str, ...] = ()

    def channels_for(self, role: AcquisitionRole) -> tuple[AcquisitionChannelV1, ...]:
        return tuple(channel for channel in self.channels if channel.role is role)

    @property
    def force_channel(self) -> AcquisitionChannelV1 | None:
        """The single excitation channel that carries a measured force.

        DO-103 §4.2 requires the excitation to be *measured* rather than
        commanded, and ruling 4 of this order's implementation places that
        measurement on the reference channel of the existing two-channel Phase 2
        model. A drive-voltage channel is an excitation channel and is not this.
        """
        for channel in self.channels_for(AcquisitionRole.EXCITATION):
            if channel.quantity == "force":
                return channel
        return None

    def plan_for(self, experiment_id: str) -> CampaignExperimentPlanV1 | None:
        for plan in self.experiments:
            if plan.experiment_id == experiment_id:
                return plan
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "created_at": self.created_at,
            "operator_id": self.operator_id,
            "interface_id": self.interface_id,
            "sample_rate_hz": self.sample_rate_hz,
            "excitation": self.excitation.to_dict(),
            "support_condition": self.support_condition,
            "channels": [channel.to_dict() for channel in self.channels],
            "environmental_context": self.environmental_context.to_dict(),
            "experiments": [plan.to_dict() for plan in self.experiments],
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> HardwareCampaignConfigV1:
        record = "HardwareCampaignConfigV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID
        _reject_unknown_keys(
            payload,
            (
                "campaign_id",
                "created_at",
                "operator_id",
                "interface_id",
                "sample_rate_hz",
                "excitation",
                "support_condition",
                "channels",
                "environmental_context",
                "experiments",
                "notes",
            ),
            record=record,
            error=err,
            code=code,
        )
        rate = payload.get("sample_rate_hz")
        if isinstance(rate, bool) or not isinstance(rate, int) or rate <= 0:
            raise err(
                code,
                f"{record}.sample_rate_hz must be a positive integer",
                {"record": record},
            )
        return cls(
            campaign_id=_require_text(
                payload, "campaign_id", record=record, error=err, code=code
            ),
            created_at=require_utc_timestamp(
                payload.get("created_at"), record=record, field_name="created_at"
            ),
            operator_id=_require_text(
                payload, "operator_id", record=record, error=err, code=code
            ),
            interface_id=_require_text(
                payload, "interface_id", record=record, error=err, code=code
            ),
            sample_rate_hz=rate,
            excitation=ExcitationContextV1.from_dict(payload.get("excitation")),
            support_condition=_optional_text(
                payload, "support_condition", record=record, error=err, code=code
            ),
            channels=tuple(
                AcquisitionChannelV1.from_dict(item)
                for item in _sequence(
                    payload, "channels", record=record, error=err, code=code
                )
            ),
            environmental_context=EnvironmentalContextV1.from_dict(
                payload.get("environmental_context")
            ),
            experiments=tuple(
                CampaignExperimentPlanV1.from_dict(item)
                for item in _sequence(
                    payload, "experiments", record=record, error=err, code=code
                )
            ),
            notes=_text_tuple(payload, "notes", record=record, error=err, code=code),
        )


@dataclass(frozen=True)
class CampaignExperimentOutcomeV1:
    """What became of one planned experiment.

    DO-103 §12 criterion 11 requires an experiment that did not run because an
    earlier gate failed to be recorded as such. A gap in the results is
    ambiguous — abandoned, forgotten, or never reached — and this record removes
    the ambiguity by naming the gate that stopped it.

    ``evidence_origin`` and ``witnessed`` summarize the study this outcome names,
    so a campaign document says what kind of evidence it holds without a reader
    having to open every study to find out. Both are *summaries of a study*, not
    independent claims: they are derived by
    :func:`~.hardware_campaign.build_campaign_outcome` from the study itself, and
    ``scripts/ttp_hardware_campaign_check.py`` re-derives them from the studies
    on disk and reports any disagreement. A summary that could drift from what it
    summarizes would be worse than no summary at all.
    """

    experiment_id: str
    kind: ExperimentKind
    status: ExperimentOutcomeStatus
    study_id: str | None = None
    study_digest: str | None = None
    evidence_origin: EvidenceOrigin | None = None
    witnessed: bool = False
    blocked_by_experiment_id: str | None = None
    note: str | None = None

    @property
    def is_hardware_evidence(self) -> bool:
        """Whether this outcome's study is hardware-origin.

        Hardware origin is the weaker of DO-103 §5.4's two standards; see
        ``witnessed`` for the one §10 promotes on.
        """
        return self.evidence_origin is EvidenceOrigin.HARDWARE

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "study_id": self.study_id,
            "study_digest": self.study_digest,
            "evidence_origin": (
                self.evidence_origin.value if self.evidence_origin else None
            ),
            "witnessed": self.witnessed,
            "blocked_by_experiment_id": self.blocked_by_experiment_id,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CampaignExperimentOutcomeV1:
        record = "CampaignExperimentOutcomeV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID
        _reject_unknown_keys(
            payload,
            (
                "experiment_id",
                "kind",
                "status",
                "study_id",
                "study_digest",
                "evidence_origin",
                "witnessed",
                "blocked_by_experiment_id",
                "note",
            ),
            record=record,
            error=err,
            code=code,
        )
        witnessed = payload.get("witnessed", False)
        if not isinstance(witnessed, bool):
            raise err(code, f"{record}.witnessed must be a boolean", {"record": record})
        origin = payload.get("evidence_origin")
        return cls(
            experiment_id=_require_text(
                payload, "experiment_id", record=record, error=err, code=code
            ),
            kind=_require_enum(
                payload, "kind", ExperimentKind, record=record, error=err, code=code
            ),
            status=_require_enum(
                payload,
                "status",
                ExperimentOutcomeStatus,
                record=record,
                error=err,
                code=code,
            ),
            study_id=_optional_text(
                payload, "study_id", record=record, error=err, code=code
            ),
            study_digest=_optional_text(
                payload, "study_digest", record=record, error=err, code=code
            ),
            evidence_origin=(
                _require_enum(
                    payload,
                    "evidence_origin",
                    EvidenceOrigin,
                    record=record,
                    error=err,
                    code=GrantReadinessErrorCode.EVIDENCE_ORIGIN_MISREPRESENTED,
                )
                if origin is not None
                else None
            ),
            witnessed=witnessed,
            blocked_by_experiment_id=_optional_text(
                payload, "blocked_by_experiment_id", record=record, error=err, code=code
            ),
            note=_optional_text(payload, "note", record=record, error=err, code=code),
        )


@dataclass(frozen=True)
class HardwareCampaignRecordV1:
    """One hardware characterization campaign: configuration, outcome, evidence.

    The campaign record is an index and an accounting, not a second evidence
    model. The measurements themselves stay in ``RepeatabilityStudyV1``
    documents exactly as DO-103 §9 rules; this record names those studies by
    identity and digest, carries the derived observations that no study record
    can hold — reciprocity residuals, mass-loading deltas, between-attachment
    variation — and states what happened to every experiment that was planned.

    A campaign with ``execution_status`` of ``NOT_EXECUTED`` is a legitimate and
    expected document. The software this order builds exists before the rig
    does, and saying so explicitly is the point.
    """

    campaign_id: str
    generated_at: str
    execution_status: CampaignExecutionStatus
    config: HardwareCampaignConfigV1
    outcomes: tuple[CampaignExperimentOutcomeV1, ...] = ()
    artifacts: tuple[ExternalArtifactV1, ...] = ()
    attachment_variation: tuple[AttachmentVariationV1, ...] = ()
    reciprocity: tuple[ReciprocityObservationV1, ...] = ()
    mass_loading: tuple[MassLoadingObservationV1, ...] = ()
    limitations: tuple[str, ...] = ()
    schema_version: str = field(default=CAMPAIGN_SCHEMA_VERSION, init=False)

    @property
    def executed_experiment_ids(self) -> tuple[str, ...]:
        """Experiments that ran, whatever they ran against."""
        return tuple(
            outcome.experiment_id
            for outcome in self.outcomes
            if outcome.status is ExperimentOutcomeStatus.EXECUTED
        )

    @property
    def hardware_experiment_ids(self) -> tuple[str, ...]:
        """Experiments that ran against hardware-origin evidence."""
        return tuple(
            outcome.experiment_id
            for outcome in self.outcomes
            if outcome.status is ExperimentOutcomeStatus.EXECUTED
            and outcome.is_hardware_evidence
        )

    @property
    def witnessed_experiment_ids(self) -> tuple[str, ...]:
        """Experiments whose study met the stricter witnessed standard (§5.4)."""
        return tuple(
            outcome.experiment_id
            for outcome in self.outcomes
            if outcome.status is ExperimentOutcomeStatus.EXECUTED and outcome.witnessed
        )

    @property
    def is_executed(self) -> bool:
        """Whether any experiment in this campaign actually ran."""
        return bool(self.executed_experiment_ids)

    @property
    def is_hardware_evidence(self) -> bool:
        """Whether any experiment ran against hardware.

        Distinct from :attr:`is_executed`, which a fixture rehearsal also
        satisfies. Nothing downstream may read one for the other.
        """
        return bool(self.hardware_experiment_ids)

    def outcome_for(self, experiment_id: str) -> CampaignExperimentOutcomeV1 | None:
        for outcome in self.outcomes:
            if outcome.experiment_id == experiment_id:
                return outcome
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at,
            "execution_status": self.execution_status.value,
            "is_hardware_evidence": self.is_hardware_evidence,
            "config": self.config.to_dict(),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "attachment_variation": [
                variation.to_dict() for variation in self.attachment_variation
            ],
            "reciprocity": [observation.to_dict() for observation in self.reciprocity],
            "mass_loading": [
                observation.to_dict() for observation in self.mass_loading
            ],
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> HardwareCampaignRecordV1:
        record = "HardwareCampaignRecordV1"
        err = ExperimentRecordError
        code = GrantReadinessErrorCode.CAMPAIGN_CONFIGURATION_INVALID
        _reject_unknown_keys(
            payload,
            (
                "schema_version",
                "campaign_id",
                "generated_at",
                "execution_status",
                "is_hardware_evidence",
                "config",
                "outcomes",
                "artifacts",
                "attachment_variation",
                "reciprocity",
                "mass_loading",
                "limitations",
            ),
            record=record,
            error=err,
            code=code,
        )
        declared = payload.get("schema_version", CAMPAIGN_SCHEMA_VERSION)
        if declared != CAMPAIGN_SCHEMA_VERSION:
            raise err(
                code,
                f"{record}.schema_version must be {CAMPAIGN_SCHEMA_VERSION!r}",
                {"record": record, "schema_version": declared},
            )
        config = payload.get("config")
        if not isinstance(config, Mapping):
            raise err(code, f"{record}.config must be an object", {"record": record})
        record_out = cls(
            campaign_id=_require_text(
                payload, "campaign_id", record=record, error=err, code=code
            ),
            generated_at=require_utc_timestamp(
                payload.get("generated_at"), record=record, field_name="generated_at"
            ),
            execution_status=_require_enum(
                payload,
                "execution_status",
                CampaignExecutionStatus,
                record=record,
                error=err,
                code=code,
            ),
            config=HardwareCampaignConfigV1.from_dict(config),
            outcomes=tuple(
                CampaignExperimentOutcomeV1.from_dict(item)
                for item in _sequence(
                    payload, "outcomes", record=record, error=err, code=code
                )
            ),
            artifacts=tuple(
                ExternalArtifactV1.from_dict(item)
                for item in _sequence(
                    payload, "artifacts", record=record, error=err, code=code
                )
            ),
            attachment_variation=tuple(
                AttachmentVariationV1.from_dict(item)
                for item in _sequence(
                    payload, "attachment_variation", record=record, error=err, code=code
                )
            ),
            reciprocity=tuple(
                ReciprocityObservationV1.from_dict(item)
                for item in _sequence(
                    payload, "reciprocity", record=record, error=err, code=code
                )
            ),
            mass_loading=tuple(
                MassLoadingObservationV1.from_dict(item)
                for item in _sequence(
                    payload, "mass_loading", record=record, error=err, code=code
                )
            ),
            limitations=_text_tuple(
                payload, "limitations", record=record, error=err, code=code
            ),
        )
        _reject_derived_disagreement(
            payload,
            {"is_hardware_evidence": record_out.is_hardware_evidence},
            record=record,
            error=err,
            code=code,
        )
        return record_out


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "STUDY_SCHEMA_VERSION",
    "CAMPAIGN_SCHEMA_VERSION",
    "KNOWN_EXCITATION_METHODS",
    "CapabilityStatus",
    "HardwareVerification",
    "EvidenceOrigin",
    "RejectionReason",
    "RiskStatus",
    "CapabilityEvidenceV1",
    "GrantReadinessAuditV1",
    "EnvironmentalContextV1",
    "ExcitationContextV1",
    "PreliminaryExperimentDefinitionV1",
    "ObservedFeatureV1",
    "PreliminaryExperimentRunV1",
    "RepeatabilityMetricV1",
    "RepeatabilityStudyV1",
    "TechnicalRiskV1",
    "ReferenceMethodV1",
    "ReferenceValidationPlanV1",
    "CalibrationTraceability",
    "ExperimentKind",
    "CampaignExecutionStatus",
    "ExperimentOutcomeStatus",
    "CampaignConditionV1",
    "GroupSpreadV1",
    "AttachmentVariationV1",
    "ReciprocityObservationV1",
    "MassLoadingObservationV1",
    "ExternalArtifactV1",
    "CampaignExperimentPlanV1",
    "HardwareCampaignConfigV1",
    "CampaignExperimentOutcomeV1",
    "HardwareCampaignRecordV1",
    "require_utc_timestamp",
]

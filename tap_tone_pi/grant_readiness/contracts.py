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

    @property
    def is_known_method(self) -> bool:
        return self.excitation_method in KNOWN_EXCITATION_METHODS

    def to_dict(self) -> dict[str, Any]:
        return {
            "excitation_method": self.excitation_method,
            "excitation_device_id": self.excitation_device_id,
            "excitation_point": self.excitation_point,
            "contact_condition": self.contact_condition,
            "fixture_id": self.fixture_id,
            "excitation_contract_id": self.excitation_contract_id,
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

    @property
    def is_known_quantity(self) -> bool:
        return self.quantity in KNOWN_ACQUISITION_QUANTITIES

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_index": self.channel_index,
            "role": self.role.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "sensor_id": self.sensor_id,
            "gain_setting": self.gain_setting,
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


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "STUDY_SCHEMA_VERSION",
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
    "require_utc_timestamp",
]

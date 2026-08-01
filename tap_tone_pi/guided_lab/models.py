# INSTRUMENT CLASS: MEASUREMENT
"""Immutable contracts for the guided laboratory (DO-100).

These records describe a *procedure*, not a result. A workflow definition
declares the questions, instructions, and evidence requirements an operator
works through; a session records what the operator supplied and where they
are. Nothing here interprets a measurement, grades an instrument, or
prescribes a modification.

Design rules held by this module:

* every public record is a frozen dataclass with a deterministic ``to_dict()``;
* timestamps are timezone-aware and serialize as UTC ISO 8601 with a ``Z``;
* collections are tuples in memory and lists on the wire;
* optional fields whose value is ``None`` are omitted from serialized output;
* evidence is referenced by logical ID only — no host path may be stored.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence, Union

from tap_tone_pi.guided_lab.errors import (
    GuidedLabActionError,
    GuidedLabErrorCode,
    GuidedLabSessionError,
)

GUIDED_LAB_SESSION_SCHEMA_VERSION = "guided_lab_session_v1"

#: Values an operator may supply as an answer.
AnswerValue = Union[str, bool, int, float]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkflowNodeKind(str, Enum):
    """The kind of step an operator is standing on."""

    QUESTION = "question"
    INSTRUCTION = "instruction"
    EVIDENCE_REQUIREMENT = "evidence_requirement"
    REVIEW = "review"
    COMPLETE = "complete"


class WorkflowAnswerKind(str, Enum):
    """The kind of value a question accepts."""

    SINGLE_CHOICE = "single_choice"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    TEXT = "text"
    MEASUREMENT_REFERENCE = "measurement_reference"


class TransitionConditionKind(str, Enum):
    """The supported ways one step may lead to the next."""

    ALWAYS = "always"
    ANSWER_EQUALS = "answer_equals"
    ANSWER_IN_SET = "answer_in_set"
    BOOLEAN_TRUE = "boolean_true"
    BOOLEAN_FALSE = "boolean_false"
    EVIDENCE_PRESENT = "evidence_present"


class GuidedLabSessionStatus(str, Enum):
    """Lifecycle state of a workflow session."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SourceAuthorityStatus(str, Enum):
    """How much authority a cited source carries.

    ``PROVISIONAL`` marks text that has not been promoted as laboratory
    doctrine. It must never be presented as settled procedure.
    """

    AUTHORITATIVE = "authoritative"
    SUPPORTING = "supporting"
    PROVISIONAL = "provisional"


TERMINAL_STATUSES = (
    GuidedLabSessionStatus.COMPLETED,
    GuidedLabSessionStatus.ABANDONED,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PATH_MARKERS = ("/", "\\", "://", "~")


def _validate_utc_aware(value: datetime, field_name: str) -> datetime:
    """Return ``value`` normalized to UTC, rejecting naive timestamps."""
    if not isinstance(value, datetime):
        raise GuidedLabActionError(
            GuidedLabErrorCode.TIMESTAMP_NOT_UTC,
            f"{field_name} must be a datetime",
            {"field": field_name, "type": type(value).__name__},
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise GuidedLabActionError(
            GuidedLabErrorCode.TIMESTAMP_NOT_UTC,
            f"{field_name} must be timezone-aware",
            {"field": field_name},
        )
    return value.astimezone(timezone.utc)


def _serialize_datetime(value: datetime) -> str:
    """Serialize a timezone-aware datetime as UTC ISO 8601 with a ``Z``."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    """Parse a UTC ISO 8601 timestamp produced by :func:`_serialize_datetime`."""
    if not isinstance(value, str):
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{field_name} must be an ISO 8601 string",
            {"field": field_name},
        )
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{field_name} is not a valid ISO 8601 timestamp",
            {"field": field_name},
        ) from exc
    if parsed.tzinfo is None:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{field_name} must carry a UTC offset",
            {"field": field_name},
        )
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime | None) -> str | None:
    """Serialize an optional timestamp."""
    return None if value is None else _serialize_datetime(value)


def _validate_finite_number(value: Any, field_name: str) -> None:
    """Reject NaN and infinities, which cannot round-trip through JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        raise GuidedLabActionError(
            GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
            f"{field_name} must be a finite number",
            {"field": field_name},
        )


def _reject_path_like(value: str | None, field_name: str) -> None:
    """Reject anything that looks like a host path.

    Evidence is referenced by logical ID. Storing a path — absolute, relative,
    or URI-shaped — would leak the operator's filesystem into a record that is
    meant to travel between machines.
    """
    if value is None:
        return
    lowered = value.strip()
    if not lowered:
        return
    if any(marker in lowered for marker in _PATH_MARKERS):
        raise GuidedLabActionError(
            GuidedLabErrorCode.EVIDENCE_REFERENCE_INVALID,
            f"{field_name} must be a logical identifier, not a path",
            {"field": field_name},
        )
    if len(lowered) >= 2 and lowered[1] == ":" and lowered[0].isalpha():
        raise GuidedLabActionError(
            GuidedLabErrorCode.EVIDENCE_REFERENCE_INVALID,
            f"{field_name} must be a logical identifier, not a drive path",
            {"field": field_name},
        )
    if lowered == ".." or lowered.startswith(".."):
        raise GuidedLabActionError(
            GuidedLabErrorCode.EVIDENCE_REFERENCE_INVALID,
            f"{field_name} must not be a relative path fragment",
            {"field": field_name},
        )


def _require_numeric_bound(value: Any, field_name: str) -> None:
    """Reject a constraint bound that is not a finite, non-boolean number.

    Checked here rather than left to the comparison below, which would raise a
    bare ``TypeError`` on a string bound and escape the ``GDL-*`` contract every
    other guided-laboratory failure honours.
    """
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuidedLabActionError(
            GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
            f"{field_name} must be a number",
            {"field": field_name, "type": type(value).__name__},
        )
    if not math.isfinite(value):
        raise GuidedLabActionError(
            GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
            f"{field_name} must be finite",
            {"field": field_name},
        )


def _require_text(value: Any, field_name: str) -> str:
    """Return ``value`` if it is a non-empty string, else reject the payload.

    The published contract types every identifier and history entry as
    ``{"type": "string", "minLength": 1}``. Enforcing that here keeps a loaded
    record from being looser than the schema it claims to satisfy — and from
    round-tripping back out as JSON the contract would reject.
    """
    if not isinstance(value, str) or not value.strip():
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{field_name} must be a non-empty string",
            {"field": field_name, "received": type(value).__name__},
        )
    return value


def _require_text_sequence(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    """Validate every entry of an identifier list."""
    return tuple(
        _require_text(value, f"{field_name}[{position}]")
        for position, value in enumerate(values)
    )


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GuidedLabActionError(
            GuidedLabErrorCode.EVIDENCE_REFERENCE_INVALID,
            f"{field_name} must be a non-empty string",
            {"field": field_name},
        )


def _validate_answer_value(value: Any, answer_kind: WorkflowAnswerKind) -> None:
    """Reject values the answer kind does not accept.

    ``bool`` is checked before ``int`` throughout: Python treats ``True`` as an
    integer, and silently accepting it would make an integer answer ambiguous.
    """
    if isinstance(value, bool):
        allowed = answer_kind is WorkflowAnswerKind.BOOLEAN
    elif isinstance(value, str):
        allowed = answer_kind in (
            WorkflowAnswerKind.SINGLE_CHOICE,
            WorkflowAnswerKind.TEXT,
            WorkflowAnswerKind.MEASUREMENT_REFERENCE,
        )
    elif isinstance(value, int):
        allowed = answer_kind in (
            WorkflowAnswerKind.INTEGER,
            WorkflowAnswerKind.DECIMAL,
        )
    elif isinstance(value, float):
        allowed = answer_kind is WorkflowAnswerKind.DECIMAL
    else:
        allowed = False

    if not allowed:
        raise GuidedLabActionError(
            GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
            f"answer kind {answer_kind.value} does not accept {type(value).__name__}",
            {"answer_kind": answer_kind.value, "type": type(value).__name__},
        )
    _validate_finite_number(value, "value")


# ---------------------------------------------------------------------------
# Question constraints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChoiceConstraintV1:
    """The closed set of values a single-choice question accepts."""

    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.allowed_values:
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                "allowed_values must not be empty",
            )
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                "allowed_values must not repeat a value",
            )

    def to_dict(self) -> dict[str, Any]:
        return {"allowed_values": list(self.allowed_values)}


@dataclass(frozen=True)
class NumericConstraintV1:
    """Inclusive bounds for an integer or decimal question."""

    minimum: int | float | None = None
    maximum: int | float | None = None

    def __post_init__(self) -> None:
        for name in ("minimum", "maximum"):
            _require_numeric_bound(getattr(self, name), name)
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                "minimum must not exceed maximum",
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.minimum is not None:
            payload["minimum"] = self.minimum
        if self.maximum is not None:
            payload["maximum"] = self.maximum
        return payload


@dataclass(frozen=True)
class TextConstraintV1:
    """Length bounds for a free-text question."""

    minimum_length: int | None = None
    maximum_length: int | None = None

    def __post_init__(self) -> None:
        for name in ("minimum_length", "maximum_length"):
            bound = getattr(self, name)
            if bound is not None and bound < 0:
                raise GuidedLabActionError(
                    GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                    f"{name} must not be negative",
                )
        if (
            self.minimum_length is not None
            and self.maximum_length is not None
            and self.minimum_length > self.maximum_length
        ):
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                "minimum_length must not exceed maximum_length",
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.minimum_length is not None:
            payload["minimum_length"] = self.minimum_length
        if self.maximum_length is not None:
            payload["maximum_length"] = self.maximum_length
        return payload


QuestionConstraintV1 = Union[ChoiceConstraintV1, NumericConstraintV1, TextConstraintV1]


# ---------------------------------------------------------------------------
# Source references
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowSourceReferenceV1:
    """Where a procedural instruction comes from.

    A ``PROVISIONAL`` reference identifies text that exists to exercise the
    workflow architecture and has not been promoted as laboratory doctrine.
    """

    source_reference_id: str
    title: str
    citation: str
    authority_status: SourceAuthorityStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_reference_id": self.source_reference_id,
            "title": self.title,
            "citation": self.citation,
            "authority_status": self.authority_status.value,
        }


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _common_node_dict(node: Any) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "kind": node.kind.value,
        "title": node.title,
        "body": node.body,
        "why_this_matters": node.why_this_matters,
        "source_reference_ids": list(node.source_reference_ids),
        "required": node.required,
    }


@dataclass(frozen=True)
class QuestionNodeV1:
    """A step that asks the operator for one value."""

    node_id: str
    title: str
    body: str
    answer_kind: WorkflowAnswerKind
    constraints: QuestionConstraintV1 | None = None
    why_this_matters: str = ""
    source_reference_ids: tuple[str, ...] = ()
    required: bool = True
    kind: WorkflowNodeKind = field(default=WorkflowNodeKind.QUESTION, init=False)

    def to_dict(self) -> dict[str, Any]:
        payload = _common_node_dict(self)
        payload["answer_kind"] = self.answer_kind.value
        if self.constraints is not None:
            payload["constraints"] = self.constraints.to_dict()
        return payload


@dataclass(frozen=True)
class InstructionNodeV1:
    """A step that presents procedure text and waits for acknowledgment."""

    node_id: str
    title: str
    body: str
    why_this_matters: str = ""
    source_reference_ids: tuple[str, ...] = ()
    required: bool = True
    kind: WorkflowNodeKind = field(default=WorkflowNodeKind.INSTRUCTION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return _common_node_dict(self)


@dataclass(frozen=True)
class EvidenceRequirementNodeV1:
    """A step that requires one or more logical evidence references."""

    node_id: str
    title: str
    body: str
    required_evidence_kinds: tuple[str, ...]
    minimum_count: int = 1
    why_this_matters: str = ""
    source_reference_ids: tuple[str, ...] = ()
    required: bool = True
    kind: WorkflowNodeKind = field(
        default=WorkflowNodeKind.EVIDENCE_REQUIREMENT, init=False
    )

    def to_dict(self) -> dict[str, Any]:
        payload = _common_node_dict(self)
        payload["required_evidence_kinds"] = list(self.required_evidence_kinds)
        payload["minimum_count"] = self.minimum_count
        return payload


@dataclass(frozen=True)
class ReviewNodeV1:
    """A step that shows the record so far and permits correction."""

    node_id: str
    title: str
    body: str
    required_node_ids: tuple[str, ...] = ()
    why_this_matters: str = ""
    source_reference_ids: tuple[str, ...] = ()
    required: bool = True
    kind: WorkflowNodeKind = field(default=WorkflowNodeKind.REVIEW, init=False)

    def to_dict(self) -> dict[str, Any]:
        payload = _common_node_dict(self)
        payload["required_node_ids"] = list(self.required_node_ids)
        return payload


@dataclass(frozen=True)
class CompleteNodeV1:
    """The terminal step of a workflow."""

    node_id: str
    title: str
    body: str
    completion_message: str
    why_this_matters: str = ""
    source_reference_ids: tuple[str, ...] = ()
    required: bool = True
    kind: WorkflowNodeKind = field(default=WorkflowNodeKind.COMPLETE, init=False)

    def to_dict(self) -> dict[str, Any]:
        payload = _common_node_dict(self)
        payload["completion_message"] = self.completion_message
        return payload


WorkflowNodeV1 = Union[
    QuestionNodeV1,
    InstructionNodeV1,
    EvidenceRequirementNodeV1,
    ReviewNodeV1,
    CompleteNodeV1,
]


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowTransitionConditionV1:
    """When one step leads to another.

    Conditions are declarative data, never callables: a definition must be
    serializable and inspectable without executing it.
    """

    kind: TransitionConditionKind
    node_id: str | None = None
    expected_value: AnswerValue | None = None
    expected_values: tuple[AnswerValue, ...] = ()
    evidence_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind.value}
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.expected_value is not None:
            payload["expected_value"] = self.expected_value
        if self.expected_values:
            payload["expected_values"] = list(self.expected_values)
        if self.evidence_kind is not None:
            payload["evidence_kind"] = self.evidence_kind
        return payload


@dataclass(frozen=True)
class WorkflowTransitionV1:
    """A directed edge between two nodes, guarded by one condition."""

    from_node_id: str
    condition: WorkflowTransitionConditionV1
    to_node_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node_id": self.from_node_id,
            "condition": self.condition.to_dict(),
            "to_node_id": self.to_node_id,
        }


# ---------------------------------------------------------------------------
# Definition and intent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowDefinitionV1:
    """A complete, versioned guided procedure."""

    workflow_id: str
    workflow_version: int
    title: str
    purpose: str
    entry_node_id: str
    nodes: tuple[WorkflowNodeV1, ...]
    transitions: tuple[WorkflowTransitionV1, ...] = ()
    source_references: tuple[WorkflowSourceReferenceV1, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "title": self.title,
            "purpose": self.purpose,
            "entry_node_id": self.entry_node_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "transitions": [t.to_dict() for t in self.transitions],
            "source_references": [ref.to_dict() for ref in self.source_references],
        }


@dataclass(frozen=True)
class WorkflowIntentV1:
    """A builder-facing goal that resolves to a workflow.

    The catalog presents intents, not analyzers: an operator starts from what
    they are trying to do, not from a choice of signal-processing tool.
    """

    intent_id: str
    title: str
    summary: str
    workflow_id: str
    available: bool
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.available and self.unavailable_reason is not None:
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_ACTION_COMBINATION,
                "an available intent must not carry an unavailable_reason",
                {"intent_id": self.intent_id},
            )
        if not self.available and not self.unavailable_reason:
            raise GuidedLabActionError(
                GuidedLabErrorCode.INVALID_ACTION_COMBINATION,
                "an unavailable intent requires an unavailable_reason",
                {"intent_id": self.intent_id},
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "intent_id": self.intent_id,
            "title": self.title,
            "summary": self.summary,
            "workflow_id": self.workflow_id,
            "available": self.available,
        }
        if self.unavailable_reason is not None:
            payload["unavailable_reason"] = self.unavailable_reason
        return payload


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowAnswerV1:
    """One value an operator supplied, with its revision history depth."""

    node_id: str
    answer_kind: WorkflowAnswerKind
    value: AnswerValue
    answered_at: datetime
    revision: int = 1

    def __post_init__(self) -> None:
        _validate_answer_value(self.value, self.answer_kind)
        if not isinstance(self.revision, int) or isinstance(self.revision, bool):
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
                "revision must be an integer",
                {"node_id": self.node_id},
            )
        if self.revision < 1:
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
                "revision must start at 1",
                {"node_id": self.node_id, "revision": self.revision},
            )
        object.__setattr__(
            self, "answered_at", _validate_utc_aware(self.answered_at, "answered_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "answer_kind": self.answer_kind.value,
            "value": self.value,
            "answered_at": _serialize_datetime(self.answered_at),
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WorkflowAnswerV1:
        _require_mapping(payload, "answer")
        _require_keys(
            payload, {"node_id", "answer_kind", "value", "answered_at"}, "answer"
        )
        _reject_unknown_keys(
            payload,
            {"node_id", "answer_kind", "value", "answered_at", "revision"},
            "answer",
        )
        return cls(
            node_id=_require_text(payload["node_id"], "node_id"),
            answer_kind=_enum_from_value(
                WorkflowAnswerKind, payload["answer_kind"], "answer_kind"
            ),
            value=payload["value"],
            answered_at=_parse_datetime(payload["answered_at"], "answered_at"),
            revision=payload.get("revision", 1),
        )


@dataclass(frozen=True)
class WorkflowEvidenceReferenceV1:
    """A logical pointer to evidence held elsewhere.

    Only identifiers travel in this record. Resolving an identifier to bytes on
    disk is the caller's concern and stays outside the guided laboratory.

    ``attached_node_id`` names the requirement step the evidence was attached
    at. The engine stamps it; a caller never has to supply it. It exists so an
    answer correction can drop evidence that belonged to an abandoned branch
    even when the surviving branch happens to ask for the same
    ``evidence_kind``. A reference that arrives without one — hand-written, or
    produced before this field existed — falls back to matching by kind.
    """

    evidence_id: str
    evidence_kind: str
    source_system: str
    label: str | None = None
    digest: str | None = None
    attached_at: datetime | None = None
    attached_node_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "evidence_kind", "source_system"):
            _require_non_empty(getattr(self, name), name)
        for name in ("evidence_id", "evidence_kind", "source_system", "label"):
            _reject_path_like(getattr(self, name), name)
        if self.attached_node_id is not None:
            _require_non_empty(self.attached_node_id, "attached_node_id")
            _reject_path_like(self.attached_node_id, "attached_node_id")
        if self.attached_at is not None:
            object.__setattr__(
                self,
                "attached_at",
                _validate_utc_aware(self.attached_at, "attached_at"),
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "source_system": self.source_system,
        }
        if self.label is not None:
            payload["label"] = self.label
        if self.digest is not None:
            payload["digest"] = self.digest
        if self.attached_at is not None:
            payload["attached_at"] = _serialize_datetime(self.attached_at)
        if self.attached_node_id is not None:
            payload["attached_node_id"] = self.attached_node_id
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WorkflowEvidenceReferenceV1:
        _require_mapping(payload, "evidence_reference")
        known = {
            "evidence_id",
            "evidence_kind",
            "source_system",
            "label",
            "digest",
            "attached_at",
            "attached_node_id",
        }
        _require_keys(
            payload,
            {"evidence_id", "evidence_kind", "source_system"},
            "evidence_reference",
        )
        _reject_unknown_keys(payload, known, "evidence_reference")
        attached_at = payload.get("attached_at")
        return cls(
            evidence_id=payload["evidence_id"],
            evidence_kind=payload["evidence_kind"],
            source_system=payload["source_system"],
            label=payload.get("label"),
            digest=payload.get("digest"),
            attached_at=(
                None
                if attached_at is None
                else _parse_datetime(attached_at, "attached_at")
            ),
            attached_node_id=payload.get("attached_node_id"),
        )


@dataclass(frozen=True)
class GuidedLabSessionV1:
    """The persisted, resumable state of one guided procedure run."""

    session_id: str
    workflow_id: str
    workflow_version: int
    status: GuidedLabSessionStatus
    current_node_id: str
    started_at: datetime
    updated_at: datetime
    answers: tuple[WorkflowAnswerV1, ...] = ()
    acknowledged_node_ids: tuple[str, ...] = ()
    evidence_references: tuple[WorkflowEvidenceReferenceV1, ...] = ()
    visited_node_ids: tuple[str, ...] = ()
    completed_at: datetime | None = None
    schema_version: str = field(default=GUIDED_LAB_SESSION_SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "started_at", _validate_utc_aware(self.started_at, "started_at")
        )
        object.__setattr__(
            self, "updated_at", _validate_utc_aware(self.updated_at, "updated_at")
        )
        if self.completed_at is not None:
            object.__setattr__(
                self,
                "completed_at",
                _validate_utc_aware(self.completed_at, "completed_at"),
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status.value,
            "current_node_id": self.current_node_id,
            "answers": [answer.to_dict() for answer in self.answers],
            "acknowledged_node_ids": list(self.acknowledged_node_ids),
            "evidence_references": [ref.to_dict() for ref in self.evidence_references],
            "visited_node_ids": list(self.visited_node_ids),
            "started_at": _serialize_datetime(self.started_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }
        completed = _utc_iso(self.completed_at)
        if completed is not None:
            payload["completed_at"] = completed
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GuidedLabSessionV1:
        """Reconstruct a session, rejecting anything this version cannot hold."""
        _require_mapping(payload, "session")
        known = {
            "schema_version",
            "session_id",
            "workflow_id",
            "workflow_version",
            "status",
            "current_node_id",
            "answers",
            "acknowledged_node_ids",
            "evidence_references",
            "visited_node_ids",
            "started_at",
            "updated_at",
            "completed_at",
        }
        required = {
            "schema_version",
            "session_id",
            "workflow_id",
            "workflow_version",
            "status",
            "current_node_id",
            "started_at",
            "updated_at",
        }
        _reject_unknown_keys(payload, known, "session")
        _require_keys(payload, required, "session")

        schema_version = payload["schema_version"]
        if schema_version != GUIDED_LAB_SESSION_SCHEMA_VERSION:
            raise GuidedLabSessionError(
                GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
                "unsupported session schema_version",
                {
                    "expected": GUIDED_LAB_SESSION_SCHEMA_VERSION,
                    "received": str(schema_version),
                },
            )

        workflow_version = payload["workflow_version"]
        if (
            not isinstance(workflow_version, int)
            or isinstance(workflow_version, bool)
            or workflow_version < 1
        ):
            # The contract types this as {"type": "integer", "minimum": 1}. A
            # version below 1 names no workflow that can exist, so accepting it
            # would load a record whose provenance pair is meaningless.
            raise GuidedLabSessionError(
                GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
                "workflow_version must be an integer of at least 1",
            )

        completed_at = payload.get("completed_at")
        return cls(
            session_id=_require_text(payload["session_id"], "session_id"),
            workflow_id=_require_text(payload["workflow_id"], "workflow_id"),
            workflow_version=workflow_version,
            status=_enum_from_value(
                GuidedLabSessionStatus, payload["status"], "status"
            ),
            current_node_id=_require_text(
                payload["current_node_id"], "current_node_id"
            ),
            started_at=_parse_datetime(payload["started_at"], "started_at"),
            updated_at=_parse_datetime(payload["updated_at"], "updated_at"),
            answers=tuple(
                WorkflowAnswerV1.from_dict(item)
                for item in _require_sequence(payload.get("answers", ()), "answers")
            ),
            acknowledged_node_ids=_require_text_sequence(
                _require_sequence(
                    payload.get("acknowledged_node_ids", ()), "acknowledged_node_ids"
                ),
                "acknowledged_node_ids",
            ),
            evidence_references=tuple(
                WorkflowEvidenceReferenceV1.from_dict(item)
                for item in _require_sequence(
                    payload.get("evidence_references", ()), "evidence_references"
                )
            ),
            visited_node_ids=_require_text_sequence(
                _require_sequence(
                    payload.get("visited_node_ids", ()), "visited_node_ids"
                ),
                "visited_node_ids",
            ),
            completed_at=(
                None
                if completed_at is None
                else _parse_datetime(completed_at, "completed_at")
            ),
        )


def guided_lab_session_from_dict(payload: Mapping[str, Any]) -> GuidedLabSessionV1:
    """Module-level alias for :meth:`GuidedLabSessionV1.from_dict`."""
    return GuidedLabSessionV1.from_dict(payload)


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowProgressV1:
    """A read-only summary of how far a session has come."""

    current_node_id: str
    visited_count: int
    answered_count: int
    evidence_count: int
    missing_required_node_ids: tuple[str, ...] = ()
    may_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_node_id": self.current_node_id,
            "visited_count": self.visited_count,
            "answered_count": self.answered_count,
            "evidence_count": self.evidence_count,
            "missing_required_node_ids": list(self.missing_required_node_ids),
            "may_complete": self.may_complete,
        }


@dataclass(frozen=True)
class WorkflowValidationFindingV1:
    """One problem found in a workflow definition."""

    code: GuidedLabErrorCode
    message: str
    node_id: str | None = None
    transition_index: int | None = None

    @property
    def sort_key(self) -> tuple[str, str, int, str]:
        """Deterministic order: code, node ID, transition index, message."""
        return (
            self.code.value,
            self.node_id or "",
            -1 if self.transition_index is None else self.transition_index,
            self.message,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.transition_index is not None:
            payload["transition_index"] = self.transition_index
        return payload


# ---------------------------------------------------------------------------
# Deserialization guards
# ---------------------------------------------------------------------------


def _require_mapping(payload: Any, label: str) -> None:
    if not isinstance(payload, Mapping):
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{label} payload must be a JSON object",
            {"received": type(payload).__name__},
        )


def _require_sequence(value: Any, label: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{label} must be a list",
            {"field": label, "received": type(value).__name__},
        )
    return list(value)


def _require_keys(payload: Mapping[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(payload))
    if missing:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{label} payload is missing required fields",
            {"missing": missing},
        )


def _reject_unknown_keys(
    payload: Mapping[str, Any], known: set[str], label: str
) -> None:
    unknown = sorted(set(payload) - known)
    if unknown:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{label} payload contains unsupported fields",
            {"unknown": unknown},
        )


def _enum_from_value(enum_cls: Any, value: Any, label: str) -> Any:
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            f"{label} is not a supported value",
            {"field": label, "received": str(value)},
        ) from exc


__all__ = [
    "GUIDED_LAB_SESSION_SCHEMA_VERSION",
    "AnswerValue",
    "ChoiceConstraintV1",
    "CompleteNodeV1",
    "EvidenceRequirementNodeV1",
    "GuidedLabSessionStatus",
    "GuidedLabSessionV1",
    "InstructionNodeV1",
    "NumericConstraintV1",
    "QuestionConstraintV1",
    "QuestionNodeV1",
    "ReviewNodeV1",
    "SourceAuthorityStatus",
    "TERMINAL_STATUSES",
    "TextConstraintV1",
    "TransitionConditionKind",
    "WorkflowAnswerKind",
    "WorkflowAnswerV1",
    "WorkflowDefinitionV1",
    "WorkflowEvidenceReferenceV1",
    "WorkflowIntentV1",
    "WorkflowNodeKind",
    "WorkflowNodeV1",
    "WorkflowProgressV1",
    "WorkflowSourceReferenceV1",
    "WorkflowTransitionConditionV1",
    "WorkflowTransitionV1",
    "WorkflowValidationFindingV1",
    "guided_lab_session_from_dict",
]

"""Contract boundary tests for the guided laboratory workflow models (DO-100).

These tests pin the public shape of `tap_tone_pi.guided_lab.models`: frozen
records, deterministic serialization, UTC-only timestamps, and rejection of
values the measurement boundary does not permit (host paths, non-finite
numbers, unsupported answer types).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from tap_tone_pi.guided_lab import (
    GuidedLabActionError,
    GuidedLabErrorCode,
    GuidedLabSessionError,
    GuidedLabSessionStatus,
    GuidedLabSessionV1,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowAnswerV1,
    WorkflowDefinitionV1,
    WorkflowEvidenceReferenceV1,
    WorkflowIntentV1,
    WorkflowNodeKind,
    WorkflowProgressV1,
    WorkflowTransitionV1,
    WorkflowValidationFindingV1,
)
from tap_tone_pi.guided_lab.models import (
    ChoiceConstraintV1,
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    InstructionNodeV1,
    NumericConstraintV1,
    QuestionNodeV1,
    ReviewNodeV1,
    SourceAuthorityStatus,
    TextConstraintV1,
    WorkflowSourceReferenceV1,
    WorkflowTransitionConditionV1,
)

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)


def _question() -> QuestionNodeV1:
    return QuestionNodeV1(
        node_id="specimen_type",
        title="Which part are you preparing to measure?",
        body="Choose the item on the bench.",
        answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
        constraints=ChoiceConstraintV1(allowed_values=("top", "back")),
    )


def _complete() -> CompleteNodeV1:
    return CompleteNodeV1(
        node_id="done",
        title="Setup record complete",
        body="The workflow record is closed.",
        completion_message="Setup workflow record complete.",
    )


class TestImmutability:
    def test_nodes_are_frozen(self):
        node = _question()
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.node_id = "other"  # type: ignore[misc]

    def test_session_is_frozen(self):
        session = GuidedLabSessionV1(
            session_id="s1",
            workflow_id="w",
            workflow_version=1,
            status=GuidedLabSessionStatus.ACTIVE,
            current_node_id="specimen_type",
            started_at=T0,
            updated_at=T0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            session.status = GuidedLabSessionStatus.COMPLETED  # type: ignore[misc]

    def test_answer_is_frozen(self):
        answer = WorkflowAnswerV1(
            node_id="specimen_type",
            answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
            value="top",
            answered_at=T0,
            revision=1,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            answer.value = "back"  # type: ignore[misc]

    def test_collection_fields_are_tuples(self):
        session = GuidedLabSessionV1(
            session_id="s1",
            workflow_id="w",
            workflow_version=1,
            status=GuidedLabSessionStatus.ACTIVE,
            current_node_id="a",
            started_at=T0,
            updated_at=T0,
        )
        assert isinstance(session.answers, tuple)
        assert isinstance(session.acknowledged_node_ids, tuple)
        assert isinstance(session.evidence_references, tuple)
        assert isinstance(session.visited_node_ids, tuple)


class TestNodeSerialization:
    def test_question_node_round_trips_kind_and_constraints(self):
        payload = _question().to_dict()
        assert payload["kind"] == "question"
        assert payload["answer_kind"] == "single_choice"
        assert payload["constraints"] == {"allowed_values": ["top", "back"]}

    def test_instruction_node_kind(self):
        node = InstructionNodeV1(
            node_id="prep",
            title="Prepare the bench",
            body="Support the plate on soft foam.",
            source_reference_ids=("src_provisional",),
        )
        payload = node.to_dict()
        assert payload["kind"] == "instruction"
        assert payload["source_reference_ids"] == ["src_provisional"]

    def test_evidence_node_kind(self):
        node = EvidenceRequirementNodeV1(
            node_id="ev",
            title="Attach the specimen record",
            body="Reference the specimen record you created.",
            required_evidence_kinds=("specimen_record",),
            minimum_count=1,
        )
        payload = node.to_dict()
        assert payload["kind"] == "evidence_requirement"
        assert payload["required_evidence_kinds"] == ["specimen_record"]
        assert payload["minimum_count"] == 1

    def test_review_node_kind(self):
        node = ReviewNodeV1(
            node_id="review",
            title="Review the record",
            body="Check each entry before closing.",
            required_node_ids=("specimen_type",),
        )
        payload = node.to_dict()
        assert payload["kind"] == "review"
        assert payload["required_node_ids"] == ["specimen_type"]

    def test_complete_node_kind(self):
        payload = _complete().to_dict()
        assert payload["kind"] == "complete"
        assert payload["completion_message"] == "Setup workflow record complete."

    def test_every_node_kind_is_a_plain_string(self):
        for node in (_question(), _complete()):
            assert isinstance(node.to_dict()["kind"], str)
            assert not isinstance(node.to_dict()["kind"], WorkflowNodeKind)

    def test_numeric_and_text_constraints_serialize(self):
        assert NumericConstraintV1(minimum=1, maximum=9).to_dict() == {
            "minimum": 1,
            "maximum": 9,
        }
        assert TextConstraintV1(minimum_length=1).to_dict() == {"minimum_length": 1}

    def test_numeric_constraint_rejects_inverted_bounds(self):
        with pytest.raises(GuidedLabActionError):
            NumericConstraintV1(minimum=9, maximum=1)

    def test_choice_constraint_rejects_empty_and_duplicate_values(self):
        with pytest.raises(GuidedLabActionError):
            ChoiceConstraintV1(allowed_values=())
        with pytest.raises(GuidedLabActionError):
            ChoiceConstraintV1(allowed_values=("top", "top"))


class TestTransitionSerialization:
    def test_always_condition_omits_unused_fields(self):
        transition = WorkflowTransitionV1(
            from_node_id="a",
            condition=WorkflowTransitionConditionV1(
                kind=TransitionConditionKind.ALWAYS
            ),
            to_node_id="b",
        )
        payload = transition.to_dict()
        assert payload["condition"] == {"kind": "always"}
        assert payload["from_node_id"] == "a"
        assert payload["to_node_id"] == "b"

    def test_answer_in_set_serializes_expected_values_as_list(self):
        condition = WorkflowTransitionConditionV1(
            kind=TransitionConditionKind.ANSWER_IN_SET,
            node_id="specimen_type",
            expected_values=("top", "back"),
        )
        assert condition.to_dict() == {
            "kind": "answer_in_set",
            "node_id": "specimen_type",
            "expected_values": ["top", "back"],
        }


class TestSourceReferences:
    def test_authority_status_serializes_as_string(self):
        ref = WorkflowSourceReferenceV1(
            source_reference_id="src_provisional",
            title="Provisional setup guidance",
            citation="Internal DO-100 placeholder",
            authority_status=SourceAuthorityStatus.PROVISIONAL,
        )
        assert ref.to_dict()["authority_status"] == "provisional"

    def test_authority_status_values(self):
        assert {status.value for status in SourceAuthorityStatus} == {
            "authoritative",
            "supporting",
            "provisional",
        }


class TestAnswers:
    def test_answer_serializes_enum_and_timestamp(self):
        answer = WorkflowAnswerV1(
            node_id="specimen_type",
            answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
            value="top",
            answered_at=T0,
            revision=1,
        )
        payload = answer.to_dict()
        assert payload == {
            "node_id": "specimen_type",
            "answer_kind": "single_choice",
            "value": "top",
            "answered_at": "2026-07-29T12:00:00Z",
            "revision": 1,
        }

    def test_revision_starts_at_one_and_must_be_positive(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowAnswerV1(
                node_id="a",
                answer_kind=WorkflowAnswerKind.TEXT,
                value="x",
                answered_at=T0,
                revision=0,
            )

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_numbers_rejected(self, bad):
        with pytest.raises(GuidedLabActionError):
            WorkflowAnswerV1(
                node_id="a",
                answer_kind=WorkflowAnswerKind.DECIMAL,
                value=bad,
                answered_at=T0,
                revision=1,
            )

    @pytest.mark.parametrize("bad", [None, ["a"], {"a": 1}, ("a",)])
    def test_unsupported_answer_values_rejected(self, bad):
        with pytest.raises(GuidedLabActionError):
            WorkflowAnswerV1(
                node_id="a",
                answer_kind=WorkflowAnswerKind.TEXT,
                value=bad,
                answered_at=T0,
                revision=1,
            )

    def test_naive_timestamp_rejected(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowAnswerV1(
                node_id="a",
                answer_kind=WorkflowAnswerKind.TEXT,
                value="x",
                answered_at=datetime(2026, 7, 29, 12, 0, 0),
                revision=1,
            )

    def test_non_utc_timestamp_is_normalized_to_utc(self):
        answer = WorkflowAnswerV1(
            node_id="a",
            answer_kind=WorkflowAnswerKind.TEXT,
            value="x",
            answered_at=datetime(
                2026, 7, 29, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5))
            ),
            revision=1,
        )
        assert answer.to_dict()["answered_at"] == "2026-07-29T12:00:00Z"

    def test_boolean_is_not_treated_as_integer(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowAnswerV1(
                node_id="a",
                answer_kind=WorkflowAnswerKind.INTEGER,
                value=True,
                answered_at=T0,
                revision=1,
            )


class TestEvidenceReferences:
    def test_evidence_serializes_and_omits_absent_optionals(self):
        ref = WorkflowEvidenceReferenceV1(
            evidence_id="ev-1",
            evidence_kind="specimen_record",
            source_system="tap_tone_pi",
        )
        payload = ref.to_dict()
        assert payload == {
            "evidence_id": "ev-1",
            "evidence_kind": "specimen_record",
            "source_system": "tap_tone_pi",
        }
        assert "label" not in payload
        assert "digest" not in payload
        assert "attached_at" not in payload

    def test_evidence_has_no_path_field(self):
        field_names = {f.name for f in dataclasses.fields(WorkflowEvidenceReferenceV1)}
        assert "path" not in field_names
        assert "file_path" not in field_names
        assert "uri" not in field_names

    @pytest.mark.parametrize(
        "bad_id",
        [
            "C:/runs/session.json",
            "C:\\runs\\session.json",
            "/var/data/session.json",
            "runs\\session",
            "../session",
            "~/session",
            "file:///runs/session.json",
        ],
    )
    def test_path_like_evidence_id_rejected(self, bad_id):
        with pytest.raises(GuidedLabActionError):
            WorkflowEvidenceReferenceV1(
                evidence_id=bad_id,
                evidence_kind="measurement_session",
                source_system="tap_tone_pi",
            )

    def test_path_like_label_rejected(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowEvidenceReferenceV1(
                evidence_id="ev-1",
                evidence_kind="measurement_session",
                source_system="tap_tone_pi",
                label="/home/luthier/runs",
            )

    def test_empty_required_evidence_fields_rejected(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowEvidenceReferenceV1(
                evidence_id="",
                evidence_kind="measurement_session",
                source_system="tap_tone_pi",
            )

    def test_attachment_node_is_absent_until_stamped(self):
        ref = WorkflowEvidenceReferenceV1(
            evidence_id="ev-1",
            evidence_kind="specimen_record",
            source_system="tap_tone_pi",
        )
        assert ref.attached_node_id is None
        assert "attached_node_id" not in ref.to_dict()

    def test_attachment_node_round_trips(self):
        ref = WorkflowEvidenceReferenceV1(
            evidence_id="ev-1",
            evidence_kind="specimen_record",
            source_system="tap_tone_pi",
            attached_node_id="e_specimen_record",
        )
        payload = ref.to_dict()
        assert payload["attached_node_id"] == "e_specimen_record"
        assert WorkflowEvidenceReferenceV1.from_dict(payload) == ref

    def test_path_like_attachment_node_rejected(self):
        """A node identifier is a name in a workflow, never a location."""
        with pytest.raises(GuidedLabActionError):
            WorkflowEvidenceReferenceV1(
                evidence_id="ev-1",
                evidence_kind="specimen_record",
                source_system="tap_tone_pi",
                attached_node_id="/runs/e_specimen_record",
            )

    def test_empty_attachment_node_rejected(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowEvidenceReferenceV1(
                evidence_id="ev-1",
                evidence_kind="specimen_record",
                source_system="tap_tone_pi",
                attached_node_id="   ",
            )


class TestSessionSerialization:
    def _session(self, **overrides) -> GuidedLabSessionV1:
        base = dict(
            session_id="session-1",
            workflow_id="plate_measurement_setup",
            workflow_version=1,
            status=GuidedLabSessionStatus.ACTIVE,
            current_node_id="specimen_type",
            answers=(
                WorkflowAnswerV1(
                    node_id="specimen_type",
                    answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
                    value="top",
                    answered_at=T0,
                    revision=1,
                ),
            ),
            acknowledged_node_ids=("prep",),
            evidence_references=(
                WorkflowEvidenceReferenceV1(
                    evidence_id="ev-1",
                    evidence_kind="specimen_record",
                    source_system="tap_tone_pi",
                    attached_at=T1,
                ),
            ),
            visited_node_ids=("specimen_type",),
            started_at=T0,
            updated_at=T1,
        )
        base.update(overrides)
        return GuidedLabSessionV1(**base)  # type: ignore[arg-type]

    def test_schema_version_is_present_and_pinned(self):
        payload = self._session().to_dict()
        assert payload["schema_version"] == "guided_lab_session_v1"

    def test_workflow_identity_is_separate_from_schema_identity(self):
        payload = self._session().to_dict()
        assert payload["workflow_id"] == "plate_measurement_setup"
        assert payload["workflow_version"] == 1
        assert payload["schema_version"] == "guided_lab_session_v1"

    def test_status_serializes_as_string(self):
        assert self._session().to_dict()["status"] == "active"

    def test_tuples_serialize_as_lists(self):
        payload = self._session().to_dict()
        assert isinstance(payload["answers"], list)
        assert isinstance(payload["acknowledged_node_ids"], list)
        assert isinstance(payload["evidence_references"], list)
        assert isinstance(payload["visited_node_ids"], list)

    def test_absent_completed_at_is_omitted(self):
        assert "completed_at" not in self._session().to_dict()

    def test_present_completed_at_is_serialized(self):
        payload = self._session(
            status=GuidedLabSessionStatus.COMPLETED, completed_at=T1
        ).to_dict()
        assert payload["completed_at"] == "2026-07-29T12:05:00Z"

    def test_to_dict_is_deterministic(self):
        session = self._session()
        assert session.to_dict() == session.to_dict()

    def test_round_trip_through_from_dict(self):
        session = self._session()
        restored = GuidedLabSessionV1.from_dict(session.to_dict())
        assert restored == session

    def test_round_trip_preserves_completed_session(self):
        session = self._session(
            status=GuidedLabSessionStatus.COMPLETED, completed_at=T1
        )
        assert GuidedLabSessionV1.from_dict(session.to_dict()) == session

    def test_from_dict_rejects_unknown_schema_version(self):
        payload = self._session().to_dict()
        payload["schema_version"] = "guided_lab_session_v2"
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(payload)

    def test_from_dict_rejects_unknown_key(self):
        payload = self._session().to_dict()
        payload["operator_notes"] = "extra"
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(payload)

    def test_from_dict_rejects_missing_required_key(self):
        payload = self._session().to_dict()
        del payload["current_node_id"]
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(payload)

    def test_from_dict_rejects_non_mapping(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_from_dict_tolerates_absent_optional_fields(self):
        payload = self._session().to_dict()
        payload["evidence_references"] = [
            {
                "evidence_id": "ev-2",
                "evidence_kind": "measurement_session",
                "source_system": "tap_tone_pi",
            }
        ]
        restored = GuidedLabSessionV1.from_dict(payload)
        assert restored.evidence_references[0].label is None
        assert restored.evidence_references[0].attached_at is None

    def test_serialized_session_contains_no_host_path(self):
        blob = repr(self._session().to_dict())
        assert "\\\\" not in blob
        assert "C:" not in blob


class TestProgressAndFindings:
    def test_progress_serializes(self):
        progress = WorkflowProgressV1(
            current_node_id="review",
            visited_count=4,
            answered_count=3,
            evidence_count=1,
            missing_required_node_ids=("ev_measurement",),
            may_complete=False,
        )
        assert progress.to_dict() == {
            "current_node_id": "review",
            "visited_count": 4,
            "answered_count": 3,
            "evidence_count": 1,
            "missing_required_node_ids": ["ev_measurement"],
            "may_complete": False,
        }

    def test_finding_serializes_code_as_string(self):
        from tap_tone_pi.guided_lab import GuidedLabErrorCode

        finding = WorkflowValidationFindingV1(
            code=GuidedLabErrorCode.DUPLICATE_NODE_ID,
            message="duplicate node id 'a'",
            node_id="a",
        )
        payload = finding.to_dict()
        assert payload["code"] == "GDL-101"
        assert payload["node_id"] == "a"
        assert "transition_index" not in payload


class TestIntents:
    def test_available_intent_serializes_without_reason(self):
        intent = WorkflowIntentV1(
            intent_id="evaluate_plate_measurement_setup",
            title="I want to prepare a plate measurement",
            summary="Walk through specimen identity, purpose, and readiness.",
            workflow_id="plate_measurement_setup",
            available=True,
            unavailable_reason=None,
        )
        payload = intent.to_dict()
        assert payload["available"] is True
        assert "unavailable_reason" not in payload

    def test_available_intent_rejects_reason(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowIntentV1(
                intent_id="x",
                title="t",
                summary="s",
                workflow_id="w",
                available=True,
                unavailable_reason="not ready",
            )

    def test_unavailable_intent_requires_reason(self):
        with pytest.raises(GuidedLabActionError):
            WorkflowIntentV1(
                intent_id="x",
                title="t",
                summary="s",
                workflow_id="w",
                available=False,
                unavailable_reason=None,
            )


class TestDefinition:
    def test_definition_serializes_nodes_and_transitions(self):
        definition = WorkflowDefinitionV1(
            workflow_id="w",
            workflow_version=1,
            title="Test workflow",
            purpose="Exercise the contract.",
            entry_node_id="specimen_type",
            nodes=(_question(), _complete()),
            transitions=(
                WorkflowTransitionV1(
                    from_node_id="specimen_type",
                    condition=WorkflowTransitionConditionV1(
                        kind=TransitionConditionKind.ALWAYS
                    ),
                    to_node_id="done",
                ),
            ),
        )
        payload = definition.to_dict()
        assert payload["workflow_version"] == 1
        assert [n["node_id"] for n in payload["nodes"]] == ["specimen_type", "done"]
        assert payload["transitions"][0]["to_node_id"] == "done"
        assert payload["source_references"] == []


class TestNumericConstraintBounds:
    """A bound that is not a number must fail inside the GDL error contract.

    Left to the comparison in ``__post_init__``, a string bound raised a bare
    ``TypeError`` — the one guided-laboratory failure a caller could not catch
    as a ``GuidedLabError`` or report as a ``GDL-*`` code.
    """

    def test_a_string_minimum_is_rejected(self):
        with pytest.raises(GuidedLabActionError) as excinfo:
            NumericConstraintV1(minimum="abc", maximum=5)
        assert excinfo.value.code is GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS

    def test_two_string_bounds_are_rejected(self):
        with pytest.raises(GuidedLabActionError):
            NumericConstraintV1(minimum="a", maximum="b")

    def test_a_boolean_bound_is_rejected(self):
        with pytest.raises(GuidedLabActionError):
            NumericConstraintV1(minimum=True)

    def test_a_non_finite_bound_is_rejected(self):
        with pytest.raises(GuidedLabActionError):
            NumericConstraintV1(maximum=float("inf"))

    def test_a_nan_bound_is_rejected(self):
        with pytest.raises(GuidedLabActionError):
            NumericConstraintV1(minimum=float("nan"))

    def test_numeric_bounds_are_still_accepted(self):
        assert NumericConstraintV1(minimum=1, maximum=2.5).to_dict() == {
            "minimum": 1,
            "maximum": 2.5,
        }

    def test_open_bounds_are_still_accepted(self):
        assert NumericConstraintV1().to_dict() == {}


class TestSessionPayloadIdentifierTypes:
    """The loader must not accept a record the published contract rejects.

    ``guided_lab_session_v1.schema.json`` types every identifier and history
    entry as ``{"type": "string", "minLength": 1}``. A loader looser than that
    accepts a record it cannot honestly hold, and writes it straight back out
    as JSON the contract would refuse.
    """

    def _payload(self, **overrides):
        payload = {
            "schema_version": "guided_lab_session_v1",
            "session_id": "s-1",
            "workflow_id": "fixture_workflow",
            "workflow_version": 1,
            "status": "active",
            "current_node_id": "q_specimen",
            "visited_node_ids": ["q_specimen"],
            "acknowledged_node_ids": [],
            "started_at": "2026-07-29T12:00:00Z",
            "updated_at": "2026-07-29T12:00:00Z",
        }
        payload.update(overrides)
        return payload

    def test_a_well_formed_payload_still_loads(self):
        session = GuidedLabSessionV1.from_dict(self._payload())
        assert session.session_id == "s-1"
        assert session.visited_node_ids == ("q_specimen",)

    @pytest.mark.parametrize("field", ["session_id", "workflow_id", "current_node_id"])
    def test_a_non_string_identifier_is_rejected(self, field):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            GuidedLabSessionV1.from_dict(self._payload(**{field: 12345}))
        assert excinfo.value.code is GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED

    @pytest.mark.parametrize("field", ["session_id", "workflow_id", "current_node_id"])
    def test_an_empty_identifier_is_rejected(self, field):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(self._payload(**{field: "   "}))

    def test_a_non_string_visited_entry_is_rejected(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            GuidedLabSessionV1.from_dict(
                self._payload(visited_node_ids=["q_specimen", 7])
            )
        assert excinfo.value.context["field"] == "visited_node_ids[1]"

    def test_a_nested_object_in_the_history_is_rejected(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(
                self._payload(visited_node_ids=[{"nested": "object"}])
            )

    def test_a_null_acknowledgment_entry_is_rejected(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            GuidedLabSessionV1.from_dict(self._payload(acknowledged_node_ids=[None]))
        assert excinfo.value.context["field"] == "acknowledged_node_ids[0]"

    def test_an_answer_with_a_non_string_node_id_is_rejected(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(
                self._payload(
                    answers=[
                        {
                            "node_id": 9,
                            "answer_kind": "text",
                            "value": "x",
                            "answered_at": "2026-07-29T12:00:00Z",
                        }
                    ]
                )
            )

    def test_a_rejected_payload_never_reports_a_host_path(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            GuidedLabSessionV1.from_dict(self._payload(session_id=12345))
        blob = repr(excinfo.value.to_dict())
        assert "C:" not in blob and "/" not in blob


class TestSessionWorkflowVersionBounds:
    """The contract types workflow_version as {"type": "integer", "minimum": 1}."""

    def _payload(self, version):
        return {
            "schema_version": "guided_lab_session_v1",
            "session_id": "s-1",
            "workflow_id": "fixture_workflow",
            "workflow_version": version,
            "status": "active",
            "current_node_id": "q_specimen",
            "started_at": "2026-07-29T12:00:00Z",
            "updated_at": "2026-07-29T12:00:00Z",
        }

    def test_version_one_loads(self):
        assert GuidedLabSessionV1.from_dict(self._payload(1)).workflow_version == 1

    def test_version_zero_is_rejected(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(self._payload(0))

    def test_a_negative_version_is_rejected(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(self._payload(-3))

    def test_a_boolean_version_is_rejected(self):
        with pytest.raises(GuidedLabSessionError):
            GuidedLabSessionV1.from_dict(self._payload(True))

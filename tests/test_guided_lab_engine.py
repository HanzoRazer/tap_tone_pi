"""Deterministic session transitions for the guided laboratory (DO-100).

Exercised against a synthetic branching workflow rather than the shipped plate
workflow, so engine behaviour is pinned independently of the procedure text.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from tap_tone_pi.guided_lab import (
    GuidedLabActionError,
    GuidedLabSessionError,
    GuidedLabSessionStatus,
    GuidedLabErrorCode,
    WorkflowDefinitionError,
)
from tap_tone_pi.guided_lab.engine import (
    abandon_session,
    acknowledge_instruction,
    advance_session,
    answer_question,
    attach_evidence,
    complete_session,
    get_current_node,
    get_workflow_progress,
    go_back,
    pause_session,
    replace_answer,
    resume_session,
    start_session,
)
from tap_tone_pi.guided_lab.models import (
    TransitionConditionKind,
    WorkflowEvidenceReferenceV1,
)
from tests.guided_lab_fixtures import (
    make_branching_definition,
    make_complete_node,
    make_evidence_node,
    make_minimal_valid_definition,
    make_question_node,
    make_transition,
)

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def specimen_evidence(evidence_id: str = "ev-specimen") -> WorkflowEvidenceReferenceV1:
    return WorkflowEvidenceReferenceV1(
        evidence_id=evidence_id,
        evidence_kind="specimen_record",
        source_system="tap_tone_pi",
    )


def started() -> tuple:
    definition = make_branching_definition()
    session = start_session(definition, session_id="s-1", started_at=T0)
    return definition, session


def walk_top_branch_to_review():
    """Answer 'top', acknowledge prep, attach evidence, land on review."""
    definition, session = started()
    session = answer_question(definition, session, "top", answered_at=at(1))
    session = advance_session(definition, session, advanced_at=at(2))
    session = acknowledge_instruction(definition, session, acknowledged_at=at(3))
    session = advance_session(definition, session, advanced_at=at(4))
    session = attach_evidence(
        definition, session, specimen_evidence(), attached_at=at(5)
    )
    session = advance_session(definition, session, advanced_at=at(6))
    return definition, session


def walk_back_branch_to_evidence():
    """Answer 'back', answer the boolean 'true', land on the evidence step."""
    definition, session = started()
    session = answer_question(definition, session, "back", answered_at=at(1))
    session = advance_session(definition, session, advanced_at=at(2))
    session = answer_question(definition, session, True, answered_at=at(3))
    session = advance_session(definition, session, advanced_at=at(4))
    return definition, session


def make_two_stage_evidence_definition():
    """Two evidence steps in a row that ask for the *same* kind.

    The shape the engine has to get right if evidence is ever to be told apart
    by where it was attached rather than by what it is called.
    """
    return dataclasses.replace(
        make_minimal_valid_definition(workflow_id="two_stage_evidence"),
        entry_node_id="e_first",
        nodes=(
            make_evidence_node("e_first"),
            make_evidence_node("e_second"),
            make_complete_node(),
        ),
        transitions=(
            make_transition("e_first", "e_second"),
            make_transition("e_second", "c_done"),
        ),
    )


def make_runtime_ambiguity_definition():
    """A definition whose ambiguity only exists for particular answers.

    An answer condition and an evidence condition leave the same node. Neither
    can be shown to overlap the other by reading the definition, so static
    validation passes it; both hold at once only once a specific answer and a
    specific reference are present.
    """
    return dataclasses.replace(
        make_minimal_valid_definition(workflow_id="runtime_ambiguity"),
        entry_node_id="q_specimen",
        nodes=(
            make_question_node(),
            make_evidence_node("e_gate"),
            make_complete_node("c_by_answer"),
            make_complete_node("c_by_evidence"),
        ),
        transitions=(
            make_transition("q_specimen", "e_gate"),
            make_transition(
                "e_gate",
                "c_by_answer",
                kind=TransitionConditionKind.ANSWER_EQUALS,
                node_id="q_specimen",
                expected_value="top",
            ),
            make_transition(
                "e_gate",
                "c_by_evidence",
                kind=TransitionConditionKind.EVIDENCE_PRESENT,
                evidence_kind="specimen_record",
            ),
        ),
    )


class TestStart:
    def test_start_is_deterministic(self):
        definition = make_branching_definition()
        first = start_session(definition, session_id="s-1", started_at=T0)
        second = start_session(definition, session_id="s-1", started_at=T0)
        assert first == second

    def test_start_records_workflow_identity(self):
        definition, session = started()
        assert session.workflow_id == definition.workflow_id
        assert session.workflow_version == definition.workflow_version
        assert session.schema_version == "guided_lab_session_v1"

    def test_start_lands_on_the_entry_node(self):
        definition, session = started()
        assert session.current_node_id == "q_specimen"
        assert session.visited_node_ids == ("q_specimen",)
        assert session.status is GuidedLabSessionStatus.ACTIVE

    def test_start_generates_an_id_when_none_supplied(self):
        definition = make_branching_definition()
        session = start_session(definition, started_at=T0)
        assert session.session_id
        assert start_session(definition, started_at=T0).session_id != session.session_id

    def test_start_rejects_an_invalid_definition(self):
        broken = dataclasses.replace(
            make_minimal_valid_definition(), entry_node_id="ghost"
        )
        with pytest.raises(WorkflowDefinitionError):
            start_session(broken, session_id="s", started_at=T0)


class TestCurrentNodeAndIdentity:
    def test_get_current_node_returns_the_exact_node(self):
        definition, session = started()
        assert get_current_node(definition, session).node_id == "q_specimen"

    def test_version_mismatch_is_gdl_201(self):
        definition, session = started()
        other = dataclasses.replace(definition, workflow_version=2)
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_current_node(other, session)
        assert excinfo.value.code is GuidedLabErrorCode.WORKFLOW_VERSION_MISMATCH

    def test_workflow_id_mismatch_is_gdl_201(self):
        definition, session = started()
        other = dataclasses.replace(definition, workflow_id="different")
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_current_node(other, session)
        assert excinfo.value.code is GuidedLabErrorCode.WORKFLOW_VERSION_MISMATCH

    def test_missing_current_node_is_gdl_202(self):
        definition, session = started()
        stray = dataclasses.replace(session, current_node_id="ghost")
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_current_node(definition, stray)
        assert excinfo.value.code is GuidedLabErrorCode.CURRENT_NODE_MISSING


class TestAnswering:
    def test_answer_records_the_value(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        assert session.answers[0].node_id == "q_specimen"
        assert session.answers[0].value == "top"
        assert session.answers[0].revision == 1
        assert session.updated_at == at(1)

    def test_answer_does_not_advance(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        assert session.current_node_id == "q_specimen"

    def test_wrong_action_for_node_is_gdl_301(self):
        definition, session = walk_top_branch_to_review()
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, "anything", answered_at=at(7))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_wrong_answer_type_is_gdl_302(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, 7, answered_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_TYPE_MISMATCH

    def test_value_outside_allowed_choices_is_gdl_303(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, "side", answered_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_numeric_bound_violation_is_gdl_303(self):
        from tap_tone_pi.guided_lab.models import (
            NumericConstraintV1,
            WorkflowAnswerKind,
        )

        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(
                    answer_kind=WorkflowAnswerKind.INTEGER,
                    constraints=NumericConstraintV1(minimum=1, maximum=5),
                ),
                make_complete_node(),
            ),
        )
        session = start_session(definition, session_id="s", started_at=T0)
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, 9, answered_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_text_length_violation_is_gdl_303(self):
        from tap_tone_pi.guided_lab.models import TextConstraintV1, WorkflowAnswerKind

        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(
                    answer_kind=WorkflowAnswerKind.TEXT,
                    constraints=TextConstraintV1(minimum_length=3),
                ),
                make_complete_node(),
            ),
        )
        session = start_session(definition, session_id="s", started_at=T0)
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, "ab", answered_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_boolean_answer_is_recorded_as_boolean(self):
        definition, session = walk_back_branch_to_evidence()
        boolean = [a for a in session.answers if a.node_id == "q_bool"][0]
        assert boolean.value is True


class TestTransitionSelection:
    def test_choice_selects_the_matching_branch(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        assert session.current_node_id == "i_prep"

    def test_other_choice_selects_the_other_branch(self):
        definition, session = started()
        session = answer_question(definition, session, "back", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        assert session.current_node_id == "q_bool"

    def test_boolean_true_branch(self):
        definition, session = walk_back_branch_to_evidence()
        assert session.current_node_id == "e_record"

    def test_boolean_false_branch(self):
        definition, session = started()
        session = answer_question(definition, session, "back", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = answer_question(definition, session, False, answered_at=at(3))
        session = advance_session(definition, session, advanced_at=at(4))
        assert session.current_node_id == "r_review"

    def test_advance_appends_to_visited_history(self):
        definition, session = walk_top_branch_to_review()
        assert session.visited_node_ids == (
            "q_specimen",
            "i_prep",
            "e_record",
            "r_review",
        )

    def test_advance_is_deterministic(self):
        first = walk_top_branch_to_review()[1]
        second = walk_top_branch_to_review()[1]
        assert first == second

    def test_advance_from_unanswered_question_is_rejected(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_advance_from_unacknowledged_instruction_is_rejected(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(3))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_no_matching_transition_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
            ),
        )
        session = start_session(definition, session_id="s", started_at=T0)
        session = answer_question(definition, session, "back", answered_at=at(1))
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(2))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_runtime_ambiguity_is_gdl_106(self):
        """Two conditions on different answers can both hold at runtime."""
        from tap_tone_pi.guided_lab.models import WorkflowAnswerKind

        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_question_node(
                    "q_other",
                    answer_kind=WorkflowAnswerKind.TEXT,
                    constraints=None,
                ),
                make_complete_node(),
            ),
            transitions=(
                make_transition(
                    "q_specimen",
                    "q_other",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
                make_transition(
                    "q_other",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_other",
                    expected_value="x",
                ),
                make_transition(
                    "q_other",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
            ),
        )
        session = start_session(definition, session_id="s", started_at=T0)
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = answer_question(definition, session, "x", answered_at=at(3))
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            advance_session(definition, session, advanced_at=at(4))
        assert excinfo.value.code is GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET


class TestInstructionsAndEvidence:
    def test_acknowledge_records_the_node(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = acknowledge_instruction(definition, session, acknowledged_at=at(3))
        assert session.acknowledged_node_ids == ("i_prep",)

    def test_acknowledge_is_idempotent(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = acknowledge_instruction(definition, session, acknowledged_at=at(3))
        session = acknowledge_instruction(definition, session, acknowledged_at=at(4))
        assert session.acknowledged_node_ids == ("i_prep",)

    def test_acknowledge_on_a_question_is_gdl_301(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            acknowledge_instruction(definition, session, acknowledged_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_attach_evidence_records_the_reference(self):
        definition, session = walk_back_branch_to_evidence()
        session = attach_evidence(
            definition, session, specimen_evidence(), attached_at=at(5)
        )
        assert session.evidence_references[0].evidence_id == "ev-specimen"
        assert session.evidence_references[0].attached_at == at(5)

    def test_attach_evidence_on_a_question_is_gdl_301(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            attach_evidence(definition, session, specimen_evidence(), attached_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_attach_evidence_of_an_unrequired_kind_is_gdl_303(self):
        definition, session = walk_back_branch_to_evidence()
        wrong = WorkflowEvidenceReferenceV1(
            evidence_id="ev-x",
            evidence_kind="unrelated_kind",
            source_system="tap_tone_pi",
        )
        with pytest.raises(GuidedLabActionError) as excinfo:
            attach_evidence(definition, session, wrong, attached_at=at(5))
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_reattaching_the_same_id_replaces_it(self):
        definition, session = walk_back_branch_to_evidence()
        session = attach_evidence(
            definition, session, specimen_evidence(), attached_at=at(5)
        )
        relabelled = dataclasses.replace(specimen_evidence(), label="Top plate")
        session = attach_evidence(definition, session, relabelled, attached_at=at(6))
        assert len(session.evidence_references) == 1
        assert session.evidence_references[0].label == "Top plate"

    def test_advance_without_required_evidence_is_gdl_304(self):
        definition, session = walk_back_branch_to_evidence()
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(5))
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING

    def test_advance_with_evidence_succeeds(self):
        definition, session = walk_back_branch_to_evidence()
        session = attach_evidence(
            definition, session, specimen_evidence(), attached_at=at(5)
        )
        session = advance_session(definition, session, advanced_at=at(6))
        assert session.current_node_id == "r_review"

    def test_attach_stamps_the_step_the_evidence_was_attached_at(self):
        definition, session = walk_back_branch_to_evidence()
        session = attach_evidence(
            definition, session, specimen_evidence(), attached_at=at(5)
        )
        assert session.evidence_references[0].attached_node_id == "e_record"

    def test_the_engine_overrides_a_caller_supplied_stamp(self):
        """Where evidence was attached is the engine's fact, not the caller's."""
        definition, session = walk_back_branch_to_evidence()
        misstamped = dataclasses.replace(
            specimen_evidence(), attached_node_id="somewhere_else"
        )
        session = attach_evidence(definition, session, misstamped, attached_at=at(5))
        assert session.evidence_references[0].attached_node_id == "e_record"

    def test_two_steps_of_the_same_kind_do_not_satisfy_each_other(self):
        """A second requirement for a kind needs its own reference."""
        definition = make_two_stage_evidence_definition()
        session = start_session(definition, session_id="s", started_at=T0)
        session = attach_evidence(
            definition, session, specimen_evidence("ev-first"), attached_at=at(1)
        )
        session = advance_session(definition, session, advanced_at=at(2))
        assert session.current_node_id == "e_second"

        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(3))
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING
        assert excinfo.value.context["attached_count"] == 0

    def test_an_unstamped_reference_is_still_counted_by_kind(self):
        """Records written by hand have no attachment site to check."""
        definition = make_two_stage_evidence_definition()
        session = start_session(definition, session_id="s", started_at=T0)
        session = dataclasses.replace(
            session, evidence_references=(specimen_evidence("ev-hand-written"),)
        )
        session = advance_session(definition, session, advanced_at=at(1))
        assert session.current_node_id == "e_second"

    def test_minimum_count_blocks_until_satisfied(self):
        definition = make_branching_definition()
        nodes = tuple(
            dataclasses.replace(node, minimum_count=2)
            if node.node_id == "e_record"
            else node
            for node in definition.nodes
        )
        definition = dataclasses.replace(definition, nodes=nodes)
        session = start_session(definition, session_id="s", started_at=T0)
        session = answer_question(definition, session, "back", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = answer_question(definition, session, True, answered_at=at(3))
        session = advance_session(definition, session, advanced_at=at(4))
        session = attach_evidence(
            definition, session, specimen_evidence("ev-a"), attached_at=at(5)
        )
        with pytest.raises(GuidedLabActionError):
            advance_session(definition, session, advanced_at=at(6))
        session = attach_evidence(
            definition, session, specimen_evidence("ev-b"), attached_at=at(7)
        )
        session = advance_session(definition, session, advanced_at=at(8))
        assert session.current_node_id == "r_review"


class TestBackNavigation:
    def test_back_follows_visited_history(self):
        definition, session = walk_top_branch_to_review()
        session = go_back(definition, session, moved_at=at(7))
        assert session.current_node_id == "e_record"
        assert session.visited_node_ids == ("q_specimen", "i_prep", "e_record")

    def test_back_from_the_entry_node_is_gdl_305(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            go_back(definition, session, moved_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.BACK_NAVIGATION_UNAVAILABLE

    def test_back_preserves_answers(self):
        definition, session = walk_top_branch_to_review()
        session = go_back(definition, session, moved_at=at(7))
        assert [a.node_id for a in session.answers] == ["q_specimen"]

    def test_back_then_advance_returns_along_the_same_path(self):
        definition, session = walk_top_branch_to_review()
        session = go_back(definition, session, moved_at=at(7))
        session = advance_session(definition, session, advanced_at=at(8))
        assert session.current_node_id == "r_review"

    def test_back_to_a_step_keeps_its_answer(self):
        """Landing on a step shows what is there, so it can be corrected."""
        definition, session = walk_back_branch_to_evidence()
        session = go_back(definition, session, moved_at=at(5))
        assert session.current_node_id == "q_bool"
        assert [a.node_id for a in session.answers] == ["q_specimen", "q_bool"]

    def test_back_past_a_step_discards_its_answer(self):
        """The abandoned step's state goes with it, as on a correction."""
        definition, session = walk_back_branch_to_evidence()
        session = go_back(definition, session, moved_at=at(5))
        session = go_back(definition, session, moved_at=at(6))
        assert session.current_node_id == "q_specimen"
        assert [a.node_id for a in session.answers] == ["q_specimen"]

    def test_back_discards_the_acknowledgment_on_the_step_being_left(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = acknowledge_instruction(definition, session, acknowledged_at=at(3))
        session = advance_session(definition, session, advanced_at=at(4))
        assert session.acknowledged_node_ids == ("i_prep",)

        # Back to i_prep keeps it; back again leaves it behind.
        session = go_back(definition, session, moved_at=at(5))
        assert session.acknowledged_node_ids == ("i_prep",)
        session = go_back(definition, session, moved_at=at(6))
        assert session.acknowledged_node_ids == ()

    def test_back_discards_evidence_attached_at_the_step_being_left(self):
        definition, session = walk_top_branch_to_review()
        assert len(session.evidence_references) == 1

        # Back to e_record: the evidence belongs to the step we are standing on.
        session = go_back(definition, session, moved_at=at(7))
        assert len(session.evidence_references) == 1

        # Back past e_record: the step is abandoned and so is its evidence.
        session = go_back(definition, session, moved_at=at(8))
        assert session.current_node_id == "i_prep"
        assert session.evidence_references == ()

    def test_back_does_not_leave_a_later_step_satisfied(self):
        """Re-advancing after a step back must re-ask, not inherit."""
        definition, session = walk_top_branch_to_review()
        session = go_back(definition, session, moved_at=at(7))
        session = go_back(definition, session, moved_at=at(8))
        session = advance_session(definition, session, advanced_at=at(9))
        assert session.current_node_id == "e_record"

        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=at(10))
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING

    def test_back_leaves_the_history_ending_where_the_session_stands(self):
        definition, session = walk_top_branch_to_review()
        session = go_back(definition, session, moved_at=at(7))
        assert session.visited_node_ids[-1] == session.current_node_id


class TestHistoryIntegrity:
    def test_history_not_ending_at_the_current_step_is_gdl_204(self):
        definition, session = walk_top_branch_to_review()
        tampered = dataclasses.replace(session, current_node_id="i_prep")
        with pytest.raises(GuidedLabSessionError) as excinfo:
            advance_session(definition, tampered, advanced_at=at(9))
        assert excinfo.value.code is GuidedLabErrorCode.CORRUPTED_HISTORY

    def test_empty_history_is_gdl_204(self):
        definition, session = started()
        tampered = dataclasses.replace(session, visited_node_ids=())
        with pytest.raises(GuidedLabSessionError) as excinfo:
            answer_question(definition, tampered, "top", answered_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.CORRUPTED_HISTORY

    def test_a_damaged_record_can_still_be_read(self):
        """Inspection is not an action; a corrupt session stays readable."""
        definition, session = walk_top_branch_to_review()
        tampered = dataclasses.replace(session, current_node_id="i_prep")
        assert get_current_node(definition, tampered).node_id == "i_prep"
        assert get_workflow_progress(definition, tampered).current_node_id == "i_prep"

    def test_a_missing_node_still_reports_gdl_202_first(self):
        definition, session = started()
        stray = dataclasses.replace(session, current_node_id="ghost")
        with pytest.raises(GuidedLabSessionError) as excinfo:
            advance_session(definition, stray, advanced_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.CURRENT_NODE_MISSING


class TestLifecycle:
    def test_pause_and_resume_preserve_state(self):
        definition, session = walk_top_branch_to_review()
        paused = pause_session(definition, session, paused_at=at(7))
        assert paused.status is GuidedLabSessionStatus.PAUSED
        resumed = resume_session(definition, paused, resumed_at=at(8))
        assert resumed.status is GuidedLabSessionStatus.ACTIVE
        assert resumed.current_node_id == session.current_node_id
        assert resumed.visited_node_ids == session.visited_node_ids
        assert resumed.answers == session.answers

    def test_actions_are_rejected_while_paused(self):
        definition, session = started()
        paused = pause_session(definition, session, paused_at=at(1))
        with pytest.raises(GuidedLabSessionError) as excinfo:
            answer_question(definition, paused, "top", answered_at=at(2))
        assert excinfo.value.code is GuidedLabErrorCode.INVALID_STATUS_TRANSITION

    def test_pausing_a_paused_session_is_gdl_203(self):
        definition, session = started()
        paused = pause_session(definition, session, paused_at=at(1))
        with pytest.raises(GuidedLabSessionError) as excinfo:
            pause_session(definition, paused, paused_at=at(2))
        assert excinfo.value.code is GuidedLabErrorCode.INVALID_STATUS_TRANSITION

    def test_resuming_an_active_session_is_gdl_203(self):
        definition, session = started()
        with pytest.raises(GuidedLabSessionError) as excinfo:
            resume_session(definition, session, resumed_at=at(1))
        assert excinfo.value.code is GuidedLabErrorCode.INVALID_STATUS_TRANSITION

    def test_abandon_marks_the_session_terminal(self):
        definition, session = started()
        abandoned = abandon_session(definition, session, abandoned_at=at(1))
        assert abandoned.status is GuidedLabSessionStatus.ABANDONED

    def test_abandoned_session_rejects_mutation_with_gdl_205(self):
        definition, session = started()
        abandoned = abandon_session(definition, session, abandoned_at=at(1))
        with pytest.raises(GuidedLabSessionError) as excinfo:
            answer_question(definition, abandoned, "top", answered_at=at(2))
        assert excinfo.value.code is GuidedLabErrorCode.SESSION_ALREADY_TERMINAL

    def test_completion_requires_the_complete_node(self):
        definition, session = walk_top_branch_to_review()
        with pytest.raises(GuidedLabActionError) as excinfo:
            complete_session(definition, session, completed_at=at(7))
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_completion_sets_status_and_timestamp(self):
        definition, session = walk_top_branch_to_review()
        session = advance_session(definition, session, advanced_at=at(7))
        assert session.current_node_id == "c_done"
        session = complete_session(definition, session, completed_at=at(8))
        assert session.status is GuidedLabSessionStatus.COMPLETED
        assert session.completed_at == at(8)

    def test_completed_session_rejects_mutation_with_gdl_205(self):
        definition, session = walk_top_branch_to_review()
        session = advance_session(definition, session, advanced_at=at(7))
        session = complete_session(definition, session, completed_at=at(8))
        with pytest.raises(GuidedLabSessionError) as excinfo:
            advance_session(definition, session, advanced_at=at(9))
        assert excinfo.value.code is GuidedLabErrorCode.SESSION_ALREADY_TERMINAL

    def test_completed_session_survives_serialization(self):
        from tap_tone_pi.guided_lab import GuidedLabSessionV1

        definition, session = walk_top_branch_to_review()
        session = advance_session(definition, session, advanced_at=at(7))
        session = complete_session(definition, session, completed_at=at(8))
        assert GuidedLabSessionV1.from_dict(session.to_dict()) == session


class TestProgress:
    def test_progress_counts_state(self):
        definition, session = walk_top_branch_to_review()
        progress = get_workflow_progress(definition, session)
        assert progress.current_node_id == "r_review"
        assert progress.visited_count == 4
        assert progress.answered_count == 1
        assert progress.evidence_count == 1

    def test_progress_reports_missing_requirements(self):
        definition, session = walk_back_branch_to_evidence()
        progress = get_workflow_progress(definition, session)
        assert "e_record" in progress.missing_required_node_ids
        assert progress.may_complete is False

    def test_progress_allows_completion_on_the_complete_node(self):
        definition, session = walk_top_branch_to_review()
        session = advance_session(definition, session, advanced_at=at(7))
        progress = get_workflow_progress(definition, session)
        assert progress.missing_required_node_ids == ()
        assert progress.may_complete is True


class TestAnswerReplacement:
    def test_replacing_an_unanswered_node_is_gdl_306(self):
        definition, session = started()
        with pytest.raises(GuidedLabActionError) as excinfo:
            replace_answer(
                definition,
                session,
                node_id="q_specimen",
                value="top",
                answered_at=at(1),
            )
        assert excinfo.value.code is GuidedLabErrorCode.REPLACEMENT_TARGET_NOT_ANSWERED

    def test_replacement_increments_the_revision(self):
        definition, session = walk_top_branch_to_review()
        session = replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(7)
        )
        answer = [a for a in session.answers if a.node_id == "q_specimen"][0]
        assert answer.revision == 2
        assert answer.value == "back"

    def test_replacement_moves_to_the_new_branch(self):
        definition, session = walk_top_branch_to_review()
        session = replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(7)
        )
        assert session.current_node_id == "q_bool"
        assert session.visited_node_ids == ("q_specimen", "q_bool")

    def test_replacement_removes_downstream_acknowledgments(self):
        definition, session = walk_top_branch_to_review()
        assert session.acknowledged_node_ids == ("i_prep",)
        session = replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(7)
        )
        assert session.acknowledged_node_ids == ()

    def test_replacement_removes_downstream_evidence(self):
        definition, session = walk_top_branch_to_review()
        assert len(session.evidence_references) == 1
        session = replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(7)
        )
        assert session.evidence_references == ()

    def test_replacement_removes_downstream_answers(self):
        definition, session = walk_back_branch_to_evidence()
        assert {a.node_id for a in session.answers} == {"q_specimen", "q_bool"}
        session = replace_answer(
            definition, session, node_id="q_specimen", value="top", answered_at=at(5)
        )
        assert {a.node_id for a in session.answers} == {"q_specimen"}
        assert session.current_node_id == "i_prep"

    def test_replacement_preserves_upstream_state(self):
        definition, session = walk_back_branch_to_evidence()
        session = replace_answer(
            definition, session, node_id="q_bool", value=False, answered_at=at(5)
        )
        specimen = [a for a in session.answers if a.node_id == "q_specimen"][0]
        assert specimen.value == "back"
        assert specimen.revision == 1
        assert specimen.answered_at == at(1)

    def test_replacement_with_the_same_value_keeps_position(self):
        definition, session = walk_top_branch_to_review()
        session = replace_answer(
            definition, session, node_id="q_specimen", value="top", answered_at=at(7)
        )
        assert session.current_node_id == "r_review"
        assert session.acknowledged_node_ids == ("i_prep",)
        assert len(session.evidence_references) == 1

    def test_replacement_does_not_jump_ahead(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = replace_answer(
            definition, session, node_id="q_specimen", value="top", answered_at=at(2)
        )
        assert session.current_node_id == "q_specimen"

    def test_replacement_rejects_an_invalid_value(self):
        definition, session = walk_top_branch_to_review()
        with pytest.raises(GuidedLabActionError) as excinfo:
            replace_answer(
                definition,
                session,
                node_id="q_specimen",
                value="side",
                answered_at=at(7),
            )
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_replacement_keeps_evidence_belonging_to_a_step_still_on_the_path(self):
        """Same kind, different step: retention follows the step, not the name."""
        definition = make_two_stage_evidence_definition()
        definition = dataclasses.replace(
            definition,
            entry_node_id="q_specimen",
            nodes=definition.nodes + (make_question_node(),),
            transitions=(
                make_transition("q_specimen", "e_first"),
                make_transition("e_first", "e_second"),
                make_transition("e_second", "c_done"),
            ),
        )
        session = start_session(definition, session_id="s", started_at=T0)
        session = answer_question(definition, session, "top", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = attach_evidence(
            definition, session, specimen_evidence("ev-first"), attached_at=at(3)
        )
        session = advance_session(definition, session, advanced_at=at(4))
        session = attach_evidence(
            definition, session, specimen_evidence("ev-second"), attached_at=at(5)
        )

        # The correction changes nothing about the route, so both survive.
        session = replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(6)
        )
        assert [e.evidence_id for e in session.evidence_references] == [
            "ev-first",
            "ev-second",
        ]

        # Stepping back off e_second drops only the reference attached there,
        # even though e_first asks for exactly the same kind.
        session = go_back(definition, session, moved_at=at(7))
        assert [e.evidence_id for e in session.evidence_references] == ["ev-first"]

    def test_ambiguity_found_while_replaying_is_gdl_106(self):
        """A replay that cannot say where the operator goes says so."""
        definition = make_runtime_ambiguity_definition()
        session = start_session(definition, session_id="s", started_at=T0)
        session = answer_question(definition, session, "back", answered_at=at(1))
        session = advance_session(definition, session, advanced_at=at(2))
        session = attach_evidence(
            definition, session, specimen_evidence(), attached_at=at(3)
        )
        session = advance_session(definition, session, advanced_at=at(4))
        assert session.current_node_id == "c_by_evidence"

        with pytest.raises(WorkflowDefinitionError) as excinfo:
            replace_answer(
                definition,
                session,
                node_id="q_specimen",
                value="top",
                answered_at=at(5),
            )
        assert excinfo.value.code is GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET
        assert excinfo.value.context["node_id"] == "e_gate"

    def test_the_ambiguous_definition_passes_static_validation(self):
        """Which is the point: the engine is the last line, not the only one."""
        from tap_tone_pi.guided_lab.validation import validate_workflow_definition

        assert validate_workflow_definition(make_runtime_ambiguity_definition()) == ()

    def test_replacement_is_deterministic(self):
        definition, first = walk_top_branch_to_review()
        _, second = walk_top_branch_to_review()
        first = replace_answer(
            definition, first, node_id="q_specimen", value="back", answered_at=at(7)
        )
        second = replace_answer(
            definition, second, node_id="q_specimen", value="back", answered_at=at(7)
        )
        assert first == second


class TestImmutability:
    def test_answer_does_not_mutate_the_input_session(self):
        definition, session = started()
        before = session.to_dict()
        answer_question(definition, session, "top", answered_at=at(1))
        assert session.to_dict() == before

    def test_advance_does_not_mutate_the_input_session(self):
        definition, session = started()
        session = answer_question(definition, session, "top", answered_at=at(1))
        before = session.to_dict()
        advance_session(definition, session, advanced_at=at(2))
        assert session.to_dict() == before

    def test_replacement_does_not_mutate_the_input_session(self):
        definition, session = walk_top_branch_to_review()
        before = session.to_dict()
        replace_answer(
            definition, session, node_id="q_specimen", value="back", answered_at=at(7)
        )
        assert session.to_dict() == before

    def test_engine_does_not_mutate_the_definition(self):
        definition, session = started()
        before = definition.to_dict()
        session = answer_question(definition, session, "top", answered_at=at(1))
        advance_session(definition, session, advanced_at=at(2))
        assert definition.to_dict() == before


class TestEvidenceIdentifierScope:
    """Re-attaching an identifier supersedes this step's entry, not an earlier one.

    Replacement used to match on ``evidence_id`` alone, so reusing one
    identifier at a second step deleted it from the first. The operator was left
    standing past a step that had silently become unmet, discovering it only
    when completion refused — with nothing to say which action caused it.
    """

    def _at_the_second_step(self):
        definition = make_two_stage_evidence_definition()
        session = start_session(definition, session_id="s-ev", started_at=T0)
        session = attach_evidence(
            definition, session, specimen_evidence("shared-id"), attached_at=at(1)
        )
        return definition, advance_session(definition, session, advanced_at=at(2))

    def test_reusing_an_identifier_later_keeps_the_earlier_entry(self):
        definition, session = self._at_the_second_step()
        session = attach_evidence(
            definition, session, specimen_evidence("shared-id"), attached_at=at(3)
        )
        assert [r.attached_node_id for r in session.evidence_references] == [
            "e_first",
            "e_second",
        ]

    def test_the_earlier_step_stays_satisfied(self):
        definition, session = self._at_the_second_step()
        session = attach_evidence(
            definition, session, specimen_evidence("shared-id"), attached_at=at(3)
        )
        assert (
            get_workflow_progress(definition, session).missing_required_node_ids == ()
        )

    def test_the_record_can_still_be_completed(self):
        definition, session = self._at_the_second_step()
        session = attach_evidence(
            definition, session, specimen_evidence("shared-id"), attached_at=at(3)
        )
        session = advance_session(definition, session, advanced_at=at(4))
        session = complete_session(definition, session, completed_at=at(5))
        assert session.status is GuidedLabSessionStatus.COMPLETED

    def test_reattaching_at_the_same_step_still_replaces(self):
        definition, session = self._at_the_second_step()
        session = attach_evidence(
            definition,
            session,
            dataclasses.replace(specimen_evidence("shared-id"), label="first"),
            attached_at=at(3),
        )
        session = attach_evidence(
            definition,
            session,
            dataclasses.replace(specimen_evidence("shared-id"), label="second"),
            attached_at=at(4),
        )
        here = [
            r for r in session.evidence_references if r.attached_node_id == "e_second"
        ]
        assert len(here) == 1
        assert here[0].label == "second"

    def test_an_unstamped_reference_is_adopted_rather_than_duplicated(self):
        definition, session = self._at_the_second_step()
        session = dataclasses.replace(
            session,
            evidence_references=(
                dataclasses.replace(
                    session.evidence_references[0], attached_node_id=None
                ),
            ),
        )
        session = attach_evidence(
            definition, session, specimen_evidence("shared-id"), attached_at=at(3)
        )
        assert len(session.evidence_references) == 1
        assert session.evidence_references[0].attached_node_id == "e_second"

    def test_distinct_identifiers_are_unaffected(self):
        definition, session = self._at_the_second_step()
        session = attach_evidence(
            definition, session, specimen_evidence("other-id"), attached_at=at(3)
        )
        assert [r.evidence_id for r in session.evidence_references] == [
            "shared-id",
            "other-id",
        ]

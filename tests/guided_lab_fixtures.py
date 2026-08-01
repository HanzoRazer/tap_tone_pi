"""Shared builders for guided laboratory tests (DO-100).

Every builder produces a valid default so each test changes only the one
property it is about. Used by the validation, engine, and CLI test modules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tap_tone_pi.guided_lab.models import (
    ChoiceConstraintV1,
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    GuidedLabSessionStatus,
    GuidedLabSessionV1,
    InstructionNodeV1,
    QuestionNodeV1,
    ReviewNodeV1,
    SourceAuthorityStatus,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowDefinitionV1,
    WorkflowSourceReferenceV1,
    WorkflowTransitionConditionV1,
    WorkflowTransitionV1,
)

FIXED_START = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)

PROVISIONAL_SOURCE = WorkflowSourceReferenceV1(
    source_reference_id="src_fixture",
    title="Fixture procedure text",
    citation="Internal test fixture",
    authority_status=SourceAuthorityStatus.PROVISIONAL,
)


def make_question_node(
    node_id: str = "q_specimen",
    *,
    answer_kind: WorkflowAnswerKind = WorkflowAnswerKind.SINGLE_CHOICE,
    constraints=ChoiceConstraintV1(allowed_values=("top", "back")),
    required: bool = True,
) -> QuestionNodeV1:
    return QuestionNodeV1(
        node_id=node_id,
        title=f"Question {node_id}",
        body="Answer this step.",
        answer_kind=answer_kind,
        constraints=constraints,
        required=required,
    )


def make_boolean_node(node_id: str = "q_bool") -> QuestionNodeV1:
    return QuestionNodeV1(
        node_id=node_id,
        title=f"Question {node_id}",
        body="Answer yes or no.",
        answer_kind=WorkflowAnswerKind.BOOLEAN,
    )


def make_instruction_node(
    node_id: str = "i_prep",
    *,
    source_reference_ids: tuple[str, ...] = ("src_fixture",),
) -> InstructionNodeV1:
    return InstructionNodeV1(
        node_id=node_id,
        title=f"Instruction {node_id}",
        body="Set the bench up as described.",
        source_reference_ids=source_reference_ids,
    )


def make_evidence_node(
    node_id: str = "e_record",
    *,
    required_evidence_kinds: tuple[str, ...] = ("specimen_record",),
    minimum_count: int = 1,
) -> EvidenceRequirementNodeV1:
    return EvidenceRequirementNodeV1(
        node_id=node_id,
        title=f"Evidence {node_id}",
        body="Attach the reference for this step.",
        required_evidence_kinds=required_evidence_kinds,
        minimum_count=minimum_count,
    )


def make_review_node(
    node_id: str = "r_review",
    *,
    required_node_ids: tuple[str, ...] = (),
) -> ReviewNodeV1:
    return ReviewNodeV1(
        node_id=node_id,
        title="Review the record",
        body="Check each entry before closing the record.",
        required_node_ids=required_node_ids,
    )


def make_complete_node(node_id: str = "c_done") -> CompleteNodeV1:
    return CompleteNodeV1(
        node_id=node_id,
        title="Setup record complete",
        body="The workflow record is closed.",
        completion_message="Setup workflow record complete.",
    )


def make_transition(
    from_node_id: str,
    to_node_id: str,
    *,
    kind: TransitionConditionKind = TransitionConditionKind.ALWAYS,
    node_id: str | None = None,
    expected_value=None,
    expected_values: tuple = (),
    evidence_kind: str | None = None,
) -> WorkflowTransitionV1:
    return WorkflowTransitionV1(
        from_node_id=from_node_id,
        condition=WorkflowTransitionConditionV1(
            kind=kind,
            node_id=node_id,
            expected_value=expected_value,
            expected_values=expected_values,
            evidence_kind=evidence_kind,
        ),
        to_node_id=to_node_id,
    )


def make_minimal_valid_definition(
    *,
    workflow_id: str = "fixture_workflow",
    workflow_version: int = 1,
) -> WorkflowDefinitionV1:
    """A two-node workflow: one question, then completion."""
    return WorkflowDefinitionV1(
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        title="Fixture workflow",
        purpose="Exercise the guided laboratory engine.",
        entry_node_id="q_specimen",
        nodes=(make_question_node(), make_complete_node()),
        transitions=(make_transition("q_specimen", "c_done"),),
        source_references=(PROVISIONAL_SOURCE,),
    )


def make_branching_definition() -> WorkflowDefinitionV1:
    """A workflow with a choice branch, an instruction, and an evidence gate.

    Shape::

        q_specimen --top--> i_prep --> e_record --> r_review --> c_done
                   --back-> q_bool --true--> e_record
                                   --false-> r_review
    """
    return WorkflowDefinitionV1(
        workflow_id="branching_fixture",
        workflow_version=1,
        title="Branching fixture workflow",
        purpose="Exercise branching, evidence, and review.",
        entry_node_id="q_specimen",
        nodes=(
            make_question_node(),
            make_boolean_node(),
            make_instruction_node(),
            make_evidence_node(),
            make_review_node(required_node_ids=("q_specimen",)),
            make_complete_node(),
        ),
        transitions=(
            make_transition(
                "q_specimen",
                "i_prep",
                kind=TransitionConditionKind.ANSWER_EQUALS,
                node_id="q_specimen",
                expected_value="top",
            ),
            make_transition(
                "q_specimen",
                "q_bool",
                kind=TransitionConditionKind.ANSWER_EQUALS,
                node_id="q_specimen",
                expected_value="back",
            ),
            make_transition(
                "q_bool",
                "e_record",
                kind=TransitionConditionKind.BOOLEAN_TRUE,
                node_id="q_bool",
            ),
            make_transition(
                "q_bool",
                "r_review",
                kind=TransitionConditionKind.BOOLEAN_FALSE,
                node_id="q_bool",
            ),
            make_transition("i_prep", "e_record"),
            make_transition("e_record", "r_review"),
            make_transition("r_review", "c_done"),
        ),
        source_references=(PROVISIONAL_SOURCE,),
    )


def make_active_session(
    definition: WorkflowDefinitionV1 | None = None,
    *,
    session_id: str = "session-fixture",
    status: GuidedLabSessionStatus = GuidedLabSessionStatus.ACTIVE,
) -> GuidedLabSessionV1:
    definition = definition or make_minimal_valid_definition()
    return GuidedLabSessionV1(
        session_id=session_id,
        workflow_id=definition.workflow_id,
        workflow_version=definition.workflow_version,
        status=status,
        current_node_id=definition.entry_node_id,
        started_at=FIXED_START,
        updated_at=FIXED_START,
        visited_node_ids=(definition.entry_node_id,),
    )

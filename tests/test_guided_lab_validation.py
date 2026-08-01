"""Workflow definition validation rules (DO-100).

Every GDL-1xx code has its own test. Validation is pure: it inspects a
definition's graph and never executes a transition.
"""

from __future__ import annotations

import dataclasses

import pytest

from tap_tone_pi.guided_lab import (
    GuidedLabErrorCode,
    WorkflowDefinitionError,
    raise_for_findings,
)
from tap_tone_pi.guided_lab.models import (
    ChoiceConstraintV1,
    NumericConstraintV1,
    SourceAuthorityStatus,
    TextConstraintV1,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowDefinitionV1,
    WorkflowSourceReferenceV1,
)
from tap_tone_pi.guided_lab.validation import (
    require_unique_workflow_keys,
    require_valid_workflow_definition,
    validate_workflow_definition,
)
from tests.guided_lab_fixtures import (
    make_boolean_node,
    make_branching_definition,
    make_complete_node,
    make_evidence_node,
    make_instruction_node,
    make_minimal_valid_definition,
    make_question_node,
    make_review_node,
    make_transition,
)


def codes(definition: WorkflowDefinitionV1) -> list[str]:
    return [f.code.value for f in validate_workflow_definition(definition)]


class TestValidDefinitions:
    def test_minimal_definition_has_no_findings(self):
        assert validate_workflow_definition(make_minimal_valid_definition()) == ()

    def test_branching_definition_has_no_findings(self):
        assert validate_workflow_definition(make_branching_definition()) == ()

    def test_require_valid_accepts_a_good_definition(self):
        require_valid_workflow_definition(make_minimal_valid_definition())

    def test_findings_are_returned_as_a_tuple(self):
        assert isinstance(
            validate_workflow_definition(make_minimal_valid_definition()), tuple
        )


class TestDuplicateNodeId:
    def test_gdl_101(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_question_node(),
                make_complete_node(),
            ),
        )
        assert GuidedLabErrorCode.DUPLICATE_NODE_ID.value in codes(definition)

    def test_finding_names_the_duplicated_node(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_question_node(), make_question_node(), make_complete_node()),
        )
        duplicate = [
            f
            for f in validate_workflow_definition(definition)
            if f.code is GuidedLabErrorCode.DUPLICATE_NODE_ID
        ]
        assert duplicate[0].node_id == "q_specimen"


class TestMissingEntryNode:
    def test_gdl_102_when_entry_is_not_a_declared_node(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), entry_node_id="not_a_node"
        )
        assert GuidedLabErrorCode.MISSING_ENTRY_NODE.value in codes(definition)

    def test_gdl_102_when_there_are_no_nodes(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), nodes=(), transitions=()
        )
        assert GuidedLabErrorCode.MISSING_ENTRY_NODE.value in codes(definition)


class TestUnknownTransitionNode:
    def test_gdl_103_unknown_source(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition("q_specimen", "c_done"),
                make_transition("ghost", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE.value in codes(definition)

    def test_gdl_103_unknown_target(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(make_transition("q_specimen", "ghost"),),
        )
        assert GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE.value in codes(definition)

    def test_gdl_103_unknown_condition_node(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="ghost",
                    expected_value="top",
                ),
            ),
        )
        assert GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE.value in codes(definition)

    def test_finding_records_the_transition_index(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition("q_specimen", "c_done"),
                make_transition("q_specimen", "ghost"),
            ),
        )
        unknown = [
            f
            for f in validate_workflow_definition(definition)
            if f.code is GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE
        ]
        assert unknown[0].transition_index == 1


class TestUnreachableRequiredNode:
    def test_gdl_104(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_question_node("q_orphan"),
                make_complete_node(),
            ),
        )
        assert GuidedLabErrorCode.UNREACHABLE_REQUIRED_NODE.value in codes(definition)

    def test_optional_unreachable_node_is_not_reported(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_question_node("q_orphan", required=False),
                make_complete_node(),
            ),
        )
        assert GuidedLabErrorCode.UNREACHABLE_REQUIRED_NODE.value not in codes(
            definition
        )


class TestNoCompletionReachable:
    def test_gdl_105_when_no_complete_node_exists(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_question_node(), make_review_node()),
            transitions=(make_transition("q_specimen", "r_review"),),
        )
        assert GuidedLabErrorCode.NO_COMPLETION_REACHABLE.value in codes(definition)

    def test_gdl_105_when_a_reachable_node_dead_ends(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_review_node(),
                make_complete_node(),
            ),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
                make_transition(
                    "q_specimen",
                    "r_review",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="back",
                ),
            ),
        )
        findings = [
            f
            for f in validate_workflow_definition(definition)
            if f.code is GuidedLabErrorCode.NO_COMPLETION_REACHABLE
        ]
        assert findings and findings[0].node_id == "r_review"


class TestAmbiguousTransitions:
    def test_gdl_106_two_always_transitions(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_question_node(), make_review_node(), make_complete_node()),
            transitions=(
                make_transition("q_specimen", "c_done"),
                make_transition("q_specimen", "r_review"),
                make_transition("r_review", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET.value in codes(definition)

    def test_gdl_106_always_alongside_a_conditional(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition("q_specimen", "c_done"),
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
            ),
        )
        assert GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET.value in codes(definition)

    def test_gdl_106_overlapping_expected_values(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_question_node(), make_review_node(), make_complete_node()),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="top",
                ),
                make_transition(
                    "q_specimen",
                    "r_review",
                    kind=TransitionConditionKind.ANSWER_IN_SET,
                    node_id="q_specimen",
                    expected_values=("top", "back"),
                ),
                make_transition("r_review", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET.value in codes(definition)

    def test_disjoint_conditions_are_not_ambiguous(self):
        assert GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET.value not in codes(
            make_branching_definition()
        )

    def test_gdl_106_duplicate_boolean_true(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_boolean_node(), make_review_node(), make_complete_node()),
            entry_node_id="q_bool",
            transitions=(
                make_transition(
                    "q_bool",
                    "c_done",
                    kind=TransitionConditionKind.BOOLEAN_TRUE,
                    node_id="q_bool",
                ),
                make_transition(
                    "q_bool",
                    "r_review",
                    kind=TransitionConditionKind.BOOLEAN_TRUE,
                    node_id="q_bool",
                ),
                make_transition("r_review", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET.value in codes(definition)


class TestUnsupportedAnswerKind:
    def test_gdl_107_boolean_condition_on_a_choice_question(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.BOOLEAN_TRUE,
                    node_id="q_specimen",
                ),
            ),
        )
        assert GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND.value in codes(definition)

    def test_gdl_107_answer_condition_on_a_non_question_node(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_instruction_node(),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "i_prep"),
                make_transition(
                    "i_prep",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="i_prep",
                    expected_value="x",
                ),
            ),
        )
        assert GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND.value in codes(definition)

    def test_gdl_107_expected_value_type_mismatch(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value=7,
                ),
            ),
        )
        assert GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND.value in codes(definition)

    def test_gdl_107_expected_value_outside_allowed_values(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                    expected_value="side",
                ),
            ),
        )
        assert GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND.value in codes(definition)


class TestInvalidQuestionConstraints:
    def test_gdl_108_single_choice_without_choice_constraint(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(constraints=None),
                make_complete_node(),
            ),
        )
        assert GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS.value in codes(
            definition
        )

    def test_gdl_108_numeric_constraint_on_a_text_question(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(
                    answer_kind=WorkflowAnswerKind.TEXT,
                    constraints=NumericConstraintV1(minimum=0),
                ),
                make_complete_node(),
            ),
            transitions=(make_transition("q_specimen", "c_done"),),
        )
        assert GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS.value in codes(
            definition
        )

    def test_gdl_108_choice_constraint_on_a_boolean_question(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(
                    answer_kind=WorkflowAnswerKind.BOOLEAN,
                    constraints=ChoiceConstraintV1(allowed_values=("yes",)),
                ),
                make_complete_node(),
            ),
        )
        assert GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS.value in codes(
            definition
        )

    def test_text_constraint_on_a_text_question_is_accepted(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(
                    answer_kind=WorkflowAnswerKind.TEXT,
                    constraints=TextConstraintV1(minimum_length=1),
                ),
                make_complete_node(),
            ),
        )
        assert validate_workflow_definition(definition) == ()

    def test_gdl_108_evidence_node_with_no_required_kinds(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_evidence_node(required_evidence_kinds=()),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "e_record"),
                make_transition("e_record", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS.value in codes(
            definition
        )

    def test_gdl_108_evidence_node_with_non_positive_minimum(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_evidence_node(minimum_count=0),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "e_record"),
                make_transition("e_record", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS.value in codes(
            definition
        )


class TestMissingSourceReference:
    def test_gdl_109_instruction_without_any_source(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_instruction_node(source_reference_ids=()),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "i_prep"),
                make_transition("i_prep", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.MISSING_SOURCE_REFERENCE.value in codes(definition)

    def test_gdl_109_dangling_source_reference_id(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_instruction_node(source_reference_ids=("src_absent",)),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "i_prep"),
                make_transition("i_prep", "c_done"),
            ),
        )
        assert GuidedLabErrorCode.MISSING_SOURCE_REFERENCE.value in codes(definition)

    def test_provisional_source_satisfies_the_requirement(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(
                make_question_node(),
                make_instruction_node(),
                make_complete_node(),
            ),
            transitions=(
                make_transition("q_specimen", "i_prep"),
                make_transition("i_prep", "c_done"),
            ),
        )
        assert validate_workflow_definition(definition) == ()

    def test_gdl_109_duplicate_source_reference_id(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            source_references=(
                WorkflowSourceReferenceV1(
                    source_reference_id="src_fixture",
                    title="One",
                    citation="a",
                    authority_status=SourceAuthorityStatus.PROVISIONAL,
                ),
                WorkflowSourceReferenceV1(
                    source_reference_id="src_fixture",
                    title="Two",
                    citation="b",
                    authority_status=SourceAuthorityStatus.SUPPORTING,
                ),
            ),
        )
        assert GuidedLabErrorCode.MISSING_SOURCE_REFERENCE.value in codes(definition)


class TestInvalidTransitionCondition:
    def test_gdl_110_always_carrying_expected_values(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ALWAYS,
                    expected_values=("top",),
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )

    def test_gdl_110_answer_equals_without_node_id(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    expected_value="top",
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )

    def test_gdl_110_answer_equals_without_expected_value(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_EQUALS,
                    node_id="q_specimen",
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )

    def test_gdl_110_answer_in_set_with_empty_tuple(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.ANSWER_IN_SET,
                    node_id="q_specimen",
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )

    def test_gdl_110_evidence_present_without_evidence_kind(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            transitions=(
                make_transition(
                    "q_specimen",
                    "c_done",
                    kind=TransitionConditionKind.EVIDENCE_PRESENT,
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )

    def test_gdl_110_boolean_true_carrying_an_expected_value(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(make_boolean_node(), make_complete_node()),
            entry_node_id="q_bool",
            transitions=(
                make_transition(
                    "q_bool",
                    "c_done",
                    kind=TransitionConditionKind.BOOLEAN_TRUE,
                    node_id="q_bool",
                    expected_value=True,
                ),
            ),
        )
        assert GuidedLabErrorCode.INVALID_TRANSITION_CONDITION.value in codes(
            definition
        )


class TestDuplicateWorkflowKey:
    def test_gdl_111_same_id_and_version(self):
        first = make_minimal_valid_definition()
        second = make_minimal_valid_definition()
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            require_unique_workflow_keys((first, second))
        assert excinfo.value.code is GuidedLabErrorCode.DUPLICATE_WORKFLOW_KEY

    def test_same_id_different_version_is_allowed(self):
        first = make_minimal_valid_definition()
        second = make_minimal_valid_definition(workflow_version=2)
        require_unique_workflow_keys((first, second))

    def test_distinct_ids_are_allowed(self):
        require_unique_workflow_keys(
            (
                make_minimal_valid_definition(),
                make_minimal_valid_definition(workflow_id="other"),
            )
        )


class TestFindingOrderAndRaising:
    def _multi_problem_definition(self) -> WorkflowDefinitionV1:
        return dataclasses.replace(
            make_minimal_valid_definition(),
            entry_node_id="not_a_node",
            nodes=(
                make_question_node(),
                make_question_node(),
                make_instruction_node(source_reference_ids=()),
                make_complete_node(),
            ),
            transitions=(make_transition("q_specimen", "ghost"),),
        )

    def test_all_independent_findings_are_collected(self):
        found = set(codes(self._multi_problem_definition()))
        assert {
            GuidedLabErrorCode.DUPLICATE_NODE_ID.value,
            GuidedLabErrorCode.MISSING_ENTRY_NODE.value,
            GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE.value,
            GuidedLabErrorCode.MISSING_SOURCE_REFERENCE.value,
        } <= found

    def test_findings_are_sorted_deterministically(self):
        findings = validate_workflow_definition(self._multi_problem_definition())
        assert list(findings) == sorted(findings, key=lambda f: f.sort_key)

    def test_validation_is_repeatable(self):
        definition = self._multi_problem_definition()
        assert validate_workflow_definition(definition) == validate_workflow_definition(
            definition
        )

    def test_require_valid_raises_with_the_first_code(self):
        definition = self._multi_problem_definition()
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            require_valid_workflow_definition(definition)
        assert excinfo.value.code.value.startswith("GDL-1")
        assert "findings" in excinfo.value.context

    def test_raise_for_findings_is_a_no_op_when_clean(self):
        raise_for_findings(())

    def test_error_to_dict_is_path_free(self):
        definition = self._multi_problem_definition()
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            require_valid_workflow_definition(definition)
        blob = repr(excinfo.value.to_dict())
        assert "C:" not in blob
        assert "\\\\" not in blob


class TestInvalidWorkflowIdentity:
    """GDL-112 — a definition must be able to key a registry and a session.

    A registry is keyed by ``(workflow_id, workflow_version)`` and every session
    carries that pair to prove which procedure it was run under. An empty id or
    a non-positive version makes both meaningless.
    """

    def test_a_valid_identity_produces_no_finding(self):
        assert "GDL-112" not in codes(make_minimal_valid_definition())

    def test_an_empty_workflow_id_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_id=""
        )
        assert "GDL-112" in codes(definition)

    def test_a_blank_workflow_id_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_id="   "
        )
        assert "GDL-112" in codes(definition)

    def test_version_zero_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_version=0
        )
        assert "GDL-112" in codes(definition)

    def test_a_negative_version_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_version=-1
        )
        assert "GDL-112" in codes(definition)

    def test_a_boolean_version_is_rejected(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_version=True
        )
        assert "GDL-112" in codes(definition)

    def test_both_problems_are_reported_together(self):
        definition = dataclasses.replace(
            make_minimal_valid_definition(), workflow_id="", workflow_version=0
        )
        assert codes(definition).count("GDL-112") == 2


class TestUnsatisfiableReviewRequirement:
    """GDL-113 — a review may only require steps an operator action satisfies.

    A review is satisfied when every id it names carries an answer or an
    acknowledgment, and only questions and instructions produce either. Naming
    anything else yields a review the session reaches and can never leave, with
    no error to explain the deadlock.
    """

    def _with_review_requiring(self, *required_node_ids: str):
        definition = make_branching_definition()
        nodes = tuple(
            make_review_node(required_node_ids=required_node_ids)
            if node.node_id == "r_review"
            else node
            for node in definition.nodes
        )
        return dataclasses.replace(definition, nodes=nodes)

    def test_requiring_a_question_is_accepted(self):
        assert "GDL-113" not in codes(self._with_review_requiring("q_specimen"))

    def test_requiring_an_instruction_is_accepted(self):
        assert "GDL-113" not in codes(self._with_review_requiring("i_prep"))

    def test_requiring_nothing_is_accepted(self):
        assert "GDL-113" not in codes(self._with_review_requiring())

    def test_requiring_an_evidence_step_is_rejected(self):
        assert "GDL-113" in codes(self._with_review_requiring("e_record"))

    def test_requiring_a_completion_node_is_rejected(self):
        assert "GDL-113" in codes(self._with_review_requiring("c_done"))

    def test_requiring_an_undeclared_node_is_rejected(self):
        assert "GDL-113" in codes(self._with_review_requiring("ghost"))

    def test_requiring_an_optional_question_is_rejected(self):
        definition = self._with_review_requiring("q_specimen")
        nodes = tuple(
            make_question_node(required=False) if node.node_id == "q_specimen" else node
            for node in definition.nodes
        )
        assert "GDL-113" in codes(dataclasses.replace(definition, nodes=nodes))

    def test_every_bad_requirement_is_reported(self):
        definition = self._with_review_requiring("e_record", "c_done", "ghost")
        assert codes(definition).count("GDL-113") == 3

    def test_the_finding_names_the_review_step(self):
        definition = self._with_review_requiring("e_record")
        findings = [
            f
            for f in validate_workflow_definition(definition)
            if f.code is GuidedLabErrorCode.UNSATISFIABLE_NODE_REQUIREMENT
        ]
        assert findings[0].node_id == "r_review"


class TestIntegerBoundsAdmitAnInteger:
    """GDL-108 — integer bounds that no integer satisfies are an authoring bug.

    ``NumericConstraintV1`` accepts fractional bounds because a decimal question
    needs them. On an integer question a pair like ``0.2 .. 0.8`` type-checks,
    validates clean, and rejects every value an operator can supply.
    """

    def _integer_question(self, minimum, maximum):
        node = make_question_node(
            answer_kind=WorkflowAnswerKind.INTEGER,
            constraints=NumericConstraintV1(minimum=minimum, maximum=maximum),
        )
        return dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(node, make_complete_node()),
        )

    def test_fractional_bounds_admitting_no_integer_are_rejected(self):
        assert "GDL-108" in codes(self._integer_question(0.2, 0.8))

    def test_bounds_admitting_one_integer_are_accepted(self):
        assert "GDL-108" not in codes(self._integer_question(0.2, 1.8))

    def test_equal_whole_bounds_are_accepted(self):
        assert "GDL-108" not in codes(self._integer_question(1, 1))

    def test_an_open_minimum_is_accepted(self):
        assert "GDL-108" not in codes(self._integer_question(None, 0.8))

    def test_an_open_maximum_is_accepted(self):
        assert "GDL-108" not in codes(self._integer_question(0.5, None))

    def test_a_decimal_question_may_keep_fractional_bounds(self):
        node = make_question_node(
            answer_kind=WorkflowAnswerKind.DECIMAL,
            constraints=NumericConstraintV1(minimum=0.2, maximum=0.8),
        )
        definition = dataclasses.replace(
            make_minimal_valid_definition(),
            nodes=(node, make_complete_node()),
        )
        assert "GDL-108" not in codes(definition)

# INSTRUMENT CLASS: MEASUREMENT
"""Pure validation of guided laboratory workflow definitions (DO-100).

Validation inspects a definition's graph. It never executes a transition,
never touches a session, and never reads from disk — the same definition
always produces the same findings in the same order.

Findings are collected rather than raised one at a time: an author fixing a
workflow should see every independent problem at once. Ordering is by code,
then node ID, then transition index, then message.

Two scopes of ambiguity are distinguished. Provably-ambiguous transition sets
(an unconditional edge sharing a source with any other edge, or two conditions
on the same target whose value sets overlap) are rejected here as GDL-106.
Ambiguity that depends on runtime state — two conditions reading *different*
answers that happen to both be true — cannot be settled statically and is
caught by the engine when it selects a transition.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from tap_tone_pi.guided_lab.errors import (
    GuidedLabErrorCode,
    WorkflowDefinitionError,
    raise_for_findings,
)
from tap_tone_pi.guided_lab.models import (
    ChoiceConstraintV1,
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    InstructionNodeV1,
    NumericConstraintV1,
    QuestionNodeV1,
    ReviewNodeV1,
    TextConstraintV1,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowDefinitionV1,
    WorkflowNodeV1,
    WorkflowTransitionConditionV1,
    WorkflowValidationFindingV1,
)

Finding = WorkflowValidationFindingV1

#: Condition kinds that read a recorded answer.
_ANSWER_CONDITIONS = (
    TransitionConditionKind.ANSWER_EQUALS,
    TransitionConditionKind.ANSWER_IN_SET,
    TransitionConditionKind.BOOLEAN_TRUE,
    TransitionConditionKind.BOOLEAN_FALSE,
)

#: Which constraint types each answer kind accepts. ``None`` is always allowed
#: except for SINGLE_CHOICE, which cannot be presented without its options.
_ALLOWED_CONSTRAINTS: dict[WorkflowAnswerKind, tuple[type, ...]] = {
    WorkflowAnswerKind.SINGLE_CHOICE: (ChoiceConstraintV1,),
    WorkflowAnswerKind.BOOLEAN: (),
    WorkflowAnswerKind.INTEGER: (NumericConstraintV1,),
    WorkflowAnswerKind.DECIMAL: (NumericConstraintV1,),
    WorkflowAnswerKind.TEXT: (TextConstraintV1,),
    WorkflowAnswerKind.MEASUREMENT_REFERENCE: (TextConstraintV1,),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_workflow_definition(
    definition: WorkflowDefinitionV1,
) -> tuple[Finding, ...]:
    """Return every problem found in ``definition``, in deterministic order."""
    findings: list[Finding] = []

    index, duplicates = _index_nodes(definition.nodes)
    findings.extend(_validate_definition_identity(definition))
    findings.extend(_validate_unique_node_ids(duplicates))
    findings.extend(_validate_entry_node(definition, index))
    findings.extend(_validate_review_requirements(definition, index))
    findings.extend(_validate_source_references(definition))
    findings.extend(_validate_node_constraints(definition))
    findings.extend(_validate_transition_references(definition, index))
    findings.extend(_validate_condition_payloads(definition))
    findings.extend(_validate_condition_answer_compatibility(definition, index))
    findings.extend(_validate_transition_determinism(definition))

    if definition.entry_node_id in index:
        reachable = _compute_reachable_nodes(definition, index)
        findings.extend(_validate_required_reachability(definition, index, reachable))
        findings.extend(_validate_reachable_completion(definition, index, reachable))

    return tuple(sorted(findings, key=lambda f: f.sort_key))


def require_valid_workflow_definition(definition: WorkflowDefinitionV1) -> None:
    """Raise :class:`WorkflowDefinitionError` if ``definition`` has any finding."""
    raise_for_findings(validate_workflow_definition(definition))


def require_unique_workflow_keys(
    definitions: Iterable[WorkflowDefinitionV1],
) -> None:
    """Reject a registry holding two definitions with the same id and version."""
    seen: set[tuple[str, int]] = set()
    for definition in definitions:
        key = (definition.workflow_id, definition.workflow_version)
        if key in seen:
            raise WorkflowDefinitionError(
                GuidedLabErrorCode.DUPLICATE_WORKFLOW_KEY,
                "workflow registry holds a duplicate id and version",
                {
                    "workflow_id": definition.workflow_id,
                    "workflow_version": definition.workflow_version,
                },
            )
        seen.add(key)


# ---------------------------------------------------------------------------
# Node-level checks
# ---------------------------------------------------------------------------


def _validate_definition_identity(definition: WorkflowDefinitionV1) -> list[Finding]:
    """The definition must be able to key a registry and a session record.

    A registry is keyed by ``(workflow_id, workflow_version)`` and every session
    carries that pair to prove which procedure it was run under. An empty id or
    a non-positive version makes both meaningless, so it is rejected here rather
    than being registered and only noticed when a session cannot be matched.
    """
    findings: list[Finding] = []
    if (
        not isinstance(definition.workflow_id, str)
        or not definition.workflow_id.strip()
    ):
        findings.append(
            Finding(
                code=GuidedLabErrorCode.INVALID_WORKFLOW_IDENTITY,
                message="workflow_id must be a non-empty string",
            )
        )
    version = definition.workflow_version
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(
            Finding(
                code=GuidedLabErrorCode.INVALID_WORKFLOW_IDENTITY,
                message="workflow_version must be an integer of at least 1",
            )
        )
    return findings


def _validate_review_requirements(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> list[Finding]:
    """A review may only require steps an operator action can satisfy.

    A review is satisfied when every id it names carries an answer or an
    acknowledgment. Only questions and instructions produce either. Naming an
    evidence step, a nested review, a completion node, or a node that is not
    declared at all yields a review that no sequence of actions can satisfy —
    the session reaches it and can never leave, with no error to explain why.
    Naming an optional step is the same trap by a slower route: the operator is
    permitted to skip it, and the review then demands it.
    """
    findings: list[Finding] = []
    for node in definition.nodes:
        if not isinstance(node, ReviewNodeV1):
            continue
        for required_id in node.required_node_ids:
            target = index.get(required_id)
            if target is None:
                findings.append(
                    Finding(
                        code=GuidedLabErrorCode.UNSATISFIABLE_NODE_REQUIREMENT,
                        message=(
                            f"review requires {required_id!r}, which this workflow "
                            "does not declare"
                        ),
                        node_id=node.node_id,
                    )
                )
                continue
            if not isinstance(target, (QuestionNodeV1, InstructionNodeV1)):
                findings.append(
                    Finding(
                        code=GuidedLabErrorCode.UNSATISFIABLE_NODE_REQUIREMENT,
                        message=(
                            f"review requires {required_id!r}, a step of kind "
                            f"{target.kind.value}; only a question or an "
                            "instruction can satisfy a review"
                        ),
                        node_id=node.node_id,
                    )
                )
                continue
            if not target.required:
                findings.append(
                    Finding(
                        code=GuidedLabErrorCode.UNSATISFIABLE_NODE_REQUIREMENT,
                        message=(
                            f"review requires {required_id!r}, which is optional "
                            "and may legitimately be skipped"
                        ),
                        node_id=node.node_id,
                    )
                )
    return findings


def _index_nodes(
    nodes: Sequence[WorkflowNodeV1],
) -> tuple[dict[str, WorkflowNodeV1], list[str]]:
    """Map node ID to node, reporting IDs declared more than once."""
    index: dict[str, WorkflowNodeV1] = {}
    duplicates: list[str] = []
    for node in nodes:
        if node.node_id in index:
            if node.node_id not in duplicates:
                duplicates.append(node.node_id)
            continue
        index[node.node_id] = node
    return index, duplicates


def _validate_unique_node_ids(duplicates: Sequence[str]) -> list[Finding]:
    return [
        Finding(
            code=GuidedLabErrorCode.DUPLICATE_NODE_ID,
            message=f"node id {node_id!r} is declared more than once",
            node_id=node_id,
        )
        for node_id in duplicates
    ]


def _validate_entry_node(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> list[Finding]:
    if definition.entry_node_id in index:
        return []
    return [
        Finding(
            code=GuidedLabErrorCode.MISSING_ENTRY_NODE,
            message=(
                f"entry node {definition.entry_node_id!r} is not declared by "
                "this workflow"
            ),
            node_id=definition.entry_node_id,
        )
    ]


def _validate_source_references(definition: WorkflowDefinitionV1) -> list[Finding]:
    """Procedural instructions must name a source, even a provisional one."""
    findings: list[Finding] = []
    known: set[str] = set()
    for reference in definition.source_references:
        if reference.source_reference_id in known:
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.MISSING_SOURCE_REFERENCE,
                    message=(
                        f"source reference {reference.source_reference_id!r} is "
                        "declared more than once"
                    ),
                )
            )
            continue
        known.add(reference.source_reference_id)

    for node in definition.nodes:
        if isinstance(node, InstructionNodeV1) and not node.source_reference_ids:
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.MISSING_SOURCE_REFERENCE,
                    message=(
                        "instruction node carries procedure text with no source "
                        "reference; cite a source or mark one provisional"
                    ),
                    node_id=node.node_id,
                )
            )
        for reference_id in node.source_reference_ids:
            if reference_id not in known:
                findings.append(
                    Finding(
                        code=GuidedLabErrorCode.MISSING_SOURCE_REFERENCE,
                        message=(f"node references unknown source {reference_id!r}"),
                        node_id=node.node_id,
                    )
                )
    return findings


def _validate_node_constraints(definition: WorkflowDefinitionV1) -> list[Finding]:
    findings: list[Finding] = []
    for node in definition.nodes:
        if isinstance(node, QuestionNodeV1):
            findings.extend(_validate_question_constraints(node))
        elif isinstance(node, EvidenceRequirementNodeV1):
            findings.extend(_validate_evidence_requirements(node))
    return findings


def _validate_question_constraints(node: QuestionNodeV1) -> list[Finding]:
    allowed = _ALLOWED_CONSTRAINTS[node.answer_kind]
    if node.constraints is None:
        if node.answer_kind is WorkflowAnswerKind.SINGLE_CHOICE:
            return [
                Finding(
                    code=GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                    message=(
                        "single_choice question requires a ChoiceConstraintV1 "
                        "listing its allowed values"
                    ),
                    node_id=node.node_id,
                )
            ]
        return []
    if not isinstance(node.constraints, allowed):
        return [
            Finding(
                code=GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                message=(
                    f"{type(node.constraints).__name__} cannot constrain a "
                    f"{node.answer_kind.value} question"
                ),
                node_id=node.node_id,
            )
        ]
    if node.answer_kind is WorkflowAnswerKind.INTEGER and isinstance(
        node.constraints, NumericConstraintV1
    ):
        return _validate_integer_bounds(node, node.constraints)
    return []


def _validate_integer_bounds(
    node: QuestionNodeV1, constraints: NumericConstraintV1
) -> list[Finding]:
    """Reject integer bounds that no integer satisfies.

    ``NumericConstraintV1`` accepts fractional bounds because a decimal question
    needs them. On an integer question a pair like ``0.2 .. 0.8`` type-checks,
    validates clean, and rejects every value an operator can supply — a step
    that can only be reached and never answered. The bounds are inclusive, so
    the admissible integers are ``ceil(minimum) .. floor(maximum)``.
    """
    lowest = None if constraints.minimum is None else math.ceil(constraints.minimum)
    highest = None if constraints.maximum is None else math.floor(constraints.maximum)
    if lowest is not None and highest is not None and lowest > highest:
        return [
            Finding(
                code=GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                message=(
                    f"integer question accepts no value: bounds "
                    f"{constraints.minimum} .. {constraints.maximum} admit no integer"
                ),
                node_id=node.node_id,
            )
        ]
    return []


def _validate_evidence_requirements(node: EvidenceRequirementNodeV1) -> list[Finding]:
    findings: list[Finding] = []
    if not node.required_evidence_kinds:
        findings.append(
            Finding(
                code=GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                message="evidence requirement declares no evidence kind",
                node_id=node.node_id,
            )
        )
    if node.minimum_count < 1:
        findings.append(
            Finding(
                code=GuidedLabErrorCode.INVALID_QUESTION_CONSTRAINTS,
                message="evidence requirement minimum_count must be at least 1",
                node_id=node.node_id,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Transition-level checks
# ---------------------------------------------------------------------------


def _validate_transition_references(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> list[Finding]:
    findings: list[Finding] = []
    for position, transition in enumerate(definition.transitions):
        for label, node_id in (
            ("from_node_id", transition.from_node_id),
            ("to_node_id", transition.to_node_id),
            ("condition node_id", transition.condition.node_id),
        ):
            if node_id is None or node_id in index:
                continue
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.UNKNOWN_TRANSITION_NODE,
                    message=f"transition {label} {node_id!r} is not a declared node",
                    node_id=node_id,
                    transition_index=position,
                )
            )
    return findings


def _validate_condition_payloads(definition: WorkflowDefinitionV1) -> list[Finding]:
    """Reject condition payloads whose fields do not match their kind."""
    findings: list[Finding] = []
    for position, transition in enumerate(definition.transitions):
        problem = _condition_payload_problem(transition.condition)
        if problem is not None:
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.INVALID_TRANSITION_CONDITION,
                    message=problem,
                    node_id=transition.from_node_id,
                    transition_index=position,
                )
            )
    return findings


def _condition_payload_problem(
    condition: WorkflowTransitionConditionV1,
) -> str | None:
    kind = condition.kind
    has_value = condition.expected_value is not None
    has_values = bool(condition.expected_values)
    has_evidence = condition.evidence_kind is not None
    has_node = condition.node_id is not None

    if kind is TransitionConditionKind.ALWAYS:
        if has_node or has_value or has_values or has_evidence:
            return "always condition must not carry a node, value, or evidence kind"
        return None

    if kind is TransitionConditionKind.ANSWER_EQUALS:
        if not has_node:
            return "answer_equals condition requires node_id"
        if not has_value:
            return "answer_equals condition requires expected_value"
        if has_values or has_evidence:
            return "answer_equals condition must carry only one expected value"
        return None

    if kind is TransitionConditionKind.ANSWER_IN_SET:
        if not has_node:
            return "answer_in_set condition requires node_id"
        if not has_values:
            return "answer_in_set condition requires a non-empty expected_values"
        if has_value or has_evidence:
            return "answer_in_set condition must carry only expected_values"
        return None

    if kind in (
        TransitionConditionKind.BOOLEAN_TRUE,
        TransitionConditionKind.BOOLEAN_FALSE,
    ):
        if not has_node:
            return f"{kind.value} condition requires node_id"
        if has_value or has_values or has_evidence:
            return f"{kind.value} condition must not carry expected values"
        return None

    if kind is TransitionConditionKind.EVIDENCE_PRESENT:
        if not has_evidence:
            return "evidence_present condition requires evidence_kind"
        if has_node or has_value or has_values:
            return "evidence_present condition must carry only evidence_kind"
        return None

    return None


def _validate_condition_answer_compatibility(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> list[Finding]:
    """Check a condition can actually read the answer it names."""
    findings: list[Finding] = []
    for position, transition in enumerate(definition.transitions):
        condition = transition.condition
        if condition.kind not in _ANSWER_CONDITIONS or condition.node_id is None:
            continue
        target = index.get(condition.node_id)
        if target is None:
            continue  # already reported as GDL-103

        if not isinstance(target, QuestionNodeV1):
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND,
                    message=(
                        f"condition reads an answer from {condition.node_id!r}, "
                        f"which is a {target.kind.value} node"
                    ),
                    node_id=condition.node_id,
                    transition_index=position,
                )
            )
            continue

        problem = _answer_compatibility_problem(condition, target)
        if problem is not None:
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.UNSUPPORTED_ANSWER_KIND,
                    message=problem,
                    node_id=condition.node_id,
                    transition_index=position,
                )
            )
    return findings


def _answer_compatibility_problem(
    condition: WorkflowTransitionConditionV1, target: QuestionNodeV1
) -> str | None:
    if condition.kind in (
        TransitionConditionKind.BOOLEAN_TRUE,
        TransitionConditionKind.BOOLEAN_FALSE,
    ):
        if target.answer_kind is not WorkflowAnswerKind.BOOLEAN:
            return (
                f"{condition.kind.value} condition requires a boolean question, "
                f"but {target.node_id!r} is {target.answer_kind.value}"
            )
        return None

    expected: tuple[Any, ...]
    if condition.kind is TransitionConditionKind.ANSWER_EQUALS:
        expected = (
            () if condition.expected_value is None else (condition.expected_value,)
        )
    else:
        expected = tuple(condition.expected_values)

    for value in expected:
        if not _value_matches_answer_kind(value, target.answer_kind):
            return (
                f"expected value {value!r} is not a valid "
                f"{target.answer_kind.value} answer for {target.node_id!r}"
            )
        if isinstance(target.constraints, ChoiceConstraintV1):
            if value not in target.constraints.allowed_values:
                return (
                    f"expected value {value!r} is not among the allowed values "
                    f"of {target.node_id!r}"
                )
    return None


def _value_matches_answer_kind(value: Any, answer_kind: WorkflowAnswerKind) -> bool:
    if isinstance(value, bool):
        return answer_kind is WorkflowAnswerKind.BOOLEAN
    if isinstance(value, str):
        return answer_kind in (
            WorkflowAnswerKind.SINGLE_CHOICE,
            WorkflowAnswerKind.TEXT,
            WorkflowAnswerKind.MEASUREMENT_REFERENCE,
        )
    if isinstance(value, int):
        return answer_kind in (
            WorkflowAnswerKind.INTEGER,
            WorkflowAnswerKind.DECIMAL,
        )
    if isinstance(value, float):
        return answer_kind is WorkflowAnswerKind.DECIMAL
    return False


def _condition_match_domain(
    condition: WorkflowTransitionConditionV1,
) -> tuple[str, str, frozenset[Any]] | None:
    """Reduce a condition to a comparable (kind, key, value-set) triple."""
    if condition.kind is TransitionConditionKind.ANSWER_EQUALS:
        return (
            "answer",
            condition.node_id or "",
            frozenset({condition.expected_value}),
        )
    if condition.kind is TransitionConditionKind.ANSWER_IN_SET:
        return ("answer", condition.node_id or "", frozenset(condition.expected_values))
    if condition.kind is TransitionConditionKind.BOOLEAN_TRUE:
        return ("answer", condition.node_id or "", frozenset({True}))
    if condition.kind is TransitionConditionKind.BOOLEAN_FALSE:
        return ("answer", condition.node_id or "", frozenset({False}))
    if condition.kind is TransitionConditionKind.EVIDENCE_PRESENT:
        return ("evidence", condition.evidence_kind or "", frozenset({True}))
    return None


def _validate_transition_determinism(
    definition: WorkflowDefinitionV1,
) -> list[Finding]:
    findings: list[Finding] = []
    grouped: dict[str, list[tuple[int, Any]]] = {}
    for position, transition in enumerate(definition.transitions):
        grouped.setdefault(transition.from_node_id, []).append((position, transition))

    for from_node_id in sorted(grouped):
        group = grouped[from_node_id]
        if len(group) < 2:
            continue

        unconditional = [
            position
            for position, transition in group
            if transition.condition.kind is TransitionConditionKind.ALWAYS
        ]
        if unconditional:
            findings.append(
                Finding(
                    code=GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET,
                    message=(
                        f"node {from_node_id!r} has an unconditional transition "
                        "alongside another transition"
                    ),
                    node_id=from_node_id,
                    transition_index=unconditional[0],
                )
            )
            continue

        for outer in range(len(group)):
            for inner in range(outer + 1, len(group)):
                left_pos, left = group[outer]
                right_pos, right = group[inner]
                left_domain = _condition_match_domain(left.condition)
                right_domain = _condition_match_domain(right.condition)
                if left_domain is None or right_domain is None:
                    continue
                if (
                    left_domain[0] != right_domain[0]
                    or left_domain[1] != right_domain[1]
                ):
                    continue
                if left_domain[2] & right_domain[2]:
                    findings.append(
                        Finding(
                            code=GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET,
                            message=(
                                f"node {from_node_id!r} has two transitions that "
                                "can match the same state"
                            ),
                            node_id=from_node_id,
                            transition_index=min(left_pos, right_pos),
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------


def _outgoing(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    for transition in definition.transitions:
        if transition.from_node_id not in index or transition.to_node_id not in index:
            continue
        edges.setdefault(transition.from_node_id, []).append(transition.to_node_id)
    return edges


def _compute_reachable_nodes(
    definition: WorkflowDefinitionV1, index: dict[str, WorkflowNodeV1]
) -> set[str]:
    edges = _outgoing(definition, index)
    reachable = {definition.entry_node_id}
    frontier = [definition.entry_node_id]
    while frontier:
        current = frontier.pop()
        for target in edges.get(current, ()):
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    return reachable


def _validate_required_reachability(
    definition: WorkflowDefinitionV1,
    index: dict[str, WorkflowNodeV1],
    reachable: set[str],
) -> list[Finding]:
    return [
        Finding(
            code=GuidedLabErrorCode.UNREACHABLE_REQUIRED_NODE,
            message=f"required node {node_id!r} cannot be reached from the entry node",
            node_id=node_id,
        )
        for node_id in sorted(index)
        if index[node_id].required and node_id not in reachable
    ]


def _validate_reachable_completion(
    definition: WorkflowDefinitionV1,
    index: dict[str, WorkflowNodeV1],
    reachable: set[str],
) -> list[Finding]:
    complete_ids = {
        node_id for node_id, node in index.items() if isinstance(node, CompleteNodeV1)
    }
    if not complete_ids:
        return [
            Finding(
                code=GuidedLabErrorCode.NO_COMPLETION_REACHABLE,
                message="workflow declares no completion node",
            )
        ]

    edges = _outgoing(definition, index)
    reverse: dict[str, list[str]] = {}
    for source, targets in edges.items():
        for target in targets:
            reverse.setdefault(target, []).append(source)

    can_complete = set(complete_ids)
    frontier = list(complete_ids)
    while frontier:
        current = frontier.pop()
        for source in reverse.get(current, ()):
            if source not in can_complete:
                can_complete.add(source)
                frontier.append(source)

    return [
        Finding(
            code=GuidedLabErrorCode.NO_COMPLETION_REACHABLE,
            message=(
                f"node {node_id!r} is reachable but no completion node can be "
                "reached from it"
            ),
            node_id=node_id,
        )
        for node_id in sorted(reachable)
        if node_id not in can_complete
    ]


__all__ = [
    "require_unique_workflow_keys",
    "require_valid_workflow_definition",
    "validate_workflow_definition",
]

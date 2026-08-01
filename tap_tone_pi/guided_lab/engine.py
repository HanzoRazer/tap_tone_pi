# INSTRUMENT CLASS: MEASUREMENT
"""Deterministic session engine for the guided laboratory (DO-100).

Every function here is a pure state transition: it takes a definition and a
session, and returns a *new* session. Nothing is mutated in place, nothing is
read from disk, and no timestamp or identifier is invented unless the caller
declines to supply one. Given the same definition, session, action, injected
time, and injected ID, the resulting session is equal.

The subtle operation is answer replacement. When an operator corrects an
earlier answer, the branch they took may no longer be the branch the workflow
would choose. Rather than patching the session, the engine replays the walk
from the entry node using the corrected answers and keeps only the state that
survives the replay: answers, acknowledgments, and evidence belonging to nodes
that are still on the path. State that is no longer reachable is dropped, not
retained "just in case" — a record that carries answers from an abandoned
branch is not an honest record of the procedure.

The replay is capped at the length of the existing visited history, so a
correction never advances an operator past the step they had reached.

Stepping back obeys the same rule by the same code path: the abandoned step's
answer, acknowledgment, and evidence go with it. Evidence is stamped with the
step it was attached at, so a step asking for a kind another step also asks for
cannot inherit the other's reference.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from tap_tone_pi.guided_lab.errors import (
    GuidedLabActionError,
    GuidedLabErrorCode,
    GuidedLabSessionError,
    WorkflowDefinitionError,
)
from tap_tone_pi.guided_lab.models import (
    TERMINAL_STATUSES,
    AnswerValue,
    ChoiceConstraintV1,
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    GuidedLabSessionStatus,
    GuidedLabSessionV1,
    InstructionNodeV1,
    NumericConstraintV1,
    QuestionNodeV1,
    ReviewNodeV1,
    TextConstraintV1,
    TransitionConditionKind,
    WorkflowAnswerV1,
    WorkflowDefinitionV1,
    WorkflowEvidenceReferenceV1,
    WorkflowNodeV1,
    WorkflowProgressV1,
    WorkflowTransitionConditionV1,
    WorkflowTransitionV1,
)
from tap_tone_pi.guided_lab.validation import require_valid_workflow_definition


# ---------------------------------------------------------------------------
# Session construction
# ---------------------------------------------------------------------------


def start_session(
    definition: WorkflowDefinitionV1,
    *,
    session_id: str | None = None,
    started_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Open a session on ``definition`` at its entry node."""
    require_valid_workflow_definition(definition)
    timestamp = _resolve_time(started_at)
    return GuidedLabSessionV1(
        session_id=session_id or str(uuid.uuid4()),
        workflow_id=definition.workflow_id,
        workflow_version=definition.workflow_version,
        status=GuidedLabSessionStatus.ACTIVE,
        current_node_id=definition.entry_node_id,
        started_at=timestamp,
        updated_at=timestamp,
        visited_node_ids=(definition.entry_node_id,),
    )


# ---------------------------------------------------------------------------
# Read-only views
# ---------------------------------------------------------------------------


def get_current_node(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> WorkflowNodeV1:
    """Return the node the session is standing on."""
    _require_matching_workflow(definition, session)
    index = _index_nodes(definition)
    node = index.get(session.current_node_id)
    if node is None:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.CURRENT_NODE_MISSING,
            "session references a node this workflow does not declare",
            {"current_node_id": session.current_node_id},
        )
    return node


def get_workflow_progress(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> WorkflowProgressV1:
    """Summarize how far the session has come and what still blocks it."""
    node = get_current_node(definition, session)
    missing = _missing_requirements(definition, session)
    return WorkflowProgressV1(
        current_node_id=session.current_node_id,
        visited_count=len(session.visited_node_ids),
        answered_count=len(session.answers),
        evidence_count=len(session.evidence_references),
        missing_required_node_ids=missing,
        may_complete=isinstance(node, CompleteNodeV1) and not missing,
    )


# ---------------------------------------------------------------------------
# Operator actions
# ---------------------------------------------------------------------------


def answer_question(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    value: AnswerValue,
    *,
    answered_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Record the operator's answer to the current question."""
    node = _require_active_node(definition, session)
    if not isinstance(node, QuestionNodeV1):
        raise _wrong_action(node, "answer a question")

    if _find_answer(session, node.node_id) is not None:
        return replace_answer(
            definition,
            session,
            node_id=node.node_id,
            value=value,
            answered_at=answered_at,
        )

    _validate_against_node(node, value)
    timestamp = _resolve_time(answered_at)
    answer = WorkflowAnswerV1(
        node_id=node.node_id,
        answer_kind=node.answer_kind,
        value=value,
        answered_at=timestamp,
        revision=1,
    )
    return _replace_session(
        session, answers=session.answers + (answer,), updated_at=timestamp
    )


def acknowledge_instruction(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    acknowledged_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Record that the operator has read the current instruction."""
    node = _require_active_node(definition, session)
    if not isinstance(node, InstructionNodeV1):
        raise _wrong_action(node, "acknowledge an instruction")

    timestamp = _resolve_time(acknowledged_at)
    if node.node_id in session.acknowledged_node_ids:
        return _replace_session(session, updated_at=timestamp)
    return _replace_session(
        session,
        acknowledged_node_ids=session.acknowledged_node_ids + (node.node_id,),
        updated_at=timestamp,
    )


def attach_evidence(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    evidence: WorkflowEvidenceReferenceV1,
    *,
    attached_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Attach a logical evidence reference to the current requirement."""
    node = _require_active_node(definition, session)
    if not isinstance(node, EvidenceRequirementNodeV1):
        raise _wrong_action(node, "attach evidence")

    if evidence.evidence_kind not in node.required_evidence_kinds:
        raise GuidedLabActionError(
            GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
            "this step does not accept that kind of evidence",
            {
                "node_id": node.node_id,
                "evidence_kind": evidence.evidence_kind,
                "accepted": list(node.required_evidence_kinds),
            },
        )

    # The engine, not the caller, is authoritative about where evidence was
    # attached: the node stamp is what lets a later correction tell this
    # reference apart from one of the same kind on an abandoned branch.
    timestamp = _resolve_time(attached_at)
    stamped = dataclasses.replace(
        evidence,
        attached_at=(
            evidence.attached_at if evidence.attached_at is not None else timestamp
        ),
        attached_node_id=node.node_id,
    )
    # Replacement is scoped to the step being stood on. Re-attaching an
    # identifier here supersedes what *this* step holds; it must not reach back
    # and delete the same identifier from an earlier step, which would silently
    # un-satisfy a step the operator has already walked past and left them
    # blocked at completion with no visible cause. An unstamped reference has
    # no attachment site and counts everywhere, so attaching it here gives it
    # one rather than duplicating it.
    remaining = tuple(
        existing
        for existing in session.evidence_references
        if not (
            existing.evidence_id == stamped.evidence_id
            and existing.attached_node_id in (None, node.node_id)
        )
    )
    return _replace_session(
        session,
        evidence_references=remaining + (stamped,),
        updated_at=timestamp,
    )


def advance_session(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    advanced_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Move to the single node whose transition condition holds."""
    node = _require_active_node(definition, session)
    if isinstance(node, CompleteNodeV1):
        raise _wrong_action(node, "advance past the final step")

    blocking = _node_requirement_problem(node, session)
    if blocking is not None:
        raise blocking

    transition = _select_transition(definition, session, node)
    timestamp = _resolve_time(advanced_at)
    return _replace_session(
        session,
        current_node_id=transition.to_node_id,
        visited_node_ids=session.visited_node_ids + (transition.to_node_id,),
        updated_at=timestamp,
    )


def go_back(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    moved_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Step back to the previous node, discarding what the step held.

    Stepping back abandons the step being left, and whatever was recorded on
    it goes too — its answer, its acknowledgment, its evidence. Keeping that
    state would leave the session claiming work at a node the operator is no
    longer standing on, and would let a later walk down a different branch
    inherit entries the operator never re-made. It is the rule
    :func:`replace_answer` applies, for the same reason.
    """
    _require_active_node(definition, session)
    if len(session.visited_node_ids) < 2:
        raise GuidedLabActionError(
            GuidedLabErrorCode.BACK_NAVIGATION_UNAVAILABLE,
            "there is no earlier step to return to",
            {"current_node_id": session.current_node_id},
        )
    history = session.visited_node_ids[:-1]
    return _retain_state_on_path(
        definition,
        session,
        path=list(history),
        answers=session.answers,
        updated_at=_resolve_time(moved_at),
    )


def replace_answer(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    node_id: str,
    value: AnswerValue,
    answered_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Correct an earlier answer and discard whatever it invalidates."""
    _require_active_session(session)
    _require_matching_workflow(definition, session)
    _require_consistent_history(session)
    index = _index_nodes(definition)

    previous = _find_answer(session, node_id)
    if previous is None:
        raise GuidedLabActionError(
            GuidedLabErrorCode.REPLACEMENT_TARGET_NOT_ANSWERED,
            "that step has not been answered, so there is nothing to replace",
            {"node_id": node_id},
        )

    node = index.get(node_id)
    if not isinstance(node, QuestionNodeV1):
        raise GuidedLabSessionError(
            GuidedLabErrorCode.CURRENT_NODE_MISSING,
            "the answered step is not a question in this workflow",
            {"node_id": node_id},
        )

    _validate_against_node(node, value)
    timestamp = _resolve_time(answered_at)
    revised = WorkflowAnswerV1(
        node_id=node_id,
        answer_kind=node.answer_kind,
        value=value,
        answered_at=timestamp,
        revision=previous.revision + 1,
    )
    answers = tuple(
        revised if answer.node_id == node_id else answer for answer in session.answers
    )
    return _invalidate_downstream_state(
        definition, session, answers=answers, updated_at=timestamp
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def pause_session(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    paused_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Suspend an active session without losing any state."""
    _require_matching_workflow(definition, session)
    _require_status(session, GuidedLabSessionStatus.ACTIVE, "pause")
    return _replace_session(
        session,
        status=GuidedLabSessionStatus.PAUSED,
        updated_at=_resolve_time(paused_at),
    )


def resume_session(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    resumed_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Return a paused session to active work at the same node."""
    _require_matching_workflow(definition, session)
    _require_status(session, GuidedLabSessionStatus.PAUSED, "resume")
    return _replace_session(
        session,
        status=GuidedLabSessionStatus.ACTIVE,
        updated_at=_resolve_time(resumed_at),
    )


def abandon_session(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    abandoned_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Close a session without completing it."""
    _require_matching_workflow(definition, session)
    _require_not_terminal(session)
    return _replace_session(
        session,
        status=GuidedLabSessionStatus.ABANDONED,
        updated_at=_resolve_time(abandoned_at),
    )


def complete_session(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    completed_at: datetime | None = None,
) -> GuidedLabSessionV1:
    """Close the record on the final node.

    Completion records that the *procedure* was worked through. It makes no
    claim about the specimen, the setup, or the measurement.
    """
    node = _require_active_node(definition, session)
    if not isinstance(node, CompleteNodeV1):
        raise _wrong_action(node, "complete the session")

    missing = _missing_requirements(definition, session)
    if missing:
        raise GuidedLabActionError(
            GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING,
            "the record still has unmet requirements",
            {"missing_required_node_ids": list(missing)},
        )

    timestamp = _resolve_time(completed_at)
    return _replace_session(
        session,
        status=GuidedLabSessionStatus.COMPLETED,
        completed_at=timestamp,
        updated_at=timestamp,
    )


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _resolve_time(value: datetime | None) -> datetime:
    return value if value is not None else datetime.now(timezone.utc)


def _require_matching_workflow(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> None:
    if (
        definition.workflow_id != session.workflow_id
        or definition.workflow_version != session.workflow_version
    ):
        raise GuidedLabSessionError(
            GuidedLabErrorCode.WORKFLOW_VERSION_MISMATCH,
            "session was started under a different workflow or version",
            {
                "session_workflow_id": session.workflow_id,
                "session_workflow_version": session.workflow_version,
                "definition_workflow_id": definition.workflow_id,
                "definition_workflow_version": definition.workflow_version,
            },
        )


def _require_not_terminal(session: GuidedLabSessionV1) -> None:
    if session.status in TERMINAL_STATUSES:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_ALREADY_TERMINAL,
            "this session is closed and cannot be changed",
            {"status": session.status.value},
        )


def _require_active_session(session: GuidedLabSessionV1) -> None:
    _require_not_terminal(session)
    if session.status is not GuidedLabSessionStatus.ACTIVE:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.INVALID_STATUS_TRANSITION,
            "this session is not active; resume it first",
            {"status": session.status.value},
        )


def _require_status(
    session: GuidedLabSessionV1, expected: GuidedLabSessionStatus, action: str
) -> None:
    _require_not_terminal(session)
    if session.status is not expected:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.INVALID_STATUS_TRANSITION,
            f"cannot {action} a session with status {session.status.value}",
            {"status": session.status.value, "expected": expected.value},
        )


def _require_consistent_history(session: GuidedLabSessionV1) -> None:
    """The recorded walk must end where the session says the operator stands.

    Checked before any action, not on a read: a damaged record should still be
    inspectable, but acting on one would build further state on top of a walk
    the engine cannot account for.
    """
    if not session.visited_node_ids:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.CORRUPTED_HISTORY,
            "the session records no visited step",
            {"current_node_id": session.current_node_id},
        )
    if session.visited_node_ids[-1] != session.current_node_id:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.CORRUPTED_HISTORY,
            "the visited history does not end at the current step",
            {
                "current_node_id": session.current_node_id,
                "last_visited_node_id": session.visited_node_ids[-1],
            },
        )


def _require_active_node(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> WorkflowNodeV1:
    _require_matching_workflow(definition, session)
    _require_active_session(session)
    node = get_current_node(definition, session)
    _require_consistent_history(session)
    return node


def _wrong_action(node: WorkflowNodeV1, attempted: str) -> GuidedLabActionError:
    return GuidedLabActionError(
        GuidedLabErrorCode.ACTION_INVALID_FOR_NODE,
        f"cannot {attempted} on a {node.kind.value} step",
        {"node_id": node.node_id, "node_kind": node.kind.value},
    )


# ---------------------------------------------------------------------------
# Answer validation
# ---------------------------------------------------------------------------


def _validate_against_node(node: QuestionNodeV1, value: AnswerValue) -> None:
    """Reject a value the question cannot hold, then one it does not allow."""
    probe_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
    WorkflowAnswerV1(
        node_id=node.node_id,
        answer_kind=node.answer_kind,
        value=value,
        answered_at=probe_at,
        revision=1,
    )

    constraints = node.constraints
    if isinstance(constraints, ChoiceConstraintV1):
        if value not in constraints.allowed_values:
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
                "that is not one of the offered choices",
                {
                    "node_id": node.node_id,
                    "allowed_values": list(constraints.allowed_values),
                },
            )
    elif isinstance(constraints, NumericConstraintV1):
        # The probe above already rejected any value the answer kind cannot
        # hold, so a numeric constraint only ever sees a number here. The
        # isinstance narrowing states that for the type checker.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if constraints.minimum is not None and value < constraints.minimum:
                raise GuidedLabActionError(
                    GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
                    "that value is below the accepted minimum",
                    {"node_id": node.node_id, "minimum": constraints.minimum},
                )
            if constraints.maximum is not None and value > constraints.maximum:
                raise GuidedLabActionError(
                    GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
                    "that value is above the accepted maximum",
                    {"node_id": node.node_id, "maximum": constraints.maximum},
                )
    elif isinstance(constraints, TextConstraintV1):
        text = str(value)
        if (
            constraints.minimum_length is not None
            and len(text) < constraints.minimum_length
        ):
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
                "that entry is shorter than this step accepts",
                {
                    "node_id": node.node_id,
                    "minimum_length": constraints.minimum_length,
                },
            )
        if (
            constraints.maximum_length is not None
            and len(text) > constraints.maximum_length
        ):
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_NOT_ALLOWED,
                "that entry is longer than this step accepts",
                {
                    "node_id": node.node_id,
                    "maximum_length": constraints.maximum_length,
                },
            )


# ---------------------------------------------------------------------------
# State inspection
# ---------------------------------------------------------------------------


def _index_nodes(definition: WorkflowDefinitionV1) -> dict[str, WorkflowNodeV1]:
    return {node.node_id: node for node in definition.nodes}


def _index_answers(
    answers: Sequence[WorkflowAnswerV1],
) -> dict[str, WorkflowAnswerV1]:
    return {answer.node_id: answer for answer in answers}


def _find_answer(session: GuidedLabSessionV1, node_id: str) -> WorkflowAnswerV1 | None:
    for answer in session.answers:
        if answer.node_id == node_id:
            return answer
    return None


def _evidence_count_for(
    evidence: Iterable[WorkflowEvidenceReferenceV1],
    node: EvidenceRequirementNodeV1,
) -> int:
    """Count the references that satisfy ``node``.

    A reference the engine stamped counts only at the step it was attached at,
    so two steps asking for the same ``evidence_kind`` cannot satisfy each
    other. An unstamped reference — hand-written, or written before the stamp
    existed — is counted by kind alone, which is all such a record supports.
    """
    return sum(
        1
        for reference in evidence
        if reference.evidence_kind in node.required_evidence_kinds
        and reference.attached_node_id in (None, node.node_id)
    )


def _node_is_satisfied(
    node: WorkflowNodeV1,
    answers: Mapping[str, WorkflowAnswerV1],
    acknowledged: Sequence[str],
    evidence: Sequence[WorkflowEvidenceReferenceV1],
) -> bool:
    """Whether a step's own requirement has been met."""
    if isinstance(node, QuestionNodeV1):
        return not node.required or node.node_id in answers
    if isinstance(node, InstructionNodeV1):
        return not node.required or node.node_id in acknowledged
    if isinstance(node, EvidenceRequirementNodeV1):
        if not node.required:
            return True
        return _evidence_count_for(evidence, node) >= node.minimum_count
    if isinstance(node, ReviewNodeV1):
        return all(
            required_id in answers or required_id in acknowledged
            for required_id in node.required_node_ids
        )
    return True


def _node_requirement_problem(
    node: WorkflowNodeV1, session: GuidedLabSessionV1
) -> GuidedLabActionError | None:
    """Return the error blocking advance from ``node``, if any."""
    answers = _index_answers(session.answers)
    if isinstance(node, EvidenceRequirementNodeV1) and not _node_is_satisfied(
        node, answers, session.acknowledged_node_ids, session.evidence_references
    ):
        return GuidedLabActionError(
            GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING,
            "this step still needs an evidence reference",
            {
                "node_id": node.node_id,
                "required_evidence_kinds": list(node.required_evidence_kinds),
                "minimum_count": node.minimum_count,
                "attached_count": _evidence_count_for(
                    session.evidence_references, node
                ),
            },
        )
    if not _node_is_satisfied(
        node, answers, session.acknowledged_node_ids, session.evidence_references
    ):
        if isinstance(node, QuestionNodeV1):
            detail = "answer this step before moving on"
        elif isinstance(node, InstructionNodeV1):
            detail = "acknowledge this step before moving on"
        else:
            detail = "this step is not yet satisfied"
        return GuidedLabActionError(
            GuidedLabErrorCode.ACTION_INVALID_FOR_NODE,
            detail,
            {"node_id": node.node_id, "node_kind": node.kind.value},
        )
    return None


def _missing_requirements(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> tuple[str, ...]:
    """Required steps the operator has reached but not yet satisfied."""
    index = _index_nodes(definition)
    answers = _index_answers(session.answers)
    seen: list[str] = []
    for node_id in session.visited_node_ids:
        node = index.get(node_id)
        if node is None or node_id in seen:
            continue
        if not _node_is_satisfied(
            node, answers, session.acknowledged_node_ids, session.evidence_references
        ):
            seen.append(node_id)
    return tuple(seen)


# ---------------------------------------------------------------------------
# Transition selection
# ---------------------------------------------------------------------------


def _values_equal(left: Any, right: Any) -> bool:
    """Compare answer values without letting ``True`` equal ``1``."""
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


def _condition_matches(
    condition: WorkflowTransitionConditionV1,
    answers: Mapping[str, WorkflowAnswerV1],
    evidence: Sequence[WorkflowEvidenceReferenceV1],
) -> bool:
    kind = condition.kind
    if kind is TransitionConditionKind.ALWAYS:
        return True

    if kind is TransitionConditionKind.EVIDENCE_PRESENT:
        return any(
            reference.evidence_kind == condition.evidence_kind for reference in evidence
        )

    answer = answers.get(condition.node_id or "")
    if answer is None:
        return False

    if kind is TransitionConditionKind.ANSWER_EQUALS:
        return _values_equal(answer.value, condition.expected_value)
    if kind is TransitionConditionKind.ANSWER_IN_SET:
        return any(
            _values_equal(answer.value, expected)
            for expected in condition.expected_values
        )
    if kind is TransitionConditionKind.BOOLEAN_TRUE:
        return answer.value is True
    if kind is TransitionConditionKind.BOOLEAN_FALSE:
        return answer.value is False
    return False


def _matching_transitions(
    definition: WorkflowDefinitionV1,
    from_node_id: str,
    answers: Mapping[str, WorkflowAnswerV1],
    evidence: Sequence[WorkflowEvidenceReferenceV1],
) -> list[WorkflowTransitionV1]:
    return [
        transition
        for transition in definition.transitions
        if transition.from_node_id == from_node_id
        and _condition_matches(transition.condition, answers, evidence)
    ]


def _select_transition(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    node: WorkflowNodeV1,
) -> WorkflowTransitionV1:
    """Exactly one transition must match; anything else is a failure."""
    answers = _index_answers(session.answers)
    matches = _matching_transitions(
        definition, node.node_id, answers, session.evidence_references
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise GuidedLabActionError(
            GuidedLabErrorCode.ACTION_INVALID_FOR_NODE,
            "no transition applies to the current answers",
            {"node_id": node.node_id},
        )
    raise WorkflowDefinitionError(
        GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET,
        "more than one transition applies to the current answers",
        {
            "node_id": node.node_id,
            "candidate_node_ids": sorted(t.to_node_id for t in matches),
        },
    )


# ---------------------------------------------------------------------------
# Replacement and invalidation
# ---------------------------------------------------------------------------


def _reachable_path_from_state(
    definition: WorkflowDefinitionV1,
    answers: Mapping[str, WorkflowAnswerV1],
    acknowledged: Sequence[str],
    evidence: Sequence[WorkflowEvidenceReferenceV1],
    max_steps: int,
) -> list[str]:
    """Replay the walk from the entry node under the supplied state.

    Stops at the first step whose requirement is unmet, at a completion node,
    where no transition applies, or after ``max_steps`` transitions —
    whichever comes first. Stopping short is an ordinary outcome: a correction
    that invalidates a later step legitimately leaves the operator earlier in
    the procedure.

    An *ambiguous* stop is not ordinary. If more than one transition applies,
    the definition cannot say where the operator goes, and silently halting
    there would present an authoring defect as a backward step. That case
    raises, as it does on a live advance.
    """
    index = _index_nodes(definition)
    path = [definition.entry_node_id]
    current = definition.entry_node_id

    for _ in range(max(max_steps, 0)):
        node = index.get(current)
        if node is None or isinstance(node, CompleteNodeV1):
            break
        if not _node_is_satisfied(node, answers, acknowledged, evidence):
            break
        matches = _matching_transitions(definition, current, answers, evidence)
        if len(matches) > 1:
            raise WorkflowDefinitionError(
                GuidedLabErrorCode.AMBIGUOUS_TRANSITION_SET,
                "more than one transition applies while replaying the correction",
                {
                    "node_id": current,
                    "candidate_node_ids": sorted(t.to_node_id for t in matches),
                },
            )
        if not matches:
            break
        current = matches[0].to_node_id
        if current in path:
            break
        path.append(current)

    return path


def _retain_state_on_path(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    path: Sequence[str],
    answers: Sequence[WorkflowAnswerV1],
    updated_at: datetime,
) -> GuidedLabSessionV1:
    """Return the session reduced to the state belonging to ``path``.

    The single place that decides what survives a change of route, so a step
    back and an answer correction cannot drift apart in what they discard.
    """
    index = _index_nodes(definition)
    on_path = set(path)

    retained_answers = tuple(answer for answer in answers if answer.node_id in on_path)
    retained_acknowledgments = tuple(
        node_id for node_id in session.acknowledged_node_ids if node_id in on_path
    )

    # Evidence the engine attached carries the step it was attached at, and
    # survives exactly while that step is on the path. A reference with no
    # stamp has no attachment site to check, so it falls back to surviving
    # while some requirement still on the path asks for its kind.
    live_kinds: set[str] = set()
    for node_id in path:
        node = index.get(node_id)
        if isinstance(node, EvidenceRequirementNodeV1):
            live_kinds.update(node.required_evidence_kinds)
    retained_evidence = tuple(
        reference
        for reference in session.evidence_references
        if (
            reference.attached_node_id in on_path
            if reference.attached_node_id is not None
            else reference.evidence_kind in live_kinds
        )
    )

    return _replace_session(
        session,
        answers=retained_answers,
        acknowledged_node_ids=retained_acknowledgments,
        evidence_references=retained_evidence,
        visited_node_ids=tuple(path),
        current_node_id=path[-1],
        updated_at=updated_at,
    )


def _invalidate_downstream_state(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    answers: tuple[WorkflowAnswerV1, ...],
    updated_at: datetime,
) -> GuidedLabSessionV1:
    """Keep only the state that survives a replay under ``answers``."""
    path = _reachable_path_from_state(
        definition,
        _index_answers(answers),
        session.acknowledged_node_ids,
        session.evidence_references,
        max_steps=max(len(session.visited_node_ids) - 1, 0),
    )
    return _retain_state_on_path(
        definition,
        session,
        path=path,
        answers=answers,
        updated_at=updated_at,
    )


def _replace_session(session: GuidedLabSessionV1, **changes: Any) -> GuidedLabSessionV1:
    """Return a new session with ``changes`` applied."""
    return dataclasses.replace(session, **changes)


__all__ = [
    "abandon_session",
    "acknowledge_instruction",
    "advance_session",
    "answer_question",
    "attach_evidence",
    "complete_session",
    "get_current_node",
    "get_workflow_progress",
    "go_back",
    "pause_session",
    "replace_answer",
    "resume_session",
    "start_session",
]

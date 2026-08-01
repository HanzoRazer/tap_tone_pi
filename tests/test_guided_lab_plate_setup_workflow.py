"""Branch coverage for the Plate Measurement Setup workflow (DO-100).

Every declared branch must reach completion, and no path may produce a
scientific or manufacturing conclusion.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from tap_tone_pi.guided_lab import (
    GuidedLabActionError,
    GuidedLabErrorCode,
    GuidedLabSessionStatus,
    GuidedLabSessionV1,
)
from tap_tone_pi.guided_lab.engine import (
    acknowledge_instruction,
    advance_session,
    answer_question,
    attach_evidence,
    complete_session,
    get_current_node,
    get_workflow_progress,
    replace_answer,
    start_session,
)
from tap_tone_pi.guided_lab.models import (
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    InstructionNodeV1,
    QuestionNodeV1,
    ReviewNodeV1,
    SourceAuthorityStatus,
    WorkflowEvidenceReferenceV1,
)
from tap_tone_pi.guided_lab.workflows import PLATE_MEASUREMENT_SETUP_V1
from tap_tone_pi.guided_lab.workflows.plate_measurement_setup_v1 import (
    ENTRY_MODES,
    PREPARATION_STATES,
    PURPOSES,
    REVIEW_REQUIRED_NODE_IDS,
    SPECIMEN_TYPES,
)

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)

BASE_ANSWERS = {
    "q_specimen_id": "TOP-2026-014",
    "q_specimen_type": "top",
    "q_specimen_other_label": "Offcut from a bookmatched set",
    "q_preparation_state": "joined",
    "q_material_label": "Sitka spruce, flitch SS-2019-03",
    "q_purpose": "characterize_material",
    "q_entry_mode": "capture_new",
    "q_ready_dimensions": True,
    "q_ready_mass": True,
    "q_ready_device": True,
    "q_ready_support": True,
    "q_ready_environment": True,
    "q_environment_skip_reason": "No hygrometer in the shop this week.",
}

EVIDENCE_FOR_KIND = {
    "specimen_record": "ev-specimen-014",
    "measurement_session": "ev-session-014",
    "existing_measurement": "ev-existing-014",
    "manual_workflow_test_note": "ev-note-014",
    "baseline_measurement": "ev-baseline-013",
}


class Clock:
    """Monotonic injected time, so every run is reproducible."""

    def __init__(self) -> None:
        self._tick = 0

    def next(self) -> datetime:
        self._tick += 1
        return T0 + timedelta(minutes=self._tick)


def run_to_completion(
    overrides: dict | None = None,
    *,
    evidence_kind_choice: dict | None = None,
    stop_at: str | None = None,
):
    """Drive the workflow with a scripted set of answers.

    Returns ``(definition, session)`` at the completion node, or at ``stop_at``
    if that node is reached first.
    """
    answers = dict(BASE_ANSWERS)
    answers.update(overrides or {})
    kind_choice = evidence_kind_choice or {}
    definition = PLATE_MEASUREMENT_SETUP_V1
    clock = Clock()
    session = start_session(definition, session_id="s-plate", started_at=T0)

    for _ in range(64):
        node = get_current_node(definition, session)
        if stop_at is not None and node.node_id == stop_at:
            return definition, session
        if isinstance(node, CompleteNodeV1):
            return definition, session
        if isinstance(node, QuestionNodeV1):
            session = answer_question(
                definition, session, answers[node.node_id], answered_at=clock.next()
            )
        elif isinstance(node, InstructionNodeV1):
            session = acknowledge_instruction(
                definition, session, acknowledged_at=clock.next()
            )
        elif isinstance(node, EvidenceRequirementNodeV1):
            kind = kind_choice.get(node.node_id, node.required_evidence_kinds[0])
            session = attach_evidence(
                definition,
                session,
                WorkflowEvidenceReferenceV1(
                    evidence_id=EVIDENCE_FOR_KIND[kind],
                    evidence_kind=kind,
                    source_system="tap_tone_pi",
                ),
                attached_at=clock.next(),
            )
        session = advance_session(definition, session, advanced_at=clock.next())

    raise AssertionError("workflow did not terminate")


def visited(session) -> tuple[str, ...]:
    return session.visited_node_ids


class TestSpecimenBranches:
    def test_top_plate_with_a_new_capture(self):
        definition, session = run_to_completion()
        session = complete_session(definition, session, completed_at=T0)
        assert session.status is GuidedLabSessionStatus.COMPLETED
        assert "q_specimen_other_label" not in visited(session)

    def test_back_plate_with_an_existing_measurement(self):
        definition, session = run_to_completion(
            {"q_specimen_type": "back", "q_entry_mode": "attach_existing"},
            evidence_kind_choice={"e_measurement_reference": "existing_measurement"},
        )
        session = complete_session(definition, session, completed_at=T0)
        assert session.status is GuidedLabSessionStatus.COMPLETED
        kinds = {ref.evidence_kind for ref in session.evidence_references}
        assert "existing_measurement" in kinds

    def test_test_panel_on_the_manual_workflow_test_path(self):
        definition, session = run_to_completion(
            {
                "q_specimen_type": "test_panel",
                "q_entry_mode": "manual_workflow_test",
            },
            evidence_kind_choice={
                "e_measurement_reference": "manual_workflow_test_note"
            },
        )
        session = complete_session(definition, session, completed_at=T0)
        assert session.status is GuidedLabSessionStatus.COMPLETED
        entry_mode = [a for a in session.answers if a.node_id == "q_entry_mode"][0]
        assert entry_mode.value == "manual_workflow_test"

    def test_other_specimen_requires_a_description(self):
        definition, session = run_to_completion({"q_specimen_type": "other"})
        assert "q_specimen_other_label" in visited(session)
        label = [a for a in session.answers if a.node_id == "q_specimen_other_label"][0]
        assert label.value == "Offcut from a bookmatched set"

    def test_manual_test_mode_is_labelled_as_workflow_testing(self):
        node = next(
            n for n in PLATE_MEASUREMENT_SETUP_V1.nodes if n.node_id == "q_entry_mode"
        )
        assert "workflow-testing" in node.body

    def test_every_specimen_type_reaches_completion(self):
        for specimen_type in SPECIMEN_TYPES:
            definition, session = run_to_completion({"q_specimen_type": specimen_type})
            assert isinstance(get_current_node(definition, session), CompleteNodeV1), (
                specimen_type
            )

    def test_every_preparation_state_reaches_completion(self):
        for state in PREPARATION_STATES:
            definition, session = run_to_completion({"q_preparation_state": state})
            assert isinstance(get_current_node(definition, session), CompleteNodeV1)

    def test_every_entry_mode_reaches_completion(self):
        kind_for_mode = {
            "capture_new": "measurement_session",
            "attach_existing": "existing_measurement",
            "manual_workflow_test": "manual_workflow_test_note",
        }
        for mode in ENTRY_MODES:
            definition, session = run_to_completion(
                {"q_entry_mode": mode},
                evidence_kind_choice={"e_measurement_reference": kind_for_mode[mode]},
            )
            assert isinstance(get_current_node(definition, session), CompleteNodeV1)


class TestPurposeBranches:
    def test_baseline_purpose_does_not_request_a_baseline_reference(self):
        _, session = run_to_completion({"q_purpose": "establish_baseline"})
        assert "e_baseline_reference" not in visited(session)

    def test_characterize_purpose_does_not_request_a_baseline_reference(self):
        _, session = run_to_completion({"q_purpose": "characterize_material"})
        assert "e_baseline_reference" not in visited(session)

    def test_verification_purpose_does_not_request_a_baseline_reference(self):
        _, session = run_to_completion({"q_purpose": "verify_earlier_measurement"})
        assert "e_baseline_reference" not in visited(session)

    def test_before_after_purpose_requests_a_baseline_reference(self):
        _, session = run_to_completion({"q_purpose": "compare_after_removal"})
        assert "e_baseline_reference" in visited(session)
        kinds = {ref.evidence_kind for ref in session.evidence_references}
        assert "baseline_measurement" in kinds

    def test_before_after_baseline_evidence_is_required(self):
        definition, session = run_to_completion(
            {"q_purpose": "compare_after_removal"}, stop_at="e_baseline_reference"
        )
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING

    def test_every_purpose_reaches_completion(self):
        for purpose in PURPOSES:
            definition, session = run_to_completion({"q_purpose": purpose})
            assert isinstance(get_current_node(definition, session), CompleteNodeV1), (
                purpose
            )


class TestEnvironmentalRecord:
    def test_supplied_environmental_record_skips_the_reason_question(self):
        _, session = run_to_completion({"q_ready_environment": True})
        assert "q_environment_skip_reason" not in visited(session)

    def test_absent_environmental_record_requires_a_reason(self):
        _, session = run_to_completion({"q_ready_environment": False})
        assert "q_environment_skip_reason" in visited(session)
        reason = [
            a for a in session.answers if a.node_id == "q_environment_skip_reason"
        ][0]
        assert reason.value == "No hygrometer in the shop this week."

    def test_skipping_without_answering_the_reason_is_blocked(self):
        definition, session = run_to_completion(
            {"q_ready_environment": False}, stop_at="q_environment_skip_reason"
        )
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_empty_reason_is_rejected(self):
        definition, session = run_to_completion(
            {"q_ready_environment": False}, stop_at="q_environment_skip_reason"
        )
        with pytest.raises(GuidedLabActionError) as excinfo:
            answer_question(definition, session, "", answered_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.ANSWER_NOT_ALLOWED

    def test_a_no_answer_elsewhere_does_not_block_the_record(self):
        definition, session = run_to_completion(
            {"q_ready_mass": False, "q_ready_dimensions": False}
        )
        session = complete_session(definition, session, completed_at=T0)
        assert session.status is GuidedLabSessionStatus.COMPLETED


class TestEvidenceRequirements:
    def test_specimen_record_is_required(self):
        definition, session = run_to_completion(stop_at="e_specimen_record")
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING

    def test_measurement_reference_is_required(self):
        definition, session = run_to_completion(stop_at="e_measurement_reference")
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.REQUIRED_EVIDENCE_MISSING

    def test_setup_acknowledgment_is_required(self):
        definition, session = run_to_completion(stop_at="i_preparation")
        with pytest.raises(GuidedLabActionError) as excinfo:
            advance_session(definition, session, advanced_at=T0)
        assert excinfo.value.code is GuidedLabErrorCode.ACTION_INVALID_FOR_NODE

    def test_no_evidence_reference_holds_a_path(self):
        _, session = run_to_completion({"q_purpose": "compare_after_removal"})
        for reference in session.evidence_references:
            for value in (reference.evidence_id, reference.label or ""):
                assert "/" not in value
                assert "\\" not in value


class TestReviewCompletenessIsNotHandMaintained:
    """The review list is written by hand; this is what keeps it honest.

    A step added to the common path but forgotten in ``REVIEW_REQUIRED_NODE_IDS``
    would weaken the review with nothing failing. Rather than trust the author,
    derive the answer from the graph: every question and instruction that lies
    on *all* routes to the review is required there, and nothing else is.
    """

    @staticmethod
    def _routes_to_review() -> list[set[str]]:
        definition = PLATE_MEASUREMENT_SETUP_V1
        edges: dict[str, list[str]] = {}
        for transition in definition.transitions:
            edges.setdefault(transition.from_node_id, []).append(transition.to_node_id)

        routes: list[set[str]] = []
        stack: list[tuple[str, tuple[str, ...]]] = [(definition.entry_node_id, ())]
        while stack:
            node_id, walked = stack.pop()
            if node_id in walked:  # a cycle cannot add a node to every route
                continue
            walked = walked + (node_id,)
            if node_id == "r_review":
                routes.append(set(walked))
                continue
            for target in edges.get(node_id, ()):
                stack.append((target, walked))
        return routes

    def test_more_than_one_route_reaches_the_review(self):
        """Otherwise the intersection below proves nothing."""
        assert len(self._routes_to_review()) > 1

    def test_the_review_requires_exactly_the_steps_on_every_route(self):
        index = {node.node_id: node for node in PLATE_MEASUREMENT_SETUP_V1.nodes}
        routes = self._routes_to_review()
        always_walked = set.intersection(*routes)
        expected = {
            node_id
            for node_id in always_walked
            if isinstance(index[node_id], (QuestionNodeV1, InstructionNodeV1))
        }
        assert set(REVIEW_REQUIRED_NODE_IDS) == expected

    def test_no_branch_only_step_is_required_at_the_review(self):
        """A review demanding one could never be satisfied on the other branch."""
        routes = self._routes_to_review()
        branch_only = set.union(*routes) - set.intersection(*routes)
        assert branch_only  # the workflow does branch
        assert branch_only.isdisjoint(REVIEW_REQUIRED_NODE_IDS)


class TestReviewAndCorrection:
    def test_review_reports_nothing_missing_on_a_full_walk(self):
        definition, session = run_to_completion(stop_at="r_review")
        progress = get_workflow_progress(definition, session)
        assert progress.missing_required_node_ids == ()

    def test_review_reports_an_outstanding_requirement(self):
        definition, session = run_to_completion(stop_at="r_review")
        stripped = dataclasses.replace(session, acknowledged_node_ids=())
        progress = get_workflow_progress(definition, stripped)
        assert "i_preparation" in progress.missing_required_node_ids
        assert "r_review" in progress.missing_required_node_ids

    def test_review_blocks_advance_while_a_requirement_is_outstanding(self):
        definition, session = run_to_completion(stop_at="r_review")
        stripped = dataclasses.replace(session, acknowledged_node_ids=())
        with pytest.raises(GuidedLabActionError):
            advance_session(definition, stripped, advanced_at=T0)

    def test_correcting_specimen_type_invalidates_dependent_state(self):
        definition, session = run_to_completion(stop_at="r_review")
        assert "q_specimen_other_label" not in visited(session)
        corrected = replace_answer(
            definition,
            session,
            node_id="q_specimen_type",
            value="other",
            answered_at=T0,
        )
        assert corrected.current_node_id == "q_specimen_other_label"
        assert corrected.acknowledged_node_ids == ()
        assert corrected.evidence_references == ()
        answered = {a.node_id for a in corrected.answers}
        assert answered == {"q_specimen_id", "q_specimen_type"}

    def test_correction_preserves_the_upstream_answer(self):
        definition, session = run_to_completion(stop_at="r_review")
        corrected = replace_answer(
            definition,
            session,
            node_id="q_specimen_type",
            value="other",
            answered_at=T0,
        )
        specimen_id = [a for a in corrected.answers if a.node_id == "q_specimen_id"][0]
        assert specimen_id.value == "TOP-2026-014"
        assert specimen_id.revision == 1

    def test_correcting_the_purpose_drops_the_baseline_reference(self):
        definition, session = run_to_completion(
            {"q_purpose": "compare_after_removal"}, stop_at="r_review"
        )
        assert any(
            ref.evidence_kind == "baseline_measurement"
            for ref in session.evidence_references
        )
        corrected = replace_answer(
            definition,
            session,
            node_id="q_purpose",
            value="characterize_material",
            answered_at=T0,
        )
        kinds = {ref.evidence_kind for ref in corrected.evidence_references}
        assert "baseline_measurement" not in kinds

    def test_correction_history_is_recorded_as_a_revision(self):
        definition, session = run_to_completion(stop_at="r_review")
        corrected = replace_answer(
            definition,
            session,
            node_id="q_specimen_type",
            value="back",
            answered_at=T0,
        )
        answer = [a for a in corrected.answers if a.node_id == "q_specimen_type"][0]
        assert answer.revision == 2


class TestCompletionRecord:
    def test_completed_record_preserves_workflow_lineage(self):
        definition, session = run_to_completion()
        session = complete_session(definition, session, completed_at=T0)
        assert session.workflow_id == "plate_measurement_setup"
        assert session.workflow_version == 1
        assert session.schema_version == "guided_lab_session_v1"
        assert session.completed_at == T0

    def test_completed_record_round_trips(self):
        definition, session = run_to_completion()
        session = complete_session(definition, session, completed_at=T0)
        assert GuidedLabSessionV1.from_dict(session.to_dict()) == session

    def test_completed_record_holds_every_required_element(self):
        definition, session = run_to_completion(
            {"q_purpose": "compare_after_removal", "q_ready_environment": False}
        )
        session = complete_session(definition, session, completed_at=T0)
        answered = {a.node_id for a in session.answers}
        assert {
            "q_specimen_id",
            "q_specimen_type",
            "q_preparation_state",
            "q_material_label",
            "q_purpose",
            "q_entry_mode",
            "q_ready_dimensions",
            "q_ready_mass",
            "q_ready_device",
            "q_ready_support",
            "q_ready_environment",
            "q_environment_skip_reason",
        } <= answered
        assert "i_preparation" in session.acknowledged_node_ids
        assert len(session.evidence_references) == 3
        assert "r_review" in session.visited_node_ids

    def test_serialized_record_contains_no_host_path(self):
        definition, session = run_to_completion()
        session = complete_session(definition, session, completed_at=T0)
        blob = repr(session.to_dict())
        assert "C:" not in blob
        assert "\\\\" not in blob


class TestBoundaryLanguage:
    ALL_TEXT = " ".join(
        " ".join(
            [
                node.title,
                node.body,
                node.why_this_matters,
                getattr(node, "completion_message", ""),
            ]
        )
        for node in PLATE_MEASUREMENT_SETUP_V1.nodes
    ).lower()

    @pytest.mark.parametrize(
        "phrase",
        [
            "target thickness",
            "remove wood",
            "wood should be removed",
            "should remove",
            "thin the plate",
            "sand until",
            "recommend",
            "optimal",
            "tone quality",
            "better tone",
            "sounds better",
            "grade",
            "scientifically valid",
            "measurement is valid",
            "correctly identified",
            # A modal-identification claim. Kept narrow so it does not fire on
            # innocuous prose such as "the entry mode is recorded".
            "the mode is",
            "mode identified",
            "identified the mode",
            "is suitable",
            "good plate",
        ],
    )
    def test_no_prohibited_conclusion_language(self, phrase):
        assert phrase not in self.ALL_TEXT

    def test_completion_message_claims_nothing_about_the_specimen(self):
        node = next(
            n for n in PLATE_MEASUREMENT_SETUP_V1.nodes if isinstance(n, CompleteNodeV1)
        )
        message = node.completion_message.lower()
        for word in ("suitable", "valid", "verified", "confirmed", "proven"):
            assert word not in message
        assert "makes no statement" in message

    def test_preparation_instruction_is_explicitly_provisional(self):
        node = next(
            n
            for n in PLATE_MEASUREMENT_SETUP_V1.nodes
            if isinstance(n, InstructionNodeV1)
        )
        assert "provisional" in node.body.lower()
        reference = next(
            ref
            for ref in PLATE_MEASUREMENT_SETUP_V1.source_references
            if ref.source_reference_id in node.source_reference_ids
        )
        assert reference.authority_status is SourceAuthorityStatus.PROVISIONAL

    def test_workflow_title_is_builder_facing(self):
        title = PLATE_MEASUREMENT_SETUP_V1.title.lower()
        for analyzer_word in ("fft", "spectrum", "analyzer", "rayleigh", "modal"):
            assert not title.startswith(analyzer_word)
        assert "plate measurement" in title

    def test_review_requirements_reference_only_answerable_steps(self):
        index = {n.node_id: n for n in PLATE_MEASUREMENT_SETUP_V1.nodes}
        review = next(
            n for n in PLATE_MEASUREMENT_SETUP_V1.nodes if isinstance(n, ReviewNodeV1)
        )
        for node_id in review.required_node_ids:
            assert isinstance(index[node_id], (QuestionNodeV1, InstructionNodeV1)), (
                node_id
            )

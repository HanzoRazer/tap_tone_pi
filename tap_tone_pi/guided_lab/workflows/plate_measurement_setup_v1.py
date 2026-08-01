# INSTRUMENT CLASS: MEASUREMENT
"""Plate Measurement Setup, version 1 — the DO-100 reference workflow.

An operator enters with a goal: *I want to prepare a plate measurement.* This
workflow walks them through specimen identity, why they are measuring, how the
measurement will enter the system, a preparation step, readiness questions,
evidence references, and a review, and closes a permanent record of what they
entered.

The record is a record of *procedure*. Completing it does not say the specimen
is suitable, does not say the setup is sound, does not identify a mode, does not
propose a thickness, and does not suggest removing wood. Every one of those
belongs to a downstream system, not here.

The preparation instruction is marked ``provisional``: no consolidated Tap Tone
Pi laboratory doctrine for plate tap setup exists in this repository yet, and
inventing a citation would be worse than admitting the gap. The text exists to
exercise the workflow architecture and says so.
"""

from __future__ import annotations

from tap_tone_pi.guided_lab.models import (
    ChoiceConstraintV1,
    CompleteNodeV1,
    EvidenceRequirementNodeV1,
    InstructionNodeV1,
    QuestionNodeV1,
    ReviewNodeV1,
    SourceAuthorityStatus,
    TextConstraintV1,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowDefinitionV1,
    WorkflowSourceReferenceV1,
    WorkflowTransitionConditionV1,
    WorkflowTransitionV1,
)

WORKFLOW_ID = "plate_measurement_setup"
WORKFLOW_VERSION = 1

# -- Answer vocabularies ----------------------------------------------------

SPECIMEN_TYPES = ("top", "back", "test_panel", "other")
PREPARATION_STATES = ("joined", "unjoined", "not_applicable")
PURPOSES = (
    "characterize_material",
    "establish_baseline",
    "compare_after_removal",
    "verify_earlier_measurement",
)
ENTRY_MODES = ("capture_new", "attach_existing", "manual_workflow_test")

#: Purposes that do not ask for a prior baseline reference.
PURPOSES_WITHOUT_BASELINE = tuple(p for p in PURPOSES if p != "compare_after_removal")

#: Evidence kinds this workflow accepts for the measurement itself.
MEASUREMENT_EVIDENCE_KINDS = (
    "measurement_session",
    "existing_measurement",
    "manual_workflow_test_note",
)

#: Steps the review stage expects an entry for on every path through the
#: workflow. Branch-only steps are deliberately absent: a review that demanded
#: them could never be satisfied on the other branch. Evidence steps are absent
#: because each one already blocks its own advance.
REVIEW_REQUIRED_NODE_IDS = (
    "q_specimen_id",
    "q_specimen_type",
    "q_preparation_state",
    "q_material_label",
    "q_purpose",
    "q_entry_mode",
    "i_preparation",
    "q_ready_dimensions",
    "q_ready_mass",
    "q_ready_device",
    "q_ready_support",
    "q_ready_environment",
)


# -- Sources ----------------------------------------------------------------

PROVISIONAL_SETUP_SOURCE = WorkflowSourceReferenceV1(
    source_reference_id="src_do100_provisional_setup",
    title="Provisional plate measurement setup guidance",
    citation=(
        "Internal DO-100 placeholder. Not promoted as Tap Tone Pi laboratory "
        "doctrine and not drawn from an external authority."
    ),
    authority_status=SourceAuthorityStatus.PROVISIONAL,
)


# -- Nodes ------------------------------------------------------------------

NODES = (
    QuestionNodeV1(
        node_id="q_specimen_id",
        title="What is this specimen called?",
        body=(
            "Give the plate or panel an identifier you will recognise later — "
            "whatever you already write on the wood or in your notes."
        ),
        answer_kind=WorkflowAnswerKind.TEXT,
        constraints=TextConstraintV1(minimum_length=1, maximum_length=120),
        why_this_matters=(
            "Every later reference in this record points back to this name. "
            "Without it the record cannot be tied to a piece of wood."
        ),
    ),
    QuestionNodeV1(
        node_id="q_specimen_type",
        title="Which part are you preparing to measure?",
        body=(
            "Choose one: 'top' for a soundboard, 'back' for a back plate, "
            "'test_panel' for an offcut or sample panel, 'other' for anything "
            "else — you will be asked to describe it."
        ),
        answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
        constraints=ChoiceConstraintV1(allowed_values=SPECIMEN_TYPES),
        why_this_matters=(
            "The part being measured is recorded as entered. This workflow "
            "does not change what it asks for based on the answer beyond "
            "requesting a description for 'other'."
        ),
    ),
    QuestionNodeV1(
        node_id="q_specimen_other_label",
        title="How would you describe this specimen?",
        body="Describe the piece in your own words.",
        answer_kind=WorkflowAnswerKind.TEXT,
        constraints=TextConstraintV1(minimum_length=1, maximum_length=200),
        why_this_matters=(
            "'other' carries no meaning on its own. Your description is what "
            "makes the record readable a year from now."
        ),
    ),
    QuestionNodeV1(
        node_id="q_preparation_state",
        title="Is the plate joined yet?",
        body=(
            "Choose one: 'joined' if the halves are glued together, "
            "'unjoined' if they are separate, 'not_applicable' for a "
            "single-piece specimen."
        ),
        answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
        constraints=ChoiceConstraintV1(allowed_values=PREPARATION_STATES),
        why_this_matters=(
            "A joined plate and its two halves are different specimens. "
            "Recording which one you measured keeps later comparisons honest."
        ),
    ),
    QuestionNodeV1(
        node_id="q_material_label",
        title="What material is this?",
        body=(
            "Enter the species, flitch, or supplier label you use for this "
            "wood. Free text — enter what you actually have written down."
        ),
        answer_kind=WorkflowAnswerKind.TEXT,
        constraints=TextConstraintV1(minimum_length=1, maximum_length=200),
        why_this_matters=(
            "The material label is stored as text, exactly as you enter it. "
            "Nothing in this workflow looks up wood properties from it."
        ),
    ),
    QuestionNodeV1(
        node_id="q_purpose",
        title="Why are you taking this measurement?",
        body=(
            "Choose one: 'characterize_material' to learn about the wood, "
            "'establish_baseline' to record a starting point, "
            "'compare_after_removal' to compare against an earlier state — "
            "you will be asked for that earlier reference — or "
            "'verify_earlier_measurement' to repeat a measurement you "
            "already took."
        ),
        answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
        constraints=ChoiceConstraintV1(allowed_values=PURPOSES),
        why_this_matters=(
            "Your stated purpose is recorded, and it decides one thing in this "
            "workflow: whether a baseline reference is requested."
        ),
    ),
    QuestionNodeV1(
        node_id="q_entry_mode",
        title="How will the measurement reach the system?",
        body=(
            "Choose one: 'capture_new' if you are about to record a new "
            "measurement, 'attach_existing' if you will point at a "
            "measurement you already have, or 'manual_workflow_test' if you "
            "are exercising this workflow itself and no real measurement is "
            "involved. Records entered as 'manual_workflow_test' are "
            "workflow-testing entries and nothing else."
        ),
        answer_kind=WorkflowAnswerKind.SINGLE_CHOICE,
        constraints=ChoiceConstraintV1(allowed_values=ENTRY_MODES),
        why_this_matters=(
            "The entry mode is recorded so a reader can tell a real "
            "measurement setup from a run made to exercise the software."
        ),
    ),
    InstructionNodeV1(
        node_id="i_preparation",
        title="Set up the bench before you measure",
        body=(
            "Provisional setup guidance for workflow validation only. This "
            "instruction has not yet been promoted as authoritative Tap Tone "
            "Pi laboratory doctrine.\n\n"
            "Suggested steps: rest the plate on soft supports away from the "
            "regions you intend to excite; keep the microphone position and "
            "distance the same as any measurement you plan to compare "
            "against; let the wood sit in the room long enough to settle; "
            "note the room temperature and humidity if you have them; and "
            "keep the tap position and strength as repeatable as you can.\n\n"
            "This list is a starting point for exercising the workflow, not a "
            "statement that a setup following it is sufficient."
        ),
        source_reference_ids=(PROVISIONAL_SETUP_SOURCE.source_reference_id,),
        why_this_matters=(
            "Acknowledging this step records that you saw the guidance. It "
            "records nothing about the state of your bench."
        ),
    ),
    QuestionNodeV1(
        node_id="q_ready_dimensions",
        title="Do you have the specimen's dimensions?",
        body="Answer yes or no.",
        answer_kind=WorkflowAnswerKind.BOOLEAN,
        why_this_matters=(
            "Recorded as entered. A 'no' does not stop the workflow; it is "
            "part of the record of what was available at the time."
        ),
    ),
    QuestionNodeV1(
        node_id="q_ready_mass",
        title="Do you have the specimen's mass?",
        body="Answer yes or no.",
        answer_kind=WorkflowAnswerKind.BOOLEAN,
        why_this_matters="Recorded as entered.",
    ),
    QuestionNodeV1(
        node_id="q_ready_device",
        title="Is your acquisition device ready?",
        body="Answer yes or no.",
        answer_kind=WorkflowAnswerKind.BOOLEAN,
        why_this_matters=(
            "Recorded as entered. This workflow does not talk to any audio "
            "device and cannot check this for you."
        ),
    ),
    QuestionNodeV1(
        node_id="q_ready_support",
        title="Is the specimen resting on a stable support?",
        body="Answer yes or no.",
        answer_kind=WorkflowAnswerKind.BOOLEAN,
        why_this_matters="Recorded as entered.",
    ),
    QuestionNodeV1(
        node_id="q_ready_environment",
        title="Do you have a temperature and humidity record?",
        body=(
            "Answer yes or no. If you answer no, you will be asked to say "
            "why, so the gap is recorded rather than silent."
        ),
        answer_kind=WorkflowAnswerKind.BOOLEAN,
        why_this_matters=(
            "Wood responds to its environment. A record without environmental "
            "data is still a record, provided the omission is stated."
        ),
    ),
    QuestionNodeV1(
        node_id="q_environment_skip_reason",
        title="Why is there no environmental record?",
        body="Say briefly why temperature and humidity are not available.",
        answer_kind=WorkflowAnswerKind.TEXT,
        constraints=TextConstraintV1(minimum_length=1, maximum_length=300),
        why_this_matters=(
            "A stated reason lets a later reader judge the gap for "
            "themselves. A silent omission does not."
        ),
    ),
    EvidenceRequirementNodeV1(
        node_id="e_specimen_record",
        title="Point at the specimen record",
        body=(
            "Attach the identifier of the specimen record this measurement "
            "belongs to. Identifiers only — this workflow stores no file "
            "paths."
        ),
        required_evidence_kinds=("specimen_record",),
        minimum_count=1,
        why_this_matters=(
            "The reference is what ties this setup record to the specimen it describes."
        ),
    ),
    EvidenceRequirementNodeV1(
        node_id="e_measurement_reference",
        title="Point at the measurement or session",
        body=(
            "Attach the identifier of the measurement session you are about "
            "to run, the existing measurement you are attaching, or the note "
            "standing in for one on a workflow-test run."
        ),
        required_evidence_kinds=MEASUREMENT_EVIDENCE_KINDS,
        minimum_count=1,
        why_this_matters=(
            "Without this reference the setup record stands alone and cannot "
            "be traced to any measurement."
        ),
    ),
    EvidenceRequirementNodeV1(
        node_id="e_baseline_reference",
        title="Point at the earlier state you are comparing against",
        body=(
            "You said you are comparing against an earlier state. Attach the "
            "identifier of that earlier measurement."
        ),
        required_evidence_kinds=("baseline_measurement",),
        minimum_count=1,
        why_this_matters=(
            "A comparison needs both sides identified. This workflow records "
            "the pairing; it does not compute the comparison."
        ),
    ),
    ReviewNodeV1(
        node_id="r_review",
        title="Review the record before closing it",
        body=(
            "Everything you entered is listed for you here, along with "
            "anything still outstanding. Go back and correct any step before "
            "closing the record — a correction discards whatever no longer "
            "applies."
        ),
        required_node_ids=REVIEW_REQUIRED_NODE_IDS,
        why_this_matters=(
            "This is the last point at which the record can be changed. Once "
            "closed it is a permanent statement of what you entered."
        ),
    ),
    CompleteNodeV1(
        node_id="c_complete",
        title="Setup workflow record complete",
        body=("The setup workflow record is closed and can be read back or exported."),
        completion_message=(
            "Setup workflow record complete. This record holds the specimen "
            "identity, purpose, entry mode, readiness answers, and evidence "
            "references you entered. It makes no statement about the "
            "specimen, the setup, or any measurement."
        ),
        why_this_matters=(
            "What was entered is now fixed and attributable. Interpreting it "
            "is a separate job for a separate system."
        ),
    ),
)


# -- Transitions ------------------------------------------------------------


def _always(from_node_id: str, to_node_id: str) -> WorkflowTransitionV1:
    return WorkflowTransitionV1(
        from_node_id=from_node_id,
        condition=WorkflowTransitionConditionV1(kind=TransitionConditionKind.ALWAYS),
        to_node_id=to_node_id,
    )


def _when_equals(
    from_node_id: str, to_node_id: str, *, node_id: str, value: object
) -> WorkflowTransitionV1:
    return WorkflowTransitionV1(
        from_node_id=from_node_id,
        condition=WorkflowTransitionConditionV1(
            kind=TransitionConditionKind.ANSWER_EQUALS,
            node_id=node_id,
            expected_value=value,  # type: ignore[arg-type]
        ),
        to_node_id=to_node_id,
    )


def _when_in(
    from_node_id: str, to_node_id: str, *, node_id: str, values: tuple
) -> WorkflowTransitionV1:
    return WorkflowTransitionV1(
        from_node_id=from_node_id,
        condition=WorkflowTransitionConditionV1(
            kind=TransitionConditionKind.ANSWER_IN_SET,
            node_id=node_id,
            expected_values=values,
        ),
        to_node_id=to_node_id,
    )


def _when_boolean(
    from_node_id: str, to_node_id: str, *, node_id: str, value: bool
) -> WorkflowTransitionV1:
    return WorkflowTransitionV1(
        from_node_id=from_node_id,
        condition=WorkflowTransitionConditionV1(
            kind=(
                TransitionConditionKind.BOOLEAN_TRUE
                if value
                else TransitionConditionKind.BOOLEAN_FALSE
            ),
            node_id=node_id,
        ),
        to_node_id=to_node_id,
    )


TRANSITIONS = (
    _always("q_specimen_id", "q_specimen_type"),
    # 'other' needs a description; the named types go straight on.
    _when_equals(
        "q_specimen_type",
        "q_specimen_other_label",
        node_id="q_specimen_type",
        value="other",
    ),
    _when_in(
        "q_specimen_type",
        "q_preparation_state",
        node_id="q_specimen_type",
        values=("top", "back", "test_panel"),
    ),
    _always("q_specimen_other_label", "q_preparation_state"),
    _always("q_preparation_state", "q_material_label"),
    _always("q_material_label", "q_purpose"),
    _always("q_purpose", "q_entry_mode"),
    _always("q_entry_mode", "i_preparation"),
    _always("i_preparation", "q_ready_dimensions"),
    _always("q_ready_dimensions", "q_ready_mass"),
    _always("q_ready_mass", "q_ready_device"),
    _always("q_ready_device", "q_ready_support"),
    _always("q_ready_support", "q_ready_environment"),
    # A missing environmental record has to be explained, not skipped.
    _when_boolean(
        "q_ready_environment",
        "e_specimen_record",
        node_id="q_ready_environment",
        value=True,
    ),
    _when_boolean(
        "q_ready_environment",
        "q_environment_skip_reason",
        node_id="q_ready_environment",
        value=False,
    ),
    _always("q_environment_skip_reason", "e_specimen_record"),
    _always("e_specimen_record", "e_measurement_reference"),
    # Only a before/after comparison asks for the earlier state.
    _when_equals(
        "e_measurement_reference",
        "e_baseline_reference",
        node_id="q_purpose",
        value="compare_after_removal",
    ),
    _when_in(
        "e_measurement_reference",
        "r_review",
        node_id="q_purpose",
        values=PURPOSES_WITHOUT_BASELINE,
    ),
    _always("e_baseline_reference", "r_review"),
    _always("r_review", "c_complete"),
)


PLATE_MEASUREMENT_SETUP_V1 = WorkflowDefinitionV1(
    workflow_id=WORKFLOW_ID,
    workflow_version=WORKFLOW_VERSION,
    title="Prepare a plate measurement",
    purpose=(
        "Walk a builder through specimen identity, measurement purpose, entry "
        "mode, preparation, readiness, and evidence references, and close a "
        "resumable record of what was entered."
    ),
    entry_node_id="q_specimen_id",
    nodes=NODES,
    transitions=TRANSITIONS,
    source_references=(PROVISIONAL_SETUP_SOURCE,),
)


__all__ = [
    "ENTRY_MODES",
    "MEASUREMENT_EVIDENCE_KINDS",
    "PLATE_MEASUREMENT_SETUP_V1",
    "PREPARATION_STATES",
    "PURPOSES",
    "PURPOSES_WITHOUT_BASELINE",
    "REVIEW_REQUIRED_NODE_IDS",
    "SPECIMEN_TYPES",
    "WORKFLOW_ID",
    "WORKFLOW_VERSION",
]

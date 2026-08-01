# INSTRUMENT CLASS: MEASUREMENT
"""Builder-goal catalog for the guided laboratory (DO-100).

The catalog is the entry point a builder actually meets. It lists goals in
their own words — "I want to prepare a plate measurement" — and resolves the
chosen goal to a workflow definition. An operator never has to pick an FFT, a
plate model, or an analyzer to get started.

Goals that are not yet built are listed anyway, marked unavailable and carrying
a reason. Listing them is honest about what is coming; resolving one fails
rather than returning a placeholder, because a half-built procedure that looks
real is worse than an absent one. It fails with ``GDL-404``, not ``GDL-402``:
"listed but not built yet" and "no such workflow" are different answers, and an
operator who picked a goal off the list should not be told they mistyped it.

The shipped registry is validated on first use rather than at import, and the
result is cached. A duplicate registry key or an unsound definition still fails
loudly the first time anything asks the catalog for a workflow — it just no
longer fails while ``ttp`` is building its argument parser, where it would have
taken down commands that have nothing to do with the guided laboratory.
"""

from __future__ import annotations

from tap_tone_pi.guided_lab.errors import (
    GuidedLabErrorCode,
    GuidedLabSessionError,
)
from tap_tone_pi.guided_lab.models import (
    WorkflowDefinitionV1,
    WorkflowIntentV1,
)
from tap_tone_pi.guided_lab.validation import (
    require_unique_workflow_keys,
    require_valid_workflow_definition,
)
from tap_tone_pi.guided_lab.workflows import WORKFLOW_DEFINITIONS

#: Builder goals, in the order an operator sees them. Available goals first.
WORKFLOW_INTENTS: tuple[WorkflowIntentV1, ...] = (
    WorkflowIntentV1(
        intent_id="evaluate_plate_measurement_setup",
        title="I want to prepare a plate measurement",
        summary=(
            "Work through specimen identity, why you are measuring, how the "
            "measurement will reach the system, bench preparation, readiness, "
            "and the references that tie the record together."
        ),
        workflow_id="plate_measurement_setup",
        available=True,
    ),
    WorkflowIntentV1(
        intent_id="compare_before_after",
        title="I want to compare a plate before and after taking material off",
        summary=(
            "Pair two measurement records of the same specimen and record what "
            "changed between them."
        ),
        workflow_id="plate_change_comparison",
        available=False,
        unavailable_reason=(
            "Not built yet. The setup workflow can already record a before/"
            "after pairing; the comparison procedure itself is a later dev "
            "order."
        ),
    ),
    WorkflowIntentV1(
        intent_id="investigate_wolf_note",
        title="I want to look into a wolf note",
        summary=(
            "Work through capturing the evidence a wolf-note investigation needs."
        ),
        workflow_id="wolf_note_investigation",
        available=False,
        unavailable_reason=(
            "Not built yet. Wolf-note detection exists as a measurement "
            "module, but no guided procedure wraps it."
        ),
    ),
    WorkflowIntentV1(
        intent_id="evaluate_plate_thickness",
        title="I want to work through a plate's thickness",
        summary="Record a thickness survey against a specimen.",
        workflow_id="plate_thickness_survey",
        available=False,
        unavailable_reason=(
            "Not built yet, and deliberately out of scope for DO-100: "
            "thickness targets are an advisory judgement that belongs "
            "downstream, not in this repository."
        ),
    ),
)


#: Set once the shipped registry has passed its uniqueness check.
_registry_checked = False


def shipped_workflow_definitions() -> tuple[WorkflowDefinitionV1, ...]:
    """Return the shipped registry, checking it the first time.

    Both halves of the promise this module's docstring makes are checked here:
    registry keys are unique, *and* every shipped definition is sound. Only the
    key check used to run, which left ``start`` — the one caller that validates
    a definition on its own — as the sole place an unsound shipped workflow
    could surface. ``show`` and ``act`` resolve the same registry and would have
    gone on serving a definition the validator rejects.

    Deliberately not an import-time check: the guided laboratory is one
    subcommand of a larger CLI, and an authoring mistake in a workflow should
    surface when someone reaches for a workflow, not when ``ttp --help`` runs.
    """
    global _registry_checked
    if not _registry_checked:
        require_unique_workflow_keys(WORKFLOW_DEFINITIONS)
        for definition in WORKFLOW_DEFINITIONS:
            require_valid_workflow_definition(definition)
        _registry_checked = True
    return WORKFLOW_DEFINITIONS


def list_workflow_intents() -> tuple[WorkflowIntentV1, ...]:
    """List every builder goal, available or not, in presentation order."""
    return WORKFLOW_INTENTS


def _unavailable_intent(workflow_id: str) -> WorkflowIntentV1 | None:
    """The listed-but-not-built goal behind ``workflow_id``, if there is one."""
    for intent in WORKFLOW_INTENTS:
        if intent.workflow_id == workflow_id and not intent.available:
            return intent
    return None


def get_workflow_definition(
    workflow_id: str,
    workflow_version: int | None = None,
) -> WorkflowDefinitionV1:
    """Resolve a workflow by id, and by version when one is given.

    Omitting ``workflow_version`` selects the highest shipped version. A goal
    the catalog lists but has not built raises ``GDL-404`` carrying the reason
    the operator was shown; anything else raises ``GDL-402``.
    """
    definitions = shipped_workflow_definitions()
    candidates = [
        definition
        for definition in definitions
        if definition.workflow_id == workflow_id
    ]
    matched_id = bool(candidates)
    if workflow_version is not None:
        candidates = [
            definition
            for definition in candidates
            if definition.workflow_version == workflow_version
        ]
    if candidates:
        return max(candidates, key=lambda definition: definition.workflow_version)

    intent = None if matched_id else _unavailable_intent(workflow_id)
    if intent is not None:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.WORKFLOW_NOT_AVAILABLE,
            "this guided laboratory goal is listed but not built yet",
            {
                "workflow_id": workflow_id,
                "intent_id": intent.intent_id,
                "unavailable_reason": intent.unavailable_reason,
            },
        )
    raise GuidedLabSessionError(
        GuidedLabErrorCode.UNKNOWN_WORKFLOW,
        "no such guided laboratory workflow",
        {
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "available_workflow_ids": sorted({d.workflow_id for d in definitions}),
        },
    )


__all__ = [
    "WORKFLOW_INTENTS",
    "get_workflow_definition",
    "list_workflow_intents",
    "shipped_workflow_definitions",
]

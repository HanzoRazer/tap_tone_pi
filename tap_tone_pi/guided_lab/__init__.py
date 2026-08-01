"""Guided Digital Laboratory — declarative operator procedures (DO-100).

A builder starts from a goal ("I want to prepare a plate measurement"), not
from an analyzer. This package owns the procedure: the questions asked, the
instructions shown, the evidence required, and the resumable session record
that results.

It deliberately owns none of the science. Nothing here computes a spectrum,
identifies a mode, proposes a thickness, or judges an instrument. The engine is
pure: given a definition, a session, an action, and an injected timestamp, the
resulting state is fully determined — no filesystem, no audio device, no
network, no model.

Public surface, and it is deliberately narrow. ``__all__`` below is a promise:
those names are supported and will not move without a version bump. Two kinds
of thing are in it —

* the **vocabulary** — the record types, enums, and error classes a caller
  needs to describe a session or catch a failure — exported flat, because a
  caller handles these constantly;
* the **behaviour** — :mod:`~tap_tone_pi.guided_lab.engine`,
  :mod:`~tap_tone_pi.guided_lab.catalog`, and
  :mod:`~tap_tone_pi.guided_lab.validation` — exported as modules, not as
  loose functions. ``engine.advance_session(...)`` says where the rule lives,
  and it keeps a package-level name from being minted for every function the
  engine will ever grow.

Anything not listed lives in a submodule and may be reorganized. Importing it
is allowed; depending on it is at your own risk.
"""

from __future__ import annotations

from tap_tone_pi.guided_lab import catalog, engine, validation
from tap_tone_pi.guided_lab.errors import (
    GuidedLabActionError,
    GuidedLabError,
    GuidedLabErrorCode,
    GuidedLabSessionError,
    WorkflowDefinitionError,
    raise_for_findings,
)
from tap_tone_pi.guided_lab.models import (
    GUIDED_LAB_SESSION_SCHEMA_VERSION,
    AnswerValue,
    GuidedLabSessionStatus,
    GuidedLabSessionV1,
    TransitionConditionKind,
    WorkflowAnswerKind,
    WorkflowAnswerV1,
    WorkflowDefinitionV1,
    WorkflowEvidenceReferenceV1,
    WorkflowIntentV1,
    WorkflowNodeKind,
    WorkflowNodeV1,
    WorkflowProgressV1,
    WorkflowTransitionV1,
    WorkflowValidationFindingV1,
    guided_lab_session_from_dict,
)

__all__ = [
    # Behaviour, as modules
    "catalog",
    "engine",
    "validation",
    # Vocabulary — models
    "GUIDED_LAB_SESSION_SCHEMA_VERSION",
    "AnswerValue",
    "GuidedLabSessionStatus",
    "GuidedLabSessionV1",
    "TransitionConditionKind",
    "WorkflowAnswerKind",
    "WorkflowAnswerV1",
    "WorkflowDefinitionV1",
    "WorkflowEvidenceReferenceV1",
    "WorkflowIntentV1",
    "WorkflowNodeKind",
    "WorkflowNodeV1",
    "WorkflowProgressV1",
    "WorkflowTransitionV1",
    "WorkflowValidationFindingV1",
    "guided_lab_session_from_dict",
    # Vocabulary — errors
    "GuidedLabActionError",
    "GuidedLabError",
    "GuidedLabErrorCode",
    "GuidedLabSessionError",
    "WorkflowDefinitionError",
    "raise_for_findings",
]

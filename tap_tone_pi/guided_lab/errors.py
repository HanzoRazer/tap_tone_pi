# INSTRUMENT CLASS: MEASUREMENT
"""Stable error vocabulary for the guided laboratory (DO-100).

Every guided-laboratory failure carries a stable ``GDL-*`` code so callers and
tests can assert on the code rather than on prose. Codes are grouped by the
layer that raises them:

  ``GDL-1xx``  workflow definition problems (authoring errors)
  ``GDL-2xx``  session integrity problems (wrong workflow, terminal state)
  ``GDL-3xx``  operator action problems (wrong action, bad value)
  ``GDL-4xx``  transport problems (malformed payload, unusable CLI request)

Error context is always JSON-serializable and never contains a host path.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


class GuidedLabErrorCode(str, Enum):
    """Stable identifiers for guided laboratory failures."""

    # -- Definition errors -------------------------------------------------
    DUPLICATE_NODE_ID = "GDL-101"
    MISSING_ENTRY_NODE = "GDL-102"
    UNKNOWN_TRANSITION_NODE = "GDL-103"
    UNREACHABLE_REQUIRED_NODE = "GDL-104"
    NO_COMPLETION_REACHABLE = "GDL-105"
    AMBIGUOUS_TRANSITION_SET = "GDL-106"
    UNSUPPORTED_ANSWER_KIND = "GDL-107"
    INVALID_QUESTION_CONSTRAINTS = "GDL-108"
    MISSING_SOURCE_REFERENCE = "GDL-109"
    # GDL-110 and GDL-111 cover two rejections DO-100 requires but does not
    # name a code for: malformed transition-condition payloads (DO-100 §4.6)
    # and duplicate (workflow_id, workflow_version) registry keys (§6.7).
    INVALID_TRANSITION_CONDITION = "GDL-110"
    DUPLICATE_WORKFLOW_KEY = "GDL-111"
    # GDL-112 and GDL-113 cover two more authoring defects the handoff names no
    # code for: a definition whose own identity cannot key a registry, and a
    # step whose requirement no operator action can ever satisfy. Both would
    # otherwise validate clean and fail — or deadlock — only at runtime.
    INVALID_WORKFLOW_IDENTITY = "GDL-112"
    UNSATISFIABLE_NODE_REQUIREMENT = "GDL-113"

    # -- Session errors ----------------------------------------------------
    WORKFLOW_VERSION_MISMATCH = "GDL-201"
    CURRENT_NODE_MISSING = "GDL-202"
    INVALID_STATUS_TRANSITION = "GDL-203"
    CORRUPTED_HISTORY = "GDL-204"
    SESSION_ALREADY_TERMINAL = "GDL-205"

    # -- Operator action errors --------------------------------------------
    ACTION_INVALID_FOR_NODE = "GDL-301"
    ANSWER_TYPE_MISMATCH = "GDL-302"
    ANSWER_NOT_ALLOWED = "GDL-303"
    REQUIRED_EVIDENCE_MISSING = "GDL-304"
    BACK_NAVIGATION_UNAVAILABLE = "GDL-305"
    REPLACEMENT_TARGET_NOT_ANSWERED = "GDL-306"
    EVIDENCE_REFERENCE_INVALID = "GDL-307"
    TIMESTAMP_NOT_UTC = "GDL-308"

    # -- Transport errors --------------------------------------------------
    SESSION_PAYLOAD_MALFORMED = "GDL-401"
    UNKNOWN_WORKFLOW = "GDL-402"
    INVALID_ACTION_COMBINATION = "GDL-403"
    # A goal the catalog lists but has not built yet is a different answer from
    # a workflow that does not exist. Collapsing the two would tell an operator
    # who picked a listed goal that they mistyped it.
    WORKFLOW_NOT_AVAILABLE = "GDL-404"
    # The guided laboratory could not be loaded at all. Raised by the CLI shell
    # rather than the package, so a defect here reports itself instead of
    # taking unrelated commands down with it.
    GUIDED_LAB_UNAVAILABLE = "GDL-405"
    # A failure the CLI did not anticipate. It exists so an unexpected exception
    # still leaves stderr holding one parseable JSON object rather than a Python
    # traceback — which would both break that contract and print host paths.
    # Carries the exception class name only, never its text.
    UNEXPECTED_CLI_FAILURE = "GDL-406"


class GuidedLabError(Exception):
    """Base class for every guided laboratory failure.

    Attributes:
        code: Stable ``GDL-*`` identifier.
        message: Human-readable description.
        context: JSON-serializable, path-free detail about the failure.
    """

    def __init__(
        self,
        code: GuidedLabErrorCode,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message
        self.context: dict[str, Any] = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a deterministic, path-free dictionary."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.context:
            payload["context"] = {k: self.context[k] for k in sorted(self.context)}
        return payload


class WorkflowDefinitionError(GuidedLabError):
    """A workflow definition is not internally consistent."""


class GuidedLabSessionError(GuidedLabError):
    """A session record is unusable against the supplied definition."""


class GuidedLabActionError(GuidedLabError):
    """An operator action is not permitted in the current state."""


def raise_for_findings(findings: Iterable[Any]) -> None:
    """Raise :class:`WorkflowDefinitionError` for the first finding, if any.

    The full finding list is carried in ``context['findings']`` so a caller can
    report every problem rather than only the first.
    """
    ordered = list(findings)
    if not ordered:
        return
    first = ordered[0]
    raise WorkflowDefinitionError(
        first.code,
        first.message,
        {"findings": [finding.to_dict() for finding in ordered]},
    )

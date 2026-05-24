# INSTRUMENT CLASS: DECISION SUPPORT
"""
Analyzer Attention Contract v1

Defines how analyzers direct user attention to analysis results.
This is a presentation-layer contract, not computational.

Mirrors: luthiers-toolbox/app/agentic/contracts/analyzer_attention.py

Authority metadata (PR 78C):
    Every directive must carry explicit authority metadata declaring
    what authority it claims (and does not claim). See ADR-0010.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tap_tone_pi.agentic.contracts.advisory_authority import AdvisoryAuthorityV1


class AttentionAction(str, Enum):
    """
    What the agent wants the user to do.

    Ordered by urgency (INSPECT < REVIEW < DECIDE < INTERVENE).
    """

    # Low urgency - FYI
    INSPECT = "inspect"

    # Medium urgency - needs review
    REVIEW = "review"
    COMPARE = "compare"

    # High urgency - needs decision
    DECIDE = "decide"
    CONFIRM = "confirm"

    # Critical - needs immediate action
    INTERVENE = "intervene"
    ABORT = "abort"


@dataclass(frozen=True)
class FocusTarget:
    """
    Where to direct attention.

    Targets are abstract references that the UI layer resolves
    to specific views, panels, or highlights.
    """

    target_type: str  # e.g., 'run', 'artifact', 'region', 'parameter'
    target_id: str
    highlight_region: Optional[Dict[str, Any]] = None
    context_refs: List[str] = field(default_factory=list)


def _utc_now() -> str:
    """Get current UTC time as RFC3339 string."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class AttentionDirectiveV1:
    """
    Analyzer's request for user attention.

    This contract flows from analyzer to the experience shell (UI).
    The UI decides how to render it (toast, modal, highlight, etc.).

    Example (wolf tone detected):
        AttentionDirectiveV1(
            directive_id="attn_abc123",
            action=AttentionAction.REVIEW,
            summary="Potential wolf tone at 247Hz",
            focus=FocusTarget(
                target_type="spectrum_region",
                target_id="peak_3",
                highlight_region={"freq_hz": 247, "bandwidth_hz": 10}
            ),
            urgency=0.7,
            confidence=0.85,
        )
    """

    # Identity
    directive_id: str

    # Action
    action: AttentionAction
    summary: str  # One-line summary for notification
    focus: FocusTarget

    # Optional fields with defaults
    detail: str = ""  # Extended explanation (markdown allowed)
    urgency: float = 0.5  # 0=FYI, 1=critical
    confidence: float = 0.5  # How confident in this directive

    # Evidence trail
    evidence_refs: List[str] = field(default_factory=list)
    source_tool: str = ""

    # Dismissal rules
    auto_dismiss_after_seconds: Optional[int] = None
    dismiss_on_action: bool = True
    supersedes: List[str] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=_utc_now)
    expires_at: Optional[str] = None

    # Authority metadata (PR 78C / ADR-0010)
    # Declares what authority this directive claims (and does not claim)
    authority: Optional["AdvisoryAuthorityV1"] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "directive_id": self.directive_id,
            "action": self.action.value,
            "summary": self.summary,
            "detail": self.detail,
            "focus": {
                "target_type": self.focus.target_type,
                "target_id": self.focus.target_id,
                "highlight_region": self.focus.highlight_region,
                "context_refs": list(self.focus.context_refs),
            },
            "urgency": self.urgency,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "source_tool": self.source_tool,
            "auto_dismiss_after_seconds": self.auto_dismiss_after_seconds,
            "dismiss_on_action": self.dismiss_on_action,
            "supersedes": list(self.supersedes),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "authority": self.authority.to_dict() if self.authority else None,
        }

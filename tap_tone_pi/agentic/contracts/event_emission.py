# INSTRUMENT CLASS: DECISION SUPPORT
"""
Event Emission Contract v1

Unified event vocabulary for cross-repo agent coordination.
Events flow from analyzer → agent layer → experience shell.

Mirrors: luthiers-toolbox/app/agentic/contracts/event_emission.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


class EventType(str, Enum):
    """
    Unified event vocabulary.

    Categories:
    - ANALYSIS_*: Analysis lifecycle events
    - ARTIFACT_*: Artifact creation/mutation events
    - DECISION_*: Decision point events
    - USER_*: User interaction events
    - SYSTEM_*: System/infrastructure events
    """

    # Analysis lifecycle
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"

    # Artifact events
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_VALIDATED = "artifact_validated"
    ARTIFACT_REJECTED = "artifact_rejected"
    ARTIFACT_PROMOTED = "artifact_promoted"

    # Decision events
    DECISION_REQUIRED = "decision_required"
    DECISION_MADE = "decision_made"
    DECISION_DEFERRED = "decision_deferred"

    # Attention events
    ATTENTION_REQUESTED = "attention_requested"
    ATTENTION_ACKNOWLEDGED = "attention_acknowledged"
    ATTENTION_DISMISSED = "attention_dismissed"

    # User interaction
    USER_ACTION = "user_action"
    USER_FEEDBACK = "user_feedback"
    USER_PREFERENCE_UPDATED = "user_preference_updated"

    # System events
    SYSTEM_HEALTH = "system_health"
    SYSTEM_ERROR = "system_error"
    SYSTEM_CONFIG_CHANGED = "system_config_changed"


def _utc_now() -> str:
    """Get current UTC time as RFC3339 string."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class EventSource:
    """
    Where an event originated.

    Enables cross-repo event correlation.
    """

    repo: str  # e.g., 'tap_tone_pi', 'luthiers-toolbox'
    component: str  # e.g., 'wolf_detector', 'feasibility_engine'
    version: str = ""


@dataclass
class AgentEventV1:
    """
    Cross-repo event for agent coordination.

    Events are the "nervous system" of the agentic layer.
    They enable loose coupling, observability, and privacy control.

    Example (analysis completed):
        AgentEventV1(
            event_id="evt_abc123",
            event_type=EventType.ANALYSIS_COMPLETED,
            source=EventSource(repo="tap_tone_pi", component="wolf_detector"),
            payload={"candidates_found": 3, "confidence": 0.87},
            privacy_layer=2,
            correlation_id="session_xyz",
        )
    """

    # Identity
    event_id: str
    event_type: EventType
    source: EventSource

    # Payload
    payload: Dict[str, Any] = field(default_factory=dict)

    # Privacy
    privacy_layer: int = 3  # 0=ephemeral, 5=cohort-only aggregates
    redacted_fields: List[str] = field(default_factory=list)

    # Correlation
    correlation_id: str = ""
    causation_id: str = ""
    parent_event_id: str = ""

    # Timestamps
    occurred_at: str = field(default_factory=_utc_now)
    recorded_at: str = field(default_factory=_utc_now)

    # Metadata
    tags: List[str] = field(default_factory=list)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        # Handle both enum and string event_type (for backward compat)
        event_type_value = (
            self.event_type.value
            if hasattr(self.event_type, "value")
            else self.event_type
        )

        # Handle source as either EventSource dataclass or dict
        if isinstance(self.source, dict):
            source_dict = self.source
        else:
            source_dict = {
                "repo": self.source.repo,
                "component": self.source.component,
                "version": self.source.version,
            }

        return {
            "event_id": self.event_id,
            "event_type": event_type_value,
            "source": source_dict,
            "payload": dict(self.payload) if self.payload else {},
            "privacy_layer": self.privacy_layer,
            "redacted_fields": list(self.redacted_fields)
            if self.redacted_fields
            else [],
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "parent_event_id": self.parent_event_id,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "tags": list(self.tags) if self.tags else [],
            "schema_version": self.schema_version,
        }

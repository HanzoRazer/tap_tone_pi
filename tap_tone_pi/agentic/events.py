"""
Event Emission Utilities

Convenience functions for emitting agentic events from the analyzer.
These wrap the raw contract creation with sensible defaults.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import (
    AgentEventV1,
    EventType,
    EventSource,
    AttentionDirectiveV1,
    AttentionAction,
    FocusTarget,
)


# -----------------------------------------------------------------------------
# Event ID Generation
# -----------------------------------------------------------------------------

def _generate_event_id() -> str:
    """Generate a unique event ID."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def _generate_directive_id() -> str:
    """Generate a unique directive ID."""
    return f"attn_{uuid.uuid4().hex[:12]}"


# -----------------------------------------------------------------------------
# Event Emission
# -----------------------------------------------------------------------------

def emit_event(
    event_type: EventType,
    component: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    privacy_layer: int = 3,
    correlation_id: str = "",
    parent_event_id: str = "",
    tags: Optional[List[str]] = None,
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """
    Emit an agentic event.

    Args:
        event_type: Type of event from unified vocabulary
        component: Component name (e.g., 'wolf_detector', 'phase2_pipeline')
        payload: Event-specific data
        privacy_layer: Privacy layer (0=ephemeral, 5=cohort-only)
        correlation_id: ID for correlating related events
        parent_event_id: Parent event for hierarchical correlation
        tags: Tags for filtering/aggregation
        event_log_path: Optional path to append event JSON

    Returns:
        The created event (already logged if event_log_path provided)
    """
    event = AgentEventV1(
        event_id=_generate_event_id(),
        event_type=event_type,
        source=EventSource(
            repo="tap_tone_pi",
            component=component,
            version="2.0.0",
        ),
        payload=payload or {},
        privacy_layer=privacy_layer,
        correlation_id=correlation_id,
        parent_event_id=parent_event_id,
        tags=tags or [],
    )

    if event_log_path:
        _append_event_to_log(event, event_log_path)

    return event


def _append_event_to_log(event: AgentEventV1, log_path: Path) -> None:
    """Append event to JSONL log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict()) + "\n")


# -----------------------------------------------------------------------------
# JSONL Event Writer
# -----------------------------------------------------------------------------

class JsonlEventWriter:
    """Append-only JSONL writer for AgentEventV1 events.

    One writer per session.  Creates the file lazily on first write.
    Single-process assumption — no locking.

    Usage:
        writer = JsonlEventWriter(Path(session_dir) / "events.jsonl")
        writer.write(event)
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._created = False

    def write(self, event: AgentEventV1) -> None:
        """Append a single event as one JSONL line."""
        if not self._created:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._created = True
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")


# -----------------------------------------------------------------------------
# Convenience Emitters
# -----------------------------------------------------------------------------

def emit_analysis_started(
    component: str,
    run_id: str,
    *,
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ANALYSIS_STARTED event."""
    return emit_event(
        EventType.ANALYSIS_STARTED,
        component,
        payload={"run_id": run_id},
        correlation_id=correlation_id or run_id,
        event_log_path=event_log_path,
    )


def emit_analysis_completed(
    component: str,
    run_id: str,
    *,
    artifacts_created: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ANALYSIS_COMPLETED event."""
    return emit_event(
        EventType.ANALYSIS_COMPLETED,
        component,
        payload={
            "run_id": run_id,
            "artifacts_created": artifacts_created or [],
            "metrics": metrics or {},
        },
        correlation_id=correlation_id or run_id,
        event_log_path=event_log_path,
    )


def emit_analysis_failed(
    component: str,
    run_id: str,
    error: str,
    *,
    error_type: str = "",
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ANALYSIS_FAILED event."""
    return emit_event(
        EventType.ANALYSIS_FAILED,
        component,
        payload={
            "run_id": run_id,
            "error": error,
            "error_type": error_type,
        },
        correlation_id=correlation_id or run_id,
        tags=["error"],
        event_log_path=event_log_path,
    )


def emit_artifact_created(
    component: str,
    run_id: str,
    artifact_name: str,
    artifact_type: str,
    *,
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ARTIFACT_CREATED event."""
    return emit_event(
        EventType.ARTIFACT_CREATED,
        component,
        payload={
            "run_id": run_id,
            "artifact_name": artifact_name,
            "artifact_type": artifact_type,
        },
        correlation_id=correlation_id or run_id,
        event_log_path=event_log_path,
    )


def emit_decision_required(
    component: str,
    run_id: str,
    decision_type: str,
    options: Optional[List[str]] = None,
    *,
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit DECISION_REQUIRED event."""
    return emit_event(
        EventType.DECISION_REQUIRED,
        component,
        payload={
            "run_id": run_id,
            "decision_type": decision_type,
            "options": options or [],
        },
        correlation_id=correlation_id or run_id,
        event_log_path=event_log_path,
    )


def emit_attention_requested(
    component: str,
    directive: AttentionDirectiveV1,
    *,
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ATTENTION_REQUESTED event with embedded directive."""
    return emit_event(
        EventType.ATTENTION_REQUESTED,
        component,
        payload={"directive": directive.to_dict()},
        correlation_id=correlation_id,
        event_log_path=event_log_path,
    )


def emit_attention_acknowledged(
    component: str,
    directive_id: str,
    *,
    action_taken: str = "",
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ATTENTION_ACKNOWLEDGED event when user accepts/acts on a directive."""
    return emit_event(
        EventType.ATTENTION_ACKNOWLEDGED,
        component,
        payload={
            "directive_id": directive_id,
            "action_taken": action_taken,
        },
        correlation_id=correlation_id,
        event_log_path=event_log_path,
    )


def emit_attention_dismissed(
    component: str,
    directive_id: str,
    *,
    reason: str = "",
    correlation_id: str = "",
    event_log_path: Optional[Path] = None,
) -> AgentEventV1:
    """Emit ATTENTION_DISMISSED event when user dismisses/rejects a directive."""
    return emit_event(
        EventType.ATTENTION_DISMISSED,
        component,
        payload={
            "directive_id": directive_id,
            "reason": reason,
        },
        correlation_id=correlation_id,
        event_log_path=event_log_path,
    )


# -----------------------------------------------------------------------------
# Attention Directive Helpers
# -----------------------------------------------------------------------------

def create_wolf_tone_directive(
    freq_hz: float,
    confidence: float,
    peak_id: str,
    *,
    bundle_sha256: str = "",
) -> AttentionDirectiveV1:
    """
    Create attention directive for wolf tone detection.

    Args:
        freq_hz: Detected frequency in Hz
        confidence: Detection confidence (0-1)
        peak_id: Peak identifier in the analysis
        bundle_sha256: Bundle hash for evidence reference

    Returns:
        Attention directive for UI rendering
    """
    evidence_refs = []
    if bundle_sha256:
        evidence_refs.append(f"wolf_candidates_v1:{bundle_sha256}:{peak_id}")

    return AttentionDirectiveV1(
        directive_id=_generate_directive_id(),
        action=AttentionAction.REVIEW,
        summary=f"Potential wolf tone at {freq_hz:.0f}Hz",
        detail=(
            f"The analyzer detected a potential wolf tone at {freq_hz:.1f}Hz "
            f"with {confidence*100:.0f}% confidence. This frequency may cause "
            f"tonal issues. Consider adjusting bracing or soundboard thickness."
        ),
        focus=FocusTarget(
            target_type="spectrum_region",
            target_id=peak_id,
            highlight_region={
                "freq_hz": freq_hz,
                "bandwidth_hz": 10,
            },
        ),
        urgency=0.7 if confidence > 0.8 else 0.5,
        confidence=confidence,
        evidence_refs=evidence_refs,
        source_tool="tap_tone_wolf_detector",
    )


def create_mode_identified_directive(
    mode_name: str,
    freq_hz: float,
    mode_id: str,
    *,
    expected_range: Optional[tuple] = None,
) -> AttentionDirectiveV1:
    """
    Create attention directive for mode identification.

    Args:
        mode_name: Name of the mode (e.g., "T(1,1)", "Cross-dipole")
        freq_hz: Detected frequency
        mode_id: Mode identifier
        expected_range: Optional (min, max) expected range for this mode

    Returns:
        Attention directive for UI rendering
    """
    detail = f"Identified {mode_name} mode at {freq_hz:.1f}Hz."

    urgency = 0.3  # Low urgency by default (informational)
    if expected_range:
        lo, hi = expected_range
        if freq_hz < lo or freq_hz > hi:
            detail += f" Note: Outside typical range ({lo}-{hi}Hz)."
            urgency = 0.6

    return AttentionDirectiveV1(
        directive_id=_generate_directive_id(),
        action=AttentionAction.INSPECT,
        summary=f"{mode_name} at {freq_hz:.0f}Hz",
        detail=detail,
        focus=FocusTarget(
            target_type="mode",
            target_id=mode_id,
            highlight_region={"freq_hz": freq_hz},
        ),
        urgency=urgency,
        confidence=0.8,
        source_tool="tap_tone_analyzer",
    )

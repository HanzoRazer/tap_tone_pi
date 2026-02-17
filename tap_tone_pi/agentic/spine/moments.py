# app/agentic/spine/moments.py
"""
Moment Detection Engine — Reference Implementation

Detects named patterns (moments) from AgentEventV1 event streams.
This is a conservative, dependency-light implementation designed to:
1. Pass the test suite
2. Work correctly in shadow mode
3. Provide a bootstrap for CI

For full specification, see: docs/EVENT_MOMENTS_CATALOG_V1.md
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


MomentName = str

# Type alias for detector return
DetectorResult = Optional[Tuple[MomentName, float, List[str]]]


PRIORITY: Dict[MomentName, int] = {
    "ERROR": 1,
    "OVERLOAD": 2,
    "TRUST_EROSION": 3,
    "DECISION_REQUIRED": 4,
    "FINDING": 5,
    "CONFIDENCE_CLIMB": 6,
    "HESITATION": 7,
    "FIRST_SIGNAL": 8,
}


def _get(e: Any, key: str, default=None):
    if isinstance(e, dict):
        return e.get(key, default)
    return getattr(e, key, default)


def _payload(e: Any) -> dict:
    p = _get(e, "payload", {}) or {}
    return p if isinstance(p, dict) else {}


def _eid(e: Any) -> str:
    return str(_get(e, "event_id", ""))


# --- Individual Detector Functions ---


def _detect_error(evs: List[Any]) -> DetectorResult:
    """Detect ERROR moment from system/analysis failures."""
    for e in evs:
        if _get(e, "event_type") in ("analysis_failed", "system_error"):
            return ("ERROR", 0.95, [_eid(e)])
    return None


def _detect_overload(evs: List[Any]) -> DetectorResult:
    """Detect OVERLOAD moment from user feedback, undo spikes, or rapid toggles."""
    # Path 1: Explicit too_much feedback
    for e in evs:
        if _get(e, "event_type") == "user_feedback":
            if _payload(e).get("feedback") == "too_much":
                return ("OVERLOAD", 0.9, [_eid(e)])

    # Path 2: Undo spike heuristic (3+ undos)
    undo_ids = [
        _eid(e)
        for e in evs
        if _get(e, "event_type") == "user_action"
        and _payload(e).get("action") == "undo"
    ]
    if len(undo_ids) >= 3:
        return ("OVERLOAD", 0.75, undo_ids[:3])

    # Path 3: Rapid open/close cycles (4+ toggles)
    toggles = [
        _eid(e)
        for e in evs
        if _get(e, "event_type") in ("tool_rendered", "tool_closed")
    ]
    if len(toggles) >= 4:
        return ("OVERLOAD", 0.65, toggles[:4])

    return None


def _detect_decision_required(evs: List[Any]) -> DetectorResult:
    """Detect DECISION_REQUIRED moment from explicit decision events."""
    for e in evs:
        if _get(e, "event_type") == "decision_required":
            return ("DECISION_REQUIRED", 0.9, [_eid(e)])
    return None


def _detect_finding(evs: List[Any]) -> DetectorResult:
    """Detect FINDING moment from attention + high-confidence artifacts."""
    attention_e = next(
        (e for e in evs if _get(e, "event_type") == "attention_requested"), None
    )

    high_conf_artifact = None
    for e in evs:
        if _get(e, "event_type") == "artifact_created":
            p = _payload(e)
            if (
                p.get("schema") == "wolf_candidates_v1"
                and float(p.get("confidence_max", 0.0)) >= 0.6
            ):
                high_conf_artifact = e
                break

    if attention_e and high_conf_artifact:
        return ("FINDING", 0.85, [_eid(attention_e)])
    if high_conf_artifact:
        return ("FINDING", 0.7, [_eid(high_conf_artifact)])
    return None


def _detect_hesitation(evs: List[Any]) -> DetectorResult:
    """Detect HESITATION moment from idle timeout or repeated hovers."""
    # Suppress hesitation if parameter change happened
    has_param_change = any(
        _get(e, "event_type") == "user_action"
        and _payload(e).get("action") == "parameter_changed"
        for e in evs
    )
    if has_param_change:
        return None

    # Path 1: idle_timeout event
    idle_e = next((e for e in evs if _get(e, "event_type") == "idle_timeout"), None)
    if idle_e:
        return ("HESITATION", 0.8, [_eid(idle_e)])

    # Path 2: Repeated hovers (2+)
    hover_events = [
        e
        for e in evs
        if _get(e, "event_type") == "user_action"
        and _payload(e).get("action") == "hover"
    ]
    if len(hover_events) >= 2:
        return ("HESITATION", 0.65, [_eid(hover_events[0]), _eid(hover_events[1])])

    return None


def _detect_first_signal(evs: List[Any]) -> DetectorResult:
    """Detect FIRST_SIGNAL moment from view_rendered or analysis_completed."""
    # Prefer view_rendered
    view_e = next(
        (
            e
            for e in evs
            if _get(e, "event_type") == "user_action"
            and _payload(e).get("action") == "view_rendered"
        ),
        None,
    )
    if view_e:
        return ("FIRST_SIGNAL", 0.75, [_eid(view_e)])

    # Fallback: analysis_completed
    comp_e = next(
        (e for e in evs if _get(e, "event_type") == "analysis_completed"), None
    )
    if comp_e:
        return ("FIRST_SIGNAL", 0.65, [_eid(comp_e)])

    return None


def _collect_attention_stats(
    evs: List[Any],
) -> Tuple[int, int, int, List[Any], List[Any]]:
    """Collect attention statistics: (shown, ack, dismiss, ack_events, dismiss_events)."""
    shown = [e for e in evs if _get(e, "event_type") == "attention_requested"]
    ack = [e for e in evs if _get(e, "event_type") == "attention_acknowledged"]
    dismiss = [e for e in evs if _get(e, "event_type") == "attention_dismissed"]
    return len(shown), len(ack), len(dismiss), ack, dismiss


def _detect_confidence_climb(
    evs: List[Any], stats: Tuple[int, int, int, List[Any], List[Any]]
) -> DetectorResult:
    """Detect CONFIDENCE_CLIMB from >=80% acknowledgment rate over >=5 outcomes."""
    total_shown, total_ack, total_dismiss, ack_events, _ = stats
    total_outcomes = total_ack + total_dismiss

    if total_shown >= 5 and total_outcomes >= 5:
        ack_rate = total_ack / total_outcomes
        if ack_rate >= 0.8:
            trigger_ids = [_eid(e) for e in ack_events[:5]]
            return ("CONFIDENCE_CLIMB", round(min(ack_rate, 0.95), 2), trigger_ids)
    return None


def _detect_trust_erosion(
    evs: List[Any], stats: Tuple[int, int, int, List[Any], List[Any]]
) -> DetectorResult:
    """Detect TRUST_EROSION from >=60% dismissal rate or 3+ idle timeouts."""
    total_shown, total_ack, total_dismiss, _, dismiss_events = stats
    total_outcomes = total_ack + total_dismiss

    # Path A: High dismissal rate
    if total_shown >= 5 and total_outcomes >= 5:
        dismiss_rate = total_dismiss / total_outcomes
        if dismiss_rate >= 0.6:
            trigger_ids = [_eid(e) for e in dismiss_events[:5]]
            return ("TRUST_EROSION", round(min(dismiss_rate, 0.95), 2), trigger_ids)

    # Path B: 3+ idle timeouts
    idle_events = [e for e in evs if _get(e, "event_type") == "idle_timeout"]
    if len(idle_events) >= 3:
        return ("TRUST_EROSION", 0.7, [_eid(e) for e in idle_events[:3]])

    return None


# --- Main Detection Entry Point ---


def detect_moments(events: List[Any]) -> List[dict]:
    """
    Detect moments from a list of AgentEventV1-like dicts/objects.

    Output: list of dicts
      { "moment": str, "confidence": float, "trigger_events": [event_id, ...] }

    Priority rule: if multiple moments detected, only highest priority is returned.
    """
    if not events:
        return []

    # Sort by occurred_at if present, otherwise keep order
    evs = sorted(events, key=lambda e: str(_get(e, "occurred_at", "")))

    detected: List[Tuple[MomentName, float, List[str]]] = []

    # Run priority-ordered detectors (early return semantics)
    if result := _detect_error(evs):
        detected.append(result)

    if not any(m[0] == "ERROR" for m in detected):
        if result := _detect_overload(evs):
            detected.append(result)

    if not any(m[0] in ("ERROR", "OVERLOAD") for m in detected):
        if result := _detect_decision_required(evs):
            detected.append(result)

    if not any(m[0] in ("ERROR", "OVERLOAD", "DECISION_REQUIRED") for m in detected):
        if result := _detect_finding(evs):
            detected.append(result)

    if not any(
        m[0] in ("ERROR", "OVERLOAD", "DECISION_REQUIRED", "FINDING") for m in detected
    ):
        if result := _detect_hesitation(evs):
            detected.append(result)

    if not detected:
        if result := _detect_first_signal(evs):
            detected.append(result)

    # Attention-based detectors (can coexist, priority handled at end)
    stats = _collect_attention_stats(evs)
    if result := _detect_confidence_climb(evs, stats):
        detected.append(result)

    if not any(m[0] == "TRUST_EROSION" for m in detected):
        if result := _detect_trust_erosion(evs, stats):
            detected.append(result)

    if not detected:
        return []

    # Apply priority suppression: keep only the single highest-priority moment
    detected.sort(key=lambda x: PRIORITY.get(x[0], 999))
    best = detected[0]
    return [
        {"moment": best[0], "confidence": float(best[1]), "trigger_events": best[2]}
    ]

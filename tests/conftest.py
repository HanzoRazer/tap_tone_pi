# tests/conftest.py
"""
Shared fixtures for agentic contract + spine tests.

These are designed to work in BOTH repos:
- luthiers-toolbox (pydantic models)
- tap_tone_pi (dataclasses)

They provide sample AgentEventV1 payloads that mirror the Markdown test cases.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

# ---------------------------------------------------------------------------
# Preflight: catch stale/missing editable install early with a clear message.
# Without this, subprocess-based tests fail with cryptic ModuleNotFoundError
# inside scripts, and deferred imports in _run_shadow_hook silently no-op.
# ---------------------------------------------------------------------------
try:
    import tap_tone_pi  # noqa: F401
except ImportError:
    pytest.exit(
        "tap_tone_pi is not importable. Run:  pip install -e .\n"
        "(Editable install required for subprocess-based and spine tests.)",
        returncode=4,
    )

# ---------------------------------------------------------------------------
# Sounddevice/PortAudio availability check for tests that need audio hardware
# ---------------------------------------------------------------------------
try:
    import sounddevice as _sd  # noqa: F401

    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    # ImportError: sounddevice not installed
    # OSError: sounddevice installed but PortAudio library not found
    HAS_SOUNDDEVICE = False

requires_sounddevice = pytest.mark.skipif(
    not HAS_SOUNDDEVICE, reason="sounddevice/PortAudio not available"
)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def mk_source(
    repo: str, component: str = "test_component", version: str = "1.0.0"
) -> dict:
    return {"repo": repo, "component": component, "version": version}


def mk_event(
    *,
    event_type: str,
    repo: str = "tap_tone_pi",
    component: str = "wolf_detector",
    occurred_at: str | None = None,
    payload: dict | None = None,
    privacy_layer: int = 2,
    schema_version: str = "1.0.0",
    event_id: str | None = None,
) -> dict:
    return {
        "event_id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "source": mk_source(repo=repo, component=component, version="2.0.0"),
        "payload": payload or {},
        "privacy_layer": privacy_layer,
        "occurred_at": occurred_at or iso_now(),
        "schema_version": schema_version,
    }


# --- Moment-case fixtures (mirror markdown examples) ---


@pytest.fixture
def ev_analysis_started():
    return mk_event(event_type="analysis_started", occurred_at="2026-02-06T12:00:01Z")


@pytest.fixture
def ev_analysis_completed_basic():
    return mk_event(
        event_type="analysis_completed",
        occurred_at="2026-02-06T12:00:30Z",
        payload={"artifacts_created": ["ods_snapshot_v1"]},
    )


@pytest.fixture
def ev_view_rendered_spectrum():
    # If you add a dedicated EventType VIEW_RENDERED later, update this fixture accordingly.
    # For now, we treat it as USER_ACTION with structured payload.
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:12Z",
        payload={"action": "view_rendered", "panel_id": "spectrum", "trace_id": "main"},
    )


@pytest.fixture
def ev_idle_timeout_9s():
    return mk_event(
        event_type="idle_timeout",
        occurred_at="2026-02-06T12:00:14Z",
        payload={"idle_seconds": 9},
    )


@pytest.fixture
def ev_hover_1():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:05Z",
        payload={"action": "hover", "target": "trace_panel", "duration_ms": 3200},
    )


@pytest.fixture
def ev_hover_2():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:09Z",
        payload={"action": "hover", "target": "trace_panel", "duration_ms": 3400},
    )


@pytest.fixture
def ev_parameter_changed():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:07Z",
        payload={"action": "parameter_changed", "param": "brightness", "value": 0.6},
    )


@pytest.fixture
def ev_user_feedback_too_much():
    return mk_event(
        event_type="user_feedback",
        occurred_at="2026-02-06T12:00:20Z",
        payload={"feedback": "too_much"},
    )


@pytest.fixture
def ev_undo_1():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:21Z",
        payload={"action": "undo"},
    )


@pytest.fixture
def ev_undo_2():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:22Z",
        payload={"action": "undo"},
    )


@pytest.fixture
def ev_undo_3():
    return mk_event(
        event_type="user_action",
        occurred_at="2026-02-06T12:00:23Z",
        payload={"action": "undo"},
    )


@pytest.fixture
def ev_tool_rendered():
    return mk_event(
        event_type="tool_rendered",
        occurred_at="2026-02-06T12:00:05Z",
        payload={"tool_id": "tap_tone_analyzer"},
    )


@pytest.fixture
def ev_tool_closed():
    return mk_event(
        event_type="tool_closed",
        occurred_at="2026-02-06T12:00:07Z",
        payload={"tool_id": "tap_tone_analyzer"},
    )


@pytest.fixture
def ev_decision_required():
    return mk_event(
        event_type="decision_required",
        occurred_at="2026-02-06T12:00:40Z",
        payload={"decision_id": "d1", "options": ["A", "B"]},
    )


@pytest.fixture
def ev_artifact_created_high_conf():
    return mk_event(
        event_type="artifact_created",
        occurred_at="2026-02-06T12:00:35Z",
        payload={"schema": "wolf_candidates_v1", "confidence_max": 0.87},
    )


@pytest.fixture
def ev_artifact_created_low_conf():
    return mk_event(
        event_type="artifact_created",
        occurred_at="2026-02-06T12:00:35Z",
        payload={"schema": "wolf_candidates_v1", "confidence_max": 0.42},
    )


@pytest.fixture
def ev_attention_requested():
    return mk_event(
        event_type="attention_requested",
        occurred_at="2026-02-06T12:00:36Z",
        payload={"directive_id": "attn_1"},
    )


@pytest.fixture
def ev_analysis_failed():
    return mk_event(
        event_type="analysis_failed",
        occurred_at="2026-02-06T12:00:25Z",
        payload={"message": "file not found"},
    )


@pytest.fixture
def ev_system_error():
    return mk_event(
        event_type="system_error",
        occurred_at="2026-02-06T12:00:25Z",
        payload={"code": "E_TIMEOUT"},
    )


# --- Directive outcome fixtures (PR #10: MOM-004/005) ---


def _mk_attention_requested(n: int, base_ts: int = 0) -> list:
    """Generate n attention_requested events with sequential timestamps."""
    return [
        mk_event(
            event_type="attention_requested",
            occurred_at=f"2026-02-06T12:{base_ts + i:02d}:00Z",
            payload={"directive_id": f"attn_{i:03d}"},
        )
        for i in range(n)
    ]


def _mk_attention_acknowledged(n: int, base_ts: int = 20) -> list:
    """Generate n attention_acknowledged events."""
    return [
        mk_event(
            event_type="attention_acknowledged",
            occurred_at=f"2026-02-06T12:{base_ts + i:02d}:00Z",
            payload={"directive_id": f"attn_{i:03d}", "action_taken": "applied"},
        )
        for i in range(n)
    ]


def _mk_attention_dismissed(n: int, base_ts: int = 20) -> list:
    """Generate n attention_dismissed events."""
    return [
        mk_event(
            event_type="attention_dismissed",
            occurred_at=f"2026-02-06T12:{base_ts + i:02d}:00Z",
            payload={"directive_id": f"attn_{i:03d}", "reason": "not relevant"},
        )
        for i in range(n)
    ]


@pytest.fixture
def ev_confidence_climb_stream():
    """5 shown + 5 acknowledged (100% ack rate) → CONFIDENCE_CLIMB."""
    return _mk_attention_requested(5) + _mk_attention_acknowledged(5)


@pytest.fixture
def ev_trust_erosion_stream():
    """5 shown + 4 dismissed + 1 ack (80% dismiss rate) → TRUST_EROSION."""
    return (
        _mk_attention_requested(5)
        + _mk_attention_dismissed(4)
        + _mk_attention_acknowledged(1, base_ts=30)
    )


@pytest.fixture
def ev_mixed_below_threshold():
    """5 shown + 3 ack + 2 dismiss (60% ack, 40% dismiss) → neither moment."""
    return (
        _mk_attention_requested(5)
        + _mk_attention_acknowledged(3)
        + _mk_attention_dismissed(2, base_ts=30)
    )


@pytest.fixture
def ev_trust_erosion_idle_path():
    """3 idle_timeout events → TRUST_EROSION via Path B."""
    return [
        mk_event(
            event_type="idle_timeout",
            occurred_at=f"2026-02-06T12:0{i}:00Z",
            payload={"idle_seconds": 10},
        )
        for i in range(3)
    ]


@pytest.fixture
def ev_too_few_shown():
    """Only 3 shown + 3 ack → below 5-directive threshold, no moment."""
    return _mk_attention_requested(3) + _mk_attention_acknowledged(3)

# tap_tone_pi/agentic/spine/__init__.py
"""
Agentic Spine — Reference Implementation (tap_tone_pi mirror)

This module contains the core agentic orchestration logic:
- moments.py: Moment detection from event streams
- policy.py: Decision policy engine
- uwsm_update.py: Deterministic UWSM preference updates
- replay.py: Shadow-mode replay harness

These implementations are intentionally conservative and designed to:
1. Pass the test suite in tests/test_moments_engine_v1.py and tests/test_policy_engine_v1.py
2. Work correctly in shadow mode (M0)
3. Provide reasonable defaults for M1/M2

For full specifications, see:
- docs/EVENT_MOMENTS_CATALOG_V1.md
- docs/AGENT_DECISION_POLICY_V1.md
- docs/UWSM_UPDATE_RULES_V1.md
"""

from .moments import detect_moments
from .policy import decide
from .uwsm_update import apply_uwsm_updates, ensure_uwsm
from .uwsm_store import (
    get_uwsm_path,
    load_uwsm_state,
    apply_uwsm_decay,
    save_uwsm_state,
)
from .replay import run_shadow_replay, load_events, ReplayConfig
from .shadow_record import (
    write_shadow_record,
    load_latest_shadow_record,
    _validate_shadow_record_v1,
)
from .view_adapter import ViewAdapter, NullViewAdapter, dispatch_commands

__all__ = [
    "detect_moments",
    "decide",
    "apply_uwsm_updates",
    "ensure_uwsm",
    "get_uwsm_path",
    "load_uwsm_state",
    "apply_uwsm_decay",
    "save_uwsm_state",
    "run_shadow_replay",
    "load_events",
    "ReplayConfig",
    "write_shadow_record",
    "load_latest_shadow_record",
    "ViewAdapter",
    "NullViewAdapter",
    "dispatch_commands",
]

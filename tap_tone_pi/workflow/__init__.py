"""Workflow module for tap-tone-pi operator loop.

Provides the deterministic operator loop:
    PREFLIGHT -> CAPTURE -> ANALYZE -> GATE -> ACCEPT/RETRY

This module enforces quality gates and prevents silent advancement
past failed measurements.
"""
from __future__ import annotations

from tap_tone_pi.workflow.operator_loop import (
    LoopState,
    OperatorLoop,
    LoopResult,
)
from tap_tone_pi.workflow.attempt import (
    Attempt,
    AttemptStatus,
    AttemptStore,
)

__all__ = [
    "LoopState",
    "OperatorLoop",
    "LoopResult",
    "Attempt",
    "AttemptStatus",
    "AttemptStore",
]

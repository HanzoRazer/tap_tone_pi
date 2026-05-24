# INSTRUMENT CLASS: MEASUREMENT
"""Workflow module for tap-tone-pi operator loop.

Provides the deterministic operator loop:
    PREFLIGHT -> CAPTURE -> ANALYZE -> GATE -> ACCEPT/RETRY

This module enforces quality gates and prevents silent advancement
past failed measurements.

Also provides measurement workflow contracts that define procedural
requirements for legitimate measurement sessions.
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
from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    FixtureRequirements,
    EnvironmentRequirements,
)
from tap_tone_pi.workflow.registry import (
    BUILTIN_WORKFLOWS,
    get_workflow,
    list_workflow_ids,
    validate_registry,
    FREE_PLATE_TAP_V1,
    BRACED_TOP_TAP_V1,
    CLOSED_BOX_TAP_V1,
    BACK_TAP_V1,
    AIR_RESONANCE_CHECK_V1,
    CALIBRATION_PASS_V1,
)

__all__ = [
    # Operator loop
    "LoopState",
    "OperatorLoop",
    "LoopResult",
    "Attempt",
    "AttemptStatus",
    "AttemptStore",
    # Workflow contracts
    "MeasurementWorkflowContractV1",
    "FixtureRequirements",
    "EnvironmentRequirements",
    "BUILTIN_WORKFLOWS",
    "get_workflow",
    "list_workflow_ids",
    "validate_registry",
    # Built-in workflows
    "FREE_PLATE_TAP_V1",
    "BRACED_TOP_TAP_V1",
    "CLOSED_BOX_TAP_V1",
    "BACK_TAP_V1",
    "AIR_RESONANCE_CHECK_V1",
    "CALIBRATION_PASS_V1",
]

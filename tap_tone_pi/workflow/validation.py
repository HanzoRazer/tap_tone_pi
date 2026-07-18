# INSTRUMENT CLASS: MEASUREMENT
"""Workflow execution evaluation helpers (Dev Order 86).

Evaluates procedural completeness of a measurement workflow by comparing
actual execution against the workflow contract requirements.

This module is MEASUREMENT class — it derives observational facts about
workflow execution, not quality judgments or recommendations.
"""

from __future__ import annotations

from datetime import datetime

from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    WorkflowExecutionEvidenceV1,
    WorkflowExecutionState,
    CalibrationState,
)


def evaluate_workflow_execution(
    contract: MeasurementWorkflowContractV1,
    *,
    repetitions_completed: int,
    repetitions_rejected: int = 0,
    calibration_state: str | CalibrationState,
    capture_geometry_present: bool = False,
    started_at_utc: str | None = None,
    completed_at_utc: str | None = None,
) -> WorkflowExecutionEvidenceV1:
    """Evaluate workflow execution against contract requirements.

    Derives observational execution evidence from the contract and
    actual captured state. Does NOT issue recommendations or judgments.

    Args:
        contract: The workflow contract defining requirements
        repetitions_completed: Number of valid repetitions captured
        repetitions_rejected: Number of rejected capture attempts
        calibration_state: Current calibration validity state
        capture_geometry_present: Whether capture geometry metadata exists
        started_at_utc: ISO timestamp when workflow started
        completed_at_utc: ISO timestamp when workflow completed

    Returns:
        WorkflowExecutionEvidenceV1 with derived execution state
    """
    # Normalize calibration state to string
    if isinstance(calibration_state, CalibrationState):
        cal_state_str = calibration_state.value
    else:
        cal_state_str = str(calibration_state)

    # Evaluate repetition completion
    required_reps = contract.required_repetitions
    reps_completed = required_repetitions_completed = (
        repetitions_completed >= required_reps
    )

    # Evaluate calibration requirement
    calibration_ok = True
    if contract.requires_calibration:
        calibration_ok = cal_state_str in (
            CalibrationState.VALID.value,
            CalibrationState.NOT_REQUIRED.value,
        )

    # Derive execution state
    if repetitions_completed == 0 and repetitions_rejected == 0:
        execution_state = WorkflowExecutionState.NOT_STARTED.value
    elif reps_completed and calibration_ok:
        execution_state = WorkflowExecutionState.COMPLETE.value
    elif repetitions_completed > 0:
        # Some progress made
        if cal_state_str == CalibrationState.FAILED.value:
            execution_state = WorkflowExecutionState.INCOMPLETE.value
        else:
            execution_state = WorkflowExecutionState.PARTIAL.value
    else:
        execution_state = WorkflowExecutionState.INCOMPLETE.value

    # Derive workflow completeness
    workflow_complete = (
        execution_state == WorkflowExecutionState.COMPLETE.value
        and required_repetitions_completed
        and calibration_ok
    )

    # Calculate duration if both timestamps present
    duration_seconds = None
    if started_at_utc and completed_at_utc:
        try:
            start = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at_utc.replace("Z", "+00:00"))
            duration_seconds = (end - start).total_seconds()
        except (ValueError, TypeError):
            pass

    return WorkflowExecutionEvidenceV1(
        workflow_id=contract.workflow_id,
        repetitions_completed=repetitions_completed,
        repetitions_rejected=repetitions_rejected,
        execution_state=execution_state,
        calibration_state=cal_state_str,
        capture_geometry_present=capture_geometry_present,
        workflow_complete=workflow_complete,
        required_repetitions_completed=required_repetitions_completed,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        duration_seconds=duration_seconds,
    )


def derive_calibration_state(
    *,
    calibration_exists: bool,
    calibration_valid: bool | None = None,
    calibration_age_days: float | None = None,
    max_age_days: int = 30,
    calibration_failed: bool = False,
    calibration_required: bool = True,
) -> CalibrationState:
    """Derive calibration state from observed conditions.

    Args:
        calibration_exists: Whether any calibration data exists
        calibration_valid: Whether calibration passed validation (if known)
        calibration_age_days: Age of calibration in days (if known)
        max_age_days: Maximum allowed calibration age
        calibration_failed: Whether calibration attempt explicitly failed
        calibration_required: Whether workflow requires calibration

    Returns:
        CalibrationState enum value
    """
    if not calibration_required:
        return CalibrationState.NOT_REQUIRED

    if calibration_failed:
        return CalibrationState.FAILED

    if not calibration_exists:
        return CalibrationState.MISSING

    # Calibration exists — check validity
    if calibration_valid is False:
        return CalibrationState.FAILED

    if calibration_age_days is not None and calibration_age_days > max_age_days:
        return CalibrationState.STALE

    return CalibrationState.VALID


__all__ = [
    "evaluate_workflow_execution",
    "derive_calibration_state",
]

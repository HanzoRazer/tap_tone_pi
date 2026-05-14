"""
tap_tone_pi/calibration/gate.py

# INSTRUMENT CLASS: MEASUREMENT
# Part of the measurement quality enforcement system.
# See docs/ADR-0009-advisory-boundary.md

Calibration enforcement gate — refuses to start a capture session when
the measurement chain is uncalibrated.

WHY THIS EXISTS:
    calibration/session_context.py records the calibration state INTO the
    session JSON, but it never blocked uncalibrated sessions from starting.
    Recording "uncalibrated" in the provenance is better than nothing, but
    it allows the operator to run 35-point grid sessions whose data cannot
    be compared to any other session's data.

    This module provides the enforcement that was previously missing:
    a hard gate that refuses uncalibrated sessions, with a --force-uncalibrated
    override for development/synthetic use and a stale-warning that lets the
    operator decide whether to recalibrate or proceed with a warning.

POLICY (from docs/hardware/TTP_HARDWARE_STACK.md):
    - VALID (≤ 30 days): session starts normally
    - STALE (> 30 days): operator prompted to recalibrate; may proceed with --force
    - UNCALIBRATED: session blocked unless --force-uncalibrated; warning in JSON
    - FAILED: session always blocked; calibration must be rerun

USAGE:
    from tap_tone_pi.calibration.gate import enforce_calibration_gate, CalibrationGateResult

    result = enforce_calibration_gate(device_index=0)
    if not result.allowed:
        print(result.message)
        sys.exit(1)
    if result.warning:
        print(result.warning)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tap_tone_pi.calibration.storage import (
    CalibrationStatus,
    get_calibration_status,
    load_calibration,
    is_calibration_stale,
    CALIBRATION_EXPIRY_DAYS,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CalibrationGateResult:
    """Result of calibration gate check."""

    allowed: bool
    status: str  # CalibrationStatus.value

    # Human-readable messages
    message: str = ""          # Shown when blocked or warned
    warning: str = ""          # Non-blocking advisory shown to operator

    # Machine-readable flags
    is_stale: bool = False
    is_uncalibrated: bool = False
    is_failed: bool = False

    # For embedding in session_state.metadata
    gate_verdict: str = "allowed"   # "allowed" | "warned" | "blocked"

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "gate_verdict": self.gate_verdict,
            "is_stale": self.is_stale,
            "is_uncalibrated": self.is_uncalibrated,
        }


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

def enforce_calibration_gate(
    device_index: int,
    *,
    allow_stale: bool = False,
    allow_uncalibrated: bool = False,
) -> CalibrationGateResult:
    """
    Check calibration status and return whether a session is permitted.

    Args:
        device_index: Audio device index to check
        allow_stale: If True, treat STALE as allowed (with warning).
                     Maps to CLI --force flag.
        allow_uncalibrated: If True, treat UNCALIBRATED as allowed (with warning).
                            Maps to CLI --force-uncalibrated flag.
                            Only for development/synthetic mode — never for
                            real measurements intended for Production Shop.

    Returns:
        CalibrationGateResult with .allowed indicating whether to proceed.
    """
    status = get_calibration_status(device_index)
    cal_data = load_calibration(device_index)

    # --- VALID ---
    if status == CalibrationStatus.VALID:
        cal_date = cal_data.calibrated_at if cal_data else "unknown"
        return CalibrationGateResult(
            allowed=True,
            status=status.value,
            message=f"Calibration valid (device {device_index}, dated {cal_date}).",
            gate_verdict="allowed",
        )

    # --- STALE ---
    if status == CalibrationStatus.STALE:
        age_days = _cal_age_days(cal_data)
        stale_msg = (
            f"Calibration is {age_days} days old (limit: {CALIBRATION_EXPIRY_DAYS} days). "
            f"Measurements may drift from earlier sessions. "
            f"Run 'ttp calibrate tone' to recalibrate."
        )
        if allow_stale:
            return CalibrationGateResult(
                allowed=True,
                status=status.value,
                warning=f"[WARN] {stale_msg}",
                is_stale=True,
                gate_verdict="warned",
            )
        return CalibrationGateResult(
            allowed=False,
            status=status.value,
            message=(
                f"[BLOCKED] {stale_msg}\n"
                f"Use --force to proceed with stale calibration, or recalibrate."
            ),
            is_stale=True,
            gate_verdict="blocked",
        )

    # --- UNCALIBRATED ---
    if status == CalibrationStatus.UNCALIBRATED:
        uncal_msg = (
            f"Device {device_index} has no calibration record. "
            f"Without calibration, amplitude measurements cannot be compared "
            f"across sessions or units. "
            f"Run 'ttp calibrate tone --device {device_index}' first."
        )
        if allow_uncalibrated:
            return CalibrationGateResult(
                allowed=True,
                status=status.value,
                warning=(
                    f"[WARN] {uncal_msg}\n"
                    f"Proceeding uncalibrated (--force-uncalibrated). "
                    f"This session MUST NOT be used for production comparisons."
                ),
                is_uncalibrated=True,
                gate_verdict="warned",
            )
        return CalibrationGateResult(
            allowed=False,
            status=status.value,
            message=(
                f"[BLOCKED] {uncal_msg}\n"
                f"Use --force-uncalibrated to override for development/synthetic testing."
            ),
            is_uncalibrated=True,
            gate_verdict="blocked",
        )

    # --- FAILED ---
    return CalibrationGateResult(
        allowed=False,
        status=status.value,
        message=(
            f"[BLOCKED] Calibration failed for device {device_index}. "
            f"The measurement chain produced an invalid calibration result. "
            f"Check audio device connection and run 'ttp calibrate tone' again."
        ),
        is_failed=True,
        gate_verdict="blocked",
    )


def _cal_age_days(cal_data) -> int:
    """Return calibration age in whole days, or 999 if unknown."""
    if cal_data is None:
        return 999
    try:
        from datetime import datetime, timezone, timedelta
        cal_at = datetime.fromisoformat(
            cal_data.calibrated_at.replace("Z", "+00:00")
        )
        age = datetime.now(timezone.utc) - cal_at
        return int(age.days)
    except Exception:
        return 999


# ---------------------------------------------------------------------------
# CLI display helper
# ---------------------------------------------------------------------------

def print_gate_result(result: CalibrationGateResult) -> None:
    """Print gate result to stdout in a consistent format."""
    if result.allowed:
        if result.warning:
            print(result.warning)
        elif result.message:
            print(result.message)
    else:
        print(result.message)

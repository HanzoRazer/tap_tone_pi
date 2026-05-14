"""
tap_tone_pi.calibration — Self-calibration workflow for measurement chain verification.

Phase 3 P0: Closes ~50% of accuracy gap vs. commercial analyzers.

This module provides:
- Loopback test: Output → Input system response measurement
- Reference tone verification: 1 kHz known amplitude verification
- Compensation curves: Per-device calibration storage
- Calibration expiry: Warn when calibration is stale
- Session context: Calibration metadata injection for provenance

Usage:
    ttp calibrate loopback     # Measure system frequency response
    ttp calibrate verify       # Verify with 1 kHz reference tone
    ttp calibrate status       # Show current calibration state
    ttp calibrate clear        # Remove stored calibration

The calibration workflow moves the analyzer from "uncalibrated" to "user-calibrated",
significantly improving measurement confidence without requiring external equipment.
"""

from .loopback import (
    LoopbackResult,
    LoopbackConfig,
    run_loopback_test,
    compute_frequency_response,
)
from .reference_tone import (
    ReferenceToneResult,
    ReferenceToneConfig,
    run_reference_tone_test,
    verify_amplitude,
)
from .storage import (
    CalibrationData,
    CalibrationStatus,
    save_calibration,
    load_calibration,
    get_calibration_status,
    clear_calibration,
    is_calibration_stale,
    CALIBRATION_EXPIRY_DAYS,
)
from .compensation import (
    CompensationCurve,
    build_compensation_curve,
    apply_compensation,
)
from .session_context import (
    CalibrationContext,
    get_calibration_context,
    format_calibration_summary,
    inject_calibration_into_meta,
    extract_calibration_offsets,
)

__all__ = [
    # Loopback
    "LoopbackResult",
    "LoopbackConfig",
    "run_loopback_test",
    "compute_frequency_response",
    # Reference tone
    "ReferenceToneResult",
    "ReferenceToneConfig",
    "run_reference_tone_test",
    "verify_amplitude",
    # Storage
    "CalibrationData",
    "CalibrationStatus",
    "save_calibration",
    "load_calibration",
    "get_calibration_status",
    "clear_calibration",
    "is_calibration_stale",
    "CALIBRATION_EXPIRY_DAYS",
    # Compensation
    "CompensationCurve",
    "build_compensation_curve",
    "apply_compensation",
    # Session context
    "CalibrationContext",
    "get_calibration_context",
    "format_calibration_summary",
    "inject_calibration_into_meta",
    "extract_calibration_offsets",
]

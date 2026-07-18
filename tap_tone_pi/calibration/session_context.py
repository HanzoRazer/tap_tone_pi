# INSTRUMENT CLASS: MEASUREMENT
"""
Calibration context injection for measurement sessions.

When a capture is made, the current device calibration status is recorded
in the session metadata. This provides provenance for measurements and
allows downstream consumers to know if the measurement chain was calibrated.

Usage:
    from tap_tone_pi.calibration.session_context import get_calibration_context

    # Get calibration context for current device
    context = get_calibration_context(device_index=1)

    # Add to session_meta.json
    session_meta["calibration"] = context
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from tap_tone_pi.calibration.storage import (
    load_calibration,
    get_calibration_status,
    is_calibration_stale,
)


@dataclass
class CalibrationContext:
    """
    Calibration context to embed in session metadata.

    This is a lightweight summary of calibration state at capture time.
    Full calibration data is stored separately.
    """

    # Status at capture time
    status: str  # "valid", "stale", "uncalibrated", "failed"

    # Device info
    device_index: int
    device_name: Optional[str] = None

    # Calibration date (if available)
    calibrated_at: Optional[str] = None

    # Key calibration values
    amplitude_offset_db: Optional[float] = None  # Measured amplitude error
    frequency_offset_hz: Optional[float] = (
        None  # Measured frequency error (from ref tone)
    )
    latency_ms: Optional[float] = None  # System latency

    # Capture timestamp
    captured_at: str = ""

    # Warning flags
    is_stale: bool = False
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if not self.captured_at:
            self.captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrationContext":
        """Create from dict."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def get_calibration_context(device_index: int) -> CalibrationContext:
    """
    Get calibration context for a device.

    Args:
        device_index: Audio device index

    Returns:
        CalibrationContext with current calibration state
    """
    status = get_calibration_status(device_index)
    data = load_calibration(device_index)

    warnings = []

    if data is None:
        # No calibration data
        return CalibrationContext(
            status="uncalibrated",
            device_index=device_index,
            warnings=[
                "Device is not calibrated. Run 'ttp calibrate' for best accuracy."
            ],
        )

    # Check staleness
    is_stale = is_calibration_stale(data)
    if is_stale:
        warnings.append(
            "Calibration is stale (older than 30 days). Consider recalibrating."
        )

    # Build context
    context = CalibrationContext(
        status=status.value,
        device_index=device_index,
        device_name=data.device_name,
        calibrated_at=data.calibrated_at,
        amplitude_offset_db=data.amplitude_error_db,
        latency_ms=data.loopback_latency_ms,
        is_stale=is_stale,
        warnings=warnings,
    )

    return context


def format_calibration_summary(context: CalibrationContext) -> str:
    """
    Format calibration context for display.

    Args:
        context: CalibrationContext to format

    Returns:
        Human-readable summary string
    """
    lines = []

    # Status with color
    status_colors = {
        "valid": "\033[92m",  # Green
        "stale": "\033[93m",  # Yellow
        "uncalibrated": "\033[91m",  # Red
        "failed": "\033[91m",  # Red
    }
    reset = "\033[0m"
    color = status_colors.get(context.status, "")

    lines.append(f"Calibration: {color}{context.status.upper()}{reset}")

    if context.device_name:
        lines.append(f"  Device: [{context.device_index}] {context.device_name}")

    if context.calibrated_at:
        lines.append(f"  Calibrated: {context.calibrated_at[:10]}")

    if context.amplitude_offset_db is not None:
        lines.append(f"  Amplitude offset: {context.amplitude_offset_db:+.2f} dB")

    if context.latency_ms is not None:
        lines.append(f"  System latency: {context.latency_ms:.1f} ms")

    for warning in context.warnings:
        lines.append(f"  ⚠ {warning}")

    return "\n".join(lines)


def inject_calibration_into_meta(
    session_meta: Dict[str, Any],
    device_index: int,
) -> Dict[str, Any]:
    """
    Inject calibration context into session metadata.

    Modifies session_meta in place and returns it.

    Args:
        session_meta: Session metadata dict
        device_index: Audio device index

    Returns:
        Modified session_meta dict
    """
    context = get_calibration_context(device_index)
    session_meta["calibration"] = context.to_dict()
    return session_meta


def extract_calibration_offsets(
    session_meta: Dict[str, Any],
) -> tuple[Optional[float], Optional[float]]:
    """
    Extract calibration offsets from session metadata.

    Useful for applying compensation to measurements.

    Args:
        session_meta: Session metadata dict with calibration section

    Returns:
        Tuple of (amplitude_offset_db, frequency_offset_hz)
        Either may be None if not available.
    """
    cal = session_meta.get("calibration", {})

    amplitude_offset = cal.get("amplitude_offset_db")
    frequency_offset = cal.get("frequency_offset_hz")

    return amplitude_offset, frequency_offset

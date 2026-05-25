# INSTRUMENT CLASS: MEASUREMENT
"""
Calibration data storage and management.

Stores per-device calibration data in user config directory.
Tracks calibration age and warns when stale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

# Calibration expires after this many days
CALIBRATION_EXPIRY_DAYS = 30


class CalibrationStatus(Enum):
    """Calibration state for a device."""

    UNCALIBRATED = "uncalibrated"
    VALID = "valid"
    STALE = "stale"  # Expired but usable with warning
    FAILED = "failed"  # Last calibration attempt failed


@dataclass
class FrequencyResponsePoint:
    """Single point in frequency response curve."""

    freq_hz: float
    magnitude_db: float
    phase_deg: float


@dataclass
class CalibrationData:
    """Complete calibration data for a device."""

    # Device identification
    device_index: int
    device_name: str

    # Calibration timestamp
    calibrated_at: str  # ISO format
    calibrated_by: str = "user"  # "user" or "factory"

    # Loopback test results
    loopback_completed: bool = False
    loopback_latency_ms: Optional[float] = None
    loopback_snr_db: Optional[float] = None
    frequency_response: List[FrequencyResponsePoint] = field(default_factory=list)

    # Reference tone test results
    reference_tone_completed: bool = False
    reference_freq_hz: float = 1000.0
    reference_amplitude_dbfs: Optional[float] = None
    measured_amplitude_dbfs: Optional[float] = None
    amplitude_error_db: Optional[float] = None

    # Overall status
    status: str = "uncalibrated"  # CalibrationStatus value
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Convert FrequencyResponsePoint objects to dicts
        d["frequency_response"] = [asdict(p) for p in self.frequency_response]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrationData":
        """Create from dictionary."""
        # Convert frequency response points
        fr_points = [
            FrequencyResponsePoint(**p) for p in d.get("frequency_response", [])
        ]
        d = dict(d)
        d["frequency_response"] = fr_points
        return cls(**d)

    def is_complete(self) -> bool:
        """Check if calibration is complete (both tests passed)."""
        return self.loopback_completed and self.reference_tone_completed


def _get_calibration_dir() -> Path:
    """Get calibration data directory."""
    # Use same config directory as user_config
    from tap_tone_pi.core.user_config import CONFIG_DIR

    cal_dir = CONFIG_DIR / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    return cal_dir


def _get_calibration_file(device_index: int) -> Path:
    """Get calibration file path for a device."""
    return _get_calibration_dir() / f"device_{device_index}.json"


def save_calibration(data: CalibrationData) -> Path:
    """
    Save calibration data to disk.

    Args:
        data: Calibration data to save

    Returns:
        Path to saved file
    """
    cal_file = _get_calibration_file(data.device_index)

    # Atomic write
    tmp_file = cal_file.with_suffix(".json.tmp")
    tmp_file.write_text(
        json.dumps(data.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_file.replace(cal_file)

    return cal_file


def load_calibration(device_index: int) -> Optional[CalibrationData]:
    """
    Load calibration data for a device.

    Args:
        device_index: Device index to load calibration for

    Returns:
        CalibrationData if found, None otherwise
    """
    cal_file = _get_calibration_file(device_index)

    if not cal_file.exists():
        return None

    try:
        d = json.loads(cal_file.read_text(encoding="utf-8"))
        return CalibrationData.from_dict(d)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def clear_calibration(device_index: int) -> bool:
    """
    Remove calibration data for a device.

    Args:
        device_index: Device index to clear

    Returns:
        True if file was removed, False if not found
    """
    cal_file = _get_calibration_file(device_index)

    if cal_file.exists():
        cal_file.unlink()
        return True
    return False


def is_calibration_stale(data: CalibrationData) -> bool:
    """
    Check if calibration data is stale (expired).

    Args:
        data: Calibration data to check

    Returns:
        True if calibration is older than CALIBRATION_EXPIRY_DAYS
    """
    try:
        cal_date = datetime.fromisoformat(data.calibrated_at)
        age = datetime.now() - cal_date
        return age > timedelta(days=CALIBRATION_EXPIRY_DAYS)
    except (ValueError, TypeError):
        return True  # Invalid date = stale


def get_calibration_status(device_index: int) -> CalibrationStatus:
    """
    Get calibration status for a device.

    Args:
        device_index: Device index to check

    Returns:
        CalibrationStatus enum value
    """
    data = load_calibration(device_index)

    if data is None:
        return CalibrationStatus.UNCALIBRATED

    if data.status == "failed":
        return CalibrationStatus.FAILED

    if not data.is_complete():
        return CalibrationStatus.UNCALIBRATED

    if is_calibration_stale(data):
        return CalibrationStatus.STALE

    return CalibrationStatus.VALID


def list_calibrated_devices() -> List[int]:
    """
    List all devices with calibration data.

    Returns:
        List of device indices with calibration files
    """
    cal_dir = _get_calibration_dir()
    devices = []

    for f in cal_dir.glob("device_*.json"):
        try:
            idx = int(f.stem.replace("device_", ""))
            devices.append(idx)
        except ValueError:
            continue

    return sorted(devices)


def get_calibration_summary() -> Dict[int, Dict[str, Any]]:
    """
    Get summary of all calibration data.

    Returns:
        Dict mapping device_index to summary info
    """
    summary = {}

    for device_idx in list_calibrated_devices():
        data = load_calibration(device_idx)
        if data:
            status = get_calibration_status(device_idx)
            summary[device_idx] = {
                "device_name": data.device_name,
                "status": status.value,
                "calibrated_at": data.calibrated_at,
                "loopback_completed": data.loopback_completed,
                "reference_tone_completed": data.reference_tone_completed,
                "stale": is_calibration_stale(data),
            }

    return summary

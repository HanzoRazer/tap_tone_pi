"""
Audio and sensor acquisition (sounddevice, serial).

Canonical location for all capture functionality. Migrated from tap_tone/capture.py.
Lazy imports are used for numpy/sounddevice to improve CLI startup time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tap_tone_pi.core.errors import (
    DeviceError,
    DeviceNotFoundError,
    DeviceOpenError,
    CaptureError,
    ValidationError,
    handle_device_error,
    with_retry,
)

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class CaptureResult:
    """Result of an audio capture operation."""

    sample_rate: int
    audio: Any  # np.ndarray, shape: (n_samples,) - use Any to avoid runtime numpy import


def list_devices() -> list[dict]:
    """List available audio input devices.

    Returns:
        List of device info dictionaries with keys:
        - index: Device index for selection
        - name: Human-readable device name
        - max_input_channels: Number of input channels
        - max_output_channels: Number of output channels
        - default_samplerate: Default sample rate

    Raises:
        DeviceError: If unable to query audio devices
    """
    import sounddevice as sd

    try:
        devices = sd.query_devices()
    except Exception as e:
        raise DeviceError(
            f"Failed to query audio devices: {e}",
            suggestion="Check that audio drivers are installed correctly",
        ) from e

    out: list[dict] = []
    for i, d in enumerate(devices):
        out.append(
            {
                "index": i,
                "name": d.get("name"),
                "max_input_channels": d.get("max_input_channels"),
                "max_output_channels": d.get("max_output_channels"),
                "default_samplerate": d.get("default_samplerate"),
            }
        )
    return out


def _validate_device(device: int | None) -> None:
    """Validate that device exists and has input channels.

    Args:
        device: Device index to validate (None means system default)

    Raises:
        DeviceNotFoundError: If device doesn't exist
        DeviceOpenError: If device has no input channels
    """
    if device is None:
        return  # Use system default

    devices = list_devices()
    device_info = None
    for d in devices:
        if d["index"] == device:
            device_info = d
            break

    if device_info is None:
        raise DeviceNotFoundError(
            f"Device index {device} not found",
            suggestion="Run 'ttp devices' to see available devices",
        )

    if device_info.get("max_input_channels", 0) <= 0:
        raise DeviceOpenError(
            f"Device '{device_info.get('name', device)}' has no input channels",
            suggestion="Select a device with input capabilities (microphone)",
        )


def record_audio(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    channels: int = 1,
    seconds: float = 2.5,
    show_countdown: bool = False,
) -> CaptureResult:
    """Record audio from an input device.

    Args:
        device: Device index (None for system default)
        sample_rate: Sample rate in Hz
        channels: Number of channels (must be 1 for now)
        seconds: Duration to record
        show_countdown: If True, display countdown during recording

    Returns:
        CaptureResult with audio data and sample rate

    Raises:
        ValidationError: If channels != 1 or seconds <= 0
        DeviceNotFoundError: If specified device doesn't exist
        DeviceOpenError: If device can't be opened
        CaptureError: If recording fails
    """
    import numpy as np
    import sounddevice as sd

    # Validate inputs
    if channels != 1:
        raise ValidationError(
            "This implementation expects mono (channels=1).",
            suggestion="Use channels=1 for tap tone analysis",
        )
    if seconds <= 0:
        raise ValidationError(
            f"Duration must be positive, got {seconds}",
            suggestion="Typical recording duration is 2-3 seconds",
        )

    # Validate device before attempting to record
    _validate_device(device)

    try:
        sd.default.samplerate = sample_rate
        if device is not None:
            sd.default.device = (device, None)
    except Exception as e:
        raise handle_device_error(e, device_id=device) from e

    n_samples = int(sample_rate * seconds)

    # Optionally show countdown in a separate thread
    stop_countdown = None
    if show_countdown:
        import sys
        import threading
        import time

        stop_countdown = threading.Event()

        def _countdown() -> None:
            assert stop_countdown is not None
            for remaining in range(int(seconds), 0, -1):
                if stop_countdown.is_set():
                    break
                sys.stdout.write("\rRecording... " + str(remaining) + "s ")
                sys.stdout.flush()
                time.sleep(1)

        countdown_thread = threading.Thread(target=_countdown, daemon=True)
        countdown_thread.start()

    # Record float32 in [-1, 1]
    try:
        audio = sd.rec(frames=n_samples, channels=channels, dtype="float32", blocking=True)
    except Exception as e:
        raise CaptureError(
            f"Recording failed: {e}",
            suggestion="Check microphone connection and permissions",
        ) from e
    finally:
        # Clean up countdown display
        if show_countdown and stop_countdown is not None:
            import sys

            stop_countdown.set()
            sys.stdout.write("\rRecording... done!   \n")
            sys.stdout.flush()

    audio = audio.reshape(-1)  # mono

    # Replace NaNs (rare but possible)
    audio = np.nan_to_num(audio, nan=0.0)

    return CaptureResult(sample_rate=sample_rate, audio=audio)


def auto_detect_device() -> int | None:
    """Auto-detect the best input device.

    Prefers:
    1. Devices with "USB" in name (measurement mics)
    2. Devices with "Microphone" in name
    3. System default

    Returns:
        Device index or None for system default
    """
    try:
        devices = list_devices()
    except DeviceError:
        return None  # Fall back to system default

    # Priority 1: USB devices (likely measurement microphones)
    for d in devices:
        if d["max_input_channels"] > 0 and "USB" in (d["name"] or "").upper():
            return d["index"]

    # Priority 2: Any microphone
    for d in devices:
        if d["max_input_channels"] > 0 and "MIC" in (d["name"] or "").upper():
            return d["index"]

    # Priority 3: First device with input channels
    for d in devices:
        if d["max_input_channels"] > 0:
            return d["index"]

    # Fallback: system default
    return None


def _get_auto_trigger_exports() -> dict[str, Any]:
    """Lazy load auto-trigger support to improve startup time."""
    from tap_tone_pi.core.auto_trigger import (
        TriggerState,
        TriggerConfig,
        TriggerResult,
        TriggerCallback,
        AutoTriggerDetector,
        record_audio_triggered,
    )
    return {
        "TriggerState": TriggerState,
        "TriggerConfig": TriggerConfig,
        "TriggerResult": TriggerResult,
        "TriggerCallback": TriggerCallback,
        "AutoTriggerDetector": AutoTriggerDetector,
        "record_audio_triggered": record_audio_triggered,
    }


def __getattr__(name: str) -> Any:
    """Lazy load auto-trigger exports on first access."""
    _auto_trigger_names = {
        "TriggerState", "TriggerConfig", "TriggerResult",
        "TriggerCallback", "AutoTriggerDetector", "record_audio_triggered"
    }
    if name in _auto_trigger_names:
        exports = _get_auto_trigger_exports()
        # Cache in module globals for future access
        globals().update(exports)
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Re-export for convenience
__all__ = [
    "CaptureResult",
    "list_devices",
    "record_audio",
    "auto_detect_device",
    # Errors
    "DeviceError",
    "DeviceNotFoundError",
    "DeviceOpenError",
    "CaptureError",
    "ValidationError",
    # Auto-trigger (lazy loaded)
    "TriggerState",
    "TriggerConfig",
    "TriggerResult",
    "TriggerCallback",
    "AutoTriggerDetector",
    "record_audio_triggered",
]

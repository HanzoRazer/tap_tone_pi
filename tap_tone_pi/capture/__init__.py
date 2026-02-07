"""
Audio and sensor acquisition (sounddevice, serial).

Canonical location for all capture functionality. Migrated from tap_tone/capture.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class CaptureResult:
    """Result of an audio capture operation."""
    sample_rate: int
    audio: np.ndarray  # shape: (n_samples,)


def list_devices() -> list[dict]:
    """List available audio input devices.

    Returns:
        List of device info dictionaries with keys:
        - index: Device index for selection
        - name: Human-readable device name
        - max_input_channels: Number of input channels
        - max_output_channels: Number of output channels
        - default_samplerate: Default sample rate
    """
    import sounddevice as sd

    devices = sd.query_devices()
    out: list[dict] = []
    for i, d in enumerate(devices):
        out.append({
            "index": i,
            "name": d.get("name"),
            "max_input_channels": d.get("max_input_channels"),
            "max_output_channels": d.get("max_output_channels"),
            "default_samplerate": d.get("default_samplerate"),
        })
    return out


def record_audio(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    channels: int = 1,
    seconds: float = 2.5,
) -> CaptureResult:
    """Record audio from an input device.

    Args:
        device: Device index (None for system default)
        sample_rate: Sample rate in Hz
        channels: Number of channels (must be 1 for now)
        seconds: Duration to record

    Returns:
        CaptureResult with audio data and sample rate

    Raises:
        ValueError: If channels != 1 or seconds <= 0
    """
    import sounddevice as sd

    if channels != 1:
        raise ValueError("This implementation expects mono (channels=1).")
    if seconds <= 0:
        raise ValueError("seconds must be > 0")

    sd.default.samplerate = sample_rate
    if device is not None:
        sd.default.device = (device, None)

    n_samples = int(sample_rate * seconds)

    # Record float32 in [-1, 1]
    audio = sd.rec(frames=n_samples, channels=channels, dtype="float32", blocking=True)
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
    devices = list_devices()

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


# Re-export for convenience
__all__ = ["CaptureResult", "list_devices", "record_audio", "auto_detect_device"]

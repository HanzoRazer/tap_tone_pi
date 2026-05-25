# INSTRUMENT CLASS: MEASUREMENT
"""Pre-flight hardware checks for audio capture.

Validates hardware is ready before capturing:
- Device exists and has input channels
- Device can be opened
- Audio levels are detectable (not silent)
- No clipping in test capture
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # numpy imported at runtime


@dataclass(frozen=True)
class PreflightResult:
    """Result of preflight hardware check."""

    ok: bool
    device_name: str
    sample_rate: int
    peak_level: float
    rms_level: float
    clipped: bool
    message: str
    suggestion: str | None = None


def run_preflight(
    device: int | None = None,
    sample_rate: int = 48000,
    duration: float = 0.5,
    quiet: bool = False,
) -> PreflightResult:
    """Run pre-flight hardware checks.

    Args:
        device: Device index (None for default)
        sample_rate: Sample rate in Hz
        duration: Test capture duration in seconds
        quiet: If True, suppress output

    Returns:
        PreflightResult with check status and details
    """
    import numpy as np

    from tap_tone_pi.capture import list_devices, record_audio

    # Check device exists
    devices = list_devices()
    input_devices = [d for d in devices if d["max_input_channels"] > 0]

    if not input_devices:
        return PreflightResult(
            ok=False,
            device_name="none",
            sample_rate=sample_rate,
            peak_level=0.0,
            rms_level=0.0,
            clipped=False,
            message="No audio input devices found",
            suggestion="Connect a microphone and try again",
        )

    # Find the specific device
    if device is not None:
        device_info = next((d for d in input_devices if d["index"] == device), None)
        if device_info is None:
            valid = [d["index"] for d in input_devices]
            return PreflightResult(
                ok=False,
                device_name="unknown",
                sample_rate=sample_rate,
                peak_level=0.0,
                rms_level=0.0,
                clipped=False,
                message=f"Device {device} not found or has no input channels",
                suggestion=f"Valid devices: {valid}",
            )
    else:
        device_info = input_devices[0]

    device_name = device_info.get("name", "Unknown")
    if not quiet:
        print(f"Preflight: Testing device [{device_info['index']}] {device_name}...")

    # Try to capture a short test sample
    try:
        result = record_audio(
            device=device_info["index"],
            sample_rate=sample_rate,
            channels=1,
            seconds=duration,
        )
    except Exception as e:
        return PreflightResult(
            ok=False,
            device_name=device_name,
            sample_rate=sample_rate,
            peak_level=0.0,
            rms_level=0.0,
            clipped=False,
            message=f"Failed to open audio device: {e}",
            suggestion="Check device connection and permissions",
        )

    # Analyze the test capture
    audio = result.audio
    peak_level = float(np.max(np.abs(audio)))
    rms_level = float(np.sqrt(np.mean(audio**2)))
    clipped = peak_level >= 0.999

    # Determine status
    if rms_level < 0.0001:
        return PreflightResult(
            ok=False,
            device_name=device_name,
            sample_rate=sample_rate,
            peak_level=peak_level,
            rms_level=rms_level,
            clipped=False,
            message="No audio detected (silent)",
            suggestion="Check microphone connection and gain",
        )

    if clipped:
        return PreflightResult(
            ok=False,
            device_name=device_name,
            sample_rate=sample_rate,
            peak_level=peak_level,
            rms_level=rms_level,
            clipped=True,
            message="Audio is clipping (too loud)",
            suggestion="Reduce microphone gain before capturing",
        )

    if peak_level > 0.9:
        return PreflightResult(
            ok=True,
            device_name=device_name,
            sample_rate=sample_rate,
            peak_level=peak_level,
            rms_level=rms_level,
            clipped=False,
            message="Audio levels are high but acceptable",
            suggestion="Consider reducing gain slightly",
        )

    if rms_level < 0.01:
        return PreflightResult(
            ok=True,
            device_name=device_name,
            sample_rate=sample_rate,
            peak_level=peak_level,
            rms_level=rms_level,
            clipped=False,
            message="Audio levels are low",
            suggestion="Consider increasing microphone gain",
        )

    return PreflightResult(
        ok=True,
        device_name=device_name,
        sample_rate=sample_rate,
        peak_level=peak_level,
        rms_level=rms_level,
        clipped=False,
        message="Hardware check passed",
    )


def print_preflight_result(result: PreflightResult) -> None:
    """Print preflight result in human-readable format."""
    status = "OK" if result.ok else "FAIL"
    print(f"Preflight: [{status}] {result.message}")
    print(f"  Device: {result.device_name}")
    print(f"  Sample rate: {result.sample_rate} Hz")
    print(f"  Peak level: {result.peak_level:.3f}")
    print(f"  RMS level: {result.rms_level:.4f}")
    if result.clipped:
        print("  Clipped: YES")
    if result.suggestion:
        print(f"  Suggestion: {result.suggestion}")


def require_preflight(
    device: int | None = None,
    sample_rate: int = 48000,
    skip: bool = False,
) -> PreflightResult | None:
    """Run preflight and exit if it fails.

    Args:
        device: Device index
        sample_rate: Sample rate
        skip: If True, skip preflight entirely

    Returns:
        PreflightResult if checks passed, None if skipped

    Raises:
        SystemExit: If preflight fails
    """
    if skip:
        return None

    result = run_preflight(device=device, sample_rate=sample_rate)

    if not result.ok:
        print("")
        print_preflight_result(result)
        print("")
        print("Preflight check failed. Fix the issue above and try again.")
        print("Use --skip-preflight to bypass this check (not recommended).")
        sys.exit(1)

    return result

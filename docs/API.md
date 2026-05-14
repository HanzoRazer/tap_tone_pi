# Tap Tone Pi API Reference

This document provides API documentation for the main tap_tone_pi modules.

## Table of Contents

- [Capture Module](#capture-module)
- [Core Errors](#core-errors)
- [Auto-Trigger](#auto-trigger)
- [CLI Validators](#cli-validators)
- [CLI Preflight](#cli-preflight)

---

## Capture Module

**Location:** `tap_tone_pi.capture`

The capture module provides audio recording functionality for tap tone measurements.

### CaptureResult

```python
@dataclass(frozen=True)
class CaptureResult:
    sample_rate: int      # Sample rate in Hz
    audio: np.ndarray     # Audio data, shape (n_samples,), float32 in [-1, 1]
```

### Functions

#### list_devices()

List available audio input devices.

```python
def list_devices() -> list[dict]
```

**Returns:** List of device dictionaries with keys:
- `index`: Device index for selection
- `name`: Human-readable device name
- `max_input_channels`: Number of input channels
- `max_output_channels`: Number of output channels
- `default_samplerate`: Default sample rate

**Raises:** `DeviceError` if unable to query audio devices

**Example:**
```python
from tap_tone_pi.capture import list_devices

devices = list_devices()
for d in devices:
    if d["max_input_channels"] > 0:
        print(f"{d['index']}: {d['name']}")
```

#### record_audio()

Record audio from an input device.

```python
def record_audio(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    channels: int = 1,
    seconds: float = 2.5,
    show_countdown: bool = False,
) -> CaptureResult
```

**Parameters:**
- `device`: Device index (None for system default)
- `sample_rate`: Sample rate in Hz (default: 48000)
- `channels`: Number of channels (must be 1)
- `seconds`: Duration to record (default: 2.5)
- `show_countdown`: Display countdown during recording

**Returns:** `CaptureResult` with audio data and sample rate

**Raises:**
- `ValidationError`: If channels != 1 or seconds <= 0
- `DeviceNotFoundError`: If specified device doesn't exist
- `DeviceOpenError`: If device can't be opened
- `CaptureError`: If recording fails

**Example:**
```python
from tap_tone_pi.capture import record_audio

result = record_audio(device=2, seconds=3.0, show_countdown=True)
print(f"Recorded {len(result.audio)} samples at {result.sample_rate} Hz")
```

#### auto_detect_device()

Auto-detect the best input device.

```python
def auto_detect_device() -> int | None
```

Priority order:
1. Devices with "USB" in name (measurement mics)
2. Devices with "Microphone" in name
3. First device with input channels
4. System default (None)

**Returns:** Device index or None for system default

---

## Core Errors

**Location:** `tap_tone_pi.core.errors`

Centralized error handling with custom exceptions, retry decorator, and error context utilities.

### Exception Hierarchy

```
TapToneError (base)
├── DeviceError
│   ├── DeviceNotFoundError
│   └── DeviceOpenError
├── CaptureError
│   └── CaptureTimeoutError
├── AnalysisError
├── QualityError
├── ValidationError
├── FileFormatError
└── ConfigError
```

All exceptions accept an optional `suggestion` parameter:

```python
raise DeviceNotFoundError(
    "Device 5 not found",
    suggestion="Run 'ttp devices' to list available devices"
)
```

### RetryConfig

Configuration for retry behavior.

```python
@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    exceptions: tuple = (Exception,)
```

### with_retry()

Decorator to retry a function on transient failures.

```python
def with_retry(
    config: RetryConfig | None = None,
    *,
    max_attempts: int | None = None,
    delay_seconds: float | None = None,
    exceptions: tuple | None = None,
) -> Callable
```

**Example:**
```python
from tap_tone_pi.core.errors import with_retry, DeviceError

@with_retry(max_attempts=3, exceptions=(DeviceError,))
def open_device(device_id):
    # ... may fail transiently
    pass
```

### ErrorContext

Context information for error reporting.

```python
@dataclass
class ErrorContext:
    operation: str
    device: str | None = None
    file_path: str | None = None
    details: dict | None = None

    def format_message(self, error: Exception) -> str
```

### format_error_for_user()

Format an error message for display to users.

```python
def format_error_for_user(
    error: Exception,
    context: ErrorContext | None = None
) -> str
```

### handle_device_error()

Convert generic exception to appropriate DeviceError subclass.

```python
def handle_device_error(
    error: Exception,
    device_id: int | None = None
) -> DeviceError
```

---

## Auto-Trigger

**Location:** `tap_tone_pi.core.auto_trigger` (lazy-loaded from `tap_tone_pi.capture`)

Provides automatic tap detection for hands-free recording.

### TriggerConfig

```python
@dataclass
class TriggerConfig:
    threshold: float = 0.1      # Amplitude threshold for detection
    pre_samples: int = 2400     # Samples to keep before trigger
    post_seconds: float = 2.5   # Recording duration after trigger
    timeout_seconds: float = 30.0  # Max wait time
```

### TriggerState

Enum for trigger state machine:
- `WAITING`: Waiting for tap
- `TRIGGERED`: Tap detected, recording
- `COMPLETE`: Recording complete
- `TIMEOUT`: Timed out waiting

### TriggerResult

```python
@dataclass
class TriggerResult:
    state: TriggerState
    audio: np.ndarray | None
    trigger_sample: int | None
```

### record_audio_triggered()

Record audio with automatic tap detection.

```python
def record_audio_triggered(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    config: TriggerConfig | None = None,
    on_state_change: TriggerCallback | None = None,
) -> TriggerResult
```

**Example:**
```python
from tap_tone_pi.capture import record_audio_triggered, TriggerConfig

config = TriggerConfig(threshold=0.15, post_seconds=3.0)
result = record_audio_triggered(config=config)

if result.state == TriggerState.COMPLETE:
    print(f"Captured {len(result.audio)} samples")
```

---

## CLI Validators

**Location:** `tap_tone_pi.cli.validators`

Input validation utilities for CLI commands.

### validate_device_index()

Validate that a device index exists and has input channels.

```python
def validate_device_index(device: int | None) -> int | None
```

Exits with code 1 if device is invalid.

### validate_output_dir()

Validate an output directory path.

```python
def validate_output_dir(
    path: str,
    must_exist: bool = False
) -> Path
```

### validate_sample_rate()

Validate a sample rate value.

```python
def validate_sample_rate(rate: int) -> int
```

Valid range: 8000-192000 Hz. Warns for non-standard rates.

### validate_duration()

Validate a recording duration.

```python
def validate_duration(seconds: float) -> float
```

Must be positive. Warns if < 0.5s or > 30s.

### validate_file_exists()

Validate that a file exists.

```python
def validate_file_exists(path: str) -> Path
```

### confirm_overwrite()

Confirm before overwriting an existing file.

```python
def confirm_overwrite(
    path: Path,
    force: bool = False
) -> bool
```

### confirm_action()

Confirm a potentially destructive action.

```python
def confirm_action(
    message: str,
    force: bool = False
) -> bool
```

---

## CLI Preflight

**Location:** `tap_tone_pi.cli.preflight`

Hardware pre-flight checks before recording.

### PreflightResult

```python
@dataclass
class PreflightResult:
    ok: bool
    device_name: str
    sample_rate: int
    peak_level: float
    rms_level: float
    clipped: bool
    message: str
    suggestion: str | None = None
```

### run_preflight()

Run hardware pre-flight check.

```python
def run_preflight(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    duration: float = 1.0,
    quiet: bool = False,
) -> PreflightResult
```

Checks:
- Audio device exists and has input channels
- Device can be opened for recording
- Audio is not silent (RMS > 0.001)
- Audio is not clipping (peak < 0.99)

### print_preflight_result()

Print preflight result to console.

```python
def print_preflight_result(result: PreflightResult) -> None
```

### require_preflight()

Run preflight and exit if it fails.

```python
def require_preflight(
    *,
    device: int | None = None,
    skip: bool = False,
    quiet: bool = False,
) -> PreflightResult | None
```

Returns None if `skip=True`, otherwise runs preflight and exits with code 1 on failure.

---

## See Also

- [Quick Start Guide](QUICK_START.md) - Getting started tutorial
- [Measurement Boundary](MEASUREMENT_BOUNDARY.md) - Scope and limitations
- [Wolf Advisor Guide](WOLF_ADVISOR_GUIDE.md) - Wolf beat analysis

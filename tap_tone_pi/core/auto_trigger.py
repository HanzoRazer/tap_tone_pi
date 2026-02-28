"""Auto-trigger detector for tap-tone-pi (Phase 10).

Detects tap onset automatically using energy threshold monitoring.
Captures audio starting slightly before the trigger event to preserve
the initial transient.

Usage:
    detector = AutoTriggerDetector(sample_rate=48000)
    result = detector.wait_and_capture(device=0, post_trigger_seconds=2.0)

    if result.triggered:
        # result.audio contains the captured audio
        pass
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np

try:
    import sounddevice as sd

    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False


class TriggerState(str, Enum):
    """States of the auto-trigger detector."""

    IDLE = "idle"  # Not started
    LISTENING = "listening"  # Monitoring for trigger
    TRIGGERED = "triggered"  # Onset detected, recording
    COMPLETED = "completed"  # Recording complete
    TIMEOUT = "timeout"  # No trigger within timeout
    ERROR = "error"  # Error occurred


@dataclass
class TriggerConfig:
    """Configuration for auto-trigger detection."""

    # Energy detection
    threshold_rms: float = 0.01  # RMS threshold for trigger (0.0-1.0)
    threshold_multiplier: float = (
        3.0  # Trigger when current RMS > baseline * multiplier
    )
    use_adaptive: bool = True  # Use adaptive threshold (baseline * multiplier)

    # Timing
    chunk_ms: int = 20  # Chunk size for monitoring (milliseconds)
    pre_trigger_ms: int = 100  # Pre-trigger buffer (milliseconds)
    post_trigger_seconds: float = 2.5  # Recording duration after trigger
    timeout_seconds: float = 30.0  # Maximum wait time for trigger

    # Settling (M3 fix: configurable ADC settling)
    baseline_samples: int = 10  # Number of chunks to establish baseline
    settle_ms: int = 200  # Settling time after start before arming
    discard_initial_ms: int = 50  # M3 fix: Discard first N ms for ADC settling

    def __post_init__(self):
        """Validate configuration."""
        if self.threshold_rms <= 0 or self.threshold_rms > 1.0:
            raise ValueError("threshold_rms must be in (0, 1.0]")
        if self.chunk_ms < 5 or self.chunk_ms > 100:
            raise ValueError("chunk_ms must be in [5, 100]")
        if self.pre_trigger_ms < 0:
            raise ValueError("pre_trigger_ms must be >= 0")
        if self.post_trigger_seconds <= 0:
            raise ValueError("post_trigger_seconds must be > 0")
        if self.discard_initial_ms < 0:
            raise ValueError("discard_initial_ms must be >= 0")


@dataclass
class TriggerResult:
    """Result from auto-trigger capture."""

    state: TriggerState
    audio: np.ndarray | None = None
    sample_rate: int = 0
    triggered: bool = False
    trigger_time_ms: float = 0.0  # Time from start to trigger
    baseline_rms: float = 0.0  # Measured baseline RMS
    trigger_rms: float = 0.0  # RMS at trigger moment
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Duration of captured audio in seconds."""
        if self.audio is None or self.sample_rate == 0:
            return 0.0
        return len(self.audio) / self.sample_rate


# Callback type for progress updates
TriggerCallback = Callable[[TriggerState, dict], None]


class AutoTriggerDetector:
    """
    Auto-trigger detector for tap-tone measurements.

    Monitors audio stream for energy spikes indicating a tap,
    then records for a specified duration after the trigger.

    Features:
    - Pre-trigger buffer captures initial transient
    - Adaptive threshold based on ambient noise floor
    - Configurable timeout for unattended operation
    - Thread-safe state machine
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        config: TriggerConfig | None = None,
        callback: TriggerCallback | None = None,
    ):
        """
        Initialize the auto-trigger detector.

        Args:
            sample_rate: Audio sample rate in Hz
            config: Trigger configuration (uses defaults if None)
            callback: Optional callback for state changes
        """
        if not HAS_SOUNDDEVICE:
            raise ImportError("sounddevice is required for auto-trigger")

        self.sample_rate = sample_rate
        self.config = config or TriggerConfig()
        self.callback = callback

        # Derived values
        self._chunk_samples = int(sample_rate * self.config.chunk_ms / 1000)
        self._pre_trigger_chunks = max(
            1, self.config.pre_trigger_ms // self.config.chunk_ms
        )
        self._post_trigger_samples = int(sample_rate * self.config.post_trigger_seconds)
        self._settle_chunks = max(1, self.config.settle_ms // self.config.chunk_ms)
        # M3 fix: Calculate discard chunks for ADC settling
        self._discard_chunks = max(
            0, self.config.discard_initial_ms // self.config.chunk_ms
        )

        # State
        self._state = TriggerState.IDLE
        self._lock = threading.Lock()
        self._armed = False
        self._triggered = False
        self._start_time: float = 0.0
        self._trigger_time: float = 0.0

        # Buffers
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=self._pre_trigger_chunks)
        self._post_buffer: list[np.ndarray] = []
        self._rms_history: deque[float] = deque(maxlen=self.config.baseline_samples)
        self._baseline_rms: float = 0.0
        self._trigger_rms: float = 0.0
        self._chunks_received: int = 0

        # Result
        self._result: TriggerResult | None = None
        self._error: str | None = None

    @property
    def state(self) -> TriggerState:
        """Current detector state."""
        with self._lock:
            return self._state

    def _set_state(self, state: TriggerState, data: dict | None = None) -> None:
        """Set state and emit callback."""
        with self._lock:
            self._state = state
        if self.callback:
            self.callback(state, data or {})

    def _compute_rms(self, audio: np.ndarray) -> float:
        """Compute RMS of audio chunk."""
        return float(np.sqrt(np.mean(audio**2)))

    def _is_trigger(self, current_rms: float) -> bool:
        """Check if current RMS indicates a trigger event."""
        if self.config.use_adaptive:
            # Adaptive: trigger if RMS exceeds baseline * multiplier
            if self._baseline_rms > 0:
                threshold = self._baseline_rms * self.config.threshold_multiplier
                return current_rms > threshold
            return False
        else:
            # Fixed threshold
            return current_rms > self.config.threshold_rms

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Callback for audio stream processing."""
        if status:
            # Audio underflow/overflow - log but continue
            pass

        # Convert to mono if needed and flatten
        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()
        audio = audio.astype(np.float32)

        self._chunks_received += 1
        current_rms = self._compute_rms(audio)

        with self._lock:
            if self._state == TriggerState.LISTENING:
                # M3 fix: Discard initial samples for ADC settling
                if self._chunks_received <= self._discard_chunks:
                    # Don't use these samples for baseline or pre-buffer
                    # ADC may have DC offset drift or transient artifacts
                    return

                # Update baseline during settling period (after discard window)
                effective_chunk = self._chunks_received - self._discard_chunks
                if effective_chunk <= self._settle_chunks:
                    self._rms_history.append(current_rms)
                    self._baseline_rms = float(np.mean(self._rms_history))
                    self._pre_buffer.append(audio.copy())
                    return

                # Arm after settling
                if not self._armed:
                    self._armed = True
                    self._baseline_rms = float(np.mean(self._rms_history))

                # Check for trigger
                if self._is_trigger(current_rms):
                    self._triggered = True
                    self._trigger_time = time.time()
                    self._trigger_rms = current_rms
                    self._state = TriggerState.TRIGGERED
                    # Don't emit callback inside lock
                else:
                    # Not triggered, update pre-buffer
                    self._pre_buffer.append(audio.copy())

            elif self._state == TriggerState.TRIGGERED:
                # Collecting post-trigger audio
                self._post_buffer.append(audio.copy())

                total_post_samples = sum(len(chunk) for chunk in self._post_buffer)
                if total_post_samples >= self._post_trigger_samples:
                    self._state = TriggerState.COMPLETED

    def wait_and_capture(
        self,
        device: int | None = None,
        post_trigger_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> TriggerResult:
        """
        Wait for trigger and capture audio.

        Args:
            device: Audio device index (None = default)
            post_trigger_seconds: Override config post_trigger_seconds
            timeout_seconds: Override config timeout_seconds

        Returns:
            TriggerResult with captured audio or timeout/error status
        """
        # Apply overrides
        if post_trigger_seconds is not None:
            self._post_trigger_samples = int(self.sample_rate * post_trigger_seconds)
        if timeout_seconds is not None:
            timeout = timeout_seconds
        else:
            timeout = self.config.timeout_seconds

        # Reset state
        self._armed = False
        self._triggered = False
        self._pre_buffer.clear()
        self._post_buffer.clear()
        self._rms_history.clear()
        self._baseline_rms = 0.0
        self._trigger_rms = 0.0
        self._chunks_received = 0
        self._error = None

        self._set_state(TriggerState.LISTENING, {"timeout": timeout})
        self._start_time = time.time()

        try:
            # Open audio stream
            with sd.InputStream(
                device=device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self._chunk_samples,
                dtype="float32",
                callback=self._audio_callback,
            ):
                # Wait for trigger or timeout
                while True:
                    with self._lock:
                        current_state = self._state

                    if current_state == TriggerState.COMPLETED:
                        break

                    if current_state == TriggerState.ERROR:
                        break

                    # Check timeout
                    elapsed = time.time() - self._start_time
                    if elapsed > timeout:
                        self._set_state(TriggerState.TIMEOUT)
                        break

                    # Small sleep to avoid busy-wait
                    time.sleep(0.01)

            # Build result
            return self._build_result()

        except Exception as e:
            self._error = str(e)
            self._set_state(TriggerState.ERROR, {"error": str(e)})
            return TriggerResult(
                state=TriggerState.ERROR,
                error=str(e),
            )

    def _build_result(self) -> TriggerResult:
        """Build the final result from captured buffers."""
        with self._lock:
            final_state = self._state
            triggered = self._triggered
            baseline_rms = self._baseline_rms
            trigger_rms = self._trigger_rms

        if final_state == TriggerState.TIMEOUT:
            return TriggerResult(
                state=TriggerState.TIMEOUT,
                triggered=False,
                baseline_rms=baseline_rms,
            )

        if final_state == TriggerState.ERROR:
            return TriggerResult(
                state=TriggerState.ERROR,
                error=self._error,
            )

        if final_state == TriggerState.COMPLETED and triggered:
            # Concatenate pre-buffer + post-buffer
            all_chunks = list(self._pre_buffer) + self._post_buffer
            audio = np.concatenate(all_chunks)

            # Calculate trigger time
            trigger_time_ms = (self._trigger_time - self._start_time) * 1000

            return TriggerResult(
                state=TriggerState.COMPLETED,
                audio=audio,
                sample_rate=self.sample_rate,
                triggered=True,
                trigger_time_ms=trigger_time_ms,
                baseline_rms=baseline_rms,
                trigger_rms=trigger_rms,
            )

        # Shouldn't reach here, but handle gracefully
        return TriggerResult(
            state=final_state,
            triggered=False,
        )

    def cancel(self) -> None:
        """Cancel waiting for trigger."""
        with self._lock:
            if self._state == TriggerState.LISTENING:
                self._state = TriggerState.IDLE


# Convenience function matching capture.py interface
def record_audio_triggered(
    *,
    device: int | None = None,
    sample_rate: int = 48000,
    post_trigger_seconds: float = 2.5,
    timeout_seconds: float = 30.0,
    threshold_rms: float = 0.01,
    pre_trigger_ms: int = 100,
    callback: TriggerCallback | None = None,
) -> TriggerResult:
    """
    Record audio with auto-trigger detection.

    Convenience function that creates a detector and captures audio.

    Args:
        device: Audio device index (None = default)
        sample_rate: Sample rate in Hz
        post_trigger_seconds: Recording duration after trigger
        timeout_seconds: Maximum wait time for trigger
        threshold_rms: RMS threshold for fixed threshold mode
        pre_trigger_ms: Pre-trigger buffer in milliseconds
        callback: Optional callback for state changes

    Returns:
        TriggerResult with captured audio or timeout/error status
    """
    config = TriggerConfig(
        threshold_rms=threshold_rms,
        pre_trigger_ms=pre_trigger_ms,
        post_trigger_seconds=post_trigger_seconds,
        timeout_seconds=timeout_seconds,
    )

    detector = AutoTriggerDetector(
        sample_rate=sample_rate,
        config=config,
        callback=callback,
    )

    return detector.wait_and_capture(device=device)


__all__ = [
    "TriggerState",
    "TriggerConfig",
    "TriggerResult",
    "TriggerCallback",
    "AutoTriggerDetector",
    "record_audio_triggered",
]

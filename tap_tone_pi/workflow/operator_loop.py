"""Operator Loop state machine for tap-tone-pi.

Implements the deterministic measurement workflow:
    IDLE -> PREFLIGHT -> READY -> CAPTURING -> ANALYZING -> GATING -> ACCEPT/RETRY

The loop enforces quality gates and prevents silent advancement
past failed measurements.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any

import numpy as np
from scipy.io import wavfile

from tap_tone_pi.capture import (
    record_audio,
    list_devices,
    CaptureResult,
    record_audio_triggered,
    TriggerState,
    TriggerResult,
)
from tap_tone_pi.core.analysis import analyze_tap, AnalysisResult
from tap_tone_pi.core.quality_gate import check_quality, format_verdict_summary
from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict
from tap_tone_pi.workflow.attempt import Attempt, AttemptStore, AttemptStatus


class LoopState(str, Enum):
    """States in the operator loop."""
    IDLE = "idle"              # No active measurement
    PREFLIGHT = "preflight"    # Checking device/environment
    READY = "ready"            # Ready for capture
    LISTENING = "listening"    # Waiting for auto-trigger (Phase 10)
    CAPTURING = "capturing"    # Recording audio
    ANALYZING = "analyzing"    # Running DSP analysis
    GATING = "gating"          # Checking quality
    PASSED = "passed"          # Quality gate passed
    WARNED = "warned"          # Quality gate warned (can proceed)
    FAILED = "failed"          # Quality gate failed (must retry)
    COMPLETED = "completed"    # Point complete, moving on


@dataclass
class LoopResult:
    """Result of a complete loop iteration."""
    attempt: Attempt
    audio: np.ndarray | None = None
    analysis: AnalysisResult | None = None
    verdict: QualityVerdict | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.attempt.succeeded

    @property
    def can_proceed(self) -> bool:
        """Check if measurement can proceed (passed or warned)."""
        if self.verdict is None:
            return False
        return self.verdict.verdict in (Verdict.PASS, Verdict.WARN)


# Type alias for callbacks
LoopCallback = Callable[[LoopState, dict[str, Any]], None]


class OperatorLoop:
    """
    Operator loop state machine.

    Usage:
        loop = OperatorLoop(session_dir="/path/to/session")
        result = loop.run_single("point_001", device=1, sample_rate=48000)

        if result.succeeded:
            print("Measurement accepted")
        else:
            print("Measurement failed, retry required")
    """

    def __init__(
        self,
        session_dir: Path | str,
        callback: LoopCallback | None = None,
    ):
        """
        Initialize the operator loop.

        Args:
            session_dir: Directory to store session data
            callback: Optional callback for state changes
        """
        self.session_dir = Path(session_dir)
        self.store = AttemptStore(self.session_dir)
        self.callback = callback
        self.state = LoopState.IDLE
        self._current_attempt: Attempt | None = None

    def _emit(self, state: LoopState, data: dict[str, Any] | None = None) -> None:
        """Emit state change to callback."""
        self.state = state
        if self.callback:
            self.callback(state, data or {})

    def preflight(self, device: int | None = None) -> tuple[bool, str]:
        """
        Run preflight checks.

        Args:
            device: Device index to check (None = check any device available)

        Returns:
            (ok, message) tuple
        """
        self._emit(LoopState.PREFLIGHT)

        devices = list_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]

        if not input_devices:
            return False, "No audio input devices found"

        if device is not None:
            matching = [d for d in input_devices if d["index"] == device]
            if not matching:
                return False, f"Device {device} not found or has no input channels"
            device_info = matching[0]
            return True, f"Device ready: [{device}] {device_info['name']}"

        return True, f"Found {len(input_devices)} input device(s)"

    def run_single(
        self,
        point_id: str,
        device: int | None = None,
        sample_rate: int = 48000,
        duration: float = 2.5,
        channels: int = 1,
        auto_trigger: bool = False,
        auto_trigger_timeout: float = 30.0,
    ) -> LoopResult:
        """
        Run a single capture-analyze-gate cycle.

        Args:
            point_id: Identifier for this measurement point
            device: Audio device index (None = default)
            sample_rate: Sample rate in Hz
            duration: Capture duration in seconds (or post-trigger if auto_trigger)
            channels: Number of channels (default 1 = mono)
            auto_trigger: If True, wait for tap onset before recording
            auto_trigger_timeout: Timeout for auto-trigger in seconds

        Returns:
            LoopResult with attempt, audio, analysis, and verdict
        """
        # Create new attempt
        attempt = self.store.create_attempt(point_id)
        self._current_attempt = attempt
        attempt_dir = self.store.get_attempt_dir(attempt)

        # Get device name for logging
        devices = list_devices()
        device_name = "default"
        if device is not None:
            matching = [d for d in devices if d["index"] == device]
            if matching:
                device_name = matching[0]["name"]

        # --- PREFLIGHT ---
        ok, msg = self.preflight(device)
        if not ok:
            attempt.status = AttemptStatus.FAILED
            self.store.save_attempt(attempt)
            return LoopResult(attempt=attempt, error=msg)

        # --- READY ---
        self._emit(LoopState.READY, {"point_id": point_id, "attempt": attempt.attempt_number})

        # --- CAPTURING ---
        if auto_trigger:
            # Auto-trigger mode: wait for tap onset
            self._emit(LoopState.LISTENING, {"timeout": auto_trigger_timeout})
            try:
                trigger_result: TriggerResult = record_audio_triggered(
                    device=device,
                    sample_rate=sample_rate,
                    post_trigger_seconds=duration,
                    timeout_seconds=auto_trigger_timeout,
                )
                if not trigger_result.triggered:
                    if trigger_result.state == TriggerState.TIMEOUT:
                        attempt.status = AttemptStatus.FAILED
                        self.store.save_attempt(attempt)
                        return LoopResult(attempt=attempt, error="Auto-trigger timeout - no tap detected")
                    else:
                        attempt.status = AttemptStatus.FAILED
                        self.store.save_attempt(attempt)
                        return LoopResult(attempt=attempt, error=f"Auto-trigger failed: {trigger_result.error}")
                
                # Convert to CaptureResult for downstream compatibility
                cap_result = CaptureResult(
                    sample_rate=trigger_result.sample_rate,
                    audio=trigger_result.audio,
                )
                actual_duration = trigger_result.duration_seconds
            except Exception as e:
                attempt.status = AttemptStatus.FAILED
                self.store.save_attempt(attempt)
                return LoopResult(attempt=attempt, error=f"Auto-trigger capture failed: {e}")
        else:
            # Fixed-duration mode
            self._emit(LoopState.CAPTURING)
            try:
                cap_result: CaptureResult = record_audio(
                    device=device,
                    sample_rate=sample_rate,
                    channels=channels,
                    seconds=duration,
                )
                actual_duration = duration
            except Exception as e:
                attempt.status = AttemptStatus.FAILED
                self.store.save_attempt(attempt)
                return LoopResult(attempt=attempt, error=f"Capture failed: {e}")

        # Emit CAPTURING state after trigger (if auto-trigger was used)
        if auto_trigger:
            self._emit(LoopState.CAPTURING, {"triggered": True})

        # Mark captured
        attempt.mark_captured(
            device_index=device or 0,
            device_name=device_name,
            sample_rate=cap_result.sample_rate,
            duration_seconds=actual_duration,
        )

        # Save audio
        audio_path = attempt_dir / "audio.wav"
        wavfile.write(str(audio_path), cap_result.sample_rate, cap_result.audio)
        attempt.audio_path = "audio.wav"

        # --- ANALYZING ---
        self._emit(LoopState.ANALYZING)
        try:
            analysis = analyze_tap(cap_result.audio, cap_result.sample_rate)
        except Exception as e:
            attempt.status = AttemptStatus.FAILED
            self.store.save_attempt(attempt)
            return LoopResult(
                attempt=attempt,
                audio=cap_result.audio,
                error=f"Analysis failed: {e}",
            )

        # Mark analyzed
        attempt.mark_analyzed(
            dominant_hz=analysis.dominant_hz,
            rms=analysis.rms,
            confidence=analysis.confidence,
            peak_count=len(analysis.peaks) if analysis.peaks else 0,
            clipped=analysis.clipped,
        )

        # Save analysis
        analysis_path = attempt_dir / "analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump({
                "dominant_hz": analysis.dominant_hz,
                "rms": float(analysis.rms),
                "confidence": float(analysis.confidence),
                "clipped": analysis.clipped,
                "peak_count": len(analysis.peaks) if analysis.peaks else 0,
                "peaks": [
                    {"freq_hz": p.freq_hz, "magnitude": float(p.magnitude)}
                    for p in (analysis.peaks or [])[:20]
                ],
            }, f, indent=2)
        attempt.analysis_path = "analysis.json"

        # --- GATING ---
        self._emit(LoopState.GATING)
        verdict = check_quality(
            analysis=analysis,
            sample_rate=cap_result.sample_rate,
            audio=cap_result.audio,
        )

        # Mark gated
        attempt.mark_gated(verdict)

        # Save quality check
        quality_path = attempt_dir / "quality_check.json"
        with open(quality_path, "w", encoding="utf-8") as f:
            json.dump(verdict.to_dict(), f, indent=2)
        attempt.quality_check_path = "quality_check.json"

        # Save attempt metadata
        self.store.save_attempt(attempt)

        # --- EMIT FINAL STATE ---
        if verdict.verdict == Verdict.PASS:
            self._emit(LoopState.PASSED, {"verdict": verdict})
        elif verdict.verdict == Verdict.WARN:
            self._emit(LoopState.WARNED, {"verdict": verdict})
        else:
            self._emit(LoopState.FAILED, {"verdict": verdict})

        return LoopResult(
            attempt=attempt,
            audio=cap_result.audio,
            analysis=analysis,
            verdict=verdict,
        )

    def override_failed(self, point_id: str, reason: str) -> Attempt | None:
        """
        Override the most recent failed attempt for a point.

        Args:
            point_id: Point identifier
            reason: Required reason for override

        Returns:
            Updated attempt or None if no failed attempt found
        """
        if not reason or not reason.strip():
            raise ValueError("Override reason is required")

        attempt = self.store.get_latest_attempt(point_id)
        if attempt is None:
            return None

        if attempt.status != AttemptStatus.FAILED:
            return None  # Can only override failed attempts

        attempt.mark_overridden(reason.strip())
        self.store.save_attempt(attempt)

        return attempt

    def get_point_status(self, point_id: str) -> dict[str, Any]:
        """
        Get status summary for a measurement point.

        Returns dict with:
            - attempt_count: Number of attempts
            - latest_status: Status of most recent attempt
            - succeeded: Whether point has a successful measurement
        """
        attempts = self.store.list_attempts(point_id)

        if not attempts:
            return {
                "attempt_count": 0,
                "latest_status": None,
                "succeeded": False,
            }

        latest = attempts[-1]
        succeeded = any(a.succeeded for a in attempts)

        return {
            "attempt_count": len(attempts),
            "latest_status": latest.status.value,
            "succeeded": succeeded,
        }


__all__ = [
    "LoopState",
    "LoopResult",
    "LoopCallback",
    "OperatorLoop",
]

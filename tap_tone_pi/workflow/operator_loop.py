"""Operator Loop state machine for tap-tone-pi.

Implements the deterministic measurement workflow:
    IDLE -> PREFLIGHT -> READY -> CAPTURING -> ANALYZING -> GATING -> ACCEPT/RETRY

The loop enforces quality gates and prevents silent advancement
past failed measurements.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any, Optional

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
from tap_tone_pi.agentic.events import (
    JsonlEventWriter,
    emit_analysis_started,
    emit_analysis_completed,
    emit_analysis_failed,
    emit_artifact_created,
    emit_decision_required,
)
from tap_tone_pi.agentic.spine.shadow_record import write_shadow_record
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
        *,
        view_adapter: Any | None = None,
        spine_mode: str = "M1",
    ):
        """
        Initialize the operator loop.

        Args:
            session_dir: Directory to store session data
            callback: Optional callback for state changes
            view_adapter: Optional ViewAdapter for M2 actuation commands.
                          Must implement focus_trace, hide_all_except,
                          highlight_delta, and reset_view methods.
            spine_mode: Spine operating mode — "M0", "M1", or "M2".
                        M2 requires a view_adapter; falls back to M1 if absent.
        """
        self.session_dir = Path(session_dir)
        self.store = AttemptStore(self.session_dir)
        self.callback = callback
        self.state = LoopState.IDLE
        self._current_attempt: Attempt | None = None
        self._event_writer = JsonlEventWriter(
            self.session_dir / "events.jsonl"
        )
        # View adapter for M2 actuation (PR #20)
        self._view_adapter = view_adapter
        # Spine mode: M0/M1/M2.  M2 without adapter silently falls back to M1.
        if spine_mode == "M2" and view_adapter is None:
            self._spine_mode = "M1"
        else:
            self._spine_mode = spine_mode if spine_mode in ("M0", "M1", "M2") else "M1"
        # UWSM cache is optional; loaded on-demand in advisory hook
        self._uwsm_cached: dict | None = None
        self._uwsm_conf_cached: dict | None = None
        self._uwsm_updated_at_cached: datetime | None = None

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _directive_field(obj: Any, key: str, default: Any = None) -> Any:
        """
        Dict/dataclass compatibility accessor for directive-like objects.

        decide() currently returns plain dict directives, but may migrate to
        frozen dataclasses later. This helper keeps OperatorLoop forward-compatible.
        """
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _ensure_uwsm_loaded(self) -> None:
        """
        Load UWSM state once per OperatorLoop instance (fail-closed).
        """
        if self._uwsm_cached is not None and self._uwsm_conf_cached is not None and self._uwsm_updated_at_cached is not None:
            return
        from tap_tone_pi.agentic.spine.uwsm_store import load_uwsm_state
        uwsm, conf, ts = load_uwsm_state(now=self._utc_now())
        self._uwsm_cached = uwsm
        self._uwsm_conf_cached = conf
        self._uwsm_updated_at_cached = ts

    def _save_uwsm(self) -> None:
        """
        Persist cached UWSM (fail-closed).
        """
        if self._uwsm_cached is None or self._uwsm_conf_cached is None:
            return
        from tap_tone_pi.agentic.spine.uwsm_store import save_uwsm_state
        save_uwsm_state(self._uwsm_cached, self._uwsm_conf_cached, now=self._utc_now())

    def _append_uwsm_audit(self, attempt: Attempt, audits: list[dict]) -> None:
        """
        Optional per-session audit log; fail-closed.
        """
        if not audits:
            return
        try:
            p = Path(self.session_dir) / "uwsm_audit.jsonl"
            rec = {
                "timestamp": self._utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "session_dir": str(self.session_dir),
                "run_id": getattr(attempt, "attempt_id", ""),
                "point_id": getattr(attempt, "point_id", ""),
                "updates": audits,
            }
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False))
                f.write("\n")
        except Exception:
            return

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

        # Event: audio artifact created
        evt = emit_artifact_created(
            component="operator_loop",
            run_id=attempt.attempt_id,
            artifact_name="audio.wav",
            artifact_type="audio",
            correlation_id=attempt.attempt_id,
        )
        evt.privacy_layer = 0
        self._event_writer.write(evt)

        # --- ANALYZING ---
        self._emit(LoopState.ANALYZING)

        # Event: analysis started
        evt = emit_analysis_started(
            component="operator_loop",
            run_id=attempt.attempt_id,
            correlation_id=attempt.attempt_id,
        )
        evt.privacy_layer = 0
        self._event_writer.write(evt)

        try:
            analysis = analyze_tap(cap_result.audio, cap_result.sample_rate)
        except Exception as e:
            # Event: analysis failed
            evt = emit_analysis_failed(
                component="operator_loop",
                run_id=attempt.attempt_id,
                error=str(e),
                correlation_id=attempt.attempt_id,
            )
            evt.privacy_layer = 0
            self._event_writer.write(evt)

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

        # Event: analysis artifact created
        evt = emit_artifact_created(
            component="operator_loop",
            run_id=attempt.attempt_id,
            artifact_name="analysis.json",
            artifact_type="analysis",
            correlation_id=attempt.attempt_id,
        )
        evt.privacy_layer = 0
        self._event_writer.write(evt)

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

        # Event: quality_check artifact created
        evt = emit_artifact_created(
            component="operator_loop",
            run_id=attempt.attempt_id,
            artifact_name="quality_check.json",
            artifact_type="quality_check",
            correlation_id=attempt.attempt_id,
        )
        evt.privacy_layer = 0
        self._event_writer.write(evt)

        # Event: analysis completed (with metrics)
        evt = emit_analysis_completed(
            component="operator_loop",
            run_id=attempt.attempt_id,
            artifacts_created=["audio.wav", "analysis.json", "quality_check.json"],
            metrics={
                "verdict": verdict.verdict.value,
                "confidence": float(analysis.confidence),
                "peak_count": len(analysis.peaks) if analysis.peaks else 0,
            },
            correlation_id=attempt.attempt_id,
        )
        evt.privacy_layer = 0
        self._event_writer.write(evt)

        # Event: decision required (FAIL/WARN only)
        if verdict.verdict in (Verdict.FAIL, Verdict.WARN):
            options = ["retry", "override", "abort"] if verdict.verdict == Verdict.FAIL else ["accept", "retry"]
            evt = emit_decision_required(
                component="operator_loop",
                run_id=attempt.attempt_id,
                decision_type="quality_gate",
                options=options,
                correlation_id=attempt.attempt_id,
            )
            evt.privacy_layer = 0
            self._event_writer.write(evt)

        # Save attempt metadata
        self.store.save_attempt(attempt)

        # --- EMIT FINAL STATE ---
        if verdict.verdict == Verdict.PASS:
            self._emit(LoopState.PASSED, {"verdict": verdict})
        elif verdict.verdict == Verdict.WARN:
            self._emit(LoopState.WARNED, {"verdict": verdict})
        else:
            self._emit(LoopState.FAILED, {"verdict": verdict})

        # --- ADVISORY MODE (M1) ---
        self._run_shadow_hook(attempt)

        return LoopResult(
            attempt=attempt,
            audio=cap_result.audio,
            analysis=analysis,
            verdict=verdict,
        )

    # -------------------------------------------------------------------------
    # Spine advisory hook (PR#4) + UWSM persistence (PR#5)
    # -------------------------------------------------------------------------

    def _run_shadow_hook(self, attempt: Attempt) -> None:
        """
        Fail-closed wrapper. Never raises.
        """
        try:
            self._run_shadow_hook_inner(attempt)
        except Exception:
            return

    def _run_shadow_hook_inner(self, attempt: Attempt) -> None:
        """
        Advisory hook:
          - loads events.jsonl
          - loads + decays persisted UWSM
          - applies UWSM updates from events
          - runs spine decide() in M1 (advisory only)
          - writes shadow/advisory record (commands_count enforced 0 elsewhere)
          - persists updated UWSM
        """
        from tap_tone_pi.agentic.spine.moments import detect_moments
        from tap_tone_pi.agentic.spine.policy import decide
        from tap_tone_pi.agentic.spine.uwsm_update import apply_uwsm_updates
        from tap_tone_pi.agentic.spine.uwsm_store import apply_uwsm_decay
        from tap_tone_pi.agentic.capabilities import TAP_TONE_ANALYZER

        session_dir = Path(self.session_dir)
        events_path = session_dir / "events.jsonl"
        if not events_path.exists():
            # No events => no advisory; write NONE moment record
            write_shadow_record(
                session_dir=session_dir,
                session_id=str(session_dir.name),
                run_id=str(getattr(attempt, "attempt_id", "")),
                mode=self._spine_mode,
                moment_id="NONE",
                moment_confidence=0.0,
                trigger_event_count=0,
                commands_count=0,
                error=None,
            )
            return

        # Load events (dicts) for moments/policy/UWSM update engine
        events: list[dict] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                # skip malformed lines; fail-closed behavior continues
                continue

        now = self._utc_now()

        # Load + decay persisted UWSM
        self._ensure_uwsm_loaded()
        assert self._uwsm_cached is not None and self._uwsm_conf_cached is not None and self._uwsm_updated_at_cached is not None
        self._uwsm_cached, self._uwsm_conf_cached = apply_uwsm_decay(
            self._uwsm_cached, self._uwsm_conf_cached, self._uwsm_updated_at_cached, now
        )

        # Apply updates (mutates UWSM); persist audit
        self._uwsm_cached, audits = apply_uwsm_updates(events=events, uwsm=self._uwsm_cached)
        self._append_uwsm_audit(attempt, audits)

        # Update cached timestamp + save to disk
        self._uwsm_updated_at_cached = now
        self._save_uwsm()

        # Detect moment + decide in M1 using updated UWSM
        moment_res = detect_moments(events)
        if not moment_res:
            write_shadow_record(
                session_dir=session_dir,
                session_id=str(session_dir.name),
                run_id=str(getattr(attempt, "attempt_id", "")),
                mode=self._spine_mode,
                moment_id="NONE",
                moment_confidence=0.0,
                trigger_event_count=0,
                commands_count=0,
                error=None,
            )
            return

        # moment_res is a list; take highest-priority entry
        top = moment_res[0] if isinstance(moment_res, list) else moment_res

        # Build capability for policy engine.
        # In M2 mode with a view adapter, declare view adjustment allowed.
        cap: Any = TAP_TONE_ANALYZER
        if self._spine_mode == "M2" and self._view_adapter is not None:
            cap = {
                "automation_limits": {"agent_can_adjust_view": True},
            }

        decision = decide(
            moment=top,
            uwsm=self._uwsm_cached,
            mode=self._spine_mode,
            capability=cap,
            context={
                "session_dir": str(session_dir),
                "run_id": str(getattr(attempt, "attempt_id", "")),
                "point_id": str(getattr(attempt, "point_id", "")),
                "workflow": "measure",
            },
        )

        # M2 command dispatch (PR #20) — fail-closed
        issue_commands = (decision or {}).get("issue_commands", [])
        commands_dispatched = 0
        if issue_commands and self._view_adapter is not None:
            try:
                from tap_tone_pi.agentic.spine.view_adapter import dispatch_commands
                commands_dispatched = dispatch_commands(
                    self._view_adapter, issue_commands,
                )
            except Exception:
                pass  # fail-closed

        directive = (decision or {}).get("directive")
        advisory_action = None
        advisory_summary = None
        advisory_focus = None
        advisory_conf = None

        if directive is not None:
            # directive may be a dict (current) or a dataclass (future)
            raw_action = self._directive_field(directive, "action")
            # AttentionAction enum values are lowercase; shadow_record
            # validator expects uppercase canonical names.
            advisory_action = (
                raw_action.name if hasattr(raw_action, "name") else
                str(raw_action).upper() if raw_action else None
            )
            advisory_summary = self._directive_field(directive, "summary")
            advisory_conf = self._directive_field(directive, "confidence")
            focus = self._directive_field(directive, "focus")
            if focus is not None:
                advisory_focus = {
                    "target_type": self._directive_field(focus, "target_type"),
                    "target_id": self._directive_field(focus, "target_id"),
                    "highlight_region": self._directive_field(focus, "highlight_region"),
                }

        # Persist advisory record
        write_shadow_record(
            session_dir=session_dir,
            session_id=str(session_dir.name),
            run_id=str(getattr(attempt, "attempt_id", "")),
            mode=self._spine_mode,
            moment_id=str(top.get("moment", "NONE")),
            moment_confidence=float(top.get("confidence", 0.0) or 0.0),
            trigger_event_count=len(top.get("trigger_events", []) or []),
            advisory_action=advisory_action,
            advisory_summary=advisory_summary,
            advisory_focus=advisory_focus,
            advisory_confidence=float(advisory_conf) if isinstance(advisory_conf, (int, float)) else None,
            commands_count=commands_dispatched,
            error=None,
            policy_trace=(decision or {}).get("diagnostic"),
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

# INSTRUMENT CLASS: MEASUREMENT
"""
Quality-gated measurement flow for tap_tone_pi GUI.

Extracted from App class in app.py. These are standalone functions
that receive the App instance (or relevant state) to decouple
measurement logic from the main App class.
"""

from __future__ import annotations

import datetime
import json
import tkinter as tk
from tkinter import messagebox

# Optional imports (guarded by App-level feature flags)
try:
    from tap_tone_pi.core.analysis import analyze_tap

    HAS_DIRECT_ANALYSIS = True
except ImportError:
    HAS_DIRECT_ANALYSIS = False

try:
    from tap_tone_pi.core.quality_gate import check_quality
    from tap_tone_pi.core.quality_policy import Verdict

    HAS_QUALITY_GATE = True
except ImportError:
    HAS_QUALITY_GATE = False

try:
    from tap_tone_pi.core.auto_trigger import (
        record_audio_triggered,
        TriggerState,
    )

    HAS_AUTO_TRIGGER = True
except ImportError:
    HAS_AUTO_TRIGGER = False

try:
    import matplotlib  # noqa: F401

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def setup_quality_measure(app, entry_vars: list) -> tuple:
    """Setup for quality measurement.

    Returns (outdir, duration, sample_rate, point_id, device, point_dir, attempt_num, attempt_dir)
    or raises ValueError on invalid input.
    """
    from tap_tone_pi.core.user_config import get_saved_device

    outdir = app.outdir()
    duration = float(entry_vars[0].get())
    sample_rate = int(entry_vars[1].get())
    point_id = entry_vars[2].get().strip() or "point_001"

    saved = get_saved_device()
    device = saved.index if saved else None
    if saved:
        sample_rate = saved.sample_rate

    point_dir = outdir / point_id
    point_dir.mkdir(parents=True, exist_ok=True)

    existing = (
        [d for d in point_dir.iterdir() if d.name.startswith("attempt_")]
        if point_dir.exists()
        else []
    )
    attempt_num = len(existing) + 1
    attempt_dir = point_dir / f"attempt_{attempt_num:03d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    return (
        outdir,
        duration,
        sample_rate,
        point_id,
        device,
        point_dir,
        attempt_num,
        attempt_dir,
    )


def capture_with_auto_trigger(
    app,
    point_id: str,
    device,
    sample_rate: int,
    duration: float,
    progress_dlg,
):
    """Capture audio using auto-trigger mode. Returns capture result or None on failure."""
    app._set_status(f"Listening for tap ({point_id})...", "progress")
    app._update_trigger_listening_state(True)
    if progress_dlg:
        progress_dlg.set_stage(1, "🎤 Waiting for tap...")
        app.update()

    try:
        trigger_result = record_audio_triggered(
            device=device,
            sample_rate=sample_rate,
            post_trigger_seconds=duration,
            timeout_seconds=30.0,
        )

        app._update_trigger_listening_state(False)

        if not trigger_result.triggered:
            if progress_dlg:
                progress_dlg.destroy()
            if trigger_result.state == TriggerState.TIMEOUT:
                app._set_status("Timeout waiting for tap", "error")
                messagebox.showwarning("Timeout", "No tap detected within 30 seconds.")
            else:
                app._set_status(f"Auto-trigger failed: {trigger_result.error}", "error")
                messagebox.showerror(
                    "Error", f"Auto-trigger failed: {trigger_result.error}"
                )
            return None

        snr = trigger_result.trigger_rms / max(trigger_result.baseline_rms, 1e-6)
        app._set_status(f"Tap detected! (SNR: {snr:.1f}x)", "success")
        if progress_dlg:
            progress_dlg.set_stage(
                1, f"✓ Tap captured ({trigger_result.duration_seconds:.1f}s)"
            )
            app.update()

        class _CapResult:
            def __init__(self, audio, sr):
                self.audio = audio
                self.sample_rate = sr

        return _CapResult(trigger_result.audio, trigger_result.sample_rate)

    except Exception as e:
        app._update_trigger_listening_state(False)
        if progress_dlg:
            progress_dlg.destroy()
        app._set_status(f"Auto-trigger error: {e}", "error")
        messagebox.showerror("Error", f"Auto-trigger capture failed: {e}")
        return None


def capture_fixed_duration(
    app,
    point_id: str,
    device,
    sample_rate: int,
    duration: float,
    progress_dlg,
):
    """Capture audio using fixed-duration mode."""
    from tap_tone_pi.capture import record_audio

    app._set_status(f"Capturing {point_id}...", "progress")
    if progress_dlg:
        progress_dlg.set_stage(1, f"Recording for {duration}s...")
        app.update()

    return record_audio(
        device=device,
        sample_rate=sample_rate,
        channels=1,
        seconds=duration,
    )


def save_quality_measure_results(
    attempt_dir,
    cap,
    result,
    verdict,
) -> None:
    """Save audio, analysis, and quality check results."""
    from tap_tone_pi.io.wav import write_wav_int16

    audio_path = attempt_dir / "audio.wav"
    write_wav_int16(audio_path, cap.audio, cap.sample_rate)

    analysis_path = attempt_dir / "analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(
            {
                "dominant_hz": result.dominant_hz,
                "rms": float(result.rms),
                "confidence": float(result.confidence),
                "clipped": result.clipped,
                "peaks": [
                    {"freq_hz": p.freq_hz, "magnitude": float(p.magnitude)}
                    for p in result.peaks[:20]
                ],
            },
            f,
            indent=2,
        )

    quality_path = attempt_dir / "quality_check.json"
    with open(quality_path, "w") as f:
        json.dump(verdict.to_dict(), f, indent=2)


def show_quality_verdict_viewer(
    app,
    point_id: str,
    attempt_num: int,
    attempt_dir,
    outdir,
    verdict,
    result,
    entry_vars: list,
) -> None:
    """Show the quality verdict viewer dialog."""
    from tap_tone_pi.gui.quality_verdict import (
        QualityVerdictViewer,
        SpectrumViewer,
    )

    def on_accept():
        app._set_status(f"{point_id} accepted", "success")
        messagebox.showinfo("Accepted", f"Measurement saved to:\n{attempt_dir}")
        if HAS_MATPLOTLIB:
            SpectrumViewer(app, result, title=f"Spectrum: {point_id}")

    def on_retry():
        do_quality_measure(app, entry_vars)

    def on_override(reason: str):
        override_path = attempt_dir / "override.json"
        with open(override_path, "w") as f:
            json.dump(
                {
                    "reason": reason,
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                },
                f,
                indent=2,
            )
        app._set_status(f"{point_id} overridden", "warning")
        messagebox.showinfo(
            "Overridden", f"Measurement overridden and saved to:\n{attempt_dir}"
        )

    QualityVerdictViewer(
        app,
        verdict=verdict,
        result=result,
        on_accept=on_accept,
        on_retry=on_retry,
        on_override=on_override,
        session_dir=outdir,
        title=f"Quality Gate: {point_id} (attempt {attempt_num})",
    )


def do_quality_measure(app, entry_vars: list[tk.StringVar]) -> None:
    """Run quality-gated measurement (Phase 7 + Phase 8 enhancements)."""
    if not HAS_QUALITY_GATE or not HAS_DIRECT_ANALYSIS:
        messagebox.showerror("Error", "Quality gate modules not available")
        return

    (
        outdir,
        duration,
        sample_rate,
        point_id,
        device,
        point_dir,
        attempt_num,
        attempt_dir,
    ) = setup_quality_measure(app, entry_vars)

    progress_dlg = None
    try:
        from tap_tone_pi.gui.widgets import CaptureProgressDialog

        progress_dlg = CaptureProgressDialog(
            app, title=f"Capturing: {point_id} (attempt {attempt_num})"
        )
    except ImportError:
        pass

    try:
        # Stage 0: Preflight
        app._set_status(f"Preflight check for {point_id}...", "progress")
        if progress_dlg:
            progress_dlg.set_stage(0, "Checking device...")
            app.update()

        # Stage 1: Capture
        use_auto_trigger = (
            hasattr(app, "auto_trigger_var")
            and app.auto_trigger_var.get()
            and HAS_AUTO_TRIGGER
        )

        if use_auto_trigger:
            cap = capture_with_auto_trigger(
                app, point_id, device, sample_rate, duration, progress_dlg
            )
            if cap is None:
                return
        else:
            cap = capture_fixed_duration(
                app, point_id, device, sample_rate, duration, progress_dlg
            )

        # Stage 2: Analyze
        app._set_status(f"Analyzing {point_id}...", "progress")
        if progress_dlg:
            progress_dlg.set_stage(2, "Running FFT analysis...")
            app.update()

        result = analyze_tap(cap.audio, cap.sample_rate)

        # Stage 3: Quality check
        app._set_status(f"Quality check for {point_id}...", "progress")
        if progress_dlg:
            progress_dlg.set_stage(3, "Evaluating quality rules...")
            app.update()

        verdict = check_quality(
            analysis=result,
            sample_rate=cap.sample_rate,
            audio=cap.audio,
        )

        if progress_dlg:
            progress_dlg.destroy()
            progress_dlg = None

        save_quality_measure_results(attempt_dir, cap, result, verdict)

        # Update status based on verdict
        if verdict.verdict == Verdict.PASS:
            app._set_status(
                f"{point_id}: PASSED ({result.dominant_hz:.1f} Hz)", "success"
            )
        elif verdict.verdict == Verdict.WARN:
            app._set_status(f"{point_id}: WARNING - review required", "warning")
        else:
            app._set_status(f"{point_id}: FAILED - retry or override", "error")

        show_quality_verdict_viewer(
            app,
            point_id,
            attempt_num,
            attempt_dir,
            outdir,
            verdict,
            result,
            entry_vars,
        )

    except Exception as e:
        if progress_dlg:
            progress_dlg.destroy()
        app._set_status(f"Error: {e}", "error")
        messagebox.showerror("Error", f"Measurement failed: {e}")

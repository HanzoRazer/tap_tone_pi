#!/usr/bin/env python3
"""
tap_tone_pi CLI — Unified command dispatcher.

Canonical location: tap_tone_pi.cli.main

Usage:
    ttp setup                # Hardware setup wizard (run first!)
    ttp devices              # List audio devices
    ttp measure --out ./out  # Quality-gated measurement (blocks on FAIL)
    ttp record --out ./out   # Record single tap (QC recorded, not gated)
    ttp live --out ./out     # Continuous recording
    ttp quick                # Zero-config quick capture
    ttp gold-run ...         # Gold standard run
    ttp gui                  # Launch Tkinter GUI
    ttp phase2 ...           # Phase 2 ODS workflow
    ttp chladni ...          # Chladni pattern analysis
    ttp bending ...          # Bending MOE calculation
    ttp export-pack ...      # Export viewer pack ZIP from session
    ttp evidence-check ...   # Preflight validate session evidence artifacts
    ttp last                 # Show most recent session
    ttp sessions             # List all sessions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# Resolve project root for session directories
def _get_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return current.parent.parent.parent


PROJECT_ROOT = _get_project_root()
SESSION_ROOTS = [
    PROJECT_ROOT / "out",
    PROJECT_ROOT / "runs_phase2",
    PROJECT_ROOT / "runs",
]


def cmd_devices(_args: argparse.Namespace) -> int:
    """List available audio devices."""
    from tap_tone_pi.capture import list_devices

    devs = list_devices()
    if not devs:
        print("No audio devices found.")
        return 1

    print("\nAvailable audio devices:\n")
    for d in devs:
        inputs = d["max_input_channels"]
        outputs = d["max_output_channels"]
        marker = " *" if inputs > 0 else ""
        print(f"  [{d['index']:2d}] {d['name']}{marker}")
        print(f"       in={inputs}, out={outputs}, rate={d['default_samplerate']}")
    print("\n  * = has input channels (usable for capture)\n")
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    """Run pre-flight hardware check."""
    from tap_tone_pi.cli.preflight import run_preflight, print_preflight_result
    from tap_tone_pi.core.user_config import get_saved_device

    # Use saved device config if no device specified
    device = args.device
    sample_rate = args.sample_rate
    if device is None:
        saved = get_saved_device()
        if saved:
            device = saved.index
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device}] {saved.name}")

    result = run_preflight(
        device=device,
        sample_rate=sample_rate,
        duration=args.duration,
        quiet=False,
    )

    print("")
    print_preflight_result(result)

    return 0 if result.ok else 1


# -------------------------------------------------------------------------
# Directive Co-Render Helper (PR #3)
# -------------------------------------------------------------------------


def _maybe_render_directive(
    args: argparse.Namespace,
    session_dir: str | Path,
) -> None:
    """Print spine shadow directive block if ``--agent-directives`` is set.

    Reads persisted shadow output only — no spine execution.
    Silent on any error or missing files.
    """
    if not getattr(args, "agent_directives", False):
        return

    sd = Path(session_dir)
    try:
        from tap_tone_pi.agentic.spine.shadow_record import load_latest_shadow_record
        from tap_tone_pi.agent.render import render_cli_shadow_record

        rec = load_latest_shadow_record(sd)
        if rec is None:
            return

        block = render_cli_shadow_record(
            rec,
            color=getattr(args, "color", True),
            verbose=getattr(args, "verbose_directives", False),
        )
        if block and block.strip():
            print("\n" + block)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        # Silent by default — directive is additive, never break CLI
        return


def cmd_record(args: argparse.Namespace) -> int:
    """Record a single tap and analyze (QC recorded, not gated)."""
    from tap_tone_pi.capture import record_audio
    from tap_tone_pi.cli.validators import (
        validate_device_index,
        validate_output_dir,
        validate_sample_rate,
        validate_duration,
    )
    from tap_tone_pi.core.analysis import analyze_tap
    from tap_tone_pi.core.config import AnalysisConfig, CaptureConfig
    from tap_tone_pi.core.quality_gate import check_quality
    from tap_tone_pi.core.user_config import get_saved_device
    from tap_tone_pi.io.storage import persist_capture

    # Validate inputs early with clear error messages
    validate_output_dir(args.out)
    validate_sample_rate(args.sample_rate)
    validate_duration(args.seconds)

    # Use saved device config if no device specified
    device = args.device
    sample_rate = args.sample_rate
    if device is None:
        saved = get_saved_device()
        if saved:
            device = saved.index
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device}] {saved.name}")

    # Validate device exists
    validate_device_index(device)

    cap_cfg = CaptureConfig(
        device=device,
        sample_rate=sample_rate,
        channels=args.channels,
        seconds=args.seconds,
    )
    an_cfg = AnalysisConfig()

    cap = record_audio(
        device=cap_cfg.device,
        sample_rate=cap_cfg.sample_rate,
        channels=cap_cfg.channels,
        seconds=cap_cfg.seconds,
        show_countdown=True,
    )

    print("Analyzing...")
    res = analyze_tap(
        cap.audio,
        cap.sample_rate,
        highpass_hz=an_cfg.highpass_hz,
        peak_min_hz=an_cfg.peak_min_hz,
        peak_max_hz=an_cfg.peak_max_hz,
        peak_min_prominence=an_cfg.peak_min_prominence,
        peak_min_spacing_hz=an_cfg.peak_min_spacing_hz,
        max_peaks=an_cfg.max_peaks,
    )

    # Quality Gate check
    # NOTE: cmd_record always emits QC evidence but does not block on FAIL.
    # Gating (block/override loop) belongs in cmd_measure/operator loop.
    qc = check_quality(res, sample_rate=cap.sample_rate, audio=cap.audio)

    _print_summary(args.label, res)

    persisted = persist_capture(
        out_dir=args.out,
        label=args.label,
        sample_rate=cap.sample_rate,
        audio=cap.audio,
        analysis=res,
    )

    # Write quality_check.json alongside analysis.json/audio.wav (atomic write)
    qc_path = persisted.capture_dir / "quality_check.json"
    qc_tmp = qc_path.with_suffix(".json.tmp")
    qc_tmp.write_text(
        json.dumps(qc.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    qc_tmp.replace(qc_path)

    # Console QC summary (keeps headless workflows friendly)
    if getattr(args, "agent", False):
        from tap_tone_pi.agent.messages import (
            AgentContext,
            build_agent_message,
            render_agent_message_cli,
        )

        ctx = AgentContext(
            workflow="record",
            point_id=args.label,
            attempt_num=1,
            max_attempts=1,
            device_name=str(cap_cfg.device or "default"),
            sample_rate=cap.sample_rate,
            policy_version=getattr(qc, "policy_version", None),
            user_stage="novice",
            show_details=getattr(args, "expert", False),
            expert_mode=getattr(args, "expert", False),
        )
        msg = build_agent_message(ctx, qc)
        print(render_agent_message_cli(msg))
    else:
        rules = (
            ",".join([tr.rule.rule_id for tr in qc.triggered_rules])
            if qc.triggered_rules
            else "none"
        )
        print(f"QC: {qc.verdict.value.upper()} rules={rules}")
    print(f"Wrote: {persisted.capture_dir}")
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    """Continuous tap recording mode."""
    from tap_tone_pi.core.user_config import get_saved_device

    # Use saved config if no device specified
    device = args.device
    sample_rate = args.sample_rate
    if device is None:
        saved = get_saved_device()
        if saved:
            device = saved.index
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device}] {saved.name}")

    print("Live mode: press Ctrl+C to stop. Tap, wait, tap...")
    i = 0
    try:
        while True:
            i += 1
            label = args.label or f"live_{i:03d}"
            ns = argparse.Namespace(
                device=device,
                sample_rate=sample_rate,
                channels=args.channels,
                seconds=args.seconds,
                out=args.out,
                label=label,
            )
            rc = cmd_record(ns)
            if rc != 0:
                return rc
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def cmd_quick(args: argparse.Namespace) -> int:
    """Zero-config quick capture: auto-detect device, capture, analyze, display."""
    from tap_tone_pi.capture import auto_detect_device, record_audio
    from tap_tone_pi.core.analysis import analyze_tap
    from tap_tone_pi.core.user_config import get_saved_device

    # Try saved config first, then auto-detect
    saved = get_saved_device()
    if saved:
        device = saved.index
        sample_rate = saved.sample_rate
        print(f"Quick capture: using saved device [{device}] {saved.name}")
    else:
        device = auto_detect_device()
        sample_rate = 48000
        device_name = "system default" if device is None else f"device {device}"
        print(f"Quick capture: using {device_name}")
        print("  (Tip: run 'ttp setup' to save your preferred device)")

    # Capture
    print("Recording 2.5s...")
    cap = record_audio(
        device=device,
        sample_rate=sample_rate,
        channels=1,
        seconds=2.5,
        show_countdown=True,
    )

    # Analyze
    print("Analyzing...")
    res = analyze_tap(cap.audio, cap.sample_rate)

    # Print results
    _print_summary(None, res)

    # Optionally show spectrum
    if args.plot:
        try:
            import matplotlib.pyplot as plt

            plt.figure(figsize=(10, 4))
            plt.semilogy(
                res.spectrum_freq_hz, res.spectrum_mag + 1e-10, "b-", linewidth=0.5
            )
            for peak in res.peaks[:5]:
                plt.axvline(peak.freq_hz, color="r", linestyle="--", alpha=0.5)
                plt.annotate(
                    f"{peak.freq_hz:.0f} Hz",
                    (peak.freq_hz, peak.magnitude),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                    color="red",
                )
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Magnitude")
            plt.xlim(20, 2000)
            plt.title(f"Quick Capture — Dominant: {res.dominant_hz:.1f} Hz")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("(matplotlib not installed, skipping plot)")

    return 0


def _list_directive_events_cli(session_dir: Path, args: argparse.Namespace) -> int:
    """List directive events (early exit handler)."""
    try:
        from tap_tone_pi.agentic.spine.directive_history import load_directive_events

        rows = load_directive_events(
            session_dir,
            limit=int(getattr(args, "directive_events_limit", 10)),
        )
        if not rows:
            print("Directive events: none")
            return 0
        print("Directive events:")
        for r in rows:
            did = r.directive_id or "-"
            comp = r.component or "-"
            ts = r.timestamp or "-"
            print(f"  {ts}  {r.event_type}  directive_id={did}  component={comp}")
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        print("Directive events: none")
    return 0


def _make_measure_state_callback(args: argparse.Namespace):
    """Create state callback for measure CLI feedback."""
    from tap_tone_pi.workflow import LoopState

    def on_state(state: LoopState, data: dict) -> None:
        if state == LoopState.PREFLIGHT:
            print("Preflight checks...")
        elif state == LoopState.READY:
            print(
                f"Ready for capture: {data.get('point_id')} (attempt {data.get('attempt')})"
            )
        elif state == LoopState.LISTENING:
            timeout = data.get("timeout", 30)
            print(f"Listening for tap... (timeout: {timeout:.0f}s)")
        elif state == LoopState.CAPTURING:
            if data.get("triggered"):
                print("Tap detected! Recording...")
            else:
                print(f"Recording {args.seconds}s...")
        elif state == LoopState.ANALYZING:
            print("Analyzing...")
        elif state == LoopState.GATING:
            print("Checking quality...")

    return on_state


def _show_analysis_summary(result) -> None:
    """Display analysis summary from measurement result."""
    if not result.analysis:
        return
    print(f"\nDominant: {result.analysis.dominant_hz or 'n/a'} Hz")
    print(
        f"RMS: {result.analysis.rms:.4f}  Confidence: {result.analysis.confidence:.2f}"
    )
    if result.analysis.peaks:
        print("Top peaks:")
        for pk in result.analysis.peaks[:5]:
            print(f"  - {pk.freq_hz:7.1f} Hz  (mag: {pk.magnitude:.3f})")


def _handle_verdict_display(
    result,
    args: argparse.Namespace,
    cfg,
    session_tracker,
    point_id: str,
    attempt_num: int,
    max_attempts: int,
    device,
    sample_rate: int,
    save_config_fn,
    update_ftue_fn,
) -> None:
    """Handle verdict display and FTUE updates."""
    from tap_tone_pi.core.quality_gate import format_verdict_summary

    if not result.verdict:
        return

    if session_tracker is not None:
        from tap_tone_pi.agent.messages import format_verdict_summary_agent

        session_tracker.record_verdict(result.verdict)
        cfg.ftue = update_ftue_fn(
            cfg.ftue,
            verdict=result.verdict,
            policy_version=getattr(result.verdict, "policy_version", None),
            increment_session=False,
        )
        save_config_fn(cfg)

        ctx = session_tracker.make_context(
            workflow="measure",
            point_id=point_id,
            attempt_num=attempt_num,
            max_attempts=max_attempts,
            device_name=str(device or "default"),
            sample_rate=sample_rate,
            policy_version=getattr(result.verdict, "policy_version", None),
            pass_count_lifetime=cfg.ftue.pass_count_lifetime,
            session_count_lifetime=cfg.ftue.session_count_lifetime,
            override_count_lifetime=cfg.ftue.override_count_lifetime,
            seen_rule_ids=tuple(cfg.ftue.seen_rule_ids),
            show_details=True,
            expert_mode=getattr(args, "expert", False),
        )
        print("\n" + format_verdict_summary_agent(ctx, result.verdict))
    else:
        print(f"\n{format_verdict_summary(result.verdict)}")


def _handle_measure_error(attempt_num: int, max_attempts: int, error: str) -> tuple:
    """Handle measurement error, return (should_continue, exit_code)."""
    print(f"\nERROR: {error}")
    if attempt_num < max_attempts:
        retry = input("Retry? [Y/n]: ").strip().lower()
        if retry in ("n", "no"):
            print("Measurement aborted.")
            return False, 1
        return True, None
    else:
        print("Max attempts reached.")
        return False, 1


def _handle_pass_verdict(loop, result) -> int:
    """Handle PASS verdict, return exit code."""
    print("\nMeasurement ACCEPTED.")
    print(f"Saved to: {loop.store.get_attempt_dir(result.attempt)}")
    return 0


def _handle_warn_verdict(loop, result) -> tuple:
    """Handle WARN verdict, return (accepted, exit_code)."""
    print("\nMeasurement has warnings.")
    accept = input("Accept anyway? [Y/n]: ").strip().lower()
    if accept not in ("n", "no"):
        print("Measurement ACCEPTED (with warnings).")
        print(f"Saved to: {loop.store.get_attempt_dir(result.attempt)}")
        return True, 0
    return False, None


def _handle_fail_verdict(
    loop,
    result,
    point_id: str,
    attempt_num: int,
    max_attempts: int,
    cfg,
    save_config_fn,
) -> tuple:
    """Handle FAIL verdict, return (should_continue, exit_code)."""
    print("\nMeasurement FAILED quality gate.")

    if attempt_num < max_attempts:
        retry = input("Retry? [Y/n]: ").strip().lower()
        if retry in ("n", "no"):
            override = input("Override with reason? [leave blank to abort]: ").strip()
            if override:
                loop.override_failed(point_id, override)
                cfg.ftue.override_count_lifetime += 1
                save_config_fn(cfg)
                print(f"Measurement OVERRIDDEN: {override}")
                print(f"Saved to: {loop.store.get_attempt_dir(result.attempt)}")
                return False, 0
            print("Measurement aborted.")
            return False, 1
        return True, None
    else:
        override = input(
            "Max attempts reached. Override with reason? [leave blank to fail]: "
        ).strip()
        if override:
            loop.override_failed(point_id, override)
            cfg.ftue.override_count_lifetime += 1
            save_config_fn(cfg)
            print(f"Measurement OVERRIDDEN: {override}")
            return False, 0
        print("Measurement FAILED.")
        return False, 1


def cmd_measure(args: argparse.Namespace) -> int:
    """Quality-gated measurement with operator loop."""
    from tap_tone_pi.core.user_config import (
        get_saved_device,
        load_config,
        save_config,
        UserConfig,
        update_ftue_from_verdict,
    )
    from tap_tone_pi.core.quality_policy import Verdict
    from tap_tone_pi.workflow import OperatorLoop

    # ---- FTUE: load once per measure session ----
    cfg = load_config() or UserConfig()
    cfg.ftue = update_ftue_from_verdict(
        cfg.ftue, verdict=None, policy_version=None, increment_session=True
    )
    save_config(cfg)

    # Resolve device
    device = args.device
    sample_rate = args.sample_rate
    if device is None:
        saved = get_saved_device()
        if saved:
            device = saved.index
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device}] {saved.name}")

    # Pre-flight hardware check
    if not getattr(args, "skip_preflight", False):
        from tap_tone_pi.cli.preflight import require_preflight
        require_preflight(device=device, sample_rate=sample_rate)

    # Create session directory
    session_dir = Path(args.out)
    session_dir.mkdir(parents=True, exist_ok=True)

    # Directive event listing (early exit)
    if getattr(args, "list_directive_events", False):
        return _list_directive_events_cli(session_dir, args)

    # Create operator loop
    loop = OperatorLoop(
        session_dir=session_dir, callback=_make_measure_state_callback(args)
    )

    max_attempts = args.max_attempts
    point_id = args.point or "point_001"

    # PR7: single source of session history
    session_tracker = None
    if getattr(args, "agent", False):
        from tap_tone_pi.agent.messages import SessionTracker

        session_tracker = SessionTracker()

    for attempt_num in range(1, max_attempts + 1):
        print(f"\n--- Attempt {attempt_num}/{max_attempts} ---")

        result = loop.run_single(
            point_id=point_id,
            device=device,
            sample_rate=sample_rate,
            duration=args.seconds,
            auto_trigger=getattr(args, "auto_trigger", False),
            auto_trigger_timeout=getattr(args, "trigger_timeout", 30.0),
        )

        if result.error:
            should_continue, exit_code = _handle_measure_error(
                attempt_num, max_attempts, result.error
            )
            if not should_continue:
                return exit_code
            continue

        _show_analysis_summary(result)

        _handle_verdict_display(
            result,
            args,
            cfg,
            session_tracker,
            point_id,
            attempt_num,
            max_attempts,
            device,
            sample_rate,
            save_config,
            update_ftue_from_verdict,
        )

        _maybe_render_directive(args, session_dir)

        if result.verdict.verdict == Verdict.PASS:
            return _handle_pass_verdict(loop, result)

        elif result.verdict.verdict == Verdict.WARN:
            accepted, exit_code = _handle_warn_verdict(loop, result)
            if accepted:
                return exit_code
            # else: continue to retry

        else:  # FAIL
            should_continue, exit_code = _handle_fail_verdict(
                loop,
                result,
                point_id,
                attempt_num,
                max_attempts,
                cfg,
                save_config,
            )
            if not should_continue:
                return exit_code

    return 1


def cmd_last(args: argparse.Namespace) -> int:
    """Show/open the most recent session directory."""
    sessions = _find_all_sessions()

    if not sessions:
        print("No sessions found.")
        return 1

    latest = max(sessions, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest.stat().st_mtime)

    print(f"\nLatest session: {latest}")
    print(f"  Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Contents:")

    total_size = 0
    for f in sorted(latest.rglob("*")):
        if f.is_file():
            rel = f.relative_to(latest)
            size = f.stat().st_size
            total_size += size
            size_str = _format_size(size)
            print(f"    {rel}  ({size_str})")

    print(f"  Total: {_format_size(total_size)}\n")

    if args.open:
        _open_path(latest)

    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    """List all sessions with metadata."""
    sessions = _find_all_sessions()

    if not sessions:
        print("No sessions found.")
        return 1

    # Sort by modification time (newest first)
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Limit if specified
    if args.limit:
        sessions = sessions[: args.limit]

    print(f"\n{'#':>3}  {'Type':<10}  {'Date':<20}  {'Path'}")
    print("-" * 80)

    for i, session in enumerate(sessions, 1):
        mtime = datetime.fromtimestamp(session.stat().st_mtime)

        # Determine session type
        if "phase2" in str(session).lower():
            stype = "phase2"
        elif "bend" in session.name.lower():
            stype = "bending"
        elif "chladni" in session.name.lower():
            stype = "chladni"
        else:
            stype = "tap"

        # Try to get point count from session.jsonl
        point_count = _count_session_points(session)
        points_str = f" ({point_count} pts)" if point_count else ""

        rel_path = (
            session.relative_to(PROJECT_ROOT)
            if session.is_relative_to(PROJECT_ROOT)
            else session
        )
        print(
            f"{i:3d}  {stype:<10}  {mtime.strftime('%Y-%m-%d %H:%M'):<20}  {rel_path}{points_str}"
        )

    print()
    return 0


def cmd_gold_run(args: argparse.Namespace) -> int:
    """Dispatch to gold-run module."""
    from tap_tone_pi.cli.gold_run import main as gold_run_main

    gold_argv = []
    gold_argv.extend(["--specimen-id", args.specimen_id])
    gold_argv.extend(["--device", str(args.device)])
    gold_argv.extend(["--out-dir", str(args.out_dir)])
    if args.points != 3:
        gold_argv.extend(["--points", str(args.points)])
    if args.dry_run:
        gold_argv.append("--dry-run")
    if args.json:
        gold_argv.append("--json")
    if args.ingest:
        gold_argv.append("--ingest")
    if args.session_id:
        gold_argv.extend(["--session-id", args.session_id])
    if args.batch_label:
        gold_argv.extend(["--batch-label", args.batch_label])
    return gold_run_main(gold_argv)


def cmd_gui(_args: argparse.Namespace) -> int:
    """Launch the Tkinter GUI."""
    from tap_tone_pi.gui.app import App

    app = App()
    app.mainloop()
    return 0


def cmd_phase2(args: argparse.Namespace) -> int:
    """Run Phase 2 ODS workflow."""
    import subprocess

    argv = [sys.executable, "scripts/phase2_slice.py", "run"]
    if args.synthetic:
        argv.append("--synthetic")
    if args.grid:
        argv.extend(["--grid", args.grid])
    if args.out:
        argv.extend(["--out", args.out])
    if args.device:
        argv.extend(["--device", str(args.device)])

    return subprocess.call(argv, cwd=str(PROJECT_ROOT))


def cmd_chladni(args: argparse.Namespace) -> int:
    """Run Chladni pattern analysis."""
    import subprocess

    if args.subcommand == "peaks":
        argv = [
            sys.executable,
            "-m",
            "tap_tone_pi.chladni.peaks_from_wav",
            "--wav",
            args.wav,
            "--out",
            args.out,
        ]
        if args.min_hz:
            argv.extend(["--min-hz", str(args.min_hz)])
        if args.max_hz:
            argv.extend(["--max-hz", str(args.max_hz)])
    elif args.subcommand == "index":
        argv = [
            sys.executable,
            "-m",
            "tap_tone_pi.chladni.index_patterns",
            "--peaks-json",
            args.peaks_json,
            "--plate-id",
            args.plate_id,
            "--out",
            args.out,
            "--images",
            *args.images,
        ]
    else:
        print(f"Unknown chladni subcommand: {args.subcommand}", file=sys.stderr)
        return 1

    return subprocess.call(argv, cwd=str(PROJECT_ROOT))


def cmd_bending(args: argparse.Namespace) -> int:
    """Run bending MOE calculation."""
    import subprocess

    argv = [
        sys.executable,
        "-m",
        "tap_tone_pi.bending.merge_and_moe",
        "--load",
        args.load,
        "--disp",
        args.disp,
        "--out-dir",
        args.out_dir,
        "--method",
        args.method,
        "--span",
        str(args.span),
        "--width",
        str(args.width),
        "--thickness",
        str(args.thickness),
    ]
    if args.rate:
        argv.extend(["--rate", str(args.rate)])

    return subprocess.call(argv, cwd=str(PROJECT_ROOT))


def cmd_export_pack(args: argparse.Namespace) -> int:
    """Export a session as viewer_pack_v1 ZIP."""
    import subprocess

    from tap_tone_pi.cli.validators import confirm_overwrite

    # Consistent with other CLI commands - resolve against PROJECT_ROOT
    session_path = Path(args.session)
    if not session_path.is_absolute():
        session_path = (PROJECT_ROOT / session_path).resolve()

    # Output path: allow relative-to-CWD for convenience
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path

    if not session_path.exists():
        print(f"Session not found: {session_path}", file=sys.stderr)
        return 1

    # Confirm overwrite if output exists
    confirm_overwrite(out_path, force=getattr(args, "force", False))

    # Guardrail: exporter expects Phase 2 session structure
    grid_json = session_path / "grid.json"
    if not grid_json.exists():
        print(
            "export-pack expects a Phase 2 session directory.\n"
            f"Missing grid.json in: {session_path}",
            file=sys.stderr,
        )
        return 1

    export_script = PROJECT_ROOT / "scripts" / "export" / "viewer_pack_v1_export.py"
    if not export_script.exists():
        print(f"Exporter script not found: {export_script}", file=sys.stderr)
        return 1

    argv = [
        sys.executable,
        str(export_script),
        "--session",
        str(session_path),
        "--out",
        str(out_path),
    ]

    # Run export
    rc = subprocess.call(argv, cwd=str(PROJECT_ROOT))
    if rc != 0:
        return rc

    # Optional ZIP validation
    if args.validate:
        validate_script = PROJECT_ROOT / "scripts" / "viewer_pack_validate.py"
        if not validate_script.exists():
            print(f"ZIP validator script not found: {validate_script}", file=sys.stderr)
            return 1

        v_argv = [
            sys.executable,
            str(validate_script),
            str(out_path),
        ]

        # Passthrough flags
        if args.strict:
            v_argv.append("--strict")
        if args.json:
            v_argv.append("--json")

        v_rc = subprocess.call(v_argv, cwd=str(PROJECT_ROOT))
        if v_rc != 0:
            return v_rc

    print(f"Wrote: {out_path}")
    return 0


def cmd_evidence_check(args: argparse.Namespace) -> int:
    """Preflight validator for session evidence artifacts."""
    from tap_tone_pi.validate.evidence_check import scan_session, render_human

    session_path = Path(args.session)
    if not session_path.is_absolute():
        session_path = (PROJECT_ROOT / session_path).resolve()

    if not session_path.exists():
        print(f"Session not found: {session_path}", file=sys.stderr)
        return 1

    report = scan_session(
        session_dir=session_path,
        strict=bool(args.strict),
        fail_on_warn=bool(args.fail_on_warn),
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_human(report))

    return report.exit_code


def cmd_completion(args: argparse.Namespace) -> int:
    """Generate shell completion script."""
    if args.shell == "bash":
        print(_bash_completion())
    elif args.shell == "zsh":
        print(_zsh_completion())
    elif args.shell == "fish":
        print(_fish_completion())
    else:
        print(f"Unknown shell: {args.shell}", file=sys.stderr)
        return 1
    return 0


# --- Helper functions ---


def _print_summary(label: str | None, res) -> None:
    """Print analysis summary to console."""
    print("")
    if label:
        print(f"Label: {label}")
    print(f"Dominant: {res.dominant_hz if res.dominant_hz else 'n/a'} Hz")
    print(
        f"RMS: {res.rms:.6f}   Clipped: {res.clipped}   Confidence: {res.confidence:.2f}"
    )
    if res.peaks:
        print("Top peaks:")
        for p in res.peaks[:8]:
            print(f"  - {p.freq_hz:8.2f} Hz   mag={p.magnitude:.3f}")
    else:
        print("No peaks detected (try higher gain or quieter room).")
    print("")


def _find_all_sessions() -> list[Path]:
    """Find all session directories across known roots."""
    sessions = []
    prefixes = ("session_", "capture_", "bend_", "chladni_", "gold_")

    for root in SESSION_ROOTS:
        if root.exists():
            for d in root.iterdir():
                if d.is_dir() and any(d.name.startswith(p) for p in prefixes):
                    sessions.append(d)
            # Also check one level deeper for date-organized sessions
            for sub in root.iterdir():
                if sub.is_dir():
                    for d in sub.iterdir():
                        if d.is_dir() and any(d.name.startswith(p) for p in prefixes):
                            sessions.append(d)

    return sessions


def _count_session_points(session_dir: Path) -> int | None:
    """Count capture points from session.jsonl if present."""
    jsonl = session_dir / "session.jsonl"
    if jsonl.exists():
        try:
            return sum(1 for _ in jsonl.open())
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass
    return None


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _open_path(path: Path) -> None:
    """Open a path in the system file manager."""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)])


def _bash_completion() -> str:
    """Generate bash completion script."""
    return """
_ttp_completions() {
    local commands="setup devices preflight measure record live quick gold-run gui phase2 chladni bending export-pack evidence-check last sessions completion"
    COMPREPLY=($(compgen -W "$commands" -- "${COMP_WORDS[COMP_CWORD]}"))
}
complete -F _ttp_completions ttp
complete -F _ttp_completions tap-tone
"""


def _zsh_completion() -> str:
    """Generate zsh completion script."""
    return """
#compdef ttp tap-tone

_ttp() {
    local commands=(
        'setup:Hardware setup wizard (run first!)'
        'devices:List audio devices'
        'preflight:Run pre-flight hardware check'
        'measure:Quality-gated measurement (recommended)'
        'record:Record one window and analyze'
        'live:Loop record+analyze'
        'quick:Zero-config quick capture'
        'gold-run:One-command Gold Standard Run'
        'gui:Launch Tkinter GUI'
        'phase2:Phase 2 ODS workflow'
        'chladni:Chladni pattern analysis'
        'bending:Bending MOE calculation'
        'export-pack:Export viewer pack ZIP from session'
        'evidence-check:Preflight validate session evidence artifacts'
        'last:Show most recent session'
        'sessions:List all sessions'
        'completion:Generate shell completion'
    )
    _describe 'command' commands
}

compdef _ttp ttp tap-tone
"""


def _fish_completion() -> str:
    """Generate fish completion script."""
    return """
complete -c ttp -f -n "__fish_use_subcommand" -a setup -d "Hardware setup wizard (run first!)"
complete -c ttp -f -n "__fish_use_subcommand" -a devices -d "List audio devices"
complete -c ttp -f -n "__fish_use_subcommand" -a preflight -d "Run pre-flight hardware check"
complete -c ttp -f -n "__fish_use_subcommand" -a measure -d "Quality-gated measurement (recommended)"
complete -c ttp -f -n "__fish_use_subcommand" -a record -d "Record one window and analyze"
complete -c ttp -f -n "__fish_use_subcommand" -a live -d "Loop record+analyze"
complete -c ttp -f -n "__fish_use_subcommand" -a quick -d "Zero-config quick capture"
complete -c ttp -f -n "__fish_use_subcommand" -a gold-run -d "One-command Gold Standard Run"
complete -c ttp -f -n "__fish_use_subcommand" -a gui -d "Launch Tkinter GUI"
complete -c ttp -f -n "__fish_use_subcommand" -a phase2 -d "Phase 2 ODS workflow"
complete -c ttp -f -n "__fish_use_subcommand" -a chladni -d "Chladni pattern analysis"
complete -c ttp -f -n "__fish_use_subcommand" -a bending -d "Bending MOE calculation"
complete -c ttp -f -n "__fish_use_subcommand" -a export-pack -d "Export viewer pack ZIP from session"
complete -c ttp -f -n "__fish_use_subcommand" -a evidence-check -d "Preflight validate session evidence artifacts"
complete -c ttp -f -n "__fish_use_subcommand" -a last -d "Show most recent session"
complete -c ttp -f -n "__fish_use_subcommand" -a sessions -d "List all sessions"
complete -c ttp -f -n "__fish_use_subcommand" -a completion -d "Generate shell completion"

complete -c tap-tone -w ttp
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the unified CLI argument parser."""
    epilog = """Quick Start:
  ttp setup              # First time? Run hardware wizard
  ttp devices            # List audio devices
  ttp quick              # Zero-config capture (auto-detect)
  ttp measure --out ./s1 # Quality-gated measurement session

Common Workflows:
  ttp gold-run --specimen-id "SG-001" --device 1 --out-dir ./runs
  ttp phase2 --grid grid.json --out ./runs_phase2
  ttp export-pack --session ./runs_phase2/session_* --out pack.zip

Documentation: https://github.com/HanzoRazer/tap_tone_pi
"""
    p = argparse.ArgumentParser(
        prog="ttp",
        description="Tap Tone Pi — Acoustic measurement instrument (v2.0.0)",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # setup (wizard) - run first!
    from tap_tone_pi.cli.wizard import run_wizard

    p_setup = sub.add_parser("setup", help="Hardware setup wizard (run first!)")
    p_setup.add_argument(
        "--reset", action="store_true", help="Clear saved config and re-run"
    )
    p_setup.add_argument(
        "--show", action="store_true", help="Show current saved config"
    )
    p_setup.set_defaults(fn=run_wizard)

    # devices
    p_dev = sub.add_parser("devices", help="List audio devices")
    p_dev.set_defaults(fn=cmd_devices)

    # preflight (hardware check)
    p_pre = sub.add_parser(
        "preflight",
        help="Run pre-flight hardware check",
        epilog="""Examples:
  ttp preflight               # Check default/saved device
  ttp preflight --device 2    # Check specific device
  ttp preflight --duration 1  # Longer test capture (1 second)

The preflight command verifies your audio hardware is ready:
- Device exists and can be opened
- Audio levels are detectable (not silent)
- No clipping in test capture
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_pre.add_argument("--device", type=int, default=None, help="Device index to test")
    p_pre.add_argument("--sample-rate", type=int, default=48000, help="Sample rate Hz")
    p_pre.add_argument("--duration", type=float, default=0.5, help="Test duration seconds")
    p_pre.set_defaults(fn=cmd_preflight)

    # record
    p_rec = sub.add_parser(
        "record",
        help="Record one window and analyze",
        epilog="""Examples:
  ttp record --out ./session1
  ttp record --out ./session1 --device 2 --seconds 3.0
  ttp record --out ./session1 --label "bridge_A1" --agent
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rec.add_argument("--device", type=int, default=None, help="Input device index")
    p_rec.add_argument("--sample-rate", type=int, default=48000)
    p_rec.add_argument("--channels", type=int, default=1)
    p_rec.add_argument("--seconds", type=float, default=2.5)
    p_rec.add_argument("--out", type=str, required=True, help="Output directory")
    p_rec.add_argument("--label", type=str, default=None, help="Tap point label")
    p_rec.add_argument(
        "--agent", action="store_true", help="Use agent-formatted QC output"
    )
    p_rec.add_argument(
        "--expert", action="store_true", help="More detailed agent output"
    )
    p_rec.add_argument(
        "--agent-directives",
        action="store_true",
        dest="agent_directives",
        help="Print advisory directive summary from spine shadow outputs (if available)",
    )
    p_rec.add_argument(
        "--verbose-directives",
        action="store_true",
        dest="verbose_directives",
        help="Include directive debug details (trigger counts, ids). Requires --agent-directives",
    )
    p_rec.set_defaults(fn=cmd_record)

    # live
    p_live = sub.add_parser("live", help="Loop record+analyze")
    p_live.add_argument("--device", type=int, default=None)
    p_live.add_argument("--sample-rate", type=int, default=48000)
    p_live.add_argument("--channels", type=int, default=1)
    p_live.add_argument("--seconds", type=float, default=2.5)
    p_live.add_argument("--out", type=str, required=True)
    p_live.add_argument("--label", type=str, default=None)
    p_live.set_defaults(fn=cmd_live)

    # quick (NEW!)
    p_quick = sub.add_parser(
        "quick",
        help="Zero-config quick capture (auto-detect device)",
        epilog="""Examples:
  ttp quick           # Capture and show frequency analysis
  ttp quick --plot    # Also display spectrum plot

The quick command auto-detects your audio device and captures a single
tap without requiring any configuration. Great for testing your setup.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_quick.add_argument("--plot", action="store_true", help="Show spectrum plot")
    p_quick.set_defaults(fn=cmd_quick)

    # measure (NEW! - quality-gated)
    p_meas = sub.add_parser(
        "measure",
        help="Quality-gated measurement with operator loop",
        epilog="""Examples:
  ttp measure --out ./session1                    # Basic measurement
  ttp measure --out ./session1 --auto-trigger     # Wait for tap onset
  ttp measure --out ./session1 --agent --expert   # Detailed agent output
  ttp measure --out ./session1 --point "A1"       # Named measurement point

The measure command enforces quality gates. If a capture fails QC,
you'll be prompted to retry or override with a reason.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_meas.add_argument("--device", type=int, default=None, help="Input device index")
    p_meas.add_argument("--sample-rate", type=int, default=48000, help="Sample rate Hz")
    p_meas.add_argument("--seconds", type=float, default=2.5, help="Capture duration")
    p_meas.add_argument(
        "--out", type=str, required=True, help="Session output directory"
    )
    p_meas.add_argument(
        "--point", type=str, default=None, help="Point ID (default: point_001)"
    )
    p_meas.add_argument(
        "--max-attempts", type=int, default=3, help="Max retry attempts"
    )
    p_meas.add_argument(
        "--agent", action="store_true", help="Use agent-formatted workflow output"
    )
    p_meas.add_argument(
        "--expert", action="store_true", help="More detailed agent output"
    )
    p_meas.add_argument(
        "--auto-trigger",
        action="store_true",
        dest="auto_trigger",
        help="Wait for tap onset before recording (Phase 10)",
    )
    p_meas.add_argument(
        "--trigger-timeout",
        type=float,
        default=30.0,
        help="Auto-trigger timeout in seconds (default: 30)",
    )
    p_meas.add_argument(
        "--agent-directives",
        action="store_true",
        dest="agent_directives",
        help="Print advisory directive summary from spine shadow outputs (if available)",
    )
    p_meas.add_argument(
        "--verbose-directives",
        action="store_true",
        dest="verbose_directives",
        help="Include directive debug details (trigger counts, ids). Requires --agent-directives",
    )
    p_meas.add_argument(
        "--list-directive-events",
        action="store_true",
        dest="list_directive_events",
        help="List recent directive outcome events (reads events.jsonl, no spine execution).",
    )
    p_meas.add_argument(
        "--directive-events-limit",
        type=int,
        default=10,
        dest="directive_events_limit",
        help="Max number of directive events to show (default: 10). Requires --list-directive-events.",
    )
    p_meas.add_argument(
        "--skip-preflight",
        action="store_true",
        dest="skip_preflight",
        help="Skip pre-flight hardware check (not recommended)",
    )
    p_meas.set_defaults(fn=cmd_measure)

    # gold-run
    p_gold = sub.add_parser(
        "gold-run",
        help="One-command Gold Standard Run",
        epilog="""Examples:
  ttp gold-run --specimen-id "SG-001" --device 1 --out-dir ./runs
  ttp gold-run --specimen-id "SG-001" --device 1 --out-dir ./runs --points 5
  ttp gold-run --specimen-id "SG-001" --device 1 --out-dir ./runs --dry-run
  ttp gold-run --specimen-id "SG-001" --device 1 --out-dir ./runs --ingest

The gold-run command captures multiple points in sequence and optionally
uploads to ToolBox for analysis.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_gold.add_argument("--specimen-id", required=True, help="Specimen identifier")
    p_gold.add_argument("--device", required=True, help="Audio device")
    p_gold.add_argument("--out-dir", required=True, help="Output directory")
    p_gold.add_argument("--points", type=int, default=3)
    p_gold.add_argument("--session-id", help="Custom session ID")
    p_gold.add_argument("--batch-label", help="Batch label")
    p_gold.add_argument("--dry-run", action="store_true")
    p_gold.add_argument("--json", action="store_true")
    p_gold.add_argument("--ingest", action="store_true")
    p_gold.set_defaults(fn=cmd_gold_run)

    # gui
    p_gui = sub.add_parser("gui", help="Launch Tkinter GUI")
    p_gui.set_defaults(fn=cmd_gui)

    # phase2
    p_p2 = sub.add_parser("phase2", help="Phase 2 ODS workflow")
    p_p2.add_argument("--synthetic", action="store_true", help="Use synthetic data")
    p_p2.add_argument("--grid", help="Grid definition JSON")
    p_p2.add_argument("--out", help="Output directory")
    p_p2.add_argument("--device", type=int, help="Audio device")
    p_p2.set_defaults(fn=cmd_phase2)

    # chladni
    p_ch = sub.add_parser("chladni", help="Chladni pattern analysis")
    ch_sub = p_ch.add_subparsers(dest="subcommand", required=True)

    p_ch_peaks = ch_sub.add_parser("peaks", help="Extract peaks from WAV")
    p_ch_peaks.add_argument("--wav", required=True)
    p_ch_peaks.add_argument("--out", required=True)
    p_ch_peaks.add_argument("--min-hz", type=float, default=50)
    p_ch_peaks.add_argument("--max-hz", type=float, default=2000)

    p_ch_index = ch_sub.add_parser("index", help="Index patterns to frequencies")
    p_ch_index.add_argument("--peaks-json", required=True)
    p_ch_index.add_argument("--plate-id", required=True)
    p_ch_index.add_argument("--out", required=True)
    p_ch_index.add_argument("--images", nargs="+", required=True)

    p_ch.set_defaults(fn=cmd_chladni)

    # bending
    p_bend = sub.add_parser("bending", help="Bending MOE calculation")
    p_bend.add_argument("--load", required=True, help="Load series JSON")
    p_bend.add_argument("--disp", required=True, help="Displacement series JSON")
    p_bend.add_argument("--out-dir", required=True)
    p_bend.add_argument("--method", default="3point", choices=["3point", "4point"])
    p_bend.add_argument("--span", type=float, required=True, help="Span in mm")
    p_bend.add_argument("--width", type=float, required=True, help="Width in mm")
    p_bend.add_argument(
        "--thickness", type=float, required=True, help="Thickness in mm"
    )
    p_bend.add_argument("--rate", type=float, default=50, help="Resample rate Hz")
    p_bend.set_defaults(fn=cmd_bending)

    # export-pack
    p_export = sub.add_parser(
        "export-pack",
        help="Export viewer_pack_v1 ZIP from a Phase 2 session",
    )
    p_export.add_argument(
        "--session",
        required=True,
        help="Session directory (repo-relative or absolute)",
    )
    p_export.add_argument(
        "--out",
        required=True,
        help="Output ZIP path",
    )
    p_export.add_argument(
        "--validate",
        action="store_true",
        help="Validate ZIP after export",
    )
    p_export.add_argument(
        "--strict",
        action="store_true",
        help="Strict validation (fail on warnings)",
    )
    p_export.add_argument(
        "--json",
        action="store_true",
        help="Emit validation results as JSON",
    )
    p_export.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite output file without confirmation",
    )
    p_export.set_defaults(fn=cmd_export_pack)

    # evidence-check (NEW)
    p_ev = sub.add_parser(
        "evidence-check",
        help="Preflight validate a session's evidence artifacts (missing/parse checks)",
    )
    p_ev.add_argument(
        "--session",
        required=True,
        help="Session directory (repo-relative or absolute)",
    )
    p_ev.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN findings as failure (non-zero exit)",
    )
    p_ev.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Alias for --strict (useful for automation readability)",
    )
    p_ev.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report",
    )
    p_ev.set_defaults(fn=cmd_evidence_check)

    # last (NEW!)
    p_last = sub.add_parser("last", help="Show most recent session")
    p_last.add_argument("--open", action="store_true", help="Open in file manager")
    p_last.set_defaults(fn=cmd_last)

    # sessions (NEW!)
    p_sess = sub.add_parser("sessions", help="List all sessions")
    p_sess.add_argument("--limit", type=int, default=20, help="Max sessions to show")
    p_sess.set_defaults(fn=cmd_sessions)

    # completion (NEW!)
    p_comp = sub.add_parser("completion", help="Generate shell completion script")
    p_comp.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell type")
    p_comp.set_defaults(fn=cmd_completion)

    # export-session-timeline (PR #16)
    p_est = sub.add_parser(
        "export-session-timeline",
        help="Export session directive timeline (read-only)",
    )
    p_est.add_argument(
        "--session",
        required=True,
        help="Path to session directory",
    )
    p_est.add_argument(
        "--out",
        default=None,
        help="Optional output path (default: <session>/meta/session_timeline_v1.json)",
    )
    p_est.set_defaults(fn=cmd_export_session_timeline)

    # calibrate (Phase 3 P0)
    from tap_tone_pi.cli.calibrate import add_calibrate_subcommand

    add_calibrate_subcommand(sub)

    return p


def cmd_export_session_timeline(args: argparse.Namespace) -> int:
    """Export session directive timeline (read-only, fail-closed)."""
    try:
        from tap_tone_pi.core.session_timeline import export_session_timeline

        session_dir = Path(args.session).resolve()
        out = Path(args.out).resolve() if getattr(args, "out", None) else None
        p = export_session_timeline(session_dir, out_path=out)
        if p is None:
            print("No session timeline exported.")
            return 0
        print(f"Wrote: {p}")
        return 0
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        print("No session timeline exported.")
        return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

"""
Phase 2 CLI command — Grid capture workflow with progress display and resume.

This module provides the `ttp phase2` subcommand with:
- Visual grid progress display
- Session resume (--resume flag)
- Per-point coherence checking

Usage:
    ttp phase2 run --grid config/grids/guitar_top_35pt.json --out ./runs_phase2
    ttp phase2 run --resume ./runs_phase2/session_20260328T100000Z
    ttp phase2 status ./runs_phase2/session_20260328T100000Z
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tap_tone_pi.core.grid import Grid, load_grid
from tap_tone_pi.phase2.grid_display import GridDisplay, PointStatus
from tap_tone_pi.phase2.session_state import SessionState
from tap_tone_pi.phase2.coherence_gate import (
    check_coherence_from_arrays,
    format_coherence_feedback,
)
from tap_tone_pi.calibration.session_context import (
    get_calibration_context,
    format_calibration_summary,
)


def cmd_phase2_run(args: argparse.Namespace) -> int:
    """
    Run Phase 2 grid capture workflow.
    
    Either starts a new session or resumes an existing one.
    """
    # Determine mode: new session or resume
    if args.resume:
        return _run_resume(args)
    else:
        return _run_new(args)


def _run_new(args: argparse.Namespace) -> int:
    """Start a new Phase 2 session."""
    # Validate inputs
    grid_path = Path(args.grid)
    if not grid_path.exists():
        print(f"Grid file not found: {grid_path}", file=sys.stderr)
        return 1
    
    # Load grid
    try:
        grid = load_grid(grid_path)
    except Exception as e:
        print(f"Failed to load grid: {e}", file=sys.stderr)
        return 1
    
    # Create session directory
    out_dir = Path(args.out)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_dir = out_dir / f"session_{timestamp}"
    
    # Create session state
    state = SessionState.create(
        session_dir,
        grid,
        grid_path=str(grid_path),
        coherence_threshold=args.coherence_threshold,
    )
    
    # Copy grid to session directory
    import shutil
    shutil.copy(grid_path, session_dir / "grid.json")
    
    # Inject calibration context
    device_index = getattr(args, "device", None) or 0
    cal_context = get_calibration_context(device_index)
    state.metadata["calibration"] = cal_context.to_dict()
    state.save()
    
    print(f"Created session: {session_dir}")
    print(format_calibration_summary(cal_context))
    print(f"Grid: {len(grid.points)} points")
    print(f"Coherence threshold: {args.coherence_threshold}")
    print()
    
    return _run_capture_loop(state, grid, args)


def _run_resume(args: argparse.Namespace) -> int:
    """Resume an existing Phase 2 session."""
    session_dir = Path(args.resume)
    
    if not SessionState.exists(session_dir):
        print(f"No session state found in: {session_dir}", file=sys.stderr)
        print("Use --grid to start a new session.", file=sys.stderr)
        return 1
    
    # Load session state
    state = SessionState.load(session_dir)
    
    # Load grid
    grid_file = session_dir / "grid.json"
    if not grid_file.exists():
        print(f"Grid file not found in session: {grid_file}", file=sys.stderr)
        return 1
    
    grid = load_grid(grid_file)
    
    # Validate grid matches session state
    grid_mismatch = _check_grid_mismatch(state, grid)
    if grid_mismatch:
        print(f"ERROR: Grid mismatch detected.", file=sys.stderr)
        print(f"  {grid_mismatch}", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"The session was started with a different grid configuration.", file=sys.stderr)
        print(f"Options:", file=sys.stderr)
        print(f"  1. Use the original grid file: {state.grid_path}", file=sys.stderr)
        print(f"  2. Start a new session with --grid", file=sys.stderr)
        return 1
    
    # Show resume status
    summary = state.summary()
    print(f"Resuming session: {session_dir}")
    print(f"Progress: {summary['captured'] + summary['warning']}/{summary['total']} ({summary['progress_pct']:.0f}%)")
    print(f"Pending: {len(state.pending_points())}")
    print(f"Failed: {summary['failed']}")
    print(f"Warnings: {summary['warning']}")
    print()
    
    return _run_capture_loop(state, grid, args)


def _check_grid_mismatch(state: SessionState, grid: Grid) -> Optional[str]:
    """
    Check if loaded grid matches session state.
    
    Returns None if OK, or error message if mismatch detected.
    """
    # Check point count
    state_points = set(state.point_order)
    grid_points = set(p.id for p in grid.points)
    
    if len(state_points) != len(grid_points):
        return f"Point count mismatch: session has {len(state_points)}, grid has {len(grid_points)}"
    
    # Check point IDs match
    missing_in_grid = state_points - grid_points
    if missing_in_grid:
        return f"Points in session but not in grid: {sorted(missing_in_grid)}"
    
    extra_in_grid = grid_points - state_points
    if extra_in_grid:
        return f"Points in grid but not in session: {sorted(extra_in_grid)}"
    
    # Check point order matches
    grid_order = [p.id for p in grid.points]
    if grid_order != state.point_order:
        return f"Point order differs between session and grid"
    
    return None


def _run_capture_loop(state: SessionState, grid: Grid, args: argparse.Namespace) -> int:
    """
    Main capture loop with grid display and coherence checking.
    
    This is the interactive loop that:
    1. Shows grid progress
    2. Prompts for each point
    3. Captures and checks coherence
    4. Updates state and display
    """
    # Initialize display
    display = GridDisplay(grid)
    
    # Check display mode
    no_progress = getattr(args, "no_progress", False)
    
    # Sync display with state
    for point_id, record in state.points.items():
        if record.status == "captured":
            display.update(point_id, PointStatus.CAPTURED)
        elif record.status == "warning":
            display.update(point_id, PointStatus.WARNING)
        elif record.status == "failed":
            display.update(point_id, PointStatus.FAILED)
        elif record.status == "skipped":
            display.update(point_id, PointStatus.SKIPPED)
    
    # Check if synthetic mode
    synthetic = getattr(args, "synthetic", False)
    
    # Main loop
    while True:
        next_point = state.next_point()
        
        if next_point is None:
            # All done
            _show_progress(display, no_progress)
            print()
            print("=" * 40)
            print("Phase 2 capture complete!")
            summary = state.summary()
            print(f"  Captured: {summary['captured']}")
            print(f"  Warnings: {summary['warning']}")
            print(f"  Failed: {summary['failed']}")
            break
        
        # Update display
        state.set_current(next_point)
        display.set_current(next_point)
        _show_progress(display, no_progress)
        
        # Get point info
        point = next((p for p in grid.points if p.id == next_point), None)
        if point:
            print(f"\nPosition: ({point.x:.1f}, {point.y:.1f}) mm")
        
        # Prompt for capture
        print()
        action = _prompt_action(next_point)
        
        if action == "capture":
            success = _do_capture(state, next_point, display, synthetic, args)
            if not success:
                # Offer retry
                retry = input("Retry this point? [Y/n]: ").strip().lower()
                if retry in ("", "y", "yes"):
                    state.reset_point(next_point)
                    display.update(next_point, PointStatus.PENDING)
                    continue
        
        elif action == "skip":
            state.mark_skipped(next_point)
            display.update(next_point, PointStatus.SKIPPED)
            state.save()
        
        elif action == "quit":
            print("\nSession paused. Resume with:")
            print(f"  ttp phase2 run --resume {state.session_dir}")
            state.save()
            return 0
    
    # Final save
    state.save()
    
    # Offer export
    if state.is_complete():
        export = input("\nExport viewer pack now? [Y/n]: ").strip().lower()
        if export in ("", "y", "yes"):
            print("Run: ttp export-pack --session", state.session_dir)
    
    return 0


def _show_progress(display: GridDisplay, no_progress: bool) -> None:
    """
    Show grid progress in appropriate mode.
    
    Args:
        display: GridDisplay instance
        no_progress: If True, use plain line-by-line output (for SSH/logging)
    """
    if no_progress:
        # Plain mode: single line, no ANSI codes
        print(display.render_compact())
    else:
        # Interactive mode: clear screen and show full grid
        print(display.clear_and_render())


def _clear_and_show(display: GridDisplay) -> None:
    """Clear screen and show grid. Deprecated: use _show_progress instead."""
    print(display.clear_and_render())


def _prompt_action(point_id: str) -> str:
    """Prompt user for action on current point."""
    print(f"Point {point_id}:")
    print("  [Enter] Capture")
    print("  [s] Skip")
    print("  [q] Quit (save and exit)")
    
    response = input("> ").strip().lower()
    
    if response in ("", "c", "capture"):
        return "capture"
    elif response in ("s", "skip"):
        return "skip"
    elif response in ("q", "quit", "exit"):
        return "quit"
    else:
        print("Unknown command. Press Enter to capture.")
        return "capture"


def _do_capture(
    state: SessionState,
    point_id: str,
    display: GridDisplay,
    synthetic: bool,
    args: argparse.Namespace,
) -> bool:
    """
    Perform capture for a single point.
    
    Returns True if capture succeeded (even with warnings).
    """
    import numpy as np
    
    print(f"Capturing {point_id}...")
    
    if synthetic:
        # Synthetic mode: generate fake data
        fs = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(fs * duration))
        
        # Random frequency between 100-400 Hz
        freq = 100 + np.random.random() * 300
        signal = np.sin(2 * np.pi * freq * t) * 0.5
        
        # Add some noise
        noise_level = np.random.random() * 0.3
        signal += np.random.randn(len(signal)) * noise_level
        
        time.sleep(0.5)  # Simulate capture time
        
        # Check coherence
        result = check_coherence_from_arrays(signal, None, fs, threshold=state.coherence_threshold)
    
    else:
        # Real capture mode
        try:
            from tap_tone_pi.capture import record_auto_trigger
            from tap_tone_pi.io.wav import write_wav_mono
            
            device = getattr(args, "device", None)
            duration = getattr(args, "duration", 2.5)
            
            # Record with auto-trigger
            signal, fs = record_auto_trigger(
                device=device,
                duration=duration,
                timeout=30.0,
            )
            
            # Save WAV
            point_dir = state.session_dir / point_id
            point_dir.mkdir(exist_ok=True)
            wav_path = point_dir / "capture.wav"
            write_wav_mono(wav_path, signal, fs)
            
            # Check coherence
            result = check_coherence_from_arrays(signal, None, fs, threshold=state.coherence_threshold)
            
        except ImportError:
            print("Audio capture not available. Use --synthetic for testing.")
            state.mark_failed(point_id, reason="Audio capture unavailable")
            display.update(point_id, PointStatus.FAILED)
            state.save()
            return False
        
        except Exception as e:
            print(f"Capture failed: {e}")
            state.mark_failed(point_id, reason=str(e))
            display.update(point_id, PointStatus.FAILED)
            state.save()
            return False
    
    # Show coherence result
    print()
    print(format_coherence_feedback(result))
    print()
    
    # Update state based on result
    if result.passed:
        state.mark_captured(point_id, coherence=result.coherence)
        display.update(point_id, PointStatus.CAPTURED)
    else:
        # Low coherence but captured
        state.mark_captured(point_id, coherence=result.coherence)  # Will become WARNING
        display.update(point_id, PointStatus.WARNING)
        
        if state.auto_retry_on_low_coherence:
            retry = input("Low coherence. Retry? [Y/n]: ").strip().lower()
            if retry in ("", "y", "yes"):
                state.reset_point(point_id)
                display.update(point_id, PointStatus.PENDING)
                return False
    
    state.save()
    return True


def cmd_phase2_status(args: argparse.Namespace) -> int:
    """Show status of a Phase 2 session."""
    session_dir = Path(args.session)
    
    if not SessionState.exists(session_dir):
        print(f"No session state found in: {session_dir}", file=sys.stderr)
        return 1
    
    state = SessionState.load(session_dir)
    summary = state.summary()
    
    # Load grid for display
    grid_file = session_dir / "grid.json"
    if grid_file.exists():
        grid = load_grid(grid_file)
        display = GridDisplay(grid, use_color=True)
        
        # Sync display with state
        for point_id, record in state.points.items():
            status_map = {
                "captured": PointStatus.CAPTURED,
                "warning": PointStatus.WARNING,
                "failed": PointStatus.FAILED,
                "skipped": PointStatus.SKIPPED,
                "pending": PointStatus.PENDING,
            }
            display.update(point_id, status_map.get(record.status, PointStatus.PENDING))
        
        print(display.render())
        print()
    
    # Summary
    print(f"Session: {session_dir}")
    print(f"Started: {state.started_at_utc}")
    print(f"Updated: {state.last_updated_utc}")
    print()
    print(f"Total points: {summary['total']}")
    print(f"  Captured: {summary['captured']}")
    print(f"  Warnings: {summary['warning']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pending: {summary['pending']}")
    print(f"  Skipped: {summary['skipped']}")
    print()
    print(f"Progress: {summary['progress_pct']:.1f}%")
    print(f"Complete: {'Yes' if summary['is_complete'] else 'No'}")
    
    # Show failed points
    if summary['failed'] > 0:
        print()
        print("Failed points:")
        for pid in state.failed_points():
            record = state.points[pid]
            reason = record.failure_reason or "Unknown"
            print(f"  {pid}: {reason}")
    
    # Show warning points
    if summary['warning'] > 0:
        print()
        print("Low coherence warnings:")
        for pid in state.warning_points():
            record = state.points[pid]
            coh = record.coherence or 0
            print(f"  {pid}: γ² = {coh:.3f}")
    
    return 0


def add_phase2_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add phase2 subcommand to CLI."""
    phase2 = subparsers.add_parser(
        "phase2",
        help="Phase 2 ODS grid capture workflow",
    )
    
    phase2_subs = phase2.add_subparsers(dest="phase2_cmd")
    
    # Run subcommand
    run_parser = phase2_subs.add_parser("run", help="Run grid capture")
    run_parser.add_argument("--grid", type=str, help="Path to grid JSON file")
    run_parser.add_argument("--out", type=str, default="./runs_phase2", help="Output directory")
    run_parser.add_argument("--resume", type=str, help="Resume session from directory")
    run_parser.add_argument("--device", type=int, help="Audio device index")
    run_parser.add_argument("--duration", type=float, default=2.5, help="Capture duration (seconds)")
    run_parser.add_argument("--coherence-threshold", type=float, default=0.7, help="Minimum coherence")
    run_parser.add_argument("--synthetic", action="store_true", help="Use synthetic data (no hardware)")
    run_parser.add_argument(
        "--no-progress",
        action="store_true",
        dest="no_progress",
        help="Disable ANSI grid display (plain line-by-line output for SSH/logging)"
    )
    run_parser.set_defaults(func=cmd_phase2_run)
    
    # Status subcommand
    status_parser = phase2_subs.add_parser("status", help="Show session status")
    status_parser.add_argument("session", type=str, help="Session directory")
    status_parser.set_defaults(func=cmd_phase2_status)


def main():
    """Standalone entry point for testing."""
    parser = argparse.ArgumentParser(description="Phase 2 CLI")
    subparsers = parser.add_subparsers(dest="cmd")
    add_phase2_subparser(subparsers)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

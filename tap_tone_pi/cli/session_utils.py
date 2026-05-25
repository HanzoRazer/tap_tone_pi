# INSTRUMENT CLASS: MEASUREMENT
"""
CLI session utilities — extracted from cli/main.py (Phase 4 maintainability restructuring).

Provides session discovery, formatting, and helper functions used by
cmd_last, cmd_sessions, and other session-related CLI commands.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_all_sessions(session_roots: list[Path]) -> list[Path]:
    """Find all session directories across known roots."""
    sessions = []
    prefixes = ("session_", "capture_", "bend_", "chladni_", "gold_")

    for root in session_roots:
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


def count_session_points(session_dir: Path) -> int | None:
    """Count capture points from session.jsonl if present."""
    jsonl = session_dir / "session.jsonl"
    if jsonl.exists():
        try:
            return sum(1 for _ in jsonl.open())
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass
    return None


def format_size(size: int) -> str:
    """Format file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def open_path(path: Path) -> None:
    """Open a path in the system file manager."""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)])


def print_summary(label: str | None, res) -> None:
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

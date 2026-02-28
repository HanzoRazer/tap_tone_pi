"""
CLI for manual entry of deflection profile data.

Provides interactive prompts for entering tuning session data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .models import TuningSession, TuningHistory
from .analysis import compute_session_stats, SessionStats


# Common measurement locations for guitar tops/backs
DEFAULT_LOCATIONS = [
    "center",
    "lower_bout",
    "upper_bout",
    "waist_L",
    "waist_R",
]


def prompt_float(prompt: str, default: Optional[float] = None) -> Optional[float]:
    """Prompt for a float value with optional default."""
    if default is not None:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("  Invalid number, try again.")


def prompt_str(prompt: str, default: str = "") -> str:
    """Prompt for a string value with optional default."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    raw = input(prompt).strip()
    return raw if raw else default


def create_new_history() -> TuningHistory:
    """Interactively create a new tuning history."""
    print("\n=== New Panel Setup ===\n")

    panel_id = prompt_str("Panel ID (e.g., 'top_001')")
    panel_type = prompt_str("Panel type", "top")
    wood_species = prompt_str("Wood species", "spruce")
    length_mm = prompt_float("Panel length (mm)", 500.0) or 500.0
    width_mm = prompt_float("Panel width (mm)", 380.0) or 380.0

    return TuningHistory(
        panel_id=panel_id,
        panel_type=panel_type,
        wood_species=wood_species,
        length_mm=length_mm,
        width_mm=width_mm,
    )


def enter_session(history: TuningHistory) -> TuningSession:
    """Interactively enter a new tuning session."""
    session_num = len(history.sessions) + 1
    print(f"\n=== Session {session_num} ===\n")

    mass_g = prompt_float("Panel mass (g)") or 0.0
    freq_hz = prompt_float("Tap frequency (Hz, Enter to skip)")
    notes = prompt_str("Session notes", "")

    session = TuningSession.create_now(
        mass_g=mass_g,
        freq_hz=freq_hz,
        notes=notes,
    )

    # Enter readings
    print("\n--- Deflection Readings ---")
    print(
        "Enter readings for each location. Press Enter with empty location to finish.\n"
    )

    while True:
        location = prompt_str("Location (or Enter to finish)")
        if not location:
            break

        thickness = prompt_float(f"  Thickness at {location} (mm)") or 0.0
        deflection = prompt_float(f"  Deflection at {location} (mm)") or 0.0
        reading_notes = prompt_str(f"  Notes for {location}", "")

        session.add_reading(
            location=location,
            thickness_mm=thickness,
            deflection_mm=deflection,
            notes=reading_notes,
        )
        print(f"  Added: {location} - {thickness}mm thick, {deflection}mm deflection")

    return session


def print_session_summary(
    session: TuningSession,
    stats: Optional[SessionStats] = None,
) -> None:
    """Print a summary of a session."""
    print("\n--- Session Summary ---")
    print(f"Mass: {session.mass_g} g")
    if session.freq_hz:
        print(f"Frequency: {session.freq_hz} Hz")
    print(f"Readings: {len(session.readings)}")

    if session.readings:
        print("\n  Location        Thick(mm)  Defl(mm)")
        print("  " + "-" * 38)
        for r in session.readings:
            print(f"  {r.location:<15} {r.thickness_mm:>8.2f}  {r.deflection_mm:>8.2f}")

    if stats:
        print("\n--- Derived Values ---")
        if stats.density_kg_m3:
            print(f"Density: {stats.density_kg_m3:.1f} kg/m³")
        if stats.avg_thickness_mm:
            print(f"Avg thickness: {stats.avg_thickness_mm:.2f} mm")
        if stats.stiffness_estimates:
            print("Stiffness (E):")
            for loc, e in stats.stiffness_estimates.items():
                print(f"  {loc}: {e:.2f} GPa")


def print_history_summary(history: TuningHistory) -> None:
    """Print summary of all sessions."""
    print(f"\n=== {history.panel_id} ({history.wood_species} {history.panel_type}) ===")
    print(f"Dimensions: {history.length_mm} x {history.width_mm} mm\n")

    if not history.sessions:
        print("No sessions recorded yet.")
        return

    print("Session  Mass(g)  Freq(Hz)  AvgThick(mm)  Readings")
    print("-" * 55)
    for i, s in enumerate(history.sessions, 1):
        freq_str = f"{s.freq_hz:.1f}" if s.freq_hz else "-"
        avg_t = s.avg_thickness_mm()
        avg_t_str = f"{avg_t:.2f}" if avg_t else "-"
        print(
            f"  {i:>3}    {s.mass_g:>7.1f}  {freq_str:>8}  {avg_t_str:>12}  {len(s.readings):>8}"
        )


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manual entry for plate tuning deflection profile",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="History file to load/save (JSON)",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Create a new panel history",
    )
    parser.add_argument(
        "--add-session",
        action="store_true",
        help="Add a new session to existing history",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print history summary",
    )

    args = parser.parse_args(argv)

    # Load or create history
    history: Optional[TuningHistory] = None

    if args.file and args.file.exists() and not args.new:
        history = TuningHistory.load(args.file)
        print(f"Loaded: {args.file}")

    if args.new or history is None:
        history = create_new_history()

    # Summary mode
    if args.summary:
        print_history_summary(history)
        return 0

    # Add session
    if args.add_session or args.new:
        session = enter_session(history)
        history.add_session(session)

        # Compute and show stats
        stats = compute_session_stats(
            session=session,
            length_mm=history.length_mm,
            width_mm=history.width_mm,
        )
        print_session_summary(session, stats)

    # Save
    if args.file:
        history.save(args.file)
        print(f"\nSaved to: {args.file}")
    else:
        # Prompt for save location
        save_path = prompt_str("Save to file (Enter to skip)")
        if save_path:
            history.save(Path(save_path))
            print(f"Saved to: {save_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

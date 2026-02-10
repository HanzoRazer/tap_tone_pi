"""Formatting helper for directive history display.

Pure function — no Tk dependency, no I/O.  Returns tuple of
pre-formatted lines suitable for embedding in any renderer
(GUI text widget, CLI print, etc.).
"""
from __future__ import annotations

from typing import Optional, Sequence

from tap_tone_pi.agentic.spine.directive_history import DirectiveEventRow


def format_directive_history(
    rows: Sequence[DirectiveEventRow],
    *,
    moment_id: Optional[str] = None,
    limit: int = 10,
) -> tuple[str, ...]:
    """Return a tuple of display lines (no trailing newline).

    *rows* should already be in chronological order (oldest → newest).
    At most *limit* rows are shown.  If *moment_id* is non-empty it is
    prepended as a header line.
    """
    lines: list[str] = []

    if moment_id and str(moment_id).strip():
        lines.append(f"Moment: {str(moment_id).strip()}")

    if not rows:
        return tuple(lines)

    lines.append("Recent directive events:")

    shown = list(rows)[-max(1, int(limit)):]
    for r in shown:
        ts = (r.timestamp or "-").strip() if isinstance(r.timestamp, str) else "-"
        et = (r.event_type or "-").strip() if isinstance(r.event_type, str) else "-"
        did = (r.directive_id or "-").strip() if isinstance(r.directive_id, str) else "-"
        comp = (r.component or "-").strip() if isinstance(r.component, str) else "-"
        lines.append(f"  {ts}  {et}  directive_id={did}  component={comp}")

    return tuple(lines)

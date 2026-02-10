"""GUI directive outcome recording — ACK / DISMISS persistence.

Reads the latest advisory from ``spine_shadow_latest.json`` and appends
an ``ATTENTION_ACKNOWLEDGED`` or ``ATTENTION_DISMISSED`` event into the
session's ``events.jsonl`` stream.

Fail-closed: never raises; returns ``False`` on any failure.
No Tkinter dependency — pure I/O helper safe for testing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional


Outcome = Literal["ack", "dismiss"]


def _extract_directive_id(rec: dict) -> Optional[str]:
    """Extract a usable directive identifier from a shadow record.

    Checks ``advisory.directive_id`` first (future-proof), then falls
    back to ``run_id`` (always present in current schema).
    Returns ``None`` if nothing usable is found.
    """
    if not isinstance(rec, dict):
        return None
    advisory = rec.get("advisory")
    if isinstance(advisory, dict):
        did = advisory.get("directive_id")
        if isinstance(did, str) and did.strip():
            return did.strip()
    # Stable fallback: run_id is always present in shadow records
    rid = rec.get("run_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return None


def record_latest_directive_outcome(
    *,
    session_dir: Path,
    outcome: Outcome,
    component: str = "gui",
) -> bool:
    """Record an explicit operator outcome for the latest advisory directive.

    - Reads: ``<session_dir>/spine_shadow_latest.json``
    - Writes: ``<session_dir>/events.jsonl`` (append-only)
    - Never raises; returns ``False`` on any failure or missing data.
    """
    try:
        from tap_tone_pi.agentic.spine.shadow_record import load_latest_shadow_record
        from tap_tone_pi.agentic.events import (
            emit_attention_acknowledged,
            emit_attention_dismissed,
        )
    except Exception:
        return False

    try:
        rec = load_latest_shadow_record(Path(session_dir))
        if rec is None:
            return False

        directive_id = _extract_directive_id(rec)
        if not directive_id:
            return False

        events_path = Path(session_dir) / "events.jsonl"

        if outcome == "ack":
            emit_attention_acknowledged(
                component,
                directive_id,
                event_log_path=events_path,
            )
        else:
            emit_attention_dismissed(
                component,
                directive_id,
                event_log_path=events_path,
            )

        return True
    except Exception:
        return False

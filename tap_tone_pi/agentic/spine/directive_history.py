"""Read-only directive event history from ``events.jsonl``.

Provides a robust JSONL reader that filters to directive-related event
types and returns normalised rows for CLI / GUI rendering.

Fail-closed: missing files, malformed lines, and unexpected schemas
are silently skipped — never raises.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


_DIRECTIVE_EVENTS = {
    "attention_requested",
    "attention_acknowledged",
    "attention_dismissed",
}


@dataclass(frozen=True)
class DirectiveEventRow:
    """One normalised directive event for display."""

    timestamp: str
    event_type: str
    directive_id: Optional[str] = None
    component: Optional[str] = None


def _safe_load_json(line: str) -> Optional[dict[str, Any]]:
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else None
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return None


def load_directive_events(
    session_dir: Path,
    *,
    limit: int = 10,
) -> list[DirectiveEventRow]:
    """Return the last *limit* directive-related events from ``events.jsonl``.

    Reads ``<session_dir>/events.jsonl`` backwards, filtering to
    ``attention_requested``, ``attention_acknowledged``, and
    ``attention_dismissed`` event types.

    Fail-closed: returns ``[]`` on missing file, I/O errors, or if no
    directive events are found.
    """
    path = Path(session_dir) / "events.jsonl"
    if not path.is_file():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return []

    rows: list[DirectiveEventRow] = []

    for line in reversed(lines):
        obj = _safe_load_json(line)
        if not obj:
            continue
        et = obj.get("event_type")
        if not isinstance(et, str):
            continue
        et_l = et.strip().lower()
        if et_l not in _DIRECTIVE_EVENTS:
            continue

        ts = obj.get("timestamp") if isinstance(obj.get("timestamp"), str) else ""

        directive_id: Optional[str] = None
        payload = obj.get("payload")
        if isinstance(payload, dict):
            did = payload.get("directive_id")
            if isinstance(did, str) and did.strip():
                directive_id = did.strip()

        component: Optional[str] = None
        source = obj.get("source")
        if isinstance(source, dict):
            comp = source.get("component")
            if isinstance(comp, str) and comp.strip():
                component = comp.strip()
        else:
            # Back-compat for any flat shapes
            comp = obj.get("component")
            if isinstance(comp, str) and comp.strip():
                component = comp.strip()

        rows.append(
            DirectiveEventRow(
                timestamp=ts,
                event_type=et_l,
                directive_id=directive_id,
                component=component,
            )
        )
        if len(rows) >= max(1, int(limit)):
            break

    return list(reversed(rows))

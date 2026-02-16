"""Read-only session directive timeline exporter.

Consolidates directive events, moment snapshots, and UI state into a
single ``session_timeline_v1.json`` for offline review, regression
analysis, and future ToolBox ingest.

Inputs (all read-only, all optional):
  - ``<session_dir>/events.jsonl``
  - ``<session_dir>/spine_shadow_latest.json``
  - ``<session_dir>/meta/advisory_state.json``

Output:
  - ``<session_dir>/meta/session_timeline_v1.json`` (default)

Fail-closed: returns ``None`` on unrecoverable errors; never raises.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        if not path.is_file():
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return None


def _safe_mkdir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass


def export_session_timeline(
    session_dir: Path,
    *,
    out_path: Optional[Path] = None,
) -> Optional[Path]:
    """Export a consolidated, read-only session directive timeline.

    Returns the written path on success, or ``None`` on failure.
    """
    try:
        session_dir = Path(session_dir)
        if not session_dir.exists():
            return None

        # Load directive events via the robust JSONL reader
        from tap_tone_pi.agentic.spine.directive_history import (
            load_directive_events,
        )

        rows = load_directive_events(session_dir, limit=10_000)
        events = [
            {
                "timestamp": r.timestamp or "",
                "event_type": r.event_type,
                "directive_id": r.directive_id,
                "component": r.component,
            }
            for r in rows
        ]

        # Counts (filtered directive events only)
        counts = {
            "attention_requested": 0,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        }
        for r in rows:
            if r.event_type in counts:
                counts[r.event_type] += 1

        # Optional: latest moment snapshot from shadow record
        moment_snapshot: Optional[dict[str, Any]] = None
        shadow = _read_json(session_dir / "spine_shadow_latest.json")
        if shadow:
            m = shadow.get("moment")
            if isinstance(m, dict):
                moment_snapshot = {
                    "id": m.get("id"),
                    "confidence": m.get("confidence"),
                    "trigger_event_count": m.get("trigger_event_count"),
                }

        # Optional: UI state
        ui_state = _read_json(
            session_dir / "meta" / "advisory_state.json",
        ) or {}

        # Optional: policy trace from shadow record (PR #19)
        policy_trace = None
        if shadow and isinstance(shadow.get("policy_trace"), dict):
            policy_trace = shadow["policy_trace"]

        # Source paths (relative, OS-neutral)
        paths = {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        }

        payload: dict[str, Any] = {
            "schema_id": "session_timeline_v1",
            "schema_version": 2,
            "session_id": session_dir.name,
            "paths": paths,
            "moment_latest": moment_snapshot,
            "directive_events": events,
            "counts": counts,
            "ui_state": ui_state,
            "latest_policy_trace": policy_trace,
        }

        if out_path is None:
            out_path = session_dir / "meta" / "session_timeline_v1.json"
        out_path = Path(out_path)
        _safe_mkdir(out_path.parent)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out_path
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return None

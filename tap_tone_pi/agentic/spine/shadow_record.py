"""Spine Shadow Directive Record v1 — Writer + Loader + Validator.

Implements the persisted shadow record format for M0 spine decisions.
This module has NO spine pipeline imports and can be used safely from
CLI, workflow, or test code.

Schema: spine_shadow_record v1
See: PR #2 / PR #3 spec for field-by-field rules.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_SCHEMA_ID = "spine_shadow_record"
_SCHEMA_VERSION = 1

_VALID_MODES = ("M0", "M1", "M2")
_VALID_ACTIONS = (
    "INSPECT", "REVIEW", "COMPARE", "DECIDE",
    "CONFIRM", "INTERVENE", "ABORT",
)
_VALID_ERROR_STAGES = (
    "load_events", "detect_moments", "decide", "write_shadow",
)


def _utc_now_iso() -> str:
    """ISO-8601 with milliseconds + Z."""
    dt = datetime.now(timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# -------------------------------------------------------------------------
# Validator
# -------------------------------------------------------------------------

def _validate_shadow_record_v1(rec: Dict[str, Any]) -> None:
    """Lightweight shape check.  Raises ``ValueError`` on invalid records."""
    required_top = [
        "schema_id", "schema_version", "timestamp",
        "session_id", "run_id", "mode",
        "moment", "advisory", "commands", "error",
    ]
    for k in required_top:
        if k not in rec:
            raise ValueError(f"shadow record missing key: {k}")

    if rec["schema_id"] != _SCHEMA_ID:
        raise ValueError(f"shadow record schema_id must be {_SCHEMA_ID!r}")
    if rec["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("shadow record schema_version must be 1")

    if not isinstance(rec["session_id"], str) or not rec["session_id"]:
        raise ValueError("shadow record session_id must be non-empty str")
    if not isinstance(rec["run_id"], str) or not rec["run_id"]:
        raise ValueError("shadow record run_id must be non-empty str")
    if rec["mode"] not in _VALID_MODES:
        raise ValueError("shadow record mode must be one of M0/M1/M2")

    # -- moment --
    moment = rec["moment"]
    if not isinstance(moment, dict):
        raise ValueError("shadow record moment must be an object")
    for k in ("id", "confidence", "trigger_event_count"):
        if k not in moment:
            raise ValueError(f"shadow record moment missing key: {k}")
    if not isinstance(moment["id"], str) or not moment["id"]:
        raise ValueError("shadow record moment.id must be non-empty str")
    if not (isinstance(moment["confidence"], (int, float))
            and 0.0 <= float(moment["confidence"]) <= 1.0):
        raise ValueError("shadow record moment.confidence must be number in [0,1]")
    if not (isinstance(moment["trigger_event_count"], int)
            and moment["trigger_event_count"] >= 0):
        raise ValueError("shadow record moment.trigger_event_count must be int >= 0")

    # -- commands --
    commands = rec["commands"]
    if not isinstance(commands, dict) or "count" not in commands:
        raise ValueError("shadow record commands must be an object with count")
    if not (isinstance(commands["count"], int) and commands["count"] >= 0):
        raise ValueError("shadow record commands.count must be int >= 0")

    # -- error --
    err = rec["error"]
    if err is not None:
        if not isinstance(err, dict):
            raise ValueError("shadow record error must be null or object")
        for k in ("type", "message", "stage"):
            if k not in err:
                raise ValueError(f"shadow record error missing key: {k}")
        if not isinstance(err["type"], str) or not err["type"]:
            raise ValueError("shadow record error.type must be non-empty str")
        if not isinstance(err["message"], str):
            raise ValueError("shadow record error.message must be str")
        if not isinstance(err["stage"], str) or not err["stage"]:
            raise ValueError("shadow record error.stage must be non-empty str")

    # -- advisory --
    advisory = rec["advisory"]
    if advisory is not None:
        if not isinstance(advisory, dict):
            raise ValueError("shadow record advisory must be null or object")
        for k in ("action", "summary", "focus", "confidence"):
            if k not in advisory:
                raise ValueError(f"shadow record advisory missing key: {k}")
        if advisory["action"] not in _VALID_ACTIONS:
            raise ValueError(
                "shadow record advisory.action must be a valid AttentionAction name"
            )
        if not isinstance(advisory["summary"], str) or not advisory["summary"]:
            raise ValueError("shadow record advisory.summary must be non-empty str")
        if not (isinstance(advisory["confidence"], (int, float))
                and 0.0 <= float(advisory["confidence"]) <= 1.0):
            raise ValueError(
                "shadow record advisory.confidence must be number in [0,1]"
            )
        focus = advisory["focus"]
        if focus is not None:
            if not isinstance(focus, dict):
                raise ValueError("shadow record advisory.focus must be null or object")
            for k in ("target_type", "target_id", "highlight_region"):
                if k not in focus:
                    raise ValueError(
                        f"shadow record advisory.focus missing key: {k}"
                    )
            if not isinstance(focus["target_type"], str) or not focus["target_type"]:
                raise ValueError(
                    "shadow record advisory.focus.target_type must be non-empty str"
                )
            if not isinstance(focus["target_id"], str) or not focus["target_id"]:
                raise ValueError(
                    "shadow record advisory.focus.target_id must be non-empty str"
                )


# -------------------------------------------------------------------------
# Writer
# -------------------------------------------------------------------------

def write_shadow_record(
    *,
    session_dir: Path,
    session_id: str,
    run_id: str,
    mode: str,
    moment_id: str,
    moment_confidence: float,
    trigger_event_count: int,
    advisory_action: Optional[str] = None,
    advisory_summary: Optional[str] = None,
    advisory_focus: Optional[Dict[str, Any]] = None,
    advisory_confidence: Optional[float] = None,
    commands_count: int = 0,
    error: Optional[Dict[str, str]] = None,
    append_path: str = "spine_shadow.jsonl",
    latest_path: str = "spine_shadow_latest.json",
    validate: bool = True,
) -> Dict[str, Any]:
    """Create + persist a Spine Shadow Directive Record v1.

    - Appends to ``<session_dir>/<append_path>`` as JSONL
    - Overwrites ``<session_dir>/<latest_path>`` as the most recent record

    Returns the record dict.
    """
    if mode not in _VALID_MODES:
        raise ValueError("mode must be one of M0/M1/M2")

    # Normalize "no moment"
    if not moment_id:
        moment_id = "NONE"
    if moment_id == "NONE":
        moment_confidence = 0.0
        trigger_event_count = 0

    advisory: Optional[Dict[str, Any]]
    if (advisory_action is None and advisory_summary is None
            and advisory_focus is None and advisory_confidence is None):
        advisory = None
    else:
        advisory = {
            "action": advisory_action or "REVIEW",
            "summary": (
                advisory_summary
                or (moment_id if moment_id != "NONE" else "No moment detected")
            ),
            "focus": advisory_focus,  # may be None
            "confidence": float(
                advisory_confidence
                if advisory_confidence is not None
                else moment_confidence
            ),
        }

    rec: Dict[str, Any] = {
        "schema_id": _SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "timestamp": _utc_now_iso(),
        "session_id": session_id,
        "run_id": run_id,
        "mode": mode,
        "moment": {
            "id": moment_id,
            "confidence": float(moment_confidence),
            "trigger_event_count": int(trigger_event_count),
        },
        "advisory": advisory,
        "commands": {"count": int(commands_count)},
        "error": error,
    }

    if validate:
        _validate_shadow_record_v1(rec)

    session_dir.mkdir(parents=True, exist_ok=True)

    # Append JSONL
    append_file = session_dir / append_path
    with append_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False))
        f.write("\n")

    # Write latest snapshot atomically
    latest_file = session_dir / latest_path
    tmp = latest_file.with_suffix(latest_file.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        try:
            import os
            os.fsync(f.fileno())
        except Exception:
            pass
    tmp.replace(latest_file)

    return rec


# -------------------------------------------------------------------------
# Loader
# -------------------------------------------------------------------------

def load_latest_shadow_record(
    session_dir: Path,
    *,
    latest_path: str = "spine_shadow_latest.json",
    append_path: str = "spine_shadow.jsonl",
    validate: bool = True,
) -> Optional[Dict[str, Any]]:
    """Load the most recent Spine Shadow Directive Record v1.

    - Prefers ``<latest_path>``
    - Falls back to the last valid JSON line in ``<append_path>``

    Returns dict or ``None`` if nothing is available.
    """
    latest_file = session_dir / latest_path
    if latest_file.exists():
        try:
            rec = json.loads(latest_file.read_text(encoding="utf-8"))
            if validate:
                _validate_shadow_record_v1(rec)
            return rec
        except Exception:
            pass  # fall through to JSONL

    append_file = session_dir / append_path
    if not append_file.exists():
        return None

    try:
        lines = append_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if validate:
                _validate_shadow_record_v1(rec)
            return rec
        except Exception:
            continue

    return None

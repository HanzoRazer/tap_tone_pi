"""Per-session advisory response persistence.

Tracks whether the operator has already ACK'd or DISMISS'd the
advisory for a given session, so the panel stays hidden on reopen.

State file: ``<session_dir>/meta/advisory_state.json``

Fail-closed: never raises.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _state_path(session_dir: Path) -> Path:
    return Path(session_dir) / "meta" / "advisory_state.json"


def _read_state(session_dir: Path) -> Dict[str, Any]:
    p = _state_path(session_dir)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return {}


def _write_state(session_dir: Path, data: Dict[str, Any]) -> None:
    try:
        meta_dir = Path(session_dir) / "meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        _state_path(session_dir).write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass


def has_responded(session_dir: Path) -> bool:
    """Return True if the operator already responded to the advisory."""
    try:
        data = _read_state(session_dir)
        return bool(data.get("responded"))
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return False


def mark_responded(session_dir: Path, *, directive_id: Optional[str] = None) -> None:
    """Persist that the operator responded. Never raises."""
    try:
        payload = _read_state(session_dir)
        payload.update(
            {
                "responded": True,
                "directive_id": directive_id,
                "timestamp": datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            }
        )
        _write_state(session_dir, payload)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass


def get_show_directive_history(
    session_dir: Path,
    *,
    default: Optional[bool] = None,
) -> Optional[bool]:
    """Read persisted UI preference for Directive History panel.

    Returns the stored boolean, or *default* if no value has been
    persisted yet (or the file is missing/malformed).
    """
    try:
        data = _read_state(session_dir)
        v = data.get("show_directive_history")
        if isinstance(v, bool):
            return v
        return default
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return default


def set_show_directive_history(session_dir: Path, value: bool) -> None:
    """Persist session-local UI preference for Directive History panel.

    Fail-closed: silently ignores write errors.
    """
    try:
        data = _read_state(session_dir)
        data["show_directive_history"] = bool(value)
        _write_state(session_dir, data)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass


def is_trust_banner_dismissed(session_dir: Path) -> bool:
    """Return True if the TRUST_EROSION banner was already dismissed."""
    try:
        data = _read_state(session_dir)
        return bool(data.get("trust_banner_dismissed"))
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return False


def mark_trust_banner_dismissed(session_dir: Path) -> None:
    """Persist that the operator dismissed the TRUST_EROSION banner. Never raises."""
    try:
        data = _read_state(session_dir)
        data["trust_banner_dismissed"] = True
        data["trust_banner_dismissed_at"] = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        _write_state(session_dir, data)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass

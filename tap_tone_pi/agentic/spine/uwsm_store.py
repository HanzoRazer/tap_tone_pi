"""
UWSM persistence + decay (v1).

Stdlib-only. Safe to call from production paths:
 - load failures fall back to defaults
 - save failures never raise (callers may choose to surface in debug)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, Optional

from tap_tone_pi.agentic.spine.uwsm_update import ensure_uwsm


SCHEMA_ID = "uwsm_state_v1"
SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso_ms() -> str:
    return _utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_iso_utc(s: str) -> Optional[datetime]:
    if not isinstance(s, str) or not s:
        return None
    try:
        # Support "...Z" and "+00:00"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return None


def get_uwsm_path() -> Path:
    """
    Resolve per-user config path for UWSM.
      - $XDG_CONFIG_HOME/tap_tone_pi/uwsm_v1.json, else
      - ~/.config/tap_tone_pi/uwsm_v1.json
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "tap_tone_pi" / "uwsm_v1.json"


def _extract_confidence_map(uwsm: dict) -> Dict[str, float]:
    dims = (uwsm or {}).get("dimensions", {}) or {}
    out: Dict[str, float] = {}
    for dim, d in dims.items():
        if isinstance(d, dict) and "confidence" in d:
            try:
                out[str(dim)] = float(d["confidence"])
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                out[str(dim)] = 0.0
    return out


def load_uwsm_state(
    *, now: Optional[datetime] = None
) -> Tuple[dict, Dict[str, float], datetime]:
    """
    Load UWSM from disk. Fail-closed to defaults.
    Returns (uwsm_dict, confidence_map, updated_at_dt).
    """
    now = now or _utc_now()
    path = get_uwsm_path()

    # Defaults
    uwsm = ensure_uwsm(None)
    conf = _extract_confidence_map(uwsm)
    updated_at = _parse_iso_utc(uwsm.get("updated_at", "")) or now

    if not path.exists():
        return uwsm, conf, updated_at

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return uwsm, conf, updated_at
        if (
            data.get("schema_id") != SCHEMA_ID
            or data.get("schema_version") != SCHEMA_VERSION
        ):
            return uwsm, conf, updated_at
        loaded = data.get("uwsm")
        if not isinstance(loaded, dict):
            return uwsm, conf, updated_at
        uwsm = ensure_uwsm(loaded)
        conf = data.get("confidence")
        if not isinstance(conf, dict):
            conf = _extract_confidence_map(uwsm)
        # Use persisted updated_at if present; else UWSM updated_at
        ts = data.get("updated_at") or uwsm.get("updated_at")
        updated_at = _parse_iso_utc(ts) or now
        return uwsm, {str(k): float(v) for k, v in conf.items()}, updated_at
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return uwsm, conf, updated_at


def apply_uwsm_decay(
    uwsm: dict,
    confidence: Dict[str, float],
    updated_at: datetime,
    now: datetime,
) -> Tuple[dict, Dict[str, float]]:
    """
    Apply exponential decay to per-dimension confidence toward floor.

    Deterministic:
      conf' = floor + (conf-floor) * 0.5 ** (dt_days / half_life_days)
    """
    uwsm = ensure_uwsm(uwsm)
    dims = uwsm.get("dimensions", {}) or {}

    dt = now - updated_at
    dt_days = max(0.0, dt.total_seconds() / 86400.0)

    for dim, d in dims.items():
        if not isinstance(d, dict):
            continue
        decay = d.get("decay", {}) or {}
        try:
            half_life_days = float(decay.get("half_life_days", 14) or 14)
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            half_life_days = 14.0
        try:
            floor = float(decay.get("floor", 0.20) or 0.20)
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            floor = 0.20

        if half_life_days <= 0:
            continue

        # Prefer confidence map if present; fall back to UWSM
        try:
            conf0 = float(confidence.get(dim, d.get("confidence", floor)))
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            conf0 = float(d.get("confidence", floor) or floor)

        # Clamp inputs
        conf0 = max(0.0, min(1.0, conf0))
        floor = max(0.0, min(1.0, floor))

        factor = 0.5 ** (dt_days / half_life_days)
        conf1 = floor + (conf0 - floor) * factor

        d["confidence"] = conf1
        confidence[str(dim)] = conf1

    return uwsm, confidence


def save_uwsm_state(
    uwsm: dict,
    confidence: Dict[str, float],
    *,
    now: Optional[datetime] = None,
) -> None:
    """
    Persist UWSM to disk atomically. Never raises.
    """
    now = now or _utc_now()
    path = get_uwsm_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "updated_at": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "uwsm": ensure_uwsm(uwsm),
            "confidence": {str(k): float(v) for k, v in (confidence or {}).items()},
        }

        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except (ImportError, OSError, ValueError, KeyError, AttributeError):
                pass
        tmp.replace(path)
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        return

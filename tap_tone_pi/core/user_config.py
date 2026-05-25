# INSTRUMENT CLASS: MEASUREMENT
"""Persistent user configuration for tap_tone_pi.

Stores user preferences (audio device, sample rate, etc.) in a JSON file
at ~/.tap_tone_pi/config.json

This enables:
- Hardware setup wizard to persist device selection
- Auto-detection of preferred device on subsequent runs
- Consistent configuration across CLI, GUI, and scripts
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from tap_tone_pi.core.quality_policy import QualityVerdict


# Default config location
CONFIG_DIR = Path.home() / ".tap_tone_pi"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class AudioDeviceConfig:
    """Validated audio device configuration."""

    index: int
    name: str
    sample_rate: int = 48000
    channels: int = 1
    validated_at: str = ""  # ISO timestamp of last validation

    def __post_init__(self) -> None:
        if not self.validated_at:
            self.validated_at = _utc_now()


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    """Deduplicate strings while preserving insertion order."""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


@dataclass
class FtueState:
    """First-time user experience (FTUE) persistence for agent messaging."""

    pass_count_lifetime: int = 0
    session_count_lifetime: int = 0
    override_count_lifetime: int = 0
    seen_rule_ids: list[str] = field(default_factory=list)
    last_seen_policy_version: str | None = None
    updated_at: str = field(default_factory=lambda: _utc_now())

    SEEN_RULES_CAP: int = 64  # bounded growth

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_count_lifetime": int(self.pass_count_lifetime),
            "session_count_lifetime": int(self.session_count_lifetime),
            "override_count_lifetime": int(self.override_count_lifetime),
            "seen_rule_ids": list(self.seen_rule_ids),
            "last_seen_policy_version": self.last_seen_policy_version,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FtueState":
        """Defensive parsing: never raise for bad ftue payloads."""
        pass_count = d.get("pass_count_lifetime", 0)
        session_count = d.get("session_count_lifetime", 0)
        override_count = d.get("override_count_lifetime", 0)
        seen = d.get("seen_rule_ids", [])
        policy = d.get("last_seen_policy_version", None)
        updated_at = d.get("updated_at", _utc_now())

        if not isinstance(pass_count, int):
            pass_count = 0
        if not isinstance(session_count, int):
            session_count = 0
        if not isinstance(override_count, int):
            override_count = 0
        if not isinstance(seen, list) or any(not isinstance(x, str) for x in seen):
            seen = []
        if policy is not None and not isinstance(policy, str):
            policy = None
        if not isinstance(updated_at, str):
            updated_at = _utc_now()

        # Deduplicate while preserving order; bound size
        seen = _dedupe_preserve_order(seen)
        seen = seen[: cls.SEEN_RULES_CAP]
        return cls(
            pass_count_lifetime=pass_count,
            session_count_lifetime=session_count,
            override_count_lifetime=override_count,
            seen_rule_ids=seen,
            last_seen_policy_version=policy,
            updated_at=updated_at,
        )


@dataclass
class UserConfig:
    """Top-level user configuration."""

    version: str = "1.1.0"
    audio_device: AudioDeviceConfig | None = None
    default_capture_seconds: float = 2.5
    default_output_dir: str = "./out"
    ftue: FtueState = field(default_factory=FtueState)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = {
            "version": self.version,
            "audio_device": asdict(self.audio_device) if self.audio_device else None,
            "default_capture_seconds": self.default_capture_seconds,
            "default_output_dir": self.default_output_dir,
            "ftue": self.ftue.to_dict() if self.ftue else FtueState().to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserConfig":
        """Create from dict (loaded from JSON)."""
        audio_device = None
        if d.get("audio_device"):
            ad = d["audio_device"]
            audio_device = AudioDeviceConfig(
                index=ad["index"],
                name=ad["name"],
                sample_rate=ad.get("sample_rate", 48000),
                channels=ad.get("channels", 1),
                validated_at=ad.get("validated_at", ""),
            )

        # Core fields (never depend on ftue parsing)
        cfg = cls(
            version=d.get("version", "1.1.0"),
            audio_device=audio_device,
            default_capture_seconds=d.get("default_capture_seconds", 2.5),
            default_output_dir=d.get("default_output_dir", "./out"),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
        )

        # FTUE is optional and must never brick config loading
        try:
            ftue_raw = d.get("ftue", None)
            if isinstance(ftue_raw, dict):
                cfg.ftue = FtueState.from_dict(ftue_raw)
            else:
                cfg.ftue = FtueState()
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            cfg.ftue = FtueState()

        return cfg


def load_config(path: Path | None = None) -> UserConfig | None:
    """Load user config from disk.

    Args:
        path: Config file path (defaults to ~/.tap_tone_pi/config.json)

    Returns:
        UserConfig if file exists and is valid, None otherwise
    """
    config_path = path or CONFIG_FILE
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UserConfig.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Corrupted config - return None, caller can re-run wizard
        print(f"Warning: Could not load config from {config_path}: {e}")
        return None


def save_config(config: UserConfig, path: Path | None = None) -> Path:
    """Save user config to disk.

    Uses atomic write (temp + replace) with fsync for Pi power-loss hardening.

    Args:
        config: UserConfig to save
        path: Config file path (defaults to ~/.tap_tone_pi/config.json)

    Returns:
        Path where config was saved
    """
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Update timestamps
    config.updated_at = _utc_now()
    if config.ftue:
        config.ftue.updated_at = _utc_now()

    # Atomic write: temp file -> fsync -> replace
    tmp_path = config_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    tmp_path.replace(config_path)
    return config_path


def get_saved_device() -> AudioDeviceConfig | None:
    """Get the saved audio device configuration.

    Convenience function for quick access to device config.

    Returns:
        AudioDeviceConfig if saved, None otherwise
    """
    config = load_config()
    return config.audio_device if config else None


def clear_config(path: Path | None = None) -> bool:
    """Delete the config file.

    Args:
        path: Config file path (defaults to ~/.tap_tone_pi/config.json)

    Returns:
        True if file was deleted, False if it didn't exist
    """
    config_path = path or CONFIG_FILE
    if config_path.exists():
        config_path.unlink()
        return True
    return False


def get_ftue_state(path: Path | None = None) -> FtueState:
    """Get FTUE state from config, or default if missing."""
    config = load_config(path)
    if config and config.ftue:
        return config.ftue
    return FtueState()


def update_ftue_from_verdict(
    ftue: FtueState,
    *,
    verdict: "QualityVerdict | None",
    policy_version: str | None = None,
    increment_session: bool = False,
) -> FtueState:
    """
    Update FTUE state deterministically from a verdict.

    - PASS increments pass_count_lifetime
    - WARN/FAIL do not increment pass_count_lifetime
    - Rule exposure is recorded when verdict exists
    - Optionally increments session_count_lifetime once per measure invocation
    """
    # Import here to avoid circular dependency
    from tap_tone_pi.core.quality_policy import Verdict

    if increment_session:
        ftue.session_count_lifetime = int(ftue.session_count_lifetime) + 1

    if verdict is None:
        ftue.updated_at = _utc_now()
        return ftue

    # Record rule exposure
    new_ids: list[str] = []
    for tr in getattr(verdict, "triggered_rules", []) or []:
        rid = getattr(getattr(tr, "rule", None), "rule_id", None)
        if isinstance(rid, str):
            new_ids.append(rid)

    combined = _dedupe_preserve_order(list(ftue.seen_rule_ids) + new_ids)
    ftue.seen_rule_ids = combined[: FtueState.SEEN_RULES_CAP]

    # PASS increments pass count (tightening: WARN does NOT)
    try:
        if verdict.verdict == Verdict.PASS:
            ftue.pass_count_lifetime = int(ftue.pass_count_lifetime) + 1
    except (ImportError, OSError, ValueError, KeyError, AttributeError):
        pass

    if policy_version is not None:
        ftue.last_seen_policy_version = policy_version

    ftue.updated_at = _utc_now()
    return ftue


__all__ = [
    "AudioDeviceConfig",
    "FtueState",
    "UserConfig",
    "load_config",
    "save_config",
    "get_saved_device",
    "get_ftue_state",
    "clear_config",
    "update_ftue_from_verdict",
    "CONFIG_DIR",
    "CONFIG_FILE",
]

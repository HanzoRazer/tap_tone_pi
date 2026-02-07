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
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Default config location
CONFIG_DIR = Path.home() / ".tap_tone_pi"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


@dataclass
class UserConfig:
    """Top-level user configuration."""
    version: str = "1.0.0"
    audio_device: AudioDeviceConfig | None = None
    default_capture_seconds: float = 2.5
    default_output_dir: str = "./out"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = {
            "version": self.version,
            "audio_device": asdict(self.audio_device) if self.audio_device else None,
            "default_capture_seconds": self.default_capture_seconds,
            "default_output_dir": self.default_output_dir,
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
        return cls(
            version=d.get("version", "1.0.0"),
            audio_device=audio_device,
            default_capture_seconds=d.get("default_capture_seconds", 2.5),
            default_output_dir=d.get("default_output_dir", "./out"),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
        )


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

    Args:
        config: UserConfig to save
        path: Config file path (defaults to ~/.tap_tone_pi/config.json)

    Returns:
        Path where config was saved
    """
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Update timestamp
    config.updated_at = _utc_now()

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)

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


__all__ = [
    "AudioDeviceConfig",
    "UserConfig",
    "load_config",
    "save_config",
    "get_saved_device",
    "clear_config",
    "CONFIG_DIR",
    "CONFIG_FILE",
]

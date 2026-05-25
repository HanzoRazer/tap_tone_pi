# INSTRUMENT CLASS: MEASUREMENT
"""Session information dataclass for measurement session metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SessionInfo:
    """Information about a measurement session."""

    path: Path
    name: str
    modified: datetime
    session_type: str = "unknown"
    point_count: int = 0
    attempt_count: int = 0
    file_count: int = 0
    size_bytes: int = 0
    has_manifest: bool = False
    latest_verdict: str | None = None

    @classmethod
    def from_path(cls, path: Path) -> "SessionInfo":
        """Create SessionInfo from a session directory path."""
        name = path.name
        modified = datetime.fromtimestamp(path.stat().st_mtime)

        # Count files and calculate size
        file_count = 0
        size_bytes = 0
        has_manifest = False
        point_count = 0
        attempt_count = 0
        session_type = "unknown"
        latest_verdict = None

        try:
            for item in path.rglob("*"):
                if item.is_file():
                    file_count += 1
                    size_bytes += item.stat().st_size
                    if item.name == "manifest.json":
                        has_manifest = True

            # Detect session type
            if (path / "chladni").exists():
                session_type = "chladni"
            elif any(path.glob("*/attempt_*")):
                session_type = "quality_gated"
                # Count points and attempts
                for point_dir in path.iterdir():
                    if point_dir.is_dir() and not point_dir.name.startswith("."):
                        attempts = list(point_dir.glob("attempt_*"))
                        if attempts:
                            point_count += 1
                            attempt_count += len(attempts)
                            # Get latest verdict
                            latest_attempt = sorted(attempts)[-1]
                            qc_file = latest_attempt / "quality_check.json"
                            if qc_file.exists():
                                try:
                                    with open(qc_file) as f:
                                        qc = json.load(f)
                                        latest_verdict = qc.get("verdict", "unknown")
                                except (
                                    ImportError,
                                    OSError,
                                    ValueError,
                                    KeyError,
                                    AttributeError,
                                ):
                                    pass
            elif (path / "analysis").exists():
                session_type = "bending"
            elif (path / "moe").exists():
                session_type = "moe"
            elif any(path.glob("*.wav")):
                session_type = "tap_tone"

        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            pass

        return cls(
            path=path,
            name=name,
            modified=modified,
            session_type=session_type,
            point_count=point_count,
            attempt_count=attempt_count,
            file_count=file_count,
            size_bytes=size_bytes,
            has_manifest=has_manifest,
            latest_verdict=latest_verdict,
        )

    @property
    def size_display(self) -> str:
        """Human-readable size."""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    @property
    def type_icon(self) -> str:
        """Icon for session type."""
        icons = {
            "quality_gated": "🎯",
            "chladni": "🔊",
            "bending": "📏",
            "moe": "📊",
            "tap_tone": "🎵",
            "unknown": "📁",
        }
        return icons.get(self.session_type, "📁")

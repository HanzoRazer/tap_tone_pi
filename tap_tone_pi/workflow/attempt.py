"""Attempt tracking for tap-tone-pi measurements.

Each capture attempt is tracked with its result and quality verdict.
Multiple attempts per measurement point are expected and normal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from tap_tone_pi.core.quality_policy import QualityVerdict, Verdict


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class AttemptStatus(str, Enum):
    """Status of a measurement attempt."""

    PENDING = "pending"  # Not yet captured
    CAPTURED = "captured"  # Captured but not analyzed
    ANALYZED = "analyzed"  # Analyzed but not gated
    PASSED = "passed"  # Passed quality gate
    WARNED = "warned"  # Passed with warnings
    FAILED = "failed"  # Failed quality gate
    OVERRIDDEN = "overridden"  # Failed but operator overrode


@dataclass
class Attempt:
    """A single measurement attempt."""

    attempt_id: str
    point_id: str
    attempt_number: int
    status: AttemptStatus = AttemptStatus.PENDING

    # Timestamps
    created_at: str = field(default_factory=_utc_now)
    captured_at: str | None = None
    analyzed_at: str | None = None
    completed_at: str | None = None

    # Capture info
    device_index: int | None = None
    device_name: str | None = None
    sample_rate: int | None = None
    duration_seconds: float | None = None

    # Analysis summary (subset, full result stored separately)
    dominant_hz: float | None = None
    rms: float | None = None
    confidence: float | None = None
    peak_count: int | None = None
    clipped: bool | None = None

    # Quality verdict
    verdict: str | None = None  # "pass", "warn", "fail"
    triggered_rules: list[str] = field(default_factory=list)

    # Override info
    override_reason: str | None = None
    overridden_at: str | None = None

    # File paths (relative to attempt directory)
    audio_path: str | None = None
    analysis_path: str | None = None
    quality_check_path: str | None = None

    def mark_captured(
        self,
        device_index: int,
        device_name: str,
        sample_rate: int,
        duration_seconds: float,
    ) -> None:
        """Mark attempt as captured."""
        self.status = AttemptStatus.CAPTURED
        self.captured_at = _utc_now()
        self.device_index = device_index
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.duration_seconds = duration_seconds

    def mark_analyzed(
        self,
        dominant_hz: float | None,
        rms: float,
        confidence: float,
        peak_count: int,
        clipped: bool,
    ) -> None:
        """Mark attempt as analyzed."""
        self.status = AttemptStatus.ANALYZED
        self.analyzed_at = _utc_now()
        self.dominant_hz = dominant_hz
        self.rms = rms
        self.confidence = confidence
        self.peak_count = peak_count
        self.clipped = clipped

    def mark_gated(self, verdict: QualityVerdict) -> None:
        """Mark attempt with quality gate result."""
        self.verdict = verdict.verdict.value
        self.triggered_rules = [r.rule.rule_id for r in verdict.triggered_rules]
        self.completed_at = _utc_now()

        if verdict.verdict == Verdict.PASS:
            self.status = AttemptStatus.PASSED
        elif verdict.verdict == Verdict.WARN:
            self.status = AttemptStatus.WARNED
        else:
            self.status = AttemptStatus.FAILED

    def mark_overridden(self, reason: str) -> None:
        """Mark a failed attempt as overridden by operator."""
        if self.status != AttemptStatus.FAILED:
            raise ValueError("Can only override failed attempts")
        self.status = AttemptStatus.OVERRIDDEN
        self.override_reason = reason
        self.overridden_at = _utc_now()

    @property
    def succeeded(self) -> bool:
        """Check if attempt succeeded (passed, warned, or overridden)."""
        return self.status in (
            AttemptStatus.PASSED,
            AttemptStatus.WARNED,
            AttemptStatus.OVERRIDDEN,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Attempt":
        """Create from dict."""
        d = d.copy()
        d["status"] = AttemptStatus(d["status"])
        return cls(**d)


class AttemptStore:
    """Persistent storage for attempts within a session."""

    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _point_dir(self, point_id: str) -> Path:
        """Get directory for a measurement point."""
        return self.session_dir / point_id

    def _attempt_dir(self, point_id: str, attempt_number: int) -> Path:
        """Get directory for a specific attempt."""
        return self._point_dir(point_id) / f"attempt_{attempt_number:03d}"

    def create_attempt(self, point_id: str) -> Attempt:
        """Create a new attempt for a point."""
        # Find next attempt number
        point_dir = self._point_dir(point_id)
        if point_dir.exists():
            existing = [d for d in point_dir.iterdir() if d.name.startswith("attempt_")]
            attempt_number = len(existing) + 1
        else:
            attempt_number = 1

        attempt_id = f"{point_id}_attempt_{attempt_number:03d}"

        attempt = Attempt(
            attempt_id=attempt_id,
            point_id=point_id,
            attempt_number=attempt_number,
        )

        # Create attempt directory
        attempt_dir = self._attempt_dir(point_id, attempt_number)
        attempt_dir.mkdir(parents=True, exist_ok=True)

        return attempt

    def save_attempt(self, attempt: Attempt) -> Path:
        """Save attempt metadata to disk."""
        attempt_dir = self._attempt_dir(attempt.point_id, attempt.attempt_number)
        attempt_dir.mkdir(parents=True, exist_ok=True)

        meta_path = attempt_dir / "attempt_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(attempt.to_dict(), f, indent=2)

        return meta_path

    def load_attempt(self, point_id: str, attempt_number: int) -> Attempt | None:
        """Load attempt from disk."""
        attempt_dir = self._attempt_dir(point_id, attempt_number)
        meta_path = attempt_dir / "attempt_meta.json"

        if not meta_path.exists():
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Attempt.from_dict(data)

    def get_attempt_dir(self, attempt: Attempt) -> Path:
        """Get the directory for an attempt's artifacts."""
        return self._attempt_dir(attempt.point_id, attempt.attempt_number)

    def list_attempts(self, point_id: str) -> list[Attempt]:
        """List all attempts for a point."""
        point_dir = self._point_dir(point_id)
        if not point_dir.exists():
            return []

        attempts = []
        for d in sorted(point_dir.iterdir()):
            if d.name.startswith("attempt_"):
                try:
                    num = int(d.name.split("_")[1])
                    attempt = self.load_attempt(point_id, num)
                    if attempt:
                        attempts.append(attempt)
                except (ValueError, IndexError):
                    pass

        return attempts

    def get_latest_attempt(self, point_id: str) -> Attempt | None:
        """Get the most recent attempt for a point."""
        attempts = self.list_attempts(point_id)
        return attempts[-1] if attempts else None

    def count_attempts(self, point_id: str) -> int:
        """Count attempts for a point."""
        return len(self.list_attempts(point_id))


__all__ = [
    "AttemptStatus",
    "Attempt",
    "AttemptStore",
]

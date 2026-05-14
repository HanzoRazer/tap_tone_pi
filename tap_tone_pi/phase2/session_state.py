"""
Phase 2 Session State — Persistent state for resumable grid capture.

Tracks which points have been captured, failed, or are pending.
Enables --resume flag to pick up where you left off.

Also exposes ``compute_grid_fingerprint`` / ``ensure_resume_grid_matches`` for
``scripts/phase2_slice.py`` checkpoint JSON (same ``session_state.json`` file).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any

from tap_tone_pi.core.grid import Grid

SESSION_STATE_SCHEMA_VERSION = "session_state_v1"
SESSION_STATE_FILENAME = "session_state.json"


def compute_grid_fingerprint(grid_path: Path) -> str:
    """SHA-256 of grid JSON file bytes (stable grid identity for resume)."""
    data = grid_path.expanduser().resolve().read_bytes()
    return hashlib.sha256(data).hexdigest()


def load_session_state(session_dir: Path) -> dict[str, Any]:
    """Load ``session_dir/session_state.json`` as a plain dict."""
    p = session_dir.expanduser().resolve() / SESSION_STATE_FILENAME
    if not p.is_file():
        raise FileNotFoundError(
            f"Resume requires {SESSION_STATE_FILENAME} in {session_dir} "
            f"(start a Phase 2 session with this build to create it)."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def save_session_state(session_dir: Path, state: dict[str, Any]) -> None:
    """Write atomic JSON state (used by ``phase2_slice`` checkpoint rows)."""
    session_dir = session_dir.expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / SESSION_STATE_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def ensure_resume_grid_matches(session_state: dict[str, Any], grid_path: Path) -> None:
    """
    Abort resume if the grid file does not match the session checkpoint.

    Raises:
        ValueError: missing ``grid_id`` or fingerprint mismatch.
    """
    expected = session_state.get("grid_id")
    if not expected:
        raise ValueError(
            "Session state has no grid_id; cannot resume safely. "
            "Re-run Phase 2 with a current build or start a new session."
        )
    actual = compute_grid_fingerprint(grid_path)
    if actual != expected:
        raise ValueError(
            "Grid mismatch: this session was recorded with a different grid file. "
            f"session grid_id={expected[:16]}…, "
            f"provided {grid_path} grid_id={actual[:16]}…. "
            "Use the same grid JSON as the session, or start a new session."
        )


PointStatusLiteral = Literal["pending", "captured", "warning", "failed", "skipped"]


@dataclass
class PointRecord:
    """Record for a single grid point."""

    point_id: str
    status: PointStatusLiteral = "pending"
    coherence: Optional[float] = None
    capture_time_utc: Optional[str] = None
    attempt_count: int = 0
    failure_reason: Optional[str] = None
    wav_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PointRecord":
        return cls(
            point_id=d["point_id"],
            status=d.get("status", "pending"),
            coherence=d.get("coherence"),
            capture_time_utc=d.get("capture_time_utc"),
            attempt_count=d.get("attempt_count", 0),
            failure_reason=d.get("failure_reason"),
            wav_path=d.get("wav_path"),
        )


@dataclass
class SessionState:
    """
    Persistent state for a Phase 2 grid capture session.

    Stored as session_state.json in the session directory.
    Atomic writes via write-to-temp-then-rename pattern.
    """

    # Metadata
    schema_version: str = "session_state_v1"
    session_dir: Path = field(default_factory=Path)
    grid_path: str = ""
    grid_id: str = ""

    # Timestamps
    started_at_utc: str = ""
    last_updated_utc: str = ""

    # Point records
    points: Dict[str, PointRecord] = field(default_factory=dict)

    # Cursor
    current_point: Optional[str] = None
    point_order: List[str] = field(default_factory=list)

    # Session config
    coherence_threshold: float = 0.7
    auto_retry_on_low_coherence: bool = True
    max_attempts_per_point: int = 3

    # Extensible metadata (calibration, environment, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    STATE_FILENAME = "session_state.json"

    @classmethod
    def create(
        cls,
        session_dir: Path,
        grid: Grid,
        grid_path: str = "",
        coherence_threshold: float = 0.7,
    ) -> "SessionState":
        """Create a new session state for a grid."""
        session_dir = Path(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build point order from grid
        point_order = [p.id for p in grid.points]

        # Initialize all points as pending
        points = {p.id: PointRecord(point_id=p.id) for p in grid.points}

        grid_id_val = ""
        if grid_path:
            gp = Path(grid_path)
            if gp.is_file():
                grid_id_val = compute_grid_fingerprint(gp)
            else:
                grid_id_val = getattr(grid, "id", "") or str(grid_path)
        else:
            grid_id_val = getattr(grid, "id", "") or ""

        state = cls(
            session_dir=session_dir,
            grid_path=grid_path,
            grid_id=grid_id_val,
            started_at_utc=now,
            last_updated_utc=now,
            points=points,
            point_order=point_order,
            coherence_threshold=coherence_threshold,
        )

        state.save()
        return state

    @classmethod
    def load(cls, session_dir: Path) -> "SessionState":
        """Load existing session state from directory."""
        session_dir = Path(session_dir)
        state_file = session_dir / cls.STATE_FILENAME

        if not state_file.exists():
            raise FileNotFoundError(
                f"No session state found at {state_file}. "
                f"Use SessionState.create() for new sessions."
            )

        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate schema version
        schema_version = data.get("schema_version", "")
        if not schema_version.startswith("session_state_"):
            raise ValueError(f"Unknown schema version: {schema_version}")

        # Reconstruct points
        points = {}
        for point_data in data.get("points", []):
            record = PointRecord.from_dict(point_data)
            points[record.point_id] = record

        return cls(
            schema_version=schema_version,
            session_dir=session_dir,
            grid_path=data.get("grid_path", ""),
            grid_id=data.get("grid_id", ""),
            started_at_utc=data.get("started_at_utc", ""),
            last_updated_utc=data.get("last_updated_utc", ""),
            points=points,
            current_point=data.get("current_point"),
            point_order=data.get("point_order", list(points.keys())),
            coherence_threshold=data.get("coherence_threshold", 0.7),
            auto_retry_on_low_coherence=data.get("auto_retry_on_low_coherence", True),
            max_attempts_per_point=data.get("max_attempts_per_point", 3),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def exists(cls, session_dir: Path) -> bool:
        """Check if a session state file exists in the directory."""
        return (Path(session_dir) / cls.STATE_FILENAME).exists()

    def save(self) -> None:
        """Save state to disk atomically."""
        self.last_updated_utc = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        data = {
            "schema_version": self.schema_version,
            "grid_path": self.grid_path,
            "grid_id": self.grid_id,
            "started_at_utc": self.started_at_utc,
            "last_updated_utc": self.last_updated_utc,
            "points": [p.to_dict() for p in self.points.values()],
            "current_point": self.current_point,
            "point_order": self.point_order,
            "coherence_threshold": self.coherence_threshold,
            "auto_retry_on_low_coherence": self.auto_retry_on_low_coherence,
            "max_attempts_per_point": self.max_attempts_per_point,
            "metadata": self.metadata,
        }

        state_file = self.session_dir / self.STATE_FILENAME
        temp_file = state_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        shutil.move(str(temp_file), str(state_file))

    def mark_captured(
        self,
        point_id: str,
        coherence: Optional[float] = None,
        wav_path: Optional[str] = None,
    ) -> None:
        """Mark a point as successfully captured."""
        if point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")

        record = self.points[point_id]
        record.attempt_count += 1
        record.capture_time_utc = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        record.coherence = coherence
        record.wav_path = wav_path

        if coherence is not None and coherence < self.coherence_threshold:
            record.status = "warning"
        else:
            record.status = "captured"

    def mark_failed(self, point_id: str, reason: str = "") -> None:
        """Mark a point as failed."""
        if point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")

        record = self.points[point_id]
        record.status = "failed"
        record.attempt_count += 1
        record.failure_reason = reason

    def mark_warning(self, point_id: str, coherence: float) -> None:
        """Mark a point as captured with low coherence warning."""
        if point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")

        record = self.points[point_id]
        record.status = "warning"
        record.coherence = coherence
        record.capture_time_utc = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def mark_skipped(self, point_id: str) -> None:
        """Mark a point as skipped."""
        if point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")

        self.points[point_id].status = "skipped"

    def reset_point(self, point_id: str) -> None:
        """Reset a point to pending status (keeps cumulative ``attempt_count``)."""
        if point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")

        prev_attempts = self.points[point_id].attempt_count
        self.points[point_id] = PointRecord(point_id=point_id)
        self.points[point_id].attempt_count = prev_attempts

    def set_current(self, point_id: Optional[str]) -> None:
        """Set the current point being measured."""
        if point_id is not None and point_id not in self.points:
            raise KeyError(f"Unknown point: {point_id}")
        self.current_point = point_id

    def pending_points(self) -> List[str]:
        """Get list of pending point IDs in order."""
        return [
            pid
            for pid in self.point_order
            if self.points[pid].status == "pending"
        ]

    def completed_points(self) -> List[str]:
        """Get list of completed (captured or warning) point IDs."""
        return [
            pid
            for pid in self.point_order
            if self.points[pid].status in ("captured", "warning")
        ]

    def failed_points(self) -> List[str]:
        """Get list of failed point IDs."""
        return [
            pid
            for pid in self.point_order
            if self.points[pid].status == "failed"
        ]

    def warning_points(self) -> List[str]:
        """Get list of points with low coherence warnings."""
        return [
            pid
            for pid in self.point_order
            if self.points[pid].status == "warning"
        ]

    def next_point(self) -> Optional[str]:
        """Get the next pending point, or None if all done."""
        pending = self.pending_points()
        return pending[0] if pending else None

    def is_complete(self) -> bool:
        """Check if all points have been captured (including warnings)."""
        return len(self.pending_points()) == 0 and len(self.failed_points()) == 0

    def progress_pct(self) -> float:
        """Get completion percentage."""
        total = len(self.points)
        done = len(self.completed_points())
        return (done / total * 100) if total > 0 else 0.0

    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            "total": len(self.points),
            "captured": len(
                [p for p in self.points.values() if p.status == "captured"]
            ),
            "warning": len(
                [p for p in self.points.values() if p.status == "warning"]
            ),
            "failed": len([p for p in self.points.values() if p.status == "failed"]),
            "pending": len(
                [p for p in self.points.values() if p.status == "pending"]
            ),
            "skipped": len(
                [p for p in self.points.values() if p.status == "skipped"]
            ),
            "progress_pct": self.progress_pct(),
            "is_complete": self.is_complete(),
        }


def demo() -> None:
    """Demo session state management."""
    import tempfile
    from tap_tone_pi.core.grid import GridPoint

    points = [
        GridPoint(id="A1", x=0.0, y=0.0),
        GridPoint(id="A2", x=50.0, y=0.0),
        GridPoint(id="B1", x=0.0, y=50.0),
        GridPoint(id="B2", x=50.0, y=50.0),
    ]
    grid = Grid(units="mm", origin="center", points=points)

    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / "session_001"

        state = SessionState.create(session_dir, grid, grid_path="test_grid.json")
        print(f"Created session at {session_dir}")
        print(f"Pending: {state.pending_points()}")

        state.set_current("A1")
        state.mark_captured("A1", coherence=0.95)

        state.set_current("A2")
        state.mark_captured("A2", coherence=0.55)

        state.set_current("B1")
        state.mark_failed("B1", reason="Audio timeout")

        state.save()

        loaded = SessionState.load(session_dir)
        print(f"\nLoaded session:")
        print(f"  Summary: {loaded.summary()}")
        print(f"  Next point: {loaded.next_point()}")
        print(f"  Warnings: {loaded.warning_points()}")
        print(f"  Failed: {loaded.failed_points()}")


if __name__ == "__main__":
    demo()

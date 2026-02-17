"""Multi-point measurement grid (Phase 9).

Provides:
- GridPoint: A single measurement location with (x, y) coordinates
- Grid: Collection of points with units and origin info
- GridSession: Tracks measurement progress across a grid
- Factory methods for common grid patterns (rectangular, circular)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

def _row_to_letters(row: int) -> str:
    """Convert row index to spreadsheet-style letter ID.

    m4 Audit Fix: Grid ID breaks at 26 rows.
    Generates Excel-style column letters: A-Z, AA-AZ, BA-BZ, etc.

    Args:
        row: Zero-based row index

    Returns:
        Letter ID (A, B, ... Z, AA, AB, ... AZ, BA, ...)
    """
    result = []
    n = row + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))

class PointStatus(str, Enum):
    """Status of a measurement point."""

    PENDING = "pending"  # Not yet measured
    PASSED = "passed"  # Measurement passed quality gate
    WARNED = "warned"  # Measurement passed with warnings
    FAILED = "failed"  # Most recent attempt failed
    SKIPPED = "skipped"  # Intentionally skipped


@dataclass
class GridPoint:
    """A single point in the measurement grid."""

    id: str
    x: float
    y: float
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        d: dict[str, Any] = {"id": self.id, "x": self.x, "y": self.y}
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GridPoint":
        """Create from dict."""
        return cls(
            id=str(d["id"]),
            x=float(d["x"]),
            y=float(d["y"]),
            label=d.get("label"),
        )


@dataclass
class Grid:
    """A measurement grid with multiple points.

    Attributes:
        grid_id: Unique identifier for this grid
        name: Human-readable name
        units: Coordinate units (mm, in, etc.)
        origin: Description of the origin point
        points: List of measurement points
        created_at: When grid was created
    """

    grid_id: str
    name: str
    units: str
    origin: str
    points: list[GridPoint]
    created_at: str = field(default_factory=_utc_now)

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self):
        return iter(self.points)

    def __getitem__(self, index: int) -> GridPoint:
        return self.points[index]

    def get_point(self, point_id: str) -> GridPoint | None:
        """Get a point by ID."""
        for p in self.points:
            if p.id == point_id:
                return p
        return None

    def point_ids(self) -> list[str]:
        """Get list of all point IDs."""
        return [p.id for p in self.points]

    def bounds(self) -> tuple[float, float, float, float]:
        """Get bounding box (min_x, min_y, max_x, max_y)."""
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "grid_id": self.grid_id,
            "name": self.name,
            "units": self.units,
            "origin": self.origin,
            "points": [p.to_dict() for p in self.points],
            "created_at": self.created_at,
        }

    def save(self, path: Path) -> None:
        """Save grid to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Grid":
        """Create from dict."""
        return cls(
            grid_id=d.get("grid_id", "grid_001"),
            name=d.get("name", "Unnamed Grid"),
            units=d.get("units", "mm"),
            origin=d.get("origin", "unspecified"),
            points=[GridPoint.from_dict(p) for p in d.get("points", [])],
            created_at=d.get("created_at", _utc_now()),
        )

    @classmethod
    def load(cls, path: Path) -> "Grid":
        """Load grid from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def rectangular(
        cls,
        rows: int,
        cols: int,
        spacing: float,
        units: str = "mm",
        origin: str = "bottom-left",
        grid_id: str | None = None,
        name: str | None = None,
    ) -> "Grid":
        """Create a rectangular grid.

        Args:
            rows: Number of rows
            cols: Number of columns
            spacing: Distance between points
            units: Coordinate units
            origin: Origin description
            grid_id: Optional grid ID
            name: Optional grid name

        Returns:
            Grid with rows x cols points
        """
        points = []
        for row in range(rows):
            for col in range(cols):
                row_letter = _row_to_letters(row)  # m4 fix: extended letter IDs
                point_id = f"{row_letter}{col + 1}"  # A1, A2, ..., AA1, etc.
                points.append(
                    GridPoint(
                        id=point_id,
                        x=col * spacing,
                        y=row * spacing,
                        label=point_id,
                    )
                )

        return cls(
            grid_id=grid_id or f"rect_{rows}x{cols}",
            name=name or f"{rows}x{cols} Rectangular Grid",
            units=units,
            origin=origin,
            points=points,
        )

    @classmethod
    def circular(
        cls,
        num_points: int,
        radius: float,
        units: str = "mm",
        origin: str = "center",
        include_center: bool = True,
        grid_id: str | None = None,
        name: str | None = None,
    ) -> "Grid":
        """Create a circular grid.

        Args:
            num_points: Number of points on the circle
            radius: Radius of the circle
            units: Coordinate units
            origin: Origin description
            include_center: Include a point at center
            grid_id: Optional grid ID
            name: Optional grid name

        Returns:
            Grid with points arranged in a circle
        """
        points = []

        # Center point
        if include_center:
            points.append(GridPoint(id="C", x=0, y=0, label="Center"))

        # Perimeter points
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            point_id = f"P{i + 1}"
            points.append(GridPoint(id=point_id, x=x, y=y, label=point_id))

        return cls(
            grid_id=grid_id or f"circ_{num_points}",
            name=name or f"{num_points}-Point Circular Grid",
            units=units,
            origin=origin,
            points=points,
        )

    @classmethod
    def line(
        cls,
        num_points: int,
        length: float,
        units: str = "mm",
        orientation: str = "horizontal",
        grid_id: str | None = None,
        name: str | None = None,
    ) -> "Grid":
        """Create a line grid (1D array of points).

        Args:
            num_points: Number of points
            length: Total length of line
            units: Coordinate units
            orientation: "horizontal" or "vertical"
            grid_id: Optional grid ID
            name: Optional grid name

        Returns:
            Grid with points in a line
        """
        spacing = length / (num_points - 1) if num_points > 1 else 0
        points = []

        for i in range(num_points):
            point_id = f"L{i + 1}"
            if orientation == "horizontal":
                points.append(
                    GridPoint(id=point_id, x=i * spacing, y=0, label=point_id)
                )
            else:
                points.append(
                    GridPoint(id=point_id, x=0, y=i * spacing, label=point_id)
                )

        return cls(
            grid_id=grid_id or f"line_{num_points}",
            name=name or f"{num_points}-Point Line",
            units=units,
            origin="start",
            points=points,
        )


@dataclass
class PointProgress:
    """Progress for a single measurement point."""

    point_id: str
    status: PointStatus = PointStatus.PENDING
    attempt_count: int = 0
    dominant_hz: float | None = None
    last_updated: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "point_id": self.point_id,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "dominant_hz": self.dominant_hz,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PointProgress":
        """Create from dict."""
        return cls(
            point_id=d["point_id"],
            status=PointStatus(d.get("status", "pending")),
            attempt_count=d.get("attempt_count", 0),
            dominant_hz=d.get("dominant_hz"),
            last_updated=d.get("last_updated", _utc_now()),
        )


@dataclass
class GridSession:
    """Tracks measurement progress across a grid.

    Attributes:
        session_id: Unique session identifier
        grid: The measurement grid
        progress: Dict of point_id -> PointProgress
        current_index: Index of current point being measured
        started_at: When session started
        completed_at: When session completed (all points done)
    """

    session_id: str
    grid: Grid
    progress: dict[str, PointProgress] = field(default_factory=dict)
    current_index: int = 0
    started_at: str = field(default_factory=_utc_now)
    completed_at: str | None = None

    def __post_init__(self):
        """Initialize progress for all points."""
        for point in self.grid.points:
            if point.id not in self.progress:
                self.progress[point.id] = PointProgress(point_id=point.id)

    @property
    def total_points(self) -> int:
        """Total number of points in grid."""
        return len(self.grid)

    @property
    def completed_count(self) -> int:
        """Number of points with successful measurements."""
        return sum(
            1
            for p in self.progress.values()
            if p.status in (PointStatus.PASSED, PointStatus.WARNED, PointStatus.SKIPPED)
        )

    @property
    def failed_count(self) -> int:
        """Number of points with failed measurements."""
        return sum(1 for p in self.progress.values() if p.status == PointStatus.FAILED)

    @property
    def pending_count(self) -> int:
        """Number of points not yet measured."""
        return sum(1 for p in self.progress.values() if p.status == PointStatus.PENDING)

    @property
    def is_complete(self) -> bool:
        """Check if all points have been measured."""
        return self.pending_count == 0 and self.failed_count == 0

    @property
    def current_point(self) -> GridPoint | None:
        """Get the current point to measure."""
        if 0 <= self.current_index < len(self.grid):
            return self.grid[self.current_index]
        return None

    def next_pending(self) -> GridPoint | None:
        """Find the next pending point."""
        for point in self.grid.points:
            if self.progress[point.id].status == PointStatus.PENDING:
                return point
        return None

    def mark_passed(self, point_id: str, dominant_hz: float) -> None:
        """Mark a point as passed."""
        if point_id in self.progress:
            prog = self.progress[point_id]
            prog.status = PointStatus.PASSED
            prog.dominant_hz = dominant_hz
            prog.attempt_count += 1
            prog.last_updated = _utc_now()
            self._advance()

    def mark_warned(self, point_id: str, dominant_hz: float) -> None:
        """Mark a point as warned (passed with warnings)."""
        if point_id in self.progress:
            prog = self.progress[point_id]
            prog.status = PointStatus.WARNED
            prog.dominant_hz = dominant_hz
            prog.attempt_count += 1
            prog.last_updated = _utc_now()
            self._advance()

    def mark_failed(self, point_id: str) -> None:
        """Mark a point as failed."""
        if point_id in self.progress:
            prog = self.progress[point_id]
            prog.status = PointStatus.FAILED
            prog.attempt_count += 1
            prog.last_updated = _utc_now()

    def mark_skipped(self, point_id: str) -> None:
        """Mark a point as skipped."""
        if point_id in self.progress:
            prog = self.progress[point_id]
            prog.status = PointStatus.SKIPPED
            prog.last_updated = _utc_now()
            self._advance()

    def reset_point(self, point_id: str) -> None:
        """Reset a point to pending."""
        if point_id in self.progress:
            prog = self.progress[point_id]
            prog.status = PointStatus.PENDING
            prog.dominant_hz = None
            prog.last_updated = _utc_now()

    def _advance(self) -> None:
        """Advance to next point."""
        self.current_index += 1
        if self.current_index >= len(self.grid):
            if self.is_complete:
                self.completed_at = _utc_now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "session_id": self.session_id,
            "grid": self.grid.to_dict(),
            "progress": {k: v.to_dict() for k, v in self.progress.items()},
            "current_index": self.current_index,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def save(self, path: Path) -> None:
        """Save session to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GridSession":
        """Create from dict."""
        grid = Grid.from_dict(d["grid"])
        progress = {
            k: PointProgress.from_dict(v) for k, v in d.get("progress", {}).items()
        }
        return cls(
            session_id=d["session_id"],
            grid=grid,
            progress=progress,
            current_index=d.get("current_index", 0),
            started_at=d.get("started_at", _utc_now()),
            completed_at=d.get("completed_at"),
        )

    @classmethod
    def load(cls, path: Path) -> "GridSession":
        """Load session from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


__all__ = [
    "PointStatus",
    "GridPoint",
    "Grid",
    "PointProgress",
    "GridSession",
]

"""
Phase 2 session loader — reads a Phase 2 scanning session directory and
produces an in-memory representation suitable for visualization.

Phase 2 sessions are produced by scripts/phase2_slice.py and contain:
  {session_dir}/
  ├── grid.json                       (phase2_grid)
  ├── session_meta.json               (phase2_session_meta_v1)
  ├── derived/
  │   ├── ods_snapshot.json           (phase2_ods_snapshot_v2)
  │   └── wsi_curve.json              (optional)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass
class Phase2Point:
    """Per-point measurement data extracted from ods_snapshot."""

    point_id: str
    x_mm: float
    y_mm: float
    H_mag: np.ndarray  # shape (n_freqs,)
    H_phase_deg: np.ndarray  # shape (n_freqs,)
    coherence: Optional[np.ndarray]  # shape (n_freqs,) or None


@dataclass
class Phase2Session:
    """Loaded Phase 2 scanning session."""

    session_dir: Path
    session_meta: dict[str, Any]  # phase2_session_meta_v1 contents
    grid_meta: dict[str, Any]  # grid.json contents (units, origin)
    freqs_hz: np.ndarray  # the scan frequency axis
    points: list[Phase2Point]  # per-point measurements

    # Optional artifacts
    wsi_curve: Optional[dict[str, Any]] = None

    # Build record linkage (populated by auto-discovery)
    build_id: Optional[str] = None

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_freqs(self) -> int:
        return len(self.freqs_hz)

    def amplitude_at_freq(self, freq_hz: float) -> dict[str, float]:
        """Return {point_id: H_mag} interpolated at the given frequency."""
        result = {}
        for p in self.points:
            value = float(np.interp(freq_hz, self.freqs_hz, p.H_mag))
            result[p.point_id] = value
        return result

    def amplitude_at_freq_index(self, idx: int) -> dict[str, float]:
        """Return {point_id: H_mag} at the given frequency index (no interpolation)."""
        result = {}
        for p in self.points:
            result[p.point_id] = float(p.H_mag[idx])
        return result

    def phase_at_freq_index(self, idx: int) -> dict[str, float]:
        """Return {point_id: H_phase_deg} at the given frequency index."""
        result = {}
        for p in self.points:
            result[p.point_id] = float(p.H_phase_deg[idx])
        return result

    def peak_response_freq(self) -> float:
        """Return the frequency where mean(H_mag across all points) is maximal."""
        if not self.points or self.n_freqs == 0:
            return 0.0
        mean_mag = np.zeros(self.n_freqs)
        for p in self.points:
            mean_mag += p.H_mag
        mean_mag /= self.n_points
        return float(self.freqs_hz[int(np.argmax(mean_mag))])

    def get_point_coords(self) -> list[tuple[str, float, float]]:
        """Return list of (point_id, x_mm, y_mm) tuples."""
        return [(p.point_id, p.x_mm, p.y_mm) for p in self.points]


class Phase2SessionLoadError(Exception):
    """Raised when a Phase 2 session cannot be loaded."""


def load_phase2_session(session_dir: Path) -> Phase2Session:
    """Load a Phase 2 session from a directory.

    Args:
        session_dir: Path to the session directory.

    Returns:
        Phase2Session populated from disk.

    Raises:
        Phase2SessionLoadError: If the session directory is malformed or
            missing required files.
    """
    session_dir = Path(session_dir)
    if not session_dir.is_dir():
        raise Phase2SessionLoadError(f"Not a directory: {session_dir}")

    # Required files
    grid_path = session_dir / "grid.json"
    meta_path = session_dir / "session_meta.json"
    snapshot_path = session_dir / "derived" / "ods_snapshot.json"

    for required in (grid_path, meta_path, snapshot_path):
        if not required.exists():
            raise Phase2SessionLoadError(
                f"Required file missing: {required.relative_to(session_dir)}"
            )

    try:
        grid_meta = json.loads(grid_path.read_text(encoding="utf-8"))
        session_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Phase2SessionLoadError(f"Invalid JSON: {e}")

    # Sanity check schema versions
    snapshot_schema = snapshot.get("schema_version", "")
    if not snapshot_schema.startswith("phase2_ods_snapshot"):
        raise Phase2SessionLoadError(
            f"Unexpected ods_snapshot schema_version: {snapshot_schema!r}"
        )

    # Build Phase2Points from snapshot
    freqs_hz = np.asarray(snapshot.get("freqs_hz", []), dtype=float)
    if freqs_hz.size == 0:
        raise Phase2SessionLoadError("ods_snapshot has empty freqs_hz")

    points = []
    for pt_data in snapshot.get("points", []):
        try:
            point = Phase2Point(
                point_id=pt_data["point_id"],
                x_mm=float(pt_data["x_mm"]),
                y_mm=float(pt_data["y_mm"]),
                H_mag=np.asarray(pt_data["H_mag"], dtype=float),
                H_phase_deg=np.asarray(pt_data["H_phase_deg"], dtype=float),
                coherence=(
                    np.asarray(pt_data["coherence"], dtype=float)
                    if "coherence" in pt_data
                    else None
                ),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise Phase2SessionLoadError(f"Malformed point in ods_snapshot: {e}")
        # Sanity: arrays should be same length as freqs_hz
        if point.H_mag.shape != freqs_hz.shape:
            raise Phase2SessionLoadError(
                f"Point {point.point_id}: H_mag length "
                f"{point.H_mag.size} != freqs_hz length {freqs_hz.size}"
            )
        points.append(point)

    if not points:
        raise Phase2SessionLoadError("ods_snapshot has no points")

    # Optional WSI curve
    wsi_path = session_dir / "derived" / "wsi_curve.json"
    wsi_curve = None
    if wsi_path.exists():
        try:
            wsi_curve = json.loads(wsi_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # Extract build_id from session_meta if present
    build_id = session_meta.get("build_id") or session_meta.get("instrument_id")

    return Phase2Session(
        session_dir=session_dir,
        session_meta=session_meta,
        grid_meta=grid_meta,
        freqs_hz=freqs_hz,
        points=points,
        wsi_curve=wsi_curve,
        build_id=build_id,
    )


def try_discover_build_record(session: Phase2Session) -> Optional[dict[str, Any]]:
    """Attempt to find and load a matching build record for the session.

    Looks for a build record at ~/.tap_tone_pi/builds_db.json that matches
    the session's build_id or instrument_id.

    Args:
        session: The loaded Phase2Session

    Returns:
        The matching build record dict, or None if not found
    """
    if session.build_id is None:
        return None

    from tap_tone_pi.materials.build_record import (
        BuildDatabase,
        BuildNotFoundError,
        build_to_dict,
    )

    try:
        db = BuildDatabase()
        db.load()
        build = db.get_build(session.build_id)
        return build_to_dict(build)
    except (BuildNotFoundError, FileNotFoundError, Exception):
        return None

"""
mode_shape_render.py — Render Rayleigh-Ritz mode shapes onto Phase 2 measurement grids.

Bridges the gap between the Rayleigh-Ritz solver (which produces mode shapes on a
plate-domain grid in meters, origin at corner) and the Phase 2 measurement workflow
(which captures amplitude/phase at named grid points in mm with various origin
conventions).

This module is a thin wrapper around RayleighRitzResult.get_mode_shape() that:

1. Translates a Phase 2 Grid into a coordinate array compatible with the solver
2. Calls the existing solver method
3. Returns predicted amplitudes keyed by point_id, normalized to peak

Use case:
    Given a Carlos Jumbo soundboard's Rayleigh-Ritz solution and a 16-point
    Phase 2 measurement grid, predict the (1,1) mode amplitude at each grid
    point. The output dict {"A1": 0.42, "A2": 0.71, ...} is the per-point
    prediction that DO-002 will compare against measured amplitudes.

Coordinate transform (this is the core work):

    Phase 2 grid coords          Solver plate coords
    ───────────────────          ────────────────────
    Units: mm                    Units: m
    Origin: configurable         Origin: corner (0, 0)
    Axes: x = treble (+),        Axes: x = grain L (+a),
          y = tail (+)                 y = cross-grain C (+b)

Supported grid origins:
    - "lower_bout_center"  — phase2_grid_mm.json default
    - "plate_corner"       — solver native, no translation
    - "soundhole_center"   — for soundhole-relative grids
    - "bridge_position"    — for bridge-relative grids

Adding new origins: add to ORIGIN_OFFSETS dispatch table at module bottom.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from tap_tone_pi.design.rayleigh_ritz import RayleighRitzResult


# =============================================================================
# Public API
# =============================================================================


@dataclass(frozen=True)
class GridPointLike:
    """Minimal point interface compatible with scripts/phase2/grid.py:GridPoint.

    We accept either the canonical GridPoint or any object with these attributes,
    avoiding a hard import dependency on scripts/phase2/.
    """

    id: str
    x: float
    y: float


@dataclass(frozen=True)
class GridLike:
    """Minimal grid interface compatible with scripts/phase2/grid.py:Grid."""

    units: str
    origin: str
    points: list[GridPointLike]


@dataclass(frozen=True)
class RenderedModeShape:
    """A predicted mode shape evaluated at named grid points.

    Attributes:
        mode_index: Solver mode index (0 = fundamental)
        mode_indices: (m, n) shape indices from RayleighRitzMode
        frequency_Hz: Predicted frequency from solver
        amplitudes_by_id: Dict mapping point_id → normalized amplitude in [-1, 1].
                          Sign is preserved (modes have positive and negative regions).
        out_of_plate_ids: Set of point_ids that fell outside the plate domain.
        peak_amplitude_raw: The unnormalized peak |w| value, useful for debugging.
        grid_origin_used: Origin convention applied during the transform.
        plate_dimensions_mm: Plate (a, b) in mm, recorded for traceability.
    """

    mode_index: int
    mode_indices: tuple[int, int]
    frequency_Hz: float
    amplitudes_by_id: dict[str, float]
    out_of_plate_ids: set[str]
    peak_amplitude_raw: float
    grid_origin_used: str
    plate_dimensions_mm: tuple[float, float]


def render_mode_shape_on_grid(
    result: RayleighRitzResult,
    grid: GridLike,
    mode_index: int = 0,
    grid_origin: Optional[str] = None,
    x_axis: str = "grain",
    y_axis: str = "cross_grain",
    normalize: bool = True,
) -> RenderedModeShape:
    """Evaluate a Rayleigh-Ritz mode shape at each Phase 2 grid point.

    Args:
        result: Solver output containing modes and plate dimensions.
        grid: Phase 2 grid with named points in mm.
        mode_index: Which mode to render (0 = fundamental).
        grid_origin: Override grid.origin string. If None, uses grid.origin.
        x_axis: Which physical direction the grid's +x represents.
                "grain" (default) or "cross_grain".
        y_axis: Which physical direction the grid's +y represents.
                "cross_grain" (default) or "grain".
        normalize: If True (default), scale so peak |amplitude| = 1.0
                   while preserving sign.

    Returns:
        RenderedModeShape with per-point amplitudes and metadata.

    Raises:
        ValueError: If grid units are not "mm".
        ValueError: If grid_origin is unknown.
        ValueError: If x_axis and y_axis specify the same direction.
        IndexError: If mode_index is out of range.
    """
    if grid.units != "mm":
        raise ValueError(
            f"Expected grid.units == 'mm', got {grid.units!r}. "
            "Convert grid to mm before rendering."
        )

    if mode_index < 0 or mode_index >= result.n_modes:
        raise IndexError(
            f"mode_index={mode_index} out of range; solver has {result.n_modes} modes."
        )

    if x_axis == y_axis:
        raise ValueError(
            f"x_axis and y_axis must differ; got both = {x_axis!r}."
        )

    valid_axes = {"grain", "cross_grain"}
    if x_axis not in valid_axes or y_axis not in valid_axes:
        raise ValueError(
            f"axes must be one of {valid_axes}; got x_axis={x_axis!r}, y_axis={y_axis!r}."
        )

    # Plate dimensions: a is along grain (L), b is across grain (C). Stored in meters.
    a_m = result.plate.a
    b_m = result.plate.b
    a_mm = a_m * 1000.0
    b_mm = b_m * 1000.0

    # Resolve grid origin
    origin_name = grid_origin if grid_origin is not None else grid.origin
    origin_offset = _get_origin_offset_mm(origin_name, a_mm, b_mm, x_axis, y_axis)

    # Transform each point: grid_mm → plate_corner_mm → plate_corner_m
    point_ids: list[str] = []
    plate_x_m: list[float] = []
    plate_y_m: list[float] = []
    out_of_plate: set[str] = set()

    for p in grid.points:
        # Apply origin offset (translation)
        gx_mm = p.x + origin_offset[0]
        gy_mm = p.y + origin_offset[1]

        # Map grid axes to plate axes (grain x cross-grain)
        if x_axis == "grain":
            plate_xa_mm = gx_mm  # along grain, plate domain [0, a_mm]
            plate_yb_mm = gy_mm  # across grain, plate domain [0, b_mm]
        else:
            # x_axis == "cross_grain", so y_axis == "grain"
            plate_xa_mm = gy_mm  # grid +y is grain direction
            plate_yb_mm = gx_mm  # grid +x is cross-grain direction

        # Check plate domain. Allow small floating-point overshoot.
        eps_mm = 0.5
        if (
            plate_xa_mm < -eps_mm
            or plate_xa_mm > a_mm + eps_mm
            or plate_yb_mm < -eps_mm
            or plate_yb_mm > b_mm + eps_mm
        ):
            out_of_plate.add(p.id)
            continue

        # Clamp tiny overshoots to plate edges
        plate_xa_mm = max(0.0, min(a_mm, plate_xa_mm))
        plate_yb_mm = max(0.0, min(b_mm, plate_yb_mm))

        point_ids.append(p.id)
        plate_x_m.append(plate_xa_mm / 1000.0)
        plate_y_m.append(plate_yb_mm / 1000.0)

    # Evaluate solver mode at each unique point individually.
    # We don't use get_mode_shape's meshgrid because our grid is scattered (not regular).
    # Instead, evaluate each point as a 1x1 mesh.
    mode = result.modes[mode_index]
    amplitudes_by_id: dict[str, float] = {}

    for pid, x_m, y_m in zip(point_ids, plate_x_m, plate_y_m):
        x_arr = np.array([x_m], dtype=np.float64)
        y_arr = np.array([y_m], dtype=np.float64)
        # get_mode_shape returns shape (len(x), len(y)) = (1, 1)
        w = result.get_mode_shape(mode_index, x_arr, y_arr)
        amplitudes_by_id[pid] = float(w[0, 0])

    # Normalize so peak |amplitude| = 1.0, preserving sign.
    if amplitudes_by_id:
        peak_raw = max(abs(v) for v in amplitudes_by_id.values())
    else:
        peak_raw = 0.0

    if normalize and peak_raw > 0.0:
        amplitudes_by_id = {
            pid: v / peak_raw for pid, v in amplitudes_by_id.items()
        }

    return RenderedModeShape(
        mode_index=mode_index,
        mode_indices=mode.mode_indices,
        frequency_Hz=mode.frequency_Hz,
        amplitudes_by_id=amplitudes_by_id,
        out_of_plate_ids=out_of_plate,
        peak_amplitude_raw=peak_raw,
        grid_origin_used=origin_name,
        plate_dimensions_mm=(a_mm, b_mm),
    )


# =============================================================================
# Origin convention dispatch
# =============================================================================


def _get_origin_offset_mm(
    origin_name: str,
    a_mm: float,
    b_mm: float,
    x_axis: str,
    y_axis: str,
) -> tuple[float, float]:
    """Return (dx, dy) in mm such that grid_mm + offset = plate_corner_mm.

    For each origin convention, we compute where the origin sits in plate-corner
    coordinates, then return its negation as the offset to add to grid coordinates.

    For example, "lower_bout_center" sits at the center of the plate in
    plate-corner coordinates: (a_mm/2, b_mm/2). To shift grid → plate_corner,
    we add (a_mm/2, b_mm/2) to each grid point.

    Args:
        origin_name: Origin convention string.
        a_mm: Plate dimension along grain (L), in mm.
        b_mm: Plate dimension across grain (C), in mm.
        x_axis: Which physical direction the grid's +x represents.
        y_axis: Which physical direction the grid's +y represents.

    Returns:
        (dx_mm, dy_mm) offset to add to grid coordinates.

    Raises:
        ValueError: If origin_name is not in ORIGIN_OFFSETS.
    """
    if origin_name not in ORIGIN_OFFSETS:
        valid = ", ".join(sorted(ORIGIN_OFFSETS.keys()))
        raise ValueError(
            f"Unknown grid origin {origin_name!r}. "
            f"Supported: {valid}. "
            "Add to ORIGIN_OFFSETS in mode_shape_render.py if needed."
        )

    return ORIGIN_OFFSETS[origin_name](a_mm, b_mm, x_axis, y_axis)


def _origin_lower_bout_center(
    a_mm: float, b_mm: float, x_axis: str, y_axis: str
) -> tuple[float, float]:
    """Origin at plate center: grid coords are centered, plate coords are corner-based."""
    # Grid origin sits at plate-corner coord (a_mm/2, b_mm/2) when grid x = grain.
    # If grid x = cross_grain, then grid origin sits at (b_mm/2, a_mm/2).
    if x_axis == "grain":
        return (a_mm / 2.0, b_mm / 2.0)
    else:
        return (b_mm / 2.0, a_mm / 2.0)


def _origin_plate_corner(
    a_mm: float, b_mm: float, x_axis: str, y_axis: str
) -> tuple[float, float]:
    """Origin at plate corner: grid coords already match solver, no translation."""
    return (0.0, 0.0)


def _origin_soundhole_center(
    a_mm: float, b_mm: float, x_axis: str, y_axis: str
) -> tuple[float, float]:
    """Origin at typical soundhole position.

    Convention used here: soundhole sits at upper bout, approximately
    25% from the neck end of the plate. This is a default — for non-standard
    body shapes, use 'plate_corner' or extend ORIGIN_OFFSETS.
    """
    if x_axis == "grain":
        return (0.25 * a_mm, b_mm / 2.0)
    else:
        return (b_mm / 2.0, 0.25 * a_mm)


def _origin_bridge_position(
    a_mm: float, b_mm: float, x_axis: str, y_axis: str
) -> tuple[float, float]:
    """Origin at typical bridge position.

    Convention: bridge sits at approximately 70% from the neck end of the plate
    (lower bout). This is a default and may need adjustment per design.
    """
    if x_axis == "grain":
        return (0.70 * a_mm, b_mm / 2.0)
    else:
        return (b_mm / 2.0, 0.70 * a_mm)


# Dispatch table. To support a new origin convention, add an entry here.
# Each function takes (a_mm, b_mm, x_axis, y_axis) and returns (dx_mm, dy_mm).
ORIGIN_OFFSETS = {
    "lower_bout_center": _origin_lower_bout_center,
    "plate_corner": _origin_plate_corner,
    "soundhole_center": _origin_soundhole_center,
    "bridge_position": _origin_bridge_position,
}


# =============================================================================
# Convenience: load Phase 2 grid from JSON
# =============================================================================


def load_grid_compatible(grid_dict: dict) -> GridLike:
    """Load a Phase 2 grid dict (parsed from JSON) into a GridLike.

    Accepts the format from examples/phase2_grid_mm.json:
        {"units": "mm", "origin": "...", "points": [{"id": "A1", "x": ..., "y": ...}, ...]}

    Also accepts the contracts/phase2_grid.schema.json format with point_id field.

    This is a convenience function for tests and CLI use. Production code can
    pass any GridLike-compatible object (e.g., scripts.phase2.grid.Grid).
    """
    points = []
    for p in grid_dict.get("points", []):
        # Support both "id" and "point_id" key names
        pid = p.get("id") or p.get("point_id")
        if pid is None:
            raise ValueError(f"Grid point missing 'id' or 'point_id': {p}")

        # Support both flat x/y and explicit x_mm/y_mm
        x = p.get("x")
        if x is None:
            x = p.get("x_mm")
        y = p.get("y")
        if y is None:
            y = p.get("y_mm")
        if x is None or y is None:
            raise ValueError(f"Grid point {pid} missing coordinates: {p}")

        points.append(GridPointLike(id=str(pid), x=float(x), y=float(y)))

    return GridLike(
        units=str(grid_dict.get("units", "mm")),
        origin=str(grid_dict.get("origin", "unknown")),
        points=points,
    )

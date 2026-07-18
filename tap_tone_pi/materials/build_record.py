# INSTRUMENT CLASS: MEASUREMENT
"""
build_record.py — Per-build instrument record database.

Persistent JSON store for instrument build records. Links together:
- Wood selection (flitch_ids from wood_db.py)
- As-built dimensions
- Measurement session paths
- Predictions and measured values
- Residual computations
- Subjective evaluations

This module enforces the instrument_build_record_v1 schema.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

SCHEMA_VERSION = "instrument_build_record_v1"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "contracts"
    / "instrument_build_record_v1.schema.json"
)

DEFAULT_BUILDS_PATH = Path.home() / ".tap_tone_pi" / "builds_db.json"
ENV_BUILDS_PATH_OVERRIDE = "TTP_BUILDS_DB_PATH"


def get_builds_path() -> Path:
    """Return the configured builds database path, honoring TTP_BUILDS_DB_PATH override."""
    override = os.environ.get(ENV_BUILDS_PATH_OVERRIDE)
    if override:
        return Path(override).expanduser()
    return DEFAULT_BUILDS_PATH


_BUILD_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")


# -----------------------------------------------------------------------------
# Nested dataclasses
# -----------------------------------------------------------------------------


@dataclass
class WoodSelection:
    """Wood flitch selections for a build."""

    top_flitch_id: Optional[str] = None
    top_subid: Optional[str] = None
    back_flitch_id: Optional[str] = None
    back_subid: Optional[str] = None
    sides_flitch_id: Optional[str] = None
    sides_subid: Optional[str] = None
    neck_flitch_id: Optional[str] = None
    neck_subid: Optional[str] = None
    brace_stock_flitch_id: Optional[str] = None
    brace_stock_subid: Optional[str] = None
    fretboard_flitch_id: Optional[str] = None
    fretboard_subid: Optional[str] = None
    bridge_flitch_id: Optional[str] = None
    bridge_subid: Optional[str] = None


@dataclass
class BraceDimension:
    """Dimensions for a single brace."""

    name: str
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    scallop_depth_mm: Optional[float] = None
    taper_type: Optional[str] = None
    notes: str = ""


@dataclass
class AsBuiltDimensions:
    """Actual dimensions as built."""

    top_thickness_grid_mm: Optional[list[list[float]]] = None
    back_thickness_grid_mm: Optional[list[list[float]]] = None
    brace_dimensions: Optional[list[BraceDimension]] = None
    soundhole_diameter_mm: Optional[float] = None
    soundhole_position_mm: Optional[float] = None
    body_depth_mm: Optional[float] = None
    body_width_lower_bout_mm: Optional[float] = None
    body_width_upper_bout_mm: Optional[float] = None
    scale_length_mm: Optional[float] = None
    tornavoz_spec: Optional[dict[str, Any]] = None


@dataclass
class MeasurementPaths:
    """Paths to measurement session outputs."""

    modal_scans: Optional[list[str]] = None
    deflection_measurements: Optional[list[str]] = None
    tap_tone_measurements: Optional[list[str]] = None
    bending_measurements: Optional[list[str]] = None
    setup_measurements: Optional[list[str]] = None


@dataclass
class PredictedValues:
    """Pre-build predictions from solver."""

    T1_hz: Optional[float] = None
    A0_hz: Optional[float] = None
    T2_hz: Optional[float] = None
    T3_hz: Optional[float] = None
    bridge_deflection_mm_at_string_load: Optional[float] = None
    top_monopole_mobility: Optional[float] = None
    prediction_session_path: Optional[str] = None


@dataclass
class MeasuredSummary:
    """Summary of measured values."""

    T1_hz: Optional[float] = None
    A0_hz: Optional[float] = None
    T2_hz: Optional[float] = None
    T3_hz: Optional[float] = None
    bridge_deflection_mm: Optional[float] = None
    top_monopole_mobility: Optional[float] = None
    measurement_date: Optional[str] = None


@dataclass
class Residuals:
    """Computed residuals between predicted and measured."""

    T1_residual_hz: Optional[float] = None
    T1_residual_pct: Optional[float] = None
    A0_residual_hz: Optional[float] = None
    A0_residual_pct: Optional[float] = None
    T2_residual_hz: Optional[float] = None
    T2_residual_pct: Optional[float] = None
    T3_residual_hz: Optional[float] = None
    T3_residual_pct: Optional[float] = None
    bridge_deflection_residual_mm: Optional[float] = None
    bridge_deflection_residual_pct: Optional[float] = None
    computed_at_utc: Optional[str] = None


@dataclass
class PlayerEvaluation:
    """A single player's evaluation of the instrument."""

    player_id: str
    date: str
    engagement_minutes: Optional[float] = None
    tone_rating: Optional[int] = None
    playability_rating: Optional[int] = None
    notes: str = ""


@dataclass
class SubjectiveEvaluation:
    """Builder notes and player evaluations."""

    builder_notes: str = ""
    player_evaluations: Optional[list[PlayerEvaluation]] = None


# -----------------------------------------------------------------------------
# Main BuildRecord dataclass
# -----------------------------------------------------------------------------


@dataclass
class BuildRecord:
    """A single instrument build record."""

    build_id: str
    design_name: str
    build_started: str
    created_at_utc: str
    wood: WoodSelection = field(default_factory=WoodSelection)

    design_blueprint_path: Optional[str] = None
    build_completed: Optional[str] = None
    updated_at_utc: Optional[str] = None
    as_built_dimensions: Optional[AsBuiltDimensions] = None
    measurements: Optional[MeasurementPaths] = None
    predicted: Optional[PredictedValues] = None
    measured_summary: Optional[MeasuredSummary] = None
    residuals: Optional[Residuals] = None
    subjective: Optional[SubjectiveEvaluation] = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not _BUILD_ID_RE.match(self.build_id):
            raise ValueError(f"Invalid build_id: {self.build_id!r}")


# -----------------------------------------------------------------------------
# Schema bridge
# -----------------------------------------------------------------------------

_schema_cache: Optional[dict[str, Any]] = None


def _load_schema() -> dict[str, Any]:
    """Load the instrument_build_record schema (cached)."""
    global _schema_cache
    if _schema_cache is None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _schema_cache = json.load(f)
    return _schema_cache


def _nested_to_dict(obj: Any) -> Any:
    """Convert nested dataclass to dict, handling lists and None."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_nested_to_dict(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


def build_to_dict(build: BuildRecord) -> dict[str, Any]:
    """Convert BuildRecord to schema-compliant dict."""
    d = asdict(build)
    d["schema_version"] = SCHEMA_VERSION
    return d


def build_from_dict(d: dict[str, Any]) -> BuildRecord:
    """Construct BuildRecord from dict (e.g., loaded from JSON)."""
    d_copy = {k: v for k, v in d.items() if k != "schema_version"}

    # Convert nested structures
    wood_data = d_copy.pop("wood", {}) or {}
    wood = WoodSelection(**wood_data)

    as_built_data = d_copy.pop("as_built_dimensions", None)
    as_built = None
    if as_built_data:
        braces_data = as_built_data.pop("brace_dimensions", None)
        braces = None
        if braces_data:
            braces = [BraceDimension(**b) for b in braces_data]
        as_built = AsBuiltDimensions(brace_dimensions=braces, **as_built_data)

    measurements_data = d_copy.pop("measurements", None)
    measurements = MeasurementPaths(**measurements_data) if measurements_data else None

    predicted_data = d_copy.pop("predicted", None)
    predicted = PredictedValues(**predicted_data) if predicted_data else None

    measured_data = d_copy.pop("measured_summary", None)
    measured = MeasuredSummary(**measured_data) if measured_data else None

    residuals_data = d_copy.pop("residuals", None)
    residuals = Residuals(**residuals_data) if residuals_data else None

    subjective_data = d_copy.pop("subjective", None)
    subjective = None
    if subjective_data:
        evals_data = subjective_data.pop("player_evaluations", None)
        evals = None
        if evals_data:
            evals = [PlayerEvaluation(**e) for e in evals_data]
        subjective = SubjectiveEvaluation(player_evaluations=evals, **subjective_data)

    return BuildRecord(
        wood=wood,
        as_built_dimensions=as_built,
        measurements=measurements,
        predicted=predicted,
        measured_summary=measured,
        residuals=residuals,
        subjective=subjective,
        **d_copy,
    )


def validate_build(build: BuildRecord) -> None:
    """Validate a BuildRecord against the schema. Raises on failure."""
    d = build_to_dict(build)
    schema = _load_schema()
    jsonschema.validate(instance=d, schema=schema)


def compute_residuals(
    predicted: PredictedValues, measured: MeasuredSummary
) -> Residuals:
    """Compute residuals between predicted and measured values.

    Residual = measured - predicted
    Residual_pct = 100 * (measured - predicted) / predicted

    Returns Residuals dataclass with computed values.
    """

    def residual(
        pred: Optional[float], meas: Optional[float]
    ) -> tuple[Optional[float], Optional[float]]:
        if pred is None or meas is None:
            return None, None
        diff = meas - pred
        pct = 100 * diff / pred if pred != 0 else None
        return diff, pct

    t1_hz, t1_pct = residual(predicted.T1_hz, measured.T1_hz)
    a0_hz, a0_pct = residual(predicted.A0_hz, measured.A0_hz)
    t2_hz, t2_pct = residual(predicted.T2_hz, measured.T2_hz)
    t3_hz, t3_pct = residual(predicted.T3_hz, measured.T3_hz)
    defl_mm, defl_pct = residual(
        predicted.bridge_deflection_mm_at_string_load,
        measured.bridge_deflection_mm,
    )

    return Residuals(
        T1_residual_hz=t1_hz,
        T1_residual_pct=t1_pct,
        A0_residual_hz=a0_hz,
        A0_residual_pct=a0_pct,
        T2_residual_hz=t2_hz,
        T2_residual_pct=t2_pct,
        T3_residual_hz=t3_hz,
        T3_residual_pct=t3_pct,
        bridge_deflection_residual_mm=defl_mm,
        bridge_deflection_residual_pct=defl_pct,
        computed_at_utc=datetime.now(timezone.utc).isoformat(),
    )


# -----------------------------------------------------------------------------
# BuildDatabase — CRUD operations
# -----------------------------------------------------------------------------


class BuildNotFoundError(KeyError):
    """Raised when a build_id is not found in the database."""


class DuplicateBuildError(ValueError):
    """Raised when attempting to add a build with an existing ID."""


class BuildDatabase:
    """Persistent JSON store for instrument build records.

    Usage:
        db = BuildDatabase()  # uses default path or TTP_BUILDS_DB_PATH env
        db.load()

        build = BuildRecord(...)
        db.add_build(build)
        db.save()

    Thread safety is not provided — callers must synchronize if needed.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize database with optional custom path.

        Args:
            path: Path to database JSON file. If None, uses get_builds_path().
        """
        self._path = path if path is not None else get_builds_path()
        self._builds: dict[str, BuildRecord] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        """Return the database file path."""
        return self._path

    def load(self) -> None:
        """Load build records from JSON file.

        Creates an empty database if the file does not exist.
        Validates each record against the schema on load.
        """
        if not self._path.exists():
            self._builds = {}
            self._loaded = True
            return

        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._builds = {}
        for record_dict in data:
            build = build_from_dict(record_dict)
            validate_build(build)
            self._builds[build.build_id] = build

        self._loaded = True

    def save(self) -> None:
        """Persist all build records to JSON file.

        Creates parent directories if they do not exist.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        records = [build_to_dict(b) for b in self._builds.values()]

        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def add_build(self, build: BuildRecord) -> None:
        """Add a new build record to the database.

        Args:
            build: BuildRecord to add

        Raises:
            DuplicateBuildError: If build_id already exists
        """
        if build.build_id in self._builds:
            raise DuplicateBuildError(
                f"Build {build.build_id!r} already exists in database"
            )
        validate_build(build)
        self._builds[build.build_id] = build

    def get_build(self, build_id: str) -> BuildRecord:
        """Retrieve a build by ID.

        Args:
            build_id: The build identifier

        Returns:
            BuildRecord for the given ID

        Raises:
            BuildNotFoundError: If build_id not found
        """
        if build_id not in self._builds:
            raise BuildNotFoundError(f"Build {build_id!r} not found")
        return self._builds[build_id]

    def update_build(self, build: BuildRecord) -> None:
        """Update an existing build record.

        The build_id must already exist in the database.
        Automatically updates updated_at_utc timestamp.

        Args:
            build: BuildRecord with updated data

        Raises:
            BuildNotFoundError: If build_id not found
        """
        if build.build_id not in self._builds:
            raise BuildNotFoundError(
                f"Cannot update: build {build.build_id!r} not found"
            )
        build.updated_at_utc = datetime.now(timezone.utc).isoformat()
        validate_build(build)
        self._builds[build.build_id] = build

    def delete_build(self, build_id: str) -> None:
        """Remove a build from the database.

        Args:
            build_id: The build identifier to remove

        Raises:
            BuildNotFoundError: If build_id not found
        """
        if build_id not in self._builds:
            raise BuildNotFoundError(f"Build {build_id!r} not found")
        del self._builds[build_id]

    def list_builds(self) -> list[str]:
        """Return all build IDs in the database."""
        return sorted(self._builds.keys())

    def list_by_design(self, design_name: str) -> list[str]:
        """Return build IDs filtered by design name.

        Args:
            design_name: Design name to filter by

        Returns:
            Sorted list of build IDs with matching design
        """
        return sorted(
            bid for bid, b in self._builds.items() if b.design_name == design_name
        )

    def list_in_progress(self) -> list[str]:
        """Return build IDs for builds not yet completed."""
        return sorted(
            bid for bid, b in self._builds.items() if b.build_completed is None
        )

    def list_completed(self) -> list[str]:
        """Return build IDs for completed builds."""
        return sorted(
            bid for bid, b in self._builds.items() if b.build_completed is not None
        )

    def __len__(self) -> int:
        """Return number of builds in database."""
        return len(self._builds)

    def __contains__(self, build_id: str) -> bool:
        """Check if build_id exists in database."""
        return build_id in self._builds

    # -------------------------------------------------------------------------
    # Stage D: Cross-reference queries
    # -------------------------------------------------------------------------

    def get_builds_using_flitch(self, flitch_id: str) -> list[str]:
        """Find all builds that reference a given flitch_id.

        Searches all wood selection fields (top, back, sides, neck, etc.)
        for the specified flitch_id.

        Args:
            flitch_id: The flitch identifier to search for

        Returns:
            Sorted list of build_ids that reference this flitch
        """
        results = []
        for build_id, build in self._builds.items():
            wood = build.wood
            flitch_ids = [
                wood.top_flitch_id,
                wood.back_flitch_id,
                wood.sides_flitch_id,
                wood.neck_flitch_id,
                wood.brace_stock_flitch_id,
                wood.fretboard_flitch_id,
                wood.bridge_flitch_id,
            ]
            if flitch_id in flitch_ids:
                results.append(build_id)
        return sorted(results)

    def compute_and_set_residuals(self, build_id: str) -> Residuals:
        """Compute residuals for a build and update the record.

        Requires both predicted and measured_summary to be set.

        Args:
            build_id: The build to compute residuals for

        Returns:
            The computed Residuals object

        Raises:
            BuildNotFoundError: If build_id not found
            ValueError: If predicted or measured_summary is not set
        """
        build = self.get_build(build_id)

        if build.predicted is None:
            raise ValueError(f"Build {build_id!r} has no predicted values")
        if build.measured_summary is None:
            raise ValueError(f"Build {build_id!r} has no measured summary")

        residuals = compute_residuals(build.predicted, build.measured_summary)
        build.residuals = residuals
        self.update_build(build)

        return residuals

    def get_referenced_flitch_ids(self, build_id: str) -> list[str]:
        """Get all non-null flitch_ids referenced by a build.

        Args:
            build_id: The build to get flitch references for

        Returns:
            List of flitch_ids (unique, sorted)

        Raises:
            BuildNotFoundError: If build_id not found
        """
        build = self.get_build(build_id)
        wood = build.wood

        flitch_ids = [
            wood.top_flitch_id,
            wood.back_flitch_id,
            wood.sides_flitch_id,
            wood.neck_flitch_id,
            wood.brace_stock_flitch_id,
            wood.fretboard_flitch_id,
            wood.bridge_flitch_id,
        ]

        return sorted(set(fid for fid in flitch_ids if fid is not None))

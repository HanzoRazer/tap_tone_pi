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
SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "instrument_build_record_v1.schema.json"

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


def compute_residuals(predicted: PredictedValues, measured: MeasuredSummary) -> Residuals:
    """Compute residuals between predicted and measured values.

    Residual = measured - predicted
    Residual_pct = 100 * (measured - predicted) / predicted

    Returns Residuals dataclass with computed values.
    """

    def residual(pred: Optional[float], meas: Optional[float]) -> tuple[Optional[float], Optional[float]]:
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

"""
wood_db.py — Per-flitch wood property database.

Persistent JSON store for wood flitch records and their measurements.
Complements tap_tone_pi/materials/wood_species.json (species reference)
with measurement records keyed to specific flitches.

This module enforces the wood_flitch_record_v1 schema and provides
type-safe dataclasses for application code.
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

from tap_tone_pi.materials import get_species, list_species

SCHEMA_VERSION = "wood_flitch_record_v1"
SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "wood_flitch_record_v1.schema.json"

DEFAULT_DB_PATH = Path.home() / ".tap_tone_pi" / "wood_db.json"
ENV_DB_PATH_OVERRIDE = "TTP_WOOD_DB_PATH"


def get_db_path() -> Path:
    """Return the configured database path, honoring TTP_WOOD_DB_PATH override."""
    override = os.environ.get(ENV_DB_PATH_OVERRIDE)
    if override:
        return Path(override).expanduser()
    return DEFAULT_DB_PATH


# -----------------------------------------------------------------------------
# Species ID validation
# -----------------------------------------------------------------------------

_SPECIES_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_FLITCH_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")
_MEASUREMENT_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{2,80}$")


def is_known_species(species_id: str) -> bool:
    """Check if species_id exists in the canonical wood_species.json."""
    return get_species(species_id) is not None


def normalize_species_freetext(freetext: str) -> Optional[str]:
    """Map common free-text species names to canonical species_ids.

    Returns None if no confident match.

    Used when ingesting legacy data from gore_spreadsheet.py / qa_lab_spec.py
    callers that store species as free-text strings.

    Examples:
        "Sitka Spruce" -> "spruce_sitka"
        "honduran mahogany" -> "mahogany_honduran"
        "Brazilian Rosewood" -> "rosewood_brazilian"
    """
    if not freetext:
        return None

    normalized = freetext.strip().lower()

    # Direct match (already canonical)
    if is_known_species(normalized):
        return normalized

    # Underscore-for-space normalization
    underscored = normalized.replace(" ", "_").replace("-", "_")
    if is_known_species(underscored):
        return underscored

    # Common free-text aliases — keep this list short and conservative
    aliases = {
        "sitka spruce": "spruce_sitka",
        "sitka": "spruce_sitka",
        "adirondack spruce": "spruce_adirondack",
        "adirondack": "spruce_adirondack",
        "red spruce": "spruce_adirondack",
        "engelmann spruce": "spruce_engelmann",
        "engelmann": "spruce_engelmann",
        "european spruce": "spruce_european",
        "german spruce": "spruce_european",
        "alpine spruce": "spruce_european",
        "honduran mahogany": "mahogany_honduran",
        "honduras mahogany": "mahogany_honduran",
        "genuine mahogany": "mahogany_honduran",
        "african mahogany": "mahogany_african",
        "khaya": "mahogany_african",
        "indian rosewood": "rosewood_east_indian",
        "east indian rosewood": "rosewood_east_indian",
        "brazilian rosewood": "rosewood_brazilian",
        "western red cedar": "cedar_western_red",
        "wrc": "cedar_western_red",
        "hard maple": "maple_hard",
        "sugar maple": "maple_hard",
        "soft maple": "maple_soft",
    }

    return aliases.get(normalized)


# -----------------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------------

@dataclass
class PlateMeasurement:
    """A single measurement event on one piece of a flitch."""

    measurement_id: str
    measured_at_utc: str  # ISO datetime
    thickness_mm_mean: float
    mass_g: float
    density_kg_m3: float

    # Optional context
    plate_subid: Optional[str] = None
    rh_at_measurement_pct: Optional[float] = None
    tempC_at_measurement: Optional[float] = None

    # Geometry (optional)
    thickness_mm_grid: Optional[list[list[float]]] = None
    thickness_mm_std: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None

    # Stiffness (optional) - field names match UncertaintyBudget convention
    E_L_GPa: Optional[float] = None
    E_L_uncertainty_GPa: Optional[float] = None
    E_L_expanded_uncertainty_GPa: Optional[float] = None
    E_C_GPa: Optional[float] = None
    E_C_uncertainty_GPa: Optional[float] = None
    E_C_expanded_uncertainty_GPa: Optional[float] = None
    coverage_factor: float = 2.0
    degrees_of_freedom: Optional[int] = None

    # Modal (optional)
    modal_freqs_hz: Optional[dict[str, float]] = None
    Q_factors: Optional[dict[str, float]] = None

    # Provenance
    session_path: Optional[str] = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not _MEASUREMENT_ID_RE.match(self.measurement_id):
            raise ValueError(f"Invalid measurement_id: {self.measurement_id!r}")


@dataclass
class FlitchRecord:
    """A single flitch with one or more measurements over time."""

    flitch_id: str
    species_id: str
    created_at_utc: str

    species_id_freetext_original: Optional[str] = None
    supplier: Optional[str] = None
    purchase_lot: Optional[str] = None
    purchase_date: Optional[str] = None
    estimated_age_years: Optional[float] = None
    moisture_content_pct_at_purchase: Optional[float] = None
    notes: str = ""

    measurements: list[PlateMeasurement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not _FLITCH_ID_RE.match(self.flitch_id):
            raise ValueError(f"Invalid flitch_id: {self.flitch_id!r}")
        if not _SPECIES_ID_RE.match(self.species_id):
            raise ValueError(f"Invalid species_id format: {self.species_id!r}")
        if not is_known_species(self.species_id):
            # Warn but allow — species reference may add new species before db updates
            import warnings
            warnings.warn(
                f"species_id {self.species_id!r} not found in wood_species.json. "
                f"Use list_species() to see canonical IDs.",
                stacklevel=2,
            )


# -----------------------------------------------------------------------------
# Schema bridge
# -----------------------------------------------------------------------------

_schema_cache: Optional[dict[str, Any]] = None


def _load_schema() -> dict[str, Any]:
    """Load the wood_flitch_record schema (cached)."""
    global _schema_cache
    if _schema_cache is None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _schema_cache = json.load(f)
    return _schema_cache


def flitch_to_dict(flitch: FlitchRecord) -> dict[str, Any]:
    """Convert FlitchRecord to schema-compliant dict.

    Adds schema_version and converts nested PlateMeasurement objects.
    """
    d = asdict(flitch)
    d["schema_version"] = SCHEMA_VERSION
    return d


def flitch_from_dict(d: dict[str, Any]) -> FlitchRecord:
    """Construct FlitchRecord from dict (e.g., loaded from JSON)."""
    # Strip schema_version from the dict before constructing (it's not a field)
    d_copy = {k: v for k, v in d.items() if k != "schema_version"}

    # Convert nested measurements
    measurements_data = d_copy.pop("measurements", [])
    measurements = [PlateMeasurement(**m) for m in measurements_data]

    return FlitchRecord(measurements=measurements, **d_copy)


def validate_flitch(flitch: FlitchRecord) -> None:
    """Validate a FlitchRecord against the schema. Raises on failure."""
    d = flitch_to_dict(flitch)
    schema = _load_schema()
    jsonschema.validate(instance=d, schema=schema)

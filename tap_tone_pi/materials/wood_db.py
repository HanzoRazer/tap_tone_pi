# INSTRUMENT CLASS: MEASUREMENT
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
from pathlib import Path
from typing import Any, Optional

import jsonschema

from tap_tone_pi.materials import get_species

SCHEMA_VERSION = "wood_flitch_record_v1"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "contracts"
    / "wood_flitch_record_v1.schema.json"
)

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


# -----------------------------------------------------------------------------
# WoodDatabase — CRUD operations
# -----------------------------------------------------------------------------


class FlitchNotFoundError(KeyError):
    """Raised when a flitch_id is not found in the database."""


class DuplicateFlitchError(ValueError):
    """Raised when attempting to add a flitch with an existing ID."""


class WoodDatabase:
    """Persistent JSON store for wood flitch records.

    Usage:
        db = WoodDatabase()  # uses default path or TTP_WOOD_DB_PATH env
        db.load()

        flitch = FlitchRecord(...)
        db.add_flitch(flitch)
        db.save()

    The database file is a JSON array of flitch records. Thread safety is
    not provided — callers must synchronize if needed.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize database with optional custom path.

        Args:
            path: Path to database JSON file. If None, uses get_db_path().
        """
        self._path = path if path is not None else get_db_path()
        self._flitches: dict[str, FlitchRecord] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        """Return the database file path."""
        return self._path

    def load(self) -> None:
        """Load flitch records from JSON file.

        Creates an empty database if the file does not exist.
        Validates each record against the schema on load.
        """
        if not self._path.exists():
            self._flitches = {}
            self._loaded = True
            return

        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._flitches = {}
        for record_dict in data:
            flitch = flitch_from_dict(record_dict)
            validate_flitch(flitch)
            self._flitches[flitch.flitch_id] = flitch

        self._loaded = True

    def save(self) -> None:
        """Persist all flitch records to JSON file.

        Creates parent directories if they do not exist.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        records = [flitch_to_dict(f) for f in self._flitches.values()]

        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def add_flitch(self, flitch: FlitchRecord) -> None:
        """Add a new flitch record to the database.

        Args:
            flitch: FlitchRecord to add

        Raises:
            DuplicateFlitchError: If flitch_id already exists
        """
        if flitch.flitch_id in self._flitches:
            raise DuplicateFlitchError(
                f"Flitch {flitch.flitch_id!r} already exists in database"
            )
        validate_flitch(flitch)
        self._flitches[flitch.flitch_id] = flitch

    def get_flitch(self, flitch_id: str) -> FlitchRecord:
        """Retrieve a flitch by ID.

        Args:
            flitch_id: The flitch identifier

        Returns:
            FlitchRecord for the given ID

        Raises:
            FlitchNotFoundError: If flitch_id not found
        """
        if flitch_id not in self._flitches:
            raise FlitchNotFoundError(f"Flitch {flitch_id!r} not found")
        return self._flitches[flitch_id]

    def update_flitch(self, flitch: FlitchRecord) -> None:
        """Update an existing flitch record.

        The flitch_id must already exist in the database.

        Args:
            flitch: FlitchRecord with updated data

        Raises:
            FlitchNotFoundError: If flitch_id not found
        """
        if flitch.flitch_id not in self._flitches:
            raise FlitchNotFoundError(
                f"Cannot update: flitch {flitch.flitch_id!r} not found"
            )
        validate_flitch(flitch)
        self._flitches[flitch.flitch_id] = flitch

    def delete_flitch(self, flitch_id: str) -> None:
        """Remove a flitch from the database.

        Args:
            flitch_id: The flitch identifier to remove

        Raises:
            FlitchNotFoundError: If flitch_id not found
        """
        if flitch_id not in self._flitches:
            raise FlitchNotFoundError(f"Flitch {flitch_id!r} not found")
        del self._flitches[flitch_id]

    def add_measurement(self, flitch_id: str, measurement: PlateMeasurement) -> None:
        """Append a measurement to an existing flitch.

        Args:
            flitch_id: The flitch to add measurement to
            measurement: PlateMeasurement to append

        Raises:
            FlitchNotFoundError: If flitch_id not found
        """
        flitch = self.get_flitch(flitch_id)
        flitch.measurements.append(measurement)
        validate_flitch(flitch)

    def list_flitches(self) -> list[str]:
        """Return all flitch IDs in the database."""
        return sorted(self._flitches.keys())

    def list_by_species(self, species_id: str) -> list[str]:
        """Return flitch IDs filtered by species.

        Args:
            species_id: Canonical species identifier

        Returns:
            Sorted list of flitch IDs with matching species
        """
        return sorted(
            fid for fid, f in self._flitches.items() if f.species_id == species_id
        )

    def __len__(self) -> int:
        """Return number of flitches in database."""
        return len(self._flitches)

    def __contains__(self, flitch_id: str) -> bool:
        """Check if flitch_id exists in database."""
        return flitch_id in self._flitches

    # -------------------------------------------------------------------------
    # Stage D: Statistics queries
    # -------------------------------------------------------------------------

    def get_latest_measurement(self, flitch_id: str) -> Optional[PlateMeasurement]:
        """Return the most recent measurement for a flitch.

        Args:
            flitch_id: The flitch identifier

        Returns:
            Most recent PlateMeasurement by measured_at_utc, or None if no measurements

        Raises:
            FlitchNotFoundError: If flitch_id not found
        """
        flitch = self.get_flitch(flitch_id)
        if not flitch.measurements:
            return None
        return max(flitch.measurements, key=lambda m: m.measured_at_utc)

    def get_all_measurements(self) -> list[tuple[str, PlateMeasurement]]:
        """Return all measurements across all flitches.

        Returns:
            List of (flitch_id, PlateMeasurement) tuples, sorted by measured_at_utc
        """
        result: list[tuple[str, PlateMeasurement]] = []
        for flitch_id, flitch in self._flitches.items():
            for m in flitch.measurements:
                result.append((flitch_id, m))
        return sorted(result, key=lambda x: x[1].measured_at_utc)

    def get_species_stats(self, species_id: str) -> "SpeciesStats":
        """Compute aggregate statistics for a species.

        Args:
            species_id: Canonical species identifier

        Returns:
            SpeciesStats with computed means and standard deviations

        Raises:
            InsufficientDataError: If no measurements exist for species
        """
        measurements: list[PlateMeasurement] = []
        flitch_ids = self.list_by_species(species_id)

        for fid in flitch_ids:
            flitch = self.get_flitch(fid)
            measurements.extend(flitch.measurements)

        if not measurements:
            raise InsufficientDataError(
                f"No measurements found for species {species_id!r}"
            )

        return SpeciesStats.from_measurements(species_id, measurements)


# -----------------------------------------------------------------------------
# Stage D: SpeciesStats dataclass
# -----------------------------------------------------------------------------


class InsufficientDataError(ValueError):
    """Raised when there is not enough data to compute statistics."""


@dataclass
class SpeciesStats:
    """Aggregate statistics for a wood species.

    Computed from all measurements of flitches with the given species_id.
    Fields are None when fewer than 2 non-null values are available for
    standard deviation calculation.
    """

    species_id: str
    flitch_count: int
    measurement_count: int

    density_kg_m3_mean: Optional[float] = None
    density_kg_m3_std: Optional[float] = None

    thickness_mm_mean: Optional[float] = None
    thickness_mm_std: Optional[float] = None

    E_L_GPa_mean: Optional[float] = None
    E_L_GPa_std: Optional[float] = None

    E_C_GPa_mean: Optional[float] = None
    E_C_GPa_std: Optional[float] = None

    @classmethod
    def from_measurements(
        cls, species_id: str, measurements: list[PlateMeasurement]
    ) -> "SpeciesStats":
        """Compute statistics from a list of measurements.

        Args:
            species_id: The species identifier
            measurements: List of PlateMeasurement objects

        Returns:
            SpeciesStats with computed values
        """
        import math

        def mean_std(values: list[float]) -> tuple[Optional[float], Optional[float]]:
            """Compute mean and sample std, returning None if insufficient data."""
            if not values:
                return None, None
            n = len(values)
            mean = sum(values) / n
            if n < 2:
                return mean, None
            variance = sum((x - mean) ** 2 for x in values) / (n - 1)
            return mean, math.sqrt(variance)

        densities = [m.density_kg_m3 for m in measurements]
        thicknesses = [m.thickness_mm_mean for m in measurements]
        e_l_values = [m.E_L_GPa for m in measurements if m.E_L_GPa is not None]
        e_c_values = [m.E_C_GPa for m in measurements if m.E_C_GPa is not None]

        d_mean, d_std = mean_std(densities)
        t_mean, t_std = mean_std(thicknesses)
        el_mean, el_std = mean_std(e_l_values)
        ec_mean, ec_std = mean_std(e_c_values)

        flitch_ids = {m.session_path for m in measurements if m.session_path}
        flitch_count = len(flitch_ids) if flitch_ids else len(measurements)

        return cls(
            species_id=species_id,
            flitch_count=flitch_count,
            measurement_count=len(measurements),
            density_kg_m3_mean=d_mean,
            density_kg_m3_std=d_std,
            thickness_mm_mean=t_mean,
            thickness_mm_std=t_std,
            E_L_GPa_mean=el_mean,
            E_L_GPa_std=el_std,
            E_C_GPa_mean=ec_mean,
            E_C_GPa_std=ec_std,
        )

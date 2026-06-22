# INSTRUMENT CLASS: MEASUREMENT
"""Pressure response map contracts (DO-94).

Contracts for spatial pressure-response mapping. These record measured
pressure response at grid positions. They do NOT identify true mode shapes
or prescribe design changes.

A microphone grid measures radiated or near-field pressure, not plate
surface velocity.

No advisory semantics. No mode-shape claims. No soundhole recommendations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CoordinateSystem(Enum):
    """Coordinate system for pressure grid."""

    BODY_LOCAL_MM = "body_local_mm"
    PLATE_LOCAL_MM = "plate_local_mm"
    FIXTURE_LOCAL_MM = "fixture_local_mm"
    MICROPHONE_GRID_MM = "microphone_grid_mm"


@dataclass(frozen=True)
class PressureGridPointV1:
    """A single point in the pressure measurement grid.

    Records the physical location of a measurement position.

    Attributes:
        point_id: Unique identifier for this point (e.g., "A1", "B3")
        x_mm: X coordinate in millimeters
        y_mm: Y coordinate in millimeters
        z_mm: Z coordinate in millimeters (optional, for 3D grids)
        label: Human-readable label (optional)
    """

    schema_version: str = field(default="pressure_grid_point_v1", init=False)
    point_id: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: Optional[float] = None
    label: Optional[str] = None
    epistemic_status: str = field(default="observed", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "point_id": self.point_id,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "epistemic_status": self.epistemic_status,
        }

        if self.z_mm is not None:
            d["z_mm"] = self.z_mm
        if self.label is not None:
            d["label"] = self.label

        return d


@dataclass(frozen=True)
class PressureGridV1:
    """A collection of pressure measurement grid points.

    Defines the spatial layout of measurement positions.

    Attributes:
        grid_id: Unique identifier for this grid
        coordinate_system: Coordinate system used
        points: Tuple of grid points
        surface_reference: Reference surface description (optional)
    """

    schema_version: str = field(default="pressure_grid_v1", init=False)
    grid_id: str = ""
    coordinate_system: str = CoordinateSystem.BODY_LOCAL_MM.value
    points: tuple[PressureGridPointV1, ...] = field(default_factory=tuple)
    surface_reference: Optional[str] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "grid_id": self.grid_id,
            "coordinate_system": self.coordinate_system,
            "points": [p.to_dict() for p in self.points],
            "epistemic_status": self.epistemic_status,
        }

        if self.surface_reference is not None:
            d["surface_reference"] = self.surface_reference

        return d


@dataclass(frozen=True)
class PressureResponseSampleV1:
    """A pressure response measurement at one grid point and frequency.

    Records the measured pressure response. Does NOT claim to identify
    mode shapes or antinodes.

    Attributes:
        sample_id: Unique identifier for this sample
        point_id: Grid point where measurement was taken
        frequency_hz: Excitation frequency
        response_amplitude_db: Measured response amplitude in dB
        response_phase_deg: Response phase in degrees (optional)
        noise_floor_db: Noise floor in dB (optional)
        snr_db: Signal-to-noise ratio in dB (optional)
        coherence: Coherence value 0-1 (optional)
        excitation_id: Link to excitation contract
        transfer_function_result_id: Link to TF result (optional)
        environment_id: Link to environment record (optional)
        fixture_id: Link to fixture record (optional)
    """

    schema_version: str = field(default="pressure_response_sample_v1", init=False)
    sample_id: str = ""
    point_id: str = ""
    frequency_hz: float = 0.0
    response_amplitude_db: float = 0.0
    response_phase_deg: Optional[float] = None
    noise_floor_db: Optional[float] = None
    snr_db: Optional[float] = None
    coherence: Optional[float] = None
    excitation_id: str = ""
    transfer_function_result_id: Optional[str] = None
    environment_id: Optional[str] = None
    fixture_id: Optional[str] = None
    epistemic_status: str = field(default="observed", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "sample_id": self.sample_id,
            "point_id": self.point_id,
            "frequency_hz": self.frequency_hz,
            "response_amplitude_db": self.response_amplitude_db,
            "excitation_id": self.excitation_id,
            "epistemic_status": self.epistemic_status,
        }

        if self.response_phase_deg is not None:
            d["response_phase_deg"] = self.response_phase_deg
        if self.noise_floor_db is not None:
            d["noise_floor_db"] = self.noise_floor_db
        if self.snr_db is not None:
            d["snr_db"] = self.snr_db
        if self.coherence is not None:
            d["coherence"] = self.coherence
        if self.transfer_function_result_id is not None:
            d["transfer_function_result_id"] = self.transfer_function_result_id
        if self.environment_id is not None:
            d["environment_id"] = self.environment_id
        if self.fixture_id is not None:
            d["fixture_id"] = self.fixture_id

        return d


@dataclass(frozen=True)
class PressureResponseMapV1:
    """A complete pressure response map at one frequency or band.

    Records pressure response across a grid of measurement positions.
    This is a measurement artifact, NOT a mode shape.

    The map shows where radiated pressure is strongest at the measured
    frequency. It does NOT identify true mode shapes or antinodes.

    Attributes:
        map_id: Unique identifier for this map
        workflow_id: Link to workflow configuration
        grid_id: Link to grid definition
        excitation_id: Link to excitation contract
        frequency_hz: Single frequency (mutually exclusive with frequency_band_hz)
        frequency_band_hz: Frequency band (mutually exclusive with frequency_hz)
        samples: Tuple of response samples
        environment_id: Link to environment record (optional)
        fixture_id: Link to fixture record (optional)
        repeatability_evidence_id: Link to repeatability evidence (optional)
        notes: Freeform notes (optional)
    """

    schema_version: str = field(default="pressure_response_map_v1", init=False)
    map_id: str = ""
    workflow_id: str = ""
    grid_id: str = ""
    excitation_id: str = ""
    frequency_hz: Optional[float] = None
    frequency_band_hz: Optional[tuple[float, float]] = None
    samples: tuple[PressureResponseSampleV1, ...] = field(default_factory=tuple)
    environment_id: Optional[str] = None
    fixture_id: Optional[str] = None
    repeatability_evidence_id: Optional[str] = None
    notes: Optional[str] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "map_id": self.map_id,
            "workflow_id": self.workflow_id,
            "grid_id": self.grid_id,
            "excitation_id": self.excitation_id,
            "samples": [s.to_dict() for s in self.samples],
            "epistemic_status": self.epistemic_status,
        }

        if self.frequency_hz is not None:
            d["frequency_hz"] = self.frequency_hz
        if self.frequency_band_hz is not None:
            d["frequency_band_hz"] = list(self.frequency_band_hz)
        if self.environment_id is not None:
            d["environment_id"] = self.environment_id
        if self.fixture_id is not None:
            d["fixture_id"] = self.fixture_id
        if self.repeatability_evidence_id is not None:
            d["repeatability_evidence_id"] = self.repeatability_evidence_id
        if self.notes is not None:
            d["notes"] = self.notes

        return d

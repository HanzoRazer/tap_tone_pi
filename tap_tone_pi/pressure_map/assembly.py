# INSTRUMENT CLASS: MEASUREMENT
"""Pressure response map assembly helpers (DO-94).

Functions for creating and assembling pressure response maps.
Validation raises ValueError for structural errors.

Use neutral language: max_response_point_id, not best_point_id.

No advisory semantics. No mode-shape claims. No soundhole recommendations.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from tap_tone_pi.pressure_map.contracts import (
    CoordinateSystem,
    PressureGridPointV1,
    PressureGridV1,
    PressureResponseSampleV1,
    PressureResponseMapV1,
)


def create_pressure_grid_point(
    point_id: str,
    x_mm: float,
    y_mm: float,
    *,
    z_mm: Optional[float] = None,
    label: Optional[str] = None,
) -> PressureGridPointV1:
    """Create a pressure grid point.

    Args:
        point_id: Unique identifier (e.g., "A1", "B3")
        x_mm: X coordinate in millimeters
        y_mm: Y coordinate in millimeters
        z_mm: Z coordinate in millimeters (optional)
        label: Human-readable label (optional)

    Returns:
        PressureGridPointV1 instance
    """
    return PressureGridPointV1(
        point_id=point_id,
        x_mm=x_mm,
        y_mm=y_mm,
        z_mm=z_mm,
        label=label,
    )


def create_pressure_grid(
    grid_id: str,
    points: list[PressureGridPointV1],
    *,
    coordinate_system: CoordinateSystem | str = CoordinateSystem.BODY_LOCAL_MM,
    surface_reference: Optional[str] = None,
) -> PressureGridV1:
    """Create a pressure measurement grid.

    Args:
        grid_id: Unique identifier
        points: List of grid points
        coordinate_system: Coordinate system used
        surface_reference: Reference surface description (optional)

    Returns:
        PressureGridV1 instance

    Raises:
        ValueError: If duplicate point IDs are detected
    """
    # Check for duplicate point IDs
    point_ids = [p.point_id for p in points]
    seen = set()
    duplicates = []
    for pid in point_ids:
        if pid in seen:
            duplicates.append(pid)
        seen.add(pid)

    if duplicates:
        raise ValueError(f"Duplicate point IDs detected: {duplicates}")

    # Convert coordinate system to string if enum
    if isinstance(coordinate_system, CoordinateSystem):
        cs_value = coordinate_system.value
    else:
        cs_value = coordinate_system

    return PressureGridV1(
        grid_id=grid_id,
        coordinate_system=cs_value,
        points=tuple(points),
        surface_reference=surface_reference,
    )


def create_pressure_response_sample(
    sample_id: str,
    point_id: str,
    frequency_hz: float,
    response_amplitude_db: float,
    excitation_id: str,
    *,
    response_phase_deg: Optional[float] = None,
    noise_floor_db: Optional[float] = None,
    snr_db: Optional[float] = None,
    coherence: Optional[float] = None,
    transfer_function_result_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    fixture_id: Optional[str] = None,
) -> PressureResponseSampleV1:
    """Create a pressure response sample.

    Args:
        sample_id: Unique identifier
        point_id: Grid point where measurement was taken
        frequency_hz: Excitation frequency
        response_amplitude_db: Measured response amplitude in dB
        excitation_id: Link to excitation contract
        response_phase_deg: Response phase in degrees (optional)
        noise_floor_db: Noise floor in dB (optional)
        snr_db: Signal-to-noise ratio in dB (optional)
        coherence: Coherence value 0-1 (optional)
        transfer_function_result_id: Link to TF result (optional)
        environment_id: Link to environment record (optional)
        fixture_id: Link to fixture record (optional)

    Returns:
        PressureResponseSampleV1 instance
    """
    return PressureResponseSampleV1(
        sample_id=sample_id,
        point_id=point_id,
        frequency_hz=frequency_hz,
        response_amplitude_db=response_amplitude_db,
        response_phase_deg=response_phase_deg,
        noise_floor_db=noise_floor_db,
        snr_db=snr_db,
        coherence=coherence,
        excitation_id=excitation_id,
        transfer_function_result_id=transfer_function_result_id,
        environment_id=environment_id,
        fixture_id=fixture_id,
    )


def assemble_pressure_response_map(
    map_id: str,
    workflow_id: str,
    grid: PressureGridV1,
    excitation_id: str,
    samples: list[PressureResponseSampleV1],
    *,
    frequency_hz: Optional[float] = None,
    frequency_band_hz: Optional[tuple[float, float]] = None,
    environment_id: Optional[str] = None,
    fixture_id: Optional[str] = None,
    repeatability_evidence_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> PressureResponseMapV1:
    """Assemble a pressure response map from samples.

    Args:
        map_id: Unique identifier
        workflow_id: Link to workflow configuration
        grid: Grid definition
        excitation_id: Link to excitation contract
        samples: List of response samples
        frequency_hz: Single frequency (mutually exclusive with frequency_band_hz)
        frequency_band_hz: Frequency band (mutually exclusive with frequency_hz)
        environment_id: Link to environment record (optional)
        fixture_id: Link to fixture record (optional)
        repeatability_evidence_id: Link to repeatability evidence (optional)
        notes: Freeform notes (optional)

    Returns:
        PressureResponseMapV1 instance

    Raises:
        ValueError: If frequency fields are not mutually exclusive
        ValueError: If samples reference unknown grid points
    """
    # Enforce frequency XOR
    if frequency_hz is not None and frequency_band_hz is not None:
        raise ValueError(
            "frequency_hz and frequency_band_hz are mutually exclusive"
        )
    if frequency_hz is None and frequency_band_hz is None:
        raise ValueError(
            "Either frequency_hz or frequency_band_hz must be specified"
        )

    # Get valid point IDs from grid
    valid_point_ids = {p.point_id for p in grid.points}

    # Check for samples referencing unknown points
    unknown_points = []
    for sample in samples:
        if sample.point_id not in valid_point_ids:
            unknown_points.append(sample.point_id)

    if unknown_points:
        raise ValueError(
            f"Samples reference unknown grid points: {unknown_points}"
        )

    return PressureResponseMapV1(
        map_id=map_id,
        workflow_id=workflow_id,
        grid_id=grid.grid_id,
        excitation_id=excitation_id,
        frequency_hz=frequency_hz,
        frequency_band_hz=frequency_band_hz,
        samples=tuple(samples),
        environment_id=environment_id,
        fixture_id=fixture_id,
        repeatability_evidence_id=repeatability_evidence_id,
        notes=notes,
    )


def normalize_pressure_response_map(
    pressure_map: PressureResponseMapV1,
) -> PressureResponseMapV1:
    """Normalize pressure response map so max response is 0 dB.

    Creates a new map with normalized amplitudes. The point with the
    highest response amplitude becomes 0.0 dB.

    Args:
        pressure_map: Original pressure response map

    Returns:
        New PressureResponseMapV1 with normalized amplitudes
    """
    if not pressure_map.samples:
        return pressure_map

    # Find max response amplitude
    max_amplitude = max(s.response_amplitude_db for s in pressure_map.samples)

    # Create normalized samples
    normalized_samples = []
    for sample in pressure_map.samples:
        normalized_sample = PressureResponseSampleV1(
            sample_id=sample.sample_id,
            point_id=sample.point_id,
            frequency_hz=sample.frequency_hz,
            response_amplitude_db=sample.response_amplitude_db - max_amplitude,
            response_phase_deg=sample.response_phase_deg,
            noise_floor_db=sample.noise_floor_db,
            snr_db=sample.snr_db,
            coherence=sample.coherence,
            excitation_id=sample.excitation_id,
            transfer_function_result_id=sample.transfer_function_result_id,
            environment_id=sample.environment_id,
            fixture_id=sample.fixture_id,
        )
        normalized_samples.append(normalized_sample)

    return PressureResponseMapV1(
        map_id=pressure_map.map_id,
        workflow_id=pressure_map.workflow_id,
        grid_id=pressure_map.grid_id,
        excitation_id=pressure_map.excitation_id,
        frequency_hz=pressure_map.frequency_hz,
        frequency_band_hz=pressure_map.frequency_band_hz,
        samples=tuple(normalized_samples),
        environment_id=pressure_map.environment_id,
        fixture_id=pressure_map.fixture_id,
        repeatability_evidence_id=pressure_map.repeatability_evidence_id,
        notes=pressure_map.notes,
    )


@dataclass(frozen=True)
class PressureResponseMapSummaryV1:
    """Summary statistics for a pressure response map.

    Uses neutral language: max_response_point_id, not best_point_id.
    """

    schema_version: str = "pressure_response_map_summary_v1"
    map_id: str = ""
    sample_count: int = 0
    min_response_db: float = 0.0
    max_response_db: float = 0.0
    mean_response_db: float = 0.0
    max_response_point_id: str = ""
    min_response_point_id: str = ""
    epistemic_status: str = "derived"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "map_id": self.map_id,
            "sample_count": self.sample_count,
            "min_response_db": self.min_response_db,
            "max_response_db": self.max_response_db,
            "mean_response_db": self.mean_response_db,
            "max_response_point_id": self.max_response_point_id,
            "min_response_point_id": self.min_response_point_id,
            "epistemic_status": self.epistemic_status,
        }


def summarize_pressure_response_map(
    pressure_map: PressureResponseMapV1,
) -> PressureResponseMapSummaryV1:
    """Compute summary statistics for a pressure response map.

    Uses neutral language: max_response_point_id, not best_point_id.

    Args:
        pressure_map: Pressure response map to summarize

    Returns:
        PressureResponseMapSummaryV1 with statistics
    """
    if not pressure_map.samples:
        return PressureResponseMapSummaryV1(
            map_id=pressure_map.map_id,
            sample_count=0,
        )

    amplitudes = [s.response_amplitude_db for s in pressure_map.samples]
    min_amplitude = min(amplitudes)
    max_amplitude = max(amplitudes)
    mean_amplitude = sum(amplitudes) / len(amplitudes)

    # Find point IDs for min/max
    max_sample = max(pressure_map.samples, key=lambda s: s.response_amplitude_db)
    min_sample = min(pressure_map.samples, key=lambda s: s.response_amplitude_db)

    return PressureResponseMapSummaryV1(
        map_id=pressure_map.map_id,
        sample_count=len(pressure_map.samples),
        min_response_db=min_amplitude,
        max_response_db=max_amplitude,
        mean_response_db=mean_amplitude,
        max_response_point_id=max_sample.point_id,
        min_response_point_id=min_sample.point_id,
    )

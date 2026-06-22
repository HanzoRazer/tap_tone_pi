# INSTRUMENT CLASS: MEASUREMENT
"""Pressure response mapping workflow (DO-94).

PressureResponseMappingWorkflowV1 defines the workflow configuration
for pressure response mapping.

This workflow records pressure response over a grid.
It does not identify true mode shapes or prescribe design changes.

No advisory semantics. No mode-shape claims. No soundhole recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class PressureResponseMappingWorkflowV1:
    """Workflow configuration for pressure response mapping.

    This workflow records pressure response over a grid.
    It does not identify true mode shapes or prescribe design changes.

    Attributes:
        workflow_id: Unique identifier
        grid_id: Link to grid definition
        excitation_id: Link to excitation contract
        target_frequencies_hz: Frequencies to measure
        requires_fixed_geometry: Whether geometry must be fixed
        requires_environment_record: Whether environment record is required
        requires_fixture_record: Whether fixture record is required
        minimum_repetitions: Minimum repetitions per point
        created_at_utc: Creation timestamp
    """

    schema_version: str = field(
        default="pressure_response_mapping_workflow_v1", init=False
    )
    workflow_id: str = ""
    grid_id: str = ""
    excitation_id: str = ""
    target_frequencies_hz: tuple[float, ...] = field(default_factory=tuple)
    requires_fixed_geometry: bool = True
    requires_environment_record: bool = True
    requires_fixture_record: bool = True
    minimum_repetitions: int = 3
    created_at_utc: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "grid_id": self.grid_id,
            "excitation_id": self.excitation_id,
            "target_frequencies_hz": list(self.target_frequencies_hz),
            "requires_fixed_geometry": self.requires_fixed_geometry,
            "requires_environment_record": self.requires_environment_record,
            "requires_fixture_record": self.requires_fixture_record,
            "minimum_repetitions": self.minimum_repetitions,
            "created_at_utc": self.created_at_utc,
            "epistemic_status": self.epistemic_status,
        }


def create_pressure_response_mapping_workflow(
    workflow_id: str,
    grid_id: str,
    excitation_id: str,
    target_frequencies_hz: list[float] | tuple[float, ...],
    *,
    requires_fixed_geometry: bool = True,
    requires_environment_record: bool = True,
    requires_fixture_record: bool = True,
    minimum_repetitions: int = 3,
    created_at_utc: Optional[str] = None,
) -> PressureResponseMappingWorkflowV1:
    """Create a pressure response mapping workflow configuration.

    Args:
        workflow_id: Unique identifier
        grid_id: Link to grid definition
        excitation_id: Link to excitation contract
        target_frequencies_hz: Frequencies to measure
        requires_fixed_geometry: Whether geometry must be fixed
        requires_environment_record: Whether environment record is required
        requires_fixture_record: Whether fixture record is required
        minimum_repetitions: Minimum repetitions per point
        created_at_utc: Creation timestamp (defaults to now)

    Returns:
        PressureResponseMappingWorkflowV1 instance
    """
    if created_at_utc is None:
        created_at_utc = datetime.now(timezone.utc).isoformat()

    return PressureResponseMappingWorkflowV1(
        workflow_id=workflow_id,
        grid_id=grid_id,
        excitation_id=excitation_id,
        target_frequencies_hz=tuple(target_frequencies_hz),
        requires_fixed_geometry=requires_fixed_geometry,
        requires_environment_record=requires_environment_record,
        requires_fixture_record=requires_fixture_record,
        minimum_repetitions=minimum_repetitions,
        created_at_utc=created_at_utc,
    )

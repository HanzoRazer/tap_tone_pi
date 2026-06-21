# INSTRUMENT CLASS: MEASUREMENT
"""A0 workflow configuration (DO-92).

MainBodyAirResonanceWorkflowV1 defines the workflow configuration
for A0 measurement using controlled excitation.

No advisory semantics. No soundhole recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Tuple


DEFAULT_A0_FREQUENCY_RANGE: Tuple[float, float] = (70.0, 130.0)
DEFAULT_A0_SELECTION_METHOD: str = "lowest_prominent_peak_in_range"
DEFAULT_MIN_CAPTURES_FOR_REPEATABILITY: int = 3


@dataclass(frozen=True)
class MainBodyAirResonanceWorkflowV1:
    """Workflow configuration for A0 measurement.

    Defines the parameters for A0 identification using
    controlled excitation and transfer function analysis.

    Attributes:
        workflow_id: Unique identifier
        excitation_type: "sweep" or "stepped" (default: sweep)
        frequency_range_hz: Search range (default: 70-130 Hz)
        selection_method: Peak selection method
        min_captures_for_repeatability: Minimum captures for repeatability
        min_prominence_db: Minimum peak prominence to consider
        min_coherence: Minimum coherence threshold
        created_at_utc: Creation timestamp
    """

    schema_version: str = field(
        default="main_body_air_resonance_workflow_v1", init=False
    )
    workflow_id: str = ""
    excitation_type: str = "sweep"
    frequency_range_hz: Tuple[float, float] = DEFAULT_A0_FREQUENCY_RANGE
    selection_method: str = DEFAULT_A0_SELECTION_METHOD
    min_captures_for_repeatability: int = DEFAULT_MIN_CAPTURES_FOR_REPEATABILITY
    min_prominence_db: float = 6.0
    min_coherence: float = 0.8
    created_at_utc: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "excitation_type": self.excitation_type,
            "frequency_range_hz": list(self.frequency_range_hz),
            "selection_method": self.selection_method,
            "min_captures_for_repeatability": self.min_captures_for_repeatability,
            "min_prominence_db": self.min_prominence_db,
            "min_coherence": self.min_coherence,
            "created_at_utc": self.created_at_utc,
            "epistemic_status": self.epistemic_status,
        }


def create_a0_workflow(
    workflow_id: str,
    *,
    excitation_type: str = "sweep",
    frequency_range_hz: Tuple[float, float] = DEFAULT_A0_FREQUENCY_RANGE,
    selection_method: str = DEFAULT_A0_SELECTION_METHOD,
    min_captures_for_repeatability: int = DEFAULT_MIN_CAPTURES_FOR_REPEATABILITY,
    min_prominence_db: float = 6.0,
    min_coherence: float = 0.8,
    created_at_utc: Optional[str] = None,
) -> MainBodyAirResonanceWorkflowV1:
    """Create an A0 workflow configuration.

    Args:
        workflow_id: Unique identifier
        excitation_type: "sweep" or "stepped"
        frequency_range_hz: Search range (default: 70-130 Hz)
        selection_method: Peak selection method
        min_captures_for_repeatability: Minimum captures for repeatability
        min_prominence_db: Minimum peak prominence
        min_coherence: Minimum coherence threshold
        created_at_utc: Creation timestamp

    Returns:
        MainBodyAirResonanceWorkflowV1 instance
    """
    if created_at_utc is None:
        created_at_utc = datetime.now(timezone.utc).isoformat()

    return MainBodyAirResonanceWorkflowV1(
        workflow_id=workflow_id,
        excitation_type=excitation_type,
        frequency_range_hz=frequency_range_hz,
        selection_method=selection_method,
        min_captures_for_repeatability=min_captures_for_repeatability,
        min_prominence_db=min_prominence_db,
        min_coherence=min_coherence,
        created_at_utc=created_at_utc,
    )

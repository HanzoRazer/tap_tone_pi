# INSTRUMENT CLASS: MEASUREMENT
"""Pressure response mapping contracts and workflow (DO-94).

This package provides spatial pressure-response mapping using controlled excitation.
It records pressure response at grid positions, NOT true mode shapes.

A microphone grid measures radiated or near-field pressure, not plate surface
velocity. The map shows where radiated pressure is strongest at each frequency.

Contracts:
- PressureGridPointV1: single grid point location
- PressureGridV1: collection of grid points
- PressureResponseSampleV1: pressure response at one point/frequency
- PressureResponseMapV1: complete map of pressure responses
- PressureResponseMappingWorkflowV1: workflow configuration

No advisory semantics. No mode-shape claims. No soundhole recommendations.
"""

from tap_tone_pi.pressure_map.contracts import (
    CoordinateSystem,
    PressureGridPointV1,
    PressureGridV1,
    PressureResponseSampleV1,
    PressureResponseMapV1,
)
from tap_tone_pi.pressure_map.workflow import (
    PressureResponseMappingWorkflowV1,
    create_pressure_response_mapping_workflow,
)
from tap_tone_pi.pressure_map.assembly import (
    create_pressure_grid_point,
    create_pressure_grid,
    create_pressure_response_sample,
    assemble_pressure_response_map,
    normalize_pressure_response_map,
    summarize_pressure_response_map,
    PressureResponseMapSummaryV1,
)

__all__ = [
    # Coordinate system
    "CoordinateSystem",
    # Contracts
    "PressureGridPointV1",
    "PressureGridV1",
    "PressureResponseSampleV1",
    "PressureResponseMapV1",
    # Workflow
    "PressureResponseMappingWorkflowV1",
    "create_pressure_response_mapping_workflow",
    # Assembly
    "create_pressure_grid_point",
    "create_pressure_grid",
    "create_pressure_response_sample",
    "assemble_pressure_response_map",
    "normalize_pressure_response_map",
    "summarize_pressure_response_map",
    "PressureResponseMapSummaryV1",
]

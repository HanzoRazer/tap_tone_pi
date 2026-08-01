"""Shipped guided laboratory workflow definitions (DO-100).

The registry is a tuple, not a mutable mapping: a definition either ships or it
does not. Uniqueness of ``(workflow_id, workflow_version)`` is enforced, but by
:func:`tap_tone_pi.guided_lab.catalog.shipped_workflow_definitions` on first
use, not here at import. A duplicate is still a hard failure the first time
anything asks for a workflow; it is no longer a failure to import the module,
which would have taken the rest of the ``ttp`` CLI down with it.
"""

from __future__ import annotations

from tap_tone_pi.guided_lab.models import WorkflowDefinitionV1
from tap_tone_pi.guided_lab.workflows.plate_measurement_setup_v1 import (
    PLATE_MEASUREMENT_SETUP_V1,
)

WORKFLOW_DEFINITIONS: tuple[WorkflowDefinitionV1, ...] = (PLATE_MEASUREMENT_SETUP_V1,)

__all__ = [
    "PLATE_MEASUREMENT_SETUP_V1",
    "WORKFLOW_DEFINITIONS",
]

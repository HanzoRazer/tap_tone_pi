# INSTRUMENT CLASS: MEASUREMENT
"""Main body air resonance (A0) measurement contracts and workflow (DO-92).

This package provides measurement contracts for A0 identification:
- A0PeakCandidateV1: candidate peak in A0 frequency range
- A0MeasurementEvidenceV1: all candidates with selection method
- A0MeasurementRecordV1: provenance-aware A0 measurement record
- MainBodyAirResonanceWorkflowV1: workflow configuration

A0 is the main air resonance (Helmholtz resonance) of the guitar body.
This workflow identifies and characterizes A0 using controlled excitation.

No advisory semantics. No soundhole recommendations.
"""

from tap_tone_pi.a0.contracts import (
    A0PeakCandidateV1,
    A0MeasurementEvidenceV1,
    A0MeasurementRecordV1,
    create_a0_peak_candidate,
    create_a0_measurement_evidence,
    create_a0_measurement_record,
)
from tap_tone_pi.a0.workflow import (
    MainBodyAirResonanceWorkflowV1,
    create_a0_workflow,
    DEFAULT_A0_FREQUENCY_RANGE,
    DEFAULT_A0_SELECTION_METHOD,
)
from tap_tone_pi.a0.peak_detection import (
    find_a0_candidates,
    select_candidate_by_method,
)

__all__ = [
    # Contracts
    "A0PeakCandidateV1",
    "A0MeasurementEvidenceV1",
    "A0MeasurementRecordV1",
    "create_a0_peak_candidate",
    "create_a0_measurement_evidence",
    "create_a0_measurement_record",
    # Workflow
    "MainBodyAirResonanceWorkflowV1",
    "create_a0_workflow",
    "DEFAULT_A0_FREQUENCY_RANGE",
    "DEFAULT_A0_SELECTION_METHOD",
    # Peak detection
    "find_a0_candidates",
    "select_candidate_by_method",
]

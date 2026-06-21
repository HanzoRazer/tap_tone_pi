# INSTRUMENT CLASS: MEASUREMENT
"""A0 measurement contracts (DO-92).

Contracts for main body air resonance (A0) measurement:
- A0PeakCandidateV1: individual candidate peak
- A0MeasurementEvidenceV1: all candidates with selection
- A0MeasurementRecordV1: provenance-aware measurement record

No advisory semantics. No soundhole recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class A0PeakCandidateV1:
    """A candidate peak in the A0 frequency range.

    Records observed peak characteristics without interpretation.

    Attributes:
        frequency_hz: Peak frequency
        amplitude_db: Peak amplitude in dB
        bandwidth_hz: Half-power bandwidth
        q_factor: Quality factor (frequency / bandwidth)
        prominence_db: Spectral prominence above local background
        confidence: Detection confidence (high/medium/low)
    """

    schema_version: str = field(default="a0_peak_candidate_v1", init=False)
    frequency_hz: float = 0.0
    amplitude_db: float = 0.0
    bandwidth_hz: float = 0.0
    q_factor: float = 0.0
    prominence_db: float = 0.0
    confidence: str = "medium"
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "frequency_hz": self.frequency_hz,
            "amplitude_db": self.amplitude_db,
            "bandwidth_hz": self.bandwidth_hz,
            "q_factor": self.q_factor,
            "prominence_db": self.prominence_db,
            "confidence": self.confidence,
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class A0MeasurementEvidenceV1:
    """Evidence record for A0 measurement.

    Stores all candidate peaks and selection metadata.
    The selection method is recorded, not hidden.

    Attributes:
        evidence_id: Unique identifier
        candidates: List of all detected candidates
        selected_candidate_index: Index of selected candidate (or None)
        selection_method: Method used for selection
        repeatability_evidence_id: Link to repeatability study
        repeatability_score: Score from repeated measurements (0-1)
        coherence_at_peak: Coherence value at selected peak frequency
        frequency_range_hz: Search range (low, high)
    """

    schema_version: str = field(default="a0_measurement_evidence_v1", init=False)
    evidence_id: str = ""
    candidates: Tuple[A0PeakCandidateV1, ...] = field(default_factory=tuple)
    selected_candidate_index: Optional[int] = None
    selection_method: str = "lowest_prominent_peak_in_range"
    repeatability_evidence_id: Optional[str] = None
    repeatability_score: Optional[float] = None
    coherence_at_peak: Optional[float] = None
    frequency_range_hz: Tuple[float, float] = (70.0, 130.0)
    computed_at_utc: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "candidates": [c.to_dict() for c in self.candidates],
            "selected_candidate_index": self.selected_candidate_index,
            "selection_method": self.selection_method,
            "frequency_range_hz": list(self.frequency_range_hz),
            "computed_at_utc": self.computed_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.repeatability_evidence_id is not None:
            d["repeatability_evidence_id"] = self.repeatability_evidence_id
        if self.repeatability_score is not None:
            d["repeatability_score"] = self.repeatability_score
        if self.coherence_at_peak is not None:
            d["coherence_at_peak"] = self.coherence_at_peak

        return d

    @property
    def selected_candidate(self) -> Optional[A0PeakCandidateV1]:
        """Return the selected candidate, or None if not selected."""
        if self.selected_candidate_index is None:
            return None
        if 0 <= self.selected_candidate_index < len(self.candidates):
            return self.candidates[self.selected_candidate_index]
        return None


@dataclass(frozen=True)
class A0MeasurementRecordV1:
    """Provenance-aware A0 measurement record.

    Links A0 measurement to excitation, TF result, and evidence.
    Contains the selected peak values for convenience.

    Attributes:
        measurement_id: Unique identifier
        workflow_id: Link to workflow configuration
        excitation_response_pair_id: Link to excitation-response pair
        transfer_function_result_id: Link to TF result
        evidence_id: Link to measurement evidence
        fixture_id: Link to fixture configuration
        environment_id: Link to environment record
        peak_frequency_hz: Selected A0 frequency
        peak_amplitude_db: Selected A0 amplitude
        bandwidth_hz: Half-power bandwidth
        q_factor: Quality factor
        measured_at_utc: Measurement timestamp
    """

    schema_version: str = field(default="a0_measurement_record_v1", init=False)
    measurement_id: str = ""
    workflow_id: str = ""
    excitation_response_pair_id: str = ""
    transfer_function_result_id: str = ""
    evidence_id: str = ""
    fixture_id: Optional[str] = None
    environment_id: Optional[str] = None
    peak_frequency_hz: float = 0.0
    peak_amplitude_db: float = 0.0
    bandwidth_hz: float = 0.0
    q_factor: float = 0.0
    measured_at_utc: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "workflow_id": self.workflow_id,
            "excitation_response_pair_id": self.excitation_response_pair_id,
            "transfer_function_result_id": self.transfer_function_result_id,
            "evidence_id": self.evidence_id,
            "peak_frequency_hz": self.peak_frequency_hz,
            "peak_amplitude_db": self.peak_amplitude_db,
            "bandwidth_hz": self.bandwidth_hz,
            "q_factor": self.q_factor,
            "measured_at_utc": self.measured_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.fixture_id is not None:
            d["fixture_id"] = self.fixture_id
        if self.environment_id is not None:
            d["environment_id"] = self.environment_id

        return d


def create_a0_peak_candidate(
    frequency_hz: float,
    amplitude_db: float,
    bandwidth_hz: float,
    q_factor: float,
    *,
    prominence_db: float = 0.0,
    confidence: str = "medium",
) -> A0PeakCandidateV1:
    """Create an A0 peak candidate.

    Args:
        frequency_hz: Peak frequency
        amplitude_db: Peak amplitude in dB
        bandwidth_hz: Half-power bandwidth
        q_factor: Quality factor
        prominence_db: Spectral prominence
        confidence: Detection confidence

    Returns:
        A0PeakCandidateV1 instance
    """
    return A0PeakCandidateV1(
        frequency_hz=frequency_hz,
        amplitude_db=amplitude_db,
        bandwidth_hz=bandwidth_hz,
        q_factor=q_factor,
        prominence_db=prominence_db,
        confidence=confidence,
    )


def create_a0_measurement_evidence(
    evidence_id: str,
    candidates: List[A0PeakCandidateV1],
    *,
    selected_candidate_index: Optional[int] = None,
    selection_method: str = "lowest_prominent_peak_in_range",
    repeatability_evidence_id: Optional[str] = None,
    repeatability_score: Optional[float] = None,
    coherence_at_peak: Optional[float] = None,
    frequency_range_hz: Tuple[float, float] = (70.0, 130.0),
    computed_at_utc: Optional[str] = None,
) -> A0MeasurementEvidenceV1:
    """Create A0 measurement evidence.

    Args:
        evidence_id: Unique identifier
        candidates: List of detected candidates
        selected_candidate_index: Index of selected candidate
        selection_method: Selection method used
        repeatability_evidence_id: Link to repeatability study
        repeatability_score: Repeatability score (0-1)
        coherence_at_peak: Coherence at selected frequency
        frequency_range_hz: Search range
        computed_at_utc: Computation timestamp

    Returns:
        A0MeasurementEvidenceV1 instance
    """
    if computed_at_utc is None:
        computed_at_utc = datetime.now(timezone.utc).isoformat()

    return A0MeasurementEvidenceV1(
        evidence_id=evidence_id,
        candidates=tuple(candidates),
        selected_candidate_index=selected_candidate_index,
        selection_method=selection_method,
        repeatability_evidence_id=repeatability_evidence_id,
        repeatability_score=repeatability_score,
        coherence_at_peak=coherence_at_peak,
        frequency_range_hz=frequency_range_hz,
        computed_at_utc=computed_at_utc,
    )


def create_a0_measurement_record(
    measurement_id: str,
    workflow_id: str,
    excitation_response_pair_id: str,
    transfer_function_result_id: str,
    evidence_id: str,
    peak_frequency_hz: float,
    peak_amplitude_db: float,
    bandwidth_hz: float,
    q_factor: float,
    *,
    fixture_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    measured_at_utc: Optional[str] = None,
) -> A0MeasurementRecordV1:
    """Create an A0 measurement record.

    Args:
        measurement_id: Unique identifier
        workflow_id: Link to workflow
        excitation_response_pair_id: Link to excitation-response pair
        transfer_function_result_id: Link to TF result
        evidence_id: Link to evidence
        peak_frequency_hz: Selected A0 frequency
        peak_amplitude_db: Selected A0 amplitude
        bandwidth_hz: Half-power bandwidth
        q_factor: Quality factor
        fixture_id: Link to fixture
        environment_id: Link to environment
        measured_at_utc: Measurement timestamp

    Returns:
        A0MeasurementRecordV1 instance
    """
    if measured_at_utc is None:
        measured_at_utc = datetime.now(timezone.utc).isoformat()

    return A0MeasurementRecordV1(
        measurement_id=measurement_id,
        workflow_id=workflow_id,
        excitation_response_pair_id=excitation_response_pair_id,
        transfer_function_result_id=transfer_function_result_id,
        evidence_id=evidence_id,
        fixture_id=fixture_id,
        environment_id=environment_id,
        peak_frequency_hz=peak_frequency_hz,
        peak_amplitude_db=peak_amplitude_db,
        bandwidth_hz=bandwidth_hz,
        q_factor=q_factor,
        measured_at_utc=measured_at_utc,
    )

# INSTRUMENT CLASS: MEASUREMENT
"""Tests for A0 workflow contracts and peak detection (DO-92).

Validates:
- A0PeakCandidateV1 structure
- A0MeasurementEvidenceV1 structure
- A0MeasurementRecordV1 structure
- MainBodyAirResonanceWorkflowV1 configuration
- Peak detection and selection
- Provenance linkage
- Advisory-free semantics
"""

import json
import pytest
import numpy as np

from tap_tone_pi.a0 import (
    # Contracts
    A0PeakCandidateV1,
    A0MeasurementEvidenceV1,
    A0MeasurementRecordV1,
    create_a0_peak_candidate,
    create_a0_measurement_evidence,
    create_a0_measurement_record,
    # Workflow
    MainBodyAirResonanceWorkflowV1,
    create_a0_workflow,
    DEFAULT_A0_FREQUENCY_RANGE,
    DEFAULT_A0_SELECTION_METHOD,
    # Peak detection
    find_a0_candidates,
    select_candidate_by_method,
)


class TestA0PeakCandidate:
    """Tests for A0PeakCandidateV1."""

    def test_candidate_is_frozen(self):
        """A0PeakCandidateV1 must be immutable."""
        candidate = A0PeakCandidateV1(frequency_hz=100.0)
        with pytest.raises(AttributeError):
            candidate.frequency_hz = 110.0

    def test_candidate_has_schema_version(self):
        """A0PeakCandidateV1 must have schema_version."""
        candidate = A0PeakCandidateV1(frequency_hz=100.0)
        assert candidate.schema_version == "a0_peak_candidate_v1"

    def test_candidate_has_epistemic_status(self):
        """A0PeakCandidateV1 must have epistemic_status = derived."""
        candidate = A0PeakCandidateV1(frequency_hz=100.0)
        assert candidate.epistemic_status == "derived"

    def test_create_candidate(self):
        """create_a0_peak_candidate must work correctly."""
        candidate = create_a0_peak_candidate(
            frequency_hz=95.5,
            amplitude_db=-12.3,
            bandwidth_hz=8.2,
            q_factor=11.6,
            prominence_db=15.0,
            confidence="high",
        )
        assert candidate.frequency_hz == 95.5
        assert candidate.amplitude_db == -12.3
        assert candidate.bandwidth_hz == 8.2
        assert candidate.q_factor == 11.6
        assert candidate.prominence_db == 15.0
        assert candidate.confidence == "high"

    def test_candidate_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        candidate = create_a0_peak_candidate(
            frequency_hz=100.0,
            amplitude_db=-10.0,
            bandwidth_hz=10.0,
            q_factor=10.0,
        )
        d = candidate.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["frequency_hz"] == 100.0


class TestA0MeasurementEvidence:
    """Tests for A0MeasurementEvidenceV1."""

    def test_evidence_is_frozen(self):
        """A0MeasurementEvidenceV1 must be immutable."""
        evidence = A0MeasurementEvidenceV1(evidence_id="ev_001")
        with pytest.raises(AttributeError):
            evidence.evidence_id = "modified"

    def test_evidence_has_schema_version(self):
        """A0MeasurementEvidenceV1 must have schema_version."""
        evidence = A0MeasurementEvidenceV1(evidence_id="ev_001")
        assert evidence.schema_version == "a0_measurement_evidence_v1"

    def test_evidence_has_epistemic_status(self):
        """A0MeasurementEvidenceV1 must have epistemic_status = derived."""
        evidence = A0MeasurementEvidenceV1(evidence_id="ev_001")
        assert evidence.epistemic_status == "derived"

    def test_create_evidence_with_candidates(self):
        """create_a0_measurement_evidence must store candidates."""
        c1 = create_a0_peak_candidate(90.0, -10.0, 8.0, 11.0)
        c2 = create_a0_peak_candidate(105.0, -8.0, 7.0, 15.0)

        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[c1, c2],
            selected_candidate_index=1,
            selection_method="lowest_prominent_peak_in_range",
        )

        assert evidence.evidence_id == "ev_001"
        assert len(evidence.candidates) == 2
        assert evidence.selected_candidate_index == 1
        assert evidence.selection_method == "lowest_prominent_peak_in_range"

    def test_selected_candidate_property(self):
        """selected_candidate must return correct candidate."""
        c1 = create_a0_peak_candidate(90.0, -10.0, 8.0, 11.0)
        c2 = create_a0_peak_candidate(105.0, -8.0, 7.0, 15.0)

        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[c1, c2],
            selected_candidate_index=1,
        )

        selected = evidence.selected_candidate
        assert selected is not None
        assert selected.frequency_hz == 105.0

    def test_selected_candidate_none_when_not_selected(self):
        """selected_candidate must return None when not selected."""
        c1 = create_a0_peak_candidate(90.0, -10.0, 8.0, 11.0)

        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[c1],
            selected_candidate_index=None,
        )

        assert evidence.selected_candidate is None

    def test_evidence_with_repeatability(self):
        """create_a0_measurement_evidence must accept repeatability."""
        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[],
            repeatability_evidence_id="rep_001",
            repeatability_score=0.95,
            coherence_at_peak=0.92,
        )

        assert evidence.repeatability_evidence_id == "rep_001"
        assert evidence.repeatability_score == 0.95
        assert evidence.coherence_at_peak == 0.92

    def test_evidence_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        c1 = create_a0_peak_candidate(90.0, -10.0, 8.0, 11.0)

        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[c1],
            selected_candidate_index=0,
        )

        d = evidence.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["evidence_id"] == "ev_001"
        assert len(parsed["candidates"]) == 1


class TestA0MeasurementRecord:
    """Tests for A0MeasurementRecordV1."""

    def test_record_is_frozen(self):
        """A0MeasurementRecordV1 must be immutable."""
        record = A0MeasurementRecordV1(measurement_id="a0_001")
        with pytest.raises(AttributeError):
            record.measurement_id = "modified"

    def test_record_has_schema_version(self):
        """A0MeasurementRecordV1 must have schema_version."""
        record = A0MeasurementRecordV1(measurement_id="a0_001")
        assert record.schema_version == "a0_measurement_record_v1"

    def test_record_has_epistemic_status(self):
        """A0MeasurementRecordV1 must have epistemic_status = derived."""
        record = A0MeasurementRecordV1(measurement_id="a0_001")
        assert record.epistemic_status == "derived"

    def test_create_record(self):
        """create_a0_measurement_record must work correctly."""
        record = create_a0_measurement_record(
            measurement_id="a0_001",
            workflow_id="wf_001",
            excitation_response_pair_id="pair_001",
            transfer_function_result_id="tf_001",
            evidence_id="ev_001",
            peak_frequency_hz=98.5,
            peak_amplitude_db=-11.2,
            bandwidth_hz=8.5,
            q_factor=11.6,
            fixture_id="fix_001",
            environment_id="env_001",
        )

        assert record.measurement_id == "a0_001"
        assert record.workflow_id == "wf_001"
        assert record.excitation_response_pair_id == "pair_001"
        assert record.transfer_function_result_id == "tf_001"
        assert record.evidence_id == "ev_001"
        assert record.peak_frequency_hz == 98.5
        assert record.fixture_id == "fix_001"
        assert record.environment_id == "env_001"

    def test_record_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        record = create_a0_measurement_record(
            measurement_id="a0_001",
            workflow_id="wf_001",
            excitation_response_pair_id="pair_001",
            transfer_function_result_id="tf_001",
            evidence_id="ev_001",
            peak_frequency_hz=98.5,
            peak_amplitude_db=-11.2,
            bandwidth_hz=8.5,
            q_factor=11.6,
        )

        d = record.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["measurement_id"] == "a0_001"
        assert parsed["peak_frequency_hz"] == 98.5


class TestMainBodyAirResonanceWorkflow:
    """Tests for MainBodyAirResonanceWorkflowV1."""

    def test_workflow_is_frozen(self):
        """MainBodyAirResonanceWorkflowV1 must be immutable."""
        workflow = MainBodyAirResonanceWorkflowV1(workflow_id="wf_001")
        with pytest.raises(AttributeError):
            workflow.workflow_id = "modified"

    def test_workflow_has_schema_version(self):
        """MainBodyAirResonanceWorkflowV1 must have schema_version."""
        workflow = MainBodyAirResonanceWorkflowV1(workflow_id="wf_001")
        assert workflow.schema_version == "main_body_air_resonance_workflow_v1"

    def test_workflow_has_epistemic_status(self):
        """MainBodyAirResonanceWorkflowV1 must have epistemic_status = derived."""
        workflow = MainBodyAirResonanceWorkflowV1(workflow_id="wf_001")
        assert workflow.epistemic_status == "derived"

    def test_default_frequency_range(self):
        """Default frequency range must be 70-130 Hz."""
        assert DEFAULT_A0_FREQUENCY_RANGE == (70.0, 130.0)

    def test_default_selection_method(self):
        """Default selection method must be lowest_prominent_peak_in_range."""
        assert DEFAULT_A0_SELECTION_METHOD == "lowest_prominent_peak_in_range"

    def test_create_workflow_defaults(self):
        """create_a0_workflow must apply defaults."""
        workflow = create_a0_workflow(workflow_id="wf_001")

        assert workflow.workflow_id == "wf_001"
        assert workflow.excitation_type == "sweep"
        assert workflow.frequency_range_hz == (70.0, 130.0)
        assert workflow.selection_method == "lowest_prominent_peak_in_range"
        assert workflow.min_captures_for_repeatability == 3
        assert workflow.min_prominence_db == 6.0
        assert workflow.min_coherence == 0.8

    def test_create_workflow_custom(self):
        """create_a0_workflow must accept custom values."""
        workflow = create_a0_workflow(
            workflow_id="wf_001",
            excitation_type="stepped",
            frequency_range_hz=(80.0, 120.0),
            selection_method="highest_amplitude",
            min_captures_for_repeatability=5,
            min_prominence_db=8.0,
            min_coherence=0.9,
        )

        assert workflow.excitation_type == "stepped"
        assert workflow.frequency_range_hz == (80.0, 120.0)
        assert workflow.selection_method == "highest_amplitude"
        assert workflow.min_captures_for_repeatability == 5
        assert workflow.min_prominence_db == 8.0
        assert workflow.min_coherence == 0.9

    def test_workflow_to_dict_is_json_serializable(self):
        """to_dict() must produce valid JSON."""
        workflow = create_a0_workflow(workflow_id="wf_001")

        d = workflow.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["workflow_id"] == "wf_001"
        assert parsed["excitation_type"] == "sweep"


class TestPeakDetection:
    """Tests for A0 peak detection."""

    def _create_test_spectrum(self):
        """Create a test spectrum with known peaks."""
        frequencies = np.linspace(50, 200, 1000)

        # Create base noise
        magnitude = np.ones_like(frequencies) * 0.01

        # Add peaks at 85 Hz, 100 Hz, 120 Hz
        for peak_freq, peak_height in [(85, 0.5), (100, 1.0), (120, 0.3)]:
            q = 15
            bandwidth = peak_freq / q
            peak = peak_height / (
                1 + ((frequencies - peak_freq) / (bandwidth / 2)) ** 2
            )
            magnitude += peak

        return frequencies, magnitude

    def test_find_a0_candidates(self):
        """find_a0_candidates must find peaks in range."""
        frequencies, magnitude = self._create_test_spectrum()

        candidates = find_a0_candidates(
            frequencies,
            magnitude,
            frequency_range_hz=(70.0, 130.0),
            min_prominence_db=3.0,
        )

        assert len(candidates) >= 2
        # Should find peaks at ~85, ~100, ~120 Hz
        freqs = [c.frequency_hz for c in candidates]
        assert any(80 < f < 90 for f in freqs)
        assert any(95 < f < 105 for f in freqs)

    def test_find_a0_candidates_empty_range(self):
        """find_a0_candidates must return empty for out-of-range."""
        frequencies, magnitude = self._create_test_spectrum()

        candidates = find_a0_candidates(
            frequencies,
            magnitude,
            frequency_range_hz=(200.0, 300.0),
        )

        assert len(candidates) == 0

    def test_select_candidate_lowest_prominent(self):
        """select_candidate_by_method must find lowest prominent peak."""
        c1 = create_a0_peak_candidate(85.0, -10.0, 6.0, 14.0, prominence_db=8.0)
        c2 = create_a0_peak_candidate(100.0, -5.0, 7.0, 14.0, prominence_db=12.0)
        c3 = create_a0_peak_candidate(120.0, -8.0, 8.0, 15.0, prominence_db=10.0)

        idx = select_candidate_by_method(
            [c1, c2, c3],
            method="lowest_prominent_peak_in_range",
            min_prominence_db=6.0,
        )

        assert idx == 0  # 85 Hz is lowest and meets threshold

    def test_select_candidate_highest_amplitude(self):
        """select_candidate_by_method must find highest amplitude."""
        c1 = create_a0_peak_candidate(85.0, -10.0, 6.0, 14.0)
        c2 = create_a0_peak_candidate(100.0, -5.0, 7.0, 14.0)
        c3 = create_a0_peak_candidate(120.0, -8.0, 8.0, 15.0)

        idx = select_candidate_by_method(
            [c1, c2, c3],
            method="highest_amplitude",
        )

        assert idx == 1  # 100 Hz has highest amplitude (-5 dB)

    def test_select_candidate_highest_q(self):
        """select_candidate_by_method must find highest Q."""
        c1 = create_a0_peak_candidate(85.0, -10.0, 6.0, 14.0)
        c2 = create_a0_peak_candidate(100.0, -5.0, 7.0, 14.0)
        c3 = create_a0_peak_candidate(120.0, -8.0, 8.0, 20.0)

        idx = select_candidate_by_method(
            [c1, c2, c3],
            method="highest_q",
        )

        assert idx == 2  # 120 Hz has highest Q (20)

    def test_select_candidate_empty_list(self):
        """select_candidate_by_method must return None for empty list."""
        idx = select_candidate_by_method([], method="lowest_prominent_peak_in_range")
        assert idx is None


class TestProvenanceLinkage:
    """Tests for provenance chain integrity."""

    def test_record_links_to_workflow(self):
        """A0MeasurementRecordV1 must link to workflow."""
        record = create_a0_measurement_record(
            measurement_id="a0_001",
            workflow_id="wf_001",
            excitation_response_pair_id="pair_001",
            transfer_function_result_id="tf_001",
            evidence_id="ev_001",
            peak_frequency_hz=98.5,
            peak_amplitude_db=-11.2,
            bandwidth_hz=8.5,
            q_factor=11.6,
        )

        d = record.to_dict()
        assert d["workflow_id"] == "wf_001"
        assert d["excitation_response_pair_id"] == "pair_001"
        assert d["transfer_function_result_id"] == "tf_001"
        assert d["evidence_id"] == "ev_001"

    def test_record_links_to_environment(self):
        """A0MeasurementRecordV1 must link to environment."""
        record = create_a0_measurement_record(
            measurement_id="a0_001",
            workflow_id="wf_001",
            excitation_response_pair_id="pair_001",
            transfer_function_result_id="tf_001",
            evidence_id="ev_001",
            peak_frequency_hz=98.5,
            peak_amplitude_db=-11.2,
            bandwidth_hz=8.5,
            q_factor=11.6,
            fixture_id="fix_001",
            environment_id="env_001",
        )

        d = record.to_dict()
        assert d["fixture_id"] == "fix_001"
        assert d["environment_id"] == "env_001"


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free semantics."""

    FORBIDDEN_ADVISORY_TERMS = {
        "recommended",
        "optimal",
        "best",
        "preferred",
        "approved",
        "good",
        "bad",
        "quality",
        "grade",
        "verdict",
        "pass",
        "fail",
        "should",
        "must",
        "proceed",
        "stop",
        "acceptable",
        "soundhole",
        "adjust",
        "modify",
        "suggestion",
    }

    def test_candidate_is_advisory_free(self):
        """A0PeakCandidateV1 must not contain advisory terms."""
        candidate = create_a0_peak_candidate(100.0, -10.0, 8.0, 12.0)
        d = candidate.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Candidate contains forbidden advisory term '{term}'"
            )

    def test_evidence_is_advisory_free(self):
        """A0MeasurementEvidenceV1 must not contain advisory terms."""
        c1 = create_a0_peak_candidate(100.0, -10.0, 8.0, 12.0)
        evidence = create_a0_measurement_evidence(
            evidence_id="ev_001",
            candidates=[c1],
            selected_candidate_index=0,
        )
        d = evidence.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Evidence contains forbidden advisory term '{term}'"
            )

    def test_record_is_advisory_free(self):
        """A0MeasurementRecordV1 must not contain advisory terms."""
        record = create_a0_measurement_record(
            measurement_id="a0_001",
            workflow_id="wf_001",
            excitation_response_pair_id="pair_001",
            transfer_function_result_id="tf_001",
            evidence_id="ev_001",
            peak_frequency_hz=98.5,
            peak_amplitude_db=-11.2,
            bandwidth_hz=8.5,
            q_factor=11.6,
        )
        d = record.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Record contains forbidden advisory term '{term}'"
            )

    def test_workflow_is_advisory_free(self):
        """MainBodyAirResonanceWorkflowV1 must not contain advisory terms."""
        workflow = create_a0_workflow(workflow_id="wf_001")
        d = workflow.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"Workflow contains forbidden advisory term '{term}'"
            )

# INSTRUMENT CLASS: MEASUREMENT
"""Tests for workflow contracts and execution evidence (Dev Order 86).

Tests cover:
- Contract serialization
- Execution evidence derivation
- Calibration state handling
- Procedural (not advisory) semantics
- Export compatibility
"""

import pytest
import json

from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    WorkflowExecutionEvidenceV1,
    WorkflowExecutionState,
    CalibrationState,
    FixtureRequirements,
    EnvironmentRequirements,
)
from tap_tone_pi.workflow.validation import (
    evaluate_workflow_execution,
    derive_calibration_state,
)
from tap_tone_pi.workflow.registry import (
    FREE_PLATE_TAP_V1,
    CALIBRATION_PASS_V1,
    BUILTIN_WORKFLOWS,
)


class TestWorkflowContractSerialization:
    """Tests for MeasurementWorkflowContractV1 serialization."""

    def test_contract_serializes_to_dict(self):
        """Contract should serialize to dict for JSON export."""
        d = FREE_PLATE_TAP_V1.to_dict()

        assert d["schema_version"] == "measurement_workflow_contract_v1"
        assert d["workflow_id"] == "free_plate_tap_v1"
        assert d["required_repetitions"] == 5
        assert d["requires_calibration"] is True

    def test_contract_serializes_to_json(self):
        """Contract dict should be JSON-serializable."""
        d = FREE_PLATE_TAP_V1.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["workflow_id"] == "free_plate_tap_v1"

    def test_minimum_coherence_optional(self):
        """minimum_coherence should be omitted when None."""
        d = FREE_PLATE_TAP_V1.to_dict()

        # Built-in workflows don't have minimum_coherence set
        assert "minimum_coherence" not in d or d.get("minimum_coherence") is None

    def test_minimum_coherence_included_when_set(self):
        """minimum_coherence should be included when set."""
        contract = MeasurementWorkflowContractV1(
            workflow_id="transfer_function_v1",
            display_name="Transfer Function",
            description="Two-channel transfer function measurement",
            required_repetitions=3,
            max_frequency_variance_pct=2.0,
            sample_rate_hz=48000,
            fft_window="hann",
            min_snr_db=25.0,
            minimum_coherence=0.7,
        )
        d = contract.to_dict()

        assert d["minimum_coherence"] == 0.7


class TestWorkflowContractValidation:
    """Tests for contract validation."""

    def test_valid_contract_has_no_errors(self):
        """Built-in workflows should validate without errors."""
        for wf_id, wf in BUILTIN_WORKFLOWS.items():
            errors = wf.validate()
            assert len(errors) == 0, f"{wf_id} has validation errors: {errors}"

    def test_invalid_repetitions_rejected(self):
        """required_repetitions < 1 should fail validation."""
        contract = MeasurementWorkflowContractV1(
            workflow_id="test",
            display_name="Test",
            description="Test",
            required_repetitions=0,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            min_snr_db=30.0,
        )
        errors = contract.validate()

        assert any("required_repetitions" in e for e in errors)

    def test_invalid_coherence_rejected(self):
        """minimum_coherence outside [0, 1] should fail validation."""
        contract = MeasurementWorkflowContractV1(
            workflow_id="test",
            display_name="Test",
            description="Test",
            required_repetitions=3,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            min_snr_db=30.0,
            minimum_coherence=1.5,
        )
        errors = contract.validate()

        assert any("minimum_coherence" in e for e in errors)


class TestWorkflowExecutionEvidence:
    """Tests for WorkflowExecutionEvidenceV1."""

    def test_evidence_serializes_to_dict(self):
        """Execution evidence should serialize to dict."""
        evidence = WorkflowExecutionEvidenceV1(
            workflow_id="free_plate_tap_v1",
            repetitions_completed=5,
            execution_state="complete",
            calibration_state="valid",
            workflow_complete=True,
            required_repetitions_completed=True,
        )
        d = evidence.to_dict()

        assert d["schema_version"] == "workflow_execution_evidence_v1"
        assert d["workflow_id"] == "free_plate_tap_v1"
        assert d["execution_state"] == "complete"
        assert d["workflow_complete"] is True

    def test_evidence_serializes_to_json(self):
        """Evidence dict should be JSON-serializable."""
        evidence = WorkflowExecutionEvidenceV1(
            workflow_id="free_plate_tap_v1",
            repetitions_completed=3,
            execution_state="partial",
            calibration_state="valid",
        )
        d = evidence.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_epistemic_status_is_derived(self):
        """epistemic_status should default to 'derived'."""
        evidence = WorkflowExecutionEvidenceV1(
            workflow_id="test",
            repetitions_completed=1,
            execution_state="partial",
            calibration_state="valid",
        )

        assert evidence.epistemic_status == "derived"


class TestWorkflowExecutionEvaluation:
    """Tests for evaluate_workflow_execution helper."""

    def test_partial_workflow_state(self):
        """Incomplete repetitions should yield partial state."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=3,  # 3 of 5 required
            calibration_state=CalibrationState.VALID,
        )

        assert evidence.execution_state == "partial"
        assert evidence.workflow_complete is False
        assert evidence.required_repetitions_completed is False

    def test_complete_workflow_state(self):
        """All requirements met should yield complete state."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,  # 5 of 5 required
            calibration_state=CalibrationState.VALID,
        )

        assert evidence.execution_state == "complete"
        assert evidence.workflow_complete is True
        assert evidence.required_repetitions_completed is True

    def test_stale_calibration_blocks_completion(self):
        """Stale calibration should prevent workflow completion."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.STALE,
        )

        assert evidence.execution_state == "partial"
        assert evidence.workflow_complete is False

    def test_missing_calibration_blocks_completion(self):
        """Missing calibration should prevent workflow completion."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.MISSING,
        )

        assert evidence.workflow_complete is False

    def test_calibration_not_required_workflow(self):
        """Workflow without calibration requirement should complete without it."""
        evidence = evaluate_workflow_execution(
            CALIBRATION_PASS_V1,  # requires_calibration=False
            repetitions_completed=3,  # 3 of 3 required
            calibration_state=CalibrationState.NOT_REQUIRED,
        )

        assert evidence.workflow_complete is True

    def test_not_started_state(self):
        """Zero repetitions should yield not_started state."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=0,
            calibration_state=CalibrationState.VALID,
        )

        assert evidence.execution_state == "not_started"
        assert evidence.workflow_complete is False

    def test_failed_calibration_yields_incomplete(self):
        """Failed calibration should yield incomplete state."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.FAILED,
        )

        assert evidence.execution_state == "incomplete"
        assert evidence.workflow_complete is False


class TestCalibrationStateDerivation:
    """Tests for derive_calibration_state helper."""

    def test_valid_calibration(self):
        """Fresh, valid calibration should return VALID."""
        state = derive_calibration_state(
            calibration_exists=True,
            calibration_valid=True,
            calibration_age_days=5,
            max_age_days=30,
        )

        assert state == CalibrationState.VALID

    def test_stale_calibration(self):
        """Expired calibration should return STALE."""
        state = derive_calibration_state(
            calibration_exists=True,
            calibration_valid=True,
            calibration_age_days=45,
            max_age_days=30,
        )

        assert state == CalibrationState.STALE

    def test_missing_calibration(self):
        """Missing calibration should return MISSING."""
        state = derive_calibration_state(
            calibration_exists=False,
        )

        assert state == CalibrationState.MISSING

    def test_failed_calibration(self):
        """Failed calibration should return FAILED."""
        state = derive_calibration_state(
            calibration_exists=True,
            calibration_failed=True,
        )

        assert state == CalibrationState.FAILED

    def test_not_required_calibration(self):
        """Calibration not required should return NOT_REQUIRED."""
        state = derive_calibration_state(
            calibration_exists=False,
            calibration_required=False,
        )

        assert state == CalibrationState.NOT_REQUIRED


class TestWorkflowSemanticsAreProcedural:
    """Tests ensuring workflow semantics are observational, not advisory."""

    FORBIDDEN_ADVISORY_TERMS = {
        "acceptable",
        "unacceptable",
        "good",
        "bad",
        "correct",
        "incorrect",
        "recommended",
        "quality",
        "grade",
        "verdict",
    }

    def test_execution_states_are_procedural(self):
        """Execution state values should be procedural, not advisory."""
        for state in WorkflowExecutionState:
            state_lower = state.value.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in state_lower, f"State {state.value} contains advisory term '{term}'"

    def test_calibration_states_are_procedural(self):
        """Calibration state values should be procedural, not advisory."""
        for state in CalibrationState:
            state_lower = state.value.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in state_lower, f"State {state.value} contains advisory term '{term}'"

    def test_evidence_dict_has_no_advisory_keys(self):
        """Serialized evidence should contain no advisory keys."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.VALID,
        )
        d = evidence.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, f"Key '{key}' contains advisory term '{term}'"


class TestWorkflowExportCompatibility:
    """Tests for export compatibility."""

    def test_contract_to_dict_excludes_none(self):
        """Contract dict should not include None values for optional fields."""
        d = FREE_PLATE_TAP_V1.to_dict()

        # minimum_coherence is None, should not be in dict
        # (or if present, should not be None)
        if "minimum_coherence" in d:
            assert d["minimum_coherence"] is not None

    def test_evidence_to_dict_excludes_timing_when_none(self):
        """Evidence dict should exclude timing fields when None."""
        evidence = WorkflowExecutionEvidenceV1(
            workflow_id="test",
            repetitions_completed=1,
            execution_state="partial",
            calibration_state="valid",
        )
        d = evidence.to_dict()

        assert "started_at_utc" not in d
        assert "completed_at_utc" not in d
        assert "duration_seconds" not in d

    def test_evidence_includes_timing_when_present(self):
        """Evidence dict should include timing fields when present."""
        evidence = WorkflowExecutionEvidenceV1(
            workflow_id="test",
            repetitions_completed=1,
            execution_state="complete",
            calibration_state="valid",
            started_at_utc="2026-05-01T10:00:00Z",
            completed_at_utc="2026-05-01T10:05:00Z",
            duration_seconds=300.0,
        )
        d = evidence.to_dict()

        assert d["started_at_utc"] == "2026-05-01T10:00:00Z"
        assert d["completed_at_utc"] == "2026-05-01T10:05:00Z"
        assert d["duration_seconds"] == 300.0

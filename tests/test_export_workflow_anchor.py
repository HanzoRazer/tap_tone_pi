# INSTRUMENT CLASS: MEASUREMENT
"""Export anchor test for workflow provenance (Dev Order 86, PR 86F).

Validates that workflow_contract and workflow_execution blocks in viewer pack
exports serialize correctly and contain no advisory semantics.
"""

import json

from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    CalibrationState,
)
from tap_tone_pi.workflow.validation import evaluate_workflow_execution
from tap_tone_pi.workflow.registry import FREE_PLATE_TAP_V1


class TestWorkflowExportAnchor:
    """Validates workflow provenance exports are well-formed and advisory-free."""

    FORBIDDEN_ADVISORY_KEYS = {
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
        "pass",
        "fail",
    }

    def test_contract_dict_is_json_serializable(self):
        """Contract.to_dict() must produce valid JSON."""
        contract = MeasurementWorkflowContractV1(
            workflow_id="test_export_v1",
            display_name="Test Export",
            description="Test workflow for export validation",
            required_repetitions=5,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            min_snr_db=30.0,
            minimum_coherence=0.8,
        )
        d = contract.to_dict()

        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "measurement_workflow_contract_v1"
        assert parsed["workflow_id"] == "test_export_v1"
        assert parsed["minimum_coherence"] == 0.8

    def test_evidence_dict_is_json_serializable(self):
        """Evidence.to_dict() must produce valid JSON."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.VALID,
            started_at_utc="2026-05-29T10:00:00Z",
            completed_at_utc="2026-05-29T10:05:00Z",
        )
        d = evidence.to_dict()

        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "workflow_execution_evidence_v1"
        assert parsed["execution_state"] == "complete"
        assert parsed["workflow_complete"] is True
        assert parsed["duration_seconds"] == 300.0

    def test_contract_keys_are_advisory_free(self):
        """Contract dict keys must not contain advisory terminology."""
        d = FREE_PLATE_TAP_V1.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_KEYS:
                assert term not in key_lower, (
                    f"Contract key '{key}' contains advisory term '{term}'"
                )

    def test_evidence_keys_are_advisory_free(self):
        """Evidence dict keys must not contain advisory terminology."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.VALID,
        )
        d = evidence.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_KEYS:
                assert term not in key_lower, (
                    f"Evidence key '{key}' contains advisory term '{term}'"
                )

    def test_evidence_values_are_observational(self):
        """Evidence string values must be observational, not advisory."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=3,
            calibration_state=CalibrationState.STALE,
        )
        d = evidence.to_dict()

        for key, value in d.items():
            if isinstance(value, str):
                value_lower = value.lower()
                for term in self.FORBIDDEN_ADVISORY_KEYS:
                    assert term not in value_lower, (
                        f"Evidence value '{value}' for key '{key}' contains advisory term '{term}'"
                    )

    def test_epistemic_status_is_derived(self):
        """Workflow evidence epistemic_status must be 'derived'."""
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=5,
            calibration_state=CalibrationState.VALID,
        )

        assert evidence.epistemic_status == "derived"
        assert evidence.to_dict()["epistemic_status"] == "derived"

    def test_schema_versions_are_present(self):
        """Both contract and evidence must include schema_version."""
        contract_dict = FREE_PLATE_TAP_V1.to_dict()
        evidence = evaluate_workflow_execution(
            FREE_PLATE_TAP_V1,
            repetitions_completed=1,
            calibration_state=CalibrationState.VALID,
        )
        evidence_dict = evidence.to_dict()

        assert "schema_version" in contract_dict
        assert "schema_version" in evidence_dict
        assert contract_dict["schema_version"] == "measurement_workflow_contract_v1"
        assert evidence_dict["schema_version"] == "workflow_execution_evidence_v1"

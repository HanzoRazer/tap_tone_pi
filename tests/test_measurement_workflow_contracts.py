# INSTRUMENT CLASS: MEASUREMENT
"""Tests for measurement workflow contracts.

Validates:
- Contract dataclass invariants
- Built-in workflow definitions
- Registry consistency
- Serialization round-trips
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.workflow.contracts import (
    MeasurementWorkflowContractV1,
    FixtureRequirements,
    EnvironmentRequirements,
)
from tap_tone_pi.workflow.registry import (
    BUILTIN_WORKFLOWS,
    get_workflow,
    list_workflow_ids,
    validate_registry,
    FREE_PLATE_TAP_V1,
    BRACED_TOP_TAP_V1,
    CLOSED_BOX_TAP_V1,
    BACK_TAP_V1,
    AIR_RESONANCE_CHECK_V1,
    CALIBRATION_PASS_V1,
)


class TestMeasurementWorkflowContractV1:
    """Tests for MeasurementWorkflowContractV1 dataclass."""

    def test_required_repetitions_must_be_positive(self):
        """required_repetitions must be >= 1."""
        wf = MeasurementWorkflowContractV1(
            workflow_id="test_v1",
            display_name="Test",
            description="Test workflow",
            required_repetitions=0,  # Invalid
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            min_snr_db=30.0,
        )
        errors = wf.validate()
        assert any("required_repetitions" in e for e in errors)

    def test_sample_rate_must_be_valid(self):
        """sample_rate_hz must be >= 8000."""
        wf = MeasurementWorkflowContractV1(
            workflow_id="test_v1",
            display_name="Test",
            description="Test workflow",
            required_repetitions=5,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=4000,  # Invalid
            fft_window="hann",
            min_snr_db=30.0,
        )
        errors = wf.validate()
        assert any("sample_rate_hz" in e for e in errors)

    def test_fft_window_must_be_known(self):
        """fft_window must be hann|hamming|blackman|boxcar."""
        wf = MeasurementWorkflowContractV1(
            workflow_id="test_v1",
            display_name="Test",
            description="Test workflow",
            required_repetitions=5,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="kaiser",  # Invalid
            min_snr_db=30.0,
        )
        errors = wf.validate()
        assert any("fft_window" in e for e in errors)

    def test_fft_size_must_be_power_of_2(self):
        """fft_size must be a power of 2."""
        wf = MeasurementWorkflowContractV1(
            workflow_id="test_v1",
            display_name="Test",
            description="Test workflow",
            required_repetitions=5,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            fft_size=3000,  # Not a power of 2
            min_snr_db=30.0,
        )
        errors = wf.validate()
        assert any("fft_size" in e for e in errors)

    def test_valid_workflow_has_no_errors(self):
        """A valid workflow passes validation."""
        wf = MeasurementWorkflowContractV1(
            workflow_id="valid_v1",
            display_name="Valid Workflow",
            description="A valid test workflow",
            required_repetitions=5,
            max_frequency_variance_pct=3.0,
            sample_rate_hz=48000,
            fft_window="hann",
            fft_size=4096,
            min_snr_db=30.0,
        )
        errors = wf.validate()
        assert errors == []

    def test_to_dict_serialization(self):
        """to_dict produces valid JSON-serializable dict."""
        wf = FREE_PLATE_TAP_V1
        d = wf.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str

        # Key fields present
        assert d["workflow_id"] == "free_plate_tap_v1"
        assert d["schema_version"] == "measurement_workflow_contract_v1"
        assert d["required_repetitions"] == 5
        assert d["sample_rate_hz"] == 48000

    def test_fixture_requirements_to_dict(self):
        """FixtureRequirements.to_dict omits None values."""
        fr = FixtureRequirements(
            support_condition="free",
            mic_position="center",
        )
        d = fr.to_dict()
        assert d["support_condition"] == "free"
        assert d["mic_position"] == "center"
        assert "fixture_id" not in d  # None values omitted
        assert "tap_position" not in d

    def test_environment_requirements_to_dict(self):
        """EnvironmentRequirements.to_dict omits None values."""
        er = EnvironmentRequirements(
            min_temperature_c=18.0,
            max_temperature_c=28.0,
        )
        d = er.to_dict()
        assert d["min_temperature_c"] == 18.0
        assert d["max_temperature_c"] == 28.0
        assert "min_humidity_pct" not in d  # None values omitted


class TestWorkflowRegistry:
    """Tests for workflow registry."""

    def test_registry_has_no_duplicate_ids(self):
        """All workflow IDs must be unique."""
        ids = list(BUILTIN_WORKFLOWS.keys())
        assert len(ids) == len(set(ids)), "Duplicate workflow IDs found"

    def test_registry_key_matches_workflow_id(self):
        """Registry key must match workflow_id."""
        for key, wf in BUILTIN_WORKFLOWS.items():
            assert key == wf.workflow_id, f"Key {key} != workflow_id {wf.workflow_id}"

    def test_all_builtins_pass_validation(self):
        """All built-in workflows must pass validation."""
        errors = validate_registry()
        assert errors == [], f"Registry validation errors: {errors}"

    def test_get_workflow_returns_correct_workflow(self):
        """get_workflow returns the correct workflow by ID."""
        wf = get_workflow("free_plate_tap_v1")
        assert wf is not None
        assert wf.workflow_id == "free_plate_tap_v1"
        assert wf is FREE_PLATE_TAP_V1

    def test_get_workflow_returns_none_for_unknown(self):
        """get_workflow returns None for unknown IDs."""
        wf = get_workflow("nonexistent_v1")
        assert wf is None

    def test_list_workflow_ids_returns_sorted_list(self):
        """list_workflow_ids returns sorted list of all IDs."""
        ids = list_workflow_ids()
        assert ids == sorted(ids)
        assert len(ids) == len(BUILTIN_WORKFLOWS)

    def test_expected_builtins_exist(self):
        """Expected built-in workflows must exist."""
        expected = [
            "free_plate_tap_v1",
            "braced_top_tap_v1",
            "closed_box_tap_v1",
            "back_tap_v1",
            "air_resonance_check_v1",
            "calibration_pass_v1",
        ]
        for wf_id in expected:
            assert wf_id in BUILTIN_WORKFLOWS, f"Missing expected workflow: {wf_id}"


class TestBuiltinWorkflowProperties:
    """Tests for specific properties of built-in workflows."""

    def test_free_plate_requires_calibration(self):
        """Free plate tap requires calibration."""
        assert FREE_PLATE_TAP_V1.requires_calibration is True

    def test_calibration_pass_does_not_require_calibration(self):
        """Calibration pass does not require prior calibration."""
        assert CALIBRATION_PASS_V1.requires_calibration is False

    def test_all_workflows_have_positive_repetitions(self):
        """All workflows require at least 1 repetition."""
        for wf_id, wf in BUILTIN_WORKFLOWS.items():
            assert wf.required_repetitions >= 1, f"{wf_id} has invalid repetitions"

    def test_all_workflows_use_valid_sample_rates(self):
        """All workflows use valid sample rates."""
        valid_rates = {8000, 16000, 22050, 44100, 48000, 96000, 192000}
        for wf_id, wf in BUILTIN_WORKFLOWS.items():
            assert wf.sample_rate_hz in valid_rates, f"{wf_id} has unusual sample rate"

    def test_closed_box_uses_larger_fft(self):
        """Closed box tap uses larger FFT for low-frequency resolution."""
        assert CLOSED_BOX_TAP_V1.fft_size >= 8192

    def test_air_resonance_allows_fewer_repetitions(self):
        """Air resonance check allows fewer repetitions (quick check)."""
        assert AIR_RESONANCE_CHECK_V1.required_repetitions < FREE_PLATE_TAP_V1.required_repetitions

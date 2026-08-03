# INSTRUMENT CLASS: MEASUREMENT
"""Schema-parity / loader-strictness tests for empirical serialization (DO-101A)."""

from __future__ import annotations

import pytest

from tap_tone_pi.empirical import (
    EmpiricalErrorCode,
    ModelInputDefinition,
    ModelOutputDefinition,
    ValidationError,
)
from tap_tone_pi.empirical.serialization import (
    empirical_model_from_dict,
    empirical_model_to_dict,
    formula_validation_envelope_from_dict,
)
from tap_tone_pi.empirical.formula_validation import validate_formula_candidate
from tap_tone_pi.empirical.util import build_model


def _minimal_payload() -> dict:
    model = build_model(
        model_id="free_free_dynamic_modulus",
        version=1,
        title="Free-free dynamic modulus",
        description="Metadata wrapper around an existing free-free E(f) relation.",
        assumptions=("free-free boundary condition",),
        inputs=(ModelInputDefinition(name="frequency_hz", unit="Hz", required=True),),
        outputs=(ModelOutputDefinition(name="young_modulus_gpa", unit="GPa"),),
    )
    return empirical_model_to_dict(model)


class TestEmpiricalSerializationStrictness:
    def test_from_dict_rejects_input_missing_required_flag(self):
        payload = _minimal_payload()
        del payload["inputs"][0]["required"]
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.parametrize(
        "field_name",
        [
            "description",
            "assumptions",
            "inputs",
            "outputs",
            "validity_domain",
            "measurement_links",
            "evidence_references",
            "calibration_history",
        ],
    )
    def test_from_dict_rejects_missing_required_top_level_fields(self, field_name):
        payload = _minimal_payload()
        del payload[field_name]
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.MISSING_REQUIRED_FIELD

    def test_from_dict_rejects_unknown_top_level_property(self):
        payload = _minimal_payload()
        payload["unexpected_field"] = "nope"
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.PAYLOAD_MALFORMED

    def test_from_dict_rejects_unknown_nested_property(self):
        payload = _minimal_payload()
        payload["measurement_links"] = [
            {"link_id": "l1", "role": "source", "extra": 123}
        ]
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.PAYLOAD_MALFORMED

    def test_from_dict_rejects_whitespace_only_model_id(self):
        payload = _minimal_payload()
        payload["model_id"] = "   "
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.MISSING_REQUIRED_FIELD

    def test_from_dict_rejects_bool_for_integer_version(self):
        payload = _minimal_payload()
        payload["version"] = True
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.TYPE_MISMATCH

    def test_from_dict_runs_semantic_validation_by_default(self):
        payload = _minimal_payload()
        payload["title"] = "Best free-free model"
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.ADVISORY_LANGUAGE_FORBIDDEN

    def test_from_dict_can_skip_semantic_validation(self):
        payload = _minimal_payload()
        payload["title"] = "Best free-free model"
        model = empirical_model_from_dict(payload, validate=False)
        assert model.title == "Best free-free model"

    def test_formula_validation_envelope_from_dict_rejects_unknown_schema_version(self):
        payload = validate_formula_candidate(
            validation_id="v1",
            formula_id="f1",
            sample_count=1,
            minimum_sample_count=1,
        ).to_dict()
        payload["schema_version"] = "wrong"
        with pytest.raises(ValidationError) as exc:
            formula_validation_envelope_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.UNKNOWN_SCHEMA_VERSION

    def test_formula_validation_envelope_from_dict_rejects_non_numeric_range(self):
        payload = validate_formula_candidate(
            validation_id="v1",
            formula_id="f1",
            sample_count=1,
            minimum_sample_count=1,
        ).to_dict()
        payload["observed_primary_variable_range"] = [1.0, "x"]
        with pytest.raises(ValidationError) as exc:
            formula_validation_envelope_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.TYPE_MISMATCH

    def test_validate_formula_candidate_rejects_negative_sample_count(self):
        with pytest.raises(ValidationError) as exc:
            validate_formula_candidate(
                validation_id="v1",
                formula_id="f1",
                sample_count=-1,
                minimum_sample_count=0,
            )
        assert exc.value.code == EmpiricalErrorCode.PAYLOAD_MALFORMED

    def test_validate_formula_candidate_rejects_inverted_range(self):
        with pytest.raises(ValidationError) as exc:
            validate_formula_candidate(
                validation_id="v1",
                formula_id="f1",
                sample_count=1,
                minimum_sample_count=1,
                observed_primary_variable_range=(10.0, 1.0),
            )
        assert exc.value.code == EmpiricalErrorCode.INVALID_VALIDITY_DOMAIN

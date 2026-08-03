# INSTRUMENT CLASS: MEASUREMENT
"""Tests for the empirical model framework foundation (DO-101A)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tap_tone_pi.empirical import (
    EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION,
    EmpiricalErrorCode,
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    FormulaValidationEnvelopeV1,
    ModelInputDefinition,
    ModelOutputDefinition,
    UncertaintyReference,
    ValidationError,
    ValidityDomain,
)
from tap_tone_pi.empirical.formula_validation import validate_formula_candidate
from tap_tone_pi.empirical.serialization import (
    empirical_model_from_dict,
    empirical_model_to_dict,
    formula_validation_envelope_from_dict,
)
from tap_tone_pi.empirical.util import build_model, clone_model, normalize_uncertainty
from tap_tone_pi.empirical.validation import validate_model


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "empirical_model_definition_v1.schema.json"
)


def _minimal_model(**overrides) -> EmpiricalModelDefinitionV1:
    kwargs = dict(
        model_id="free_free_dynamic_modulus",
        version=1,
        title="Free-free dynamic modulus",
        description="Metadata wrapper around an existing free-free E(f) relation.",
        assumptions=("free-free boundary condition", "Euler-Bernoulli beam"),
        inputs=(
            ModelInputDefinition(name="frequency_hz", unit="Hz", required=True),
            ModelInputDefinition(name="length_mm", unit="mm", required=True),
        ),
        outputs=(ModelOutputDefinition(name="young_modulus_gpa", unit="GPa"),),
        validity_domain=ValidityDomain(
            primary_variable_name="frequency_hz",
            observed_range=(40.0, 120.0),
            declared_range=(45.0, 100.0),
        ),
        uncertainty=UncertaintyReference(
            uncertainty_model_id="gum_budget_v1",
            uncertainty_summary="Referenced existing GUM budget; not embedded.",
        ),
    )
    kwargs.update(overrides)
    return build_model(**kwargs)


class TestEmpiricalSchemaRegistry:
    def test_schema_is_registered(self):
        registry = json.loads(
            (SCHEMA_PATH.parent / "schema_registry.json").read_text(encoding="utf-8")
        )
        assert "empirical_model_definition" in registry["schemas"]
        assert (
            "empirical_model_definition"
            in registry["owners"]["governance-team"]["schemas"]
        )
        entry = registry["schemas"]["empirical_model_definition"]
        assert entry["schema_version_const"] == "empirical_model_definition_v1"
        assert entry["path"] == "contracts/empirical_model_definition_v1.schema.json"


class TestEmpiricalModelContracts:
    def test_round_trip_serialization(self):
        model = _minimal_model()
        payload = empirical_model_to_dict(model)
        restored = empirical_model_from_dict(payload)
        assert empirical_model_to_dict(restored) == payload
        assert restored.schema_version == EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION
        assert restored.epistemic_status == "derived"

    def test_schema_accepts_serialized_model(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        payload = empirical_model_to_dict(_minimal_model())
        jsonschema.validate(instance=payload, schema=schema)

    def test_from_dict_rejects_unknown_schema_version(self):
        payload = empirical_model_to_dict(_minimal_model())
        payload["schema_version"] = "empirical_model_definition_v0"
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.UNKNOWN_SCHEMA_VERSION

    def test_from_dict_rejects_version_below_one(self):
        payload = empirical_model_to_dict(_minimal_model())
        payload["version"] = 0
        with pytest.raises(ValidationError) as exc:
            empirical_model_from_dict(payload)
        assert exc.value.code == EmpiricalErrorCode.INVALID_VERSION

    def test_validate_rejects_missing_inputs_and_outputs(self):
        model = EmpiricalModelDefinitionV1(
            model_id="x",
            version=1,
            title="Incomplete",
        )
        findings = validate_model(model)
        codes = {f.code for f in findings}
        assert EmpiricalErrorCode.MISSING_INPUTS in codes
        assert EmpiricalErrorCode.MISSING_OUTPUTS in codes

    def test_validate_rejects_duplicate_input_names(self):
        with pytest.raises(ValidationError) as exc:
            build_model(
                model_id="dup",
                version=1,
                title="Dup inputs",
                inputs=(
                    ModelInputDefinition(name="x"),
                    ModelInputDefinition(name="x"),
                ),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        assert exc.value.code == EmpiricalErrorCode.DUPLICATE_INPUT_NAME

    def test_validate_rejects_invalid_validity_domain(self):
        with pytest.raises(ValidationError) as exc:
            build_model(
                model_id="inverted_range",
                version=1,
                title="Inverted observed range",
                inputs=(ModelInputDefinition(name="x"),),
                outputs=(ModelOutputDefinition(name="y"),),
                validity_domain=ValidityDomain(observed_range=(10.0, 1.0)),
            )
        assert exc.value.code == EmpiricalErrorCode.INVALID_VALIDITY_DOMAIN

    def test_validate_rejects_advisory_language(self):
        with pytest.raises(ValidationError) as exc:
            build_model(
                model_id="advisory",
                version=1,
                title="Best free-free model",
                inputs=(ModelInputDefinition(name="x"),),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        assert exc.value.code == EmpiricalErrorCode.ADVISORY_LANGUAGE_FORBIDDEN

    @pytest.mark.parametrize(
        "text",
        [
            "recommended.",
            "best,",
            "optimize:",
            "(good)",
            '"bad"',
        ],
    )
    def test_validate_rejects_advisory_terms_with_punctuation(self, text):
        findings = validate_model(
            EmpiricalModelDefinitionV1(
                model_id="m",
                version=1,
                title="Valid title",
                description=text,
                inputs=(ModelInputDefinition(name="x"),),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        )
        assert any(
            f.code == EmpiricalErrorCode.ADVISORY_LANGUAGE_FORBIDDEN for f in findings
        )

    @pytest.mark.parametrize(
        "text",
        [
            "goodman relation",
            "badge identifier",
            "betterment study",
            "optimization-free reporting",
        ],
    )
    def test_validate_does_not_reject_non_advisory_substrings(self, text):
        findings = validate_model(
            EmpiricalModelDefinitionV1(
                model_id="m",
                version=1,
                title="Valid title",
                description=text,
                inputs=(ModelInputDefinition(name="x"),),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        )
        assert all(
            f.code != EmpiricalErrorCode.ADVISORY_LANGUAGE_FORBIDDEN for f in findings
        )

    def test_validate_rejects_whitespace_only_model_id(self):
        findings = validate_model(
            EmpiricalModelDefinitionV1(
                model_id="   ",
                version=1,
                title="Valid title",
                inputs=(ModelInputDefinition(name="x"),),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        )
        assert any(f.path == "model_id" for f in findings)

    def test_validate_rejects_whitespace_only_input_name(self):
        findings = validate_model(
            EmpiricalModelDefinitionV1(
                model_id="m",
                version=1,
                title="Valid",
                inputs=(ModelInputDefinition(name="   "),),
                outputs=(ModelOutputDefinition(name="y"),),
            )
        )
        assert any(f.path == "inputs[0].name" for f in findings)

    def test_uncertainty_reference_is_not_a_budget(self):
        ref = UncertaintyReference(
            uncertainty_model_id="existing",
            uncertainty_record_id="rec_1",
            uncertainty_summary="summary only",
        )
        assert set(ref.to_dict()) == {
            "uncertainty_model_id",
            "uncertainty_record_id",
            "uncertainty_summary",
        }
        assert (
            normalize_uncertainty(
                UncertaintyReference(
                    uncertainty_model_id="  ",
                    uncertainty_record_id=None,
                    uncertainty_summary="  ",
                )
            )
            is None
        )

    def test_clone_model_preserves_identity_unless_overridden(self):
        model = _minimal_model()
        cloned = clone_model(model, title="Free-free dynamic modulus (copy)")
        assert cloned.model_id == model.model_id
        assert cloned.version == model.version
        assert cloned.title != model.title

    def test_clone_model_revalidates_by_default(self):
        model = _minimal_model()
        with pytest.raises(ValidationError) as exc:
            clone_model(
                model,
                inputs=(
                    ModelInputDefinition(name="x"),
                    ModelInputDefinition(name="x"),
                ),
            )
        assert exc.value.code == EmpiricalErrorCode.DUPLICATE_INPUT_NAME

    def test_clone_model_can_skip_validation(self):
        model = _minimal_model()
        cloned = clone_model(
            model,
            validate=False,
            inputs=(
                ModelInputDefinition(name="x"),
                ModelInputDefinition(name="x"),
            ),
        )
        findings = validate_model(cloned)
        assert any(f.code == EmpiricalErrorCode.DUPLICATE_INPUT_NAME for f in findings)


class TestFormulaValidationEnvelopeMigration:
    def test_envelope_lives_in_empirical_and_serializes(self):
        envelope = validate_formula_candidate(
            validation_id="val_1",
            formula_id="formula_1",
            sample_count=12,
            minimum_sample_count=10,
            observed_primary_variable_range=(2.0, 4.0),
            declared_primary_variable_range=(1.5, 4.0),
        )
        assert isinstance(envelope, FormulaValidationEnvelopeV1)
        payload = envelope.to_dict()
        assert payload["schema_version"] == "formula_validation_envelope_v1"
        assert payload["extrapolation_detected"] is True
        restored = formula_validation_envelope_from_dict(payload)
        assert restored.to_dict() == payload

    def test_envelope_projects_validity_domain(self):
        envelope = validate_formula_candidate(
            validation_id="val_2",
            formula_id="formula_2",
            sample_count=5,
            minimum_sample_count=5,
            observed_primary_variable_range=(0.0, 1.0),
            declared_primary_variable_range=(0.0, 1.0),
        )
        domain = envelope.validity_domain()
        assert domain.observed_range == (0.0, 1.0)
        assert domain.declared_range == (0.0, 1.0)

    def test_evidence_reference_round_trip(self):
        ref = EvidenceReference(
            reference_id="ev_1",
            kind="literature",
            citation="Gore & Gilet",
        )
        assert ref.to_dict()["kind"] == "literature"

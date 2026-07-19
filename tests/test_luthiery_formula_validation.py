# INSTRUMENT CLASS: MEASUREMENT
"""Tests for the luthiery formula validation envelope (Dev Order 95).

Covers FormulaValidationEnvelopeV1, the scalar validate_formula_candidate()
helper, the evidence-object overload, and the additive viewer-pack export
block. Asserts validation output stays measurement-class: no pass/fail,
approval, recommendation, or optimization language.
"""

import json
from pathlib import Path

from scripts.phase2.export_viewer_pack_v1 import _build_manifest
from tap_tone_pi.experiment import (
    create_formula_candidate_evidence,
    fit_linear_cohort_regression,
)
from tap_tone_pi.luthiery import (
    FormulaValidationEnvelopeV1,
    create_luthiery_formula_target,
    validate_formula_candidate,
    validate_formula_candidate_from_evidence,
)
from tap_tone_pi.luthiery.formula_targets import LuthieryFormulaDomain


#: Terms that must never appear in a validation artifact.
FORBIDDEN_TERMS = {
    "approved",
    "rejected",
    "best",
    "optimal",
    "recommended",
    "use_this",
    "valid_formula",
    "invalid_formula",
}


def _envelope(**overrides) -> FormulaValidationEnvelopeV1:
    kwargs = dict(
        validation_id="val_001",
        formula_id="formula_001",
        sample_count=12,
        minimum_sample_count=8,
        process_variance_available=True,
        repeatability_available=True,
        covariates_present=True,
        residual_std_available=True,
        r_squared_available=True,
        observed_primary_variable_range=(2.0, 4.0),
        declared_primary_variable_range=(2.5, 3.5),
    )
    kwargs.update(overrides)
    return validate_formula_candidate(**kwargs)


class TestFormulaValidationEnvelope:
    def test_formula_validation_envelope_serializes(self):
        env = _envelope()
        d = env.to_dict()
        parsed = json.loads(json.dumps(d))

        assert parsed["schema_version"] == "formula_validation_envelope_v1"
        assert parsed["validation_id"] == "val_001"
        assert parsed["formula_id"] == "formula_001"
        assert parsed["sample_count"] == 12
        assert parsed["minimum_sample_count"] == 8
        assert parsed["sample_count_sufficient"] is True
        assert parsed["extrapolation_detected"] is False
        assert parsed["observed_primary_variable_range"] == [2.0, 4.0]
        assert parsed["declared_primary_variable_range"] == [2.5, 3.5]
        assert parsed["epistemic_status"] == "derived"
        assert isinstance(parsed["validation_notes"], list)

    def test_sample_count_sufficiency_true(self):
        env = _envelope(sample_count=10, minimum_sample_count=10)
        assert env.sample_count_sufficient is True
        assert "sample count below declared minimum" not in env.validation_notes

    def test_sample_count_sufficiency_false(self):
        env = _envelope(sample_count=5, minimum_sample_count=8)
        assert env.sample_count_sufficient is False
        assert "sample count below declared minimum" in env.validation_notes

    def test_process_variance_absence_is_recorded(self):
        env = _envelope(process_variance_available=False)
        assert env.process_variance_available is False
        assert "process variance evidence absent" in env.validation_notes

    def test_repeatability_absence_is_recorded(self):
        env = _envelope(repeatability_available=False)
        assert env.repeatability_available is False
        assert "repeatability evidence absent" in env.validation_notes

    def test_covariate_absence_is_recorded(self):
        env = _envelope(covariates_present=False)
        assert env.covariates_present is False
        assert "covariate evidence absent" in env.validation_notes

    def test_extrapolation_detected_when_declared_range_exceeds_observed(self):
        env = _envelope(
            observed_primary_variable_range=(2.0, 4.0),
            declared_primary_variable_range=(1.0, 5.0),
        )
        assert env.extrapolation_detected is True
        assert "declared range extends beyond observed range" in env.validation_notes

    def test_no_extrapolation_when_declared_range_within_observed(self):
        env = _envelope(
            observed_primary_variable_range=(2.0, 4.0),
            declared_primary_variable_range=(2.5, 3.5),
        )
        assert env.extrapolation_detected is False
        assert (
            "declared range extends beyond observed range" not in env.validation_notes
        )

    def test_no_extrapolation_when_range_unknown(self):
        env = _envelope(
            observed_primary_variable_range=None,
            declared_primary_variable_range=(1.0, 5.0),
        )
        assert env.extrapolation_detected is False

    def test_validation_notes_are_measurement_language_only(self):
        # Build a fully-deficient envelope so every note fires.
        env = validate_formula_candidate(
            validation_id="val_x",
            formula_id="formula_x",
            sample_count=2,
            minimum_sample_count=10,
            process_variance_available=False,
            repeatability_available=False,
            covariates_present=False,
            residual_std_available=False,
            r_squared_available=False,
            observed_primary_variable_range=(2.0, 3.0),
            declared_primary_variable_range=(1.0, 5.0),
        )
        blob = json.dumps(env.to_dict()).lower()
        for term in FORBIDDEN_TERMS:
            assert term not in blob, f"forbidden term '{term}' present in artifact"
        # Notes must be present and factual.
        assert len(env.validation_notes) >= 5


class TestValidateFromEvidence:
    def _make_formula(self, with_covariate=True):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]
        covariates = (
            {"density_g_cm3": [0.4, 0.41, 0.42, 0.43, 0.44]} if with_covariate else None
        )
        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="A0_Hz",
            primary_variable_name="thickness_mm",
            response_values=y,
            primary_variable_values=x,
            covariates=covariates,
        )
        return create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

    def test_overload_derives_descriptors_from_evidence(self):
        formula = self._make_formula(with_covariate=True)
        target = create_luthiery_formula_target(
            target_id="target_001",
            domain=LuthieryFormulaDomain.TOP_GRADUATION.value,
            studied_variable_name="thickness_mm",
            response_variable_name="A0_Hz",
        )
        env = validate_formula_candidate_from_evidence(
            validation_id="val_001",
            minimum_sample_count=3,
            formula_candidate=formula,
            target=target,
            process_variance_evidence=object(),
            repeatability_evidence=None,
            observed_primary_variable_range=(1.0, 5.0),
            declared_primary_variable_range=(1.0, 5.0),
        )
        assert env.formula_id == "formula_001"
        assert env.target_id == "target_001"
        assert env.regression_evidence_id == "ev_001"
        assert env.experiment_design_id == "design_001"
        assert env.campaign_id == "campaign_001"
        assert env.sample_count == 5
        assert env.sample_count_sufficient is True
        assert env.covariates_present is True
        assert env.process_variance_available is True
        assert env.repeatability_available is False
        assert "repeatability evidence absent" in env.validation_notes

    def test_overload_records_absent_covariates(self):
        formula = self._make_formula(with_covariate=False)
        env = validate_formula_candidate_from_evidence(
            validation_id="val_002",
            minimum_sample_count=3,
            formula_candidate=formula,
        )
        assert env.covariates_present is False
        assert "covariate evidence absent" in env.validation_notes


class TestFormulaValidationExportIntegration:
    def test_phase2_export_includes_optional_formula_validation_envelope(self):
        env = _envelope()

        manifest = _build_manifest(
            [],
            Path("session_test"),
            [],
            formula_validation_envelope=env.to_dict(),
        )
        assert manifest["formula_validation_envelope"]["validation_id"] == "val_001"

        manifest_bare = _build_manifest([], Path("session_test"), [])
        assert "formula_validation_envelope" not in manifest_bare

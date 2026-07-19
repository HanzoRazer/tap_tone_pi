# INSTRUMENT CLASS: MEASUREMENT
"""Tests for cohort regression evidence contracts (Dev Order 89C).

Tests cover:
- Linear regression coefficient recovery
- Intercept handling
- Covariate support
- Input validation
- Edge cases (zero variance, few samples)
- Formula candidate generation
- Serialization
- Constitutional semantics (no advisory fields)
"""

import json
import pytest

from tap_tone_pi.experiment import (
    RegressionInputV1,
    RegressionCoefficientV1,
    fit_linear_cohort_regression,
    create_formula_candidate_evidence,
)


class TestLinearRegressionBasic:
    """Tests for basic linear regression functionality."""

    def test_linear_regression_recovers_simple_slope(self):
        """Regression should recover known slope from synthetic data."""
        # y = 10 + 2*x (perfect linear relationship)
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="A0_Hz",
            primary_variable_name="thickness_mm",
            response_values=y,
            primary_variable_values=x,
        )

        assert evidence.intercept == pytest.approx(10.0, rel=0.01)

        # Find primary coefficient
        primary_coeff = None
        for c in evidence.coefficients:
            if c.term_name == "thickness_mm":
                primary_coeff = c.coefficient
                break

        assert primary_coeff is not None
        assert primary_coeff == pytest.approx(2.0, rel=0.01)

    def test_linear_regression_includes_intercept(self):
        """Regression should always include intercept coefficient."""
        x = [1.0, 2.0, 3.0, 4.0]
        y = [5.0, 6.0, 7.0, 8.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        intercept_found = False
        for c in evidence.coefficients:
            if c.term_name == "intercept":
                intercept_found = True
                break

        assert intercept_found

    def test_regression_computes_r_squared(self):
        """Regression should compute R² for imperfect fit."""
        # y ≈ 10 + 2*x with some noise
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.5, 13.8, 16.2, 17.9, 20.1]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        assert evidence.r_squared is not None
        assert 0.0 <= evidence.r_squared <= 1.0
        assert evidence.r_squared > 0.9  # Should be high for this data

    def test_regression_computes_adjusted_r_squared(self):
        """Regression should compute adjusted R²."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.5, 13.8, 16.2, 17.9, 20.1]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        assert evidence.adjusted_r_squared is not None
        assert evidence.adjusted_r_squared <= evidence.r_squared

    def test_regression_computes_residual_std(self):
        """Regression should compute residual standard deviation."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.5, 13.8, 16.2, 17.9, 20.1]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        assert evidence.residual_std is not None
        assert evidence.residual_std >= 0

    def test_regression_computes_standard_errors(self):
        """Regression should compute coefficient standard errors."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        y = [12.5, 13.8, 16.2, 17.9, 20.1, 22.3, 24.0, 26.2]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        for coeff in evidence.coefficients:
            assert coeff.standard_error is not None
            assert coeff.standard_error >= 0


class TestRegressionWithCovariates:
    """Tests for regression with covariates."""

    def test_regression_accepts_covariates(self):
        """Regression should accept and use covariates."""
        # y = 10 + 2*x + 3*cov
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        cov = [0.5, 1.0, 1.5, 2.0, 2.5]
        y = [13.5, 17.0, 20.5, 24.0, 27.5]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="primary",
            response_values=y,
            primary_variable_values=x,
            covariates={"covariate": cov},
        )

        assert "covariate" in evidence.covariate_names
        assert len(evidence.coefficients) == 3  # intercept + primary + covariate

    def test_regression_orders_covariates_alphabetically(self):
        """Covariates should be ordered alphabetically."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 12.0, 14.0, 16.0, 18.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="primary",
            response_values=y,
            primary_variable_values=x,
            covariates={
                "zebra": [1.0, 2.0, 3.0, 4.0, 5.0],
                "alpha": [0.5, 1.0, 1.5, 2.0, 2.5],
                "beta": [0.1, 0.2, 0.3, 0.4, 0.5],
            },
        )

        assert evidence.covariate_names == ("alpha", "beta", "zebra")


class TestRegressionValidation:
    """Tests for input validation."""

    def test_regression_rejects_mismatched_lengths(self):
        """Regression should reject mismatched response/predictor lengths."""
        x = [1.0, 2.0, 3.0]
        y = [10.0, 12.0]

        with pytest.raises(ValueError) as exc_info:
            fit_linear_cohort_regression(
                evidence_id="ev_001",
                experiment_design_id="design_001",
                campaign_id="campaign_001",
                response_variable_name="response",
                primary_variable_name="predictor",
                response_values=y,
                primary_variable_values=x,
            )

        assert "Length mismatch" in str(exc_info.value)

    def test_regression_rejects_mismatched_covariate_lengths(self):
        """Regression should reject mismatched covariate lengths."""
        x = [1.0, 2.0, 3.0]
        y = [10.0, 12.0, 14.0]

        with pytest.raises(ValueError) as exc_info:
            fit_linear_cohort_regression(
                evidence_id="ev_001",
                experiment_design_id="design_001",
                campaign_id="campaign_001",
                response_variable_name="response",
                primary_variable_name="predictor",
                response_values=y,
                primary_variable_values=x,
                covariates={"bad_cov": [1.0, 2.0]},
            )

        assert "Length mismatch" in str(exc_info.value)
        assert "bad_cov" in str(exc_info.value)

    def test_regression_rejects_too_few_samples(self):
        """Regression should reject fewer than 2 samples."""
        x = [1.0]
        y = [10.0]

        with pytest.raises(ValueError) as exc_info:
            fit_linear_cohort_regression(
                evidence_id="ev_001",
                experiment_design_id="design_001",
                campaign_id="campaign_001",
                response_variable_name="response",
                primary_variable_name="predictor",
                response_values=y,
                primary_variable_values=x,
            )

        assert "At least 2 samples required" in str(exc_info.value)


class TestZeroVarianceHandling:
    """Tests for zero response variance edge case."""

    def test_regression_handles_zero_response_variance(self):
        """Regression should handle constant response gracefully."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 10.0, 10.0, 10.0, 10.0]  # All same

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        # Should return R² = None (not 0.0, not error)
        assert evidence.r_squared is None
        assert evidence.adjusted_r_squared is None
        # Should still have coefficients (slope should be ~0)
        assert len(evidence.coefficients) >= 2


class TestFormulaCandidateEvidence:
    """Tests for formula candidate generation."""

    def test_formula_candidate_generates_math_notation(self):
        """Formula text should use math notation."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="A0_Hz",
            primary_variable_name="thickness_mm",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        assert "A0_Hz = " in formula.formula_text
        assert "×" in formula.formula_text
        assert "thickness_mm" in formula.formula_text

    def test_formula_candidate_includes_standard_limitations(self):
        """Formula should auto-add standard limitations."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        assert "linear model only" in formula.limitations
        assert "N=5 samples" in formula.limitations

    def test_formula_candidate_adds_zero_variance_limitation(self):
        """Formula should note when R² is undefined."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 10.0, 10.0, 10.0, 10.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        assert "R² undefined: zero response variance" in formula.limitations

    def test_formula_candidate_accepts_additional_limitations(self):
        """Formula should accept additional limitations."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
            additional_limitations=["dreadnought only", "sitka spruce only"],
        )

        assert "dreadnought only" in formula.limitations
        assert "sitka spruce only" in formula.limitations


class TestSerialization:
    """Tests for serialization."""

    def test_regression_evidence_to_dict_round_trips(self):
        """Regression evidence should serialize to dict correctly."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        d = evidence.to_dict()

        assert d["schema_version"] == "cohort_regression_evidence_v1"
        assert d["evidence_id"] == "ev_001"
        assert "coefficients" in d
        assert "r_squared" in d

    def test_regression_evidence_serializes_to_json(self):
        """Regression evidence dict should be JSON-serializable."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        d = evidence.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_formula_candidate_serializes_without_recommendation_language(self):
        """Formula candidate should not contain recommendation language."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        d = formula.to_dict()
        json_str = json.dumps(d)

        # Check for forbidden recommendation language
        forbidden = ["recommend", "optimal", "best", "should", "must"]
        for term in forbidden:
            assert term not in json_str.lower(), (
                f"Formula candidate contains forbidden term '{term}'"
            )


class TestConstitutionalSemantics:
    """Tests ensuring regression output is measurement-class only."""

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
        "winner",
        "should",
        "must",
        "prescription",
    }

    def test_regression_output_is_measurement_class_only(self):
        """Regression evidence should not contain advisory fields."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        d = evidence.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Evidence key '{key}' contains advisory term '{term}'"
                )

    def test_formula_candidate_fields_are_advisory_free(self):
        """Formula candidate should not contain advisory fields."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )

        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        d = formula.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Formula key '{key}' contains advisory term '{term}'"
                )

    def test_all_epistemic_status_are_derived(self):
        """All DO-89C types epistemic_status should be 'derived'."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        regression_input = RegressionInputV1(
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            sample_count=5,
        )
        regression_coeff = RegressionCoefficientV1(
            term_name="predictor",
            coefficient=2.0,
        )
        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )
        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        assert regression_input.epistemic_status == "derived"
        assert regression_coeff.epistemic_status == "derived"
        assert evidence.epistemic_status == "derived"
        assert formula.epistemic_status == "derived"

    def test_schema_versions_are_present(self):
        """All DO-89C types should have schema_version."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        regression_input = RegressionInputV1()
        regression_coeff = RegressionCoefficientV1()
        evidence = fit_linear_cohort_regression(
            evidence_id="ev_001",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            response_variable_name="response",
            primary_variable_name="predictor",
            response_values=y,
            primary_variable_values=x,
        )
        formula = create_formula_candidate_evidence(
            formula_id="formula_001",
            regression_evidence=evidence,
        )

        assert regression_input.schema_version == "regression_input_v1"
        assert regression_coeff.schema_version == "regression_coefficient_v1"
        assert evidence.schema_version == "cohort_regression_evidence_v1"
        assert formula.schema_version == "formula_candidate_evidence_v1"

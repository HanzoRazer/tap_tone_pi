# INSTRUMENT CLASS: MEASUREMENT
"""Export anchor test for cohort regression provenance (Dev Order 89C).

Validates that cohort_regression_evidence and formula_candidate_evidence
blocks in viewer pack exports serialize correctly and contain no advisory
semantics.
"""

import json

from tap_tone_pi.experiment import (
    fit_linear_cohort_regression,
    create_formula_candidate_evidence,
)


class TestCohortRegressionExportAnchor:
    """Validates cohort regression exports are well-formed and advisory-free."""

    FORBIDDEN_ADVISORY_KEYS = {
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
        "prescription",
        "use_this",
    }

    def test_regression_evidence_dict_is_json_serializable(self):
        """Regression evidence to_dict() must produce valid JSON."""
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

        d = evidence.to_dict()
        json_str = json.dumps(d, indent=2)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == "cohort_regression_evidence_v1"

    def test_formula_candidate_dict_is_json_serializable(self):
        """Formula candidate to_dict() must produce valid JSON."""
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

        d = formula.to_dict()
        json_str = json.dumps(d, indent=2)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == "formula_candidate_evidence_v1"

    def test_regression_evidence_keys_are_advisory_free(self):
        """Regression evidence keys must not contain advisory terms."""
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

        d = evidence.to_dict()
        json_str = json.dumps(d)

        for term in self.FORBIDDEN_ADVISORY_KEYS:
            assert term not in json_str.lower(), (
                f"Regression evidence contains forbidden term '{term}'"
            )

    def test_formula_candidate_keys_are_advisory_free(self):
        """Formula candidate keys must not contain advisory terms."""
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

        d = formula.to_dict()
        json_str = json.dumps(d)

        for term in self.FORBIDDEN_ADVISORY_KEYS:
            assert term not in json_str.lower(), (
                f"Formula candidate contains forbidden term '{term}'"
            )

    def test_formula_text_is_descriptive_not_prescriptive(self):
        """Formula text must describe, not prescribe."""
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

        # Should be descriptive equation
        assert "A0_Hz = " in formula.formula_text
        assert "×" in formula.formula_text

        # Should not contain prescriptive language
        prescriptive_terms = ["use", "set", "should", "must", "build", "cut"]
        for term in prescriptive_terms:
            assert term not in formula.formula_text.lower(), (
                f"Formula text contains prescriptive term '{term}'"
            )

    def test_limitations_are_always_present(self):
        """Formula candidate must always include standard limitations."""
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

        assert "linear model only" in formula.limitations
        assert any("N=" in lim and "samples" in lim for lim in formula.limitations)

    def test_export_block_includes_schema_version(self):
        """Export blocks must include schema_version."""
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

        assert evidence.schema_version == "cohort_regression_evidence_v1"
        assert formula.schema_version == "formula_candidate_evidence_v1"

    def test_export_block_includes_epistemic_status(self):
        """Export blocks must include epistemic_status = derived."""
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

        assert evidence.epistemic_status == "derived"
        assert formula.epistemic_status == "derived"

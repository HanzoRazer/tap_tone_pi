# INSTRUMENT CLASS: MEASUREMENT
"""Tests for experiment design contracts (Dev Order 89A).

Tests cover:
- Response variable creation and serialization
- Covariate creation and serialization
- Randomization plan creation
- Baseline rebuild plan creation
- Experiment design creation and composition
- Design validation
- Campaign linkage
- Constitutional semantics (no advisory fields)
"""

import json
import pytest

from tap_tone_pi.experiment import (
    MinimumInterestingEffectV1,
    DeclaredResponseVariableV1,
    CovariateDefinitionV1,
    RandomizationPlanV1,
    BaselineRebuildPlanV1,
    ExperimentDesignV1,
    DesignValidationEvidenceV1,
    create_response_variable,
    create_minimum_interesting_effect,
    create_covariate,
    create_randomization_plan,
    create_baseline_rebuild_plan,
    create_experiment_design,
    validate_experiment_design,
)
from tap_tone_pi.provenance import create_campaign


class TestMinimumInterestingEffect:
    """Tests for MinimumInterestingEffectV1."""

    def test_create_mie_minimal(self):
        """create_minimum_interesting_effect with minimal args should work."""
        mie = create_minimum_interesting_effect(5.0)

        assert mie.value == 5.0
        assert mie.unit == "percent"
        assert mie.description is None

    def test_create_mie_full(self):
        """create_minimum_interesting_effect with all args should work."""
        mie = create_minimum_interesting_effect(
            value=3.0,
            unit="Hz",
            description="3 Hz shift in A0",
        )

        assert mie.value == 3.0
        assert mie.unit == "Hz"
        assert mie.description == "3 Hz shift in A0"

    def test_mie_serializes_to_dict(self):
        """MinimumInterestingEffectV1 should serialize to dict."""
        mie = create_minimum_interesting_effect(5.0, "percent")
        d = mie.to_dict()

        assert d["schema_version"] == "minimum_interesting_effect_v1"
        assert d["value"] == 5.0
        assert d["epistemic_status"] == "derived"


class TestDeclaredResponseVariable:
    """Tests for DeclaredResponseVariableV1."""

    def test_create_response_variable_minimal(self):
        """create_response_variable with minimal args should work."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")

        assert rv.variable_id == "rv_001"
        assert rv.name == "A0 Frequency"
        assert rv.unit == "Hz"

    def test_create_response_variable_with_workflow(self):
        """create_response_variable with workflow linkage should work."""
        rv = create_response_variable(
            "rv_001",
            "A0 Frequency",
            "Hz",
            measurement_workflow_id="a0_workflow_v1",
        )

        assert rv.measurement_workflow_id == "a0_workflow_v1"

    def test_create_response_variable_with_mie(self):
        """create_response_variable with MIE should work."""
        mie = create_minimum_interesting_effect(5.0, "percent")
        rv = create_response_variable(
            "rv_001",
            "A0 Frequency",
            "Hz",
            minimum_interesting_effect=mie,
        )

        assert rv.minimum_interesting_effect is not None
        assert rv.minimum_interesting_effect.value == 5.0

    def test_response_variable_serializes_to_dict(self):
        """DeclaredResponseVariableV1 should serialize to dict."""
        mie = create_minimum_interesting_effect(5.0)
        rv = create_response_variable(
            "rv_001",
            "A0 Frequency",
            "Hz",
            minimum_interesting_effect=mie,
        )
        d = rv.to_dict()

        assert d["schema_version"] == "declared_response_variable_v1"
        assert d["variable_id"] == "rv_001"
        assert "minimum_interesting_effect" in d

    def test_response_variable_serializes_to_json(self):
        """DeclaredResponseVariableV1 dict should be JSON-serializable."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")
        d = rv.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestCovariateDefinition:
    """Tests for CovariateDefinitionV1."""

    def test_create_covariate_minimal(self):
        """create_covariate with minimal args should work."""
        cov = create_covariate("cov_001", "density", "kg/m3")

        assert cov.covariate_id == "cov_001"
        assert cov.name == "density"
        assert cov.unit == "kg/m3"

    def test_create_covariate_with_source(self):
        """create_covariate with source should work."""
        cov = create_covariate(
            "cov_001",
            "longitudinal_moe",
            "GPa",
            source="wood_database",
        )

        assert cov.source == "wood_database"

    def test_covariate_serializes_to_dict(self):
        """CovariateDefinitionV1 should serialize to dict."""
        cov = create_covariate("cov_001", "density", "kg/m3")
        d = cov.to_dict()

        assert d["schema_version"] == "covariate_definition_v1"
        assert d["covariate_id"] == "cov_001"
        assert d["epistemic_status"] == "derived"


class TestRandomizationPlan:
    """Tests for RandomizationPlanV1."""

    def test_create_randomization_plan_minimal(self):
        """create_randomization_plan with minimal args should work."""
        plan = create_randomization_plan("plan_001")

        assert plan.plan_id == "plan_001"
        assert plan.randomization_method == "simple"

    def test_create_randomization_plan_with_seed(self):
        """create_randomization_plan with seed should work."""
        plan = create_randomization_plan(
            "plan_001",
            "blocked",
            seed=42,
            description="Blocked by wood species",
        )

        assert plan.randomization_method == "blocked"
        assert plan.seed == 42
        assert plan.description == "Blocked by wood species"

    def test_randomization_plan_serializes_to_dict(self):
        """RandomizationPlanV1 should serialize to dict."""
        plan = create_randomization_plan("plan_001", seed=42)
        d = plan.to_dict()

        assert d["schema_version"] == "randomization_plan_v1"
        assert d["seed"] == 42


class TestBaselineRebuildPlan:
    """Tests for BaselineRebuildPlanV1."""

    def test_create_baseline_rebuild_plan_minimal(self):
        """create_baseline_rebuild_plan with minimal args should work."""
        plan = create_baseline_rebuild_plan("plan_001", (1, 8, 15, 20))

        assert plan.plan_id == "plan_001"
        assert plan.rebuild_at_build_numbers == (1, 8, 15, 20)

    def test_create_baseline_rebuild_plan_from_list(self):
        """create_baseline_rebuild_plan should accept list."""
        plan = create_baseline_rebuild_plan("plan_001", [1, 8, 15, 20])

        assert plan.rebuild_at_build_numbers == (1, 8, 15, 20)

    def test_create_baseline_rebuild_plan_with_recipe(self):
        """create_baseline_rebuild_plan with recipe ID should work."""
        plan = create_baseline_rebuild_plan(
            "plan_001",
            (1, 8, 15, 20),
            baseline_recipe_id="dreadnought_baseline_v1",
        )

        assert plan.baseline_recipe_id == "dreadnought_baseline_v1"

    def test_baseline_rebuild_plan_serializes_to_dict(self):
        """BaselineRebuildPlanV1 should serialize to dict."""
        plan = create_baseline_rebuild_plan("plan_001", (1, 8, 15))
        d = plan.to_dict()

        assert d["schema_version"] == "baseline_rebuild_plan_v1"
        assert d["rebuild_at_build_numbers"] == [1, 8, 15]


class TestExperimentDesign:
    """Tests for ExperimentDesignV1."""

    def test_create_experiment_design_minimal(self):
        """create_experiment_design with minimal args should work."""
        design = create_experiment_design(
            "design_001",
            "Dreadnought Cohort Study",
            target_cohort_size=20,
        )

        assert design.design_id == "design_001"
        assert design.title == "Dreadnought Cohort Study"
        assert design.target_cohort_size == 20

    def test_create_experiment_design_full(self):
        """create_experiment_design with all args should work."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")
        cov = create_covariate("cov_001", "density", "kg/m3")
        rand_plan = create_randomization_plan("rand_001", "blocked")
        baseline_plan = create_baseline_rebuild_plan("baseline_001", (1, 8, 15, 20))

        design = create_experiment_design(
            "design_001",
            "Dreadnought Cohort Study",
            target_cohort_size=20,
            description="Process variance feasibility study",
            response_variables=[rv],
            covariates=[cov],
            randomization_plan=rand_plan,
            baseline_rebuild_plan=baseline_plan,
            tags=["dreadnought", "cohort", "batch1"],
        )

        assert len(design.response_variables) == 1
        assert len(design.covariates) == 1
        assert design.randomization_plan is not None
        assert design.baseline_rebuild_plan is not None
        assert "dreadnought" in design.tags

    def test_with_response_variable(self):
        """with_response_variable should add to design."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")

        updated = design.with_response_variable(rv)

        assert len(updated.response_variables) == 1
        assert updated.response_variables[0].variable_id == "rv_001"

    def test_with_covariate(self):
        """with_covariate should add to design."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        cov = create_covariate("cov_001", "density", "kg/m3")

        updated = design.with_covariate(cov)

        assert len(updated.covariates) == 1
        assert updated.covariates[0].covariate_id == "cov_001"

    def test_with_randomization_plan(self):
        """with_randomization_plan should attach plan."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        plan = create_randomization_plan("rand_001")

        updated = design.with_randomization_plan(plan)

        assert updated.randomization_plan is not None

    def test_with_baseline_rebuild_plan(self):
        """with_baseline_rebuild_plan should attach plan."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        plan = create_baseline_rebuild_plan("baseline_001", (1, 8, 15))

        updated = design.with_baseline_rebuild_plan(plan)

        assert updated.baseline_rebuild_plan is not None

    def test_experiment_design_serializes_to_dict(self):
        """ExperimentDesignV1 should serialize to dict."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")
        design = create_experiment_design(
            "design_001",
            "Test",
            target_cohort_size=10,
            response_variables=[rv],
        )
        d = design.to_dict()

        assert d["schema_version"] == "experiment_design_v1"
        assert d["design_id"] == "design_001"
        assert len(d["response_variables"]) == 1

    def test_experiment_design_serializes_to_json(self):
        """ExperimentDesignV1 dict should be JSON-serializable."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        d = design.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestDesignValidation:
    """Tests for design validation."""

    def test_validate_complete_design(self):
        """validate_experiment_design should pass for complete design."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")
        cov = create_covariate("cov_001", "density", "kg/m3")
        rand_plan = create_randomization_plan("rand_001")
        baseline_plan = create_baseline_rebuild_plan("baseline_001", (1, 8, 15))

        design = create_experiment_design(
            "design_001",
            "Test",
            target_cohort_size=20,
            response_variables=[rv],
            covariates=[cov],
            randomization_plan=rand_plan,
            baseline_rebuild_plan=baseline_plan,
        )

        evidence = validate_experiment_design(design)

        assert evidence.is_complete is True
        assert evidence.has_response_variables is True
        assert evidence.has_covariates is True
        assert evidence.has_randomization_plan is True
        assert evidence.has_baseline_rebuild_plan is True
        assert evidence.has_cohort_size is True
        assert len(evidence.validation_notes) == 0

    def test_validate_incomplete_design(self):
        """validate_experiment_design should flag missing elements."""
        design = create_experiment_design(
            "design_001",
            "Test",
            target_cohort_size=0,
        )

        evidence = validate_experiment_design(design)

        assert evidence.is_complete is False
        assert evidence.has_response_variables is False
        assert evidence.has_covariates is False
        assert evidence.has_randomization_plan is False
        assert evidence.has_baseline_rebuild_plan is False
        assert evidence.has_cohort_size is False
        assert len(evidence.validation_notes) == 5

    def test_validation_evidence_serializes_to_dict(self):
        """DesignValidationEvidenceV1 should serialize to dict."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        evidence = validate_experiment_design(design)
        d = evidence.to_dict()

        assert d["schema_version"] == "design_validation_evidence_v1"
        assert "has_response_variables" in d


class TestCampaignDesignLinkage:
    """Tests for campaign-to-design linkage."""

    def test_campaign_with_experiment_design(self):
        """Campaign should link to experiment design."""
        campaign = create_campaign("camp_001", "Test Campaign")
        updated = campaign.with_experiment_design("design_001")

        assert updated.experiment_design_id == "design_001"

    def test_campaign_preserves_design_on_mutation(self):
        """Campaign mutations should preserve experiment_design_id."""
        campaign = create_campaign("camp_001", "Test Campaign")
        campaign = campaign.with_experiment_design("design_001")
        campaign = campaign.with_measurement("m001")

        assert campaign.experiment_design_id == "design_001"
        assert "m001" in campaign.measurement_ids

    def test_campaign_serializes_design_id(self):
        """Campaign to_dict should include experiment_design_id."""
        campaign = create_campaign("camp_001", "Test Campaign")
        campaign = campaign.with_experiment_design("design_001")
        d = campaign.to_dict()

        assert d["experiment_design_id"] == "design_001"


class TestConstitutionalSemantics:
    """Tests ensuring experiment design contains no advisory semantics."""

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
        "improved",
    }

    def test_response_variable_fields_are_advisory_free(self):
        """DeclaredResponseVariableV1 should not contain advisory fields."""
        rv = create_response_variable("rv_001", "A0 Frequency", "Hz")
        d = rv.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Response variable key '{key}' contains advisory term '{term}'"
                )

    def test_covariate_fields_are_advisory_free(self):
        """CovariateDefinitionV1 should not contain advisory fields."""
        cov = create_covariate("cov_001", "density", "kg/m3")
        d = cov.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Covariate key '{key}' contains advisory term '{term}'"
                )

    def test_experiment_design_fields_are_advisory_free(self):
        """ExperimentDesignV1 should not contain advisory fields."""
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        d = design.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Design key '{key}' contains advisory term '{term}'"
                )

    def test_all_epistemic_status_are_derived(self):
        """All DO-89A types epistemic_status should be 'derived'."""
        mie = create_minimum_interesting_effect(5.0)
        rv = create_response_variable("rv_001", "A0", "Hz")
        cov = create_covariate("cov_001", "density", "kg/m3")
        rand = create_randomization_plan("rand_001")
        baseline = create_baseline_rebuild_plan("baseline_001", (1, 8))
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        evidence = validate_experiment_design(design)

        assert mie.epistemic_status == "derived"
        assert rv.epistemic_status == "derived"
        assert cov.epistemic_status == "derived"
        assert rand.epistemic_status == "derived"
        assert baseline.epistemic_status == "derived"
        assert design.epistemic_status == "derived"
        assert evidence.epistemic_status == "derived"

    def test_schema_versions_are_present(self):
        """All DO-89A types should have schema_version."""
        mie = create_minimum_interesting_effect(5.0)
        rv = create_response_variable("rv_001", "A0", "Hz")
        cov = create_covariate("cov_001", "density", "kg/m3")
        rand = create_randomization_plan("rand_001")
        baseline = create_baseline_rebuild_plan("baseline_001", (1, 8))
        design = create_experiment_design("design_001", "Test", target_cohort_size=10)
        evidence = validate_experiment_design(design)

        assert mie.schema_version == "minimum_interesting_effect_v1"
        assert rv.schema_version == "declared_response_variable_v1"
        assert cov.schema_version == "covariate_definition_v1"
        assert rand.schema_version == "randomization_plan_v1"
        assert baseline.schema_version == "baseline_rebuild_plan_v1"
        assert design.schema_version == "experiment_design_v1"
        assert evidence.schema_version == "design_validation_evidence_v1"

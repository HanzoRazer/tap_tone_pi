# INSTRUMENT CLASS: MEASUREMENT
"""Tests for cohort execution plan (DO-89D).

Validates:
- CohortExecutionPlanV1 structure and serialization
- create_cohort_execution_plan() aggregation
- render_cohort_execution_plan_markdown() output
- Advisory-free semantics in all outputs
"""

import json
import pytest

from tap_tone_pi.experiment import (
    # DO-89A
    ExperimentDesignV1,
    create_experiment_design,
    create_response_variable,
    create_minimum_interesting_effect,
    create_covariate,
    create_randomization_plan,
    create_baseline_rebuild_plan,
    # DO-89B
    create_reference_body,
    # DO-89D
    CohortExecutionPlanV1,
    ResponseVariableSummaryV1,
    CovariateSummaryV1,
    BaselineScheduleSummaryV1,
    ExecutionChecklistItemV1,
    create_cohort_execution_plan,
    render_cohort_execution_plan_markdown,
)


class TestExecutionPlanDataclasses:
    """Tests for execution plan dataclass structure."""

    def test_cohort_execution_plan_is_frozen(self):
        """CohortExecutionPlanV1 must be immutable."""
        plan = CohortExecutionPlanV1(plan_id="plan_001")
        with pytest.raises(AttributeError):
            plan.plan_id = "modified"

    def test_cohort_execution_plan_has_schema_version(self):
        """CohortExecutionPlanV1 must have schema_version."""
        plan = CohortExecutionPlanV1(plan_id="plan_001")
        assert plan.schema_version == "cohort_execution_plan_v1"

    def test_cohort_execution_plan_has_epistemic_status(self):
        """CohortExecutionPlanV1 must have epistemic_status = derived."""
        plan = CohortExecutionPlanV1(plan_id="plan_001")
        assert plan.epistemic_status == "derived"

    def test_response_variable_summary_to_dict(self):
        """ResponseVariableSummaryV1 must serialize correctly."""
        summary = ResponseVariableSummaryV1(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
            minimum_interesting_effect_value=5.0,
            minimum_interesting_effect_unit="Hz",
        )
        d = summary.to_dict()
        assert d["variable_id"] == "var_001"
        assert d["name"] == "A0_Hz"
        assert d["unit"] == "Hz"
        assert d["minimum_interesting_effect_value"] == 5.0

    def test_covariate_summary_to_dict(self):
        """CovariateSummaryV1 must serialize correctly."""
        summary = CovariateSummaryV1(
            covariate_id="cov_001",
            name="thickness_mm",
            unit="mm",
            source="caliper",
        )
        d = summary.to_dict()
        assert d["covariate_id"] == "cov_001"
        assert d["name"] == "thickness_mm"
        assert d["source"] == "caliper"

    def test_execution_checklist_item_to_dict(self):
        """ExecutionChecklistItemV1 must serialize correctly."""
        item = ExecutionChecklistItemV1(
            step_number=1,
            action="Measure thickness",
            timing="per_specimen",
        )
        d = item.to_dict()
        assert d["step_number"] == 1
        assert d["action"] == "Measure thickness"


class TestCreateCohortExecutionPlan:
    """Tests for create_cohort_execution_plan()."""

    @pytest.fixture
    def sample_experiment_design(self) -> ExperimentDesignV1:
        """Create a sample experiment design for testing."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
            minimum_interesting_effect=create_minimum_interesting_effect(
                value=5.0, unit="Hz"
            ),
        )
        cov1 = create_covariate(
            covariate_id="cov_001",
            name="thickness_mm",
            unit="mm",
            source="caliper",
        )
        cov2 = create_covariate(
            covariate_id="cov_002",
            name="species",
            unit="categorical",
            source="visual_id",
        )
        rand_plan = create_randomization_plan(
            plan_id="rand_001",
            randomization_method="blocked",
        )
        baseline_plan = create_baseline_rebuild_plan(
            plan_id="baseline_001",
            rebuild_at_build_numbers=[1, 8, 15, 20],
            description="Rebuild baseline every 8 builds",
        )
        return create_experiment_design(
            design_id="exp_001",
            title="Dreadnought Cohort Study",
            target_cohort_size=20,
            response_variables=[rv],
            covariates=[cov1, cov2],
            randomization_plan=rand_plan,
            baseline_rebuild_plan=baseline_plan,
        )

    @pytest.fixture
    def sample_reference_body(self):
        """Create a sample reference body for testing."""
        return create_reference_body(
            reference_body_id="ref_001",
            description="Seasoned spruce reference top",
            body_style="dreadnought",
            notes="Repeatability reference",
        )

    def test_creates_plan_with_correct_identity(
        self, sample_experiment_design, sample_reference_body
    ):
        """Plan must have correct identity fields."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
            reference_body=sample_reference_body,
        )
        assert plan.plan_id == "plan_001"
        assert plan.experiment_design_id == "exp_001"
        assert plan.experiment_name == "Dreadnought Cohort Study"

    def test_creates_plan_with_response_variables(self, sample_experiment_design):
        """Plan must include response variable summaries."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert len(plan.response_variables) == 1
        assert plan.response_variables[0].name == "A0_Hz"
        assert plan.response_variables[0].unit == "Hz"

    def test_creates_plan_with_covariates(self, sample_experiment_design):
        """Plan must include covariate summaries."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert len(plan.covariates) == 2
        names = [c.name for c in plan.covariates]
        assert "thickness_mm" in names
        assert "species" in names

    def test_creates_plan_with_baseline_schedule(self, sample_experiment_design):
        """Plan must include baseline schedule summary."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert plan.baseline_schedule is not None
        assert plan.baseline_schedule.plan_id == "baseline_001"
        assert plan.baseline_schedule.rebuild_at_build_numbers == [1, 8, 15, 20]

    def test_creates_plan_with_reference_body(
        self, sample_experiment_design, sample_reference_body
    ):
        """Plan must include reference body summary when provided."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
            reference_body=sample_reference_body,
        )
        assert plan.reference_body is not None
        assert plan.reference_body.reference_body_id == "ref_001"

    def test_creates_plan_without_reference_body(self, sample_experiment_design):
        """Plan must work without reference body."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert plan.reference_body is None

    def test_derives_measurement_workflows(self, sample_experiment_design):
        """Plan must derive measurement workflows from variables."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert len(plan.measurement_workflows) >= 1
        workflow_ids = [w.workflow_id for w in plan.measurement_workflows]
        assert "tap_tone" in workflow_ids

    def test_derives_execution_checklist(
        self, sample_experiment_design, sample_reference_body
    ):
        """Plan must derive execution checklist."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
            reference_body=sample_reference_body,
        )
        assert len(plan.execution_checklist) >= 1
        actions = [item.action for item in plan.execution_checklist]
        assert any("baseline" in a.lower() for a in actions)

    def test_derives_provenance_requirements(self, sample_experiment_design):
        """Plan must derive provenance requirements."""
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=sample_experiment_design,
        )
        assert len(plan.provenance_requirements) >= 1
        artifact_types = [pr.artifact_type for pr in plan.provenance_requirements]
        assert "measurement_session" in artifact_types


class TestRenderCohortExecutionPlanMarkdown:
    """Tests for render_cohort_execution_plan_markdown()."""

    @pytest.fixture
    def sample_plan(self) -> CohortExecutionPlanV1:
        """Create a sample plan for rendering tests."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
            minimum_interesting_effect=create_minimum_interesting_effect(
                value=5.0, unit="Hz"
            ),
        )
        cov = create_covariate(
            covariate_id="cov_001",
            name="thickness_mm",
            unit="mm",
            source="caliper",
        )
        baseline_plan = create_baseline_rebuild_plan(
            plan_id="baseline_001",
            rebuild_at_build_numbers=[1, 8, 15, 20],
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Test Cohort",
            target_cohort_size=20,
            response_variables=[rv],
            covariates=[cov],
            baseline_rebuild_plan=baseline_plan,
        )
        ref_body = create_reference_body(
            reference_body_id="ref_001",
            description="Test reference body",
            body_style="dreadnought",
            notes="Repeatability reference",
        )
        return create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
            reference_body=ref_body,
        )

    def test_renders_markdown_header(self, sample_plan):
        """Rendered Markdown must have header with experiment name."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "# Cohort Execution Plan: Test Cohort" in md

    def test_renders_instrument_class(self, sample_plan):
        """Rendered Markdown must include INSTRUMENT CLASS."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "INSTRUMENT CLASS: MEASUREMENT" in md

    def test_renders_all_nine_sections(self, sample_plan):
        """Rendered Markdown must have all 9 sections."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "## 1. Plan Identity" in md
        assert "## 2. Declared Response Variables" in md
        assert "## 3. Required Covariates" in md
        assert "## 4. Cohort Build Plan" in md
        assert "## 5. Baseline Rebuild Schedule" in md
        assert "## 6. Reference Body / Repeatability Check" in md
        assert "## 7. Required Measurement Workflows" in md
        assert "## 8. Execution Checklist" in md
        assert "## 9. Export / Provenance Requirements" in md

    def test_renders_response_variable_table(self, sample_plan):
        """Rendered Markdown must include response variable table."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "| Variable | Unit | Workflow | MIE |" in md
        assert "A0_Hz" in md

    def test_renders_covariate_table(self, sample_plan):
        """Rendered Markdown must include covariate table."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "| Covariate | Unit | Source |" in md
        assert "thickness_mm" in md

    def test_renders_checklist_table(self, sample_plan):
        """Rendered Markdown must include checklist table."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "| Step | Action | Timing |" in md

    def test_renders_schema_version_footer(self, sample_plan):
        """Rendered Markdown must include schema version footer."""
        md = render_cohort_execution_plan_markdown(sample_plan)
        assert "cohort_execution_plan_v1" in md


class TestExecutionPlanSerialization:
    """Tests for execution plan JSON serialization."""

    @pytest.fixture
    def sample_plan(self) -> CohortExecutionPlanV1:
        """Create a sample plan for serialization tests."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Test Cohort",
            target_cohort_size=10,
            response_variables=[rv],
        )
        return create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )

    def test_to_dict_is_json_serializable(self, sample_plan):
        """to_dict() must produce valid JSON."""
        d = sample_plan.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == "cohort_execution_plan_v1"

    def test_to_dict_includes_all_sections(self, sample_plan):
        """to_dict() must include all plan sections."""
        d = sample_plan.to_dict()
        assert "plan_id" in d
        assert "response_variables" in d
        assert "covariates" in d
        assert "baseline_schedule" in d
        assert "measurement_workflows" in d
        assert "execution_checklist" in d
        assert "provenance_requirements" in d


class TestAdvisoryFreeSemantics:
    """Tests for advisory-free semantics in execution plans."""

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
        "change",
    }

    @pytest.fixture
    def sample_plan(self) -> CohortExecutionPlanV1:
        """Create a sample plan for advisory-free tests."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        cov = create_covariate(
            covariate_id="cov_001",
            name="thickness_mm",
            unit="mm",
            source="caliper",
        )
        baseline_plan = create_baseline_rebuild_plan(
            plan_id="baseline_001",
            rebuild_at_build_numbers=[1, 8, 15, 20],
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Test Cohort",
            target_cohort_size=20,
            response_variables=[rv],
            covariates=[cov],
            baseline_rebuild_plan=baseline_plan,
        )
        ref_body = create_reference_body(
            reference_body_id="ref_001",
            description="Test reference body",
            body_style="dreadnought",
            notes="Repeatability reference",
        )
        return create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
            reference_body=ref_body,
        )

    def test_json_output_is_advisory_free(self, sample_plan):
        """JSON output must not contain advisory terms."""
        d = sample_plan.to_dict()
        json_str = json.dumps(d).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in json_str, (
                f"JSON contains forbidden advisory term '{term}'"
            )

    def test_markdown_output_is_advisory_free(self, sample_plan):
        """Markdown output must not contain advisory terms."""
        md = render_cohort_execution_plan_markdown(sample_plan).lower()
        for term in self.FORBIDDEN_ADVISORY_TERMS:
            assert term not in md, (
                f"Markdown contains forbidden advisory term '{term}'"
            )

    def test_checklist_uses_procedural_language(self, sample_plan):
        """Checklist items must use procedural, not prescriptive language."""
        for item in sample_plan.execution_checklist:
            action_lower = item.action.lower()
            procedural_verbs = ["measure", "record", "perform", "rebuild", "export"]
            has_procedural = any(v in action_lower for v in procedural_verbs)
            assert has_procedural, (
                f"Checklist action '{item.action}' should use procedural language"
            )


class TestExecutionPlanEdgeCases:
    """Tests for edge cases in execution plan creation."""

    def test_handles_no_baseline_plan(self):
        """Plan must handle experiment with no baseline plan."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="No Baseline Study",
            target_cohort_size=5,
            response_variables=[rv],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        assert plan.baseline_schedule is None

    def test_handles_no_covariates(self):
        """Plan must handle experiment with no covariates."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="No Covariate Study",
            target_cohort_size=5,
            response_variables=[rv],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        assert len(plan.covariates) == 0

    def test_handles_multiple_response_variables(self):
        """Plan must handle multiple response variables."""
        rv1 = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        rv2 = create_response_variable(
            variable_id="var_002",
            name="MOE_GPa",
            unit="GPa",
            measurement_workflow_id="bending_rig",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Multi-Response Study",
            target_cohort_size=10,
            response_variables=[rv1, rv2],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        assert len(plan.response_variables) == 2
        assert len(plan.measurement_workflows) >= 2

    def test_markdown_renders_empty_sections_gracefully(self):
        """Markdown must handle empty sections gracefully."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Minimal Study",
            target_cohort_size=5,
            response_variables=[rv],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        md = render_cohort_execution_plan_markdown(plan)
        assert "No baseline rebuild schedule defined" in md
        assert "No reference body defined" in md


class TestWorkflowDerivation:
    """Tests for measurement workflow derivation."""

    def test_unspecified_workflow_handled(self):
        """Variables without workflow_id must show as unspecified."""
        rv = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Unspecified Workflow Study",
            target_cohort_size=5,
            response_variables=[rv],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        workflow_ids = [w.workflow_id for w in plan.measurement_workflows]
        assert "unspecified" in workflow_ids

    def test_multiple_variables_same_workflow(self):
        """Multiple variables with same workflow must be grouped."""
        rv1 = create_response_variable(
            variable_id="var_001",
            name="A0_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        rv2 = create_response_variable(
            variable_id="var_002",
            name="A1_Hz",
            unit="Hz",
            measurement_workflow_id="tap_tone",
        )
        design = create_experiment_design(
            design_id="exp_001",
            title="Grouped Workflow Study",
            target_cohort_size=5,
            response_variables=[rv1, rv2],
        )
        plan = create_cohort_execution_plan(
            plan_id="plan_001",
            experiment_design=design,
        )
        tap_tone_workflows = [
            w for w in plan.measurement_workflows if w.workflow_id == "tap_tone"
        ]
        assert len(tap_tone_workflows) == 1
        assert "A0_Hz" in tap_tone_workflows[0].required_for
        assert "A1_Hz" in tap_tone_workflows[0].required_for

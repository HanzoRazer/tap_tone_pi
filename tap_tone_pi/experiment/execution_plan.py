# INSTRUMENT CLASS: MEASUREMENT
"""Cohort execution plan export and lab manual integration (DO-89D).

Converts experiment design contracts into a usable lab execution packet:
- CohortExecutionPlanV1: structured plan with 9 sections
- create_cohort_execution_plan(): aggregates from input contracts
- render_cohort_execution_plan_markdown(): renders to Markdown

Procedural instructions only. No judgment language. No recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from tap_tone_pi.experiment.experiment_design import ExperimentDesignV1
from tap_tone_pi.experiment.reference_body import ReferenceBodyRecordV1
from tap_tone_pi.experiment.response_variables import DeclaredResponseVariableV1
from tap_tone_pi.experiment.covariates import CovariateDefinitionV1
from tap_tone_pi.experiment.baseline_plan import BaselineRebuildPlanV1


@dataclass(frozen=True)
class ResponseVariableSummaryV1:
    """Summary of a response variable for the execution plan."""

    variable_id: str
    name: str
    unit: str
    measurement_workflow_id: Optional[str]
    minimum_interesting_effect_value: Optional[float]
    minimum_interesting_effect_unit: Optional[str]

    def to_dict(self) -> dict:
        return {
            "variable_id": self.variable_id,
            "name": self.name,
            "unit": self.unit,
            "measurement_workflow_id": self.measurement_workflow_id,
            "minimum_interesting_effect_value": self.minimum_interesting_effect_value,
            "minimum_interesting_effect_unit": self.minimum_interesting_effect_unit,
        }


@dataclass(frozen=True)
class CovariateSummaryV1:
    """Summary of a covariate for the execution plan."""

    covariate_id: str
    name: str
    unit: str
    source: Optional[str]

    def to_dict(self) -> dict:
        return {
            "covariate_id": self.covariate_id,
            "name": self.name,
            "unit": self.unit,
            "source": self.source,
        }


@dataclass(frozen=True)
class BaselineScheduleSummaryV1:
    """Summary of baseline rebuild schedule."""

    plan_id: str
    rebuild_at_build_numbers: List[int]
    description: Optional[str]

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "rebuild_at_build_numbers": list(self.rebuild_at_build_numbers),
            "description": self.description,
        }


@dataclass(frozen=True)
class ReferenceBodySummaryV1:
    """Summary of reference body for repeatability checks."""

    reference_body_id: str
    body_style: str
    description: Optional[str]
    state: str

    def to_dict(self) -> dict:
        return {
            "reference_body_id": self.reference_body_id,
            "body_style": self.body_style,
            "description": self.description,
            "state": self.state,
        }


@dataclass(frozen=True)
class MeasurementWorkflowSummaryV1:
    """Summary of a required measurement workflow."""

    workflow_id: str
    required_for: List[str]  # List of variable names this workflow measures

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "required_for": list(self.required_for),
        }


@dataclass(frozen=True)
class ExecutionChecklistItemV1:
    """Single item in the execution checklist."""

    step_number: int
    action: str
    timing: str  # "per_specimen", "per_build_session", "at_baseline", etc.

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "timing": self.timing,
        }


@dataclass(frozen=True)
class ProvenanceRequirementV1:
    """Export/provenance requirement."""

    artifact_type: str
    format: str
    required_fields: List[str]

    def to_dict(self) -> dict:
        return {
            "artifact_type": self.artifact_type,
            "format": self.format,
            "required_fields": list(self.required_fields),
        }


@dataclass(frozen=True)
class CohortExecutionPlanV1:
    """Complete cohort execution plan with 9 sections.

    Section order:
    1. Plan identity / traceability
    2. Declared response variables
    3. Required covariates
    4. Cohort build plan
    5. Baseline rebuild schedule
    6. Reference body / repeatability check
    7. Required measurement workflows
    8. Execution checklist
    9. Export/provenance requirements
    """

    schema_version: str = field(default="cohort_execution_plan_v1")
    epistemic_status: str = field(default="derived")

    # Section 1: Plan identity / traceability
    plan_id: str = field(default="")
    experiment_design_id: str = field(default="")
    experiment_name: str = field(default="")
    created_utc: str = field(default="")
    plan_version: str = field(default="1")

    # Section 2: Declared response variables
    response_variables: List[ResponseVariableSummaryV1] = field(default_factory=list)

    # Section 3: Required covariates
    covariates: List[CovariateSummaryV1] = field(default_factory=list)

    # Section 4: Cohort build plan
    cohort_size: int = field(default=0)
    randomization_strategy: str = field(default="")
    blocking_variables: List[str] = field(default_factory=list)

    # Section 5: Baseline rebuild schedule
    baseline_schedule: Optional[BaselineScheduleSummaryV1] = field(default=None)

    # Section 6: Reference body / repeatability check
    reference_body: Optional[ReferenceBodySummaryV1] = field(default=None)

    # Section 7: Required measurement workflows
    measurement_workflows: List[MeasurementWorkflowSummaryV1] = field(
        default_factory=list
    )

    # Section 8: Execution checklist
    execution_checklist: List[ExecutionChecklistItemV1] = field(default_factory=list)

    # Section 9: Export/provenance requirements
    provenance_requirements: List[ProvenanceRequirementV1] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "epistemic_status": self.epistemic_status,
            "plan_id": self.plan_id,
            "experiment_design_id": self.experiment_design_id,
            "experiment_name": self.experiment_name,
            "created_utc": self.created_utc,
            "plan_version": self.plan_version,
            "response_variables": [rv.to_dict() for rv in self.response_variables],
            "covariates": [c.to_dict() for c in self.covariates],
            "cohort_size": self.cohort_size,
            "randomization_strategy": self.randomization_strategy,
            "blocking_variables": list(self.blocking_variables),
            "baseline_schedule": (
                self.baseline_schedule.to_dict() if self.baseline_schedule else None
            ),
            "reference_body": (
                self.reference_body.to_dict() if self.reference_body else None
            ),
            "measurement_workflows": [
                mw.to_dict() for mw in self.measurement_workflows
            ],
            "execution_checklist": [ec.to_dict() for ec in self.execution_checklist],
            "provenance_requirements": [
                pr.to_dict() for pr in self.provenance_requirements
            ],
        }


def _derive_measurement_workflows(
    response_variables: List[DeclaredResponseVariableV1],
) -> List[MeasurementWorkflowSummaryV1]:
    """Derive required measurement workflows from response variables."""
    workflow_map: dict[str, set[str]] = {}

    for rv in response_variables:
        workflow_id = rv.measurement_workflow_id or "unspecified"
        if workflow_id not in workflow_map:
            workflow_map[workflow_id] = set()
        workflow_map[workflow_id].add(rv.name)

    workflows = []
    for workflow_id, variables in sorted(workflow_map.items()):
        workflows.append(
            MeasurementWorkflowSummaryV1(
                workflow_id=workflow_id,
                required_for=sorted(variables),
            )
        )

    return workflows


def _derive_execution_checklist(
    response_variables: List[DeclaredResponseVariableV1],
    covariates: List[CovariateDefinitionV1],
    baseline_plan: Optional[BaselineRebuildPlanV1],
    reference_body: Optional[ReferenceBodyRecordV1],
) -> List[ExecutionChecklistItemV1]:
    """Derive execution checklist from plan components."""
    checklist: List[ExecutionChecklistItemV1] = []
    step = 1

    # Baseline measurement at start
    if baseline_plan:
        checklist.append(
            ExecutionChecklistItemV1(
                step_number=step,
                action="Perform baseline measurement on reference body",
                timing="at_cohort_start",
            )
        )
        step += 1

    # Record covariates
    if covariates:
        cov_names = ", ".join(c.name for c in covariates)
        checklist.append(
            ExecutionChecklistItemV1(
                step_number=step,
                action=f"Record covariates: {cov_names}",
                timing="per_specimen",
            )
        )
        step += 1

    # Response variable measurements
    for rv in response_variables:
        workflow = rv.measurement_workflow_id or "standard workflow"
        checklist.append(
            ExecutionChecklistItemV1(
                step_number=step,
                action=f"Measure {rv.name} using {workflow}",
                timing="per_specimen",
            )
        )
        step += 1

    # Reference body repeatability check
    if reference_body:
        checklist.append(
            ExecutionChecklistItemV1(
                step_number=step,
                action="Perform repeatability check on reference body",
                timing="per_baseline_interval",
            )
        )
        step += 1

    # Baseline rebuild
    if baseline_plan and baseline_plan.rebuild_at_build_numbers:
        builds_str = ", ".join(str(b) for b in baseline_plan.rebuild_at_build_numbers)
        checklist.append(
            ExecutionChecklistItemV1(
                step_number=step,
                action=f"Rebuild baseline at builds: {builds_str}",
                timing="at_scheduled_builds",
            )
        )
        step += 1

    # Export provenance
    checklist.append(
        ExecutionChecklistItemV1(
            step_number=step,
            action="Export measurement provenance and artifacts",
            timing="per_specimen",
        )
    )

    return checklist


def _derive_provenance_requirements(
    response_variables: List[DeclaredResponseVariableV1],
    covariates: List[CovariateDefinitionV1],
) -> List[ProvenanceRequirementV1]:
    """Derive provenance requirements from plan components."""
    requirements = [
        ProvenanceRequirementV1(
            artifact_type="measurement_session",
            format="JSON",
            required_fields=[
                "session_id",
                "timestamp_utc",
                "specimen_id",
                "environment_temp_c",
                "environment_rh_pct",
            ],
        ),
    ]

    # Add response variable artifacts
    for rv in response_variables:
        requirements.append(
            ProvenanceRequirementV1(
                artifact_type=f"response_{rv.name}",
                format="JSON",
                required_fields=["value", "unit", "workflow_id", "timestamp_utc"],
            )
        )

    # Add covariate artifacts
    for cov in covariates:
        requirements.append(
            ProvenanceRequirementV1(
                artifact_type=f"covariate_{cov.name}",
                format="JSON",
                required_fields=["value", "unit", "source", "timestamp_utc"],
            )
        )

    return requirements


def create_cohort_execution_plan(
    plan_id: str,
    experiment_design: ExperimentDesignV1,
    reference_body: Optional[ReferenceBodyRecordV1] = None,
    plan_version: str = "1",
) -> CohortExecutionPlanV1:
    """Create a cohort execution plan from experiment design contracts.

    Args:
        plan_id: Unique identifier for this execution plan
        experiment_design: The governing experiment design
        reference_body: Optional reference body for repeatability checks
        plan_version: Version string for this plan iteration

    Returns:
        CohortExecutionPlanV1 with all 9 sections populated
    """
    # Section 2: Response variables
    response_summaries = [
        ResponseVariableSummaryV1(
            variable_id=rv.variable_id,
            name=rv.name,
            unit=rv.unit,
            measurement_workflow_id=rv.measurement_workflow_id,
            minimum_interesting_effect_value=(
                rv.minimum_interesting_effect.value
                if rv.minimum_interesting_effect
                else None
            ),
            minimum_interesting_effect_unit=(
                rv.minimum_interesting_effect.unit
                if rv.minimum_interesting_effect
                else None
            ),
        )
        for rv in experiment_design.response_variables
    ]

    # Section 3: Covariates
    covariate_summaries = [
        CovariateSummaryV1(
            covariate_id=cov.covariate_id,
            name=cov.name,
            unit=cov.unit,
            source=cov.source,
        )
        for cov in experiment_design.covariates
    ]

    # Section 5: Baseline schedule
    baseline_schedule = None
    if experiment_design.baseline_rebuild_plan:
        brp = experiment_design.baseline_rebuild_plan
        baseline_schedule = BaselineScheduleSummaryV1(
            plan_id=brp.plan_id,
            rebuild_at_build_numbers=list(brp.rebuild_at_build_numbers),
            description=brp.description,
        )

    # Section 6: Reference body
    ref_body_summary = None
    if reference_body:
        ref_body_summary = ReferenceBodySummaryV1(
            reference_body_id=reference_body.reference_body_id,
            body_style=reference_body.body_style,
            description=reference_body.description,
            state=reference_body.state,
        )

    # Section 7: Measurement workflows
    workflows = _derive_measurement_workflows(
        list(experiment_design.response_variables),
    )

    # Section 8: Execution checklist
    checklist = _derive_execution_checklist(
        list(experiment_design.response_variables),
        list(experiment_design.covariates),
        experiment_design.baseline_rebuild_plan,
        reference_body,
    )

    # Section 9: Provenance requirements
    provenance_reqs = _derive_provenance_requirements(
        list(experiment_design.response_variables),
        list(experiment_design.covariates),
    )

    return CohortExecutionPlanV1(
        plan_id=plan_id,
        experiment_design_id=experiment_design.design_id,
        experiment_name=experiment_design.title,
        created_utc=datetime.now(timezone.utc).isoformat(),
        plan_version=plan_version,
        response_variables=response_summaries,
        covariates=covariate_summaries,
        cohort_size=experiment_design.target_cohort_size,
        randomization_strategy=experiment_design.randomization_plan.randomization_method
        if experiment_design.randomization_plan
        else "none",
        blocking_variables=[],
        baseline_schedule=baseline_schedule,
        reference_body=ref_body_summary,
        measurement_workflows=workflows,
        execution_checklist=checklist,
        provenance_requirements=provenance_reqs,
    )


def render_cohort_execution_plan_markdown(plan: CohortExecutionPlanV1) -> str:
    """Render a cohort execution plan as Markdown.

    Args:
        plan: The execution plan to render

    Returns:
        Markdown string suitable for lab use
    """
    lines: List[str] = []

    # Header
    lines.append(f"# Cohort Execution Plan: {plan.experiment_name}")
    lines.append("")
    lines.append("**INSTRUMENT CLASS: MEASUREMENT**")
    lines.append("")

    # Section 1: Plan Identity / Traceability
    lines.append("## 1. Plan Identity")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Plan ID | `{plan.plan_id}` |")
    lines.append(f"| Experiment Design ID | `{plan.experiment_design_id}` |")
    lines.append(f"| Plan Version | {plan.plan_version} |")
    lines.append(f"| Created (UTC) | {plan.created_utc} |")
    lines.append(f"| Cohort Size | {plan.cohort_size} |")
    lines.append("")

    # Section 2: Declared Response Variables
    lines.append("## 2. Declared Response Variables")
    lines.append("")
    if plan.response_variables:
        lines.append("| Variable | Unit | Workflow | MIE |")
        lines.append("|----------|------|----------|-----|")
        for rv in plan.response_variables:
            workflow = rv.measurement_workflow_id or "—"
            mie_str = (
                f"{rv.minimum_interesting_effect_value} {rv.minimum_interesting_effect_unit}"
                if rv.minimum_interesting_effect_value is not None
                else "—"
            )
            lines.append(
                f"| {rv.name} | {rv.unit} | {workflow} | {mie_str} |"
            )
        lines.append("")
    else:
        lines.append("No response variables declared.")
        lines.append("")

    # Section 3: Required Covariates
    lines.append("## 3. Required Covariates")
    lines.append("")
    if plan.covariates:
        lines.append("| Covariate | Unit | Source |")
        lines.append("|-----------|------|--------|")
        for cov in plan.covariates:
            source = cov.source or "—"
            lines.append(
                f"| {cov.name} | {cov.unit} | {source} |"
            )
        lines.append("")
    else:
        lines.append("No covariates declared.")
        lines.append("")

    # Section 4: Cohort Build Plan
    lines.append("## 4. Cohort Build Plan")
    lines.append("")
    lines.append(f"- **Cohort size:** {plan.cohort_size}")
    lines.append(f"- **Randomization strategy:** {plan.randomization_strategy}")
    if plan.blocking_variables:
        lines.append(
            f"- **Blocking variables:** {', '.join(plan.blocking_variables)}"
        )
    lines.append("")

    # Section 5: Baseline Rebuild Schedule
    lines.append("## 5. Baseline Rebuild Schedule")
    lines.append("")
    if plan.baseline_schedule:
        lines.append(f"- **Plan ID:** `{plan.baseline_schedule.plan_id}`")
        lines.append(
            f"- **Rebuild at builds:** {', '.join(str(b) for b in plan.baseline_schedule.rebuild_at_build_numbers)}"
        )
        if plan.baseline_schedule.description:
            lines.append(f"- **Description:** {plan.baseline_schedule.description}")
    else:
        lines.append("No baseline rebuild schedule defined.")
    lines.append("")

    # Section 6: Reference Body / Repeatability Check
    lines.append("## 6. Reference Body / Repeatability Check")
    lines.append("")
    if plan.reference_body:
        lines.append(f"- **Reference body ID:** `{plan.reference_body.reference_body_id}`")
        lines.append(f"- **Body style:** {plan.reference_body.body_style}")
        lines.append(f"- **State:** {plan.reference_body.state}")
        if plan.reference_body.description:
            lines.append(f"- **Description:** {plan.reference_body.description}")
    else:
        lines.append("No reference body defined.")
    lines.append("")

    # Section 7: Required Measurement Workflows
    lines.append("## 7. Required Measurement Workflows")
    lines.append("")
    if plan.measurement_workflows:
        lines.append("| Workflow ID | Required For |")
        lines.append("|-------------|--------------|")
        for wf in plan.measurement_workflows:
            lines.append(f"| {wf.workflow_id} | {', '.join(wf.required_for)} |")
        lines.append("")
    else:
        lines.append("No measurement workflows derived.")
        lines.append("")

    # Section 8: Execution Checklist
    lines.append("## 8. Execution Checklist")
    lines.append("")
    if plan.execution_checklist:
        lines.append("| Step | Action | Timing |")
        lines.append("|------|--------|--------|")
        for item in plan.execution_checklist:
            lines.append(
                f"| {item.step_number} | {item.action} | {item.timing} |"
            )
        lines.append("")
    else:
        lines.append("No checklist items.")
        lines.append("")

    # Section 9: Export / Provenance Requirements
    lines.append("## 9. Export / Provenance Requirements")
    lines.append("")
    if plan.provenance_requirements:
        for req in plan.provenance_requirements:
            lines.append(f"### {req.artifact_type}")
            lines.append("")
            lines.append(f"- **Format:** {req.format}")
            lines.append(f"- **Required fields:** {', '.join(req.required_fields)}")
            lines.append("")
    else:
        lines.append("No provenance requirements defined.")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated from schema version: {plan.schema_version}*")

    return "\n".join(lines)

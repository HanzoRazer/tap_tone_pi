# INSTRUMENT CLASS: MEASUREMENT
"""Experiment design contracts for cohort planning (Dev Order 89A).

ExperimentDesignV1 is the governing object that defines what is being
tested, how it is being tested, and what variables matter — before
measurements begin.

This module supports:
- Cohort planning
- Controlled studies
- Response variable declaration
- Covariate declaration
- Randomization planning
- Baseline rebuild schedules

No advisory behavior. No formula generation. No statistical recommendations.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from tap_tone_pi.experiment.response_variables import DeclaredResponseVariableV1
from tap_tone_pi.experiment.covariates import CovariateDefinitionV1
from tap_tone_pi.experiment.randomization import RandomizationPlanV1
from tap_tone_pi.experiment.baseline_plan import BaselineRebuildPlanV1


@dataclass(frozen=True)
class ExperimentDesignV1:
    """A formal experiment design for a cohort study.

    The experiment design is the governing object that sits above
    campaigns in the provenance hierarchy. It declares:
    - What response variables are being measured
    - What covariates are being tracked
    - How randomization is handled
    - When baseline rebuilds occur
    - Target cohort size

    The platform records planned methodology. It does not evaluate
    methodology or recommend design changes.

    Attributes:
        design_id: Unique identifier for this design
        title: Human-readable title
        description: Description of the experiment
        target_cohort_size: Planned number of specimens
        response_variables: Declared response variables
        covariates: Declared covariates
        randomization_plan: Optional randomization methodology
        baseline_rebuild_plan: Optional baseline rebuild schedule
        created_at_utc: ISO 8601 creation timestamp
        tags: Optional metadata tags
    """

    schema_version: str = field(default="experiment_design_v1", init=False)
    design_id: str = ""
    title: str = ""
    description: str | None = None
    target_cohort_size: int = 0
    response_variables: tuple[DeclaredResponseVariableV1, ...] = ()
    covariates: tuple[CovariateDefinitionV1, ...] = ()
    randomization_plan: RandomizationPlanV1 | None = None
    baseline_rebuild_plan: BaselineRebuildPlanV1 | None = None
    created_at_utc: str | None = None
    tags: tuple[str, ...] = ()
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "design_id": self.design_id,
            "title": self.title,
            "target_cohort_size": self.target_cohort_size,
            "response_variables": [rv.to_dict() for rv in self.response_variables],
            "covariates": [cov.to_dict() for cov in self.covariates],
            "epistemic_status": self.epistemic_status,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.randomization_plan is not None:
            d["randomization_plan"] = self.randomization_plan.to_dict()
        if self.baseline_rebuild_plan is not None:
            d["baseline_rebuild_plan"] = self.baseline_rebuild_plan.to_dict()
        if self.created_at_utc is not None:
            d["created_at_utc"] = self.created_at_utc
        if self.tags:
            d["tags"] = list(self.tags)
        return d

    def with_response_variable(
        self, variable: DeclaredResponseVariableV1
    ) -> "ExperimentDesignV1":
        """Return a new design with an additional response variable."""
        return replace(
            self,
            response_variables=self.response_variables + (variable,),
        )

    def with_covariate(self, covariate: CovariateDefinitionV1) -> "ExperimentDesignV1":
        """Return a new design with an additional covariate."""
        return replace(
            self,
            covariates=self.covariates + (covariate,),
        )

    def with_randomization_plan(
        self, plan: RandomizationPlanV1
    ) -> "ExperimentDesignV1":
        """Return a new design with the specified randomization plan."""
        return replace(self, randomization_plan=plan)

    def with_baseline_rebuild_plan(
        self, plan: BaselineRebuildPlanV1
    ) -> "ExperimentDesignV1":
        """Return a new design with the specified baseline rebuild plan."""
        return replace(self, baseline_rebuild_plan=plan)


def create_experiment_design(
    design_id: str,
    title: str,
    target_cohort_size: int,
    *,
    description: str | None = None,
    response_variables: list[DeclaredResponseVariableV1] | None = None,
    covariates: list[CovariateDefinitionV1] | None = None,
    randomization_plan: RandomizationPlanV1 | None = None,
    baseline_rebuild_plan: BaselineRebuildPlanV1 | None = None,
    tags: list[str] | None = None,
    timestamp_utc: str | None = None,
) -> ExperimentDesignV1:
    """Create an experiment design.

    Args:
        design_id: Unique identifier
        title: Human-readable title
        target_cohort_size: Planned number of specimens
        description: Optional description
        response_variables: List of declared response variables
        covariates: List of declared covariates
        randomization_plan: Optional randomization methodology
        baseline_rebuild_plan: Optional baseline rebuild schedule
        tags: Optional metadata tags
        timestamp_utc: Optional ISO 8601 timestamp (defaults to now)

    Returns:
        ExperimentDesignV1 instance
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    return ExperimentDesignV1(
        design_id=design_id,
        title=title,
        description=description,
        target_cohort_size=target_cohort_size,
        response_variables=tuple(response_variables or []),
        covariates=tuple(covariates or []),
        randomization_plan=randomization_plan,
        baseline_rebuild_plan=baseline_rebuild_plan,
        created_at_utc=timestamp_utc,
        tags=tuple(tags or []),
    )

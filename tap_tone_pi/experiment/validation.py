# INSTRUMENT CLASS: MEASUREMENT
"""Design validation evidence contracts for experiment design (Dev Order 89A).

Validation evidence records the completeness/procedural readiness of an
experiment design. This is structural validation, not statistical adequacy.

No advisory semantics. No design recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from tap_tone_pi.experiment.experiment_design import ExperimentDesignV1


@dataclass(frozen=True)
class DesignValidationEvidenceV1:
    """Evidence of experiment design validation.

    Records completeness checks for an experiment design:
    - Has at least one response variable
    - Has declared covariates
    - Has a baseline rebuild plan
    - Has a randomization plan
    - Has a cohort size

    This is procedural readiness, not statistical adequacy.

    Attributes:
        design_id: ID of the validated design
        has_response_variables: At least one response variable declared
        has_covariates: At least one covariate declared
        has_baseline_rebuild_plan: Baseline rebuild plan attached
        has_randomization_plan: Randomization plan attached
        has_cohort_size: Target cohort size > 0
        is_complete: All completeness checks pass
        validation_notes: Optional notes about validation
        validated_at_utc: ISO 8601 validation timestamp
    """

    schema_version: str = field(default="design_validation_evidence_v1", init=False)
    design_id: str = ""
    has_response_variables: bool = False
    has_covariates: bool = False
    has_baseline_rebuild_plan: bool = False
    has_randomization_plan: bool = False
    has_cohort_size: bool = False
    is_complete: bool = False
    validation_notes: tuple[str, ...] = ()
    validated_at_utc: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "design_id": self.design_id,
            "has_response_variables": self.has_response_variables,
            "has_covariates": self.has_covariates,
            "has_baseline_rebuild_plan": self.has_baseline_rebuild_plan,
            "has_randomization_plan": self.has_randomization_plan,
            "has_cohort_size": self.has_cohort_size,
            "is_complete": self.is_complete,
            "epistemic_status": self.epistemic_status,
        }
        if self.validation_notes:
            d["validation_notes"] = list(self.validation_notes)
        if self.validated_at_utc is not None:
            d["validated_at_utc"] = self.validated_at_utc
        return d


def validate_experiment_design(
    design: ExperimentDesignV1,
    *,
    timestamp_utc: str | None = None,
) -> DesignValidationEvidenceV1:
    """Validate an experiment design for completeness.

    Checks procedural readiness, not statistical adequacy.

    Args:
        design: The experiment design to validate
        timestamp_utc: Optional ISO 8601 timestamp (defaults to now)

    Returns:
        DesignValidationEvidenceV1 with validation results
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    notes: list[str] = []

    has_response_variables = len(design.response_variables) > 0
    if not has_response_variables:
        notes.append("No response variables declared")

    has_covariates = len(design.covariates) > 0
    if not has_covariates:
        notes.append("No covariates declared")

    has_baseline_rebuild_plan = design.baseline_rebuild_plan is not None
    if not has_baseline_rebuild_plan:
        notes.append("No baseline rebuild plan attached")

    has_randomization_plan = design.randomization_plan is not None
    if not has_randomization_plan:
        notes.append("No randomization plan attached")

    has_cohort_size = design.target_cohort_size > 0
    if not has_cohort_size:
        notes.append("Target cohort size is zero")

    is_complete = (
        has_response_variables
        and has_covariates
        and has_baseline_rebuild_plan
        and has_randomization_plan
        and has_cohort_size
    )

    return DesignValidationEvidenceV1(
        design_id=design.design_id,
        has_response_variables=has_response_variables,
        has_covariates=has_covariates,
        has_baseline_rebuild_plan=has_baseline_rebuild_plan,
        has_randomization_plan=has_randomization_plan,
        has_cohort_size=has_cohort_size,
        is_complete=is_complete,
        validation_notes=tuple(notes),
        validated_at_utc=timestamp_utc,
    )

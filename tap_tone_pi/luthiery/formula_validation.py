# INSTRUMENT CLASS: MEASUREMENT
"""Formula validation envelope contracts and helpers (Dev Order 95).

This is the error-detection layer around luthiery formula-candidate evidence
(DO-89C / DO-94). It records whether the supporting evidence is structurally
sufficient, reproducible, and bounded.

Detectable conditions (factual only):
- sample count below a declared minimum
- absence of process variance evidence
- absence of repeatability evidence
- absence of covariates
- absence of residual standard deviation / R-squared statistics
- extrapolation: a declared variable range extending beyond the observed range

It records evidence sufficiency only. It is not an authority over formulas:
no pass/fail, no approval, no recommendation, no optimization, no
significance claims, no p-values.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FormulaValidationEnvelopeV1:
    """Error-detection envelope around a formula candidate's evidence.

    Every boolean is a factual statement about the supporting evidence, not a
    judgement of the formula. ``validation_notes`` restate the detected
    conditions in measurement language.

    Attributes:
        validation_id: Unique identifier for this envelope.
        formula_id: The FormulaCandidateEvidenceV1 (DO-89C) formula_id.
        target_id: Optional LuthieryFormulaTargetV1 (DO-94) target_id.
        regression_evidence_id: Optional cohort regression evidence id.
        experiment_design_id: Optional link to an experiment design.
        campaign_id: Optional link to a measurement campaign.
        sample_count: Observed sample count behind the formula.
        minimum_sample_count: Declared minimum sample count.
        sample_count_sufficient: sample_count >= minimum_sample_count.
        process_variance_available: Whether process variance evidence exists.
        repeatability_available: Whether repeatability evidence exists.
        covariates_present: Whether covariates were included.
        residual_std_available: Whether a residual std was computed.
        r_squared_available: Whether an R-squared was computed.
        observed_primary_variable_range: (min, max) of observed primary values.
        declared_primary_variable_range: (min, max) the formula is applied over.
        extrapolation_detected: Whether the declared range exceeds the observed.
        validation_notes: Factual notes for each detected condition.
    """

    schema_version: str = field(default="formula_validation_envelope_v1", init=False)
    validation_id: str = ""
    formula_id: str = ""
    target_id: str | None = None
    regression_evidence_id: str | None = None
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    sample_count: int = 0
    minimum_sample_count: int = 0
    sample_count_sufficient: bool = False
    process_variance_available: bool = False
    repeatability_available: bool = False
    covariates_present: bool = False
    residual_std_available: bool = False
    r_squared_available: bool = False
    observed_primary_variable_range: tuple[float, float] | None = None
    declared_primary_variable_range: tuple[float, float] | None = None
    extrapolation_detected: bool = False
    validation_notes: tuple[str, ...] = ()
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "validation_id": self.validation_id,
            "formula_id": self.formula_id,
            "sample_count": self.sample_count,
            "minimum_sample_count": self.minimum_sample_count,
            "sample_count_sufficient": self.sample_count_sufficient,
            "process_variance_available": self.process_variance_available,
            "repeatability_available": self.repeatability_available,
            "covariates_present": self.covariates_present,
            "residual_std_available": self.residual_std_available,
            "r_squared_available": self.r_squared_available,
            "extrapolation_detected": self.extrapolation_detected,
            "validation_notes": list(self.validation_notes),
            "epistemic_status": self.epistemic_status,
        }
        if self.target_id is not None:
            d["target_id"] = self.target_id
        if self.regression_evidence_id is not None:
            d["regression_evidence_id"] = self.regression_evidence_id
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.observed_primary_variable_range is not None:
            d["observed_primary_variable_range"] = list(
                self.observed_primary_variable_range
            )
        if self.declared_primary_variable_range is not None:
            d["declared_primary_variable_range"] = list(
                self.declared_primary_variable_range
            )
        return d

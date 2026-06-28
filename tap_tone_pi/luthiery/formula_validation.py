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

from tap_tone_pi.experiment.cohort_regression import FormulaCandidateEvidenceV1
from tap_tone_pi.luthiery.formula_targets import LuthieryFormulaTargetV1


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


def _detect_extrapolation(
    observed: tuple[float, float] | None,
    declared: tuple[float, float] | None,
) -> bool:
    """Return True when the declared range extends beyond the observed range.

    Returns False when either range is unknown (the condition cannot be
    assessed) — absence of evidence is recorded separately as a note.
    """
    if observed is None or declared is None:
        return False
    obs_lo, obs_hi = observed
    dec_lo, dec_hi = declared
    return dec_lo < obs_lo or dec_hi > obs_hi


def validate_formula_candidate(
    *,
    validation_id: str,
    formula_id: str,
    sample_count: int,
    minimum_sample_count: int,
    target_id: str | None = None,
    regression_evidence_id: str | None = None,
    experiment_design_id: str | None = None,
    campaign_id: str | None = None,
    process_variance_available: bool = False,
    repeatability_available: bool = False,
    covariates_present: bool = False,
    residual_std_available: bool = False,
    r_squared_available: bool = False,
    observed_primary_variable_range: tuple[float, float] | None = None,
    declared_primary_variable_range: tuple[float, float] | None = None,
) -> FormulaValidationEnvelopeV1:
    """Build a validation envelope from scalar evidence descriptors.

    Computes sample-count sufficiency and extrapolation, then records a factual
    note for every detected condition. Produces evidence only — no approval,
    rejection, grade, or recommendation.

    Args:
        validation_id: Unique identifier for this envelope.
        formula_id: The formula candidate being checked.
        sample_count: Observed sample count.
        minimum_sample_count: Declared minimum sample count.
        target_id: Optional luthiery formula target id.
        regression_evidence_id: Optional regression evidence id.
        experiment_design_id: Optional experiment design id.
        campaign_id: Optional campaign id.
        process_variance_available: Whether process variance evidence exists.
        repeatability_available: Whether repeatability evidence exists.
        covariates_present: Whether covariates were included.
        residual_std_available: Whether a residual std was computed.
        r_squared_available: Whether an R-squared was computed.
        observed_primary_variable_range: (min, max) of observed values.
        declared_primary_variable_range: (min, max) the formula spans.

    Returns:
        A frozen FormulaValidationEnvelopeV1.
    """
    sample_count_sufficient = sample_count >= minimum_sample_count
    extrapolation_detected = _detect_extrapolation(
        observed_primary_variable_range, declared_primary_variable_range
    )

    notes: list[str] = []
    if not sample_count_sufficient:
        notes.append("sample count below declared minimum")
    if not process_variance_available:
        notes.append("process variance evidence absent")
    if not repeatability_available:
        notes.append("repeatability evidence absent")
    if not covariates_present:
        notes.append("covariate evidence absent")
    if not residual_std_available:
        notes.append("residual standard deviation absent")
    if not r_squared_available:
        notes.append("R-squared evidence absent")
    if extrapolation_detected:
        notes.append("declared range extends beyond observed range")

    return FormulaValidationEnvelopeV1(
        validation_id=validation_id,
        formula_id=formula_id,
        target_id=target_id,
        regression_evidence_id=regression_evidence_id,
        experiment_design_id=experiment_design_id,
        campaign_id=campaign_id,
        sample_count=sample_count,
        minimum_sample_count=minimum_sample_count,
        sample_count_sufficient=sample_count_sufficient,
        process_variance_available=process_variance_available,
        repeatability_available=repeatability_available,
        covariates_present=covariates_present,
        residual_std_available=residual_std_available,
        r_squared_available=r_squared_available,
        observed_primary_variable_range=observed_primary_variable_range,
        declared_primary_variable_range=declared_primary_variable_range,
        extrapolation_detected=extrapolation_detected,
        validation_notes=tuple(notes),
    )


def validate_formula_candidate_from_evidence(
    *,
    validation_id: str,
    minimum_sample_count: int,
    formula_candidate: FormulaCandidateEvidenceV1,
    target: LuthieryFormulaTargetV1 | None = None,
    process_variance_evidence: object | None = None,
    repeatability_evidence: object | None = None,
    observed_primary_variable_range: tuple[float, float] | None = None,
    declared_primary_variable_range: tuple[float, float] | None = None,
) -> FormulaValidationEnvelopeV1:
    """Build a validation envelope by deriving descriptors from evidence objects.

    Convenience over :func:`validate_formula_candidate`. The sample count,
    covariate presence, residual std, and R-squared availability are read from
    the formula candidate's embedded regression evidence (DO-89C). Process
    variance (DO-89B) and repeatability (DO-85) availability are inferred from
    whether their evidence objects were supplied. Variable ranges are not stored
    on the evidence objects, so they remain explicit optional arguments.

    Args:
        validation_id: Unique identifier for this envelope.
        minimum_sample_count: Declared minimum sample count.
        formula_candidate: The DO-89C formula candidate to check.
        target: Optional luthiery formula target (supplies target_id).
        process_variance_evidence: DO-89B evidence object, or None if absent.
        repeatability_evidence: DO-85 evidence object, or None if absent.
        observed_primary_variable_range: (min, max) of observed values.
        declared_primary_variable_range: (min, max) the formula spans.

    Returns:
        A frozen FormulaValidationEnvelopeV1.
    """
    reg = formula_candidate.regression_evidence

    sample_count = reg.sample_count if reg is not None else 0
    covariates_present = bool(reg is not None and reg.covariate_names)
    residual_std_available = bool(reg is not None and reg.residual_std is not None)
    r_squared_available = bool(reg is not None and reg.r_squared is not None)
    regression_evidence_id = reg.evidence_id if reg is not None else None

    experiment_design_id = formula_candidate.experiment_design_id or (
        reg.experiment_design_id if reg is not None else None
    )
    campaign_id = formula_candidate.campaign_id or (
        reg.campaign_id if reg is not None else None
    )

    return validate_formula_candidate(
        validation_id=validation_id,
        formula_id=formula_candidate.formula_id,
        sample_count=sample_count,
        minimum_sample_count=minimum_sample_count,
        target_id=target.target_id if target is not None else None,
        regression_evidence_id=regression_evidence_id or None,
        experiment_design_id=experiment_design_id or None,
        campaign_id=campaign_id or None,
        process_variance_available=process_variance_evidence is not None,
        repeatability_available=repeatability_evidence is not None,
        covariates_present=covariates_present,
        residual_std_available=residual_std_available,
        r_squared_available=r_squared_available,
        observed_primary_variable_range=observed_primary_variable_range,
        declared_primary_variable_range=declared_primary_variable_range,
    )

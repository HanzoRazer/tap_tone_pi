# INSTRUMENT CLASS: MEASUREMENT
"""Formula validation envelope contracts and helpers (Dev Order 95).

DO-101A moved the shared envelope type and scalar builder into
``tap_tone_pi.empirical``. This module remains the luthiery import path and
keeps the evidence-object convenience helper that depends on luthiery targets
and DO-89C formula candidates.

Public serialized ``schema_version`` values are unchanged.
"""

from __future__ import annotations

from tap_tone_pi.empirical.contracts import FormulaValidationEnvelopeV1
from tap_tone_pi.empirical.formula_validation import (
    _detect_extrapolation,
    validate_formula_candidate,
)
from tap_tone_pi.experiment.cohort_regression import FormulaCandidateEvidenceV1
from tap_tone_pi.luthiery.formula_targets import LuthieryFormulaTargetV1

__all__ = [
    "FormulaValidationEnvelopeV1",
    "validate_formula_candidate",
    "validate_formula_candidate_from_evidence",
]


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


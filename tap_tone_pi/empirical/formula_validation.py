# INSTRUMENT CLASS: MEASUREMENT
"""Formula validation envelope helpers (DO-95 → DO-101A).

Shared authority for building :class:`FormulaValidationEnvelopeV1`. The
luthiery package re-exports these helpers so existing imports keep working.
"""

from __future__ import annotations

from tap_tone_pi.empirical.contracts import FormulaValidationEnvelopeV1


def detect_extrapolation(
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


# Keep the private name used by historical tests / wrappers.
_detect_extrapolation = detect_extrapolation


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
    """
    sample_count_sufficient = sample_count >= minimum_sample_count
    extrapolation_detected = detect_extrapolation(
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

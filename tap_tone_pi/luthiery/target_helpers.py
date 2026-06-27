# INSTRUMENT CLASS: MEASUREMENT
"""Helpers for constructing luthiery formula targets and evidence links (DO-94).

These helpers build the declarative contracts in ``formula_targets`` with
deterministic, checked inputs. They connect luthiery domain meaning to the
existing DO-89C cohort regression evidence. They do not perform statistics
and do not produce build instructions.
"""

from typing import Sequence

from tap_tone_pi.luthiery.formula_targets import (
    KNOWN_LUTHIERY_FORMULA_DOMAINS,
    LuthieryFormulaEvidenceLinkV1,
    LuthieryFormulaTargetV1,
)


def create_luthiery_formula_target(
    *,
    target_id: str,
    domain: str,
    studied_variable_name: str,
    response_variable_name: str,
    covariate_names: Sequence[str] = (),
    experiment_design_id: str | None = None,
    campaign_id: str | None = None,
    notes: str | None = None,
) -> LuthieryFormulaTargetV1:
    """Create a luthiery formula target with checked, deterministic inputs.

    Args:
        target_id: Unique identifier for this target.
        domain: One of the known LuthieryFormulaDomain values.
        studied_variable_name: The build variable being studied (required).
        response_variable_name: The measured response variable (required).
        covariate_names: Controlled covariates; sorted deterministically.
        experiment_design_id: Optional link to an experiment design.
        campaign_id: Optional link to a measurement campaign.
        notes: Optional descriptive notes.

    Returns:
        A frozen LuthieryFormulaTargetV1.

    Raises:
        ValueError: If the domain is unknown, or if the studied or response
            variable name is empty.
    """
    if domain not in KNOWN_LUTHIERY_FORMULA_DOMAINS:
        raise ValueError(
            f"Unknown luthiery formula domain: {domain!r}. "
            f"Known domains: {sorted(KNOWN_LUTHIERY_FORMULA_DOMAINS)}"
        )

    if not studied_variable_name:
        raise ValueError("studied_variable_name is required")

    if not response_variable_name:
        raise ValueError("response_variable_name is required")

    sorted_covariates = tuple(sorted(covariate_names))

    return LuthieryFormulaTargetV1(
        target_id=target_id,
        domain=domain,
        studied_variable_name=studied_variable_name,
        response_variable_name=response_variable_name,
        covariate_names=sorted_covariates,
        experiment_design_id=experiment_design_id,
        campaign_id=campaign_id,
        notes=notes,
    )


def link_formula_candidate_to_target(
    *,
    link_id: str,
    target: LuthieryFormulaTargetV1,
    formula_id: str,
    regression_evidence_id: str | None = None,
) -> LuthieryFormulaEvidenceLinkV1:
    """Link a formula-candidate evidence object to a luthiery formula target.

    The resulting link inherits the experiment design and campaign IDs from
    the target so lineage is preserved without restating them.

    Args:
        link_id: Unique identifier for this link.
        target: The LuthieryFormulaTargetV1 being linked.
        formula_id: The FormulaCandidateEvidenceV1 (DO-89C) formula_id.
        regression_evidence_id: Optional underlying regression evidence id.

    Returns:
        A frozen LuthieryFormulaEvidenceLinkV1.

    Raises:
        ValueError: If formula_id is empty.
    """
    if not formula_id:
        raise ValueError("formula_id is required")

    return LuthieryFormulaEvidenceLinkV1(
        link_id=link_id,
        target_id=target.target_id,
        formula_id=formula_id,
        regression_evidence_id=regression_evidence_id,
        experiment_design_id=target.experiment_design_id,
        campaign_id=target.campaign_id,
    )

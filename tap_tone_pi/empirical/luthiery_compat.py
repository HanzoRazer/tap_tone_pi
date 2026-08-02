# INSTRUMENT CLASS: MEASUREMENT
"""Compatibility mapping from luthiery formula contracts (DO-101A).

Luthiery remains the domain consumer. These adapters project existing
``LuthieryFormulaTargetV1`` / ``LuthieryFormulaEvidenceLinkV1`` records onto
empirical contracts without changing luthiery serialized output.
"""

from __future__ import annotations

from typing import Any

from tap_tone_pi.empirical.contracts import (
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    MeasurementLink,
    ModelInputDefinition,
    ModelOutputDefinition,
    ValidityDomain,
)
from tap_tone_pi.empirical.errors import EmpiricalErrorCode, ValidationError
from tap_tone_pi.empirical.util import build_model


def empirical_model_from_luthiery_target(
    target: Any,
    *,
    version: int = 1,
    validate: bool = True,
) -> EmpiricalModelDefinitionV1:
    """Project a luthiery formula target onto an empirical model definition.

    Preserves domain meaning as ``domain`` plus an assumption entry. Does not
    alter the target's own ``to_dict()`` serialization.
    """
    try:
        target_id = str(target.target_id)
        domain = str(target.domain)
        studied = str(target.studied_variable_name)
        response = str(target.response_variable_name)
        covariates = tuple(str(name) for name in target.covariate_names)
        experiment_design_id = target.experiment_design_id
        campaign_id = target.campaign_id
        notes = target.notes
    except Exception as exc:  # noqa: BLE001 — narrow to EMP-* contract
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            "luthiery target is missing required attributes",
            {"exception_type": type(exc).__name__},
        ) from None

    inputs = [
        ModelInputDefinition(
            name=studied,
            description="Primary studied variable from luthiery formula target",
            required=True,
            quantity_kind="studied_variable",
        )
    ]
    for name in covariates:
        inputs.append(
            ModelInputDefinition(
                name=name,
                description="Covariate from luthiery formula target",
                required=False,
                quantity_kind="covariate",
            )
        )

    outputs = [
        ModelOutputDefinition(
            name=response,
            description="Response variable from luthiery formula target",
            quantity_kind="response_variable",
        )
    ]

    links: list[MeasurementLink] = []
    if experiment_design_id or campaign_id:
        links.append(
            MeasurementLink(
                link_id=f"link_{target_id}",
                role="luthiery_formula_target",
                experiment_design_id=experiment_design_id,
                campaign_id=campaign_id,
            )
        )

    assumptions = [
        f"luthiery formula domain: {domain}",
        "projected from LuthieryFormulaTargetV1; equation implementation unchanged",
    ]

    return build_model(
        model_id=target_id,
        version=version,
        title=f"{domain}: {studied} → {response}",
        description=(
            "Empirical projection of a luthiery formula target. "
            "Mathematical ownership remains with the existing equation modules."
        ),
        assumptions=assumptions,
        inputs=inputs,
        outputs=outputs,
        validity_domain=ValidityDomain(primary_variable_name=studied),
        measurement_links=links,
        domain=domain,
        notes=notes,
        validate=validate,
    )


def evidence_reference_from_luthiery_link(link: Any) -> EvidenceReference:
    """Project a luthiery evidence link onto a shared EvidenceReference."""
    try:
        return EvidenceReference(
            reference_id=str(link.link_id),
            kind="luthiery_formula_evidence_link",
            formula_id=str(link.formula_id) if link.formula_id else None,
            regression_evidence_id=link.regression_evidence_id,
            notes=(
                f"target_id={link.target_id}"
                if getattr(link, "target_id", None)
                else None
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            "luthiery evidence link is missing required attributes",
            {"exception_type": type(exc).__name__},
        ) from None

# INSTRUMENT CLASS: MEASUREMENT
"""Compatibility mapping from luthiery formula contracts (DO-101A).

Luthiery remains the domain consumer. These adapters project existing
``LuthieryFormulaTargetV1`` / ``LuthieryFormulaEvidenceLinkV1`` records onto
empirical contracts without changing luthiery serialized output.
"""

from __future__ import annotations

from typing import Any, Iterable

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


def _require_nonempty_str(obj: Any, attr: str) -> str:
    if not hasattr(obj, attr):
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery object missing attribute {attr!r}",
            {"attribute": attr},
        )
    value = getattr(obj, attr)
    if not isinstance(value, str) or value.strip() == "":
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery attribute {attr!r} must be a non-empty string",
            {
                "attribute": attr,
                "got_type": type(value).__name__,
            },
        )
    return value.strip()


def _optional_str_attr(obj: Any, attr: str) -> str | None:
    if not hasattr(obj, attr):
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery object missing attribute {attr!r}",
            {"attribute": attr},
        )
    value = getattr(obj, attr)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery attribute {attr!r} must be a string or null",
            {"attribute": attr, "got_type": type(value).__name__},
        )
    stripped = value.strip()
    return stripped or None


def _require_str_sequence(obj: Any, attr: str) -> tuple[str, ...]:
    if not hasattr(obj, attr):
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery object missing attribute {attr!r}",
            {"attribute": attr},
        )
    value = getattr(obj, attr)
    if value is None:
        return ()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            f"luthiery attribute {attr!r} must be a sequence of strings",
            {"attribute": attr, "got_type": type(value).__name__},
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or item.strip() == "":
            raise ValidationError(
                EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
                f"luthiery attribute {attr!r}[{i}] must be a non-empty string",
                {"attribute": attr, "index": i},
            )
        out.append(item.strip())
    return tuple(out)


def empirical_model_from_luthiery_target(
    target: Any,
    *,
    version: int = 1,
    validate: bool = True,
) -> EmpiricalModelDefinitionV1:
    """Project a luthiery formula target onto an empirical model definition.

    Preserves domain meaning as ``domain`` plus an assumption entry. Does not
    alter the target's own ``to_dict()`` serialization. Rejects missing or
    non-string identity fields instead of coercing them with ``str(...)``.
    """
    try:
        target_id = _require_nonempty_str(target, "target_id")
        domain = _require_nonempty_str(target, "domain")
        studied = _require_nonempty_str(target, "studied_variable_name")
        response = _require_nonempty_str(target, "response_variable_name")
        covariates = _require_str_sequence(target, "covariate_names")
        experiment_design_id = _optional_str_attr(target, "experiment_design_id")
        campaign_id = _optional_str_attr(target, "campaign_id")
        notes = _optional_str_attr(target, "notes")
    except ValidationError:
        raise
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
        reference_id = _require_nonempty_str(link, "link_id")
        formula_id = _optional_str_attr(link, "formula_id")
        regression_evidence_id = _optional_str_attr(link, "regression_evidence_id")
        target_id = _optional_str_attr(link, "target_id")
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(
            EmpiricalErrorCode.LUTHIERY_COMPAT_FAILED,
            "luthiery evidence link is missing required attributes",
            {"exception_type": type(exc).__name__},
        ) from None

    return EvidenceReference(
        reference_id=reference_id,
        kind="luthiery_formula_evidence_link",
        formula_id=formula_id,
        regression_evidence_id=regression_evidence_id,
        notes=f"target_id={target_id}" if target_id else None,
    )

# INSTRUMENT CLASS: MEASUREMENT
"""Luthiery formula target contracts (Dev Order 94).

These contracts attach luthiery-specific domain meaning to the generic
cohort-regression evidence produced by DO-89C. A formula *target* declares
*what physical relationship is being studied* — it does NOT tell a builder
what to do.

Allowed (declarative, descriptive):
    "This cohort studies top thickness against A0 frequency with density,
     E_L, E_C, and humidity held as covariates."

Forbidden (advisory, prescriptive):
    build instructions, "this brace height", soundhole/bridge placement,
    "this will sound better".

A formula target is later linked to a FormulaCandidateEvidenceV1 (DO-89C)
via LuthieryFormulaEvidenceLinkV1. The link carries IDs only; it adds no
new statistics and no advisory content.

No optimization. No design selection. No build prescriptions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LuthieryFormulaDomain(str, Enum):
    """The luthiery mechanism a formula target describes.

    These name *what physical relationship is being studied*, not any
    construction decision.
    """

    TOP_GRADUATION = "top_graduation"
    BRACING = "bracing"
    SOUNDHOLE = "soundhole"
    BRIDGE = "bridge"
    BODY_AIR = "body_air"
    PLATE_STIFFNESS = "plate_stiffness"


#: Set of known domain string values, for membership checks.
KNOWN_LUTHIERY_FORMULA_DOMAINS: frozenset[str] = frozenset(
    d.value for d in LuthieryFormulaDomain
)


@dataclass(frozen=True)
class LuthieryFormulaTargetV1:
    """Declares which luthiery relationship a formula is trying to model.

    This is a *target*, not evidence. It describes the studied variable, the
    response variable, and the controlled covariates for a cohort study. It
    does not contain coefficients, fit statistics, or recommendations.

    Attributes:
        target_id: Unique identifier for this target.
        domain: One of the LuthieryFormulaDomain values.
        studied_variable_name: The build variable being varied/studied.
        response_variable_name: The measured acoustic/mechanical response.
        covariate_names: Controlled covariates (sorted for determinism).
        experiment_design_id: Optional link to an experiment design.
        campaign_id: Optional link to a measurement campaign.
        notes: Optional descriptive notes (must stay non-advisory).
    """

    schema_version: str = field(default="luthiery_formula_target_v1", init=False)
    target_id: str = ""
    domain: str = ""
    studied_variable_name: str = ""
    response_variable_name: str = ""
    covariate_names: tuple[str, ...] = ()
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    notes: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "target_id": self.target_id,
            "domain": self.domain,
            "studied_variable_name": self.studied_variable_name,
            "response_variable_name": self.response_variable_name,
            "covariate_names": list(self.covariate_names),
            "epistemic_status": self.epistemic_status,
        }
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class LuthieryFormulaEvidenceLinkV1:
    """Links a formula-candidate evidence object to a luthiery formula target.

    The link carries identifiers only. It adds no statistics and no advisory
    content; it records that a given formula candidate is evidence for a given
    luthiery formula target.

    Attributes:
        link_id: Unique identifier for this link.
        target_id: The LuthieryFormulaTargetV1 being linked.
        formula_id: The FormulaCandidateEvidenceV1 (DO-89C) formula_id.
        regression_evidence_id: Optional underlying regression evidence id.
        experiment_design_id: Optional link to an experiment design.
        campaign_id: Optional link to a measurement campaign.
    """

    schema_version: str = field(default="luthiery_formula_evidence_link_v1", init=False)
    link_id: str = ""
    target_id: str = ""
    formula_id: str = ""
    regression_evidence_id: str | None = None
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "link_id": self.link_id,
            "target_id": self.target_id,
            "formula_id": self.formula_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.regression_evidence_id is not None:
            d["regression_evidence_id"] = self.regression_evidence_id
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        return d

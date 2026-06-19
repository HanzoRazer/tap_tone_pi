# INSTRUMENT CLASS: MEASUREMENT
"""Covariate definition contracts for experiment design (Dev Order 89A).

Covariates are variables that may influence the response but are not
the primary focus of the experiment. This module provides declarative
contracts for specifying what covariates are being tracked.

No advisory semantics. No importance ranking. No statistical recommendations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CovariateDefinitionV1:
    """A declared covariate for an experiment design.

    Covariates are variables tracked alongside response variables.
    They may be used in future regression analysis but the platform
    does not determine their importance or recommend covariates.

    Attributes:
        covariate_id: Unique identifier for this covariate
        name: Human-readable name (e.g., "density", "longitudinal_moe")
        unit: Unit of measurement (e.g., "kg/m3", "GPa")
        source: Where this covariate comes from (e.g., "wood_database", "measured")
        description: Optional description of the covariate
    """

    schema_version: str = field(default="covariate_definition_v1", init=False)
    covariate_id: str = ""
    name: str = ""
    unit: str = ""
    source: str | None = None
    description: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "covariate_id": self.covariate_id,
            "name": self.name,
            "unit": self.unit,
            "epistemic_status": self.epistemic_status,
        }
        if self.source is not None:
            d["source"] = self.source
        if self.description is not None:
            d["description"] = self.description
        return d


def create_covariate(
    covariate_id: str,
    name: str,
    unit: str,
    *,
    source: str | None = None,
    description: str | None = None,
) -> CovariateDefinitionV1:
    """Create a covariate definition.

    Args:
        covariate_id: Unique identifier
        name: Human-readable name
        unit: Unit of measurement
        source: Where this covariate comes from
        description: Optional description

    Returns:
        CovariateDefinitionV1 instance
    """
    return CovariateDefinitionV1(
        covariate_id=covariate_id,
        name=name,
        unit=unit,
        source=source,
        description=description,
    )

# INSTRUMENT CLASS: MEASUREMENT
"""Declared response variable contracts for experiment design (Dev Order 89A).

Response variables are the outcomes being measured in an experiment.
This module provides declarative contracts for specifying what is being
measured, not how to interpret the results.

No advisory semantics. No statistical recommendations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MinimumInterestingEffectV1:
    """Minimum effect size considered meaningful for a response variable.

    This is an informational declaration, not a statistical threshold.
    The platform records it; it does not determine significance.

    Attributes:
        value: The minimum effect magnitude (e.g., 5.0 for 5% shift)
        unit: The unit of the effect (e.g., "percent", "Hz", "ratio")
        description: Optional human-readable description
    """

    schema_version: str = field(default="minimum_interesting_effect_v1", init=False)
    value: float = 0.0
    unit: str = "percent"
    description: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "value": self.value,
            "unit": self.unit,
            "epistemic_status": self.epistemic_status,
        }
        if self.description is not None:
            d["description"] = self.description
        return d


@dataclass(frozen=True)
class DeclaredResponseVariableV1:
    """A declared response variable for an experiment design.

    Response variables are the outcomes being measured. This contract
    stores names, units, and optional workflow linkage only.

    The platform records the declaration. It does not evaluate
    the choice of response variable or recommend alternatives.

    Attributes:
        variable_id: Unique identifier for this variable declaration
        name: Human-readable name (e.g., "A0 Frequency", "Monopole Mobility")
        unit: Unit of measurement (e.g., "Hz", "mm/s/N")
        measurement_workflow_id: Optional link to workflow that produces this
        minimum_interesting_effect: Optional MIE declaration
        description: Optional description of what this variable represents
    """

    schema_version: str = field(default="declared_response_variable_v1", init=False)
    variable_id: str = ""
    name: str = ""
    unit: str = ""
    measurement_workflow_id: str | None = None
    minimum_interesting_effect: MinimumInterestingEffectV1 | None = None
    description: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "variable_id": self.variable_id,
            "name": self.name,
            "unit": self.unit,
            "epistemic_status": self.epistemic_status,
        }
        if self.measurement_workflow_id is not None:
            d["measurement_workflow_id"] = self.measurement_workflow_id
        if self.minimum_interesting_effect is not None:
            d["minimum_interesting_effect"] = self.minimum_interesting_effect.to_dict()
        if self.description is not None:
            d["description"] = self.description
        return d


def create_response_variable(
    variable_id: str,
    name: str,
    unit: str,
    *,
    measurement_workflow_id: str | None = None,
    minimum_interesting_effect: MinimumInterestingEffectV1 | None = None,
    description: str | None = None,
) -> DeclaredResponseVariableV1:
    """Create a declared response variable.

    Args:
        variable_id: Unique identifier
        name: Human-readable name
        unit: Unit of measurement
        measurement_workflow_id: Optional workflow that produces this
        minimum_interesting_effect: Optional MIE declaration
        description: Optional description

    Returns:
        DeclaredResponseVariableV1 instance
    """
    return DeclaredResponseVariableV1(
        variable_id=variable_id,
        name=name,
        unit=unit,
        measurement_workflow_id=measurement_workflow_id,
        minimum_interesting_effect=minimum_interesting_effect,
        description=description,
    )


def create_minimum_interesting_effect(
    value: float,
    unit: str = "percent",
    description: str | None = None,
) -> MinimumInterestingEffectV1:
    """Create a minimum interesting effect declaration.

    Args:
        value: The minimum effect magnitude
        unit: The unit of the effect
        description: Optional description

    Returns:
        MinimumInterestingEffectV1 instance
    """
    return MinimumInterestingEffectV1(
        value=value,
        unit=unit,
        description=description,
    )

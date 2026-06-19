# INSTRUMENT CLASS: MEASUREMENT
"""Randomization plan contracts for experiment design (Dev Order 89A).

Randomization plans describe how experimental units are assigned to
conditions. This module provides declarative contracts for recording
randomization methodology.

No advisory semantics. No randomization recommendations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RandomizationPlanV1:
    """A randomization plan for an experiment design.

    Records the methodology used for randomizing experimental units.
    The platform stores the plan; it does not evaluate or recommend
    randomization strategies.

    Attributes:
        plan_id: Unique identifier for this plan
        randomization_method: Method used (e.g., "simple", "blocked", "stratified")
        seed: Optional random seed for reproducibility
        description: Optional description of the randomization approach
    """

    schema_version: str = field(default="randomization_plan_v1", init=False)
    plan_id: str = ""
    randomization_method: str = "simple"
    seed: int | None = None
    description: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "randomization_method": self.randomization_method,
            "epistemic_status": self.epistemic_status,
        }
        if self.seed is not None:
            d["seed"] = self.seed
        if self.description is not None:
            d["description"] = self.description
        return d


def create_randomization_plan(
    plan_id: str,
    randomization_method: str = "simple",
    *,
    seed: int | None = None,
    description: str | None = None,
) -> RandomizationPlanV1:
    """Create a randomization plan.

    Args:
        plan_id: Unique identifier
        randomization_method: Method used (e.g., "simple", "blocked", "stratified")
        seed: Optional random seed
        description: Optional description

    Returns:
        RandomizationPlanV1 instance
    """
    return RandomizationPlanV1(
        plan_id=plan_id,
        randomization_method=randomization_method,
        seed=seed,
        description=description,
    )

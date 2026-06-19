# INSTRUMENT CLASS: MEASUREMENT
"""Baseline rebuild plan contracts for experiment design (Dev Order 89A).

Baseline rebuild plans specify when reference/control specimens are
rebuilt during a cohort study. This enables σ_build estimation over time.

No advisory semantics. No schedule recommendations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BaselineRebuildPlanV1:
    """A baseline rebuild plan for an experiment design.

    Specifies at which build numbers the baseline/control recipe
    should be rebuilt. This enables tracking of builder skill drift
    and process variance decomposition (σ_measurement vs σ_build).

    Attributes:
        plan_id: Unique identifier for this plan
        rebuild_at_build_numbers: Build numbers at which to rebuild baseline
        baseline_recipe_id: Identifier for the frozen baseline recipe
        description: Optional description of the rebuild rationale
    """

    schema_version: str = field(default="baseline_rebuild_plan_v1", init=False)
    plan_id: str = ""
    rebuild_at_build_numbers: tuple[int, ...] = ()
    baseline_recipe_id: str | None = None
    description: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "rebuild_at_build_numbers": list(self.rebuild_at_build_numbers),
            "epistemic_status": self.epistemic_status,
        }
        if self.baseline_recipe_id is not None:
            d["baseline_recipe_id"] = self.baseline_recipe_id
        if self.description is not None:
            d["description"] = self.description
        return d


def create_baseline_rebuild_plan(
    plan_id: str,
    rebuild_at_build_numbers: tuple[int, ...] | list[int],
    *,
    baseline_recipe_id: str | None = None,
    description: str | None = None,
) -> BaselineRebuildPlanV1:
    """Create a baseline rebuild plan.

    Args:
        plan_id: Unique identifier
        rebuild_at_build_numbers: Build numbers for baseline rebuilds
        baseline_recipe_id: Identifier for the frozen baseline recipe
        description: Optional description

    Returns:
        BaselineRebuildPlanV1 instance
    """
    if isinstance(rebuild_at_build_numbers, list):
        rebuild_at_build_numbers = tuple(rebuild_at_build_numbers)

    return BaselineRebuildPlanV1(
        plan_id=plan_id,
        rebuild_at_build_numbers=rebuild_at_build_numbers,
        baseline_recipe_id=baseline_recipe_id,
        description=description,
    )

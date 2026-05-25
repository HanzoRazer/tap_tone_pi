# INSTRUMENT CLASS: MEASUREMENT
"""
Formatting utilities for uncertainty reporting.
"""

from __future__ import annotations

import math
from typing import Dict, Any

from .budget import UncertaintyBudget


def format_with_uncertainty(
    value: float,
    uncertainty: float,
    unit: str = "",
    significant_figures: int = 2,
    show_relative: bool = False,
) -> str:
    """
    Format a value with its uncertainty.

    Args:
        value: Measured value
        uncertainty: Expanded uncertainty (±)
        unit: Unit string
        significant_figures: Number of significant figures for uncertainty
        show_relative: Also show relative uncertainty

    Returns:
        Formatted string like "440.0 ± 1.2 Hz"
    """
    if uncertainty == 0 or math.isinf(uncertainty) or math.isnan(uncertainty):
        return f"{value:.4g} {unit}".strip()

    # Determine decimal places from uncertainty
    if uncertainty >= 1:
        unc_decimals = max(0, significant_figures - int(math.log10(uncertainty)) - 1)
    else:
        unc_decimals = (
            significant_figures - int(math.floor(math.log10(uncertainty))) - 1
        )

    unc_decimals = max(0, min(unc_decimals, 6))

    # Format both to same decimal places
    value_str = f"{value:.{unc_decimals}f}"
    unc_str = f"{uncertainty:.{unc_decimals}f}"

    result = f"{value_str} ± {unc_str}"

    if unit:
        result += f" {unit}"

    if show_relative and value != 0:
        rel_percent = (uncertainty / abs(value)) * 100
        result += f" ({rel_percent:.1f}%)"

    return result


def format_uncertainty_budget(
    budget: UncertaintyBudget,
    show_components: bool = True,
    indent: str = "  ",
) -> str:
    """
    Format a complete uncertainty budget as human-readable text.

    Args:
        budget: UncertaintyBudget to format
        show_components: Whether to show individual components
        indent: Indentation string for components

    Returns:
        Multi-line formatted string
    """
    lines = []

    # Header with result
    if budget.measurement_value is not None:
        result_str = format_with_uncertainty(
            budget.measurement_value,
            budget.expanded_uncertainty,
            budget.measurement_unit,
            show_relative=True,
        )
        lines.append(f"Result: {result_str}")
    else:
        lines.append(
            f"Expanded uncertainty: ± {budget.expanded_uncertainty:.4g} {budget.measurement_unit}"
        )

    lines.append(f"Coverage factor: k = {budget.coverage_factor}")

    # Components breakdown
    if show_components and budget.components:
        lines.append("")
        lines.append("Uncertainty components:")

        # Sort by contribution (largest first)
        sorted_components = sorted(
            budget.components, key=lambda c: c.contribution, reverse=True
        )

        for c in sorted_components:
            contribution_pct = (
                c.contribution / (budget.combined_standard_uncertainty**2) * 100
                if budget.combined_standard_uncertainty > 0
                else 0
            )

            line = f"{indent}{c.name}: ± {c.value:.4g} {c.unit}"
            if contribution_pct >= 1:
                line += f" ({contribution_pct:.1f}%)"

            lines.append(line)

            if c.description:
                lines.append(f"{indent}{indent}→ {c.description}")

    # Summary statistics
    lines.append("")
    lines.append(
        f"Combined standard uncertainty (1σ): {budget.combined_standard_uncertainty:.4g} {budget.measurement_unit}"
    )
    if budget.relative_uncertainty_percent is not None:
        lines.append(
            f"Relative expanded uncertainty: {budget.relative_uncertainty_percent:.1f}%"
        )

    return "\n".join(lines)


def uncertainty_to_dict(budget: UncertaintyBudget) -> Dict[str, Any]:
    """
    Convert uncertainty budget to dictionary for JSON output.

    Args:
        budget: UncertaintyBudget to convert

    Returns:
        Dictionary suitable for JSON serialization
    """
    return budget.to_dict()


def format_measurement_with_budget(
    name: str,
    budget: UncertaintyBudget,
    include_breakdown: bool = False,
) -> str:
    """
    Format a named measurement with its uncertainty budget.

    Args:
        name: Measurement name
        budget: UncertaintyBudget
        include_breakdown: Whether to include component breakdown

    Returns:
        Formatted string
    """
    lines = [f"=== {name} ==="]

    if budget.measurement_value is not None:
        lines.append(
            format_with_uncertainty(
                budget.measurement_value,
                budget.expanded_uncertainty,
                budget.measurement_unit,
                show_relative=True,
            )
        )

    if include_breakdown:
        lines.append("")
        lines.append(format_uncertainty_budget(budget, show_components=True))

    return "\n".join(lines)


def format_relative_uncertainty(
    value: float,
    uncertainty: float,
    precision: int = 1,
) -> str:
    """
    Format relative uncertainty as percentage.

    Args:
        value: Measured value
        uncertainty: Expanded uncertainty
        precision: Decimal places for percentage

    Returns:
        String like "± 2.5%"
    """
    if value == 0 or math.isinf(uncertainty) or math.isnan(uncertainty):
        return "± inf%"

    rel_percent = (uncertainty / abs(value)) * 100
    return f"± {rel_percent:.{precision}f}%"


def format_confidence_interval(
    value: float,
    uncertainty: float,
    unit: str = "",
    coverage_factor: float = 2.0,
) -> str:
    """
    Format measurement as confidence interval.

    Args:
        value: Measured value
        uncertainty: Expanded uncertainty
        unit: Unit string
        coverage_factor: k factor for confidence level

    Returns:
        String like "[438.8, 441.2] Hz (k=2, 95%)"
    """
    lower = value - uncertainty
    upper = value + uncertainty

    # Estimate confidence level from k
    if coverage_factor >= 3:
        confidence = "99.7%"
    elif coverage_factor >= 2.58:
        confidence = "99%"
    elif coverage_factor >= 2:
        confidence = "95%"
    elif coverage_factor >= 1.64:
        confidence = "90%"
    else:
        confidence = f"~{int(68 + (coverage_factor - 1) * 27)}%"

    return f"[{lower:.4g}, {upper:.4g}] {unit} (k={coverage_factor}, {confidence})"

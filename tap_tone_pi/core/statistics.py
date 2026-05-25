# INSTRUMENT CLASS: MEASUREMENT
"""
Statistical functions for measurement uncertainty quantification.

Phase 3.2: Measurement Uncertainty Reporting

This module provides GUM-compliant (Guide to Uncertainty in Measurement)
statistical functions for:
- Type A uncertainty evaluation (repeated measurements)
- Confidence interval computation
- Repeatability metrics
- Uncertainty propagation

All functions follow ISO/IEC Guide 98-3:2008 (GUM) conventions:
- Standard uncertainty u(x) = standard deviation of the mean
- Expanded uncertainty U = k × u(x) where k is coverage factor
- For k=2: U gives approximately 95% confidence interval

Example:
    >>> from tap_tone_pi.core.statistics import compute_type_a_uncertainty
    >>> measurements = [185.2, 185.4, 185.1, 185.3, 185.2]
    >>> result = compute_type_a_uncertainty(measurements)
    >>> print(f"Mean: {result.mean:.2f} ± {result.expanded_uncertainty:.2f} Hz")
    Mean: 185.24 ± 0.11 Hz
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# Coverage factors for different confidence levels
# k=1: 68.3%, k=2: 95.4%, k=2.58: 99%, k=3: 99.7%
COVERAGE_FACTOR_95 = 2.0
COVERAGE_FACTOR_99 = 2.58
COVERAGE_FACTOR_68 = 1.0


@dataclass(frozen=True)
class TypeAResult:
    """Result of Type A uncertainty evaluation (statistical analysis).

    Type A evaluation derives uncertainty from repeated measurements using
    statistical methods per GUM Section 4.2.

    Attributes:
        mean: Arithmetic mean of measurements
        std_dev: Sample standard deviation (with Bessel correction)
        std_uncertainty: Standard uncertainty u(x) = std_dev / √n
        expanded_uncertainty: U = k × u(x) for specified coverage factor
        coverage_factor: k value used for expanded uncertainty
        n_measurements: Number of measurements
        degrees_of_freedom: n - 1 for sample statistics
        min_value: Minimum measurement
        max_value: Maximum measurement
        range_value: max - min
    """

    mean: float
    std_dev: float
    std_uncertainty: float
    expanded_uncertainty: float
    coverage_factor: float
    n_measurements: int
    degrees_of_freedom: int
    min_value: float
    max_value: float
    range_value: float

    @property
    def relative_std_dev(self) -> float:
        """Relative standard deviation (coefficient of variation)."""
        if abs(self.mean) < 1e-10:
            return 0.0
        return self.std_dev / abs(self.mean)

    @property
    def relative_uncertainty(self) -> float:
        """Relative standard uncertainty u(x)/|mean|."""
        if abs(self.mean) < 1e-10:
            return 0.0
        return self.std_uncertainty / abs(self.mean)

    @property
    def confidence_interval(self) -> tuple[float, float]:
        """Confidence interval (mean - U, mean + U)."""
        return (
            self.mean - self.expanded_uncertainty,
            self.mean + self.expanded_uncertainty,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "mean": self.mean,
            "std_dev": self.std_dev,
            "std_uncertainty": self.std_uncertainty,
            "expanded_uncertainty": self.expanded_uncertainty,
            "coverage_factor": self.coverage_factor,
            "n_measurements": self.n_measurements,
            "degrees_of_freedom": self.degrees_of_freedom,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "range_value": self.range_value,
            "relative_std_dev": self.relative_std_dev,
            "relative_uncertainty": self.relative_uncertainty,
            "confidence_interval": list(self.confidence_interval),
        }

    def format_value(self, precision: int = 2) -> str:
        """Format as 'mean ± uncertainty' string."""
        return f"{self.mean:.{precision}f} ± {self.expanded_uncertainty:.{precision}f}"


def compute_type_a_uncertainty(
    measurements: Sequence[float],
    *,
    coverage_factor: float = COVERAGE_FACTOR_95,
) -> TypeAResult:
    """
    Compute Type A uncertainty from repeated measurements.

    Type A evaluation uses statistical methods to analyze repeated
    observations per GUM Section 4.2.

    Args:
        measurements: Sequence of measurement values
        coverage_factor: k value for expanded uncertainty (default 2.0 for 95%)

    Returns:
        TypeAResult with mean, std deviation, and uncertainty values

    Raises:
        ValueError: If fewer than 2 measurements provided

    Physics:
        - Sample mean: x̄ = (1/n) × Σxᵢ
        - Sample std dev: s = √[(1/(n-1)) × Σ(xᵢ - x̄)²]  (Bessel correction)
        - Standard uncertainty: u(x̄) = s / √n
        - Expanded uncertainty: U = k × u(x̄)

    Example:
        >>> freq_readings = [185.2, 185.4, 185.1, 185.3, 185.2]
        >>> result = compute_type_a_uncertainty(freq_readings)
        >>> print(f"Frequency: {result.format_value()} Hz")
        Frequency: 185.24 ± 0.11 Hz
    """
    values = list(measurements)
    n = len(values)

    if n < 2:
        raise ValueError(f"Type A evaluation requires at least 2 measurements, got {n}")

    # Compute statistics
    mean = sum(values) / n
    min_val = min(values)
    max_val = max(values)

    # Sample standard deviation with Bessel's correction (n-1)
    sum_sq_diff = sum((x - mean) ** 2 for x in values)
    variance = sum_sq_diff / (n - 1)
    std_dev = math.sqrt(variance)

    # Standard uncertainty of the mean
    std_uncertainty = std_dev / math.sqrt(n)

    # Expanded uncertainty
    expanded_uncertainty = coverage_factor * std_uncertainty

    return TypeAResult(
        mean=mean,
        std_dev=std_dev,
        std_uncertainty=std_uncertainty,
        expanded_uncertainty=expanded_uncertainty,
        coverage_factor=coverage_factor,
        n_measurements=n,
        degrees_of_freedom=n - 1,
        min_value=min_val,
        max_value=max_val,
        range_value=max_val - min_val,
    )


@dataclass
class RepeatabilityMetrics:
    """Metrics for measurement repeatability assessment.

    Repeatability: Closeness of agreement between successive measurements
    under the same conditions (same operator, equipment, location, short time).

    Attributes:
        mean: Mean value
        repeatability_std_dev: Standard deviation of repeated measurements
        repeatability_limit: r = 2.8 × s_r (95% probability limit)
        coefficient_of_variation: CV = 100% × s_r / mean
        range_value: Max - Min
        n_measurements: Number of measurements
        is_acceptable: True if CV < threshold
    """

    mean: float
    repeatability_std_dev: float
    repeatability_limit: float
    coefficient_of_variation_pct: float
    range_value: float
    n_measurements: int
    is_acceptable: bool
    acceptance_threshold_pct: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "mean": self.mean,
            "repeatability_std_dev": self.repeatability_std_dev,
            "repeatability_limit": self.repeatability_limit,
            "coefficient_of_variation_pct": self.coefficient_of_variation_pct,
            "range_value": self.range_value,
            "n_measurements": self.n_measurements,
            "is_acceptable": self.is_acceptable,
            "acceptance_threshold_pct": self.acceptance_threshold_pct,
        }


def compute_repeatability(
    measurements: Sequence[float],
    *,
    acceptance_threshold_pct: float = 1.0,
) -> RepeatabilityMetrics:
    """
    Compute repeatability metrics for a series of measurements.

    Repeatability is the precision under repeatable conditions (same operator,
    equipment, location, short time interval).

    Args:
        measurements: Sequence of repeated measurement values
        acceptance_threshold_pct: Maximum acceptable CV% for repeatability

    Returns:
        RepeatabilityMetrics with repeatability statistics

    Raises:
        ValueError: If fewer than 2 measurements provided

    Physics:
        - Repeatability limit r = 2.8 × s_r (ISO 5725-2)
        - Two results should not differ by more than r at 95% confidence
        - CV = 100% × s_r / x̄

    Example:
        >>> readings = [440.2, 440.1, 440.3, 440.2, 440.2]
        >>> rep = compute_repeatability(readings)
        >>> print(f"CV: {rep.coefficient_of_variation_pct:.3f}%")
        CV: 0.017%
    """
    values = list(measurements)
    n = len(values)

    if n < 2:
        raise ValueError(f"Repeatability requires at least 2 measurements, got {n}")

    # Basic statistics
    mean = sum(values) / n
    min_val = min(values)
    max_val = max(values)

    # Repeatability standard deviation
    sum_sq_diff = sum((x - mean) ** 2 for x in values)
    s_r = math.sqrt(sum_sq_diff / (n - 1))

    # Repeatability limit (ISO 5725-2: r = 2.8 × s_r for 95% confidence)
    r = 2.8 * s_r

    # Coefficient of variation
    cv_pct = (100.0 * s_r / abs(mean)) if abs(mean) > 1e-10 else 0.0

    return RepeatabilityMetrics(
        mean=mean,
        repeatability_std_dev=s_r,
        repeatability_limit=r,
        coefficient_of_variation_pct=cv_pct,
        range_value=max_val - min_val,
        n_measurements=n,
        is_acceptable=cv_pct <= acceptance_threshold_pct,
        acceptance_threshold_pct=acceptance_threshold_pct,
    )


def combine_uncertainties(
    *uncertainties: float,
    correlation: float = 0.0,
) -> float:
    """
    Combine independent uncertainties using root-sum-of-squares.

    For uncorrelated inputs: u_c = √(u₁² + u₂² + ... + uₙ²)
    For correlated inputs (n=2): u_c = √(u₁² + u₂² + 2×r×u₁×u₂)

    Args:
        *uncertainties: Individual standard uncertainties
        correlation: Correlation coefficient r (only for exactly 2 inputs)

    Returns:
        Combined standard uncertainty

    Raises:
        ValueError: If correlation given for n != 2 inputs

    Example:
        >>> # Combine frequency uncertainties from two independent sources
        >>> u_cal = 0.5  # Calibration uncertainty
        >>> u_rep = 0.3  # Repeatability uncertainty
        >>> u_combined = combine_uncertainties(u_cal, u_rep)
        >>> print(f"Combined: {u_combined:.2f} Hz")
        Combined: 0.58 Hz
    """
    values = list(uncertainties)
    n = len(values)

    if n == 0:
        return 0.0

    if correlation != 0.0:
        if n != 2:
            raise ValueError(
                f"Correlation coefficient only valid for 2 inputs, got {n}"
            )
        u1, u2 = values
        return math.sqrt(u1**2 + u2**2 + 2 * correlation * u1 * u2)

    # Root sum of squares for uncorrelated inputs
    return math.sqrt(sum(u**2 for u in values))


def propagate_uncertainty_linear(
    coefficients: Sequence[float],
    uncertainties: Sequence[float],
) -> float:
    """
    Propagate uncertainties through a linear function.

    For y = c₁x₁ + c₂x₂ + ... + cₙxₙ:
    u(y) = √(c₁²u₁² + c₂²u₂² + ... + cₙ²uₙ²)

    Assumes uncorrelated inputs.

    Args:
        coefficients: Sensitivity coefficients [c₁, c₂, ..., cₙ]
        uncertainties: Standard uncertainties [u₁, u₂, ..., uₙ]

    Returns:
        Propagated standard uncertainty u(y)

    Raises:
        ValueError: If lengths don't match

    Example:
        >>> # y = 2*a + 3*b, with u(a)=0.1, u(b)=0.2
        >>> u_y = propagate_uncertainty_linear([2, 3], [0.1, 0.2])
        >>> print(f"u(y) = {u_y:.2f}")
        u(y) = 0.63
    """
    c = list(coefficients)
    u = list(uncertainties)

    if len(c) != len(u):
        raise ValueError(
            f"Length mismatch: {len(c)} coefficients, {len(u)} uncertainties"
        )

    return math.sqrt(sum(ci**2 * ui**2 for ci, ui in zip(c, u)))


def propagate_uncertainty_relative(
    value: float,
    relative_uncertainties: Sequence[float],
) -> float:
    """
    Propagate relative uncertainties for multiplicative functions.

    For y = k × x₁ × x₂ × ... × xₙ (or divisions):
    u_rel(y) = √(u_rel(x₁)² + u_rel(x₂)² + ... + u_rel(xₙ)²)

    Args:
        value: The computed result value y
        relative_uncertainties: Relative uncertainties [u₁/x₁, u₂/x₂, ...]

    Returns:
        Absolute standard uncertainty u(y)

    Example:
        >>> # Density = mass / volume
        >>> density = 2700  # kg/m³
        >>> u_rel_mass = 0.001  # 0.1% mass uncertainty
        >>> u_rel_vol = 0.002   # 0.2% volume uncertainty
        >>> u_density = propagate_uncertainty_relative(
        ...     density, [u_rel_mass, u_rel_vol]
        ... )
        >>> print(f"Density: {density} ± {u_density:.1f} kg/m³")
        Density: 2700 ± 6.0 kg/m³
    """
    u_rel_combined = math.sqrt(sum(ur**2 for ur in relative_uncertainties))
    return abs(value) * u_rel_combined


@dataclass
class UncertaintyBudget:
    """Uncertainty budget for tracking multiple uncertainty sources.

    An uncertainty budget documents all contributions to the combined
    uncertainty of a measurement result.

    Example:
        >>> budget = UncertaintyBudget()
        >>> budget.add_component("Repeatability", 0.3, "Hz", "Type A")
        >>> budget.add_component("Calibration", 0.5, "Hz", "Type B")
        >>> budget.add_component("Resolution", 0.1, "Hz", "Type B")
        >>> print(f"Combined: {budget.combined_uncertainty:.2f} Hz")
        Combined: 0.59 Hz
    """

    components: list[dict] = field(default_factory=list)

    def add_component(
        self,
        name: str,
        uncertainty: float,
        unit: str = "",
        source_type: str = "Type A",
        degrees_of_freedom: int | None = None,
    ) -> None:
        """
        Add an uncertainty component to the budget.

        Args:
            name: Component name (e.g., "Repeatability", "Calibration")
            uncertainty: Standard uncertainty value
            unit: Unit of measurement
            source_type: "Type A" (statistical) or "Type B" (other)
            degrees_of_freedom: Degrees of freedom (for Welch-Satterthwaite)
        """
        self.components.append(
            {
                "name": name,
                "uncertainty": uncertainty,
                "unit": unit,
                "source_type": source_type,
                "degrees_of_freedom": degrees_of_freedom,
                "contribution_pct": None,  # Computed when combined
            }
        )

    @property
    def combined_uncertainty(self) -> float:
        """Combined standard uncertainty from all components."""
        if not self.components:
            return 0.0
        return math.sqrt(sum(c["uncertainty"] ** 2 for c in self.components))

    def compute_contributions(self) -> None:
        """Compute percentage contribution of each component."""
        combined_sq = self.combined_uncertainty**2
        if combined_sq < 1e-20:
            return

        for c in self.components:
            c["contribution_pct"] = 100.0 * (c["uncertainty"] ** 2) / combined_sq

    def expanded_uncertainty(self, coverage_factor: float = 2.0) -> float:
        """Compute expanded uncertainty U = k × u_c."""
        return coverage_factor * self.combined_uncertainty

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        self.compute_contributions()
        return {
            "components": self.components,
            "combined_uncertainty": self.combined_uncertainty,
            "expanded_uncertainty_k2": self.expanded_uncertainty(2.0),
        }

    def format_report(self, result_value: float = 0.0, unit: str = "") -> str:
        """Format as human-readable uncertainty budget report."""
        self.compute_contributions()
        lines = []
        lines.append("Uncertainty Budget")
        lines.append("=" * 60)

        # Components table
        lines.append(f"{'Source':<25} {'Type':<8} {'u(x)':<12} {'Contribution':<12}")
        lines.append("-" * 60)

        for c in self.components:
            u_str = f"{c['uncertainty']:.4f}"
            if c["unit"]:
                u_str += f" {c['unit']}"
            contrib = c.get("contribution_pct", 0.0) or 0.0
            lines.append(
                f"{c['name']:<25} {c['source_type']:<8} {u_str:<12} {contrib:>6.1f}%"
            )

        lines.append("-" * 60)
        u_c = self.combined_uncertainty
        U = self.expanded_uncertainty(2.0)
        lines.append(f"Combined standard uncertainty u_c: {u_c:.4f} {unit}")
        lines.append(f"Expanded uncertainty U (k=2):      {U:.4f} {unit}")

        if result_value != 0.0:
            lines.append("")
            lines.append(f"Result: {result_value:.4f} ± {U:.4f} {unit} (k=2, 95%)")

        return "\n".join(lines)


def is_measurement_outlier(
    value: float,
    reference: float,
    uncertainty: float,
    *,
    threshold_sigma: float = 3.0,
) -> bool:
    """
    Check if a measurement is an outlier based on uncertainty bounds.

    A measurement is flagged as an outlier if it deviates from the reference
    by more than threshold_sigma × uncertainty.

    Args:
        value: Measurement value to check
        reference: Reference value (mean or expected)
        uncertainty: Standard uncertainty of the measurement
        threshold_sigma: Number of standard deviations for outlier (default 3σ)

    Returns:
        True if value is an outlier

    Example:
        >>> mean = 185.0
        >>> std = 0.5
        >>> is_measurement_outlier(186.8, mean, std)  # 3.6σ away
        True
    """
    if uncertainty <= 0:
        return False
    deviation = abs(value - reference)
    return deviation > threshold_sigma * uncertainty


def compute_weighted_mean(
    values: Sequence[float],
    uncertainties: Sequence[float],
) -> tuple[float, float]:
    """
    Compute uncertainty-weighted mean and its uncertainty.

    Weights are inverse-variance weights: wᵢ = 1/uᵢ²
    Weighted mean: x̄_w = Σ(wᵢxᵢ) / Σwᵢ
    Uncertainty: u(x̄_w) = 1 / √(Σwᵢ)

    Args:
        values: Measurement values
        uncertainties: Standard uncertainties of each value

    Returns:
        (weighted_mean, uncertainty_of_mean)

    Raises:
        ValueError: If lengths don't match or any uncertainty is zero

    Example:
        >>> # Combine measurements with different precisions
        >>> freqs = [185.2, 185.4]
        >>> uncertainties = [0.5, 0.2]  # Second is more precise
        >>> mean, u_mean = compute_weighted_mean(freqs, uncertainties)
        >>> print(f"Mean: {mean:.2f} ± {u_mean:.2f} Hz")
        Mean: 185.37 ± 0.19 Hz
    """
    vals = list(values)
    uncs = list(uncertainties)

    if len(vals) != len(uncs):
        raise ValueError(
            f"Length mismatch: {len(vals)} values, {len(uncs)} uncertainties"
        )

    if len(vals) == 0:
        raise ValueError("Empty input")

    if any(u <= 0 for u in uncs):
        raise ValueError("All uncertainties must be positive")

    # Inverse-variance weights
    weights = [1.0 / (u**2) for u in uncs]
    sum_weights = sum(weights)

    # Weighted mean
    weighted_sum = sum(w * v for w, v in zip(weights, vals))
    mean = weighted_sum / sum_weights

    # Uncertainty of weighted mean
    uncertainty = 1.0 / math.sqrt(sum_weights)

    return mean, uncertainty


__all__ = [
    # Constants
    "COVERAGE_FACTOR_95",
    "COVERAGE_FACTOR_99",
    "COVERAGE_FACTOR_68",
    # Classes
    "TypeAResult",
    "RepeatabilityMetrics",
    "UncertaintyBudget",
    # Functions
    "compute_type_a_uncertainty",
    "compute_repeatability",
    "combine_uncertainties",
    "propagate_uncertainty_linear",
    "propagate_uncertainty_relative",
    "is_measurement_outlier",
    "compute_weighted_mean",
]

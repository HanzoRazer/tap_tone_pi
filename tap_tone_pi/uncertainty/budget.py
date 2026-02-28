"""
Uncertainty budget structures and combination rules.

Follows ISO/IEC Guide 98-3:2008 (GUM) principles for the evaluation and
expression of measurement uncertainty.

Key concepts:
- Type A evaluation: Statistical analysis of repeated observations
- Type B evaluation: Other means (specifications, calibration certificates,
  prior knowledge, manufacturer's specifications)
- Combined standard uncertainty: RSS combination with sensitivity coefficients
- Effective degrees of freedom: Welch-Satterthwaite formula
- Expanded uncertainty: Coverage factor for confidence interval

Mathematical Background:
------------------------
For input quantities x_i with standard uncertainties u(x_i), the combined
standard uncertainty of output y = f(x_1, x_2, ..., x_N) is:

    u_c(y) = sqrt(Σ (∂f/∂x_i)² u²(x_i) + 2 Σ Σ (∂f/∂x_i)(∂f/∂x_j) u(x_i,x_j))

For uncorrelated inputs, the second term vanishes.

The effective degrees of freedom (Welch-Satterthwaite):

    ν_eff = u_c⁴(y) / Σ [(c_i u(x_i))⁴ / ν_i]

where c_i are sensitivity coefficients and ν_i are degrees of freedom.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import numpy as np
from scipy import stats


class UncertaintyType(Enum):
    """Type of uncertainty evaluation per GUM classification."""

    TYPE_A = "type_a"  # Statistical analysis of repeated observations
    TYPE_B = "type_b"  # Other means (specifications, calibration data, etc.)


class DistributionType(Enum):
    """Probability distribution assumed for Type B uncertainty."""

    NORMAL = "normal"           # Gaussian, u = a/k where k is coverage factor
    RECTANGULAR = "rectangular" # Uniform, u = a/√3
    TRIANGULAR = "triangular"   # u = a/√6
    U_SHAPED = "u_shaped"       # Arcsine, u = a/√2
    CUSTOM = "custom"           # User-specified divisor


@dataclass
class UncertaintyComponent:
    """
    Single component of measurement uncertainty.

    Represents a single source of uncertainty with its standard uncertainty,
    sensitivity coefficient, and degrees of freedom.

    Attributes
    ----------
    name : str
        Descriptive name for this uncertainty source.
    value : float
        Standard uncertainty u(x_i) in measurement units.
    unit : str
        Physical unit of the uncertainty.
    uncertainty_type : UncertaintyType
        TYPE_A for statistical evaluation, TYPE_B for other methods.
    distribution : DistributionType
        Assumed probability distribution (for Type B).
    description : str
        Human-readable description of this source.
    sensitivity_coefficient : float
        Partial derivative c_i = ∂y/∂x_i (default 1.0 for direct influence).
    degrees_of_freedom : int
        ν_i for this component. For Type A: n-1. For Type B: 50 (approx ∞).
    half_width : float
        Original half-width 'a' before converting to standard uncertainty.
    coverage_factor_used : float
        Coverage factor used to derive standard uncertainty from half-width.
    """

    name: str
    value: float  # Standard uncertainty (1σ)
    unit: str
    uncertainty_type: UncertaintyType = UncertaintyType.TYPE_B
    distribution: DistributionType = DistributionType.NORMAL
    description: str = ""
    sensitivity_coefficient: float = 1.0  # Partial derivative factor
    degrees_of_freedom: int = 50  # Default: effectively infinite for Type B
    half_width: Optional[float] = None  # Original 'a' value
    coverage_factor_used: Optional[float] = None

    @property
    def contribution(self) -> float:
        """Contribution to combined variance (c_i × u_i)²."""
        return (self.sensitivity_coefficient * self.value) ** 2

    @property
    def contribution_to_variance(self) -> float:
        """Alias for contribution - squared term in RSS."""
        return self.contribution

    @property
    def percent_contribution(self) -> Optional[float]:
        """Placeholder - computed at budget level."""
        return None


def create_type_a_source(
    name: str,
    observations: np.ndarray,
    unit: str = "",
    description: str = "",
    sensitivity_coefficient: float = 1.0,
) -> UncertaintyComponent:
    """
    Create Type A uncertainty from repeated observations.

    Type A evaluation uses statistical analysis:
        u(x) = s / √n

    where s is the sample standard deviation and n is the number of observations.

    Parameters
    ----------
    name : str
        Name for this uncertainty source.
    observations : np.ndarray
        Array of repeated measurements.
    unit : str
        Physical unit.
    description : str
        Human-readable description.
    sensitivity_coefficient : float
        Partial derivative ∂y/∂x.

    Returns
    -------
    UncertaintyComponent
        Type A uncertainty component.

    Example
    -------
    >>> readings = np.array([100.1, 100.3, 99.9, 100.2, 100.0])
    >>> uc = create_type_a_source("repeatability", readings, "Hz")
    >>> print(f"u = {uc.value:.3f} Hz, ν = {uc.degrees_of_freedom}")
    u = 0.071 Hz, ν = 4
    """
    n = len(observations)
    if n < 2:
        raise ValueError("Type A requires at least 2 observations")

    std_dev = np.std(observations, ddof=1)  # Sample standard deviation
    standard_uncertainty = std_dev / np.sqrt(n)  # Standard error of mean

    return UncertaintyComponent(
        name=name,
        value=float(standard_uncertainty),
        unit=unit,
        uncertainty_type=UncertaintyType.TYPE_A,
        distribution=DistributionType.NORMAL,
        description=description or f"Type A from {n} observations",
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=n - 1,
        half_width=None,
        coverage_factor_used=None,
    )


def create_type_b_rectangular(
    name: str,
    half_width: float,
    unit: str = "",
    description: str = "",
    sensitivity_coefficient: float = 1.0,
) -> UncertaintyComponent:
    """
    Create Type B uncertainty with rectangular (uniform) distribution.

    For a quantity known to lie within ±a with equal probability:
        u(x) = a / √3

    This is appropriate when only bounds are known with no preference
    for any value within the range.

    Parameters
    ----------
    name : str
        Name for this uncertainty source.
    half_width : float
        Half-width 'a' of the rectangular distribution (±a).
    unit : str
        Physical unit.
    description : str
        Human-readable description.
    sensitivity_coefficient : float
        Partial derivative ∂y/∂x.

    Returns
    -------
    UncertaintyComponent
        Type B uncertainty component with rectangular distribution.

    Example
    -------
    >>> # Resolution uncertainty: ±0.5 of last digit
    >>> uc = create_type_b_rectangular("resolution", 0.5, "Hz")
    >>> print(f"u = {uc.value:.3f} Hz")
    u = 0.289 Hz
    """
    divisor = np.sqrt(3)
    standard_uncertainty = half_width / divisor

    return UncertaintyComponent(
        name=name,
        value=float(standard_uncertainty),
        unit=unit,
        uncertainty_type=UncertaintyType.TYPE_B,
        distribution=DistributionType.RECTANGULAR,
        description=description or f"Rectangular ±{half_width} {unit}",
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=50,  # Effectively infinite
        half_width=float(half_width),
        coverage_factor_used=divisor,
    )


def create_type_b_normal(
    name: str,
    expanded_uncertainty: float,
    coverage_factor: float = 2.0,
    unit: str = "",
    description: str = "",
    sensitivity_coefficient: float = 1.0,
) -> UncertaintyComponent:
    """
    Create Type B uncertainty with normal distribution.

    For a quantity stated with expanded uncertainty U at coverage k:
        u(x) = U / k

    This is appropriate for calibration certificates and specifications
    stated at known confidence levels.

    Parameters
    ----------
    name : str
        Name for this uncertainty source.
    expanded_uncertainty : float
        Expanded uncertainty U (e.g., from calibration certificate).
    coverage_factor : float
        Coverage factor k (default 2.0 for ~95% confidence).
    unit : str
        Physical unit.
    description : str
        Human-readable description.
    sensitivity_coefficient : float
        Partial derivative ∂y/∂x.

    Returns
    -------
    UncertaintyComponent
        Type B uncertainty component with normal distribution.

    Example
    -------
    >>> # Calibration uncertainty: U = 0.05 Hz at k=2
    >>> uc = create_type_b_normal("calibration", 0.05, 2.0, "Hz")
    >>> print(f"u = {uc.value:.4f} Hz")
    u = 0.0250 Hz
    """
    standard_uncertainty = expanded_uncertainty / coverage_factor

    return UncertaintyComponent(
        name=name,
        value=float(standard_uncertainty),
        unit=unit,
        uncertainty_type=UncertaintyType.TYPE_B,
        distribution=DistributionType.NORMAL,
        description=description or f"Normal, U={expanded_uncertainty} at k={coverage_factor}",
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=50,  # Effectively infinite
        half_width=float(expanded_uncertainty),
        coverage_factor_used=float(coverage_factor),
    )


def create_type_b_triangular(
    name: str,
    half_width: float,
    unit: str = "",
    description: str = "",
    sensitivity_coefficient: float = 1.0,
) -> UncertaintyComponent:
    """
    Create Type B uncertainty with triangular distribution.

    For a quantity known to lie within ±a with values near center more likely:
        u(x) = a / √6

    This is appropriate when central values are more probable than extremes,
    but the exact distribution is unknown.

    Parameters
    ----------
    name : str
        Name for this uncertainty source.
    half_width : float
        Half-width 'a' of the triangular distribution (±a).
    unit : str
        Physical unit.
    description : str
        Human-readable description.
    sensitivity_coefficient : float
        Partial derivative ∂y/∂x.

    Returns
    -------
    UncertaintyComponent
        Type B uncertainty component with triangular distribution.
    """
    divisor = np.sqrt(6)
    standard_uncertainty = half_width / divisor

    return UncertaintyComponent(
        name=name,
        value=float(standard_uncertainty),
        unit=unit,
        uncertainty_type=UncertaintyType.TYPE_B,
        distribution=DistributionType.TRIANGULAR,
        description=description or f"Triangular ±{half_width} {unit}",
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=50,
        half_width=float(half_width),
        coverage_factor_used=divisor,
    )


def create_type_b_uform(
    name: str,
    half_width: float,
    unit: str = "",
    description: str = "",
    sensitivity_coefficient: float = 1.0,
) -> UncertaintyComponent:
    """
    Create Type B uncertainty with U-shaped (arcsine) distribution.

    For a quantity that tends toward extremes (e.g., sinusoidal variation):
        u(x) = a / √2

    This is appropriate for quantities that spend more time at the limits
    than at the center, such as periodic oscillations.

    Parameters
    ----------
    name : str
        Name for this uncertainty source.
    half_width : float
        Half-width 'a' of the distribution (±a).
    unit : str
        Physical unit.
    description : str
        Human-readable description.
    sensitivity_coefficient : float
        Partial derivative ∂y/∂x.

    Returns
    -------
    UncertaintyComponent
        Type B uncertainty component with U-shaped distribution.
    """
    divisor = np.sqrt(2)
    standard_uncertainty = half_width / divisor

    return UncertaintyComponent(
        name=name,
        value=float(standard_uncertainty),
        unit=unit,
        uncertainty_type=UncertaintyType.TYPE_B,
        distribution=DistributionType.U_SHAPED,
        description=description or f"U-shaped ±{half_width} {unit}",
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=50,
        half_width=float(half_width),
        coverage_factor_used=divisor,
    )


@dataclass
class UncertaintyBudget:
    """
    Complete uncertainty budget for a measurement.

    Combines multiple uncertainty components using root-sum-square (RSS)
    per GUM methodology.
    """

    components: List[UncertaintyComponent] = field(default_factory=list)
    coverage_factor: float = 2.0  # k=2 for ~95% confidence
    degrees_of_freedom: Optional[int] = None  # For Welch-Satterthwaite
    measurement_value: Optional[float] = None
    measurement_unit: str = ""

    @property
    def combined_standard_uncertainty(self) -> float:
        """Combined standard uncertainty (1σ) via RSS."""
        if not self.components:
            return 0.0
        sum_squares = sum(c.contribution for c in self.components)
        return math.sqrt(sum_squares)

    @property
    def expanded_uncertainty(self) -> float:
        """Expanded uncertainty at coverage factor k."""
        return self.combined_standard_uncertainty * self.coverage_factor

    @property
    def relative_uncertainty(self) -> Optional[float]:
        """Relative expanded uncertainty (as fraction)."""
        if self.measurement_value is None or self.measurement_value == 0:
            return None
        return self.expanded_uncertainty / abs(self.measurement_value)

    @property
    def relative_uncertainty_percent(self) -> Optional[float]:
        """Relative expanded uncertainty (as percent)."""
        rel = self.relative_uncertainty
        return rel * 100 if rel is not None else None

    def add_component(
        self,
        name: str,
        value: float,
        unit: str,
        uncertainty_type: UncertaintyType = UncertaintyType.TYPE_B,
        description: str = "",
        sensitivity_coefficient: float = 1.0,
    ) -> None:
        """Add an uncertainty component to the budget."""
        self.components.append(
            UncertaintyComponent(
                name=name,
                value=value,
                unit=unit,
                uncertainty_type=uncertainty_type,
                description=description,
                sensitivity_coefficient=sensitivity_coefficient,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "components": [
                {
                    "name": c.name,
                    "value": c.value,
                    "unit": c.unit,
                    "type": c.uncertainty_type.value,
                    "description": c.description,
                    "sensitivity_coefficient": c.sensitivity_coefficient,
                    "contribution_squared": c.contribution,
                }
                for c in self.components
            ],
            "combined_standard_uncertainty": self.combined_standard_uncertainty,
            "coverage_factor": self.coverage_factor,
            "expanded_uncertainty": self.expanded_uncertainty,
            "degrees_of_freedom": self.degrees_of_freedom,
            "measurement_value": self.measurement_value,
            "measurement_unit": self.measurement_unit,
            "relative_uncertainty_percent": self.relative_uncertainty_percent,
        }


def welch_satterthwaite_dof(
    contributions: List[float],
    degrees_of_freedom: List[int],
) -> float:
    """
    Calculate effective degrees of freedom using Welch-Satterthwaite formula.

    The effective degrees of freedom for combined uncertainty:

        ν_eff = u_c⁴(y) / Σ [(c_i u(x_i))⁴ / ν_i]

    Parameters
    ----------
    contributions : List[float]
        List of (c_i × u_i)² values for each component.
    degrees_of_freedom : List[int]
        Degrees of freedom ν_i for each component.

    Returns
    -------
    float
        Effective degrees of freedom ν_eff.

    Notes
    -----
    - For Type A with n observations: ν = n - 1
    - For Type B (well-characterized): ν ≈ 50 (effectively infinite)
    - Result is typically truncated to integer for t-distribution lookup
    """
    if not contributions or not degrees_of_freedom:
        return float('inf')

    if len(contributions) != len(degrees_of_freedom):
        raise ValueError("contributions and degrees_of_freedom must have same length")

    u_c_squared = sum(contributions)
    u_c_fourth = u_c_squared ** 2

    denominator = 0.0
    for u_i_sq, nu_i in zip(contributions, degrees_of_freedom):
        if nu_i > 0:
            denominator += (u_i_sq ** 2) / nu_i

    if denominator == 0:
        return float('inf')

    nu_eff = u_c_fourth / denominator
    return nu_eff


def coverage_factor(
    degrees_of_freedom: float,
    confidence_level: float = 0.95,
) -> float:
    """
    Calculate coverage factor k for given degrees of freedom and confidence.

    Uses Student's t-distribution for finite degrees of freedom.
    For ν → ∞, approaches the normal distribution values.

    Parameters
    ----------
    degrees_of_freedom : float
        Effective degrees of freedom ν_eff.
    confidence_level : float
        Confidence level (default 0.95 for 95%).

    Returns
    -------
    float
        Coverage factor k.

    Example
    -------
    >>> k = coverage_factor(10, 0.95)
    >>> print(f"k = {k:.3f}")  # 2.228
    k = 2.228
    >>> k = coverage_factor(float('inf'), 0.95)
    >>> print(f"k = {k:.3f}")  # 1.960
    k = 1.960
    """
    if degrees_of_freedom <= 0:
        return 2.0  # Fallback

    if np.isinf(degrees_of_freedom) or degrees_of_freedom > 1000:
        # Use normal distribution
        return float(stats.norm.ppf((1 + confidence_level) / 2))

    # Use t-distribution
    return float(stats.t.ppf((1 + confidence_level) / 2, degrees_of_freedom))


@dataclass
class CombinedUncertainty:
    """
    Result of uncertainty combination following GUM methodology.

    Attributes
    ----------
    combined_standard_uncertainty : float
        u_c(y) - combined standard uncertainty.
    effective_degrees_of_freedom : float
        ν_eff from Welch-Satterthwaite.
    coverage_factor : float
        k at specified confidence level.
    expanded_uncertainty : float
        U = k × u_c(y).
    confidence_level : float
        Probability coverage.
    component_contributions : Dict[str, float]
        Percent contribution from each source.
    dominant_source : str
        Name of largest contributor.
    """
    combined_standard_uncertainty: float
    effective_degrees_of_freedom: float
    coverage_factor: float
    expanded_uncertainty: float
    confidence_level: float
    component_contributions: Dict[str, float] = field(default_factory=dict)
    dominant_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "combined_standard_uncertainty": self.combined_standard_uncertainty,
            "effective_degrees_of_freedom": self.effective_degrees_of_freedom,
            "coverage_factor": self.coverage_factor,
            "expanded_uncertainty": self.expanded_uncertainty,
            "confidence_level": self.confidence_level,
            "component_contributions_percent": self.component_contributions,
            "dominant_source": self.dominant_source,
        }


def combine_uncertainties(*uncertainties: float) -> float:
    """
    Combine multiple standard uncertainties via root-sum-square.

    This is the uncorrelated case. For correlated quantities,
    use the full propagation function.

    Args:
        *uncertainties: Standard uncertainties to combine

    Returns:
        Combined standard uncertainty
    """
    return math.sqrt(sum(u**2 for u in uncertainties))


def combine_with_gum(
    components: List[UncertaintyComponent],
    confidence_level: float = 0.95,
) -> CombinedUncertainty:
    """
    Combine uncertainty components following full GUM methodology.

    Computes:
    1. Combined standard uncertainty via RSS with sensitivity coefficients
    2. Effective degrees of freedom via Welch-Satterthwaite
    3. Coverage factor from t-distribution
    4. Expanded uncertainty and contribution percentages

    Parameters
    ----------
    components : List[UncertaintyComponent]
        List of uncertainty components.
    confidence_level : float
        Confidence level for expanded uncertainty.

    Returns
    -------
    CombinedUncertainty
        Complete GUM-compliant uncertainty result.
    """
    if not components:
        return CombinedUncertainty(
            combined_standard_uncertainty=0.0,
            effective_degrees_of_freedom=float('inf'),
            coverage_factor=coverage_factor(float('inf'), confidence_level),
            expanded_uncertainty=0.0,
            confidence_level=confidence_level,
        )

    # Calculate contributions
    contributions = [c.contribution for c in components]
    dofs = [c.degrees_of_freedom for c in components]

    # Combined standard uncertainty
    u_c = math.sqrt(sum(contributions))

    # Effective degrees of freedom
    nu_eff = welch_satterthwaite_dof(contributions, dofs)

    # Coverage factor
    k = coverage_factor(nu_eff, confidence_level)

    # Expanded uncertainty
    U = k * u_c

    # Contribution percentages
    total_variance = sum(contributions)
    contribution_pct = {}
    dominant = ""
    max_contrib = 0.0

    for c, contrib in zip(components, contributions):
        pct = 100.0 * contrib / total_variance if total_variance > 0 else 0.0
        contribution_pct[c.name] = round(pct, 2)
        if contrib > max_contrib:
            max_contrib = contrib
            dominant = c.name

    return CombinedUncertainty(
        combined_standard_uncertainty=u_c,
        effective_degrees_of_freedom=nu_eff,
        coverage_factor=k,
        expanded_uncertainty=U,
        confidence_level=confidence_level,
        component_contributions=contribution_pct,
        dominant_source=dominant,
    )


def expand_uncertainty(
    standard_uncertainty: float, coverage_factor: float = 2.0
) -> float:
    """
    Expand standard uncertainty to confidence interval.

    Args:
        standard_uncertainty: Standard uncertainty (1σ)
        coverage_factor: k factor (default 2.0 for ~95%)

    Returns:
        Expanded uncertainty
    """
    return standard_uncertainty * coverage_factor


# Common uncertainty factors for tap tone measurements
UNCERTAINTY_FACTORS = {
    # Calibration state
    "calibrated_system": 0.5,  # dB, calibrated audio system
    "uncalibrated_system": 2.0,  # dB, uncalibrated audio system
    # Signal quality
    "high_snr": 0.3,  # dB, SNR > 40 dB
    "medium_snr": 0.8,  # dB, SNR 20-40 dB
    "low_snr": 2.0,  # dB, SNR < 20 dB
    # Frequency resolution (relative to FFT bin width)
    "peak_interpolation": 0.3,  # Fraction of bin width
    # Physical measurements
    "length_measurement": 0.5,  # mm, manual measurement
    "thickness_measurement": 0.05,  # mm, digital caliper
    "mass_measurement": 0.1,  # grams, digital scale
    # Methodology
    "deflection_method": 0.03,  # Relative MOE uncertainty (3%)
    "tap_tone_method": 0.05,  # Relative MOE uncertainty (5%)
}


def get_calibration_uncertainty_factor(is_calibrated: bool) -> float:
    """
    Get uncertainty factor based on calibration state.

    Args:
        is_calibrated: Whether device is calibrated

    Returns:
        Uncertainty factor in dB
    """
    if is_calibrated:
        return UNCERTAINTY_FACTORS["calibrated_system"]
    return UNCERTAINTY_FACTORS["uncalibrated_system"]


def get_snr_uncertainty_factor(snr_db: float) -> float:
    """
    Get uncertainty factor based on SNR.

    Args:
        snr_db: Signal-to-noise ratio in dB

    Returns:
        Uncertainty factor in dB
    """
    if snr_db >= 40:
        return UNCERTAINTY_FACTORS["high_snr"]
    elif snr_db >= 20:
        return UNCERTAINTY_FACTORS["medium_snr"]
    else:
        return UNCERTAINTY_FACTORS["low_snr"]

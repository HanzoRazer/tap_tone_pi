"""
Uncertainty budget structures and combination rules.

Follows GUM (Guide to the Expression of Uncertainty in Measurement) principles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class UncertaintyType(Enum):
    """Type of uncertainty evaluation."""

    TYPE_A = "type_a"  # Statistical analysis of repeated observations
    TYPE_B = "type_b"  # Other means (specifications, calibration data, etc.)


@dataclass
class UncertaintyComponent:
    """Single component of measurement uncertainty."""

    name: str
    value: float  # Standard uncertainty (1σ)
    unit: str
    uncertainty_type: UncertaintyType = UncertaintyType.TYPE_B
    description: str = ""
    sensitivity_coefficient: float = 1.0  # Partial derivative factor

    @property
    def contribution(self) -> float:
        """Contribution to combined uncertainty (squared)."""
        return (self.sensitivity_coefficient * self.value) ** 2


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


def combine_uncertainties(*uncertainties: float) -> float:
    """
    Combine multiple standard uncertainties via root-sum-square.

    Args:
        *uncertainties: Standard uncertainties to combine

    Returns:
        Combined standard uncertainty
    """
    return math.sqrt(sum(u**2 for u in uncertainties))


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

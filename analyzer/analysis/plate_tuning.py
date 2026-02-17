"""
Plate Tuning Regression Engine.

Computes linear regression on mass vs frequency measurements.
Outputs are objective mathematical results, not prescriptive advice.

Physics basis: f ∝ √(Stiffness / Mass)
For small changes: Δf/f ≈ -0.5 × Δm/m (mass dominates when thinning uniformly)

This module performs measurement analysis only - no advisory logic.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from datetime import datetime


@dataclass
class TuningPoint:
    """Single measurement point in the tuning process."""

    mass_g: float  # Plate mass in grams
    freq_hz: float  # Measured frequency (monopole, etc.)
    deflection_x_mm: Optional[float] = None  # Cross-grain deflection
    deflection_y_mm: Optional[float] = None  # Along-grain deflection
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mass_g": self.mass_g,
            "freq_hz": self.freq_hz,
            "deflection_x_mm": self.deflection_x_mm,
            "deflection_y_mm": self.deflection_y_mm,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TuningPoint":
        return cls(
            mass_g=d["mass_g"],
            freq_hz=d["freq_hz"],
            deflection_x_mm=d.get("deflection_x_mm"),
            deflection_y_mm=d.get("deflection_y_mm"),
            timestamp=d.get("timestamp", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class RegressionResult:
    """Result of linear regression fit."""

    slope: float  # Hz per gram (typically negative - less mass = higher freq)
    intercept: float  # Frequency at zero mass (theoretical)
    r_squared: float  # Goodness of fit (0-1)
    n_points: int  # Number of data points

    # Derived predictions
    hz_per_gram: float  # How much frequency changes per gram removed

    def predict_freq(self, mass_g: float) -> float:
        """Predict frequency for a given mass."""
        return self.slope * mass_g + self.intercept

    def predict_mass_for_freq(self, target_freq_hz: float) -> float:
        """Predict mass needed to achieve target frequency."""
        if abs(self.slope) < 1e-9:
            return float("inf")  # Slope too flat
        return (target_freq_hz - self.intercept) / self.slope

    def compute_mass_delta(self, current_mass_g: float, target_freq_hz: float) -> float:
        """Compute mass difference between current and predicted target mass."""
        target_mass = self.predict_mass_for_freq(target_freq_hz)
        return current_mass_g - target_mass


class PlateTuningRegression:
    """
    Linear regression analyzer for plate tuning.

    Takes measurement points (mass, frequency) and fits a line to predict
    how much wood to remove to reach a target frequency.
    """

    def __init__(self):
        self.points: List[TuningPoint] = []
        self._result: Optional[RegressionResult] = None
        self.target_freq_hz: Optional[float] = None
        self.plate_name: str = "Untitled Plate"

    def add_point(self, point: TuningPoint) -> None:
        """Add a measurement point."""
        self.points.append(point)
        self._result = None  # Invalidate cached result

    def remove_point(self, index: int) -> None:
        """Remove a measurement point by index."""
        if 0 <= index < len(self.points):
            self.points.pop(index)
            self._result = None

    def clear_points(self) -> None:
        """Clear all measurement points."""
        self.points.clear()
        self._result = None

    def set_target(self, freq_hz: float) -> None:
        """Set target frequency."""
        self.target_freq_hz = freq_hz

    def can_regress(self) -> bool:
        """Check if we have enough points for regression."""
        return len(self.points) >= 2

    def fit(self) -> Optional[RegressionResult]:
        """
        Fit linear regression: freq = slope * mass + intercept

        Returns:
            RegressionResult or None if insufficient data
        """
        if not self.can_regress():
            return None

        # Extract arrays
        masses = np.array([p.mass_g for p in self.points])
        freqs = np.array([p.freq_hz for p in self.points])

        # Linear regression using least squares
        n = len(masses)
        sum_x = np.sum(masses)
        sum_y = np.sum(freqs)
        sum_xy = np.sum(masses * freqs)
        sum_x2 = np.sum(masses**2)

        denom = n * sum_x2 - sum_x**2
        if abs(denom) < 1e-9:
            return None  # Points are collinear in x

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R-squared
        y_pred = slope * masses + intercept
        ss_res = np.sum((freqs - y_pred) ** 2)
        ss_tot = np.sum((freqs - np.mean(freqs)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        self._result = RegressionResult(
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            n_points=n,
            hz_per_gram=slope,  # Direct interpretation
        )

        return self._result

    @property
    def result(self) -> Optional[RegressionResult]:
        """Get cached regression result, fitting if needed."""
        if self._result is None and self.can_regress():
            self.fit()
        return self._result

    def get_prediction(self) -> Optional[Dict[str, Any]]:
        """
        Get prediction for reaching target frequency.

        Returns:
            Dict with current state, target, and how much to remove
        """
        if not self.result or not self.target_freq_hz:
            return None

        if not self.points:
            return None

        # Current state (most recent measurement point)
        current = self.points[-1]

        # Compute predictions (objective math)
        target_mass = self.result.predict_mass_for_freq(self.target_freq_hz)
        mass_delta = self.result.compute_mass_delta(current.mass_g, self.target_freq_hz)

        return {
            "current_mass_g": current.mass_g,
            "current_freq_hz": current.freq_hz,
            "target_freq_hz": self.target_freq_hz,
            "target_mass_g": target_mass,
            "mass_delta_g": mass_delta,  # positive = current > target
            "hz_per_gram": self.result.hz_per_gram,
            "r_squared": self.result.r_squared,
            "confidence": "high"
            if self.result.r_squared > 0.9
            else "medium"
            if self.result.r_squared > 0.7
            else "low",
        }

    def get_trajectory_data(self) -> Dict[str, Any]:
        """
        Get data for plotting the tuning trajectory.

        Returns:
            Dict with points, regression line, and target overlay
        """
        if not self.points:
            return {
                "points": {"mass_g": [], "freq_hz": [], "labels": []},
                "line": None,
                "target": None,
            }

        masses = [p.mass_g for p in self.points]
        freqs = [p.freq_hz for p in self.points]

        data = {
            "points": {
                "mass_g": masses,
                "freq_hz": freqs,
                "labels": [f"#{i + 1}" for i in range(len(self.points))],
            },
            "line": None,
            "target": None,
        }

        if self.result:
            # Extend line beyond data points
            mass_min = min(masses) * 0.9
            mass_max = max(masses) * 1.1

            # If we have a target, extend to include it
            if self.target_freq_hz:
                target_mass = self.result.predict_mass_for_freq(self.target_freq_hz)
                if target_mass > 0:
                    mass_min = min(mass_min, target_mass * 0.95)
                    mass_max = max(mass_max, target_mass * 1.05)

            line_masses = np.linspace(mass_min, mass_max, 100)
            line_freqs = self.result.predict_freq(line_masses)

            data["line"] = {
                "mass_g": line_masses.tolist(),
                "freq_hz": line_freqs.tolist(),
                "equation": f"f = {self.result.slope:.3f}m + {self.result.intercept:.1f}",
                "r_squared": self.result.r_squared,
            }

        if self.target_freq_hz and self.result:
            target_mass = self.result.predict_mass_for_freq(self.target_freq_hz)
            data["target"] = {
                "freq_hz": self.target_freq_hz,
                "predicted_mass_g": target_mass,
            }

        return data

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plate_name": self.plate_name,
            "target_freq_hz": self.target_freq_hz,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlateTuningRegression":
        """Deserialize from dictionary."""
        reg = cls()
        reg.plate_name = d.get("plate_name", "Untitled Plate")
        reg.target_freq_hz = d.get("target_freq_hz")
        reg.points = [TuningPoint.from_dict(p) for p in d.get("points", [])]
        return reg


def quick_predict(
    points: List[Tuple[float, float]],  # [(mass_g, freq_hz), ...]
    target_freq_hz: float,
) -> Dict[str, float]:
    """
    Quick prediction without creating full objects.

    Args:
        points: List of (mass_g, freq_hz) tuples
        target_freq_hz: Target frequency

    Returns:
        Dict with prediction results
    """
    reg = PlateTuningRegression()
    for mass, freq in points:
        reg.add_point(TuningPoint(mass_g=mass, freq_hz=freq))
    reg.set_target(target_freq_hz)

    pred = reg.get_prediction()
    return pred if pred else {}

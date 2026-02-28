"""
Limit curve definitions and interpolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np


class LimitType(Enum):
    """Type of limit curve."""

    UPPER = "upper"  # Maximum allowed value
    LOWER = "lower"  # Minimum required value


@dataclass
class LimitPoint:
    """A single point on a limit curve."""

    frequency_hz: float
    value_db: float

    def __post_init__(self):
        if self.frequency_hz <= 0:
            raise ValueError(f"Frequency must be positive: {self.frequency_hz}")


@dataclass
class LimitCurve:
    """
    A frequency-dependent limit curve.

    Points are interpolated (log frequency, linear dB) between defined points.
    """

    name: str
    limit_type: LimitType
    points: List[LimitPoint] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        # Sort points by frequency
        self.points = sorted(self.points, key=lambda p: p.frequency_hz)

    @property
    def freq_range(self) -> Tuple[float, float]:
        """Get frequency range of the curve."""
        if not self.points:
            return (0.0, 0.0)
        return (self.points[0].frequency_hz, self.points[-1].frequency_hz)

    def get_limit_at_freq(self, freq_hz: float) -> Optional[float]:
        """
        Get the limit value at a specific frequency.

        Uses log-linear interpolation between points.
        Returns None if frequency is outside the curve range.

        Args:
            freq_hz: Frequency in Hz

        Returns:
            Limit value in dB, or None if outside range
        """
        if not self.points:
            return None

        if len(self.points) == 1:
            return self.points[0].value_db

        # Check bounds
        if freq_hz < self.points[0].frequency_hz:
            return None
        if freq_hz > self.points[-1].frequency_hz:
            return None

        # Find bracketing points
        for i in range(len(self.points) - 1):
            if (
                self.points[i].frequency_hz
                <= freq_hz
                <= self.points[i + 1].frequency_hz
            ):
                return _interpolate_log_linear(
                    freq_hz,
                    self.points[i].frequency_hz,
                    self.points[i].value_db,
                    self.points[i + 1].frequency_hz,
                    self.points[i + 1].value_db,
                )

        return None

    def to_arrays(
        self,
        frequencies_hz: Optional[np.ndarray] = None,
        n_points: int = 100,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert curve to numpy arrays for plotting.

        Args:
            frequencies_hz: Specific frequencies to evaluate at
            n_points: Number of points if generating (log spaced)

        Returns:
            Tuple of (frequencies, values) arrays
        """
        if frequencies_hz is None:
            f_min, f_max = self.freq_range
            if f_min <= 0 or f_max <= 0:
                return np.array([]), np.array([])
            frequencies_hz = np.logspace(
                np.log10(f_min),
                np.log10(f_max),
                n_points,
            )

        values = np.array(
            [
                self.get_limit_at_freq(f)
                if self.get_limit_at_freq(f) is not None
                else np.nan
                for f in frequencies_hz
            ]
        )

        return frequencies_hz, values

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "limit_type": self.limit_type.value,
            "description": self.description,
            "points": [
                {"frequency_hz": p.frequency_hz, "value_db": p.value_db}
                for p in self.points
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LimitCurve":
        """Create from dictionary."""
        points = [
            LimitPoint(
                frequency_hz=p["frequency_hz"],
                value_db=p["value_db"],
            )
            for p in data.get("points", [])
        ]
        return cls(
            name=data["name"],
            limit_type=LimitType(data["limit_type"]),
            points=points,
            description=data.get("description", ""),
        )


def _interpolate_log_linear(
    freq: float,
    f1: float,
    v1: float,
    f2: float,
    v2: float,
) -> float:
    """
    Interpolate between two points using log frequency, linear value.

    Args:
        freq: Target frequency
        f1, v1: First point (frequency, value)
        f2, v2: Second point (frequency, value)

    Returns:
        Interpolated value
    """
    if f1 == f2:
        return v1

    # Log interpolation position
    log_f = math.log10(freq)
    log_f1 = math.log10(f1)
    log_f2 = math.log10(f2)

    t = (log_f - log_f1) / (log_f2 - log_f1)

    # Linear interpolation of values
    return v1 + t * (v2 - v1)


def create_limit_curve(
    name: str,
    limit_type: LimitType,
    frequencies_hz: List[float],
    values_db: List[float],
    description: str = "",
) -> LimitCurve:
    """
    Create a limit curve from frequency/value lists.

    Args:
        name: Curve name
        limit_type: UPPER or LOWER
        frequencies_hz: List of frequencies
        values_db: List of corresponding values
        description: Optional description

    Returns:
        LimitCurve
    """
    if len(frequencies_hz) != len(values_db):
        raise ValueError("Frequencies and values must have same length")

    points = [
        LimitPoint(frequency_hz=f, value_db=v)
        for f, v in zip(frequencies_hz, values_db)
    ]

    return LimitCurve(
        name=name,
        limit_type=limit_type,
        points=points,
        description=description,
    )


def interpolate_limit(
    curve: LimitCurve,
    frequencies_hz: np.ndarray,
) -> np.ndarray:
    """
    Interpolate limit curve at given frequencies.

    Args:
        curve: LimitCurve to interpolate
        frequencies_hz: Array of frequencies

    Returns:
        Array of limit values (NaN where undefined)
    """
    return np.array(
        [
            curve.get_limit_at_freq(f)
            if curve.get_limit_at_freq(f) is not None
            else np.nan
            for f in frequencies_hz
        ]
    )


def create_flat_limit(
    name: str,
    limit_type: LimitType,
    value_db: float,
    freq_min: float = 20.0,
    freq_max: float = 20000.0,
) -> LimitCurve:
    """
    Create a flat (constant) limit curve.

    Args:
        name: Curve name
        limit_type: UPPER or LOWER
        value_db: Constant limit value
        freq_min: Minimum frequency
        freq_max: Maximum frequency

    Returns:
        LimitCurve with constant value
    """
    return LimitCurve(
        name=name,
        limit_type=limit_type,
        points=[
            LimitPoint(frequency_hz=freq_min, value_db=value_db),
            LimitPoint(frequency_hz=freq_max, value_db=value_db),
        ],
        description=f"Flat {limit_type.value} limit at {value_db} dB",
    )


def create_sloped_limit(
    name: str,
    limit_type: LimitType,
    value_at_1khz_db: float,
    slope_db_per_octave: float,
    freq_min: float = 20.0,
    freq_max: float = 20000.0,
) -> LimitCurve:
    """
    Create a sloped limit curve (constant dB/octave).

    Args:
        name: Curve name
        limit_type: UPPER or LOWER
        value_at_1khz_db: Value at 1 kHz
        slope_db_per_octave: Slope in dB per octave (positive = rising with freq)
        freq_min: Minimum frequency
        freq_max: Maximum frequency

    Returns:
        LimitCurve with constant slope
    """
    # Calculate values at endpoints
    octaves_from_1khz_min = math.log2(freq_min / 1000.0)
    octaves_from_1khz_max = math.log2(freq_max / 1000.0)

    value_min = value_at_1khz_db + slope_db_per_octave * octaves_from_1khz_min
    value_max = value_at_1khz_db + slope_db_per_octave * octaves_from_1khz_max

    return LimitCurve(
        name=name,
        limit_type=limit_type,
        points=[
            LimitPoint(frequency_hz=freq_min, value_db=value_min),
            LimitPoint(frequency_hz=1000.0, value_db=value_at_1khz_db),
            LimitPoint(frequency_hz=freq_max, value_db=value_max),
        ],
        description=f"Sloped {limit_type.value} limit: {value_at_1khz_db} dB @ 1kHz, {slope_db_per_octave:+.1f} dB/octave",
    )

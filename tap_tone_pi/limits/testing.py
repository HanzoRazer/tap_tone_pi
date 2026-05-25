# INSTRUMENT CLASS: MEASUREMENT
"""
Limit testing and violation detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from .curves import LimitCurve, LimitType
from .masks import FrequencyMask


class TestVerdict(Enum):
    """Overall test verdict."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"  # Violations within margin


@dataclass
class LimitViolation:
    """A single limit violation."""

    frequency_hz: float
    measured_db: float
    limit_db: float
    limit_type: LimitType
    limit_name: str
    margin_db: float  # How much over/under (negative = violation)

    @property
    def severity_db(self) -> float:
        """Magnitude of violation (always positive for violations)."""
        return abs(self.margin_db) if self.margin_db < 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "frequency_hz": self.frequency_hz,
            "measured_db": self.measured_db,
            "limit_db": self.limit_db,
            "limit_type": self.limit_type.value,
            "limit_name": self.limit_name,
            "margin_db": self.margin_db,
            "severity_db": self.severity_db,
        }


@dataclass
class LimitTestResult:
    """Result of testing against limits."""

    verdict: TestVerdict
    violations: List[LimitViolation] = field(default_factory=list)
    worst_margin_db: float = float("inf")  # Smallest margin (most violated)
    average_margin_db: float = float("inf")
    points_tested: int = 0
    points_masked: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.verdict == TestVerdict.PASS

    @property
    def violation_count(self) -> int:
        """Number of violations."""
        return len(self.violations)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "verdict": self.verdict.value,
            "passed": self.passed,
            "violation_count": self.violation_count,
            "worst_margin_db": self.worst_margin_db,
            "average_margin_db": self.average_margin_db,
            "points_tested": self.points_tested,
            "points_masked": self.points_masked,
            "timestamp": self.timestamp,
            "violations": [v.to_dict() for v in self.violations],
        }


def check_against_limits(
    frequencies_hz: np.ndarray,
    values_db: np.ndarray,
    limits: List[LimitCurve],
    mask: Optional[FrequencyMask] = None,
    warn_margin_db: float = 3.0,
) -> LimitTestResult:
    """
    Check measured values against limit curves.

    Args:
        frequencies_hz: Array of frequencies
        values_db: Array of measured values in dB
        limits: List of limit curves to test against
        mask: Optional frequency mask to exclude regions
        warn_margin_db: Margin within which to warn (not fail)

    Returns:
        LimitTestResult with verdict and violations
    """
    if len(frequencies_hz) != len(values_db):
        raise ValueError("Frequencies and values must have same length")

    violations = []
    margins = []
    points_tested = 0
    points_masked = 0

    for freq, value in zip(frequencies_hz, values_db):
        # Check if masked
        if mask and mask.is_masked(freq):
            points_masked += 1
            continue

        points_tested += 1

        # Check each limit
        for limit in limits:
            limit_value = limit.get_limit_at_freq(freq)
            if limit_value is None:
                continue  # Frequency outside limit range

            # Calculate margin
            if limit.limit_type == LimitType.UPPER:
                # Upper limit: margin = limit - measured (positive = good)
                margin = limit_value - value
            else:
                # Lower limit: margin = measured - limit (positive = good)
                margin = value - limit_value

            margins.append(margin)

            # Check for violation (negative margin)
            if margin < 0:
                violations.append(
                    LimitViolation(
                        frequency_hz=freq,
                        measured_db=value,
                        limit_db=limit_value,
                        limit_type=limit.limit_type,
                        limit_name=limit.name,
                        margin_db=margin,
                    )
                )

    # Calculate statistics
    if margins:
        worst_margin = min(margins)
        avg_margin = sum(margins) / len(margins)
    else:
        worst_margin = float("inf")
        avg_margin = float("inf")

    # Determine verdict
    if not violations:
        verdict = TestVerdict.PASS
    elif worst_margin >= -warn_margin_db:
        # Violations within warning margin
        verdict = TestVerdict.WARN
    else:
        verdict = TestVerdict.FAIL

    return LimitTestResult(
        verdict=verdict,
        violations=violations,
        worst_margin_db=worst_margin,
        average_margin_db=avg_margin,
        points_tested=points_tested,
        points_masked=points_masked,
    )


def calculate_margin(
    frequencies_hz: np.ndarray,
    values_db: np.ndarray,
    limits: List[LimitCurve],
    mask: Optional[FrequencyMask] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate margin to limits at each frequency.

    Args:
        frequencies_hz: Array of frequencies
        values_db: Array of measured values
        limits: Limit curves
        mask: Optional frequency mask

    Returns:
        Tuple of (frequencies, margins) where margins are:
        - Positive: within limits
        - Negative: violation
        - NaN: masked or no limit defined
    """
    margins = np.full_like(values_db, np.nan)

    for i, (freq, value) in enumerate(zip(frequencies_hz, values_db)):
        if mask and mask.is_masked(freq):
            continue

        # Find most restrictive margin across all limits
        worst_margin = float("inf")

        for limit in limits:
            limit_value = limit.get_limit_at_freq(freq)
            if limit_value is None:
                continue

            if limit.limit_type == LimitType.UPPER:
                margin = limit_value - value
            else:
                margin = value - limit_value

            if margin < worst_margin:
                worst_margin = margin

        if worst_margin != float("inf"):
            margins[i] = worst_margin

    return frequencies_hz, margins


def find_violations(
    frequencies_hz: np.ndarray,
    values_db: np.ndarray,
    limits: List[LimitCurve],
    mask: Optional[FrequencyMask] = None,
) -> List[LimitViolation]:
    """
    Find all limit violations.

    Convenience function that returns just the violations list.

    Args:
        frequencies_hz: Array of frequencies
        values_db: Array of measured values
        limits: Limit curves
        mask: Optional frequency mask

    Returns:
        List of LimitViolation objects
    """
    result = check_against_limits(
        frequencies_hz=frequencies_hz,
        values_db=values_db,
        limits=limits,
        mask=mask,
    )
    return result.violations


def format_test_result(
    result: LimitTestResult,
    verbose: bool = False,
) -> str:
    """
    Format test result as human-readable string.

    Args:
        result: LimitTestResult to format
        verbose: Include detailed violation list

    Returns:
        Formatted string
    """
    lines = []

    # Verdict
    verdict_str = result.verdict.value.upper()
    lines.append(f"Limit Test: {verdict_str}")
    lines.append("")

    # Summary
    lines.append(f"Points tested: {result.points_tested}")
    if result.points_masked > 0:
        lines.append(f"Points masked: {result.points_masked}")

    if result.worst_margin_db != float("inf"):
        lines.append(f"Worst margin: {result.worst_margin_db:+.1f} dB")
        lines.append(f"Average margin: {result.average_margin_db:+.1f} dB")

    # Violations
    if result.violations:
        lines.append("")
        lines.append(f"Violations: {len(result.violations)}")

        if verbose:
            lines.append("")
            for v in result.violations:
                lines.append(
                    f"  {v.frequency_hz:.1f} Hz: {v.measured_db:.1f} dB "
                    f"(limit: {v.limit_db:.1f} dB, margin: {v.margin_db:+.1f} dB)"
                )

    return "\n".join(lines)

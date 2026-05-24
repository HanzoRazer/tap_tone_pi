# INSTRUMENT CLASS: DECISION SUPPORT
"""Typed confidence domain contract.

Defines explicit confidence domains to prevent conflation of measurement
confidence with advisory confidence.

The key invariant:
    - MEASUREMENT modules emit `signal` or `measurement` confidence
    - DECISION_SUPPORT modules emit `interpretive` or `recommendation` confidence
    - These domains must not cross without explicit authority

See: docs/AGE_CONSTITUTIONAL_CONTRACT.md
     docs/ADR-0010-guidance-authority-boundary.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List


class ConfidenceDomain(str, Enum):
    """Domain of a confidence value.

    SIGNAL: Confidence in signal detection (SNR, peak extraction)
    MEASUREMENT: Confidence in measurement validity (repeatability, calibration)
    INTERPRETIVE: Confidence in interpretation (pattern matching, anomaly)
    RECOMMENDATION: Confidence in recommendation utility (user relevance)
    """

    SIGNAL = "signal"
    MEASUREMENT = "measurement"
    INTERPRETIVE = "interpretive"
    RECOMMENDATION = "recommendation"


# Domains reserved for MEASUREMENT authority
MEASUREMENT_DOMAINS = frozenset({
    ConfidenceDomain.SIGNAL,
    ConfidenceDomain.MEASUREMENT,
})

# Domains allowed for DECISION_SUPPORT authority
ADVISORY_DOMAINS = frozenset({
    ConfidenceDomain.INTERPRETIVE,
    ConfidenceDomain.RECOMMENDATION,
})


@dataclass(frozen=True)
class TypedConfidenceV1:
    """Confidence value with explicit domain.

    This contract prevents accidental authority escalation by ensuring
    confidence values are tagged with their semantic domain.

    Attributes:
        value: Confidence in [0.0, 1.0]
        domain: Which domain this confidence applies to
        source: Component that produced this confidence (e.g., "wolf_beat_model")

    Example:
        TypedConfidenceV1(
            value=0.85,
            domain=ConfidenceDomain.INTERPRETIVE,
            source="wolf_beat_model"
        )
    """

    value: float
    domain: ConfidenceDomain
    source: str = ""

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence value must be in [0.0, 1.0], got {self.value}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "value": self.value,
            "domain": self.domain.value,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TypedConfidenceV1":
        """Deserialize from dict."""
        return cls(
            value=float(d["value"]),
            domain=ConfidenceDomain(d["domain"]),
            source=str(d.get("source", "")),
        )

    def is_advisory_domain(self) -> bool:
        """Returns True if this confidence is from an advisory domain."""
        return self.domain in ADVISORY_DOMAINS

    def is_measurement_domain(self) -> bool:
        """Returns True if this confidence is from a measurement domain."""
        return self.domain in MEASUREMENT_DOMAINS

    def validate_for_advisory(self) -> List[str]:
        """Validate that this confidence is appropriate for advisory use.

        Returns list of errors (empty if valid).
        """
        errors: List[str] = []
        if self.domain in MEASUREMENT_DOMAINS:
            errors.append(
                f"Advisory systems cannot emit {self.domain.value} confidence. "
                f"Use {ConfidenceDomain.INTERPRETIVE.value} or "
                f"{ConfidenceDomain.RECOMMENDATION.value} instead."
            )
        return errors


__all__ = [
    "ConfidenceDomain",
    "TypedConfidenceV1",
    "MEASUREMENT_DOMAINS",
    "ADVISORY_DOMAINS",
]

# INSTRUMENT CLASS: DECISION SUPPORT
"""Advisory authority contract.

Defines explicit authority metadata for advisory/guidance outputs.
Every directive must declare what authority it claims (and does not claim).

This prevents advisory systems from accidentally inheriting measurement
authority or producing outputs that contaminate the provenance chain.

See: docs/ADR-0010-guidance-authority-boundary.md
     docs/AGE_CONSTITUTIONAL_CONTRACT.md
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class AuthorityClass(str, Enum):
    """Authority class of an output.

    MEASUREMENT: Calibrated facts that may enter measurement exports
    PROVENANCE: Process metadata (timestamps, calibration records)
    DECISION_SUPPORT: Advisory outputs that guide attention
    INTERPRETIVE: Value judgments (reserved for future use)
    """

    MEASUREMENT = "measurement"
    PROVENANCE = "provenance"
    DECISION_SUPPORT = "decision_support"
    INTERPRETIVE = "interpretive"


class GuidanceScope(str, Enum):
    """Scope of guidance within DECISION_SUPPORT class.

    ATTENTION_GUIDANCE: Point, highlight, prioritize, suggest inspection
    EXPLANATION: Summarize, explain measurement quality issues
    WORKFLOW_HINT: Suggest next measurement step
    """

    ATTENTION_GUIDANCE = "attention_guidance"
    EXPLANATION = "explanation"
    WORKFLOW_HINT = "workflow_hint"


@dataclass(frozen=True)
class AdvisoryAuthorityV1:
    """Explicit authority declaration for advisory outputs.

    This contract makes the limitations of guidance outputs machine-readable
    and auditable. Every directive should carry this metadata.

    Attributes:
        authority_class: The authority class (always DECISION_SUPPORT for AGE)
        authority_scope: The guidance scope within that class
        can_establish_truth: Whether this output may establish acoustic truth
        can_modify_measurement: Whether this output may change measurement state
        can_enter_measurement_export: Whether this output may appear in viewer_pack_v1
    """

    authority_class: AuthorityClass
    authority_scope: GuidanceScope
    can_establish_truth: bool = False
    can_modify_measurement: bool = False
    can_enter_measurement_export: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "authority_class": self.authority_class.value,
            "authority_scope": self.authority_scope.value,
            "can_establish_truth": self.can_establish_truth,
            "can_modify_measurement": self.can_modify_measurement,
            "can_enter_measurement_export": self.can_enter_measurement_export,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AdvisoryAuthorityV1":
        """Deserialize from dict."""
        return cls(
            authority_class=AuthorityClass(d["authority_class"]),
            authority_scope=GuidanceScope(d["authority_scope"]),
            can_establish_truth=d.get("can_establish_truth", False),
            can_modify_measurement=d.get("can_modify_measurement", False),
            can_enter_measurement_export=d.get("can_enter_measurement_export", False),
        )

    def validate(self) -> list[str]:
        """Validate authority invariants. Returns list of errors."""
        errors: list[str] = []

        # DECISION_SUPPORT cannot establish truth
        if self.authority_class == AuthorityClass.DECISION_SUPPORT:
            if self.can_establish_truth:
                errors.append(
                    "DECISION_SUPPORT authority cannot establish truth"
                )
            if self.can_enter_measurement_export:
                errors.append(
                    "DECISION_SUPPORT authority cannot enter measurement export"
                )

        # MEASUREMENT authority has inverse constraints
        if self.authority_class == AuthorityClass.MEASUREMENT:
            if not self.can_establish_truth:
                errors.append(
                    "MEASUREMENT authority must be able to establish truth"
                )
            if not self.can_enter_measurement_export:
                errors.append(
                    "MEASUREMENT authority must be able to enter measurement export"
                )

        return errors


# ---------------------------------------------------------------------------
# Pre-defined authority constants for common use cases
# ---------------------------------------------------------------------------

AGE_ATTENTION_AUTHORITY = AdvisoryAuthorityV1(
    authority_class=AuthorityClass.DECISION_SUPPORT,
    authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
    can_establish_truth=False,
    can_modify_measurement=False,
    can_enter_measurement_export=False,
)

AGE_EXPLANATION_AUTHORITY = AdvisoryAuthorityV1(
    authority_class=AuthorityClass.DECISION_SUPPORT,
    authority_scope=GuidanceScope.EXPLANATION,
    can_establish_truth=False,
    can_modify_measurement=False,
    can_enter_measurement_export=False,
)

AGE_WORKFLOW_AUTHORITY = AdvisoryAuthorityV1(
    authority_class=AuthorityClass.DECISION_SUPPORT,
    authority_scope=GuidanceScope.WORKFLOW_HINT,
    can_establish_truth=False,
    can_modify_measurement=False,
    can_enter_measurement_export=False,
)


__all__ = [
    "AuthorityClass",
    "GuidanceScope",
    "AdvisoryAuthorityV1",
    "AGE_ATTENTION_AUTHORITY",
    "AGE_EXPLANATION_AUTHORITY",
    "AGE_WORKFLOW_AUTHORITY",
]

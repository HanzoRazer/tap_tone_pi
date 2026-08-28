# INSTRUMENT CLASS: MEASUREMENT
"""Boot-time self-test threshold — the one output that runs on the instrument.

It does not run in the audio callback. It runs once at boot with the input muted
and catches what a design budget cannot: a cold joint on the clock line, a
converter that came up in the wrong clock mode, a regulator oscillating.

**The margin is policy, not physics.** The source used a bare ``6.0`` default,
and a bare default in a scientific record becomes a constant by attrition — cited
once, then twice, then defended. Here the margin carries its own provenance, so a
reader can see whether it was proposed, assumed, or measured across healthy
units.

**Standard library only.** See :mod:`.quantities`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .noise import NoiseBudget
from .quantities import Provenance, Quantity

__all__ = [
    "DEFAULT_MARGIN_DB",
    "SelfTestThresholdPolicy",
    "SelfTestThresholds",
    "self_test_thresholds",
]

DEFAULT_MARGIN_DB = 6.0
"""The source's default. ``PROPOSED`` until a population of healthy units says otherwise."""


@dataclass(frozen=True)
class SelfTestThresholdPolicy:
    """How much worse than the design budget a healthy unit may measure.

    Separated from the threshold itself so the *policy* and the *derived number*
    do not share a provenance. The expected floor is `DERIVED` from the noise
    budget; the margin is a judgement about acceptable spread and starts life
    `PROPOSED`.
    """

    allowed_margin_db: Quantity = None  # type: ignore[assignment]
    duration_s: float = 3.0
    input_state: str = "shorted_or_muted"

    def __post_init__(self) -> None:
        if self.allowed_margin_db is None:
            object.__setattr__(
                self,
                "allowed_margin_db",
                Quantity(
                    DEFAULT_MARGIN_DB,
                    "dB",
                    Provenance.PROPOSED,
                    "source default; not a measured population spread",
                ),
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed_margin_db": self.allowed_margin_db.as_dict(),
            "duration_s": self.duration_s,
            "input_state": self.input_state,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SelfTestThresholdPolicy:
        return cls(
            allowed_margin_db=Quantity.from_dict(payload["allowed_margin_db"]),
            duration_s=float(payload.get("duration_s", 3.0)),
            input_state=str(payload.get("input_state", "shorted_or_muted")),
        )


@dataclass(frozen=True)
class SelfTestThresholds:
    """A runtime threshold derived from a design-time budget."""

    test: str
    expected_noise_floor_dbfs: float
    fail_above_dbfs: float
    limiter_at_design: str
    policy: SelfTestThresholdPolicy
    action_on_fail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "test": self.test,
            "expected_noise_floor_dbfs": self.expected_noise_floor_dbfs,
            "expected_noise_floor_provenance": Provenance.DERIVED.value,
            "fail_above_dbfs": self.fail_above_dbfs,
            "fail_above_provenance": Provenance.DERIVED.value,
            "limiter_at_design": self.limiter_at_design,
            "policy": self.policy.as_dict(),
            "action_on_fail": self.action_on_fail,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SelfTestThresholds:
        return cls(
            test=str(payload["test"]),
            expected_noise_floor_dbfs=float(payload["expected_noise_floor_dbfs"]),
            fail_above_dbfs=float(payload["fail_above_dbfs"]),
            limiter_at_design=str(payload["limiter_at_design"]),
            policy=SelfTestThresholdPolicy.from_dict(payload["policy"]),
            action_on_fail=str(payload["action_on_fail"]),
        )


def self_test_thresholds(
    budget: NoiseBudget, policy: SelfTestThresholdPolicy | None = None
) -> SelfTestThresholds:
    """Convert a design-time noise budget into a boot-time threshold."""
    policy = policy or SelfTestThresholdPolicy()
    expected_floor_dbfs = -budget.combined_snr_db
    return SelfTestThresholds(
        test="boot_noise_floor",
        expected_noise_floor_dbfs=expected_floor_dbfs,
        fail_above_dbfs=expected_floor_dbfs + float(policy.allowed_margin_db),
        limiter_at_design=budget.limiter,
        policy=policy,
        action_on_fail=(
            "Do not accept a session. Report the measured floor and the expected "
            "floor. A floor above threshold means the assembled instrument does "
            "not match the design budget."
        ),
    )

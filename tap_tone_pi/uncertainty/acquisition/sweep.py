# INSTRUMENT CLASS: MEASUREMENT
"""Stage 1 sweep limits — the input an operator can silently get wrong.

Sweeping faster than a resonance can respond smears the peak, shifts it, and
reads its amplitude low. Nothing in the captured data says this happened; the
spectrum simply comes back wrong in a plausible-looking way.

    τ         = Q / (π·f)
    dwell_min = k · τ
    BW_½      = f / Q
    rate_max  = BW_½² / safety

**These are advisory outputs.** DO-107 §4.8: they are computed and reported and
they do **not** drive the excitation system. Turning them into acquisition
behavior is a successor order, and a long computed sweep time is a constraint
result rather than a product requirement.

``Q`` is the binding parameter and is normally ``PROPOSED``. Its provenance
travels with the result, because limits derived from a guessed Q are a guess with
units on it.

**Standard library only.** See :mod:`.quantities`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .quantities import Provenance
from .specs import SweepSpec

__all__ = ["SweepLimits", "compute_sweep_limits"]


@dataclass(frozen=True)
class SweepLimits:
    """Advisory sweep constraints at one frequency.

    ``q_provenance`` is carried so a reader can see whether these limits rest on
    a measurement or on an assumption. It is the difference between a constraint
    and a guess.
    """

    at_frequency_hz: float
    assumed_q: float
    q_provenance: Provenance
    time_constant_s: float
    min_dwell_per_step_s: float
    half_power_bandwidth_hz: float
    max_sweep_rate_hz_per_s: float
    min_total_sweep_time_s: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_provisional(self) -> bool:
        """True while Q is not evidence-grade."""
        return not self.q_provenance.is_evidence

    def as_dict(self) -> dict[str, Any]:
        return {
            "at_frequency_hz": self.at_frequency_hz,
            "assumed_q": self.assumed_q,
            "q_provenance": self.q_provenance.value,
            "is_provisional": self.is_provisional,
            "time_constant_s": self.time_constant_s,
            "min_dwell_per_step_s": self.min_dwell_per_step_s,
            "half_power_bandwidth_hz": self.half_power_bandwidth_hz,
            "max_sweep_rate_hz_per_s": self.max_sweep_rate_hz_per_s,
            "min_total_sweep_time_s": self.min_total_sweep_time_s,
            "notes": list(self.notes),
        }


def compute_sweep_limits(sweep: SweepSpec, f_hz: float) -> SweepLimits:
    """Modal time constant, dwell, bandwidth and rate limits at ``f_hz``."""
    q = float(sweep.expected_q)
    if q <= 0 or f_hz <= 0:
        raise ValueError("Q and frequency must be positive")

    tau = q / (math.pi * f_hz)
    dwell_min = sweep.settle_time_constants * tau
    half_power_bw = f_hz / q
    rate_max = (half_power_bw**2) / sweep.sweep_safety_factor

    span = float(sweep.f_stop_hz) - float(sweep.f_start_hz)
    min_sweep_time = span / rate_max if rate_max > 0 else float("inf")

    notes = [
        "Q is the binding parameter. If the true Q is higher than assumed, "
        "these limits are optimistic and the peak will read low."
    ]
    if not sweep.expected_q.provenance.is_evidence:
        notes.append(
            f"Q is {sweep.expected_q.provenance.value.upper()}, not measured. "
            "These limits are PRELIMINARY and inherit that status."
        )
    notes.append(
        "Advisory only. These limits do not drive the excitation system in this "
        "order; acquisition control is a successor order."
    )

    return SweepLimits(
        at_frequency_hz=f_hz,
        assumed_q=q,
        q_provenance=sweep.expected_q.provenance,
        time_constant_s=tau,
        min_dwell_per_step_s=dwell_min,
        half_power_bandwidth_hz=half_power_bw,
        max_sweep_rate_hz_per_s=rate_max,
        min_total_sweep_time_s=min_sweep_time,
        notes=tuple(notes),
    )

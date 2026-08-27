# INSTRUMENT CLASS: MEASUREMENT
"""Chain-level frequency budget: four contributors, reported separately.

The separation is the point. The usual outcome is that both electronic terms are
negligible and the physical term dominates by orders of magnitude — which is the
finding that changes what an operator does, and which disappears the moment the
terms are summed into one number.

Authority boundaries, because this is the one area where the repository already
held a conflict (see ``docs/ACQUISITION_BUDGET_AUTHORITY.md``):

**Bin resolution is canonically owned by**
:func:`tap_tone_pi.uncertainty.frequency.compute_frequency_resolution`. This
module does **not** become a second authority for it. It evaluates the elementary
identity ``Δf = 1/T`` locally because importing the canonical implementation
would pull NumPy into the instrument runtime and violate the dependency boundary.
Agreement between the two is pinned by an integration test. The same principle
applies wherever an existing authority cannot be imported into the stdlib core.

**The estimator floor is a candidate, not a certified bound.** It is carried
faithfully from the acquisition source and is deliberately *not* called a
Cramér–Rao lower bound. ``core/session_diff.py`` computes a different expression
under that name; the conflict is recorded as **B-020** and is not resolved here,
because the newer acquisition mathematics material carries an acknowledged
factor-of-two and SNR-convention discrepancy around exactly this term. Promoting
either expression now would settle by appearance rather than by derivation.

**Standard library only.** See :mod:`.quantities`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .noise import rss
from .specs import CaptureSpec, ClockSpec, SpecimenSpec

__all__ = [
    "FrequencyBudget",
    "estimator_floor_candidate_hz",
    "clock_scale_error_hz",
    "frequency_budget",
]


def clock_scale_error_hz(mode_frequency_hz: float, accuracy_ppm: float) -> float:
    """Systematic frequency-scale error from clock accuracy.

    A fractional clock error scales *every* measured frequency by the same
    proportion. This is not jitter and never combines with it: jitter is random
    and raises the noise floor, accuracy is systematic and moves the answer.
    """
    return mode_frequency_hz * accuracy_ppm * 1e-6


def estimator_floor_candidate_hz(
    record_length_s: float, n_samples: int, snr_db: float
) -> float:
    """Single-tone estimator floor — **candidate expression, source formula**.

    ``(1 / (π·T)) · √(6 / (SNR_linear · N))``, with ``SNR_linear = 10^(SNR_dB/10)``.

    Reproduced from the acquisition-budget source for parity. **Its authority
    status is open.** It is not labelled a Cramér–Rao lower bound here, for two
    reasons recorded under B-020: another site in this repository computes a
    different expression under that name, and the newer acquisition mathematics
    material flags an unresolved factor-of-two and SNR-convention question about
    this very term while marking itself not source-verified.

    Whatever it is, it is a *lower bound on an estimator* rather than an achieved
    precision, so it is reported as ``DERIVED`` and never as ``MEASURED``.
    """
    if record_length_s <= 0:
        raise ValueError("record_length_s must be positive")
    n = max(n_samples, 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    return (1.0 / (math.pi * record_length_s)) * math.sqrt(6.0 / (snr_lin * n))


@dataclass(frozen=True)
class FrequencyBudget:
    """Stage 5 + Stage 7 result.

    ``physical_repeatability_hz`` of ``None`` means unmeasured, and
    ``combined_hz`` is then an **electronic lower bound** rather than a
    measurement uncertainty. The distinction is carried in ``notes`` and in
    :attr:`is_electronic_lower_bound` rather than left for a reader to infer.
    """

    mode_frequency_hz: float
    clock_error_hz: float
    bin_width_hz: float
    estimator_floor_hz: float
    physical_repeatability_hz: float | None
    combined_hz: float
    dominant: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_electronic_lower_bound(self) -> bool:
        """True when physical repeatability was not supplied."""
        return self.physical_repeatability_hz is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode_frequency_hz": self.mode_frequency_hz,
            "clock_error_hz": self.clock_error_hz,
            "bin_width_hz": self.bin_width_hz,
            "estimator_floor_hz": self.estimator_floor_hz,
            "estimator_floor_status": "candidate_source_formula",
            "physical_repeatability_hz": self.physical_repeatability_hz,
            "combined_hz": self.combined_hz,
            "is_electronic_lower_bound": self.is_electronic_lower_bound,
            "dominant": self.dominant,
            "notes": list(self.notes),
        }


def frequency_budget(
    clock: ClockSpec,
    capture: CaptureSpec,
    specimen: SpecimenSpec,
    snr_db: float,
) -> FrequencyBudget:
    """Four contributors to the uncertainty on a measured mode frequency."""
    notes: list[str] = []
    f = float(specimen.mode_frequency_hz)

    clock_err = clock_scale_error_hz(f, float(clock.accuracy_ppm))
    bin_w = capture.bin_width_hz()
    estimator_floor = estimator_floor_candidate_hz(
        float(capture.record_length_s), capture.n_samples(), snr_db
    )

    phys = (
        float(specimen.physical_repeatability_hz)
        if specimen.physical_repeatability_hz is not None
        else None
    )

    # NOTE (source parity): when peak interpolation is enabled the source sets
    # the "spectral_resolution" contributor to the estimator floor rather than
    # to the bin width, while also carrying "estimator_floor" as its own entry.
    # The estimator term therefore enters the combination twice. This is
    # reproduced faithfully rather than corrected -- DO-107A establishes what the
    # existing calculator says; deciding what it ought to say is the
    # source-reconciliation work. See the parity report and B-021.
    contributors = {
        "clock_accuracy": clock_err,
        "spectral_resolution": (
            estimator_floor if capture.peak_interpolation else bin_w
        ),
        "estimator_floor": estimator_floor,
    }
    if phys is not None:
        contributors["physical_repeatability"] = phys

    combined = rss(*(v for v in contributors.values() if v is not None))
    dominant = max(contributors, key=lambda k: contributors[k])

    if phys is None:
        notes.append(
            "physical_repeatability_hz is not supplied. The reported combined "
            "figure is an ELECTRONIC lower bound and must not be quoted as "
            "measurement uncertainty. Measure the same plate across sessions "
            "with remounting to obtain it."
        )
    elif dominant == "physical_repeatability":
        notes.append(
            "Physical repeatability dominates. Improving the record length, the "
            "clock, or the converter changes nothing. Effort belongs on "
            "fixturing, coupling, and environmental control."
        )

    if 0 < clock_err < combined / 100.0:
        notes.append(
            f"Clock accuracy contributes {clock_err:.3g} Hz, under 1% of the "
            f"combined figure. A TCXO would not be worth its cost."
        )

    return FrequencyBudget(
        mode_frequency_hz=f,
        clock_error_hz=clock_err,
        bin_width_hz=bin_w,
        estimator_floor_hz=estimator_floor,
        physical_repeatability_hz=phys,
        combined_hz=combined,
        dominant=dominant,
        notes=tuple(notes),
    )

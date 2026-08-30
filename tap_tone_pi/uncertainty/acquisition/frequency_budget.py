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
from typing import Any, Mapping

from .noise import rss
from .quantities import FormulaStatus
from .specs import CaptureSpec, ClockSpec, SpecimenSpec

__all__ = [
    "AggregateContributor",
    "FrequencyBudget",
    "estimator_floor_candidate_hz",
    "clock_scale_error_hz",
    "frequency_budget",
]


@dataclass(frozen=True)
class AggregateContributor:
    """One value actually supplied to the combination.

    Kept as a **sequence rather than a mapping**, and carrying both the
    contributor slot and the reportable quantity that filled it, because those
    two are not always the same thing and the difference is load-bearing.

    Under B-021 the ``spectral_resolution`` slot is filled by the *estimator
    floor* rather than by the bin width, so the estimator enters the combination
    twice and the bin width enters not at all. A mapping keyed by conceptual
    quantity would collapse those two entries and hide it; the bin width would
    still be reported beside a combined figure it never touched.

    This makes the defect visible as data. When B-021 is repaired the change
    shows up as a different contributor composition rather than as an unexplained
    movement in ``combined_hz``.
    """

    role: str
    """The contributor slot in the combination."""

    source_quantity: str
    """Which reportable quantity supplied this value."""

    value_hz: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "source_quantity": self.source_quantity,
            "value_hz": self.value_hz,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AggregateContributor:
        return cls(
            role=str(payload["role"]),
            source_quantity=str(payload["source_quantity"]),
            value_hz=float(payload["value_hz"]),
        )


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
    combined_contributors: tuple[AggregateContributor, ...] = field(
        default_factory=tuple
    )
    """Exactly what was supplied to the combination, in order, duplicates kept.

    ``combined_hz`` is the root-sum-square of these values and of nothing else.
    A reportable quantity absent from this sequence did not contribute, however
    prominently it appears above.
    """

    estimator_floor_status: FormulaStatus = FormulaStatus.CANDIDATE_SOURCE_FORMULA
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
            "estimator_floor_status": self.estimator_floor_status.value,
            "physical_repeatability_hz": self.physical_repeatability_hz,
            "combined_hz": self.combined_hz,
            "is_electronic_lower_bound": self.is_electronic_lower_bound,
            "dominant": self.dominant,
            "combined_contributors": [c.as_dict() for c in self.combined_contributors],
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FrequencyBudget:
        return cls(
            mode_frequency_hz=float(payload["mode_frequency_hz"]),
            clock_error_hz=float(payload["clock_error_hz"]),
            bin_width_hz=float(payload["bin_width_hz"]),
            estimator_floor_hz=float(payload["estimator_floor_hz"]),
            physical_repeatability_hz=(
                None
                if payload.get("physical_repeatability_hz") is None
                else float(payload["physical_repeatability_hz"])
            ),
            combined_hz=float(payload["combined_hz"]),
            dominant=str(payload["dominant"]),
            combined_contributors=tuple(
                AggregateContributor.from_dict(c)
                for c in payload.get("combined_contributors", ())
            ),
            estimator_floor_status=FormulaStatus(
                payload.get("estimator_floor_status", "candidate_source_formula")
            ),
            notes=tuple(payload.get("notes", ())),
        )


def frequency_budget(
    clock: ClockSpec,
    capture: CaptureSpec,
    specimen: SpecimenSpec,
    snr_db: float,
) -> FrequencyBudget:
    """The contributors to the uncertainty on a measured mode frequency.

    How many there are depends on the configuration, and the count is not a
    fixed property of the model:

    * peak interpolation on  -- clock accuracy and the spectral resolution term
      (filled by the estimator floor): **two**, or three when the specimen
      supplies physical repeatability.
    * peak interpolation off -- clock accuracy, spectral resolution (filled by
      the bin width) and the estimator floor: **three**, or four with physical
      repeatability.

    Before DO-107M the interpolating case carried the estimator floor twice and
    so always reported three or four. Callers must read the sequence rather
    than assume a length.
    """
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

    # B-021, partial reconciliation (DO-107M).
    #
    # The archived source filled the "spectral_resolution" slot with the
    # estimator floor when peak interpolation was enabled *and* carried
    # "estimator_floor" as a second entry, so the estimator term entered the
    # root-sum-square twice. That duplication is provably wrong whatever the
    # estimator expression turns out to be, so it is removed here: the slot is
    # filled once, and the source quantity that filled it is named.
    #
    # What is NOT settled, and is deliberately not decided here:
    # whether ``bin_width_hz`` should also enter the aggregate when the
    # estimator floor is present. Restoring it would not be a de-duplication --
    # at TTP values the bin width is orders of magnitude above the clock error
    # and would dominate the result. Adding a dominant term is a positive
    # mathematical claim and it depends on the estimator model that B-020 has
    # not yet established. Removing a proven duplicate does not license it.
    # B-021 therefore stays open on that question alone. See D107M-04.
    #
    # Without interpolation the two entries are distinct quantities, not a
    # duplicate, and are left exactly as the source had them.
    contributors = [
        AggregateContributor("clock_accuracy", "clock_error_hz", clock_err),
    ]
    if capture.peak_interpolation:
        contributors.append(
            AggregateContributor(
                "spectral_resolution", "estimator_floor_hz", estimator_floor
            )
        )
    else:
        contributors.append(
            AggregateContributor("spectral_resolution", "bin_width_hz", bin_w)
        )
        contributors.append(
            AggregateContributor(
                "estimator_floor", "estimator_floor_hz", estimator_floor
            )
        )
    if phys is not None:
        contributors.append(
            AggregateContributor(
                "physical_repeatability", "physical_repeatability_hz", phys
            )
        )

    combined = rss(*(c.value_hz for c in contributors))
    dominant = max(contributors, key=lambda c: c.value_hz).role

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
        combined_contributors=tuple(contributors),
        notes=tuple(notes),
    )

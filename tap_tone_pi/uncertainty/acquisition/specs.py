# INSTRUMENT CLASS: MEASUREMENT
"""Acquisition-chain specifications (DO-107A).

Six records describing what a measurement session was configured with, mapped to
the acquisition model's stages:

===========================  =====  ==================================
:class:`SpecimenSpec`        0      the thing measured, and its geometry
:class:`SweepSpec`           1      driven excitation
:class:`FrontEndSpec`        2      conditioning
:class:`ConverterSpec`       3      digitization
:class:`ClockSpec`           5      timing
:class:`CaptureSpec`         6      what the acquisition recorded
===========================  =====  ==================================

**These carry inputs, never results.** Nothing here computes a budget; the
numerical work lives in the budget modules so that a specification stays a
statement about a rig rather than a cache of conclusions drawn from it.

All frozen. A specification that can be edited after a budget was computed from
it turns that budget into a record of nothing in particular.

**Standard library only** — see :mod:`.quantities` for why that boundary is not
negotiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .quantities import AcquisitionQuantityError, Quantity

__all__ = [
    "ConverterSpec",
    "ClockSpec",
    "FrontEndSpec",
    "CaptureSpec",
    "SweepSpec",
    "SpecimenSpec",
    "CLOCK_TOPOLOGIES",
]

# Recognised sample-clock arrangements. The distinction that matters is whether
# the resulting jitter is broadband and Gaussian or a discrete spur, because the
# noise budget may root-sum-square the first and may not the second.
CLOCK_TOPOLOGIES = ("local_xo", "host_fractional_n", "cleanup_pll")


def _require_positive(q: Quantity, name: str) -> None:
    if float(q) <= 0:
        raise AcquisitionQuantityError(
            f"{name} must be greater than zero, got {float(q)}"
        )


@dataclass(frozen=True)
class ConverterSpec:
    """Stage 3 — the converter itself.

    ``hp_corner_hz`` of ``None`` means **unmeasured**, which is itself a finding
    and not a synonym for zero: an AC-coupled input whose corner nobody has
    measured has unbounded phase error at the lowest modes, and E0 T3 exists to
    measure it.
    """

    name: str
    bits: int
    full_scale_vrms: Quantity
    thermal_snr_db: Quantity
    aperture_jitter_s: Quantity
    sample_rate_hz: Quantity
    ac_coupled: bool = True
    hp_corner_hz: Quantity | None = None
    anti_alias_filter: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.bits, int)
            or isinstance(self.bits, bool)
            or self.bits <= 0
        ):
            raise AcquisitionQuantityError(
                "ConverterSpec.bits must be a positive integer"
            )
        _require_positive(self.full_scale_vrms, "ConverterSpec.full_scale_vrms")
        _require_positive(self.aperture_jitter_s, "ConverterSpec.aperture_jitter_s")
        _require_positive(self.sample_rate_hz, "ConverterSpec.sample_rate_hz")
        if self.hp_corner_hz is not None:
            _require_positive(self.hp_corner_hz, "ConverterSpec.hp_corner_hz")

    def nyquist_hz(self) -> float:
        """Half the sample rate. A property of the configuration, not a budget."""
        return float(self.sample_rate_hz) / 2.0


@dataclass(frozen=True)
class ClockSpec:
    """Stage 5 — the sample clock.

    **Jitter and accuracy are different problems and are never merged.** Jitter
    is random and raises the noise floor; accuracy is systematic and scales every
    measured frequency. Improving one does nothing for the other.
    """

    name: str
    rms_jitter_s: Quantity
    accuracy_ppm: Quantity
    topology: str = "local_xo"
    spurious: bool = False

    def __post_init__(self) -> None:
        _require_positive(self.rms_jitter_s, "ClockSpec.rms_jitter_s")
        if float(self.accuracy_ppm) < 0:
            raise AcquisitionQuantityError("ClockSpec.accuracy_ppm cannot be negative")
        if self.topology not in CLOCK_TOPOLOGIES:
            raise AcquisitionQuantityError(
                f"ClockSpec.topology {self.topology!r} is not one of "
                + ", ".join(CLOCK_TOPOLOGIES)
            )

    def is_gaussian_model_valid(self) -> bool:
        """Whether jitter may be combined as broadband Gaussian noise.

        ``False`` for a fractional-N clock, whose jitter appears as discrete
        spurs. Root-sum-squaring a spur with broadband noise understates what a
        listener or a spectrum will see, so the budget reports rather than
        combines it.
        """
        return not self.spurious


@dataclass(frozen=True)
class FrontEndSpec:
    """Stage 2 — conditioning. At audio band this is usually the limiting term."""

    name: str
    input_referred_noise_v_per_rthz: Quantity
    gain_db: Quantity
    bandwidth_hz: Quantity

    def __post_init__(self) -> None:
        _require_positive(
            self.input_referred_noise_v_per_rthz,
            "FrontEndSpec.input_referred_noise_v_per_rthz",
        )
        _require_positive(self.bandwidth_hz, "FrontEndSpec.bandwidth_hz")


@dataclass(frozen=True)
class CaptureSpec:
    """Stage 6 — what the acquisition actually recorded."""

    record_length_s: Quantity
    sample_rate_hz: Quantity
    window: str = "hann"
    peak_interpolation: bool = True

    def __post_init__(self) -> None:
        _require_positive(self.record_length_s, "CaptureSpec.record_length_s")
        _require_positive(self.sample_rate_hz, "CaptureSpec.sample_rate_hz")

    def n_samples(self) -> int:
        return int(round(float(self.record_length_s) * float(self.sample_rate_hz)))

    def bin_width_hz(self) -> float:
        """Raw spectral resolution, ``1 / T``.

        The canonical bin-resolution function is
        :func:`tap_tone_pi.uncertainty.frequency.compute_frequency_resolution`,
        which computes the same quantity as ``sample_rate / fft_size``. It is not
        called from here: it imports :mod:`tap_tone_pi.uncertainty.budget`, which
        imports NumPy, and this module must stay importable on the instrument.

        The two are held in agreement by test rather than by call — see the
        agreement test in the acquisition test module. Delegation to the
        canonical function happens at the integration boundary, on the same
        pattern as the modulus adapter.
        """
        return 1.0 / float(self.record_length_s)


@dataclass(frozen=True)
class SweepSpec:
    """Stage 1 — driven excitation. Sweeping too fast smears the peak.

    ``expected_q`` is the binding parameter and is almost always ``PROPOSED``
    until measured. Its provenance travels into the sweep limits, because limits
    computed from a guessed Q are a guess with units.
    """

    f_start_hz: Quantity
    f_stop_hz: Quantity
    expected_q: Quantity
    settle_time_constants: float = 3.0
    sweep_safety_factor: float = 4.0

    def __post_init__(self) -> None:
        _require_positive(self.f_start_hz, "SweepSpec.f_start_hz")
        _require_positive(self.f_stop_hz, "SweepSpec.f_stop_hz")
        _require_positive(self.expected_q, "SweepSpec.expected_q")
        if float(self.f_stop_hz) <= float(self.f_start_hz):
            raise AcquisitionQuantityError(
                "SweepSpec.f_stop_hz must be above f_start_hz"
            )
        if self.settle_time_constants <= 0 or self.sweep_safety_factor <= 0:
            raise AcquisitionQuantityError(
                "SweepSpec settle_time_constants and sweep_safety_factor must be positive"
            )


@dataclass(frozen=True)
class SpecimenSpec:
    """Stage 0 — the thing being measured, and the geometry the modulus depends on.

    For a plate, ``f ∝ (t / L²)·√(E / (ρ(1 − ν²)))``, so ``E ∝ f² L⁴ ρ / t²``.
    The propagation of that relationship is **not** implemented here or anywhere
    in this package: :func:`tap_tone_pi.uncertainty.stiffness.compute_tap_tone_moe_uncertainty`
    is canonical for it and the acquisition modulus adapter delegates.

    ``physical_repeatability_hz`` of ``None`` means **unmeasured**, and there is
    deliberately no default. Session-to-session variation from remounting,
    coupling, temperature and moisture routinely dominates every electronic term
    combined; supplying a plausible number would make a budget look complete
    while quietly resting on a figure nobody observed.
    """

    name: str
    mode_frequency_hz: Quantity
    length_m: Quantity
    length_uncertainty_m: Quantity
    thickness_m: Quantity
    thickness_uncertainty_m: Quantity
    density_kg_m3: Quantity
    density_uncertainty_kg_m3: Quantity
    physical_repeatability_hz: Quantity | None = None

    def __post_init__(self) -> None:
        for name in (
            "mode_frequency_hz",
            "length_m",
            "thickness_m",
            "density_kg_m3",
        ):
            _require_positive(getattr(self, name), f"SpecimenSpec.{name}")
        for name in (
            "length_uncertainty_m",
            "thickness_uncertainty_m",
            "density_uncertainty_kg_m3",
        ):
            if float(getattr(self, name)) < 0:
                raise AcquisitionQuantityError(
                    f"SpecimenSpec.{name} cannot be negative"
                )
        if self.physical_repeatability_hz is not None:
            if float(self.physical_repeatability_hz) < 0:
                raise AcquisitionQuantityError(
                    "SpecimenSpec.physical_repeatability_hz cannot be negative"
                )

    def has_measured_repeatability(self) -> bool:
        """Whether a full uncertainty claim is possible at all.

        ``False`` does not mean the budget is wrong — it means the frequency
        figure is an electronic lower bound rather than a measurement uncertainty.
        """
        return self.physical_repeatability_hz is not None


def spec_quantities(spec: Any) -> list[Quantity]:
    """Every :class:`Quantity` reachable from a specification, in field order.

    Used by the provenance summary. Kept here rather than in the budget so that
    adding a field to a specification cannot silently escape the provenance
    count — the walk follows ``__dataclass_fields__`` rather than a hand-written
    list that would need remembering.
    """
    found: list[Quantity] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, Quantity):
            found.append(obj)
        elif hasattr(obj, "__dataclass_fields__"):
            for name in obj.__dataclass_fields__:
                walk(getattr(obj, name))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)

    walk(spec)
    return found

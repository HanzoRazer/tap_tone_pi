# INSTRUMENT CLASS: MEASUREMENT
"""Stage 3 noise budget: four independent terms, with the dominant one named.

The naming is the product. A combined SNR figure without a limiter is not
actionable — an operator cannot tell from it whether a better clock, a quieter
preamp or a different converter would change anything, and on an audio-band
instrument the answer is almost never the clock.

**Error mechanisms are kept separate and are never merged into one "ADC error"
term.** Jitter, quantization, converter thermal noise and front-end noise combine
on noise power because they are independent and broadband. Aliasing does not
belong in that sum at all — it is a different mechanism with a different remedy —
and a fractional-N clock's discrete spurs must not be root-sum-squared as though
they were Gaussian.

**Standard library only.** See :mod:`.quantities`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from .specs import ClockSpec, ConverterSpec, FrontEndSpec

__all__ = [
    "NoiseBudget",
    "jitter_snr_db",
    "jitter_budget_s",
    "quantization_snr_db",
    "combine_snr_db",
    "rss",
    "front_end_output_noise_vrms",
    "front_end_snr_db",
    "noise_budget",
    "clock_topology_note",
]


def rss(*values: float) -> float:
    """Root-sum-square of independent terms.

    Elementary arithmetic rather than a modelling choice, evaluated locally so
    the acquisition core stays importable without NumPy. It is not a second
    authority for anything.
    """
    return math.sqrt(sum(v * v for v in values))


def jitter_snr_db(f_in_hz: float, tj_rms_s: float) -> float:
    """Jitter-limited SNR for a full-scale sine: ``SNR = -20·log₁₀(2π·f·t_j)``.

    Assumes uncorrelated Gaussian jitter. **Does not hold for the discrete spurs
    a fractional-N clock produces** — see :func:`clock_topology_note` and
    :meth:`~.specs.ClockSpec.is_gaussian_model_valid`.
    """
    if f_in_hz <= 0 or tj_rms_s <= 0:
        raise ValueError("f_in_hz and tj_rms_s must be positive")
    return -20.0 * math.log10(2.0 * math.pi * f_in_hz * tj_rms_s)


def jitter_budget_s(f_in_hz: float, target_snr_db: float) -> float:
    """Maximum total RMS jitter that still supports ``target_snr_db`` at ``f_in_hz``."""
    if f_in_hz <= 0:
        raise ValueError("f_in_hz must be positive")
    return (10.0 ** (-target_snr_db / 20.0)) / (2.0 * math.pi * f_in_hz)


def quantization_snr_db(bits: int) -> float:
    """Ideal quantization SNR for a full-scale sine: ``6.02·N + 1.76`` dB."""
    return 6.02 * bits + 1.76


def combine_snr_db(*snr_db: float) -> float:
    """Combine independent SNR terms on a noise-power basis."""
    terms = [s for s in snr_db if s is not None and math.isfinite(s)]
    if not terms:
        raise ValueError("no finite SNR terms to combine")
    power = sum(10.0 ** (-s / 10.0) for s in terms)
    return -10.0 * math.log10(power)


def front_end_output_noise_vrms(front_end: FrontEndSpec) -> float:
    """Input-referred noise density integrated over the band, times gain."""
    gain = 10.0 ** (float(front_end.gain_db) / 20.0)
    return (
        float(front_end.input_referred_noise_v_per_rthz)
        * math.sqrt(float(front_end.bandwidth_hz))
        * gain
    )


def front_end_snr_db(front_end: FrontEndSpec, full_scale_vrms: float) -> float:
    """Front-end SNR against the converter's full scale."""
    noise = front_end_output_noise_vrms(front_end)
    if noise <= 0:
        return float("inf")
    return 20.0 * math.log10(full_scale_vrms / noise)


@dataclass(frozen=True)
class NoiseBudget:
    """Stage 3 result. ``limiter`` is the field that makes it actionable."""

    f_in_hz: float
    terms_db: dict[str, float]
    combined_snr_db: float
    limiter: str
    limiter_share: float
    total_jitter_s: float
    jitter_headroom_db: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "f_in_hz": self.f_in_hz,
            "terms_db": dict(self.terms_db),
            "combined_snr_db": self.combined_snr_db,
            "limiter": self.limiter,
            # Unrounded for the same reason as ModulusBudget: the payload is a
            # contract, not a report. terms_db and combined_snr_db are already
            # rounded in the stored fields, which is source parity rather than
            # serialization loss.
            "limiter_share": self.limiter_share,
            "total_jitter_s": self.total_jitter_s,
            "jitter_headroom_db": self.jitter_headroom_db,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> NoiseBudget:
        return cls(
            f_in_hz=float(payload["f_in_hz"]),
            terms_db={k: float(v) for k, v in payload["terms_db"].items()},
            combined_snr_db=float(payload["combined_snr_db"]),
            limiter=str(payload["limiter"]),
            limiter_share=float(payload["limiter_share"]),
            total_jitter_s=float(payload["total_jitter_s"]),
            jitter_headroom_db=float(payload["jitter_headroom_db"]),
            notes=tuple(payload.get("notes", ())),
        )


def noise_budget(
    converter: ConverterSpec,
    clock: ClockSpec,
    front_end: FrontEndSpec | None,
    f_in_hz: float,
) -> NoiseBudget:
    """Four independent terms, combined on noise power, dominant one named."""
    notes: list[str] = []

    tj_total = rss(float(clock.rms_jitter_s), float(converter.aperture_jitter_s))

    terms = {
        "quantization": quantization_snr_db(converter.bits),
        "converter_thermal": float(converter.thermal_snr_db),
        "jitter": jitter_snr_db(f_in_hz, tj_total),
    }
    if front_end is not None:
        terms["front_end"] = front_end_snr_db(
            front_end, float(converter.full_scale_vrms)
        )

    combined = combine_snr_db(*terms.values())

    powers = {k: 10.0 ** (-v / 10.0) for k, v in terms.items()}
    total_power = sum(powers.values())
    limiter = max(powers, key=lambda k: powers[k])
    share = powers[limiter] / total_power

    # How much worse could the clock get before jitter starts to matter?
    non_jitter = combine_snr_db(*(v for k, v in terms.items() if k != "jitter"))
    headroom = terms["jitter"] - non_jitter

    if limiter != "jitter":
        notes.append(
            f"Jitter is not the limiting term at {f_in_hz:.4g} Hz "
            f"({headroom:.1f} dB below the {limiter} floor). "
            f"Clock improvement buys nothing here."
        )
    if not clock.is_gaussian_model_valid():
        notes.append(
            "Clock is marked spurious (fractional-N). Root-sum-square of a "
            "discrete spur with broadband jitter is NOT valid -- this figure "
            "understates audibility. Model the spur separately."
        )
    if not converter.anti_alias_filter:
        notes.append(
            "Converter has no input anti-alias filter. Out-of-band energy folds "
            "into the analysis band and is unrecoverable. With no filter there "
            "is also no bound on input slew rate, which is the mechanism by "
            "which jitter could matter here despite the headroom above. "
            "These are separate error mechanisms; do not merge them."
        )
    if converter.ac_coupled and converter.hp_corner_hz is None:
        notes.append(
            "Converter is AC-coupled and the high-pass corner is unmeasured. "
            "Phase error at the lowest modes is unbounded until it is."
        )

    return NoiseBudget(
        f_in_hz=f_in_hz,
        terms_db={k: round(v, 2) for k, v in terms.items()},
        combined_snr_db=round(combined, 2),
        limiter=limiter,
        limiter_share=share,
        total_jitter_s=tj_total,
        jitter_headroom_db=headroom,
        notes=tuple(notes),
    )


def clock_topology_note(clock: ClockSpec) -> str:
    """Human-readable statement of what the clock choice costs."""
    table = {
        "local_xo": "Local crystal, converter is clock master. Lowest jitter path.",
        "host_fractional_n": (
            "Host fractional-N divider drives the converter. Jitter is typically "
            "two to three orders worse than a local XO and is spurious rather "
            "than Gaussian."
        ),
        "cleanup_pll": "External clean-up PLL. Between the two.",
    }
    return table.get(clock.topology, f"Unrecognised topology: {clock.topology}")

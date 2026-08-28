"""
acquisition_budget.py — Stage 3 / Stage 7 uncertainty budget for the TTP
acquisition stack.

WHAT THIS IS
------------
The Jitter-to-SNR calculator, rebuilt as a chain component rather than a web
page, and extended to terminate in the units a decision is actually made in.

Placement in the nine-stage acquisition model:

    Stage 0  measurand & decision   -- caller supplies; this module consumes it
    Stage 2  conditioning           -- FrontEndSpec  (input-referred noise)
    Stage 3  digitization           -- ConverterSpec, ClockSpec -> noise_budget()
    Stage 5  timing                 -- ClockSpec.accuracy_ppm  -> clock_error()
    Stage 7  analysis               -- everything below the noise budget

It never runs inside a control loop and it never runs per sample. It runs once
per measurement session, consumes that session's parameters, and emits a record.

WHAT IT IS FOR
--------------
Two jobs, both design-time or session-time:

  1. Show which term actually limits the measurement. On an audio-band
     instrument the answer is almost never jitter, and the module is built to
     say so plainly rather than to always return PASS.

  2. Propagate to the decision. A luthier cannot act on "138 dB". They can act
     on "this rig distinguishes plates whose E_L differs by more than 1.8%".

PROVENANCE DISCIPLINE
---------------------
Every quantity carries a Provenance tag. A number typed into a slider and a
number read off a datasheet do not render identically, because one is
load-bearing and the other is a guess. Emitted records preserve the tag.

Consumers of the emitted dict must treat any budget containing PROPOSED inputs
as unvalidated. `AcquisitionBudget.is_evidence_grade()` enforces this.

Standard library only. No numpy, no scipy. It has to run on the instrument.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


__all__ = [
    "Provenance",
    "Quantity",
    "ConverterSpec",
    "ClockSpec",
    "FrontEndSpec",
    "CaptureSpec",
    "SweepSpec",
    "SpecimenSpec",
    "NoiseBudget",
    "FrequencyBudget",
    "ModulusBudget",
    "AcquisitionBudget",
    "jitter_snr_db",
    "jitter_budget_s",
    "quantization_snr_db",
    "combine_snr_db",
    "TTP_ANALYZER_PROFILE",
    "SMART_GUITAR_PROFILE",
]


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

class Provenance(str, Enum):
    """Where a number came from. Ordered weakest to strongest."""

    PROPOSED = "proposed"      # concept figure, no measurement behind it
    ASSUMED = "assumed"        # standard practice or engineering judgement
    DATASHEET = "datasheet"    # manufacturer document
    DERIVED = "derived"        # computed from other tagged quantities
    MEASURED = "measured"      # measured on this instrument

    @property
    def is_evidence(self) -> bool:
        return self in (Provenance.DATASHEET, Provenance.DERIVED, Provenance.MEASURED)


@dataclass(frozen=True)
class Quantity:
    """A number that knows its unit and where it came from."""

    value: float
    unit: str
    provenance: Provenance
    source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            object.__setattr__(self, "provenance", Provenance(self.provenance))

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "provenance": self.provenance.value,
            "source": self.source,
        }

    def __float__(self) -> float:
        return float(self.value)


def _q(x: Quantity | float, unit: str = "", prov: Provenance = Provenance.ASSUMED) -> Quantity:
    """Coerce a bare float into a Quantity so callers can be lazy at the edges."""
    if isinstance(x, Quantity):
        return x
    return Quantity(float(x), unit, prov, source="caller-supplied bare value")


# --------------------------------------------------------------------------
# Core relationships
# --------------------------------------------------------------------------

def jitter_snr_db(f_in_hz: float, tj_rms_s: float) -> float:
    """
    Jitter-limited SNR for a full-scale sine.

        SNR = -20 log10(2 pi f_in t_j)

    Assumes uncorrelated Gaussian jitter. Does NOT hold for the discrete spurs
    produced by a fractional-N clock -- see clock_topology_note().
    """
    if f_in_hz <= 0 or tj_rms_s <= 0:
        raise ValueError("f_in_hz and tj_rms_s must be positive")
    return -20.0 * math.log10(2.0 * math.pi * f_in_hz * tj_rms_s)


def jitter_budget_s(f_in_hz: float, target_snr_db: float) -> float:
    """Maximum total RMS jitter that still supports target_snr_db at f_in_hz."""
    if f_in_hz <= 0:
        raise ValueError("f_in_hz must be positive")
    return (10.0 ** (-target_snr_db / 20.0)) / (2.0 * math.pi * f_in_hz)


def quantization_snr_db(bits: int) -> float:
    """Ideal quantization SNR for a full-scale sine: 6.02 N + 1.76 dB."""
    return 6.02 * bits + 1.76


def combine_snr_db(*snr_db: float) -> float:
    """Combine independent SNR terms on a noise-power basis."""
    terms = [s for s in snr_db if s is not None and math.isfinite(s)]
    if not terms:
        raise ValueError("no finite SNR terms to combine")
    power = sum(10.0 ** (-s / 10.0) for s in terms)
    return -10.0 * math.log10(power)


def rss(*values: float) -> float:
    """Root-sum-square of independent terms."""
    return math.sqrt(sum(v * v for v in values))


# --------------------------------------------------------------------------
# Stage specifications
# --------------------------------------------------------------------------

@dataclass
class ConverterSpec:
    """Stage 3 -- the converter itself."""

    name: str
    bits: int
    full_scale_vrms: Quantity
    thermal_snr_db: Quantity            # datasheet SNR, the converter's own floor
    aperture_jitter_s: Quantity
    sample_rate_hz: Quantity
    ac_coupled: bool = True
    hp_corner_hz: Quantity | None = None   # None == unmeasured, which is itself a finding
    anti_alias_filter: bool = False

    def nyquist_hz(self) -> float:
        return float(self.sample_rate_hz) / 2.0


@dataclass
class ClockSpec:
    """Stage 5 -- the sample clock. Jitter and accuracy are different problems."""

    name: str
    rms_jitter_s: Quantity              # random -> noise floor
    accuracy_ppm: Quantity              # systematic -> frequency scale error
    topology: str = "local_xo"          # local_xo | host_fractional_n | cleanup_pll
    spurious: bool = False              # True for fractional-N: RSS is not valid

    def is_gaussian_model_valid(self) -> bool:
        return not self.spurious


@dataclass
class FrontEndSpec:
    """Stage 2 -- conditioning. At audio band this is usually the limiting term."""

    name: str
    input_referred_noise_v_per_rthz: Quantity
    gain_db: Quantity
    bandwidth_hz: Quantity

    def output_noise_vrms(self) -> float:
        gain = 10.0 ** (float(self.gain_db) / 20.0)
        return float(self.input_referred_noise_v_per_rthz) * math.sqrt(float(self.bandwidth_hz)) * gain

    def snr_db(self, full_scale_vrms: float) -> float:
        n = self.output_noise_vrms()
        if n <= 0:
            return float("inf")
        return 20.0 * math.log10(full_scale_vrms / n)


@dataclass
class CaptureSpec:
    """Stage 6 -- what the acquisition actually recorded."""

    record_length_s: Quantity
    sample_rate_hz: Quantity
    window: str = "hann"
    peak_interpolation: bool = True

    def n_samples(self) -> int:
        return int(round(float(self.record_length_s) * float(self.sample_rate_hz)))

    def bin_width_hz(self) -> float:
        return 1.0 / float(self.record_length_s)


@dataclass
class SweepSpec:
    """Stage 1 -- driven excitation. Sweeping too fast smears the peak."""

    f_start_hz: Quantity
    f_stop_hz: Quantity
    expected_q: Quantity                # plate modes: typically 30-80
    settle_time_constants: float = 3.0  # 3 tau ~= 95% settled
    sweep_safety_factor: float = 4.0


@dataclass
class SpecimenSpec:
    """
    Stage 0 -- the thing being measured, and the geometry the modulus depends on.

    For a plate,  f  proportional to  (t / L^2) * sqrt(E / (rho (1 - nu^2)))
    so            E  proportional to  f^2 L^4 rho / t^2
    """

    name: str
    mode_frequency_hz: Quantity
    length_m: Quantity
    length_uncertainty_m: Quantity
    thickness_m: Quantity
    thickness_uncertainty_m: Quantity
    density_kg_m3: Quantity
    density_uncertainty_kg_m3: Quantity
    # Session-to-session physical repeatability of the measured frequency.
    # Mic repositioning, coupling, temperature, moisture. MUST be measured.
    physical_repeatability_hz: Quantity | None = None


# --------------------------------------------------------------------------
# Stage 3 -- noise budget
# --------------------------------------------------------------------------

@dataclass
class NoiseBudget:
    f_in_hz: float
    terms_db: dict[str, float]
    combined_snb_db: float
    limiter: str
    limiter_share: float
    total_jitter_s: float
    jitter_headroom_db: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "f_in_hz": self.f_in_hz,
            "terms_db": self.terms_db,
            "combined_snr_db": self.combined_snb_db,
            "limiter": self.limiter,
            "limiter_share": round(self.limiter_share, 4),
            "total_jitter_s": self.total_jitter_s,
            "jitter_headroom_db": round(self.jitter_headroom_db, 2),
            "notes": self.notes,
        }


def noise_budget(
    converter: ConverterSpec,
    clock: ClockSpec,
    front_end: FrontEndSpec | None,
    f_in_hz: float,
) -> NoiseBudget:
    """
    Stage 3. Four independent terms, combined on noise power, with the dominant
    one named. The naming is the product -- a number without a limiter is not
    actionable.
    """
    notes: list[str] = []

    tj_total = rss(float(clock.rms_jitter_s), float(converter.aperture_jitter_s))

    terms = {
        "quantization": quantization_snr_db(converter.bits),
        "converter_thermal": float(converter.thermal_snr_db),
        "jitter": jitter_snr_db(f_in_hz, tj_total),
    }
    if front_end is not None:
        terms["front_end"] = front_end.snr_db(float(converter.full_scale_vrms))

    combined = combine_snr_db(*terms.values())

    powers = {k: 10.0 ** (-v / 10.0) for k, v in terms.items()}
    total_power = sum(powers.values())
    limiter = max(powers, key=powers.get)
    share = powers[limiter] / total_power

    # Headroom: how much worse could the clock get before jitter starts to matter?
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
        combined_snb_db=round(combined, 2),
        limiter=limiter,
        limiter_share=share,
        total_jitter_s=tj_total,
        jitter_headroom_db=headroom,
        notes=notes,
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


# --------------------------------------------------------------------------
# Stage 5 + Stage 7 -- frequency budget
# --------------------------------------------------------------------------

@dataclass
class FrequencyBudget:
    mode_frequency_hz: float
    clock_error_hz: float
    bin_width_hz: float
    estimator_floor_hz: float
    physical_repeatability_hz: float | None
    combined_hz: float
    dominant: str
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode_frequency_hz": self.mode_frequency_hz,
            "clock_error_hz": self.clock_error_hz,
            "bin_width_hz": self.bin_width_hz,
            "estimator_floor_hz": self.estimator_floor_hz,
            "physical_repeatability_hz": self.physical_repeatability_hz,
            "combined_hz": self.combined_hz,
            "dominant": self.dominant,
            "notes": self.notes,
        }


def frequency_budget(
    clock: ClockSpec,
    capture: CaptureSpec,
    specimen: SpecimenSpec,
    snr_db: float,
) -> FrequencyBudget:
    """
    Stage 7. Four contributors to the uncertainty on a measured mode frequency.

    Reported separately on purpose. The usual outcome is that the two
    electronic terms are negligible and the physical term dominates by orders
    of magnitude, which is the finding that changes what the operator does.
    """
    notes: list[str] = []
    f = float(specimen.mode_frequency_hz)

    # Systematic: a fractional clock error scales every measured frequency.
    clock_err = f * float(clock.accuracy_ppm) * 1e-6

    # Raw spectral resolution.
    bin_w = capture.bin_width_hz()

    # Estimator floor: single-tone Cramer-Rao bound, standard asymptotic form.
    # Marked DERIVED, not MEASURED -- it is a lower bound, not an achieved value.
    n = max(capture.n_samples(), 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    estimator_floor = (1.0 / (math.pi * float(capture.record_length_s))) * math.sqrt(
        6.0 / (snr_lin * n)
    )

    phys = (
        float(specimen.physical_repeatability_hz)
        if specimen.physical_repeatability_hz is not None
        else None
    )

    contributors = {
        "clock_accuracy": clock_err,
        "spectral_resolution": bin_w if not capture.peak_interpolation else estimator_floor,
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

    if clock_err > 0 and clock_err < combined / 100.0:
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
        notes=notes,
    )


# --------------------------------------------------------------------------
# Stage 1 -- sweep limits
# --------------------------------------------------------------------------

def compute_sweep_limits(sweep: SweepSpec, f_hz: float) -> dict[str, Any]:
    """
    The one input an operator can get wrong in a way that silently ruins the
    measurement. Sweeping faster than a resonance can respond smears the peak,
    shifts it, and reads its amplitude low.

        tau        = Q / (pi f)
        dwell_min  = k * tau
        rate_max   = (f / Q)^2 / safety
    """
    q = float(sweep.expected_q)
    if q <= 0 or f_hz <= 0:
        raise ValueError("Q and frequency must be positive")

    tau = q / (math.pi * f_hz)
    dwell_min = sweep.settle_time_constants * tau
    half_power_bw = f_hz / q
    rate_max = (half_power_bw ** 2) / sweep.sweep_safety_factor

    span = float(sweep.f_stop_hz) - float(sweep.f_start_hz)
    min_sweep_time = span / rate_max if rate_max > 0 else float("inf")

    return {
        "at_frequency_hz": f_hz,
        "assumed_q": q,
        "time_constant_s": tau,
        "min_dwell_per_step_s": dwell_min,
        "half_power_bandwidth_hz": half_power_bw,
        "max_sweep_rate_hz_per_s": rate_max,
        "min_total_sweep_time_s": min_sweep_time,
        "note": (
            "Q is the binding parameter. If the true Q is higher than assumed, "
            "these limits are optimistic and the peak will read low."
        ),
    }


# --------------------------------------------------------------------------
# Stage 7 -- terminate in the decision
# --------------------------------------------------------------------------

@dataclass
class ModulusBudget:
    relative_uncertainty: float
    contributions: dict[str, float]
    dominant: str
    smallest_resolvable_delta_pct: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_uncertainty": round(self.relative_uncertainty, 6),
            "relative_uncertainty_pct": round(self.relative_uncertainty * 100.0, 3),
            "contributions": {k: round(v, 6) for k, v in self.contributions.items()},
            "dominant": self.dominant,
            "smallest_resolvable_delta_pct": round(self.smallest_resolvable_delta_pct, 3),
            "notes": self.notes,
        }


def modulus_budget(specimen: SpecimenSpec, freq: FrequencyBudget) -> ModulusBudget:
    """
    Propagate to E_L, which is what the brace prescription consumes.

        E  proportional to  f^2 L^4 rho / t^2

        dE/E = sqrt( (2 df/f)^2 + (4 dL/L)^2 + (drho/rho)^2 + (2 dt/t)^2 )

    The sensitivity coefficients are the point. Length enters to the FOURTH
    power and thickness to the SECOND -- a luthier chasing frequency precision
    while measuring thickness with a ruler has the priorities backwards.
    """
    f = float(specimen.mode_frequency_hz)
    contributions = {
        "frequency": 2.0 * (freq.combined_hz / f),
        "length": 4.0 * (float(specimen.length_uncertainty_m) / float(specimen.length_m)),
        "density": float(specimen.density_uncertainty_kg_m3) / float(specimen.density_kg_m3),
        "thickness": 2.0 * (float(specimen.thickness_uncertainty_m) / float(specimen.thickness_m)),
    }

    total = rss(*contributions.values())
    dominant = max(contributions, key=lambda k: contributions[k])

    # Two plates are distinguishable when their difference exceeds the combined
    # uncertainty of two independent measurements.
    smallest_delta = total * math.sqrt(2.0) * 100.0

    notes = [
        f"Dominant term is {dominant} "
        f"({contributions[dominant] / total * 100.0:.0f}% of the total in quadrature)."
    ]
    if dominant in ("thickness", "length"):
        notes.append(
            "The dominant term is dimensional, not electronic. No improvement to "
            "the acquisition chain reduces this uncertainty. Better calipers will."
        )
    if freq.physical_repeatability_hz is None:
        notes.append(
            "Frequency term omits physical repeatability. This budget is "
            "OPTIMISTIC and is not evidence-grade."
        )

    return ModulusBudget(
        relative_uncertainty=total,
        contributions=contributions,
        dominant=dominant,
        smallest_resolvable_delta_pct=smallest_delta,
        notes=notes,
    )


# --------------------------------------------------------------------------
# Stage 3 -- boot-time self-test thresholds
# --------------------------------------------------------------------------

def self_test_thresholds(budget: NoiseBudget, margin_db: float = 6.0) -> dict[str, Any]:
    """
    Convert the design-time budget into a runtime threshold.

    This is the only part of this module whose output executes on the
    instrument. It does not run in the audio callback; it runs once at boot
    with the input muted, and it catches the failures a design budget cannot:
    a cold joint on the clock line, a converter that came up in the wrong
    clock mode, a regulator oscillating.
    """
    expected_floor_dbfs = -budget.combined_snb_db
    return {
        "test": "boot_noise_floor",
        "input_state": "shorted_or_muted",
        "duration_s": 3.0,
        "expected_noise_floor_dbfs": round(expected_floor_dbfs, 2),
        "fail_above_dbfs": round(expected_floor_dbfs + margin_db, 2),
        "margin_db": margin_db,
        "limiter_at_design": budget.limiter,
        "action_on_fail": (
            "Do not accept a session. Report the measured floor and the expected "
            "floor. A floor above threshold means the assembled instrument does "
            "not match the design budget."
        ),
    }


# --------------------------------------------------------------------------
# Aggregate record
# --------------------------------------------------------------------------

@dataclass
class AcquisitionBudget:
    """The emitted artefact. This is what attaches to a measurement."""

    profile: str
    converter: ConverterSpec
    clock: ClockSpec
    front_end: FrontEndSpec | None
    capture: CaptureSpec | None
    sweep: SweepSpec | None
    specimen: SpecimenSpec | None

    noise: NoiseBudget | None = None
    frequency: FrequencyBudget | None = None
    modulus: ModulusBudget | None = None
    sweep_limits: dict[str, Any] | None = None

    schema_version: str = "acquisition_budget_v1"

    def compute(self, f_in_hz: float | None = None) -> "AcquisitionBudget":
        f_in = f_in_hz
        if f_in is None and self.specimen is not None:
            f_in = float(self.specimen.mode_frequency_hz)
        if f_in is None:
            raise ValueError("f_in_hz required when no specimen is supplied")

        self.noise = noise_budget(self.converter, self.clock, self.front_end, f_in)

        if self.capture is not None and self.specimen is not None:
            self.frequency = frequency_budget(
                self.clock, self.capture, self.specimen, self.noise.combined_snb_db
            )
            self.modulus = modulus_budget(self.specimen, self.frequency)

        if self.sweep is not None:
            self.sweep_limits = compute_sweep_limits(self.sweep, f_in)

        return self

    def provenance_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {p.value: 0 for p in Provenance}

        def walk(obj: Any) -> None:
            if isinstance(obj, Quantity):
                counts[obj.provenance.value] += 1
            elif hasattr(obj, "__dataclass_fields__"):
                for name in obj.__dataclass_fields__:
                    walk(getattr(obj, name))
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    walk(item)

        for spec in (self.converter, self.clock, self.front_end,
                     self.capture, self.sweep, self.specimen):
            if spec is not None:
                walk(spec)
        return counts

    def is_evidence_grade(self) -> tuple[bool, list[str]]:
        """
        A budget is evidence-grade only if no input is PROPOSED and the
        physical repeatability has been measured. Returns (ok, reasons).
        """
        reasons: list[str] = []
        counts = self.provenance_summary()
        if counts[Provenance.PROPOSED.value] > 0:
            reasons.append(
                f"{counts[Provenance.PROPOSED.value]} input(s) are PROPOSED "
                f"(unvalidated concept figures)"
            )
        if counts[Provenance.ASSUMED.value] > 0:
            reasons.append(
                f"{counts[Provenance.ASSUMED.value]} input(s) are ASSUMED"
            )
        if self.specimen is not None and self.specimen.physical_repeatability_hz is None:
            reasons.append("physical repeatability has not been measured")
        if not self.converter.anti_alias_filter:
            reasons.append("converter has no input anti-alias filter (B-014)")
        if self.converter.ac_coupled and self.converter.hp_corner_hz is None:
            reasons.append("AC-coupling corner unmeasured")
        return (len(reasons) == 0, reasons)

    def emit(self) -> dict[str, Any]:
        ok, reasons = self.is_evidence_grade()
        out: dict[str, Any] = {
            "schema": self.schema_version,
            "profile": self.profile,
            "evidence_grade": ok,
            "evidence_blockers": reasons,
            "provenance_counts": self.provenance_summary(),
            "inputs": {
                "converter": _spec_dict(self.converter),
                "clock": _spec_dict(self.clock),
                "front_end": _spec_dict(self.front_end),
                "capture": _spec_dict(self.capture),
                "sweep": _spec_dict(self.sweep),
                "specimen": _spec_dict(self.specimen),
            },
            "results": {},
        }
        if self.noise:
            out["results"]["noise"] = self.noise.as_dict()
            out["results"]["self_test"] = self_test_thresholds(self.noise)
            out["results"]["clock_topology"] = clock_topology_note(self.clock)
        if self.frequency:
            out["results"]["frequency"] = self.frequency.as_dict()
        if self.modulus:
            out["results"]["modulus"] = self.modulus.as_dict()
        if self.sweep_limits:
            out["results"]["sweep_limits"] = self.sweep_limits
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.emit(), indent=indent)


def _spec_dict(spec: Any) -> Any:
    if spec is None:
        return None
    d = asdict(spec)
    return _unwrap(d)


def _unwrap(obj: Any) -> Any:
    if isinstance(obj, dict):
        if set(obj.keys()) >= {"value", "unit", "provenance"}:
            return obj
        return {k: _unwrap(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unwrap(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------
# Figures traceable to TTP_HARDWARE_STACK.md Rev 1.5 are DATASHEET.
# Everything else is PROPOSED or ASSUMED until E0 measures it.

def TTP_ANALYZER_PROFILE() -> AcquisitionBudget:
    """TTP Analyzer, Phase 2B contact drive, spruce top plate."""
    converter = ConverterSpec(
        name="HiFiBerry DAC+ ADC Pro",
        bits=24,
        full_scale_vrms=Quantity(2.1, "Vrms", Provenance.DATASHEET,
                                 "Rev 1.5, unbalanced maximum"),
        thermal_snr_db=Quantity(110.0, "dB", Provenance.DATASHEET, "Rev 1.5 typ."),
        aperture_jitter_s=Quantity(1e-12, "s", Provenance.PROPOSED,
                                   "not published; placeholder pending E0/T4"),
        sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET, "Rev 1.5"),
        ac_coupled=True,
        hp_corner_hz=None,                 # E0/T3 measures this
        anti_alias_filter=False,           # B-014
    )
    clock = ClockSpec(
        name="on-board local oscillator",
        rms_jitter_s=Quantity(5e-12, "s", Provenance.PROPOSED,
                              "vendor cites low-jitter dual-domain clock, no figure"),
        accuracy_ppm=Quantity(20.0, "ppm", Provenance.ASSUMED, "typical XO grade"),
        topology="local_xo",
        spurious=False,
    )
    front_end = FrontEndSpec(
        name="OPA1612 balanced mic preamp",
        input_referred_noise_v_per_rthz=Quantity(1.1e-9, "V/rtHz",
                                                 Provenance.DATASHEET, "OPA1612"),
        gain_db=Quantity(52.0, "dB", Provenance.PROPOSED,
                         "MID position; prototype hypothesis, not a constant"),
        bandwidth_hz=Quantity(20000.0, "Hz", Provenance.ASSUMED, "declared band"),
    )
    capture = CaptureSpec(
        record_length_s=Quantity(4.0, "s", Provenance.ASSUMED, "working default"),
        sample_rate_hz=Quantity(48000.0, "Hz", Provenance.DATASHEET, "Rev 1.5"),
        window="hann",
        peak_interpolation=True,
    )
    sweep = SweepSpec(
        f_start_hz=Quantity(60.0, "Hz", Provenance.ASSUMED, "below lowest plate mode"),
        f_stop_hz=Quantity(2000.0, "Hz", Provenance.ASSUMED, "top of declared band"),
        expected_q=Quantity(50.0, "-", Provenance.PROPOSED, "braced top, typical range 30-80"),
    )
    specimen = SpecimenSpec(
        name="spruce top plate, mode 2",
        mode_frequency_hz=Quantity(187.0, "Hz", Provenance.ASSUMED, "worked example"),
        length_m=Quantity(0.500, "m", Provenance.ASSUMED, "worked example"),
        length_uncertainty_m=Quantity(0.0005, "m", Provenance.ASSUMED, "steel rule"),
        thickness_m=Quantity(0.0028, "m", Provenance.ASSUMED, "worked example"),
        thickness_uncertainty_m=Quantity(0.00002, "m", Provenance.ASSUMED, "digital caliper"),
        density_kg_m3=Quantity(420.0, "kg/m3", Provenance.ASSUMED, "worked example"),
        density_uncertainty_kg_m3=Quantity(4.0, "kg/m3", Provenance.ASSUMED,
                                           "mass and volume measurement"),
        physical_repeatability_hz=None,    # UNMEASURED -- blocks evidence grade
    )
    return AcquisitionBudget(
        profile="ttp_analyzer_phase2b",
        converter=converter, clock=clock, front_end=front_end,
        capture=capture, sweep=sweep, specimen=specimen,
    )


def SMART_GUITAR_PROFILE(pi_is_i2s_master: bool = False) -> AcquisitionBudget:
    """
    Smart Guitar audio front end. No specimen, no capture, no sweep -- it is a
    signal path, not a measurement chain, so only the Stage 3 noise budget
    applies. The decision this profile exists to make is clock topology.
    """
    converter = ConverterSpec(
        name="audio codec (candidate)",
        bits=24,
        full_scale_vrms=Quantity(2.1, "Vrms", Provenance.ASSUMED, "line level"),
        thermal_snr_db=Quantity(110.0, "dB", Provenance.ASSUMED, "class-typical"),
        aperture_jitter_s=Quantity(1e-12, "s", Provenance.PROPOSED, "placeholder"),
        sample_rate_hz=Quantity(48000.0, "Hz", Provenance.ASSUMED, "audio callback rate"),
        ac_coupled=True,
        hp_corner_hz=Quantity(10.0, "Hz", Provenance.ASSUMED, "typical codec coupling"),
        anti_alias_filter=True,
    )
    if pi_is_i2s_master:
        clock = ClockSpec(
            name="Pi 5 fractional-N I2S",
            rms_jitter_s=Quantity(1e-9, "s", Provenance.PROPOSED,
                                  "fractional-N divider, order-of-magnitude"),
            accuracy_ppm=Quantity(50.0, "ppm", Provenance.ASSUMED, "SoC oscillator"),
            topology="host_fractional_n",
            spurious=True,
        )
    else:
        clock = ClockSpec(
            name="local XO, codec master",
            rms_jitter_s=Quantity(50e-12, "s", Provenance.ASSUMED, "modest XO"),
            accuracy_ppm=Quantity(20.0, "ppm", Provenance.ASSUMED, "typical XO grade"),
            topology="local_xo",
            spurious=False,
        )
    front_end = FrontEndSpec(
        name="instrument preamp",
        input_referred_noise_v_per_rthz=Quantity(2.0e-9, "V/rtHz",
                                                 Provenance.ASSUMED, "candidate"),
        gain_db=Quantity(20.0, "dB", Provenance.ASSUMED, "pickup level"),
        bandwidth_hz=Quantity(20000.0, "Hz", Provenance.ASSUMED, "audio band"),
    )
    return AcquisitionBudget(
        profile="smart_guitar_master" if pi_is_i2s_master else "smart_guitar_slave",
        converter=converter, clock=clock, front_end=front_end,
        capture=None, sweep=None, specimen=None,
    )


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def format_report(b: AcquisitionBudget) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"ACQUISITION BUDGET -- {b.profile}")
    add("=" * 68)

    ok, reasons = b.is_evidence_grade()
    add(f"Evidence grade: {'YES' if ok else 'NO'}")
    for r in reasons:
        add(f"  blocker: {r}")
    add("")

    if b.noise:
        n = b.noise
        add(f"Stage 3 -- noise budget at {n.f_in_hz:.4g} Hz")
        for k, v in sorted(n.terms_db.items(), key=lambda kv: kv[1]):
            mark = "  <-- LIMITS" if k == n.limiter else ""
            add(f"  {k:<20} {v:>8.2f} dB{mark}")
        add(f"  {'combined':<20} {n.combined_snb_db:>8.2f} dB")
        add(f"  total jitter          {n.total_jitter_s * 1e12:>8.2f} ps rms")
        add(f"  jitter headroom       {n.jitter_headroom_db:>8.1f} dB")
        add("")
        for note in n.notes:
            add(f"  ! {note}")
        add("")

    if b.sweep_limits:
        s = b.sweep_limits
        add(f"Stage 1 -- sweep limits at {s['at_frequency_hz']:.4g} Hz, Q={s['assumed_q']:.0f}")
        add(f"  half-power bandwidth  {s['half_power_bandwidth_hz']:>8.2f} Hz")
        add(f"  min dwell per step    {s['min_dwell_per_step_s'] * 1000:>8.1f} ms")
        add(f"  max sweep rate        {s['max_sweep_rate_hz_per_s']:>8.2f} Hz/s")
        add(f"  min total sweep time  {s['min_total_sweep_time_s']:>8.1f} s")
        add("")

    if b.frequency:
        f = b.frequency
        add(f"Stage 7 -- frequency uncertainty at {f.mode_frequency_hz:.4g} Hz")
        add(f"  clock accuracy        {f.clock_error_hz:>12.6g} Hz")
        add(f"  FFT bin width         {f.bin_width_hz:>12.6g} Hz")
        add(f"  estimator floor (CRB) {f.estimator_floor_hz:>12.6g} Hz")
        rep = f.physical_repeatability_hz
        add(f"  physical repeatability{(f'{rep:>12.6g} Hz' if rep is not None else '   UNMEASURED'):>13}")
        add(f"  combined              {f.combined_hz:>12.6g} Hz   (dominant: {f.dominant})")
        add("")
        for note in f.notes:
            add(f"  ! {note}")
        add("")

    if b.modulus:
        m = b.modulus
        add("Stage 7 -- propagation to E_L")
        for k, v in sorted(m.contributions.items(), key=lambda kv: -kv[1]):
            mark = "  <-- DOMINANT" if k == m.dominant else ""
            add(f"  {k:<20} {v * 100:>8.3f} %{mark}")
        add(f"  {'combined':<20} {m.relative_uncertainty * 100:>8.3f} %")
        add("")
        add(f"  SMALLEST RESOLVABLE DIFFERENCE IN E_L: "
            f"{m.smallest_resolvable_delta_pct:.2f} %")
        add("")
        for note in m.notes:
            add(f"  ! {note}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    which = sys.argv[1] if len(sys.argv) > 1 else "ttp"

    if which == "ttp":
        b = TTP_ANALYZER_PROFILE().compute()
    elif which == "sg-master":
        b = SMART_GUITAR_PROFILE(pi_is_i2s_master=True).compute(f_in_hz=20000.0)
    elif which == "sg-slave":
        b = SMART_GUITAR_PROFILE(pi_is_i2s_master=False).compute(f_in_hz=20000.0)
    elif which == "json":
        print(TTP_ANALYZER_PROFILE().compute().to_json())
        raise SystemExit(0)
    else:
        print("usage: acquisition_budget.py [ttp|sg-master|sg-slave|json]")
        raise SystemExit(2)

    print(format_report(b))

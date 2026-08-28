# INSTRUMENT CLASS: MEASUREMENT
"""Propagation to E_L — **an adapter, not a second modulus authority**.

The luthier cannot act on "138 dB". They can act on "this rig distinguishes
plates whose E_L differs by more than 1.8%". That translation is what this module
provides, and it is the only reason the acquisition budget terminates in a
material property at all.

**The propagation itself is not implemented here — but its aggregate is
currently bypassed.**
:func:`tap_tone_pi.uncertainty.stiffness.compute_tap_tone_moe_uncertainty` is
canonical for ``E ∝ f²·L⁴·ρ/t²`` and its sensitivity coefficients (2, 4, 1, 2).
This module calls it and reads its output. The coefficients are never written
down here — a delegation test asserts they come from the canonical function, so
if this module ever grows its own copy the test fails.

The call passes ``E_GPa = 1.0`` so the returned components are *relative*
contributions directly, and passes ``snr_db=40`` with ``is_calibrated=True`` to
suppress the canonical function's two additional penalty components, which model
signal quality and calibration state rather than geometric propagation and are
accounted for elsewhere in the acquisition budget.

**This is the boundary where the stdlib rule stops.** The canonical authority
imports NumPy, so the import happens inside the function rather than at module
load. Importing this module remains instrument-safe; *calling* it requires the
canonical uncertainty subsystem, and a budget computed where that is unavailable
records the modulus section as unavailable with a reason rather than failing or
inventing one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from .frequency_budget import FrequencyBudget
from .noise import rss
from .quantities import ResultAvailability
from .specs import SpecimenSpec

__all__ = [
    "ModulusBudget",
    "ModulusUnavailable",
    "UnavailableSection",
    "modulus_budget",
    "modulus_budget_or_unavailable",
]

# Machine-readable reason codes. A generic "computation failed" would not let a
# reader distinguish a missing dependency from a bad input.
REASON_CANONICAL_AUTHORITY_UNAVAILABLE = "canonical_authority_unavailable"
REASON_CANONICAL_COMPONENTS_MISSING = "canonical_components_missing"


@dataclass(frozen=True)
class UnavailableSection:
    """A section that was requested and could not be computed.

    Exists so that ``UNAVAILABLE`` is a *serializable scientific state* rather
    than an exception type. An exception is the right way to cross a dependency
    boundary in code and the wrong thing to publish: the alternatives it leaves a
    record are a fabricated number or a bare null whose meaning a reader has to
    guess.

    **No values are fabricated.** The section carries a status and a reason and
    nothing numeric at all.
    """

    reason_code: str
    reason: str
    availability: ResultAvailability = ResultAvailability.UNAVAILABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> UnavailableSection:
        return cls(
            reason_code=str(payload["reason_code"]),
            reason=str(payload["reason"]),
            availability=ResultAvailability(payload.get("availability", "unavailable")),
        )


# Canonical component name -> acquisition-budget term name. The canonical
# function owns the physics and the naming; this maps its vocabulary onto ours
# without restating either.
_CANONICAL_TERMS = {
    "Frequency measurement": "frequency",
    "Length measurement": "length",
    "Thickness measurement": "thickness",
    "Density calculation": "density",
}


class ModulusUnavailable(RuntimeError):
    """The canonical modulus authority could not be reached.

    Raised only where the caller asked for propagation explicitly. The aggregate
    budget catches it and records the section as unavailable, because an
    instrument that cannot import NumPy can still produce a perfectly truthful
    noise and frequency budget.
    """


@dataclass(frozen=True)
class ModulusBudget:
    """Relative uncertainty in E_L, and what it means for telling plates apart."""

    relative_uncertainty: float
    contributions: dict[str, float]
    dominant: str
    smallest_resolvable_delta_pct: float
    availability: ResultAvailability = ResultAvailability.AVAILABLE
    component_authority: str = (
        "tap_tone_pi.uncertainty.stiffness.compute_tap_tone_moe_uncertainty"
    )
    aggregation: str = "canonical_components_with_B022_aggregate_workaround"
    """How the combined figure was produced.

    Deliberately **not** a claim of ordinary canonical delegation. The
    sensitivity model and the component construction come from the canonical
    authority; its *aggregate* is bypassed because it double-applies the
    sensitivity coefficients (B-022). The local root-sum-square is a generic
    aggregation forced by that defect, and this marker exists so a reader can
    tell the difference — and so the workaround is removed rather than
    naturalized when B-022 is repaired.
    """

    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.value,
            # Not rounded. Rounding belongs to report rendering; a contract
            # payload that loses precision cannot round-trip, and a lossy
            # record is one a later reader cannot recompute from.
            "relative_uncertainty": self.relative_uncertainty,
            "relative_uncertainty_pct": self.relative_uncertainty * 100.0,
            "contributions": dict(self.contributions),
            "dominant": self.dominant,
            "smallest_resolvable_delta_pct": self.smallest_resolvable_delta_pct,
            "component_authority": self.component_authority,
            "aggregation": self.aggregation,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ModulusBudget:
        return cls(
            relative_uncertainty=float(payload["relative_uncertainty"]),
            contributions={
                k: float(v) for k, v in payload.get("contributions", {}).items()
            },
            dominant=str(payload["dominant"]),
            smallest_resolvable_delta_pct=float(
                payload["smallest_resolvable_delta_pct"]
            ),
            availability=ResultAvailability(payload.get("availability", "available")),
            component_authority=str(payload["component_authority"]),
            aggregation=str(payload["aggregation"]),
            notes=tuple(payload.get("notes", ())),
        )


def modulus_budget_or_unavailable(
    specimen: SpecimenSpec, freq: FrequencyBudget
) -> ModulusBudget | UnavailableSection:
    """Compute the modulus budget, or return a representable unavailable state.

    This is what an aggregate budget calls. The exception form remains for
    callers that asked for propagation explicitly and want to fail loudly; this
    form is what gets serialized, because a record must be able to say what it
    could not compute.
    """
    try:
        return modulus_budget(specimen, freq)
    except ModulusUnavailable as exc:
        return UnavailableSection(
            reason_code=(
                REASON_CANONICAL_COMPONENTS_MISSING
                if "did not return the expected" in str(exc)
                else REASON_CANONICAL_AUTHORITY_UNAVAILABLE
            ),
            reason=(
                "canonical uncertainty authority unavailable in the "
                "instrument-safe environment; modulus propagation delegates to "
                "tap_tone_pi.uncertainty.stiffness, which requires the general "
                "uncertainty subsystem"
            ),
        )


def modulus_budget(specimen: SpecimenSpec, freq: FrequencyBudget) -> ModulusBudget:
    """Propagate the frequency budget and the geometry into relative E_L uncertainty.

    **The components come from the canonical authority; the aggregate does not.**
    Every sensitivity coefficient and every per-term contribution is produced by
    :func:`~tap_tone_pi.uncertainty.stiffness.compute_tap_tone_moe_uncertainty`.
    Its combined figure is bypassed under B-022 — see the comment at the
    aggregation step. That bypass is temporary and is marked as such in the
    result rather than presented as normal delegation.

    The only other arithmetic here is the two-measurement distinguishability
    rule, which is a decision criterion rather than modulus physics.
    """
    try:
        from tap_tone_pi.uncertainty.stiffness import compute_tap_tone_moe_uncertainty
    except ImportError as exc:  # pragma: no cover - exercised in a subprocess
        raise ModulusUnavailable(
            "canonical uncertainty authority unavailable in the instrument-safe "
            "environment: tap_tone_pi.uncertainty.stiffness could not be "
            "imported, and it requires the general uncertainty subsystem"
        ) from exc

    # E_GPa = 1.0 makes every returned component a relative contribution.
    # snr_db = 40 and is_calibrated = True suppress the canonical function's two
    # non-geometric penalty components; signal quality is already accounted for
    # in the noise budget, and calibration state is not a propagation term.
    canonical = compute_tap_tone_moe_uncertainty(
        E_GPa=1.0,
        frequency_hz=float(specimen.mode_frequency_hz),
        frequency_uncertainty_hz=freq.combined_hz,
        length_mm=float(specimen.length_m) * 1000.0,
        length_uncertainty_mm=float(specimen.length_uncertainty_m) * 1000.0,
        thickness_mm=float(specimen.thickness_m) * 1000.0,
        thickness_uncertainty_mm=float(specimen.thickness_uncertainty_m) * 1000.0,
        density_kg_m3=float(specimen.density_kg_m3),
        density_uncertainty_kg_m3=float(specimen.density_uncertainty_kg_m3),
        snr_db=40.0,
        is_calibrated=True,
    )

    contributions: dict[str, float] = {}
    for component in canonical.components:
        term = _CANONICAL_TERMS.get(component.name)
        if term is not None:
            contributions[term] = float(component.value)

    missing = sorted(set(_CANONICAL_TERMS.values()) - set(contributions))
    if missing:
        raise ModulusUnavailable(
            "the canonical modulus authority did not return the expected "
            f"component(s): {', '.join(missing)}. Its component naming may have "
            "changed; this adapter must be updated rather than reimplementing "
            "the propagation"
        )

    # The canonical authority's own combination cannot be used here.
    # ``compute_tap_tone_moe_uncertainty`` pre-multiplies each component value by
    # its sensitivity coefficient AND passes that coefficient to
    # ``add_component``, while ``UncertaintyComponent.contribution`` is
    # ``(c_i * u_i)**2`` -- so ``combined_standard_uncertainty`` applies every
    # coefficient a second time. For this specimen it returns 0.0341 where the
    # correct root-sum-square is 0.0176, and the inflation is not even a constant
    # factor: it depends on which term dominates.
    #
    # The *component values* are correct, so they are combined here. RSS of
    # independent terms is elementary arithmetic, not a second propagation
    # authority -- the coefficients still come entirely from the canonical
    # function. Recorded as B-022; not fixed here, because changing a canonical
    # uncertainty authority is not an integration order's job.
    total = rss(*contributions.values())
    dominant = max(contributions, key=lambda k: contributions[k])

    # Two plates are distinguishable when their difference exceeds the combined
    # uncertainty of two independent measurements. A decision rule about
    # comparing measurements, not part of the modulus model.
    smallest_delta = total * math.sqrt(2.0) * 100.0

    notes = [
        "Components and sensitivity coefficients delegated to "
        "compute_tap_tone_moe_uncertainty. Its combined figure is bypassed under "
        "B-022, which double-applies the coefficients; the aggregate here is a "
        "local root-sum-square of the canonical components and is a temporary "
        "workaround, not canonical aggregation.",
        f"Dominant term is {dominant} "
        f"({contributions[dominant] / total * 100.0:.0f}% of the total in quadrature).",
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
        notes=tuple(notes),
    )


def relative_contributions_rss(contributions: dict[str, float]) -> float:
    """RSS of relative contributions.

    Provided for callers that need to recombine a subset. The aggregate figure
    always comes from the canonical authority; this exists so that recombination
    at the edges does not become a reason to reimplement propagation.
    """
    return rss(*contributions.values())

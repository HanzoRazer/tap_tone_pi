# INSTRUMENT CLASS: MEASUREMENT
"""The emitted artifact: :class:`AcquisitionBudgetV1`.

Assembles the section results, summarizes input provenance, and states — with
reasons — whether the whole thing is evidence-grade.

**A budget is not an evidence grade.** The engine must be able to produce a
genuinely useful design-stage budget full of ``PROPOSED`` values while truthfully
refusing to call it evidence. That is what makes the tool usable before the
hardware exists without letting design intentions become measurement claims.

**Two independent axes.** A computation can rest on excellent inputs and still
carry an unresolved authority condition; a mathematically settled computation can
consume ``PROPOSED`` inputs and fail on those. Evidence grade reads both, and
:class:`EvidenceReason` says which one failed.

**Standard library only.** See :mod:`.quantities`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .frequency_budget import FrequencyBudget
from .modulus import ModulusBudget, UnavailableSection, modulus_budget_or_unavailable
from .noise import NoiseBudget, clock_topology_note, noise_budget
from .quantities import Provenance, ResultAvailability
from .self_test import SelfTestThresholdPolicy, SelfTestThresholds, self_test_thresholds
from .specs import (
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    FrontEndSpec,
    SpecimenSpec,
    SweepSpec,
    spec_quantities,
)
from .sweep import SweepLimits, compute_sweep_limits
from .frequency_budget import frequency_budget

__all__ = [
    "ACQUISITION_BUDGET_SCHEMA_VERSION",
    "EvidenceCondition",
    "EvidenceReason",
    "EvidenceAssessment",
    "AcquisitionBudgetV1",
]

ACQUISITION_BUDGET_SCHEMA_VERSION = "acquisition_budget_v1"


class EvidenceCondition(str, Enum):
    """Why a budget is or is not evidence-grade.

    Typed so a consumer never has to reverse-engineer the decision out of
    provenance counts and free-text notes. The conditions fall on two axes, and
    the split is deliberate: **input** conditions are about where the numbers
    came from, **computation** conditions are about whether the path that
    produced them is settled.
    """

    # --- input conditions --------------------------------------------------
    PROPOSED_INPUTS = "proposed_inputs"
    ASSUMED_INPUTS = "assumed_inputs"
    PHYSICAL_REPEATABILITY_UNMEASURED = "physical_repeatability_unmeasured"

    # --- instrument conditions ---------------------------------------------
    NO_ANTI_ALIAS_FILTER = "no_anti_alias_filter"
    COUPLING_CORNER_UNMEASURED = "coupling_corner_unmeasured"

    # --- computation conditions --------------------------------------------
    SECTION_UNAVAILABLE = "section_unavailable"
    PROVISIONAL_FORMULA = "provisional_formula"
    CONTRIBUTOR_COMPOSITION_DEFECT = "contributor_composition_defect"
    AGGREGATE_AUTHORITY_WORKAROUND = "aggregate_authority_workaround"


@dataclass(frozen=True)
class EvidenceReason:
    """One condition, whether it blocks, and what it refers to."""

    condition: EvidenceCondition
    blocking: bool
    detail: str
    reference: str | None = None
    """Backlog identifier where one exists, e.g. ``B-021``."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition.value,
            "blocking": self.blocking,
            "detail": self.detail,
            "reference": self.reference,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceReason:
        return cls(
            condition=EvidenceCondition(payload["condition"]),
            blocking=bool(payload["blocking"]),
            detail=str(payload["detail"]),
            reference=payload.get("reference"),
        )


@dataclass(frozen=True)
class EvidenceAssessment:
    """The boolean, and why.

    ``evidence_grade`` is true only when the inputs are evidence-qualified **and**
    no unresolved computation condition invalidates the claimed result.

    **Evidence-qualified inputs are necessary but not sufficient.** An otherwise
    fully qualified budget stays non-evidence-grade while a blocking computation
    condition is present — which is the state the current mathematics is in.

    A non-blocking reason is still reported. It records something true about the
    computation — authority debt, typically — without pretending it invalidates
    the emitted result.
    """

    evidence_grade: bool
    reasons: tuple[EvidenceReason, ...] = field(default_factory=tuple)

    @property
    def blockers(self) -> tuple[EvidenceReason, ...]:
        return tuple(r for r in self.reasons if r.blocking)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_grade": self.evidence_grade,
            "reasons": [r.as_dict() for r in self.reasons],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceAssessment:
        return cls(
            evidence_grade=bool(payload["evidence_grade"]),
            reasons=tuple(
                EvidenceReason.from_dict(r) for r in payload.get("reasons", ())
            ),
        )


@dataclass(frozen=True)
class AcquisitionBudgetV1:
    """What attaches to a measurement session."""

    profile: str
    converter: ConverterSpec
    clock: ClockSpec
    front_end: FrontEndSpec | None = None
    capture: CaptureSpec | None = None
    sweep: SweepSpec | None = None
    specimen: SpecimenSpec | None = None

    noise: NoiseBudget | None = None
    frequency: FrequencyBudget | None = None
    modulus: ModulusBudget | UnavailableSection | None = None
    sweep_limits: SweepLimits | None = None
    self_test: SelfTestThresholds | None = None
    clock_topology: str = ""

    schema_version: str = field(default=ACQUISITION_BUDGET_SCHEMA_VERSION, init=False)

    # -- computation --------------------------------------------------------

    def computed(
        self,
        f_in_hz: float | None = None,
        self_test_policy: SelfTestThresholdPolicy | None = None,
    ) -> AcquisitionBudgetV1:
        """Return a new budget with every computable section filled in.

        Returns a copy rather than mutating, because the record is frozen: a
        budget whose results can change after the fact is a record of nothing in
        particular.
        """
        f_in = f_in_hz
        if f_in is None and self.specimen is not None:
            f_in = float(self.specimen.mode_frequency_hz)
        if f_in is None:
            raise ValueError("f_in_hz is required when no specimen is supplied")

        noise = noise_budget(self.converter, self.clock, self.front_end, f_in)

        frequency = None
        modulus: ModulusBudget | UnavailableSection | None = None
        if self.capture is not None and self.specimen is not None:
            frequency = frequency_budget(
                self.clock, self.capture, self.specimen, noise.combined_snr_db
            )
            # Never an exception at this boundary: an unavailable section is a
            # serializable outcome, not an error.
            modulus = modulus_budget_or_unavailable(self.specimen, frequency)

        limits = (
            compute_sweep_limits(self.sweep, f_in) if self.sweep is not None else None
        )

        return AcquisitionBudgetV1(
            profile=self.profile,
            converter=self.converter,
            clock=self.clock,
            front_end=self.front_end,
            capture=self.capture,
            sweep=self.sweep,
            specimen=self.specimen,
            noise=noise,
            frequency=frequency,
            modulus=modulus,
            sweep_limits=limits,
            self_test=self_test_thresholds(noise, self_test_policy),
            clock_topology=clock_topology_note(self.clock),
        )

    # -- provenance and evidence -------------------------------------------

    def provenance_summary(self) -> dict[str, int]:
        """How many input quantities carry each provenance tag."""
        counts = {p.value: 0 for p in Provenance}
        for spec in (
            self.converter,
            self.clock,
            self.front_end,
            self.capture,
            self.sweep,
            self.specimen,
        ):
            if spec is not None:
                for quantity in spec_quantities(spec):
                    counts[quantity.provenance.value] += 1
        return counts

    def evidence(self) -> EvidenceAssessment:
        """Assess evidence grade across both axes, with typed reasons."""
        reasons: list[EvidenceReason] = []
        counts = self.provenance_summary()

        # --- input axis ----------------------------------------------------
        if counts[Provenance.PROPOSED.value]:
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.PROPOSED_INPUTS,
                    blocking=True,
                    detail=(
                        f"{counts[Provenance.PROPOSED.value]} input(s) are PROPOSED "
                        "— concept figures with no measurement behind them"
                    ),
                )
            )
        if counts[Provenance.ASSUMED.value]:
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.ASSUMED_INPUTS,
                    blocking=True,
                    detail=(
                        f"{counts[Provenance.ASSUMED.value]} input(s) are ASSUMED "
                        "— engineering judgement without a cited source"
                    ),
                )
            )
        if self.specimen is not None and not self.specimen.has_measured_repeatability():
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.PHYSICAL_REPEATABILITY_UNMEASURED,
                    blocking=True,
                    detail=(
                        "physical repeatability is unmeasured, so the frequency "
                        "figure is an electronic lower bound rather than a "
                        "measurement uncertainty"
                    ),
                )
            )

        # --- instrument axis -----------------------------------------------
        if not self.converter.anti_alias_filter:
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.NO_ANTI_ALIAS_FILTER,
                    blocking=True,
                    detail=(
                        "the converter has no input anti-alias filter; out-of-band "
                        "energy folds into the analysis band unrecoverably"
                    ),
                    reference="B-014",
                )
            )
        if self.converter.ac_coupled and self.converter.hp_corner_hz is None:
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.COUPLING_CORNER_UNMEASURED,
                    blocking=True,
                    detail=(
                        "the AC-coupling corner is unmeasured, so phase error at "
                        "the lowest modes is unbounded (E0 T3 measures it)"
                    ),
                )
            )

        # --- computation axis ------------------------------------------------
        if isinstance(self.modulus, UnavailableSection):
            reasons.append(
                EvidenceReason(
                    EvidenceCondition.SECTION_UNAVAILABLE,
                    blocking=True,
                    detail=f"modulus section unavailable: {self.modulus.reason}",
                )
            )
        elif isinstance(self.modulus, ModulusBudget):
            if self.modulus.aggregation != "canonical":
                reasons.append(
                    EvidenceReason(
                        EvidenceCondition.AGGREGATE_AUTHORITY_WORKAROUND,
                        # Advisory, not blocking. This is authority debt rather
                        # than a defect in the emitted result: the components and
                        # their sensitivities come from the canonical authority,
                        # the combination over them is a correct generic RSS, and
                        # parity independently confirms agreement with the source
                        # calculator. What is unresolved is that the repository's
                        # nominal canonical aggregate disagrees, because it
                        # double-applies its own coefficients. Repairing B-022
                        # will remove this condition without changing the number.
                        blocking=False,
                        detail=(
                            "the modulus aggregate bypasses the canonical "
                            "authority, which double-applies its sensitivity "
                            "coefficients. The component values and this "
                            "combination are correct and agree with the source "
                            "calculator; what is unresolved is that the canonical "
                            "aggregate disagrees with them"
                        ),
                        reference="B-022",
                    )
                )

        if self.frequency is not None:
            if not self.frequency.estimator_floor_status.is_established:
                reasons.append(
                    EvidenceReason(
                        EvidenceCondition.PROVISIONAL_FORMULA,
                        blocking=True,
                        detail=(
                            "the estimator-floor expression is carried from the "
                            "source for parity and its authority is unresolved; "
                            "it is not a certified bound"
                        ),
                        reference="B-020",
                    )
                )
            sources = [c.source_quantity for c in self.frequency.combined_contributors]
            if len(sources) != len(set(sources)):
                duplicated = sorted({s for s in sources if sources.count(s) > 1})
                reasons.append(
                    EvidenceReason(
                        EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT,
                        blocking=True,
                        detail=(
                            "the frequency combination draws "
                            f"{', '.join(duplicated)} more than once; the combined "
                            "figure is not what the intended contributor model "
                            "would give"
                        ),
                        reference="B-021",
                    )
                )
            elif (
                "estimator_floor_hz" in sources
                and "bin_width_hz" not in sources
                and not self.frequency.estimator_floor_status.is_established
            ):
                # The duplicate DO-107A preserved is gone -- that half of B-021
                # is repaired and provably so. What remains is a composition
                # question, not a bookkeeping one: the spectral-resolution slot
                # is filled by the estimator floor, and the bin width is reported
                # without entering the combination. Whether that is right depends
                # on the estimator model, which B-020 has not established.
                # Restoring the bin width would add a term that dominates at TTP
                # values, so it cannot be done as tidying.
                reasons.append(
                    EvidenceReason(
                        EvidenceCondition.CONTRIBUTOR_COMPOSITION_DEFECT,
                        blocking=True,
                        detail=(
                            "the spectral resolution term is filled by "
                            "estimator_floor_hz while bin_width_hz is reported and "
                            "does not enter the combination; whether both belong "
                            "in the aggregate depends on the estimator model, "
                            "which is not established"
                        ),
                        reference="B-021",
                    )
                )

        return EvidenceAssessment(
            evidence_grade=not any(r.blocking for r in reasons),
            reasons=tuple(reasons),
        )

    # -- serialization ------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        def section(value: Any) -> Any:
            return None if value is None else value.as_dict()

        modulus_payload = section(self.modulus)
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "inputs": {
                "converter": _spec_dict(self.converter),
                "clock": _spec_dict(self.clock),
                "front_end": _spec_dict(self.front_end),
                "capture": _spec_dict(self.capture),
                "sweep": _spec_dict(self.sweep),
                "specimen": _spec_dict(self.specimen),
            },
            "results": {
                "noise": section(self.noise),
                "frequency": section(self.frequency),
                "modulus": modulus_payload,
                "sweep_limits": section(self.sweep_limits),
                "self_test": section(self.self_test),
                "clock_topology": self.clock_topology,
            },
            "provenance_summary": self.provenance_summary(),
            "evidence": self.evidence().as_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AcquisitionBudgetV1:
        version = payload.get("schema_version", ACQUISITION_BUDGET_SCHEMA_VERSION)
        if version != ACQUISITION_BUDGET_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {ACQUISITION_BUDGET_SCHEMA_VERSION!r}, "
                f"not {version!r}"
            )
        inputs = payload["inputs"]
        results = payload.get("results", {})

        modulus_payload = results.get("modulus")
        modulus: ModulusBudget | UnavailableSection | None = None
        if modulus_payload is not None:
            # The availability discriminator is what makes an unavailable section
            # recoverable rather than collapsing to null or an error shape.
            if (
                modulus_payload.get("availability")
                == ResultAvailability.UNAVAILABLE.value
            ):
                modulus = UnavailableSection.from_dict(modulus_payload)
            else:
                modulus = ModulusBudget.from_dict(modulus_payload)

        return cls(
            profile=str(payload["profile"]),
            converter=_spec_from(ConverterSpec, inputs["converter"]),
            clock=_spec_from(ClockSpec, inputs["clock"]),
            front_end=_spec_from(FrontEndSpec, inputs.get("front_end")),
            capture=_spec_from(CaptureSpec, inputs.get("capture")),
            sweep=_spec_from(SweepSpec, inputs.get("sweep")),
            specimen=_spec_from(SpecimenSpec, inputs.get("specimen")),
            noise=_maybe(NoiseBudget, results.get("noise")),
            frequency=_maybe(FrequencyBudget, results.get("frequency")),
            modulus=modulus,
            sweep_limits=_maybe(SweepLimits, results.get("sweep_limits")),
            self_test=_maybe(SelfTestThresholds, results.get("self_test")),
            clock_topology=str(results.get("clock_topology", "")),
        )


# ---------------------------------------------------------------------------
# Specification serialization
# ---------------------------------------------------------------------------

_QUANTITY_KEYS = {"value", "unit", "provenance", "source"}


def _spec_dict(spec: Any) -> Any:
    """Serialize a specification, keeping quantities as quantities."""
    if spec is None:
        return None
    from .quantities import Quantity

    out: dict[str, Any] = {}
    for name in spec.__dataclass_fields__:
        value = getattr(spec, name)
        if isinstance(value, Quantity):
            out[name] = value.as_dict()
        elif isinstance(value, Enum):
            out[name] = value.value
        else:
            out[name] = value
    return out


def _spec_from(cls: type, payload: Mapping[str, Any] | None) -> Any:
    if payload is None:
        return None
    from .quantities import Quantity

    kwargs: dict[str, Any] = {}
    for name in cls.__dataclass_fields__:  # type: ignore[attr-defined]
        if name not in payload:
            continue
        value = payload[name]
        if isinstance(value, Mapping) and _QUANTITY_KEYS >= set(value):
            kwargs[name] = Quantity.from_dict(value)
        else:
            kwargs[name] = value
    return cls(**kwargs)


def _maybe(cls: type, payload: Mapping[str, Any] | None) -> Any:
    return None if payload is None else cls.from_dict(payload)  # type: ignore[attr-defined]

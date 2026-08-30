# INSTRUMENT CLASS: MEASUREMENT
"""E0 bench observations into acquisition-budget inputs (DO-107B).

DO-106 records what a converter did on a bench. DO-107A records what a
measurement configuration implies. This module is the join, and the only thing
it is allowed to do is carry a number across it without losing where the number
came from.

**It owns no equations.** Selection, row identification, unit normalization,
provenance and refusal are its whole job. Every jitter, noise, frequency and
propagation expression stays with the authority that already holds it — see
:mod:`.noise`, :mod:`.frequency_budget`, :mod:`.modulus` — and this module calls
:meth:`~.budget.AcquisitionBudgetV1.computed` rather than computing anything.

**Only an observation becomes ``MEASURED``.** An executed E0 record is not a
licence to promote the datasheet figure beside it: the mapping either finds the
number or it does not, and where it does not the acquisition input keeps the
provenance it already had. Nothing here emits zero, nominal, or null-as-measured
for a measurement nobody took.

**The mapping is explicit.** :data:`E0_MAPPINGS` names each source group, the
field inside it, the acquisition input it fills and the conversion applied. No
field is located by searching an E0 payload for a plausible name, and an
observation with no acquisition counterpart is recorded in
:data:`E0_UNMAPPED_GROUPS` with the reason it stays characterization evidence —
which is a normal outcome, not a gap.

**E0 characterizes; it does not qualify.** ``EXECUTED`` means every required
observation was recorded, not that the board passed, and this module adds no
threshold, no verdict and no pass condition to a protocol that deliberately has
none. What it can say is which acquisition inputs a bench actually replaced.

**Standard library only.** :mod:`tap_tone_pi.grant_readiness.e0_characterization`
is itself stdlib-only, so consuming it here does not breach the boundary
:mod:`.quantities` documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from tap_tone_pi.grant_readiness.e0_characterization import (
    E0AdcCharacterizationV1,
    E0ExecutionStatus,
    E0InputPath,
)

from .budget import AcquisitionBudgetV1
from .quantities import AcquisitionQuantityError, Provenance, Quantity
from .self_test import SelfTestThresholdPolicy
from .specs import ConverterSpec

__all__ = [
    "E0_MAPPINGS",
    "E0_UNMAPPED_GROUPS",
    "E0AdapterError",
    "E0Adaptation",
    "E0InformedBudget",
    "E0Mapping",
    "E0MappingOutcome",
    "E0MappingStatus",
    "E0OperatingPoint",
    "E0UnmappedGroup",
    "adapt_e0_characterization",
    "build_acquisition_budget_from_e0",
    "e0_informed_converter",
    "e0_source_locator",
    "parse_e0_source_locator",
    "compare_budget_inputs",
]


class E0AdapterError(AcquisitionQuantityError):
    """The adaptation cannot proceed truthfully.

    Raised for the two situations where continuing would produce a record that
    reads as evidence and is not: a record that carries no observations at all,
    and an operating point that does not describe the configuration the budget
    is written for. Everything else is reported per mapping, because a missing
    observation is a finding rather than an error.
    """


# ---------------------------------------------------------------------------
# The operating point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0OperatingPoint:
    """Which row of a bench table this budget is entitled to.

    T1 is a table over sample rate and PGA setting, and T6 is a table over input
    path. A budget written for 48 kHz at 0 dB of gain on the unbalanced input may
    not quote the 96 kHz row, so the caller states the configuration and the
    adapter matches it exactly. There is no nearest-row rule: an approximate
    match would be a measurement of something else.
    """

    sample_rate_hz: float
    pga_db: float
    input_path: E0InputPath = E0InputPath.UNBALANCED

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "pga_db": self.pga_db,
            "input_path": self.input_path.value,
        }


# ---------------------------------------------------------------------------
# Source locators
# ---------------------------------------------------------------------------

_LOCATOR_PREFIX = "e0:"


def e0_source_locator(
    characterization_id: str, test: str, group: str, selector: str, field: str
) -> str:
    """A deterministic address for one E0 observation.

    ``e0:<characterization_id>/<test>/<group>[<selector>]#<field>``

    DO-106 gives rows no identifiers of their own, so identity is composed from
    the values that already select the row — the sample rate and gain of a T1
    cell, the input path of a T6 cell. That is an address built from existing
    fields rather than a parallel evidence-ID scheme, and it resolves against the
    record without a lookup table.
    """
    body = f"{characterization_id}/{test}/{group}"
    if selector:
        body += f"[{selector}]"
    return f"{_LOCATOR_PREFIX}{body}#{field}"


def parse_e0_source_locator(source: str) -> dict[str, str]:
    """Take a locator back apart, for tracing a quantity to its bench row.

    The inverse of :func:`e0_source_locator`. Provided because provenance that
    cannot be walked backwards is decoration: given a serialized quantity, this
    is what says which record, which test and which observation to open.

    Raises:
        ValueError: if ``source`` is not an E0 locator.
    """
    if not source.startswith(_LOCATOR_PREFIX) or "#" not in source:
        raise ValueError(f"not an E0 source locator: {source!r}")
    body, field = source[len(_LOCATOR_PREFIX) :].rsplit("#", 1)
    selector = ""
    if body.endswith("]") and "[" in body:
        body, selector = body[:-1].split("[", 1)
    parts = body.split("/")
    if len(parts) != 3:
        raise ValueError(f"not an E0 source locator: {source!r}")
    return {
        "characterization_id": parts[0],
        "test": parts[1],
        "group": parts[2],
        "selector": selector,
        "field": field,
    }


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------
#
# Deterministic changes of reference or of unit prefix, nothing else. A
# conversion that needed a bandwidth, a full-scale voltage or a noise model
# would be an equation, and equations belong to the budget modules.


def _identity(value: float) -> float:
    return value


def _dbfs_to_snr_db(value: float) -> float:
    """A level below full scale, restated as a ratio to full scale.

    ``dBFS`` is defined against full scale, so the signal-to-noise ratio of a
    full-scale sine against that floor is its negation. This is the definition
    of the reference, not a noise model: no bandwidth, weighting or
    quantization term enters it.
    """
    return -value


# ---------------------------------------------------------------------------
# The mapping table
# ---------------------------------------------------------------------------


class E0MappingStatus(str, Enum):
    """What became of one mapping on one record."""

    CONSUMED = "consumed"
    """The observation was present and became a MEASURED acquisition input."""

    NOT_OBSERVED = "not_observed"
    """No such observation. The acquisition input keeps its existing provenance."""

    REFUSED = "refused"
    """An observation was found and rejected. Refusals are reported, not skipped."""


@dataclass(frozen=True)
class _Extraction:
    """What one group yielded when asked for one field.

    ``status`` is decided by the extractor rather than inferred from the absence
    of a value, because *nobody measured this* and *this was measured and will
    not be carried* are different findings that must not collapse into one.
    """

    status: E0MappingStatus
    value: float | None = None
    selector: str = ""
    detail: str = ""


def _observed(value: float, selector: str = "") -> _Extraction:
    return _Extraction(E0MappingStatus.CONSUMED, value=value, selector=selector)


def _absent(detail: str, selector: str = "") -> _Extraction:
    return _Extraction(E0MappingStatus.NOT_OBSERVED, selector=selector, detail=detail)


def _refused(detail: str, selector: str = "") -> _Extraction:
    return _Extraction(E0MappingStatus.REFUSED, selector=selector, detail=detail)


@dataclass(frozen=True)
class E0Mapping:
    """One E0 observation, one acquisition input, and the step between them."""

    test: str
    group: str
    field: str
    target: str
    """Dotted acquisition input, e.g. ``converter.hp_corner_hz``."""

    source_unit: str
    target_unit: str
    convert: Callable[[float], float]
    conversion: str
    """Human-readable statement of what :attr:`convert` does."""

    required: bool
    """Whether absence is reported as an unfilled slot in the audit."""

    extract: Callable[
        [E0AdcCharacterizationV1, E0OperatingPoint],
        "_Extraction",
    ]
    """``(record, operating_point) -> _Extraction``, in the group's own terms."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "test": self.test,
            "group": self.group,
            "field": self.field,
            "target": self.target,
            "source_unit": self.source_unit,
            "target_unit": self.target_unit,
            "conversion": self.conversion,
            "required": self.required,
        }


def _extract_noise_floor(
    record: E0AdcCharacterizationV1, point: E0OperatingPoint
) -> _Extraction:
    """T1: the input-shorted floor at exactly this sample rate and gain."""
    selector = f"sample_rate_hz={point.sample_rate_hz:g},pga_db={point.pga_db:g}"
    rows = [
        row
        for row in record.noise_floor
        if row.sample_rate_hz == point.sample_rate_hz and row.pga_db == point.pga_db
    ]
    if not rows:
        return _absent(
            "T1 records no noise floor at this sample rate and PGA setting",
            selector,
        )
    if len(rows) > 1:
        return _refused(
            f"T1 records {len(rows)} noise-floor cells for one sample rate and "
            "PGA setting; the row this budget is entitled to is ambiguous",
            selector,
        )
    value = rows[0].rms_dbfs
    if value >= 0.0:
        # An input-shorted floor at or above full scale is not a floor. Feeding
        # it forward would produce a negative SNR that the noise budget would
        # combine as though it meant something.
        return _refused(
            f"T1 records an input-shorted floor of {value:g} dBFS, at or above "
            "full scale; that is not a noise floor and is not carried forward",
            selector,
        )
    return _observed(value, selector)


def _extract_coupling_corner(
    record: E0AdcCharacterizationV1, point: E0OperatingPoint
) -> _Extraction:
    """T3: the measured high-pass corner.

    The sweep behind it is not consumed and not discarded — amplitude *and*
    phase stay in the E0 record, where T3 requires them. What the budget has a
    slot for is the corner.
    """
    corner = record.coupling.measured_corner_hz
    if corner is None:
        return _absent("T3 records no measured corner frequency")
    return _observed(corner)


def _extract_hard_clip(
    record: E0AdcCharacterizationV1, point: E0OperatingPoint
) -> _Extraction:
    """T6: where this input path stops working, on the path being budgeted."""
    selector = f"path={point.input_path.value}"
    rows = [row for row in record.full_scale if row.path is point.input_path]
    if not rows:
        return _absent(f"T6 records no {point.input_path.value} input path", selector)
    value = rows[0].hard_clip_vrms
    if value is None:
        return _absent(
            "T6 recorded this path without a hard-clip level; the 0.1% THD point "
            "is a different level answering a different question and is not "
            "substituted for it",
            selector,
        )
    return _observed(value, selector)


#: Every E0 observation that fills an acquisition input, and nothing else.
#:
#: Three entries, deliberately. The converter inputs below are the ones E0 was
#: run to establish and the ones :class:`~.specs.ConverterSpec` has slots for.
#: Everything else E0 measures is real evidence about the board that this
#: contract has nowhere to put — see :data:`E0_UNMAPPED_GROUPS`.
E0_MAPPINGS: tuple[E0Mapping, ...] = (
    E0Mapping(
        test="T1",
        group="noise_floor",
        field="rms_dbfs",
        target="converter.thermal_snr_db",
        source_unit="dBFS",
        target_unit="dB",
        convert=_dbfs_to_snr_db,
        conversion="negated: a level below full scale is a ratio to full scale",
        required=True,
        extract=_extract_noise_floor,
    ),
    E0Mapping(
        test="T3",
        group="coupling",
        field="measured_corner_hz",
        target="converter.hp_corner_hz",
        source_unit="Hz",
        target_unit="Hz",
        convert=_identity,
        conversion="none",
        required=True,
        extract=_extract_coupling_corner,
    ),
    E0Mapping(
        test="T6",
        group="full_scale",
        field="hard_clip_vrms",
        target="converter.full_scale_vrms",
        source_unit="Vrms",
        target_unit="Vrms",
        convert=_identity,
        conversion="none",
        required=True,
        extract=_extract_hard_clip,
    ),
)


@dataclass(frozen=True)
class E0UnmappedGroup:
    """An E0 observation group that stays characterization evidence."""

    test: str
    group: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"test": self.test, "group": self.group, "reason": self.reason}


#: Why each unconsumed group is unconsumed.
#:
#: Recorded rather than left implicit: a future contract change that silently
#: dropped an observation would otherwise be indistinguishable from an
#: observation that never had a home. None of these reasons is a judgement about
#: the board.
E0_UNMAPPED_GROUPS: tuple[E0UnmappedGroup, ...] = (
    E0UnmappedGroup(
        test="T1",
        group="spurs",
        reason=(
            "discrete tones. The noise budget combines broadband terms on noise "
            "power and refuses to root-sum-square a spur with them; there is no "
            "acquisition input for one, and inventing an equivalent broadband "
            "level would be a model this adapter may not own"
        ),
    ),
    E0UnmappedGroup(
        test="T2",
        group="pga",
        reason=(
            "gain accuracy has no acquisition input, and the input-referred "
            "noise column is in dBFS. Converting it to the front end's V/rtHz "
            "density needs a noise bandwidth and a full-scale voltage — an "
            "equation, which belongs to the noise authority and not here"
        ),
    ),
    E0UnmappedGroup(
        test="T3",
        group="coupling.points",
        reason=(
            "the amplitude and phase sweep supports the corner that is consumed. "
            "Phase is retained in the E0 record, where T3 requires it; it is not "
            "reduced away, and the budget has no per-frequency phase input"
        ),
    ),
    E0UnmappedGroup(
        test="T4",
        group="out_of_band",
        reason=(
            "attenuation figures describe how the converter answered injected "
            "tones. ConverterSpec.anti_alias_filter states whether an input "
            "filter is fitted, which is a fact about the hardware rather than a "
            "conclusion to be drawn from a response table. B-014 is answered by "
            "reading T4, by a human, and is not closed here"
        ),
    ),
    E0UnmappedGroup(
        test="T5",
        group="balanced_scope",
        reason=(
            "the input-mode control's scope bears on which instrument can use "
            "the balanced path, not on a budget input. Its full-scale figures "
            "are not substituted for T6's: one target takes one source, so a "
            "budget cannot mix two definitions of full scale"
        ),
    ),
    E0UnmappedGroup(
        test="T6",
        group="full_scale.thd_0p1pct_vrms",
        reason=(
            "the 0.1% THD point and hard clip are separate levels answering "
            "different questions. full_scale_vrms is the level the converter "
            "runs out of range at, so hard clip fills it and the distortion "
            "point stays characterization evidence"
        ),
    ),
    E0UnmappedGroup(
        test="T7",
        group="loopback",
        reason=(
            "the playrec offset is a DAC-to-ADC round trip, not a sample-clock "
            "measurement and not an ADC phase reference. Reading it as aperture "
            "jitter or clock jitter would infer a timing relationship the "
            "commanded waveform cannot establish"
        ),
    ),
)


# ---------------------------------------------------------------------------
# Adaptation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0MappingOutcome:
    """One mapping, applied to one record."""

    mapping: E0Mapping
    status: E0MappingStatus
    quantity: Quantity | None = None
    source: str | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "test": self.mapping.test,
            "group": self.mapping.group,
            "field": self.mapping.field,
            "target": self.mapping.target,
            "status": self.status.value,
            "value": None if self.quantity is None else self.quantity.value,
            "unit": None if self.quantity is None else self.quantity.unit,
            "source": self.source,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class E0Adaptation:
    """What one E0 record supplied, what it did not, and what was ignored.

    The audit surface DO-107B §17 asks for: which observations were consumed,
    which acquisition inputs they filled, which were ignored, and why. Answering
    it from data rather than from memory is what keeps a later contract change
    from dropping an observation quietly.
    """

    characterization_id: str
    execution_status: E0ExecutionStatus
    operating_point: E0OperatingPoint
    outcomes: tuple[E0MappingOutcome, ...]
    unmapped: tuple[E0UnmappedGroup, ...] = E0_UNMAPPED_GROUPS

    def measured(self) -> dict[str, Quantity]:
        """Acquisition input name to the quantity E0 supplied for it."""
        return {
            outcome.mapping.target: outcome.quantity
            for outcome in self.outcomes
            if outcome.status is E0MappingStatus.CONSUMED
            and outcome.quantity is not None
        }

    def unfilled(self) -> tuple[E0MappingOutcome, ...]:
        """Required mappings that produced nothing, with the reason each gave."""
        return tuple(
            outcome
            for outcome in self.outcomes
            if outcome.mapping.required
            and outcome.status is not E0MappingStatus.CONSUMED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "characterization_id": self.characterization_id,
            "execution_status": self.execution_status.value,
            "operating_point": self.operating_point.as_dict(),
            "outcomes": [o.as_dict() for o in self.outcomes],
            "unmapped": [u.as_dict() for u in self.unmapped],
        }


def adapt_e0_characterization(
    record: E0AdcCharacterizationV1,
    operating_point: E0OperatingPoint,
) -> E0Adaptation:
    """Read one E0 record at one operating point. Computes nothing.

    Every mapping in :data:`E0_MAPPINGS` is attempted and every attempt is
    reported, including the ones that found nothing: a mapping that quietly
    produced no outcome would be indistinguishable from a mapping that was never
    tried.

    Raises:
        E0AdapterError: if the record is ``PREPARED``. Preparation is not
            measurement — a record that states no bench has been touched cannot
            supply a measured input, and asking it to is a caller error rather
            than a finding about the board.
    """
    if record.execution_status is E0ExecutionStatus.PREPARED:
        raise E0AdapterError(
            f"E0 record {record.characterization_id!r} is PREPARED and carries no "
            "observations. PREPARED means no bench has been touched; it cannot "
            "supply a measured acquisition input"
        )

    outcomes: list[E0MappingOutcome] = []
    for mapping in E0_MAPPINGS:
        found = mapping.extract(record, operating_point)
        if found.status is not E0MappingStatus.CONSUMED or found.value is None:
            # Absent and refused both leave the acquisition input alone. They
            # stay distinct because one is a bench that has not run and the other
            # is a bench result this adapter declined to carry forward.
            outcomes.append(
                E0MappingOutcome(
                    mapping=mapping, status=found.status, detail=found.detail
                )
            )
            continue

        source = e0_source_locator(
            record.characterization_id,
            mapping.test,
            mapping.group,
            found.selector,
            mapping.field,
        )
        outcomes.append(
            E0MappingOutcome(
                mapping=mapping,
                status=E0MappingStatus.CONSUMED,
                quantity=Quantity(
                    mapping.convert(found.value),
                    mapping.target_unit,
                    Provenance.MEASURED,
                    source,
                ),
                source=source,
                detail=found.detail,
            )
        )

    return E0Adaptation(
        characterization_id=record.characterization_id,
        execution_status=record.execution_status,
        operating_point=operating_point,
        outcomes=tuple(outcomes),
    )


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def e0_informed_converter(
    converter: ConverterSpec, adaptation: E0Adaptation
) -> ConverterSpec:
    """A converter specification with E0's observations substituted in.

    Only the inputs the adaptation actually filled change. Everything else keeps
    the provenance it arrived with — a datasheet figure beside a measured one
    stays ``DATASHEET``, because the bench that measured its neighbour did not
    measure it.

    Raises:
        E0AdapterError: if the specification's sample rate is not the rate the
            observations were taken at. A noise floor measured at one rate is not
            a noise floor at another, and substituting across rates would put a
            measurement of one configuration into a budget for a different one.
    """
    point = adaptation.operating_point
    configured = float(converter.sample_rate_hz)
    if configured != point.sample_rate_hz:
        raise E0AdapterError(
            f"the budget's converter is configured at {configured:g} Hz and the "
            f"E0 observations were selected at {point.sample_rate_hz:g} Hz. A "
            "measurement of one configuration is not evidence about another"
        )

    measured = adaptation.measured()
    replacements: dict[str, Quantity] = {}
    for target, quantity in measured.items():
        section, _, field = target.partition(".")
        if section == "converter":
            replacements[field] = quantity

    return ConverterSpec(
        name=converter.name,
        bits=converter.bits,
        full_scale_vrms=replacements.get("full_scale_vrms", converter.full_scale_vrms),
        thermal_snr_db=replacements.get("thermal_snr_db", converter.thermal_snr_db),
        aperture_jitter_s=converter.aperture_jitter_s,
        sample_rate_hz=converter.sample_rate_hz,
        ac_coupled=converter.ac_coupled,
        hp_corner_hz=replacements.get("hp_corner_hz", converter.hp_corner_hz),
        anti_alias_filter=converter.anti_alias_filter,
    )


@dataclass(frozen=True)
class E0InformedBudget:
    """A computed budget, beside the account of what E0 changed in it."""

    budget: AcquisitionBudgetV1
    adaptation: E0Adaptation


def build_acquisition_budget_from_e0(
    base: AcquisitionBudgetV1,
    record: E0AdcCharacterizationV1,
    operating_point: E0OperatingPoint,
    *,
    f_in_hz: float | None = None,
    self_test_policy: SelfTestThresholdPolicy | None = None,
) -> E0InformedBudget:
    """Rebuild ``base`` with E0's measured inputs and compute it.

    The composition is
    :meth:`~.budget.AcquisitionBudgetV1.computed` and nothing else: no noise,
    frequency, sweep or modulus expression is evaluated here, so an E0-informed
    budget and a hand-built budget carrying the same inputs are the same numbers
    by construction rather than by agreement.

    ``base`` supplies everything E0 does not measure — the clock, the front end,
    the capture, the sweep and the specimen — with the provenance it already
    carries. Nothing in it is promoted as a side effect of the converter being
    characterized.
    """
    adaptation = adapt_e0_characterization(record, operating_point)
    converter = e0_informed_converter(base.converter, adaptation)

    rebuilt = AcquisitionBudgetV1(
        profile=base.profile,
        converter=converter,
        clock=base.clock,
        front_end=base.front_end,
        capture=base.capture,
        sweep=base.sweep,
        specimen=base.specimen,
    )
    return E0InformedBudget(
        budget=rebuilt.computed(f_in_hz=f_in_hz, self_test_policy=self_test_policy),
        adaptation=adaptation,
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_budget_inputs(
    before: AcquisitionBudgetV1, after: AcquisitionBudgetV1
) -> dict[str, dict[str, Any]]:
    """Which input quantities differ between two budgets, and how.

    Answers what physical characterization actually changed. It reports value and
    provenance movement per input; it grades nothing, and a changed provenance
    with an unchanged value is as much a result as the reverse.
    """
    sections = ("converter", "clock", "front_end", "capture", "sweep", "specimen")
    changed: dict[str, dict[str, Any]] = {}

    for section in sections:
        old_spec = getattr(before, section)
        new_spec = getattr(after, section)
        if old_spec is None or new_spec is None:
            continue
        for field in old_spec.__dataclass_fields__:
            old = getattr(old_spec, field)
            new = getattr(new_spec, field)
            if not isinstance(old, Quantity) and not isinstance(new, Quantity):
                continue
            if old == new:
                continue
            changed[f"{section}.{field}"] = {
                "before": None if old is None else _quantity_view(old),
                "after": None if new is None else _quantity_view(new),
            }
    return changed


def _quantity_view(quantity: Quantity) -> Mapping[str, Any]:
    return {
        "value": quantity.value,
        "unit": quantity.unit,
        "provenance": quantity.provenance.value,
        "source": quantity.source,
    }

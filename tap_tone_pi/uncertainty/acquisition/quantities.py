# INSTRUMENT CLASS: MEASUREMENT
"""Provenance-bearing quantities for the acquisition budget (DO-107A).

A number typed into a slider and a number read off a datasheet do not render
identically, because one is load-bearing and the other is a guess. Every input to
an acquisition budget therefore carries where it came from, and that tag survives
serialization unchanged.

**Standard library only.** This module runs on the instrument. It imports
``math``, ``dataclasses``, ``enum`` and ``typing`` and nothing else, and it must
not acquire a dependency on :mod:`tap_tone_pi.uncertainty.budget` — that package
is canonical for general uncertainty propagation and imports NumPy, which is
exactly the transitive leak the stdlib boundary exists to prevent. Adaptation to
it happens at an integration boundary, not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "Provenance",
    "Quantity",
    "AcquisitionQuantityError",
    "as_quantity",
    "ResultAvailability",
    "FormulaStatus",
]


class AcquisitionQuantityError(ValueError):
    """A quantity is not usable as evidence input.

    Deliberately a plain ``ValueError`` subclass rather than a member of the
    grant-readiness error family: that family lives in a package this one may not
    import, and an acquisition budget must be constructible on an instrument with
    nothing else loaded.
    """


class Provenance(str, Enum):
    """Where a number came from. Ordered weakest to strongest.

    The ordering is the point. ``PROPOSED`` and ``ASSUMED`` are stated intentions
    and engineering judgement; the rest have something behind them. A budget
    built from the first two is a design study, which is useful — it just is not
    evidence, and :meth:`is_evidence` is what lets the difference be enforced
    rather than remembered.
    """

    PROPOSED = "proposed"
    """A concept figure with no measurement behind it."""

    ASSUMED = "assumed"
    """Standard practice or engineering judgement, no cited source."""

    DATASHEET = "datasheet"
    """A manufacturer's published nominal figure."""

    DERIVED = "derived"
    """Computed from other tagged quantities in this record."""

    MEASURED = "measured"
    """Observed on this instrument."""

    @property
    def is_evidence(self) -> bool:
        """Whether this tag can support an evidence-grade claim."""
        return self in (Provenance.DATASHEET, Provenance.DERIVED, Provenance.MEASURED)


class ResultAvailability(str, Enum):
    """Whether a section of a budget could be computed at all.

    An exception is the right way to cross a dependency boundary in code; it is
    the wrong thing to serialize. A published record must be able to say *this
    was requested and could not be computed, and here is why* — otherwise the
    only representations left are a fabricated number or a bare ``null`` whose
    meaning a reader has to guess.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class FormulaStatus(str, Enum):
    """Authority status of the expression behind a computed term.

    Deliberately two members rather than a taxonomy. This exists because one
    term — the estimator floor — is carried faithfully from the acquisition
    source while its authority is genuinely unresolved (B-020, plus the
    unverified factor-of-two in the newer acquisition mathematics). It is a
    different axis from :class:`Provenance`, which records where a *number* came
    from rather than whether the *formula* producing it is settled.
    """

    ESTABLISHED = "established"
    """The expression is settled and named for what it is."""

    CANDIDATE_SOURCE_FORMULA = "candidate_source_formula"
    """Reproduced from the source for parity; its authority is unresolved."""

    @property
    def is_established(self) -> bool:
        return self is FormulaStatus.ESTABLISHED


@dataclass(frozen=True)
class Quantity:
    """A number that knows its unit and where it came from.

    Frozen because a budget is a record of what was believed at a moment. A
    quantity whose provenance can be mutated after the fact is a quantity whose
    provenance means nothing.
    """

    value: float
    unit: str
    provenance: Provenance
    source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            try:
                object.__setattr__(self, "provenance", Provenance(self.provenance))
            except ValueError as exc:
                raise AcquisitionQuantityError(
                    f"unknown provenance {self.provenance!r}; permitted: "
                    + ", ".join(p.value for p in Provenance)
                ) from exc

        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise AcquisitionQuantityError(
                f"Quantity.value must be a number, not {type(self.value).__name__}"
            )
        numeric = float(self.value)
        if not math.isfinite(numeric):
            # NaN and infinity are refused rather than stored. A budget that
            # carries one produces a combined figure that is silently NaN, and a
            # NaN uncertainty reads as "no answer yet" rather than as a defect.
            raise AcquisitionQuantityError(
                f"Quantity.value must be finite, not {self.value!r}"
            )
        object.__setattr__(self, "value", numeric)

        if not isinstance(self.unit, str):
            raise AcquisitionQuantityError("Quantity.unit must be a string")

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "provenance": self.provenance.value,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Quantity:
        unknown = sorted(set(payload) - {"value", "unit", "provenance", "source"})
        if unknown:
            raise AcquisitionQuantityError(
                f"Quantity payload carries unknown field(s): {', '.join(unknown)}"
            )
        if "provenance" not in payload:
            raise AcquisitionQuantityError("Quantity payload records no provenance")
        return cls(
            value=payload.get("value"),  # type: ignore[arg-type]
            unit=payload.get("unit", ""),
            provenance=payload["provenance"],
            source=payload.get("source", "") or "",
        )

    def __float__(self) -> float:
        return float(self.value)


def as_quantity(
    x: Quantity | float,
    unit: str = "",
    provenance: Provenance = Provenance.ASSUMED,
) -> Quantity:
    """Coerce a bare number into a :class:`Quantity` at an edge.

    Callers may be lazy at the boundary, but the laziness is recorded rather than
    hidden: a bare float becomes ``ASSUMED`` with a source saying so. It never
    becomes ``MEASURED``, and it never arrives untagged.
    """
    if isinstance(x, Quantity):
        return x
    return Quantity(float(x), unit, provenance, source="caller-supplied bare value")

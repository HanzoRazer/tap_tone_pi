# INSTRUMENT CLASS: MEASUREMENT
"""Acquisition Budget Authority (DO-107A).

Answers, for one measurement configuration: what limits this measurement, what
uncertainty follows from those limits, and how large a physical difference must
exist before the Analyzer can distinguish it.

**Standard library only, transitively.** Everything importable from this package
must load on the instrument without NumPy. That rules out importing
:mod:`tap_tone_pi.uncertainty.budget` or :mod:`~tap_tone_pi.uncertainty.frequency`
from here, both of which reach NumPy — adaptation to those canonical authorities
happens at an integration boundary outside this package.

See ``docs/ACQUISITION_BUDGET_AUTHORITY.md`` for the ownership boundaries,
including which calculations delegate rather than being reimplemented here.
"""

from __future__ import annotations

from .quantities import (
    AcquisitionQuantityError,
    Provenance,
    Quantity,
    as_quantity,
)
from .specs import (
    CLOCK_TOPOLOGIES,
    CaptureSpec,
    ClockSpec,
    ConverterSpec,
    FrontEndSpec,
    SpecimenSpec,
    SweepSpec,
    spec_quantities,
)

__all__ = [
    "AcquisitionQuantityError",
    "Provenance",
    "Quantity",
    "as_quantity",
    "CLOCK_TOPOLOGIES",
    "CaptureSpec",
    "ClockSpec",
    "ConverterSpec",
    "FrontEndSpec",
    "SpecimenSpec",
    "SweepSpec",
    "spec_quantities",
]

"""Luthier Acoustics Laboratory — laboratory-side components of the TTP Analyzer.

Currently exposes the Laboratory Manual contracts: the identity and maturity
metadata for laboratory procedure documents packaged with the desktop
instrument. The read-only registry over these contracts is added alongside.

The manual documents procedures, apparatus, limits, and measurement context. It
does not execute measurements, alter engineering results, or promote
experimental methods into validated production workflows.

Imports here are deliberately narrow — no GUI dependency may enter the
Laboratory core.
"""

from tap_tone_pi.acoustic_lab.manual_contracts import (
    SCHEMA_VERSION,
    LaboratoryManualEntryV1,
    LaboratoryManualManifestV1,
    ManualContractError,
    ManualStatus,
)

__all__ = [
    "SCHEMA_VERSION",
    "LaboratoryManualEntryV1",
    "LaboratoryManualManifestV1",
    "ManualContractError",
    "ManualStatus",
]

"""Luthier Acoustics Laboratory — laboratory-side components of the TTP Analyzer.

Currently exposes the Laboratory Manual: a versioned, read-only, offline
registry of laboratory procedure documents packaged with the desktop
instrument.

The manual documents procedures, apparatus, limits, and measurement context. It
does not execute measurements, alter engineering results, or promote
experimental methods into validated production workflows.

Imports here are deliberately narrow — no GUI dependency may enter the
Laboratory core. The desktop viewer imports this package; this package does not
import the desktop viewer.
"""

from tap_tone_pi.acoustic_lab.manual_contracts import (
    SCHEMA_VERSION,
    LaboratoryManualEntryV1,
    LaboratoryManualManifestV1,
    ManualContractError,
    ManualStatus,
)
from tap_tone_pi.acoustic_lab.manual_registry import (
    ManualDocumentMissingError,
    ManualEntryNotFoundError,
    ManualRegistryError,
    ManualValidationReport,
    filter_manual_entries,
    get_manual_entry,
    list_manual_entries,
    load_laboratory_manual_manifest,
    read_manual_entry_text,
    resolve_manual_entry_path,
    validate_manual_manifest,
)

__all__ = [
    "SCHEMA_VERSION",
    "LaboratoryManualEntryV1",
    "LaboratoryManualManifestV1",
    "ManualContractError",
    "ManualStatus",
    "ManualDocumentMissingError",
    "ManualEntryNotFoundError",
    "ManualRegistryError",
    "ManualValidationReport",
    "filter_manual_entries",
    "get_manual_entry",
    "list_manual_entries",
    "load_laboratory_manual_manifest",
    "read_manual_entry_text",
    "resolve_manual_entry_path",
    "validate_manual_manifest",
]

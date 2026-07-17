# INSTRUMENT CLASS: MEASUREMENT
"""Laboratory Manual registry — read-only lookup over packaged manual resources.

Canonical location: tap_tone_pi.acoustic_lab.manual_registry

Loads the packaged manifest, lists and filters registered documents, and
resolves document paths safely beneath the manual root. Every operation is
read-only, deterministic, and offline: nothing here writes, downloads, renders,
or promotes.

The MEASUREMENT instrument class above is a boundary declaration, not a claim
that this module measures anything: it asserts that nothing here carries
interpretive authority. The registry describes document identity and maturity.
It does not judge whether a documented hypothesis is true.

Resource resolution goes through importlib.resources only. There is
deliberately no source-tree fallback pointing at a separate canonical
directory — tap_tone_pi/acoustic_lab/manual/ is the single authored copy, so
the packaged path and the authored path are the same path (DO-97 §4.2 ruling).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

try:  # Python 3.11+
    from importlib.resources.abc import Traversable
except ImportError:  # Python 3.10 — removed from importlib.abc in 3.14
    from importlib.abc import Traversable

from tap_tone_pi.acoustic_lab.manual_contracts import (
    LaboratoryManualEntryV1,
    LaboratoryManualManifestV1,
    ManualStatus,
    _coerce_status,
)

MANUAL_PACKAGE = "tap_tone_pi.acoustic_lab"
MANUAL_DIRNAME = "manual"
MANIFEST_FILENAME = "manual_manifest.json"

__all__ = [
    "MANUAL_PACKAGE",
    "MANUAL_DIRNAME",
    "MANIFEST_FILENAME",
    "ManualRegistryError",
    "ManualEntryNotFoundError",
    "ManualDocumentMissingError",
    "load_laboratory_manual_manifest",
    "list_manual_entries",
    "get_manual_entry",
    "filter_manual_entries",
    "resolve_manual_entry_path",
    "read_manual_entry_text",
    "validate_manual_manifest",
]


class ManualRegistryError(RuntimeError):
    """Raised when the packaged manual cannot be loaded or resolved."""


class ManualEntryNotFoundError(ManualRegistryError, KeyError):
    """Raised when no registered entry has the requested doc_id."""

    def __str__(self) -> str:
        # KeyError.__str__ repr-quotes its argument; keep the plain message.
        return self.args[0] if self.args else ""


class ManualDocumentMissingError(ManualRegistryError):
    """Raised when a registered document is absent from the packaged manual."""


def _manual_root() -> Traversable:
    """Return the packaged manual directory.

    The manual is package *data*, not a subpackage, so it is addressed as a
    directory beneath tap_tone_pi.acoustic_lab rather than imported.
    """
    try:
        root = resources.files(MANUAL_PACKAGE) / MANUAL_DIRNAME
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        raise ManualRegistryError(
            f"Laboratory Manual resources are not available: {MANUAL_PACKAGE!r} "
            f"is not importable. The package build may be missing manual data."
        ) from exc

    if not root.is_dir():
        raise ManualRegistryError(
            f"Laboratory Manual directory {MANUAL_DIRNAME!r} is missing from the "
            f"installed package. The package build may be missing manual data."
        )
    return root


def load_laboratory_manual_manifest() -> LaboratoryManualManifestV1:
    """Load and validate the packaged Laboratory Manual manifest.

    Raises:
        ManualRegistryError: manifest absent, unreadable, or malformed JSON.
        ManualContractError: manifest violates an identity or status rule.
    """
    manifest_resource = _manual_root() / MANIFEST_FILENAME

    try:
        raw = manifest_resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManualRegistryError(
            f"Laboratory Manual manifest {MANIFEST_FILENAME!r} is missing from the "
            f"packaged manual. The package build may be missing manual data."
        ) from exc
    except OSError as exc:
        raise ManualRegistryError(f"Could not read Laboratory Manual manifest: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManualRegistryError(
            f"Laboratory Manual manifest is not valid JSON (line {exc.lineno}, "
            f"column {exc.colno}): {exc.msg}"
        ) from exc

    return LaboratoryManualManifestV1.from_dict(parsed)


def list_manual_entries(
    manifest: LaboratoryManualManifestV1 | None = None,
) -> tuple[LaboratoryManualEntryV1, ...]:
    """Return all registered entries in authored order."""
    if manifest is None:
        manifest = load_laboratory_manual_manifest()
    return manifest.entries


def get_manual_entry(
    doc_id: str,
    manifest: LaboratoryManualManifestV1 | None = None,
) -> LaboratoryManualEntryV1:
    """Return the entry with the given stable doc_id.

    Raises:
        ManualEntryNotFoundError: no entry has that doc_id.
    """
    if manifest is None:
        manifest = load_laboratory_manual_manifest()

    for entry in manifest.entries:
        if entry.doc_id == doc_id:
            return entry

    raise ManualEntryNotFoundError(f"No Laboratory Manual entry with doc_id {doc_id!r}")


def filter_manual_entries(
    manifest: LaboratoryManualManifestV1 | None = None,
    *,
    section: str | None = None,
    status: ManualStatus | str | None = None,
) -> tuple[LaboratoryManualEntryV1, ...]:
    """Return entries matching every supplied filter, in authored order.

    An unfiltered call returns everything. Filters are exact matches, ANDed
    together. Passing no filters is not an error.

    Raises:
        ManualContractError: status is not a recognized value.
    """
    entries: Iterable[LaboratoryManualEntryV1] = list_manual_entries(manifest)

    if section is not None:
        entries = [e for e in entries if e.section == section]

    if status is not None:
        # Coerce via the shared validator so an unknown status is a loud error
        # rather than a silently empty result set.
        wanted = _coerce_status(status)
        entries = [e for e in entries if e.status is wanted]

    return tuple(entries)


def _resolve_traversable(entry: LaboratoryManualEntryV1) -> Traversable:
    """Return the packaged resource for an entry, verifying containment."""
    root = _manual_root()

    resource: Traversable = root
    for part in entry.path.split("/"):
        resource = resource / part

    # entry.path is already syntactically validated (relative, no '..'), but a
    # concrete filesystem root can still escape via symlink. Re-check against
    # the resolved real path when the resource is a real file on disk.
    try:
        root_real = Path(str(root)).resolve(strict=True)
        resource_real = Path(str(resource)).resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        # Non-filesystem loader (zipimport, etc.): syntactic validation stands.
        return resource

    if not resource_real.is_relative_to(root_real):
        raise ManualRegistryError(
            f"Registered path for {entry.doc_id!r} resolves outside the manual root: {entry.path!r}"
        )
    return resource


def resolve_manual_entry_path(
    entry: LaboratoryManualEntryV1 | str,
    manifest: LaboratoryManualManifestV1 | None = None,
) -> Path:
    """Return the on-disk path of a registered document.

    Accepts an entry or a doc_id. The returned path is guaranteed to exist and
    to lie beneath the packaged manual root.

    Raises:
        ManualEntryNotFoundError: doc_id is not registered.
        ManualDocumentMissingError: the registered file is not in the package.
        ManualRegistryError: the path escapes the manual root.
    """
    if isinstance(entry, str):
        entry = get_manual_entry(entry, manifest)

    resource = _resolve_traversable(entry)

    if not resource.is_file():
        raise ManualDocumentMissingError(
            f"Registered document for {entry.doc_id!r} is missing from the packaged "
            f"manual: {entry.path!r}"
        )

    return Path(str(resource))


def read_manual_entry_text(
    entry: LaboratoryManualEntryV1 | str,
    manifest: LaboratoryManualManifestV1 | None = None,
) -> str:
    """Return the Markdown source of a registered document, unmodified.

    The source is returned verbatim. Nothing here transforms or rewrites it.

    Raises:
        ManualEntryNotFoundError: doc_id is not registered.
        ManualDocumentMissingError: the registered file is not in the package.
    """
    if isinstance(entry, str):
        entry = get_manual_entry(entry, manifest)

    resource = _resolve_traversable(entry)

    try:
        return resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManualDocumentMissingError(
            f"Registered document for {entry.doc_id!r} is missing from the packaged "
            f"manual: {entry.path!r}"
        ) from exc
    except OSError as exc:
        raise ManualRegistryError(f"Could not read document {entry.doc_id!r}: {exc}") from exc


@dataclass(frozen=True)
class ManualValidationReport:
    """Result of a full manifest integrity check."""

    manual_revision: str
    entry_count: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def validate_manual_manifest(
    manifest: LaboratoryManualManifestV1 | None = None,
) -> ManualValidationReport:
    """Check every registered entry resolves to a real packaged document.

    Contract-level rules (unique IDs, valid status, safe paths) are enforced at
    construction; this adds the check that construction cannot make — that the
    files actually ship. Collects all problems rather than raising on the first,
    so a maintainer sees the whole picture at once.
    """
    if manifest is None:
        manifest = load_laboratory_manual_manifest()

    problems: list[str] = []

    for entry in manifest.entries:
        try:
            resolve_manual_entry_path(entry, manifest)
        except ManualRegistryError as exc:
            problems.append(f"{entry.doc_id}: {exc}")

    return ManualValidationReport(
        manual_revision=manifest.manual_revision,
        entry_count=len(manifest.entries),
        problems=tuple(problems),
    )

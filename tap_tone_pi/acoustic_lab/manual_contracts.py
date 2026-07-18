# INSTRUMENT CLASS: MEASUREMENT
"""Laboratory Manual contracts — document identity and maturity metadata.

Canonical location: tap_tone_pi.acoustic_lab.manual_contracts

These dataclasses describe *documents*, not measurements. They record which
laboratory procedures exist, where their source Markdown lives, and how mature
each one is. They do not execute measurements, interpret results, or judge
whether a documented hypothesis is true.

The MEASUREMENT instrument class above is a boundary declaration, not a claim
that this module measures anything: it asserts that nothing here carries
interpretive authority (see the instrument-class governance check in ci/).

Status vocabulary (DO-97 §4.3):
  approved    — validated procedure suitable for normal instrument use
  provisional — laboratory method under controlled evaluation
  deferred    — documented concept not authorized for execution
  superseded  — retained for lineage, not presented as a current procedure

Promotion between statuses is a separate governed action. Nothing in this
module promotes an entry.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = "laboratory_manual_manifest_v1"


class ManualStatus(str, Enum):
    """Maturity of a registered manual document."""

    APPROVED = "approved"
    PROVISIONAL = "provisional"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"


class ManualContractError(ValueError):
    """Raised when manual metadata violates an identity or safety rule."""


def _require_text(value: Any, field_name: str) -> str:
    """Return value as a non-empty stripped string or raise."""
    if not isinstance(value, str):
        raise ManualContractError(f"{field_name} must be a string, got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ManualContractError(f"{field_name} must not be empty")
    return text


def parse_manual_status(value: object) -> ManualStatus:
    """Normalize a public manual status value or raise ManualContractError.

    Accepts an existing ``ManualStatus`` or one of the serialized status
    strings. This is the public, contract-owned normalization interface: the
    registry and other callers use it instead of reaching for a private helper.
    """
    if isinstance(value, ManualStatus):
        return value
    try:
        return ManualStatus(value)
    except ValueError:
        permitted = ", ".join(s.value for s in ManualStatus)
        raise ManualContractError(
            f"status must be one of: {permitted} (got {value!r})"
        ) from None


def _validate_relative_path(value: Any) -> str:
    """Return value as a manual-root-relative POSIX path or raise.

    Rejects absolute paths, drive-qualified paths, and any '..' segment. This
    is a syntactic check on the declared path; resolution against the real
    manual root is the registry's job (see manual_registry.resolve_manual_entry_path).
    """
    text = _require_text(value, "path")
    normalized = text.replace("\\", "/")

    if normalized.startswith("/") or PurePosixPath(normalized).is_absolute():
        raise ManualContractError(f"path must be relative to the manual root, got {text!r}")
    # Catches Windows drive letters ('C:/x') and UNC-ish forms that PurePosixPath treats as relative.
    if ":" in normalized.split("/")[0]:
        raise ManualContractError(f"path must not be drive-qualified, got {text!r}")
    if ".." in PurePosixPath(normalized).parts:
        raise ManualContractError(f"path must not traverse outside the manual root, got {text!r}")

    collapsed = posixpath.normpath(normalized)
    if collapsed in (".", ""):
        raise ManualContractError(f"path must name a document, got {text!r}")
    return collapsed


@dataclass(frozen=True)
class LaboratoryManualEntryV1:
    """One registered Laboratory Manual document.

    Identity fields (doc_id, title, path, section, revision) are required.
    doc_id is the stable handle callers use; it must not change when a
    document is retitled or moved.
    """

    doc_id: str
    title: str
    path: str
    section: str
    status: ManualStatus
    revision: str
    applies_to: tuple[str, ...] = field(default_factory=tuple)
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_id", _require_text(self.doc_id, "doc_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "path", _validate_relative_path(self.path))
        object.__setattr__(self, "section", _require_text(self.section, "section"))
        object.__setattr__(self, "status", parse_manual_status(self.status))
        object.__setattr__(self, "revision", _require_text(self.revision, "revision"))

        # applies_to is a *sequence* of tags, not scalar text. A bare string or
        # bytes is iterable, so tuple() would silently shatter it into single
        # characters ("workflow" -> ('w','o',...)). Reject scalar text loudly.
        if isinstance(self.applies_to, (str, bytes, bytearray)):
            raise ManualContractError(
                "applies_to must be a sequence of tags, not scalar "
                f"{type(self.applies_to).__name__}"
            )
        try:
            applies_to = tuple(self.applies_to)
        except TypeError as exc:
            raise ManualContractError("applies_to must be an iterable of tags") from exc
        for item in applies_to:
            _require_text(item, "applies_to entry")
        object.__setattr__(self, "applies_to", applies_to)

        # Supersession consistency (DO-97G §6.1): the two facts must agree.
        if self.status is ManualStatus.SUPERSEDED:
            if self.superseded_by is None:
                raise ManualContractError(
                    f"{self.doc_id!r} is superseded but names no replacement (superseded_by)"
                )
        elif self.superseded_by is not None:
            raise ManualContractError(
                f"{self.doc_id!r} declares superseded_by but its status is "
                f"{self.status.value!r}, not 'superseded'"
            )

        if self.superseded_by is not None:
            superseded_by = _require_text(self.superseded_by, "superseded_by")
            if superseded_by == self.doc_id:
                raise ManualContractError(f"{self.doc_id!r} cannot supersede itself")
            object.__setattr__(self, "superseded_by", superseded_by)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict. Key order is stable."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "path": self.path,
            "section": self.section,
            "status": self.status.value,
            "revision": self.revision,
            "applies_to": list(self.applies_to),
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LaboratoryManualEntryV1":
        """Construct from a manifest entry dict."""
        if not isinstance(d, dict):
            raise ManualContractError(f"entry must be an object, got {type(d).__name__}")

        unknown = set(d) - {
            "doc_id",
            "title",
            "path",
            "section",
            "status",
            "revision",
            "applies_to",
            "superseded_by",
        }
        if unknown:
            raise ManualContractError(f"unknown entry field(s): {', '.join(sorted(unknown))}")

        missing = {"doc_id", "title", "path", "section", "status", "revision"} - set(d)
        if missing:
            raise ManualContractError(f"entry missing required field(s): {', '.join(sorted(missing))}")

        applies_to = d.get("applies_to") or []
        if not isinstance(applies_to, list):
            raise ManualContractError("applies_to must be a list")

        return cls(
            doc_id=d["doc_id"],
            title=d["title"],
            path=d["path"],
            section=d["section"],
            status=d["status"],
            revision=d["revision"],
            applies_to=tuple(applies_to),
            superseded_by=d.get("superseded_by"),
        )


@dataclass(frozen=True)
class LaboratoryManualManifestV1:
    """The versioned Laboratory Manual manifest.

    Entry order is preserved exactly as authored — it is the manual's reading
    order, not an incidental detail. Nothing here sorts or reorders entries.
    """

    manual_revision: str
    entries: tuple[LaboratoryManualEntryV1, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "manual_revision", _require_text(self.manual_revision, "manual_revision"))
        object.__setattr__(self, "schema_version", _require_text(self.schema_version, "schema_version"))
        object.__setattr__(self, "entries", tuple(self.entries))

        if self.schema_version != SCHEMA_VERSION:
            raise ManualContractError(
                f"unsupported manifest schema_version {self.schema_version!r} "
                f"(this build reads {SCHEMA_VERSION!r})"
            )

        seen: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, LaboratoryManualEntryV1):
                raise ManualContractError(
                    f"entries must be LaboratoryManualEntryV1, got {type(entry).__name__}"
                )
            if entry.doc_id in seen:
                raise ManualContractError(f"duplicate doc_id in manifest: {entry.doc_id!r}")
            seen.add(entry.doc_id)

        # Invariant 4: a superseded entry names its replacement when one exists.
        # A dangling reference is a registration error, not a display concern.
        for entry in self.entries:
            if entry.superseded_by is not None and entry.superseded_by not in seen:
                raise ManualContractError(
                    f"{entry.doc_id!r} is superseded by unknown doc_id {entry.superseded_by!r}"
                )

        # Invariant 5: supersession must be acyclic. Walk each chain tracking the
        # active path so a loop is caught the moment a node reappears on its own
        # walk — a single global visited set would miss the active recursion.
        replacement_by_id = {
            entry.doc_id: entry.superseded_by
            for entry in self.entries
            if entry.superseded_by is not None
        }
        for start in replacement_by_id:
            path: list[str] = [start]
            on_path = {start}
            node = replacement_by_id[start]
            while node is not None:
                if node in on_path:
                    path.append(node)
                    cycle = path[path.index(node):]
                    raise ManualContractError(
                        "supersession cycle detected: " + " -> ".join(cycle)
                    )
                path.append(node)
                on_path.add(node)
                node = replacement_by_id.get(node)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict. Entry order is preserved."""
        return {
            "schema_version": self.schema_version,
            "manual_revision": self.manual_revision,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LaboratoryManualManifestV1":
        """Construct from a parsed manifest document."""
        if not isinstance(d, dict):
            raise ManualContractError(f"manifest must be an object, got {type(d).__name__}")

        unknown = set(d) - {"schema_version", "manual_revision", "entries"}
        if unknown:
            raise ManualContractError(f"unknown manifest field(s): {', '.join(sorted(unknown))}")

        missing = {"schema_version", "manual_revision"} - set(d)
        if missing:
            raise ManualContractError(f"manifest missing required field(s): {', '.join(sorted(missing))}")

        entries = d.get("entries")
        if entries is None:
            raise ManualContractError("manifest missing required field(s): entries")
        if not isinstance(entries, list):
            raise ManualContractError("entries must be a list")

        return cls(
            manual_revision=d["manual_revision"],
            entries=tuple(LaboratoryManualEntryV1.from_dict(e) for e in entries),
            schema_version=d["schema_version"],
        )

# INSTRUMENT CLASS: MEASUREMENT
"""The acquisition budget as session evidence (DO-107B).

A Phase 2 session records what was captured. An ``acquisition_budget_v1`` records
what the chain that captured it could resolve. Keeping the second beside the
first is what lets a later reader ask *what was this instrument capable of on the
day these numbers were taken* without reconstructing the answer from memory.

**One file, one session, one budget.** The budget lands at
``<session>/meta/acquisition_budget.json`` carrying the exact serialized payload
— not a summary of it, and not a copy flattened into session metadata, which
would leave two documents free to disagree. Replacing an attached budget is
refused unless the caller says so outright.

**Attachment is by path, because that is the mechanism this repository already
has.** ``scripts/phase2/export_viewer_pack_v1.py`` discovers every optional
evidence document the same way — ``meta/<name>.json`` beside the session, copied
into the pack, no registration step. Adding a pointer to ``metadata.json`` would
mean rewriting a file the capture run already wrote, and a reference that can
drift from the file it names is worse than a convention that cannot.

**A session without a budget is a normal session.** Every Phase 2 session
recorded before this existed has none, and none of them becomes invalid or
incomplete for it: :func:`load_acquisition_budget` returns ``None`` and says
nothing further. What is *not* silent is a budget that is present and unreadable
— that raises, because a corrupt record reading as an absent one is how evidence
disappears quietly.

**Attaching a budget acquires no data.** This module writes a document about a
session; it captures nothing, and the ``synthetic`` flag the session already
carries is untouched by it. A fixture session with an acquisition budget attached
is still a fixture session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tap_tone_pi.uncertainty.acquisition import (
    AcquisitionBudgetV1,
    validate_acquisition_budget,
)

__all__ = [
    "ACQUISITION_BUDGET_FILENAME",
    "ACQUISITION_BUDGET_RELPATH",
    "SessionAcquisitionError",
    "acquisition_budget_path",
    "attach_acquisition_budget",
    "find_acquisition_budget",
    "has_acquisition_budget",
    "load_acquisition_budget",
    "load_acquisition_budget_payload",
]

ACQUISITION_BUDGET_FILENAME = "acquisition_budget.json"

#: Where a budget is written, and where the viewer pack expects to find it.
ACQUISITION_BUDGET_RELPATH = f"meta/{ACQUISITION_BUDGET_FILENAME}"


class SessionAcquisitionError(ValueError):
    """A session's acquisition budget cannot be written or read truthfully."""


def acquisition_budget_path(session_dir: Path | str) -> Path:
    """The canonical location of a session's acquisition budget."""
    return Path(session_dir).expanduser() / "meta" / ACQUISITION_BUDGET_FILENAME


def find_acquisition_budget(session_dir: Path | str) -> Path | None:
    """The attached budget's path, or ``None``.

    Looks in ``meta/`` first and then beside the session, matching how the
    viewer-pack exporter locates every other optional evidence document. A
    hand-placed file is found; nothing is moved or rewritten to normalize it.
    """
    root = Path(session_dir).expanduser()
    for candidate in (
        root / "meta" / ACQUISITION_BUDGET_FILENAME,
        root / ACQUISITION_BUDGET_FILENAME,
    ):
        if candidate.is_file():
            return candidate
    return None


def has_acquisition_budget(session_dir: Path | str) -> bool:
    """Whether this session carries a budget. Absence is legal and common."""
    return find_acquisition_budget(session_dir) is not None


def attach_acquisition_budget(
    session_dir: Path | str,
    budget: AcquisitionBudgetV1,
    *,
    replace: bool = False,
) -> Path:
    """Write ``budget`` into ``session_dir`` as session evidence.

    The bytes are the canonical serialization of the budget and nothing else, so
    what a reader loads back is what was computed rather than a rendering of it.
    The semantic contract is checked first: a payload whose evidence grade
    disagrees with its own reasons, or whose combination does not match its own
    contributors, is refused rather than filed.

    Args:
        session_dir: an existing session directory.
        budget: the computed budget to attach.
        replace: permit overwriting a budget this session already carries.

    Raises:
        SessionAcquisitionError: if the session does not exist, if a budget is
            already attached and ``replace`` is false, or if the payload fails
            its own contract.
    """
    root = Path(session_dir).expanduser()
    if not root.is_dir():
        raise SessionAcquisitionError(
            f"session directory does not exist: {root}. A budget describes the "
            "chain that acquired a session; there is no session here to describe"
        )

    existing = find_acquisition_budget(root)
    if existing is not None and not replace:
        raise SessionAcquisitionError(
            f"session already carries an acquisition budget at {existing.name}. "
            "A session records one acquisition chain; pass replace=True to state "
            "that superseding it is intended"
        )

    payload = budget.as_dict()
    problems = validate_acquisition_budget(payload)
    if problems:
        raise SessionAcquisitionError(
            "budget fails its own contract and was not attached: " + "; ".join(problems)
        )

    target = root / "meta" / ACQUISITION_BUDGET_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    if existing is not None and existing != target:
        # A hand-placed copy beside the session would now disagree with the
        # canonical one. Two budgets is the state this module exists to prevent.
        existing.unlink()
    return target


def load_acquisition_budget(session_dir: Path | str) -> AcquisitionBudgetV1 | None:
    """Read a session's attached budget, or ``None`` if it carries none.

    Raises:
        SessionAcquisitionError: if a budget is present and cannot be read as
            one. An unreadable record must not be indistinguishable from a
            session that never had one.
    """
    path = find_acquisition_budget(session_dir)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionAcquisitionError(
            f"{path.name} is attached to this session and is not readable JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise SessionAcquisitionError(
            f"{path.name} is attached to this session and is not an object"
        )
    try:
        return AcquisitionBudgetV1.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionAcquisitionError(
            f"{path.name} is attached to this session and is not an "
            f"acquisition_budget_v1 record: {exc}"
        ) from exc


def load_acquisition_budget_payload(session_dir: Path | str) -> dict[str, Any] | None:
    """The attached budget's bytes, parsed but not reconstructed.

    For readers that need what the file says rather than what it deserializes to
    — a digest check, or the contract validator, which must see the payload as
    written.
    """
    path = find_acquisition_budget(session_dir)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionAcquisitionError(
            f"{path.name} is attached to this session and is not readable JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise SessionAcquisitionError(
            f"{path.name} is attached to this session and is not an object"
        )
    return payload

# INSTRUMENT CLASS: MEASUREMENT
"""Repository capability audit (DO-102).

Takes a declared capability inventory and tests it against the repository tree:
does the code named actually exist, does an IMPLEMENTED claim have tests behind
it, does anything claim hardware verification nobody has witnessed.

The audit does not infer capability from filenames. A capability is a claim
somebody is prepared to make; this module's job is to check the claim, not to
manufacture one. An inventory that disagrees with the tree fails loudly rather
than being silently corrected — a claim that quietly repairs itself is not
evidence.

Output ordering is deterministic: capabilities are sorted by identifier, so two
audits of the same tree produce byte-identical JSON and a stable digest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from tap_tone_pi.grant_readiness.contracts import (
    CapabilityEvidenceV1,
    GrantReadinessAuditV1,
)
from tap_tone_pi.grant_readiness.errors import CapabilityAuditError
from tap_tone_pi.grant_readiness.inventory import (
    INVENTORY_LIMITATIONS,
    TTP_CAPABILITY_INVENTORY,
)
from tap_tone_pi.grant_readiness.validation import (
    ValidationFinding,
    evidence_digest,
    raise_for_findings,
    validate_capability_inventory,
    validate_no_unwitnessed_hardware_claim,
)

# The repository root, resolved from this module's location:
# tap_tone_pi/grant_readiness/audit.py -> two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]


def audit_findings(
    inventory: Sequence[CapabilityEvidenceV1] | None = None,
    *,
    repo_root: Path | None = None,
) -> list[ValidationFinding]:
    """Return every problem with an inventory, checked against the tree."""
    entries = TTP_CAPABILITY_INVENTORY if inventory is None else tuple(inventory)
    root = REPO_ROOT if repo_root is None else repo_root

    findings = list(validate_capability_inventory(entries, repo_root=root))
    findings.extend(validate_no_unwitnessed_hardware_claim(entries))
    return findings


def build_grant_readiness_audit(
    *,
    audit_id: str,
    generated_at: str,
    inventory: Sequence[CapabilityEvidenceV1] | None = None,
    repo_root: Path | None = None,
    repository_commit: str | None = None,
    limitations: Sequence[str] | None = None,
    strict: bool = True,
) -> GrantReadinessAuditV1:
    """Build an audit from a declared inventory plus repository state.

    Args:
        audit_id: Identifier for this audit.
        generated_at: ISO-8601 UTC instant.
        inventory: Capability claims; defaults to the shipped inventory.
        repo_root: Tree to check evidence paths against; defaults to this
            repository.
        repository_commit: Commit the audit was generated against, where known.
            Resolved by the caller — this module runs no subprocess.
        limitations: What the audit does not establish; defaults to the shipped
            limitations.
        strict: Raise on the first finding. Set ``False`` only to inspect a
            broken inventory; a non-strict audit is not publishable evidence.

    Returns:
        A :class:`GrantReadinessAuditV1` with capabilities in deterministic
        order.

    Raises:
        CapabilityAuditError: When ``strict`` and the inventory disagrees with
            the repository.
    """
    entries = TTP_CAPABILITY_INVENTORY if inventory is None else tuple(inventory)

    if strict:
        raise_for_findings(
            audit_findings(entries, repo_root=repo_root),
            error_cls=CapabilityAuditError,
        )

    ordered = tuple(sorted(entries, key=lambda entry: entry.capability_id))

    return GrantReadinessAuditV1(
        audit_id=audit_id,
        generated_at=generated_at,
        capabilities=ordered,
        repository_commit=repository_commit,
        limitations=tuple(
            INVENTORY_LIMITATIONS if limitations is None else limitations
        ),
    )


def audit_digest(audit: GrantReadinessAuditV1) -> str:
    """Return the audit's canonical SHA-256, for citing it from a report."""
    return evidence_digest(audit.to_dict())


__all__ = [
    "REPO_ROOT",
    "audit_findings",
    "build_grant_readiness_audit",
    "audit_digest",
]

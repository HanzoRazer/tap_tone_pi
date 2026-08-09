"""Repository capability audit (DO-102, Commit 5).

The load-bearing test here is the drift check: the production inventory must
agree, entry for entry, with the baseline frozen in
``tests/test_nsf_capability_baseline.py`` before any of this code existed.
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.grant_readiness import (
    CapabilityEvidenceV1,
    CapabilityStatus,
    GrantReadinessAuditV1,
    GrantReadinessErrorCode,
    HardwareVerification,
)
from tap_tone_pi.grant_readiness.audit import (
    REPO_ROOT,
    audit_digest,
    audit_findings,
    build_grant_readiness_audit,
)
from tap_tone_pi.grant_readiness.errors import CapabilityAuditError
from tap_tone_pi.grant_readiness.inventory import (
    INVENTORY_LIMITATIONS,
    TTP_CAPABILITY_INVENTORY,
)

from tests.test_nsf_capability_baseline import CAPABILITY_BASELINE

jsonschema = pytest.importorskip("jsonschema")

UTC_NOW = "2026-08-09T12:00:00+00:00"


def build(**overrides) -> GrantReadinessAuditV1:
    kwargs = {"audit_id": "audit-1", "generated_at": UTC_NOW}
    kwargs.update(overrides)
    return build_grant_readiness_audit(**kwargs)


# ---------------------------------------------------------------------------
# The drift check
# ---------------------------------------------------------------------------


class TestInventoryMatchesFrozenBaseline:
    """The audit cannot be rewritten to agree with itself."""

    def test_same_capability_ids(self):
        assert [entry.capability_id for entry in TTP_CAPABILITY_INVENTORY] == [
            entry["capability_id"] for entry in CAPABILITY_BASELINE
        ]

    @pytest.mark.parametrize(
        "index",
        range(len(CAPABILITY_BASELINE)),
        ids=lambda i: CAPABILITY_BASELINE[i]["capability_id"],
    )
    def test_entry_matches_baseline(self, index):
        declared = TTP_CAPABILITY_INVENTORY[index]
        frozen = CAPABILITY_BASELINE[index]

        assert declared.capability_id == frozen["capability_id"]
        assert declared.name == frozen["name"]
        assert declared.status.value == frozen["status"]
        assert declared.implementation_paths == frozen["implementation_paths"]
        assert declared.test_paths == frozen["test_paths"]
        assert declared.hardware_verified.value == frozen["hardware_verified"]
        assert declared.notes == frozen["notes"]

    def test_inventory_stays_bounded(self):
        assert 15 <= len(TTP_CAPABILITY_INVENTORY) <= 25


# ---------------------------------------------------------------------------
# The shipped inventory against the tree
# ---------------------------------------------------------------------------


class TestShippedInventory:
    def test_audits_clean_against_the_repository(self):
        assert audit_findings() == []

    def test_nothing_claims_witnessed_hardware(self):
        for entry in TTP_CAPABILITY_INVENTORY:
            assert entry.hardware_verified is not (
                HardwareVerification.VERIFIED_ON_HARDWARE
            )

    def test_every_status_is_represented_honestly(self):
        statuses = {entry.status for entry in TTP_CAPABILITY_INVENTORY}
        # A baseline in which everything is IMPLEMENTED would not be an audit.
        assert CapabilityStatus.EXPERIMENTAL in statuses
        assert CapabilityStatus.PARTIAL in statuses

    def test_limitations_are_declared(self):
        assert INVENTORY_LIMITATIONS
        for limitation in INVENTORY_LIMITATIONS:
            assert limitation.strip()

    def test_limitations_separate_implementation_from_accuracy(self):
        text = " ".join(INVENTORY_LIMITATIONS).lower()
        assert "not a statement about measurement accuracy" in text
        assert "no traceability is claimed" in text


# ---------------------------------------------------------------------------
# Audit construction
# ---------------------------------------------------------------------------


class TestBuildAudit:
    def test_builds_from_the_shipped_inventory(self):
        audit = build()
        assert len(audit.capabilities) == len(TTP_CAPABILITY_INVENTORY)
        assert audit.schema_version == "nsf_grant_readiness_audit_v1"

    def test_capabilities_are_sorted_deterministically(self):
        ids = [entry.capability_id for entry in build().capabilities]
        assert ids == sorted(ids)

    def test_two_audits_of_the_same_tree_are_identical(self):
        first = json.dumps(build().to_dict(), sort_keys=True, allow_nan=False)
        second = json.dumps(build().to_dict(), sort_keys=True, allow_nan=False)
        assert first == second

    def test_digest_is_stable(self):
        assert audit_digest(build()) == audit_digest(build())

    def test_digest_changes_when_a_status_changes(self):
        altered = tuple(
            CapabilityEvidenceV1(
                capability_id=entry.capability_id,
                name=entry.name,
                status=(
                    CapabilityStatus.PARTIAL
                    if entry.capability_id == "unified_cli"
                    else entry.status
                ),
                implementation_paths=entry.implementation_paths,
                test_paths=entry.test_paths,
                evidence_refs=entry.evidence_refs,
                hardware_verified=entry.hardware_verified,
                notes=entry.notes,
            )
            for entry in TTP_CAPABILITY_INVENTORY
        )
        assert audit_digest(build(inventory=altered)) != audit_digest(build())

    def test_repository_commit_is_recorded_when_supplied(self):
        assert build(repository_commit="9ab7aad").repository_commit == "9ab7aad"

    def test_repository_commit_is_optional(self):
        assert build().repository_commit is None

    def test_status_counts_sum_to_the_capability_count(self):
        audit = build()
        assert sum(audit.status_counts.values()) == len(audit.capabilities)

    def test_hardware_verified_count_is_zero(self):
        assert build().hardware_verified_count == 0

    def test_default_limitations_travel_with_the_audit(self):
        assert build().limitations == INVENTORY_LIMITATIONS


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def evidence(**overrides) -> CapabilityEvidenceV1:
    kwargs = {
        "capability_id": "unified_cli",
        "name": "Unified CLI",
        "status": CapabilityStatus.IMPLEMENTED,
        "implementation_paths": ("tap_tone_pi/cli/main.py",),
        "test_paths": ("tests/test_cli_validators.py",),
        "hardware_verified": HardwareVerification.NOT_APPLICABLE,
        "notes": "n",
    }
    kwargs.update(overrides)
    return CapabilityEvidenceV1(**kwargs)


class TestAuditRejections:
    def test_implemented_without_evidence_is_refused(self):
        with pytest.raises(CapabilityAuditError) as exc:
            build(inventory=(evidence(implementation_paths=(), test_paths=()),))
        assert exc.value.code is (
            GrantReadinessErrorCode.MISSING_IMPLEMENTATION_EVIDENCE
        )

    def test_unresolvable_path_is_refused(self):
        with pytest.raises(CapabilityAuditError) as exc:
            build(inventory=(evidence(implementation_paths=("tap_tone_pi/ghost.py",)),))
        assert exc.value.code is GrantReadinessErrorCode.UNRESOLVED_EVIDENCE_PATH

    def test_duplicate_capability_id_is_refused(self):
        with pytest.raises(CapabilityAuditError) as exc:
            build(inventory=(evidence(), evidence()))
        assert exc.value.code is GrantReadinessErrorCode.DUPLICATE_CAPABILITY_ID

    def test_witnessed_hardware_claim_is_refused(self):
        with pytest.raises(CapabilityAuditError) as exc:
            build(
                inventory=(
                    evidence(
                        hardware_verified=HardwareVerification.VERIFIED_ON_HARDWARE
                    ),
                )
            )
        assert exc.value.code is (GrantReadinessErrorCode.INVALID_HARDWARE_VERIFICATION)

    def test_planned_capability_naming_code_is_refused(self):
        with pytest.raises(CapabilityAuditError) as exc:
            build(inventory=(evidence(status=CapabilityStatus.PLANNED),))
        assert exc.value.code is (
            GrantReadinessErrorCode.CONTRADICTORY_CAPABILITY_CLAIM
        )

    def test_every_finding_is_reported_not_just_the_first(self):
        broken = (
            evidence(implementation_paths=(), test_paths=()),
            evidence(capability_id="other", implementation_paths=("nope.py",)),
        )
        with pytest.raises(CapabilityAuditError) as exc:
            build(inventory=broken)
        assert len(exc.value.context["findings"]) >= 2

    def test_non_strict_mode_still_builds_for_inspection(self):
        audit = build(
            inventory=(evidence(implementation_paths=("tap_tone_pi/ghost.py",)),),
            strict=False,
        )
        assert len(audit.capabilities) == 1


# ---------------------------------------------------------------------------
# The generated audit is a valid artifact
# ---------------------------------------------------------------------------


class TestGeneratedAuditIsValid:
    @pytest.fixture(scope="class")
    def schema(self) -> dict:
        path = REPO_ROOT / "contracts" / "nsf_grant_readiness_audit_v1.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_validates_against_its_schema(self, schema):
        jsonschema.validate(build().to_dict(), schema)

    def test_round_trips(self):
        audit = build()
        assert GrantReadinessAuditV1.from_dict(audit.to_dict()) == audit

    def test_carries_no_host_paths(self):
        text = json.dumps(build().to_dict())
        assert str(REPO_ROOT) not in text
        assert "C:\\" not in text

    def test_repo_root_resolves_to_the_repository(self):
        assert (REPO_ROOT / "pyproject.toml").exists()
        assert (REPO_ROOT / "tap_tone_pi" / "grant_readiness").is_dir()

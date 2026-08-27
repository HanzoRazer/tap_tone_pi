"""E1 physical ownership census integrity (DO-104R).

Kept separate from ``test_e1_hardware_bom.py`` deliberately, and not because
this is a new dev order. The census is the authority on **possession**, which is
established only by someone physically looking; the BOM suite is the authority
on **design and selection**, established on paper. Putting possession
invariants into the BOM suite would conflate the two, which is the specific
confusion the whole DO-104O/DO-104R sequence exists to prevent.

The line these tests hold: *the census may not claim more than it observed.*
Its most dangerous failure is not an error - it is an item nobody mentioned
quietly reading as absent, because absence is what authorizes a purchase.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HARDWARE = REPO_ROOT / "docs" / "hardware"


def load_checker():
    path = REPO_ROOT / "scripts" / "check_e1_hardware_bom.py"
    spec = importlib.util.spec_from_file_location("check_e1_hardware_bom", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return load_checker()


@pytest.fixture(scope="module")
def census(checker):
    return checker.parse_optional_table(checker.CENSUS_PATH, checker.CENSUS_KEY)


@pytest.fixture(scope="module")
def census_text():
    return (HARDWARE / "TTP_E1_OWNERSHIP_CENSUS.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sprints():
    return (REPO_ROOT / "SPRINTS.md").read_text(encoding="utf-8")


_CHECKER = load_checker()
REQUIRED_ROLES = _CHECKER.CENSUS_REQUIRED_ROLES
METHODS = _CHECKER.OBSERVATION_METHODS


def row(category="Shaker / exciter", role="SHAKER-001", **overrides):
    """One census row, valid unless a test breaks it on purpose."""
    base = {
        "Category": category,
        "BOM role": role,
        "Ownership": "CONFIRMED_ABSENT",
        "Manufacturer": "—",
        "Model": "—",
        "Serial / asset ID": "—",
        "Qty": "0",
        "Condition": "—",
        "Location": "—",
        "Observation method": "OPERATOR_ATTESTATION",
        "Disposition": "NOT_APPLICABLE",
    }
    base.update(overrides)
    return base


def owned(**overrides):
    """A row claiming possession, which must therefore carry identity."""
    base = {
        "Ownership": "CONFIRMED_PRESENT",
        "Manufacturer": "Some Manufacturer",
        "Model": "Some Model",
        "Serial / asset ID": "SN-000123",
        "Qty": "1",
        "Condition": "good",
        "Disposition": "COMPATIBILITY_REQUIRES_VERIFICATION",
    }
    base.update(overrides)
    return row(**base)


def full_census(**per_role):
    """All ten categories, absent by default, with named roles overridden."""
    rows = [row(role=r) for r in REQUIRED_ROLES]
    rows.append(row(category="Speaker / Phase 2A driver", role="— (not an E1 BOM row)"))
    return [per_role.get(r["BOM role"].replace("-", "_"), r) for r in rows]


class TestTheCommittedCensus:
    def test_the_checker_passes_the_committed_documents(self, checker):
        assert checker.main([]) == 0

    def test_the_census_was_performed(self, checker, census_text):
        assert checker.census_status(census_text) == "PERFORMED"

    def test_all_ten_categories_are_covered(self, checker, census):
        assert len(census) == checker.CENSUS_REQUIRED_CATEGORY_COUNT
        assert checker.validate_census_role_coverage(census) == []

    def test_every_category_is_resolved(self, census):
        # No category was left UNKNOWN, so nothing is pending re-inspection.
        assert {r["Ownership"] for r in census} == {"CONFIRMED_ABSENT"}

    def test_nothing_is_owned_so_nothing_is_assessed(self, census):
        assert {r["Disposition"] for r in census} == {"NOT_APPLICABLE"}

    def test_no_identity_was_fabricated(self, checker, census):
        for r in census:
            assert not checker.is_set(r["Serial / asset ID"]), r["Category"]
            assert not checker.is_set(r["Manufacturer"]), r["Category"]

    def test_the_method_is_attestation_not_inspection(self, census):
        # A negative result is answered by the absence of a thing, which cannot
        # be handled or photographed. Recording it as hands-on inspection would
        # overstate the evidence.
        assert {r["Observation method"] for r in census} == {"OPERATOR_ATTESTATION"}

    def test_the_register_gained_no_rows(self, checker):
        register = checker.parse_table(checker.REGISTER_PATH, "local_id")
        assert len(register) == 13
        assert {r["inspection_status"] for r in register} == {"NOT_RECEIVED"}


class TestCensusSemantics:
    def test_an_absent_item_is_accepted(self, checker):
        assert checker.check_census(full_census(), [], "PERFORMED") == []

    def test_an_unknown_item_is_accepted(self, checker):
        rows = full_census(
            SHAKER_001=row(Ownership="UNKNOWN", **{"Observation method": "—"})
        )
        assert checker.check_census(rows, [], "PERFORMED") == []

    def test_an_owned_item_is_accepted_with_identity(self, checker):
        assert (
            checker.check_census(full_census(SHAKER_001=owned()), [], "PERFORMED") == []
        )

    def test_an_omitted_item_does_not_silently_become_absent(self, checker):
        # The failure that matters most. A category nobody mentioned must be
        # reported as missing, never read as absence - absence authorizes a
        # purchase and silence does not.
        rows = [r for r in full_census() if r["BOM role"] != "FORCE-001"]
        problems = checker.check_census(rows, [], "PERFORMED")
        assert any("FORCE-001" in p for p in problems)

    @pytest.mark.parametrize("missing", REQUIRED_ROLES)
    def test_every_required_role_must_appear(self, checker, missing):
        rows = [r for r in full_census() if r["BOM role"] != missing]
        assert any(missing in p for p in checker.validate_census_role_coverage(rows))

    def test_an_unperformed_census_may_not_claim_findings(self, checker):
        problems = checker.check_census(full_census(), [], "NOT_PERFORMED")
        assert any("NOT_PERFORMED" in p for p in problems)

    def test_a_performed_census_must_establish_something(self, checker):
        rows = [
            row(role=r, Ownership="UNKNOWN", **{"Observation method": "—"})
            for r in checker.CENSUS_REQUIRED_ROLES
        ]
        rows.append(
            row(
                category="Speaker",
                role="—",
                Ownership="UNKNOWN",
                **{"Observation method": "—"},
            )
        )
        problems = checker.check_census(rows, [], "PERFORMED")
        assert any("establishes nothing" in p for p in problems)

    def test_an_unknown_census_status_is_refused(self, checker):
        assert any(
            "census status" in p
            for p in checker.check_census(full_census(), [], "MOSTLY_DONE")
        )


class TestIdentity:
    def test_an_owned_item_without_identity_is_refused(self, checker):
        rows = [owned(**{"Serial / asset ID": "—"})]
        problems = checker.validate_owned_asset_identity(rows, [])
        assert any("no serial or asset identifier" in p for p in problems)

    def test_an_owned_item_without_a_model_is_refused(self, checker):
        rows = [owned(Model="—")]
        assert any(
            "records no model" in p
            for p in checker.validate_owned_asset_identity(rows, [])
        )

    def test_a_locally_assigned_asset_id_satisfies_identity(self, checker):
        # A non-serialised fixture still needs to be distinguishable.
        rows = [owned(**{"Serial / asset ID": "TTP-ASSET-021"})]
        assert checker.validate_owned_asset_identity(rows, []) == []

    def test_an_absent_item_carrying_a_serial_is_refused(self, checker):
        # A fabricated observation: nobody has a serial number for a thing they
        # do not have.
        rows = [row(**{"Serial / asset ID": "SN-999"})]
        problems = checker.validate_owned_asset_identity(rows, [])
        assert any("an absent item has no serial number" in p for p in problems)

    def test_an_unknown_ownership_value_is_refused(self, checker):
        assert any(
            "unknown ownership" in p
            for p in checker.validate_owned_asset_identity(
                [row(Ownership="PROBABLY")], []
            )
        )


class TestObservationMethod:
    @pytest.mark.parametrize("method", METHODS)
    def test_each_recognised_method_is_accepted(self, checker, method):
        rows = [row(**{"Observation method": method})]
        assert checker.validate_census_observation_method(rows) == []

    def test_an_established_state_needs_a_method(self, checker):
        rows = [row(**{"Observation method": "—"})]
        assert any(
            "observation method" in p
            for p in checker.validate_census_observation_method(rows)
        )

    def test_an_unknown_row_needs_no_method(self, checker):
        rows = [row(Ownership="UNKNOWN", **{"Observation method": "—"})]
        assert checker.validate_census_observation_method(rows) == []

    def test_an_invented_method_is_refused(self, checker):
        rows = [row(**{"Observation method": "I_ASSUME_SO"})]
        assert checker.validate_census_observation_method(rows)


class TestOwnershipAndCompatibilityAreIndependent:
    def test_owning_something_does_not_make_it_compatible(self, checker):
        # OWNED != COMPATIBLE. An owned item still needs a real disposition.
        rows = [owned(Disposition="NOT_APPLICABLE")]
        problems = checker.validate_ownership_compatibility_pair(rows)
        assert any("needs a real disposition" in p for p in problems)

    def test_an_owned_item_may_remain_unverified(self, checker):
        rows = [owned(Disposition="COMPATIBILITY_REQUIRES_VERIFICATION")]
        assert checker.validate_ownership_compatibility_pair(rows) == []

    def test_an_owned_item_may_be_incompatible(self, checker):
        rows = [owned(Disposition="INCOMPATIBLE")]
        assert checker.validate_ownership_compatibility_pair(rows) == []

    def test_an_unowned_item_cannot_have_been_assessed(self, checker):
        rows = [row(Disposition="COMPATIBLE")]
        problems = checker.validate_ownership_compatibility_pair(rows)
        assert any("nothing unowned has been assessed" in p for p in problems)

    def test_an_unknown_disposition_is_refused(self, checker):
        assert any(
            "disposition" in p
            for p in checker.validate_ownership_compatibility_pair(
                [owned(Disposition="FINE")]
            )
        )


class TestTheSelectionBoundary:
    """Census results may not become selections or purchases."""

    def test_the_census_records_no_selection_state(self, census_text):
        for claim in ("SELECTED", "PURCHASE_AUTHORIZED", "ORDERED"):
            for line in census_text.splitlines():
                if line.startswith("|") and claim in line:
                    pytest.fail(f"census row carries {claim}: {line}")

    def test_confirmed_absent_does_not_authorize_purchase(self, checker):
        # The precondition is satisfied by the census; the authorization is not
        # created by it. Every candidate stays on HOLD.
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        assert {r["procurement_action"] for r in candidates} == {"HOLD"}

    def test_the_census_makes_recommendation_legal_but_not_actioned(self, checker):
        # RECOMMEND_PURCHASE requires CONFIRMED_ABSENT, so the census unlocks it
        # without performing it. Both halves are asserted.
        rows = [
            {
                "candidate_id": "X-001",
                "ownership": "CONFIRMED_ABSENT",
                "procurement_action": "RECOMMEND_PURCHASE",
            }
        ]
        assert checker.validate_procurement_semantics(rows) == []
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        assert not any(
            r["procurement_action"] == "RECOMMEND_PURCHASE" for r in candidates
        )

    def test_no_hardware_is_represented_as_received(self, checker):
        bom = checker.parse_table(checker.BOM_PATH, "local_id")
        for r in bom:
            assert checker.rung(r["status"]) < checker.rung("RECEIVED"), r["local_id"]


class TestBacklogDisposition:
    def test_b014_remains_open(self, sprints):
        block = sprints.split("### B-014")[1].split("###")[0]
        assert "**Status:** open" in block

    def test_b015_remains_open(self, sprints):
        block = sprints.split("### B-015")[1].split("###")[0]
        assert "**Status:** open" in block

    def test_an_unperformed_census_could_not_have_closed_b016(self, checker):
        # F.27, held as a property of the checker rather than of prose.
        problems = checker.check_census(full_census(), [], "NOT_PERFORMED")
        assert problems


class TestARepresentativeMixedCensus:
    """G: the shapes the real census does not contain, guarded for the future.

    The committed census is uniformly absent, so none of the owned-equipment
    paths are exercised by it. This builds the mixed case the order asks for -
    an exact match, a confirmed absence, an unknown, an owned alternate needing
    verification, and unexpected equipment - and runs it through the same checks.
    """

    @pytest.fixture
    def mixed(self, checker):
        rows = full_census(
            HOST_001=owned(
                category="Raspberry Pi 5",
                role="HOST-001",
                Manufacturer="Raspberry Pi",
                Model="Raspberry Pi 5 8GB",
                Disposition="COMPATIBLE",
            ),
            ADC_001=owned(
                category="Audio interface (alternate)",
                role="ADC-001",
                Manufacturer="Some Other Vendor",
                Model="Two-Channel Interface",
                Disposition="COMPATIBILITY_REQUIRES_VERIFICATION",
            ),
            MIC_001=row(
                category="Microphone",
                role="MIC-001",
                Ownership="UNKNOWN",
                **{"Observation method": "—"},
            ),
        )
        return rows

    def test_the_mixed_census_validates(self, checker, mixed):
        assert checker.check_census(mixed, [], "PERFORMED") == []

    def test_each_state_is_represented(self, mixed):
        assert {r["Ownership"] for r in mixed} == {
            "CONFIRMED_PRESENT",
            "CONFIRMED_ABSENT",
            "UNKNOWN",
        }

    def test_an_owned_exact_match_may_be_compatible(self, checker, mixed):
        host = next(r for r in mixed if r["BOM role"] == "HOST-001")
        assert host["Disposition"] == "COMPATIBLE"
        assert checker.validate_ownership_compatibility_pair([host]) == []

    def test_an_owned_alternate_stays_unverified(self, checker, mixed):
        # 4.7: an alternate creates a reconciliation question, not a
        # substitution. It may not arrive as COMPATIBLE on category alone.
        adc = next(r for r in mixed if r["BOM role"] == "ADC-001")
        assert adc["Disposition"] == "COMPATIBILITY_REQUIRES_VERIFICATION"

    def test_the_unknown_row_blocks_nothing_else(self, checker, mixed):
        assert checker.validate_census_role_coverage(mixed) == []

    def test_an_owned_alternate_without_identity_still_fails(self, checker, mixed):
        broken = [
            owned(role="ADC-001", **{"Serial / asset ID": "—"})
            if r["BOM role"] == "ADC-001"
            else r
            for r in mixed
        ]
        assert checker.check_census(broken, [], "PERFORMED")


class TestCensusAndBomAgree:
    """One possession story, whichever document a reader opens."""

    def test_the_committed_documents_agree(self, checker):
        census = checker.parse_optional_table(checker.CENSUS_PATH, checker.CENSUS_KEY)
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        assert checker.validate_census_bom_agreement(census, candidates) == []

    def test_a_disagreement_is_caught(self, checker):
        census = [row(role="SHAKER-001", Ownership="CONFIRMED_ABSENT")]
        candidates = [
            {
                "candidate_id": "SHAKER-PE-001",
                "role_local_id": "SHAKER-001",
                "ownership": "UNKNOWN",
            }
        ]
        problems = checker.validate_census_bom_agreement(census, candidates)
        assert any("disagrees with the census" in p for p in problems)

    def test_a_stale_unknown_in_the_bom_is_caught(self, checker):
        # The realistic version: the census resolved a role and the BOM was not
        # updated, so a reader deciding what to buy gets two answers.
        census = [
            row(
                role="MIC-001",
                Ownership="CONFIRMED_PRESENT",
                Manufacturer="X",
                Model="Y",
                **{"Serial / asset ID": "SN-1"},
                Disposition="COMPATIBLE",
            )
        ]
        candidates = [
            {
                "candidate_id": "MIC-PE-001",
                "role_local_id": "MIC-001",
                "ownership": "CONFIRMED_ABSENT",
            }
        ]
        assert checker.validate_census_bom_agreement(census, candidates)

    def test_a_role_absent_from_the_census_is_not_forced(self, checker):
        # Candidate roles the census does not cover are left alone rather than
        # being defaulted to anything.
        census = [row(role="SHAKER-001")]
        candidates = [
            {
                "candidate_id": "TIP-PE-001",
                "role_local_id": "TIP-001",
                "ownership": "UNKNOWN",
            }
        ]
        assert checker.validate_census_bom_agreement(census, candidates) == []


class TestBacklogAfterTheCensus:
    def test_b016_is_closed_by_the_performed_census(self, sprints):
        block = sprints.split("### B-016")[1].split("### ")[0]
        assert "**Status:** **closed**" in block
        assert "DO-104R" in block

    def test_b014_remains_open(self, sprints):
        block = sprints.split("### B-014")[1].split("### ")[0]
        assert "**Status:** open" in block
        assert "Not affected by the DO-104R census" in block

    def test_b015_remains_open(self, sprints):
        block = sprints.split("### B-015")[1].split("### ")[0]
        assert "**Status:** open" in block

    def test_current_ends_at_the_human_selection_gate(self):
        text = (REPO_ROOT / "docs" / "dev_orders" / "CURRENT.md").read_text(
            encoding="utf-8"
        )
        assert "BLOCKED AT THE HUMAN SELECTION GATE" in text
        # and does not advance to procurement on its own
        assert "PURCHASE_AUTHORIZED" not in text

"""The PR admission protocol's vocabulary map stays true (TTP-PR-ADMISSION-001).

The protocol owns no state. Its whole value is that it points at the authorities
that do, using their words spelled their way — so its one failure mode is
drifting out of date and quietly becoming a *competing* vocabulary, which is the
thing it exists to prevent.

These tests hold exactly that and nothing more. They check that the document
names the enum members the code actually defines, and that the checker constants
it cites still exist. They do not check whether a claim is true, whether a
limitation is the right limitation, or whether an inference follows — all of
which are review questions the protocol explicitly leaves to humans.

There is no PR-body parsing here and no CI gate. A PR body is not in the
repository.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness.contracts import (
    CalibrationTraceability,
    CampaignExecutionStatus,
    CapabilityStatus,
    EvidenceOrigin,
    ExperimentOutcomeStatus,
    HardwareVerification,
    RiskStatus,
)
from tap_tone_pi.uncertainty.acquisition.quantities import (
    FormulaStatus,
    Provenance,
    ResultAvailability,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "TTP_PR_ADMISSION_PROTOCOL.md"
TEMPLATE_PATH = REPO_ROOT / ".github" / "pull_request_template.md"
CONTRIBUTING_PATH = REPO_ROOT / "CONTRIBUTING.md"


def load_e1_checker():
    path = REPO_ROOT / "scripts" / "check_e1_hardware_bom.py"
    spec = importlib.util.spec_from_file_location("check_e1_hardware_bom", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def protocol() -> str:
    return PROTOCOL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def flat(text: str) -> str:
    """Collapse whitespace so a prose assertion survives a line rewrap."""
    return " ".join(text.split())


class TestTheDocumentsExist:
    def test_the_protocol_is_sited_with_the_other_authority_documents(self):
        assert PROTOCOL_PATH.exists()
        assert PROTOCOL_PATH.parent.name == "docs"

    def test_no_governance_root_was_invented(self):
        # Inventing a constitutional root is a stop condition, not a siting
        # decision this increment was authorized to make.
        assert not (REPO_ROOT / "docs" / "governance").exists()

    def test_the_claim_record_is_in_the_standard_github_location(self):
        assert TEMPLATE_PATH.exists()

    def test_contributing_points_at_the_protocol_rather_than_copying_it(self):
        text = CONTRIBUTING_PATH.read_text(encoding="utf-8")
        assert "docs/TTP_PR_ADMISSION_PROTOCOL.md" in text
        assert "Do not increase the strength of a claim" in flat(text)


class TestTheVocabularyMapMatchesTheLiveEnums:
    """The protocol's reuse must be mechanical, not aspirational.

    If an enum gains or loses a member, this document goes stale silently. That
    staleness is how a pointer to an authority turns into a competing
    vocabulary, so it fails here instead.
    """

    @pytest.mark.parametrize(
        "enum_cls",
        [
            Provenance,
            FormulaStatus,
            ResultAvailability,
            CapabilityStatus,
            HardwareVerification,
            EvidenceOrigin,
            ExperimentOutcomeStatus,
            CampaignExecutionStatus,
            CalibrationTraceability,
            RiskStatus,
        ],
    )
    def test_every_member_of_a_mapped_enum_appears(self, protocol, enum_cls):
        for member in enum_cls:
            assert member.name in protocol, f"{enum_cls.__name__}.{member.name}"

    def test_the_provenance_ladder_is_named_in_full(self, protocol):
        # The five-value input vocabulary is the one most likely to be reached
        # for by a PR author, so it is asserted by name as well as by iteration.
        for value in ("PROPOSED", "ASSUMED", "DATASHEET", "DERIVED", "MEASURED"):
            assert value in protocol

    def test_the_owning_module_paths_are_named_and_real(self, protocol):
        for relative in (
            "tap_tone_pi/uncertainty/acquisition/quantities.py",
            "tap_tone_pi/grant_readiness/contracts.py",
            "scripts/check_e1_hardware_bom.py",
        ):
            assert relative in protocol
            assert (REPO_ROOT / relative).exists()

    @pytest.mark.parametrize(
        "constant",
        [
            "STATUS_ORDER",
            "OWNERSHIP_STATES",
            "COMPATIBILITY_DISPOSITIONS",
            "PROCUREMENT_ACTIONS",
        ],
    )
    def test_the_cited_e1_constants_still_exist(self, protocol, constant):
        checker = load_e1_checker()
        assert hasattr(checker, constant), constant
        assert constant in protocol
        for value in getattr(checker, constant):
            assert value in protocol, f"{constant}: {value}"

    def test_the_cited_authority_documents_exist(self, protocol):
        for name in (
            "ADR-0011-measurement-authority.md",
            "ADR-0012-epistemic-status-taxonomy.md",
            "ACQUISITION_BUDGET_AUTHORITY.md",
            "ANALYZER_CAPABILITY_MATRIX.md",
        ):
            assert name in protocol
            assert (REPO_ROOT / "docs" / name).exists()


class TestTheProtocolClaimsNoAuthority:
    def test_it_states_that_it_owns_nothing(self, protocol):
        assert "**Owns:** nothing" in protocol
        assert "not a new source of scientific or hardware truth" in flat(protocol)

    def test_it_records_its_own_enforcement_maturity(self, protocol):
        assert "**Enforcement maturity:** `PROSE`" in protocol
        assert "**Scope maturity:** `TTP-LOCAL`" in protocol

    def test_it_adds_no_required_check(self):
        # Enforcement maturity is PROSE. A workflow here would be a promotion
        # this increment was not authorized to make.
        workflows = REPO_ROOT / ".github" / "workflows"
        for path in workflows.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            assert "TTP_PR_ADMISSION" not in text, path.name
            assert "pull_request_template" not in text, path.name

    def test_it_lists_what_automation_must_not_decide(self, protocol):
        for forbidden in (
            "whether an equation is scientifically correct",
            "whether a transducer is suitable",
            "whether a mode identification is physically valid",
            "whether an uncertainty model is authoritative",
        ):
            assert forbidden in protocol

    def test_it_names_what_is_left_to_reviewer_judgment(self, protocol):
        assert "Deliberately left to reviewer judgment" in protocol
        assert "material" in protocol


class TestTheAxesDoNotCollapse:
    """The correction that kept this from becoming a nine-rung ladder.

    OWNED is not above SELECTED. The register holds the counterexample, and a
    protocol that flattened these into one scale would force a document to
    assert a selection nobody made.
    """

    def test_the_protocol_refuses_a_single_status_scale(self, protocol):
        assert "These are axes, not one ladder" in protocol
        assert "As a single status field it is wrong" in flat(protocol)

    def test_it_cites_the_repository_counterexample(self, protocol):
        text = flat(protocol)
        assert "CONFIRMED_PRESENT` and is *not* `SELECTED`" in text
        assert "SELECTION_DEFERRED" in text

    def test_the_counterexample_is_still_true_of_the_register(self):
        # If the Pi is ever selected, the argument above needs rewriting rather
        # than quietly surviving as a stale illustration.
        checker = load_e1_checker()
        bom = checker.parse_table(checker.BOM_PATH, "local_id")
        host = next(row for row in bom if row["local_id"] == "HOST-001")
        assert host["status"] == "SELECTED"  # design selection only
        census = checker.parse_table(checker.CENSUS_PATH, "Category")
        owned = [r for r in census if r["Ownership"].strip() == "CONFIRMED_PRESENT"]
        assert [r["BOM role"].strip() for r in owned] == ["HOST-001"]

    def test_the_two_meanings_of_derived_are_distinguished(self, protocol):
        assert 'Two authorities use the word "derived"' in protocol


class TestEveryRuleHasADemonstratedExample:
    """The anti-overreach rule: no rule without a repository example.

    Each boundary the protocol draws cites the merged artifact that demonstrates
    it. A rule with no example would be a rule invented for its own sake, which
    is how a discipline turns into bureaucracy.
    """

    @pytest.mark.parametrize(
        "evidence",
        [
            "validate_measured_force",
            "validate_no_unwitnessed_hardware_claim",
            "CANDIDATE_SOURCE_FORMULA",
            "B-020",
            "B-022",
            "6c5366f",
        ],
    )
    def test_the_boundary_section_cites_real_artifacts(self, protocol, evidence):
        assert evidence in protocol

    def test_the_cited_validators_exist_in_the_code(self):
        checker = load_e1_checker()
        assert hasattr(checker, "validate_measured_force")
        from tap_tone_pi.grant_readiness import validation

        assert hasattr(validation, "validate_no_unwitnessed_hardware_claim")

    def test_unmerged_evidence_is_labelled_as_unmerged(self, protocol):
        # DO-108P is open as PR #39. Citing it as though it were repository
        # authority would be the exact failure the protocol names.
        assert "not merged to `main`" in protocol

    def test_the_authoring_mistake_is_recorded_rather_than_hidden(self, protocol):
        # A test asserted a file "does not exist" when it was absent from one
        # branch. The file is on main now. The correction history is part of why
        # the protocol exists, so it is written down.
        assert "An unmerged branch is not the repository" in protocol
        assert (REPO_ROOT / "docs" / "ANALYZER_CAPABILITY_MATRIX.md").exists()


class TestTheClaimRecord:
    @pytest.mark.parametrize(
        "field",
        [
            "Claim class",
            "Source / instrument",
            "Observation",
            "Provenance",
            "Supported inference",
            "Scope",
            "Limitation / blind spot",
            "Unresolved condition",
            "Falsifier",
            "Evidence reference",
        ],
    )
    def test_the_template_carries_every_field(self, template, field):
        assert field in template

    def test_the_protocol_and_the_template_agree_on_the_fields(self, protocol):
        # Two documents listing the chain differently is the same drift problem
        # the vocabulary map has, one layer up.
        for field in ("CLAIM CLASS", "PROVENANCE", "FALSIFIER", "SCOPE"):
            assert field in protocol

    def test_routine_work_is_exempt(self, template, protocol):
        assert "Routine work" in template
        assert "apply to routine work" in flat(protocol)

    def test_absent_fields_are_marked_not_deleted(self, template, protocol):
        assert "n/a" in template
        assert "with a reason" in flat(protocol)

    def test_the_promotion_checklist_covers_the_demonstrated_failures(self, template):
        text = flat(template)
        for promotion in (
            "`CANDIDATE` → `SELECTED`",
            "reported as `MEASURED`",
            "No `NOT_EXECUTED` record carries a result",
            "No component rating is reported as a system requirement",
        ):
            assert promotion in text

    def test_readiness_is_not_a_green_test_suite(self, template, protocol):
        assert "READY FOR REVIEW" in template
        assert "DRAFT / INVESTIGATING" in template
        assert "not** ready for review merely because" in protocol

    def test_the_three_standing_statements_are_present(self, template):
        text = flat(template)
        assert (
            "A passing software test does not establish a valid physical measurement"
            in text
        )
        assert "does not become a measured TTP quantity" in text
        assert "Commanded excitation is not measured mechanical input force" in text


class TestUniversalClaims:
    def test_the_protocol_bounds_negative_claims(self, protocol):
        assert "bound a negative to the population you observed" in flat(protocol)

    def test_it_uses_the_force_measurement_case(self, protocol):
        # "TTP has no force measurement" is false: the bending subsystem
        # measures force. The example is only useful if that stays true.
        assert "the bending subsystem measures force" in flat(protocol)
        assert (REPO_ROOT / "tap_tone_pi" / "bending").is_dir()


class TestDO108PIsTheWorkedExample:
    def test_a_pr_may_be_ready_with_its_question_open(self, protocol):
        text = flat(protocol)
        assert "may be ready for review with its central question unanswered" in text
        assert "PCB evidence gate `BLOCKED`" in text

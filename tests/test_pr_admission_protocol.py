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
import re
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


def normalized(text: str) -> str:
    """``flat``, plus markdown blockquote and emphasis markers removed.

    The canonical definition is a bolded blockquote in the protocol and a
    bolded blockquote in the template. Comparing the *sentence* means comparing
    it without the presentation markers that wrap it, or a rewrap from ``> **x**``
    to ``**x**`` would read as a definition change.
    """
    without_quotes = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return " ".join(without_quotes.replace("**", "").split())


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
        # Materiality has a definition; only borderline application stays
        # judgment. The section must not treat "material" as undefined.
        text = flat(protocol)
        assert "borderline change meets the material-claim definition" in text
        assert "does not eliminate edge cases" in text


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


# The canonical normative definition. The protocol owns it; the template quotes
# it verbatim because a contributor needs the criterion at the point of decision;
# CONTRIBUTING links to it and must not establish a rival. Held as one constant
# here so a drifted copy fails rather than quietly becoming a second authority.
CANONICAL_MATERIAL_DEFINITION = (
    "A material claim is a claim whose acceptance could change a reviewer's "
    "understanding of TTP's scientific validity, measurement capability, "
    "hardware state, uncertainty, validation status, or readiness for physical "
    "use."
)

# Wording that would constitute defining materiality rather than citing it.
DEFINITION_SHAPED = "could change a reviewer's understanding"


class TestMaterialClaimDefinition:
    """One normative definition, quoted where needed, redefined nowhere.

    T7, as ruled: not three files carrying identical prose, but one owner, one
    verbatim quotation at the point of use, and no competing third definition.
    The definition reduces subjectivity; borderline application stays judgment.
    """

    def test_the_protocol_owns_the_definition(self, protocol):
        assert "What counts as a material claim" in protocol
        assert CANONICAL_MATERIAL_DEFINITION in normalized(protocol)

    def test_the_protocol_states_it_exactly_once(self, protocol):
        # A second copy inside the owning document is the same drift risk, one
        # file earlier than the one T7 was written about.
        assert normalized(protocol).count(CANONICAL_MATERIAL_DEFINITION) == 1

    def test_the_protocol_claims_the_ownership_explicitly(self, protocol):
        text = flat(protocol)
        assert "This protocol owns the normative definition" in text
        assert "nothing else defines it" in text

    def test_the_template_quotes_it_verbatim(self, template):
        # Verbatim, because the contributor decides at the template and should
        # not have to follow a link to learn the criterion.
        assert CANONICAL_MATERIAL_DEFINITION in normalized(template)

    def test_contributing_links_rather_than_redefines(self):
        text = CONTRIBUTING_PATH.read_text(encoding="utf-8")
        assert "TTP_PR_ADMISSION_PROTOCOL.md#what-counts-as-a-material-claim" in text
        assert DEFINITION_SHAPED not in flat(text)
        assert "only place that defines it" in flat(text)

    def test_no_fourth_definition_appears_anywhere_else(self):
        # Bounded to the three documents this increment governs, which is the
        # population actually examined.
        for path in (REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"):
            if path.exists():
                assert DEFINITION_SHAPED not in flat(path.read_text(encoding="utf-8"))


class TestTheDefaultTemplateIsShort:
    """T-friction: answering No must cost a contributor nothing.

    The parent template put the whole dossier inline, so a routine PR scrolled
    past eleven empty headings after being told to stop. 001A moved the record
    into the protocol and left a gate behind.
    """

    def test_the_gate_is_asked(self, template):
        assert "## Material evidence-bearing claim?" in template
        assert "**No**" in template
        assert "**Yes**" in template

    def test_the_dossier_is_not_inline(self, template):
        # The fields live in the protocol now. Their presence here would mean
        # the move did not happen.
        for field in (
            "**Claim class:**",
            "**Source / instrument:**",
            "**Falsifier:**",
            "**Evidence reference:**",
        ):
            assert field not in template

    def test_the_template_stays_small(self, template):
        # Not a style rule: length is the friction being removed. The parent
        # template was ~120 lines; a routine contributor should see a fraction.
        assert len(template.splitlines()) < 45

    def test_the_yes_path_links_to_the_record_and_the_example(self, template):
        assert "TTP_PR_ADMISSION_PROTOCOL.md#the-evidence-record" in template
        assert "worked-example" in template

    def test_the_anchor_targets_exist_in_the_protocol(self, protocol):
        # A dead anchor would send an evidence-bearing author nowhere.
        assert "## The evidence record" in protocol
        assert "### Worked example — datasheet rating is not a TTP requirement" in (
            protocol
        )

    def test_routine_work_is_exempt_from_the_record(self, template, protocol):
        assert "routine work" in flat(template).lower()
        assert "apply to routine work" in flat(protocol)

    def test_verification_is_still_required_of_routine_prs(self, template):
        # T8. "No material claim" must not become "no testing reported".
        text = flat(template)
        assert "## Verification" in template
        assert "Required for every PR, routine or not" in text
        assert "never from saying what was run" in text


class TestTheEvidenceRecordMovedToTheProtocol:
    @pytest.mark.parametrize(
        "field",
        [
            "CLAIM ID",
            "CLAIM CLASS",
            "SOURCE / INSTRUMENT",
            "OBSERVATION",
            "PROVENANCE",
            "SUPPORTED INFERENCE",
            "SCOPE",
            "LIMITATION / BLIND SPOT",
            "UNRESOLVED CONDITION",
            "FALSIFIER",
            "EVIDENCE REFERENCE",
        ],
    )
    def test_the_protocol_carries_every_field(self, protocol, field):
        assert field in protocol

    def test_the_record_says_it_is_what_the_template_links_to(self, protocol):
        assert "This is the section the PR template links to" in flat(protocol)

    def test_absent_fields_are_marked_not_deleted(self, protocol):
        assert "with a reason" in flat(protocol)

    def test_the_promotion_checklist_moved_intact(self, protocol):
        text = flat(protocol)
        for promotion in (
            "No hardware state promoted",
            "No DATASHEET or DERIVED value reported as MEASURED",
            "No NOT_EXECUTED record carrying a result",
            "No component rating reported as a system requirement",
        ):
            assert promotion in text

    def test_readiness_is_not_a_green_test_suite(self, protocol):
        assert "READY FOR REVIEW" in protocol
        assert "DRAFT / INVESTIGATING" in protocol
        assert "not** ready for review merely because" in protocol


class TestReviewerTriage:
    def test_the_triage_exists(self, protocol):
        assert "## Reviewer triage" in protocol

    @pytest.mark.parametrize(
        "step",
        [
            "Material claim?",
            "Named source/instrument?",
            "Observation separated from inference?",
            "Provenance explicit?",
            "Scope bounded?",
            "Limitation / unresolved condition visible?",
            "Evidence state silently promoted?",
        ],
    )
    def test_each_triage_step_is_present(self, protocol, step):
        assert step in protocol

    def test_step_one_is_a_gate_that_protects_ordinary_prs(self, protocol):
        # The friction failure runs both ways: a reviewer withholding approval
        # for a missing record that was never required is the same problem.
        text = flat(protocol)
        assert "Step 1 is a gate, not a formality" in text
        assert "must not withhold approval" in text


class TestWorkedClaimExample:
    """A filled end-to-end example lowers contributor error more than more prose."""

    def test_the_protocol_carries_a_datasheet_rating_example(self, protocol):
        text = flat(protocol).lower()
        assert "Worked example" in protocol
        assert "DATASHEET" in protocol
        assert "24 w" in text
        assert "SUPPORTED INFERENCE" in protocol
        assert "LIMITATION / BLIND SPOT" in protocol

    def test_it_uses_the_manufacturers_own_terminology(self, protocol):
        # T4-adjacent, and the defect 001A corrected: the Dayton sheet's
        # parameter is "RMS Power Handling", not a continuous rating. A protocol
        # teaching evidence discipline must not overstate its own source.
        #
        # Scoped to the example block: "24 W continuous" appears elsewhere in
        # the protocol as the quoted wording of the corrected draft, which is
        # the record of the fix rather than a live overstatement.
        example = flat(_worked_example(protocol))
        assert "RMS Power Handling" in example
        assert "24 W continuous" not in example

    def test_the_correction_itself_is_recorded(self, protocol):
        text = flat(protocol)
        assert "stronger characterization than the source establishes" in text
        assert '"24 W continuous"' in text

    def test_the_rating_is_never_labelled_measured(self, protocol):
        # T4. The example's provenance is DATASHEET and must stay there.
        example = _worked_example(protocol)
        assert "PROVENANCE               DATASHEET" in example
        assert "MEASURED" not in example

    def test_it_does_not_assert_a_required_ttp_power(self, protocol):
        # T5. The whole point of the example. Scoped to the example block: the
        # Hardware PRs section carries "TTP requires a 24 W amplifier" as an
        # explicit must-NOT-become, which is the rule rather than a violation.
        example = flat(_worked_example(protocol))
        for promotion in (
            "TTP requires 24 W",
            "TTP requires a 24 W",
            "required TTP excitation power is 24 W",
        ):
            assert promotion not in example

    def test_it_states_what_the_rating_does_not_support(self, protocol):
        example = flat(_worked_example(protocol))
        assert "Does not establish a TTP operating requirement" in example
        assert "amplifier sizing target" in example
        assert "safe or appropriate for a plate" in example

    def test_it_points_at_bench_characterization_as_the_validation_step(self, protocol):
        # T6. The unresolved condition must name the experiment that resolves
        # it, not merely say "unknown".
        example = flat(_worked_example(protocol))
        assert "remain to be established experimentally" in example
        assert "bench" in example.lower()
        assert "minimum useful" in example


def _worked_example(protocol: str) -> str:
    """The worked example's fenced block, so assertions cannot stray outside it."""
    start = protocol.index("### Worked example")
    end = protocol.index("**Note the wording.**", start)
    return protocol[start:end]


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

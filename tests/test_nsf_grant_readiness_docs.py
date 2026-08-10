"""DO-102 documentation drift guards (Commit 8).

The five NSF documents make claims that live in code. These tests keep the two
from diverging: the risk register is byte-identical to what its source renders,
and the technical baseline agrees with the ratified inventory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tap_tone_pi.grant_readiness.contracts import CapabilityStatus
from tap_tone_pi.grant_readiness.inventory import (
    INVENTORY_LIMITATIONS,
    TTP_CAPABILITY_INVENTORY,
)
from tap_tone_pi.grant_readiness.report import render_risk_register
from tap_tone_pi.grant_readiness.risks import REFERENCE_METHODS, TECHNICAL_RISKS

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

REQUIRED_DOCS = (
    "NSF_TTP_TECHNICAL_BASELINE.md",
    "NSF_TTP_PRELIMINARY_EXPERIMENT.md",
    "NSF_TTP_PHASE_I_TECHNICAL_RISKS.md",
    "NSF_TTP_REFERENCE_VALIDATION_PLAN.md",
    "NSF_TTP_PROJECT_PITCH_SOURCE.md",
)

# Language no DO-102 document may contain. "accurate to", "calibrated", and
# "validated against" are deliberately absent from this list: the pitch-source
# drafting notes name them as phrases to avoid, and a check that fired on that
# would punish the document for warning against them.
FORBIDDEN_IN_DOCS = (
    "industry-leading",
    "proven accurate",
    "laboratory-equivalent",
    "market opportunity of",
    "revenue",
    "customers will",
    "best-in-class",
)


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def flat(name: str) -> str:
    """Document text with all whitespace collapsed.

    Prose assertions run against this so a reflowed paragraph does not fail a
    test about what the document says. Structural assertions — table rows,
    headings — still run against the raw text.
    """
    return " ".join(read(name).split())


def prose(name: str) -> str:
    """Flattened text with markdown emphasis and quoting stripped.

    Lets an assertion state what a document says without also pinning how it is
    marked up.
    """
    text = flat(name)
    for marker in ("**", "*", "`", "> "):
        text = text.replace(marker, "")
    return text


class TestDocumentsExist:
    @pytest.mark.parametrize("name", REQUIRED_DOCS)
    def test_document_exists_and_is_substantial(self, name):
        path = DOCS / name
        assert path.exists(), name
        assert len(path.read_text(encoding="utf-8")) > 1000


@pytest.mark.parametrize("name", REQUIRED_DOCS)
class TestDocumentLanguage:
    def test_no_unsupported_language(self, name):
        lowered = read(name).lower()
        for phrase in FORBIDDEN_IN_DOCS:
            assert phrase not in lowered, f"{name}: {phrase}"

    def test_no_host_paths(self, name):
        text = read(name)
        assert str(REPO_ROOT) not in text
        assert "C:\\Users" not in text


class TestRiskRegisterCannotDrift:
    """The register is generated from its source, so it cannot disagree."""

    def test_matches_its_source_exactly(self):
        assert read("NSF_TTP_PHASE_I_TECHNICAL_RISKS.md") == render_risk_register(
            TECHNICAL_RISKS
        )

    def test_every_risk_id_appears(self):
        text = read("NSF_TTP_PHASE_I_TECHNICAL_RISKS.md")
        for risk in TECHNICAL_RISKS:
            assert f"## {risk.risk_id} — {risk.title}" in text


class TestTechnicalBaselineMatchesInventory:
    @pytest.fixture(scope="class")
    def text(self) -> str:
        return read("NSF_TTP_TECHNICAL_BASELINE.md")

    def test_counts_match_the_ratified_inventory(self, text):
        counts = {status: 0 for status in CapabilityStatus}
        for capability in TTP_CAPABILITY_INVENTORY:
            counts[capability.status] += 1

        assert f"| IMPLEMENTED | {counts[CapabilityStatus.IMPLEMENTED]} |" in text
        assert f"| EXPERIMENTAL | {counts[CapabilityStatus.EXPERIMENTAL]} |" in text
        assert f"| PARTIAL | {counts[CapabilityStatus.PARTIAL]} |" in text
        assert f"| PLANNED | {counts[CapabilityStatus.PLANNED]} |" in text
        assert f"| **Total audited** | **{len(TTP_CAPABILITY_INVENTORY)}** |" in text

    def test_every_capability_is_named(self, text):
        for capability in TTP_CAPABILITY_INVENTORY:
            assert f"`{capability.capability_id}`" in text, capability.capability_id

    def test_ratified_partial_entries_are_documented_as_partial(self, text):
        partial_section = text.split("## PARTIAL")[1].split("## PLANNED")[0]
        for capability_id in (
            "audio_capture",
            "controlled_excitation",
            "multitap_statistics",
            "chladni_pattern_indexing",
        ):
            assert f"`{capability_id}`" in partial_section, capability_id

    def test_experimental_entries_are_documented_as_experimental(self, text):
        section = text.split("## EXPERIMENTAL")[1].split("## PARTIAL")[0]
        assert "`damping_q_estimation`" in section
        assert "`wolf_tone_detection`" in section

    def test_implemented_framing_is_stated(self):
        assert (
            "IMPLEMENTED means the capability exists in the repository and is "
            "exercised by automated tests. It does not imply intended-hardware "
            "verification, calibrated accuracy, or external validation unless "
            "separately stated." in prose("NSF_TTP_TECHNICAL_BASELINE.md")
        )

    def test_hardware_framing_is_stated(self):
        flattened = flat("NSF_TTP_TECHNICAL_BASELINE.md")
        assert (
            "None of the 25 audited capabilities has been witnessed end-to-end "
            "on the intended TTP hardware configuration during DO-102." in flattened
        )
        assert (
            "Software implementation status and hardware verification are "
            "tracked independently." in flattened
        )

    def test_inventory_limitations_are_reflected(self, text):
        # The document and the machine-readable limitations say the same thing.
        assert "no traceability" in " ".join(INVENTORY_LIMITATIONS).lower()
        assert "no traceability to any" in text.lower()

    def test_stale_baseline_failure_is_recorded_as_stale(self, text):
        flattened = flat("NSF_TTP_TECHNICAL_BASELINE.md")
        assert "test_advisory_in_calibration_is_error" in flattened
        assert "no longer reproduces" in flattened
        assert "is not carried forward" in flattened

    def test_stale_correction_is_attributed_to_do102_not_upstream(self):
        # PR #18 closed DO-100 but left the baseline list untouched, so this
        # correction is DO-102's own rather than a duplicate of upstream work.
        assert "PR #18 closed DO-100 but did not touch the baseline list" in flat(
            "NSF_TTP_TECHNICAL_BASELINE.md"
        )

    def test_reproducing_baseline_failures_are_named(self, text):
        assert "session_20260101T234237Z" in text
        assert "session_20260101T235209Z" in text
        assert "missing required keys: ['bending']" in text


class TestSupportingInfrastructureIsNotCounted:
    """Infrastructure landed after the audit is recorded, not counted."""

    @pytest.fixture(scope="class")
    def text(self) -> str:
        return read("NSF_TTP_TECHNICAL_BASELINE.md")

    def test_section_exists(self, text):
        assert (
            "## Supporting Scientific Infrastructure Landed After Initial Audit" in text
        )

    def test_both_items_are_recorded(self, text):
        section = text.split("## Supporting Scientific Infrastructure")[1].split(
            "## Current evidence"
        )[0]
        assert "tap_tone_pi/empirical/" in section
        assert "tonewood_radiation_ratio_v1" in section

    def test_neither_is_in_the_capability_inventory(self):
        # The denominator is instrument capabilities, not repository modules.
        ids = {c.capability_id for c in TTP_CAPABILITY_INVENTORY}
        assert "empirical_model_framework" not in ids
        assert "tonewood_radiation_ratio_contract" not in ids
        assert len(TTP_CAPABILITY_INVENTORY) == 25

    def test_the_denominator_is_explicitly_defended(self, text):
        flattened = flat("NSF_TTP_TECHNICAL_BASELINE.md")
        assert "the denominator above stays at 25" in flattened
        assert "Neither is counted as an instrument capability" in flattened

    def test_radiation_ratio_is_marked_not_a_measurement_capability(self, text):
        assert "Not a measurement capability." in text

    def test_empirical_framework_is_marked_no_hardware_implication(self, text):
        assert "No hardware implication" in text

    def test_regression_scope_names_their_tests(self, text):
        for test_module in (
            "tests/test_empirical_contracts.py",
            "tests/test_empirical_luthiery_compat.py",
            "tests/test_radiation_ratio_contract.py",
        ):
            assert test_module in text, test_module

    def test_their_test_modules_exist(self):
        for test_module in (
            "test_empirical_contracts.py",
            "test_empirical_luthiery_compat.py",
            "test_radiation_ratio_contract.py",
        ):
            assert (REPO_ROOT / "tests" / test_module).exists(), test_module


class TestPreliminaryExperimentDoc:
    @pytest.fixture(scope="class")
    def text(self) -> str:
        return read("NSF_TTP_PRELIMINARY_EXPERIMENT.md")

    def test_states_it_is_not_executed(self, text):
        flattened = flat("NSF_TTP_PRELIMINARY_EXPERIMENT.md")
        assert "not executed" in flattened.lower()
        assert "deferred execution gate" in flattened

    def test_separates_repeatability_from_accuracy(self, text):
        assert "Accuracy requires a reference." in text

    def test_excitation_is_not_hard_coded_to_manual_tap(self, text):
        flattened = flat("NSF_TTP_PRELIMINARY_EXPERIMENT.md")
        assert "is one permitted value" in flattened
        assert "not** privileged as the canonical method" in flattened
        assert "shaker" in flattened.lower()

    def test_no_repeat_count_target_is_set(self, text):
        assert "The repeat count is not a target." in text

    def test_records_every_rejection_reason(self, text):
        for reason in (
            "CLIPPING",
            "INSUFFICIENT_SIGNAL",
            "ANALYSIS_FAILURE",
            "INVALID_METADATA",
            "QUALITY_GATE_REJECTED",
            "MISSING_ARTIFACT",
        ):
            assert reason in text

    def test_states_the_sd_convention(self, text):
        assert "Bessel" in text


class TestReferenceValidationDoc:
    @pytest.fixture(scope="class")
    def text(self) -> str:
        return read("NSF_TTP_REFERENCE_VALIDATION_PLAN.md")

    def test_states_nothing_has_been_compared(self, text):
        assert "No comparison against any reference method has been performed" in flat(
            "NSF_TTP_REFERENCE_VALIDATION_PLAN.md"
        )

    def test_every_method_appears(self, text):
        for method in REFERENCE_METHODS:
            assert method.method in text

    def test_partners_are_tbd(self, text):
        assert "TBD" in text
        assert "unknown, not pending" in text

    def test_distinguishes_internal_consistency_from_traceability(self, text):
        flattened = flat("NSF_TTP_REFERENCE_VALIDATION_PLAN.md")
        assert "internal signal-chain consistency" in flattened
        assert "does not mean traceability" in flattened


class TestPitchSourceDoc:
    @pytest.fixture(scope="class")
    def text(self) -> str:
        return read("NSF_TTP_PROJECT_PITCH_SOURCE.md")

    def test_disclaims_being_a_submission(self, text):
        assert "**This is not a submission.**" in text

    def test_all_four_headings_present(self, text):
        for heading in (
            "## 1. Technology Innovation",
            "## 2. Technical Objectives and Challenges",
            "## 3. Market Opportunity",
            "## 4. Company and Team",
        ):
            assert heading in text

    def test_market_and_team_are_placeholders(self, text):
        market = text.split("## 3. Market Opportunity")[1]
        assert market.count("[HUMAN INPUT REQUIRED]") == 11
        assert "**Not generated.**" in market

    def test_ratified_counts_are_quoted(self):
        flattened = flat("NSF_TTP_PROJECT_PITCH_SOURCE.md")
        assert "19 are IMPLEMENTED" in flattened
        assert "2 are EXPERIMENTAL" in flattened
        assert "4 are PARTIAL" in flattened
        assert "0 are PLANNED" in flattened

    def test_hardware_status_is_stated(self, text):
        assert "0 of 25" in text

    def test_no_success_threshold_is_set(self, text):
        assert "none has a success threshold attached" in flat(
            "NSF_TTP_PROJECT_PITCH_SOURCE.md"
        )

    def test_partial_acquisition_and_excitation_are_disclosed(self, text):
        flattened = flat("NSF_TTP_PROJECT_PITCH_SOURCE.md")
        assert "Acquisition and excitation are honestly incomplete." in flattened
        assert "not built" in flattened

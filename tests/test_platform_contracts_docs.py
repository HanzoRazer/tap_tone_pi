# INSTRUMENT CLASS: GOVERNANCE
"""Tests for platform contract documentation.

Validates that platform contract docs exist and contain required invariants.
"""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent / "docs" / "platform-contracts"


class TestPlatformContractDocsExist:
    """Tests verifying required platform contract docs exist."""

    def test_readme_exists(self):
        """README.md should exist."""
        assert (ROOT / "README.md").is_file()

    def test_authority_contract_exists(self):
        """authority-v1.md should exist."""
        assert (ROOT / "authority-v1.md").is_file()

    def test_confidence_contract_exists(self):
        """confidence-v1.md should exist."""
        assert (ROOT / "confidence-v1.md").is_file()

    def test_epistemic_status_contract_exists(self):
        """epistemic-status-v1.md should exist."""
        assert (ROOT / "epistemic-status-v1.md").is_file()

    def test_review_decision_contract_exists(self):
        """review-decision-v1.md should exist."""
        assert (ROOT / "review-decision-v1.md").is_file()


class TestContractsAreVocabOnly:
    """Tests verifying contracts are vocabulary-only, not runtime integration."""

    def test_readme_states_vocab_only(self):
        """README must state these are vocabulary convergence only."""
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "vocabulary convergence only" in text

    def test_readme_requires_dev_orders_for_runtime(self):
        """README must state runtime integration requires Dev Orders."""
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "Runtime integration requires explicit Dev Orders" in text


class TestAuthorityContractInvariants:
    """Tests verifying authority contract contains core invariants."""

    def test_core_invariant_present(self):
        """Authority contract must contain core invariant about routing attention."""
        text = (ROOT / "authority-v1.md").read_text(encoding="utf-8")
        assert "may route attention" in text
        assert "may not establish truth" in text

    def test_six_authority_classes_defined(self):
        """Authority contract must define six authority classes."""
        text = (ROOT / "authority-v1.md").read_text(encoding="utf-8")
        for cls in ["measurement", "provenance", "decision_support",
                    "interpretive", "operator", "external"]:
            assert f"### {cls}" in text, f"Missing authority class: {cls}"


class TestConfidenceContractInvariants:
    """Tests verifying confidence contract contains core rules."""

    def test_no_bare_confidence_rule(self):
        """Confidence contract must reject bare confidence."""
        text = (ROOT / "confidence-v1.md").read_text(encoding="utf-8")
        assert "no bare confidence" in text.lower()

    def test_domain_value_source_required(self):
        """Confidence contract must require domain + value + source."""
        text = (ROOT / "confidence-v1.md").read_text(encoding="utf-8")
        assert "domain + value + source" in text.lower()

    def test_six_confidence_domains_defined(self):
        """Confidence contract must define six domains."""
        text = (ROOT / "confidence-v1.md").read_text(encoding="utf-8")
        for domain in ["signal", "measurement", "interpretive",
                       "recommendation", "historical", "ranking"]:
            assert f"### {domain}" in text, f"Missing confidence domain: {domain}"


class TestEpistemicStatusContractInvariants:
    """Tests verifying epistemic status contract blocks prediction laundering."""

    def test_predicted_cannot_become_observed(self):
        """Epistemic contract must block predicted → observed."""
        text = (ROOT / "epistemic-status-v1.md").read_text(encoding="utf-8")
        assert "Predicted cannot become observed" in text

    def test_heuristic_cannot_become_measurement(self):
        """Epistemic contract must block heuristic → measurement."""
        text = (ROOT / "epistemic-status-v1.md").read_text(encoding="utf-8")
        assert "Heuristic cannot become measurement" in text

    def test_seven_statuses_defined(self):
        """Epistemic contract must define seven statuses."""
        text = (ROOT / "epistemic-status-v1.md").read_text(encoding="utf-8")
        for status in ["observed", "derived", "estimated", "predicted",
                       "heuristic", "operator_annotated", "externally_sourced"]:
            assert f"### {status}" in text, f"Missing epistemic status: {status}"


class TestReviewDecisionContractInvariants:
    """Tests verifying review decision contract blocks execution authority."""

    def test_does_not_authorize_implementation(self):
        """Review contract must state it does not authorize implementation."""
        text = (ROOT / "review-decision-v1.md").read_text(encoding="utf-8")
        assert "do not automatically authorize implementation" in text

    def test_does_not_authorize_execution(self):
        """Review contract must state it does not authorize execution."""
        text = (ROOT / "review-decision-v1.md").read_text(encoding="utf-8")
        assert "execution" in text
        # Check the core invariant
        assert "do not automatically authorize" in text

    def test_six_decision_types_defined(self):
        """Review contract must define six decision types."""
        text = (ROOT / "review-decision-v1.md").read_text(encoding="utf-8")
        for dtype in ["acknowledge", "request_more_evidence", "defer",
                      "reject", "mark_reviewed", "approve_for_downstream_review"]:
            assert f"### {dtype}" in text, f"Missing decision type: {dtype}"

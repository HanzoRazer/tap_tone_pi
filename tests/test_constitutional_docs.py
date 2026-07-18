# INSTRUMENT CLASS: MEASUREMENT
"""Tests for constitutional documentation.

Validates that required constitutional documents exist and contain
required terms and invariants.

See: DO-81 (Measurement Authority & Epistemic Status)
"""

from __future__ import annotations

from pathlib import Path


DOCS_DIR = Path(__file__).parent.parent / "docs"


class TestConstitutionalDocsExist:
    """Tests verifying required constitutional documents exist."""

    def test_measurement_authority_adr_exists(self):
        """ADR-0011 for measurement authority should exist."""
        path = DOCS_DIR / "ADR-0011-measurement-authority.md"
        assert path.is_file(), f"Missing {path}"

    def test_epistemic_status_adr_exists(self):
        """ADR-0012 for epistemic status should exist."""
        path = DOCS_DIR / "ADR-0012-epistemic-status-taxonomy.md"
        assert path.is_file(), f"Missing {path}"

    def test_epistemic_status_matrix_exists(self):
        """EPISTEMIC_STATUS_MATRIX.md quick reference should exist."""
        path = DOCS_DIR / "EPISTEMIC_STATUS_MATRIX.md"
        assert path.is_file(), f"Missing {path}"

    def test_age_constitutional_contract_exists(self):
        """AGE_CONSTITUTIONAL_CONTRACT.md should exist."""
        path = DOCS_DIR / "AGE_CONSTITUTIONAL_CONTRACT.md"
        assert path.is_file(), f"Missing {path}"

    def test_guidance_authority_adr_exists(self):
        """ADR-0010 for guidance authority should exist."""
        path = DOCS_DIR / "ADR-0010-guidance-authority-boundary.md"
        assert path.is_file(), f"Missing {path}"


class TestEpistemicStatusesDefined:
    """Tests verifying all epistemic statuses are defined in ADR-0012."""

    REQUIRED_STATUSES = [
        "Observed",
        "Derived",
        "Estimated",
        "Predicted",
        "Heuristic",
        "Operator-Annotated",
        "Externally-Sourced",
    ]

    def test_all_epistemic_statuses_defined(self):
        """ADR-0012 must define all required epistemic statuses."""
        path = DOCS_DIR / "ADR-0012-epistemic-status-taxonomy.md"
        text = path.read_text(encoding="utf-8")

        for status in self.REQUIRED_STATUSES:
            assert status in text, f"Missing epistemic status: {status}"

    def test_epistemic_status_has_definition_section(self):
        """Each epistemic status should have a definition section."""
        path = DOCS_DIR / "ADR-0012-epistemic-status-taxonomy.md"
        text = path.read_text(encoding="utf-8")

        # Check for section headers (### Status)
        for status in self.REQUIRED_STATUSES:
            # Normalize for headers (Operator-Annotated has hyphen)
            assert f"### {status}" in text, f"Missing definition section for: {status}"


class TestMeasurementAuthorityInvariants:
    """Tests verifying core invariants in ADR-0011."""

    def test_capture_integrity_not_acoustic_truth(self):
        """ADR-0011 must state that capture integrity ≠ acoustic truth."""
        path = DOCS_DIR / "ADR-0011-measurement-authority.md"
        text = path.read_text(encoding="utf-8")

        assert "Capture integrity" in text
        assert "acoustic truth" in text.lower()

    def test_defines_artifact_types(self):
        """ADR-0011 must define the artifact authority types."""
        path = DOCS_DIR / "ADR-0011-measurement-authority.md"
        text = path.read_text(encoding="utf-8")

        required_types = [
            "Observational",
            "Derived",
            "Interpretive",
            "Advisory",
            "Historical",
            "Operator Annotation",
        ]

        for artifact_type in required_types:
            assert artifact_type in text, f"Missing artifact type: {artifact_type}"

    def test_has_forbidden_claims_section(self):
        """ADR-0011 must list forbidden claims."""
        path = DOCS_DIR / "ADR-0011-measurement-authority.md"
        text = path.read_text(encoding="utf-8")

        assert "Forbidden" in text or "forbidden" in text
        assert "acoustically correct" in text.lower()


class TestEpistemicStatusInheritance:
    """Tests verifying authority inheritance rules."""

    def test_no_silent_inheritance_invariant(self):
        """ADR-0012 must state the no-silent-inheritance rule."""
        path = DOCS_DIR / "ADR-0012-epistemic-status-taxonomy.md"
        text = path.read_text(encoding="utf-8")

        assert "silently inherit" in text.lower() or "silent" in text.lower()
        assert "authority" in text.lower()

    def test_forbidden_transitions_documented(self):
        """ADR-0012 must document forbidden status transitions."""
        path = DOCS_DIR / "ADR-0012-epistemic-status-taxonomy.md"
        text = path.read_text(encoding="utf-8")

        # Should have a forbidden transitions section
        assert "Forbidden" in text


class TestAGEConstitutionalContract:
    """Tests verifying AGE constitutional contract."""

    def test_age_cannot_establish_truth(self):
        """AGE contract must state it cannot establish truth."""
        path = DOCS_DIR / "AGE_CONSTITUTIONAL_CONTRACT.md"
        text = path.read_text(encoding="utf-8")

        assert "truth" in text.lower()
        assert "DECISION SUPPORT" in text or "decision_support" in text

    def test_age_references_epistemic_status(self):
        """AGE contract should reference epistemic status constraints."""
        path = DOCS_DIR / "AGE_CONSTITUTIONAL_CONTRACT.md"
        text = path.read_text(encoding="utf-8")

        # Should reference ADR-0011 and ADR-0012
        assert "ADR-0011" in text or "epistemic" in text.lower()

    def test_age_outputs_are_heuristic(self):
        """AGE contract must classify outputs as Heuristic."""
        path = DOCS_DIR / "AGE_CONSTITUTIONAL_CONTRACT.md"
        text = path.read_text(encoding="utf-8")

        assert "Heuristic" in text


class TestCrossReferences:
    """Tests verifying documents cross-reference each other."""

    def test_adr_0010_references_adr_0011(self):
        """ADR-0010 should reference ADR-0011."""
        path = DOCS_DIR / "ADR-0010-guidance-authority-boundary.md"
        text = path.read_text(encoding="utf-8")

        assert "ADR-0011" in text

    def test_adr_0010_references_adr_0012(self):
        """ADR-0010 should reference ADR-0012."""
        path = DOCS_DIR / "ADR-0010-guidance-authority-boundary.md"
        text = path.read_text(encoding="utf-8")

        assert "ADR-0012" in text

    def test_matrix_references_adrs(self):
        """Epistemic status matrix should reference source ADRs."""
        path = DOCS_DIR / "EPISTEMIC_STATUS_MATRIX.md"
        text = path.read_text(encoding="utf-8")

        assert "ADR-0011" in text
        assert "ADR-0012" in text

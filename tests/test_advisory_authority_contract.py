# INSTRUMENT CLASS: MEASUREMENT
"""Tests for advisory authority contract.

Validates:
- Authority class enumeration
- Guidance scope enumeration
- AdvisoryAuthorityV1 invariants
- Serialization/deserialization
- Pre-defined authority constants
"""

from __future__ import annotations

import pytest

from tap_tone_pi.agentic.contracts.advisory_authority import (
    AuthorityClass,
    GuidanceScope,
    AdvisoryAuthorityV1,
    AGE_ATTENTION_AUTHORITY,
    AGE_EXPLANATION_AUTHORITY,
    AGE_WORKFLOW_AUTHORITY,
)


class TestAuthorityClassEnum:
    """Tests for AuthorityClass enumeration."""

    def test_authority_classes_exist(self):
        """All expected authority classes should exist."""
        assert AuthorityClass.MEASUREMENT == "measurement"
        assert AuthorityClass.PROVENANCE == "provenance"
        assert AuthorityClass.DECISION_SUPPORT == "decision_support"
        assert AuthorityClass.INTERPRETIVE == "interpretive"

    def test_authority_class_is_string_enum(self):
        """AuthorityClass should be usable as a string."""
        # StrEnum value can be used in JSON serialization
        assert AuthorityClass.DECISION_SUPPORT.value == "decision_support"
        # Can compare with string value
        assert AuthorityClass.DECISION_SUPPORT == "decision_support"


class TestGuidanceScopeEnum:
    """Tests for GuidanceScope enumeration."""

    def test_guidance_scopes_exist(self):
        """All expected guidance scopes should exist."""
        assert GuidanceScope.ATTENTION_GUIDANCE == "attention_guidance"
        assert GuidanceScope.EXPLANATION == "explanation"
        assert GuidanceScope.WORKFLOW_HINT == "workflow_hint"


class TestAdvisoryAuthorityV1:
    """Tests for AdvisoryAuthorityV1 dataclass."""

    def test_default_decision_support_cannot_establish_truth(self):
        """DECISION_SUPPORT authority should default to cannot establish truth."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
        )
        assert auth.can_establish_truth is False

    def test_default_decision_support_cannot_modify_measurement(self):
        """DECISION_SUPPORT authority should default to cannot modify measurement."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
        )
        assert auth.can_modify_measurement is False

    def test_default_decision_support_cannot_enter_measurement_export(self):
        """DECISION_SUPPORT authority should default to cannot enter export."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
        )
        assert auth.can_enter_measurement_export is False

    def test_validate_decision_support_with_truth_claim_fails(self):
        """DECISION_SUPPORT claiming truth should fail validation."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
            can_establish_truth=True,  # Invalid!
        )
        errors = auth.validate()
        assert len(errors) > 0
        assert any("cannot establish truth" in e for e in errors)

    def test_validate_decision_support_with_export_claim_fails(self):
        """DECISION_SUPPORT claiming export entry should fail validation."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
            can_enter_measurement_export=True,  # Invalid!
        )
        errors = auth.validate()
        assert len(errors) > 0
        assert any("cannot enter measurement export" in e for e in errors)

    def test_validate_valid_decision_support_passes(self):
        """Valid DECISION_SUPPORT authority should pass validation."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
            can_establish_truth=False,
            can_modify_measurement=False,
            can_enter_measurement_export=False,
        )
        errors = auth.validate()
        assert errors == []

    def test_validate_measurement_without_truth_fails(self):
        """MEASUREMENT authority must be able to establish truth."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.MEASUREMENT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,  # Unusual but testable
            can_establish_truth=False,  # Invalid for MEASUREMENT
            can_enter_measurement_export=True,
        )
        errors = auth.validate()
        assert any("must be able to establish truth" in e for e in errors)


class TestAdvisoryAuthoritySerialization:
    """Tests for AdvisoryAuthorityV1 serialization."""

    def test_to_dict(self):
        """to_dict should produce JSON-serializable dict."""
        auth = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.ATTENTION_GUIDANCE,
        )
        d = auth.to_dict()

        assert d["authority_class"] == "decision_support"
        assert d["authority_scope"] == "attention_guidance"
        assert d["can_establish_truth"] is False
        assert d["can_modify_measurement"] is False
        assert d["can_enter_measurement_export"] is False

    def test_from_dict(self):
        """from_dict should reconstruct the object."""
        original = AdvisoryAuthorityV1(
            authority_class=AuthorityClass.DECISION_SUPPORT,
            authority_scope=GuidanceScope.EXPLANATION,
        )
        d = original.to_dict()
        restored = AdvisoryAuthorityV1.from_dict(d)

        assert restored.authority_class == original.authority_class
        assert restored.authority_scope == original.authority_scope
        assert restored.can_establish_truth == original.can_establish_truth

    def test_round_trip(self):
        """to_dict -> from_dict should preserve all fields."""
        original = AGE_ATTENTION_AUTHORITY
        restored = AdvisoryAuthorityV1.from_dict(original.to_dict())

        assert restored == original


class TestPredefinedAuthorities:
    """Tests for pre-defined authority constants."""

    def test_age_attention_authority_is_decision_support(self):
        """AGE_ATTENTION_AUTHORITY should be DECISION_SUPPORT."""
        assert AGE_ATTENTION_AUTHORITY.authority_class == AuthorityClass.DECISION_SUPPORT

    def test_age_attention_authority_cannot_establish_truth(self):
        """AGE_ATTENTION_AUTHORITY cannot establish truth."""
        assert AGE_ATTENTION_AUTHORITY.can_establish_truth is False

    def test_age_attention_authority_cannot_modify_measurement(self):
        """AGE_ATTENTION_AUTHORITY cannot modify measurement."""
        assert AGE_ATTENTION_AUTHORITY.can_modify_measurement is False

    def test_age_attention_authority_cannot_enter_export(self):
        """AGE_ATTENTION_AUTHORITY cannot enter measurement export."""
        assert AGE_ATTENTION_AUTHORITY.can_enter_measurement_export is False

    def test_all_predefined_authorities_valid(self):
        """All pre-defined authorities should pass validation."""
        for auth in [
            AGE_ATTENTION_AUTHORITY,
            AGE_EXPLANATION_AUTHORITY,
            AGE_WORKFLOW_AUTHORITY,
        ]:
            errors = auth.validate()
            assert errors == [], f"{auth} failed validation: {errors}"

    def test_predefined_authorities_have_distinct_scopes(self):
        """Pre-defined authorities should have distinct scopes."""
        scopes = [
            AGE_ATTENTION_AUTHORITY.authority_scope,
            AGE_EXPLANATION_AUTHORITY.authority_scope,
            AGE_WORKFLOW_AUTHORITY.authority_scope,
        ]
        assert len(scopes) == len(set(scopes))

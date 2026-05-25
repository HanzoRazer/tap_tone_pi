# INSTRUMENT CLASS: GOVERNANCE
"""Tests for platform contract JSON schemas.

Validates that platform contract schemas are valid and enforce invariants.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).parent.parent / "docs" / "platform-contracts" / "schemas"


def _load(name: str) -> dict:
    """Load a schema by name."""
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class TestAuthoritySchema:
    """Tests for authority-v1.schema.json."""

    def test_schema_is_valid_json(self):
        """Schema should be valid JSON."""
        schema = _load("authority-v1.schema.json")
        assert "$schema" in schema

    def test_accepts_decision_support(self):
        """Schema should accept decision_support with required fields."""
        schema = _load("authority-v1.schema.json")
        jsonschema.validate(
            {
                "authority_class": "decision_support",
                "authority_scope": "attention_guidance",
                "can_establish_truth": False,
                "can_authorize_execution": False,
                "can_enter_measurement_export": False,
                "source_repo": "tap_tone_pi",
                "local_authority_type": "AuthorityClass.DECISION_SUPPORT",
            },
            schema,
        )

    def test_accepts_measurement(self):
        """Schema should accept measurement authority."""
        schema = _load("authority-v1.schema.json")
        jsonschema.validate(
            {
                "authority_class": "measurement",
                "can_establish_truth": False,
                "can_authorize_execution": False,
                "can_enter_measurement_export": True,
            },
            schema,
        )

    def test_rejects_unknown_authority_class(self):
        """Schema should reject unknown authority class."""
        schema = _load("authority-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "authority_class": "unknown_class",
                    "can_establish_truth": False,
                    "can_authorize_execution": False,
                    "can_enter_measurement_export": False,
                },
                schema,
            )

    def test_rejects_missing_required_fields(self):
        """Schema should reject missing required fields."""
        schema = _load("authority-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"authority_class": "measurement"},
                schema,
            )


class TestConfidenceSchema:
    """Tests for confidence-v1.schema.json."""

    def test_schema_is_valid_json(self):
        """Schema should be valid JSON."""
        schema = _load("confidence-v1.schema.json")
        assert "$schema" in schema

    def test_requires_domain_value_source(self):
        """Schema should require domain, value, and source."""
        schema = _load("confidence-v1.schema.json")
        jsonschema.validate(
            {
                "domain": "ranking",
                "value": 0.72,
                "source": "luthiers.rank_score",
                "does_not_imply": ["approval", "execution_authority"],
            },
            schema,
        )

    def test_rejects_value_above_one(self):
        """Schema should reject confidence > 1.0."""
        schema = _load("confidence-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "domain": "signal",
                    "value": 1.5,
                    "source": "test",
                },
                schema,
            )

    def test_rejects_value_below_zero(self):
        """Schema should reject confidence < 0.0."""
        schema = _load("confidence-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "domain": "signal",
                    "value": -0.1,
                    "source": "test",
                },
                schema,
            )

    def test_rejects_missing_source(self):
        """Schema should reject missing source."""
        schema = _load("confidence-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "domain": "interpretive",
                    "value": 0.85,
                },
                schema,
            )

    def test_rejects_empty_source(self):
        """Schema should reject empty source string."""
        schema = _load("confidence-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "domain": "interpretive",
                    "value": 0.85,
                    "source": "",
                },
                schema,
            )


class TestEpistemicStatusSchema:
    """Tests for epistemic-status-v1.schema.json."""

    def test_schema_is_valid_json(self):
        """Schema should be valid JSON."""
        schema = _load("epistemic-status-v1.schema.json")
        assert "$schema" in schema

    def test_accepts_derived_artifact(self):
        """Schema should accept derived artifact."""
        schema = _load("epistemic-status-v1.schema.json")
        jsonschema.validate(
            {
                "status": "derived",
                "source": "fft_peak_extractor",
                "may_enter_measurement_export": True,
            },
            schema,
        )

    def test_accepts_predicted_with_export_false(self):
        """Schema should accept predicted with may_enter_measurement_export=False."""
        schema = _load("epistemic-status-v1.schema.json")
        jsonschema.validate(
            {
                "status": "predicted",
                "source": "rayleigh_ritz_solver",
                "may_enter_measurement_export": False,
                "prohibited_transitions": ["observed", "derived"],
            },
            schema,
        )

    def test_accepts_heuristic_with_export_false(self):
        """Schema should accept heuristic with may_enter_measurement_export=False."""
        schema = _load("epistemic-status-v1.schema.json")
        jsonschema.validate(
            {
                "status": "heuristic",
                "source": "age_directive_engine",
                "may_enter_measurement_export": False,
            },
            schema,
        )

    def test_rejects_unknown_status(self):
        """Schema should reject unknown epistemic status."""
        schema = _load("epistemic-status-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "status": "unknown_status",
                    "source": "test",
                    "may_enter_measurement_export": False,
                },
                schema,
            )


class TestReviewDecisionSchema:
    """Tests for review-decision-v1.schema.json."""

    def test_schema_is_valid_json(self):
        """Schema should be valid JSON."""
        schema = _load("review-decision-v1.schema.json")
        assert "$schema" in schema

    def test_accepts_mark_reviewed(self):
        """Schema should accept mark_reviewed decision."""
        schema = _load("review-decision-v1.schema.json")
        jsonschema.validate(
            {
                "decision_type": "mark_reviewed",
                "resulting_status": "reviewed",
                "human_review_recorded": True,
                "implementation_authorized": False,
                "execution_authorized": False,
                "machine_output_allowed": False,
                "reviewer_ref": "operator@example.com",
            },
            schema,
        )

    def test_rejects_execution_authorized_true(self):
        """Schema should reject execution_authorized=True."""
        schema = _load("review-decision-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "decision_type": "mark_reviewed",
                    "human_review_recorded": True,
                    "implementation_authorized": False,
                    "execution_authorized": True,
                    "machine_output_allowed": False,
                },
                schema,
            )

    def test_rejects_implementation_authorized_true(self):
        """Schema should reject implementation_authorized=True."""
        schema = _load("review-decision-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "decision_type": "mark_reviewed",
                    "human_review_recorded": True,
                    "implementation_authorized": True,
                    "execution_authorized": False,
                    "machine_output_allowed": False,
                },
                schema,
            )

    def test_rejects_machine_output_allowed_true(self):
        """Schema should reject machine_output_allowed=True."""
        schema = _load("review-decision-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "decision_type": "mark_reviewed",
                    "human_review_recorded": True,
                    "implementation_authorized": False,
                    "execution_authorized": False,
                    "machine_output_allowed": True,
                },
                schema,
            )

    def test_rejects_human_review_recorded_false(self):
        """Schema should reject human_review_recorded=False."""
        schema = _load("review-decision-v1.schema.json")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "decision_type": "mark_reviewed",
                    "human_review_recorded": False,
                    "implementation_authorized": False,
                    "execution_authorized": False,
                    "machine_output_allowed": False,
                },
                schema,
            )

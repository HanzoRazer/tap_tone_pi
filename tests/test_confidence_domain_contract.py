# INSTRUMENT CLASS: MEASUREMENT
"""Tests for typed confidence domain contract.

Validates:
- ConfidenceDomain enumeration
- TypedConfidenceV1 invariants
- Domain classification (advisory vs measurement)
- Serialization/deserialization
- Advisory validation rules
"""

from __future__ import annotations

import pytest

from tap_tone_pi.agentic.contracts.confidence_domain import (
    ConfidenceDomain,
    TypedConfidenceV1,
    MEASUREMENT_DOMAINS,
    ADVISORY_DOMAINS,
)


class TestConfidenceDomainEnum:
    """Tests for ConfidenceDomain enumeration."""

    def test_all_domains_exist(self):
        """All expected confidence domains should exist."""
        assert ConfidenceDomain.SIGNAL == "signal"
        assert ConfidenceDomain.MEASUREMENT == "measurement"
        assert ConfidenceDomain.INTERPRETIVE == "interpretive"
        assert ConfidenceDomain.RECOMMENDATION == "recommendation"

    def test_domain_is_string_enum(self):
        """ConfidenceDomain should be usable as a string."""
        assert ConfidenceDomain.SIGNAL.value == "signal"
        assert ConfidenceDomain.INTERPRETIVE == "interpretive"

    def test_measurement_domains_set(self):
        """MEASUREMENT_DOMAINS should contain signal and measurement."""
        assert ConfidenceDomain.SIGNAL in MEASUREMENT_DOMAINS
        assert ConfidenceDomain.MEASUREMENT in MEASUREMENT_DOMAINS
        assert ConfidenceDomain.INTERPRETIVE not in MEASUREMENT_DOMAINS
        assert ConfidenceDomain.RECOMMENDATION not in MEASUREMENT_DOMAINS

    def test_advisory_domains_set(self):
        """ADVISORY_DOMAINS should contain interpretive and recommendation."""
        assert ConfidenceDomain.INTERPRETIVE in ADVISORY_DOMAINS
        assert ConfidenceDomain.RECOMMENDATION in ADVISORY_DOMAINS
        assert ConfidenceDomain.SIGNAL not in ADVISORY_DOMAINS
        assert ConfidenceDomain.MEASUREMENT not in ADVISORY_DOMAINS

    def test_domains_are_disjoint(self):
        """Measurement and advisory domains should not overlap."""
        assert MEASUREMENT_DOMAINS.isdisjoint(ADVISORY_DOMAINS)


class TestTypedConfidenceV1:
    """Tests for TypedConfidenceV1 dataclass."""

    def test_create_interpretive_confidence(self):
        """Create a valid interpretive confidence."""
        conf = TypedConfidenceV1(
            value=0.85,
            domain=ConfidenceDomain.INTERPRETIVE,
            source="wolf_beat_model",
        )
        assert conf.value == 0.85
        assert conf.domain == ConfidenceDomain.INTERPRETIVE
        assert conf.source == "wolf_beat_model"

    def test_create_recommendation_confidence(self):
        """Create a valid recommendation confidence."""
        conf = TypedConfidenceV1(
            value=0.7,
            domain=ConfidenceDomain.RECOMMENDATION,
            source="attention_policy",
        )
        assert conf.value == 0.7
        assert conf.domain == ConfidenceDomain.RECOMMENDATION

    def test_create_signal_confidence(self):
        """Create a valid signal confidence (for MEASUREMENT modules)."""
        conf = TypedConfidenceV1(
            value=0.95,
            domain=ConfidenceDomain.SIGNAL,
            source="peak_extractor",
        )
        assert conf.value == 0.95
        assert conf.domain == ConfidenceDomain.SIGNAL

    def test_value_bounds_low(self):
        """Confidence value cannot be negative."""
        with pytest.raises(ValueError, match="must be in"):
            TypedConfidenceV1(value=-0.1, domain=ConfidenceDomain.INTERPRETIVE)

    def test_value_bounds_high(self):
        """Confidence value cannot exceed 1.0."""
        with pytest.raises(ValueError, match="must be in"):
            TypedConfidenceV1(value=1.5, domain=ConfidenceDomain.INTERPRETIVE)

    def test_value_at_boundaries(self):
        """Confidence values at 0.0 and 1.0 are valid."""
        low = TypedConfidenceV1(value=0.0, domain=ConfidenceDomain.RECOMMENDATION)
        high = TypedConfidenceV1(value=1.0, domain=ConfidenceDomain.RECOMMENDATION)
        assert low.value == 0.0
        assert high.value == 1.0

    def test_default_source_is_empty(self):
        """Source defaults to empty string if not provided."""
        conf = TypedConfidenceV1(value=0.5, domain=ConfidenceDomain.INTERPRETIVE)
        assert conf.source == ""

    def test_is_advisory_domain(self):
        """is_advisory_domain returns True for advisory domains."""
        interp = TypedConfidenceV1(value=0.8, domain=ConfidenceDomain.INTERPRETIVE)
        rec = TypedConfidenceV1(value=0.6, domain=ConfidenceDomain.RECOMMENDATION)
        sig = TypedConfidenceV1(value=0.9, domain=ConfidenceDomain.SIGNAL)
        meas = TypedConfidenceV1(value=0.7, domain=ConfidenceDomain.MEASUREMENT)

        assert interp.is_advisory_domain() is True
        assert rec.is_advisory_domain() is True
        assert sig.is_advisory_domain() is False
        assert meas.is_advisory_domain() is False

    def test_is_measurement_domain(self):
        """is_measurement_domain returns True for measurement domains."""
        sig = TypedConfidenceV1(value=0.9, domain=ConfidenceDomain.SIGNAL)
        meas = TypedConfidenceV1(value=0.7, domain=ConfidenceDomain.MEASUREMENT)
        interp = TypedConfidenceV1(value=0.8, domain=ConfidenceDomain.INTERPRETIVE)

        assert sig.is_measurement_domain() is True
        assert meas.is_measurement_domain() is True
        assert interp.is_measurement_domain() is False


class TestTypedConfidenceValidation:
    """Tests for advisory validation rules."""

    def test_validate_interpretive_for_advisory_passes(self):
        """Interpretive confidence is valid for advisory use."""
        conf = TypedConfidenceV1(
            value=0.85,
            domain=ConfidenceDomain.INTERPRETIVE,
            source="wolf_advisor",
        )
        errors = conf.validate_for_advisory()
        assert errors == []

    def test_validate_recommendation_for_advisory_passes(self):
        """Recommendation confidence is valid for advisory use."""
        conf = TypedConfidenceV1(
            value=0.7,
            domain=ConfidenceDomain.RECOMMENDATION,
        )
        errors = conf.validate_for_advisory()
        assert errors == []

    def test_validate_signal_for_advisory_fails(self):
        """Signal confidence is NOT valid for advisory use."""
        conf = TypedConfidenceV1(
            value=0.95,
            domain=ConfidenceDomain.SIGNAL,
            source="peak_extractor",
        )
        errors = conf.validate_for_advisory()
        assert len(errors) == 1
        assert "signal" in errors[0].lower()
        assert "cannot emit" in errors[0].lower()

    def test_validate_measurement_for_advisory_fails(self):
        """Measurement confidence is NOT valid for advisory use."""
        conf = TypedConfidenceV1(
            value=0.9,
            domain=ConfidenceDomain.MEASUREMENT,
            source="repeatability_check",
        )
        errors = conf.validate_for_advisory()
        assert len(errors) == 1
        assert "measurement" in errors[0].lower()


class TestTypedConfidenceSerialization:
    """Tests for TypedConfidenceV1 serialization."""

    def test_to_dict(self):
        """to_dict should produce JSON-serializable dict."""
        conf = TypedConfidenceV1(
            value=0.85,
            domain=ConfidenceDomain.INTERPRETIVE,
            source="wolf_beat_model",
        )
        d = conf.to_dict()

        assert d["value"] == 0.85
        assert d["domain"] == "interpretive"
        assert d["source"] == "wolf_beat_model"

    def test_from_dict(self):
        """from_dict should reconstruct the object."""
        original = TypedConfidenceV1(
            value=0.7,
            domain=ConfidenceDomain.RECOMMENDATION,
            source="attention_policy",
        )
        d = original.to_dict()
        restored = TypedConfidenceV1.from_dict(d)

        assert restored.value == original.value
        assert restored.domain == original.domain
        assert restored.source == original.source

    def test_round_trip(self):
        """to_dict -> from_dict should preserve all fields."""
        original = TypedConfidenceV1(
            value=0.95,
            domain=ConfidenceDomain.SIGNAL,
            source="snr_estimator",
        )
        restored = TypedConfidenceV1.from_dict(original.to_dict())

        assert restored == original

    def test_frozen_dataclass(self):
        """TypedConfidenceV1 should be immutable."""
        conf = TypedConfidenceV1(
            value=0.5,
            domain=ConfidenceDomain.INTERPRETIVE,
        )
        with pytest.raises(AttributeError):
            conf.value = 0.9

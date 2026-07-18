# INSTRUMENT CLASS: MEASUREMENT
"""Tests for process variance evidence contracts (Dev Order 89B).

Tests cover:
- Reference body creation and serialization
- Variance decomposition computation
- Process variance evidence creation
- Feasibility summary creation
- Variance band classification
- Constitutional semantics (no advisory fields)
"""

import json
import pytest

from tap_tone_pi.experiment import (
    VarianceBandThresholdsV1,
    create_reference_body,
    decompose_variance,
    compute_process_variance_evidence,
    classify_variance_band,
    create_feasibility_summary,
)


class TestReferenceBodyRecord:
    """Tests for ReferenceBodyRecordV1."""

    def test_create_reference_body_minimal(self):
        """create_reference_body with minimal args should work."""
        ref = create_reference_body("ref_001", "dreadnought")

        assert ref.reference_body_id == "ref_001"
        assert ref.body_style == "dreadnought"
        assert ref.state == "unstrung_assembled"

    def test_create_reference_body_full(self):
        """create_reference_body with all args should work."""
        ref = create_reference_body(
            "ref_001",
            "dreadnought",
            specimen_id="specimen_001",
            description="Sitka/rosewood dreadnought reference",
            state="unstrung_assembled",
            wood_species_top="sitka_spruce",
            wood_species_back_sides="indian_rosewood",
            notes="Built 2026-01-15",
        )

        assert ref.specimen_id == "specimen_001"
        assert ref.wood_species_top == "sitka_spruce"
        assert ref.wood_species_back_sides == "indian_rosewood"

    def test_with_measurement_adds_measurement(self):
        """with_measurement should add measurement ID."""
        ref = create_reference_body("ref_001", "dreadnought")
        updated = ref.with_measurement("m001")

        assert "m001" in updated.measurement_ids
        assert len(updated.measurement_ids) == 1

    def test_with_measurement_is_idempotent(self):
        """with_measurement should not add duplicates."""
        ref = create_reference_body("ref_001", "dreadnought")
        ref = ref.with_measurement("m001")
        ref = ref.with_measurement("m001")

        assert len(ref.measurement_ids) == 1

    def test_reference_body_serializes_to_dict(self):
        """ReferenceBodyRecordV1 should serialize to dict."""
        ref = create_reference_body("ref_001", "dreadnought")
        d = ref.to_dict()

        assert d["schema_version"] == "reference_body_record_v1"
        assert d["reference_body_id"] == "ref_001"
        assert d["epistemic_status"] == "derived"

    def test_reference_body_serializes_to_json(self):
        """ReferenceBodyRecordV1 dict should be JSON-serializable."""
        ref = create_reference_body("ref_001", "dreadnought")
        d = ref.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestVarianceDecomposition:
    """Tests for variance decomposition computation."""

    def test_decompose_variance_basic(self):
        """decompose_variance should compute σ_build correctly."""
        # σ_total = 5, σ_measurement = 3
        # σ²_build = 25 - 9 = 16
        # σ_build = 4
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")

        assert decomp.sigma_total == 5.0
        assert decomp.sigma_measurement == 3.0
        assert decomp.sigma_build == pytest.approx(4.0, rel=0.01)
        assert decomp.sigma_build_squared == pytest.approx(16.0, rel=0.01)
        assert decomp.clamped_to_zero is False

    def test_decompose_variance_clamps_negative(self):
        """decompose_variance should clamp negative σ²_build to zero."""
        # σ_total = 3, σ_measurement = 5
        # σ²_build = 9 - 25 = -16 → clamped to 0
        decomp = decompose_variance(3.0, 5.0, "A0", "Hz")

        assert decomp.sigma_build == 0.0
        assert decomp.sigma_build_squared == 0.0
        assert decomp.clamped_to_zero is True

    def test_decompose_variance_equal_inputs(self):
        """decompose_variance with equal inputs should give zero build variance."""
        decomp = decompose_variance(5.0, 5.0, "A0", "Hz")

        assert decomp.sigma_build == 0.0
        assert decomp.clamped_to_zero is False

    def test_decompose_variance_zero_measurement(self):
        """decompose_variance with zero measurement should give full build variance."""
        decomp = decompose_variance(5.0, 0.0, "A0", "Hz")

        assert decomp.sigma_build == pytest.approx(5.0, rel=0.01)
        assert decomp.clamped_to_zero is False

    def test_decomposition_serializes_to_dict(self):
        """VarianceDecompositionV1 should serialize to dict."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        d = decomp.to_dict()

        assert d["schema_version"] == "variance_decomposition_v1"
        assert "sigma_build" in d
        assert d["response_variable"] == "A0"


class TestProcessVarianceEvidence:
    """Tests for ProcessVarianceEvidenceV1."""

    def test_compute_process_variance_evidence_basic(self):
        """compute_process_variance_evidence should compute statistics."""
        cohort = [100.0, 102.0, 98.0, 101.0, 99.0]
        reference = [100.0, 100.5, 99.5, 100.2, 99.8]

        evidence = compute_process_variance_evidence(
            "ev_001",
            cohort,
            reference,
            "A0",
            "Hz",
        )

        assert evidence.evidence_id == "ev_001"
        assert evidence.measurement_count_cohort == 5
        assert evidence.measurement_count_reference == 5
        assert evidence.cohort_mean is not None
        assert evidence.cohort_std is not None
        assert evidence.reference_std is not None
        assert evidence.decomposition is not None

    def test_compute_process_variance_evidence_with_linkage(self):
        """compute_process_variance_evidence should store linkage."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [100.0, 102.0],
            [100.0, 100.5],
            "A0",
            "Hz",
            experiment_design_id="design_001",
            campaign_id="campaign_001",
            reference_body_id="ref_001",
        )

        assert evidence.experiment_design_id == "design_001"
        assert evidence.campaign_id == "campaign_001"
        assert evidence.reference_body_id == "ref_001"

    def test_compute_process_variance_evidence_empty_cohort(self):
        """compute_process_variance_evidence should handle empty cohort."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [],
            [100.0, 100.5],
            "A0",
            "Hz",
        )

        assert evidence.measurement_count_cohort == 0
        assert evidence.cohort_mean is None
        assert evidence.cohort_std is None

    def test_compute_process_variance_evidence_single_value(self):
        """compute_process_variance_evidence should handle single value."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [100.0],
            [100.0],
            "A0",
            "Hz",
        )

        assert evidence.cohort_std == 0.0
        assert evidence.reference_std == 0.0

    def test_process_variance_evidence_serializes_to_dict(self):
        """ProcessVarianceEvidenceV1 should serialize to dict."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [100.0, 102.0, 98.0],
            [100.0, 100.5, 99.5],
            "A0",
            "Hz",
        )
        d = evidence.to_dict()

        assert d["schema_version"] == "process_variance_evidence_v1"
        assert "cohort_values" in d
        assert "decomposition" in d

    def test_process_variance_evidence_serializes_to_json(self):
        """ProcessVarianceEvidenceV1 dict should be JSON-serializable."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [100.0, 102.0],
            [100.0, 100.5],
            "A0",
            "Hz",
        )
        d = evidence.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestVarianceBandClassification:
    """Tests for variance band classification."""

    def test_classify_variance_band_low(self):
        """classify_variance_band should return 'low' below low threshold."""
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable="A0",
        )
        band = classify_variance_band(2.5, thresholds)

        assert band == "low"

    def test_classify_variance_band_medium(self):
        """classify_variance_band should return 'medium' between thresholds."""
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable="A0",
        )
        band = classify_variance_band(5.0, thresholds)

        assert band == "medium"

    def test_classify_variance_band_high(self):
        """classify_variance_band should return 'high' above high threshold."""
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable="A0",
        )
        band = classify_variance_band(15.0, thresholds)

        assert band == "high"

    def test_classify_variance_band_at_low_boundary(self):
        """classify_variance_band at low boundary should return 'low'."""
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable="A0",
        )
        band = classify_variance_band(3.0, thresholds)

        assert band == "low"

    def test_classify_variance_band_at_high_boundary(self):
        """classify_variance_band at high boundary should return 'medium'."""
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=3.0,
            high_threshold_pct=10.0,
            response_variable="A0",
        )
        band = classify_variance_band(10.0, thresholds)

        assert band == "medium"


class TestFeasibilitySummary:
    """Tests for FeasibilitySummaryV1."""

    def test_create_feasibility_summary_basic(self):
        """create_feasibility_summary should compute CV and band."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")

        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )

        assert summary.summary_id == "summary_001"
        assert summary.sigma_build == pytest.approx(4.0, rel=0.01)
        # CV = 4/100 * 100 = 4%
        assert summary.cv_build_pct == pytest.approx(4.0, rel=0.01)
        assert summary.variance_band == "medium"  # 3% < 4% <= 10%

    def test_create_feasibility_summary_low_band(self):
        """create_feasibility_summary should classify low variance."""
        decomp = decompose_variance(2.0, 1.5, "A0", "Hz")

        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )

        # σ_build = sqrt(4 - 2.25) = sqrt(1.75) ≈ 1.32
        # CV = 1.32/100 * 100 = 1.32%
        assert summary.variance_band == "low"

    def test_create_feasibility_summary_with_linkage(self):
        """create_feasibility_summary should store linkage."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")

        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
            experiment_design_id="design_001",
            campaign_id="campaign_001",
        )

        assert summary.experiment_design_id == "design_001"
        assert summary.campaign_id == "campaign_001"

    def test_create_feasibility_summary_custom_thresholds(self):
        """create_feasibility_summary should use custom thresholds."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        thresholds = VarianceBandThresholdsV1(
            low_threshold_pct=5.0,
            high_threshold_pct=15.0,
            response_variable="A0",
        )

        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
            thresholds=thresholds,
        )

        # CV = 4%, thresholds are 5%/15%
        assert summary.variance_band == "low"  # 4% <= 5%

    def test_feasibility_summary_serializes_to_dict(self):
        """FeasibilitySummaryV1 should serialize to dict."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )
        d = summary.to_dict()

        assert d["schema_version"] == "feasibility_summary_v1"
        assert "variance_band" in d
        assert "cv_build_pct" in d

    def test_feasibility_summary_serializes_to_json(self):
        """FeasibilitySummaryV1 dict should be JSON-serializable."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )
        d = summary.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestConstitutionalSemantics:
    """Tests ensuring process variance contains no advisory semantics."""

    FORBIDDEN_ADVISORY_TERMS = {
        "recommended",
        "optimal",
        "best",
        "preferred",
        "approved",
        "good",
        "bad",
        "quality",
        "grade",
        "verdict",
        "winner",
        "passed",
        "failed",
        "success",
        "green",
        "yellow",
    }
    # Note: "red" removed because it appears in "squared" (false positive)
    # Note: "pass"/"fail" changed to "passed"/"failed" to avoid false positives

    def test_reference_body_fields_are_advisory_free(self):
        """ReferenceBodyRecordV1 should not contain advisory fields."""
        ref = create_reference_body("ref_001", "dreadnought")
        d = ref.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Reference body key '{key}' contains advisory term '{term}'"
                )

    def test_variance_decomposition_fields_are_advisory_free(self):
        """VarianceDecompositionV1 should not contain advisory fields."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        d = decomp.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Decomposition key '{key}' contains advisory term '{term}'"
                )

    def test_process_variance_evidence_fields_are_advisory_free(self):
        """ProcessVarianceEvidenceV1 should not contain advisory fields."""
        evidence = compute_process_variance_evidence(
            "ev_001",
            [100.0, 102.0],
            [100.0, 100.5],
            "A0",
            "Hz",
        )
        d = evidence.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Evidence key '{key}' contains advisory term '{term}'"
                )

    def test_feasibility_summary_fields_are_advisory_free(self):
        """FeasibilitySummaryV1 should not contain advisory fields."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )
        d = summary.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Summary key '{key}' contains advisory term '{term}'"
                )

    def test_variance_band_uses_neutral_language(self):
        """variance_band should use neutral language (low/medium/high)."""
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        summary = create_feasibility_summary(
            "summary_001",
            "A0",
            "Hz",
            cohort_mean=100.0,
            decomposition=decomp,
            cohort_size=20,
            reference_measurement_count=10,
        )

        assert summary.variance_band in ("low", "medium", "high")

    def test_all_epistemic_status_are_derived(self):
        """All DO-89B types epistemic_status should be 'derived'."""
        ref = create_reference_body("ref_001", "dreadnought")
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        evidence = compute_process_variance_evidence(
            "ev_001", [100.0], [100.0], "A0", "Hz"
        )
        thresholds = VarianceBandThresholdsV1()
        summary = create_feasibility_summary(
            "summary_001", "A0", "Hz", 100.0, decomp, 20, 10
        )

        assert ref.epistemic_status == "derived"
        assert decomp.epistemic_status == "derived"
        assert evidence.epistemic_status == "derived"
        assert thresholds.epistemic_status == "derived"
        assert summary.epistemic_status == "derived"

    def test_schema_versions_are_present(self):
        """All DO-89B types should have schema_version."""
        ref = create_reference_body("ref_001", "dreadnought")
        decomp = decompose_variance(5.0, 3.0, "A0", "Hz")
        evidence = compute_process_variance_evidence(
            "ev_001", [100.0], [100.0], "A0", "Hz"
        )
        thresholds = VarianceBandThresholdsV1()
        summary = create_feasibility_summary(
            "summary_001", "A0", "Hz", 100.0, decomp, 20, 10
        )

        assert ref.schema_version == "reference_body_record_v1"
        assert decomp.schema_version == "variance_decomposition_v1"
        assert evidence.schema_version == "process_variance_evidence_v1"
        assert thresholds.schema_version == "variance_band_thresholds_v1"
        assert summary.schema_version == "feasibility_summary_v1"

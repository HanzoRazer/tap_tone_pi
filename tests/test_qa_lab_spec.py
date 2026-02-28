#!/usr/bin/env python3
"""
Tests for QA/QC Lab Specification Sheet module.
"""

import json
import tempfile
from pathlib import Path

import pytest

from tap_tone_pi.bending.qa_lab_spec import (
    # Section dataclasses
    SampleIdentification,
    SetupParameters,
    PrimaryMeasurements,
    ModeResult,
    ModalAnalysis,
    UncertaintyComponent,
    ErrorAnalysis,
    TriggeredRuleInfo,
    QualityAssessment,
    WolfToneAnalysis,
    QALabSpecEntry,
    # Builder and export
    build_qa_lab_spec_entry,
    export_qa_lab_csv,
    export_qa_lab_json,
    QA_LAB_CSV_COLUMNS,
)


class TestSampleIdentification:
    """Test SampleIdentification dataclass."""

    def test_basic_creation(self):
        """Should create sample ID with required fields."""
        sample = SampleIdentification(
            specimen_id="Sitka_001_L",
            grain_direction="L",
            species="Sitka Spruce",
        )
        assert sample.specimen_id == "Sitka_001_L"
        assert sample.grain_direction == "L"
        assert sample.species == "Sitka Spruce"

    def test_to_dict_omits_none(self):
        """to_dict should omit None values."""
        sample = SampleIdentification(specimen_id="Test_001")
        d = sample.to_dict()
        assert "specimen_id" in d
        assert "batch_id" not in d  # None values omitted


class TestSetupParameters:
    """Test SetupParameters dataclass."""

    def test_equipment_fields(self):
        """Should capture equipment identification."""
        setup = SetupParameters(
            device_id="DEV001",
            fixture_id="FIX003",
            mic_id="MIC_CM5",
            is_calibrated=True,
            calibration_date="2026-01-15",
        )
        assert setup.device_id == "DEV001"
        assert setup.is_calibrated is True

    def test_environment_fields(self):
        """Should capture environmental conditions."""
        setup = SetupParameters(
            temperature_c=22.5,
            humidity_rh=45.0,
        )
        d = setup.to_dict()
        assert d["temperature_c"] == 22.5
        assert d["humidity_rh"] == 45.0


class TestPrimaryMeasurements:
    """Test PrimaryMeasurements dataclass."""

    def test_dimensions(self):
        """Should capture physical dimensions."""
        meas = PrimaryMeasurements(
            length_mm=400.0,
            width_mm=30.0,
            thickness_mm=3.2,
            mass_g=15.5,
            density_kg_m3=420.0,
        )
        assert meas.length_mm == 400.0
        assert meas.density_kg_m3 == 420.0

    def test_frequencies(self):
        """Should capture peak frequencies."""
        meas = PrimaryMeasurements(
            fundamental_freq_hz=187.5,
            peak_frequencies_hz=[187.5, 523.1, 1025.4],
        )
        assert len(meas.peak_frequencies_hz) == 3


class TestModalAnalysis:
    """Test ModalAnalysis dataclass."""

    def test_modes_list(self):
        """Should store multiple modes."""
        mode1 = ModeResult(
            mode_number=1,
            frequency_hz=187.5,
            damping_ratio=0.015,
            quality_factor=33.3,
            amplitude=0.85,
            confidence="high",
        )
        mode2 = ModeResult(
            mode_number=2,
            frequency_hz=523.1,
            damping_ratio=0.012,
            quality_factor=41.7,
            amplitude=0.62,
            confidence="medium",
        )

        modal = ModalAnalysis(
            modes=[mode1, mode2],
            n_modes_identified=2,
            dominant_mode_freq_hz=187.5,
            dominant_mode_damping=0.015,
            dominant_mode_Q=33.3,
        )

        d = modal.to_dict()
        assert d["n_modes_identified"] == 2
        assert len(d["modes"]) == 2
        assert d["dominant_mode_Q"] == 33.3

    def test_modal_overlap_warning(self):
        """Should flag modal overlap."""
        modal = ModalAnalysis(modal_overlap_warning=True)
        assert modal.modal_overlap_warning is True


class TestErrorAnalysis:
    """Test ErrorAnalysis (uncertainty budget) dataclass."""

    def test_combined_uncertainty(self):
        """Should store GUM-compliant uncertainty."""
        errors = ErrorAnalysis(
            combined_standard_uncertainty=0.35,
            expanded_uncertainty=0.70,
            coverage_factor=2.0,
            confidence_level_percent=95.0,
            effective_dof=25.0,
            dominant_error_source="Thickness measurement",
        )
        assert errors.expanded_uncertainty == 0.70
        assert errors.coverage_factor == 2.0

    def test_uncertainty_components(self):
        """Should store individual components."""
        comp = UncertaintyComponent(
            name="Thickness measurement",
            value=0.25,
            unit="GPa",
            type="type_b",
            sensitivity_coefficient=3.0,
            description="Thickness ± 0.05 mm (×3 sensitivity)",
        )
        errors = ErrorAnalysis(components=[comp])
        d = errors.to_dict()
        assert len(d["components"]) == 1


class TestQualityAssessment:
    """Test QualityAssessment dataclass."""

    def test_pass_verdict(self):
        """Should record pass verdict."""
        qa = QualityAssessment(
            verdict="pass",
            error_count=0,
            warning_count=0,
        )
        assert qa.verdict == "pass"

    def test_triggered_rules(self):
        """Should record triggered rules."""
        rule = TriggeredRuleInfo(
            rule_id="Q010",
            severity="soft",
            message="Signal is quiet",
        )
        qa = QualityAssessment(
            verdict="warn",
            triggered_rules=[rule],
            warning_count=1,
        )
        d = qa.to_dict()
        assert d["warning_count"] == 1
        assert len(d["triggered_rules"]) == 1

    def test_crossval_fields(self):
        """Should include cross-validation results."""
        qa = QualityAssessment(
            crossval_agreement="good",
            crossval_delta_percent=3.5,
        )
        assert qa.crossval_agreement == "good"


class TestWolfToneAnalysis:
    """Test WolfToneAnalysis dataclass."""

    def test_no_wolf(self):
        """Should indicate no wolf detected."""
        wolf = WolfToneAnalysis(wolf_detected=False)
        assert wolf.wolf_detected is False
        assert wolf.worst_wolf_severity == "none"

    def test_wolf_detected(self):
        """Should capture wolf parameters."""
        wolf = WolfToneAnalysis(
            wolf_detected=True,
            worst_wolf_freq_hz=187.5,
            worst_wolf_beat_hz=3.2,
            worst_wolf_severity="moderate",
            n_wolf_pairs=2,
            recommendation="Add 2g wolf eliminator",
        )
        d = wolf.to_dict()
        assert d["wolf_detected"] is True
        assert d["worst_wolf_beat_hz"] == 3.2


class TestQALabSpecEntry:
    """Test the complete QALabSpecEntry dataclass."""

    def test_basic_entry(self):
        """Should create entry with all sections."""
        entry = QALabSpecEntry(
            sample=SampleIdentification(specimen_id="Test_001"),
            setup=SetupParameters(device_id="DEV001"),
            measurements=PrimaryMeasurements(thickness_mm=3.0),
        )
        assert entry.sample.specimen_id == "Test_001"
        assert entry.setup.device_id == "DEV001"

    def test_to_dict_structure(self):
        """to_dict should have correct structure."""
        entry = QALabSpecEntry(
            sample=SampleIdentification(specimen_id="Test_001"),
            E_static_GPa=12.5,
            SI=340.0,
        )
        d = entry.to_dict()

        assert d["schema_id"] == "qa_lab_spec_v1"
        assert "sample_identification" in d
        assert "derived_properties" in d
        assert d["derived_properties"]["E_static_GPa"] == 12.5
        assert d["derived_properties"]["stiffness_index"]["SI"] == 340.0

    def test_compute_entry_hash(self):
        """Should compute deterministic hash."""
        entry = QALabSpecEntry(
            sample=SampleIdentification(specimen_id="Test_001"),
            E_static_GPa=12.5,
        )
        hash1 = entry.compute_entry_hash()
        hash2 = entry.compute_entry_hash()

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_hash_changes_with_data(self):
        """Different data should produce different hash."""
        entry1 = QALabSpecEntry(
            sample=SampleIdentification(specimen_id="Test_001"),
            E_static_GPa=12.5,
        )
        entry2 = QALabSpecEntry(
            sample=SampleIdentification(specimen_id="Test_001"),
            E_static_GPa=12.6,  # Different E
        )
        assert entry1.compute_entry_hash() != entry2.compute_entry_hash()


class TestBuildQALabSpecEntry:
    """Test the build_qa_lab_spec_entry function."""

    def test_basic_build(self):
        """Should build entry from minimal inputs."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Sitka_001_L",
            direction="L",
            thickness_mm=3.0,
            species="Sitka Spruce",
            density_kg_m3=420.0,
        )

        assert entry.sample.specimen_id == "Sitka_001_L"
        assert entry.sample.species == "Sitka Spruce"
        assert entry.measurements.thickness_mm == 3.0
        assert entry.measurements.density_kg_m3 == 420.0

    def test_session_metadata(self):
        """Should capture session metadata."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
            run_id="RUN_20260217_001",
            session_id="SESSION_001",
            operator_id="JSmith",
            device_id="DEV003",
        )

        assert entry.sample.run_id == "RUN_20260217_001"
        assert entry.setup.operator_id == "JSmith"
        assert entry.setup.device_id == "DEV003"

    def test_environment(self):
        """Should capture environment conditions."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
            temperature_c=22.0,
            humidity_rh=45.0,
        )

        assert entry.setup.temperature_c == 22.0
        assert entry.setup.humidity_rh == 45.0

    def test_calibration_state(self):
        """Should capture calibration state."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
            is_calibrated=True,
            calibration_date="2026-01-15",
        )

        assert entry.setup.is_calibrated is True
        assert entry.setup.calibration_date == "2026-01-15"

    def test_audit_hash_populated(self):
        """Should populate audit hash."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
        )

        assert entry.audit.entry_hash_sha256 is not None
        assert len(entry.audit.entry_hash_sha256) == 64

    def test_timestamp_populated(self):
        """Should populate timestamps."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
        )

        assert entry.setup.test_timestamp_utc != ""
        assert entry.audit.export_timestamp_utc != ""

    def test_with_bending_json(self):
        """Should load bending data from JSON."""
        bending_data = {
            "E_GPa": 12.5,
            "E_euler_bernoulli_GPa": 13.2,
            "shear_correction": {
                "applied": True,
                "reduction_percent": 5.3,
            },
            "fit": {
                "r2": 0.9987,
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(bending_data, f)
            bending_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Test_001",
                thickness_mm=3.0,
                bending_json_path=bending_path,
            )

            assert entry.E_static_GPa == 12.5
            assert entry.E_uncorrected_GPa == 13.2
            assert entry.shear_correction_applied is True
            assert entry.shear_correction_percent == 5.3
            assert entry.fit_r_squared == 0.9987
            assert entry.audit.bending_data_sha256 is not None
        finally:
            Path(bending_path).unlink()

    def test_with_acoustic_json(self):
        """Should load acoustic data from JSON."""
        peaks_data = {
            "peaks_hz": [187.5, 523.1, 1025.4],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(peaks_data, f)
            peaks_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Test_001",
                thickness_mm=3.0,
                length_mm=400.0,
                density_kg_m3=420.0,
                acoustic_json_path=peaks_path,
            )

            assert entry.measurements.fundamental_freq_hz == 187.5
            assert len(entry.measurements.peak_frequencies_hz) == 3
            assert entry.E_dynamic_GPa is not None
            assert entry.audit.peaks_data_sha256 is not None
        finally:
            Path(peaks_path).unlink()

    def test_stiffness_index_computed(self):
        """Should compute SI from E and thickness."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
            density_kg_m3=420.0,
        )
        # No bending data, so no E, so no SI
        assert entry.SI is None

        # Create with bending data
        bending_data = {"E_GPa": 12.0}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(bending_data, f)
            bending_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Test_001",
                thickness_mm=3.0,
                bending_json_path=bending_path,
            )
            # SI = E × h³ = 12 × 27 = 324
            assert entry.SI == pytest.approx(324.0, rel=0.01)
        finally:
            Path(bending_path).unlink()

    def test_derived_properties(self):
        """Should compute derived properties."""
        bending_data = {"E_GPa": 12.0}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(bending_data, f)
            bending_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Test_001",
                thickness_mm=3.0,
                density_kg_m3=420.0,
                bending_json_path=bending_path,
            )

            # Wave speed = √(E/ρ) = √(12e9/420) ≈ 5345 m/s
            assert entry.wave_speed_m_s is not None
            assert 5000 < entry.wave_speed_m_s < 6000

            assert entry.specific_stiffness is not None
            assert entry.radiation_ratio is not None
        finally:
            Path(bending_path).unlink()


class TestCSVExport:
    """Test CSV export functionality."""

    def test_csv_columns_defined(self):
        """CSV columns should be defined."""
        assert len(QA_LAB_CSV_COLUMNS) > 30  # Comprehensive

    def test_export_single_entry(self):
        """Should export single entry to CSV."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            direction="L",
            thickness_mm=3.0,
            species="Sitka Spruce",
            density_kg_m3=420.0,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            csv_path = f.name

        try:
            export_qa_lab_csv([entry], csv_path)

            # Read and verify
            import csv

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["specimen_id"] == "Test_001"
            assert rows[0]["species"] == "Sitka Spruce"
            assert rows[0]["grain_direction"] == "L"
        finally:
            Path(csv_path).unlink()

    def test_export_multiple_entries(self):
        """Should export multiple entries."""
        entries = [
            build_qa_lab_spec_entry(
                specimen_id=f"Test_{i:03d}",
                thickness_mm=3.0,
            )
            for i in range(5)
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            csv_path = f.name

        try:
            export_qa_lab_csv(entries, csv_path)

            import csv

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 5
        finally:
            Path(csv_path).unlink()


class TestJSONExport:
    """Test JSON export functionality."""

    def test_export_json(self):
        """Should export to JSON format."""
        entry = build_qa_lab_spec_entry(
            specimen_id="Test_001",
            thickness_mm=3.0,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json_path = f.name

        try:
            export_qa_lab_json([entry], json_path)

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["schema_id"] == "qa_lab_spec_collection_v1"
            assert data["entry_count"] == 1
            assert len(data["entries"]) == 1
            assert data["entries"][0]["schema_id"] == "qa_lab_spec_v1"
        finally:
            Path(json_path).unlink()


class TestFullWorkflow:
    """Test complete workflow scenarios."""

    def test_sitka_spruce_dreadnought(self):
        """Full workflow for typical Sitka top."""
        # Create mock data files
        bending_data = {
            "E_GPa": 13.5,
            "E_euler_bernoulli_GPa": 14.2,
            "shear_correction": {"applied": True, "reduction_percent": 4.9},
            "fit": {"r2": 0.9992},
        }
        peaks_data = {
            "peaks_hz": [195.2, 546.8, 1078.3],
            "peaks": [
                {"frequency_hz": 195.2, "amplitude": 0.92},
                {"frequency_hz": 546.8, "amplitude": 0.65},
                {"frequency_hz": 1078.3, "amplitude": 0.41},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bending_data, f)
            bending_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(peaks_data, f)
            peaks_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Sitka_Top_001_L",
                direction="L",
                thickness_mm=3.2,
                species="Sitka Spruce",
                batch_id="BATCH_2026_001",
                density_kg_m3=430.0,
                length_mm=400.0,
                width_mm=32.0,
                bending_json_path=bending_path,
                acoustic_json_path=peaks_path,
                instrument="dreadnought",
                operator_id="JSmith",
                device_id="DEV001",
                is_calibrated=True,
                temperature_c=22.0,
                humidity_rh=45.0,
            )

            # Verify complete entry
            assert entry.sample.specimen_id == "Sitka_Top_001_L"
            assert entry.sample.batch_id == "BATCH_2026_001"
            assert entry.E_static_GPa == 13.5
            assert entry.E_dynamic_GPa is not None
            assert entry.SI is not None
            assert 400 < entry.SI < 500  # Dreadnought range
            # instrument_type matches the preset lookup string
            assert "dreadnought" in entry.instrument_type.lower()
            assert entry.preset_match_status in ["low", "good", "high"]
            assert entry.wave_speed_m_s is not None
            assert entry.audit.entry_hash_sha256 is not None

            # JSON export should work
            d = entry.to_dict()
            json_str = json.dumps(d)  # Should not raise
            assert len(json_str) > 100
        finally:
            Path(bending_path).unlink()
            Path(peaks_path).unlink()

    def test_cedar_classical(self):
        """Full workflow for cedar classical top."""
        bending_data = {"E_GPa": 9.8}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bending_data, f)
            bending_path = f.name

        try:
            entry = build_qa_lab_spec_entry(
                specimen_id="Cedar_Top_001_L",
                direction="L",
                thickness_mm=2.8,
                species="Western Red Cedar",
                density_kg_m3=380.0,
                bending_json_path=bending_path,
                instrument="classical",
            )

            assert entry.E_static_GPa == 9.8
            # SI = 9.8 × 2.8³ = 9.8 × 21.95 = 215
            assert 200 < entry.SI < 250
        finally:
            Path(bending_path).unlink()

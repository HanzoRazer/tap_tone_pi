#!/usr/bin/env python3
"""
Tests for Gore-style build spreadsheet integration.
"""

import json

import pytest

from tap_tone_pi.bending.gore_spreadsheet import (
    dynamic_modulus_from_frequency,
    frequency_from_modulus,
    cross_validate_modulus,
    build_spreadsheet_entry,
    generate_spreadsheet,
    export_csv,
    BuildSpreadsheetEntry,
)


class TestDynamicModulusCalculations:
    """Test dynamic E from tap tone frequency."""

    def test_dynamic_modulus_basic(self):
        """Dynamic E calculation should produce reasonable values."""
        # For E=12 GPa, ρ=420 kg/m³, L=300 mm, h=3 mm, expected f≈183 Hz
        # Using consistent values: f=183 Hz should give E≈12 GPa
        E = dynamic_modulus_from_frequency(
            freq_hz=183.0,
            density_kg_m3=420.0,
            length_mm=300.0,
            thickness_mm=3.0,
        )
        # Should be in range 10-14 GPa for spruce (allowing computation tolerance)
        assert 10.0 < E < 14.0, f"E_dynamic = {E:.2f} GPa is out of range"

    def test_frequency_from_modulus_inverts(self):
        """frequency_from_modulus should be inverse of dynamic_modulus_from_frequency."""
        E_input = 12.0
        density = 420.0
        length = 300.0
        thickness = 3.0

        # Compute frequency from E
        freq = frequency_from_modulus(E_input, density, length, thickness)

        # Compute E back from frequency
        E_back = dynamic_modulus_from_frequency(freq, density, length, thickness)

        assert E_back == pytest.approx(E_input, rel=1e-4)

    def test_dynamic_modulus_mode_2(self):
        """Mode 2 should give higher frequency → same E."""
        # Using f₂ = f₁ × (λ₂/λ₁)² relationship
        density = 420.0
        length = 300.0
        thickness = 3.0
        E_actual = 12.0

        # Compute mode 1 and mode 2 frequencies
        f1 = frequency_from_modulus(E_actual, density, length, thickness, mode_number=1)
        f2 = frequency_from_modulus(E_actual, density, length, thickness, mode_number=2)

        # f₂/f₁ ≈ (λ₂/λ₁)² ≈ (7.853/4.730)² ≈ 2.76
        ratio = f2 / f1
        expected_ratio = (7.853 / 4.730) ** 2
        assert ratio == pytest.approx(expected_ratio, rel=0.01)

    def test_dynamic_modulus_cantilever(self):
        """Cantilever mode should use different λ."""
        E_ff = dynamic_modulus_from_frequency(
            300.0, 420.0, 300.0, 3.0, boundary="free-free"
        )
        E_cant = dynamic_modulus_from_frequency(
            300.0, 420.0, 300.0, 3.0, boundary="cantilever"
        )
        # Cantilever λ₁ ≈ 1.875 << free-free λ₁ ≈ 4.730
        # So for same frequency, cantilever implies MUCH higher E
        assert E_cant > E_ff * 5

    def test_dynamic_modulus_scaling(self):
        """Verify scaling relationships."""
        # E ∝ f², so doubling f should quadruple E
        E1 = dynamic_modulus_from_frequency(200.0, 420.0, 300.0, 3.0)
        E2 = dynamic_modulus_from_frequency(400.0, 420.0, 300.0, 3.0)
        assert E2 == pytest.approx(E1 * 4, rel=1e-3)

        # E ∝ L⁴, so halving L should divide E by 16 (shorter beam = same f needs softer material)
        E3 = dynamic_modulus_from_frequency(200.0, 420.0, 150.0, 3.0)
        assert E3 == pytest.approx(E1 / 16, rel=1e-3)


class TestCrossValidation:
    """Test static vs dynamic E cross-validation."""

    def test_crossval_good_agreement(self):
        """Good agreement when static ≈ dynamic."""
        result = cross_validate_modulus(
            E_static_GPa=12.0,
            E_dynamic_GPa=12.3,  # 2.5% diff
        )
        assert result.agreement == "good"
        assert result.delta_percent == pytest.approx(2.5, rel=0.1)

    def test_crossval_marginal_agreement(self):
        """Marginal agreement at threshold boundary."""
        result = cross_validate_modulus(
            E_static_GPa=12.0,
            E_dynamic_GPa=12.9,  # 7.5% diff
            threshold_percent=10.0,
        )
        assert result.agreement == "marginal"

    def test_crossval_poor_agreement(self):
        """Poor agreement when divergence exceeds threshold."""
        result = cross_validate_modulus(
            E_static_GPa=12.0,
            E_dynamic_GPa=14.0,  # 16.7% diff
            threshold_percent=10.0,
        )
        assert result.agreement == "poor"
        assert len(result.warnings) > 0
        assert any("exceeds" in w.lower() for w in result.warnings)

    def test_crossval_no_acoustic(self):
        """No acoustic data should report no_acoustic."""
        result = cross_validate_modulus(E_static_GPa=12.0)
        assert result.agreement == "no_acoustic"
        assert result.E_dynamic_GPa is None

    def test_crossval_from_frequency(self):
        """Should compute E_dynamic from frequency when needed."""
        result = cross_validate_modulus(
            E_static_GPa=12.0,
            measured_freq_hz=300.0,
            density_kg_m3=420.0,
            length_mm=300.0,
            thickness_mm=3.0,
        )
        assert result.E_dynamic_GPa is not None
        assert result.agreement != "no_acoustic"

    def test_crossval_predicts_frequency(self):
        """Should predict frequency from E_static when geometry available."""
        result = cross_validate_modulus(
            E_static_GPa=12.0,
            density_kg_m3=420.0,
            length_mm=300.0,
            thickness_mm=3.0,
        )
        assert result.predicted_freq_hz is not None
        assert result.predicted_freq_hz > 0

    def test_crossval_warning_dynamic_much_higher(self):
        """Warning when E_dynamic >> E_static."""
        result = cross_validate_modulus(
            E_static_GPa=10.0,
            E_dynamic_GPa=15.0,  # 50% higher
        )
        assert any("E_dynamic >> E_static" in w for w in result.warnings)

    def test_crossval_warning_static_much_higher(self):
        """Warning when E_static >> E_dynamic."""
        result = cross_validate_modulus(
            E_static_GPa=15.0,
            E_dynamic_GPa=10.0,  # 33% lower
        )
        assert any("E_static >> E_dynamic" in w for w in result.warnings)


class TestBuildSpreadsheetEntry:
    """Test spreadsheet entry building."""

    @pytest.fixture
    def sample_bending_json(self, tmp_path):
        """Create sample bending_moe.json."""
        data = {
            "artifact_type": "bending_moe",
            "E_GPa": 12.5,
            "E_euler_bernoulli_GPa": 13.2,
            "shear_correction": {
                "applied": True,
                "factor": 1.056,
                "reduction_percent": 5.3,
            },
            "fit": {"r2": 0.9987, "warning": None},
        }
        path = tmp_path / "bending_moe.json"
        path.write_text(json.dumps(data))
        return str(path)

    @pytest.fixture
    def sample_acoustic_json(self, tmp_path):
        """Create sample peaks.json."""
        data = {"peaks_hz": [287.5, 575.0, 862.5]}
        path = tmp_path / "peaks.json"
        path.write_text(json.dumps(data))
        return str(path)

    def test_build_entry_basic(self):
        """Basic entry without data files."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
        )
        assert entry.specimen_id == "Test_001_L"
        assert entry.direction == "L"
        assert entry.thickness_mm == 3.0
        assert entry.timestamp_utc is not None

    def test_build_entry_with_bending(self, sample_bending_json):
        """Entry with bending data should populate E_static."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
            bending_json_path=sample_bending_json,
        )
        assert entry.E_static_GPa == pytest.approx(12.5, rel=1e-3)
        assert entry.shear_correction_applied is True
        assert entry.shear_correction_percent == pytest.approx(5.3, rel=0.1)

    def test_build_entry_with_acoustic(self, sample_acoustic_json):
        """Entry with acoustic data should populate frequency."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
            acoustic_json_path=sample_acoustic_json,
        )
        assert entry.fundamental_freq_hz == pytest.approx(287.5, rel=1e-3)

    def test_build_entry_full(self, sample_bending_json, sample_acoustic_json):
        """Full entry should include cross-validation."""
        entry = build_spreadsheet_entry(
            specimen_id="Sitka_001_L",
            direction="L",
            thickness_mm=3.0,
            bending_json_path=sample_bending_json,
            acoustic_json_path=sample_acoustic_json,
            density_kg_m3=420.0,
            length_mm=300.0,
            instrument="dreadnought",
        )
        assert entry.E_static_GPa is not None
        assert entry.E_dynamic_GPa is not None
        assert entry.crossval_agreement is not None
        assert entry.SI is not None
        assert entry.instrument_type == "dreadnought"

    def test_build_entry_provenance(self, sample_bending_json):
        """Entry should include provenance information."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
            bending_json_path=sample_bending_json,
        )
        assert "bending_json_path" in entry.provenance
        assert "bending_json_sha256" in entry.provenance
        assert len(entry.provenance["bending_json_sha256"]) == 64  # SHA-256 hex


class TestBuildSpreadsheet:
    """Test spreadsheet generation."""

    def test_generate_spreadsheet_single_entry(self):
        """Spreadsheet with single entry."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
        )
        sheet = generate_spreadsheet([entry])
        assert sheet.schema_id == "gore_build_spreadsheet"
        assert len(sheet.entries) == 1
        assert sheet.created_utc is not None

    def test_generate_spreadsheet_orthotropic_summary(self):
        """Spreadsheet with L and C entries should include orthotropic summary."""
        entry_L = BuildSpreadsheetEntry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
            timestamp_utc="2026-02-17T12:00:00Z",
            E_static_GPa=12.0,
        )
        entry_L.SI = 324.0

        entry_C = BuildSpreadsheetEntry(
            specimen_id="Test_001_C",
            direction="C",
            thickness_mm=3.0,
            timestamp_utc="2026-02-17T12:00:00Z",
            E_static_GPa=0.8,
        )
        entry_C.SI = 21.6

        sheet = generate_spreadsheet([entry_L, entry_C])
        assert sheet.orthotropic_summary is not None
        assert sheet.orthotropic_summary["E_ratio_L_C"] == pytest.approx(15.0, rel=1e-2)

    def test_spreadsheet_to_dict(self):
        """Spreadsheet should serialize correctly."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
        )
        sheet = generate_spreadsheet([entry])
        d = sheet.to_dict()
        assert "schema_id" in d
        assert "entries" in d
        assert len(d["entries"]) == 1


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_csv_creates_file(self, tmp_path):
        """CSV export should create file."""
        entry = build_spreadsheet_entry(
            specimen_id="Test_001_L",
            direction="L",
            thickness_mm=3.0,
        )
        sheet = generate_spreadsheet([entry])
        csv_path = tmp_path / "output.csv"
        export_csv(sheet, str(csv_path))
        assert csv_path.exists()

    def test_export_csv_content(self, tmp_path):
        """CSV should contain expected columns and data."""
        entry = build_spreadsheet_entry(
            specimen_id="Sitka_001_L",
            direction="L",
            thickness_mm=3.5,
        )
        sheet = generate_spreadsheet([entry])
        csv_path = tmp_path / "output.csv"
        export_csv(sheet, str(csv_path))

        content = csv_path.read_text()
        lines = content.strip().split("\n")

        # Check header
        header = lines[0]
        assert "specimen_id" in header
        assert "thickness_mm" in header
        assert "SI" in header

        # Check data row
        data = lines[1]
        assert "Sitka_001_L" in data
        assert "3.5" in data

    def test_export_csv_multiple_entries(self, tmp_path):
        """CSV with multiple entries."""
        entries = [
            build_spreadsheet_entry(f"Test_{i:03d}_L", "L", 3.0 + i * 0.1)
            for i in range(3)
        ]
        sheet = generate_spreadsheet(entries)
        csv_path = tmp_path / "output.csv"
        export_csv(sheet, str(csv_path))

        content = csv_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 4  # Header + 3 rows


class TestPhysicalRealism:
    """Test physical realism of integrated calculations."""

    def test_sitka_spruce_full_workflow(self, tmp_path):
        """Full workflow with realistic Sitka spruce values."""
        # Create realistic bending data
        bending = {
            "E_GPa": 12.5,
            "E_euler_bernoulli_GPa": 13.2,
            "shear_correction": {"applied": True, "reduction_percent": 5.3},
            "fit": {"r2": 0.998},
        }
        bending_path = tmp_path / "bending_moe.json"
        bending_path.write_text(json.dumps(bending))

        # Create realistic acoustic data
        # For E=12.5 GPa, ρ=420, L=300mm, h=3mm, fundamental f≈187 Hz
        acoustic = {"peaks_hz": [187.0, 374.0, 561.0]}
        acoustic_path = tmp_path / "peaks.json"
        acoustic_path.write_text(json.dumps(acoustic))

        entry = build_spreadsheet_entry(
            specimen_id="Sitka_001_L",
            direction="L",
            thickness_mm=3.0,
            bending_json_path=str(bending_path),
            acoustic_json_path=str(acoustic_path),
            density_kg_m3=420.0,
            length_mm=300.0,
            width_mm=25.0,
            species="Sitka Spruce",
            instrument="dreadnought",
        )

        # Verify physical realism
        assert 10.0 < entry.E_static_GPa < 16.0, "E_static out of range for spruce"
        assert 10.0 < entry.E_dynamic_GPa < 16.0, "E_dynamic out of range for spruce"
        assert 300 < entry.SI < 400, "SI out of range for typical spruce"
        assert 5000 < entry.wave_speed_m_s < 6000, "Wave speed out of range"
        # Cross-validation should show good agreement since we used consistent values
        assert entry.crossval_agreement in ["good", "marginal"], (
            "Cross-validation should pass"
        )

    def test_cedar_classical_workflow(self, tmp_path):
        """Full workflow with realistic cedar values."""
        # Create realistic bending data (cedar is softer)
        bending = {
            "E_GPa": 8.5,
            "shear_correction": {"applied": True, "reduction_percent": 6.0},
            "fit": {"r2": 0.995},
        }
        bending_path = tmp_path / "bending_moe.json"
        bending_path.write_text(json.dumps(bending))

        # For cedar (E≈8.5 GPa) to reach classical SI range (280-380):
        # h = (SI/E)^(1/3) = (320/8.5)^(1/3) ≈ 3.35 mm
        entry = build_spreadsheet_entry(
            specimen_id="Cedar_001_L",
            direction="L",
            thickness_mm=3.4,  # Thicker to compensate for lower E
            bending_json_path=str(bending_path),
            density_kg_m3=380.0,
            species="Western Red Cedar",
            instrument="classical",
        )

        # Cedar should be in classical range
        assert 7.0 < entry.E_static_GPa < 11.0, "E out of range for cedar"
        # SI = 8.5 × 3.4³ = 8.5 × 39.3 = 334 GPa·mm³ (in range 280-380)
        assert entry.preset_match_status == "good", (
            f"Cedar SI={entry.SI:.0f} should be in range"
        )

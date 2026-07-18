"""
Tests for tap_tone_pi.export.bending module.
"""

import json
import pytest

from tap_tone_pi.export.bending import (
    BendingData,
    load_bending_data,
    load_bending_pair,
    add_bending_to_manifest,
    validate_bending_section,
)


@pytest.fixture
def sample_moe_data():
    """Sample bending_moe.json data."""
    return {
        "E_GPa": 10.5,
        "specific_modulus_GPa_per_gcm3": 26.25,
        "c_m_s": 5123.0,
        "density_g_cm3": 0.40,
        "span_mm": 400,
        "method": "3point",
    }


@pytest.fixture
def bending_session(tmp_path, sample_moe_data):
    """Create a bending session directory with moe data."""
    session_dir = tmp_path / "bending_session"
    session_dir.mkdir()

    moe_file = session_dir / "bending_moe.json"
    with open(moe_file, "w") as f:
        json.dump(sample_moe_data, f)

    return session_dir


class TestBendingData:
    """Tests for BendingData dataclass."""

    def test_from_moe_json(self, sample_moe_data):
        """Should construct from bending_moe.json format."""
        data = BendingData.from_moe_json(sample_moe_data)

        assert data.E_L_GPa == 10.5
        assert data.specific_modulus_GPa_per_gcm3 == 26.25
        assert data.c_m_s == 5123.0
        assert data.density_g_cm3 == 0.40
        assert data.span_mm == 400
        assert data.method == "3point"

    def test_orthotropic_ratio(self):
        """orthotropic_ratio should compute E_L/E_C."""
        data = BendingData(E_L_GPa=10.0, E_C_GPa=0.8)

        assert data.orthotropic_ratio == pytest.approx(12.5)

    def test_orthotropic_ratio_none_without_E_C(self):
        """orthotropic_ratio should be None if E_C not set."""
        data = BendingData(E_L_GPa=10.0)

        assert data.orthotropic_ratio is None

    def test_to_manifest_dict(self, sample_moe_data):
        """Should convert to manifest dict format."""
        data = BendingData.from_moe_json(sample_moe_data)
        manifest = data.to_manifest_dict()

        assert "E_L_GPa" in manifest
        assert manifest["E_L_GPa"] == 10.5
        assert manifest["span_mm"] == 400
        assert manifest["method"] == "3point"

    def test_to_manifest_dict_rounds_values(self):
        """Values should be rounded appropriately."""
        data = BendingData(
            E_L_GPa=10.123456789,
            c_m_s=5123.456789,
        )
        manifest = data.to_manifest_dict()

        assert manifest["E_L_GPa"] == 10.123  # 3 decimal places
        assert manifest["c_m_s"] == 5123.5  # 1 decimal place

    def test_to_manifest_dict_excludes_none(self):
        """None values should be excluded from manifest."""
        data = BendingData(E_L_GPa=10.0)  # No E_C
        manifest = data.to_manifest_dict()

        assert "E_C_GPa" not in manifest

    def test_to_manifest_dict_includes_orthotropic_ratio(self):
        """Should include computed orthotropic_ratio."""
        data = BendingData(E_L_GPa=10.0, E_C_GPa=0.8)
        manifest = data.to_manifest_dict()

        assert "orthotropic_ratio" in manifest
        assert manifest["orthotropic_ratio"] == 12.5


class TestLoadBendingData:
    """Tests for load_bending_data function."""

    def test_load_from_directory(self, bending_session):
        """Should load bending data from session directory."""
        data = load_bending_data(bending_session)

        assert data.E_L_GPa == 10.5
        assert data.span_mm == 400

    def test_load_sets_source_bundle(self, bending_session):
        """Should set source_bundle with provenance info."""
        data = load_bending_data(bending_session)

        assert data.source_bundle is not None
        assert "bending_moe.json" in data.source_bundle

    def test_load_nonexistent_raises(self, tmp_path):
        """Should raise FileNotFoundError for missing directory."""
        with pytest.raises(FileNotFoundError):
            load_bending_data(tmp_path / "nonexistent")

    def test_load_no_moe_file_raises(self, tmp_path):
        """Should raise FileNotFoundError for missing moe file."""
        empty_dir = tmp_path / "empty_session"
        empty_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            load_bending_data(empty_dir)


class TestLoadBendingPair:
    """Tests for load_bending_pair function."""

    def test_load_pair(self, tmp_path):
        """Should combine along-grain and cross-grain data."""
        # Along-grain session
        along_dir = tmp_path / "along_grain"
        along_dir.mkdir()
        with open(along_dir / "bending_moe.json", "w") as f:
            json.dump({"E_GPa": 10.5, "span_mm": 400, "method": "3point"}, f)

        # Cross-grain session
        cross_dir = tmp_path / "cross_grain"
        cross_dir.mkdir()
        with open(cross_dir / "bending_moe.json", "w") as f:
            json.dump({"E_GPa": 0.8, "span_mm": 200, "method": "3point"}, f)

        data = load_bending_pair(along_dir, cross_dir)

        assert data.E_L_GPa == 10.5
        assert data.E_C_GPa == 0.8
        assert data.orthotropic_ratio == pytest.approx(13.125)

    def test_load_pair_without_cross(self, bending_session):
        """Should work with only along-grain data."""
        data = load_bending_pair(bending_session, None)

        assert data.E_L_GPa == 10.5
        assert data.E_C_GPa is None


class TestAddBendingToManifest:
    """Tests for add_bending_to_manifest function."""

    def test_add_bending_section(self, bending_session):
        """Should add bending section to manifest."""
        manifest = {
            "schema_version": "v1",
            "contents": {"audio": True, "spectra": True},
        }

        result = add_bending_to_manifest(manifest, bending_dir=bending_session)

        assert "bending" in result
        assert result["bending"]["E_L_GPa"] == 10.5

    def test_updates_contents_flag(self, bending_session):
        """Should set contents.bending = True."""
        manifest = {
            "schema_version": "v1",
            "contents": {"audio": True},
        }

        result = add_bending_to_manifest(manifest, bending_dir=bending_session)

        assert result["contents"]["bending"] is True

    def test_accepts_bending_data_directly(self):
        """Should accept pre-loaded BendingData."""
        manifest = {"contents": {}}
        bending = BendingData(E_L_GPa=11.0, E_C_GPa=0.9)

        result = add_bending_to_manifest(manifest, bending_data=bending)

        assert result["bending"]["E_L_GPa"] == 11.0
        assert result["bending"]["E_C_GPa"] == 0.9

    def test_raises_without_data(self):
        """Should raise ValueError if no data provided."""
        manifest = {}

        with pytest.raises(ValueError):
            add_bending_to_manifest(manifest)


class TestValidateBendingSection:
    """Tests for validate_bending_section function."""

    def test_valid_section(self):
        """Valid bending section should pass."""
        section = {
            "E_L_GPa": 10.5,
            "E_C_GPa": 0.8,
            "span_mm": 400,
            "method": "3point",
        }

        is_valid, errors = validate_bending_section(section)

        assert is_valid
        assert len(errors) == 0

    def test_missing_E_L(self):
        """Missing E_L_GPa should fail."""
        section = {"span_mm": 400, "method": "3point"}

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("E_L_GPa" in e for e in errors)

    def test_E_L_out_of_range(self):
        """E_L outside valid range should fail."""
        section = {"E_L_GPa": 100.0}  # Too high

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("out of valid range" in e for e in errors)

    def test_E_C_out_of_range(self):
        """E_C outside valid range should fail."""
        section = {"E_L_GPa": 10.0, "E_C_GPa": 15.0}  # Too high

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("E_C_GPa" in e for e in errors)

    def test_invalid_method(self):
        """Invalid method should fail."""
        section = {"E_L_GPa": 10.0, "method": "5point"}

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("method" in e for e in errors)

    def test_orthotropic_ratio_too_low(self):
        """Orthotropic ratio < 1 should fail."""
        section = {"E_L_GPa": 5.0, "orthotropic_ratio": 0.5}

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("orthotropic_ratio" in e for e in errors)

    def test_orthotropic_ratio_too_high(self):
        """Orthotropic ratio > 50 should fail."""
        section = {"E_L_GPa": 10.0, "orthotropic_ratio": 60}

        is_valid, errors = validate_bending_section(section)

        assert not is_valid
        assert any("implausibly high" in e for e in errors)


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, bending_session):
        """Test complete workflow from load to manifest."""
        # Load bending data
        bending = load_bending_data(bending_session)

        # Add to manifest
        manifest = {
            "schema_version": "v1",
            "schema_id": "viewer_pack_v1",
            "contents": {"audio": True, "spectra": True, "coherence": False},
        }

        add_bending_to_manifest(manifest, bending_data=bending)

        # Validate bending section
        is_valid, errors = validate_bending_section(manifest["bending"])

        assert is_valid, f"Validation failed: {errors}"
        assert manifest["contents"]["bending"] is True

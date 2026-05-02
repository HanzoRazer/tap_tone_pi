"""
Tests for wood_flitch_record_v1 JSON schema validation.

DO-003 Stage A acceptance tests:
- Schema loads as valid JSON Schema
- Valid example passes validation
- Missing required field fails validation
- Bad species_id pattern fails validation
- Bad flitch_id pattern fails validation
- Empty measurements array is allowed
- All optional measurement fields can be null
"""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "wood_flitch_record_v1.schema.json"


@pytest.fixture
def schema():
    """Load the wood flitch record schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def valid_flitch():
    """A minimal valid flitch record."""
    return {
        "schema_version": "wood_flitch_record_v1",
        "flitch_id": "SITKA_2026_PACIFIC_001",
        "species_id": "spruce_sitka",
        "created_at_utc": "2026-05-02T12:00:00Z",
        "measurements": [],
    }


@pytest.fixture
def valid_measurement():
    """A minimal valid measurement."""
    return {
        "measurement_id": "M_20260502T120000Z",
        "measured_at_utc": "2026-05-02T12:00:00Z",
        "thickness_mm_mean": 3.2,
        "mass_g": 145.0,
        "density_kg_m3": 420.0,
    }


class TestSchemaLoads:
    """Schema file is valid JSON Schema."""

    def test_schema_is_valid_json(self, schema):
        """Schema loads without error."""
        assert "$schema" in schema
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_has_required_structure(self, schema):
        """Schema has expected top-level keys."""
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "$defs" in schema
        assert "PlateMeasurement" in schema["$defs"]


class TestValidRecords:
    """Valid records pass validation."""

    def test_minimal_flitch_passes(self, schema, valid_flitch):
        """Minimal valid flitch with empty measurements passes."""
        jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_flitch_with_measurement_passes(self, schema, valid_flitch, valid_measurement):
        """Flitch with one measurement passes."""
        valid_flitch["measurements"] = [valid_measurement]
        jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_full_measurement_passes(self, schema, valid_flitch):
        """Measurement with all optional fields passes."""
        full_measurement = {
            "measurement_id": "M_FULL_001",
            "measured_at_utc": "2026-05-02T14:30:00Z",
            "plate_subid": "TOP_HALF_A",
            "rh_at_measurement_pct": 45.0,
            "tempC_at_measurement": 22.5,
            "thickness_mm_grid": [[3.1, 3.2], [3.0, 3.1]],
            "thickness_mm_mean": 3.1,
            "thickness_mm_std": 0.08,
            "length_mm": 520.0,
            "width_mm": 210.0,
            "mass_g": 150.0,
            "density_kg_m3": 415.0,
            "E_L_GPa": 12.5,
            "E_L_uncertainty_GPa": 0.3,
            "E_L_expanded_uncertainty_GPa": 0.6,
            "E_C_GPa": 0.9,
            "E_C_uncertainty_GPa": 0.05,
            "E_C_expanded_uncertainty_GPa": 0.1,
            "coverage_factor": 2.0,
            "degrees_of_freedom": 8,
            "modal_freqs_hz": {"(1,1)": 85.2, "(2,1)": 152.0},
            "Q_factors": {"(1,1)": 45.0, "(2,1)": 38.0},
            "session_path": "runs_phase2/session_20260502/",
            "notes": "First measurement after kiln drying",
        }
        valid_flitch["measurements"] = [full_measurement]
        jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_all_optional_flitch_fields(self, schema, valid_flitch):
        """Flitch with all optional fields passes."""
        valid_flitch["species_id_freetext_original"] = "Sitka Spruce"
        valid_flitch["supplier"] = "Pacific Rim Tonewoods"
        valid_flitch["purchase_lot"] = "LOT-2026-Q1"
        valid_flitch["purchase_date"] = "2026-01-15"
        valid_flitch["estimated_age_years"] = 80
        valid_flitch["moisture_content_pct_at_purchase"] = 12.5
        valid_flitch["notes"] = "Excellent grain, AAA grade"
        jsonschema.validate(instance=valid_flitch, schema=schema)


class TestMissingRequired:
    """Missing required fields fail validation."""

    def test_missing_schema_version(self, schema, valid_flitch):
        """Missing schema_version fails."""
        del valid_flitch["schema_version"]
        with pytest.raises(jsonschema.ValidationError, match="schema_version"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_missing_flitch_id(self, schema, valid_flitch):
        """Missing flitch_id fails."""
        del valid_flitch["flitch_id"]
        with pytest.raises(jsonschema.ValidationError, match="flitch_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_missing_species_id(self, schema, valid_flitch):
        """Missing species_id fails."""
        del valid_flitch["species_id"]
        with pytest.raises(jsonschema.ValidationError, match="species_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_missing_measurements(self, schema, valid_flitch):
        """Missing measurements array fails."""
        del valid_flitch["measurements"]
        with pytest.raises(jsonschema.ValidationError, match="measurements"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_missing_measurement_required(self, schema, valid_flitch):
        """Measurement missing required field fails."""
        bad_measurement = {
            "measurement_id": "M_001",
            "measured_at_utc": "2026-05-02T12:00:00Z",
            # missing thickness_mm_mean, mass_g, density_kg_m3
        }
        valid_flitch["measurements"] = [bad_measurement]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=valid_flitch, schema=schema)


class TestPatternValidation:
    """ID patterns are enforced."""

    def test_invalid_flitch_id_lowercase(self, schema, valid_flitch):
        """flitch_id must start with uppercase."""
        valid_flitch["flitch_id"] = "sitka_2026_001"  # lowercase
        with pytest.raises(jsonschema.ValidationError, match="flitch_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_invalid_flitch_id_too_short(self, schema, valid_flitch):
        """flitch_id must be at least 3 chars."""
        valid_flitch["flitch_id"] = "AB"
        with pytest.raises(jsonschema.ValidationError, match="flitch_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_invalid_species_id_uppercase(self, schema, valid_flitch):
        """species_id must be lowercase."""
        valid_flitch["species_id"] = "SPRUCE_SITKA"  # uppercase
        with pytest.raises(jsonschema.ValidationError, match="species_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_invalid_species_id_spaces(self, schema, valid_flitch):
        """species_id cannot have spaces."""
        valid_flitch["species_id"] = "spruce sitka"
        with pytest.raises(jsonschema.ValidationError, match="species_id"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_invalid_measurement_id(self, schema, valid_flitch, valid_measurement):
        """measurement_id must match pattern."""
        valid_measurement["measurement_id"] = "m_001"  # lowercase start
        valid_flitch["measurements"] = [valid_measurement]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=valid_flitch, schema=schema)


class TestNullableFields:
    """Optional fields can be null."""

    def test_nullable_optional_fields(self, schema, valid_flitch, valid_measurement):
        """All nullable measurement fields can be explicit null."""
        valid_measurement["plate_subid"] = None
        valid_measurement["rh_at_measurement_pct"] = None
        valid_measurement["tempC_at_measurement"] = None
        valid_measurement["thickness_mm_grid"] = None
        valid_measurement["thickness_mm_std"] = None
        valid_measurement["length_mm"] = None
        valid_measurement["width_mm"] = None
        valid_measurement["E_L_GPa"] = None
        valid_measurement["E_L_uncertainty_GPa"] = None
        valid_measurement["E_C_GPa"] = None
        valid_measurement["modal_freqs_hz"] = None
        valid_measurement["Q_factors"] = None
        valid_measurement["session_path"] = None
        valid_measurement["degrees_of_freedom"] = None
        valid_flitch["measurements"] = [valid_measurement]
        jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_nullable_flitch_fields(self, schema, valid_flitch):
        """Nullable flitch fields can be null."""
        valid_flitch["species_id_freetext_original"] = None
        valid_flitch["supplier"] = None
        valid_flitch["purchase_lot"] = None
        valid_flitch["purchase_date"] = None
        valid_flitch["estimated_age_years"] = None
        valid_flitch["moisture_content_pct_at_purchase"] = None
        jsonschema.validate(instance=valid_flitch, schema=schema)


class TestAdditionalProperties:
    """additionalProperties: false is enforced."""

    def test_extra_flitch_field_rejected(self, schema, valid_flitch):
        """Unknown field at flitch level fails."""
        valid_flitch["unknown_field"] = "should fail"
        with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

    def test_extra_measurement_field_rejected(self, schema, valid_flitch, valid_measurement):
        """Unknown field at measurement level fails."""
        valid_measurement["unknown_field"] = "should fail"
        valid_flitch["measurements"] = [valid_measurement]
        with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
            jsonschema.validate(instance=valid_flitch, schema=schema)

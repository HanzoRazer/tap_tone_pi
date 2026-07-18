"""
Tests for instrument_build_record_v1 JSON schema validation.

DO-004 Stage A acceptance tests:
- Schema loads as valid JSON Schema
- Valid example passes validation
- Missing required field fails validation
- Bad build_id pattern fails validation
- Empty optional sections allowed
- All nested definitions validate correctly
- Player evaluation structure validates
"""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = (
    Path(__file__).parent.parent
    / "contracts"
    / "instrument_build_record_v1.schema.json"
)


@pytest.fixture
def schema():
    """Load the instrument build record schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def valid_build():
    """A minimal valid build record."""
    return {
        "schema_version": "instrument_build_record_v1",
        "build_id": "CARLOS_JUMBO_001",
        "design_name": "Carlos Jumbo",
        "build_started": "2026-05-01",
        "created_at_utc": "2026-05-01T10:00:00Z",
        "wood": {},
    }


@pytest.fixture
def full_wood_selection():
    """Complete wood selection with all flitch references."""
    return {
        "top_flitch_id": "SITKA_2026_PACIFIC_001",
        "top_subid": "A",
        "back_flitch_id": "ROSEWOOD_2026_LUTHIER_003",
        "back_subid": "bookmatched_pair",
        "sides_flitch_id": "ROSEWOOD_2026_LUTHIER_003",
        "sides_subid": "sides_A",
        "neck_flitch_id": "MAHOGANY_2026_VENDOR_001",
        "neck_subid": None,
        "brace_stock_flitch_id": "SPRUCE_ADIRONDACK_2026_001",
        "brace_stock_subid": None,
        "fretboard_flitch_id": "EBONY_2026_001",
        "fretboard_subid": None,
        "bridge_flitch_id": "ROSEWOOD_2026_LUTHIER_003",
        "bridge_subid": "bridge_blank",
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
        assert "WoodSelection" in schema["$defs"]
        assert "AsBuiltDimensions" in schema["$defs"]
        assert "MeasurementPaths" in schema["$defs"]
        assert "PredictedValues" in schema["$defs"]
        assert "Residuals" in schema["$defs"]
        assert "PlayerEvaluation" in schema["$defs"]


class TestValidRecords:
    """Valid records pass validation."""

    def test_minimal_build_passes(self, schema, valid_build):
        """Minimal valid build with empty wood section passes."""
        jsonschema.validate(instance=valid_build, schema=schema)

    def test_build_with_wood_selection(self, schema, valid_build, full_wood_selection):
        """Build with complete wood selection passes."""
        valid_build["wood"] = full_wood_selection
        jsonschema.validate(instance=valid_build, schema=schema)

    def test_build_with_all_sections(self, schema, valid_build):
        """Build with all optional sections passes."""
        valid_build["build_completed"] = "2026-06-15"
        valid_build["design_blueprint_path"] = "designs/carlos_jumbo_v1.pdf"
        valid_build["as_built_dimensions"] = {
            "top_thickness_grid_mm": [[2.8, 2.9], [2.9, 3.0]],
            "soundhole_diameter_mm": 102.0,
            "scale_length_mm": 650.0,
        }
        valid_build["measurements"] = {
            "modal_scans": ["runs_phase2/session_001/ods_snapshot.json"],
            "tap_tone_measurements": ["tap_sessions/build_001_top.json"],
        }
        valid_build["predicted"] = {
            "T1_hz": 95.0,
            "A0_hz": 100.0,
            "bridge_deflection_mm_at_string_load": 0.8,
        }
        valid_build["measured_summary"] = {
            "T1_hz": 92.0,
            "A0_hz": 98.0,
            "bridge_deflection_mm": 0.75,
        }
        valid_build["residuals"] = {
            "T1_residual_hz": -3.0,
            "T1_residual_pct": -3.16,
            "A0_residual_hz": -2.0,
            "A0_residual_pct": -2.0,
        }
        valid_build["subjective"] = {
            "builder_notes": "Excellent response, quick break-in expected.",
            "player_evaluations": [
                {
                    "player_id": "Ross",
                    "date": "2026-06-20",
                    "engagement_minutes": 45,
                    "tone_rating": 8,
                    "playability_rating": 9,
                    "notes": "Great projection, warm bass, clear trebles.",
                }
            ],
        }
        valid_build["notes"] = "First Carlos Jumbo build."
        jsonschema.validate(instance=valid_build, schema=schema)

    def test_brace_dimensions(self, schema, valid_build):
        """Build with brace dimension array passes."""
        valid_build["as_built_dimensions"] = {
            "brace_dimensions": [
                {
                    "name": "X_bass",
                    "height_mm": 8.0,
                    "width_mm": 6.0,
                    "length_mm": 240.0,
                    "scallop_depth_mm": 2.0,
                    "taper_type": "parabolic",
                },
                {
                    "name": "X_treble",
                    "height_mm": 7.5,
                    "width_mm": 6.0,
                    "length_mm": 235.0,
                },
            ],
        }
        jsonschema.validate(instance=valid_build, schema=schema)


class TestMissingRequired:
    """Missing required fields fail validation."""

    def test_missing_schema_version(self, schema, valid_build):
        """Missing schema_version fails."""
        del valid_build["schema_version"]
        with pytest.raises(jsonschema.ValidationError, match="schema_version"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_missing_build_id(self, schema, valid_build):
        """Missing build_id fails."""
        del valid_build["build_id"]
        with pytest.raises(jsonschema.ValidationError, match="build_id"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_missing_design_name(self, schema, valid_build):
        """Missing design_name fails."""
        del valid_build["design_name"]
        with pytest.raises(jsonschema.ValidationError, match="design_name"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_missing_build_started(self, schema, valid_build):
        """Missing build_started fails."""
        del valid_build["build_started"]
        with pytest.raises(jsonschema.ValidationError, match="build_started"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_missing_wood(self, schema, valid_build):
        """Missing wood section fails."""
        del valid_build["wood"]
        with pytest.raises(jsonschema.ValidationError, match="wood"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_player_evaluation_missing_required(self, schema, valid_build):
        """Player evaluation missing required fields fails."""
        valid_build["subjective"] = {
            "player_evaluations": [
                {
                    "notes": "Missing player_id and date",
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=valid_build, schema=schema)


class TestPatternValidation:
    """ID patterns are enforced."""

    def test_invalid_build_id_lowercase(self, schema, valid_build):
        """build_id must start with uppercase."""
        valid_build["build_id"] = "carlos_jumbo_001"
        with pytest.raises(jsonschema.ValidationError, match="build_id"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_invalid_build_id_too_short(self, schema, valid_build):
        """build_id must be at least 3 chars."""
        valid_build["build_id"] = "AB"
        with pytest.raises(jsonschema.ValidationError, match="build_id"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_valid_build_id_with_numbers(self, schema, valid_build):
        """build_id can contain numbers."""
        valid_build["build_id"] = "DREADNOUGHT_2026_001"
        jsonschema.validate(instance=valid_build, schema=schema)


class TestNullableFields:
    """Optional fields can be null."""

    def test_nullable_sections(self, schema, valid_build):
        """All major nullable sections can be null."""
        valid_build["build_completed"] = None
        valid_build["design_blueprint_path"] = None
        valid_build["as_built_dimensions"] = None
        valid_build["measurements"] = None
        valid_build["predicted"] = None
        valid_build["measured_summary"] = None
        valid_build["residuals"] = None
        valid_build["subjective"] = None
        jsonschema.validate(instance=valid_build, schema=schema)

    def test_nullable_wood_fields(self, schema, valid_build):
        """Wood selection fields can all be null."""
        valid_build["wood"] = {
            "top_flitch_id": None,
            "top_subid": None,
            "back_flitch_id": None,
            "back_subid": None,
            "sides_flitch_id": None,
            "sides_subid": None,
            "neck_flitch_id": None,
            "brace_stock_flitch_id": None,
        }
        jsonschema.validate(instance=valid_build, schema=schema)

    def test_nullable_predicted_fields(self, schema, valid_build):
        """All predicted fields can be null."""
        valid_build["predicted"] = {
            "T1_hz": None,
            "A0_hz": None,
            "T2_hz": None,
            "T3_hz": None,
            "bridge_deflection_mm_at_string_load": None,
            "top_monopole_mobility": None,
            "prediction_session_path": None,
        }
        jsonschema.validate(instance=valid_build, schema=schema)


class TestAdditionalProperties:
    """additionalProperties: false is enforced."""

    def test_extra_build_field_rejected(self, schema, valid_build):
        """Unknown field at build level fails."""
        valid_build["unknown_field"] = "should fail"
        with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_extra_wood_field_rejected(self, schema, valid_build):
        """Unknown field in wood section fails."""
        valid_build["wood"]["unknown_wood_field"] = "should fail"
        with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_extra_player_eval_field_rejected(self, schema, valid_build):
        """Unknown field in player evaluation fails."""
        valid_build["subjective"] = {
            "player_evaluations": [
                {
                    "player_id": "Test",
                    "date": "2026-05-01",
                    "unknown_field": "should fail",
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
            jsonschema.validate(instance=valid_build, schema=schema)


class TestValueConstraints:
    """Numeric constraints are enforced."""

    def test_negative_frequency_rejected(self, schema, valid_build):
        """Frequencies must be positive."""
        valid_build["predicted"] = {"T1_hz": -50.0}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_rating_out_of_range(self, schema, valid_build):
        """Ratings must be 1-10."""
        valid_build["subjective"] = {
            "player_evaluations": [
                {
                    "player_id": "Test",
                    "date": "2026-05-01",
                    "tone_rating": 15,
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=valid_build, schema=schema)

    def test_zero_engagement_allowed(self, schema, valid_build):
        """Zero engagement minutes is valid."""
        valid_build["subjective"] = {
            "player_evaluations": [
                {
                    "player_id": "Quick test",
                    "date": "2026-05-01",
                    "engagement_minutes": 0,
                }
            ],
        }
        jsonschema.validate(instance=valid_build, schema=schema)

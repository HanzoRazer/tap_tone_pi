"""Measurement schema validation tests.

Tests validate example JSON files against their respective schemas
in contracts/schemas/.
"""

import json
import pathlib

import pytest
from jsonschema import validate, ValidationError

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts" / "schemas"
EXAMPLES = ROOT / "examples" / "measurement"


class TestTapPeaksSchema:
    """Tests for tap_peaks schema validation."""
    
    @pytest.fixture
    def schema(self):
        return json.loads((SCHEMAS / "tap_peaks.schema.json").read_text())
    
    def test_valid_example(self, schema):
        """Valid tap_peaks example should validate."""
        example = json.loads((EXAMPLES / "tap_peaks.json").read_text())
        validate(example, schema)
    
    def test_minimal_valid(self, schema):
        """Minimal valid document should pass."""
        doc = {
            "schema_id": "tap_peaks",
            "schema_version": "1.0",
            "artifact_type": "chladni_peaks",
            "wav_path": "recording.wav",
            "wav_sha256": "a" * 64,
            "fs_hz": 44100,
            "band_hz": [50, 2000],
            "peaks_hz": [102.5, 175.3, 248.1],
        }
        validate(doc, schema)
    
    def test_missing_required_field_fails(self, schema):
        """Missing required field should fail."""
        doc = {
            "schema_id": "tap_peaks",
            "schema_version": "1.0",
            # missing artifact_type and others
        }
        with pytest.raises(ValidationError):
            validate(doc, schema)


class TestMoeResultSchema:
    """Tests for moe_result schema validation."""
    
    @pytest.fixture
    def schema(self):
        return json.loads((SCHEMAS / "moe_result.schema.json").read_text())
    
    def test_valid_example(self, schema):
        """Valid moe_result example should validate."""
        example = json.loads((EXAMPLES / "moe_result.json").read_text())
        validate(example, schema)
    
    def test_minimal_valid(self, schema):
        """Minimal valid document should pass."""
        doc = {
            "schema_id": "moe_result",
            "schema_version": "1.0",
            "artifact_type": "bending_moe",
            "created_utc": "2026-03-29T12:00:00Z",
            "specimen_id": "spruce-top-001",
            "method": "3PT",
            "span_mm": 400.0,
            "width_mm": 50.0,
            "thickness_mm": 3.5,
            "E_GPa": 12.8,
        }
        validate(doc, schema)
    
    def test_with_optional_fields(self, schema):
        """Document with optional fields should pass."""
        doc = {
            "schema_id": "moe_result",
            "schema_version": "1.0",
            "artifact_type": "bending_moe",
            "created_utc": "2026-03-29T12:00:00Z",
            "specimen_id": "spruce-top-001",
            "method": "4PT",
            "span_mm": 400.0,
            "width_mm": 50.0,
            "thickness_mm": 3.5,
            "E_GPa": 12.8,
            "EI_Nmm2": 1456000.0,
            "uncertainty": {
                "E_GPa_pm": 0.5,
                "EI_Nmm2_pm": 50000.0,
            },
        }
        validate(doc, schema)


class TestManifestSchema:
    """Tests for manifest schema validation."""
    
    @pytest.fixture
    def schema(self):
        return json.loads((SCHEMAS / "manifest.schema.json").read_text())
    
    def test_valid_example(self, schema):
        """Valid manifest example should validate."""
        example = json.loads((EXAMPLES / "manifest.json").read_text())
        validate(example, schema)
    
    def test_minimal_valid(self, schema):
        """Minimal valid document should pass."""
        doc = {
            "schema_id": "measurement_manifest",
            "schema_version": "1.0",
            "created_utc": "2026-03-29T12:00:00Z",
            "artifacts": ["tap_peaks.json", "moe_result.json"],
        }
        validate(doc, schema)
    
    def test_with_artifact_objects(self, schema):
        """Artifacts as objects should pass."""
        doc = {
            "schema_id": "measurement_manifest",
            "schema_version": "1.0",
            "created_utc": "2026-03-29T12:00:00Z",
            "artifacts": [
                {
                    "path": "tap_peaks.json",
                    "sha256": "a" * 64,
                    "artifact_type": "chladni_peaks",
                },
            ],
        }
        validate(doc, schema)


class TestDisplacementSeriesSchema:
    """Tests for displacement_series schema validation."""
    
    @pytest.fixture
    def schema(self):
        return json.loads((SCHEMAS / "displacement_series.schema.json").read_text())
    
    def test_valid_example(self, schema):
        """Valid displacement_series example should validate."""
        example = json.loads((EXAMPLES / "displacement_series.json").read_text())
        validate(example, schema)
    
    def test_minimal_valid(self, schema):
        """Minimal valid document should pass."""
        doc = {
            "schema_id": "displacement_series",
            "schema_version": "1.0",
            "artifact_type": "displacement_series",
            "created_utc": "2026-03-29T12:00:00Z",
            "unit": "mm",
            "sample_rate_hz": 20,
            "data": [[0.0, 0.0], [0.05, 0.03]],
        }
        validate(doc, schema)


class TestLoadSeriesSchema:
    """Tests for load_series schema validation."""
    
    @pytest.fixture
    def schema(self):
        return json.loads((SCHEMAS / "load_series.schema.json").read_text())
    
    def test_valid_example(self, schema):
        """Valid load_series example should validate."""
        example = json.loads((EXAMPLES / "load_series.json").read_text())
        validate(example, schema)
    
    def test_minimal_valid(self, schema):
        """Minimal valid document should pass."""
        doc = {
            "schema_id": "load_series",
            "schema_version": "1.0",
            "artifact_type": "load_series",
            "created_utc": "2026-03-29T12:00:00Z",
            "unit": "N",
            "sample_rate_hz": 50,
            "data": [[0.0, 0.1], [0.02, 0.15]],
        }
        validate(doc, schema)

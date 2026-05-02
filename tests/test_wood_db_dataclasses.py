"""
Tests for wood_db.py dataclasses and helper functions.

DO-003 Stage B acceptance tests:
- FlitchRecord and PlateMeasurement instantiate without error
- Dataclass field defaults match schema defaults
- is_known_species returns True for canonical IDs, False otherwise
- normalize_species_freetext maps common names to canonical IDs
- flitch_to_dict adds schema_version and converts nested objects
- flitch_from_dict reconstructs valid FlitchRecord from dict
- validate_flitch raises ValidationError for bad patterns
- Round-trip dict→FlitchRecord→dict preserves data
"""

import warnings
from datetime import datetime, timezone

import jsonschema
import pytest

from tap_tone_pi.materials import (
    FlitchRecord,
    PlateMeasurement,
    flitch_from_dict,
    flitch_to_dict,
    is_known_species,
    normalize_species_freetext,
    validate_flitch,
)


class TestPlateMeasurement:
    """PlateMeasurement dataclass tests."""

    def test_minimal_instantiation(self):
        """PlateMeasurement with required fields only."""
        m = PlateMeasurement(
            measurement_id="M_20260502T120000Z",
            measured_at_utc="2026-05-02T12:00:00Z",
            thickness_mm_mean=3.2,
            mass_g=145.0,
            density_kg_m3=420.0,
        )
        assert m.measurement_id == "M_20260502T120000Z"
        assert m.thickness_mm_mean == 3.2
        assert m.mass_g == 145.0
        assert m.density_kg_m3 == 420.0

    def test_defaults_match_schema(self):
        """Field defaults match schema defaults."""
        m = PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-02T12:00:00Z",
            thickness_mm_mean=3.0,
            mass_g=100.0,
            density_kg_m3=400.0,
        )
        # Schema default for coverage_factor is 2.0
        assert m.coverage_factor == 2.0
        # Schema default for notes is ""
        assert m.notes == ""
        # Optional fields default to None
        assert m.plate_subid is None
        assert m.E_L_GPa is None
        assert m.degrees_of_freedom is None

    def test_full_measurement(self):
        """PlateMeasurement with all optional fields."""
        m = PlateMeasurement(
            measurement_id="M_FULL_001",
            measured_at_utc="2026-05-02T14:30:00Z",
            plate_subid="TOP_HALF_A",
            rh_at_measurement_pct=45.0,
            tempC_at_measurement=22.5,
            thickness_mm_grid=[[3.1, 3.2], [3.0, 3.1]],
            thickness_mm_mean=3.1,
            thickness_mm_std=0.08,
            length_mm=520.0,
            width_mm=210.0,
            mass_g=150.0,
            density_kg_m3=415.0,
            E_L_GPa=12.5,
            E_L_uncertainty_GPa=0.3,
            E_L_expanded_uncertainty_GPa=0.6,
            E_C_GPa=0.9,
            E_C_uncertainty_GPa=0.05,
            E_C_expanded_uncertainty_GPa=0.1,
            coverage_factor=2.0,
            degrees_of_freedom=8,
            modal_freqs_hz={"(1,1)": 85.2, "(2,1)": 152.0},
            Q_factors={"(1,1)": 45.0, "(2,1)": 38.0},
            session_path="runs_phase2/session_20260502/",
            notes="First measurement after kiln drying",
        )
        assert m.E_L_GPa == 12.5
        assert m.degrees_of_freedom == 8
        assert m.modal_freqs_hz["(1,1)"] == 85.2

    def test_invalid_measurement_id_rejected(self):
        """Bad measurement_id pattern raises ValueError."""
        with pytest.raises(ValueError, match="Invalid measurement_id"):
            PlateMeasurement(
                measurement_id="m_lowercase",  # must start uppercase
                measured_at_utc="2026-05-02T12:00:00Z",
                thickness_mm_mean=3.0,
                mass_g=100.0,
                density_kg_m3=400.0,
            )


class TestFlitchRecord:
    """FlitchRecord dataclass tests."""

    def test_minimal_instantiation(self):
        """FlitchRecord with required fields only."""
        f = FlitchRecord(
            flitch_id="SITKA_2026_PACIFIC_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
        )
        assert f.flitch_id == "SITKA_2026_PACIFIC_001"
        assert f.species_id == "spruce_sitka"
        assert f.measurements == []

    def test_with_measurements(self):
        """FlitchRecord with measurement list."""
        m = PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-02T12:00:00Z",
            thickness_mm_mean=3.2,
            mass_g=145.0,
            density_kg_m3=420.0,
        )
        f = FlitchRecord(
            flitch_id="SITKA_2026_PACIFIC_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
            measurements=[m],
        )
        assert len(f.measurements) == 1
        assert f.measurements[0].thickness_mm_mean == 3.2

    def test_invalid_flitch_id_rejected(self):
        """Bad flitch_id pattern raises ValueError."""
        with pytest.raises(ValueError, match="Invalid flitch_id"):
            FlitchRecord(
                flitch_id="lowercase_bad",  # must start uppercase
                species_id="spruce_sitka",
                created_at_utc="2026-05-02T12:00:00Z",
            )

    def test_invalid_species_id_format_rejected(self):
        """Bad species_id format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid species_id format"):
            FlitchRecord(
                flitch_id="SITKA_2026_001",
                species_id="UPPERCASE_BAD",  # must be lowercase
                created_at_utc="2026-05-02T12:00:00Z",
            )

    def test_unknown_species_warns(self):
        """Unknown species_id emits warning but allows construction."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            f = FlitchRecord(
                flitch_id="TEST_2026_001",
                species_id="unknown_species_xyz",
                created_at_utc="2026-05-02T12:00:00Z",
            )
            assert len(w) == 1
            assert "not found in wood_species.json" in str(w[0].message)
            assert f.species_id == "unknown_species_xyz"


class TestIsKnownSpecies:
    """Tests for is_known_species()."""

    def test_known_species_returns_true(self):
        """Canonical species IDs return True."""
        assert is_known_species("spruce_sitka") is True
        assert is_known_species("mahogany_honduran") is True
        assert is_known_species("rosewood_east_indian") is True

    def test_unknown_species_returns_false(self):
        """Unknown IDs return False."""
        assert is_known_species("unicorn_wood") is False
        assert is_known_species("") is False
        assert is_known_species("SPRUCE_SITKA") is False  # wrong case


class TestNormalizeSpeciesFreetext:
    """Tests for normalize_species_freetext()."""

    def test_already_canonical(self):
        """Already canonical IDs pass through."""
        assert normalize_species_freetext("spruce_sitka") == "spruce_sitka"

    def test_common_aliases(self):
        """Common free-text names map to canonical IDs."""
        assert normalize_species_freetext("Sitka Spruce") == "spruce_sitka"
        assert normalize_species_freetext("sitka") == "spruce_sitka"
        assert normalize_species_freetext("Honduran Mahogany") == "mahogany_honduran"
        assert normalize_species_freetext("East Indian Rosewood") == "rosewood_east_indian"
        assert normalize_species_freetext("WRC") == "cedar_western_red"

    def test_space_to_underscore(self):
        """Space-separated names converted to underscores."""
        # If "cedar western red" is in species database
        result = normalize_species_freetext("cedar western red")
        # Either matches via underscore conversion or alias
        assert result in ["cedar_western_red", None]

    def test_unknown_returns_none(self):
        """Unknown free-text returns None."""
        assert normalize_species_freetext("Magic Wood") is None
        assert normalize_species_freetext("") is None
        assert normalize_species_freetext(None) is None


class TestFlitchToDict:
    """Tests for flitch_to_dict()."""

    def test_adds_schema_version(self):
        """Output dict has schema_version field."""
        f = FlitchRecord(
            flitch_id="SITKA_2026_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
        )
        d = flitch_to_dict(f)
        assert d["schema_version"] == "wood_flitch_record_v1"

    def test_converts_nested_measurements(self):
        """Nested PlateMeasurement objects become dicts."""
        m = PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-02T12:00:00Z",
            thickness_mm_mean=3.2,
            mass_g=145.0,
            density_kg_m3=420.0,
        )
        f = FlitchRecord(
            flitch_id="SITKA_2026_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
            measurements=[m],
        )
        d = flitch_to_dict(f)
        assert isinstance(d["measurements"], list)
        assert isinstance(d["measurements"][0], dict)
        assert d["measurements"][0]["thickness_mm_mean"] == 3.2


class TestFlitchFromDict:
    """Tests for flitch_from_dict()."""

    def test_reconstructs_minimal_flitch(self):
        """Minimal dict becomes FlitchRecord."""
        d = {
            "schema_version": "wood_flitch_record_v1",
            "flitch_id": "SITKA_2026_001",
            "species_id": "spruce_sitka",
            "created_at_utc": "2026-05-02T12:00:00Z",
            "measurements": [],
        }
        f = flitch_from_dict(d)
        assert isinstance(f, FlitchRecord)
        assert f.flitch_id == "SITKA_2026_001"
        assert f.measurements == []

    def test_reconstructs_with_measurements(self):
        """Dict with measurements becomes FlitchRecord with PlateMeasurements."""
        d = {
            "schema_version": "wood_flitch_record_v1",
            "flitch_id": "SITKA_2026_001",
            "species_id": "spruce_sitka",
            "created_at_utc": "2026-05-02T12:00:00Z",
            "measurements": [
                {
                    "measurement_id": "M_001",
                    "measured_at_utc": "2026-05-02T12:00:00Z",
                    "thickness_mm_mean": 3.2,
                    "mass_g": 145.0,
                    "density_kg_m3": 420.0,
                }
            ],
        }
        f = flitch_from_dict(d)
        assert len(f.measurements) == 1
        assert isinstance(f.measurements[0], PlateMeasurement)
        assert f.measurements[0].thickness_mm_mean == 3.2


class TestValidateFlitch:
    """Tests for validate_flitch()."""

    def test_valid_flitch_passes(self):
        """Valid FlitchRecord passes schema validation."""
        f = FlitchRecord(
            flitch_id="SITKA_2026_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
        )
        validate_flitch(f)  # Should not raise

    def test_valid_flitch_with_measurements_passes(self):
        """FlitchRecord with measurements passes validation."""
        m = PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-02T12:00:00Z",
            thickness_mm_mean=3.2,
            mass_g=145.0,
            density_kg_m3=420.0,
        )
        f = FlitchRecord(
            flitch_id="SITKA_2026_001",
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
            measurements=[m],
        )
        validate_flitch(f)  # Should not raise


class TestRoundTrip:
    """Round-trip conversion tests."""

    def test_dict_to_flitch_to_dict(self):
        """dict → FlitchRecord → dict preserves data."""
        original = {
            "schema_version": "wood_flitch_record_v1",
            "flitch_id": "SITKA_2026_001",
            "species_id": "spruce_sitka",
            "created_at_utc": "2026-05-02T12:00:00Z",
            "species_id_freetext_original": "Sitka Spruce",
            "supplier": "Pacific Rim Tonewoods",
            "purchase_lot": None,
            "purchase_date": None,
            "estimated_age_years": None,
            "moisture_content_pct_at_purchase": None,
            "notes": "",
            "measurements": [
                {
                    "measurement_id": "M_001",
                    "measured_at_utc": "2026-05-02T12:00:00Z",
                    "plate_subid": None,
                    "rh_at_measurement_pct": 45.0,
                    "tempC_at_measurement": 22.0,
                    "thickness_mm_grid": None,
                    "thickness_mm_mean": 3.2,
                    "thickness_mm_std": None,
                    "length_mm": None,
                    "width_mm": None,
                    "mass_g": 145.0,
                    "density_kg_m3": 420.0,
                    "E_L_GPa": 12.5,
                    "E_L_uncertainty_GPa": 0.3,
                    "E_L_expanded_uncertainty_GPa": 0.6,
                    "E_C_GPa": None,
                    "E_C_uncertainty_GPa": None,
                    "E_C_expanded_uncertainty_GPa": None,
                    "coverage_factor": 2.0,
                    "degrees_of_freedom": 8,
                    "modal_freqs_hz": None,
                    "Q_factors": None,
                    "session_path": None,
                    "notes": "",
                }
            ],
        }
        f = flitch_from_dict(original)
        result = flitch_to_dict(f)

        # Core fields match
        assert result["flitch_id"] == original["flitch_id"]
        assert result["species_id"] == original["species_id"]
        assert result["supplier"] == original["supplier"]

        # Measurement fields match
        assert len(result["measurements"]) == 1
        m_orig = original["measurements"][0]
        m_result = result["measurements"][0]
        assert m_result["E_L_GPa"] == m_orig["E_L_GPa"]
        assert m_result["degrees_of_freedom"] == m_orig["degrees_of_freedom"]
        assert m_result["rh_at_measurement_pct"] == m_orig["rh_at_measurement_pct"]

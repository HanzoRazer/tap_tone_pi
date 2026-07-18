"""
Tests for WoodDatabase statistics queries.

DO-003 Stage D acceptance tests:
- get_latest_measurement() returns most recent by measured_at_utc
- get_latest_measurement() returns None for flitch with no measurements
- get_all_measurements() returns sorted (flitch_id, measurement) tuples
- get_species_stats() computes mean/std for density, thickness, E_L, E_C
- get_species_stats() raises InsufficientDataError for empty species
- SpeciesStats.from_measurements() handles single measurement (std=None)
- SpeciesStats fields are None when insufficient data for std
"""

import math
from pathlib import Path

import pytest

from tap_tone_pi.materials import (
    FlitchRecord,
    InsufficientDataError,
    PlateMeasurement,
    SpeciesStats,
    WoodDatabase,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_wood_db.json"


@pytest.fixture
def populated_db(temp_db_path: Path) -> WoodDatabase:
    """A database with multiple flitches and measurements."""
    db = WoodDatabase(temp_db_path)
    db.load()

    # Sitka flitch with 3 measurements
    sitka1 = FlitchRecord(
        flitch_id="SITKA_2026_001",
        species_id="spruce_sitka",
        created_at_utc="2026-05-01T10:00:00Z",
    )
    db.add_flitch(sitka1)
    db.add_measurement(
        "SITKA_2026_001",
        PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-01T10:00:00Z",
            thickness_mm_mean=3.0,
            mass_g=140.0,
            density_kg_m3=400.0,
            E_L_GPa=12.0,
            E_C_GPa=0.8,
        ),
    )
    db.add_measurement(
        "SITKA_2026_001",
        PlateMeasurement(
            measurement_id="M_002",
            measured_at_utc="2026-05-02T10:00:00Z",
            thickness_mm_mean=3.2,
            mass_g=145.0,
            density_kg_m3=420.0,
            E_L_GPa=12.5,
            E_C_GPa=0.85,
        ),
    )
    db.add_measurement(
        "SITKA_2026_001",
        PlateMeasurement(
            measurement_id="M_003",
            measured_at_utc="2026-05-03T10:00:00Z",
            thickness_mm_mean=3.1,
            mass_g=142.0,
            density_kg_m3=410.0,
            E_L_GPa=12.2,
        ),
    )

    # Second sitka flitch with 1 measurement
    sitka2 = FlitchRecord(
        flitch_id="SITKA_2026_002",
        species_id="spruce_sitka",
        created_at_utc="2026-05-02T08:00:00Z",
    )
    db.add_flitch(sitka2)
    db.add_measurement(
        "SITKA_2026_002",
        PlateMeasurement(
            measurement_id="M_004",
            measured_at_utc="2026-05-02T08:00:00Z",
            thickness_mm_mean=2.9,
            mass_g=135.0,
            density_kg_m3=395.0,
            E_L_GPa=11.8,
            E_C_GPa=0.75,
        ),
    )

    # Mahogany flitch with no measurements
    mahog = FlitchRecord(
        flitch_id="MAHOGANY_2026_001",
        species_id="mahogany_honduran",
        created_at_utc="2026-05-01T09:00:00Z",
    )
    db.add_flitch(mahog)

    # Cedar flitch with 1 measurement (for single-measurement edge case)
    cedar = FlitchRecord(
        flitch_id="CEDAR_2026_001",
        species_id="cedar_western_red",
        created_at_utc="2026-05-01T11:00:00Z",
    )
    db.add_flitch(cedar)
    db.add_measurement(
        "CEDAR_2026_001",
        PlateMeasurement(
            measurement_id="M_005",
            measured_at_utc="2026-05-01T11:00:00Z",
            thickness_mm_mean=4.0,
            mass_g=100.0,
            density_kg_m3=350.0,
        ),
    )

    return db


class TestGetLatestMeasurement:
    """Tests for WoodDatabase.get_latest_measurement()."""

    def test_returns_most_recent(self, populated_db: WoodDatabase):
        """get_latest_measurement() returns measurement with latest timestamp."""
        latest = populated_db.get_latest_measurement("SITKA_2026_001")

        assert latest is not None
        assert latest.measurement_id == "M_003"
        assert latest.measured_at_utc == "2026-05-03T10:00:00Z"

    def test_returns_none_for_no_measurements(self, populated_db: WoodDatabase):
        """get_latest_measurement() returns None for flitch without measurements."""
        latest = populated_db.get_latest_measurement("MAHOGANY_2026_001")

        assert latest is None

    def test_single_measurement(self, populated_db: WoodDatabase):
        """get_latest_measurement() works with single measurement."""
        latest = populated_db.get_latest_measurement("CEDAR_2026_001")

        assert latest is not None
        assert latest.measurement_id == "M_005"


class TestGetAllMeasurements:
    """Tests for WoodDatabase.get_all_measurements()."""

    def test_returns_all_sorted(self, populated_db: WoodDatabase):
        """get_all_measurements() returns all measurements sorted by time."""
        all_measurements = populated_db.get_all_measurements()

        assert len(all_measurements) == 5

        # Verify sorted by measured_at_utc
        timestamps = [m.measured_at_utc for _, m in all_measurements]
        assert timestamps == sorted(timestamps)

    def test_includes_flitch_id(self, populated_db: WoodDatabase):
        """Each tuple includes the correct flitch_id."""
        all_measurements = populated_db.get_all_measurements()

        flitch_ids = [fid for fid, _ in all_measurements]
        assert "SITKA_2026_001" in flitch_ids
        assert "SITKA_2026_002" in flitch_ids
        assert "CEDAR_2026_001" in flitch_ids

    def test_empty_database(self, temp_db_path: Path):
        """get_all_measurements() returns empty list for empty db."""
        db = WoodDatabase(temp_db_path)
        db.load()

        assert db.get_all_measurements() == []


class TestGetSpeciesStats:
    """Tests for WoodDatabase.get_species_stats()."""

    def test_computes_stats(self, populated_db: WoodDatabase):
        """get_species_stats() computes mean and std for all fields."""
        stats = populated_db.get_species_stats("spruce_sitka")

        assert stats.species_id == "spruce_sitka"
        assert stats.measurement_count == 4

        # Check density stats (4 values: 400, 420, 410, 395)
        expected_density_mean = (400 + 420 + 410 + 395) / 4
        assert stats.density_kg_m3_mean == pytest.approx(expected_density_mean, rel=1e-6)
        assert stats.density_kg_m3_std is not None
        assert stats.density_kg_m3_std > 0

        # Check thickness stats (4 values: 3.0, 3.2, 3.1, 2.9)
        expected_thickness_mean = (3.0 + 3.2 + 3.1 + 2.9) / 4
        assert stats.thickness_mm_mean == pytest.approx(expected_thickness_mean, rel=1e-6)

        # Check E_L stats (4 values: 12.0, 12.5, 12.2, 11.8)
        expected_el_mean = (12.0 + 12.5 + 12.2 + 11.8) / 4
        assert stats.E_L_GPa_mean == pytest.approx(expected_el_mean, rel=1e-6)

        # Check E_C stats (only 3 values: 0.8, 0.85, 0.75 — M_003 has None)
        expected_ec_mean = (0.8 + 0.85 + 0.75) / 3
        assert stats.E_C_GPa_mean == pytest.approx(expected_ec_mean, rel=1e-6)

    def test_raises_for_no_measurements(self, populated_db: WoodDatabase):
        """get_species_stats() raises InsufficientDataError for empty species."""
        with pytest.raises(InsufficientDataError, match="No measurements found"):
            populated_db.get_species_stats("mahogany_honduran")

    def test_raises_for_unknown_species(self, populated_db: WoodDatabase):
        """get_species_stats() raises for species with no flitches."""
        with pytest.raises(InsufficientDataError, match="No measurements found"):
            populated_db.get_species_stats("rosewood_brazilian")


class TestSpeciesStats:
    """Tests for SpeciesStats.from_measurements()."""

    def test_single_measurement_no_std(self):
        """Single measurement: mean computed, std is None."""
        m = PlateMeasurement(
            measurement_id="M_001",
            measured_at_utc="2026-05-01T10:00:00Z",
            thickness_mm_mean=3.0,
            mass_g=140.0,
            density_kg_m3=400.0,
            E_L_GPa=12.0,
        )

        stats = SpeciesStats.from_measurements("test_species", [m])

        assert stats.measurement_count == 1
        assert stats.density_kg_m3_mean == 400.0
        assert stats.density_kg_m3_std is None
        assert stats.E_L_GPa_mean == 12.0
        assert stats.E_L_GPa_std is None

    def test_two_measurements_computes_std(self):
        """Two measurements: both mean and std computed."""
        measurements = [
            PlateMeasurement(
                measurement_id="M_001",
                measured_at_utc="2026-05-01T10:00:00Z",
                thickness_mm_mean=3.0,
                mass_g=140.0,
                density_kg_m3=400.0,
            ),
            PlateMeasurement(
                measurement_id="M_002",
                measured_at_utc="2026-05-02T10:00:00Z",
                thickness_mm_mean=3.2,
                mass_g=145.0,
                density_kg_m3=420.0,
            ),
        ]

        stats = SpeciesStats.from_measurements("test_species", measurements)

        assert stats.measurement_count == 2
        assert stats.density_kg_m3_mean == 410.0  # (400 + 420) / 2
        assert stats.density_kg_m3_std is not None

        # Sample std for [400, 420] = sqrt(200) ≈ 14.14
        expected_std = math.sqrt(((400 - 410) ** 2 + (420 - 410) ** 2) / 1)
        assert stats.density_kg_m3_std == pytest.approx(expected_std, rel=1e-6)

    def test_all_null_optional_field(self):
        """Optional field with all None values: mean and std are None."""
        measurements = [
            PlateMeasurement(
                measurement_id="M_001",
                measured_at_utc="2026-05-01T10:00:00Z",
                thickness_mm_mean=3.0,
                mass_g=140.0,
                density_kg_m3=400.0,
                E_L_GPa=None,
            ),
            PlateMeasurement(
                measurement_id="M_002",
                measured_at_utc="2026-05-02T10:00:00Z",
                thickness_mm_mean=3.2,
                mass_g=145.0,
                density_kg_m3=420.0,
                E_L_GPa=None,
            ),
        ]

        stats = SpeciesStats.from_measurements("test_species", measurements)

        assert stats.E_L_GPa_mean is None
        assert stats.E_L_GPa_std is None
        assert stats.E_C_GPa_mean is None
        assert stats.E_C_GPa_std is None

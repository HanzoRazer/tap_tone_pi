"""
Tests for WoodDatabase CRUD operations.

DO-003 Stage C acceptance tests:
- WoodDatabase.load() creates empty db if file missing
- WoodDatabase.load() loads existing records from JSON
- WoodDatabase.save() persists records to JSON
- add_flitch() adds new record, raises DuplicateFlitchError for duplicates
- get_flitch() retrieves by ID, raises FlitchNotFoundError if missing
- update_flitch() replaces existing, raises FlitchNotFoundError if missing
- delete_flitch() removes record, raises FlitchNotFoundError if missing
- add_measurement() appends to existing flitch
- list_flitches() returns sorted IDs
- list_by_species() filters by species_id
- Round-trip: save() then load() preserves all data
"""

import json
from pathlib import Path

import pytest

from tap_tone_pi.materials import (
    DuplicateFlitchError,
    FlitchNotFoundError,
    FlitchRecord,
    PlateMeasurement,
    WoodDatabase,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_wood_db.json"


@pytest.fixture
def sample_flitch() -> FlitchRecord:
    """A sample flitch record."""
    return FlitchRecord(
        flitch_id="SITKA_2026_PACIFIC_001",
        species_id="spruce_sitka",
        created_at_utc="2026-05-02T12:00:00Z",
        supplier="Pacific Rim Tonewoods",
    )


@pytest.fixture
def sample_measurement() -> PlateMeasurement:
    """A sample measurement."""
    return PlateMeasurement(
        measurement_id="M_20260502T120000Z",
        measured_at_utc="2026-05-02T12:00:00Z",
        thickness_mm_mean=3.2,
        mass_g=145.0,
        density_kg_m3=420.0,
    )


class TestDatabaseLoad:
    """Tests for WoodDatabase.load()."""

    def test_creates_empty_db_if_missing(self, temp_db_path: Path):
        """load() with no file creates empty database."""
        db = WoodDatabase(temp_db_path)
        assert not temp_db_path.exists()

        db.load()

        assert len(db) == 0
        assert db.list_flitches() == []

    def test_loads_existing_records(self, temp_db_path: Path):
        """load() reads existing JSON records."""
        records = [
            {
                "schema_version": "wood_flitch_record_v1",
                "flitch_id": "SITKA_2026_001",
                "species_id": "spruce_sitka",
                "created_at_utc": "2026-05-02T12:00:00Z",
                "species_id_freetext_original": None,
                "supplier": None,
                "purchase_lot": None,
                "purchase_date": None,
                "estimated_age_years": None,
                "moisture_content_pct_at_purchase": None,
                "notes": "",
                "measurements": [],
            }
        ]
        temp_db_path.write_text(json.dumps(records))

        db = WoodDatabase(temp_db_path)
        db.load()

        assert len(db) == 1
        assert "SITKA_2026_001" in db


class TestDatabaseSave:
    """Tests for WoodDatabase.save()."""

    def test_creates_parent_directories(self, tmp_path: Path):
        """save() creates parent dirs if needed."""
        nested_path = tmp_path / "a" / "b" / "c" / "db.json"
        db = WoodDatabase(nested_path)
        db.load()

        db.save()

        assert nested_path.exists()

    def test_persists_records(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """save() writes records to JSON."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        db.save()

        data = json.loads(temp_db_path.read_text())
        assert len(data) == 1
        assert data[0]["flitch_id"] == sample_flitch.flitch_id


class TestAddFlitch:
    """Tests for WoodDatabase.add_flitch()."""

    def test_adds_new_record(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """add_flitch() adds a new record."""
        db = WoodDatabase(temp_db_path)
        db.load()

        db.add_flitch(sample_flitch)

        assert len(db) == 1
        assert sample_flitch.flitch_id in db

    def test_rejects_duplicate(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """add_flitch() raises DuplicateFlitchError for existing ID."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        with pytest.raises(DuplicateFlitchError, match="already exists"):
            db.add_flitch(sample_flitch)


class TestGetFlitch:
    """Tests for WoodDatabase.get_flitch()."""

    def test_retrieves_existing(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """get_flitch() returns the record."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        result = db.get_flitch(sample_flitch.flitch_id)

        assert result.flitch_id == sample_flitch.flitch_id
        assert result.supplier == sample_flitch.supplier

    def test_raises_not_found(self, temp_db_path: Path):
        """get_flitch() raises FlitchNotFoundError for missing ID."""
        db = WoodDatabase(temp_db_path)
        db.load()

        with pytest.raises(FlitchNotFoundError, match="not found"):
            db.get_flitch("NONEXISTENT_001")


class TestUpdateFlitch:
    """Tests for WoodDatabase.update_flitch()."""

    def test_updates_existing(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """update_flitch() replaces the record."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        updated = FlitchRecord(
            flitch_id=sample_flitch.flitch_id,
            species_id="spruce_sitka",
            created_at_utc="2026-05-02T12:00:00Z",
            supplier="Updated Supplier",
            notes="Updated notes",
        )
        db.update_flitch(updated)

        result = db.get_flitch(sample_flitch.flitch_id)
        assert result.supplier == "Updated Supplier"
        assert result.notes == "Updated notes"

    def test_raises_not_found(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """update_flitch() raises FlitchNotFoundError for missing ID."""
        db = WoodDatabase(temp_db_path)
        db.load()

        with pytest.raises(FlitchNotFoundError, match="not found"):
            db.update_flitch(sample_flitch)


class TestDeleteFlitch:
    """Tests for WoodDatabase.delete_flitch()."""

    def test_removes_existing(self, temp_db_path: Path, sample_flitch: FlitchRecord):
        """delete_flitch() removes the record."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        db.delete_flitch(sample_flitch.flitch_id)

        assert sample_flitch.flitch_id not in db
        assert len(db) == 0

    def test_raises_not_found(self, temp_db_path: Path):
        """delete_flitch() raises FlitchNotFoundError for missing ID."""
        db = WoodDatabase(temp_db_path)
        db.load()

        with pytest.raises(FlitchNotFoundError, match="not found"):
            db.delete_flitch("NONEXISTENT_001")


class TestAddMeasurement:
    """Tests for WoodDatabase.add_measurement()."""

    def test_appends_measurement(
        self,
        temp_db_path: Path,
        sample_flitch: FlitchRecord,
        sample_measurement: PlateMeasurement,
    ):
        """add_measurement() appends to flitch."""
        db = WoodDatabase(temp_db_path)
        db.load()
        db.add_flitch(sample_flitch)

        db.add_measurement(sample_flitch.flitch_id, sample_measurement)

        result = db.get_flitch(sample_flitch.flitch_id)
        assert len(result.measurements) == 1
        assert result.measurements[0].thickness_mm_mean == 3.2

    def test_raises_not_found(
        self, temp_db_path: Path, sample_measurement: PlateMeasurement
    ):
        """add_measurement() raises FlitchNotFoundError for missing flitch."""
        db = WoodDatabase(temp_db_path)
        db.load()

        with pytest.raises(FlitchNotFoundError, match="not found"):
            db.add_measurement("NONEXISTENT_001", sample_measurement)


class TestListMethods:
    """Tests for list_flitches() and list_by_species()."""

    def test_list_flitches_sorted(self, temp_db_path: Path):
        """list_flitches() returns sorted IDs."""
        db = WoodDatabase(temp_db_path)
        db.load()

        db.add_flitch(
            FlitchRecord(
                flitch_id="ZEBRA_2026_001",
                species_id="spruce_sitka",
                created_at_utc="2026-05-02T12:00:00Z",
            )
        )
        db.add_flitch(
            FlitchRecord(
                flitch_id="APPLE_2026_001",
                species_id="spruce_sitka",
                created_at_utc="2026-05-02T12:00:00Z",
            )
        )

        result = db.list_flitches()

        assert result == ["APPLE_2026_001", "ZEBRA_2026_001"]

    def test_list_by_species(self, temp_db_path: Path):
        """list_by_species() filters by species_id."""
        db = WoodDatabase(temp_db_path)
        db.load()

        db.add_flitch(
            FlitchRecord(
                flitch_id="SITKA_2026_001",
                species_id="spruce_sitka",
                created_at_utc="2026-05-02T12:00:00Z",
            )
        )
        db.add_flitch(
            FlitchRecord(
                flitch_id="MAHOGANY_2026_001",
                species_id="mahogany_honduran",
                created_at_utc="2026-05-02T12:00:00Z",
            )
        )
        db.add_flitch(
            FlitchRecord(
                flitch_id="SITKA_2026_002",
                species_id="spruce_sitka",
                created_at_utc="2026-05-02T12:00:00Z",
            )
        )

        sitka_ids = db.list_by_species("spruce_sitka")
        mahogany_ids = db.list_by_species("mahogany_honduran")

        assert sitka_ids == ["SITKA_2026_001", "SITKA_2026_002"]
        assert mahogany_ids == ["MAHOGANY_2026_001"]


class TestRoundTrip:
    """Round-trip persistence tests."""

    def test_save_load_preserves_data(
        self,
        temp_db_path: Path,
        sample_flitch: FlitchRecord,
        sample_measurement: PlateMeasurement,
    ):
        """save() then load() preserves all data."""
        db1 = WoodDatabase(temp_db_path)
        db1.load()
        db1.add_flitch(sample_flitch)
        db1.add_measurement(sample_flitch.flitch_id, sample_measurement)
        db1.save()

        db2 = WoodDatabase(temp_db_path)
        db2.load()

        assert len(db2) == 1
        flitch = db2.get_flitch(sample_flitch.flitch_id)
        assert flitch.supplier == sample_flitch.supplier
        assert len(flitch.measurements) == 1
        assert flitch.measurements[0].thickness_mm_mean == 3.2
        assert flitch.measurements[0].density_kg_m3 == 420.0

    def test_multiple_flitches_round_trip(self, temp_db_path: Path):
        """Multiple flitches survive round-trip."""
        db1 = WoodDatabase(temp_db_path)
        db1.load()

        for i in range(5):
            db1.add_flitch(
                FlitchRecord(
                    flitch_id=f"TEST_2026_{i:03d}",
                    species_id="spruce_sitka",
                    created_at_utc="2026-05-02T12:00:00Z",
                    notes=f"Flitch {i}",
                )
            )
        db1.save()

        db2 = WoodDatabase(temp_db_path)
        db2.load()

        assert len(db2) == 5
        assert db2.get_flitch("TEST_2026_002").notes == "Flitch 2"

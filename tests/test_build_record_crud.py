"""
Tests for BuildDatabase CRUD operations.

DO-004 Stage C acceptance tests:
- BuildDatabase.load() creates empty db if file missing
- BuildDatabase.load() loads existing records from JSON
- BuildDatabase.save() persists records to JSON
- add_build() adds new record, raises DuplicateBuildError for duplicates
- get_build() retrieves by ID, raises BuildNotFoundError if missing
- update_build() replaces existing, raises BuildNotFoundError if missing
- delete_build() removes record, raises BuildNotFoundError if missing
- list_builds() returns sorted IDs
- list_by_design() filters by design_name
- list_in_progress() / list_completed() filter by build_completed
- Round-trip: save() then load() preserves all data
"""

import json
from pathlib import Path

import pytest

from tap_tone_pi.materials import (
    BuildDatabase,
    BuildNotFoundError,
    BuildRecord,
    DuplicateBuildError,
    PredictedValues,
    WoodSelection,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_builds_db.json"


@pytest.fixture
def sample_build() -> BuildRecord:
    """A sample build record."""
    return BuildRecord(
        build_id="CARLOS_JUMBO_001",
        design_name="Carlos Jumbo",
        build_started="2026-05-01",
        created_at_utc="2026-05-01T10:00:00Z",
        wood=WoodSelection(top_flitch_id="SITKA_2026_001"),
    )


@pytest.fixture
def completed_build() -> BuildRecord:
    """A completed build record."""
    return BuildRecord(
        build_id="DREADNOUGHT_001",
        design_name="Standard Dreadnought",
        build_started="2026-01-01",
        build_completed="2026-02-15",
        created_at_utc="2026-01-01T10:00:00Z",
    )


class TestDatabaseLoad:
    """Tests for BuildDatabase.load()."""

    def test_creates_empty_db_if_missing(self, temp_db_path: Path):
        """load() with no file creates empty database."""
        db = BuildDatabase(temp_db_path)
        assert not temp_db_path.exists()

        db.load()

        assert len(db) == 0
        assert db.list_builds() == []

    def test_loads_existing_records(self, temp_db_path: Path):
        """load() reads existing JSON records."""
        records = [
            {
                "schema_version": "instrument_build_record_v1",
                "build_id": "TEST_001",
                "design_name": "Test Design",
                "build_started": "2026-05-01",
                "created_at_utc": "2026-05-01T10:00:00Z",
                "wood": {},
            }
        ]
        temp_db_path.write_text(json.dumps(records))

        db = BuildDatabase(temp_db_path)
        db.load()

        assert len(db) == 1
        assert "TEST_001" in db


class TestDatabaseSave:
    """Tests for BuildDatabase.save()."""

    def test_creates_parent_directories(self, tmp_path: Path):
        """save() creates parent dirs if needed."""
        nested_path = tmp_path / "a" / "b" / "c" / "db.json"
        db = BuildDatabase(nested_path)
        db.load()

        db.save()

        assert nested_path.exists()

    def test_persists_records(self, temp_db_path: Path, sample_build: BuildRecord):
        """save() writes records to JSON."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)

        db.save()

        data = json.loads(temp_db_path.read_text())
        assert len(data) == 1
        assert data[0]["build_id"] == sample_build.build_id


class TestAddBuild:
    """Tests for BuildDatabase.add_build()."""

    def test_adds_new_record(self, temp_db_path: Path, sample_build: BuildRecord):
        """add_build() adds a new record."""
        db = BuildDatabase(temp_db_path)
        db.load()

        db.add_build(sample_build)

        assert len(db) == 1
        assert sample_build.build_id in db

    def test_rejects_duplicate(self, temp_db_path: Path, sample_build: BuildRecord):
        """add_build() raises DuplicateBuildError for existing ID."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)

        with pytest.raises(DuplicateBuildError, match="already exists"):
            db.add_build(sample_build)


class TestGetBuild:
    """Tests for BuildDatabase.get_build()."""

    def test_retrieves_existing(self, temp_db_path: Path, sample_build: BuildRecord):
        """get_build() returns the record."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)

        result = db.get_build(sample_build.build_id)

        assert result.build_id == sample_build.build_id
        assert result.design_name == sample_build.design_name

    def test_raises_not_found(self, temp_db_path: Path):
        """get_build() raises BuildNotFoundError for missing ID."""
        db = BuildDatabase(temp_db_path)
        db.load()

        with pytest.raises(BuildNotFoundError, match="not found"):
            db.get_build("NONEXISTENT_001")


class TestUpdateBuild:
    """Tests for BuildDatabase.update_build()."""

    def test_updates_existing(self, temp_db_path: Path, sample_build: BuildRecord):
        """update_build() replaces the record."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)

        updated = BuildRecord(
            build_id=sample_build.build_id,
            design_name="Carlos Jumbo",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            notes="Updated notes",
            predicted=PredictedValues(T1_hz=95.0),
        )
        db.update_build(updated)

        result = db.get_build(sample_build.build_id)
        assert result.notes == "Updated notes"
        assert result.predicted.T1_hz == 95.0
        assert result.updated_at_utc is not None

    def test_raises_not_found(self, temp_db_path: Path, sample_build: BuildRecord):
        """update_build() raises BuildNotFoundError for missing ID."""
        db = BuildDatabase(temp_db_path)
        db.load()

        with pytest.raises(BuildNotFoundError, match="not found"):
            db.update_build(sample_build)


class TestDeleteBuild:
    """Tests for BuildDatabase.delete_build()."""

    def test_removes_existing(self, temp_db_path: Path, sample_build: BuildRecord):
        """delete_build() removes the record."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)

        db.delete_build(sample_build.build_id)

        assert sample_build.build_id not in db
        assert len(db) == 0

    def test_raises_not_found(self, temp_db_path: Path):
        """delete_build() raises BuildNotFoundError for missing ID."""
        db = BuildDatabase(temp_db_path)
        db.load()

        with pytest.raises(BuildNotFoundError, match="not found"):
            db.delete_build("NONEXISTENT_001")


class TestListMethods:
    """Tests for list_builds(), list_by_design(), list_in_progress(), list_completed()."""

    def test_list_builds_sorted(self, temp_db_path: Path):
        """list_builds() returns sorted IDs."""
        db = BuildDatabase(temp_db_path)
        db.load()

        db.add_build(
            BuildRecord(
                build_id="ZEBRA_001",
                design_name="Test",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )
        )
        db.add_build(
            BuildRecord(
                build_id="APPLE_001",
                design_name="Test",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )
        )

        result = db.list_builds()

        assert result == ["APPLE_001", "ZEBRA_001"]

    def test_list_by_design(self, temp_db_path: Path):
        """list_by_design() filters by design name."""
        db = BuildDatabase(temp_db_path)
        db.load()

        db.add_build(
            BuildRecord(
                build_id="JUMBO_001",
                design_name="Carlos Jumbo",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )
        )
        db.add_build(
            BuildRecord(
                build_id="DREAD_001",
                design_name="Standard Dreadnought",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )
        )
        db.add_build(
            BuildRecord(
                build_id="JUMBO_002",
                design_name="Carlos Jumbo",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
            )
        )

        jumbo_ids = db.list_by_design("Carlos Jumbo")
        dread_ids = db.list_by_design("Standard Dreadnought")

        assert jumbo_ids == ["JUMBO_001", "JUMBO_002"]
        assert dread_ids == ["DREAD_001"]

    def test_list_in_progress(
        self, temp_db_path: Path, sample_build: BuildRecord, completed_build: BuildRecord
    ):
        """list_in_progress() returns builds without build_completed."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)
        db.add_build(completed_build)

        in_progress = db.list_in_progress()

        assert in_progress == ["CARLOS_JUMBO_001"]

    def test_list_completed(
        self, temp_db_path: Path, sample_build: BuildRecord, completed_build: BuildRecord
    ):
        """list_completed() returns builds with build_completed set."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(sample_build)
        db.add_build(completed_build)

        completed = db.list_completed()

        assert completed == ["DREADNOUGHT_001"]


class TestRoundTrip:
    """Round-trip persistence tests."""

    def test_save_load_preserves_data(
        self, temp_db_path: Path, sample_build: BuildRecord
    ):
        """save() then load() preserves all data."""
        db1 = BuildDatabase(temp_db_path)
        db1.load()
        db1.add_build(sample_build)
        db1.save()

        db2 = BuildDatabase(temp_db_path)
        db2.load()

        assert len(db2) == 1
        build = db2.get_build(sample_build.build_id)
        assert build.design_name == sample_build.design_name
        assert build.wood.top_flitch_id == sample_build.wood.top_flitch_id

    def test_multiple_builds_round_trip(self, temp_db_path: Path):
        """Multiple builds survive round-trip."""
        db1 = BuildDatabase(temp_db_path)
        db1.load()

        for i in range(5):
            db1.add_build(
                BuildRecord(
                    build_id=f"TEST_2026_{i:03d}",
                    design_name="Test Design",
                    build_started="2026-05-01",
                    created_at_utc="2026-05-01T10:00:00Z",
                    notes=f"Build {i}",
                )
            )
        db1.save()

        db2 = BuildDatabase(temp_db_path)
        db2.load()

        assert len(db2) == 5
        assert db2.get_build("TEST_2026_002").notes == "Build 2"

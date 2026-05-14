"""
Tests for BuildDatabase cross-reference queries.

DO-004 Stage D acceptance tests:
- get_builds_using_flitch() finds builds referencing a flitch
- get_builds_using_flitch() searches all wood selection fields
- compute_and_set_residuals() computes and saves residuals
- compute_and_set_residuals() raises when predicted/measured missing
- get_referenced_flitch_ids() returns unique flitch_ids
"""

from pathlib import Path

import pytest

from tap_tone_pi.materials import (
    BuildDatabase,
    BuildRecord,
    MeasuredSummary,
    PredictedValues,
    WoodSelection,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_builds_db.json"


@pytest.fixture
def populated_db(temp_db_path: Path) -> BuildDatabase:
    """A database with multiple builds for cross-reference testing."""
    db = BuildDatabase(temp_db_path)
    db.load()

    # Build 1: uses SITKA for top, ROSEWOOD for back/sides
    db.add_build(
        BuildRecord(
            build_id="BUILD_001",
            design_name="Carlos Jumbo",
            build_started="2026-05-01",
            created_at_utc="2026-05-01T10:00:00Z",
            wood=WoodSelection(
                top_flitch_id="SITKA_2026_001",
                back_flitch_id="ROSEWOOD_2026_001",
                sides_flitch_id="ROSEWOOD_2026_001",
                neck_flitch_id="MAHOGANY_2026_001",
            ),
        )
    )

    # Build 2: uses same SITKA top, different back
    db.add_build(
        BuildRecord(
            build_id="BUILD_002",
            design_name="Standard Dreadnought",
            build_started="2026-05-15",
            created_at_utc="2026-05-15T10:00:00Z",
            wood=WoodSelection(
                top_flitch_id="SITKA_2026_001",
                back_flitch_id="KOA_2026_001",
                sides_flitch_id="KOA_2026_001",
            ),
        )
    )

    # Build 3: with predictions and measurements for residual testing
    db.add_build(
        BuildRecord(
            build_id="BUILD_003",
            design_name="Test Build",
            build_started="2026-06-01",
            created_at_utc="2026-06-01T10:00:00Z",
            wood=WoodSelection(top_flitch_id="ADIRONDACK_2026_001"),
            predicted=PredictedValues(T1_hz=100.0, A0_hz=100.0),
            measured_summary=MeasuredSummary(T1_hz=95.0, A0_hz=102.0),
        )
    )

    # Build 4: predictions only (no measured)
    db.add_build(
        BuildRecord(
            build_id="BUILD_004",
            design_name="Test Build",
            build_started="2026-06-15",
            created_at_utc="2026-06-15T10:00:00Z",
            predicted=PredictedValues(T1_hz=90.0),
        )
    )

    return db


class TestGetBuildsUsingFlitch:
    """Tests for BuildDatabase.get_builds_using_flitch()."""

    def test_finds_builds_with_top(self, populated_db: BuildDatabase):
        """Finds builds using flitch for top."""
        builds = populated_db.get_builds_using_flitch("SITKA_2026_001")
        assert builds == ["BUILD_001", "BUILD_002"]

    def test_finds_builds_with_back_sides(self, populated_db: BuildDatabase):
        """Finds builds using flitch for back/sides."""
        builds = populated_db.get_builds_using_flitch("ROSEWOOD_2026_001")
        assert builds == ["BUILD_001"]

    def test_finds_builds_with_neck(self, populated_db: BuildDatabase):
        """Finds builds using flitch for neck."""
        builds = populated_db.get_builds_using_flitch("MAHOGANY_2026_001")
        assert builds == ["BUILD_001"]

    def test_no_builds_found(self, populated_db: BuildDatabase):
        """Returns empty list when no builds use flitch."""
        builds = populated_db.get_builds_using_flitch("NONEXISTENT_FLITCH")
        assert builds == []


class TestComputeAndSetResiduals:
    """Tests for BuildDatabase.compute_and_set_residuals()."""

    def test_computes_and_sets(self, populated_db: BuildDatabase):
        """Computes residuals and updates the build."""
        residuals = populated_db.compute_and_set_residuals("BUILD_003")

        assert residuals.T1_residual_hz == -5.0
        assert residuals.T1_residual_pct == -5.0
        assert residuals.A0_residual_hz == 2.0
        assert residuals.computed_at_utc is not None

        # Verify it was saved
        build = populated_db.get_build("BUILD_003")
        assert build.residuals is not None
        assert build.residuals.T1_residual_hz == -5.0
        assert build.updated_at_utc is not None

    def test_raises_when_no_predicted(self, populated_db: BuildDatabase):
        """Raises ValueError when predicted is not set."""
        # BUILD_001 has no predicted values
        with pytest.raises(ValueError, match="no predicted values"):
            populated_db.compute_and_set_residuals("BUILD_001")

    def test_raises_when_no_measured(self, populated_db: BuildDatabase):
        """Raises ValueError when measured_summary is not set."""
        # BUILD_004 has predicted but no measured
        with pytest.raises(ValueError, match="no measured summary"):
            populated_db.compute_and_set_residuals("BUILD_004")


class TestGetReferencedFlitchIds:
    """Tests for BuildDatabase.get_referenced_flitch_ids()."""

    def test_returns_unique_sorted(self, populated_db: BuildDatabase):
        """Returns unique, sorted flitch_ids."""
        flitch_ids = populated_db.get_referenced_flitch_ids("BUILD_001")

        # ROSEWOOD appears twice (back and sides) but should be deduplicated
        assert flitch_ids == [
            "MAHOGANY_2026_001",
            "ROSEWOOD_2026_001",
            "SITKA_2026_001",
        ]

    def test_filters_none_values(self, populated_db: BuildDatabase):
        """Filters out None values."""
        flitch_ids = populated_db.get_referenced_flitch_ids("BUILD_002")

        # Only has top, back, sides — no neck, brace, fretboard, bridge
        assert flitch_ids == ["KOA_2026_001", "SITKA_2026_001"]

    def test_empty_wood_selection(self, temp_db_path: Path):
        """Returns empty list for build with no flitches selected."""
        db = BuildDatabase(temp_db_path)
        db.load()
        db.add_build(
            BuildRecord(
                build_id="EMPTY_001",
                design_name="Empty Test",
                build_started="2026-05-01",
                created_at_utc="2026-05-01T10:00:00Z",
                wood=WoodSelection(),
            )
        )

        flitch_ids = db.get_referenced_flitch_ids("EMPTY_001")
        assert flitch_ids == []

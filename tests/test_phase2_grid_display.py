"""
Tests for tap_tone_pi.phase2.grid_display module.
"""

import pytest
from tap_tone_pi.phase2.grid_display import GridDisplay, PointStatus, Colors
from tap_tone_pi.core.grid import Grid, GridPoint


@pytest.fixture
def sample_grid():
    """Create a 3x3 test grid."""
    points = []
    for row, y in enumerate([0, 50, 100]):
        for col, x in enumerate([0, 50, 100]):
            point_id = f"{chr(65 + row)}{col + 1}"  # A1, A2, A3, B1, ...
            points.append(GridPoint(id=point_id, x=float(x), y=float(y)))
    return Grid(units="mm", origin="center", points=points)


@pytest.fixture
def sample_display(sample_grid):
    """Create a GridDisplay with the sample grid."""
    return GridDisplay(sample_grid, use_color=False)


class TestGridDisplay:
    """Tests for GridDisplay class."""

    def test_init_all_pending(self, sample_display):
        """All points should start as pending."""
        stats = sample_display.get_stats()
        assert stats["pending"] == 9
        assert stats["captured"] == 0
        assert stats["failed"] == 0

    def test_update_status(self, sample_display):
        """Should update point status correctly."""
        sample_display.update("A1", PointStatus.CAPTURED)
        sample_display.update("A2", PointStatus.FAILED)
        sample_display.update("A3", PointStatus.WARNING)

        assert sample_display.statuses["A1"] == PointStatus.CAPTURED
        assert sample_display.statuses["A2"] == PointStatus.FAILED
        assert sample_display.statuses["A3"] == PointStatus.WARNING

    def test_get_stats(self, sample_display):
        """Should return correct counts."""
        sample_display.update("A1", PointStatus.CAPTURED)
        sample_display.update("A2", PointStatus.CAPTURED)
        sample_display.update("B1", PointStatus.WARNING)
        sample_display.update("B2", PointStatus.FAILED)

        stats = sample_display.get_stats()
        assert stats["captured"] == 2
        assert stats["warning"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 5

    def test_set_current(self, sample_display):
        """Should set current point."""
        sample_display.set_current("B2")
        assert sample_display.current_point == "B2"

        sample_display.set_current(None)
        assert sample_display.current_point is None

    def test_render_contains_stats(self, sample_display):
        """Rendered output should contain progress stats."""
        sample_display.update("A1", PointStatus.CAPTURED)
        sample_display.update("A2", PointStatus.CAPTURED)

        output = sample_display.render()

        assert "Progress:" in output
        assert "2/9" in output

    def test_render_contains_legend(self, sample_display):
        """Rendered output should contain legend."""
        output = sample_display.render()

        assert "captured" in output
        assert "pending" in output
        assert "failed" in output

    def test_render_contains_current_point(self, sample_display):
        """Rendered output should show current point."""
        sample_display.set_current("B2")
        output = sample_display.render()

        assert "Current: B2" in output

    def test_render_compact(self, sample_display):
        """Compact render should be single line."""
        sample_display.update("A1", PointStatus.CAPTURED)
        sample_display.update("A2", PointStatus.CAPTURED)
        sample_display.update("A3", PointStatus.CAPTURED)
        sample_display.set_current("B1")

        output = sample_display.render_compact()

        assert "3/9" in output
        assert "B1" in output
        assert "\n" not in output


class TestPointStatus:
    """Tests for PointStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses should exist."""
        assert PointStatus.PENDING
        assert PointStatus.CAPTURED
        assert PointStatus.WARNING
        assert PointStatus.FAILED
        assert PointStatus.SKIPPED

    def test_status_values(self):
        """Status values should be strings."""
        assert PointStatus.PENDING.value == "pending"
        assert PointStatus.CAPTURED.value == "captured"


class TestColors:
    """Tests for Colors class."""

    def test_supports_color_with_no_color_env(self, monkeypatch):
        """NO_COLOR env var should disable colors."""
        monkeypatch.setenv("NO_COLOR", "1")
        assert Colors.supports_color() is False

    def test_supports_color_with_force_color_env(self, monkeypatch):
        """FORCE_COLOR env var should enable colors."""
        monkeypatch.setenv("FORCE_COLOR", "1")
        monkeypatch.delenv("NO_COLOR", raising=False)
        assert Colors.supports_color() is True


class TestGridMatrix:
    """Tests for grid matrix building."""

    def test_build_grid_matrix_dimensions(self, sample_display):
        """Matrix should have correct dimensions."""
        matrix, x_coords, y_coords = sample_display._build_grid_matrix()

        assert len(matrix) == 3  # 3 rows
        assert len(matrix[0]) == 3  # 3 columns
        assert len(x_coords) == 3
        assert len(y_coords) == 3

    def test_build_grid_matrix_point_placement(self, sample_display):
        """Points should be in correct matrix positions."""
        matrix, x_coords, y_coords = sample_display._build_grid_matrix()

        # y_coords are sorted in reverse (top to bottom)
        # So row 0 should have the highest y values (C row)
        # and row 2 should have the lowest y values (A row)

        # Check that all points are placed
        all_points = set()
        for row in matrix:
            for point_id in row:
                if point_id:
                    all_points.add(point_id)

        assert len(all_points) == 9


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_grid(self):
        """Should handle empty grid gracefully."""
        grid = Grid(units="mm", origin="center", points=[])
        display = GridDisplay(grid, use_color=False)

        output = display.render()
        assert "0 points" in output

    def test_single_point_grid(self):
        """Should handle single point grid."""
        grid = Grid(
            units="mm", origin="center", points=[GridPoint(id="X1", x=0.0, y=0.0)]
        )
        display = GridDisplay(grid, use_color=False)

        display.update("X1", PointStatus.CAPTURED)
        stats = display.get_stats()

        assert stats["captured"] == 1
        assert stats["pending"] == 0

    def test_irregular_grid(self):
        """Should handle non-rectangular point layout."""
        # Triangle of points
        points = [
            GridPoint(id="A1", x=0.0, y=0.0),
            GridPoint(id="B1", x=-25.0, y=50.0),
            GridPoint(id="B2", x=25.0, y=50.0),
        ]
        grid = Grid(units="mm", origin="center", points=points)
        display = GridDisplay(grid, use_color=False)

        output = display.render()
        assert "3 points" in output

"""Tests for tap_tone_pi.core.grid module (Phase 9)."""
import json
import pytest
from pathlib import Path

from tap_tone_pi.core.grid import (
    GridPoint,
    Grid,
    GridSession,
    PointProgress,
    PointStatus,
)


class TestGridPoint:
    """Tests for GridPoint dataclass."""

    def test_create_point(self):
        p = GridPoint(id="A1", x=10.0, y=20.0)
        assert p.id == "A1"
        assert p.x == 10.0
        assert p.y == 20.0
        assert p.label is None

    def test_create_point_with_label(self):
        p = GridPoint(id="P1", x=0.0, y=0.0, label="Center")
        assert p.label == "Center"

    def test_to_dict(self):
        p = GridPoint(id="A1", x=10.0, y=20.0, label="Test")
        d = p.to_dict()
        assert d == {"id": "A1", "x": 10.0, "y": 20.0, "label": "Test"}

    def test_to_dict_no_label(self):
        p = GridPoint(id="A1", x=10.0, y=20.0)
        d = p.to_dict()
        assert "label" not in d

    def test_from_dict(self):
        d = {"id": "B2", "x": 5.5, "y": 7.7, "label": "Corner"}
        p = GridPoint.from_dict(d)
        assert p.id == "B2"
        assert p.x == 5.5
        assert p.y == 7.7
        assert p.label == "Corner"


class TestGrid:
    """Tests for Grid dataclass."""

    def test_create_grid(self):
        points = [
            GridPoint(id="A1", x=0, y=0),
            GridPoint(id="A2", x=10, y=0),
            GridPoint(id="B1", x=0, y=10),
        ]
        g = Grid(
            grid_id="test_grid",
            name="Test Grid",
            units="mm",
            origin="bottom-left",
            points=points,
        )
        assert g.grid_id == "test_grid"
        assert len(g) == 3

    def test_rectangular_factory(self):
        g = Grid.rectangular(rows=3, cols=4, spacing=10.0)
        assert len(g) == 12
        assert g.grid_id == "rect_3x4"
        assert g.name == "3x4 Rectangular Grid"

        # Check point IDs (A1-A4, B1-B4, C1-C4)
        ids = g.point_ids()
        assert "A1" in ids
        assert "A4" in ids
        assert "C1" in ids
        assert "C4" in ids

    def test_circular_factory(self):
        g = Grid.circular(num_points=8, radius=50.0)
        # 8 perimeter + 1 center
        assert len(g) == 9
        assert g.get_point("C") is not None  # Center

    def test_circular_factory_no_center(self):
        g = Grid.circular(num_points=8, radius=50.0, include_center=False)
        assert len(g) == 8
        assert g.get_point("C") is None

    def test_line_factory(self):
        g = Grid.line(num_points=5, length=100.0)
        assert len(g) == 5
        # First and last points
        assert g[0].x == 0
        assert g[-1].x == 100.0

    def test_line_factory_vertical(self):
        g = Grid.line(num_points=5, length=100.0, orientation="vertical")
        assert len(g) == 5
        assert g[0].y == 0
        assert g[-1].y == 100.0

    def test_get_point(self):
        g = Grid.rectangular(rows=2, cols=2, spacing=10.0)
        p = g.get_point("A1")
        assert p is not None
        assert p.id == "A1"

    def test_get_point_not_found(self):
        g = Grid.rectangular(rows=2, cols=2, spacing=10.0)
        p = g.get_point("Z99")
        assert p is None

    def test_bounds(self):
        g = Grid.rectangular(rows=3, cols=4, spacing=10.0)
        min_x, min_y, max_x, max_y = g.bounds()
        assert min_x == 0
        assert min_y == 0
        assert max_x == 30.0  # 3 columns, 0-based = 0, 10, 20, 30
        assert max_y == 20.0  # 2 rows * 10

    def test_to_dict(self):
        g = Grid.rectangular(rows=2, cols=2, spacing=10.0)
        d = g.to_dict()
        assert d["grid_id"] == "rect_2x2"
        assert len(d["points"]) == 4

    def test_from_dict(self):
        original = Grid.rectangular(rows=2, cols=2, spacing=10.0)
        d = original.to_dict()
        restored = Grid.from_dict(d)
        assert restored.grid_id == original.grid_id
        assert len(restored) == len(original)

    def test_save_and_load(self, tmp_path):
        g = Grid.rectangular(rows=2, cols=3, spacing=15.0, name="Test Save")
        path = tmp_path / "grid.json"
        g.save(path)

        assert path.exists()

        loaded = Grid.load(path)
        assert loaded.grid_id == g.grid_id
        assert loaded.name == "Test Save"
        assert len(loaded) == 6


class TestPointProgress:
    """Tests for PointProgress dataclass."""

    def test_create_progress(self):
        p = PointProgress(point_id="A1")
        assert p.status == PointStatus.PENDING
        assert p.attempt_count == 0
        assert p.dominant_hz is None

    def test_to_dict(self):
        p = PointProgress(
            point_id="A1",
            status=PointStatus.PASSED,
            attempt_count=2,
            dominant_hz=185.5,
        )
        d = p.to_dict()
        assert d["status"] == "passed"
        assert d["dominant_hz"] == 185.5

    def test_from_dict(self):
        d = {
            "point_id": "B2",
            "status": "warned",
            "attempt_count": 1,
            "dominant_hz": 220.0,
            "last_updated": "2026-02-07T12:00:00Z",
        }
        p = PointProgress.from_dict(d)
        assert p.point_id == "B2"
        assert p.status == PointStatus.WARNED
        assert p.dominant_hz == 220.0


class TestGridSession:
    """Tests for GridSession."""

    @pytest.fixture
    def grid_2x2(self):
        return Grid.rectangular(rows=2, cols=2, spacing=10.0)

    def test_create_session(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        assert session.total_points == 4
        assert session.pending_count == 4
        assert session.completed_count == 0

    def test_progress_initialized(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        # All points should have progress entries
        for point in grid_2x2.points:
            assert point.id in session.progress
            assert session.progress[point.id].status == PointStatus.PENDING

    def test_mark_passed(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_passed("A1", dominant_hz=185.0)

        assert session.progress["A1"].status == PointStatus.PASSED
        assert session.progress["A1"].dominant_hz == 185.0
        assert session.completed_count == 1
        assert session.pending_count == 3

    def test_mark_warned(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_warned("A1", dominant_hz=190.0)

        assert session.progress["A1"].status == PointStatus.WARNED
        assert session.completed_count == 1

    def test_mark_failed(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_failed("A1")

        assert session.progress["A1"].status == PointStatus.FAILED
        assert session.failed_count == 1
        assert session.completed_count == 0

    def test_mark_skipped(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_skipped("A1")

        assert session.progress["A1"].status == PointStatus.SKIPPED
        assert session.completed_count == 1

    def test_reset_point(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_passed("A1", dominant_hz=185.0)
        session.reset_point("A1")

        assert session.progress["A1"].status == PointStatus.PENDING
        assert session.progress["A1"].dominant_hz is None

    def test_next_pending(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_passed("A1", 100.0)
        session.mark_passed("A2", 110.0)

        next_point = session.next_pending()
        assert next_point is not None
        assert next_point.id == "B1"

    def test_next_pending_none_left(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        for point in grid_2x2.points:
            session.mark_passed(point.id, 100.0)

        assert session.next_pending() is None

    def test_is_complete(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        assert not session.is_complete

        for point in grid_2x2.points:
            session.mark_passed(point.id, 100.0)

        assert session.is_complete
        assert session.completed_at is not None

    def test_is_not_complete_with_failed(self, grid_2x2):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_passed("A1", 100.0)
        session.mark_passed("A2", 110.0)
        session.mark_passed("B1", 120.0)
        session.mark_failed("B2")

        assert not session.is_complete

    def test_save_and_load(self, grid_2x2, tmp_path):
        session = GridSession(session_id="test_001", grid=grid_2x2)
        session.mark_passed("A1", 185.0)
        session.mark_warned("A2", 190.0)

        path = tmp_path / "session.json"
        session.save(path)

        loaded = GridSession.load(path)
        assert loaded.session_id == "test_001"
        assert loaded.progress["A1"].status == PointStatus.PASSED
        assert loaded.progress["A2"].status == PointStatus.WARNED
        assert loaded.progress["A2"].dominant_hz == 190.0


class TestGridEdgeCases:
    """Edge case tests."""

    def test_empty_grid(self):
        g = Grid(
            grid_id="empty",
            name="Empty",
            units="mm",
            origin="origin",
            points=[],
        )
        assert len(g) == 0
        assert g.bounds() == (0, 0, 0, 0)

    def test_single_point_line(self):
        g = Grid.line(num_points=1, length=0)
        assert len(g) == 1
        assert g[0].x == 0

    def test_point_iteration(self):
        g = Grid.rectangular(rows=2, cols=2, spacing=10.0)
        ids = [p.id for p in g]
        assert len(ids) == 4

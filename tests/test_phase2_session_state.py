"""
Tests for tap_tone_pi.phase2.session_state module.
"""

import json
import pytest
from pathlib import Path

from tap_tone_pi.phase2.session_state import SessionState, PointRecord
from tap_tone_pi.core.grid import Grid, GridPoint


@pytest.fixture
def sample_grid():
    """Create a small test grid."""
    points = [
        GridPoint(id="A1", x=0.0, y=0.0),
        GridPoint(id="A2", x=50.0, y=0.0),
        GridPoint(id="B1", x=0.0, y=50.0),
        GridPoint(id="B2", x=50.0, y=50.0),
    ]
    return Grid(units="mm", origin="center", points=points)


@pytest.fixture
def session_state(tmp_path, sample_grid):
    """Create a session state in a temp directory."""
    session_dir = tmp_path / "test_session"
    return SessionState.create(session_dir, sample_grid, grid_path="test_grid.json")


class TestSessionStateCreate:
    """Tests for SessionState.create()."""
    
    def test_creates_directory(self, tmp_path, sample_grid):
        """Should create session directory if it doesn't exist."""
        session_dir = tmp_path / "new_session"
        assert not session_dir.exists()
        
        SessionState.create(session_dir, sample_grid)
        
        assert session_dir.exists()
    
    def test_creates_state_file(self, tmp_path, sample_grid):
        """Should create session_state.json file."""
        session_dir = tmp_path / "test_session"
        SessionState.create(session_dir, sample_grid)
        
        state_file = session_dir / "session_state.json"
        assert state_file.exists()
    
    def test_initializes_all_points_pending(self, session_state):
        """All points should start as pending."""
        assert len(session_state.pending_points()) == 4
        assert len(session_state.completed_points()) == 0
    
    def test_preserves_point_order(self, session_state):
        """Point order should match grid order."""
        assert session_state.point_order == ["A1", "A2", "B1", "B2"]
    
    def test_sets_timestamps(self, session_state):
        """Should set started_at and last_updated timestamps."""
        assert session_state.started_at_utc
        assert session_state.last_updated_utc
        assert "T" in session_state.started_at_utc  # ISO format


class TestSessionStateLoad:
    """Tests for SessionState.load()."""
    
    def test_load_roundtrip(self, session_state):
        """Should load identical state after save."""
        session_state.mark_captured("A1", coherence=0.92)
        session_state.mark_failed("A2", reason="Test failure")
        session_state.save()
        
        loaded = SessionState.load(session_state.session_dir)
        
        assert loaded.points["A1"].status == "captured"
        assert loaded.points["A1"].coherence == 0.92
        assert loaded.points["A2"].status == "failed"
        assert loaded.points["A2"].failure_reason == "Test failure"
    
    def test_load_nonexistent_raises(self, tmp_path):
        """Should raise FileNotFoundError for nonexistent session."""
        with pytest.raises(FileNotFoundError):
            SessionState.load(tmp_path / "nonexistent")
    
    def test_exists_check(self, session_state, tmp_path):
        """SessionState.exists() should correctly detect state files."""
        assert SessionState.exists(session_state.session_dir)
        assert not SessionState.exists(tmp_path / "nonexistent")


class TestSessionStateOperations:
    """Tests for state modification operations."""
    
    def test_mark_captured(self, session_state):
        """mark_captured should update status and coherence."""
        session_state.mark_captured("A1", coherence=0.95, wav_path="A1/capture.wav")
        
        record = session_state.points["A1"]
        assert record.status == "captured"
        assert record.coherence == 0.95
        assert record.wav_path == "A1/capture.wav"
        assert record.attempt_count == 1
    
    def test_mark_captured_low_coherence_becomes_warning(self, session_state):
        """Low coherence capture should become warning status."""
        session_state.mark_captured("A1", coherence=0.5)  # Below 0.7 threshold
        
        assert session_state.points["A1"].status == "warning"
    
    def test_mark_failed(self, session_state):
        """mark_failed should update status and reason."""
        session_state.mark_failed("A1", reason="Audio timeout")
        
        record = session_state.points["A1"]
        assert record.status == "failed"
        assert record.failure_reason == "Audio timeout"
    
    def test_mark_skipped(self, session_state):
        """mark_skipped should update status."""
        session_state.mark_skipped("A1")
        assert session_state.points["A1"].status == "skipped"
    
    def test_reset_point(self, session_state):
        """reset_point should return to pending status."""
        session_state.mark_captured("A1", coherence=0.95)
        session_state.reset_point("A1")
        
        assert session_state.points["A1"].status == "pending"
        assert session_state.points["A1"].coherence is None
    
    def test_set_current(self, session_state):
        """set_current should update current_point."""
        session_state.set_current("B1")
        assert session_state.current_point == "B1"
    
    def test_set_current_invalid_point_raises(self, session_state):
        """set_current with invalid point should raise KeyError."""
        with pytest.raises(KeyError):
            session_state.set_current("INVALID")
    
    def test_attempt_count_increments(self, session_state):
        """Multiple captures should increment attempt_count."""
        session_state.mark_captured("A1", coherence=0.5)
        session_state.reset_point("A1")
        session_state.mark_captured("A1", coherence=0.9)
        
        assert session_state.points["A1"].attempt_count == 2


class TestSessionStateQueries:
    """Tests for state query methods."""
    
    def test_pending_points(self, session_state):
        """pending_points should return ordered list of pending points."""
        session_state.mark_captured("A1", coherence=0.9)
        session_state.mark_failed("A2")
        
        pending = session_state.pending_points()
        assert pending == ["B1", "B2"]
    
    def test_completed_points(self, session_state):
        """completed_points should include captured and warning."""
        session_state.mark_captured("A1", coherence=0.9)  # captured
        session_state.mark_captured("A2", coherence=0.5)  # warning
        
        completed = session_state.completed_points()
        assert "A1" in completed
        assert "A2" in completed
    
    def test_failed_points(self, session_state):
        """failed_points should return failed points only."""
        session_state.mark_failed("A1")
        session_state.mark_captured("A2", coherence=0.9)
        
        failed = session_state.failed_points()
        assert failed == ["A1"]
    
    def test_warning_points(self, session_state):
        """warning_points should return low-coherence points."""
        session_state.mark_captured("A1", coherence=0.5)  # warning
        session_state.mark_captured("A2", coherence=0.9)  # captured
        
        warnings = session_state.warning_points()
        assert warnings == ["A1"]
    
    def test_next_point(self, session_state):
        """next_point should return first pending point."""
        assert session_state.next_point() == "A1"
        
        session_state.mark_captured("A1", coherence=0.9)
        assert session_state.next_point() == "A2"
    
    def test_next_point_none_when_complete(self, session_state):
        """next_point should return None when all done."""
        for pid in ["A1", "A2", "B1", "B2"]:
            session_state.mark_captured(pid, coherence=0.9)
        
        assert session_state.next_point() is None
    
    def test_is_complete(self, session_state):
        """is_complete should check for pending and failed points."""
        assert not session_state.is_complete()
        
        for pid in ["A1", "A2", "B1", "B2"]:
            session_state.mark_captured(pid, coherence=0.9)
        
        assert session_state.is_complete()
    
    def test_is_complete_false_with_failures(self, session_state):
        """is_complete should be False if there are failures."""
        session_state.mark_captured("A1", coherence=0.9)
        session_state.mark_captured("A2", coherence=0.9)
        session_state.mark_captured("B1", coherence=0.9)
        session_state.mark_failed("B2")
        
        assert not session_state.is_complete()
    
    def test_progress_pct(self, session_state):
        """progress_pct should return correct percentage."""
        assert session_state.progress_pct() == 0.0
        
        session_state.mark_captured("A1", coherence=0.9)
        assert session_state.progress_pct() == 25.0
        
        session_state.mark_captured("A2", coherence=0.9)
        assert session_state.progress_pct() == 50.0
    
    def test_summary(self, session_state):
        """summary should return complete stats dict."""
        session_state.mark_captured("A1", coherence=0.9)
        session_state.mark_captured("A2", coherence=0.5)  # warning
        session_state.mark_failed("B1")
        
        summary = session_state.summary()
        
        assert summary["total"] == 4
        assert summary["captured"] == 1
        assert summary["warning"] == 1
        assert summary["failed"] == 1
        assert summary["pending"] == 1
        assert summary["progress_pct"] == 50.0
        assert summary["is_complete"] is False


class TestPointRecord:
    """Tests for PointRecord dataclass."""
    
    def test_to_dict(self):
        """to_dict should exclude None values."""
        record = PointRecord(point_id="A1", status="captured", coherence=0.95)
        d = record.to_dict()
        
        assert d["point_id"] == "A1"
        assert d["coherence"] == 0.95
        assert "failure_reason" not in d  # None excluded
    
    def test_from_dict(self):
        """from_dict should reconstruct record."""
        d = {
            "point_id": "A1",
            "status": "warning",
            "coherence": 0.6,
            "attempt_count": 2,
        }
        record = PointRecord.from_dict(d)
        
        assert record.point_id == "A1"
        assert record.status == "warning"
        assert record.coherence == 0.6
        assert record.attempt_count == 2


class TestAtomicSave:
    """Tests for atomic save behavior."""
    
    def test_save_is_atomic(self, session_state):
        """Save should use atomic write pattern."""
        session_state.mark_captured("A1", coherence=0.9)
        session_state.save()
        
        # Verify state file exists and is valid
        state_file = session_state.session_dir / "session_state.json"
        assert state_file.exists()
        
        with open(state_file) as f:
            data = json.load(f)
        
        assert data["schema_version"] == "session_state_v1"
    
    def test_no_temp_file_left_behind(self, session_state):
        """No .tmp file should remain after save."""
        session_state.save()
        
        tmp_file = session_state.session_dir / "session_state.tmp"
        assert not tmp_file.exists()


class TestGridMismatchValidation:
    """Tests for grid mismatch detection on resume."""
    
    def test_matching_grid_returns_none(self, sample_grid, session_state):
        """Matching grid should return None (no error)."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        result = _check_grid_mismatch(session_state, sample_grid)
        assert result is None
    
    def test_different_point_count_detected(self, session_state):
        """Different point count should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        # Create grid with different point count
        smaller_grid = Grid(
            units="mm",
            origin="center",
            points=[
                GridPoint(id="A1", x=0.0, y=0.0),
                GridPoint(id="A2", x=50.0, y=0.0),
            ]
        )
        
        result = _check_grid_mismatch(session_state, smaller_grid)
        
        assert result is not None
        assert "Point count mismatch" in result
    
    def test_different_point_ids_detected(self, session_state):
        """Different point IDs should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        # Create grid with different point IDs
        different_grid = Grid(
            units="mm",
            origin="center",
            points=[
                GridPoint(id="X1", x=0.0, y=0.0),
                GridPoint(id="X2", x=50.0, y=0.0),
                GridPoint(id="Y1", x=0.0, y=50.0),
                GridPoint(id="Y2", x=50.0, y=50.0),
            ]
        )
        
        result = _check_grid_mismatch(session_state, different_grid)
        
        assert result is not None
        assert "Points in session but not in grid" in result or "Points in grid but not in session" in result
    
    def test_different_point_order_detected(self, session_state):
        """Different point order should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        # Create grid with same points but different order
        reordered_grid = Grid(
            units="mm",
            origin="center",
            points=[
                GridPoint(id="B2", x=50.0, y=50.0),
                GridPoint(id="B1", x=0.0, y=50.0),
                GridPoint(id="A2", x=50.0, y=0.0),
                GridPoint(id="A1", x=0.0, y=0.0),
            ]
        )
        
        result = _check_grid_mismatch(session_state, reordered_grid)
        
        assert result is not None
        assert "order differs" in result

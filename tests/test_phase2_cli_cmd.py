"""
Tests for tap_tone_pi.cli.phase2_cmd module.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import argparse

from tap_tone_pi.core.grid import Grid, GridPoint
from tap_tone_pi.phase2.session_state import SessionState


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
def session_with_grid(tmp_path, sample_grid):
    """Create a session directory with grid and state."""
    session_dir = tmp_path / "test_session"
    
    # Create session state
    state = SessionState.create(session_dir, sample_grid, grid_path="test_grid.json")
    
    # Save grid
    grid_data = {
        "units": sample_grid.units,
        "origin": sample_grid.origin,
        "points": [{"id": p.id, "x": p.x, "y": p.y} for p in sample_grid.points]
    }
    with open(session_dir / "grid.json", "w") as f:
        json.dump(grid_data, f)
    
    return session_dir, state, sample_grid


class TestCheckGridMismatch:
    """Tests for _check_grid_mismatch function."""
    
    def test_matching_grid_returns_none(self, sample_grid, tmp_path):
        """Matching grid should return None (no error)."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        session_dir = tmp_path / "session"
        state = SessionState.create(session_dir, sample_grid)
        
        result = _check_grid_mismatch(state, sample_grid)
        
        assert result is None
    
    def test_point_count_mismatch(self, sample_grid, tmp_path):
        """Different point count should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        session_dir = tmp_path / "session"
        state = SessionState.create(session_dir, sample_grid)
        
        # Create smaller grid
        smaller_grid = Grid(
            units="mm",
            origin="center",
            points=[GridPoint(id="A1", x=0.0, y=0.0)]
        )
        
        result = _check_grid_mismatch(state, smaller_grid)
        
        assert result is not None
        assert "Point count mismatch" in result
        assert "4" in result  # session has 4
        assert "1" in result  # grid has 1
    
    def test_missing_point_ids(self, sample_grid, tmp_path):
        """Missing point IDs should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        session_dir = tmp_path / "session"
        state = SessionState.create(session_dir, sample_grid)
        
        # Create grid with different IDs
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
        
        result = _check_grid_mismatch(state, different_grid)
        
        assert result is not None
        assert "Points in session but not in grid" in result or "Points in grid but not in session" in result
    
    def test_point_order_mismatch(self, sample_grid, tmp_path):
        """Different point order should be detected."""
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        session_dir = tmp_path / "session"
        state = SessionState.create(session_dir, sample_grid)
        
        # Create grid with reversed order
        reversed_grid = Grid(
            units="mm",
            origin="center",
            points=[
                GridPoint(id="B2", x=50.0, y=50.0),
                GridPoint(id="B1", x=0.0, y=50.0),
                GridPoint(id="A2", x=50.0, y=0.0),
                GridPoint(id="A1", x=0.0, y=0.0),
            ]
        )
        
        result = _check_grid_mismatch(state, reversed_grid)
        
        assert result is not None
        assert "order differs" in result


class TestShowProgress:
    """Tests for _show_progress function."""
    
    def test_no_progress_mode_uses_compact(self, sample_grid, capsys):
        """--no-progress should use compact output."""
        from tap_tone_pi.cli.phase2_cmd import _show_progress
        from tap_tone_pi.phase2.grid_display import GridDisplay
        
        display = GridDisplay(sample_grid, use_color=False)
        
        _show_progress(display, no_progress=True)
        
        captured = capsys.readouterr()
        
        # Compact mode should be single line with progress bar
        assert "█" in captured.out or "░" in captured.out
        # Should NOT have the full grid header
        assert "Phase 2 Grid Progress" not in captured.out
    
    def test_progress_mode_uses_full_display(self, sample_grid, capsys):
        """Normal mode should use full ANSI display."""
        from tap_tone_pi.cli.phase2_cmd import _show_progress
        from tap_tone_pi.phase2.grid_display import GridDisplay
        
        display = GridDisplay(sample_grid, use_color=False)
        
        _show_progress(display, no_progress=False)
        
        captured = capsys.readouterr()
        
        # Full mode should have header
        assert "Phase 2 Grid Progress" in captured.out
        # Full mode should have legend
        assert "captured" in captured.out


class TestArgumentParser:
    """Tests for CLI argument parsing."""
    
    def test_no_progress_flag_exists(self):
        """--no-progress flag should be recognized."""
        from tap_tone_pi.cli.phase2_cmd import add_phase2_subparser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_phase2_subparser(subparsers)
        
        # Parse with --no-progress
        args = parser.parse_args(["phase2", "run", "--grid", "test.json", "--no-progress"])
        
        assert args.no_progress is True
    
    def test_no_progress_default_false(self):
        """--no-progress should default to False."""
        from tap_tone_pi.cli.phase2_cmd import add_phase2_subparser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_phase2_subparser(subparsers)
        
        args = parser.parse_args(["phase2", "run", "--grid", "test.json"])
        
        assert args.no_progress is False
    
    def test_coherence_threshold_configurable(self):
        """--coherence-threshold should be configurable."""
        from tap_tone_pi.cli.phase2_cmd import add_phase2_subparser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_phase2_subparser(subparsers)
        
        args = parser.parse_args(["phase2", "run", "--grid", "test.json", "--coherence-threshold", "0.8"])
        
        assert args.coherence_threshold == 0.8
    
    def test_coherence_threshold_default(self):
        """--coherence-threshold should default to 0.7."""
        from tap_tone_pi.cli.phase2_cmd import add_phase2_subparser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_phase2_subparser(subparsers)
        
        args = parser.parse_args(["phase2", "run", "--grid", "test.json"])
        
        assert args.coherence_threshold == 0.7
    
    def test_synthetic_flag(self):
        """--synthetic flag should be recognized."""
        from tap_tone_pi.cli.phase2_cmd import add_phase2_subparser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_phase2_subparser(subparsers)
        
        args = parser.parse_args(["phase2", "run", "--grid", "test.json", "--synthetic"])
        
        assert args.synthetic is True


class TestResumeValidation:
    """Tests for resume with grid validation."""
    
    def test_resume_with_matching_grid_succeeds(self, session_with_grid, capsys):
        """Resume should succeed when grid matches."""
        session_dir, state, grid = session_with_grid
        
        # Mark some progress
        state.mark_captured("A1", coherence=0.9)
        state.save()
        
        # Check grid mismatch
        from tap_tone_pi.cli.phase2_cmd import _check_grid_mismatch
        
        result = _check_grid_mismatch(state, grid)
        
        assert result is None  # No mismatch


class TestStatusCommand:
    """Tests for phase2 status command."""
    
    def test_status_shows_summary(self, session_with_grid, capsys):
        """Status command should show session summary."""
        session_dir, state, grid = session_with_grid
        
        # Mark some progress
        state.mark_captured("A1", coherence=0.95)
        state.mark_captured("A2", coherence=0.55)  # warning
        state.mark_failed("B1", reason="Test failure")
        state.save()
        
        # Create args
        args = argparse.Namespace(session=str(session_dir))
        
        # Run status
        from tap_tone_pi.cli.phase2_cmd import cmd_phase2_status
        
        result = cmd_phase2_status(args)
        
        assert result == 0
        
        captured = capsys.readouterr()
        
        # Should show counts
        assert "Captured: 1" in captured.out
        assert "Warnings: 1" in captured.out
        assert "Failed: 1" in captured.out
        assert "Pending: 1" in captured.out
        
        # Should show failed point details
        assert "B1" in captured.out
        assert "Test failure" in captured.out

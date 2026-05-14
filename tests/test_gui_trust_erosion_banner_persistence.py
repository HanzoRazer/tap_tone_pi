"""Tests for TRUST_EROSION banner session-persistent dismissal (PR #13 Seg 2)."""

from pathlib import Path

from tap_tone_pi.gui.advisory_state import (
    is_trust_banner_dismissed,
    mark_trust_banner_dismissed,
)


def test_trust_banner_dismissal_persists(tmp_path: Path):
    session_dir = tmp_path / "sess"
    session_dir.mkdir()

    assert is_trust_banner_dismissed(session_dir) is False
    mark_trust_banner_dismissed(session_dir)
    assert is_trust_banner_dismissed(session_dir) is True


def test_trust_banner_coexists_with_advisory_state(tmp_path: Path):
    """mark_trust_banner_dismissed must not clobber existing advisory state."""
    from tap_tone_pi.gui.advisory_state import has_responded, mark_responded

    session_dir = tmp_path / "sess"
    session_dir.mkdir()

    mark_responded(session_dir, directive_id="d1")
    assert has_responded(session_dir) is True

    mark_trust_banner_dismissed(session_dir)
    assert is_trust_banner_dismissed(session_dir) is True
    # advisory state must still be intact
    assert has_responded(session_dir) is True


def test_trust_banner_false_when_no_session_dir(tmp_path: Path):
    """Non-existent session dir → False, never raises."""
    assert is_trust_banner_dismissed(tmp_path / "nonexistent") is False

"""Tests for show_directive_history session-local persistence (PR #15.1)."""

from pathlib import Path

from tap_tone_pi.gui.advisory_state import (
    get_show_directive_history,
    set_show_directive_history,
)


def test_round_trip_true(tmp_path: Path):
    sess = tmp_path / "sess"
    sess.mkdir()

    assert get_show_directive_history(sess, default=None) is None
    set_show_directive_history(sess, True)
    assert get_show_directive_history(sess, default=None) is True


def test_round_trip_false(tmp_path: Path):
    sess = tmp_path / "sess"
    sess.mkdir()

    set_show_directive_history(sess, True)
    set_show_directive_history(sess, False)
    assert get_show_directive_history(sess, default=None) is False


def test_default_when_missing(tmp_path: Path):
    """No persisted value → returns the caller-supplied default."""
    assert get_show_directive_history(tmp_path / "nope", default=False) is False
    assert get_show_directive_history(tmp_path / "nope", default=None) is None


def test_coexists_with_other_state(tmp_path: Path):
    """Setting toggle must not clobber advisory_state neighbours."""
    from tap_tone_pi.gui.advisory_state import (
        has_responded,
        mark_responded,
        is_trust_banner_dismissed,
        mark_trust_banner_dismissed,
    )

    sess = tmp_path / "sess"
    sess.mkdir()

    mark_responded(sess, directive_id="d1")
    mark_trust_banner_dismissed(sess)
    set_show_directive_history(sess, True)

    assert has_responded(sess) is True
    assert is_trust_banner_dismissed(sess) is True
    assert get_show_directive_history(sess, default=None) is True

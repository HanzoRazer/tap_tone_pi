"""Tests for ``ttp measure --list-directive-events`` (PR #14 Seg 1)."""
import argparse
import json
from pathlib import Path
from unittest import mock

from tap_tone_pi.agentic.spine.directive_history import load_directive_events


def _make_args(out: str) -> argparse.Namespace:
    """Build a minimal Namespace that satisfies cmd_measure up to the listing path."""
    return argparse.Namespace(
        out=out,
        device=0,
        sample_rate=48000,
        list_directive_events=True,
        directive_events_limit=10,
    )


def test_cmd_measure_lists_events(tmp_path: Path, capsys):
    sess = tmp_path / "sess"
    sess.mkdir()
    p = sess / "events.jsonl"
    ev = {
        "event_type": "attention_acknowledged",
        "timestamp": "t1",
        "payload": {"directive_id": "d1"},
        "source": {"component": "cli"},
    }
    p.write_text(json.dumps(ev) + "\n", encoding="utf-8")

    from tap_tone_pi.cli.main import cmd_measure

    # Patch FTUE config I/O so cmd_measure doesn't touch real user config
    with mock.patch("tap_tone_pi.cli.main.Path"):
        # We need Path to work for session_dir, so only patch config calls
        pass

    with (
        mock.patch("tap_tone_pi.core.user_config.load_config", return_value=None),
        mock.patch("tap_tone_pi.core.user_config.save_config"),
        mock.patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None),
    ):
        rc = cmd_measure(_make_args(out=str(sess)))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Directive events:" in out
    assert "attention_acknowledged" in out
    assert "directive_id=d1" in out
    assert "component=cli" in out


def test_cmd_measure_lists_none_when_empty(tmp_path: Path, capsys):
    sess = tmp_path / "sess"
    sess.mkdir()

    from tap_tone_pi.cli.main import cmd_measure

    with (
        mock.patch("tap_tone_pi.core.user_config.load_config", return_value=None),
        mock.patch("tap_tone_pi.core.user_config.save_config"),
        mock.patch("tap_tone_pi.core.user_config.get_saved_device", return_value=None),
    ):
        rc = cmd_measure(_make_args(out=str(sess)))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Directive events: none" in out

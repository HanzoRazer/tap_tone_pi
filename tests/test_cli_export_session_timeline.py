"""CLI smoke test for ``ttp export-session-timeline`` (PR #16 Seg 1)."""
import argparse
from pathlib import Path

from tap_tone_pi.cli.main import cmd_export_session_timeline


def _make_args(session: str, out: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(session=session, out=out)


def test_cli_export_session_timeline_writes(tmp_path: Path, capsys):
    sess = tmp_path / "session_003"
    sess.mkdir()

    rc = cmd_export_session_timeline(_make_args(session=str(sess)))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Wrote:" in out


def test_cli_export_session_timeline_missing_dir(tmp_path: Path, capsys):
    rc = cmd_export_session_timeline(
        _make_args(session=str(tmp_path / "nonexistent")),
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "No session timeline exported" in out
